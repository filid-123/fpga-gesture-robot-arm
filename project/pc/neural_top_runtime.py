"""Verified model packages and explicitly selected inference providers.

CPU and CUDA are development backends, never evidence of AMD/ROCm execution.
Vitis AI is experimental: actual node placement must be established from profiling.
"""
from pathlib import Path
import hashlib
import json
import platform
import time
import re
import cv2
import numpy as np

CLASSES = ['background', 'red_cube', 'yellow_cube', 'blue_cube']


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_package(path):
    path = Path(path).resolve()
    spec = json.loads(path.read_bytes())
    if spec.get('schema') != 'gesture.ai_pc.neural_top_package.v1':
        raise ValueError('Unknown neural model package')
    if spec.get('classes') != CLASSES or spec.get('input_encoding') != 'RGB_FLOAT_0_1':
        raise ValueError('Model classes or input encoding mismatch')
    size = spec.get('input_size_wh')
    if (not isinstance(size, list) or len(size) != 2 or
            any(type(v) is not int or v < 32 or v > 2048 or v % 4 for v in size)):
        raise ValueError('Invalid static input size')
    if spec.get('architecture') != 'tiny_top_unet_v1':
        raise ValueError('Unsupported model architecture')
    if not any(spec.get(kind) for kind in ('checkpoint', 'onnx')):
        raise ValueError('Model package contains no weights')
    for kind in ('checkpoint', 'onnx'):
        entry = spec.get(kind)
        if entry is None:
            continue
        p = (path.parent / entry['file']).resolve()
        if not p.is_relative_to(path.parent) or sha256(p) != entry['sha256']:
            raise ValueError(f'{kind} model hash/path mismatch')
    return spec, path.parent


def prepare(frame, size, roi=None):
    if frame.ndim != 3 or frame.shape[2] != 3 or frame.dtype != np.uint8:
        raise ValueError('Require BGR uint8 frame')
    h, w = frame.shape[:2]
    x, y, rw, rh = roi or (0, 0, w, h)
    if any(type(v) is not int for v in (x, y, rw, rh)) or min(x, y) < 0 or min(rw, rh) < 4 or x+rw > w or y+rh > h:
        raise ValueError('Invalid original-image ROI')
    iw, ih = size
    scale = min(iw / rw, ih / rh)
    nw, nh = max(1, round(rw * scale)), max(1, round(rh * scale))
    left, top = (iw - nw) // 2, (ih - nh) // 2
    rgb = cv2.cvtColor(frame[y:y+rh, x:x+rw], cv2.COLOR_BGR2RGB)
    canvas = np.zeros((ih, iw, 3), np.uint8)
    canvas[top:top+nh, left:left+nw] = cv2.resize(rgb, (nw, nh), interpolation=cv2.INTER_AREA)
    return np.ascontiguousarray(canvas.transpose(2, 0, 1)[None], dtype=np.float32) / 255., {
        'raw_size_wh': [w, h], 'input_size_wh': list(size), 'roi_xywh_raw': [x, y, rw, rh],
        'resized_size_wh': [nw, nh], 'padding_left_top': [left, top],
        'scale_xy': [nw / rw, nh / rh], 'convention': 'OpenCV pixel-centre resize'}


def restore_probabilities(logits, mapping):
    iw, ih = mapping['input_size_wh']
    logits = np.asarray(logits, dtype=np.float32)
    if logits.shape != (1, 4, ih, iw) or not np.isfinite(logits).all():
        raise ValueError('Invalid neural output tensor')
    a = logits[0] - np.max(logits[0], axis=0, keepdims=True)
    p = np.exp(a)
    p /= np.sum(p, axis=0, keepdims=True)
    l, t = mapping['padding_left_top']
    nw, nh = mapping['resized_size_wh']
    x, y, rw, rh = mapping['roi_xywh_raw']
    w, h = mapping['raw_size_wh']
    full = np.zeros((4, h, w), np.float32)
    full[0] = 1.
    for k in range(4):
        full[k, y:y+rh, x:x+rw] = cv2.resize(p[k, t:t+nh, l:l+nw], (rw, rh), interpolation=cv2.INTER_LINEAR)
    return full


class NeuralRuntime:
    def __init__(self, package, backend='onnx_cpu', provider_options=None):
        self.spec, self.directory = load_package(package)
        self.backend = backend
        self.profile_path = None
        self.info = {'requested_backend': backend, 'actual_backend': backend, 'cpu_fallback': False,
                     'model_package_sha256': sha256(package), 'precision': 'fp32',
                     'host_platform': platform.platform(), 'amd_acceptance': False}
        if backend in ('torch_cpu', 'torch_cuda', 'rocm'):
            if not self.spec.get('checkpoint'):
                raise ValueError('Selected backend requires a checkpoint')
            import torch
            from pc.neural_top_model import TinyTopNet
            hip = torch.version.hip
            available = torch.cuda.is_available()
            if backend == 'rocm' and (not hip or not available):
                raise RuntimeError('ROCm requested but no HIP-backed GPU; CPU/CUDA substitution refused')
            if backend == 'torch_cuda' and (hip or not available):
                raise RuntimeError('NVIDIA CUDA requested but unavailable')
            self.device = 'cpu' if backend == 'torch_cpu' else 'cuda'
            self.model = TinyTopNet(self.spec['width'])
            state = torch.load(self.directory / self.spec['checkpoint']['file'], map_location='cpu', weights_only=True)
            self.model.load_state_dict(state, strict=True)
            self.model.eval().to(self.device)
            self.torch = torch
            self.info.update(framework='torch', framework_version=torch.__version__, hip_version=hip,
                             cuda_version=torch.version.cuda, device=('cpu' if self.device == 'cpu' else torch.cuda.get_device_name(0)),
                             model_sha256=self.spec['checkpoint']['sha256'])
        elif backend in ('onnx_cpu', 'vitisai'):
            if not self.spec.get('onnx'):
                raise ValueError('Selected backend requires an ONNX model')
            import onnxruntime as ort
            provider = 'CPUExecutionProvider' if backend == 'onnx_cpu' else 'VitisAIExecutionProvider'
            if provider not in ort.get_available_providers():
                raise RuntimeError(f'{provider} unavailable; fallback refused')
            opts = ort.SessionOptions()
            opts.intra_op_num_threads = 4
            opts.enable_profiling = backend == 'vitisai'
            if backend == 'vitisai':
                if not provider_options:
                    raise ValueError('Vitis AI requires explicit version-matched provider options')
                opts.add_session_config_entry('session.disable_cpu_ep_fallback', '1')
            self.session = ort.InferenceSession(str(self.directory / self.spec['onnx']['file']),
                sess_options=opts, providers=[provider], provider_options=[provider_options or {}])
            self.session.disable_fallback()
            inp = self.session.get_inputs()
            iw, ih = self.spec['input_size_wh']
            if len(inp) != 1 or inp[0].shape != [1, 3, ih, iw] or inp[0].type != 'tensor(float)':
                raise ValueError('ONNX input differs from package')
            self.input_name = inp[0].name
            self.info.update(framework='onnxruntime', framework_version=ort.__version__,
                             actual_providers=self.session.get_providers(),
                             node_placement_verified=False, model_sha256=self.spec['onnx']['sha256'])
        else:
            raise ValueError('Unsupported backend')

    def run(self, frame, roi=None):
        start = time.perf_counter_ns()
        tensor, mapping = prepare(frame, self.spec['input_size_wh'], roi)
        prepared = time.perf_counter_ns()
        if self.backend.startswith('torch') or self.backend == 'rocm':
            torch = self.torch
            with torch.inference_mode():
                x = torch.from_numpy(tensor).to(self.device)
                if self.device != 'cpu':
                    torch.cuda.synchronize()
                model_start = time.perf_counter_ns()
                out = self.model(x)
                if self.device != 'cpu':
                    torch.cuda.synchronize()
                model_end = time.perf_counter_ns()
                logits = out.cpu().numpy()
        else:
            model_start = time.perf_counter_ns()
            logits = self.session.run(None, {self.input_name: tensor})[0]
            model_end = time.perf_counter_ns()
        probabilities = restore_probabilities(logits, mapping)
        end = time.perf_counter_ns()
        return probabilities, {'backend': dict(self.info), 'mapping': mapping,
            'timing_ms': {'preprocess': (prepared-start)/1e6, 'model': (model_end-model_start)/1e6,
                          'postprocess': (end-model_end)/1e6, 'total_perception': (end-start)/1e6,
                          'input_transfer': (model_start-prepared)/1e6}}

    def close_profile(self):
        if self.backend != 'vitisai':
            return None
        path = self.session.end_profiling()
        events = json.loads(Path(path).read_bytes())
        providers = [e.get('args', {}).get('provider') for e in events if e.get('cat') == 'Node']
        providers = [p for p in providers if p]
        verified = bool(providers) and all(p == 'VitisAIExecutionProvider' for p in providers)
        self.info['node_placement_verified'] = verified
        return {'profile_path': path, 'providers': sorted(set(providers)), 'node_events': len(providers),
                'npu_execution_verified': verified}
