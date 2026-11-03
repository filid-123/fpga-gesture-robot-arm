"""TinyTopNet: learned RGB top-surface segmentation, background/red/yellow/blue.

No colour thresholds, pretrained downloads, calibration or robot transport here.
Static, convolution/ReLU/pool/resize/concat architecture for ONNX portability.
"""
import torch
from torch import nn
from torch.nn import functional as F


class Block(nn.Sequential):
    def __init__(self, cin, cout):
        super().__init__(nn.Conv2d(cin, cout, 3, padding=1), nn.ReLU(),
                         nn.Conv2d(cout, cout, 3, padding=1), nn.ReLU())


class TinyTopNet(nn.Module):
    architecture = 'tiny_top_unet_v1'

    def __init__(self, width=12):
        super().__init__()
        self.width = width
        self.e1 = Block(3, width)
        self.e2 = Block(width, width * 2)
        self.e3 = Block(width * 2, width * 4)
        self.d2 = Block(width * 6, width * 2)
        self.d1 = Block(width * 3, width)
        self.head = nn.Conv2d(width, 4, 1)

    def forward(self, rgb):
        a = self.e1(rgb)
        b = self.e2(F.max_pool2d(a, 2))
        c = self.e3(F.max_pool2d(b, 2))
        d = self.d2(torch.cat((F.interpolate(c, size=b.shape[-2:], mode='nearest'), b), 1))
        e = self.d1(torch.cat((F.interpolate(d, size=a.shape[-2:], mode='nearest'), a), 1))
        return self.head(e)
