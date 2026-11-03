"""Portable stdlib-only audit of the accepted red restock, never hardware."""
import argparse
import hashlib
import json
from pathlib import Path


def read(path):
    return json.loads(Path(path).read_text('utf-8-sig'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def sequence(plan):
    output = []
    def event(item):
        output.append(dict(index=len(output), label=item['label'], kind='gripper_event', wire_json=item['wire_json']))
    event(plan['initial_event'])
    for stage in plan['stages']:
        for frame in stage['stage']['stream_frames']:
            output.append(dict(index=len(output), label=stage['phase'], kind='motion',
                               period_s=stage['stage']['period_s'], wire_json=frame['wire_json']))
        if stage['phase'] in plan['event_after_stage']:
            event(plan['event_after_stage'][stage['phase']])
    event(plan['final_event'])
    return output


def q16(wire):
    values = [round(wire[n]*65536) & 0xffffffff for n in ('base','shoulder','elbow','wrist','roll','hand')]
    return ''.join(f'{v:08x}' for v in reversed(values))


def verify(folder, observed=None, pl_samples=None):
    folder = Path(folder).resolve()
    manifest = read(folder/'MANIFEST.json')['files_sha256']
    actual = {p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file()}
    require(actual == set(manifest)|{'MANIFEST.json'}, 'Manifest file set mismatch')
    for name, digest in manifest.items():
        path = (folder/name).resolve()
        require(path.is_relative_to(folder), 'Unsafe manifest path')
        require(sha(path) == digest, 'SHA mismatch: '+name)
    package = read(folder/'PACKAGE.json')
    evidence = package['evidence']
    get = lambda name: read(folder/evidence[name])
    plan, session, result, acceptance = map(get, ('plan','session','result','acceptance'))
    sim, execution, origin = map(get, ('simulation','execution','origin'))
    require(acceptance['status'] == 'OPERATOR_ACCEPTED_COMPLETE_RESTOCK', 'Missing operator acceptance')
    for key in ('plan','session','result'):
        require(acceptance[key+'_sha256'] == sha(folder/evidence[key]), 'Acceptance binding: '+key)
    require(acceptance['execution_verification_sha256'] == sha(folder/evidence['execution']), 'Execution binding')
    require(session['engine_sha256'] == sha(folder/'source/pc/mode_b/RestockSerialSession.cs'), 'Executed source differs')
    require(sim['passed'] and not sim['mesh_collisions'] and sim['route_sha256'] == sha(folder/evidence['plan']), 'Mesh binding')
    require(plan['origin_record_sha256'] == sha(folder/evidence['origin']), 'Original grasp record differs')
    require(plan['return_centre_mm'] == origin['original_pickup']['centre_mm'], 'Dynamic original source differs')
    require(origin['delivery_plan_sha256'] == sha(folder/evidence['delivery_plan']), 'Original delivery plan differs')
    require(origin['delivery_result_sha256'] == sha(folder/evidence['delivery_result']), 'Original delivery evidence differs')
    expected = sequence(plan)
    exported = [json.loads(line) for line in (folder/'sequence.jsonl').read_text('utf8').splitlines()]
    require(exported == expected, 'Exported command sequence differs')
    wires = [(x['label'], x['wire_json']) for x in expected]
    require(wires == [(x['label'], x['wire_json']) for x in result['requests']], 'Actual executed commands differ')
    require(wires == [(op['label'], wire) for op in session['operations'] for wire in op['wires']], 'Session commands differ')
    require(len(wires) == 3835 and len(plan['stages']) == 13, 'Unexpected route shape')
    require(execution['passed'] and result['serial_closed'] and result['release_observed'], 'Incomplete execution')
    require(result['completed_stages'] == [op['label'] for op in session['operations']], 'Incomplete stages')
    require(acceptance['first_request_to_final_feedback_seconds'] == execution['first_request_to_final_feedback_seconds'], 'Timing differs')
    require(len(read(folder/'phase_map.json')) == 9, 'Workflow mapping differs')
    motion = [q16(json.loads(x['wire_json'])) for x in expected if x['kind'] == 'motion']
    require((folder/'motion_q16.mem').read_text('ascii').splitlines() == motion, 'Q16 reference differs')
    if observed:
        rows = [json.loads(line) for line in Path(observed).read_text('utf-8-sig').splitlines()]
        require(len(rows) == len(expected), 'Observed command count differs')
        require(all((a['label'], a['wire_json']) == (b['label'], b['wire_json']) for a,b in zip(rows,expected)), 'Observed commands differ')
    if pl_samples:
        require(Path(pl_samples).read_text('ascii').lower().splitlines() == motion, 'Observed PL samples differ')
    return dict(passed=True, files=len(manifest), requests=len(wires), motion_frames=len(motion),
                gripper_events=len(wires)-len(motion), mesh_samples=sim['samples_checked'],
                actual_seconds=acceptance['first_request_to_final_feedback_seconds'],
                operator_accepted=True, hardware_accessed=False,
                fpga_task_accepted=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--observed', type=Path)
    parser.add_argument('--pl-samples', type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(verify(args.root,args.observed,args.pl_samples)))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, 'RESTOCK_ACCEPTED_AUDIT_FAILED: '+str(exc)+'\n')
