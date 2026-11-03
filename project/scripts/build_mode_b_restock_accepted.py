"""Export the physically accepted130.6s red restock for Git/teammate review."""
from pathlib import Path
import argparse
import json
import shutil
import zipfile
from verify_mode_b_restock_accepted import read, sha, sequence, q16, verify
from rehearse_mode_b_restock import GROUPS

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT/'artifacts/phase3c/mode_b_return_20261029/session_runs/20261029_094927_5503514'
DEST = ROOT/'docs/phase3c/mode_b_restock_20261029/accepted_red_v2'
SOURCES = [
    'pc/mode_b/RestockSerialSession.cs','pc/mode_b/restock_workflow.py',
    'scripts/prepare_mode_b_restock.py','scripts/prepare_mode_b_restock_depth.py',
    'scripts/prepare_mode_b_restock_speed.py','scripts/prepare_mode_b_restock_session.py',
    'scripts/run_mode_b_restock.ps1','scripts/run_mode_b_restock_session.ps1',
    'scripts/rehearse_mode_b_restock.py','scripts/try_mode_b_loaded_route.ps1',
    'scripts/prepare_mode_b_loaded_route.py','scripts/prepare_mode_b_approach.py',
    'scripts/mode_b_serial_stream.ps1','scripts/mode_b_native_stream.ps1',
    'scripts/collect_mode_b_serial_pose.ps1','scripts/roarm_state_json.ps1',
    'scripts/test_mode_b_restock.py','scripts/test_mode_b_restock_depth.py',
    'scripts/test_mode_b_restock_speed.py','scripts/test_mode_b_restock_rehearsal.py',
    'scripts/test_mode_b_restock_session.py','scripts/test_mode_b_restock_session.ps1',
    'sim/phase3_robot/verify_mode_b_loaded_route.py','config/ai_pc/mode_b_restock_20261029.json']

README = '''# 模式B红块补回：实体接受130.6秒

本包是2026-10-29已验证的“公共点(300,200)抓起→本任务原抓取位置放回→空夹低HOME”基线。用户确认全程正常。运行`python verify.py`仅需Python3.10+标准库，不连接任何硬件，也不依赖开发机绝对路径。

本次原位(651.87944665,257.80145958,15)mm，公共点物体中心Z15mm、桌面承托。红块公共点向下8mm为本次已验证接触修正，保持原释放中心。需移走覆盖公共点的150mm交付承托物，原位须空闲。这个固定成功案例不能替代任意动态源点或其他物体的新规划与验证。

13运动段+4夹爪事件共3835请求，原生弧度T102/20ms/spd640/acc254；原4条T106事件保持。`sequence.jsonl`含精确动作顺序，`execution.json`含段周期、停留和夹爪等待公式，`phase_map.json`映射9个补回状态。不要无间隔灌入串口。当前PC位置残差只记录，通信/设备/扭矩故障阻止后续，无自动重发。任意未知姿态直接回HOME没有验证。

执行器整程持久TTL；周期从WriteLine开始计算，写入阻塞包含在20ms内；迟到延后，不压缩追赶。Windows运行期请求1ms计时精度，结束恢复。实测首请求至末反馈130.643542秒，较174.782041秒缩短25.25%，较204.040416秒缩短35.97%；平均实际帧间隔21.495ms。

`motion_q16.mem`是从本次实际T102弧度导出的192位Q16.16参考，低32位b，然后s/e/t/r/g，文本显示g..b，最近偶数舍入。它只用于对比，不宣称既有PL五次插补能逐位生成该PCHIP几何曲线。夹爪T106事件另在sequence中，不能省略。

板端导出后可离线比较：`python verify.py --observed board_requests.jsonl`（每行label、wire_json），或`python verify.py --pl-samples board_motion.mem`。这些只比较内容和顺序，实际周期、背压和状态事件还需联测。

`evidence/`保存原计划、源记录、实发、精确网格证明和独立用户接受记录的原始字节；旧文件的执行前false/待反馈字段不回写，最终接受由ACCEPTANCE证明。其中开发机绝对路径仅作来源，校验使用包内相对映射。`source/`是算法/执行源码审阅快照，运行依赖原开发机文件布局、numpy/scipy、CAD/模型及已绑定历史数据，不是换机直接操作硬件的部署包。

模式B选择项可重排；补回使用该任务冻结原抓取记录，不能套模式A固定三槽。需背景重新武装，原位为空的同选项再次选中才触发；补回不用PALM。取消/故障适配器源码和旧三类取消仿真审阅ZIP在上级目录。红块正常补回实物接受不覆盖取消分支、橡皮/圆柱补回、网页/FPGA桥接或NPU整任务验收。3873个原生网格样本证明不包含摩擦、夹持力和伺服动力学。
'''


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n','utf8')


def build(dest=DEST):
    if dest.exists() and any(dest.iterdir()):
        raise ValueError('Use a fresh package directory')
    dest.mkdir(parents=True,exist_ok=True)
    session=read(RUN/'SESSION.json');plan=read(session['plan_file']);origin_path=Path(plan['origin_record_file']);origin=read(origin_path)
    evidence={}
    def copy(name,source,target):
        source=Path(source);where=dest/target;where.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source,where);evidence[name]=target
    for name,source in [('plan',Path(session['plan_file'])),('simulation',Path(session['simulation_file'])),
        ('session',RUN/'SESSION.json'),('result',RUN/'RESTOCK_RESULT.json'),
        ('acceptance',RUN/'ACCEPTED_SESSION_V2.json'),('execution',RUN/'EXECUTION_VERIFICATION.json'),
        ('origin',origin_path),('delivery_plan',Path(origin['delivery_plan_file'])),
        ('delivery_result',Path(origin['delivery_result_file']))]:
        copy(name,source,'evidence/'+name.upper()+'.json')
    for name in SOURCES:
        copy('source:'+name,ROOT/name,'source/'+name)
    for name in ('scripts/mode_a_upgrade_profile.py','scripts/mode_a_upgrade_backend.py','SOURCE_MANIFEST.json'):
        copy('filid:'+name,ROOT/'artifacts/phase3c/mode_b_return_20261029/filid_timing_480f3e6'/name,'filid_reference/'+name)
    copy('verify',ROOT/'scripts/verify_mode_b_restock_accepted.py','verify.py')
    rows=sequence(plan)
    (dest/'sequence.jsonl').write_text(''.join(json.dumps(x,separators=(',',':'))+'\n' for x in rows),'utf8')
    (dest/'motion_q16.mem').write_text(''.join(q16(json.loads(x['wire_json']))+'\n' for x in rows if x['kind']=='motion'),'ascii')
    write(dest/'phase_map.json',[dict(state=state,labels=list(labels)) for state,labels in GROUPS])
    write(dest/'execution.json',dict(start_firmware_rad_b_s_e_t_r_g=session['start'],entry_limits_deg=session['entry_limits_deg'],
        serial=dict(baud=115200,data_bits=8,parity='N',stop_bits=1,dtr=False,rts=False),
        query_period_ms=100,feedback_timeout_ms=2000,
        gripper_dwell_formula='abs(target_g - fresh_observed_g)*4096/(2*pi)/spd +1 seconds',
        boundary_feedback=dict(samples=3,spacing_ms=100,residual_policy='OBSERVE_ONLY'),
        operations=[{k:v for k,v in op.items() if k!='wires'}|dict(requests=len(op['wires']),
            gripper_wire=op['wires'][0] if op['kind']=='event' else None) for op in session['operations']]))
    write(dest/'PACKAGE.json',dict(schema='gesture.mode_b.accepted_restock_handoff.v1',object_class='red_cube',
        public_xy_mm=[300,200],original_return_mm=plan['return_centre_mm'],evidence=evidence,
        physical_normal_red_restock_accepted=True,fpga_task_accepted=False,source_snapshot_is_live_deployment=False))
    (dest/'README_CN.md').write_text(README,'utf8')
    write(dest/'MANIFEST.json',dict(files_sha256={p.relative_to(dest).as_posix():sha(p) for p in sorted(dest.rglob('*')) if p.is_file()}))
    report=verify(dest)
    archive=dest.parent/'MODE_B_RED_RESTOCK_ACCEPTED_20261029.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for path in sorted(dest.rglob('*')):
            if path.is_file():z.write(path,(Path('accepted_red_v2')/path.relative_to(dest)).as_posix())
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for name,digest in read(dest/'MANIFEST.json')['files_sha256'].items():
            import hashlib
            assert hashlib.sha256(z.read('accepted_red_v2/'+name)).hexdigest()==digest
    write(dest.parent/'ACCEPTED_RED_VERIFICATION.json',dict(verification=report,archive_bytes=archive.stat().st_size,
        archive_sha256=sha(archive),zip_crc_and_all_manifest_sha256_passed=True))
    print(json.dumps(report|dict(zip_bytes=archive.stat().st_size,zip_sha256=sha(archive))))


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',type=Path,default=DEST)
    build(ap.parse_args().output)
