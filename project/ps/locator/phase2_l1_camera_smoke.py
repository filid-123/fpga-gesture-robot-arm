"""Finite USB-camera smoke test for the signed Phase 2-L1 Stub overlay.

The script does not program the FPGA.  Run the low-level v4 board acceptance
first so the reset-fix bitstream, Locator Stub model and active classifier model
are resident.  This test then proves two live paths from the same camera frame:

* explicit candidate 128x128 letterbox -> Locator Stub -> bit-exact output;
* existing Phase 1 center crop -> 32x32 classifier -> CLASS_ID.

The Locator preprocessing selection is recorded as a candidate only.  It must
not be promoted to production until the algorithm team supplies frozen vectors.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import mmap
import os
import platform
import time
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

from locator_driver import (
    LOCATOR_CTRL_BASE,
    LOCATOR_CTRL_SIZE,
    LOCATOR_INPUT_BASE,
    LOCATOR_INPUT_SIZE,
    LOCATOR_OUTPUT_BASE,
    LOCATOR_OUTPUT_SIZE,
    LocatorDriver,
)
from phase2_l1_pipeline import (
    LetterboxSpec,
    bgr_to_gray_u8,
    classifier_center_crop_u8,
    letterbox_gray_u8,
)


CLASSIFIER_BASE = 0x4000_0000
CLASSIFIER_SIZE = 0x1000
REG_CTRL = 0x00
REG_STATUS = 0x04
REG_CLASS_ID = 0x08
REG_ABI = 0x0C
REG_IMG_ADDR = 0x20
REG_IMG_DATA = 0x24


class LowMMIO:
    def __init__(self, base: int, length: int):
        page = mmap.PAGESIZE
        physical_base = base & ~(page - 1)
        offset = base - physical_base
        fd = os.open("/dev/mem", os.O_RDWR | os.O_SYNC)
        try:
            self._mmap = mmap.mmap(
                fd,
                length + offset,
                mmap.MAP_SHARED,
                mmap.PROT_READ | mmap.PROT_WRITE,
                offset=physical_base,
            )
        finally:
            os.close(fd)
        self.array = np.frombuffer(
            self._mmap, dtype=np.uint32, count=length // 4, offset=offset
        )

    def read(self, offset: int) -> int:
        return int(self.array[offset // 4]) & 0xFFFF_FFFF

    def write(self, offset: int, value: int) -> None:
        self.array[offset // 4] = np.uint32(value & 0xFFFF_FFFF)


def run_classifier(cnn: LowMMIO, image_u8: np.ndarray, timeout_s: float) -> tuple[int, float]:
    pixels = np.ascontiguousarray(image_u8, dtype=np.uint8).reshape(-1)
    if pixels.size != 1024:
        raise ValueError("classifier input must contain 1024 uint8 pixels")
    cnn.write(REG_IMG_ADDR, 0)
    for pixel in pixels:
        cnn.write(REG_IMG_DATA, int(pixel))
    started = time.monotonic()
    cnn.write(REG_CTRL, 1)
    deadline = started + timeout_s
    while time.monotonic() < deadline:
        if cnn.read(REG_STATUS) & 0x4:
            elapsed_ms = (time.monotonic() - started) * 1000.0
            class_id = cnn.read(REG_CLASS_ID)
            if class_id not in (0, 1, 2, 3):
                raise AssertionError(f"classifier returned invalid class {class_id}")
            return class_id, elapsed_ms
        time.sleep(0.0005)
    raise TimeoutError("classifier inference timed out")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="/dev/video0")
    parser.add_argument("--frames", type=int, default=30)
    parser.add_argument("--infer-every", type=int, default=3)
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--result", default="camera_smoke_result.json")
    args = parser.parse_args()
    if args.frames <= 0 or args.infer_every <= 0:
        raise ValueError("frames and infer-every must be positive")

    result_path = Path(args.result)
    if result_path.exists():
        raise FileExistsError(f"refusing to overwrite {result_path}")
    if not Path(args.device).exists():
        raise FileNotFoundError(args.device)

    locator_spec = LetterboxSpec(
        target_width=128,
        target_height=128,
        pad_value=0,
        interpolation="nearest",
        resize_rounding="half_up",
        odd_padding="top_left_floor",
    )
    preprocessing_contract = {
        "status": "candidate_only_algorithm_vectors_pending",
        "gray": "opencv_bgr2gray",
        "letterbox": {
            "size": [128, 128],
            "padding_value": 0,
            "interpolation": locator_spec.interpolation,
            "resize_rounding": locator_spec.resize_rounding,
            "odd_padding": locator_spec.odd_padding,
        },
        "classifier": {
            "roi": "center_square",
            "roi_scale": 0.45,
            "size": [32, 32],
            "interpolation": "linear",
        },
    }

    cnn = LowMMIO(CLASSIFIER_BASE, CLASSIFIER_SIZE)
    if cnn.read(REG_ABI) != 0x0001_0000:
        raise RuntimeError("classifier ABI is not 1.0; run board acceptance first")
    locator = LocatorDriver(
        LowMMIO(LOCATOR_CTRL_BASE, LOCATOR_CTRL_SIZE),
        LowMMIO(LOCATOR_INPUT_BASE, LOCATOR_INPUT_SIZE),
        LowMMIO(LOCATOR_OUTPUT_BASE, LOCATOR_OUTPUT_SIZE),
    )
    locator.assert_abi()
    # Make a rerun independent of output ownership left by an interrupted test.
    # The L1 contract requires SOFT_RESET to preserve MODEL_VALID.
    locator.soft_reset()

    cap = cv2.VideoCapture(args.device, cv2.CAP_V4L2)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
    if not cap.isOpened():
        raise RuntimeError(f"cannot open camera {args.device}")

    captured = 0
    hashes = set()
    classifier_runs = []
    locator_runs = []
    first_frame = None
    first_locator_input = None
    first_classifier_input = None
    started = time.monotonic()
    try:
        for frame_index in range(args.frames):
            ok, frame = cap.read()
            if not ok or frame is None:
                raise RuntimeError(f"camera read failed at frame {frame_index}")
            if frame.dtype != np.uint8 or frame.ndim != 3 or frame.shape[2] != 3:
                raise AssertionError(f"unexpected camera frame shape/dtype: {frame.shape}/{frame.dtype}")
            captured += 1
            hashes.add(hashlib.sha256(frame.tobytes()).hexdigest())
            if first_frame is None:
                first_frame = frame.copy()

            if frame_index % args.infer_every != 0:
                continue
            gray = bgr_to_gray_u8(frame, method="opencv_bgr2gray")
            locator_input, transform = letterbox_gray_u8(gray, locator_spec)
            classifier_input, roi = classifier_center_crop_u8(
                frame,
                roi_scale=0.45,
                output_size=32,
                grayscale_method="opencv_bgr2gray",
                interpolation="linear",
            )
            if first_locator_input is None:
                first_locator_input = locator_input.copy()
                first_classifier_input = classifier_input.copy()

            loc_started = time.monotonic()
            loc_result = locator.run_stub(locator_input, frame_index, timeout_s=1.0)
            loc_elapsed_ms = (time.monotonic() - loc_started) * 1000.0
            locator.release_output(1 << loc_result.buffer_id)
            locator_runs.append(
                {
                    "frame_id": frame_index,
                    "elapsed_ms": round(loc_elapsed_ms, 3),
                    "output_buffer": loc_result.buffer_id,
                    "output_sha256": hashlib.sha256(
                        loc_result.raw_map_i32.astype("<i4", copy=False).tobytes()
                    ).hexdigest(),
                    "letterbox": {
                        "source": [transform.source_width, transform.source_height],
                        "resized": [transform.resized_width, transform.resized_height],
                        "padding_ltrb": [
                            transform.pad_left,
                            transform.pad_top,
                            transform.pad_right,
                            transform.pad_bottom,
                        ],
                    },
                }
            )
            class_id, class_elapsed_ms = run_classifier(cnn, classifier_input, 1.0)
            classifier_runs.append(
                {
                    "frame_id": frame_index,
                    "class_id": class_id,
                    "elapsed_ms": round(class_elapsed_ms, 3),
                    "roi_xyxy": list(roi),
                }
            )
    finally:
        cap.release()

    if captured != args.frames:
        raise AssertionError(f"captured {captured}/{args.frames} frames")
    if len(hashes) < 2:
        raise AssertionError("camera frames did not change")
    if not locator_runs or len(locator_runs) != len(classifier_runs):
        raise AssertionError("live inference runs were not completed")

    image_files = {
        "frame": "camera_smoke_first_frame.png",
        "locator_input": "camera_smoke_locator_128.png",
        "classifier_input": "camera_smoke_classifier_32.png",
    }
    for path in image_files.values():
        if Path(path).exists():
            raise FileExistsError(f"refusing to overwrite {path}")
    if not cv2.imwrite(image_files["frame"], first_frame):
        raise RuntimeError("failed to write first camera frame")
    if not cv2.imwrite(image_files["locator_input"], first_locator_input):
        raise RuntimeError("failed to write locator input preview")
    if not cv2.imwrite(image_files["classifier_input"], first_classifier_input):
        raise RuntimeError("failed to write classifier input preview")

    result = {
        "status": "PASS",
        "finished_utc": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(),
        "device": args.device,
        "requested_resolution": [args.width, args.height],
        "actual_resolution": [int(first_frame.shape[1]), int(first_frame.shape[0])],
        "frames": captured,
        "unique_frame_hashes": len(hashes),
        "elapsed_s": round(time.monotonic() - started, 3),
        "preprocessing_contract": preprocessing_contract,
        "locator_stub_runs": locator_runs,
        "classifier_runs": classifier_runs,
        "image_files": image_files,
    }
    result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
