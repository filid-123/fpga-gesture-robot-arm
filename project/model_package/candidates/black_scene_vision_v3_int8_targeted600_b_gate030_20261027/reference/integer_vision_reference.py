"""Full uint8/int8/int32 CNN reference for the frozen B + six-class release."""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
import sys

import numpy as np

INT32_MIN=-(1<<31);INT32_MAX=(1<<31)-1
CLASSES=('background','one','two','three','fist','palm')


def wrap32(values):
    low=np.asarray(values,dtype=np.int64)&0xFFFFFFFF
    return np.where(low>=0x80000000,low-(1<<32),low).astype(np.int32)


def round_shift(values,M,shift):
    product=np.asarray(values,dtype=np.int64)*np.asarray(M,dtype=np.int64)
    if np.ndim(shift)==0:
        s=int(shift);return product if s==0 else (product+(1<<(s-1)))>>s
    shifts=np.asarray(shift,dtype=np.int64)
    bias=np.where(shifts>0,np.left_shift(np.int64(1),np.maximum(0,shifts-1)),0)
    return (product+bias)>>shifts


def requant(acc,M,shift):return np.clip(round_shift(wrap32(acc),M,shift),0,255).astype(np.uint8)


def pool(x):
    c,h,w=x.shape
    if h%2 or w%2:raise ValueError('Pool shape must be even')
    return x.reshape(c,h//2,2,w//2,2).max(axis=(2,4))


def convolution(x,w,b,dilation=1,oracle=False):
    """int64 exact sum followed by signed32 wrap, same modulo as MAC wrapping."""
    x=np.asarray(x,dtype=np.uint8);w=np.asarray(w,dtype=np.int8);b=np.asarray(b,dtype=np.int32)
    if x.ndim!=3 or w.ndim!=4 or w.shape[1]!=x.shape[0] or w.shape[2:]!=(3,3):raise ValueError('Invalid convolution dimensions')
    pad=int(dilation);p=np.pad(x.astype(np.int64),((0,0),(pad,pad),(pad,pad)))
    if oracle:
        acc=np.broadcast_to(b.astype(np.int64)[:,None,None],(w.shape[0],x.shape[1],x.shape[2])).copy()
        # Independent coordinate/tap oracle, unlike the window-based main path.
        for ky in range(3):
            for kx in range(3):
                samples=p[:,ky*pad:ky*pad+x.shape[1],kx*pad:kx*pad+x.shape[2]]
                acc+=np.einsum('ihw,oi->ohw',samples,w[:,:,ky,kx].astype(np.int64),dtype=np.int64,optimize=True)
    else:
        windows=np.lib.stride_tricks.sliding_window_view(p,(2*pad+1,2*pad+1),axis=(1,2))[:,:, :,::pad,::pad]
        acc=np.einsum('ihwkl,oikl->ohw',windows,w.astype(np.int64),dtype=np.int64,optimize=True)
        acc+=b.astype(np.int64)[:,None,None]
    return wrap32(acc),acc


def dense(x,w,b,oracle=False):
    if oracle:
        flat=np.asarray(x,dtype=np.uint8).reshape(-1)
        full=np.array([sum(int(v)*int(q) for v,q in zip(flat,row))+int(bias)
                       for row,bias in zip(np.asarray(w,dtype=np.int8),np.asarray(b,dtype=np.int32))],dtype=np.int64)
    else:
        full=np.asarray(w,dtype=np.int8).astype(np.int64)@np.asarray(x,dtype=np.uint8).reshape(-1).astype(np.int64)
        full+=np.asarray(b,dtype=np.int32).astype(np.int64)
    return wrap32(full),full


def forward_locator(image,p,oracle=False):
    current=np.asarray(image,dtype=np.uint8).reshape(1,128,128)
    stages={'input_u8':current.copy()};ranges={}
    def conv(name,x,d=1):
        raw,full=convolution(x,p[name+'_weight_q'],p[name+'_bias_q'],d,oracle)
        stages[name+'_acc_i32']=raw
        ranges[name]={'min':int(full.min()),'max':int(full.max()),'overflow_count':int(((full<INT32_MIN)|(full>INT32_MAX)).sum())}
        return raw
    def activate(name,raw):
        shifted=round_shift(raw,int(p[name+'_M']),int(p[name+'_shift']))
        activated=np.clip(shifted,0,255).astype(np.uint8);stages[name+'_u8']=activated
        ranges[name]['high_saturation_count']=int((shifted>255).sum())
        ranges[name]['activation_elements']=int(shifted.size)
        return activated
    for name in ('conv1','conv2','conv3'):
        current=pool(activate(name,conv(name,current)));stages[name+'_pool_u8']=current
    f3=current
    g1=activate('g1',conv('g1',f3,2));residual=conv('g2',g1,5)
    f4=activate('conv4',conv('conv4',f3));base=conv('conv5',f4)
    aligned=round_shift(residual,p['residual_M'][:,None,None],p['residual_shift'][:,None,None])
    summed=base[1:].astype(np.int64)+aligned
    result=np.concatenate((base[:1],wrap32(summed)),axis=0)
    stages.update(residual_aligned_i64=aligned,residual_sum_i64=summed,locator_fused_i32=result)
    ranges['fusion']={'min':int(summed.min()),'max':int(summed.max()),'overflow_count':int(((summed<INT32_MIN)|(summed>INT32_MAX)).sum())}
    return result,stages,ranges


def forward_classifier(image,p,oracle=False):
    current=np.asarray(image,dtype=np.uint8).reshape(1,32,32);stages={'input_u8':current.copy()};ranges={}
    for name in ('conv1','conv2','conv3'):
        raw,full=convolution(current,p[name+'_weight_q'],p[name+'_bias_q'],1,oracle)
        shifted=round_shift(raw,int(p[name+'_M']),int(p[name+'_shift']))
        activated=np.clip(shifted,0,255).astype(np.uint8);current=pool(activated)
        stages.update({name+'_acc_i32':raw,name+'_u8':activated,name+'_pool_u8':current})
        ranges[name]={'min':int(full.min()),'max':int(full.max()),'overflow_count':int(((full<INT32_MIN)|(full>INT32_MAX)).sum()),
            'high_saturation_count':int((shifted>255).sum()),'activation_elements':int(shifted.size)}
    raw,full=dense(current,p['fc1_weight_q'],p['fc1_bias_q'],oracle);hidden=requant(raw,int(p['fc1_M']),int(p['fc1_shift']))
    stages.update(fc1_acc_i32=raw,fc1_u8=hidden)
    shifted=round_shift(raw,int(p['fc1_M']),int(p['fc1_shift']))
    ranges['fc1']={'min':int(full.min()),'max':int(full.max()),'overflow_count':int(((full<INT32_MIN)|(full>INT32_MAX)).sum()),
        'high_saturation_count':int((shifted>255).sum()),'activation_elements':int(shifted.size)}
    logits,full=dense(hidden,p['fc2_weight_q'],p['fc2_bias_q'],oracle);stages['fc2_logits_i32']=logits
    ranges['fc2']={'min':int(full.min()),'max':int(full.max()),'overflow_count':int(((full<INT32_MIN)|(full>INT32_MAX)).sum())}
    return logits,stages,ranges


def decode_locator(output,p,source_width=640,source_height=480):
    flat=int(np.argmax(output[0].reshape(-1)));y,x=divmod(flat,16)
    scales=p['conv5_output_scale'];q=output[:,y,x]
    values=q.astype(np.float64)*scales;cx=8*(x+.5+values[1]);cy=8*(y+.5+values[2])
    width=128*np.clip(values[3],0,1);height=128*np.clip(values[4],0,1)
    box128=np.clip([cx-width/2,cy-height/2,cx+width/2,cy+height/2],0,128)
    scale=min(128/source_width,128/source_height)
    padx=(128-round(source_width*scale))//2;pady=(128-round(source_height*scale))//2
    box=(box128-np.array([padx,pady,padx,pady]))/scale
    box=np.minimum(np.maximum(box,0),[source_width,source_height,source_width,source_height])
    raw_conf=int(q[0]);detected=raw_conf>=int(p['confidence_threshold_i32'])
    return {'peak_xy':[x,y],'confidence_raw_i32':raw_conf,'confidence_logit':float(values[0]),
        'confidence':float(1/(1+math.exp(-float(np.clip(values[0],-700,700))))),'detected':bool(detected),
        'bbox_source':box.tolist(),'regression_float':values[1:].tolist()}


class IntegerVision:
    def __init__(self,package_root,stabilize=False):
        self.root=Path(package_root)
        self.locator=dict(np.load(self.root/'quantized/locator/parameters.npz',allow_pickle=False))
        self.classifier=dict(np.load(self.root/'quantized/classifier/parameters.npz',allow_pickle=False))
        sys.path.insert(0,str(self.root/'reference'))
        from locator_temporal_pc import GeometryStabilizer
        self.stabilizer=GeometryStabilizer() if stabilize else None

    def classify_input(self,image):
        logits,_,_=forward_classifier(image,self.classifier)
        k=int(np.argmax(logits))
        return {'class_id':k,'class':CLASSES[k],'logits_i32':logits.tolist()}

    def predict(self,frame,timestamp=None):
        from preprocessing import preprocess_bgr_to_locator_input
        return self.predict_small(preprocess_bgr_to_locator_input(frame),timestamp)

    def predict_small(self,small,timestamp=None):
        from preprocessing import clipped_int_box,square_roi_from_source_box,classifier_from_small,small_roi_descriptor
        small=np.asarray(small)
        if small.dtype!=np.uint8 or small.shape!=(128,128):raise ValueError('Expected128x128uint8')
        if small[:16].any() or small[112:].any():raise ValueError('Letterbox rows must be zero')
        raw,_,_=forward_locator(small,self.locator)
        decoded=decode_locator(raw,self.locator,640,480)
        effective=decoded['bbox_source'];filtered=None
        if self.stabilizer is not None:
            if timestamp is None:raise ValueError('Acquisition timestamp seconds required')
            filtered=self.stabilizer.update(effective,decoded['detected'],640,480,timestamp)
            effective=filtered['effective_box']
        roi=None;classification=None;descriptor=None
        if decoded['detected'] and decoded['bbox_source'][2]>decoded['bbox_source'][0] and decoded['bbox_source'][3]>decoded['bbox_source'][1]:
            roi=square_roi_from_source_box(clipped_int_box(effective,640,480),640,480,.18)
            descriptor=small_roi_descriptor(roi)
            classification=self.classify_input(classifier_from_small(small,roi))
        return {**decoded,'effective_bbox_source':list(effective),'roi_source':list(roi) if roi else None,
                'small_roi':descriptor,'classifier':classification,'stabilizer':filtered,
                'fresh_target_gesture':bool(classification and classification['class_id']!=0)}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--verify',action='store_true')
    parser.add_argument('--image',type=Path);parser.add_argument('--small-npy',type=Path);args=parser.parse_args()
    root=Path(__file__).resolve().parent.parent
    sys.path.insert(0,str(root/'reference'))
    from preprocessing import read_bgr_image
    from verify_delivery import verify_hashes
    verify_hashes(root)
    runtime=IntegerVision(root)
    if args.verify:
        index=json.loads((root/'golden_integer/index.json').read_text(encoding='utf-8'))
        for item in index['samples']:
            expected=np.load(root/item['vectors'],allow_pickle=False)
            _,ls,_=forward_locator(expected['locator_input_u8'],runtime.locator)
            _,cs,_=forward_classifier(expected['classifier_input_u8'],runtime.classifier)
            _,lo,_=forward_locator(expected['locator_input_u8'],runtime.locator,oracle=True)
            _,co,_=forward_classifier(expected['classifier_input_u8'],runtime.classifier,oracle=True)
            for name,value in ls.items():
                assert np.array_equal(value,expected['locator_'+name]),name
                assert np.array_equal(value,lo[name]),'tap oracle '+name
            for name,value in cs.items():
                assert np.array_equal(value,expected['classifier_'+name]),name
                assert np.array_equal(value,co[name]),'tap oracle '+name
            actual=runtime.predict(read_bgr_image(root/item['image']))
            assert actual['peak_xy']==item['pipeline']['peak_xy']
            assert actual['detected']==item['pipeline']['detected']
            assert actual['roi_source']==item['pipeline']['roi_source']
            assert actual['classifier']==item['pipeline']['classifier']
            folder=root/'golden_integer'/item['id']
            stream=[int(line,16) for line in (folder/'locator_output_stream_addr12_data32.mem').read_text().splitlines()]
            for j,word in enumerate(stream):
                cell,channel=divmod(j,5)
                assert word>>32==channel*256+cell
                assert word&0xFFFFFFFF==int(ls['locator_fused_i32'][channel,cell//16,cell%16])&0xFFFFFFFF
            def bank_bytes(name,bank):
                words=np.array([int(line,16) for line in (folder/'banks'/f'{name}_bank{bank}.mem').read_text().splitlines()],dtype='<u4')
                return np.frombuffer(words.tobytes(),dtype=np.uint8)
            act0=np.stack([bank_bytes('act0_F3_and_residual',b) for b in range(8)])
            for ch in range(16):assert np.array_equal(act0[ch%8,ch//8*256:(ch//8+1)*256],ls['conv3_pool_u8'][ch].reshape(-1))
            residual=np.zeros((4,256),dtype=np.int64)
            for k in range(4):
                for b in range(4):residual[k]|=act0[2*k+(b>>1),0x200+(b&1)*256:0x300+(b&1)*256].astype(np.int64)<<(8*b)
            assert np.array_equal(wrap32(residual).reshape(4,16,16),ls['g2_acc_i32'])
            for name,key,channels in (('act1_G1','g1_u8',8),('act1_F4','conv4_u8',24)):
                banks=np.stack([bank_bytes(name,b) for b in range(8)])
                for ch in range(channels):assert np.array_equal(banks[ch%8,ch//8*256:(ch//8+1)*256],ls[key][ch].reshape(-1))
        print(json.dumps({'status':'PASS_COMPLETE_INTEGER_CNN_GOLDENS','samples':len(index['samples']),
            'independent_tap_and_scalar_dense_oracles':True,'bank_and_output_stream_exact':True,'RTL_simulated':False}))
    elif args.image:print(json.dumps(runtime.predict(read_bgr_image(args.image)),ensure_ascii=False,indent=2))
    elif args.small_npy:print(json.dumps(runtime.predict_small(np.load(args.small_npy,allow_pickle=False)),ensure_ascii=False,indent=2))
    else:parser.error('Choose --verify, --image or --small-npy')


if __name__=='__main__':main()
