"""Portable, stdlib-only optimized Mode B vector verifier. No device access."""
import argparse
import hashlib
import json
import math
from pathlib import Path

NAMES = ('b', 's', 'e', 't', 'r', 'g')
WIRE = ('base', 'shoulder', 'elbow', 'wrist', 'roll', 'hand')
FAST = ('BUFFER', 'PREPLACE', 'RETREAT', 'RETURN_CLEAR')
PHASES = ('DIRECT_PREGRASP', 'DESCEND', 'LIFT', 'INNER_HOLD', 'BUFFER',
          'PREPLACE', 'PLACE', 'RELEASE_CLEARANCE', 'RETREAT', 'RETURN_CLEAR',
          'INNER_RETURN', 'RETURN_LOW_HOME')
EVENTS = {'DIRECT_PREGRASP': ('OPEN_HIGH', 'open_before_descent_wire_json'),
          'DESCEND': ('CLOSE_SOURCE', 'close_after_descent_wire_json'),
          'PLACE': ('RELEASE', 'release_wire_json')}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def q16(command):
    words = [round(command[k]*65536) for k in WIRE]
    require(all(-2**31 <= w < 2**31 for w in words), 'Q16 overflow')
    return ''.join(f'{w & 0xffffffff:08x}' for w in reversed(words))


def verify(root, object_class=None, observed=None, pl_samples=None):
    root = Path(root).resolve()
    manifest = read(root/'MANIFEST.json')['files']
    actual = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
    require(actual == set(manifest) | {'MANIFEST.json'}, 'Package file set changed')
    for name, item in manifest.items():
        p = (root/name).resolve()
        require(p.is_relative_to(root), 'Path escapes package')
        require(p.stat().st_size == item['bytes'] and sha(p) == item['sha256'], 'Hash: '+name)
    package = read(root/'PACKAGE.json')
    require(not package['hardware_execution_enabled'], 'Offline reference expected')
    home = read(root/'HOME.json')
    require(home['joint_order'] == list(NAMES), 'HOME order')
    require(home['firmware_joint_q16'] == [round(home['firmware_joint_rad'][k]*65536) for k in NAMES], 'HOME Q16')
    summaries = []
    for item in package['objects']:
        cls = item['object_class']; folder = root/'objects'/cls
        plan = read(folder/'PLAN.json')
        require(plan['request']['object_class'] == cls, 'Class mismatch')
        require(plan['request']['destination']['support_centre_mm'] == [285,195,150], 'Support changed')
        require(plan['release_clearance_mm'] == 8, 'Lateral clearance changed')
        require(plan['offline_verification']['passed'], 'Geometry verification missing')
        require(plan['joint_transit_phases'] == list(FAST), 'Fast phase set changed')
        require(plan['phase_speed_multiplier'] == dict.fromkeys(FAST,2.0), 'Phase factor')
        if cls != 'red_cube':
            require('table_clearance_by_link_mm' not in plan['local_scene_config'], 'Red floor leaked')
            require(not item['new_speed_physical_test_performed'], 'Untested speed mislabeled')
        require([s['phase'] for s in plan['stages']] == list(PHASES), 'Phase order')
        sequence = []; gold = []; phases = read(folder/'phase_map.json')
        segments = read(folder/'quintic_segments.json')
        require([s['phase'] for s in segments] == list(FAST), 'Sparse segment order')
        seconds = 0.0
        for number, stage in enumerate(plan['stages']):
            phase = stage['phase']; data = stage['stage']; frames = data['stream_frames']
            dt = data['period_s']; begin = len(sequence)
            require(dt == (.04 if number < 3 else .02), 'Period mismatch')
            for i, frame in enumerate(frames):
                c = json.loads(frame['wire_json'])
                require(c['T'] == 102 and all(math.isfinite(c[k]) for k in WIRE), 'Invalid motion')
                require(0 < c['spd'] <= 4095 and 0 < c['acc'] <= 254, 'Native parameter range')
                require([c[k] for k in WIRE] == [frame['command_firmware_rad'][k] for k in NAMES], 'Joint mapping')
                sequence.append({'index':len(sequence),'label':phase,'kind':'motion','sample_in_stage':i,
                    'period_s':dt,'stage_offset_s':i*dt,'wire_json':frame['wire_json']})
                gold.append(q16(c))
            require(phases[number]['phase'] == phase and phases[number]['request_start_index'] == begin
                and phases[number]['request_end_index_inclusive'] == len(sequence)-1
                and phases[number]['motion_samples'] == len(frames)
                and phases[number]['period_s'] == dt
                and phases[number]['native_spd'] == c['spd']
                and phases[number]['native_acc'] == c['acc'], 'Phase export mismatch')
            require(math.isclose(data['nominal_motion_seconds'], len(frames)*dt), 'Nominal time')
            seconds += data['nominal_motion_seconds']
            if phase in FAST:
                segment = next(s for s in segments if s['phase'] == phase)
                require(stage['speed_adjustment']['path'] == 'JOINT_QUINTIC', 'Wrong curve')
                require(segment['sample_count'] == len(frames)
                    and segment['curve_duration_s'] == (len(frames)-1)*dt, 'Quintic timing')
                q0 = [frames[0]['command_firmware_rad'][n] for n in NAMES[:5]]
                q1 = [data['target_firmware_rad'][n] for n in NAMES[:5]]
                coefficients = [[a,0.,0.,10*(b-a),-15*(b-a),6*(b-a)] for a,b in zip(q0,q1)]
                require(segment['normalized_u_coefficients_rad'] == coefficients, 'Sparse coefficients')
                for i, f in enumerate(frames):
                    u = i/(len(frames)-1); blend = 10*u**3-15*u**4+6*u**5
                    for n,a,b in zip(NAMES[:5],q0,q1):
                        require(abs(f['command_firmware_rad'][n]-(a+(b-a)*blend)) < 1e-10, 'Quintic sample')
            if phase in EVENTS:
                label,key = EVENTS[phase]
                sequence.append({'index':len(sequence),'label':label,'kind':'gripper_event','wire_json':plan[key]})
        sequence.append({'index':len(sequence),'label':'PARK_CLOSE','kind':'gripper_event','wire_json':plan['park_close_wire_json']})
        rows = [json.loads(line) for line in (folder/'sequence.jsonl').read_text(encoding='utf-8').splitlines()]
        require(rows == sequence, 'Sequence differs from plan')
        require((folder/'commands.jsonl').read_text(encoding='utf-8').splitlines() == [s['wire_json'] for s in sequence], 'Commands')
        require((folder/'motion_q16.mem').read_text(encoding='ascii').splitlines() == gold, 'Q16 vector')
        require(len(sequence) == item['requests'] and len(gold) == item['motion_samples'], 'Counts')
        require(math.isclose(seconds,item['nominal_motion_seconds']), 'Summary duration')
        if cls == 'red_cube':
            feedback = read(root/'evidence/red/OPERATOR_FEEDBACK.json')
            result_path = root/'evidence/red/RESULT.json'
            result = read(result_path)
            require(feedback['plan']['sha256'] == sha(folder/'PLAN.json') == result['route_sha256'], 'Red plan binding')
            require(feedback['result']['sha256'] == sha(result_path), 'Red result binding')
            require(feedback['status'] == 'OPERATOR_ACCEPTED_POSTRELEASE_SPEED', 'Red speed feedback')
            require(not result['error'] and result['completed_stages'] == list(PHASES), 'Red run incomplete')
            require([(s['label'],s['wire_json']) for s in sequence] ==
                [(s['label'],s['wire_json']) for s in result['requests']], 'Red actual commands')
        if cls == object_class:
            if observed:
                other = [json.loads(line) for line in Path(observed).read_text(encoding='utf-8-sig').splitlines()]
                require([(s['index'],s['label'],s['wire_json']) for s in sequence] ==
                    [(s['index'],s['label'],s['wire_json']) for s in other], 'Board accepted requests differ')
            if pl_samples:
                require([s.strip().lower() for s in Path(pl_samples).read_text(encoding='ascii').splitlines()] == gold, 'PL samples differ')
        summaries.append({'object_class':cls,'requests':len(sequence),'motion_samples':len(gold),'nominal_motion_seconds':seconds})
    require(not (observed or pl_samples) or object_class in {s['object_class'] for s in summaries}, 'Choose --object-class')
    return {'passed':True,'files_checked':len(manifest),'objects':summaries,'hardware_accessed':False,'fpga_bit_exact_accepted':False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package',type=Path,default=Path(__file__).resolve().parent)
    parser.add_argument('--object-class',choices=['red_cube','small_canister','eraser'])
    parser.add_argument('--observed',type=Path)
    parser.add_argument('--pl-samples',type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.package,args.object_class,args.observed,args.pl_samples),ensure_ascii=False))
