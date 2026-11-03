"""OV5640 -> PL letterbox -> Locator -> selectable PL ROI -> classifier."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from pynq import Overlay

from camera_l2_driver import CameraL2Driver
from phase2_l2_ov5640_bringup import require_autostart_stopped


ROOT = Path(__file__).resolve().parent
LOCATOR_DIR = ROOT.parent / "locator"
sys.path.insert(0, str(LOCATOR_DIR))

CLASS_NAMES = ("background", "fist", "mute", "palm")
CLASS_ABI = 0x0C
CLASS_STATUS = 0x04
CLASS_ID = 0x08
CLASS_CONTROL = 0x00
CLASS_WEIGHT_ADDR = 0x10
CLASS_WEIGHT_DATA = 0x14
CLASS_DESC_ADDR = 0x28
CLASS_DESC_DATA = 0x2C
ROI_MODE_SAME_FRAME = "same-frame-128"
ROI_MODE_NEXT_SOF = "next-sof-vga"


def read_mem_words(path: Path):
    return [
        int(line.strip(), 16)
        for line in path.read_text(encoding="ascii").splitlines()
        if line.strip()
    ]


def load_classifier_model(cnn, package_dir: Path) -> None:
    weights = read_mem_words(package_dir / "weights_all.mem")
    descriptors = read_mem_words(package_dir / "layer_descriptors.mem")
    if len(weights) != 9838 or len(descriptors) != 64:
        raise RuntimeError("classifier-v3 package size mismatch")
    cnn.write(CLASS_WEIGHT_ADDR, 0)
    for word in weights:
        cnn.write(CLASS_WEIGHT_DATA, word)
    cnn.write(CLASS_DESC_ADDR, 0)
    for word in descriptors:
        cnn.write(CLASS_DESC_DATA, word)


def run_preloaded_classifier(cnn, *, timeout_s: float) -> int:
    """Start the classifier without rewriting its PL-filled input memory."""

    cnn.write(CLASS_CONTROL, 1)
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if cnn.read(CLASS_STATUS) & 0x4:
            class_id = int(cnn.read(CLASS_ID))
            if class_id not in range(len(CLASS_NAMES)):
                raise RuntimeError(f"classifier returned invalid class {class_id}")
            return class_id
        time.sleep(0.0005)
    raise TimeoutError("classifier inference timed out")


def enforce_streaming_minimum(
    box, *, minimum_side: int = 32, frame_width: int = 640, frame_height: int = 480
):
    x0, y0, x1, y1 = box
    side = x1 - x0
    if side >= minimum_side:
        return box
    center_x = (x0 + x1) / 2.0
    center_y = (y0 + y1) / 2.0
    left = int(round(center_x - minimum_side / 2.0))
    top = int(round(center_y - minimum_side / 2.0))
    left = min(max(left, 0), frame_width - minimum_side)
    top = min(max(top, 0), frame_height - minimum_side)
    return left, top, left + minimum_side, top + minimum_side


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the complete Phase 2-L2 PL camera/Locator/ROI/classifier loop"
    )
    parser.add_argument("--bit", type=Path, default=ROOT / "phase2_l2_ov5640.bit")
    parser.add_argument("--hwh", type=Path, default=ROOT / "phase2_l2_ov5640.hwh")
    parser.add_argument(
        "--locator-package", type=Path, default=LOCATOR_DIR / "locator_v16"
    )
    parser.add_argument(
        "--classifier-package", type=Path, default=LOCATOR_DIR / "classifier_v3"
    )
    parser.add_argument("--iterations", type=int, default=10)
    parser.add_argument("--timeout", type=float, default=3.0)
    parser.add_argument("--min-classified", type=int, default=1)
    parser.add_argument(
        "--roi-mode",
        choices=(ROI_MODE_SAME_FRAME, ROI_MODE_NEXT_SOF),
        default=ROI_MODE_SAME_FRAME,
    )
    args = parser.parse_args()
    if args.iterations <= 0:
        raise ValueError("--iterations must be positive")
    if args.min_classified < 0:
        raise ValueError("--min-classified must be non-negative")

    require_autostart_stopped()
    if not args.bit.is_file() or not args.hwh.is_file():
        raise FileNotFoundError("paired Phase 2-L2 .bit/.hwh files are required")
    if args.bit.stem != args.hwh.stem:
        raise ValueError("PYNQ requires .bit and .hwh to use the same basename")

    from locator_driver import LocatorDriver
    import phase2_l1_pipeline as pipeline

    overlay = Overlay(str(args.bit), download=True)
    cnn = overlay.gesture_top_0
    if int(cnn.read(CLASS_ABI)) != 0x0001_0000:
        raise RuntimeError("classifier ABI mismatch")

    camera = CameraL2Driver.from_pynq()
    locator = LocatorDriver.from_pynq()
    held_camera_buffer = None
    held_locator_mask = 0
    try:
        camera.power_on()
        chip_id = camera.assert_chip_id()
        camera.configure_vga_yuyv()
        camera.prepare_capture(camera_source=True)

        locator.assert_abi()
        locator.soft_reset()
        manifest = locator.load_v16_package(args.locator_package, timeout_s=2.0)
        decode_spec = pipeline.raw_decode_spec_from_manifest(
            manifest, clamp_to_locator=True
        )
        load_classifier_model(cnn, args.classifier_package)

        transform = pipeline.LetterboxTransform(
            source_width=640,
            source_height=480,
            target_width=128,
            target_height=128,
            resized_width=128,
            resized_height=96,
            pad_left=0,
            pad_top=16,
            pad_right=0,
            pad_bottom=16,
        )
        temporal_spec = pipeline.TemporalFilterSpec(class_count=len(CLASS_NAMES))
        bbox_filter = pipeline.BboxEmaHold(temporal_spec)
        class_filter = pipeline.ClassConfirmSwitch(temporal_spec)

        print(f"PASS: OV5640 chip ID = 0x{chip_id:04X}; models loaded", flush=True)
        completed = 0
        for index in range(args.iterations):
            buffer_id, frame_id = camera.wait_frame(timeout_s=args.timeout)
            held_camera_buffer = buffer_id
            locator.submit_preloaded(buffer_id, frame_id)
            top1_result = locator.wait_top1(frame_id=frame_id, timeout_s=args.timeout)
            held_locator_mask = 1 << top1_result.buffer_id
            detection = pipeline.decode_top1_raw_values(
                top1_result.cell_x,
                top1_result.cell_y,
                top1_result.raw_values_i32,
                decode_spec,
            )
            locator.release_output(held_locator_mask)
            held_locator_mask = 0
            roi_bbox = None
            if detection.passed_threshold and detection.bbox_locator_xyxy is not None:
                roi_bbox = (
                    detection.bbox_locator_xyxy
                    if args.roi_mode == ROI_MODE_SAME_FRAME
                    else pipeline.locator_bbox_to_source(
                        detection.bbox_locator_xyxy, transform, clip_to_source=True
                    )
                )
            stable = bbox_filter.update(roi_bbox)
            if roi_bbox is None:
                camera.release_buffer(buffer_id)
                held_camera_buffer = None
                class_state = class_filter.update(None)
                output_name = (
                    "none"
                    if class_state.output_class is None
                    else CLASS_NAMES[class_state.output_class]
                )
                print(
                    f"NO DETECTION: iter={index} frame={frame_id} "
                    f"confidence_i32={detection.confidence_i32} output={output_name}",
                    flush=True,
                )
                continue

            frame_width, frame_height = (
                (128, 128)
                if args.roi_mode == ROI_MODE_SAME_FRAME
                else (640, 480)
            )
            crop_box = pipeline.prepare_source_crop_box(
                stable.bbox_xyxy,
                frame_width,
                frame_height,
                expansion_ratio=pipeline.ROI_MARGIN_EACH_SIDE,
                make_square=True,
                clip_to_source=True,
            )
            if args.roi_mode == ROI_MODE_SAME_FRAME:
                camera.arm_same_frame_roi(
                    buffer_id, crop_box, descriptor_tag=frame_id
                )
                roi_result = camera.wait_roi(
                    descriptor_tag=frame_id,
                    source_frame_id=frame_id,
                    timeout_s=args.timeout,
                )
                camera.release_buffer(buffer_id)
                held_camera_buffer = None
            else:
                crop_box = enforce_streaming_minimum(crop_box)
                camera.release_buffer(buffer_id)
                held_camera_buffer = None
                camera.arm_roi(crop_box, descriptor_tag=frame_id)
                roi_result = camera.wait_roi(
                    descriptor_tag=frame_id, timeout_s=args.timeout
                )
            raw_class = run_preloaded_classifier(cnn, timeout_s=args.timeout)
            class_state = class_filter.update(raw_class)
            output_name = (
                "pending"
                if class_state.output_class is None
                else CLASS_NAMES[class_state.output_class]
            )
            completed += 1
            print(
                "PASS: iter={} roi_mode={} locator_frame={} roi_source_frame={} "
                "confidence_i32={} crop={} raw_class={} output={}".format(
                    index,
                    args.roi_mode,
                    frame_id,
                    roi_result.source_frame_id,
                    detection.confidence_i32,
                    crop_box,
                    CLASS_NAMES[raw_class],
                    output_name,
                ),
                flush=True,
            )
            camera.release_all_buffers()

        if completed < args.min_classified:
            raise RuntimeError(
                f"Only {completed} ROI/classifier runs completed; "
                f"required at least {args.min_classified}"
            )
        print(
            f"PASS: Phase 2-L2 closed loop completed {completed}/{args.iterations} "
            "ROI/classifier runs",
            flush=True,
        )
        return 0
    finally:
        try:
            if held_locator_mask:
                locator.release_output(held_locator_mask)
        finally:
            try:
                if held_camera_buffer is not None:
                    camera.release_buffer(held_camera_buffer)
            finally:
                camera.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
