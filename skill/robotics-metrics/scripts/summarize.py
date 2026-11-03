"""Summarize explicit task or timing observations; simulation stays labelled simulation."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path


def quantile(values, probability):
    ordered = sorted(values)
    if not ordered:
        raise ValueError('No observations')
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def stats(values):
    return {name: quantile(values, p) for name, p in [('p50', .5), ('p95', .95), ('p99', .99), ('max', 1.)]}


def summarize(path, kind, conditions, evidence_kind, start=None, end=None):
    path = Path(path)
    if not conditions.strip():
        raise ValueError('Measurement conditions are required')
    with path.open(encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError('Empty observations; do not turn NOT_RUN into a zero result')
    result = {'schema': 'robotics.metrics.v1', 'kind': kind, 'conditions': conditions,
              'evidence_kind': evidence_kind, 'samples': len(rows),
              'input_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
              'quantile_method': 'linear interpolation at (n-1)*p; no unobserved maximum extrapolation'}
    if kind == 'task':
        if any(r.get('outcome') not in ('success', 'failure', 'intervention') for r in rows):
            raise ValueError('Each valid trial needs outcome=success|failure|intervention')
        counts = {label: sum(r['outcome'] == label for r in rows) for label in ('success', 'failure', 'intervention')}
        result.update(counts=counts, success_rate=counts['success'] / len(rows),
                      denominator='All supplied valid trials, including failures and interventions')
    else:
        if kind == 'latency' and (not start or not end):
            raise ValueError('Latency requires explicit measured start and end events')
        columns = ['preprocess_ms', 'inference_ms', 'postprocess_ms', 'total_ms'] if kind == 'inference' else ['duration_ms']
        values = {column: [] for column in columns}
        for row in rows:
            if kind == 'inference' and row.get('batch') != '1':
                raise ValueError('Inference comparison requires batch=1 in every row')
            for column in columns:
                value = float(row[column])
                if not math.isfinite(value) or value < 0:
                    raise ValueError('Negative/nonfinite timing: ' + column)
                values[column].append(value)
            if kind == 'inference' and sum(values[c][-1] for c in columns[:3]) > values['total_ms'][-1] + 1e-6:
                raise ValueError('Total perception time is smaller than its measured components')
        result['timing_ms'] = {column: stats(data) for column, data in values.items()}
        if kind == 'latency':
            result.update(start_event=start, end_event=end)
        result['tail_caveat'] = 'Small sample percentiles do not establish long-run tail latency.'
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--csv', type=Path, required=True)
    parser.add_argument('--kind', choices=['task', 'latency', 'inference', 'rtt'], required=True)
    parser.add_argument('--conditions', required=True)
    parser.add_argument('--evidence-kind', choices=['physical', 'saved_input', 'simulation', 'synthetic'], required=True)
    parser.add_argument('--start')
    parser.add_argument('--end')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    try:
        result = summarize(args.csv, args.kind, args.conditions, args.evidence_kind, args.start, args.end)
        result['passed'] = True
    except (OSError, ValueError, KeyError, TypeError) as exc:
        result = {'passed': False, 'error': str(exc)}
    text = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding='utf-8')
    print(text, end='')
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
