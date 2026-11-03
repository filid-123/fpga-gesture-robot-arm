"""Untrained PC prototype for the hardware-prioritized B geometry residual branch."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import torch
from torch import nn

from locator_model import HandLocatorNet, assert_fixed_locator_topology


@dataclass(frozen=True)
class ContextBContract:
    base_parameters: int = 7265
    added_parameters: int = 1452
    total_parameters: int = 8717
    base_macs: int = 7649280
    added_macs: int = 368640
    total_macs: int = 8017920
    geometry_input_channels: int = 16
    geometry_hidden_channels: int = 8
    geometry_output_channels: int = 4
    geometry_dilation_g1: int = 2
    geometry_dilation_g2: int = 5
    geometry_feature_shape: tuple[int, int, int] = (16, 16, 16)
    output_shape: tuple[int, int, int] = (5, 16, 16)
    residual_channel_order: tuple[str, str, str, str] = ("dx", "dy", "width", "height")


class HandLocatorNetContextB(nn.Module):
    """Original locator plus a zero-initialized geometry-only residual branch.

    The original confidence path and Conv4/Conv5 path remain intact. The new
    branch reads Conv3's pooled 16x16x16 feature, produces four geometry
    residual channels, and adds them to dx/dy/width/height. Zero initialization
    makes the initial output exactly equal to HandLocatorNet.
    """

    def __init__(self, branch_seed: int = 20261011) -> None:
        super().__init__()
        self.base = HandLocatorNet()
        self.base.requires_grad_(False)
        self.base.eval()
        self.branch_seed = branch_seed
        # Seed before branch creation, while preserving the caller's RNG stream.
        with torch.random.fork_rng(devices=[]):
            torch.manual_seed(branch_seed)
            self.geometry_g1 = nn.Conv2d(16, 8, kernel_size=3, stride=1, padding=2, dilation=2, bias=True)
            self.geometry_g2 = nn.Conv2d(8, 4, kernel_size=3, stride=1, padding=5, dilation=5, bias=True)
        self.geometry_relu = nn.ReLU(inplace=False)
        # G1 keeps the normal Conv2d initialization. G2 is the zero-initialized
        # residual gate, so the complete branch starts at exact zero while the
        # first learned residual layer has a usable initialized feature basis.
        nn.init.zeros_(self.geometry_g2.weight)
        nn.init.zeros_(self.geometry_g2.bias)

    def train(self, mode: bool = True) -> HandLocatorNetContextB:
        super().train(mode)
        self.base.eval()
        return self

    def trainable_geometry_parameters(self):
        """The sole parameter collection intended for a branch optimizer."""
        return [*self.geometry_g1.parameters(), *self.geometry_g2.parameters()]

    def forward_with_base(self, inputs: torch.Tensor):
        with torch.no_grad():
            x = self.base.pool(self.base.relu(self.base.conv1(inputs)))
            x = self.base.pool(self.base.relu(self.base.conv2(x)))
            f3 = self.base.pool(self.base.relu(self.base.conv3(x)))
            base_features = self.base.relu(self.base.conv4(f3))
            base_output = self.base.conv5(base_features)
        residual = self.geometry_g2(self.geometry_relu(self.geometry_g1(f3)))
        return torch.cat((base_output[:, :1], base_output[:, 1:] + residual), dim=1), base_output

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        return self.forward_with_base(inputs)[0]


def contract() -> dict[str, Any]:
    value = asdict(ContextBContract())
    value["geometry_feature_shape"] = list(value["geometry_feature_shape"])
    value["output_shape"] = list(value["output_shape"])
    value["residual_channel_order"] = list(value["residual_channel_order"])
    return value


def assert_context_b_topology(model: HandLocatorNetContextB) -> None:
    if sum(parameter.numel() for parameter in model.parameters()) != ContextBContract.total_parameters:
        raise AssertionError("Context B parameter count changed")
    assert_fixed_locator_topology(model.base)
    if tuple(model.geometry_g1.weight.shape) != (8, 16, 3, 3) or tuple(model.geometry_g2.weight.shape) != (4, 8, 3, 3):
        raise AssertionError("Context B geometry branch shape changed")
    if any(p.requires_grad for p in model.base.parameters()):
        raise AssertionError("Context B original backbone must stay frozen")
    if not all(p.requires_grad for p in model.trainable_geometry_parameters()):
        raise AssertionError("Context B geometry branch must remain trainable")

