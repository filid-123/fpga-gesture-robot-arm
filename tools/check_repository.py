"""Check the Git source subset or a restored complete p4.1 package, without hardware access."""
import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def check(root=ROOT, complete=False):
    root = Path(root).resolve()
    inventory = json.loads((root / 'report/provenance/source_archive_inventory.json').read_bytes())
    review = root / 'report/provenance/public_review.json'
    redactions = json.loads(review.read_bytes())['project_redactions'] if review.is_file() else {}
    errors, missing = [], []
    checked = 0
    for member in inventory['members']:
        name = member['path']
        path = (root / 'project' / name).resolve()
        if not path.is_relative_to((root / 'project').resolve()):
            raise ValueError('Inventory path outside project')
        if not path.is_file():
            if member['git_included'] or complete:
                errors.append('Missing: project/' + name)
            if not member['git_included']:
                missing.append(name)
            continue
        redaction = redactions.get('project/' + name)
        allowed = redaction if redaction and redaction['source_sha256'] == member['sha256'] else None
        expected_size = allowed['bytes'] if allowed else member['bytes']
        expected_hash = allowed['public_sha256'] if allowed else member['sha256']
        if path.stat().st_size != expected_size or digest(path) != expected_hash:
            errors.append('Changed baseline: project/' + name)
        checked += 1
    for name in ('patch_id', 'hotfix_id', 'task_abi'):
        expected = {'patch_id': 'native_giao_full_workspace_p4',
                    'hotfix_id': 'startup_route_map_p4_1', 'task_abi': 0x340e}[name]
        manifest = json.loads((root / 'project/mode_ab_manifest.json').read_bytes())
        if manifest.get(name) != expected:
            errors.append('Wrong release identity: ' + name)
    seal = root / 'report/provenance/publication_manifest.json'
    if seal.is_file():
        for name, expected in json.loads(seal.read_bytes())['files'].items():
            path = (root / name).resolve()
            if not path.is_relative_to(root) or not path.is_file() or digest(path) != expected:
                errors.append('Publication file differs: ' + name)
    acceptance_path = 'report/acceptance/board_test_20261101.json'
    acceptance = json.loads((root / acceptance_path).read_bytes())
    if acceptance['release']['archive_sha256'] != inventory['archive_sha256']:
        errors.append('Field acceptance refers to a different archive')
    return {'schema': 'gesture.publication.check.v1', 'passed': not errors,
            'scope': 'complete_publication_with_restored_assets' if complete and redactions else ('complete_original_package' if complete else 'published_source_subset'),
            'baseline_members_checked': checked, 'baseline_members_total': inventory['archive_files'],
            'missing_external_assets': len(missing), 'full_runtime_ready': not missing and not errors,
            'archive_sha256': inventory['archive_sha256'], 'errors': errors,
            'hardware_access': False, 'physical_test_in_this_check': 'NOT_RUN',
            'release_status': acceptance['status'],
            'physical_closed_loop': acceptance['operator_confirmation']['physical_task_result'],
            'acceptance_evidence': acceptance_path}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--complete', action='store_true')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    report = check(args.root, args.complete)
    value = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(value, encoding='utf-8')
    print(value, end='')
    raise SystemExit(0 if report['passed'] else 1)
