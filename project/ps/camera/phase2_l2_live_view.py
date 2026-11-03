"""Live Jupyter view for the current Phase 2-L2 OV5640 hardware.

The left panel is the exact 128x128 Gray8 frame retained by PL for Locator.
The right panel reconstructs the 32x32 classifier input with the same nearest
mapping used by the same-frame ROI hardware.  The hardware ROI completion is
also checked against the camera frame ID before classification starts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import signal
import statistics
import subprocess
import sys
import time
from collections import Counter, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional, Sequence

import numpy as np


EXPECTED_BIT_SHA256 = "e7487df16110d63c86ee313c2c34f70154a515c328a7475089045ef1f68528ad"
EXPECTED_HWH_SHA256 = "035dd48cce4f594e71c37ea1eafe1100a3d0f8e2bfb9c51467665fdf780535fb"
EXPECTED_CAMERA_ABI = 0x0000_0403
EXPECTED_LOCATOR_ABI = 0x0000_0302
EXPECTED_CLASSIFIER_ABI = 0x0001_0000
EXPECTED_TOP1_MAGIC = 0x5431_5231
ACTIVE_SERVICES = (
    "gesture-demo-sameframe128.service",
    "gesture-demo.service",
    "gesture-demo-l2.service",
)
GPIO_BASE = 0x4120_0000
GPIO_SIZE = 0x0001_0000
ACTIVE_IMAGE_ROWS = slice(16, 112)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_artifact_pair(
    bit_path: Path, hwh_path: Path, *, allow_unverified: bool = False
) -> dict:
    """Reject mixed or stale implementation artifacts before programming PL."""

    bit_path = Path(bit_path).resolve()
    hwh_path = Path(hwh_path).resolve()
    if not bit_path.is_file() or not hwh_path.is_file():
        raise FileNotFoundError("paired Phase 2-L2 .bit/.hwh files are required")
    if bit_path.parent != hwh_path.parent or bit_path.stem != hwh_path.stem:
        raise ValueError("BIT and HWH must share one directory and basename")
    actual = {"bit": sha256_file(bit_path), "hwh": sha256_file(hwh_path)}
    expected = {"bit": EXPECTED_BIT_SHA256, "hwh": EXPECTED_HWH_SHA256}
    if not allow_unverified and actual != expected:
        raise RuntimeError(
            "hardware artifact hash mismatch: expected {} got {}; "
            "use --allow-unverified-artifacts only for an intentional A/B build".format(
                expected, actual
            )
        )
    return actual


def active_gesture_services(
    runner: Callable[..., object] = subprocess.run,
) -> list[str]:
    active = []
    for service in ACTIVE_SERVICES:
        result = runner(
            ["systemctl", "is-active", "--quiet", service],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if int(getattr(result, "returncode")) == 0:
            active.append(service)
    return active


def require_services_stopped(
    runner: Callable[..., object] = subprocess.run,
) -> None:
    active = active_gesture_services(runner)
    if active:
        raise RuntimeError(
            "stop the competing hardware service first: " + ", ".join(active)
        )


def reconstruct_same_frame_roi(
    frame_u8: np.ndarray, crop_box_xyxy: Sequence[int]
) -> np.ndarray:
    """Reproduce RTL address mapping: source=floor(dst*side/32)."""

    frame = np.asarray(frame_u8)
    if frame.dtype != np.uint8 or frame.shape != (128, 128):
        raise ValueError("frame must be uint8 with shape 128x128")
    if len(crop_box_xyxy) != 4:
        raise ValueError("crop box must contain x0, y0, x1, y1")
    x0, y0, x1, y1 = (int(value) for value in crop_box_xyxy)
    side = x1 - x0
    if side <= 0 or side != y1 - y0:
        raise ValueError("crop box must be a non-empty square")
    if x0 < 0 or y0 < 0 or x1 > 128 or y1 > 128:
        raise ValueError("crop box must fit inside the 128x128 frame")
    offsets = (np.arange(32, dtype=np.int64) * side) // 32
    return np.ascontiguousarray(frame[y0 + offsets[:, None], x0 + offsets[None, :]])


def frame_light_metrics(frame_u8: np.ndarray) -> dict:
    """Measure only the active 128x96 letterbox region, excluding black pads."""

    frame = np.asarray(frame_u8)
    if frame.dtype != np.uint8 or frame.shape != (128, 128):
        raise ValueError("frame must be uint8 with shape 128x128")
    active = frame[ACTIVE_IMAGE_ROWS, :]
    p05, p95 = np.percentile(active, (5, 95))
    return {
        "mean": round(float(np.mean(active)), 2),
        "std": round(float(np.std(active)), 2),
        "p05": round(float(p05), 2),
        "p95": round(float(p95), 2),
        "dark_pct": round(float(np.mean(active <= 16) * 100.0), 2),
        "bright_pct": round(float(np.mean(active >= 240) * 100.0), 2),
    }


def _draw_box(cv2, image, box, color, scale: int) -> None:
    if box is None:
        return
    x0, y0, x1, y1 = (int(round(float(value) * scale)) for value in box)
    limit_x, limit_y = image.shape[1] - 1, image.shape[0] - 1
    x0, x1 = min(max(x0, 0), limit_x), min(max(x1, 0), limit_x)
    y0, y1 = min(max(y0, 0), limit_y), min(max(y1, 0), limit_y)
    if x1 > x0 and y1 > y0:
        cv2.rectangle(image, (x0, y0), (x1, y1), color, 2)


def compose_preview(
    cv2,
    frame_u8: np.ndarray,
    classifier_roi_u8: Optional[np.ndarray],
    *,
    raw_box,
    stable_box,
    crop_box,
    lines: Sequence[str],
) -> np.ndarray:
    scale = 4
    left = cv2.cvtColor(
        cv2.resize(frame_u8, (512, 512), interpolation=cv2.INTER_NEAREST),
        cv2.COLOR_GRAY2BGR,
    )
    _draw_box(cv2, left, raw_box, (0, 255, 0), scale)
    _draw_box(cv2, left, stable_box, (0, 255, 255), scale)
    _draw_box(cv2, left, crop_box, (255, 255, 0), scale)

    canvas = np.full((660, 900, 3), 24, dtype=np.uint8)
    canvas[62:574, 12:524] = left
    if classifier_roi_u8 is not None:
        roi = cv2.cvtColor(
            cv2.resize(classifier_roi_u8, (256, 256), interpolation=cv2.INTER_NEAREST),
            cv2.COLOR_GRAY2BGR,
        )
        canvas[112:368, 612:868] = roi
    cv2.putText(canvas, "Exact PL Locator input (128x128)", (12, 34),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
    cv2.putText(canvas, "Classifier ROI (32x32)", (590, 86),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2, cv2.LINE_AA)
    cv2.putText(canvas, "green=raw  yellow=EMA  cyan=18% square ROI", (12, 606),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
    for index, line in enumerate(lines[:8]):
        cv2.putText(canvas, str(line), (548, 404 + index * 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.47, (0, 255, 255), 1, cv2.LINE_AA)
    return canvas


def summarize(values: Sequence[float]) -> Optional[dict]:
    if not values:
        return None
    ordered = sorted(float(value) for value in values)
    p95 = ordered[min(len(ordered) - 1, (95 * len(ordered) + 99) // 100 - 1)]
    return {
        "min": round(ordered[0], 3),
        "mean": round(statistics.fmean(ordered), 3),
        "p95": round(p95, 3),
        "max": round(ordered[-1], 3),
    }


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Current OV5640 -> Locator -> same-frame ROI -> classifier live view"
    )
    parser.add_argument("--deploy-dir", required=True)
    parser.add_argument("--duration", type=float, default=120.0,
                        help="seconds; 0 runs until interrupted")
    parser.add_argument("--max-frames", type=int, default=0,
                        help="0 means unlimited")
    parser.add_argument("--timeout", type=float, default=3.0)
    parser.add_argument("--jpeg-quality", type=int, default=78)
    parser.add_argument("--save-every", type=int, default=30,
                        help="save one annotated PNG every N frames; 0 disables")
    parser.add_argument("--result-dir", default="")
    parser.add_argument("--no-save", action="store_true")
    parser.add_argument("--no-led", action="store_true")
    parser.add_argument("--allow-unverified-artifacts", action="store_true")
    args = parser.parse_args(argv)
    if args.duration < 0 or args.max_frames < 0 or args.timeout <= 0:
        parser.error("duration/max-frames must be non-negative and timeout positive")
    if args.jpeg_quality not in range(1, 101) or args.save_every < 0:
        parser.error("jpeg-quality must be 1..100 and save-every non-negative")
    if args.no_save and args.result_dir:
        parser.error("--result-dir cannot be combined with --no-save")
    return args


def main(argv=None) -> int:
    args = parse_args(argv)
    deploy_dir = Path(args.deploy_dir).resolve()
    camera_dir, locator_dir = deploy_dir / "camera", deploy_dir / "locator"
    bit_path = camera_dir / "phase2_l2_ov5640.bit"
    hwh_path = camera_dir / "phase2_l2_ov5640.hwh"
    required = (
        camera_dir / "camera_l2_driver.py",
        camera_dir / "phase2_l2_headless.py",
        camera_dir / "phase2_l2_closed_loop.py",
        locator_dir / "locator_driver.py",
        locator_dir / "phase2_l1_pipeline.py",
        locator_dir / "locator_v16" / "locator_model_blob.mem",
        locator_dir / "locator_v16" / "locator_quantization_manifest.json",
        locator_dir / "classifier_v3" / "weights_all.mem",
        locator_dir / "classifier_v3" / "layer_descriptors.mem",
    )
    for path in required:
        if not path.is_file():
            raise FileNotFoundError(path)
    require_services_stopped()
    artifact_hashes = validate_artifact_pair(
        bit_path, hwh_path, allow_unverified=args.allow_unverified_artifacts
    )

    sys.path[:0] = [str(camera_dir), str(locator_dir)]
    for name in (
        "camera_l2_driver", "phase2_l2_headless", "phase2_l2_closed_loop",
        "locator_driver", "phase2_l1_pipeline",
    ):
        sys.modules.pop(name, None)

    import cv2
    from IPython.display import Image as DisplayImage
    from IPython.display import display, update_display
    from pynq import Clocks, MMIO, Overlay
    from camera_l2_driver import (
        ABI_VERSION as CAMERA_ABI_REG,
        DROP_COUNT as CAMERA_DROP_COUNT,
        FORMAT_ERROR_COUNT,
        CameraL2Driver,
    )
    from locator_driver import (
        ABI_VERSION as LOCATOR_ABI_REG,
        DROP_COUNT as LOCATOR_DROP_COUNT,
        STALL_COUNT,
        TOP1_CAPABILITY,
        LocatorDriver,
        validate_hwh_clock_contract,
    )
    import phase2_l1_pipeline as pipeline
    from phase2_l2_closed_loop import (
        CLASS_ABI, CLASS_NAMES, load_classifier_model, run_preloaded_classifier,
    )
    from phase2_l2_headless import initialize_camera_with_retry

    validate_hwh_clock_contract(hwh_path)
    overlay = Overlay(str(bit_path), download=True)
    cnn = overlay.gesture_top_0
    camera = CameraL2Driver.from_pynq()
    locator = LocatorDriver.from_pynq()
    gpio = MMIO(GPIO_BASE, GPIO_SIZE)
    old_gpio_data, old_gpio_tri = int(gpio.read(0x00)), int(gpio.read(0x04))
    held_camera_buffer = None
    held_locator_mask = 0
    stop = {"requested": False, "signal": None}

    def request_stop(signum, _frame):
        stop.update(requested=True, signal=signum)

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_dir = None
    if not args.no_save:
        result_dir = (
            Path(args.result_dir).resolve()
            if args.result_dir
            else deploy_dir / "live_results" / timestamp
        )
        if result_dir.exists():
            raise FileExistsError(result_dir)
        result_dir.mkdir(parents=True)

    rows = []
    latest_preview = None
    loop_times = deque(maxlen=20)
    class_counts = Counter()
    runs = classified = detected_runs = 0
    failure = None
    started = time.monotonic()
    display_id = "phase2-l2-live-" + timestamp
    display_started = False

    try:
        camera.assert_abi()
        locator.assert_abi()
        if camera.read(CAMERA_ABI_REG) != EXPECTED_CAMERA_ABI:
            raise RuntimeError("unexpected camera ABI constant")
        if locator.read(LOCATOR_ABI_REG) != EXPECTED_LOCATOR_ABI:
            raise RuntimeError("unexpected Locator ABI constant")
        if int(cnn.read(CLASS_ABI)) != EXPECTED_CLASSIFIER_ABI:
            raise RuntimeError("classifier ABI mismatch")
        if locator.read(TOP1_CAPABILITY) != EXPECTED_TOP1_MAGIC:
            raise RuntimeError("PL Top-1 capability mismatch")

        locator.soft_reset()
        manifest = locator.load_v16_package(locator_dir / "locator_v16", timeout_s=2.0)
        decode_spec = pipeline.raw_decode_spec_from_manifest(manifest, clamp_to_locator=True)
        load_classifier_model(cnn, locator_dir / "classifier_v3")
        temporal_spec = pipeline.TemporalFilterSpec(class_count=len(CLASS_NAMES))
        bbox_filter = pipeline.BboxEmaHold(temporal_spec)
        class_filter = pipeline.ClassConfirmSwitch(temporal_spec)
        if not args.no_led:
            gpio.write(0x00, 0)
            gpio.write(0x04, 0)

        chip_id = initialize_camera_with_retry(camera)
        camera.prepare_capture(camera_source=True)
        counters_before = {
            "locator_stall": locator.read(STALL_COUNT),
            "locator_drop": locator.read(LOCATOR_DROP_COUNT),
            "camera_drop": camera.read(CAMERA_DROP_COUNT),
            "camera_format": camera.read(FORMAT_ERROR_COUNT),
        }
        print(
            "LIVE VIEW STARTED: chip=0x{:04X} cameraABI=0x{:08X} "
            "locatorABI=0x{:08X} classifierABI=0x{:08X}".format(
                chip_id, EXPECTED_CAMERA_ABI, EXPECTED_LOCATOR_ABI,
                EXPECTED_CLASSIFIER_ABI,
            ), flush=True,
        )

        while not stop["requested"]:
            if args.duration and time.monotonic() - started >= args.duration:
                break
            if args.max_frames and runs >= args.max_frames:
                break
            loop_started = time.monotonic()
            buffer_id, frame_id = camera.wait_frame(timeout_s=args.timeout)
            held_camera_buffer = buffer_id
            read_started = time.monotonic()
            frame = camera.read_buffer(buffer_id)
            readback_ms = (time.monotonic() - read_started) * 1000.0

            locator.submit_preloaded(buffer_id, frame_id)
            locator_started = time.monotonic()
            top1 = locator.wait_top1(frame_id=frame_id, timeout_s=args.timeout)
            locator_ms = (time.monotonic() - locator_started) * 1000.0
            held_locator_mask = 1 << top1.buffer_id
            detection = pipeline.decode_top1_raw_values(
                top1.cell_x, top1.cell_y, top1.raw_values_i32, decode_spec
            )
            locator.release_output(held_locator_mask)
            held_locator_mask = 0

            raw_box = None
            if detection.passed_threshold and detection.bbox_locator_xyxy is not None:
                raw_box = detection.bbox_locator_xyxy
                detected_runs += 1
            stable = bbox_filter.update(raw_box)
            crop_box = None
            roi_image = None
            raw_class = None
            roi_source_frame = None
            classifier_ms = None
            if raw_box is None:
                camera.release_buffer(buffer_id)
                held_camera_buffer = None
                class_state = class_filter.update(None)
            else:
                crop_box = pipeline.prepare_source_crop_box(
                    stable.bbox_xyxy, 128, 128,
                    expansion_ratio=pipeline.ROI_MARGIN_EACH_SIDE,
                    make_square=True, clip_to_source=True,
                )
                roi_image = reconstruct_same_frame_roi(frame, crop_box)
                camera.arm_same_frame_roi(buffer_id, crop_box, descriptor_tag=frame_id)
                roi_result = camera.wait_roi(
                    descriptor_tag=frame_id, source_frame_id=frame_id,
                    timeout_s=args.timeout,
                )
                roi_source_frame = roi_result.source_frame_id
                camera.release_buffer(buffer_id)
                held_camera_buffer = None
                classifier_started = time.monotonic()
                raw_class = run_preloaded_classifier(cnn, timeout_s=args.timeout)
                classifier_ms = (time.monotonic() - classifier_started) * 1000.0
                class_state = class_filter.update(raw_class)
                classified += 1
                class_counts[CLASS_NAMES[raw_class]] += 1
            camera.release_all_buffers()

            output_class = class_state.output_class
            output_name = "none" if output_class is None else CLASS_NAMES[output_class]
            if not args.no_led:
                gpio.write(0x00, 0 if output_class is None else 1 << output_class)
            light = frame_light_metrics(frame)
            loop_ms = (time.monotonic() - loop_started) * 1000.0
            loop_times.append(loop_ms)
            fps = 1000.0 / max(statistics.fmean(loop_times), 0.001)
            state = "DETECT" if raw_box is not None else ("HOLD" if stable.held else "NO HAND")
            edge_touch = bool(
                crop_box is not None and (
                    crop_box[0] == 0 or crop_box[1] == 0
                    or crop_box[2] == 128 or crop_box[3] == 128
                )
            )
            lines = (
                "{} frame={} FPS={:.2f}".format(state, frame_id, fps),
                "conf={} / threshold={}".format(
                    detection.confidence_i32, decode_spec.confidence_threshold_i32
                ),
                "class raw={} output={}".format(
                    "none" if raw_class is None else CLASS_NAMES[raw_class], output_name
                ),
                "light mean/std={:.1f}/{:.1f}".format(light["mean"], light["std"]),
                "dark/bright={:.1f}%/{:.1f}%".format(
                    light["dark_pct"], light["bright_pct"]
                ),
                "crop={} edge_touch={}".format(crop_box, edge_touch),
                "roi_frame={} locator_ms={:.1f}".format(roi_source_frame, locator_ms),
                "readback={:.1f}ms loop={:.1f}ms".format(readback_ms, loop_ms),
            )
            latest_preview = compose_preview(
                cv2, frame, roi_image, raw_box=raw_box,
                stable_box=stable.bbox_xyxy, crop_box=crop_box, lines=lines,
            )
            ok, encoded = cv2.imencode(
                ".jpg", latest_preview,
                [int(cv2.IMWRITE_JPEG_QUALITY), args.jpeg_quality],
            )
            if not ok:
                raise RuntimeError("JPEG encode failed")
            image = DisplayImage(data=encoded.tobytes(), format="jpeg")
            if not display_started:
                display(image, display_id=display_id)
                display_started = True
            else:
                update_display(image, display_id=display_id)

            runs += 1
            row = {
                "index": runs - 1,
                "frame_id": frame_id,
                "detected": raw_box is not None,
                "confidence_i32": detection.confidence_i32,
                "threshold_i32": decode_spec.confidence_threshold_i32,
                "raw_bbox_xyxy": None if raw_box is None else list(raw_box),
                "ema_bbox_xyxy": None if stable.bbox_xyxy is None else list(stable.bbox_xyxy),
                "ema_held": stable.held,
                "crop_box_xyxy": None if crop_box is None else list(crop_box),
                "crop_touches_edge": edge_touch,
                "roi_source_frame_id": roi_source_frame,
                "raw_class": None if raw_class is None else CLASS_NAMES[raw_class],
                "output_class": output_name,
                "light": light,
                "timing_ms": {
                    "frame_readback": round(readback_ms, 3),
                    "locator": round(locator_ms, 3),
                    "classifier": None if classifier_ms is None else round(classifier_ms, 3),
                    "loop": round(loop_ms, 3),
                },
            }
            rows.append(row)
            if result_dir is not None and args.save_every and runs % args.save_every == 0:
                cv2.imwrite(str(result_dir / "frame_{:06d}.png".format(runs)), latest_preview)

        counters_after = {
            "locator_stall": locator.read(STALL_COUNT),
            "locator_drop": locator.read(LOCATOR_DROP_COUNT),
            "camera_drop": camera.read(CAMERA_DROP_COUNT),
            "camera_format": camera.read(FORMAT_ERROR_COUNT),
        }
        counter_delta = {
            key: (counters_after[key] - counters_before[key]) & 0xFFFF_FFFF
            for key in counters_before
        }
        if counter_delta["locator_drop"] or counter_delta["camera_format"]:
            raise RuntimeError("hardware error counter increased: {}".format(counter_delta))
        if runs == 0 or latest_preview is None:
            raise RuntimeError("live view stopped before one frame completed")

        if result_dir is not None:
            last_preview_path = result_dir / "last_preview.png"
            if not cv2.imwrite(str(last_preview_path), latest_preview):
                raise RuntimeError("failed to save last preview")
            summary = {
                "status": "STOPPED_BY_USER" if stop["requested"] else "COMPLETE",
                "scope": "interactive_debug_not_accuracy_acceptance",
                "finished_utc": datetime.now(timezone.utc).isoformat(),
                "deploy_dir": str(deploy_dir),
                "artifact_sha256": artifact_hashes,
                "abi": {
                    "camera": "0x{:08X}".format(EXPECTED_CAMERA_ABI),
                    "locator": "0x{:08X}".format(EXPECTED_LOCATOR_ABI),
                    "classifier": "0x{:08X}".format(EXPECTED_CLASSIFIER_ABI),
                },
                "runs": runs,
                "detected_runs": detected_runs,
                "classified_runs": classified,
                "raw_class_counts": dict(class_counts),
                "loop_ms": summarize([row["timing_ms"]["loop"] for row in rows]),
                "hardware_counters": {
                    "before": counters_before, "after": counters_after,
                    "delta": counter_delta,
                },
                "display_contract": {
                    "left": "exact PL-retained 128x128 Locator Gray8 input",
                    "right": "32x32 software reconstruction of exact RTL nearest mapping",
                    "roi_source_frame_checked": True,
                },
                "last_preview": str(last_preview_path),
                "frames": rows,
            }
            (result_dir / "result.json").write_text(
                json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            print("RESULT_DIR:", result_dir, flush=True)
        print(
            "LIVE VIEW COMPLETE: runs={} detected={} classified={} raw_classes={}".format(
                runs, detected_runs, classified, dict(class_counts)
            ), flush=True,
        )
        return 0
    except BaseException as exc:
        failure = exc
        raise
    finally:
        try:
            if held_locator_mask:
                locator.release_output(held_locator_mask)
        finally:
            try:
                if held_camera_buffer is not None:
                    camera.release_buffer(held_camera_buffer)
            finally:
                try:
                    camera.shutdown()
                finally:
                    if not args.no_led:
                        gpio.write(0x00, 0)
                        gpio.write(0x04, old_gpio_tri)
                        if old_gpio_tri == 0:
                            gpio.write(0x00, old_gpio_data)
        if failure is not None:
            print("LIVE VIEW FAILED: {}: {}".format(type(failure).__name__, failure), flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
