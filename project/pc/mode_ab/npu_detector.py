"""Frozen detector numerics on the explicit Windows ML AMD NPU device.

The original FP32 ONNX is preserved. WinML VitisAI compiles float models using
its automatic BF16 path. This adapter reuses the frozen preprocessing/decoder
and refuses CPU execution; core placement is checked before accepting frames.
"""
from pathlib import Path
import json
import time

from pc.multiobject.yolo import Detector, load_package, digest
from pc.mode_ab.winml import NpuCatalog


class WindowsNpuDetector(Detector):
    def __init__(self, package, cache_root, catalog_info=None):
        import onnxruntime as ort
        self.catalog = None
        if catalog_info is None:
            self.catalog = NpuCatalog()
            self.catalog_info = self.catalog.ready()
            devices = self.catalog.devices
        else:
            # Keep the SDK catalog and the inference ORT in separate processes.
            # Each uses its own supported Python dependencies and DLL loader.
            self.catalog_info = dict(catalog_info)
            library = Path(catalog_info['library_path'])
            if not library.is_file() or catalog_info.get('provider')!='VitisAIExecutionProvider':
                raise ValueError('Missing certified AMD NPU library')
            ort.register_execution_provider_library('VitisAIExecutionProvider', str(library))
            devices = [d for d in ort.get_ep_devices() if d.ep_name=='VitisAIExecutionProvider']
            if not devices:
                raise RuntimeError('No AMD NPU device; CPU fallback refused')
        self.spec, model = load_package(package)
        self.backend = 'npu'
        if self.spec['precision'] != 'fp32':
            raise ValueError('This adapter uses the immutable original FP32 source model')
        cache = Path(cache_root)
        cache.mkdir(parents=True, exist_ok=True)
        options = ort.SessionOptions()
        options.intra_op_num_threads = 4
        options.enable_profiling = True
        options.profile_file_prefix = str(cache/'npu_placement')
        options.add_session_config_entry('session.disable_cpu_ep_fallback', '1')
        options.add_provider_for_devices(devices, {})
        started = time.perf_counter()
        self.session = ort.InferenceSession(str(model), sess_options=options)
        self.session.disable_fallback()
        inputs = self.session.get_inputs()
        w,h = self.spec['input_size_wh']
        if len(inputs)!=1 or inputs[0].shape != [1,3,h,w] or inputs[0].type != 'tensor(float)':
            raise ValueError('Frozen detector input changed')
        self.input_name = inputs[0].name
        self.info = dict(requested_backend='npu', actual_backend='npu', framework='onnxruntime_windowsml',
                         framework_version=ort.__version__, actual_providers=self.session.get_providers(),
                         source_precision='fp32', compilation_policy='WINML_AUTOMATIC_BF16',
                         cpu_fallback=False, npu_execution_verified=False,
                         model_sha256=digest(model), package_sha256=digest(package),
                         classes=self.spec['classes'], trained_classes=self.spec['trained_classes'],
                         session_creation_s=time.perf_counter()-started, catalog=self.catalog_info)
        self.placement = None

    def verify_placement(self):
        if self.placement:
            return self.placement
        path = self.session.end_profiling()
        events = json.loads(Path(path).read_text('utf-8'))
        nodes = [e for e in events if e.get('cat')=='Node' and e.get('args',{}).get('provider')]
        npu = [e for e in nodes if e['args']['provider']=='VitisAIExecutionProvider']
        cpu = [e for e in nodes if e['args']['provider']=='CPUExecutionProvider']
        if not npu or cpu:
            raise RuntimeError('NPU placement was not exclusive; motion remains unavailable')
        self.placement = dict(profile_path=str(path), profile_sha256=digest(path),
                              npu_node_events=len(npu), cpu_node_events=len(cpu), verified=True)
        self.info['npu_execution_verified'] = True
        self.info['placement'] = self.placement
        return self.placement

    def close(self):
        self.session = None
        if self.catalog:
            self.catalog.close()
