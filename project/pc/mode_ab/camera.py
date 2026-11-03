"""One raw DirectShow camera, newest-frame capture and same-frame HIP inference."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import threading
import time
import cv2
import numpy as np
from pc.rgb_dshow import inspect_devices,select_device
from pc.mode_ab.motion import ROOT


def set_property(path,name,value,flags):
    p=subprocess.run(['powershell','-NoProfile','-ExecutionPolicy','Bypass','-File',
        str(ROOT/'scripts/set_mode_ab_camera_profile.ps1'),'-DevicePath',path,
        '-Property',name,'-Value',str(value),'-Flags',str(flags)],capture_output=True,
        timeout=20,creationflags=subprocess.CREATE_NO_WINDOW)
    result=json.loads(p.stdout.decode('utf-8-sig'))
    if p.returncode or not result.get('ReadbackMatched'):raise RuntimeError('Camera control readback failed: '+name)
    return result


class Camera:
    def __init__(self,out):
        self.out=Path(out);self.lock=threading.RLock();self.stop=threading.Event()
        self.latest=None;self.result=None;self.jpeg=None;self.error=None
        self.cap=None;self.threads=[];self.controls=[];self.device=None;self.ready=False

    def start(self,path):
        if self.stop.is_set():raise RuntimeError('Previous camera attempt ended; restart the session before reconnecting')
        if self.cap or self.threads:raise RuntimeError('Camera already started; restart the session to change devices')
        self.device=select_device(inspect_devices(),path)
        if 'vid_32e6&pid_9228' not in path.lower():raise ValueError('Use the calibrated ordinary RGB camera VID32e6/PID9228')
        try:
            for name,value,flags in [('exposure',-4,2),('brightness',0,2),('gain',0,2),('white_balance',4000,1)]:
                self.controls.append((name,set_property(path,name,value,flags)))
            self.cap=cv2.VideoCapture(int(self.device['Index']),cv2.CAP_DSHOW)
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH,1920);self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT,1080)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE,1)
            if not self.cap.isOpened():raise RuntimeError('DirectShow camera open failed')
            # Verify index identity again after opening, before trusting any frame.
            if select_device(inspect_devices(),path)['Index']!=self.device['Index']:raise RuntimeError('Camera index changed')
            (self.out/'rgb_camera.json').write_text(json.dumps(dict(device=self.device,controls=self.controls),indent=2))
            for target in (self.capture,self.infer):
                thread=threading.Thread(target=target,daemon=True);self.threads.append(thread);thread.start()
        except Exception:
            self.close();raise

    def capture(self):
        index=0
        try:
            while not self.stop.is_set():
                started=time.monotonic();ok,frame=self.cap.read();captured=time.monotonic()
                if not ok or frame.shape!=(1080,1920,3):raise RuntimeError('Calibrated raw 1920x1080 frame unavailable')
                index+=1
                with self.lock:self.latest=(index,frame,started,captured)
        except Exception as exc:
            with self.lock:self.error=repr(exc);self.ready=False

    def infer(self):
        try:
            import sys
            sys.path.insert(0,str(ROOT/'scripts'))
            from verify_mode_b_visual_bundle import verify_current,local
            from replay_mode_b_visual_bundle import load_projection
            from pc.mode_ab.vision_workspace import project_rows,WorkspaceDetector,workspace_polygon_pixels
            from pc.mode_ab.gpu import RocmDetector,RocmSurface
            from pc.mode_b.tiled_detector import TiledDetector
            from pc.mode_b.surface_ensemble import AlignedSurfaceEnsemble
            from pc.mode_b.perception import Perception
            from pc.mode_b.profile import Profile
            from pc.rgb_table_geometry import RGBTableGeometry
            c,f,w=verify_current(ROOT)
            detector=RocmDetector(local(ROOT,f['detector_package']));surface=RocmSurface(local(ROOT,f['surface_package']))
            geometry=RGBTableGeometry(local(ROOT,w['table_file']),ROOT)
            workspace_polygon=np.rint(workspace_polygon_pixels(geometry)).astype(np.int32)
            engine=Perception(WorkspaceDetector(TiledDetector(detector),geometry,c['localization_dimensions']),
                AlignedSurfaceEnsemble(surface),Profile.load(local(ROOT,f['profile'])))
            xy=np.array(w['pattern_outer_corners_desktop_xyz_mm'])[:,:2];bounds=np.r_[xy.min(0),xy.max(0)]
            previous=None
            with (self.out/'vision.jsonl').open('x',encoding='utf-8') as log:
                while not self.stop.is_set():
                    with self.lock:latest=self.latest
                    if latest is None or latest[0]==previous:
                        self.stop.wait(.01);continue
                    index,frame,started,captured=latest;previous=index
                    surface.timings=[]
                    obs=engine.infer(frame,index,offline=False)
                    rows=project_rows(obs,geometry,c['localization_dimensions'],bounds,load_projection())
                    result=dict(frame_id=index,frame_sha256=obs['frame_sha256'],captured_monotonic=captured,
                        capture_started_monotonic=started,completed_monotonic=time.monotonic(),
                        camera_path=self.device['DevicePath'],table_sha256=c['current_table_sha256'],
                        localizations=rows,recognitions=obs['recognitions'],total_ms=obs['total_ms'],
                        workspace_excluded_detections=deepcopy(engine.detector.last_excluded),
                        detector=obs['backend'],surface=surface.info,surface_passes=deepcopy(surface.timings),physical_execution=False,
                        timing_source='HOST_CAPTURE_READ_START_NOT_SENSOR_EXPOSURE_START')
                    canvas=frame.copy()
                    cv2.polylines(canvas,[workspace_polygon],True,(0,210,255),2,cv2.LINE_AA)
                    cv2.putText(canvas,'B centre XY: X490..690 Y215..355 mm',(18,25),cv2.FONT_HERSHEY_SIMPLEX,.6,(0,210,255),2)
                    for d in obs['recognitions']:
                        a,b,x,y=map(round,d['bbox_xyxy_raw']);cv2.rectangle(canvas,(a,b),(x,y),(57,213,155),2)
                        cv2.putText(canvas,d['class_name'],(a,max(25,b-8)),cv2.FONT_HERSHEY_SIMPLEX,.6,(57,213,155),2)
                    ok,jpeg=cv2.imencode('.jpg',canvas,[cv2.IMWRITE_JPEG_QUALITY,80])
                    if not ok:raise RuntimeError('Camera preview encoding failed')
                    log.write(json.dumps(result)+'\n');log.flush()
                    with self.lock:self.result=result;self.jpeg=jpeg.tobytes();self.ready=True
        except Exception as exc:
            with self.lock:self.error=repr(exc);self.ready=False

    def snapshot(self):
        with self.lock:
            result=deepcopy(self.result)
            fresh=bool(result and time.monotonic()-result['captured_monotonic']<1.)
            return dict(ready=self.ready and fresh,error=self.error,observation=result,device=self.device)

    def close(self):
        self.stop.set()
        for thread in self.threads:thread.join(timeout=3)
        if self.cap:self.cap.release()
        restoration=[]
        for name,record in reversed(self.controls):
            before=record['Before']
            try:restoration.append(dict(property=name,result=set_property(self.device['DevicePath'],name,before['Value'],before['Flags'])))
            except Exception as exc:restoration.append(dict(property=name,error=repr(exc)))
        if self.controls:(self.out/'rgb_restore.json').write_text(json.dumps(restoration,indent=2))
