"""Compile an accepted trajectory for one persistent TTL session (no hardware)."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAMES = ('b', 's', 'e', 't', 'r', 'g')
ENGINE = ROOT / 'pc/mode_b/RestockSerialSession.cs'


def read(path):
    return json.loads(Path(path).read_text('utf-8-sig'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def compile_session(plan_file, verification_file, acceptance_file):
    plan_file, verification_file, acceptance_file = map(Path, (plan_file, verification_file, acceptance_file))
    plan, sim, acceptance = map(read, (plan_file, verification_file, acceptance_file))
    if not sim['passed'] or sim['route_sha256'] != sha(plan_file):
        raise ValueError('Exact native mesh verification required')
    if (acceptance['status'] != 'OPERATOR_ACCEPTED_COMPLETE_RESTOCK' or
            acceptance['plan_sha256'] != sha(plan_file) or
            sha(acceptance['result_file']) != acceptance['result_sha256']):
        raise ValueError('Bound operator acceptance of this exact plan required')
    from prepare_mode_b_restock import validate_plan
    validate_plan(plan_file)
    operations = []

    def event(value):
        command = json.loads(value['wire_json'])
        if command['T'] != 106 or command['spd'] <= 0:
            raise ValueError('Unexpected gripper event')
        operations.append(dict(kind='event', label=value['label'], wires=[value['wire_json']],
            period_ms=0, settle_ms=0, target_g=command['cmd'], gripper_spd=command['spd']))

    event(plan['initial_event'])
    for stage in plan['stages']:
        frames = stage['stage']['stream_frames']
        period = stage['stage']['period_s'] * 1000
        if not frames or not math.isfinite(period) or period != 20:
            raise ValueError('Checked 20ms native stream required')
        wires = [f['wire_json'] for f in frames]
        for wire in wires:
            command = json.loads(wire)
            if command['T'] != 102:
                raise ValueError('Only original native T102 frames')
        label = stage['phase']
        # filid uses22 ticks of settling between non-grouped arm legs. Keep
        # a larger pause at contact endpoints, plus fresh spaced observations.
        settle = 800 if label.endswith(('PUBLIC_DESCEND', 'SOURCE_DESCEND')) else 440
        operations.append(dict(kind='stream', label=label, wires=wires, period_ms=period,
            settle_ms=settle, target=[stage['stage']['target_firmware_rad'][n] for n in NAMES]))
        if label in plan['event_after_stage']:
            event(plan['event_after_stage'][label])
    event(plan['final_event'])
    if len(operations) != 17 or plan['task_kind'] != 'RESTOCK':
        raise ValueError('This candidate only supports the accepted complete13+4 restock')
    wire_hash = hashlib.sha256(''.join(w+'\n' for op in operations for w in op['wires']).encode()).hexdigest()
    return dict(schema='gesture.mode_b.restock_serial_session.v1',
        plan_file=str(plan_file.resolve()), plan_sha256=sha(plan_file),
        simulation_file=str(verification_file.resolve()), simulation_sha256=sha(verification_file),
        acceptance_file=str(acceptance_file.resolve()), acceptance_sha256=sha(acceptance_file),
        engine_sha256=sha(ENGINE), original_source_mm=plan['return_centre_mm'],
        start=[plan['start_firmware_rad'][n] for n in NAMES],
        entry_limits_deg=[plan['arrival_tolerance_deg'][n] for n in NAMES],
        operations=operations, ordered_wire_lf_sha256=wire_hash,
        requests=sum(len(op['wires']) for op in operations), nominal_motion_seconds=plan['nominal_motion_seconds'],
        original_geometry_and_gripper_wires_unchanged=True,
        period_ms=20, query_period_ms=100, feedback_timeout_ms=2000,
        physical_execution_of_session_accepted=False)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--plan', required=True, type=Path)
    ap.add_argument('--verification', required=True, type=Path)
    ap.add_argument('--acceptance', required=True, type=Path)
    ap.add_argument('--output', required=True, type=Path)
    args = ap.parse_args()
    value = compile_session(args.plan, args.verification, args.acceptance)
    if args.output.exists() and read(args.output) != value:
        ap.error('Use a fresh output for a changed session')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(value, indent=2)+'\n', 'utf8')
    print(json.dumps({k: value[k] for k in ('requests', 'nominal_motion_seconds', 'ordered_wire_lf_sha256')}))
