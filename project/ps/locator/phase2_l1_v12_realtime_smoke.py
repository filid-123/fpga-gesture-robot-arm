"""Finite USB -> Locator v12 -> PS bbox -> classifier engineering smoke test.

This script does not program the FPGA.  Run the formal v12 static HIL first,
then execute this file against the same isolated deployment directory.  The
Locator letterbox below remains an explicit engineering candidate.  The
classifier crop follows the frozen Phase 2-L1 ROI geometry contract.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import statistics
import sys
import time
from collections import Counter
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
    # Nearest-rank P95 uses ceil(0.95 * N) - 1 for a zero-based list.
    # The previous floor-like expression selected the maximum when N=20.
    p95_index = min(len(ordered) - 1, max(0, (95 * len(ordered) + 99) // 100 - 1))
    return {
        "min": round(ordered[0], 3),
        "mean": round(statistics.fmean(ordered), 3),
        "p95": round(ordered[p95_index], 3),
        "max": round(ordered[-1], 3),
    }


def load_local_pipeline_module(path: Path):
    module_name = "phase2_l1_pipeline_frozen_smoke"
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
    parser = argparse.ArgumentParser()
    parser.add_argument("--deploy-dir", required=True)
    parser.add_argument("--scene", required=True)
    parser.add_argument("--device", default="/dev/video0")
    parser.add_argument("--frames", type=int, default=60)
    parser.add_argument("--infer-every", type=int, default=3)
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--timeout", type=float, default=2.0)
    parser.add_argument("--result", default="")
    parser.add_argument("--no-led", action="store_true")
    parser.add_argument("--bbox-expansion", type=float, default=0.18)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.frames <= 0 or args.infer_every <= 0:
        raise ValueError("frames and infer-every must be positive")
    if args.bbox_expansion < 0.0:
        raise ValueError("bbox-expansion must be non-negative")

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
    from pynq import MMIO
    from locator_driver import DROP_COUNT, STALL_COUNT, STATUS, STATUS_MODEL_VALID, LocatorDriver
    pipeline = load_local_pipeline_module(local_pipeline_path)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    result_path = Path(args.result) if args.result else Path.cwd() / (
        "phase2_l1_v12_realtime_{}_{}.json".format(args.scene, timestamp)
    )
    result_path = result_path.resolve()
    preview_path = result_path.with_name(result_path.stem + "_preview.png")
    if result_path.exists() or preview_path.exists():
        raise FileExistsError("refusing to overwrite result or preview")

    preprocessing_contract = {
        "status": (
            "frozen_roi_with_engineering_locator_preprocess"
            if abs(args.bbox_expansion - pipeline.ROI_MARGIN_EACH_SIDE) < 1e-12
            else "explicit_nonproduction_roi_ab_override"
        ),
        "roi_contract_version": pipeline.ROI_CONTRACT_VERSION,
        "gray": "opencv_bgr2gray",
        "letterbox": {
            "target": [128, 128],
            "pad_value": 0,
            "interpolation": "nearest",
            "resize_rounding": "half_up",
            "odd_padding": "top_left_floor",
        },
        "bbox_crop": {
            "expansion_ratio_each_side": args.bbox_expansion,
            "make_square": True,
            "boundary": "shift_complete_square_inside_source_without_padding",
            "rounding": "python_round",
            "slice_bounds": "right_and_bottom_exclusive",
            "classifier_size": [32, 32],
            "classifier_interpolation": "linear",
        },
    }
    letterbox_spec = pipeline.LetterboxSpec(
        target_width=128,
        target_height=128,
        pad_value=0,
        interpolation="nearest",
        resize_rounding="half_up",
        odd_padding="top_left_floor",
    )

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
        raise RuntimeError("classifier ABI mismatch")
    classifier_model_load_ms = load_classifier_model(cnn, deploy_dir / "classification_active")

    gpio = MMIO(GPIO_BASE, GPIO_SIZE)
    old_gpio_data = int(gpio.read(0x00))
    old_gpio_tri = int(gpio.read(0x04))

    cap = cv2.VideoCapture(args.device, cv2.CAP_V4L2)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
    if not cap.isOpened():
        raise RuntimeError("cannot open camera {}".format(args.device))
    if not args.no_led:
        gpio.write(0x04, 0)

    frame_hashes = set()
    frame_shapes = set()
    frame_brightness = []
    rows = []
    latest_preview = None
    stall_before = locator.read(STALL_COUNT)
    drop_before = locator.read(DROP_COUNT)
    session_started = time.monotonic()
    try:
        for frame_index in range(args.frames):
            frame_started = time.monotonic()
            capture_started = frame_started
            ok, frame = cap.read()
            capture_ms = (time.monotonic() - capture_started) * 1000.0
            if not ok or frame is None:
                raise RuntimeError("camera read failed at frame {}".format(frame_index))
            if frame.dtype != np.uint8 or frame.ndim != 3 or frame.shape[2] != 3:
                raise RuntimeError("unexpected frame {}/{}".format(frame.shape, frame.dtype))
            frame_hashes.add(hashlib.sha256(frame.tobytes()).hexdigest())
            frame_shapes.add(tuple(int(value) for value in frame.shape))
            frame_brightness.append(float(np.mean(frame)))

            if frame_index % args.infer_every:
                continue

            preprocess_started = time.monotonic()
            gray = pipeline.bgr_to_gray_u8(frame, method="opencv_bgr2gray")
            locator_input, transform = pipeline.letterbox_gray_u8(gray, letterbox_spec)
            preprocess_ms = (time.monotonic() - preprocess_started) * 1000.0

            frame_id = (0x9000_0000 + frame_index) & 0xFFFF_FFFF
            submit_started = time.monotonic()
            input_buffer = locator.submit(locator_input, frame_id)
            locator_submit_ms = (time.monotonic() - submit_started) * 1000.0

            loc_result = None
            try:
                wait_started = time.monotonic()
                loc_result = locator.wait_output(frame_id=frame_id, timeout_s=args.timeout)
                locator_wait_read_ms = (time.monotonic() - wait_started) * 1000.0

                decode_started = time.monotonic()
                detection = pipeline.decode_top1_raw_map(loc_result.raw_map_i32, decode_spec)
                source_bbox = None
                crop_box = None
                class_id = None
                class_name = None
                classifier_upload_ms = None
                classifier_infer_ms = None
                crop_error = None

                if detection.passed_threshold and detection.bbox_locator_xyxy is not None:
                    source_bbox = pipeline.locator_bbox_to_source(
                        detection.bbox_locator_xyxy, transform, clip_to_source=True
                    )
                    try:
                        classifier_input, crop_box = pipeline.classifier_bbox_crop_u8(
                            frame,
                            source_bbox,
                            expansion_ratio=args.bbox_expansion,
                            make_square=True,
                            clip_to_source=True,
                            output_size=32,
                            grayscale_method="opencv_bgr2gray",
                            interpolation="linear",
                        )
                        class_id, classifier_upload_ms, classifier_infer_ms = run_classifier(
                            cnn, classifier_input, args.timeout
                        )
                        class_name = CLASS_NAMES[class_id]
                    except ValueError as exc:
                        crop_error = str(exc)

                if not args.no_led:
                    gpio.write(0x00, 0 if class_id is None else (1 << class_id))

                decode_crop_class_ms = (time.monotonic() - decode_started) * 1000.0
                pipeline_ms = (time.monotonic() - preprocess_started) * 1000.0
                frame_to_led_ms = (time.monotonic() - frame_started) * 1000.0

                preview = frame.copy()
                if source_bbox is not None:
                    x0, y0, x1, y1 = [int(round(value)) for value in source_bbox]
                    color = (0, 255, 0) if detection.passed_threshold else (0, 0, 255)
                    cv2.rectangle(preview, (x0, y0), (x1, y1), color, 2)
                label = "raw={} class={}".format(
                    detection.confidence_i32, class_name or "none"
                )
                cv2.putText(preview, label, (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
                latest_preview = preview

                rows.append(
                    {
                        "frame_index": frame_index,
                        "frame_id": "0x{:08X}".format(frame_id),
                        "input_buffer": input_buffer,
                        "output_buffer": loc_result.buffer_id,
                        "capture_ms": round(capture_ms, 3),
                        "preprocess_ms": round(preprocess_ms, 3),
                        "locator_submit_ms": round(locator_submit_ms, 3),
                        "locator_wait_read_ms": round(locator_wait_read_ms, 3),
                        "decode_crop_class_ms": round(decode_crop_class_ms, 3),
                        "classifier_upload_ms": None if classifier_upload_ms is None else round(classifier_upload_ms, 3),
                        "classifier_infer_ms": None if classifier_infer_ms is None else round(classifier_infer_ms, 3),
                        "pipeline_ms": round(pipeline_ms, 3),
                        "frame_to_led_ms": round(frame_to_led_ms, 3),
                        "confidence_raw_i32": detection.confidence_i32,
                        "threshold_raw_i32": decode_spec.confidence_threshold_i32,
                        "detected": detection.passed_threshold,
                        "valid_geometry": detection.valid_geometry,
                        "top1_xy": [detection.cell_x, detection.cell_y],
                        "bbox_locator_xyxy": None if detection.bbox_locator_xyxy is None else list(detection.bbox_locator_xyxy),
                        "bbox_source_xyxy": None if source_bbox is None else list(source_bbox),
                        "crop_box_xyxy": None if crop_box is None else list(crop_box),
                        "crop_error": crop_error,
                        "class_id": class_id,
                        "class_name": class_name,
                    }
                )
            finally:
                if loc_result is not None:
                    locator.release_output(1 << loc_result.buffer_id)
    finally:
        cap.release()
        if not args.no_led:
            gpio.write(0x00, old_gpio_data)
            gpio.write(0x04, old_gpio_tri)

    expected_runs = (args.frames + args.infer_every - 1) // args.infer_every
    if len(frame_hashes) < 2:
        raise RuntimeError("camera frames are frozen")
    if len(rows) != expected_runs:
        raise RuntimeError("completed {}/{} inference runs".format(len(rows), expected_runs))
    stall_after = locator.read(STALL_COUNT)
    drop_after = locator.read(DROP_COUNT)
    drop_delta = (drop_after - drop_before) & 0xFFFF_FFFF
    stall_delta = (stall_after - stall_before) & 0xFFFF_FFFF
    if drop_delta != 0:
        raise RuntimeError("hardware DROP_COUNT increased by {}".format(drop_delta))
    if latest_preview is None or not cv2.imwrite(str(preview_path), latest_preview):
        raise RuntimeError("failed to save preview")

    timing_keys = (
        "capture_ms",
        "preprocess_ms",
        "locator_submit_ms",
        "locator_wait_read_ms",
        "decode_crop_class_ms",
        "classifier_upload_ms",
        "classifier_infer_ms",
        "pipeline_ms",
        "frame_to_led_ms",
    )
    timing = {
        key: summarize([row[key] for row in rows if row[key] is not None])
        for key in timing_keys
    }
    class_counts = Counter(row["class_name"] for row in rows if row["class_name"] is not None)
    result = {
        "status": "PASS",
        "scope": "engineering_smoke_not_accuracy_acceptance",
        "finished_utc": datetime.now(timezone.utc).isoformat(),
        "scene": args.scene,
        "deploy_dir": str(deploy_dir),
        "device": args.device,
        "requested_resolution": [args.width, args.height],
        "actual_shapes_hwc": [list(shape) for shape in sorted(frame_shapes)],
        "frames": args.frames,
        "unique_frame_hashes": len(frame_hashes),
        "inference_runs": len(rows),
        "ps_source_drop_count": args.frames - len(rows),
        "detected_runs": sum(bool(row["detected"]) for row in rows),
        "valid_bbox_runs": sum(row["bbox_source_xyxy"] is not None for row in rows),
        "classifier_runs": sum(row["class_id"] is not None for row in rows),
        "class_counts": dict(class_counts),
        "brightness": summarize(frame_brightness),
        "timing_ms": timing,
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
        "preprocessing_contract": preprocessing_contract,
        "elapsed_s": round(time.monotonic() - session_started, 3),
        "preview_png": str(preview_path),
        "runs": rows,
    }
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("REALTIME SMOKE RESULT: PASS")
    print("SCENE:", args.scene)
    print("FRAMES/UNIQUE/INFER:", args.frames, len(frame_hashes), len(rows))
    print("DETECTED/BBOX/CLASSIFIED:", result["detected_runs"], result["valid_bbox_runs"], result["classifier_runs"])
    print("CLASS COUNTS:", result["class_counts"])
    print("BRIGHTNESS:", result["brightness"])
    print("TIMING_MS:", json.dumps(timing, ensure_ascii=False, sort_keys=True))
    print("HW COUNTERS:", result["hardware_counters"])
    print("RESULT_JSON:", result_path)
    print("PREVIEW_PNG:", preview_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
