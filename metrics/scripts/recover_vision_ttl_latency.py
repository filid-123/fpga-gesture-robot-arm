"""Recover vision-to-TTL observation timing from accepted p4.1 telemetry."""
import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path

from recover_recorded_metrics import stats

ROOT = Path(__file__).resolve().parents[2]
CLOCK = '0x43c60084'
COLUMNS = ('session', 'mode', 'start_row', 'tx_row', 'feedback_row',
           'start_ms', 'tx_ms', 'feedback_ms', 'previous_feedback_ms',
           'tx_count_before', 'tx_count', 'feedback_seq_at_tx', 'feedback_seq')
UINT32 = 1 << 32


def elapsed(end, start):
    return (end - start) % UINT32


def samples(rows):
    """Use the last idle or admission observation, then a strictly later feedback observation."""
    records = []
    rejected = Counter()
    for index in range(1, len(rows)):
        before, admission = rows[index - 1:index + 1]
        mode = admission['fpga_mode']
        if before['state'] != 'IDLE' or before['fpga_mode'] != mode:
            continue
        if admission['state'] != {'A': 'RUN', 'B': 'WAIT_PATH'}.get(mode):
            continue
        gesture = admission['selected_gesture']
        if gesture not in (1, 2, 3):
            rejected['selection_missing'] += 1
            continue

        def matches(row):
            return row['qualified'] and row['vision_valid'] and row['gesture'] == f'OBJECT_{gesture}'

        if matches(before):
            start_index = index - 1
        elif matches(admission):
            start_index = index
        else:
            rejected['qualified_gesture_unobserved'] += 1
            continue

        tx = None
        record = None
        for current_index in range(index, len(rows)):
            row = rows[current_index]
            if (row['fpga_mode'] != mode or row['state'] not in ('WAIT_PATH', 'RUN')
                    or row['selected_gesture'] != gesture
                    or row['selected_task_id'] != admission['selected_task_id']
                    or row['fault'] != 'NONE' or row['arm_fault']):
                break
            if tx is None and row['state'] == 'RUN' and row['motion_frames'] > before['motion_frames']:
                tx = current_index
                continue
            if (tx is not None and row['state'] == 'RUN' and row['feedback_live_valid']
                    and row['feedback_mask'] == 63
                    and 0 < (row['feedback_seq'] - rows[tx]['feedback_seq']) % 65536 < 32768):
                start_ms = rows[start_index]['raw'][CLOCK]
                tx_ms = rows[tx]['raw'][CLOCK]
                end_ms = row['raw'][CLOCK]
                prev_ms = rows[current_index - 1]['raw'][CLOCK]
                if 0 < elapsed(end_ms, tx_ms) <= elapsed(end_ms, start_ms) < UINT32 // 2:
                    record = dict(zip(COLUMNS[1:], (mode, start_index + 1, tx + 1, current_index + 1,
                        start_ms, tx_ms, end_ms, prev_ms, before['motion_frames'],
                        rows[tx]['motion_frames'], rows[tx]['feedback_seq'], row['feedback_seq'])))
                    break
        if record is not None:
            records.append(record)
        elif tx is None:
            rejected['motion_tx_unobserved_before_exit'] += 1
        else:
            rejected['fresh_feedback_unobserved_before_exit'] += 1
    return records, dict(rejected)


def summarize(rows):
    return {
        mode: {
            'vision_to_ttl_feedback_observed_ms': stats([elapsed(r['feedback_ms'], r['start_ms']) for r in group]),
            'feedback_observation_step_ms': stats([elapsed(r['feedback_ms'], r['previous_feedback_ms']) for r in group]),
        }
        for mode in ('A', 'B')
        if (group := [r for r in rows if r['mode'] == mode])
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runs-dir', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    csv_path = args.out / 'samples.csv'
    summary_path = args.out / 'summary.json'
    if args.runs_dir is None:
        with csv_path.open(newline='', encoding='utf8') as stream:
            rows = [{k: v if k in ('session', 'mode') else int(v) for k, v in row.items()}
                    for row in csv.DictReader(stream)]
        saved = json.loads(summary_path.read_bytes())
        if summarize(rows) != saved['modes'] or hashlib.sha256(csv_path.read_bytes()).hexdigest() != saved['samples_sha256']:
            raise ValueError('Published TTL samples or statistics differ')
        print(json.dumps(saved['modes'], indent=2))
        return
    acceptance = json.loads((ROOT / 'report/acceptance/board_test_20261101.json').read_bytes())
    output, sources = [], []
    for session in acceptance['sessions']:
        name = session['run']
        data = (args.runs_dir / name / 'telemetry.jsonl').read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if digest != session['source_files']['telemetry.jsonl']['sha256']:
            raise ValueError('Telemetry checksum mismatch: ' + name)
        rows = [json.loads(line) for line in data.splitlines()]
        if len(rows) != session['telemetry_rows']:
            raise ValueError('Telemetry row count differs: ' + name)
        records, rejected = samples(rows)
        output.extend(dict(session=name, **record) for record in records)
        sources.append(dict(session=name, telemetry_sha256=digest, rows=len(rows),
                            accepted=len(records), excluded=rejected))
    args.out.mkdir(parents=True, exist_ok=False)
    with csv_path.open('x', newline='', encoding='utf8') as stream:
        writer = csv.DictWriter(stream, COLUMNS, lineterminator='\n')
        writer.writeheader()
        writer.writerows(output)
    summary = {
        'schema': 'gesture.vision_ttl_poll_observation.v1',
        'release': '0.1.0-p4.1',
        'clock': 'FPGA VIS+0x84 millisecond counter, modulo 2^32, read by sequential JTAG telemetry',
        'start': 'Matching qualified selection at last IDLE or first observed task admission',
        'end': 'First strictly later RUN observation with a fresh full six-channel TTL feedback snapshot after observed motion TX',
        'scope': 'Observed software-hardware feedback loop, including sampling delay and mode B path preparation. No per-command acknowledgment pairing or physical-motion onset timestamp.',
        'sessions': sources,
        'modes': summarize(output),
        'samples_sha256': hashlib.sha256(csv_path.read_bytes()).hexdigest(),
    }
    summary_path.write_bytes((json.dumps(summary, indent=2) + '\n').encode())
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
