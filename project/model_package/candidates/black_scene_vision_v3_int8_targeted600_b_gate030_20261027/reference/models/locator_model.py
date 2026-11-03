from __future__ import annotations

import torch
from torch import nn


LOCATOR_INPUT_SHAPE = (1, 128, 128)
LOCATOR_OUTPUT_SHAPE = (5, 16, 16)
LOCATOR_TASK_ID = "locator_six_class_v1"
LOCATOR_ARCHITECTURE = "HandLocatorNet_1x128x128_to_5x16x16"
LOCATOR_OUTPUT_CHANNELS = (
    "confidence",
    "dx",
    "dy",
    "width",
    "height",
)
LOCATOR_TARGET_POLICY = {
    "positive": "any visible hand, including target and non-target gestures",
    "negative": "no visible hand",
    "class_semantics": "class-agnostic hand presence and one primary bbox",
}


class HandLocatorNet(nn.Module):
    """Class-agnostic six-task 1x128x128 -> 5x16x16 hand locator.

    The six-class task belongs to the downstream classifier.  The locator has
    no gesture-class output: one/two/three/fist/palm and every non-target
    visible hand are positive localization targets, while a no-hand frame is
    negative.  Keeping this topology preserves the existing FPGA output ABI.
    """

    def __init__(self) -> None:
        super().__init__()
        self.conv1 = nn.Conv2d(1, 8, kernel_size=3, stride=1, padding=1, bias=True)
        self.conv2 = nn.Conv2d(8, 12, kernel_size=3, stride=1, padding=1, bias=True)
        self.conv3 = nn.Conv2d(12, 16, kernel_size=3, stride=1, padding=1, bias=True)
        self.conv4 = nn.Conv2d(16, 24, kernel_size=3, stride=1, padding=1, bias=True)
        self.conv5 = nn.Conv2d(24, 5, kernel_size=3, stride=1, padding=1, bias=True)
        self.relu = nn.ReLU(inplace=False)
        self.pool = nn.MaxPool2d(kernel_size=2, stride=2)

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        x = self.pool(self.relu(self.conv1(inputs)))
        x = self.pool(self.relu(self.conv2(x)))
        x = self.pool(self.relu(self.conv3(x)))
        x = self.relu(self.conv4(x))
        return self.conv5(x)


def model_parameter_counts(model: nn.Module) -> dict[str, int]:
    weights = sum(
        parameter.numel()
        for name, parameter in model.named_parameters()
        if name.endswith("weight")
    )
    biases = sum(
        parameter.numel()
        for name, parameter in model.named_parameters()
        if name.endswith("bias")
    )
    return {"weights": weights, "biases": biases, "total": weights + biases}


def assert_fixed_locator_topology(model: nn.Module) -> None:
    counts = model_parameter_counts(model)
    expected = {"weights": 7200, "biases": 65, "total": 7265}
    if counts != expected:
        raise AssertionError(f"Locator topology changed: expected {expected}, got {counts}")
    reference = next(model.parameters(), None)
    device = reference.device if reference is not None else torch.device("cpu")
    dtype = reference.dtype if reference is not None else torch.float32
    with torch.inference_mode():
        output = model(
            torch.zeros(
                1, *LOCATOR_INPUT_SHAPE, device=device, dtype=dtype
            )
        )
    if tuple(output.shape) != (1, *LOCATOR_OUTPUT_SHAPE):
        raise AssertionError(f"Unexpected locator output shape: {tuple(output.shape)}")
