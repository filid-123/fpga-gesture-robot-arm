"""Restore locally held excluded assets from the exact original archive; never downloads or publishes them."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def restore(root, archive_path):
    root = Path(root).resolve()
    inventory = json.loads((root / 'report/provenance/source_archive_inventory.json').read_bytes())
    with Path(archive_path).open('rb') as stream:
        actual = hashlib.file_digest(stream, 'sha256').hexdigest()
    if actual != inventory['archive_sha256']:
        raise ValueError('Wrong source archive; no assets restored')
    members = {row['path']: row for row in inventory['members']}
    project = (root / 'project').resolve()
    if not project.is_relative_to(root):
        raise ValueError('Project directory leaves the selected repository')
    restored = 0
    with zipfile.ZipFile(archive_path) as archive:
        names = [n.filename for n in archive.infolist() if not n.is_dir()]
        if len(names) != len(set(names)) or set(names) != set(members):
            raise ValueError('Archive inventory differs')
        if archive.testzip():
            raise ValueError('Archive CRC error')
        pending = []
        for name, meta in members.items():
            if meta['git_included']:
                continue
            target = (project / name).resolve()
            if not target.is_relative_to(project):
                raise ValueError('Unsafe asset destination: ' + name)
            content = archive.read(name)
            if len(content) != meta['bytes'] or hashlib.sha256(content).hexdigest() != meta['sha256']:
                raise ValueError('Asset differs: ' + name)
            if target.exists():
                with target.open('rb') as stream:
                    if hashlib.file_digest(stream, 'sha256').hexdigest() != meta['sha256']:
                        raise ValueError('Existing local asset differs; refusing overwrite: ' + name)
            else:
                pending.append((name, target))
        # All existing files and archive members have been checked before the first write.
        for name, target in pending:
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(name) as source, target.open('xb') as destination:
                shutil.copyfileobj(source, destination)
            restored += 1
    return {'passed': True, 'restored_assets': restored, 'hardware_access': False,
            'redistribution_permission': 'UNCHANGED; local restoration grants no new rights'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args()
    try:
        result = restore(args.root, args.archive)
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
        result = {'passed': False, 'error': str(exc)}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result['passed'] else 1)
