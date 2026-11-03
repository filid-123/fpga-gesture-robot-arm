"""TRAIN-only static PTQ for both frozen networks, including B residual ROM."""
from __future__ import annotations
import ast
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys

import numpy as np
import torch

ROOT=Path(__file__).resolve().parent.parent
FLOAT=ROOT/'handoff/black_scene_vision_v1_20261013'
OUT=ROOT/'quantized_black_scene_v1_20261013'
LOC=ROOT/'hand_locator';CLS=ROOT/'gesture_CNN'
sys.path.insert(0,str(FLOAT/'reference'))
from pc_reference import VisionReference
from integer_vision_reference import forward_locator,forward_classifier,decode_locator


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def read(p):return json.loads(p.read_text(encoding='utf-8'))


def write(p,obj):p.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def away(x):
    x=np.asarray(x,dtype=np.float64);return np.where(x>=0,np.floor(x+.5),np.ceil(x-.5))


def multiplier(ratio,fixed31=False):
    for s in ((31,) if fixed31 else range(31,-1,-1)):
        m=int(math.floor(ratio*(1<<s)+.5))
        if 1<=m<=(1<<31)-1:return m,s
    raise ValueError(f'Cannot represent multiplier {ratio}, fixed31={fixed31}')


def quant_layer(weight,bias,input_scale,output_scale=None,per_channel=False,fixed31=False):
    w=weight.detach().numpy().astype(np.float64);b=bias.detach().numpy().astype(np.float64)
    axes=tuple(range(1,w.ndim))
    sw=np.maximum(np.max(np.abs(w),axis=axes)/127.,1e-12) if per_channel else max(float(np.max(np.abs(w)))/127.,1e-12)
    broadcast=np.reshape(sw,(-1,)+(1,)*(w.ndim-1)) if per_channel else sw
    wq=np.clip(away(w/broadcast),-127,127).astype(np.int8)
    sb=input_scale*sw;bq=away(b/sb)
    if np.any(np.abs(bq)>(1<<31)-1):raise OverflowError('Bias does not fit signed32')
    parameters={'weight_q':wq,'bias_q':bq.astype(np.int32),'weight_scale':np.asarray(sw,dtype=np.float64),
        'bias_scale':np.asarray(sb,dtype=np.float64)}
    info={'weight_shape':list(w.shape),'weight_granularity':'per_output_channel' if per_channel else 'per_layer',
        'weight_scale':np.asarray(sw).tolist(),'bias_scale':np.asarray(sb).tolist(),'input_scale':float(input_scale)}
    if output_scale is not None:
        m,s=multiplier(float(sb/output_scale),fixed31)
        parameters.update(M=np.asarray(m,dtype=np.int32),shift=np.asarray(s,dtype=np.uint32),output_scale=np.asarray(output_scale,dtype=np.float64))
        info.update(M=m,shift=s,output_scale=float(output_scale))
    else:info['output']='raw signed32 accumulator, no ReLU or requant'
    return parameters,info


def read_legacy_descriptor_helpers():
    path=CLS/'export_quantized_model_six_class.py';source=path.read_text(encoding='utf-8');tree=ast.parse(source)
    names=('pack_descriptor_words','build_layer_descriptors')
    namespace={'TYPE_CONV':0,'TYPE_POOL':1,'TYPE_DENSE':2,'ACT_PING':0,'ACT_PONG':1,'ACT_INPUT':2}
    text='\n\n'.join(ast.get_source_segment(source,n) for name in names for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
    exec(compile(text,str(path),'exec'),namespace)
    return namespace


def write_mem(path,blob):
    if len(blob)%4:raise ValueError('Word MEM requires4-byte aligned length')
    words=np.frombuffer(blob,dtype='<u4')
    path.write_text(''.join(f'{int(w):08X}\n' for w in words),encoding='ascii')


def main():
    if OUT.exists():raise FileExistsError('Keep prior export; no overwrite')
    torch.set_num_threads(2)
    runtime=VisionReference();manifest=read(FLOAT/'manifest.json')
    for key in ('locator','classifier'):
        if sha(FLOAT/manifest[key]['path'])!=manifest[key]['sha256']:raise ValueError('Frozen model changed')
    sys.path.insert(0,str(LOC))
    from locator_data import LocatorDataset
    ld=LOC/'datasets/locator_black_scene_only_v1_20261013'
    cd=CLS/'datasets/classifier_black_scene_only_v1_20261013'
    # Verify data artifacts and original raw images. Historical live-code
    # source hashes are not required after deliberate post-training filtering.
    bindings={}
    for d in (ld,cd):
        prep=read(d/'preparation_report.json')
        for p,h in prep['artifact_sha256'].items():
            if sha(Path(p))!=h:raise ValueError('Prepared data artifact changed')
            bindings[p]=h
    ds=LocatorDataset(ld,'train',image_cache_root=ld/'cache')
    if len(ds)!=358:raise ValueError('Expected358 legal locator TRAIN records')
    lx=np.stack([np.rint(ds[i][0].numpy()[0]*255).astype(np.uint8) for i in range(len(ds))])
    cr=[json.loads(l) for l in (cd/'train_manifest.jsonl').read_text(encoding='utf-8').splitlines() if l]
    ids=[i for i,r in enumerate(cr) if r['classifier_train_eligible']]
    cx=np.load(cd/'train_inputs_u8.npy',allow_pickle=False)[ids,0]
    if len(cx)!=309:raise ValueError('Expected309 legal classifier calibration crops')
    for r in ds.records+cr:
        raw=Path(r['image']);expected=r['image_sha256']
        if sha(raw)!=expected:raise ValueError('Raw calibration image changed')
        bindings[str(raw)]=expected
    lmax={name:0. for name in ('conv1','conv2','conv3','conv4','g1')}
    fmap={'conv1':'f1_pooled','conv2':'f2_pooled','conv3':'f3_pooled','conv4':'f4_relu','g1':'g1_relu'}
    for x in lx:
        _,s=runtime.forward_locator(x)
        for name,key in fmap.items():lmax[name]=max(lmax[name],float(s[key].max()))
    cmax={name:0. for name in ('conv1','conv2','conv3','fc1')}
    for x in cx:
        _,s=runtime.forward_classifier(x)
        for name,key in {'conv1':'classifier_f1','conv2':'classifier_f2','conv3':'classifier_f3','fc1':'classifier_fc1_relu'}.items():
            cmax[name]=max(cmax[name],float(s[key].max()))
    lp={};li={};state=runtime.locator.state_dict();previous=1/255
    for name in ('conv1','conv2','conv3','conv4'):
        output_scale=max(lmax[name]/255,1e-12)
        p,info=quant_layer(state['base.'+name+'.weight'],state['base.'+name+'.bias'],previous,output_scale,fixed31=True)
        lp.update({name+'_'+k:v for k,v in p.items()});li[name]=info;previous=output_scale
    p,info=quant_layer(state['base.conv5.weight'],state['base.conv5.bias'],previous,per_channel=True)
    lp.update({'conv5_'+k:v for k,v in p.items()});li['conv5']=info
    lp['conv5_output_scale']=p['bias_scale']
    sH=max(lmax['g1']/255,1e-12)
    p,info=quant_layer(state['geometry_g1.weight'],state['geometry_g1.bias'],float(lp['conv3_output_scale']),sH)
    lp.update({'g1_'+k:v for k,v in p.items()});li['g1']=info
    p,info=quant_layer(state['geometry_g2.weight'],state['geometry_g2.bias'],sH,per_channel=True)
    lp.update({'g2_'+k:v for k,v in p.items()});li['g2']=info
    pairs=[multiplier(float(p['bias_scale'][i]/lp['conv5_output_scale'][i+1])) for i in range(4)]
    lp['residual_M']=np.array([v[0] for v in pairs],dtype=np.int32);lp['residual_shift']=np.array([v[1] for v in pairs],dtype=np.uint32)
    lp['confidence_threshold_i32']=np.asarray(math.ceil(math.log(.451/(1-.451))/lp['conv5_output_scale'][0]),dtype=np.int32)
    cp={};ci={};state=runtime.classifier.state_dict();previous=1/255
    for name in ('conv1','conv2','conv3','fc1','fc2'):
        output_scale=max(cmax[name]/255,1e-12) if name!='fc2' else None
        p,info=quant_layer(state[name+'.weight'],state[name+'.bias'],previous,output_scale)
        cp.update({name+'_'+k:v for k,v in p.items()});ci[name]=info
        if output_scale is not None:previous=output_scale
    cp['fc2_output_scale']=cp['fc2_bias_scale']
    OUT.mkdir()
    for name,p in (('locator',lp),('classifier',cp)):
        (OUT/name).mkdir();np.savez_compressed(OUT/name/'parameters.npz',**p)
    # Fixed v16 base parameter addresses plus the accepted B/config extension.
    base_offsets={'conv1':(0,72),'conv2':(128,992),'conv3':(1088,2816),'conv4':(2880,6336),'conv5':(6464,7544),
        'g1':(0x1DC0,0x2240),'g2':(0x2260,0x2380)}
    blob=bytearray(16384);layout=[]
    for name,(wo,bo) in base_offsets.items():
        wb=lp[name+'_weight_q'].tobytes(order='C');bb=lp[name+'_bias_q'].astype('<i4').tobytes()
        blob[wo:wo+len(wb)]=wb;blob[bo:bo+len(bb)]=bb
        layout.append({'layer':name,'weight_offset':wo,'weight_bytes':len(wb),'bias_offset':bo,'bias_bytes':len(bb)})
    for j,name in enumerate(('conv1','conv2','conv3','conv4','g1')):
        blob[0x2400+8*j:0x2408+8*j]=np.array([int(lp[name+'_M']),int(lp[name+'_shift'])],dtype='<u4').tobytes()
    for j in range(4):blob[0x2440+8*j:0x2448+8*j]=np.array([lp['residual_M'][j],lp['residual_shift'][j]],dtype='<u4').tobytes()
    (OUT/'locator/model_rom_16k.bin').write_bytes(blob);write_mem(OUT/'locator/model_rom_16k.mem',blob)
    write(OUT/'locator/layout.json',{'bytes':16384,'valid_end':0x2460,'word_count':4096,'word_address_bits':12,'endianness':'little','layers':layout})
    # Existing classifier4-byte parameter packing and8 x8-word descriptors.
    cblob=bytearray();clayout=[]
    for name in ('conv1','conv2','conv3','fc1','fc2'):
        cblob.extend(bytes((-len(cblob))%4));wo=len(cblob);wb=cp[name+'_weight_q'].tobytes();cblob.extend(wb)
        cblob.extend(bytes((-len(cblob))%4));bo=len(cblob);bb=cp[name+'_bias_q'].astype('<i4').tobytes();cblob.extend(bb)
        clayout.append({'layer':name,'weight_offset_bytes':wo,'weight_size_bytes':len(wb),'bias_offset_bytes':bo,'bias_size_bytes':len(bb)})
    if len(cblob)!=39488:raise ValueError('Classifier packing length mismatch')
    (OUT/'classifier/weights_all.bin').write_bytes(cblob);write_mem(OUT/'classifier/weights_all.mem',cblob)
    ns=read_legacy_descriptor_helpers()
    descriptors=ns['build_layer_descriptors']({n:{'M':int(cp[n+'_M']) if n!='fc2' else 0,'shift':int(cp[n+'_shift']) if n!='fc2' else 0} for n in ci},clayout)
    if descriptors[7][0]!=0x01060102:raise ValueError('Six-class final descriptor mismatch')
    desc=np.asarray(descriptors,dtype='<u4');(OUT/'classifier/layer_descriptors.bin').write_bytes(desc.tobytes())
    write_mem(OUT/'classifier/layer_descriptors.mem',desc.tobytes())
    write(OUT/'classifier/layout_and_descriptors.json',{'bytes':39488,'layers':clayout,'descriptor_words':descriptors,'final_Cout':6})
    calibration={'locator_TRAIN_frames':358,'classifier_TRAIN_crops':309,'selection':'all eligible legal TRAIN; strict100% activation maximum',
        'locator_activation_maxima':lmax,'classifier_activation_maxima':cmax,'input_scale':1/255,
        'data_artifact_and_raw_sha256':bindings,'VAL_or_TEST_used_for_calibration':False}
    write(OUT/'calibration.json',calibration)
    manifest={'status':'EXPORTED_INTEGER_PARAMETERS_PENDING_VALIDATION','float_release':manifest['release_id'],
        'locator_model_sha256':manifest['locator']['sha256'],'classifier_model_sha256':manifest['classifier']['sha256'],
        'locator_layers':li,'classifier_layers':ci,'residual_M':lp['residual_M'].tolist(),'residual_shift':lp['residual_shift'].tolist(),
        'confidence_threshold_raw_i32':int(lp['confidence_threshold_i32']),'confidence_probability':.451,
        'weight_bias_rounding':'nearest half away from zero','runtime_rounding':'nearest half toward positive infinity',
        'accumulator':'signed int32 modulo wrap','activation':'uint8 clamp after positive M/shift',
        'residual_fusion':'full signed64 intermediates then WRAP32','classifier_logits':'six raw signed32 outputs, common positive scale',
        'locator_original_hidden_shifts':[int(lp[n+'_shift']) for n in ('conv1','conv2','conv3','conv4')],
        'RTL_simulated':False,'TEST_read':False,'files_sha256':{p.relative_to(OUT).as_posix():sha(p) for p in OUT.rglob('*') if p.is_file()}}
    write(OUT/'manifest.json',manifest)
    print(json.dumps({'status':manifest['status'],'confidence_threshold':manifest['confidence_threshold_raw_i32'],
        'base_shifts':manifest['locator_original_hidden_shifts'],'locator_rom_bytes':len(blob),'classifier_weights_bytes':len(cblob),
        'residual_M':manifest['residual_M'],'residual_shift':manifest['residual_shift'],'output':str(OUT)},ensure_ascii=False))


if __name__=='__main__':main()
