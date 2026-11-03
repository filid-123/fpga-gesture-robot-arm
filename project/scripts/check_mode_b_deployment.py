"""Same-image CPU or explicit NPU/ROCm deployment stages, with no hardware motion."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pc.mode_b.deployment import compare, detect, load_inputs, surfaces


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--inputs', type=Path, default=ROOT/'handoff/inputs.json')
    sub = p.add_subparsers(dest='stage', required=True)
    sub.add_parser('inputs')
    d = sub.add_parser('detect')
    d.add_argument('--package', type=Path, required=True)
    d.add_argument('--backend', choices=['onnx_cpu', 'npu'], required=True)
    d.add_argument('--provider-options', type=Path)
    d.add_argument('--runs', type=int, default=30)
    d.add_argument('--out', type=Path, required=True)
    s = sub.add_parser('surface')
    s.add_argument('--detections', type=Path, required=True)
    s.add_argument('--backend', choices=['torch_cpu', 'rocm'], required=True)
    s.add_argument('--out', type=Path, required=True)
    c = sub.add_parser('compare')
    c.add_argument('--reference', type=Path, default=ROOT/'handoff/cpu_surface/surface.json')
    c.add_argument('--candidate', type=Path, required=True)
    c.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    if a.stage == 'inputs':
        data = load_inputs(a.inputs, ROOT)
        print(json.dumps({'status': 'INPUT_HASHES_AND_SPLITS_PASS',
                          'replay_frames': len(data['replay']),
                          'calibration_images': len(data['calibration']['items'])}))
        return
    if a.stage == 'detect':
        options = json.loads(a.provider_options.read_bytes()) if a.provider_options else None
        result = detect(a.inputs, ROOT, a.package, a.backend, a.out, options, a.runs)
    elif a.stage == 'surface':
        result = surfaces(a.inputs, ROOT, a.detections, a.backend, a.out)
    else:
        result = compare(a.reference, a.candidate, a.inputs, ROOT, a.out)
    print(json.dumps({'status': result['status'], 'records': len(result['records']),
                      'physical_execution': False, 'path_submissions': 0}))


if __name__ == '__main__':
    main()
