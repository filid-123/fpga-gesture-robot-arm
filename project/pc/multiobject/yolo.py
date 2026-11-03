"""Static YOLOv8 ONNX, raw outputs, explicit CPU/NPU choice and no fallback."""
from pathlib import Path
import hashlib
import json
import time
import cv2
import numpy as np
from pc.multiobject.registry import TASKS


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def image_digest(frame):
    return hashlib.sha256(memoryview(np.ascontiguousarray(frame))).hexdigest()


def load_package(path):
    path = Path(path).resolve()
    spec = json.loads(path.read_bytes())
    if spec.get('schema') != 'gesture.ai_pc.yolov8_package.v1':
        raise ValueError('Unknown detector package')
    names = spec.get('classes')
    if (not isinstance(names, list) or not names or len(set(names)) != len(names) or
            any(not isinstance(n, str) or not n for n in names)):
        raise ValueError('Invalid detector class order')
    role = spec.get('role')
    if role not in ('cube_detector', 'object_recognizer', 'mode_b_detector'):
        raise ValueError('Invalid detector role')
    if role == 'mode_b_detector':
        from pc.mode_b.profile import CLASSES, PROFILE_ID
        if names != CLASSES or spec.get('profile_id') != PROFILE_ID:
            raise ValueError('Mode B detector class order/profile mismatch')
    if role == 'cube_detector' and names[:3] != list(TASKS.values()):
        raise ValueError('Cube head must begin red/yellow/blue in that order')
    trained = spec.get('trained_classes')
    if not isinstance(trained, list) or not set(trained).issubset(names):
        raise ValueError('Explicit trained class coverage required')
    if role == 'cube_detector' and not set(TASKS.values()).issubset(trained):
        raise ValueError('Untrained colour task head refused')
    if spec.get('output_encoding') != 'YOLOV8_XYWH_CLASS_PROB_NO_NMS':
        raise ValueError('Unsupported detector head layout')
    size = spec.get('input_size_wh')
    if (not isinstance(size, list) or len(size) != 2 or
            any(type(v) is not int or not 32 <= v <= 2048 or v % 32 for v in size)):
        raise ValueError('Static multiple-of-32 input required')
    model = (path.parent / spec['onnx']['file']).resolve()
    if not model.is_relative_to(path.parent) or digest(model) != spec['onnx']['sha256']:
        raise ValueError('Detector model hash/path mismatch')
    if spec.get('input_encoding') != 'RGB_FLOAT_0_1_LETTERBOX_114':
        raise ValueError('Detector preprocessing mismatch')
    return spec, model


def prepare(frame, size, roi=None):
    if not isinstance(frame, np.ndarray) or frame.dtype != np.uint8 or frame.ndim != 3 or frame.shape[2] != 3:
        raise ValueError('BGR uint8 image required')
    h, w = frame.shape[:2]
    x, y, rw, rh = roi if roi is not None else (0, 0, w, h)
    if (any(type(v) is not int for v in (x, y, rw, rh)) or min(x, y) < 0 or
            min(rw, rh) <= 0 or x+rw > w or y+rh > h):
        raise ValueError('Invalid detector ROI')
    iw, ih = size
    scale = min(iw/rw, ih/rh)
    nw, nh = max(1, round(rw*scale)), max(1, round(rh*scale))
    left, top = (iw-nw)//2, (ih-nh)//2
    canvas = np.full((ih, iw, 3), 114, np.uint8)
    canvas[top:top+nh, left:left+nw] = cv2.resize(frame[y:y+rh, x:x+rw], (nw, nh))
    tensor = np.ascontiguousarray(canvas[:, :, ::-1].transpose(2, 0, 1)[None], dtype=np.float32)/255
    return tensor, {'roi_xywh_raw': [x, y, rw, rh], 'input_size_wh': list(size),
                    'raw_size_wh': [w, h], 'padding_left_top': [left, top],
                    'resized_size_wh': [nw, nh], 'scale_xy': [nw/rw, nh/rh]}


def iou(a, b):
    a, b = np.asarray(a), np.asarray(b)
    lo, hi = np.maximum(a[:2], b[:2]), np.minimum(a[2:], b[2:])
    inter = np.prod(np.maximum(hi-lo, 0))
    area = np.prod(a[2:]-a[:2])+np.prod(b[2:]-b[:2])-inter
    return float(inter/area) if area > 0 else 0.


def decode(output, mapping, names, confidence=.4, nms_iou=.5, max_detections=100):
    a = np.asarray(output)
    if (a.ndim != 3 or a.shape[:2] != (1, 4+len(names)) or not np.isfinite(a).all() or
            not .01 <= confidence < 1 or not 0 < nms_iou < 1):
        raise ValueError('Invalid YOLO raw output or thresholds')
    a = a[0].T
    if np.any(a[:, 4:] < -.001) or np.any(a[:, 4:] > 1.001):
        raise ValueError('Require class probabilities, not logits/objectness')
    ids = a[:, 4:].argmax(1)
    scores = a[np.arange(len(a)), ids+4]
    # Bound worst-case CPU postprocessing even on malformed/noisy model outputs.
    indices = np.flatnonzero(scores >= confidence)
    indices = indices[np.argsort(-scores[indices], kind='stable')[:3000]]
    x, y, rw, rh = mapping['roi_xywh_raw']
    left, top = mapping['padding_left_top']
    sx, sy = mapping['scale_xy']
    candidates = []
    for j in indices:
        cx, cy, bw, bh = map(float, a[j, :4])
        if bw <= 0 or bh <= 0:
            continue
        box = [(cx-bw/2-left)/sx+x, (cy-bh/2-top)/sy+y,
               (cx+bw/2-left)/sx+x, (cy+bh/2-top)/sy+y]
        box = [max(x, box[0]), max(y, box[1]), min(x+rw, box[2]), min(y+rh, box[3])]
        if box[2]-box[0] < 2 or box[3]-box[1] < 2:
            continue
        cls = int(ids[j])
        if any(c['class_id'] == cls and iou(box, c['bbox_xyxy_raw']) > nms_iou for c in candidates):
            continue
        candidates.append({'class_id': cls, 'class_name': names[cls],
                           'confidence': float(scores[j]), 'bbox_xyxy_raw': box})
        if len(candidates) >= max_detections:
            break
    return candidates


class Detector:
    def __init__(self, package, backend='npu', provider_options=None, profile_dir=None):
        import onnxruntime as ort
        self.spec, model = load_package(package)
        self.backend = backend
        provider = {'npu': 'VitisAIExecutionProvider', 'onnx_cpu': 'CPUExecutionProvider'}.get(backend)
        if provider is None or provider not in ort.get_available_providers():
            raise RuntimeError(f'{backend} unavailable; fallback refused')
        if backend == 'npu' and (not provider_options or self.spec.get('precision') not in ('bf16', 'int8', 'xint8')):
            raise ValueError('NPU requires a quantized package and explicit SDK-matched options')
        options = ort.SessionOptions()
        options.intra_op_num_threads = 4
        if backend == 'npu':
            options.add_session_config_entry('session.disable_cpu_ep_fallback', '1')
            provider_options = dict(provider_options)
            # Compiled caches must not alias the custom and COCO models.
            provider_options['cache_key'] = str(provider_options.get('cache_key', 'multiobject'))+'_'+digest(model)[:16]
            options.log_severity_level = 0
            options.enable_profiling = True
            if profile_dir:
                Path(profile_dir).mkdir(parents=True, exist_ok=True)
                options.profile_file_prefix = str(Path(profile_dir)/('ort_npu_'+digest(model)[:16]))
        self.session = ort.InferenceSession(str(model), sess_options=options, providers=[provider],
                    provider_options=[provider_options or {}])
        self.session.disable_fallback()
        inp = self.session.get_inputs()
        w, h = self.spec['input_size_wh']
        if len(inp) != 1 or inp[0].shape != [1, 3, h, w] or inp[0].type != 'tensor(float)':
            raise ValueError('Detector input shape/type mismatch')
        if len(self.session.get_outputs()) != 1:
            raise ValueError('One raw detector output required')
        self.input_name = inp[0].name
        self.info = {'requested_backend': backend, 'actual_backend': backend, 'role': self.spec['role'],
                     'framework': 'onnxruntime', 'framework_version': ort.__version__,
                     'actual_providers': self.session.get_providers(), 'cpu_fallback': False,
                     'precision': self.spec['precision'], 'classes': self.spec['classes'],
                     'trained_classes': self.spec['trained_classes'],
                     'model_sha256': digest(model), 'package_sha256': digest(package),
                     'npu_execution_verified': False, 'hardware_acceptance': 'PENDING'}

    def run(self, frame, roi=None, confidence=.4):
        start = time.perf_counter_ns()
        tensor, mapping = prepare(frame, self.spec['input_size_wh'], roi)
        before = time.perf_counter_ns()
        raw = self.session.run(None, {self.input_name: tensor})[0]
        after = time.perf_counter_ns()
        found = decode(raw, mapping, self.spec['classes'], confidence)
        # A registered but untrained class must not become a task candidate.
        for d in found:
            d.update(model_role=self.spec['role'], trained=d['class_name'] in self.spec['trained_classes'])
        return found, {'backend': dict(self.info), 'mapping': mapping,
                       'timing_ms': {'preprocess': (before-start)/1e6, 'model': (after-before)/1e6,
                                     'decode_nms': (time.perf_counter_ns()-after)/1e6}}

    def close(self):
        if self.backend != 'npu':
            return None
        from pc.multiobject.evidence import summarize_profile
        return summarize_profile(self.session.end_profiling())
