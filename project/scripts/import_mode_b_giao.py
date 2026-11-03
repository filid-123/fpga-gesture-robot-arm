"""Import the reviewed Giao runtime without replacing any Mode A file.

Original Git blobs are retained byte for byte, including frozen manifests.
This script never contacts hardware or checks out the teammate branch.
"""
from pathlib import Path
import hashlib
import json
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = 'a345624f5f345c28d0915b38aa45bb307a64bec8'


def blob(path):
    return subprocess.check_output(['git', 'show', SOURCE+':'+path], cwd=ROOT)


def main():
    backup = ROOT/'backups/mode_ab_v0_1_0_a014_baseline.zip'
    with zipfile.ZipFile(backup) as archive:
        if archive.testzip() is not None:
            raise ValueError('Baseline backup CRC failure')
    manifest_name = 'MODE_B_VISUAL_BUNDLE_MANIFEST.json'
    manifest = json.loads(blob(manifest_name))
    wanted = {row['path']: row['sha256'] for row in manifest['files']}
    paths = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', SOURCE], cwd=ROOT, text=True).splitlines()
    prefixes = ('pc/', 'config/ai_pc/', 'sim/models/mode_b_roarm_nominal/', 'docs/phase3c/mode_b_teammate_handoff_20261028/',
                'docs/phase3c/mode_b_restock_20261029/',
                'docs/phase3c/mode_b_visual_bundle_20261029/')
    for name in paths:
        if name.startswith(prefixes) and not name.endswith('.zip'):
            # Common files are deliberately not replaced. A conflict below is fatal.
            wanted.setdefault(name, None)
    wanted[manifest_name] = None
    for name in paths:
        if name.startswith('scripts/') and ('mode_b' in name or 'project_console' in name):
            wanted.setdefault(name, None)
    imported, existing = {}, []
    # Read and verify everything before the first write.
    pending = []
    for name, expected in sorted(wanted.items()):
        path = (ROOT/name).resolve()
        if not path.is_relative_to(ROOT) or Path(name).is_absolute():
            raise ValueError('Invalid upstream path: '+name)
        data = blob(name)
        sha = hashlib.sha256(data).hexdigest()
        if expected and expected != sha:
            raise ValueError('Upstream manifest mismatch: '+name)
        if path.exists():
            if hashlib.sha256(path.read_bytes()).hexdigest() != sha:
                raise ValueError('Existing file differs; review before importing: '+name)
            existing.append(name)
        else:
            pending.append((path, data))
        imported[name] = sha
    for path, data in pending:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    out = ROOT/'board_evidence/mode_ab_v0_1_0'
    out.mkdir(parents=True, exist_ok=True)
    report = dict(source_commit=SOURCE, a_baseline_commit='0e827fe4',
                  imported_files=len(pending), existing_identical=existing,
                  source_files=imported, hardware_access=False,
                  backup_sha256=hashlib.sha256(backup.read_bytes()).hexdigest())
    (out/'upstream_import.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({k: report[k] for k in ('source_commit', 'imported_files', 'backup_sha256')}))


if __name__ == '__main__':
    main()
