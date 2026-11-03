"""Portable approved PC path: integer gate/Top1, float old400 geometry, float600 CLF."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
import numpy as np
import torch
REF=Path(__file__).resolve().parent;BUNDLE=REF.parent
sys.path.insert(0,str(REF));sys.path.insert(0,str(REF/'models'))
from integer_vision_reference import IntegerVision,forward_locator,decode_locator
from locator_context_b import HandLocatorNetContextB
from gesture_model_v4_six_class import GestureCNN6,CLASS_NAMES
from preprocessing import read_bgr_image,preprocess_bgr_to_locator_input,clipped_int_box,square_roi_from_source_box,classifier_from_small,small_roi_descriptor


def verify_files():
    from verify_delivery import verify_hashes
    return verify_hashes(BUNDLE)


class VisionReference(IntegerVision):
    def __init__(self,stabilize=False):
        super().__init__(BUNDLE,stabilize)
        lp=torch.load(BUNDLE/'models/locator_best.pt',map_location='cpu',weights_only=False)
        cp=torch.load(BUNDLE/'models/classifier_final.pt',map_location='cpu',weights_only=False)
        if tuple(cp['class_names'])!=CLASS_NAMES:raise ValueError('Class order differs')
        self.geometry=HandLocatorNetContextB(branch_seed=lp['branch_seed']);self.geometry.load_state_dict(lp['model_state_dict'],strict=True)
        self.geometry.eval().requires_grad_(False)
        self.model=GestureCNN6();self.model.load_state_dict(cp['model_state_dict'],strict=True);self.model.eval().requires_grad_(False)

    @torch.inference_mode()
    def forward_classifier(self,image):
        x=torch.from_numpy(np.asarray(image).copy()).float().reshape(1,1,32,32)/255
        m=self.model;stages={'input_f32':x.numpy()}
        for i in (1,2,3):
            raw=getattr(m,'conv'+str(i))(x);x=getattr(m,'pool'+str(i))(getattr(m,'relu'+str(i))(raw))
            stages['conv'+str(i)+'_raw_f32']=raw.numpy();stages['pool'+str(i)+'_f32']=x.numpy()
        raw=m.fc1(m.flatten(x));hidden=m.relu4(raw);logits=m.fc2(hidden)
        stages.update(fc1_raw_f32=raw.numpy(),fc1_relu_f32=hidden.numpy(),logits_f32=logits.numpy())
        probabilities=logits.softmax(1)[0].numpy();k=int(np.argmax(probabilities))
        return {'class_id':k,'class':CLASS_NAMES[k],'confidence':float(probabilities[k]),'logits_float32':logits[0].tolist()},stages

    def classify_input(self,image):return self.forward_classifier(image)[0]

    @torch.inference_mode()
    def predict_small(self,small,timestamp=None):
        if small.dtype!=np.uint8 or small.shape!=(128,128) or small[:16].any() or small[112:].any():raise ValueError('Exact B128 required')
        raw,_,_=forward_locator(small,self.locator);decoded=decode_locator(raw,self.locator);x,y=decoded['peak_xy']
        tensor=torch.from_numpy(small[None,None].astype(np.float32)/255);output=self.geometry(tensor)
        v=output[0,1:,y,x];center=torch.stack((x+.5+v[0],y+.5+v[1]))*8
        sizes=v[2:].clamp(0,1)*128;box=torch.cat((center-sizes/2,center+sizes/2)).clamp(0,128).numpy()
        source=np.clip((box-np.array([0,16,0,16]))*5,[0,0,0,0],[640,480,640,480]);effective=source.tolist();filtered=None
        if self.stabilizer is not None:
            if timestamp is None:raise ValueError('Acquisition timestamp required')
            filtered=self.stabilizer.update(effective,decoded['detected'],640,480,timestamp);effective=filtered['effective_box']
        roi=None;classification=None;descriptor=None
        if decoded['detected'] and source[2]>source[0] and source[3]>source[1]:
            roi=square_roi_from_source_box(clipped_int_box(effective,640,480),640,480,.18)
            descriptor=small_roi_descriptor(roi);classification=self.classify_input(classifier_from_small(small,roi))
        return {**decoded,'bbox_source':source.tolist(),'effective_bbox_source':list(effective),
                'roi_source':list(roi) if roi else None,'small_roi':descriptor,'classifier':classification,
                'stabilizer':filtered,'precision':'integer_gate_float_geometry_float_classifier',
                'fresh_target_gesture':bool(classification and classification['class_id']!=0)}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--verify',action='store_true')
    parser.add_argument('--image',type=Path);parser.add_argument('--small-npy',type=Path);args=parser.parse_args()
    torch.set_num_threads(4);verify_files();runtime=VisionReference()
    if args.verify:
        index=json.loads((BUNDLE/'golden_integer/index.json').read_text(encoding='utf-8'))
        for item in index['samples']:
            expected=np.load(BUNDLE/item['float_classifier_vectors'],allow_pickle=False)
            integer=np.load(BUNDLE/item['vectors'],allow_pickle=False)
            _,stages=runtime.forward_classifier(integer['classifier_input_u8'])
            for name,value in stages.items():np.testing.assert_allclose(value,expected[name],atol=1e-5,rtol=1e-4)
            current=runtime.predict(read_bgr_image(BUNDLE/item['image']));reference=item['pipeline_approved_PC']
            assert current['detected']==reference['detected'] and current['roi_source']==reference['roi_source']
            np.testing.assert_allclose(current['bbox_source'],reference['bbox_source'],atol=1e-4,rtol=1e-5)
            if current['classifier']:assert current['classifier']['class']==reference['classifier']['class']
        print(json.dumps({'status':'PASS_APPROVED_PC_FLOAT_GEOMETRY_CLASSIFIER600','samples':len(index['samples'])}))
    elif args.image:print(json.dumps(runtime.predict(read_bgr_image(args.image)),ensure_ascii=False,indent=2))
    elif args.small_npy:print(json.dumps(runtime.predict_small(np.load(args.small_npy,allow_pickle=False)),ensure_ascii=False,indent=2))
    else:parser.error('Choose --verify, --image or --small-npy')


if __name__=='__main__':main()
