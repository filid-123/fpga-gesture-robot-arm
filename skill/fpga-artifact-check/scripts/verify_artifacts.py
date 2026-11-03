"""Verify source/build binding, routed timing, and matching BIT/HWH/XSA without loading an FPGA."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import zipfile


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def local(root, name):
    name = str(name).replace('\\', '/')
    path = (root / name).resolve()
    if ':' in name or not path.is_relative_to(root.resolve()):
        raise ValueError('Expected a package-relative path: ' + name)
    return path


def finite(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('Missing or nonfinite numeric build result')
    return value


def count(value):
    finite(value)
    if not isinstance(value, int) or value < 0:
        raise ValueError('Expected a nonnegative integer build count')
    return value


def verify(root, summary_path, sources_path, artifact_dir='hardware'):
    root = Path(root).resolve()
    summary_file = local(root, summary_path)
    source_file = local(root, sources_path)
    summary = json.loads(summary_file.read_bytes())
    sources = json.loads(source_file.read_bytes())['files']
    if not sources:
        raise ValueError('Empty source binding')
    if summary.get('source_binding_sha256') != digest(source_file):
        raise ValueError('Build summary does not bind the supplied source manifest')
    for name, expected in sources.items():
        if not re.fullmatch('[a-f0-9]{64}', expected) or digest(local(root, name)) != expected:
            raise ValueError('Build source mismatch: ' + name)
    timing = summary['timing_ns']
    for key in ('WNS', 'WHS', 'TNS', 'THS'):
        value = finite(timing[key])
        if (key in ('WNS', 'WHS') and value < 0) or (key in ('TNS', 'THS') and value != 0):
            raise ValueError('Routed timing failed: ' + key)
    if count(summary['drc_errors']) != 0:
        raise ValueError('DRC errors remain')
    for key in ('cdc_unsafe', 'cdc_unknown'):
        if count(summary[key]) != 0:
            raise ValueError('Unresolved CDC: ' + key)
    if count(summary['cdc_safe']) != count(summary['cdc_endpoints']):
        raise ValueError('Incomplete CDC coverage')
    artifacts = summary['artifacts']
    by_ext = {}
    for name, meta in artifacts.items():
        path = local(root, str(Path(artifact_dir) / name))
        ext = path.suffix.lower()
        if ext in by_ext:
            raise ValueError('Ambiguous artifact extension: ' + ext)
        if count(meta['bytes']) == 0 or path.stat().st_size != meta['bytes'] or digest(path) != meta['sha256']:
            raise ValueError('Artifact mismatch: ' + name)
        by_ext[ext] = path
    if set(by_ext) != {'.bit', '.hwh', '.xsa'}:
        raise ValueError('Exactly one BIT, HWH and XSA are required')
    with zipfile.ZipFile(by_ext['.xsa']) as archive:
        if archive.testzip():
            raise ValueError('XSA CRC failed')
        for ext in ('.bit', '.hwh'):
            matches = [n for n in archive.namelist() if Path(n).name == by_ext[ext].name]
            if len(matches) != 1:
                raise ValueError('Missing or ambiguous XSA member: ' + ext)
            if hashlib.sha256(archive.read(matches[0])).hexdigest() != digest(by_ext[ext]):
                raise ValueError('XSA member differs: ' + ext)
    return {'schema': 'fpga.artifact.check.v1', 'passed': True, 'source_files': len(sources),
            'artifacts': artifacts, 'timing_ns': timing, 'utilization': summary.get('utilization'),
            'drc_errors': 0, 'cdc_safe': summary['cdc_safe'], 'hardware_access': False,
            'claim': 'Stored build evidence and artifacts agree; no new implementation or board test was run.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--summary', required=True)
    parser.add_argument('--sources', required=True)
    parser.add_argument('--artifact-dir', default='hardware')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    try:
        report = verify(args.root, args.summary, args.sources, args.artifact_dir)
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile) as exc:
        report = {'passed': False, 'error': str(exc), 'hardware_access': False}
    text = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding='utf-8')
    print(text, end='')
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
