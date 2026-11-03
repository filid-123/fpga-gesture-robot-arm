"""Pretrained MobileNetV3 encoder with a learned binary cube-top decoder."""
from pathlib import Path
import json
import time
import cv2
import numpy as np
import torch
from torch import nn
from torch.nn import functional as F
from pc.multiobject.yolo import digest


class SurfaceNet(nn.Module):
    architecture = 'mobilenetv3_small_top_unet_v1'

    def __init__(self, pretrained=False):
        super().__init__()
        from torchvision.models import mobilenet_v3_small, MobileNet_V3_Small_Weights
        weights = MobileNet_V3_Small_Weights.IMAGENET1K_V1 if pretrained else None
        self.encoder = mobilenet_v3_small(weights=weights).features
        self.decoder = nn.Sequential(nn.Conv2d(576+48, 96, 3, padding=1), nn.ReLU(),
                                     nn.Conv2d(96, 32, 3, padding=1), nn.ReLU())
        self.head = nn.Sequential(nn.Conv2d(32+16, 24, 3, padding=1), nn.ReLU(), nn.Conv2d(24, 1, 1))
        self.register_buffer('mean', torch.tensor([.485, .456, .406]).view(1, 3, 1, 1))
        self.register_buffer('std', torch.tensor([.229, .224, .225]).view(1, 3, 1, 1))

    def forward(self, x):
        size = x.shape[-2:]
        z = (x-self.mean)/self.std
        early, middle = None, None
        for i, layer in enumerate(self.encoder):
            z = layer(z)
            if i == 1:
                early = z
            if i == 8:
                middle = z
        z = self.decoder(torch.cat((F.interpolate(z, size=middle.shape[-2:], mode='bilinear',
                                                 align_corners=False), middle), 1))
        z = self.head(torch.cat((F.interpolate(z, size=early.shape[-2:], mode='bilinear',
                                              align_corners=False), early), 1))
        return F.interpolate(z, size=size, mode='bilinear', align_corners=False)


class SurfaceRuntime:
    def __init__(self, package, backend='rocm'):
        path = Path(package).resolve()
        self.spec = json.loads(path.read_bytes())
        if (self.spec.get('schema') != 'gesture.ai_pc.surface_package.v1' or
                self.spec.get('architecture') != SurfaceNet.architecture or
                self.spec.get('input_encoding') != 'RGB_FLOAT_0_1_INTERNAL_IMAGENET_NORMALIZATION'):
            raise ValueError('Invalid surface package')
        entry = self.spec['checkpoint']
        file = (path.parent/entry['file']).resolve()
        if not file.is_relative_to(path.parent) or digest(file) != entry['sha256']:
            raise ValueError('Surface checkpoint hash/path mismatch')
        if backend == 'rocm':
            if not torch.version.hip or not torch.cuda.is_available():
                raise RuntimeError('ROCm requested without HIP device; fallback refused')
            self.device = 'cuda'
        elif backend == 'torch_cpu':
            self.device = 'cpu'
        else:
            raise ValueError('Surface backend must be rocm or explicitly development torch_cpu')
        self.model = SurfaceNet().eval().to(self.device)
        self.model.load_state_dict(torch.load(file, map_location='cpu', weights_only=True), strict=True)
        self.side = self.spec['input_side']
        if type(self.side) is not int or self.side < 64 or self.side > 1024 or self.side % 32:
            raise ValueError('Invalid surface input side')
        self.info = {'actual_backend': backend, 'requested_backend': backend,
                     'framework': 'torch', 'framework_version': torch.__version__,
                     'hip_version': torch.version.hip, 'model_sha256': digest(file),
                     'device': 'cpu' if self.device == 'cpu' else torch.cuda.get_device_name(0),
                     'hardware_acceptance': 'PENDING', 'cpu_fallback': False}

    def run(self, frame, box):
        h, w = frame.shape[:2]
        x, y = np.floor(box[:2]).astype(int)
        x2, y2 = np.ceil(box[2:]).astype(int)
        if min(x, y) < 0 or x2 > w or y2 > h or x2 <= x or y2 <= y:
            raise ValueError('Invalid surface ROI')
        start = time.perf_counter_ns()
        crop = cv2.cvtColor(cv2.resize(frame[y:y2, x:x2], (self.side, self.side)), cv2.COLOR_BGR2RGB)
        tensor = torch.from_numpy(np.ascontiguousarray(crop.transpose(2, 0, 1)[None], dtype=np.float32)/255)
        with torch.inference_mode():
            logits = self.model(tensor.to(self.device))
            p = logits.sigmoid()[0, 0].cpu().numpy()
        if not np.isfinite(p).all():
            raise ValueError('Nonfinite surface output')
        return cv2.resize(p, (x2-x, y2-y)), [int(x), int(y)], {
            'backend': dict(self.info), 'total_ms': (time.perf_counter_ns()-start)/1e6}
