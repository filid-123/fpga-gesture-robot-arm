"""Collect labeled Phase 2-L1 hard samples on an accepted PYNQ overlay.

The tool never programs an Overlay.  One invocation represents exactly one
operator-controlled truth label.  It saves only selected failures (plus sparse
correct controls), records the exact frozen preprocessing artifacts, and can
package the completed session as a verified ZIP for the algorithm team.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import time
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import phase2_l1_v12_live_view as live


FORMAT_VERSION = "phase2_l1_failure_batch_v1"
TRUTH_CLASS_IDS = {
    "no_hand": None,
    "fist": 1,
    "mute": 2,
    "palm": 3,
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_component(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value)).strip("._-")
    if not cleaned:
        raise ValueError("session must contain at least one ASCII letter or digit")
    return cleaned[:80]


def decide_sample_type(
    *,
    truth: str,
    threshold_passed: bool,
    locator_usable: bool,
    raw_class_id,
    correct_ordinal: int,
    correct_control_every: int,
):
    """Return the training-review category for one raw inference result."""

    if truth not in TRUTH_CLASS_IDS:
        raise ValueError("unsupported truth label")
    if correct_control_every < 0:
        raise ValueError("correct_control_every must be non-negative")

    expected_class_id = TRUTH_CLASS_IDS[truth]
    if truth == "no_hand":
        return "locator_false_positive" if threshold_passed else None

    if not locator_usable:
        return "locator_false_negative"
    if raw_class_id is None:
        return "classifier_preprocess_error"
    if int(raw_class_id) != expected_class_id:
        return "classifier_misclassification"
    if correct_control_every and correct_ordinal % correct_control_every == 0:
        return "correct_control"
    return None


def write_json(path: Path, value) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def save_sample_artifacts(
    *,
    cv2,
    sample_dir: Path,
    source_gray_u8,
    locator_input_u8,
    conv5_raw_i32,
    classifier_roi_u8,
    preview_bgr,
    metadata: dict,
) -> dict:
    """Write one sample atomically enough for Ctrl+C-safe session recovery."""

    import numpy as np

    sample_dir.mkdir(parents=False, exist_ok=False)
    artifacts = {}

    def save_png(name: str, image) -> None:
        path = sample_dir / name
        array = np.ascontiguousarray(image, dtype=np.uint8)
        if not cv2.imwrite(str(path), array):
            raise RuntimeError("failed to save {}".format(path))
        artifacts[name] = {
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }

    save_png("source_gray.png", source_gray_u8)
    save_png("locator_input_128x128.png", locator_input_u8)

    raw_path = sample_dir / "conv5_raw_i32.bin"
    raw = np.ascontiguousarray(conv5_raw_i32, dtype="<i4")
    if raw.shape != (5, 16, 16):
        raise ValueError("Conv5 raw map must have shape (5, 16, 16)")
    raw_path.write_bytes(raw.tobytes(order="C"))
    if raw_path.stat().st_size != 5120:
        raise RuntimeError("Conv5 raw map must contain exactly 5,120 bytes")
    artifacts[raw_path.name] = {
        "bytes": raw_path.stat().st_size,
        "sha256": sha256_file(raw_path),
    }

    if classifier_roi_u8 is not None:
        save_png("classifier_roi_32x32.png", classifier_roi_u8)
    if preview_bgr is not None:
        preview_path = sample_dir / "preview.jpg"
        if not cv2.imwrite(
            str(preview_path), preview_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 82]
        ):
            raise RuntimeError("failed to save {}".format(preview_path))
        artifacts[preview_path.name] = {
            "bytes": preview_path.stat().st_size,
            "sha256": sha256_file(preview_path),
            "training_use": "forbidden_annotated_review_only",
        }

    metadata = dict(metadata)
    metadata["artifacts"] = artifacts
    write_json(sample_dir / "metadata.json", metadata)
    return metadata


def package_session(session_dir: Path, *, create_zip: bool) -> dict:
    """Create a per-file SHA manifest and optionally a CRC-verified ZIP."""

    session_dir = Path(session_dir).resolve()
    if not session_dir.is_dir():
        raise FileNotFoundError(session_dir)

    manifest_path = session_dir / "sha256_manifest.json"
    files = [
        path
        for path in sorted(session_dir.rglob("*"))
        if path.is_file() and path != manifest_path
    ]
    manifest = {
        "format": FORMAT_VERSION,
        "session": session_dir.name,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "file_count": len(files),
        "files": [
            {
                "path": path.relative_to(session_dir).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            for path in files
        ],
    }
    write_json(manifest_path, manifest)

    result = {
        "manifest": str(manifest_path),
        "manifest_entries": len(files),
        "zip": None,
        "zip_bytes": None,
        "zip_sha256": None,
        "zip_entries": None,
    }
    if not create_zip:
        return result

    zip_path = session_dir.parent / (session_dir.name + ".zip")
    if zip_path.exists():
        raise FileExistsError("refusing to overwrite {}".format(zip_path))
    with zipfile.ZipFile(
        str(zip_path), "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6
    ) as archive:
        for path in sorted(session_dir.rglob("*")):
            if path.is_file():
                archive.write(
                    str(path),
                    arcname=(
                        Path(session_dir.name) / path.relative_to(session_dir)
                    ).as_posix(),
                )
    with zipfile.ZipFile(str(zip_path), "r") as archive:
        bad_name = archive.testzip()
        if bad_name is not None:
            raise RuntimeError("ZIP CRC failed at {}".format(bad_name))
        zip_entries = len(archive.infolist())
    result.update(
        {
            "zip": str(zip_path),
            "zip_bytes": zip_path.stat().st_size,
            "zip_sha256": sha256_file(zip_path),
            "zip_entries": zip_entries,
        }
    )
    return result


def make_preview(
    *,
    cv2,
    frame_bgr,
    truth: str,
    sample_type: str,
    confidence_i32: int,
    threshold_i32: int,
    raw_class_name,
    raw_bbox,
    stable_bbox,
    crop_box,
):
    preview = frame_bgr.copy()
    height, width = preview.shape[:2]
    for box, color in (
        (raw_bbox, (0, 255, 0)),
        (stable_bbox, (0, 255, 255)),
    ):
        rectangle = live.rounded_draw_box(box, width, height)
        if rectangle is not None:
            cv2.rectangle(preview, rectangle[0], rectangle[1], color, 2)
    if crop_box is not None:
        x0, y0, x1, y1 = (int(value) for value in crop_box)
        rectangle = live.rounded_draw_box((x0, y0, x1 - 1, y1 - 1), width, height)
        if rectangle is not None:
            cv2.rectangle(preview, rectangle[0], rectangle[1], (255, 255, 0), 2)

    line1 = "truth={}  type={}".format(truth, sample_type)
    line2 = "raw={} threshold={} class={}".format(
        confidence_i32, threshold_i32, raw_class_name or "none"
    )
    cv2.rectangle(preview, (0, 0), (width - 1, 58), (0, 0, 0), -1)
    cv2.putText(
        preview, line1, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.52,
        (0, 255, 255), 2, cv2.LINE_AA
    )
    cv2.putText(
        preview, line2, (8, 48), cv2.FONT_HERSHEY_SIMPLEX, 0.48,
        (255, 255, 255), 1, cv2.LINE_AA
    )
    return preview


def parse_args():
    parser = argparse.ArgumentParser(
        description="Collect labeled Locator/classifier failures and create a handoff ZIP"
    )
    parser.add_argument("--deploy-dir", required=True)
    parser.add_argument("--truth", required=True, choices=tuple(TRUTH_CLASS_IDS))
    parser.add_argument("--session", required=True)
    parser.add_argument("--device", default="/dev/video0")
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--duration", type=float, default=120.0)
    parser.add_argument("--warmup", type=float, default=3.0)
    parser.add_argument("--timeout", type=float, default=2.0)
    parser.add_argument("--max-samples", type=int, default=300)
    parser.add_argument("--min-save-gap", type=float, default=0.5)
    parser.add_argument("--correct-control-every", type=int, default=20)
    parser.add_argument(
        "--output-root", default="/home/xilinx/phase2_l1_failure_data"
    )
    parser.add_argument("--no-preview", action="store_true")
    parser.add_argument("--no-zip", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.width <= 0 or args.height <= 0:
        raise ValueError("width and height must be positive")
    if args.duration < 0.0 or args.warmup < 0.0:
        raise ValueError("duration and warmup must be non-negative")
    if args.timeout <= 0.0:
        raise ValueError("timeout must be positive")
    if args.max_samples < 0 or args.correct_control_every < 0:
        raise ValueError("sample limits must be non-negative")
    if args.min_save_gap < 0.0:
        raise ValueError("min-save-gap must be non-negative")

    deploy_dir = Path(args.deploy_dir).resolve()
    script_dir = Path(__file__).resolve().parent
    pipeline_path = script_dir / "phase2_l1_pipeline.py"
    live_view_path = script_dir / "phase2_l1_v12_live_view.py"
    quant_manifest_path = (
        deploy_dir / "locator_v12" / "locator_quantization_manifest.json"
    )
    classifier_dir = deploy_dir / "classification_active"
    required = [
        deploy_dir / "locator_driver.py",
        quant_manifest_path,
        classifier_dir / "weights_all.mem",
        classifier_dir / "layer_descriptors.mem",
        pipeline_path,
        live_view_path,
    ]
    for path in required:
        if not path.is_file():
            raise FileNotFoundError(path)
    if str(deploy_dir) not in sys.path:
        sys.path.insert(0, str(deploy_dir))

    import cv2
    import numpy as np
    from pynq import MMIO
    from locator_driver import (
        ABI_VERSION,
        COMPUTED_DESC_CRC,
        COMPUTED_MODEL_CRC,
        DESC_VERSION,
        DROP_COUNT,
        MODEL_VERSION,
        STALL_COUNT,
        STATUS,
        STATUS_MODEL_VALID,
        LocatorDriver,
    )

    pipeline = live.load_local_pipeline_module(pipeline_path)
    if abs(pipeline.ROI_MARGIN_EACH_SIDE - 0.18) >= 1e-12:
        raise RuntimeError("failure capture requires the frozen 18% ROI contract")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    session_name = "session_{}_{}_{}".format(
        timestamp, args.truth, safe_component(args.session)
    )
    output_root = Path(args.output_root).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    session_dir = output_root / session_name
    session_dir.mkdir(parents=False, exist_ok=False)
    samples_dir = session_dir / "samples"
    samples_dir.mkdir()
    contract_dir = session_dir / "contract"
    contract_dir.mkdir()
    shutil.copy2(str(pipeline_path), str(contract_dir / pipeline_path.name))
    shutil.copy2(
        str(quant_manifest_path), str(contract_dir / quant_manifest_path.name)
    )
    for name in ("package_manifest.json", "quantization_manifest.json"):
        source = classifier_dir / name
        if source.is_file():
            shutil.copy2(str(source), str(contract_dir / ("classifier_" + name)))

    quant_manifest = json.loads(quant_manifest_path.read_text(encoding="utf-8"))
    letterbox_spec = pipeline.LetterboxSpec(
        target_width=128,
        target_height=128,
        pad_value=0,
        interpolation="nearest",
        resize_rounding="half_up",
        odd_padding="top_left_floor",
    )
    temporal_spec = pipeline.TemporalFilterSpec(
        bbox_ema_alpha=0.30,
        miss_hold_frames=3,
        class_vote_window=5,
        class_switch_frames=2,
        class_count=len(live.CLASS_NAMES),
    )
    bbox_filter = pipeline.BboxEmaHold(temporal_spec)

    locator = LocatorDriver.from_pynq()
    locator.assert_abi()
    locator.soft_reset()
    locator_model_reload_ms = 0.0
    if not locator.read(STATUS) & STATUS_MODEL_VALID:
        started = time.monotonic()
        quant_manifest = locator.load_v12_package(
            deploy_dir / "locator_v12", timeout_s=args.timeout
        )
        locator_model_reload_ms = (time.monotonic() - started) * 1000.0
    decode_spec = pipeline.raw_decode_spec_from_manifest(
        quant_manifest, clamp_to_locator=True
    )

    cnn = MMIO(live.CLASSIFIER_BASE, live.CLASSIFIER_SIZE)
    if int(cnn.read(live.REG_ABI)) != 0x0001_0000:
        raise RuntimeError("classifier ABI mismatch; run the accepted v12 board test first")
    classifier_model_load_ms = live.load_classifier_model(cnn, classifier_dir)

    provenance = {
        "collector_sha256": sha256_file(Path(__file__).resolve()),
        "pipeline_sha256": sha256_file(pipeline_path),
        "live_view_helpers_sha256": sha256_file(live_view_path),
        "locator_quantization_manifest_sha256": sha256_file(quant_manifest_path),
        "classifier_weights_sha256": sha256_file(classifier_dir / "weights_all.mem"),
        "classifier_descriptors_sha256": sha256_file(
            classifier_dir / "layer_descriptors.mem"
        ),
        "locator_hardware": {
            "abi": "0x{:08X}".format(locator.read(ABI_VERSION)),
            "model_crc": "0x{:08X}".format(locator.read(COMPUTED_MODEL_CRC)),
            "descriptor_crc": "0x{:08X}".format(locator.read(COMPUTED_DESC_CRC)),
            "model_version": "0x{:08X}".format(locator.read(MODEL_VERSION)),
            "descriptor_version": "0x{:08X}".format(locator.read(DESC_VERSION)),
        },
    }
    for name in (
        "phase2_l1_cnn_v12.bit",
        "phase2_l1_cnn_v12.hwh",
        "deploy_sha256.json",
    ):
        path = deploy_dir / name
        if path.is_file():
            provenance[name + "_sha256"] = sha256_file(path)

    cap = None
    status = "COMPLETE"
    error_text = None
    interrupted = False
    inference_runs = 0
    saved_samples = 0
    correct_ordinal = 0
    raw_detected_runs = 0
    usable_locator_runs = 0
    classifier_runs = 0
    frame_shapes = set()
    candidate_counts = Counter()
    saved_counts = Counter()
    raw_class_counts = Counter()
    input_buffers = Counter()
    output_buffers = Counter()
    last_saved_at = {}
    timing_rows = []
    samples_jsonl = session_dir / "samples.jsonl"
    session_started_utc = datetime.now(timezone.utc).isoformat()
    session_started = time.monotonic()
    stall_before = locator.read(STALL_COUNT)
    drop_before = locator.read(DROP_COUNT)

    try:
        cap = cv2.VideoCapture(args.device, cv2.CAP_V4L2)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        if not cap.isOpened():
            raise RuntimeError("cannot open camera {}".format(args.device))

        warmup_deadline = time.monotonic() + args.warmup
        while time.monotonic() < warmup_deadline:
            ok, _ = cap.read()
            if not ok:
                raise RuntimeError("camera read failed during warmup")

        bbox_filter.reset()
        collection_started = time.monotonic()
        print("FAILURE CAPTURE STARTED")
        print("TRUTH:", args.truth)
        print("SESSION_DIR:", session_dir)
        if args.truth == "no_hand":
            print("RULE: no real, reflected, photographed or screen hand may appear")
        else:
            print("RULE: keep exactly one {} visible for the entire session".format(args.truth))

        while args.duration == 0.0 or time.monotonic() - collection_started < args.duration:
            if args.max_samples and saved_samples >= args.max_samples:
                break
            loop_started = time.monotonic()
            ok, frame = cap.read()
            if not ok or frame is None:
                raise RuntimeError("camera read failed")
            if frame.dtype != np.uint8 or frame.ndim != 3 or frame.shape[2] != 3:
                raise RuntimeError("unexpected frame {}/{}".format(frame.shape, frame.dtype))
            frame_shapes.add(tuple(int(value) for value in frame.shape))

            gray = pipeline.bgr_to_gray_u8(frame, method="opencv_bgr2gray")
            locator_input, transform = pipeline.letterbox_gray_u8(gray, letterbox_spec)
            frame_id = (0xC000_0000 + inference_runs) & 0xFFFF_FFFF
            input_buffer = locator.submit(locator_input, frame_id)
            input_buffers[input_buffer] += 1

            loc_result = None
            try:
                loc_result = locator.wait_output(frame_id=frame_id, timeout_s=args.timeout)
                output_buffers[loc_result.buffer_id] += 1
                detection = pipeline.decode_top1_raw_map(
                    loc_result.raw_map_i32, decode_spec
                )
                inference_runs += 1
                if detection.passed_threshold:
                    raw_detected_runs += 1

                raw_source_bbox = None
                if detection.passed_threshold and detection.bbox_locator_xyxy is not None:
                    raw_source_bbox = pipeline.locator_bbox_to_source(
                        detection.bbox_locator_xyxy,
                        transform,
                        clip_to_source=True,
                    )
                locator_usable = raw_source_bbox is not None
                if locator_usable:
                    usable_locator_runs += 1

                bbox_state = bbox_filter.update(raw_source_bbox)
                stable_source_bbox = bbox_state.bbox_xyxy
                classifier_input = None
                crop_box = None
                raw_class_id = None
                raw_class_name = None
                crop_error = None

                # Classifier training samples are admitted only on a current,
                # usable raw detection. Held boxes remain metadata for Locator
                # false negatives and never feed the classification dataset.
                if locator_usable and stable_source_bbox is not None:
                    try:
                        classifier_input, crop_box = pipeline.classifier_bbox_crop_u8(
                            frame,
                            stable_source_bbox,
                            expansion_ratio=pipeline.ROI_MARGIN_EACH_SIDE,
                            make_square=True,
                            clip_to_source=True,
                            output_size=32,
                            grayscale_method="opencv_bgr2gray",
                            interpolation="linear",
                        )
                        raw_class_id, upload_ms, infer_ms = live.run_classifier(
                            cnn, classifier_input, args.timeout
                        )
                        classifier_runs += 1
                        raw_class_name = live.CLASS_NAMES[raw_class_id]
                        raw_class_counts[raw_class_name] += 1
                    except ValueError as exc:
                        crop_error = str(exc)
                        upload_ms = None
                        infer_ms = None
                else:
                    upload_ms = None
                    infer_ms = None

                expected_class_id = TRUTH_CLASS_IDS[args.truth]
                if (
                    expected_class_id is not None
                    and locator_usable
                    and raw_class_id == expected_class_id
                ):
                    correct_ordinal += 1

                sample_type = decide_sample_type(
                    truth=args.truth,
                    threshold_passed=detection.passed_threshold,
                    locator_usable=locator_usable,
                    raw_class_id=raw_class_id,
                    correct_ordinal=correct_ordinal,
                    correct_control_every=args.correct_control_every,
                )
                now = time.monotonic()
                should_save = False
                if sample_type is not None:
                    candidate_counts[sample_type] += 1
                    should_save = (
                        now - last_saved_at.get(sample_type, float("-inf"))
                        >= args.min_save_gap
                    )

                if should_save:
                    saved_samples += 1
                    sample_dir = samples_dir / "sample_{:06d}_{}".format(
                        saved_samples, sample_type
                    )
                    preview = None
                    if not args.no_preview:
                        preview = make_preview(
                            cv2=cv2,
                            frame_bgr=frame,
                            truth=args.truth,
                            sample_type=sample_type,
                            confidence_i32=detection.confidence_i32,
                            threshold_i32=decode_spec.confidence_threshold_i32,
                            raw_class_name=raw_class_name,
                            raw_bbox=raw_source_bbox,
                            stable_bbox=stable_source_bbox,
                            crop_box=crop_box,
                        )
                    metadata = {
                        "format": FORMAT_VERSION,
                        "session": session_name,
                        "sample_index": saved_samples,
                        "sample_path": sample_dir.relative_to(session_dir).as_posix(),
                        "captured_utc": datetime.now(timezone.utc).isoformat(),
                        "truth": args.truth,
                        "truth_class_id": expected_class_id,
                        "failure_type": sample_type,
                        "training_eligibility": {
                            "locator": (
                                "eligible_negative"
                                if sample_type == "locator_false_positive"
                                else "requires_manual_bbox"
                                if sample_type == "locator_false_negative"
                                else "not_primary_locator_sample"
                            ),
                            "classifier": (
                                "eligible_exact_runtime_roi"
                                if sample_type
                                in {"classifier_misclassification", "correct_control"}
                                else "forbidden"
                            ),
                        },
                        "frame_id": "0x{:08X}".format(frame_id),
                        "frame_shape_hwc": list(frame.shape),
                        "input_buffer": input_buffer,
                        "output_buffer": loc_result.buffer_id,
                        "confidence_raw_i32": detection.confidence_i32,
                        "threshold_raw_i32": decode_spec.confidence_threshold_i32,
                        "threshold_passed": detection.passed_threshold,
                        "valid_geometry": detection.valid_geometry,
                        "locator_usable": locator_usable,
                        "top1_xy": [detection.cell_x, detection.cell_y],
                        "bbox_locator_xyxy": (
                            None
                            if detection.bbox_locator_xyxy is None
                            else list(detection.bbox_locator_xyxy)
                        ),
                        "raw_bbox_source_xyxy": (
                            None if raw_source_bbox is None else list(raw_source_bbox)
                        ),
                        "stable_bbox_source_xyxy": (
                            None
                            if stable_source_bbox is None
                            else list(stable_source_bbox)
                        ),
                        "held_bbox": bbox_state.held,
                        "miss_count": bbox_state.miss_count,
                        "crop_box_xyxy": None if crop_box is None else list(crop_box),
                        "crop_error": crop_error,
                        "raw_class_id": raw_class_id,
                        "raw_class_name": raw_class_name,
                        "conv5": {
                            "shape": [5, 16, 16],
                            "layout": "CHW row-major",
                            "dtype": "signed int32 little-endian",
                        },
                        "preprocessing": {
                            "gray": "opencv_bgr2gray",
                            "letterbox": "128x128 nearest half_up top_left_floor pad0",
                            "roi_contract": pipeline.ROI_CONTRACT_VERSION,
                            "roi_margin_each_side": pipeline.ROI_MARGIN_EACH_SIDE,
                        },
                        "classifier_upload_ms": (
                            None if upload_ms is None else round(upload_ms, 3)
                        ),
                        "classifier_infer_ms": (
                            None if infer_ms is None else round(infer_ms, 3)
                        ),
                    }
                    metadata = save_sample_artifacts(
                        cv2=cv2,
                        sample_dir=sample_dir,
                        source_gray_u8=gray,
                        locator_input_u8=locator_input,
                        conv5_raw_i32=loc_result.raw_map_i32,
                        classifier_roi_u8=classifier_input,
                        preview_bgr=preview,
                        metadata=metadata,
                    )
                    with samples_jsonl.open("a", encoding="utf-8") as stream:
                        stream.write(json.dumps(metadata, ensure_ascii=False) + "\n")
                    saved_counts[sample_type] += 1
                    last_saved_at[sample_type] = now
                    print(
                        "SAVED {}/{}: {} raw={} class={}".format(
                            saved_samples,
                            args.max_samples if args.max_samples else "unlimited",
                            sample_type,
                            detection.confidence_i32,
                            raw_class_name or "none",
                        )
                    )

                timing_rows.append((time.monotonic() - loop_started) * 1000.0)
            finally:
                if loc_result is not None:
                    locator.release_output(1 << loc_result.buffer_id)
    except KeyboardInterrupt:
        interrupted = True
        status = "STOPPED_BY_USER"
        print("CAPTURE STOP REQUESTED")
    except Exception as exc:
        status = "ERROR"
        error_text = "{}: {}".format(type(exc).__name__, exc)
    finally:
        if cap is not None:
            cap.release()

    stall_after = locator.read(STALL_COUNT)
    drop_after = locator.read(DROP_COUNT)
    stall_delta = (stall_after - stall_before) & 0xFFFF_FFFF
    drop_delta = (drop_after - drop_before) & 0xFFFF_FFFF
    if drop_delta and error_text is None:
        status = "ERROR"
        error_text = "hardware DROP_COUNT increased by {}".format(drop_delta)

    session = {
        "format": FORMAT_VERSION,
        "status": status,
        "error": error_text,
        "interrupted": interrupted,
        "session": session_name,
        "session_label": args.session,
        "deploy_dir": str(deploy_dir),
        "truth": args.truth,
        "truth_class_id": TRUTH_CLASS_IDS[args.truth],
        "started_utc": session_started_utc,
        "finished_utc": datetime.now(timezone.utc).isoformat(),
        "elapsed_s": round(time.monotonic() - session_started, 3),
        "collection_duration_requested_s": args.duration,
        "camera_warmup_s": args.warmup,
        "device": args.device,
        "requested_resolution": [args.width, args.height],
        "actual_shapes_hwc": [list(shape) for shape in sorted(frame_shapes)],
        "inference_runs": inference_runs,
        "raw_detected_runs": raw_detected_runs,
        "usable_locator_runs": usable_locator_runs,
        "classifier_runs": classifier_runs,
        "candidate_counts": dict(candidate_counts),
        "saved_counts": dict(saved_counts),
        "saved_samples": saved_samples,
        "raw_class_counts": dict(raw_class_counts),
        "selection": {
            "max_samples": args.max_samples,
            "min_save_gap_s_per_type": args.min_save_gap,
            "correct_control_every": args.correct_control_every,
            "held_roi_classifier_training": "forbidden",
        },
        "preprocessing": {
            "roi_contract": pipeline.ROI_CONTRACT_VERSION,
            "roi_margin_each_side": pipeline.ROI_MARGIN_EACH_SIDE,
            "bbox_ema_alpha": temporal_spec.bbox_ema_alpha,
            "confidence_threshold_i32": decode_spec.confidence_threshold_i32,
        },
        "hardware_counters": {
            "stall_before": stall_before,
            "stall_after": stall_after,
            "stall_delta": stall_delta,
            "drop_before": drop_before,
            "drop_after": drop_after,
            "drop_delta": drop_delta,
        },
        "buffers": {
            "input": dict(input_buffers),
            "output": dict(output_buffers),
        },
        "loop_ms": live.summarize(timing_rows),
        "model_load_ms": {
            "locator_reload": round(locator_model_reload_ms, 3),
            "classifier_reload": round(classifier_model_load_ms, 3),
        },
        "provenance": provenance,
    }
    write_json(session_dir / "session.json", session)
    package = package_session(session_dir, create_zip=not args.no_zip)

    print("CAPTURE RESULT:", status)
    print("INFERENCE/SAVED:", inference_runs, saved_samples)
    print("CANDIDATES:", dict(candidate_counts))
    print("SAVED COUNTS:", dict(saved_counts))
    print("HW COUNTERS:", session["hardware_counters"])
    print("SESSION_DIR:", session_dir)
    print("MANIFEST:", package["manifest"])
    if package["zip"] is not None:
        print("ZIP:", package["zip"])
        print("ZIP BYTES:", package["zip_bytes"])
        print("ZIP SHA-256:", package["zip_sha256"])

    if error_text is not None:
        raise RuntimeError(error_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
