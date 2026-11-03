"""Capture a fresh check at the reviewed exposure; restore driver mode on exit."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time
import cv2

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from pc.rgb_dshow import inspect_devices, select_device, set_exposure
from pc.multiobject.dataset import write_image
from pc.multiobject.public_data import sha256
from pc.multiobject.yolo import image_digest

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--out',type=Path,required=True)
p.add_argument('--exposure',type=int,default=-4)
p.add_argument('--frames',type=int,default=5)
a=p.parse_args()
a.out.mkdir(parents=True,exist_ok=False)
profile_path=Path(__file__).parent/'reviewed_camera_adjusted_exposure_profile.json'
profile=json.loads(profile_path.read_bytes())
device_path=profile['device']['DevicePath']
report={'schema':'gesture.ai_pc.mode_b_raw_check_capture.v1','status':'STARTING',
        'scene_role':'EXCLUDED_FROM_CURRENT_TRAINING_AND_CHECKPOINT_SELECTION',
        'used_for_training':False,'physical_execution':False,'path_submissions':0,
        'table_coordinates_enabled':False,'exposure_profile_sha256':sha256(profile_path),'frames':[]}
cap=None
original=None

def settle(seconds):
    end=time.monotonic()+seconds
    image=None
    while time.monotonic()<end or image is None:
        ok,image=cap.read()
        if not ok:raise RuntimeError('Camera frame unavailable')
    return image

try:
    dev=select_device(inspect_devices(),device_path)
    original=dev['Controls']['exposure']
    report['device_before']=dev
    cap=cv2.VideoCapture(dev['Index'],cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,1920)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT,1080)
    if not cap.isOpened():raise RuntimeError('Camera unavailable')
    report['warmup_auto_write']=set_exposure(device_path,original['Value'],1)
    settle(3)
    report['manual_write']=set_exposure(device_path,a.exposure,2)
    settle(3)
    control=select_device(inspect_devices(),device_path)['Controls']['exposure']
    report['readback_after_settle']=control
    if control.get('GetHResult')!=0 or control.get('Flags')!=2 or control.get('Value')!=a.exposure:
        raise RuntimeError('Exposure did not remain at the requested manual setting')
    for index in range(a.frames):
        frame=settle(.35)
        if frame.shape!=(1080,1920,3):raise RuntimeError('Unexpected frame dimensions')
        dest=a.out/f'frame_{index:06d}_raw.png'
        write_image(dest,frame)
        report['frames'].append({'image':dest.resolve().relative_to(ROOT).as_posix(),
            'image_sha256':sha256(dest),'pixel_sha256':image_digest(frame),
            'received_utc':datetime.now(timezone.utc).isoformat(),
            'image_size_wh':[1920,1080],'exposure':a.exposure,'flags':2})
    report['status']='COMPLETED'
except Exception as exc:
    report.update(status='ERROR',error=repr(exc))
    raise
finally:
    if original is not None:
        try:
            report['restore']=set_exposure(device_path,original['Value'],original['Flags'])
            if cap is not None and cap.isOpened():settle(1.5)
        except Exception as exc:
            report['restore_error']=repr(exc)
    if cap is not None:cap.release()
    (a.out/'capture.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
print(json.dumps({'status':report['status'],'frames':len(report['frames']),
                  'restore':report.get('restore',{}).get('ReadbackMatched'),'output':str(a.out)}))
