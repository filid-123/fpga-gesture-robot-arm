"""PYNQ hardware-in-the-loop regression for the active model package.

This replaces the legacy 0x18 class-bypass test. Every sample is written to
the real input BRAM and compared with the argmax of its exported INT32 logits.
"""

import argparse
import struct
import time
from pathlib import Path

from pynq import Overlay


REG_CTRL = 0x00
REG_STATUS = 0x04
REG_CLASS_ID = 0x08
REG_ABI_VERSION = 0x0C
REG_WEIGHT_ADDR = 0x10
REG_WEIGHT_DATA = 0x14
REG_IMG_ADDR = 0x20
REG_IMG_DATA = 0x24
REG_DESC_INDEX = 0x28
REG_DESC_DATA = 0x2C


def read_mem_words(path: Path):
    words = []
    for line in path.read_text(encoding="utf-8").splitlines():
        token = line.strip()
        if token and not token.startswith("//"):
            words.append(int(token, 16))
    return words


def expected_class(logit_path: Path):
    raw = logit_path.read_bytes()
    logits = struct.unpack(f"<{len(raw) // 4}i", raw)
    return max(range(len(logits)), key=logits.__getitem__), logits


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bitstream", default="design_1_wrapper.bit")
    parser.add_argument("--model-package", default="model_package/active")
    parser.add_argument("--timeout", type=float, default=1.0)
    args = parser.parse_args()

    package = Path(args.model_package)
    overlay = Overlay(args.bitstream)
    cnn = overlay.gesture_top_0

    abi = cnn.read(REG_ABI_VERSION)
    if abi != 0x00010000:
        raise RuntimeError(f"FPGA ABI mismatch: 0x{abi:08X}")

    weights = read_mem_words(package / "weights_all.mem")
    descriptors = read_mem_words(package / "layer_descriptors.mem")

    cnn.write(REG_WEIGHT_ADDR, 0)
    for word in weights:
        cnn.write(REG_WEIGHT_DATA, word)

    cnn.write(REG_DESC_INDEX, 0)
    for word in descriptors:
        cnn.write(REG_DESC_DATA, word)

    passed = 0
    samples = sorted((package / "golden_vectors").iterdir())
    for sample in samples:
        if not sample.is_dir():
            continue
        pixels = (sample / "input_u8.bin").read_bytes()
        if len(pixels) != 1024:
            raise ValueError(f"{sample.name}: expected 1024 input bytes")

        expected, logits = expected_class(sample / "fc2_logits_i32.bin")
        cnn.write(REG_IMG_ADDR, 0)
        for pixel in pixels:
            cnn.write(REG_IMG_DATA, pixel)

        cnn.write(REG_CTRL, 1)
        deadline = time.monotonic() + args.timeout
        while (cnn.read(REG_STATUS) & 0x04) == 0:
            if time.monotonic() >= deadline:
                raise TimeoutError(f"{sample.name}: inference timeout")

        actual = cnn.read(REG_CLASS_ID)
        ok = actual == expected
        passed += int(ok)
        print(
            f"{'PASS' if ok else 'FAIL'} {sample.name}: "
            f"expected={expected} actual={actual} logits={logits}"
        )

    print(f"HIL result: {passed}/{len(samples)} bit-exact class matches")
    if passed != len(samples):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
