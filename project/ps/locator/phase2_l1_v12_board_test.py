"""Board acceptance for the Phase 2-L1 v12 real Locator overlay.

The test programs only the Phase 2-L1 candidate overlay.  It uploads the
official 1,904-word model, checks all four delivered Conv5 golden maps and PS
Top-1 decoding, then reruns the sealed Phase 1 classifier vectors and GPIO.
"""

from __future__ import annotations

import hashlib
import json
import platform
import struct
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from pynq import Clocks, MMIO, Overlay

from locator_driver import (
    ABI_VERSION,
    AXI_INTC_BASE,
    AXI_INTC_SIZE,
    COMPUTED_DESC_CRC,
    COMPUTED_MODEL_CRC,
    INPUT_FREE_MASK,
    IRQ_ENABLE,
    IRQ_STATUS,
    LOCATOR_ABI_VERSION,
    LOCATOR_V12_DESC_CRC32,
    LOCATOR_V12_MODEL_CRC32,
    OUTPUT_FRAME_ID_0,
    OUTPUT_FRAME_ID_1,
    OUTPUT_VALID_MASK,
    STATUS,
    STATUS_ERROR,
    STATUS_IDLE,
    STATUS_MODEL_VALID,
    LocatorDriver,
    validate_hwh_clock_contract,
)
from phase2_l1_pipeline import decode_top1_raw_map, raw_decode_spec_from_manifest


ROOT = Path(__file__).resolve().parent
BITSTREAM = ROOT / "phase2_l1_cnn_v12.bit"
HWH = ROOT / "phase2_l1_cnn_v12.hwh"
LOCATOR_PACKAGE = ROOT / "locator_v12"
GOLDEN_ROOT = LOCATOR_PACKAGE / "golden_vectors_v1"
CLASS_PACKAGE = ROOT / "classification_active"
RESULT_JSON = ROOT / "phase2_l1_v12_board_test_result.json"


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_mem_words(path: Path):
    return [
        int(line.strip(), 16)
        for line in path.read_text(encoding="ascii").splitlines()
        if line.strip() and not line.lstrip().startswith("//")
    ]


def expected_class(logit_path: Path):
    raw = logit_path.read_bytes()
    logits = struct.unpack("<{}i".format(len(raw) // 4), raw)
    return max(range(len(logits)), key=logits.__getitem__), logits


def wait_mask(mmio, offset, mask, expected, timeout_s=1.0):
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        value = int(mmio.read(offset)) & 0xFFFF_FFFF
        if value & mask == expected:
            return value
        time.sleep(0.0005)
    raise TimeoutError(
        "timeout at offset 0x{:X}: mask=0x{:X}, expected=0x{:X}".format(
            offset, mask, expected
        )
    )


def run_classifier(cnn, image_bytes: bytes, timeout_s=1.0):
    reg_ctrl, reg_status, reg_class_id = 0x00, 0x04, 0x08
    reg_img_addr, reg_img_data = 0x20, 0x24
    check(len(image_bytes) == 1024, "classifier input must contain 1,024 bytes")
    cnn.write(reg_img_addr, 0)
    for pixel in image_bytes:
        cnn.write(reg_img_data, pixel)
    started = time.monotonic()
    cnn.write(reg_ctrl, 1)
    deadline = started + timeout_s
    while time.monotonic() < deadline:
        if cnn.read(reg_status) & 0x4:
            return int(cnn.read(reg_class_id)), (time.monotonic() - started) * 1000.0
        time.sleep(0.0005)
    raise TimeoutError("classifier inference timed out")


def main() -> int:
    started = datetime.now(timezone.utc)
    result = {
        "status": "RUNNING",
        "started_utc": started.isoformat(),
        "board": {
            "platform": platform.platform(),
            "python": sys.version,
            "numpy": np.__version__,
        },
        "artifacts": {},
        "checks": [],
    }

    def record(name, **details):
        row = {"name": name, "status": "PASS"}
        row.update(details)
        result["checks"].append(row)
        print("PASS:", name, json.dumps(details, ensure_ascii=False, sort_keys=True), flush=True)

    required = [
        BITSTREAM,
        HWH,
        ROOT / "locator_driver.py",
        ROOT / "phase2_l1_pipeline.py",
        LOCATOR_PACKAGE / "locator_model_blob.mem",
        LOCATOR_PACKAGE / "locator_layer_layout.json",
        LOCATOR_PACKAGE / "locator_quantization_manifest.json",
        GOLDEN_ROOT / "manifest.json",
        CLASS_PACKAGE / "weights_all.mem",
        CLASS_PACKAGE / "layer_descriptors.mem",
    ]
    for path in required:
        check(path.is_file(), "missing required file: {}".format(path))
        result["artifacts"][str(path.relative_to(ROOT))] = {
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
    record("deployment artifacts present and hashed")

    clock_contract = validate_hwh_clock_contract(HWH)
    record("HWH clock/reset contract", contract=clock_contract)

    overlay_started = time.monotonic()
    overlay = Overlay(str(BITSTREAM))
    record("candidate overlay programmed", load_ms=round((time.monotonic() - overlay_started) * 1000.0, 3))

    driver = LocatorDriver.from_pynq()
    record(
        "fabric clocks enabled before Locator MMIO",
        fclk0_mhz=float(Clocks.fclk0_mhz),
        fclk1_mhz=float(Clocks.fclk1_mhz),
    )
    driver.assert_abi()
    driver.soft_reset()
    status = driver.read(STATUS)
    check(driver.read(ABI_VERSION) == LOCATOR_ABI_VERSION, "Locator ABI mismatch")
    check(status & STATUS_IDLE, "Locator is not idle")
    check(not status & STATUS_ERROR, "Locator error is set after reset")
    check(driver.read(INPUT_FREE_MASK) & 0x3 == 0x3, "input reset mask mismatch")
    check(driver.read(OUTPUT_VALID_MASK) & 0x3 == 0, "output reset mask mismatch")
    record("Locator ABI and reset state", abi="0x{:08X}".format(LOCATOR_ABI_VERSION))

    model_started = time.monotonic()
    quant_manifest = driver.load_v12_package(LOCATOR_PACKAGE, timeout_s=2.0)
    model_ms = (time.monotonic() - model_started) * 1000.0
    check(driver.read(STATUS) & STATUS_MODEL_VALID, "MODEL_VALID was not set")
    check(driver.read(COMPUTED_MODEL_CRC) == LOCATOR_V12_MODEL_CRC32, "model CRC mismatch")
    check(driver.read(COMPUTED_DESC_CRC) == LOCATOR_V12_DESC_CRC32, "descriptor CRC mismatch")
    record(
        "1,904-word model upload and hardware CRC",
        load_ms=round(model_ms, 3),
        model_crc="0x{:08X}".format(LOCATOR_V12_MODEL_CRC32),
        descriptor_crc="0x{:08X}".format(LOCATOR_V12_DESC_CRC32),
    )

    intc = MMIO(AXI_INTC_BASE, AXI_INTC_SIZE)
    intc_ipr, intc_ier, intc_iar, intc_mer = 0x04, 0x08, 0x0C, 0x1C
    locator_irq_mask = 1 << 1
    driver.clear_irq()
    intc.write(intc_iar, locator_irq_mask)
    intc.write(intc_ier, locator_irq_mask)
    intc.write(intc_mer, 0x3)
    driver.write(IRQ_ENABLE, 0x3)

    decode_spec = raw_decode_spec_from_manifest(quant_manifest, clamp_to_locator=True)
    golden_manifest = json.loads((GOLDEN_ROOT / "manifest.json").read_text(encoding="utf-8"))
    locator_rows = []
    held_mask = 0
    held_frame_ids = []
    for case_index, case_entry in enumerate(golden_manifest["cases"]):
        frame_id = 0x1200_0000 + case_index
        case_id = case_entry["case_id"]
        case_dir = GOLDEN_ROOT / case_id
        image = np.fromfile(case_dir / "input_u8.bin", dtype=np.uint8).reshape(128, 128)
        expected = np.fromfile(case_dir / "conv5_acc_i32.bin", dtype="<i4").reshape(5, 16, 16)
        case_json = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
        reference = case_json["ps_reference_decode"]

        inference_started = time.monotonic()
        driver.submit(image, frame_id)
        actual_result = driver.wait_output(frame_id=frame_id, timeout_s=2.0)
        elapsed_ms = (time.monotonic() - inference_started) * 1000.0
        check(np.array_equal(actual_result.raw_map_i32, expected), "{} Conv5 mismatch".format(case_id))
        detection = decode_top1_raw_map(actual_result.raw_map_i32, decode_spec)
        expected_x, expected_y = reference["center_cell_xy"]
        check((detection.cell_x, detection.cell_y) == (expected_x, expected_y), "{} Top-1 cell mismatch".format(case_id))
        check(detection.confidence_i32 == reference["confidence_raw_int32"], "{} raw confidence mismatch".format(case_id))
        expected_detect = detection.confidence_i32 >= decode_spec.confidence_threshold_i32
        check(detection.passed_threshold == expected_detect, "{} threshold mismatch".format(case_id))
        check(detection.bbox_locator_xyxy is not None, "{} invalid bbox geometry".format(case_id))
        check(np.allclose(detection.bbox_locator_xyxy, reference["bbox_xyxy_128"], rtol=0.0, atol=1e-9), "{} bbox mismatch".format(case_id))

        locator_rows.append(
            {
                "case": case_id,
                "frame_id": "0x{:08X}".format(frame_id),
                "output_buffer": actual_result.buffer_id,
                "elapsed_ms": round(elapsed_ms, 3),
                "top1_xy": [detection.cell_x, detection.cell_y],
                "confidence_raw_i32": detection.confidence_i32,
                "detected": detection.passed_threshold,
                "conv5_sha256": hashlib.sha256(actual_result.raw_map_i32.astype("<i4", copy=False).tobytes()).hexdigest(),
            }
        )
        held_mask |= 1 << actual_result.buffer_id
        held_frame_ids.append(frame_id)
        if case_index == 1:
            check(held_mask == 0x3, "first two inferences did not use both output buffers")
            check(driver.read(OUTPUT_VALID_MASK) & 0x3 == 0x3, "both output buffers were not valid")
            check(driver.read(OUTPUT_FRAME_ID_0) == held_frame_ids[0], "buffer 0 Frame ID mismatch")
            check(driver.read(OUTPUT_FRAME_ID_1) == held_frame_ids[1], "buffer 1 Frame ID mismatch")
            driver.release_output(held_mask)
            held_mask = 0
            held_frame_ids = []
        elif case_index > 1:
            driver.release_output(held_mask)
            held_mask = 0
            held_frame_ids = []

    check(driver.read(INPUT_FREE_MASK) & 0x3 == 0x3, "input buffers were not released")
    check(driver.read(OUTPUT_VALID_MASK) & 0x3 == 0, "output buffers were not released")
    record("four full Conv5 maps and PS Top-1/bbox decode", runs=locator_rows)

    check(driver.read(IRQ_STATUS) & 0x1, "completion IRQ status was not set")
    pending = wait_mask(intc, intc_ipr, locator_irq_mask, locator_irq_mask)
    driver.clear_irq()
    intc.write(intc_iar, locator_irq_mask)
    wait_mask(intc, intc_ipr, locator_irq_mask, 0)
    record("Locator IRQ through AXI Interrupt Controller", pending="0x{:08X}".format(pending))

    driver.soft_reset()
    check(driver.read(STATUS) & STATUS_MODEL_VALID, "SOFT_RESET did not preserve MODEL_VALID")
    check(driver.read(OUTPUT_VALID_MASK) & 0x3 == 0, "SOFT_RESET output mask mismatch")
    record(
        "ping/pong Frame ID and SOFT_RESET ownership",
        output_frame_id_0="0x{:08X}".format(driver.read(OUTPUT_FRAME_ID_0)),
        output_frame_id_1="0x{:08X}".format(driver.read(OUTPUT_FRAME_ID_1)),
    )

    cnn = overlay.gesture_top_0
    check(cnn.read(0x0C) == 0x0001_0000, "classifier ABI mismatch")
    weights = read_mem_words(CLASS_PACKAGE / "weights_all.mem")
    descriptors = read_mem_words(CLASS_PACKAGE / "layer_descriptors.mem")
    check(len(weights) == 9838, "classifier weight count mismatch")
    check(len(descriptors) == 64, "classifier descriptor count mismatch")
    cnn.write(0x10, 0)
    for word in weights:
        cnn.write(0x14, word)
    cnn.write(0x28, 0)
    for word in descriptors:
        cnn.write(0x2C, word)

    classifier_rows = []
    for sample in sorted((CLASS_PACKAGE / "golden_vectors").iterdir()):
        if not sample.is_dir():
            continue
        expected_id, logits = expected_class(sample / "fc2_logits_i32.bin")
        actual_id, elapsed_ms = run_classifier(cnn, (sample / "input_u8.bin").read_bytes())
        check(actual_id == expected_id, "{} classifier mismatch".format(sample.name))
        classifier_rows.append(
            {
                "sample": sample.name,
                "expected": expected_id,
                "actual": actual_id,
                "elapsed_ms": round(elapsed_ms, 3),
                "logits": list(logits),
            }
        )
    check(len(classifier_rows) == 8, "expected exactly 8 classifier samples")
    record("preserved gesture_top_0 HIL 8/8", runs=classifier_rows)

    gpio = overlay.axi_gpio_0
    gpio_before = int(gpio.read(0x00)) & 0xF
    gpio.write(0x04, 0)
    gpio.write(0x00, 0xA)
    gpio_readback = int(gpio.read(0x00)) & 0xF
    gpio.write(0x00, gpio_before)
    check(gpio_readback == 0xA, "AXI GPIO readback mismatch")
    record("GPIO/LED register path", readback="0x{:X}".format(gpio_readback))

    driver.write(IRQ_ENABLE, 0)
    intc.write(intc_ier, 0)
    intc.write(intc_mer, 0)
    result["status"] = "PASS"
    result["finished_utc"] = datetime.now(timezone.utc).isoformat()
    result["elapsed_s"] = round((datetime.now(timezone.utc) - started).total_seconds(), 3)
    RESULT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("BOARD TEST RESULT: PASS", flush=True)
    print("RESULT_JSON:", RESULT_JSON, flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:
        failure = {
            "status": "FAIL",
            "finished_utc": datetime.now(timezone.utc).isoformat(),
            "error": "{}: {}".format(type(exc).__name__, exc),
            "traceback": traceback.format_exc(),
        }
        RESULT_JSON.write_text(json.dumps(failure, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("BOARD TEST RESULT: FAIL", flush=True)
        traceback.print_exc()
        raise SystemExit(1)
