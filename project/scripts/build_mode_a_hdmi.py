"""Isolated complete ABI3409 implementation; no board or actuator access."""
from pathlib import Path
import sys
import hashlib,json,os,re,subprocess,time
from run_mode_a_v3_checks import W,source_list,PKG
H=W/'board_evidence/mode_a_hdmi_impl_a3'


def main():
    H.mkdir(parents=True,exist_ok=True)
    project=Path('D:/FPGA_Projects/Gesture/builds/mode_a_hdmi_v012_20261028_a3')
    if project.exists():raise FileExistsError(project)
    paths=source_list()+list((W/'native_motion/constraints').glob('*.xdc'))+list((W/'native_motion/scripts').glob('*roarm*.tcl'))
    paths += list((W/'native_motion/rtl/hdmi').iterdir())
    paths += [W/'native_motion/geometry_alpha_q16.mem',W/'native_motion/rtl/autonomous/black_geometry_constants.vh',W/'native_motion/rtl/autonomous/ov5640_vga_yuyv.mem']
    paths += [PKG/'quantized'/f for f in ['locator/model_rom_16k.mem','classifier/weights_all.mem','classifier/layer_descriptors.mem']]
    hashes={p.relative_to(W).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    (H/'BUILT_SOURCE_HASHES.json').write_text(json.dumps(dict(files=hashes,parameters=dict(TIMED_WALKTHROUGH=1,HANDOVER_V2=1,HAND_ALIGN=1,HAND_ALIGN_REGIONS=4,HAND_ALIGN_LOCATOR=1,ENABLE_HDMI=1),task_abi='3409'),indent=2)+'\n','utf-8')
    env=os.environ.copy();env.update(ROARM_BUILD_DIR=str(project),ROARM_REPORT_DIR=str(H/'implemented_reports'),ROARM_TIMED_WALKTHROUGH='1',ROARM_HANDOVER_V2='1',ROARM_HAND_ALIGN='1',ROARM_HAND_ALIGN_REGIONS='4',ROARM_HAND_ALIGN_LOCATOR='1',ROARM_HDMI='1',GESTURE_PYTHON=sys.executable)
    records=[]
    for label,name in [('create','create_roarm_closed_loop_project.tcl'),('implement','build_roarm_closed_loop.tcl')]:
        tokens=['E:/Xilinx/2026.1/Vivado/bin/vivado.bat','-mode','batch','-notrace','-source',str(W/'native_motion/scripts'/name),'-log',str(H/(label+'.log')),'-journal',str(H/(label+'.jou'))]
        if any(re.search(r'["%!^&|<>]',t) for t in tokens):raise ValueError('Unsafe token')
        cmd='cmd.exe /d /s /c "'+' '.join('"'+t+'"' for t in tokens)+'"';started=time.monotonic()
        with (H/(label+'_stdout.txt')).open('xb',buffering=0) as out:
            proc=subprocess.Popen(cmd,cwd=W,env=env,stdout=out,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
            (H/'BUILD_PROGRESS.json').write_text(json.dumps(dict(stage=label,pid=proc.pid,project=str(project)))+'\n','utf-8')
            print('START '+label,flush=True);code=proc.wait()
        records.append(dict(label=label,command=cmd,exit_code=code,wall_s=time.monotonic()-started))
        (H/'BUILD_COMMANDS.json').write_text(json.dumps(records,indent=2)+'\n','utf-8')
        if code:raise RuntimeError(label+' failed '+str(code))
        print('PASS '+label,flush=True)
    for rel,digest in hashes.items():
        if hashlib.sha256((W/rel).read_bytes()).hexdigest()!=digest:raise ValueError('Source changed during build '+rel)
    (H/'BUILD_COMPLETED.json').write_text(json.dumps(dict(passed=True,project=str(project),hardware_access=False,review='PENDING_INDEPENDENT_REPORT_REVIEW'),indent=2)+'\n','utf-8')


if __name__=='__main__':main()
