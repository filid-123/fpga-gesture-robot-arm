"""Windows native HTML-controlled AB session. Explicit --run accesses hardware."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import signal
import sys
import threading
import time
os.environ.setdefault('MIOPEN_FIND_MODE','FAST')
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
PATCH_ID='native_giao_full_workspace_p4'


def runtime_inputs(root, manifest):
    profile = json.loads((root/'ab_runtime_profile.json').read_bytes())
    if (profile['schema'] != 'gesture.ab_public_runtime.v1'
            or profile['task_abi'] != manifest['task_abi']
            or profile['patch_id'] != manifest['patch_id']):
        raise ValueError('Public runtime profile does not match the release')
    inputs = manifest['inputs']
    omitted = set(profile['omitted_archive_members'])
    external = profile['external_assets']
    if (not omitted <= inputs.keys() or omitted.intersection(external)
            or any(inputs.get(name) != digest for name, digest in external.items())):
        raise ValueError('Public runtime profile has inconsistent input bindings')
    missing = [name for name in external if not (root/name).is_file()]
    if missing:
        raise ValueError('Missing approved runtime assets: '+', '.join(missing))
    return {name: digest for name, digest in inputs.items() if name not in omitted}


def load(root, runtime_only=False):
    manifest=json.loads((root/'mode_ab_manifest.json').read_bytes())
    if manifest['version']!='0.1.0' or manifest['task_abi']!=0x340e:raise ValueError('Wrong AB package ABI; use the matching ABI340E full package and BIT')
    if manifest.get('patch_id')!=PATCH_ID:raise ValueError('Wrong AB package patch; use the complete native_giao_full_workspace_p4 package')
    selected = runtime_inputs(root, manifest) if runtime_only else manifest['inputs']
    for name,digest in selected.items():
        path=(root/name).resolve()
        if not path.is_relative_to(root.resolve()) or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
            raise ValueError('Sealed package input changed: '+name)
    p=json.loads((root/'candidate/bank1/PLAN_NATIVE.json').read_bytes())
    t=json.loads((root/'candidate/S4_BANKED_CANDIDATE.json').read_bytes())
    from mode_a_restock_config import load_restock
    t['restock']=load_restock(root)
    return manifest,p,t,json.loads((root/'candidate/mode_ab/home_transitions.json').read_bytes())


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    choice=ap.add_mutually_exclusive_group(required=True)
    choice.add_argument('--run',action='store_true');choice.add_argument('--check-only',action='store_true')
    choice.add_argument('--preview',action='store_true',help='Disconnected HTML only; no camera/board opened automatically')
    ap.add_argument('--root',type=Path,default=ROOT);ap.add_argument('--out-dir',type=Path)
    ap.add_argument('--runtime-only',action='store_true',help='Use the shipped public AB runtime profile')
    ap.add_argument('--port',type=int,default=8765);ap.add_argument('--no-browser',action='store_true')
    ap.add_argument('--monitor-only',action='store_true');ap.add_argument('--seconds',type=float,default=0)
    args=ap.parse_args()
    import math
    if not math.isfinite(args.seconds) or args.seconds<0:ap.error('--seconds must be finite and nonnegative')
    if args.monitor_only and not args.run:ap.error('--monitor-only requires --run')
    if args.root.resolve()!=ROOT.resolve():ap.error('Run the script inside the selected complete package')
    if args.check_only:
        m,_,_,_=load(args.root,args.runtime_only);print(json.dumps(dict(result='PUBLIC_RUNTIME_INPUTS_PASS' if args.runtime_only else 'SEALED_PACKAGE_INPUTS_PASS',version=m['version'],patch_id=m.get('patch_id','base'),hotfix_id=m.get('hotfix_id'),physical_access=False)));return 0
    if args.out_dir is None:ap.error('Use a new --out-dir for each session')
    args.out_dir.mkdir(parents=True,exist_ok=False)
    from pc.mode_ab.control import Controller
    from pc.mode_ab.camera import Camera
    from pc.mode_ab.http import Console
    controller=Controller(args.out_dir/'control.jsonl');camera=Camera(args.out_dir)
    stop=threading.Event();previous=signal.signal(signal.SIGINT,lambda *_:stop.set())
    board=runtime=console=None;result=dict(version='0.1.0',patch_id=PATCH_ID,started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        physical_success=None,execution='DISCONNECTED_PREVIEW' if args.preview else 'REAL_HARDWARE_SESSION')
    try:
        if args.run:
            manifest,p,t,transitions=load(args.root,args.runtime_only)
            result['hotfix_id']=manifest.get('hotfix_id')
            from pc.mode_ab.board import Board
            from pc.mode_ab.runtime import Runtime
            board=Board(args.root,args.out_dir,controller,p,t,transitions,stop)
            runtime=Runtime(board,camera,controller,args.out_dir)
        console=Console(controller,camera,args.port,runtime)
        url=console.start();print('HTML_CONSOLE '+url,flush=True)
        if not args.no_browser:
            import webbrowser
            webbrowser.open(url)
        if board:board.start(query_only=args.monitor_only)
        started=time.monotonic()
        while not stop.is_set() and (args.seconds==0 or time.monotonic()-started<args.seconds):
            if runtime and not args.monitor_only:runtime.tick()
            elif board:
                s=board.observe('QUERY_ONLY_NO_MOTION')
                if s['motion_frames']:raise RuntimeError('Unexpected motion during query-only test')
            stop.wait(.08)
        result['result']='QUERY_ONLY_COMPLETED' if args.monitor_only else 'OPERATOR_STOPPED'
    except InterruptedError:result['result']='OPERATOR_STOPPED'
    except Exception as exc:
        result.update(result='STOPPED_ERROR',error=repr(exc));print('STOPPED_ERROR',repr(exc),flush=True)
    finally:
        if console:console.close()
        if runtime:runtime.close()
        if board:
            shutdown=board.close();result['shutdown']=shutdown
            if shutdown.get('shutdown_error') or shutdown.get('service_close_error'):
                result['result']='STOPPED_ERROR'
        try:camera.close()
        except Exception as exc:result.update(result='STOPPED_ERROR',camera_shutdown_error=repr(exc))
        result['finished_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
        (args.out_dir/'session_result.json').write_text(json.dumps(result,indent=2)+'\n')
        signal.signal(signal.SIGINT,previous)
    return 2 if result['result']=='STOPPED_ERROR' else 0


if __name__=='__main__':raise SystemExit(main())
