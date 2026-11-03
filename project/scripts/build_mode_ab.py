"""Build the complete A/B overlay in a new isolated Vivado project."""
from pathlib import Path
import sys
import argparse
import hashlib
import json
import os
import subprocess
import time
from run_mode_a_v3_checks import W, source_list, PKG


def main(attempt):
    if not attempt.isalnum():
        raise ValueError('Alphanumeric build attempt required')
    out=W/('board_evidence/mode_ab_impl_'+attempt)
    project=Path('D:/FPGA_Projects/Gesture/builds')/('mode_ab_v0_1_0_'+attempt)
    if out.exists() or project.exists():
        raise FileExistsError('A build attempt must use fresh directories')
    out.mkdir(parents=True)
    files=set(source_list())|set((W/'native_motion/constraints').glob('*.xdc'))|set((W/'native_motion/scripts').glob('*roarm*.tcl'))
    files|={p for p in (W/'native_motion/rtl/hdmi').iterdir() if p.is_file()}
    files|={W/'native_motion/geometry_alpha_q16.mem',W/'native_motion/rtl/autonomous/black_geometry_constants.vh',W/'native_motion/rtl/autonomous/ov5640_vga_yuyv.mem'}
    files|={PKG/'quantized'/p for p in ('locator/model_rom_16k.mem','classifier/weights_all.mem','classifier/layer_descriptors.mem')}
    hashes={p.relative_to(W).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}
    params=dict(TIMED_WALKTHROUGH=1,HANDOVER_V2=1,HAND_ALIGN=1,HAND_ALIGN_REGIONS=4,HAND_ALIGN_LOCATOR=1,ENABLE_HDMI=1,UPGRADE=1,AUTO_RESTOCK=1,DYNAMIC_B=1,FAST_B=1)
    (out/'built_source_hashes.json').write_text(json.dumps(dict(files=hashes,parameters=params,task_abi='340e'),indent=2)+'\n',encoding='utf-8')
    env=os.environ.copy()
    env.update(ROARM_BUILD_DIR=str(project),ROARM_REPORT_DIR=str(out/'implemented_reports'),
               GESTURE_PYTHON=sys.executable,
               ROARM_TIMED_WALKTHROUGH='1',ROARM_HANDOVER_V2='1',ROARM_HAND_ALIGN='1',ROARM_HAND_ALIGN_REGIONS='4',
               ROARM_HAND_ALIGN_LOCATOR='1',ROARM_HDMI='1',ROARM_UPGRADE='1',ROARM_AUTO_RESTOCK='1',ROARM_DYNAMIC_B='1',ROARM_FAST_B='1')
    records=[]
    for label,name in [('create','create_roarm_closed_loop_project.tcl'),('implement','build_roarm_closed_loop.tcl')]:
        args=['E:/Xilinx/2026.1/Vivado/bin/vivado.bat','-mode','batch','-notrace',
              '-source',str(W/'native_motion/scripts'/name),'-log',str(out/(label+'.log')),'-journal',str(out/(label+'.jou'))]
        started=time.monotonic()
        with (out/(label+'_stdout.txt')).open('xb',buffering=0) as stream:
            p=subprocess.Popen(args,cwd=W,env=env,stdout=stream,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
            print('START',label,'PID',p.pid,flush=True)
            code=p.wait()
        records.append(dict(stage=label,command=args,exit_code=code,wall_s=time.monotonic()-started))
        (out/'commands.json').write_text(json.dumps(records,indent=2)+'\n',encoding='utf-8')
        if code:
            raise RuntimeError('Vivado failed at '+label+'; inspect '+str(out))
        print('PASS',label,flush=True)
    for name,sha in hashes.items():
        if hashlib.sha256((W/name).read_bytes()).hexdigest()!=sha:
            raise RuntimeError('Source changed during build: '+name)
    (out/'build_completed.json').write_text(json.dumps(dict(project=str(project),result='BUILD_COMPLETED_REVIEW_PENDING',hardware_access=False),indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--attempt',required=True)
    main(p.parse_args().attempt)
