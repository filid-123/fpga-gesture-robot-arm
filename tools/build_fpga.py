"""Plan or run the original p4 FPGA build in a new output directory, keeping released artifacts intact."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vivado', type=Path, required=True, help='Full path to vivado.bat')
    parser.add_argument('--out', type=Path, required=True, help='New directory outside project/')
    parser.add_argument('--execute', action='store_true', help='Without this flag only emit the build plan')
    args = parser.parse_args()
    project = ROOT / 'project'
    out = args.out.resolve()
    if out.exists() or out.is_relative_to(project.resolve()):
        parser.error('Use a new output directory outside the sealed project/')
    sources = project / 'evidence/implementation/built_source_hashes.json'
    original = json.loads(sources.read_bytes())
    review = ROOT / 'report/provenance/public_review.json'
    redactions = json.loads(review.read_bytes())['project_redactions'] if review.is_file() else {}
    for name, expected in original['files'].items():
        redaction = redactions.get('project/' + name)
        if redaction and redaction['source_sha256'] == expected:
            expected = redaction['public_sha256']
        with (project / name).open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != expected:
                parser.error('Build source differs: ' + name)
    flags = {'TIMED_WALKTHROUGH': 1, 'HANDOVER_V2': 1, 'HAND_ALIGN': 1,
             'HAND_ALIGN_REGIONS': 4, 'HAND_ALIGN_LOCATOR': 1, 'HDMI': 1,
             'UPGRADE': 1, 'AUTO_RESTOCK': 1, 'DYNAMIC_B': 1, 'FAST_B': 1}
    environment = {'ROARM_' + name: str(value) for name, value in flags.items()}
    environment.update(ROARM_BUILD_DIR=str(out / 'vivado'), ROARM_REPORT_DIR=str(out / 'reports'),
                       GESTURE_PYTHON=sys.executable)
    commands = [[str(args.vivado), '-mode', 'batch', '-notrace', '-source',
                 str(project / 'native_motion/scripts' / name),
                 '-log', str(out / (stage + '.log')), '-journal', str(out / (stage + '.jou'))]
                for stage, name in [('create', 'create_roarm_closed_loop_project.tcl'),
                                    ('implement', 'build_roarm_closed_loop.tcl')]]
    plan = {'schema': 'gesture.reproducible.build.v1', 'parameters': environment,
            'commands': commands, 'source_manifest_sha256': hashlib.sha256(sources.read_bytes()).hexdigest(),
            'hardware_access': False, 'execution': 'NOT_RUN'}
    if args.execute:
        if os.name != 'nt' or not args.vivado.is_file():
            parser.error('Execute requires Windows and an existing Vivado executable')
        out.mkdir(parents=True)
        env = os.environ.copy()
        env.update(environment)
        (out / 'build_plan.json').write_text(json.dumps(plan, indent=2) + '\n', encoding='utf-8')
        for index, command in enumerate(commands):
            with (out / ('stage_' + str(index) + '_stdout.txt')).open('xb') as stream:
                code = subprocess.call(command, cwd=project, env=env, stdout=stream,
                                       stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
            if code:
                raise SystemExit('Vivado failed: ' + str(code) + '; retain output for diagnosis')
        plan['execution'] = 'BUILD_COMPLETED_REVIEW_REQUIRED'
        (out / 'build_result.json').write_text(json.dumps(plan, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(plan, indent=2))


if __name__ == '__main__':
    main()
