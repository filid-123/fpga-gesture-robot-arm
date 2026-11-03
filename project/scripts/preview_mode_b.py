"""Offline six-object candidate replay. No camera, network or arm connections."""
from pathlib import Path
import argparse
import json
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from pc.mode_b.profile import Profile
from pc.mode_b.perception import Perception,draw
from pc.multiobject.yolo import Detector
from pc.multiobject.surface import SurfaceRuntime
from pc.multiobject.dataset import read_image,write_image


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--image',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--detector',type=Path,default=ROOT/'model_package/mode_b/detector_public_v3/model.json')
    p.add_argument('--surface',type=Path,default=ROOT/'model_package/mode_b/surface_public_v3/model.json')
    p.add_argument('--tiled',action='store_true',help='Full-frame plus overlapping square views for small objects')
    p.add_argument('--surface-ensemble',action='store_true',help='Align and average five fixed same-frame neural surface crops')
    a=p.parse_args()
    if a.out.exists():p.error('Fresh replay output required')
    profile=Profile.load(ROOT/'config/ai_pc/mode_b_six_objects_v1.json')
    import torch
    torch.set_num_threads(4)
    detector=Detector(a.detector,backend='onnx_cpu');surface=SurfaceRuntime(a.surface,backend='torch_cpu')
    if a.surface_ensemble:
        from pc.mode_b.surface_ensemble import AlignedSurfaceEnsemble
        surface=AlignedSurfaceEnsemble(surface)
    if a.tiled:
        from pc.mode_b.tiled_detector import TiledDetector
        detector=TiledDetector(detector)
    image=read_image(a.image);obs=Perception(detector,surface,profile).infer(image)
    a.out.mkdir(parents=True);write_image(a.out/'raw.png',image);write_image(a.out/'detected.png',draw(image,obs))
    (a.out/'observation.json').write_text(json.dumps(obs,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'status':'COMPLETED','classes':[r['class_name'] for r in obs['recognitions']],
                      'localizations':[{k:r[k] for k in ('task_id','class_name','status')} for r in obs['localizations']],
                      'physical_execution':False,'path_submissions':0,'output':str(a.out)}))


if __name__=='__main__':main()
