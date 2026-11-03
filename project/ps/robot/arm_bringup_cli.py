"""Profile/protocol bring-up CLI for RoArm-M3-Pro and SO-ARM101 (PC or PYNQ PS).

Safe commands (no port is opened):

    python arm_bringup_cli.py check      <profile.yaml>
    python arm_bringup_cli.py preview    <profile.yaml> --mem <golden.mem> --segment 2
    python arm_bringup_cli.py pl-config  <profile.yaml> [--out image.json]

Gated commands (refused until the profile and the official protocol file are
complete; see UNKNOWN_PARAMETERS.yaml):

    python arm_bringup_cli.py listen     <profile.yaml> --seconds 10
        RoArm: open the port and print feedback lines only (robot_readonly).
    python arm_bringup_cli.py rate-test  <profile.yaml> --rate-hz 20 --seconds 5
        RoArm: read the current pose from feedback, then send set_joints with
        exactly that pose (zero motion) at the requested rate and report the
        achieved rate, write time and feedback latency.  Needs purpose=robot.

Opening an ESP32 port can reset the controller: keep the e-stop in hand.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Sequence

import arm_backend as ab
import arm_frame_template as aft
from arm_fixed_point import map_joint_vector, unpack_192
from arm_profile import ArmProfile, ProfileError, RealOutputBlocked
from arm_serial_common import percentile
from roarm_json_reference import (
    ProtocolFieldMissing,
    RoArmJsonProtocol,
    encode_command,
    parse_feedback_line,
    preview_command,
)
from roarm_serial_transport import RoArmSerialTransport
import so101_feetech_reference as ft


def load(profile_path: Path):
    profile = ArmProfile.load(profile_path)
    if profile.backend == "so101_feetech":
        protocol = ft.FeetechProtocol.load(profile.protocol_file)
    else:
        protocol = RoArmJsonProtocol.load(profile.protocol_file)
    return profile, protocol


def cmd_check(profile, protocol) -> dict:
    blockers = list(profile.missing_for_real_output())
    if isinstance(protocol, RoArmJsonProtocol):
        blockers += protocol.missing_fields(required_channels=profile.required_feedback_channels)
    else:
        blockers += protocol.missing_fields()
    return {
        "profile": str(profile.path),
        "backend": profile.backend,
        "bench_only": profile.bench_only,
        "mapping_complete": profile.mapping_complete(),
        "real_output_ready": not blockers,
        "status": "READY_FOR_ROBOT" if not blockers else "BLOCKED_EXTERNAL_INPUT",
        "blockers": blockers,
    }


def cmd_preview(profile, protocol, samples) -> dict:
    frames = []
    maps = profile.channel_maps() if profile.mapping_complete() else None
    for index, sample in enumerate(samples[:3] + samples[-1:]):
        devices = map_joint_vector(sample, maps)[0] if maps else (None,) * 6
        if isinstance(protocol, RoArmJsonProtocol):
            preview = preview_command(protocol, "set_joints", devices)
            frames.append({"sample": index, "sendable": preview.sendable, "text": preview.text,
                           "blockers": list(preview.blockers)})
        else:
            blockers = protocol.codec_blockers()
            if blockers or maps is None:
                frames.append({"sample": index, "sendable": False,
                               "text": f"<Feetech sync-write, values {devices}>",
                               "blockers": blockers + ([] if maps else ["unit mapping TBD"])})
            else:
                data, _ = ft.sync_write_positions(protocol, [m.device_id for m in maps], devices)
                frames.append({"sample": index, "sendable": False, "hex": data.hex(" "), "blockers": []})
    return {"profile": str(profile.path), "frames": frames}


def cmd_pl_config(profile, protocol) -> dict:
    config = ab.build_pl_config(profile, protocol)
    return {
        "source": config.source,
        "backend_sel": config.backend_sel,
        "baud_div": [config.baud_div_roarm, config.baud_div_bus],
        "template_words": {"cmd": config.template.cmd_words, "req": config.template.req_words},
        "template_ram": [f"{w:04X}" for w in config.template.ram[: config.template.cmd_words + config.template.req_words]],
        "channel_maps": [m.__dict__ for m in config.channel_maps],
        "required_mask": config.required_mask,
        "reads_per_cycle": config.reads_per_cycle,
        "feedback_timeout_ticks": config.feedback_timeout_ticks,
    }


def cmd_listen(profile, protocol, seconds: float) -> dict:
    permit = ab.require_real_output(profile, protocol, purpose="robot_readonly")
    records = 0
    with RoArmSerialTransport(profile.transport.port, profile.transport.baudrate, permit=permit,
                              dry_run=False) as transport:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            line = transport.read_line(0.2)
            if line is None:
                continue
            record = parse_feedback_line(protocol, line.data)
            print(json.dumps({"t_ns": line.timestamp_ns, "raw": line.data.decode("ascii", "replace").strip(),
                              "device_values": record.device_values if record else None}))
            records += record is not None
    return {"feedback_records": records}


def cmd_rate_test(profile, protocol, rate_hz: float, seconds: float) -> dict:
    permit = ab.require_real_output(profile, protocol, purpose="robot")
    with RoArmSerialTransport(profile.transport.port, profile.transport.baudrate, permit=permit,
                              dry_run=False) as transport:
        pose = None
        deadline = time.monotonic() + 3.0
        while pose is None and time.monotonic() < deadline:
            line = transport.read_line(0.2)
            record = parse_feedback_line(protocol, line.data) if line else None
            if record and all(v is not None for v in record.device_values):
                pose = record.device_values
        if pose is None:
            raise RuntimeError("no complete feedback before the rate test; refusing to command")
        frame = encode_command(protocol, "set_joints", pose)        # hold the measured pose
        period = 1.0 / rate_hz
        writes, lateness = [], []
        start = time.perf_counter()
        count = int(seconds * rate_hz)
        for index in range(count):
            target = start + index * period
            delay = target - time.perf_counter()
            if delay > 0:
                time.sleep(delay)
            lateness.append(max(0.0, time.perf_counter() - target))
            record = transport.send_line(frame)
            writes.append(time.perf_counter())
            _ = record
        feedback = transport.stats.rx_lines
    elapsed = writes[-1] - writes[0] if len(writes) > 1 else 0.0
    return {
        "requested_rate_hz": rate_hz,
        "achieved_rate_hz": (len(writes) - 1) / elapsed if elapsed else None,
        "lateness_p95_ms": percentile(lateness, 95.0) * 1000,
        "lateness_max_ms": max(lateness) * 1000,
        "feedback_lines_during_test": feedback,
        "frame_bytes": len(frame),
        "note": "hold-position commands only; feedback latency needs the firmware's echo semantics",
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("check", "preview", "pl-config", "listen", "rate-test"))
    parser.add_argument("profile", type=Path)
    parser.add_argument("--mem", type=Path)
    parser.add_argument("--segment", type=int, default=2)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--seconds", type=float, default=10.0)
    parser.add_argument("--rate-hz", type=float, default=20.0)
    args = parser.parse_args(argv)
    profile, protocol = load(args.profile)
    try:
        if args.command == "check":
            result = cmd_check(profile, protocol)
        elif args.command == "preview":
            if args.mem is None:
                raise SystemExit("--mem is required for preview")
            lines = [l.strip() for l in args.mem.read_text(encoding="ascii").splitlines() if l.strip()]
            samples = [unpack_192(int(lines[args.segment * 32 + i], 16)) for i in range(1, 33)]
            result = cmd_preview(profile, protocol, samples)
        elif args.command == "pl-config":
            result = cmd_pl_config(profile, protocol)
        elif args.command == "listen":
            if profile.backend != "roarm_m3_json":
                raise SystemExit("listen is implemented for the RoArm JSON backend")
            result = cmd_listen(profile, protocol, args.seconds)
        else:
            if profile.backend != "roarm_m3_json":
                raise SystemExit("rate-test is implemented for the RoArm JSON backend")
            result = cmd_rate_test(profile, protocol, args.rate_hz, args.seconds)
    except (RealOutputBlocked, ProfileError, ProtocolFieldMissing, aft.TemplateError) as error:
        print(json.dumps({"command": args.command, "status": "BLOCKED_EXTERNAL_INPUT", "reason": str(error)},
                         indent=2))
        return 3
    if args.out:
        args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, default=str))
    return 0 if result.get("status", "OK") != "BLOCKED_EXTERNAL_INPUT" else 3


if __name__ == "__main__":
    sys.exit(main())
