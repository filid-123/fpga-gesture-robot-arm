"""Resume an interrupted, source-bound implementation from its placed checkpoint."""
import argparse, hashlib, json, os, subprocess, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def main(attempt):
    if not attempt.isalnum(): raise ValueError('Invalid attempt')
    out=ROOT/('board_evidence/mode_ab_impl_'+attempt)
    binding=json.loads((out/'built_source_hashes.json').read_bytes())
    for n,d in binding['files'].items():
        if hashlib.sha256((ROOT/n).read_bytes()).hexdigest()!=d: raise ValueError('Built input changed: '+n)
    project=Path('D:/FPGA_Projects/Gesture/builds')/('mode_ab_v0_1_0_'+attempt)
    if not (project/'Gesture_Roarm_ClosedLoop.runs/impl_1/roarm_closed_loop_wrapper_placed.dcp').is_file():
        raise ValueError('No reusable placed checkpoint')
    original=(ROOT/'native_motion/scripts/build_roarm_closed_loop.tcl').read_text()
    start=original.index('reset_run synth_1'); end=original.index('wait_on_run impl_1')
    text=original[:start]+'''reset_run -from_step phys_opt_design impl_1
launch_runs impl_1 -to_step write_bitstream -jobs 4
'''+original[end:]
    text=text.replace('set script_dir [file dirname [file normalize [info script]]]',
        'set script_dir {'+(ROOT/'native_motion/scripts').as_posix()+'}')
    suffix=1
    while (out/f'resume{suffix}_stdout.txt').exists(): suffix+=1
    stem=f'resume{suffix}'
    script=out/(stem+'.tcl');script.write_text(text)
    env=os.environ.copy();env.update(ROARM_BUILD_DIR=str(project),ROARM_REPORT_DIR=str(out/'implemented_reports'),ROARM_UPGRADE='1')
    cmd=['E:/Xilinx/2026.1/Vivado/bin/vivado.bat','-mode','batch','-notrace','-source',str(script),'-log',str(out/(stem+'.log')),'-journal',str(out/(stem+'.jou'))]
    started=time.monotonic()
    with (out/(stem+'_stdout.txt')).open('xb',buffering=0) as f:
        r=subprocess.run(cmd,env=env,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
    (out/(stem+'_command.json')).write_text(json.dumps(dict(command=cmd,exit_code=r.returncode,wall_s=time.monotonic()-started,hardware_access=False),indent=2))
    if r.returncode: raise RuntimeError('Resume failed; see '+stem+'_stdout.txt')
    for n,d in binding['files'].items():
        if hashlib.sha256((ROOT/n).read_bytes()).hexdigest()!=d: raise ValueError('Built input changed: '+n)
    (out/'build_completed.json').write_text(json.dumps(dict(project=str(project),result='BUILD_COMPLETED_REVIEW_PENDING',resumed_from='placed_checkpoint',hardware_access=False),indent=2))
    print('PASS: resumed implementation completed',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--attempt',required=True);main(p.parse_args().attempt)
