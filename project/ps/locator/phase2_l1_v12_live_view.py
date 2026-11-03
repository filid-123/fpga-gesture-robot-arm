"""Jupyter live view for the accepted Phase 2-L1 v12 board candidate.

The script intentionally does not program an Overlay.  Run the formal v12
board test once after each board boot, then execute this file from a Jupyter
cell.  The browser receives annotated JPEG frames while inference remains on
the PYNQ PS/PL system.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import statistics
import sys
import time
from collections import Counter, deque
from datetime import datetime, timezone
from pathlib import Path


CLASSIFIER_BASE = 0x4000_0000
CLASSIFIER_SIZE = 0x1000
GPIO_BASE = 0x4120_0000
GPIO_SIZE = 0x10000

REG_CTRL = 0x00
REG_STATUS = 0x04
REG_CLASS_ID = 0x08
REG_ABI = 0x0C
REG_WEIGHT_ADDR = 0x10
REG_WEIGHT_DATA = 0x14
REG_IMG_ADDR = 0x20
REG_IMG_DATA = 0x24
REG_DESC_INDEX = 0x28
REG_DESC_DATA = 0x2C

CLASS_NAMES = ("background", "fist", "mute", "palm")
EXPECTED_ROI_CONTRACT = "phase2_l1_roi_v1_18pct_square_shift_pyround"


def read_mem_words(path: Path):
    return [
        int(line.strip(), 16)
        for line in path.read_text(encoding="ascii").splitlines()
        if line.strip() and not line.lstrip().startswith("//")
    ]


def summarize(values):
    if not values:
        return None
    ordered = sorted(float(value) for value in values)
    p95_index = min(len(ordered) - 1, max(0, (95 * len(ordered) + 99) // 100 - 1))
    return {
        "min": round(ordered[0], 3),
        "mean": round(statistics.fmean(ordered), 3),
        "p95": round(ordered[p95_index], 3),
        "max": round(ordered[-1], 3),
    }


def rounded_draw_box(box_xyxy, width: int, height: int):
    """Return a clipped OpenCV rectangle or None for invalid geometry."""
    if box_xyxy is None or width <= 0 or height <= 0:
        return None
    x0, y0, x1, y1 = [int(round(float(value))) for value in box_xyxy]
    x0 = min(max(x0, 0), width - 1)
    x1 = min(max(x1, 0), width - 1)
    y0 = min(max(y0, 0), height - 1)
    y1 = min(max(y1, 0), height - 1)
    if x1 <= x0 or y1 <= y0:
        return None
    return (x0, y0), (x1, y1)


def load_local_pipeline_module(path: Path):
    """Load the uploaded frozen PS pipeline without reusing a stale notebook module."""
    module_name = "phase2_l1_pipeline_frozen_runtime"
    spec = importlib.util.spec_from_file_location(module_name, str(path))
    if spec is None or spec.loader is None:
        raise ImportError("cannot load local pipeline module {}".format(path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    if getattr(module, "ROI_CONTRACT_VERSION", None) != EXPECTED_ROI_CONTRACT:
        raise RuntimeError(
            "local phase2_l1_pipeline.py does not implement the frozen ROI contract"
        )
    return module


def make_status_lines(
    state: str,
    confidence_i32: int,
    threshold_i32: int,
    raw_class_name,
    output_class_name,
    miss_count: int,
    pipeline_ms: float,
    display_fps: float,
):
    line1 = "{}  raw={}  threshold={}  cls={}->{}  miss={}".format(
        state,
        confidence_i32,
        threshold_i32,
        raw_class_name or "none",
        output_class_name or "none",
        miss_count,
    )
    line2 = "pipeline={:.1f} ms  live={:.1f} FPS  green=raw yellow=EMA cyan=ROI".format(
        pipeline_ms, display_fps
    )
    return line1, line2


def load_classifier_model(cnn, package_dir: Path) -> float:
    weights = read_mem_words(package_dir / "weights_all.mem")
    descriptors = read_mem_words(package_dir / "layer_descriptors.mem")
    if len(weights) != 9838:
        raise RuntimeError("classification weights must contain 9,838 words")
    if len(descriptors) != 64:
        raise RuntimeError("classification descriptors must contain 64 words")
    started = time.monotonic()
    cnn.write(REG_WEIGHT_ADDR, 0)
    for word in weights:
        cnn.write(REG_WEIGHT_DATA, word)
    cnn.write(REG_DESC_INDEX, 0)
    for word in descriptors:
        cnn.write(REG_DESC_DATA, word)
    return (time.monotonic() - started) * 1000.0


def run_classifier(cnn, image_u8, timeout_s: float):
    import numpy as np

    pixels = np.ascontiguousarray(image_u8, dtype=np.uint8).reshape(-1)
    if pixels.size != 1024:
        raise ValueError("classifier input must contain 1,024 uint8 pixels")

    upload_started = time.monotonic()
    cnn.write(REG_IMG_ADDR, 0)
    for pixel in pixels:
        cnn.write(REG_IMG_DATA, int(pixel))
    upload_ms = (time.monotonic() - upload_started) * 1000.0

    infer_started = time.monotonic()
    cnn.write(REG_CTRL, 1)
    deadline = infer_started + timeout_s
    while time.monotonic() < deadline:
        if cnn.read(REG_STATUS) & 0x4:
            infer_ms = (time.monotonic() - infer_started) * 1000.0
            class_id = int(cnn.read(REG_CLASS_ID))
            if class_id not in range(len(CLASS_NAMES)):
                raise RuntimeError("classifier returned invalid class {}".format(class_id))
            return class_id, upload_ms, infer_ms
        time.sleep(0.0005)
    raise TimeoutError("classifier inference timed out")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Display live USB -> Locator v12 -> classifier results in Jupyter"
    )
    parser.add_argument("--deploy-dir", required=True)
    parser.add_argument("--device", default="/dev/video0")
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument(
        "--duration",
        type=float,
        default=120.0,
        help="seconds to run; 0 runs until the Jupyter stop button is pressed",
    )
    parser.add_argument("--timeout", type=float, default=2.0)
    parser.add_argument("--bbox-expansion", type=float, default=0.18)
    parser.add_argument("--bbox-ema-alpha", type=float, default=0.30)
    parser.add_argument("--miss-hold-frames", type=int, default=3)
    parser.add_argument("--class-vote-window", type=int, default=5)
    parser.add_argument("--class-switch-frames", type=int, default=2)
    parser.add_argument(
        "--disable-temporal",
        action="store_true",
        help="show raw per-frame behavior while keeping the frozen ROI rule",
    )
    parser.add_argument("--jpeg-quality", type=int, default=75)
    parser.add_argument(
        "--display-every",
        type=int,
        default=1,
        help="update browser once per N inference results",
    )
    parser.add_argument("--result", default="")
    parser.add_argument("--no-led", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.width <= 0 or args.height <= 0:
        raise ValueError("width and height must be positive")
    if args.duration < 0.0:
        raise ValueError("duration must be non-negative")
    if args.timeout <= 0.0:
        raise ValueError("timeout must be positive")
    if args.bbox_expansion < 0.0:
        raise ValueError("bbox-expansion must be non-negative")
    if not 0.0 < args.bbox_ema_alpha <= 1.0:
        raise ValueError("bbox-ema-alpha must be in (0, 1]")
    if args.miss_hold_frames < 0:
        raise ValueError("miss-hold-frames must be non-negative")
    if args.class_vote_window <= 0 or args.class_switch_frames <= 0:
        raise ValueError("class vote and switch frame counts must be positive")
    if args.jpeg_quality not in range(1, 101):
        raise ValueError("jpeg-quality must be in 1..100")
    if args.display_every <= 0:
        raise ValueError("display-every must be positive")

    deploy_dir = Path(args.deploy_dir).resolve()
    if not deploy_dir.is_dir():
        raise FileNotFoundError(deploy_dir)
    script_dir = Path(__file__).resolve().parent
    local_pipeline_path = script_dir / "phase2_l1_pipeline.py"
    required = [
        deploy_dir / "locator_driver.py",
        deploy_dir / "locator_v12" / "locator_quantization_manifest.json",
        deploy_dir / "classification_active" / "weights_all.mem",
        deploy_dir / "classification_active" / "layer_descriptors.mem",
        local_pipeline_path,
    ]
    for path in required:
        if not path.is_file():
            raise FileNotFoundError(path)
    if str(deploy_dir) not in sys.path:
        sys.path.insert(0, str(deploy_dir))

    import cv2
    import numpy as np
    from IPython.display import Image as DisplayImage
    from IPython.display import display, update_display
    from pynq import MMIO
    from locator_driver import DROP_COUNT, STALL_COUNT, STATUS, STATUS_MODEL_VALID, LocatorDriver

    pipeline = load_local_pipeline_module(local_pipeline_path)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    result_path = Path(args.result) if args.result else Path.cwd() / (
        "phase2_l1_v12_live_view_{}.json".format(timestamp)
    )
    result_path = result_path.resolve()
    preview_path = result_path.with_name(result_path.stem + "_last.png")
    if result_path.exists() or preview_path.exists():
        raise FileExistsError("refusing to overwrite result or preview")

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
        class_count=len(CLASS_NAMES),
    )
    bbox_filter = pipeline.BboxEmaHold(temporal_spec)
    class_filter = pipeline.ClassVoteSwitch(temporal_spec)

    locator = LocatorDriver.from_pynq()
    locator.assert_abi()
    locator.soft_reset()
    quant_manifest_path = deploy_dir / "locator_v12" / "locator_quantization_manifest.json"
    quant_manifest = json.loads(quant_manifest_path.read_text(encoding="utf-8"))
    locator_model_reload_ms = 0.0
    if not locator.read(STATUS) & STATUS_MODEL_VALID:
        started = time.monotonic()
        quant_manifest = locator.load_v12_package(deploy_dir / "locator_v12", timeout_s=args.timeout)
        locator_model_reload_ms = (time.monotonic() - started) * 1000.0
    decode_spec = pipeline.raw_decode_spec_from_manifest(quant_manifest, clamp_to_locator=True)

    cnn = MMIO(CLASSIFIER_BASE, CLASSIFIER_SIZE)
    if int(cnn.read(REG_ABI)) != 0x0001_0000:
        raise RuntimeError("classifier ABI mismatch; load the accepted v12 Overlay first")
    classifier_model_load_ms = load_classifier_model(cnn, deploy_dir / "classification_active")

    gpio = MMIO(GPIO_BASE, GPIO_SIZE)
    old_gpio_data = int(gpio.read(0x00))
    old_gpio_tri = int(gpio.read(0x04))

    cap = None
    rows = []
    frame_shapes = set()
    latest_preview = None
    display_started = False
    display_id = "phase2-l1-v12-live-{}".format(timestamp)
    recent_loop_ms = deque(maxlen=20)
    interrupted = False
    stall_before = locator.read(STALL_COUNT)
    drop_before = locator.read(DROP_COUNT)
    session_started = time.monotonic()

    try:
        cap = cv2.VideoCapture(args.device, cv2.CAP_V4L2)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        if not cap.isOpened():
            raise RuntimeError("cannot open camera {}".format(args.device))
        if not args.no_led:
            gpio.write(0x04, 0)

        print("LIVE VIEW STARTED: use the Jupyter stop button to finish safely")
        while args.duration == 0.0 or time.monotonic() - session_started < args.duration:
            loop_started = time.monotonic()
            capture_started = loop_started
            ok, frame = cap.read()
            capture_ms = (time.monotonic() - capture_started) * 1000.0
            if not ok or frame is None:
                raise RuntimeError("camera read failed")
            if frame.dtype != np.uint8 or frame.ndim != 3 or frame.shape[2] != 3:
                raise RuntimeError("unexpected frame {}/{}".format(frame.shape, frame.dtype))
            frame_shapes.add(tuple(int(value) for value in frame.shape))

            preprocess_started = time.monotonic()
            gray = pipeline.bgr_to_gray_u8(frame, method="opencv_bgr2gray")
            locator_input, transform = pipeline.letterbox_gray_u8(gray, letterbox_spec)
            preprocess_ms = (time.monotonic() - preprocess_started) * 1000.0

            inference_index = len(rows)
            frame_id = (0xA000_0000 + inference_index) & 0xFFFF_FFFF
            submit_started = time.monotonic()
            input_buffer = locator.submit(locator_input, frame_id)
            locator_submit_ms = (time.monotonic() - submit_started) * 1000.0

            loc_result = None
            try:
                wait_started = time.monotonic()
                loc_result = locator.wait_output(frame_id=frame_id, timeout_s=args.timeout)
                locator_wait_read_ms = (time.monotonic() - wait_started) * 1000.0

                detection = pipeline.decode_top1_raw_map(loc_result.raw_map_i32, decode_spec)
                raw_source_bbox = None
                stable_source_bbox = None
                held_bbox = False
                miss_count = 0
                crop_box = None
                raw_class_id = None
                raw_class_name = None
                voted_class_id = None
                output_class_id = None
                output_class_name = None
                pending_class_id = None
                pending_count = 0
                classifier_upload_ms = None
                classifier_infer_ms = None
                crop_error = None

                if detection.passed_threshold and detection.bbox_locator_xyxy is not None:
                    raw_source_bbox = pipeline.locator_bbox_to_source(
                        detection.bbox_locator_xyxy, transform, clip_to_source=True
                    )

                if args.disable_temporal:
                    stable_source_bbox = raw_source_bbox
                else:
                    bbox_state = bbox_filter.update(raw_source_bbox)
                    stable_source_bbox = bbox_state.bbox_xyxy
                    held_bbox = bbox_state.held
                    miss_count = bbox_state.miss_count

                if stable_source_bbox is not None:
                    try:
                        classifier_input, crop_box = pipeline.classifier_bbox_crop_u8(
                            frame,
                            stable_source_bbox,
                            expansion_ratio=args.bbox_expansion,
                            make_square=True,
                            clip_to_source=True,
                            output_size=32,
                            grayscale_method="opencv_bgr2gray",
                            interpolation="linear",
                        )
                        raw_class_id, classifier_upload_ms, classifier_infer_ms = run_classifier(
                            cnn, classifier_input, args.timeout
                        )
                        raw_class_name = CLASS_NAMES[raw_class_id]
                        if args.disable_temporal:
                            voted_class_id = raw_class_id
                            output_class_id = raw_class_id
                        else:
                            class_state = class_filter.update(raw_class_id)
                            voted_class_id = class_state.voted_class
                            output_class_id = class_state.output_class
                            pending_class_id = class_state.pending_class
                            pending_count = class_state.pending_count
                        if output_class_id is not None:
                            output_class_name = CLASS_NAMES[output_class_id]
                    except ValueError as exc:
                        crop_error = str(exc)
                        output_class_id = class_filter.output_class
                        if output_class_id is not None:
                            output_class_name = CLASS_NAMES[output_class_id]
                elif not args.disable_temporal:
                    class_filter.reset()

                if not args.no_led:
                    gpio.write(0x00, 0 if output_class_id is None else (1 << output_class_id))

                pipeline_ms = (time.monotonic() - preprocess_started) * 1000.0
                preview = frame.copy()
                height, width = preview.shape[:2]
                locator_box = rounded_draw_box(raw_source_bbox, width, height)
                stable_box = rounded_draw_box(stable_source_bbox, width, height)
                classifier_box = rounded_draw_box(crop_box, width, height)
                if locator_box is not None:
                    cv2.rectangle(preview, locator_box[0], locator_box[1], (0, 255, 0), 2)
                if stable_box is not None and not args.disable_temporal:
                    cv2.rectangle(preview, stable_box[0], stable_box[1], (0, 255, 255), 2)
                if classifier_box is not None:
                    cv2.rectangle(preview, classifier_box[0], classifier_box[1], (255, 255, 0), 2)

                provisional_loop_ms = (time.monotonic() - loop_started) * 1000.0
                recent_loop_ms.append(provisional_loop_ms)
                display_fps = 1000.0 / max(statistics.fmean(recent_loop_ms), 0.001)
                if detection.passed_threshold:
                    display_state = "DETECT"
                elif held_bbox:
                    display_state = "HOLD"
                else:
                    display_state = "NO HAND"
                line1, line2 = make_status_lines(
                    display_state,
                    detection.confidence_i32,
                    decode_spec.confidence_threshold_i32,
                    raw_class_name,
                    output_class_name,
                    miss_count,
                    pipeline_ms,
                    display_fps,
                )
                cv2.rectangle(preview, (0, 0), (width - 1, 58), (0, 0, 0), -1)
                cv2.putText(
                    preview, line1, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                    (0, 255, 255), 2, cv2.LINE_AA
                )
                cv2.putText(
                    preview, line2, (8, 48), cv2.FONT_HERSHEY_SIMPLEX, 0.48,
                    (255, 255, 255), 1, cv2.LINE_AA
                )
                latest_preview = preview

                encode_started = time.monotonic()
                encoded_ok, encoded = cv2.imencode(
                    ".jpg", preview, [int(cv2.IMWRITE_JPEG_QUALITY), args.jpeg_quality]
                )
                if not encoded_ok:
                    raise RuntimeError("JPEG encode failed")
                if inference_index % args.display_every == 0:
                    display_image = DisplayImage(data=encoded.tobytes(), format="jpeg")
                    if not display_started:
                        display(display_image, display_id=display_id)
                        display_started = True
                    else:
                        update_display(display_image, display_id=display_id)
                display_encode_ms = (time.monotonic() - encode_started) * 1000.0
                loop_ms = (time.monotonic() - loop_started) * 1000.0
                recent_loop_ms[-1] = loop_ms

                rows.append(
                    {
                        "index": inference_index,
                        "frame_id": "0x{:08X}".format(frame_id),
                        "input_buffer": input_buffer,
                        "output_buffer": loc_result.buffer_id,
                        "confidence_raw_i32": detection.confidence_i32,
                        "threshold_raw_i32": decode_spec.confidence_threshold_i32,
                        "detected": detection.passed_threshold,
                        "raw_detected": detection.passed_threshold,
                        "effective_bbox": stable_source_bbox is not None,
                        "held_bbox": held_bbox,
                        "miss_count": miss_count,
                        "top1_xy": [detection.cell_x, detection.cell_y],
                        "bbox_source_xyxy": None if raw_source_bbox is None else list(raw_source_bbox),
                        "raw_bbox_source_xyxy": None if raw_source_bbox is None else list(raw_source_bbox),
                        "stable_bbox_source_xyxy": None if stable_source_bbox is None else list(stable_source_bbox),
                        "crop_box_xyxy": None if crop_box is None else list(crop_box),
                        "crop_error": crop_error,
                        "raw_class_id": raw_class_id,
                        "raw_class_name": raw_class_name,
                        "voted_class_id": voted_class_id,
                        "pending_class_id": pending_class_id,
                        "pending_count": pending_count,
                        "output_class_id": output_class_id,
                        "output_class_name": output_class_name,
                        "class_id": output_class_id,
                        "class_name": output_class_name,
                        "capture_ms": round(capture_ms, 3),
                        "preprocess_ms": round(preprocess_ms, 3),
                        "locator_submit_ms": round(locator_submit_ms, 3),
                        "locator_wait_read_ms": round(locator_wait_read_ms, 3),
                        "classifier_upload_ms": None if classifier_upload_ms is None else round(classifier_upload_ms, 3),
                        "classifier_infer_ms": None if classifier_infer_ms is None else round(classifier_infer_ms, 3),
                        "pipeline_ms": round(pipeline_ms, 3),
                        "display_encode_ms": round(display_encode_ms, 3),
                        "loop_ms": round(loop_ms, 3),
                    }
                )
            finally:
                if loc_result is not None:
                    locator.release_output(1 << loc_result.buffer_id)
    except KeyboardInterrupt:
        interrupted = True
        print("LIVE VIEW STOP REQUESTED")
    finally:
        if cap is not None:
            cap.release()
        if not args.no_led:
            gpio.write(0x00, old_gpio_data)
            gpio.write(0x04, old_gpio_tri)

    stall_after = locator.read(STALL_COUNT)
    drop_after = locator.read(DROP_COUNT)
    stall_delta = (stall_after - stall_before) & 0xFFFF_FFFF
    drop_delta = (drop_after - drop_before) & 0xFFFF_FFFF
    if drop_delta != 0:
        raise RuntimeError("hardware DROP_COUNT increased by {}".format(drop_delta))
    if not rows or latest_preview is None:
        raise RuntimeError("live view stopped before completing one inference")
    if not cv2.imwrite(str(preview_path), latest_preview):
        raise RuntimeError("failed to save final preview")

    timing_keys = (
        "capture_ms",
        "preprocess_ms",
        "locator_submit_ms",
        "locator_wait_read_ms",
        "classifier_upload_ms",
        "classifier_infer_ms",
        "pipeline_ms",
        "display_encode_ms",
        "loop_ms",
    )
    result = {
        "status": "STOPPED_BY_USER" if interrupted else "COMPLETE",
        "scope": "interactive_live_view_not_accuracy_acceptance",
        "finished_utc": datetime.now(timezone.utc).isoformat(),
        "deploy_dir": str(deploy_dir),
        "device": args.device,
        "requested_resolution": [args.width, args.height],
        "actual_shapes_hwc": [list(shape) for shape in sorted(frame_shapes)],
        "requested_duration_s": args.duration,
        "elapsed_s": round(time.monotonic() - session_started, 3),
        "inference_runs": len(rows),
        "detected_runs": sum(bool(row["detected"]) for row in rows),
        "effective_bbox_runs": sum(bool(row["effective_bbox"]) for row in rows),
        "held_bbox_runs": sum(bool(row["held_bbox"]) for row in rows),
        "classifier_runs": sum(row["raw_class_id"] is not None for row in rows),
        "raw_class_counts": dict(
            Counter(row["raw_class_name"] for row in rows if row["raw_class_name"])
        ),
        "output_class_counts": dict(
            Counter(row["output_class_name"] for row in rows if row["output_class_name"])
        ),
        "class_counts": dict(
            Counter(row["output_class_name"] for row in rows if row["output_class_name"])
        ),
        "timing_ms": {
            key: summarize([row[key] for row in rows if row[key] is not None])
            for key in timing_keys
        },
        "hardware_counters": {
            "stall_before": stall_before,
            "stall_after": stall_after,
            "stall_delta": stall_delta,
            "drop_before": drop_before,
            "drop_after": drop_after,
            "drop_delta": drop_delta,
        },
        "model_load_ms": {
            "locator_reload": round(locator_model_reload_ms, 3),
            "classifier_reload": round(classifier_model_load_ms, 3),
        },
        "preprocessing_contract": {
            "status": (
                "frozen_roi_contract"
                if abs(args.bbox_expansion - pipeline.ROI_MARGIN_EACH_SIDE) < 1e-12
                else "explicit_nonproduction_ab_override"
            ),
            "roi_contract_version": pipeline.ROI_CONTRACT_VERSION,
            "gray": "opencv_bgr2gray",
            "letterbox": "128x128 nearest half_up top_left_floor pad0",
            "bbox_expansion_ratio_each_side": args.bbox_expansion,
            "square_side": "python_round((1 + 2*margin) * max(width, height))",
            "boundary": "shift_complete_square_inside_source_without_padding",
            "slice_bounds": "right_and_bottom_exclusive",
            "classifier_resize": "32x32 linear",
        },
        "temporal_contract": {
            "enabled": not args.disable_temporal,
            "bbox_ema_alpha_new_observation": args.bbox_ema_alpha,
            "miss_hold_frames": args.miss_hold_frames,
            "class_vote_window": args.class_vote_window,
            "class_switch_frames": args.class_switch_frames,
            "held_bbox_policy": "crop_and_classify_current_frame",
            "reset_policy": "clear_bbox_vote_and_output_after_hold_expires",
        },
        "preview_png": str(preview_path),
        "runs": rows,
    }
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("LIVE VIEW RESULT:", result["status"])
    print(
        "INFERENCE/RAW_DETECTED/EFFECTIVE_BBOX/CLASSIFIED:",
        len(rows),
        result["detected_runs"],
        result["effective_bbox_runs"],
        result["classifier_runs"],
    )
    print("RAW CLASS COUNTS:", result["raw_class_counts"])
    print("OUTPUT CLASS COUNTS:", result["output_class_counts"])
    print("TIMING_MS:", json.dumps(result["timing_ms"], ensure_ascii=False, sort_keys=True))
    print("HW COUNTERS:", result["hardware_counters"])
    print("RESULT_JSON:", result_path)
    print("LAST_PREVIEW:", preview_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
