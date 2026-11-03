"""PS-side Phase 2-L1 preprocessing and raw-map decoding primitives.

The v12 raw-output scales and confidence threshold can be loaded from the
official quantization manifest.  Camera preprocessing remains explicit; the
classifier ROI geometry and temporal defaults are frozen by the L1 PS contract.
"""

from __future__ import annotations

import json
import math
from collections import Counter, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Deque, Mapping, Optional, Sequence, Tuple, Union

import numpy as np


LOCATOR_CHANNELS = 5
LOCATOR_GRID = 16
LOCATOR_INPUT_SIZE = 128
LOCATOR_OUTPUT_WORDS = LOCATOR_CHANNELS * LOCATOR_GRID * LOCATOR_GRID
LOCATOR_OUTPUT_BYTES = LOCATOR_OUTPUT_WORDS * 4
ROI_CONTRACT_VERSION = "phase2_l1_roi_v1_18pct_square_shift_pyround"
ROI_MARGIN_EACH_SIDE = 0.18


@dataclass(frozen=True)
class LetterboxSpec:
    target_width: int
    target_height: int
    pad_value: int
    interpolation: str
    resize_rounding: str
    odd_padding: str

    def __post_init__(self) -> None:
        if self.target_width <= 0 or self.target_height <= 0:
            raise ValueError("letterbox target dimensions must be positive")
        if not 0 <= self.pad_value <= 255:
            raise ValueError("pad_value must be uint8")
        if self.interpolation not in {"nearest", "linear", "area"}:
            raise ValueError("interpolation must be nearest, linear or area")
        if self.resize_rounding not in {"floor", "half_up"}:
            raise ValueError("resize_rounding must be floor or half_up")
        if self.odd_padding not in {"top_left_floor", "top_left_ceil"}:
            raise ValueError("odd_padding must be top_left_floor or top_left_ceil")


@dataclass(frozen=True)
class LetterboxTransform:
    source_width: int
    source_height: int
    target_width: int
    target_height: int
    resized_width: int
    resized_height: int
    pad_left: int
    pad_top: int
    pad_right: int
    pad_bottom: int

    @property
    def scale_x(self) -> float:
        return self.resized_width / self.source_width

    @property
    def scale_y(self) -> float:
        return self.resized_height / self.source_height


@dataclass(frozen=True)
class RawDecodeSpec:
    accumulator_scales: Tuple[float, float, float, float, float]
    confidence_threshold_i32: int
    clamp_to_locator: bool

    def __post_init__(self) -> None:
        if len(self.accumulator_scales) != LOCATOR_CHANNELS:
            raise ValueError("exactly five accumulator scales are required")
        if not all(math.isfinite(value) and value > 0.0 for value in self.accumulator_scales):
            raise ValueError("all accumulator scales must be finite and positive")
        if not -(1 << 31) <= self.confidence_threshold_i32 < (1 << 31):
            raise ValueError("confidence threshold must fit signed int32")


@dataclass(frozen=True)
class TemporalFilterSpec:
    bbox_ema_alpha: float = 0.30
    miss_hold_frames: int = 3
    class_vote_window: int = 5
    class_switch_frames: int = 2
    gesture_confirm_frames: int = 2
    background_confirm_frames: int = 3
    none_confirm_frames: int = 3
    class_count: int = 4

    def __post_init__(self) -> None:
        if not math.isfinite(self.bbox_ema_alpha) or not 0.0 < self.bbox_ema_alpha <= 1.0:
            raise ValueError("bbox_ema_alpha must be in (0, 1]")
        if self.miss_hold_frames < 0:
            raise ValueError("miss_hold_frames must be non-negative")
        if self.class_vote_window <= 0:
            raise ValueError("class_vote_window must be positive")
        if self.class_switch_frames <= 0:
            raise ValueError("class_switch_frames must be positive")
        if self.gesture_confirm_frames <= 0:
            raise ValueError("gesture_confirm_frames must be positive")
        if self.background_confirm_frames <= 0:
            raise ValueError("background_confirm_frames must be positive")
        if self.none_confirm_frames <= 0:
            raise ValueError("none_confirm_frames must be positive")
        if self.class_count <= 0:
            raise ValueError("class_count must be positive")


@dataclass(frozen=True)
class TemporalBBoxState:
    bbox_xyxy: Optional[Tuple[float, float, float, float]]
    held: bool
    miss_count: int


class BboxEmaHold:
    """EMA-filter observed float xyxy boxes and bridge short detector misses."""

    def __init__(self, spec: TemporalFilterSpec):
        self.spec = spec
        self._bbox = None
        self._miss_count = 0

    def reset(self) -> None:
        self._bbox = None
        self._miss_count = 0

    def update(self, observed_bbox_xyxy) -> TemporalBBoxState:
        if observed_bbox_xyxy is not None:
            if len(observed_bbox_xyxy) != 4:
                raise ValueError("bbox must contain x0, y0, x1, y1")
            observed = tuple(float(value) for value in observed_bbox_xyxy)
            if not all(math.isfinite(value) for value in observed):
                raise ValueError("bbox coordinates must be finite")
            if observed[2] <= observed[0] or observed[3] <= observed[1]:
                raise ValueError("bbox must have positive width and height")
            if self._bbox is None:
                self._bbox = observed
            else:
                alpha = self.spec.bbox_ema_alpha
                self._bbox = tuple(
                    alpha * new_value + (1.0 - alpha) * old_value
                    for old_value, new_value in zip(self._bbox, observed)
                )
            self._miss_count = 0
            return TemporalBBoxState(self._bbox, False, 0)

        self._miss_count += 1
        if self._bbox is not None and self._miss_count <= self.spec.miss_hold_frames:
            return TemporalBBoxState(self._bbox, True, self._miss_count)
        self._bbox = None
        return TemporalBBoxState(None, False, self._miss_count)


@dataclass(frozen=True)
class TemporalClassState:
    voted_class: int
    output_class: Optional[int]
    pending_class: Optional[int]
    pending_count: int


class ClassVoteSwitch:
    """Five-frame majority voting with confirmed output-class transitions."""

    def __init__(self, spec: TemporalFilterSpec):
        self.spec = spec
        self._window: Deque[int] = deque(maxlen=spec.class_vote_window)
        self._output_class = None
        self._pending_class = None
        self._pending_count = 0

    @property
    def output_class(self) -> Optional[int]:
        return self._output_class

    def reset(self) -> None:
        self._window.clear()
        self._output_class = None
        self._pending_class = None
        self._pending_count = 0

    def update(self, raw_class: int) -> TemporalClassState:
        raw_class = int(raw_class)
        if raw_class not in range(self.spec.class_count):
            raise ValueError("raw_class is outside the configured class range")
        self._window.append(raw_class)
        counts = Counter(self._window)
        maximum = max(counts.values())
        candidates = {class_id for class_id, count in counts.items() if count == maximum}
        if self._output_class in candidates:
            voted_class = self._output_class
        else:
            voted_class = next(class_id for class_id in reversed(self._window) if class_id in candidates)

        if voted_class == self._output_class:
            self._pending_class = None
            self._pending_count = 0
        else:
            if voted_class == self._pending_class:
                self._pending_count += 1
            else:
                self._pending_class = voted_class
                self._pending_count = 1
            if self._pending_count >= self.spec.class_switch_frames:
                self._output_class = voted_class
                self._pending_class = None
                self._pending_count = 0

        return TemporalClassState(
            voted_class=voted_class,
            output_class=self._output_class,
            pending_class=self._pending_class,
            pending_count=self._pending_count,
        )


@dataclass(frozen=True)
class TemporalClassConfirmState:
    candidate_class: Optional[int]
    output_class: Optional[int]
    pending_class: Optional[int]
    pending_count: int
    required_count: int


class ClassConfirmSwitch:
    """Consecutive-result hysteresis with asymmetric gesture/background/none gates."""

    def __init__(self, spec: TemporalFilterSpec):
        self.spec = spec
        self._output_class = None
        self._pending_class = None
        self._pending_count = 0

    @property
    def output_class(self) -> Optional[int]:
        return self._output_class

    def reset(self) -> None:
        self._output_class = None
        self._pending_class = None
        self._pending_count = 0

    def _required_count(self, candidate_class: Optional[int]) -> int:
        if candidate_class is None:
            return self.spec.none_confirm_frames
        if candidate_class == 0:
            return self.spec.background_confirm_frames
        return self.spec.gesture_confirm_frames

    def update(self, candidate_class: Optional[int]) -> TemporalClassConfirmState:
        if candidate_class is not None:
            candidate_class = int(candidate_class)
            if candidate_class not in range(self.spec.class_count):
                raise ValueError("candidate_class is outside the configured class range")
        required_count = self._required_count(candidate_class)

        if candidate_class == self._output_class:
            self._pending_class = None
            self._pending_count = 0
        else:
            if candidate_class == self._pending_class:
                self._pending_count += 1
            else:
                self._pending_class = candidate_class
                self._pending_count = 1
            if self._pending_count >= required_count:
                self._output_class = candidate_class
                self._pending_class = None
                self._pending_count = 0

        return TemporalClassConfirmState(
            candidate_class=candidate_class,
            output_class=self._output_class,
            pending_class=self._pending_class,
            pending_count=self._pending_count,
            required_count=required_count,
        )


def raw_decode_spec_from_manifest(
    manifest_or_path, *, clamp_to_locator: bool
) -> RawDecodeSpec:
    """Build the signed CHW decoder contract from the frozen v12 manifest."""

    if isinstance(manifest_or_path, Mapping):
        manifest = dict(manifest_or_path)
    else:
        manifest = json.loads(Path(manifest_or_path).read_text(encoding="utf-8"))
    output = manifest.get("conv5_output", {})
    threshold = manifest.get("confidence_threshold", {})
    if output.get("shape") != [5, 16, 16]:
        raise ValueError("manifest Conv5 shape must be [5, 16, 16]")
    if output.get("layout") != "CHW row-major, offset=((channel*16+y)*16+x)":
        raise ValueError("manifest Conv5 layout mismatch")
    if output.get("dtype") != "signed int32 little-endian":
        raise ValueError("manifest Conv5 dtype mismatch")
    if output.get("channel_order") != ["confidence", "dx", "dy", "width", "height"]:
        raise ValueError("manifest Conv5 channel order mismatch")
    scales = tuple(float(value) for value in output.get("accumulator_scale_per_channel", ()))
    raw_threshold = threshold.get("integer_raw_int32")
    if threshold.get("integer_comparison") != (
        "detected iff top1_confidence_raw_int32 >= integer_raw_int32"
    ):
        raise ValueError("manifest confidence comparison mismatch")
    return RawDecodeSpec(
        accumulator_scales=scales,
        confidence_threshold_i32=int(raw_threshold),
        clamp_to_locator=clamp_to_locator,
    )


@dataclass(frozen=True)
class Top1Detection:
    cell_x: int
    cell_y: int
    confidence_i32: int
    confidence_real: float
    dx: float
    dy: float
    width_normalized: float
    height_normalized: float
    passed_threshold: bool
    valid_geometry: bool
    bbox_locator_xyxy: Optional[Tuple[float, float, float, float]]


def _rounded_size(value: float, mode: str) -> int:
    if mode == "floor":
        return int(math.floor(value))
    if mode == "half_up":
        return int(math.floor(value + 0.5))
    raise ValueError("unsupported resize rounding mode")


def compute_letterbox_transform(
    source_width: int, source_height: int, spec: LetterboxSpec
) -> LetterboxTransform:
    if source_width <= 0 or source_height <= 0:
        raise ValueError("source dimensions must be positive")
    scale = min(spec.target_width / source_width, spec.target_height / source_height)
    resized_width = max(1, min(spec.target_width, _rounded_size(source_width * scale, spec.resize_rounding)))
    resized_height = max(1, min(spec.target_height, _rounded_size(source_height * scale, spec.resize_rounding)))
    horizontal = spec.target_width - resized_width
    vertical = spec.target_height - resized_height
    if spec.odd_padding == "top_left_floor":
        pad_left = horizontal // 2
        pad_top = vertical // 2
    else:
        pad_left = (horizontal + 1) // 2
        pad_top = (vertical + 1) // 2
    return LetterboxTransform(
        source_width=source_width,
        source_height=source_height,
        target_width=spec.target_width,
        target_height=spec.target_height,
        resized_width=resized_width,
        resized_height=resized_height,
        pad_left=pad_left,
        pad_top=pad_top,
        pad_right=horizontal - pad_left,
        pad_bottom=vertical - pad_top,
    )


def _require_cv2():
    try:
        import cv2  # type: ignore
    except ImportError as exc:
        raise RuntimeError("OpenCV is required for image preprocessing") from exc
    return cv2


def bgr_to_gray_u8(frame_bgr: np.ndarray, *, method: str) -> np.ndarray:
    if method != "opencv_bgr2gray":
        raise ValueError("method must be explicitly set to opencv_bgr2gray")
    frame = np.asarray(frame_bgr)
    if frame.dtype != np.uint8 or frame.ndim != 3 or frame.shape[2] != 3:
        raise ValueError("frame_bgr must be HxWx3 uint8")
    cv2 = _require_cv2()
    return np.ascontiguousarray(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), dtype=np.uint8)


def letterbox_gray_u8(
    gray_u8: np.ndarray, spec: LetterboxSpec
) -> Tuple[np.ndarray, LetterboxTransform]:
    gray = np.asarray(gray_u8)
    if gray.dtype != np.uint8 or gray.ndim != 2:
        raise ValueError("gray_u8 must be HxW uint8")
    transform = compute_letterbox_transform(gray.shape[1], gray.shape[0], spec)
    cv2 = _require_cv2()
    interpolation = {
        "nearest": cv2.INTER_NEAREST,
        "linear": cv2.INTER_LINEAR,
        "area": cv2.INTER_AREA,
    }[spec.interpolation]
    resized = cv2.resize(
        gray,
        (transform.resized_width, transform.resized_height),
        interpolation=interpolation,
    )
    output = np.full(
        (spec.target_height, spec.target_width), spec.pad_value, dtype=np.uint8
    )
    y0, x0 = transform.pad_top, transform.pad_left
    output[y0 : y0 + transform.resized_height, x0 : x0 + transform.resized_width] = resized
    return np.ascontiguousarray(output), transform


def parse_raw_output_i32(
    raw: Union[bytes, bytearray, memoryview, np.ndarray, Sequence[int]]
) -> np.ndarray:
    if isinstance(raw, (bytes, bytearray, memoryview)):
        if len(raw) != LOCATOR_OUTPUT_BYTES:
            raise ValueError(f"raw output must contain exactly {LOCATOR_OUTPUT_BYTES} bytes")
        words = np.frombuffer(raw, dtype="<i4").copy()
    else:
        array = np.asarray(raw)
        if array.size != LOCATOR_OUTPUT_WORDS:
            raise ValueError(f"raw output must contain exactly {LOCATOR_OUTPUT_WORDS} words")
        if array.dtype == np.uint32:
            words = np.ascontiguousarray(array.reshape(-1)).view(np.int32)
        elif array.dtype == np.int32:
            words = np.ascontiguousarray(array.reshape(-1))
        else:
            values = np.asarray(array, dtype=np.int64).reshape(-1)
            if np.any(values < -(1 << 31)) or np.any(values >= (1 << 31)):
                raise ValueError("raw output values must fit signed int32")
            words = values.astype(np.int32)
    return words.reshape(LOCATOR_CHANNELS, LOCATOR_GRID, LOCATOR_GRID)


def decode_top1_raw_values(
    cell_x: int,
    cell_y: int,
    raw_values_i32: Sequence[int],
    spec: RawDecodeSpec,
) -> Top1Detection:
    """Decode one PL-reduced confidence/dx/dy/width/height tuple."""

    cell_x = int(cell_x)
    cell_y = int(cell_y)
    if cell_x not in range(LOCATOR_GRID) or cell_y not in range(LOCATOR_GRID):
        raise ValueError("Top-1 cell is outside the 16x16 grid")
    values = tuple(int(value) for value in raw_values_i32)
    if len(values) != LOCATOR_CHANNELS:
        raise ValueError("Top-1 summary must contain exactly five raw values")
    if any(value < -(1 << 31) or value >= (1 << 31) for value in values):
        raise ValueError("Top-1 raw values must fit signed int32")
    confidence_i32, dx_i32, dy_i32, width_i32, height_i32 = values
    scales = spec.accumulator_scales
    dx = dx_i32 * scales[1]
    dy = dy_i32 * scales[2]
    width_normalized = width_i32 * scales[3]
    height_normalized = height_i32 * scales[4]
    valid_geometry = (
        math.isfinite(dx)
        and math.isfinite(dy)
        and math.isfinite(width_normalized)
        and math.isfinite(height_normalized)
        and width_normalized > 0.0
        and height_normalized > 0.0
    )
    bbox = None
    if valid_geometry:
        stride = LOCATOR_INPUT_SIZE / LOCATOR_GRID
        center_x = stride * (cell_x + 0.5 + dx)
        center_y = stride * (cell_y + 0.5 + dy)
        width = LOCATOR_INPUT_SIZE * width_normalized
        height = LOCATOR_INPUT_SIZE * height_normalized
        x0, y0 = center_x - width / 2.0, center_y - height / 2.0
        x1, y1 = center_x + width / 2.0, center_y + height / 2.0
        if spec.clamp_to_locator:
            x0 = min(max(x0, 0.0), float(LOCATOR_INPUT_SIZE))
            y0 = min(max(y0, 0.0), float(LOCATOR_INPUT_SIZE))
            x1 = min(max(x1, 0.0), float(LOCATOR_INPUT_SIZE))
            y1 = min(max(y1, 0.0), float(LOCATOR_INPUT_SIZE))
            valid_geometry = x1 > x0 and y1 > y0
        if valid_geometry:
            bbox = (x0, y0, x1, y1)
    return Top1Detection(
        cell_x=cell_x,
        cell_y=cell_y,
        confidence_i32=confidence_i32,
        confidence_real=confidence_i32 * scales[0],
        dx=dx,
        dy=dy,
        width_normalized=width_normalized,
        height_normalized=height_normalized,
        passed_threshold=confidence_i32 >= spec.confidence_threshold_i32,
        valid_geometry=valid_geometry,
        bbox_locator_xyxy=bbox,
    )


def decode_top1_raw_map(raw_map_i32: np.ndarray, spec: RawDecodeSpec) -> Top1Detection:
    raw_map = parse_raw_output_i32(raw_map_i32)
    flat_index = int(np.argmax(raw_map[0]))
    cell_y, cell_x = divmod(flat_index, LOCATOR_GRID)
    raw_values = tuple(
        int(raw_map[channel, cell_y, cell_x]) for channel in range(LOCATOR_CHANNELS)
    )
    return decode_top1_raw_values(cell_x, cell_y, raw_values, spec)

def locator_bbox_to_source(
    bbox_locator_xyxy: Sequence[float],
    transform: LetterboxTransform,
    *,
    clip_to_source: bool,
) -> Tuple[float, float, float, float]:
    if len(bbox_locator_xyxy) != 4:
        raise ValueError("bbox must contain x0, y0, x1, y1")
    x0, y0, x1, y1 = (float(value) for value in bbox_locator_xyxy)
    source_x0 = (x0 - transform.pad_left) / transform.scale_x
    source_y0 = (y0 - transform.pad_top) / transform.scale_y
    source_x1 = (x1 - transform.pad_left) / transform.scale_x
    source_y1 = (y1 - transform.pad_top) / transform.scale_y
    if clip_to_source:
        source_x0 = min(max(source_x0, 0.0), float(transform.source_width))
        source_y0 = min(max(source_y0, 0.0), float(transform.source_height))
        source_x1 = min(max(source_x1, 0.0), float(transform.source_width))
        source_y1 = min(max(source_y1, 0.0), float(transform.source_height))
    return source_x0, source_y0, source_x1, source_y1


def center_square_box(
    image_width: int, image_height: int, *, scale: float
) -> Tuple[int, int, int, int]:
    if image_width <= 0 or image_height <= 0:
        raise ValueError("image dimensions must be positive")
    if not math.isfinite(scale) or not 0.0 < scale <= 1.0:
        raise ValueError("scale must be in (0, 1]")
    short_side = min(image_width, image_height)
    side = max(1, min(short_side, int(math.floor(short_side * scale + 0.5))))
    left = image_width // 2 - side // 2
    top = image_height // 2 - side // 2
    return left, top, left + side, top + side


def prepare_source_crop_box(
    bbox_source_xyxy: Sequence[float],
    image_width: int,
    image_height: int,
    *,
    expansion_ratio: float,
    make_square: bool,
    clip_to_source: bool,
) -> Tuple[int, int, int, int]:
    """Convert a decoded float bbox to explicit OpenCV pixel-slice bounds.

    ``expansion_ratio`` is applied on every side.  When ``make_square`` and
    ``clip_to_source`` are true, the frozen Phase 2-L1 rule uses Python
    ``round`` for the side and origin, then shifts the complete square inside
    the source image.  It never clips individual edges into a rectangle.
    Right and bottom are exclusive slice bounds.
    """

    if len(bbox_source_xyxy) != 4:
        raise ValueError("bbox must contain x0, y0, x1, y1")
    if image_width <= 0 or image_height <= 0:
        raise ValueError("image dimensions must be positive")
    if not math.isfinite(expansion_ratio) or expansion_ratio < 0.0:
        raise ValueError("expansion_ratio must be finite and non-negative")
    x0, y0, x1, y1 = (float(value) for value in bbox_source_xyxy)
    if not all(math.isfinite(value) for value in (x0, y0, x1, y1)):
        raise ValueError("bbox coordinates must be finite")
    if x1 <= x0 or y1 <= y0:
        raise ValueError("bbox must have positive width and height")

    center_x = (x0 + x1) / 2.0
    center_y = (y0 + y1) / 2.0
    if make_square:
        side = int(round((1.0 + 2.0 * expansion_ratio) * max(x1 - x0, y1 - y0)))
        side = max(1, min(side, image_width, image_height))
        left = int(round(center_x - side / 2.0))
        top = int(round(center_y - side / 2.0))
        if clip_to_source:
            left = min(max(left, 0), image_width - side)
            top = min(max(top, 0), image_height - side)
        elif left < 0 or top < 0 or left + side > image_width or top + side > image_height:
            raise ValueError("unclipped square crop box falls outside the source frame")
        return left, top, left + side, top + side

    width = (x1 - x0) * (1.0 + 2.0 * expansion_ratio)
    height = (y1 - y0) * (1.0 + 2.0 * expansion_ratio)
    left = int(math.floor(center_x - width / 2.0))
    top = int(math.floor(center_y - height / 2.0))
    right = int(math.ceil(center_x + width / 2.0))
    bottom = int(math.ceil(center_y + height / 2.0))
    if clip_to_source:
        left = min(max(left, 0), image_width)
        top = min(max(top, 0), image_height)
        right = min(max(right, 0), image_width)
        bottom = min(max(bottom, 0), image_height)
    elif left < 0 or top < 0 or right > image_width or bottom > image_height:
        raise ValueError("unclipped crop box falls outside the source frame")
    if right <= left or bottom <= top:
        raise ValueError("bbox is empty after pixel conversion/clipping")
    return left, top, right, bottom


def classifier_center_crop_u8(
    frame_bgr: np.ndarray,
    *,
    roi_scale: float,
    output_size: int,
    grayscale_method: str,
    interpolation: str,
) -> Tuple[np.ndarray, Tuple[int, int, int, int]]:
    if output_size <= 0:
        raise ValueError("output_size must be positive")
    if interpolation not in {"nearest", "linear", "area"}:
        raise ValueError("unsupported interpolation")
    frame = np.asarray(frame_bgr)
    if frame.dtype != np.uint8 or frame.ndim != 3 or frame.shape[2] != 3:
        raise ValueError("frame_bgr must be HxWx3 uint8")
    box = center_square_box(frame.shape[1], frame.shape[0], scale=roi_scale)
    x0, y0, x1, y1 = box
    gray = bgr_to_gray_u8(frame[y0:y1, x0:x1], method=grayscale_method)
    cv2 = _require_cv2()
    mode = {"nearest": cv2.INTER_NEAREST, "linear": cv2.INTER_LINEAR, "area": cv2.INTER_AREA}[interpolation]
    resized = cv2.resize(gray, (output_size, output_size), interpolation=mode)
    return np.ascontiguousarray(resized, dtype=np.uint8), box


def classifier_bbox_crop_u8(
    frame_bgr: np.ndarray,
    bbox_source_xyxy: Sequence[float],
    *,
    expansion_ratio: float,
    make_square: bool,
    clip_to_source: bool,
    output_size: int,
    grayscale_method: str,
    interpolation: str,
) -> Tuple[np.ndarray, Tuple[int, int, int, int]]:
    """Crop a decoded bbox from the retained source frame for classification."""

    if output_size <= 0:
        raise ValueError("output_size must be positive")
    if interpolation not in {"nearest", "linear", "area"}:
        raise ValueError("unsupported interpolation")
    frame = np.asarray(frame_bgr)
    if frame.dtype != np.uint8 or frame.ndim != 3 or frame.shape[2] != 3:
        raise ValueError("frame_bgr must be HxWx3 uint8")
    box = prepare_source_crop_box(
        bbox_source_xyxy,
        frame.shape[1],
        frame.shape[0],
        expansion_ratio=expansion_ratio,
        make_square=make_square,
        clip_to_source=clip_to_source,
    )
    x0, y0, x1, y1 = box
    gray = bgr_to_gray_u8(frame[y0:y1, x0:x1], method=grayscale_method)
    cv2 = _require_cv2()
    mode = {"nearest": cv2.INTER_NEAREST, "linear": cv2.INTER_LINEAR, "area": cv2.INTER_AREA}[interpolation]
    resized = cv2.resize(gray, (output_size, output_size), interpolation=mode)
    return np.ascontiguousarray(resized, dtype=np.uint8), box
