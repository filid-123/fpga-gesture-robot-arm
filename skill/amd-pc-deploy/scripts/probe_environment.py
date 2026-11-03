"""Inspect an inference environment and model hashes without opening devices other than an optional HIP probe."""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import re
import sys


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def inspect(requirements=(), models=(), require_hip=False):
    report = {'schema': 'amd.pc.environment.v1', 'python': platform.python_version(),
              'system': platform.system(), 'architecture': platform.machine(),
              'requirements': [], 'models': [], 'hip': {'status': 'NOT_RUN'},
              'camera_access': False, 'robot_access': False}
    errors = []
    for requirement_file in requirements:
        for line in Path(requirement_file).read_text(encoding='utf-8-sig').splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            match = re.fullmatch(r'([A-Za-z0-9_.-]+)(?:\[[A-Za-z0-9_,.-]+\])?==([^ ;]+)', line)
            if not match:
                raise ValueError('Only explicit package==version requirements are supported: ' + line)
            name, expected = match.groups()
            try:
                actual = importlib.metadata.version(name)
            except importlib.metadata.PackageNotFoundError:
                actual = None
            passed = actual == expected
            report['requirements'].append({'package': name, 'expected': expected, 'actual': actual, 'passed': passed})
            if not passed:
                errors.append('Dependency mismatch: ' + name)
    for model_json in models:
        spec_path = Path(model_json)
        spec = json.loads(spec_path.read_bytes())
        entries = [spec[key] for key in ('onnx', 'checkpoint') if key in spec]
        if not entries:
            raise ValueError('Model declaration requires onnx or checkpoint with file and sha256')
        for entry in entries:
            root = spec_path.resolve().parent
            path = (root / entry['file']).resolve()
            if not path.is_relative_to(root):
                raise ValueError('Model path leaves its package')
            expected = entry['sha256']
            if not re.fullmatch('[a-f0-9]{64}', expected):
                raise ValueError('Invalid model SHA256')
            actual = digest(path) if path.is_file() else None
            passed = actual == expected
            report['models'].append({'file': entry['file'], 'expected_sha256': expected,
                                     'actual_sha256': actual, 'passed': passed})
            if not passed:
                errors.append('Missing or changed model: ' + entry['file'])
    if require_hip:
        try:
            import torch
            if not torch.version.hip or not torch.cuda.is_available():
                raise RuntimeError('A real HIP device is required; CPU fallback is not acceptance')
            # Execute and synchronize actual device work, rather than trusting a package name.
            tensor = torch.tensor([2., 3.], device='cuda')
            actual = float((tensor * tensor).sum().cpu())
            torch.cuda.synchronize()
            if actual != 13.:
                raise RuntimeError('HIP arithmetic probe failed')
            report['hip'] = {'status': 'PASS', 'framework_version': torch.__version__,
                             'hip_version': torch.version.hip, 'device': torch.cuda.get_device_name(0),
                             'actual_backend': 'rocm', 'cpu_fallback': False}
        except Exception as exc:
            report['hip'] = {'status': 'FAIL', 'error': str(exc)}
            errors.append('HIP device probe failed')
    report['errors'] = errors
    report['passed'] = not errors
    report['model_inference'] = 'NOT_RUN'
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--requirements', type=Path, action='append', default=[])
    parser.add_argument('--model-json', type=Path, action='append', default=[])
    parser.add_argument('--require-hip', action='store_true')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    try:
        report = inspect(args.requirements, args.model_json, args.require_hip)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        report = {'passed': False, 'error': str(exc)}
    text = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding='utf-8')
    print(text, end='')
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
