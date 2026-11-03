"""Summarize window-blocked qualified PALM periods without copying raw logs."""
from pathlib import Path
import argparse
import datetime
import hashlib
import json


def analyze(run):
    run = Path(run)
    p = run/'telemetry.jsonl'
    rows = [json.loads(s) for s in p.read_text('utf-8').splitlines() if s.strip()]
    session = json.loads((run/'SESSION_RESULT.json').read_text('utf-8'))
    periods, current = [], []
    def eligible(r):
        return (r['model'] == 'PALM' and r['qualified'] and r['vision_valid']
                and r['state'] == 'WAIT_PALM' and r['align_candidate_valid']
                and r['align_same'] and not r['pre_minimum_wait']
                and not r['palm_window_ok'] and r['palm_hold_ms'] == 0)
    for i, r in enumerate(rows, 1):
        if current and (not eligible(r) or
                        r['align_retarget_count'] != current[-1][1]['align_retarget_count']):
            periods.append(current)
            current = []
        if eligible(r):
            current.append((i, r))
    if current:
        periods.append(current)
    def duration(a, b):
        return (datetime.datetime.fromisoformat(b['timestamp']) -
                datetime.datetime.fromisoformat(a['timestamp'])).total_seconds()
    details = []
    for group in periods:
        a, b = group[0][1], group[-1][1]
        if duration(a, b) < 1:
            continue
        y1 = [(r['raw']['0x43c60024'] >> 16) & 511 for _, r in group]
        details.append(dict(first_row=group[0][0], last_row=group[-1][0],
                            duration_s=duration(a, b), snapshots=len(group),
                            bank=a['align_bank'], pre_wait_ms=[a['palm_wait_ms'], b['palm_wait_ms']],
                            raw_y1_min=min(y1), raw_y1_max=max(y1), palm_hold_ms=0))
    return dict(result='QUALIFIED_PALM_BLOCKED_BY_LEGACY_FULL_BOX_WINDOW',
                source_version=session['version'], source_run=run.name,
                raw_log_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
                snapshots=len(rows), duration_s=duration(rows[0], rows[-1]),
                qualified_palm_snapshots=sum(r['model']=='PALM' and r['qualified'] for r in rows),
                window_ok_snapshots=sum(bool(r['palm_window_ok']) for r in rows),
                blocked_stable_periods=details,
                done=rows[-1]['done_counter'], cancelled=rows[-1]['cancelled_counter'],
                errors_max={k:max(r[k] for r in rows) for k in
                            ('arm_errors','planner_errors','feedback_errors','feedback_timeouts')},
                session_result=session['result'],
                restore={k:session[k] for k in ('motion_shutdown','sensor_restore','PS_CPU_restore')},
                new_patch_physical_test='NOT_RUN')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    if args.out.exists():
        raise FileExistsError(args.out)
    result = analyze(args.run)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2)+'\n', 'utf-8')
    print(json.dumps(result, indent=2))
