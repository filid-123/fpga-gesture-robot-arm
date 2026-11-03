"""Verify a portable ZIP or extracted package using only Python's standard library."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import zipfile


def safe_name(name):
    p = PurePosixPath(name)
    if p.is_absolute() or '..' in p.parts or '\\' in name or ':' in name:
        raise ValueError('Unsafe archive path')
    return name


def verify_zip(path):
    with zipfile.ZipFile(path) as z:
        names = [safe_name(n) for n in z.namelist()]
        if len(set(names)) != len(names):
            raise ValueError('Duplicate archive entries')
        manifest = json.loads(z.read('FILE_MANIFEST.json'))
        rows = manifest['files']
        if set(names) != {r['path'] for r in rows}|{'FILE_MANIFEST.json'} or len(rows)+1 != len(names):
            raise ValueError('Archive files differ from manifest')
        for row in rows:
            if hashlib.sha256(z.read(row['path'])).hexdigest() != row['sha256']:
                raise ValueError('Archive content mismatch: '+row['path'])
    return len(rows)


def verify_folder(root):
    root = Path(root).resolve()
    data = json.loads((root/'FILE_MANIFEST.json').read_bytes())
    for row in data['files']:
        file = (root/safe_name(row['path'])).resolve()
        if not file.is_relative_to(root) or hashlib.sha256(file.read_bytes()).hexdigest() != row['sha256']:
            raise ValueError('Extracted content mismatch: '+row['path'])
    return len(data['files'])


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('path', type=Path)
    a = p.parse_args()
    count = verify_folder(a.path) if a.path.is_dir() else verify_zip(a.path)
    print(json.dumps({'status': 'ALL_PACKAGE_HASHES_PASS', 'files': count}))
