"""Build the 2026-10-30 offline speed handoff; no robot/camera connection."""
import json
import shutil
import zipfile
from pathlib import Path

from build_mode_b_teammate_handoff import source_snapshot
from verify_mode_b_optimized_handoff import read, sha, q16, verify, EVENTS, FAST

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT/'docs/phase3c/mode_b_optimized_handoff_20261030'
EVIDENCE = ROOT/'artifacts/phase3c/mode_b_speed_release_20261030'
RED = ROOT/'artifacts/phase3c/mode_b_red_retry_20261030/return_fast_v3'
BASE = ROOT/'artifacts/phase3c/mode_b_ttl_20261028'


def write(path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def copy(source, target):
    target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(source,target)


README = '''# 模式B最终提速联测包 · 2026-10-30

本包为三类抓取→抬升→缓冲→交付→退爪→低HOME的当前参考。红块放置后撤离速度已获用户“合适”确认；按用户要求，把同样四段提速应用到圆柱和橡皮，不追加实体试验。两类旧抓取已成功，新转运曲线需队友联测，不标为已实测。

| 类别 | 基础倍率 | 原名义纯运动s | 新名义纯运动s | 抓取补偿/闭合 |
|---|---:|---:|---:|---|
| 红块 red_cube | 2 | 44.20（优化前） | 22.62 | 本局部下降12mm；2.70rad / spd40 / acc5 |
| 圆柱 small_canister | 2 | 43.90 | 23.10 | 桌面X+10mm、原抓取高度；2.80rad / spd40 / acc5 |
| 橡皮 eraser | 3 | 29.02 | 15.00 | 桌面X+13/Y+10mm、下降8mm；2.95rad / spd60 / acc5 |

时间只统计采样运动，不含夹爪停留、查询和确认；不承诺整程耗时同比下降。基础倍率保持各类已成功的抓取速度。主锚向外2mm只加一次，补偿只改运动命令，不写回相机坐标。橡皮额外残差仍限参考点(631.6914,265.6341)的25mm内；红块depth12同样只限其局部25mm，不复制到其他类。源范围和哈希见各自PLAN/PROFILE。

先在仓库根目录运行（仅Python3.10+标准库，不连接硬件）：

```powershell
python -B docs/phase3c/mode_b_optimized_handoff_20261030/verify.py
```

每类 `objects/<类>/` 含完整PLAN、phase_map、sequence/commands、Q16.16参考和四段quintic_segments。`execution.json`给周期、串口参数、夹爪等待及任务状态映射。HOME来自已接受低位停放；承托中心仍(285,195,150)mm，缓冲沿filid设定。历史成功补回130.6秒保持原配置，见 ../mode_b_restock_20261029/README_CN.md；这次只优化正常交付的四段，不改变公共点补回算法。

四段BUFFER/PREPLACE/RETREAT/RETURN_CLEAR使用关节五次曲线q=q0+(q1-q0)(10u³−15u⁴+6u⁵)，额外速度因子2。T102 spd分别2640/2640/3960，acc均254封顶并按同一加速度上限重计时，周期20ms。其余几何/抓取/事件参数保持；放置后仍先横向退爪8mm再上撤。新关节曲线不保证末端直线，因此已经逐样本进行本地关节/包围盒约束检查；本次没有新增Coppelia网格或实体测试。

`quintic_segments`用归一化u的六项系数；曲线时长=(样本数−1)×周期，段发送占时=样本数×周期，两者分开。其他段沿原笛卡尔PCHIP/五次时间律采样；不要将它们误当同一条关节五次曲线。motion_q16是六通道固件弧度、最近偶数舍入、低32位b再s/e/t/r/g；不包含T106事件。PL定点插补尚未逐点验收。

板端先离线输出接受的样本/事件，与本包比对：

```powershell
python -B docs/phase3c/mode_b_optimized_handoff_20261030/verify.py --object-class eraser --observed board_requests.jsonl
python -B docs/phase3c/mode_b_optimized_handoff_20261030/verify.py --object-class eraser --pl-samples board_motion.mem
```

observed每行至少index/label/wire_json，PL每行48位hex。离线比对不证明真实周期、碰撞或夹持力。不得把commands无间隔灌入串口。PC试验的PREPLACE固定2.5秒等待不是正式手势确认；FPGA需实现PRE等待≥2秒、PALM连续500ms许可、FIST连续1秒取消及通信故障处理，原模式A不变。动态选择顺序不得被旧三类参考编号覆盖。

原始相机源点冻结在PROFILE/origin_for_restock，原位归还使用该点，不用补偿后的指令位置。参考点仅供离线向量联测；新位置由当前视觉包重新识别，不能直接复放样例抓取。当前视觉入口 ../mode_b_visual_bundle_20261029/GIT_DELIVERY_CN.md。

`source_snapshot/`和SOURCE_INDEX包含当前规划/执行源码及配置审阅快照；带开发机绝对路径和历史哈希的输入证据保持原样。它不是换机即用的实时部署包：动态规划需部署视觉/几何环境并重新绑定本机证据路径，不能只替换路径字符串后继续使用旧SHA。实体入口scripts/run_mode_b_ttl_{red,cylinder,eraser}_trial.ps1显式传当前共享speed profile；没有Move不会发送运动。新包核验与本次生成均无设备访问。

evidence保存历史基线/用户反馈，保留旧计划false/pending字段；独立红块OPERATOR_FEEDBACK只接受本轮撤离速度。NPU实际执行、FPGA整链、取消/故障分支和新速度动力学仍由队友联测，不由发送完成推断接受。
'''


def build(dest=DEST):
    dest = Path(dest)
    if dest.exists() and any(dest.iterdir()):
        raise ValueError('Use a fresh output directory')
    dest.mkdir(parents=True,exist_ok=True)
    (dest/'README_CN.md').write_text(README,encoding='utf-8')
    copy(ROOT/'scripts/verify_mode_b_optimized_handoff.py',dest/'verify.py')
    copy(ROOT/'config/ai_pc/robot_home_current.json',dest/'HOME.json')
    config = ROOT/'config/ai_pc/mode_b_transit_speed_20261030_v1.json'
    copy(config,dest/'SPEED_PROFILE.json')
    copy(EVIDENCE/'OFFLINE_PROPAGATION_VERIFICATION.json',dest/'OFFLINE_PROPAGATION_VERIFICATION.json')
    copy(EVIDENCE/'SOFTWARE_VERIFICATION.json',dest/'SOFTWARE_VERIFICATION.json')
    feedback = read(RED/'OPERATOR_FEEDBACK.json')
    for name,source in [('OPERATOR_FEEDBACK.json',RED/'OPERATOR_FEEDBACK.json'),
                        ('EXECUTION_REVIEW.json',RED/'EXECUTION_REVIEW.json'),
                        ('RESULT.json',Path(feedback['result']['file']))]:
        copy(source,dest/'evidence/red'/name)
    for cls,source in [('small_canister',BASE/'cylinder_trial_v2/ACCEPTED_CYLINDER_TRIAL_V2.json'),
                       ('eraser',BASE/'eraser_right10_trial_v1/ACCEPTED_ERASER_RIGHT10_TRIAL.json')]:
        copy(source,dest/'evidence'/cls/'BASELINE_ACCEPTANCE.json')
    summaries = []
    for cls in ('red_cube','small_canister','eraser'):
        plan_path = RED/'LOADED_ROUTE_PLAN.json' if cls=='red_cube' else EVIDENCE/cls/'LOADED_ROUTE_PLAN.json'
        plan = read(plan_path); folder = dest/'objects'/cls
        copy(plan_path,folder/'PLAN.json')
        sequence = []; golden = []; phases = []; sparse = []
        for stage in plan['stages']:
            phase = stage['phase']; data = stage['stage']; frames = data['stream_frames']
            begin = len(sequence); dt = data['period_s']
            for i,f in enumerate(frames):
                sequence.append({'index':len(sequence),'label':phase,'kind':'motion','sample_in_stage':i,
                    'period_s':dt,'stage_offset_s':i*dt,'wire_json':f['wire_json']})
                golden.append(q16(json.loads(f['wire_json'])))
            wire = json.loads(frames[0]['wire_json'])
            phases.append({'phase':phase,'carrying':stage['carrying'],'request_start_index':begin,
                'request_end_index_inclusive':len(sequence)-1,'motion_samples':len(frames),'period_s':dt,
                'nominal_motion_seconds':data['nominal_motion_seconds'],
                'target_firmware_rad':data['target_firmware_rad'],'native_spd':wire['spd'],'native_acc':wire['acc'],
                'path_kind':'JOINT_QUINTIC' if phase in FAST or phase=='RETURN_LOW_HOME' else 'CARTESIAN_PCHIP_QUINTIC'})
            if phase in FAST:
                q0 = [frames[0]['command_firmware_rad'][n] for n in ('b','s','e','t','r')]
                q1 = [data['target_firmware_rad'][n] for n in ('b','s','e','t','r')]
                sparse.append({'phase':phase,'joint_order':['b','s','e','t','r'],
                    'normalized_u_coefficients_rad':[[a,0.,0.,10*(b-a),-15*(b-a),6*(b-a)] for a,b in zip(q0,q1)],
                    'sample_count':len(frames),'sample_u':'i/(sample_count-1)',
                    'curve_duration_s':(len(frames)-1)*dt,'send_duration_s':len(frames)*dt,
                    'period_s':dt,'constant_hand_rad':wire['hand'],'native_spd':wire['spd'],'native_acc':wire['acc'],
                    'pl_quantized_interpolation_bit_exact_accepted':False})
            if phase in EVENTS:
                label,key = EVENTS[phase]
                sequence.append({'index':len(sequence),'label':label,'kind':'gripper_event','wire_json':plan[key]})
        sequence.append({'index':len(sequence),'label':'PARK_CLOSE','kind':'gripper_event','wire_json':plan['park_close_wire_json']})
        (folder/'sequence.jsonl').write_text(''.join(json.dumps(s,separators=(',',':'))+'\n' for s in sequence),encoding='utf-8')
        (folder/'commands.jsonl').write_text(''.join(s['wire_json']+'\n' for s in sequence),encoding='utf-8')
        (folder/'motion_q16.mem').write_text('\n'.join(golden)+'\n',encoding='ascii')
        write(folder/'phase_map.json',phases);write(folder/'quintic_segments.json',sparse)
        profile = {'object_class':cls,'source_centre_mm':plan['request']['pickup']['centre_mm'],
            'yaw_deg':plan['request']['pickup']['yaw_deg'],'destination':plan['request']['destination'],
            'origin_for_restock':plan['request']['pickup'],'base_speed_multiplier':plan['speed_multiplier'],
            'nominal_motion_seconds':plan['nominal_motion_seconds'],'requests':len(sequence),'motion_samples':len(golden),
            'close_command':json.loads(plan['close_after_descent_wire_json']),
            'local_transfer':plan['local_transfer'],'new_speed_physical_test_performed':cls=='red_cube',
            'physical_scope':'POSTRELEASE_SPEED_ACCEPTED' if cls=='red_cube' else 'BASELINE_GRASP_ACCEPTED_NEW_TRANSIT_SPEED_UNTESTED',
            'source_plan_sha256':sha(plan_path)}
        write(folder/'PROFILE.json',profile);summaries.append(profile)
    source_snapshot(dest)
    extras = ['scripts/mode_b_transit_speed.py','scripts/mode_b_red_depth.py',
        'scripts/build_mode_b_optimized_handoff.py','scripts/verify_mode_b_optimized_handoff.py',
        'scripts/build_mode_b_teammate_handoff.py','scripts/verify_mode_b_teammate_handoff.py',
        'scripts/try_mode_b_ttl_home.ps1','scripts/test_mode_b_red_depth.py',
        'config/ai_pc/mode_b_transit_speed_20261030_v1.json',
        'config/ai_pc/mode_b_red_grasp_depth_20261030_v1.json',
        'config/ai_pc/mode_b_red_grasp_depth_20261030_v2.json',
        'config/ai_pc/mode_b_red_grasp_depth_20261030_v3.json',
        'config/ai_pc/mode_b_red_depth_active_20261030.json']
    index = read(dest/'SOURCE_INDEX.json')
    paths = {item['repository_path'] for item in index['files']} | set(extras)
    for rel in extras:
        copy(ROOT/rel,dest/'source_snapshot'/rel)
    index['files'] = [{'repository_path':rel,'sha256':sha(ROOT/rel)} for rel in sorted(paths)]
    write(dest/'SOURCE_INDEX.json',index)
    write(dest/'execution.json',{'baud':115200,'format':'8N1','flow_control':False,'dtr':False,'rts':False,
        'encoding':'UTF8_JSON_PLUS_LF','native_joint_unit':'radian','home_T122_unit':'degree',
        'pickup_period_s':.04,'tail_period_s':.02,'residuals':'OBSERVE_ONLY_DEFAULT',
        'communication_or_device_fault_stops_new_requests':True,'automatic_motion_retry':False,
        'gripper_wait_seconds':'abs(target_rad-current_rad)*4096/(2*pi)/spd + 1; then fresh feedback',
        'pc_test_preplace_wait_s':2.5,'pc_wait_is_fpga_gesture_confirmation':False,
        'formal_preplace_min_wait_s':2,'formal_palm_continuous_s':.5,'formal_fist_cancel_continuous_s':1,
        'state_mapping':{'DIRECT_PREGRASP':'APPROACH','OPEN_HIGH':'OPEN','DESCEND':'DESCEND',
            'CLOSE_SOURCE':'CLOSE_GRIP','LIFT':'LIFT','INNER_HOLD':'INNER_HOLD','BUFFER':'BUFFER',
            'PREPLACE':'PRE_WAIT','PLACE':'DELIVER','RELEASE':'RELEASE',
            'RELEASE_CLEARANCE':'RELEASE_CLEARANCE','RETREAT':'HAND_CLEAR','RETURN_CLEAR':'RETURN_CLEAR',
            'INNER_RETURN':'INNER_RETURN','RETURN_LOW_HOME':'RETURN_HOME','PARK_CLOSE':'WAIT_VISION'},
        'new_fpga_binary_protocol_implemented':False,'reference_ids_do_not_replace_dynamic_selection_order':True})
    write(dest/'PACKAGE.json',{'schema':'gesture.mode_b.optimized_handoff.v1','date':'2026-10-30',
        'hardware_execution_enabled':False,'objects':summaries,'additional_hardware_access_this_task':False,
        'restock130s_reference_changed':False,'npu_fpga_closed_loop_accepted':False})
    write(dest/'MANIFEST.json',{'algorithm':'SHA256','files':{
        p.relative_to(dest).as_posix():{'bytes':p.stat().st_size,'sha256':sha(p)}
        for p in sorted(dest.rglob('*')) if p.is_file()}})
    report = verify(dest)
    archive = dest.with_suffix('.zip')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in sorted(dest.rglob('*')):
            if p.is_file(): z.write(p,(Path(dest.name)/p.relative_to(dest)).as_posix())
    with zipfile.ZipFile(archive) as z:
        if z.testzip() is not None: raise ValueError('ZIP CRC failed')
        for name,expected in read(dest/'MANIFEST.json')['files'].items():
            import hashlib
            if hashlib.sha256(z.read(dest.name+'/'+name)).hexdigest()!=expected['sha256']:
                raise ValueError('ZIP SHA mismatch: '+name)
    write(EVIDENCE/'PACKAGE_VERIFICATION.json',{'verification':report,'archive':str(archive),
        'archive_bytes':archive.stat().st_size,'archive_sha256':sha(archive),'zip_crc_and_manifest_sha_passed':True})
    print(json.dumps(report,ensure_ascii=False))
    return report


if __name__ == '__main__':
    build()
