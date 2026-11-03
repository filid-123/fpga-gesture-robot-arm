"""Recover p4.1 metrics from recorded data, or independently recheck the sanitized public CSVs. No devices."""
import argparse
import collections
import csv
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
MODEL = 'project/model_package/candidates/black_scene_vision_v3_int8_targeted600_b_gate030_20261027'
CLASSES = ['background', 'one', 'two', 'three', 'fist', 'palm']
OPS = {'R', 'W', 'B', 'T', 'U', 'V'}


def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def stats(values):
    values = sorted(float(x) for x in values)
    if not values or any(not math.isfinite(x) or x < 0 for x in values):
        raise ValueError('Missing, negative or nonfinite timing observations')
    def quantile(p):
        index = (len(values) - 1) * p
        a, b = math.floor(index), math.ceil(index)
        return values[a] + (values[b] - values[a]) * (index - a)
    return {'n': len(values), **{k: quantile(p) for k, p in [('p50', .5), ('p95', .95), ('p99', .99), ('max', 1)]}}


def task_summary(review, acceptance):
    expected = collections.Counter()
    for key, count in acceptance['log_scope']['completion_counts'].items():
        mode, _, kind = key.split('/')
        expected[mode, kind] += count
    totals = collections.Counter()
    groups = []
    seen = set()
    for row in review['groups']:
        key = row['mode'], row['kind']
        if key in seen:
            raise ValueError('Duplicate operator outcome group')
        seen.add(key)
        n, success, failure = (row[k] for k in ('attempts', 'successes', 'failures'))
        if any(type(v) is not int or v < 0 for v in (n, success, failure)) or n == 0 or success + failure != n or expected[key] != n:
            raise ValueError('Operator denominator does not match the documented cohort')
        groups.append(dict(row, success_rate_pct=100 * success / n))
        totals.update(attempts=n, successes=success, failures=failure)
    if seen != set(expected):
        raise ValueError('Operator review omits a task group')
    for key in ('attempts', 'successes', 'failures'):
        if totals[key] != review['total_' + key]:
            raise ValueError('Operator summary total mismatch')
    return dict(totals, success_rate_pct=100 * totals['successes'] / totals['attempts'], groups=groups,
                provenance='OPERATOR_REVIEWED_RECORDED_COHORT', cohort_definition=review['cohort_definition'])


def rpc_summary(rows):
    valid = [r for r in rows if r['operation'] != 'CLOSE']
    if not valid or any(r['operation'] not in OPS or type(r['ok']) is not bool for r in valid):
        raise ValueError('Unexpected or missing board RPC observations')
    failed = sum(not r['ok'] for r in valid)
    return {'attempts': len(valid), 'successes': len(valid) - failed, 'failures': failed,
            'command_error_rate_pct': 100 * failed / len(valid),
            'all_attempts_rtt_ms': stats([r['roundtrip_ms'] for r in valid]),
            'successful_rtt_ms': stats([r['roundtrip_ms'] for r in valid if r['ok']]),
            'by_operation': {op: {'attempts': sum(r['operation'] == op for r in valid),
                                  'failures': sum(r['operation'] == op and not r['ok'] for r in valid),
                                  'successful_rtt_ms': stats([r['roundtrip_ms'] for r in valid if r['operation'] == op and r['ok']])}
                             for op in sorted({r['operation'] for r in valid})},
            'excluded_close_records': len(rows) - len(valid),
            'endpoint': 'Python BoardBridge.call -> local XSDB/JTAG/PL AXI -> decoded RPC reply; includes host scheduling and batch payload effects',
            'error_semantics': 'Recorded command exceptions, including Invalid context; not UART bit-error rate or Ethernet packet loss'}


def quality_summary(rows):
    matrix = [[0] * 6 for _ in range(6)]
    groups = collections.defaultdict(lambda: [0, 0])
    hands = correct_hands = detected_hands = 0
    for row in rows:
        truth, predicted = row['truth'], row['predicted_action']
        matrix[CLASSES.index(truth)][CLASSES.index(predicted)] += 1
        groups[row['group']][0] += truth == predicted
        groups[row['group']][1] += 1
        if truth != 'background':
            hands += 1
            correct_hands += truth == predicted
            detected_hands += row['detected']
    total = sum(sum(r) for r in matrix)
    if not total or not hands:
        raise ValueError('No labeled development observations')
    per_class = {}
    for i, name in enumerate(CLASSES):
        tp = matrix[i][i]
        fp = sum(matrix[j][i] for j in range(6) if j != i)
        fn = sum(matrix[i][j] for j in range(6) if j != i)
        per_class[name] = {'support': sum(matrix[i]), 'f1': 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.}
    correct = sum(matrix[i][i] for i in range(6))
    return {'samples': total, 'correct': correct, 'accuracy_pct': 100 * correct / total,
            'macro_f1': sum(v['f1'] for v in per_class.values()) / 6,
            'hands': hands, 'correct_hands': correct_hands, 'hand_accuracy_pct': 100 * correct_hands / hands,
            'hand_detection_recall_pct': 100 * detected_hands / hands,
            'groups': {k: {'correct': v[0], 'samples': v[1], 'accuracy_pct': 100 * v[0] / v[1]} for k, v in groups.items()},
            'classes': CLASSES, 'confusion_matrix': matrix, 'per_class': per_class,
            'scope': 'Full-integer reference on existing DEV sets; not independent TEST and not a new board accuracy test. Rejected detections and classifier background both mean no effective gesture.',
            'not_claimed': 'B-mode detector mAP or segmentation mIoU; no such independent ground-truth score is derived here.'}


def fpga_summary(histogram, clock_hz):
    loc = {r['locator_cycles'] for r in histogram if r['locator_cycles'] > 0}
    cls = {r['classifier_cycles'] for r in histogram if r['classifier_cycles'] > 0}
    if len(loc) != 1 or len(cls) != 1:
        raise ValueError('Stage counters are absent or variable; do not assume a single fixed latency')
    loc, cls = next(iter(loc)), next(iter(cls))
    return {'clock_hz': clock_hz, 'telemetry_observations': sum(r['observations'] for r in histogram),
            'locator_cycles': loc, 'classifier_cycles': cls,
            'locator_ms': loc * 1000 / clock_hz, 'classifier_ms': cls * 1000 / clock_hz,
            'cnn_service_sum_ms': (loc + cls) * 1000 / clock_hz,
            'classifier_zero_observations': sum(r['observations'] for r in histogram if r['classifier_cycles'] == 0),
            'scope': 'Actual latched start/done cycle counters. Repeated observations of a held counter are not independent inference trials. Sum is CNN service time, excluding capture, ROI, confirmation and actuator response; no CPU speedup claimed.'}


def read_jsonl(path):
    with Path(path).open(encoding='utf-8-sig') as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def write_csv(path, columns, rows):
    with Path(path).open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, columns, lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def clock_from_hwh(root):
    tree = ET.parse(root / 'project/hardware/roarm_closed_loop.hwh')
    values = {float(x.attrib['VALUE']) for x in tree.iter() if x.attrib.get('NAME') == 'PCW_FPGA1_PERIPHERAL_FREQMHZ'}
    if len(values) != 1:
        raise ValueError('Cannot identify the recorded FCLK1 frequency')
    return int(next(iter(values)) * 1_000_000)


def model_predictions(root):
    folder = root / MODEL / 'quantized'
    source = json.loads((folder / 'validation_rows.json').read_bytes())
    recorded = json.loads((folder / 'validation.json').read_bytes())
    rows = []
    for group, data in source.items():
        raw_matrix = [[0] * 7 for _ in range(6)]
        for index, row in enumerate(data):
            output = row['full_integer_class'] if row['detected'] else 'no_detection'
            raw_matrix[CLASSES.index(row['truth'])][(CLASSES + ['no_detection']).index(output)] += 1
            rows.append({'group': group, 'sample': index, 'truth': row['truth'], 'detected': bool(row['detected']),
                         'integer_class': row['full_integer_class'], 'predicted_action': output if output != 'no_detection' else 'background'})
        if raw_matrix != recorded['metrics'][group]['full_integer']['confusion_matrix']:
            raise ValueError('Recomputed predictions differ from the frozen confusion matrix')
    return rows


def recover(root, runs, out):
    acceptance = json.loads((root / 'report/acceptance/board_test_20261101.json').read_bytes())
    review = json.loads((root / 'report/acceptance/task_outcomes_review_20261101.json').read_bytes())
    rpc, histogram, inputs = [], [], []
    errors = collisions = 0
    for session in acceptance['sessions']:
        folder = runs / session['run']
        telemetry = folder / 'telemetry.jsonl'
        if sha(telemetry) != session['source_files']['telemetry.jsonl']['sha256']:
            raise ValueError('Private telemetry differs from accepted source: ' + session['run'])
        comm = folder / 'communication.jsonl'
        inputs += [{'run': session['run'], 'file': p.name, 'bytes': p.stat().st_size, 'sha256': sha(p)} for p in (telemetry, comm)]
        counts = collections.Counter()
        for row in read_jsonl(telemetry):
            raw = row['raw']
            if raw['0x43c50010'] != 0x340e or raw['0x43c60070'] != 0x022267a9 or raw['0x43c60008'] != 0x3506:
                raise ValueError('Wrong recorded task/model/vision identity')
            if row['fault'] != 'NONE' or row['feedback_errors'] or row['feedback_timeouts']:
                errors += 1
            collisions = max(collisions, raw['0x43c6020c'])
            counts[raw['0x43c60200'], raw['0x43c60204']] += 1
        if sum(counts.values()) != session['telemetry_rows']:
            raise ValueError('Telemetry count differs from accepted summary')
        histogram += [{'run': session['run'], 'locator_cycles': k[0], 'classifier_cycles': k[1], 'observations': n} for k, n in sorted(counts.items())]
        for index, row in enumerate(read_jsonl(comm)):
            error = row.get('error', '')
            rpc.append({'run': session['run'], 'record': index, 'operation': row['operation'], 'ok': row['ok'],
                        'roundtrip_ms': row['roundtrip_ms'],
                        'error_kind': 'NONE' if row['ok'] else ('XSDB_INVALID_CONTEXT' if 'invalid context' in error.lower() else 'OTHER_RECORDED_RPC_ERROR')})
    predictions = model_predictions(root)
    report = {'schema': 'gesture.recovered.metrics.v1', 'date': '2026-11-01', 'release': '0.1.0-p4.1',
              'tasks': task_summary(review, acceptance), 'communication': rpc_summary(rpc),
              'ai_quality': quality_summary(predictions), 'fpga': fpga_summary(histogram, clock_from_hwh(root)),
              'telemetry_error_observations': errors, 'trace_collision_counter_max': collisions,
              'sensor_to_physical_response': {'status': 'MISSING_PAIRED_PHYSICAL_ENDPOINT',
                 'reason': 'Joint feedback is sampled, but these non-atomic register snapshots do not bind a unique sensor event to physical motion onset with a synchronized timestamp. Frame age, network service time and RPC RTT cannot replace this endpoint.'},
              'new_hardware_access': False, 'new_model_inference': False, 'raw_private_logs_published': False}
    if out.exists():
        raise FileExistsError('Use a new evidence directory; do not overwrite an earlier result')
    out.mkdir(parents=True)
    write_csv(out / 'rpc_samples.csv', ['run', 'record', 'operation', 'ok', 'roundtrip_ms', 'error_kind'],
              [dict(x, ok=int(x['ok'])) for x in rpc if x['operation'] in OPS])
    write_csv(out / 'fpga_cycle_observations.csv', ['run', 'locator_cycles', 'classifier_cycles', 'observations'], histogram)
    write_csv(out / 'int8_dev_predictions.csv', ['group', 'sample', 'truth', 'detected', 'integer_class', 'predicted_action'],
              [dict(x, detected=int(x['detected'])) for x in predictions])
    report['public_csv_sha256'] = {p.name: sha(p) for p in out.glob('*.csv')}
    (out / 'summary.json').write_bytes((json.dumps(report, ensure_ascii=False, indent=2) + '\n').encode())
    provenance = {'private_sources': inputs, 'public_sources': {name: sha(root / name) for name in [
        'report/acceptance/board_test_20261101.json', 'report/acceptance/task_outcomes_review_20261101.json',
        MODEL + '/quantized/validation.json', MODEL + '/quantized/validation_rows.json',
        'project/hardware/roarm_closed_loop.hwh', 'project/native_motion/rtl/integration/mode_a_observer.v',
        'project/native_motion/rtl/integration/s5_vision_event_adapter.v', 'project/pc/mode_ab/board.py']},
        'script_sha256': sha(Path(__file__)), 'privacy': 'Only RPC timings/statuses, aggregate cycle observations and development labels are exported. No images, raw JTAG data, joint positions or device paths are copied.'}
    (out / 'provenance.json').write_bytes((json.dumps(provenance, ensure_ascii=False, indent=2) + '\n').encode())
    return report


def verify_public(root, folder):
    report = json.loads((folder / 'summary.json').read_bytes())
    for name, expected in report['public_csv_sha256'].items():
        if sha(folder / name) != expected:
            raise ValueError('Published evidence CSV changed: ' + name)
    provenance = json.loads((folder / 'provenance.json').read_bytes())
    for name, expected in provenance['public_sources'].items():
        if sha(root / name) != expected:
            raise ValueError('Recorded public source changed: ' + name)
    if sha(Path(__file__)) != provenance['script_sha256']:
        raise ValueError('Use the recorded recovery script version')
    def read(name):
        with (folder / name).open(encoding='utf-8', newline='') as f:
            return list(csv.DictReader(f))
    rpc = [dict(r, ok=r['ok'] == '1', roundtrip_ms=float(r['roundtrip_ms'])) for r in read('rpc_samples.csv')]
    pred = [dict(r, detected=r['detected'] == '1') for r in read('int8_dev_predictions.csv')]
    if pred != [dict(r, sample=str(r['sample'])) for r in model_predictions(root)]:
        raise ValueError('Public predictions do not match the frozen model records')
    hist = [{**r, **{k: int(r[k]) for k in ('locator_cycles', 'classifier_cycles', 'observations')}} for r in read('fpga_cycle_observations.csv')]
    actual = {'communication': rpc_summary(rpc), 'ai_quality': quality_summary(pred),
              'fpga': fpga_summary(hist, clock_from_hwh(root)),
              'tasks': task_summary(json.loads((root / 'report/acceptance/task_outcomes_review_20261101.json').read_bytes()),
                                    json.loads((root / 'report/acceptance/board_test_20261101.json').read_bytes()))}
    # Recovery excludes CLOSE records from its public CSV; all other numeric results must agree exactly.
    actual['communication']['excluded_close_records'] = report['communication']['excluded_close_records']
    for key, value in actual.items():
        if value != report[key]:
            raise ValueError('Public recomputation differs: ' + key)
    return {'passed': True, 'public_metrics_recomputed': list(actual), 'hardware_access': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--runs-dir', type=Path)
    parser.add_argument('--out-dir', type=Path)
    parser.add_argument('--verify-public', type=Path)
    args = parser.parse_args()
    if args.verify_public:
        result = verify_public(args.root, args.verify_public)
    else:
        if not args.runs_dir or not args.out_dir:
            parser.error('Recovery requires --runs-dir and a new --out-dir')
        result = recover(args.root, args.runs_dir, args.out_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
