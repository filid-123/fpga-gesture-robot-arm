"""Verify or install the nine p4.1 external runtime assets from a local authorized source."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
CHANNELS = ROOT / 'report/provenance/runtime_asset_channels.json'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def install(rows, read):
    pending = []
    for row in rows:
        target = (ROOT / row['path']).resolve()
        if not target.is_relative_to((ROOT / 'project').resolve()):
            raise ValueError('Unsafe asset destination')
        content = read(row['path'])
        if len(content) != row['bytes'] or sha(content) != row['sha256']:
            raise ValueError('Incorrect source asset: ' + row['path'])
        if target.exists():
            if sha(target.read_bytes()) != row['sha256']:
                raise ValueError('Existing file differs: ' + row['path'])
        else:
            pending.append((target, content))
    for target, content in pending:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write(content)
    return len(pending)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group()
    source.add_argument('--source-dir', type=Path, help='Local directory with the project-relative layout from the channel list')
    source.add_argument('--archive', type=Path, help='Locally held original p4.1 archive')
    args = parser.parse_args()
    rows = json.loads(CHANNELS.read_bytes())['assets']
    installed = 0
    if args.source_dir:
        installed = install(rows, lambda name: (args.source_dir / name).read_bytes())
    elif args.archive:
        inventory = json.loads((ROOT/'report/provenance/source_archive_inventory.json').read_bytes())
        with args.archive.open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != inventory['archive_sha256']:
                raise ValueError('Original p4.1 archive checksum differs')
        with zipfile.ZipFile(args.archive) as archive:
            installed = install(rows, lambda name: archive.read(name.removeprefix('project/')))
    missing, mismatched = [], []
    for row in rows:
        path = ROOT / row['path']
        if not path.is_file():
            missing.append(row['path'])
        elif sha(path.read_bytes()) != row['sha256']:
            mismatched.append(row['path'])
    print(json.dumps(dict(verified=not (missing or mismatched), installed=installed,
                          missing=missing, mismatched=mismatched), indent=2))
    return bool(missing or mismatched)


if __name__ == '__main__':
    raise SystemExit(main())
