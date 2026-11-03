"""Headless boot service for the Phase 2-L1 Locator-v16/classifier-v3 demo.

Unlike the Jupyter live viewer, this entry point programs the candidate
Overlay, loads both model packages, waits for a USB camera, and drives only
the physical LEDs.  It writes status messages to stdout for systemd/journald
but does not render or save camera frames.
"""

from __future__ import annotations

import argparse
import json
import signal
import sys
import time
from pathlib import Path


DEFAULT_CAMERA = (
    "/dev/v4l/by-id/"
    "usb-Web_Camera_Web_Camera_202604081837-video-index0"
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run Locator v16 and classifier v3 without Jupyter"
    )
    parser.add_argument("--deploy-dir", required=True)
    parser.add_argument("--device", default=DEFAULT_CAMERA)
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument(
        "--duration", type=float, default=0.0,
        help="seconds to run; 0 runs until SIGINT or SIGTERM",
    )
    parser.add_argument("--timeout", type=float, default=2.0)
    parser.add_argument("--camera-retry", type=float, default=2.0)
    parser.add_argument("--status-interval", type=float, default=2.0)
    parser.add_argument("--bbox-expansion", type=float, default=0.18)
    parser.add_argument("--bbox-ema-alpha", type=float, default=0.30)
    parser.add_argument("--miss-hold-frames", type=int, default=3)
    parser.add_argument("--class-vote-window", type=int, default=5)
    parser.add_argument("--class-switch-frames", type=int, default=2)
    parser.add_argument("--no-led", action="store_true")
    return parser.parse_args()


def validate_args(args) -> None:
    if args.width <= 0 or args.height <= 0:
        raise ValueError("width and height must be positive")
    if args.duration < 0.0:
        raise ValueError("duration must be non-negative")
    if args.timeout <= 0.0 or args.camera_retry <= 0.0:
        raise ValueError("timeout and camera-retry must be positive")
    if args.status_interval <= 0.0:
        raise ValueError("status-interval must be positive")
    if args.bbox_expansion < 0.0:
        raise ValueError("bbox-expansion must be non-negative")
    if not 0.0 < args.bbox_ema_alpha <= 1.0:
        raise ValueError("bbox-ema-alpha must be in (0, 1]")
    if args.miss_hold_frames < 0:
        raise ValueError("miss-hold-frames must be non-negative")
    if args.class_vote_window <= 0 or args.class_switch_frames <= 0:
        raise ValueError("class vote and switch frame counts must be positive")


def wait_for_camera(device: str, retry_s: float, stop_requested) -> bool:
    announced = False
    while not stop_requested():
        if Path(device).exists():
            return True
        if not announced:
            print("WAITING FOR CAMERA:", device, flush=True)
            announced = True
        time.sleep(retry_s)
    return False


def open_camera(cv2, device: str, width: int, height: int):
    cap = cv2.VideoCapture(device, cv2.CAP_V4L2)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    if not cap.isOpened():
        cap.release()
        return None
    return cap


def main() -> int:
    args = parse_args()
    validate_args(args)

    deploy_dir = Path(args.deploy_dir).resolve()
    script_dir = Path(__file__).resolve().parent
    bitstream = deploy_dir / "phase2_l1_locator_v16_classifier_v3.bit"
    hwh = deploy_dir / "phase2_l1_locator_v16_classifier_v3.hwh"
    required = (
        bitstream,
        hwh,
        deploy_dir / "locator_driver.py",
        deploy_dir / "phase2_l1_pipeline.py",
        deploy_dir / "phase2_l1_v16_v3_live_view.py",
        deploy_dir / "locator_v16" / "locator_model_blob.mem",
        deploy_dir / "locator_v16" / "locator_layer_layout.json",
        deploy_dir / "locator_v16" / "locator_quantization_manifest.json",
        deploy_dir / "classifier_v3" / "weights_all.mem",
        deploy_dir / "classifier_v3" / "layer_descriptors.mem",
    )
    for path in required:
        if not path.is_file():
            raise FileNotFoundError(path)

    if str(deploy_dir) not in sys.path:
        sys.path.insert(0, str(deploy_dir))

    import cv2
    import numpy as np
    from pynq import Clocks, MMIO, Overlay
    from locator_driver import DROP_COUNT, STALL_COUNT, LocatorDriver
    import phase2_l1_v16_v3_live_view as live

    pipeline = live.load_local_pipeline_module(deploy_dir / "phase2_l1_pipeline.py")

    stop = {"requested": False}

    def request_stop(signum, _frame):
        stop["requested"] = True
        print("STOP REQUESTED: signal={}".format(signum), flush=True)

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)
    stop_requested = lambda: stop["requested"]

    if not wait_for_camera(args.device, args.camera_retry, stop_requested):
        return 0

    overlay_started = time.monotonic()
    overlay = Overlay(str(bitstream))
    # Keep the Overlay alive for the lifetime of all MMIO objects.
    _ = overlay
    print(
        "OVERLAY PROGRAMMED: {:.1f} ms".format(
            (time.monotonic() - overlay_started) * 1000.0
        ),
        flush=True,
    )

    locator = LocatorDriver.from_pynq()
    locator.assert_abi()
    locator.soft_reset()
    quant_manifest = locator.load_v16_package(
        deploy_dir / "locator_v16", timeout_s=args.timeout
    )
    decode_spec = pipeline.raw_decode_spec_from_manifest(
        quant_manifest, clamp_to_locator=True
    )

    cnn = MMIO(live.CLASSIFIER_BASE, live.CLASSIFIER_SIZE)
    if int(cnn.read(live.REG_ABI)) != 0x0001_0000:
        raise RuntimeError("classifier ABI mismatch after programming Overlay")
    classifier_load_ms = live.load_classifier_model(
        cnn, deploy_dir / "classifier_v3"
    )

    gpio = MMIO(live.GPIO_BASE, live.GPIO_SIZE)
    old_gpio_data = int(gpio.read(0x00))
    old_gpio_tri = int(gpio.read(0x04))
    if not args.no_led:
        gpio.write(0x00, 0)
        gpio.write(0x04, 0)

    print(
        "MODELS READY: locator=v16 classifier=v3 classifier_load_ms={:.1f} ".format(
            classifier_load_ms
        )
        + "fclk0_mhz={:.1f} fclk1_mhz={:.1f}".format(
            float(Clocks.fclk0_mhz), float(Clocks.fclk1_mhz)
        ),
        flush=True,
    )

    letterbox_spec = pipeline.LetterboxSpec(
        target_width=128,
        target_height=128,
        pad_value=0,
        interpolation="nearest",
        resize_rounding="half_up",
        odd_padding="top_left_floor",
    )
    temporal_spec = pipeline.TemporalFilterSpec(
        bbox_ema_alpha=args.bbox_ema_alpha,
        miss_hold_frames=args.miss_hold_frames,
        class_vote_window=args.class_vote_window,
        class_switch_frames=args.class_switch_frames,
        class_count=len(live.CLASS_NAMES),
    )
    bbox_filter = pipeline.BboxEmaHold(temporal_spec)
    class_filter = pipeline.ClassVoteSwitch(temporal_spec)

    cap = None
    inference_count = 0
    latest_class_id = None
    session_started = time.monotonic()
    last_status = session_started - args.status_interval
    stall_before = locator.read(STALL_COUNT)
    drop_before = locator.read(DROP_COUNT)

    try:
        print("GESTURE SERVICE RUNNING: device={}".format(args.device), flush=True)
        while not stop_requested() and (
            args.duration == 0.0
            or time.monotonic() - session_started < args.duration
        ):
            if cap is None:
                if not wait_for_camera(args.device, args.camera_retry, stop_requested):
                    break
                cap = open_camera(cv2, args.device, args.width, args.height)
                if cap is None:
                    print("CAMERA OPEN FAILED; retrying", flush=True)
                    time.sleep(args.camera_retry)
                    continue
                print("CAMERA OPENED:", args.device, flush=True)

            loop_started = time.monotonic()
            ok, frame = cap.read()
            if not ok or frame is None:
                print("CAMERA READ FAILED; reopening", flush=True)
                cap.release()
                cap = None
                bbox_filter.reset()
                class_filter.reset()
                latest_class_id = None
                if not args.no_led:
                    gpio.write(0x00, 0)
                time.sleep(args.camera_retry)
                continue
            if frame.dtype != np.uint8 or frame.ndim != 3 or frame.shape[2] != 3:
                raise RuntimeError(
                    "unexpected camera frame {}/{}".format(frame.shape, frame.dtype)
                )

            gray = pipeline.bgr_to_gray_u8(frame, method="opencv_bgr2gray")
            locator_input, transform = pipeline.letterbox_gray_u8(
                gray, letterbox_spec
            )
            frame_id = (0xB000_0000 + inference_count) & 0xFFFF_FFFF
            locator.submit(locator_input, frame_id)
            loc_result = None
            try:
                loc_result = locator.wait_output(
                    frame_id=frame_id, timeout_s=args.timeout
                )
                detection = pipeline.decode_top1_raw_map(
                    loc_result.raw_map_i32, decode_spec
                )
                raw_source_bbox = None
                if (
                    detection.passed_threshold
                    and detection.bbox_locator_xyxy is not None
                ):
                    raw_source_bbox = pipeline.locator_bbox_to_source(
                        detection.bbox_locator_xyxy,
                        transform,
                        clip_to_source=True,
                    )

                bbox_state = bbox_filter.update(raw_source_bbox)
                stable_bbox = bbox_state.bbox_xyxy
                raw_class_id = None
                latest_class_id = None
                if stable_bbox is not None:
                    try:
                        classifier_input, _crop_box = (
                            pipeline.classifier_bbox_crop_u8(
                                frame,
                                stable_bbox,
                                expansion_ratio=args.bbox_expansion,
                                make_square=True,
                                clip_to_source=True,
                                output_size=32,
                                grayscale_method="opencv_bgr2gray",
                                interpolation="linear",
                            )
                        )
                        raw_class_id, _upload_ms, _infer_ms = live.run_classifier(
                            cnn, classifier_input, args.timeout
                        )
                        latest_class_id = class_filter.update(
                            raw_class_id
                        ).output_class
                    except ValueError as exc:
                        print("ROI SKIPPED:", exc, flush=True)
                        latest_class_id = class_filter.output_class
                else:
                    class_filter.reset()

                if not args.no_led:
                    gpio.write(
                        0x00,
                        0
                        if latest_class_id is None
                        else (1 << int(latest_class_id)),
                    )

                inference_count += 1
                now = time.monotonic()
                if now - last_status >= args.status_interval:
                    output_name = (
                        "none"
                        if latest_class_id is None
                        else live.CLASS_NAMES[int(latest_class_id)]
                    )
                    print(
                        "STATUS: runs={} raw={} threshold={} detected={} ".format(
                            inference_count,
                            detection.confidence_i32,
                            decode_spec.confidence_threshold_i32,
                            detection.passed_threshold,
                        )
                        + "class={} loop_ms={:.1f}".format(
                            output_name,
                            (now - loop_started) * 1000.0,
                        ),
                        flush=True,
                    )
                    last_status = now
            finally:
                if loc_result is not None:
                    locator.release_output(1 << loc_result.buffer_id)
    finally:
        if cap is not None:
            cap.release()
        if not args.no_led:
            gpio.write(0x00, 0)
            gpio.write(0x04, old_gpio_tri)
            if old_gpio_tri == 0:
                gpio.write(0x00, old_gpio_data)

    stall_after = locator.read(STALL_COUNT)
    drop_after = locator.read(DROP_COUNT)
    counters = {
        "stall_delta": (stall_after - stall_before) & 0xFFFF_FFFF,
        "drop_delta": (drop_after - drop_before) & 0xFFFF_FFFF,
    }
    print(
        "GESTURE SERVICE STOPPED: runs={} counters={}".format(
            inference_count, json.dumps(counters, sort_keys=True)
        ),
        flush=True,
    )
    return 0 if counters["drop_delta"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
