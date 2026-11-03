"""Verify or install the nine p4.1 external runtime assets from pinned upstream channels or local sources."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
import zipfile

ROOT = Path(__file__).resolve().parents[1]
CHANNELS = ROOT / 'report/provenance/runtime_asset_channels.json'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def download(row):
    url = row['channel']
    source = urlsplit(url)
    if source.scheme != 'https' or source.netloc != 'raw.githubusercontent.com':
        raise ValueError('Unexpected channel for ' + row['path'])
    try:
        size = row['bytes']
        chunk_size = 1024 * 1024
        if size <= chunk_size:
            with urlopen(url, timeout=90) as response:
                return response.read(size + 1)

        def fetch_chunk(start):
            end = min(start + chunk_size, size) - 1
            request = Request(f'{url}?offset={start}', headers={'Range': f'bytes={start}-{end}'})
            with urlopen(request, timeout=90) as response:
                if response.headers.get('Content-Range') != f'bytes {start}-{end}/{size}':
                    raise ValueError('Unexpected byte range for ' + row['path'])
                chunk = response.read(end - start + 2)
            if len(chunk) != end - start + 1:
                raise ValueError('Incomplete byte range for ' + row['path'])
            return chunk

        with ThreadPoolExecutor(max_workers=6) as workers:
            return b''.join(workers.map(fetch_chunk, range(0, size, chunk_size)))
    except (URLError, TimeoutError) as exc:
        raise ValueError(f"Could not download {row['path']}: {exc}") from exc


def install(rows, read, *, skip_installed=False):
    pending = []
    for row in rows:
        target = (ROOT / row['path']).resolve()
        if not target.is_relative_to((ROOT / 'project').resolve()):
            raise ValueError('Unsafe asset destination')
        if target.exists() and sha(target.read_bytes()) != row['sha256']:
            raise ValueError('Existing file differs: ' + row['path'])
        if target.exists() and skip_installed:
            continue
        content = read(row['path'])
        if len(content) != row['bytes'] or sha(content) != row['sha256']:
            raise ValueError('Incorrect source asset: ' + row['path'])
        if not target.exists():
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
    source.add_argument('--download', action='store_true', help='Download the nine assets from pinned upstream channels')
    args = parser.parse_args()
    rows = json.loads(CHANNELS.read_bytes())['assets']
    installed = 0
    if args.download:
        by_path = {row['path']: row for row in rows}
        installed = install(rows, lambda name: download(by_path[name]), skip_installed=True)
    elif args.source_dir:
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
