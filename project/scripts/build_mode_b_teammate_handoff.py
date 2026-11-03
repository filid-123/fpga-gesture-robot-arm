"""Export accepted TTL trials into a portable, offline teammate review package."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

from verify_mode_b_teammate_handoff import verify, q16_hex

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'docs/phase3c/mode_b_teammate_handoff_20261028'
BASE = ROOT / 'artifacts/phase3c/mode_b_ttl_20261028'
CASES = [
    ('red_cube', 1, 'today_native_anchor/ACCEPTED_SECOND_POSITION.json',
     'today_native_anchor/new_position_trial/native_plan', '20261028_130433_9936683'),
    ('small_canister', 3, 'cylinder_trial_v2/ACCEPTED_CYLINDER_TRIAL_V2.json',
     'cylinder_trial_v2/native_plan_v1', '20261028_133722_0931306'),
    ('eraser', 2, 'eraser_right10_trial_v1/ACCEPTED_ERASER_RIGHT10_TRIAL.json',
     'eraser_right10_trial_v1/complete_trials/20261028_144419_0188168/native_plan',
     '20261028_144452_0562891'),
]


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def copy(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)


README = '''# 模式B队友联测包 · 2026-10-28

这是三类物体的**实物成功轨迹、HOME、执行参数和状态机交接基线**。先用 Python 离线校验，再做板端输出对比；包内校验不会连接机械臂、相机或FPGA。

```powershell
python .\\verify.py
```

使用 Python 3.10+ 标准库即可；可把整个目录或同级ZIP搬到另一台电脑。`PACKAGE.json` 为机器入口，`MANIFEST.json` 绑定所有文件，`objects/` 按类存完整数据。新增动态取物位置必须重新规划、仿真，并保留任务和原始取物坐标；不能重放另一位置的固定成功轨迹。

| 类别/模式B ID | 实物验证速度 | 实物修正 | 抓取闭合 |
|---|---|---|---|
| red_cube / 1 | 2倍；两处红块成功，本包导出第二处整程 | 固定主锚基础向外2mm | 2.70rad，spd40/acc5 |
| eraser / 2 | 3倍；最新完整流程成功 | 桌面X+13/Y+10mm，另有固定主锚向外2mm | 2.95rad，spd60/acc5 |
| small_canister / 3 | 2倍；向右修正后完整流程成功 | 桌面X+10mm，另有固定主锚向外2mm | 2.80rad，spd40/acc5 |

三个现有本机完整入口默认3倍，但红块/圆柱3倍尚无实物接受，不能把默认值当验证结果。橡皮修正只允许距(631.6914,265.6341,7.5)mm的XY **25mm** 内，Z保持7.5mm；其他位置需重新确认局部残差。各类修正只作用于运动命令，相机读数不改；主锚向外2mm只加一次，不逐轮累加。150mm主锚包络是软件局部范围，尚无全区域实物标定。

当前桌面原点为左前角，X向右，Y远离底座，Z向上，单位mm。底座轴投影(585,25)。目标承托面中心 **(285,195,150)mm**，平顶80×80mm、无凸边是本轮代理模型，用户按filid布置并接受整程，未另行测量承托尺寸。旧名义仿真包的(260,160,30)不是本轮实体交付点。

HOME见 `HOME.json`，低位收回不遮挡取物区；b/s/e/t/r/g为固件弧度，`native_return_target.T=122`使用度。固件XYZ不是桌面高度或木块中心。任意未知姿态直接回HOME未验证；正常已知路径返回成功，不应改成任意姿态盲目归位。

队友先读 `INTEGRATION_CN.md`（接口、周期、状态和责任），再读 `BRANCH_TEST_CN.md`（分支测试）。`objects/<类>/phase_map.json` 定位阶段，`sequence.jsonl`定位每条指令及事件，`commands.jsonl`保持原始JSON；**不能将整个JSONL无间隔灌入串口**。运动段间有反馈与等待，夹爪事件需要自身停留与反馈。

`motion_q16.mem` 为本次从实际固件弧度新导出的192位参考：低32位b，依次s/e/t/r/g，带符号Q16.16，最近偶数舍入，十六进制按g..b显示。只包含T102运动样本，T106事件保持在sequence中；它不是旧名义URDF关节表。新参考尚未与RTL/板卡比对。

板端导出接受时的样本/事件后可运行：

```powershell
python .\\verify.py --object-class eraser --observed .\\board_requests.jsonl
python .\\verify.py --object-class eraser --pl-samples .\\board_motion.mem
```

第一种每行至少包含`index,label,wire_json`，包括夹爪事件；第二种每行48位hex、仅T102样本。离线比对数值/顺序不验证真实时间，周期、背压和中断需单独测。

`evidence/`保持原始计划/实发/仿真/用户接受记录不改写，因此其中仍有开发机绝对路径和执行前false标志；当前实物接受由同目录独立ACCEPTANCE文件及其哈希证明。portable校验不读取这些绝对路径。`source_snapshot/`是算法/执行源码审阅快照，绑定路径和哈希见`SOURCE_INDEX.json`；不是换机可直接运行的相机/实体部署包。现场原始图、模型权重、venv和海量逐次采集不装入此包；视觉/NPU交接沿用独立冻结包。

实物整程成功与Coppelia4.10网格无碰撞已有证据；摩擦/夹持力/滑落动力学、全域残差标定、真实NPU/ROCm落点、FPGA整任务执行和确认/取消/故障分支尚未联合验收。本轮整理只进行离线导出和验证，没有发送硬件指令。
'''

INTEGRATION = '''# 接口和联测顺序

## 分工与模式边界

模式A保持filid固定物槽和1红/2黄/3蓝任务映射。模式B采用独立profile：1红方块、2橡皮、3圆柱，HOME完成后视觉给动态取物坐标。两模式可共用缓冲/交付逻辑，不共用固定取物坐标、类别编码或旧关节残差。

PC负责NPU视觉结果绑定、目标选择、局部实物补偿、完整路径/反解、全段碰撞与限速检查、任务阶段和归还源点。FPGA/PS负责接收已审核任务、周期轨迹执行、事件与反馈、确认/取消/超时/断链。新模式B整任务报文需队友确认并实现，当前JSON是交接表示，不能直接冒充已有PATH_SUBMIT协议。

正式目标仍为PC交稀疏关键点/段参数、PL插补，PC密集样本作黄金参考。当前实体PC执行的是PCHIP/五次时间律的原生T102采样流；旧PL梯形插补不能直接等价复现。队友应先选定兼容的段表示/插补与定点舍入，用本包逐点比对；若改变插补，需重新仿真并实体回归。旧32段限制应按新版适配器分块，块边界保持速度、任务ID和事件，不能截断完整任务。

## 数据输入

`DYNAMIC_INPUT_EXAMPLE.json`是接口草案和已成功坐标例子；不是在线已有二进制报文。必须绑定模式profile、task_id、帧ID/时间、标定哈希、物体尺寸/朝向、源中心与承托面中心。相机改变后旧标定/残差不能沿用；NPU实际运行证据单独记录。算法入口见快照`scripts/prepare_mode_b_empirical_transfer.py:prepare(capture_path,request_path,speed_multiplier)`，经`prepare_mode_b_ttl_full_trial.py`分派。原始hash链含本机路径，需要重新部署解析与绑定，不能只改路径字符串而保留旧hash。

归还目标使用任务开始时冻结的原始动态源点，不能用补偿后的指令位置，也不能用取消时新识别到的其他物体。每条反馈要关联task_id、段号、样本号、时间戳，区分发送成功/设备接收/实际完成。`Workflow.event('DONE')`只是意图模型，调用方需先核验对应动作的完成证据；CLOSE的DONE不能仅靠串口写成功就当作已夹稳。

## 坐标、执行参数

五个运动轴+独立夹爪六通道，不是六自由度末端任意位姿解。T102字段`base,shoulder,elbow,wrist,roll,hand`全部rad；T106夹爪`cmd`为rad；T122 HOME参考为deg；只读T105查询不是运动。PowerShell大小写不敏感，`T`和`t`不能当普通同名属性读入，参考`roarm_state_json.ps1`处理。

TTL：COM5为本机例子，115200/8N1，无流控，DTR/RTS=false；每条JSON后LF。PC不自动重发运动。入口/下降/抬升40ms，后半程20ms，具体每段样本以phase_map为准。3倍拾取spd480/acc180；3倍后半程spd1980/acc254（原297被254封顶并同步重计时），不能自行发送acc297。T102 spd单位为舵机steps/s，acc为100steps/s²，不是rad/s或轨迹倍率。

张开1.586rad/spd300/acc20，收纳闭合3.10rad/spd100/acc20，物体闭合见README。当前监督试验残差仅记录；通信失败/设备故障仍阻止后续请求，不重发，不承诺软件退出等同物理急停。夹爪停留按`abs(目标rad-当前rad)*4096/(2*pi)/spd+1s`估算并读反馈，不能删除后直接抬升。

名义运动时间只统计采样段，实际还含夹爪停留、状态查询与阶段等待；最新橡皮29.02s名义、119.575s实际，不能把后者写成29秒任务。实发时间戳保存在RESULT.json；首条与末反馈时间不等同每条采样周期精确达标。

## 状态映射

| 包内动作/事件 | 正式意图 | 后续条件 |
|---|---|---|
| 已知路径进入低HOME | HOME→WAIT_VISION | 空夹、已知状态、任务未持物 |
| DIRECT_PREGRASP + OPEN_HIGH | APPROACH_CORRECTED | 动态目标有效、张开后反馈 |
| DESCEND + CLOSE_SOURCE | DESCEND→CLOSE | 源点不变、闭合与夹持证据 |
| LIFT | VERTICAL_LIFT | 持物确认，禁止仅用写成功代替 |
| INNER_HOLD→BUFFER→PREPLACE | INNER_HOLD→BUFFER→PRE→PRE_WAIT | 到位/净空；缓冲为持物停留，不放下 |
| PLACE | DELIVER | PRE至少2s且PALM连续500ms |
| RELEASE | RELEASE | 支撑/交付许可、提交释放后禁止自动撤销取回 |
| RELEASE_CLEARANCE→RETREAT | RELEASE_CLEARANCE→HAND_CLEAR | 松开、向外8mm退爪与上撤 |
| RETURN_CLEAR→INNER_RETURN→RETURN_LOW_HOME + PARK_CLOSE | RETURN_CLEAR→INNER_RETURN→RETURN_HOME | 空夹、清空当前任务后等待下一帧 |

filid基准commit85b4bcaf000a8b69c50ca6d65bbd88b07afe4735：INNER=(585,225,90)，B=(360,200,160)，中档PRE=(350,215,180)，H=(285,195,175)，H_CLEAR=(285,195,195)。这些是link5局部(0,0,115.428)的工具参考点，H的175不是承托150，也不是各物块中心。导出计划已按各物体附着和尺寸重求PLACE；禁止直接把H写成物块中心目标。

## 建议队友按此顺序验收

1. PC离线verify三类数据，读HOME/参数/阶段，确认独立模式Bprofile。
2. 无机械臂，板端输出三类完整样本/事件，导出接受握手的向量并比对。另测40/20ms节拍、背压、不重复及跨块边界。
3. 按BRANCH_TEST先软件事件注入，再板端空载，再实体受控验收；已知静止节点才接续归还轨迹，运动中先建立停稳状态并重规划。
4. 接入NPU真实帧与任务绑定，明确视觉过期/目标切换处理；最后用已验证类速度实体联测，新速度另验。

本包没有实现新RTL/PS协议，不改变现有ModeA。待交接审核项是新版段表示、事件ID/帧格式、完成与夹持/支撑判定信号、取消路径生成及实际板端时序。
'''

BRANCHES = '''# 模式B分支怎么补测

这些是下一轮验收用例，不是已经实物通过的结论。当前TTL正常路径在PREPLACE后固定等2.5s即交付，未连接FPGA真实确认/取消；先在软件或板端无机械臂注入事件。参考实现`source_snapshot/pc/mode_b/postlift_workflow.py`只发意图，不执行取消轨迹。

| 用例 | 操作/注入 | 应看到的结果 |
|---|---|---|
| 正常确认 | PRE_WAIT中先等至少2s，再PALM连续500ms | 只发一次DELIVER，随后支撑确认→RELEASE→退爪→HOME |
| 不确认/短抖动 | 无PALM或不足500ms | 停在PRE_WAIT保持夹持，不因固定2.5s自动放下 |
| 等待时取消 | 持物、释放提交前，FIST连续1s | 回任务原取物位置→受控放回→竖直撤离→HOME；不去交付释放 |
| 不同持物阶段取消 | 分别在抬升后/BUFFER/PRE已知静止节点注入FIST | 各自从该节点选有效归还路线，源点保持任务最初值 |
| 释放边界取消 | RELEASE_SUBMITTED之前/之后各注入一次 | 提交前可转归还；提交后不自动取回已释放物体 |
| 断链/设备故障 | 注入COMM_LOST或ARM_FAULT | FAULT_HOLD，停止新增运动，恢复通信不自动续跑/回HOME |
| 无效几何/视觉过期 | 目标越界、旧帧、标定变化、橡皮超25mm局部区 | 提交前拒绝；执行中变为无效则HOLD并重新审核 |
| 重复/乱序/目标切换 | 重放旧task_id或阶段完成、放置前切换类别 | 拒绝旧事件，不重发运动/释放，新任务从空夹HOME建立 |
| 松夹或夹取失败 | 未取得GRASP_VERIFIED | 不把电机到位当成功持物；保持/恢复路径需重新选择 |

旧名义包有静止节点取消归还路径，但其URDF/交付点/关节映射不同，不能直接用于这次实体轨迹。当前实体取消轨迹尚未导出并仿真；先实现并验证，再做实物取消。运动中取消不能简单反向播放原样本流；应停止提交、处理队列、取得新鲜姿态/持物状态并规划撤离/归还。

每个用例记录：task_id、源/交付坐标、类/速度、事件时序、板端接收/完成日志、取消生效点、是否松夹、最终物块位置及HOME/故障状态。判断手势持续时间和去抖由识别/FPGA适配层实现，不能把已确认字符串当原始手势就直接放行。
'''


def source_snapshot(dest):
    paths = {Path('pc/mode_b/postlift_workflow.py'), Path('pc/roarm_reference_kinematics.py')}
    scripts = ['prepare_mode_b_empirical_transfer.py', 'prepare_mode_b_ttl_full_trial.py',
               'prepare_mode_b_loaded_route.py', 'prepare_mode_b_red_restart.py',
               'prepare_mode_b_cylinder_restart.py', 'prepare_mode_b_eraser_restart.py',
               'mode_b_eraser_geometry.py', 'try_mode_b_loaded_route.ps1', 'mode_b_native_stream.ps1',
               'mode_b_serial_stream.ps1', 'collect_mode_b_serial_pose.ps1',
               'run_mode_b_ttl_red_trial.ps1', 'run_mode_b_ttl_cylinder_trial.ps1',
               'run_mode_b_ttl_eraser_trial.ps1', 'roarm_state_json.ps1',
               'test_mode_b_empirical_transfer.py', 'test_mode_b_cylinder_transfer.py',
               'test_mode_b_eraser_transfer.py', 'test_mode_b_local_grasp_correction.py']
    paths.update(Path('scripts') / name for name in scripts)
    paths.update(p.relative_to(ROOT) for p in (ROOT/'pc/mode_b/motion').glob('*.py'))
    paths.add(Path('sim/phase3_robot/verify_mode_b_loaded_route.py'))
    # Include local Python imports needed to review the selected algorithms.
    pending = list(paths)
    while pending:
        rel = pending.pop()
        if rel.suffix != '.py':
            continue
        for node in ast.walk(ast.parse((ROOT/rel).read_text(encoding='utf-8-sig'))):
            names = [node.module] if isinstance(node, ast.ImportFrom) and node.module else (
                [n.name for n in node.names] if isinstance(node, ast.Import) else [])
            for name in names:
                for candidate in (Path(*name.split('.')).with_suffix('.py'),
                                  Path('scripts')/Path(*name.split('.')).with_suffix('.py')):
                    if (ROOT/candidate).is_file() and candidate not in paths:
                        paths.add(candidate)
                        pending.append(candidate)
    paths.add(Path('requirements-mode-b-motion.txt'))
    configs = ['robot_home_current.json', 'roarm_reference_geometry.json',
               'mode_b_filid_postlift_20261028.json', 'mode_b_commissioning_tolerance_20261028.json',
               'mode_b_red_grasp_correction_20261028.json',
               'mode_b_cylinder_grasp_20261028_v2.json', 'mode_b_cylinder_grasp_active_20261028.json',
               'mode_b_eraser_grasp_20261028_v4.json', 'mode_b_eraser_grasp_active_20261028.json']
    for name in configs:
        path = Path('config/ai_pc')/name
        if (ROOT/path).exists():
            paths.add(path)
    index = []
    for rel in sorted(paths):
        copy(ROOT/rel, dest/'source_snapshot'/rel)
        index.append({'repository_path': rel.as_posix(), 'sha256': sha(ROOT/rel)})
    write(dest/'SOURCE_INDEX.json', {'purpose': 'REVIEW_SNAPSHOT_NOT_PORTABLE_LIVE_RUNTIME',
                                   'files': index,
                                   'external_dependencies': ['numpy/scipy and motion requirements',
                                    'CoppeliaSim4.10 + URDF meshes for a new simulation run',
                                    'frozen vision models, camera/exposure device and local calibration',
                                    'original hash-bound JSON evidence graph for new dynamic planning',
                                    'local PowerShell/serial and fresh state for any live commissioning']})


def build(dest=DEST):
    dest = Path(dest)
    if dest.exists() and any(dest.iterdir()):
        raise ValueError('Use a fresh output directory; never overwrite a release')
    dest.mkdir(parents=True, exist_ok=True)
    copy(ROOT/'scripts/verify_mode_b_teammate_handoff.py', dest/'verify.py')
    copy(ROOT/'config/ai_pc/robot_home_current.json', dest/'HOME.json')
    for name, content in [('README_CN.md', README), ('INTEGRATION_CN.md', INTEGRATION), ('BRANCH_TEST_CN.md', BRANCHES)]:
        (dest/name).write_text(content, encoding='utf-8')
    provenance = []
    objects = []
    for cls, class_id, accepted_rel, plan_rel, run in CASES:
        folder = dest/'objects'/cls
        plan_path = BASE/plan_rel/'LOADED_ROUTE_PLAN.json'
        result_path = ROOT/'artifacts/phase3c/mode_b_pc_trial_20261028/loaded_route_trials'/run/'LOADED_ROUTE_RESULT.json'
        for name, source in [('PLAN.json', plan_path), ('RESULT.json', result_path),
                             ('COPPELIA.json', BASE/plan_rel/'COPPELIA_VERIFICATION.json'),
                             ('ACCEPTANCE.json', BASE/accepted_rel)]:
            copy(source, folder/'evidence'/name)
            provenance.append({'package_path': (folder/'evidence'/name).relative_to(dest).as_posix(),
                               'original_repository_path': source.relative_to(ROOT).as_posix(), 'sha256': sha(source)})
        plan = read(plan_path)
        sequence = []
        golden = []
        phases = []
        def event(label, key):
            sequence.append({'index': len(sequence), 'label': label, 'kind': 'gripper_event', 'wire_json': plan[key]})
        for stage in plan['stages']:
            data = stage['stage']
            begin = len(sequence)
            for i, frame in enumerate(data['stream_frames']):
                sequence.append({'index': len(sequence), 'label': stage['phase'], 'kind': 'motion',
                                 'sample_in_stage': i, 'period_s': data['period_s'],
                                 'stage_offset_s': i*data['period_s'], 'wire_json': frame['wire_json']})
                golden.append(q16_hex(json.loads(frame['wire_json'])))
            phases.append({'phase': stage['phase'], 'carrying': stage['carrying'],
                           'request_start_index': begin, 'request_end_index_inclusive': len(sequence)-1,
                           'motion_samples': len(data['stream_frames']), 'period_s': data['period_s'],
                           'nominal_motion_seconds': data['nominal_motion_seconds'],
                           'target_firmware_rad': data['target_firmware_rad']})
            if stage['phase'] == 'DIRECT_PREGRASP':
                event('OPEN_HIGH', 'open_before_descent_wire_json')
            elif stage['phase'] == 'DESCEND':
                event('CLOSE_SOURCE', 'close_after_descent_wire_json')
            elif stage['phase'] == 'PLACE':
                event('RELEASE', 'release_wire_json')
        event('PARK_CLOSE', 'park_close_wire_json')
        (folder/'sequence.jsonl').write_text(''.join(json.dumps(x,separators=(',',':'))+'\n' for x in sequence),encoding='utf-8')
        (folder/'commands.jsonl').write_text(''.join(x['wire_json']+'\n' for x in sequence),encoding='utf-8')
        (folder/'motion_q16.mem').write_text('\n'.join(golden)+'\n',encoding='ascii')
        write(folder/'phase_map.json', phases)
        source = plan['request']['pickup']['centre_mm']
        item = {'object_class': cls, 'mode_b_class_id': class_id, 'operator_accepted': True,
                'physically_tested_speed_multiplier': plan['speed_multiplier'], 'source_centre_mm': source,
                'yaw_deg': plan['request']['pickup']['yaw_deg'], 'requests': len(sequence),
                'motion_samples': len(golden), 'nominal_motion_seconds': plan['nominal_motion_seconds'],
                'close_command': json.loads(plan['close_after_descent_wire_json']),
                'local_transfer': plan['local_transfer']}
        if cls == 'eraser':
            item['correction_locality'] = plan['source_correction_locality']
        objects.append(item)
        write(folder/'PROFILE.json', item)
    # Keep original calibration/offset records for provenance without rewriting their hashes or acceptance flags.
    evidence_paths = [BASE/'today_native_anchor/ACCEPTED_NATIVE_SOURCE_ANCHOR.json',
                      BASE/'cylinder_trial_v2/OPERATOR_GRASP_OFFSET.json',
                      BASE/'eraser_right10_trial_v1/OPERATOR_GRASP_OFFSET.json',
                      BASE/'eraser_right10_trial_v1/EXECUTION_VERIFICATION.json',
                      BASE/'eraser_right10_trial_v1/SOFTWARE_VERIFICATION.json']
    for source in evidence_paths:
        if not source.exists():
            continue
        rel = Path('reference_evidence')/source.relative_to(BASE)
        copy(source, dest/rel)
        provenance.append({'package_path': rel.as_posix(), 'original_repository_path': source.relative_to(ROOT).as_posix(),
                           'sha256': sha(source)})
    source_snapshot(dest)
    write(dest/'PROVENANCE.json', provenance)
    write(dest/'DYNAMIC_INPUT_EXAMPLE.json', {
        'schema': 'gesture.mode_b.teammate_input_draft.v1', 'wire_protocol_implemented': False,
        'profile': 'MODE_B_DYNAMIC', 'task_id': 'REPLACE_WITH_FRESH_UNIQUE_ID',
        'frame_id': 'REPLACE_WITH_NPU_FRAME_ID', 'capture_utc': 'REPLACE_WITH_FRESH_TIMESTAMP',
        'npu_execution_evidence': 'REQUIRED_SEPARATELY', 'frame': 'desk_global_mm',
        'object_class': 'eraser', 'mode_b_class_id': 2, 'size_mm': [65,15,15],
        'pickup': {'centre_mm': objects[2]['source_centre_mm'], 'yaw_deg': objects[2]['yaw_deg'],
                   'yaw_semantics': 'DETECTED_LONG_AXIS_DEGREES'},
        'destination': {'support_centre_mm': [285,195,150], 'size_xy_mm': [80,80], 'rim_height_mm': 0},
        'calibration_sha256': read(BASE/'today_native_anchor/ACCEPTED_NATIVE_SOURCE_ANCHOR.json')['table_transform_sha256'],
        'home_id': read(dest/'HOME.json')['home_id'], 'speed_multiplier': 3,
        'raw_source_must_remain_unchanged': True, 'offsets_applied_once_in_motion_adapter': True})
    write(dest/'PACKAGE.json', {'schema': 'gesture.mode_b.teammate_handoff.v1', 'date': '2026-10-28',
                               'hardware_execution_enabled': False, 'objects': objects,
                               'npu_fpga_closed_loop_accepted': False,
                               'scope': 'ACCEPTED_TTL_REFERENCE_AND_FPGA_INTEGRATION_REVIEW'})
    write(dest/'MANIFEST.json', {'algorithm': 'SHA256', 'files': {
        p.relative_to(dest).as_posix(): {'bytes': p.stat().st_size, 'sha256': sha(p)}
        for p in sorted(dest.rglob('*')) if p.is_file()}})
    report = verify(dest)
    archive = dest.with_suffix('.zip')
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for p in sorted(dest.rglob('*')):
            if p.is_file():
                z.write(p, (Path(dest.name)/p.relative_to(dest)).as_posix())
    with zipfile.ZipFile(archive) as z:
        if z.testzip() is not None:
            raise ValueError('ZIP CRC failed')
        for name, expected in read(dest/'MANIFEST.json')['files'].items():
            if hashlib.sha256(z.read(dest.name+'/'+name)).hexdigest() != expected['sha256']:
                raise ValueError('ZIP manifest mismatch: '+name)
    print(json.dumps({'verification': report, 'archive': archive.name, 'bytes': archive.stat().st_size,
                      'archive_sha256': sha(archive)},ensure_ascii=False))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=DEST)
    build(parser.parse_args().output)
