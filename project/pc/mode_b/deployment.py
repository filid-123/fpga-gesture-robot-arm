"""Portable, file-based mode B deployment checks; no camera or robot transport.

Detector and surface stages run in separate SDK environments. Their interchange
is bound to the same original pixels, profile, model ancestry and spatial policy.
CPU runs are explicit references and cannot become NPU/ROCm acceptance records.
"""
from collections import Counter
from pathlib import Path
import json
import time

import cv2
import numpy as np

from pc.mode_b.profile import CLASSES, Profile
from pc.multiobject.dataset import read_image, write_image
from pc.multiobject.yolo import Detector, digest, image_digest, iou, load_package

SCHEMA = 'gesture.ai_pc.mode_b_deployment_inputs.v1'
POLICY = {'tiled': True, 'surface_ensemble': True,
          'detector_confidence': .4, 'surface_confidence': .7,
          'image_processing': 'RAW'}


def save(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2,
                                   allow_nan=False)+'\n', encoding='utf8')


def inside(root, relative):
    root = Path(root).resolve()
    path = (root/relative).resolve()
    if Path(relative).is_absolute() or not path.is_relative_to(root):
        raise ValueError('Input path escapes deployment root')
    return path


def load_inputs(path, root):
    path, root = Path(path).resolve(), Path(root).resolve()
    data = json.loads(path.read_bytes())
    if (data.get('schema') != SCHEMA or data.get('classes') != CLASSES
            or data.get('policy') != POLICY or data.get('physical_execution') is not False):
        raise ValueError('Explicit frozen six-class deployment inputs required')
    for relative, sha in data['assets_sha256'].items():
        if digest(inside(root, relative)) != sha:
            raise ValueError('Deployment asset hash mismatch: '+relative)
    Profile.load(inside(root, data['profile']))
    rows = data['replay']+data['calibration']['items']
    if not data['replay'] or not data['calibration']['items']:
        raise ValueError('Replay and TRAIN calibration images required')
    if len({r['id'] for r in data['replay']}) != len(data['replay']):
        raise ValueError('Duplicate replay IDs')
    splits, pixels = {}, {}
    for row in rows:
        file = inside(root, row['image'])
        image = read_image(file)
        if (digest(file) != row['image_sha256'] or image_digest(image) != row['pixel_sha256']
                or list(image.shape[1::-1]) != row['image_size_wh']):
            raise ValueError('Image hash/pixels/size mismatch')
        split = row['split']
        for mapping, key in ((splits, row['session_id']), (pixels, row['pixel_sha256'])):
            if key in mapping and mapping[key] != split:
                raise ValueError('Replay/calibration content or session leakage')
            mapping[key] = split
    if any(r['split'] != 'replay' for r in data['replay']):
        raise ValueError('Replay split required')
    source = json.loads(inside(root, data['calibration']['source_manifest']).read_bytes())
    if source.get('schema') != 'gesture.ai_pc.mode_b_dataset.v1' or source.get('classes') != CLASSES:
        raise ValueError('Six-class source dataset required')
    indexed = {r['image']: r for r in source['items']}
    # Check the entire source split metadata, not only the selected calibration subset.
    known = {}
    for row in source['items']:
        for key in ('session_id', 'image_sha256', 'pixel_sha256'):
            token = (key, row[key])
            if token in known and known[token] != row['split']:
                raise ValueError('Source dataset split leakage')
            known[token] = row['split']
        if row['pixel_sha256'] in {r['pixel_sha256'] for r in data['replay']}:
            raise ValueError('Replay pixels found in source training/development data')
    for row in data['calibration']['items']:
        original = indexed.get(row['source_image'], {})
        if (row['split'] != 'train' or original.get('split') != 'train'
                or any(original.get(k) != row[k] for k in
                       ('image_sha256', 'pixel_sha256', 'session_id', 'image_size_wh'))):
            raise ValueError('Calibration is not bound to source TRAIN content')
    return data


def fresh(path):
    path = Path(path)
    path.mkdir(parents=True, exist_ok=False)
    return path


def stats(times):
    return {key: float(val) for key, val in zip(('p50', 'p95', 'p99', 'max'),
            [*np.percentile(times, [50, 95, 99]), max(times)])}


def package_for(data, root, package, backend):
    spec, model = load_package(package)
    expected = json.loads(inside(root, data['detector']).read_bytes())
    if spec['role'] != 'mode_b_detector' or spec['classes'] != CLASSES:
        raise ValueError('Six-class detector required')
    if backend == 'onnx_cpu':
        valid = spec['precision'] == 'fp32' and digest(model) == expected['onnx']['sha256']
    else:
        valid = (spec.get('float_source_sha256') == expected['onnx']['sha256']
                 and spec.get('deployment_inputs_sha256') == data['_manifest_sha256']
                 and spec['precision'] in ('bf16', 'xint8', 'int8'))
    if not valid:
        raise ValueError('Detector model ancestry/input manifest mismatch')
    return spec


def detect(inputs, root, package, backend, out, options=None, runs=1):
    from pc.mode_b.tiled_detector import TiledDetector
    if runs < 1:
        raise ValueError('Positive benchmark run count required')
    data = load_inputs(inputs, root)
    data['_manifest_sha256'] = digest(inputs)
    package_for(data, root, package, backend)
    out = fresh(out)
    result = {'schema': 'gesture.ai_pc.mode_b_detector_stage.v1', 'status': 'ERROR',
              'inputs_sha256': digest(inputs), 'policy': POLICY, 'records': [],
              'requested_backend': backend, 'physical_execution': False,
              'path_submissions': 0, 'npu_acceptance': 'NOT_ACCEPTED'}
    detector = None
    try:
        detector = TiledDetector(Detector(package, backend, options, out))
        first = read_image(inside(root, data['replay'][0]['image']))
        # First inference includes compilation/cold model work; warm up separately.
        start = time.perf_counter_ns()
        detector.run(first, confidence=.4)
        result['first_inference_ms'] = (time.perf_counter_ns()-start)/1e6
        for _ in range(3):
            detector.run(first, confidence=.4)
        times = []
        for _ in range(runs):
            start = time.perf_counter_ns()
            detector.run(first, confidence=.4)
            times.append((time.perf_counter_ns()-start)/1e6)
        for row in data['replay']:
            frame = read_image(inside(root, row['image']))
            found, meta = detector.run(frame, confidence=.4)
            result['records'].append({'id': row['id'], 'pixel_sha256': image_digest(frame),
                                      'detections': found, 'meta': meta})
        result.update(status='COMPLETED', backend=detector.info, benchmark_runs=runs,
                      timing_ms=stats(times), timing_scope='WARM_FULL_FRAME_AND_SQUARE_VIEWS_DETECTOR_ONLY')
    except Exception as exc:
        result['error'] = f'{type(exc).__name__}: {exc}'
        raise
    finally:
        if detector is not None:
            result['profile'] = detector.close()
        save(out/'detector.json', result)
    return result


class RecordedDetector:
    """Use detections only on their exact original frame, without re-detection."""
    def __init__(self, spec, row):
        self.spec, self.row = spec, row
        self.info = row['meta']['backend']

    def run(self, frame, roi=None, confidence=.4):
        if roi is not None or confidence != .4 or image_digest(frame) != self.row['pixel_sha256']:
            raise ValueError('Cross-environment frame/policy mismatch')
        return self.row['detections'], self.row['meta']


def validate_detector_record(result, data, inputs):
    if (result.get('schema') != 'gesture.ai_pc.mode_b_detector_stage.v1'
            or result.get('status') != 'COMPLETED' or result.get('inputs_sha256') != digest(inputs)
            or result.get('policy') != POLICY or result.get('physical_execution') is not False):
        raise ValueError('Complete, matching detector stage required')
    expected = [(r['id'], r['pixel_sha256']) for r in data['replay']]
    actual = [(r['id'], r['pixel_sha256']) for r in result['records']]
    if actual != expected:
        raise ValueError('Detector stage frame set/order mismatch')
    backend = result.get('backend', {})
    if (backend.get('actual_backend') not in ('onnx_cpu', 'npu')
            or backend.get('actual_backend') != result.get('requested_backend')
            or backend.get('cpu_fallback') is not False or backend.get('classes') != CLASSES):
        raise ValueError('Detector backend identity mismatch')
    for row in result['records']:
        info = row['meta']['backend']
        if any(info.get(k) != backend.get(k) for k in ('actual_backend', 'model_sha256', 'classes')):
            raise ValueError('Mixed backend/model detector records')
        for det in row['detections']:
            box = np.asarray(det.get('bbox_xyxy_raw'), float)
            if (det.get('class_name') not in CLASSES or det.get('class_id') != CLASSES.index(det['class_name'])
                    or box.shape != (4,) or not np.isfinite(box).all() or np.any(box[2:] <= box[:2])):
                raise ValueError('Invalid six-class detector record')
    return result


def surfaces(inputs, root, detector_file, backend, out):
    # No Torch import is required in the detector SDK process.
    import torch
    from pc.mode_b.perception import Perception, draw
    from pc.mode_b.surface_ensemble import AlignedSurfaceEnsemble
    from pc.multiobject.surface import SurfaceRuntime
    torch.set_num_threads(4)
    data = load_inputs(inputs, root)
    recorded = validate_detector_record(json.loads(Path(detector_file).read_bytes()), data, inputs)
    out = fresh(out)
    summary = {'schema': 'gesture.ai_pc.mode_b_surface_stage.v1', 'status': 'ERROR',
               'inputs_sha256': digest(inputs), 'detector_record_sha256': digest(detector_file),
               'requested_backend': backend, 'records': [], 'physical_execution': False,
               'path_submissions': 0, 'metric_localization_accepted': False,
               'npu_acceptance': 'NOT_ACCEPTED', 'rocm_acceptance': 'NOT_ACCEPTED'}
    try:
        surface = AlignedSurfaceEnsemble(SurfaceRuntime(inside(root, data['surface']), backend))
        profile = Profile.load(inside(root, data['profile']))
        spec = json.loads(inside(root, data['detector']).read_bytes())
        times, classes, tops = [], Counter(), Counter()
        for row, detected in zip(data['replay'], recorded['records']):
            frame = read_image(inside(root, row['image']))
            obs = Perception(RecordedDetector(spec, detected), surface, profile).infer(frame)
            save(out/(row['id']+'_observation.json'), obs)
            write_image(out/(row['id']+'_detected.png'), draw(frame, obs))
            summary['records'].append({'id': row['id'], 'observation': obs})
            classes.update(r['class_name'] for r in obs['recognitions'])
            tops.update(r['class_name'] for r in obs['localizations'] if r['pixel_surface'])
            times.append(obs['total_ms'])
        summary.update(status='COMPLETED', backend=surface.info, detections_by_class=dict(classes),
                       available_tops_by_class=dict(tops), timing_ms=stats(times),
                       timing_scope='SURFACE_CROPS_GEOMETRY_WITH_CACHED_DETECTIONS_NO_IO',
                       rocm_execution_observed=bool(backend == 'rocm' and torch.version.hip),
                       rocm_version_acceptance='REVIEW_OFFICIAL_INSTALLED_RELEASE_AND_SUPPORT_MATRIX')
    except Exception as exc:
        summary['error'] = f'{type(exc).__name__}: {exc}'
        raise
    finally:
        save(out/'surface.json', summary)
    return summary


def contour(fit):
    return np.asarray(fit.get('quad_pixel_uv') or fit['contour_pixel_uv'], np.float32)


def polygon_iou(a, b):
    a, b = contour(a), contour(b)
    lo = np.floor(np.minimum(a.min(0), b.min(0))).astype(int)
    hi = np.ceil(np.maximum(a.max(0), b.max(0))).astype(int)
    size = hi-lo+3
    if np.any(size <= 0) or np.prod(size) > 20_000_000:
        raise ValueError('Unbounded comparison polygon')
    masks = [np.zeros((size[1], size[0]), np.uint8) for _ in range(2)]
    for mask, points in zip(masks, (a, b)):
        cv2.fillPoly(mask, [np.rint(points-lo+1).astype(np.int32)], 1)
    return float(np.count_nonzero(masks[0]&masks[1])/max(1, np.count_nonzero(masks[0]|masks[1])))


def compare(reference_file, candidate_file, inputs, root, out):
    data = load_inputs(inputs, root)
    ref, new = [json.loads(Path(p).read_bytes()) for p in (reference_file, candidate_file)]
    ids = [r['id'] for r in data['replay']]
    for report in (ref, new):
        if (report.get('schema') != 'gesture.ai_pc.mode_b_surface_stage.v1'
                or report.get('status') != 'COMPLETED' or report.get('inputs_sha256') != digest(inputs)
                or [r['id'] for r in report['records']] != ids):
            raise ValueError('Complete, same-input surface runs required for comparison')
    rows = []
    for source, a, b in zip(data['replay'], ref['records'], new['records']):
        a, b = a['observation'], b['observation']
        if a['frame_sha256'] != source['pixel_sha256'] or b['frame_sha256'] != source['pixel_sha256']:
            raise ValueError('Comparison observation/frame mismatch')
        pairs, unmatched, used = [], [], set()
        for det in a['recognitions']:
            options = [(iou(det['bbox_xyxy_raw'], d['bbox_xyxy_raw']), j, d)
                       for j, d in enumerate(b['recognitions'])
                       if j not in used and d['class_name'] == det['class_name']]
            match = max(options, key=lambda r: r[0]) if options else None
            if match is None or match[0] < .5:
                unmatched.append(det['class_name'])
                continue
            score, j, d = match
            used.add(j)
            pairs.append({'class_name': det['class_name'], 'bbox_iou': score,
                          'confidence_delta': d['confidence']-det['confidence'],
                          'box_centre_delta_raw_px': float(np.linalg.norm(
                              (np.array(det['bbox_xyxy_raw'])[:2]+det['bbox_xyxy_raw'][2:])/2-
                              (np.array(d['bbox_xyxy_raw'])[:2]+d['bbox_xyxy_raw'][2:])/2))})
        extra = [d['class_name'] for j, d in enumerate(b['recognitions']) if j not in used]
        local = []
        for x, y in zip(a['localizations'], b['localizations']):
            if x['task_id'] != y['task_id']:
                raise ValueError('Localization task order mismatch')
            row = {'task_id': x['task_id'], 'class_name': x['class_name'],
                   'reference_status': x['status'], 'candidate_status': y['status'],
                   'reference_available': bool(x['pixel_surface']),
                   'candidate_available': bool(y['pixel_surface'])}
            if x['pixel_surface'] and y['pixel_surface']:
                row['top_polygon_iou'] = polygon_iou(x['pixel_surface'], y['pixel_surface'])
                if x['pixel_surface']['pixel_uv'] and y['pixel_surface']['pixel_uv']:
                    row['centre_delta_raw_px'] = float(np.linalg.norm(
                        np.array(x['pixel_surface']['pixel_uv'])-y['pixel_surface']['pixel_uv']))
                else:
                    row['centre_policy'] = 'BOTTLE_CONTOUR_ONLY_PHYSICAL_CENTRE_NEEDS_TOP_PLANE'
            local.append(row)
        rows.append({'id': source['id'], 'matched': pairs, 'missing_relative_to_cpu': unmatched,
                     'extra_relative_to_cpu': extra, 'localizations': local})
    out = Path(out)
    if out.exists():
        raise ValueError('Fresh comparison output required')
    result = {'schema': 'gesture.ai_pc.mode_b_deployment_comparison.v1',
              'status': 'REGRESSION_DIAGNOSTICS_COMPLETE_REVIEW_REQUIRED', 'records': rows,
              'reference_sha256': digest(reference_file), 'candidate_sha256': digest(candidate_file),
              'inputs_sha256': digest(inputs), 'ground_truth': 'CPU_REFERENCE_NOT_INDEPENDENT_GT',
              'physical_execution': False, 'path_submissions': 0,
              'metric_localization_accepted': False, 'hardware_acceptance': False}
    out.parent.mkdir(parents=True, exist_ok=True)
    save(out, result)
    return result
