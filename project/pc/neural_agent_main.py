"""Neural-only S7 perception/task service; no unaccepted physical paths.

The camera worker updates a latest-frame slot while the existing protocol pump
handles heartbeats. Requests consume a fresh stable observation or CANCEL. Until
base/TCP/real IK acceptance, even a valid target produces preview + CANCEL.
"""
from pathlib import Path
import argparse
from copy import deepcopy
import json
import socket
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'pc')]
from pc.neural_top_runtime import NeuralRuntime
from pc.neural_top_perception import NeuralTopPerception
from pc.neural_task_pipeline import NeuralTaskPipeline
from pc.rgb_table_geometry import RGBTableGeometry
from pc.rgb_workspace_overlay import RGBWorkspaceOverlay
from pick_pipeline import PipelineReport
from pc_task_agent import PcTaskAgent
from phase3_event_log import EventLog
from pc_agent_main import run_agent


class LatestObservation:
    def __init__(self):
        self.lock = threading.Lock()
        self.observation, self.error = None, None

    def publish(self, observation):
        with self.lock:
            self.observation, self.error = deepcopy(observation), None

    def invalidate(self, error):
        with self.lock:
            self.observation, self.error = None, str(error)

    def read(self):
        with self.lock:
            return deepcopy(self.observation)


class NeuralRequestPipeline:
    def __init__(self, source, config):
        self.source, self.config = source, config
        self.last_preview = None

    def handle(self, req, limits):
        started = time.monotonic_ns()
        obs = self.source.read()
        if obs is None or obs.get('offline_snapshot') is not False:
            self.last_preview = {'candidate':None,'reason':'NO_LIVE_NEURAL_OBSERVATION',
                                 'physical_execution':False,'joint_path':None}
            return None, PipelineReport(req.task_id,req.object_id,'NO_LIVE_NEURAL_OBSERVATION',
                                        t_ns={'start':started,'rejected':time.monotonic_ns()})
        try:
            pipe = NeuralTaskPipeline(obs, self.config)
            result = pipe.handle(req, limits)
            self.last_preview = pipe.last_preview
            return result
        except (ValueError, KeyError, TypeError) as exc:
            self.last_preview = {'candidate':None,'reason':'INVALID_NEURAL_OBSERVATION',
                                 'error':str(exc),'physical_execution':False,'joint_path':None}
            return None, PipelineReport(req.task_id,req.object_id,'INVALID_NEURAL_OBSERVATION',
                                        t_ns={'start':started,'rejected':time.monotonic_ns()})


def camera_worker(stop, source, detector, camera_index, roi, log):
    import cv2
    cap = None
    try:
        cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
        if not cap.isOpened():
            raise RuntimeError('Camera open failed')
        cap.set(cv2.CAP_PROP_FRAME_WIDTH,1920)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT,1080)
        index = 0
        while not stop.is_set():
            ok, frame = cap.read()
            received = time.monotonic_ns()
            if not ok:
                raise RuntimeError('Camera read failed')
            obs = detector.infer(frame,index,received,roi=roi)
            index += 1
            source.publish(obs)
            log.emit('neural_observation',frame_index=obs['frame_index'],
                     received_monotonic_ns=received,timing_ms=obs['timing_ms'],
                     backend=obs['backend'],detections=obs['detections'],
                     timestamp_basis='HOST_READ_COMPLETE_NOT_SENSOR_EXPOSURE',physical_execution=False)
    except Exception as exc:
        source.invalidate(exc)
        log.emit('neural_source_failed',error=str(exc),physical_execution=False)
        stop.set()
    finally:
        if cap is not None:
            cap.release()


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--host',required=True)
    p.add_argument('--port',type=int,default=50555)
    p.add_argument('--runtime-config',type=Path,default=ROOT/'config/ai_pc/neural_top_development.json')
    p.add_argument('--backend',choices=['rocm','onnx_cpu','torch_cpu','torch_cuda','vitisai'],default='rocm')
    p.add_argument('--provider-options',type=Path)
    p.add_argument('--camera',type=int,default=1)
    p.add_argument('--seconds',type=float,default=60.)
    p.add_argument('--out',type=Path,required=True)
    a = p.parse_args(argv)
    settings = json.loads(a.runtime_config.read_bytes())
    if settings.get('schema') != 'gesture.ai_pc.neural_top_runtime_config.v1' or settings.get('robot_execution_enabled'):
        p.error('Only neural preview/task-cancellation configuration is implemented')
    if not 0 < a.port < 65536 or a.seconds <= 0:
        p.error('Invalid port or duration')
    a.out.mkdir(parents=True,exist_ok=False)
    stop, source = threading.Event(), LatestObservation()
    worker, sock = None, None
    log = EventLog('pc',a.out/'events.jsonl',meta={'perception':'NEURAL_TOP','physical_execution':False})
    summary = {'status':'ERROR','physical_execution':False,'path_submissions':0,
               'mode':'LIVE_NEURAL_PREVIEW_CANCEL_ONLY','amd_acceptance':'NOT_ACCEPTED'}
    try:
        options = json.loads(a.provider_options.read_bytes()) if a.provider_options else None
        runtime = NeuralRuntime(ROOT/settings['model_file'],a.backend,options)
        geometry = RGBTableGeometry(ROOT/settings['table_file'],ROOT)
        workspace = RGBWorkspaceOverlay(ROOT/settings['workspace_file'],ROOT)
        detector = NeuralTopPerception(runtime,geometry,workspace,
                    confidence=settings['confidence'],top_height_mm=settings['known_top_height_mm'],
                    cube_side_mm=settings['cube_side_mm'],max_frame_age_ms=settings['max_frame_age_ms'])
        config = json.loads((ROOT/settings['task_config_file']).read_bytes())
        pipeline = NeuralRequestPipeline(source,config)
        agent = PcTaskAgent(pipeline,log=log)
        worker = threading.Thread(target=camera_worker,args=(stop,source,detector,a.camera,
                      settings['roi_xywh_raw'],log),daemon=True)
        worker.start()
        # Do not connect the board when model/camera initialization has already failed.
        deadline = time.monotonic()+min(10.,a.seconds)
        while source.read() is None and not stop.is_set() and time.monotonic()<deadline:
            stop.wait(.02)
        if source.read() is None:
            raise RuntimeError(source.error or 'No initial neural camera observation')
        sock = socket.create_connection((a.host,a.port),timeout=3.)
        started = time.monotonic()
        run_agent(sock,agent,stop=lambda: stop.is_set() or time.monotonic()-started>a.seconds)
        summary.update(status='COMPLETED' if source.error is None else 'SOURCE_FAILED',
                       backend=runtime.info,path_submissions=agent.submissions,
                       last_task_preview=pipeline.last_preview,source_error=source.error)
        if runtime.backend=='vitisai':
            summary['npu_profile'] = runtime.close_profile()
    except Exception as exc:
        summary['error'] = f'{type(exc).__name__}: {exc}'
    finally:
        stop.set()
        if sock is not None:
            sock.close()
        if worker is not None:
            worker.join(timeout=3.)
        log.close()
        (a.out/'summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False),flush=True)
    return 0 if summary['status']=='COMPLETED' else 2


if __name__=='__main__':
    raise SystemExit(main())
