"""Non-interactive PYNQ acceptance for the isolated Phase 2-L1 Stub overlay.

The script is intentionally self-contained for an unattended board run.  It
programs only the PL, writes only result files beside this script, and validates
both the new Locator skeleton and the preserved Phase 1 classifier path.
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

from locator_driver import validate_hwh_clock_contract


ROOT = Path(__file__).resolve().parent
BITSTREAM = ROOT / "phase2_l1_stub.bit"
HWH = ROOT / "phase2_l1_stub.hwh"
CLASS_PACKAGE = ROOT / "classification_active"
RESULT_JSON = ROOT / "board_test_result_v2.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def read_mem_words(path: Path):
    words = []
    for line in path.read_text(encoding="utf-8").splitlines():
        token = line.strip()
        if token and not token.startswith("//"):
            words.append(int(token, 16))
    return words


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


def main():
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
        entry = {"name": name, "status": "PASS"}
        entry.update(details)
        result["checks"].append(entry)
        print(
            "PASS:",
            name,
            json.dumps(details, ensure_ascii=False, sort_keys=True),
            flush=True,
        )

    required = [BITSTREAM, HWH, ROOT / "locator_driver.py"]
    required += [
        CLASS_PACKAGE / "weights_all.mem",
        CLASS_PACKAGE / "layer_descriptors.mem",
        CLASS_PACKAGE / "package_manifest.json",
        CLASS_PACKAGE / "quantization_manifest.json",
    ]
    for path in required:
        check(path.is_file(), "missing required file: {}".format(path))
        result["artifacts"][str(path.relative_to(ROOT))] = {
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
    record("deployment files and hashes")

    clock_contract = validate_hwh_clock_contract(HWH)
    record("HWH FCLK1 safety contract", clocks=clock_contract)

    overlay_t0 = time.monotonic()
    overlay = Overlay(str(BITSTREAM))
    overlay_ms = (time.monotonic() - overlay_t0) * 1000.0
    expected_ips = {
        "gesture_top_0": (0x40000000, 0x1000),
        "axi_gpio_0": (0x41200000, 0x10000),
        "axi_intc_0": (0x41800000, 0x10000),
        "locator_input_ctrl": (0x42000000, 0x8000),
        "locator_output_ctrl": (0x42010000, 0x4000),
        "locator_top_0": (0x43C00000, 0x4000),
    }
    observed_ips = {}
    metadata_windows = {}
    for source_name, source in (
        ("ip_dict", getattr(overlay, "ip_dict", {})),
        ("mem_dict", getattr(overlay, "mem_dict", {})),
    ):
        for key, metadata in source.items():
            metadata_windows[(source_name, key)] = metadata
    for name, (base, address_range) in expected_ips.items():
        matches = []
        for (source_name, key), metadata in metadata_windows.items():
            if (
                int(metadata.get("phys_addr", -1)) == base
                and int(metadata.get("addr_range", -1)) == address_range
            ):
                matches.append((source_name, key, metadata))
        check(
            len(matches) == 1,
            "HWH address 0x{:08X}/0x{:X} has {} metadata matches: {}".format(
                base, address_range, len(matches), [(item[0], item[1]) for item in matches]
            ),
        )
        source_name, metadata_key, metadata = matches[0]
        actual_base = int(metadata["phys_addr"])
        actual_range = int(metadata["addr_range"])
        check(actual_base == base, "{} base is 0x{:08X}".format(name, actual_base))
        check(
            actual_range == address_range,
            "{} range is 0x{:X}".format(name, actual_range),
        )
        observed_ips[name] = {
            "metadata_source": source_name,
            "metadata_key": metadata_key,
            "phys_addr": "0x{:08X}".format(actual_base),
            "addr_range": "0x{:X}".format(actual_range),
        }
    record("Overlay load and HWH address map", load_ms=round(overlay_ms, 3), ips=observed_ips)
    result["interrupt_pins"] = sorted(getattr(overlay, "interrupt_pins", {}).keys())

    from locator_driver import (
        ABI_VERSION,
        AXI_INTC_BASE,
        AXI_INTC_SIZE,
        COMPUTED_DESC_CRC,
        COMPUTED_MODEL_CRC,
        DROP_COUNT,
        INPUT_FREE_MASK,
        IRQ_ENABLE,
        IRQ_STATUS,
        LOCATOR_ABI_VERSION,
        OUTPUT_BUFFER_ID,
        OUTPUT_FRAME_ID_0,
        OUTPUT_FRAME_ID_1,
        OUTPUT_VALID_MASK,
        STALL_COUNT,
        STATUS,
        STATUS_ERROR,
        STATUS_IDLE,
        STATUS_MODEL_VALID,
        LocatorDriver,
        crc32_words,
        expected_stub_words,
        make_stub_payload,
    )

    driver = LocatorDriver.from_pynq()
    record(
        "PS fabric clocks enabled before Locator MMIO",
        fclk0_mhz=float(Clocks.fclk0_mhz),
        fclk1_mhz=float(Clocks.fclk1_mhz),
    )
    driver.assert_abi()
    driver.soft_reset()
    status = driver.read(STATUS)
    check(driver.read(ABI_VERSION) == LOCATOR_ABI_VERSION, "Locator ABI mismatch")
    check(status & STATUS_IDLE, "Locator is not idle after reset")
    check(not status & STATUS_ERROR, "Locator error is set after reset")
    check(driver.read(INPUT_FREE_MASK) & 0x3 == 0x3, "input mask reset value is wrong")
    check(driver.read(OUTPUT_VALID_MASK) & 0x3 == 0, "output mask reset value is wrong")
    record("Locator AXI ABI and reset state", abi="0x{:08X}".format(LOCATOR_ABI_VERSION))

    model_words, desc_words = make_stub_payload()
    model_t0 = time.monotonic()
    driver.load_model(
        model_words,
        desc_words,
        model_version=0x00010001,
        desc_version=0x00010001,
    )
    model_ms = (time.monotonic() - model_t0) * 1000.0
    check(driver.read(COMPUTED_MODEL_CRC) == crc32_words(model_words), "model CRC mismatch")
    check(driver.read(COMPUTED_DESC_CRC) == crc32_words(desc_words), "descriptor CRC mismatch")
    check(driver.read(STATUS) & STATUS_MODEL_VALID, "MODEL_VALID was not set")
    record(
        "Locator bulk model/descriptor load and CRC-32",
        load_ms=round(model_ms, 3),
        model_crc="0x{:08X}".format(crc32_words(model_words)),
        desc_crc="0x{:08X}".format(crc32_words(desc_words)),
    )

    # AXI INTC channel 1 (bit 1) is the synchronized Locator level interrupt.
    intc = MMIO(AXI_INTC_BASE, AXI_INTC_SIZE)
    INTC_IPR, INTC_IER, INTC_IAR, INTC_MER = 0x04, 0x08, 0x0C, 0x1C
    LOCATOR_IRQ_MASK = 1 << 1
    driver.clear_irq()
    intc.write(INTC_IAR, LOCATOR_IRQ_MASK)
    intc.write(INTC_IER, LOCATOR_IRQ_MASK)
    intc.write(INTC_MER, 0x3)
    driver.write(IRQ_ENABLE, 0x3)

    rng = np.random.RandomState(0x0302)
    image0 = rng.randint(0, 256, size=(128, 128)).astype(np.uint8)
    image1 = ((np.indices((128, 128)).sum(axis=0) * 37 + 11) & 0xFF).astype(np.uint8)
    frame0, frame1 = 0xFFFFFFFF, 0x00000000
    inference_rows = []
    for expected_buffer, image, frame_id in (
        (0, image0, frame0),
        (1, image1, frame1),
    ):
        t0 = time.monotonic()
        result_item = driver.run_stub(image, frame_id)
        elapsed_ms = (time.monotonic() - t0) * 1000.0
        actual = result_item.raw_map_i32.reshape(-1).view(np.uint32)
        expected = expected_stub_words(image, frame_id)
        check(result_item.buffer_id == expected_buffer, "unexpected output buffer")
        check(result_item.frame_id == frame_id, "Frame ID did not round-trip")
        check(np.array_equal(actual, expected), "Stub output is not bit-exact")
        inference_rows.append(
            {
                "buffer": result_item.buffer_id,
                "frame_id": "0x{:08X}".format(result_item.frame_id),
                "elapsed_ms": round(elapsed_ms, 3),
                "output_words": int(actual.size),
                "output_sha256": hashlib.sha256(actual.astype("<u4").tobytes()).hexdigest(),
            }
        )

    check(driver.read(OUTPUT_VALID_MASK) & 0x3 == 0x3, "two outputs were not published")
    check(driver.read(OUTPUT_FRAME_ID_0) == frame0, "buffer 0 Frame ID mismatch")
    check(driver.read(OUTPUT_FRAME_ID_1) == frame1, "buffer 1 Frame ID mismatch")
    check(driver.read(OUTPUT_BUFFER_ID) == 1, "latest output notification is not buffer 1")
    check(driver.read(INPUT_FREE_MASK) & 0x3 == 0x3, "input buffers were not released")
    check(driver.read(STALL_COUNT) == 0, "unexpected Stub stall count")
    check(driver.read(DROP_COUNT) == 0, "unexpected Stub drop count")
    record("Locator ping-pong, uint32 Frame ID wrap and 2x1280-word bit-exact output", runs=inference_rows)

    check(driver.read(IRQ_STATUS) & 0x1, "Locator completion IRQ status was not set")
    intc_pending = wait_mask(intc, INTC_IPR, LOCATOR_IRQ_MASK, LOCATOR_IRQ_MASK)
    driver.clear_irq()
    intc.write(INTC_IAR, LOCATOR_IRQ_MASK)
    wait_mask(intc, INTC_IPR, LOCATOR_IRQ_MASK, 0)
    record("Locator IRQ through AXI Interrupt Controller", pending="0x{:08X}".format(intc_pending))

    driver.release_output(0x3)
    check(driver.read(OUTPUT_VALID_MASK) & 0x3 == 0, "OUTPUT_RELEASE did not clear both buffers")
    driver.soft_reset()
    check(driver.read(STATUS) & STATUS_MODEL_VALID, "SOFT_RESET did not preserve MODEL_VALID")
    check(driver.read(INPUT_FREE_MASK) & 0x3 == 0x3, "SOFT_RESET input mask mismatch")
    check(driver.read(OUTPUT_VALID_MASK) & 0x3 == 0, "SOFT_RESET output mask mismatch")
    record("atomic OUTPUT_RELEASE and SOFT_RESET retains model")

    # Preserve the V1.0 classifier and production model contract inside the new overlay.
    cnn = overlay.gesture_top_0
    REG_CTRL, REG_STATUS, REG_CLASS_ID, REG_ABI = 0x00, 0x04, 0x08, 0x0C
    REG_WEIGHT_ADDR, REG_WEIGHT_DATA = 0x10, 0x14
    REG_IMG_ADDR, REG_IMG_DATA = 0x20, 0x24
    REG_DESC_INDEX, REG_DESC_DATA = 0x28, 0x2C
    check(cnn.read(REG_ABI) == 0x00010000, "classifier ABI mismatch")
    weights = read_mem_words(CLASS_PACKAGE / "weights_all.mem")
    descriptors = read_mem_words(CLASS_PACKAGE / "layer_descriptors.mem")
    check(len(weights) == 9838, "active classifier weight count mismatch")
    cnn.write(REG_WEIGHT_ADDR, 0)
    for word in weights:
        cnn.write(REG_WEIGHT_DATA, word)
    cnn.write(REG_DESC_INDEX, 0)
    for word in descriptors:
        cnn.write(REG_DESC_DATA, word)

    class_rows = []
    sample_dirs = sorted((CLASS_PACKAGE / "golden_vectors").iterdir())
    for sample in sample_dirs:
        if not sample.is_dir():
            continue
        pixels = (sample / "input_u8.bin").read_bytes()
        check(len(pixels) == 1024, "{} input byte count mismatch".format(sample.name))
        expected, logits = expected_class(sample / "fc2_logits_i32.bin")
        cnn.write(REG_IMG_ADDR, 0)
        for pixel in pixels:
            cnn.write(REG_IMG_DATA, pixel)
        t0 = time.monotonic()
        cnn.write(REG_CTRL, 1)
        deadline = time.monotonic() + 1.0
        while cnn.read(REG_STATUS) & 0x4 == 0:
            if time.monotonic() >= deadline:
                raise TimeoutError("{} classifier timeout".format(sample.name))
        elapsed_ms = (time.monotonic() - t0) * 1000.0
        actual = int(cnn.read(REG_CLASS_ID))
        check(actual == expected, "{} expected {}, got {}".format(sample.name, expected, actual))
        class_rows.append(
            {
                "sample": sample.name,
                "expected": expected,
                "actual": actual,
                "elapsed_ms": round(elapsed_ms, 3),
                "logits": list(logits),
            }
        )
    check(len(class_rows) == 8, "expected exactly 8 classifier golden samples")
    record("preserved classifier ABI and golden-vector HIL 8/8", runs=class_rows)

    # Register-level GPIO test. Restore the pre-test value before leaving.
    gpio = overlay.axi_gpio_0
    gpio_before = int(gpio.read(0x00)) & 0xF
    gpio.write(0x04, 0x0)
    gpio.write(0x00, 0xA)
    gpio_readback = int(gpio.read(0x00)) & 0xF
    gpio.write(0x00, gpio_before)
    check(gpio_readback == 0xA, "AXI GPIO readback mismatch")
    record("AXI GPIO/LED register readback with restored state", readback="0x{:X}".format(gpio_readback))

    driver.write(IRQ_ENABLE, 0)
    intc.write(INTC_IER, 0)
    intc.write(INTC_MER, 0)
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
