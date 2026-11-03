"""Offline Mode B integration artifacts. No transport or physical executor."""
from __future__ import annotations

from copy import deepcopy
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys

from pc import planner_p2p_reference as pc_reference
from .export import load_package
from .state_machine import TaskMachine, simulate_task
from .trajectory import regenerate, sample_digest


OBJECTS = ("red_cube", "eraser", "small_canister")
PROFILE = "mode_b_red_eraser_canister_v1"
JOINTS = ["b", "s", "e", "t", "r", "g"]


def encode_sample(row):
    """One readmemh word: 192 bits, b in bits 31:0, g in bits 191:160."""
    if len(row) != 6 or any(type(v) is not int or not -(1 << 31) <= v < (1 << 31) for v in row):
        raise ValueError("Expected six signed int32 channels")
    return "".join(f"{v & 0xffffffff:08X}" for v in reversed(row))


def read_samples(path):
    rows = []
    for line_number, line in enumerate(Path(path).read_text(encoding="ascii").splitlines(), 1):
        word = line.split("//", 1)[0].strip()
        if not word:
            continue
        if len(word) != 48 or any(c not in "0123456789abcdefABCDEF" for c in word):
            raise ValueError(f"Expected one 192-bit hex word at line {line_number}")
        unsigned = [int(word[i:i+8], 16) for i in range(0, 48, 8)]
        rows.append(tuple(v if v < (1 << 31) else v-(1 << 32) for v in reversed(unsigned)))
    return rows


def compare_samples(expected_path, actual_path):
    expected, actual = read_samples(expected_path), read_samples(actual_path)
    if not expected:
        raise ValueError("Empty expected sample stream")
    first = None
    for index, (a, b) in enumerate(zip(expected, actual)):
        if a != b:
            first = {"sample_index": index, "expected_q16": list(a), "actual_q16": list(b)}
            break
    return {"passed": len(expected) == len(actual) and first is None,
            "expected_samples": len(expected), "actual_samples": len(actual),
            "first_mismatch": first, "expected_sample_sha256": sample_digest(expected),
            "actual_sample_sha256": sample_digest(actual),
            "scope": "ACCEPTED_SAMPLE_VALUES_ONLY_NOT_TIMING_OR_PHYSICAL_MOTION"}


def load_blocks(plan, path):
    """Apply the draft block size to normal AND cancellation routes."""
    chunks = []
    cursor = list(path["start_q16"])
    for offset in range(0, len(path["segments"]), 32):
        segments = deepcopy(path["segments"][offset:offset+32])
        if segments[0]["start_q16"] != cursor:
            raise ValueError("Block start discontinuity")
        chunks.append({"index": len(chunks), "first_segment_index": offset,
                       "start_q16": cursor, "segments": segments,
                       "requires_previous_chunk_done": bool(chunks)})
        cursor = list(segments[-1]["target_q16"])
    if cursor != plan["start_q16"]:
        raise ValueError("Route does not finish at simulation HOME")
    return chunks


def verify_adapter(plan, adapter):
    required = {"physical_execution_allowed": False, "mode_a_tables_changed": False,
                "whole_task_atomic_validation_required": True,
                "status": "REQUIRES_FPGA_TEAM_ADAPTER_REVIEW_NOT_LEGACY_PATH_SUBMIT",
                "joint_mapping": "UNVERIFIED_URDF_TO_DEVICE"}
    if any(adapter.get(k) != v for k, v in required.items()):
        raise ValueError("Unexpected adapter deployment or contract state")
    for key in ("task_id", "config_sha256", "sample_sha256"):
        if adapter.get(key) != plan[key]:
            raise ValueError("Adapter/task identity mismatch")
    chunks = load_blocks(plan, plan)
    # Older draft chunks have no first_segment_index. Compare their full content.
    for chunk in chunks:
        chunk.pop("first_segment_index")
    if adapter.get("chunks") != chunks or adapter.get("cancel_branches") != plan["cancel_branches"]:
        raise ValueError("Adapter route differs from checked task")


def _load_reference(root, relative, suffix):
    name = "_mode_b_review_reference_"+suffix
    spec = importlib.util.spec_from_file_location(name, root/relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+"\n", encoding="utf8")


def _files(directory):
    return {p.relative_to(directory).as_posix(): {"sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
            "bytes": p.stat().st_size} for p in sorted(directory.rglob("*"))
            if p.is_file() and p != directory/"MANIFEST.json"}


def build_review(root, examples, output):
    """Copy verified plans; export accepted-sample goldens and PS/PYNQ parity."""
    root, examples, output = Path(root), Path(examples), Path(output)
    if output.exists():
        raise ValueError("Output must be new; existing evidence is never overwritten")
    references = {"pc": pc_reference,
        "ps": _load_reference(root, Path("ps/robot/planner_p2p_reference.py"), "ps"),
        "pynq": _load_reference(root, Path("pynq/planner_p2p_reference.py"), "pynq")}
    # Validate every source before creating the output folder.
    loaded = {}
    for name in OBJECTS:
        folder = examples/name
        plan, config = load_package(folder/"complete_task.json")
        adapter = json.loads((folder/"fpga_adapter_draft.json").read_text(encoding="utf8"))
        verify_adapter(plan, adapter)
        mesh = json.loads((folder/"coppelia_verification.json").read_text(encoding="utf8"))
        if not mesh.get("passed") or any(mesh.get(k) != plan[k]
                for k in ("plan_sha256", "config_sha256", "sample_sha256", "urdf_sha256")):
            raise ValueError("Mesh replay report does not match verified plan")
        if (set(mesh.get("cancel_branches", {})) != set(plan["cancel_branches"]) or
                not all(b["passed"] for b in mesh["cancel_branches"].values())):
            raise ValueError("Cancellation replay evidence incomplete")
        if (plan["object_class"] != name or plan["mode"] != "B" or
                plan["joint_order"] != JOINTS or plan["joint_space"] != "URDF_SIMULATION_RAD_NOT_FIRMWARE_RAD" or
                plan["deployment"]["physical_execution_allowed"] is not False or
                not simulate_task(plan)["complete"]):
            raise ValueError("Unsupported task/profile or deployment state")
        loaded[name] = plan, config
    first_plan, first_config = loaded[OBJECTS[0]]
    destination = first_plan["request"]["destination"]
    if any(c != first_config or p["request"]["destination"] != destination for p, c in loaded.values()):
        raise ValueError("The shared handoff must have one configuration and destination")
    output.mkdir(parents=True)
    inventory, tools, total_segments, total_samples = [], {}, 0, 0
    for name, (plan, config) in loaded.items():
        folder = output/"tasks"/name
        shutil.copytree(examples/name, folder)
        routes = {"normal": plan, **{"cancel_"+k.lower(): v for k, v in plan["cancel_branches"].items()}}
        blocks, route_results, phase_rows = {}, [], []
        for route_name, route in routes.items():
            rows, moves = [], []
            for index, (segment, values) in enumerate(regenerate(route["start_q16"], route["segments"], config)):
                for reference_name, ref in references.items():
                    move = ref.MoveParams(tuple(segment["start_q16"]), tuple(segment["target_q16"]),
                        segment["n"], segment["na"], segment["profile"], segment["period_cycles"],
                        config["clock_hz"], tuple(segment["vmax_q16"]), tuple(segment["amax_q32"]))
                    if not ref.validate(move, move.start).ok or ref.samples(move) != values:
                        raise ValueError(f"{reference_name} reference mismatch: {name}/{route_name}/{index}")
                moves.append({"segment_index": index, "sample_offset": len(rows), **deepcopy(segment),
                              "stall_timeout_cycles": config["clock_hz"]})
                phase_rows.append([route_name, index, segment["phase"], len(rows), segment["n"],
                    segment["na"], segment["period_cycles"], segment["payload_attached"], segment["event_after"] or ""])
                rows.extend(values)
            if len(rows) != route["sample_count"] or sample_digest(rows) != route["sample_sha256"]:
                raise ValueError("Route golden sample mismatch")
            golden = folder/(route_name+"_samples_192.mem")
            golden.write_text("// Accepted samples: g r t e s b, each signed int32 Q16.16; sample0 NOT emitted.\n"+
                              "\n".join(encode_sample(r) for r in rows)+"\n", encoding="ascii")
            if read_samples(golden) != rows:
                raise ValueError("Golden packing round trip mismatch")
            with (folder/(route_name+"_moves.jsonl")).open("w", encoding="utf8") as stream:
                for move in moves:
                    stream.write(json.dumps(move, ensure_ascii=False, allow_nan=False)+"\n")
            blocks[route_name] = {"start_q16": route["start_q16"], "requires": route.get("requires", []),
                                 "chunks": load_blocks(plan, route)}
            route_results.append({"route": route_name, "segments": len(moves), "samples": len(rows),
                                  "sample_sha256": route["sample_sha256"], "references_match": ["pc", "ps", "pynq"]})
            total_segments += len(moves)
            total_samples += len(rows)
        _json(folder/"load_blocks.json", {"schema": "gesture.mode_b.offline_load_blocks.v1",
              "task_id": plan["task_id"], "plan_sha256": plan["plan_sha256"],
              "profile_id": PROFILE, "physical_execution_allowed": False,
              "not_legacy_path_submit": True, "routes": blocks})
        with (folder/"phase_map.csv").open("w", encoding="utf8", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(["route", "segment_index", "phase", "sample_offset", "n", "na", "period_cycles", "payload_attached", "event_after"])
            writer.writerows(phase_rows)
        # Guard checks exercise the actual task reference without supplying events.
        machine = TaskMachine(plan)
        segment = machine.next_segment(0)
        if machine.next_segment(1) is not None or machine.feedback("wrong_task", [v/65536 for v in segment["target_q16"]], settled=True):
            raise ValueError("Duplicate or wrong-task guard failed")
        machine.fault("OFFLINE_LINK_LOSS_TEST")
        if machine.next_segment(100) is not None:
            raise ValueError("Fault hold guard failed")
        inventory.append({"object_class": name, "gesture_object_id": plan["gesture_object_id"],
            "plan_sha256": plan["plan_sha256"], "config_sha256": plan["config_sha256"],
            "task_directory": "tasks/"+name, "routes": route_results,
            "seconds_excluding_waits": plan["nominal_motion_seconds"],
            "guard_checks": "DUPLICATE_WRONG_TASK_FAULT_HOLD_PASSED"})
        tools[name] = {"grasp_width_mm": plan["grasp_model"]["object_width_mm"],
            "T_link5_grasp": plan["grasp_model"]["link5_from_grasp_mm"],
            "T_grasp_object_at_attachment": plan["attachment"]["grasp_from_object"],
            "gripper": plan["gripper"]}
    _json(output/"SIMULATION_HOME_AND_TOOLS.json", {
        "schema": "gesture.mode_b.nominal_home_tools.v1", "status": "SIMULATION_ONLY_NOT_FIRMWARE_VALUES",
        "physical_execution_allowed": False, "joint_order": JOINTS,
        "home_q16": first_plan["start_q16"], "home_rad_after_quantization": [v/65536 for v in first_plan["start_q16"]],
        "table_from_urdf_world": first_config["table_from_urdf_world"],
        "transform_convention": "T_parent_child maps child coordinates to parent; translation mm; column vectors",
        "fk_chain": "T_desk_grasp = T_desk_urdf_world * URDF(q + joint_bias) * T_link5_grasp(object_width) * T_tool_residual",
        "residual": first_config["residual"], "objects": tools,
        "physical_home_source_for_comparison_only": "docs/phase3c/mode1_red_fpga_handoff_20261027/HOME.json"})
    _json(output/"PHYSICAL_CALIBRATION_TEMPLATE.json", {
        "schema": "gesture.mode_b.physical_calibration_inputs.v1", "status": "INCOMPLETE_NOT_EXECUTABLE",
        "physical_execution_allowed": False, "joint_order": JOINTS,
        "physical_home_firmware_rad": None, "T_desk_firmware_base": None,
        "joint_mapping": {"formula_candidate": "firmware_rad = sign * simulation_rad + offset_rad",
                          "sign": [None]*6, "offset_rad": [None]*6, "verified": False,
                          "gripper_requires_separate_nonlinear_width_mapping": True},
        "physical_tools_by_grasp_width": None, "gripper_width_mapping": None,
        "measured_limits_and_payload_speeds": None, "residual_validation_samples": None,
        "destination_support": {"planned": destination, "measured": None},
        "evidence_required": ["timestamp_and_installation_id", "raw_firmware_feedback", "desk_xyz_and_reference_definition",
                              "held_out_fk_position_and_orientation_errors", "tracking_error_and_clearance_budget"],
        "existing_data_policy": "Reuse matching-installation successful evidence; do not fit mixed TCP definitions or incompatible joint spaces."})
    _json(output/"HANDOFF.json", {"schema": "gesture.mode_b.fpga_review_bundle.v1", "profile_id": PROFILE,
        "status": "OFFLINE_INTEGRATION_REVIEW", "physical_execution_allowed": False,
        "destination": destination, "period_s": first_config["period_s"], "clock_hz": first_config["clock_hz"],
        "joint_order": JOINTS, "joint_space": first_plan["joint_space"], "task_load_block_max_segments": 32,
        "tasks": inventory, "total_routes": 12, "total_segments": total_segments, "total_samples": total_samples,
        "reference_parity_scope": "Python PC/PS/PYNQ copies; not an RTL run or board test",
        "timing_verification": "NOT_RUN_ON_RTL_OR_BOARD", "sample_layout": "192 bits; b low 32 bits; g high 32 bits; signed Q16.16 rad",
        "sample_rule": "Sample k=1..N; initial sample0 absent; hold/wait cycles do not add accepted samples",
        "event_gates": {"GRASP_VERIFIED": "before lift", "PALM_READY": "buffer and delivery TTL",
                        "SUPPORT_VERIFIED": "before release, with valid PALM_READY",
                        "SOURCE_VACANT": "before cancellation descent",
                        "PLACEMENT_AND_EMPTY_HOME_VERIFIED": "normal complete",
                        "CANCEL_PLACEMENT_AND_EMPTY_HOME_VERIFIED": "required board-adapter extension for cancellation complete"},
        "fault_policy": "HOLD; no arbitrary-state auto HOME, no blind resend or resume",
        "cancel_policy": "Only exact validated stationary LIFT/BUFFER/PREPLACE endpoint; otherwise HOLD and replan from fresh feedback",
        "reference_source_sha256": {str(p): hashlib.sha256((root/p).read_bytes()).hexdigest()
             for p in (Path("pc/planner_p2p_reference.py"), Path("ps/robot/planner_p2p_reference.py"),
                       Path("pynq/planner_p2p_reference.py"))}})
    sources = [Path("pc/planner_p2p_reference.py"), Path("ps/robot/planner_p2p_reference.py"),
        Path("pynq/planner_p2p_reference.py"), Path("rtl/robot/planner_p2p_core.v"),
        Path("rtl/robot/planner_seq_mult.v"), Path("rtl/robot/planner_seq_div.v"),
        Path("pc/mode_b/motion/state_machine.py")]
    for relative in sources:
        target = output/"reference_sources"/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root/relative, target)
    # Preserve package-relative imports so a teammate can verify the ZIP alone.
    tool_sources = [Path("pc/planner_p2p_reference.py"), Path("scripts/build_mode_b_fpga_review.py")]
    tool_sources += [p.relative_to(root) for p in (root/"pc/mode_b/motion").glob("*.py")]
    for relative in tool_sources:
        target = output/"review_tools"/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root/relative, target)
    (output/"review_tools/requirements.txt").write_text("numpy>=1.26\nscipy>=1.13\n", encoding="ascii")
    (output/"README_CN.md").write_text(r'''# 模式B FPGA离线交接：从整程仿真到板端对照

此包提供红块、橡皮和圆柱的3条正常任务与9条取消归还路径，当前承托面中心为(260,160,30)mm。三类均已通过名义运动学和CoppeliaSim网格回放。包内数值属于URDF仿真关节空间；状态为OFFLINE_INTEGRATION_REVIEW，实体执行标志false。

## 队友可以立即做的事

1. 离线核对完整任务装载、分块、事件等待和取消分支；再将参数喂给既有planner_p2p_core仿真或板端无机械臂的输出记录器。
2. 在m_valid && m_ready时记录192位样本，和相应MEM逐字比较。正式运行由PL生成周期样本，MEM仅为检查用黄金样本。
3. 对照通过后反馈真实时钟、周期、板端格式/容量、事件来源与日志；实体标定和设备单位转换单独完成。

模式A继续用原1红/2黄/3蓝固定表。模式B必须带profile_id=mode_b_red_eraser_canister_v1，独立解释为1红块/2橡皮/3圆柱。不要把任务号单独当作物品类型。

## 文件用途

| 文件 | 用途 |
| --- | --- |
| HANDOFF.json | 任务/计划哈希、全路径计数、事件、周期和通道约定 |
| SIMULATION_HOME_AND_TOOLS.json | 仿真HOME、各物宽的完整工具矩阵、附着矩阵；与实机HOME分开 |
| PHYSICAL_CALIBRATION_TEMPLATE.json | 后续实测项，缺失值为null，不能靠改true来通过验收 |
| tasks/*/complete_task.json | 经仿真检查的整程稀疏任务与取消分支 |
| tasks/*/load_blocks.json | 正常和取消路径均按每块≤32段装载；不是旧PATH_SUBMIT |
| tasks/*/phase_map.csv | 每一段的状态、样本偏移、持物状态和后置事件 |
| tasks/*/*_moves.jsonl | 按顺序装载的PL参数；含start/target/n/na/profile/period/vmax/amax/stall |
| tasks/*/*_samples_192.mem | 每行192bit，低32位b，高32位g；负数为二补码Q16.16 |
| tasks/*/coppelia_verification.json | 正常与取消网格回放原报告 |
| reference_sources/ | 当时的PC/PS/PYNQ参考、PL插补RTL与任务状态机快照 |
| review_tools/ | 可离线运行的包校验与样本比较工具 |
| MANIFEST.json | 包内全部文件的哈希和长度 |

## 解压后离线校验

已有numpy/scipy时直接运行第二条；依赖不足时在独立Python环境安装第一条。命令均在本README所在目录执行，不访问相机、网络、串口或机械臂。

```powershell
python -m pip install -r .\review_tools\requirements.txt
python -B .\review_tools\scripts\build_mode_b_fpga_review.py --verify .
```

正常应输出passed=true、tasks=3、routes=12、samples=10515。比较一个红块正常流程的实际输出：

```powershell
python -B .\review_tools\scripts\build_mode_b_fpga_review.py --compare-mem .\tasks\red_cube\normal_samples_192.mem C:\capture\red_normal_actual.mem
```

样本k=1..N，起点sample0不输出。只记录接受握手时刻，不记录等待重复值。数据匹配不证明20ms时序、背压/急停或实体跟随；这些需另外验收。当前三份Python参考逐样本一致，不宣称已运行RTL或板测。

## 事件与故障

夹取后GRASP_VERIFIED才抬升；BUFFER持物等待PALM_READY；交付段按预计结束时间检查PALM_READY有效期，松爪前还要SUPPORT_VERIFIED；结束必须有PLACEMENT_AND_EMPTY_HOME_VERIFIED。事件来自真实感知/传感器或明确标记的调试确认，不能以固定等待代替。运行中撤销许可、反馈超时、重复任务必须由板端适配层落实。

取消只在已检查LIFT/BUFFER/PREPLACE静止端点开放，归还原取物位前确认SOURCE_VACANT。运动中/误差端点取消先HOLD并以新反馈重算。取消完成还需实体归还成功与空夹HOME证据，板端适配扩展事件CANCEL_PLACEMENT_AND_EMPTY_HOME_VERIFIED；现有TaskMachine只演示正常任务，未实现完整取消执行器。

未知姿态、持物故障或断链不自动回HOME。恢复必须从新反馈确定连接路径。该包没有实体通信实现，不能直接将URDF数值发送为固件T102/T104。

## 实体阶段还需补齐

优先筛选同安装、同固定爪/夹取中心定义的旧成功记录。实机HOME、桌面到固件基座变换、关节零位/符号/偏置、夹爪开口非线性映射、不同物宽工具中心、负载限速与跟随残差需验收。现有模式A历史HOME仅供比较，不自动套入本模型。

承托物按90×90mm无凸边建模，高度30mm；尺寸与实际支架/手臂包络待核对。仿真刚性持物，未验证摩擦、夹持力、掉落或落稳。NPU和ROCm目标机、当前毫米定位及FPGA整任务适配仍需独立验收。
''', encoding="utf8")
    _json(output/"MANIFEST.json", {"schema": "gesture.mode_b.review_bundle_manifest.v1", "files": _files(output)})
    return json.loads((output/"HANDOFF.json").read_text(encoding="utf8"))


def verify_review(output):
    """Recheck transferred artifact files, references, routes and golden packing."""
    output = Path(output)
    manifest = json.loads((output/"MANIFEST.json").read_text(encoding="utf8"))
    actual = _files(output)
    if actual != manifest["files"]:
        raise ValueError("Review bundle file/hash set mismatch")
    handoff = json.loads((output/"HANDOFF.json").read_text(encoding="utf8"))
    if handoff["physical_execution_allowed"] is not False or handoff["profile_id"] != PROFILE:
        raise ValueError("Unexpected handoff deployment/profile")
    segments, samples = 0, 0
    for name in OBJECTS:
        folder = output/"tasks"/name
        plan, config = load_package(folder/"complete_task.json")
        blocks = json.loads((folder/"load_blocks.json").read_text(encoding="utf8"))
        for route_name, route in {"normal": plan, **{"cancel_"+k.lower(): v for k, v in plan["cancel_branches"].items()}}.items():
            if blocks["routes"][route_name]["chunks"] != load_blocks(plan, route):
                raise ValueError("Load blocks differ from checked route")
            rows = [r for _, values in regenerate(route["start_q16"], route["segments"], config) for r in values]
            if rows != read_samples(folder/(route_name+"_samples_192.mem")):
                raise ValueError("Golden stream differs from checked route")
            moves = [json.loads(line) for line in (folder/(route_name+"_moves.jsonl")).read_text(encoding="utf8").splitlines()]
            expected_moves = [{"segment_index": i, "sample_offset": s["sample_offset"], **s,
                               "stall_timeout_cycles": config["clock_hz"]} for i, s in enumerate(route["segments"])]
            if moves != expected_moves:
                raise ValueError("Move descriptors differ from checked route")
            segments += len(moves)
            samples += len(rows)
    if segments != handoff["total_segments"] or samples != handoff["total_samples"]:
        raise ValueError("Bundle route totals mismatch")
    return {"passed": True, "tasks": 3, "routes": 12, "segments": segments, "samples": samples,
            "physical_execution_allowed": False}
