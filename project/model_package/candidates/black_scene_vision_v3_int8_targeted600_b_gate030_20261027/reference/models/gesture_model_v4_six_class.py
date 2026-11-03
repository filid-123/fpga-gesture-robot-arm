from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import torch
from torch import nn


CLASS_NAMES = (
    "background",
    "one",
    "two",
    "three",
    "fist",
    "palm",
)
CLASS_TO_ID = {name: index for index, name in enumerate(CLASS_NAMES)}
NUM_CLASSES = len(CLASS_NAMES)
INPUT_SHAPE = (1, 32, 32)
ARCHITECTURE_NAME = "GestureCNN_1x32x32_to_6_v4"

LEGACY_V3_CLASS_NAMES = ("background", "fist", "mute", "palm")
LEGACY_TO_V4_CLASS = {
    "background": "background",
    "fist": "fist",
    "palm": "palm",
}


class GestureCNN6(nn.Module):
    """Six-class classifier with the deployed v3 feature extractor.

    The 1x32x32 input, three convolution/pooling stages, and 512->64 fully
    connected feature layer are unchanged.  Only fc2 grows from 4 to 6
    outputs, in CLASS_NAMES order.
    """

    def __init__(self) -> None:
        super().__init__()
        self.conv1 = nn.Conv2d(1, 8, 3, padding=1)
        self.relu1 = nn.ReLU(inplace=False)
        self.pool1 = nn.MaxPool2d(2, 2)
        self.conv2 = nn.Conv2d(8, 16, 3, padding=1)
        self.relu2 = nn.ReLU(inplace=False)
        self.pool2 = nn.MaxPool2d(2, 2)
        self.conv3 = nn.Conv2d(16, 32, 3, padding=1)
        self.relu3 = nn.ReLU(inplace=False)
        self.pool3 = nn.MaxPool2d(2, 2)
        self.flatten = nn.Flatten()
        self.fc1 = nn.Linear(512, 64)
        self.relu4 = nn.ReLU(inplace=False)
        self.fc2 = nn.Linear(64, NUM_CLASSES)

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        x = self.pool1(self.relu1(self.conv1(inputs)))
        x = self.pool2(self.relu2(self.conv2(x)))
        x = self.pool3(self.relu3(self.conv3(x)))
        x = self.flatten(x)
        x = self.relu4(self.fc1(x))
        return self.fc2(x)


# Convenient name for future training/export scripts.  The explicit
# GestureCNN6 name makes accidental loading of the old four-class model clear.
GestureCNN = GestureCNN6


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


def assert_six_class_topology(model: nn.Module) -> None:
    expected_counts = {"weights": 38984, "biases": 126, "total": 39110}
    actual_counts = model_parameter_counts(model)
    if actual_counts != expected_counts:
        raise AssertionError(
            f"Classifier topology changed: expected {expected_counts}, got {actual_counts}"
        )
    if model.fc2.in_features != 64 or model.fc2.out_features != NUM_CLASSES:
        raise AssertionError(
            f"Expected fc2 64->{NUM_CLASSES}, got "
            f"{model.fc2.in_features}->{model.fc2.out_features}"
        )
    reference = next(model.parameters(), None)
    device = reference.device if reference is not None else torch.device("cpu")
    dtype = reference.dtype if reference is not None else torch.float32
    with torch.inference_mode():
        output = model(torch.zeros(1, *INPUT_SHAPE, device=device, dtype=dtype))
    if tuple(output.shape) != (1, NUM_CLASSES):
        raise AssertionError(f"Unexpected classifier output shape: {tuple(output.shape)}")


def _load_payload(
    checkpoint: str | Path | Mapping[str, Any],
    map_location: str | torch.device = "cpu",
) -> Mapping[str, Any]:
    if isinstance(checkpoint, (str, Path)):
        payload = torch.load(
            Path(checkpoint), map_location=map_location, weights_only=False
        )
    else:
        payload = checkpoint
    if not isinstance(payload, Mapping) or "model_state_dict" not in payload:
        raise ValueError("Expected a checkpoint containing model_state_dict")
    return payload


def initialize_from_v3(
    model: GestureCNN6,
    checkpoint: str | Path | Mapping[str, Any],
    map_location: str | torch.device = "cpu",
) -> dict[str, Any]:
    """Initialize v4 without pretending that legacy mute equals one.

    conv1..conv3 and fc1 are copied exactly from v3.  fc2 rows for background,
    fist, and palm are copied to their new class IDs.  The new one/two/three
    rows retain the model constructor's normal initialization.  Callers should
    set the random seed before constructing the model when reproducibility is
    required.
    """

    payload = _load_payload(checkpoint, map_location=map_location)
    source_names = tuple(payload.get("class_names", ()))
    if source_names != LEGACY_V3_CLASS_NAMES:
        raise ValueError(
            f"Expected v3 class order {LEGACY_V3_CLASS_NAMES}, got {source_names}"
        )
    source_state = payload["model_state_dict"]
    target_state = model.state_dict()
    copied_tensors: list[str] = []

    with torch.no_grad():
        for key, target_tensor in target_state.items():
            if key.startswith("fc2."):
                continue
            if key not in source_state:
                raise KeyError(f"Missing v3 tensor: {key}")
            source_tensor = source_state[key]
            if tuple(source_tensor.shape) != tuple(target_tensor.shape):
                raise ValueError(
                    f"Shape mismatch for {key}: {tuple(source_tensor.shape)} "
                    f"vs {tuple(target_tensor.shape)}"
                )
            target_tensor.copy_(source_tensor)
            copied_tensors.append(key)

        source_weight = source_state["fc2.weight"]
        source_bias = source_state["fc2.bias"]
        if tuple(source_weight.shape) != (4, 64) or tuple(source_bias.shape) != (4,):
            raise ValueError("Legacy fc2 must have shapes (4,64) and (4,)")

        copied_rows: list[dict[str, Any]] = []
        for source_name, target_name in LEGACY_TO_V4_CLASS.items():
            source_id = source_names.index(source_name)
            target_id = CLASS_TO_ID[target_name]
            model.fc2.weight[target_id].copy_(source_weight[source_id])
            model.fc2.bias[target_id].copy_(source_bias[source_id])
            copied_rows.append(
                {
                    "source_class": source_name,
                    "source_id": source_id,
                    "target_class": target_name,
                    "target_id": target_id,
                }
            )

    return {
        "source_class_names": list(source_names),
        "target_class_names": list(CLASS_NAMES),
        "copied_backbone_tensors": copied_tensors,
        "copied_fc2_rows": copied_rows,
        "new_fc2_rows": ["one", "two", "three"],
        "discarded_source_rows": ["mute"],
    }
