"""Frozen models executed on an explicit HIP device, with no CPU fallback."""
import time
import cv2
import numpy as np
import torch
from pc.multiobject.yolo import load_package, digest, prepare, decode
from pc.multiobject.surface import SurfaceRuntime


def hip_info():
    if not torch.version.hip or not torch.cuda.is_available():
        raise RuntimeError('ROCm HIP device required; CPU fallback refused')
    return dict(framework='torch', framework_version=torch.__version__,
                hip_version=torch.version.hip, device=torch.cuda.get_device_name(0),
                requested_backend='rocm', actual_backend='rocm', cpu_fallback=False)


class RocmDetector:
    def __init__(self, package):
        import onnx
        from onnx2torch import convert
        self.info = hip_info()
        self.spec, model = load_package(package)
        if self.spec['precision'] != 'fp32':
            raise ValueError('Immutable original FP32 detector required')
        self.model = convert(onnx.load(str(model))).eval().to('cuda')
        if any(t.device.type != 'cuda' for t in list(self.model.parameters())+list(self.model.buffers())):
            raise RuntimeError('Detector parameters are not exclusively on HIP')
        self.info.update(role=self.spec['role'], model_sha256=digest(model),
                         package_sha256=digest(package), precision='fp32',
                         conversion='onnx2torch', conversion_version='1.5.15',
                         classes=self.spec['classes'], trained_classes=self.spec['trained_classes'])

    def run(self, frame, roi=None, confidence=.4):
        start = time.perf_counter_ns()
        array, mapping = prepare(frame, self.spec['input_size_wh'], roi)
        before = time.perf_counter_ns()
        with torch.inference_mode():
            raw = self.model(torch.from_numpy(array).to('cuda'))
            if isinstance(raw, (list, tuple)):
                if len(raw) != 1:
                    raise ValueError('Expected one frozen detector output')
                raw = raw[0]
            raw = raw.cpu().numpy()  # Synchronizes the actual batch-one result.
        after = time.perf_counter_ns()
        found = decode(raw, mapping, self.spec['classes'], confidence)
        for row in found:
            row.update(model_role=self.spec['role'], trained=row['class_name'] in self.spec['trained_classes'])
        return found, dict(backend=dict(self.info), mapping=mapping,
                          timing_ms=dict(preprocess=(before-start)/1e6, model=(after-before)/1e6,
                                         decode_nms=(time.perf_counter_ns()-after)/1e6))


def fuse_eval_pairs(module):
    count = 0
    for child in module.children():
        count += fuse_eval_pairs(child)
    if isinstance(module, torch.nn.Sequential):
        for i in range(len(module)-1):
            if isinstance(module[i], torch.nn.Conv2d) and isinstance(module[i+1], torch.nn.BatchNorm2d):
                module[i] = torch.nn.utils.fuse_conv_bn_eval(module[i], module[i+1])
                module[i+1] = torch.nn.Identity()
                count += 1
    return count


class RocmSurface(SurfaceRuntime):
    def __init__(self, package):
        super().__init__(package, 'rocm')
        # Exact inference-time Conv/BN algebra avoids the SDK's missing-header
        # BatchNorm JIT path. Original checkpoint bytes remain unchanged.
        self.info.update(hip_info(), eval_conv_bn_pairs_fused=fuse_eval_pairs(self.model))
        if any(isinstance(m, torch.nn.BatchNorm2d) for m in self.model.modules()):
            raise RuntimeError('An unfused BatchNorm remains')
        self.timings=[]

    def run(self,frame,box):
        h,w=frame.shape[:2];x,y=np.floor(box[:2]).astype(int);x2,y2=np.ceil(box[2:]).astype(int)
        if min(x,y)<0 or x2>w or y2>h or x2<=x or y2<=y:raise ValueError('Invalid surface ROI')
        start=time.perf_counter_ns()
        crop=cv2.cvtColor(cv2.resize(frame[y:y2,x:x2],(self.side,self.side)),cv2.COLOR_BGR2RGB)
        tensor=torch.from_numpy(np.ascontiguousarray(crop.transpose(2,0,1)[None],dtype=np.float32)/255).to('cuda')
        torch.cuda.synchronize();before=time.perf_counter_ns()
        with torch.inference_mode():logits=self.model(tensor)
        torch.cuda.synchronize();after=time.perf_counter_ns()
        p=logits.sigmoid()[0,0].cpu().numpy()
        if not np.isfinite(p).all():raise ValueError('Nonfinite surface output')
        p=cv2.resize(p,(x2-x,y2-y));end=time.perf_counter_ns()
        timing=dict(preprocess=(before-start)/1e6,model=(after-before)/1e6,
                    postprocess=(end-after)/1e6,total=(end-start)/1e6)
        self.timings.append(dict(roi_xyxy_raw=[int(x),int(y),int(x2),int(y2)],timing_ms=timing))
        return p,[int(x),int(y)],dict(backend=dict(self.info),total_ms=timing['total'],timing_ms=timing)
