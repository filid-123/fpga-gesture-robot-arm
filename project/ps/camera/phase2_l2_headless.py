"""Headless OV5640 -> 8-lane Locator -> PL ROI -> classifier demo."""

from __future__ import annotations

import argparse
import json
import signal
import sys
import time
from pathlib import Path


GPIO_BASE = 0x4120_0000
GPIO_SIZE = 0x0001_0000
CAMERA_INIT_ATTEMPTS = 3
CAMERA_INIT_RETRY_DELAY_S = 1.0


def initialize_camera_with_retry(
    camera,
    *,
    attempts: int = CAMERA_INIT_ATTEMPTS,
    retry_delay_s: float = CAMERA_INIT_RETRY_DELAY_S,
    sleeper=time.sleep,
    on_retry=None,
) -> int:
    """Initialize OV5640, recovering bounded transient SCCB failures in-process."""

    if attempts < 1 or retry_delay_s < 0.0:
        raise ValueError("attempts must be positive and retry_delay_s non-negative")
    for attempt in range(1, attempts + 1):
        try:
            camera.power_on()
            chip_id = camera.assert_chip_id()
            camera.configure_vga_yuyv()
            return chip_id
        except OSError as exc:
            camera.shutdown()
            if attempt == attempts:
                raise
            message = (
                f"WARNING: OV5640 SCCB initialization attempt {attempt}/{attempts} "
                f"failed: {exc}; retrying after {retry_delay_s:.1f}s"
            )
            if on_retry is None:
                print(message, flush=True)
            else:
                on_retry(message)
            sleeper(retry_delay_s)

    raise AssertionError("unreachable")


def parse_args():
    parser = argparse.ArgumentParser(description="Run the Phase 2-L2 demo without Jupyter")
    parser.add_argument("--deploy-dir", required=True)
    parser.add_argument("--duration", type=float, default=0.0)
    parser.add_argument("--timeout", type=float, default=3.0)
    parser.add_argument("--status-interval", type=float, default=2.0)
    parser.add_argument("--no-led", action="store_true")
    parser.add_argument(
        "--roi-mode",
        choices=("same-frame-128", "next-sof-vga"),
        default="same-frame-128",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.duration < 0.0 or args.timeout <= 0.0 or args.status_interval <= 0.0:
        raise ValueError("duration must be non-negative; timeouts must be positive")

    deploy_dir = Path(args.deploy_dir).resolve()
    camera_dir = deploy_dir / "camera"
    locator_dir = deploy_dir / "locator"
    bitstream = camera_dir / "phase2_l2_ov5640.bit"
    hwh = camera_dir / "phase2_l2_ov5640.hwh"
    required = (
        bitstream,
        hwh,
        camera_dir / "camera_l2_driver.py",
        camera_dir / "phase2_l2_closed_loop.py",
        locator_dir / "locator_driver.py",
        locator_dir / "phase2_l1_pipeline.py",
        locator_dir / "locator_v16" / "locator_model_blob.mem",
        locator_dir / "classifier_v3" / "weights_all.mem",
        locator_dir / "classifier_v3" / "layer_descriptors.mem",
    )
    for path in required:
        if not path.is_file():
            raise FileNotFoundError(path)
    sys.path[:0] = [str(camera_dir), str(locator_dir)]

    from pynq import Clocks, MMIO, Overlay
    from camera_l2_driver import (
        DROP_COUNT as CAMERA_DROP_COUNT,
        FORMAT_ERROR_COUNT,
        CameraL2Driver,
    )
    from locator_driver import DROP_COUNT, STALL_COUNT, LocatorDriver, validate_hwh_clock_contract
    import phase2_l1_pipeline as pipeline
    from phase2_l2_closed_loop import (
        CLASS_NAMES,
        ROI_MODE_NEXT_SOF,
        ROI_MODE_SAME_FRAME,
        enforce_streaming_minimum,
        load_classifier_model,
        run_preloaded_classifier,
    )

    validate_hwh_clock_contract(hwh)
    stop = {"requested": False}

    def request_stop(signum, _frame):
        stop["requested"] = True
        print(f"STOP REQUESTED: signal={signum}", flush=True)

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)

    overlay = Overlay(str(bitstream), download=True)
    cnn = overlay.gesture_top_0
    camera = CameraL2Driver.from_pynq()
    locator = LocatorDriver.from_pynq()
    gpio = MMIO(GPIO_BASE, GPIO_SIZE)
    old_gpio_data = int(gpio.read(0x00))
    old_gpio_tri = int(gpio.read(0x04))
    held_camera_buffer = None
    held_locator_mask = 0
    runs = 0
    classified = 0
    no_detection = 0

    try:
        if int(cnn.read(0x0C)) != 0x0001_0000:
            raise RuntimeError("classifier ABI mismatch")
        locator.assert_abi()
        locator.soft_reset()
        manifest = locator.load_v16_package(locator_dir / "locator_v16", timeout_s=2.0)
        decode_spec = pipeline.raw_decode_spec_from_manifest(
            manifest, clamp_to_locator=True
        )
        load_classifier_model(cnn, locator_dir / "classifier_v3")
        if not args.no_led:
            gpio.write(0x00, 0)
            gpio.write(0x04, 0)

        chip_id = initialize_camera_with_retry(camera)
        camera.prepare_capture(camera_source=True)

        transform = pipeline.LetterboxTransform(
            640, 480, 128, 128, 128, 96, 0, 16, 0, 16
        )
        temporal_spec = pipeline.TemporalFilterSpec(class_count=len(CLASS_NAMES))
        bbox_filter = pipeline.BboxEmaHold(temporal_spec)
        class_filter = pipeline.ClassConfirmSwitch(temporal_spec)
        locator_stall_before = locator.read(STALL_COUNT)
        locator_drop_before = locator.read(DROP_COUNT)
        camera_drop_before = camera.read(CAMERA_DROP_COUNT)
        camera_format_before = camera.read(FORMAT_ERROR_COUNT)
        started = time.monotonic()
        last_status = started - args.status_interval
        latest_output = "none"

        print(
            "GESTURE L2 SERVICE RUNNING: chip_id=0x{:04X} fclk0={:.1f}MHz "
            "fclk1={:.1f}MHz locator=8lane top1=PL roi={} "
            "confirm=gesture2/background3/none3".format(
                chip_id,
                float(Clocks.fclk0_mhz),
                float(Clocks.fclk1_mhz),
                args.roi_mode,
            ),
            flush=True,
        )

        while not stop["requested"] and (
            args.duration == 0.0 or time.monotonic() - started < args.duration
        ):
            loop_started = time.monotonic()
            buffer_id, frame_id = camera.wait_frame(timeout_s=args.timeout)
            held_camera_buffer = buffer_id
            locator.submit_preloaded(buffer_id, frame_id)
            top1 = locator.wait_top1(frame_id=frame_id, timeout_s=args.timeout)
            held_locator_mask = 1 << top1.buffer_id
            detection = pipeline.decode_top1_raw_values(
                top1.cell_x, top1.cell_y, top1.raw_values_i32, decode_spec
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
                latest_output = (
                    "none"
                    if class_state.output_class is None
                    else CLASS_NAMES[class_state.output_class]
                )
                no_detection += 1
                if not args.no_led:
                    gpio.write(
                        0x00,
                        0
                        if class_state.output_class is None
                        else 1 << int(class_state.output_class),
                    )
            else:
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
                    camera.wait_roi(
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
                    camera.wait_roi(
                        descriptor_tag=frame_id, timeout_s=args.timeout
                    )
                raw_class = run_preloaded_classifier(cnn, timeout_s=args.timeout)
                class_state = class_filter.update(raw_class)
                latest_output = (
                    "pending"
                    if class_state.output_class is None
                    else CLASS_NAMES[class_state.output_class]
                )
                if not args.no_led:
                    gpio.write(
                        0x00,
                        0
                        if class_state.output_class is None
                        else 1 << int(class_state.output_class),
                    )
                classified += 1
            camera.release_all_buffers()
            runs += 1

            now = time.monotonic()
            if now - last_status >= args.status_interval:
                print(
                    "STATUS: runs={} classified={} no_detection={} confidence={} "
                    "output={} loop_ms={:.1f}".format(
                        runs,
                        classified,
                        no_detection,
                        detection.confidence_i32,
                        latest_output,
                        (now - loop_started) * 1000.0,
                    ),
                    flush=True,
                )
                last_status = now

        counters = {
            "locator_stall_delta": (locator.read(STALL_COUNT) - locator_stall_before)
            & 0xFFFF_FFFF,
            "locator_drop_delta": (locator.read(DROP_COUNT) - locator_drop_before)
            & 0xFFFF_FFFF,
            "camera_drop_delta": (camera.read(CAMERA_DROP_COUNT) - camera_drop_before)
            & 0xFFFF_FFFF,
            "camera_format_delta": (
                camera.read(FORMAT_ERROR_COUNT) - camera_format_before
            )
            & 0xFFFF_FFFF,
        }
        print(
            "GESTURE L2 SERVICE STOPPED: runs={} classified={} counters={}".format(
                runs, classified, json.dumps(counters, sort_keys=True)
            ),
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
                if not args.no_led:
                    gpio.write(0x00, 0)
                    gpio.write(0x04, old_gpio_tri)
                    if old_gpio_tri == 0:
                        gpio.write(0x00, old_gpio_data)


if __name__ == "__main__":
    raise SystemExit(main())
