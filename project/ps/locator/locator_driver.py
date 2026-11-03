"""Phase 2-L1 Locator MMIO driver.

This module is usable from a PYNQ Jupyter notebook and is independently unit
testable on a PC.  It supports the retained control-path Stub regression and
the frozen v12/v16 five-layer Locator packages.
"""

from __future__ import annotations

import json
import time
import xml.etree.ElementTree as ET
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence, Tuple

import numpy as np


# Frozen for the Phase 2-L1 skeleton Block Design. Phase 1 addresses are not
# duplicated here because this driver only owns Locator resources.
LOCATOR_CTRL_BASE = 0x43C0_0000
LOCATOR_CTRL_SIZE = 0x0000_4000
LOCATOR_INPUT_BASE = 0x4200_0000
LOCATOR_INPUT_SIZE = 0x0000_8000
LOCATOR_OUTPUT_BASE = 0x4201_0000
LOCATOR_OUTPUT_SIZE = 0x0000_4000
AXI_INTC_BASE = 0x4180_0000
AXI_INTC_SIZE = 0x0001_0000

REQUIRED_HWH_CLOCKS = {
    "PCW_EN_CLK1_PORT": "1",
    "PCW_FCLK_CLK1_BUF": "TRUE",
    "PCW_FPGA1_PERIPHERAL_FREQMHZ": "100",
}

REQUIRED_HWH_RESETS = {
    "rst_ps_50m": {
        "C_EXT_RESET_HIGH": "0",
        "C_AUX_RESET_HIGH": "1",
    },
    "rst_locator_100m": {
        "C_EXT_RESET_HIGH": "0",
        "C_AUX_RESET_HIGH": "1",
    },
}


def validate_hwh_clock_contract(path):
    """Reject an overlay whose fabric clocks or reset domains are unsafe."""

    root = ET.parse(path).getroot()
    parameters = {}
    reset_parameters = {}
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1] != "PARAMETER":
            continue
        name = element.attrib.get("NAME")
        if name in REQUIRED_HWH_CLOCKS:
            parameters[name] = element.attrib.get("VALUE", "")

    for module in root.iter():
        if module.tag.rsplit("}", 1)[-1] != "MODULE":
            continue
        instance = module.attrib.get("INSTANCE")
        if instance not in REQUIRED_HWH_RESETS:
            continue
        reset_parameters[instance] = {}
        for element in module.iter():
            if element.tag.rsplit("}", 1)[-1] != "PARAMETER":
                continue
            name = element.attrib.get("NAME")
            if name in REQUIRED_HWH_RESETS[instance]:
                reset_parameters[instance][name] = element.attrib.get("VALUE", "")

    mismatches = []
    for name, expected in REQUIRED_HWH_CLOCKS.items():
        actual = parameters.get(name)
        if actual != expected:
            mismatches.append("{} expected {}, got {}".format(name, expected, actual))
    for instance, expected_parameters in REQUIRED_HWH_RESETS.items():
        actual_parameters = reset_parameters.get(instance, {})
        for name, expected in expected_parameters.items():
            actual = actual_parameters.get(name)
            if actual != expected:
                mismatches.append(
                    "{} {} expected {}, got {}".format(instance, name, expected, actual)
                )
    if mismatches:
        raise RuntimeError("unsafe Phase 2-L1 HWH clock contract: " + "; ".join(mismatches))
    return {"clocks": parameters, "resets": reset_parameters}

LOCATOR_ABI_VERSION = 0x0000_0302

CONTROL = 0x0000
STATUS = 0x0004
IRQ_ENABLE = 0x0008
IRQ_STATUS = 0x000C
ABI_VERSION = 0x0010
ERROR_CODE = 0x0014
INPUT_BUFFER_ID = 0x0018
INPUT_FRAME_ID = 0x001C
INPUT_FREE_MASK = 0x0020
OUTPUT_BUFFER_ID = 0x0024
OUTPUT_FRAME_ID_0 = 0x0028
OUTPUT_FRAME_ID_1 = 0x002C
OUTPUT_VALID_MASK = 0x0030
OUTPUT_RELEASE = 0x0034
MODEL_WORD_COUNT = 0x0038
DESC_WORD_COUNT = 0x003C
EXPECTED_MODEL_CRC = 0x0040
COMPUTED_MODEL_CRC = 0x0044
EXPECTED_DESC_CRC = 0x0048
COMPUTED_DESC_CRC = 0x004C
MODEL_VERSION = 0x0050
DESC_VERSION = 0x0054
STALL_COUNT = 0x0058
DROP_COUNT = 0x005C
TOP1_CAPABILITY = 0x0060
TOP1_CELL_0 = 0x0064
TOP1_CELL_1 = 0x007C
TOP1_CAPABILITY_MAGIC = 0x5431_5231

MODEL_WINDOW = 0x1000
DESC_WINDOW = 0x3000

CMD_START = 1 << 0
CMD_SOFT_RESET = 1 << 1
CMD_MODEL_COMMIT = 1 << 2
CMD_MODEL_INVALIDATE = 1 << 3
CMD_CLEAR_ERROR = 1 << 4
CMD_CLEAR_IRQ = 1 << 5

STATUS_IDLE = 1 << 0
STATUS_BUSY = 1 << 1
STATUS_DONE = 1 << 2
STATUS_ERROR = 1 << 3
STATUS_MODEL_VALID = 1 << 4
STATUS_MODEL_ERROR = 1 << 5

MODEL_WORDS = 1904
MAX_DESC_WORDS = 1024
INPUT_WORDS_PER_BUFFER = 4096
INPUT_PIXELS = 128 * 128
INPUT_BUFFER_STRIDE_WORDS = 4096
OUTPUT_WORDS = 5 * 16 * 16
OUTPUT_BUFFER_STRIDE_WORDS = 2048

LOCATOR_V12_MODEL_CRC32 = 0x63F1_9DDB
LOCATOR_V12_MODEL_VERSION = 0x000C_0000
LOCATOR_V16_MODEL_CRC32 = 0x21FC_0351
LOCATOR_V16_MODEL_VERSION = 0x0010_0000
# Hardware-owned minimal descriptor for the fixed-function v12 datapath.
# Bytes of this little-endian word spell "LOCD".  Layer offsets and quantized
# arithmetic remain authoritative in locator_layer_layout.json and the
# quantization manifest; the current RTL does not execute descriptor fields.
LOCATOR_V12_DESC_WORDS = (0x4443_4F4C,)
LOCATOR_V12_DESC_VERSION = 0x0000_0001
LOCATOR_V12_DESC_CRC32 = 0x21A5_6B2B
# v16 keeps the same fixed topology and hardware-owned integration descriptor.
LOCATOR_V16_DESC_WORDS = LOCATOR_V12_DESC_WORDS
LOCATOR_V16_DESC_VERSION = LOCATOR_V12_DESC_VERSION
LOCATOR_V16_DESC_CRC32 = LOCATOR_V12_DESC_CRC32


@dataclass(frozen=True)
class LocatorResult:
    buffer_id: int
    frame_id: int
    raw_map_i32: np.ndarray


@dataclass(frozen=True)
class LocatorTop1Result:
    buffer_id: int
    frame_id: int
    cell_x: int
    cell_y: int
    raw_values_i32: Tuple[int, int, int, int, int]


def _as_u32_words(words: Sequence[int], *, name: str) -> np.ndarray:
    array = np.asarray(words)
    if array.ndim != 1:
        raise ValueError(f"{name} must be a one-dimensional word array")
    if array.dtype.kind not in "iu":
        raise TypeError(f"{name} must contain integer values")
    return np.ascontiguousarray(array.astype(np.uint32, copy=False))


def _u32_to_i32(value: int) -> int:
    value = int(value) & 0xFFFF_FFFF
    return value - 0x1_0000_0000 if value & 0x8000_0000 else value


def pack_input_u8(image_u8: np.ndarray) -> np.ndarray:
    """Pack 128x128 UINT8 pixels into little-endian 32-bit MMIO words."""

    pixels = np.asarray(image_u8)
    if pixels.dtype != np.uint8:
        raise TypeError("Locator input must be uint8")
    if pixels.size != INPUT_PIXELS:
        raise ValueError(f"Locator input must contain exactly {INPUT_PIXELS} pixels")
    pixels = np.ascontiguousarray(pixels.reshape(-1)).reshape(-1, 4).astype(np.uint32)
    return (
        pixels[:, 0]
        | (pixels[:, 1] << np.uint32(8))
        | (pixels[:, 2] << np.uint32(16))
        | (pixels[:, 3] << np.uint32(24))
    ).astype(np.uint32, copy=False)


def crc32_words(words: Sequence[int]) -> int:
    """CRC-32/ISO-HDLC over little-endian uint32 word bytes."""

    array = _as_u32_words(words, name="CRC words").astype("<u4", copy=False)
    return zlib.crc32(array.tobytes(order="C")) & 0xFFFF_FFFF


def make_stub_payload(desc_words: int = 8) -> Tuple[np.ndarray, np.ndarray]:
    """Return a deterministic, non-production payload for Stub-only board tests."""

    if not 1 <= desc_words <= MAX_DESC_WORDS:
        raise ValueError("desc_words is outside the skeleton contract")
    model = (np.arange(MODEL_WORDS, dtype=np.uint32) * np.uint32(0x01010101))
    desc = np.arange(desc_words, dtype=np.uint32) ^ np.uint32(0xA5A50000)
    return model, desc


def _read_locator_package(package_dir, *, expected_crc32: int, version_name: str) -> Tuple[np.ndarray, dict]:
    """Read a fixed-topology Locator package with an explicit expected CRC."""

    root = Path(package_dir)
    model_path = root / "locator_model_blob.mem"
    layout_path = root / "locator_layer_layout.json"
    quant_path = root / "locator_quantization_manifest.json"
    for path in (model_path, layout_path, quant_path):
        if not path.is_file():
            raise FileNotFoundError(path)

    words = np.asarray(
        [int(line.strip(), 16) for line in model_path.read_text(encoding="ascii").splitlines()
         if line.strip()],
        dtype=np.uint32,
    )
    layout = json.loads(layout_path.read_text(encoding="utf-8"))
    quant = json.loads(quant_path.read_text(encoding="utf-8"))
    if words.size != MODEL_WORDS or layout.get("blob_words") != MODEL_WORDS:
        raise ValueError(f"{version_name} model/layout must contain exactly 1904 words")
    if layout.get("blob_bytes") != MODEL_WORDS * 4:
        raise ValueError(f"{version_name} layout byte count mismatch")
    if int(layout.get("blob_crc32_iso_hdlc", "0"), 16) != expected_crc32:
        raise ValueError(f"{version_name} layout declares an unexpected model CRC")
    if crc32_words(words) != expected_crc32:
        raise ValueError(f"{version_name} model payload CRC mismatch")
    if quant.get("architecture") != "HandLocatorNet_1x128x128_to_5x16x16":
        raise ValueError(f"{version_name} architecture mismatch")
    output = quant.get("conv5_output", {})
    if output.get("shape") != [5, 16, 16] or output.get("dtype") != "signed int32 little-endian":
        raise ValueError(f"{version_name} Conv5 output contract mismatch")
    return words, quant


def read_locator_v12_package(package_dir) -> Tuple[np.ndarray, dict]:
    """Read and validate the frozen v12 model/layout/quantization package."""

    return _read_locator_package(
        package_dir,
        expected_crc32=LOCATOR_V12_MODEL_CRC32,
        version_name="v12",
    )


def read_locator_v16_package(package_dir) -> Tuple[np.ndarray, dict]:
    """Read and validate the frozen v16 model/layout/quantization package."""

    return _read_locator_package(
        package_dir,
        expected_crc32=LOCATOR_V16_MODEL_CRC32,
        version_name="v16",
    )


def expected_stub_words(image_u8: np.ndarray, frame_id: int) -> np.ndarray:
    """Bit-exact oracle for the temporary locator_stub_engine."""

    packed = pack_input_u8(image_u8)
    checksum = int(np.bitwise_xor.reduce(packed, dtype=np.uint32))
    indices = np.arange(OUTPUT_WORDS, dtype=np.uint32)
    return indices ^ np.uint32(checksum) ^ np.uint32(frame_id & 0xFFFF_FFFF)


class LocatorDriver:
    """Register and bulk frame-buffer driver with explicit buffer ownership."""

    def __init__(self, ctrl_mmio, input_mmio, output_mmio):
        for name, obj, minimum_words in (
            ("ctrl_mmio", ctrl_mmio, LOCATOR_CTRL_SIZE // 4),
            ("input_mmio", input_mmio, LOCATOR_INPUT_SIZE // 4),
            ("output_mmio", output_mmio, LOCATOR_OUTPUT_SIZE // 4),
        ):
            if not hasattr(obj, "read") or not hasattr(obj, "write"):
                raise TypeError(f"{name} must provide read(offset) and write(offset, value)")
            if not hasattr(obj, "array") or len(obj.array) < minimum_words:
                raise ValueError(f"{name}.array is smaller than the hardware window")
        self.ctrl = ctrl_mmio
        self.input = input_mmio
        self.output = output_mmio

    @classmethod
    def from_pynq(cls):
        """Create a driver after making the two PS fabric clocks explicit.

        FCLK1 must be running before the first access to the Locator control
        window behind the AXI Clock Converter.  An access with the destination
        clock stopped can leave a Zynq GP transaction waiting indefinitely.
        """

        try:
            from pynq import Clocks, MMIO
        except ImportError as exc:  # pragma: no cover - only available on PYNQ
            raise RuntimeError("from_pynq() must run on a PYNQ image") from exc
        # Do this before constructing or touching any Locator MMIO object.  The
        # HWH also carries these values, but the explicit assignment protects
        # older PYNQ images and custom Overlay loading paths.
        Clocks.fclk0_mhz = 50.0
        Clocks.fclk1_mhz = 100.0
        return cls(
            MMIO(LOCATOR_CTRL_BASE, LOCATOR_CTRL_SIZE),
            MMIO(LOCATOR_INPUT_BASE, LOCATOR_INPUT_SIZE),
            MMIO(LOCATOR_OUTPUT_BASE, LOCATOR_OUTPUT_SIZE),
        )

    def read(self, offset: int) -> int:
        return int(self.ctrl.read(offset)) & 0xFFFF_FFFF

    def write(self, offset: int, value: int) -> None:
        self.ctrl.write(offset, int(value) & 0xFFFF_FFFF)

    def assert_abi(self) -> None:
        actual = self.read(ABI_VERSION)
        if actual != LOCATOR_ABI_VERSION:
            raise RuntimeError(
                f"Locator ABI mismatch: expected 0x{LOCATOR_ABI_VERSION:08X}, "
                f"got 0x{actual:08X}"
            )

    def _wait_until(self, predicate, timeout_s: float, operation: str) -> int:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            status = self.read(STATUS)
            if predicate(status):
                return status
            time.sleep(0.0005)
        raise TimeoutError(f"Timeout while waiting for {operation}")

    def clear_error(self) -> None:
        self.write(CONTROL, CMD_CLEAR_ERROR)

    def clear_irq(self) -> None:
        self.write(CONTROL, CMD_CLEAR_IRQ)

    def soft_reset(self) -> None:
        self.write(CONTROL, CMD_SOFT_RESET)

    def load_model(
        self,
        model_words: Sequence[int],
        desc_words: Sequence[int],
        *,
        model_version: int,
        desc_version: int,
        timeout_s: float = 1.0,
    ) -> None:
        model = _as_u32_words(model_words, name="model_words")
        desc = _as_u32_words(desc_words, name="desc_words")
        if model.size != MODEL_WORDS:
            raise ValueError(f"model_words must contain exactly {MODEL_WORDS} words")
        if not 1 <= desc.size <= MAX_DESC_WORDS:
            raise ValueError("desc_words must contain 1..1024 words")
        if not model_version or not desc_version:
            raise ValueError("model and descriptor versions must be non-zero")
        if self.read(STATUS) & STATUS_BUSY:
            raise RuntimeError("Cannot load Locator model while hardware is busy")

        # NumPy slice assignment uses PYNQ's memory-backed MMIO array and avoids
        # thousands of Python-level write() calls.
        self.ctrl.array[MODEL_WINDOW // 4 : MODEL_WINDOW // 4 + MODEL_WORDS] = model
        self.ctrl.array[DESC_WINDOW // 4 : DESC_WINDOW // 4 + desc.size] = desc

        model_crc = crc32_words(model)
        desc_crc = crc32_words(desc)
        self.write(MODEL_WORD_COUNT, model.size)
        self.write(DESC_WORD_COUNT, desc.size)
        self.write(EXPECTED_MODEL_CRC, model_crc)
        self.write(EXPECTED_DESC_CRC, desc_crc)
        self.write(MODEL_VERSION, model_version)
        self.write(DESC_VERSION, desc_version)
        self.write(CONTROL, CMD_MODEL_COMMIT)

        status = self._wait_until(
            lambda value: bool(value & (STATUS_MODEL_VALID | STATUS_MODEL_ERROR)),
            timeout_s,
            "MODEL_COMMIT",
        )
        if status & STATUS_MODEL_ERROR:
            raise RuntimeError(
                f"Locator model commit failed: error=0x{self.read(ERROR_CODE):02X}"
            )
        if self.read(COMPUTED_MODEL_CRC) != model_crc:
            raise RuntimeError("Hardware model CRC readback mismatch")
        if self.read(COMPUTED_DESC_CRC) != desc_crc:
            raise RuntimeError("Hardware descriptor CRC readback mismatch")

    def load_v12_package(self, package_dir, *, timeout_s: float = 1.0) -> dict:
        """Upload the frozen v12 model and the hardware-owned descriptor."""

        model, quantization_manifest = read_locator_v12_package(package_dir)
        descriptor = np.asarray(LOCATOR_V12_DESC_WORDS, dtype=np.uint32)
        if crc32_words(descriptor) != LOCATOR_V12_DESC_CRC32:
            raise RuntimeError("internal v12 descriptor CRC constant mismatch")
        self.load_model(
            model,
            descriptor,
            model_version=LOCATOR_V12_MODEL_VERSION,
            desc_version=LOCATOR_V12_DESC_VERSION,
            timeout_s=timeout_s,
        )
        return quantization_manifest

    def load_v16_package(self, package_dir, *, timeout_s: float = 1.0) -> dict:
        """Upload the frozen v16 model and fixed-topology descriptor."""

        model, quantization_manifest = read_locator_v16_package(package_dir)
        descriptor = np.asarray(LOCATOR_V16_DESC_WORDS, dtype=np.uint32)
        if crc32_words(descriptor) != LOCATOR_V16_DESC_CRC32:
            raise RuntimeError("internal v16 descriptor CRC constant mismatch")
        self.load_model(
            model,
            descriptor,
            model_version=LOCATOR_V16_MODEL_VERSION,
            desc_version=LOCATOR_V16_DESC_VERSION,
            timeout_s=timeout_s,
        )
        return quantization_manifest

    def choose_input_buffer(self) -> int:
        mask = self.read(INPUT_FREE_MASK) & 0x3
        if mask & 0x1:
            return 0
        if mask & 0x2:
            return 1
        raise RuntimeError("No free Locator input buffer")

    def submit(
        self,
        image_u8: np.ndarray,
        frame_id: int,
        *,
        input_buffer_id: Optional[int] = None,
    ) -> int:
        buffer_id = self._prepare_submit(input_buffer_id)

        packed = pack_input_u8(image_u8)
        start = buffer_id * INPUT_BUFFER_STRIDE_WORDS
        self.input.array[start : start + INPUT_WORDS_PER_BUFFER] = packed
        self.write(INPUT_BUFFER_ID, buffer_id)
        self.write(INPUT_FRAME_ID, frame_id)
        self.write(CONTROL, CMD_START)
        return buffer_id

    def _prepare_submit(self, input_buffer_id: Optional[int]) -> int:
        self.assert_abi()
        status = self.read(STATUS)
        if not status & STATUS_MODEL_VALID:
            raise RuntimeError("Locator model is not valid")
        if status & STATUS_BUSY:
            raise RuntimeError("Locator is busy; START never queues")
        if self.read(OUTPUT_VALID_MASK) & 0x3 == 0x3:
            raise RuntimeError("Both Locator output buffers are held by PS")

        buffer_id = self.choose_input_buffer() if input_buffer_id is None else input_buffer_id
        if buffer_id not in (0, 1):
            raise ValueError("input_buffer_id must be 0 or 1")
        if not (self.read(INPUT_FREE_MASK) & (1 << buffer_id)):
            raise RuntimeError(f"Locator input buffer {buffer_id} is not free")
        return buffer_id

    def submit_preloaded(self, input_buffer_id: int, frame_id: int) -> int:
        """Start Locator on a PL-preloaded input buffer without a PS copy.

        Phase 2-L2 uses this entry point after the camera front end publishes
        one of its two 128x128 buffers. The Block Design source mux must be set
        to camera before this command is issued.
        """

        buffer_id = self._prepare_submit(input_buffer_id)
        self.write(INPUT_BUFFER_ID, buffer_id)
        self.write(INPUT_FRAME_ID, frame_id)
        self.write(CONTROL, CMD_START)
        return buffer_id

    def wait_output(
        self, *, frame_id: Optional[int] = None, timeout_s: float = 1.0
    ) -> LocatorResult:
        expected_frame = None if frame_id is None else frame_id & 0xFFFF_FFFF

        def find_ready() -> Optional[Tuple[int, int]]:
            mask = self.read(OUTPUT_VALID_MASK) & 0x3
            for buffer_id, frame_reg in ((0, OUTPUT_FRAME_ID_0), (1, OUTPUT_FRAME_ID_1)):
                if mask & (1 << buffer_id):
                    actual_frame = self.read(frame_reg)
                    if expected_frame is None or actual_frame == expected_frame:
                        return buffer_id, actual_frame
            return None

        deadline = time.monotonic() + timeout_s
        ready = find_ready()
        while ready is None and time.monotonic() < deadline:
            if self.read(STATUS) & STATUS_ERROR:
                raise RuntimeError(
                    f"Locator inference failed: error=0x{self.read(ERROR_CODE):02X}"
                )
            time.sleep(0.0005)
            ready = find_ready()
        if ready is None:
            raise TimeoutError("Timeout while waiting for Locator output")

        buffer_id, actual_frame = ready
        start = buffer_id * OUTPUT_BUFFER_STRIDE_WORDS
        words = np.array(
            self.output.array[start : start + OUTPUT_WORDS], dtype=np.uint32, copy=True
        )
        raw_map = words.view(np.int32).reshape(5, 16, 16)
        return LocatorResult(buffer_id, actual_frame, raw_map)

    def wait_top1(
        self, *, frame_id: Optional[int] = None, timeout_s: float = 1.0
    ) -> LocatorTop1Result:
        """Read the PL-reduced Top-1 raw values without copying the 5 KiB map."""

        if self.read(TOP1_CAPABILITY) != TOP1_CAPABILITY_MAGIC:
            raise RuntimeError("Locator PL Top-1 reducer is not available")
        expected_frame = None if frame_id is None else frame_id & 0xFFFF_FFFF
        deadline = time.monotonic() + timeout_s
        ready = None
        while ready is None and time.monotonic() < deadline:
            mask = self.read(OUTPUT_VALID_MASK) & 0x3
            for buffer_id, frame_reg in ((0, OUTPUT_FRAME_ID_0), (1, OUTPUT_FRAME_ID_1)):
                if mask & (1 << buffer_id):
                    actual_frame = self.read(frame_reg)
                    if expected_frame is None or actual_frame == expected_frame:
                        ready = (buffer_id, actual_frame)
                        break
            if ready is None:
                if self.read(STATUS) & STATUS_ERROR:
                    raise RuntimeError(
                        f"Locator inference failed: error=0x{self.read(ERROR_CODE):02X}"
                    )
                time.sleep(0.0005)
        if ready is None:
            raise TimeoutError("Timeout while waiting for Locator Top-1 output")

        buffer_id, actual_frame = ready
        base = TOP1_CELL_0 if buffer_id == 0 else TOP1_CELL_1
        cell_index = self.read(base) & 0xFF
        raw_values = tuple(
            _u32_to_i32(self.read(base + 4 * index)) for index in range(1, 6)
        )
        cell_y, cell_x = divmod(cell_index, 16)
        return LocatorTop1Result(
            buffer_id, actual_frame, cell_x, cell_y, raw_values
        )

    def release_output(self, buffer_mask: int) -> None:
        mask = int(buffer_mask) & 0x3
        if not mask:
            raise ValueError("buffer_mask must release output buffer 0 and/or 1")
        valid = self.read(OUTPUT_VALID_MASK) & 0x3
        if mask & ~valid:
            raise RuntimeError(
                f"Cannot release invalid output buffer(s): mask=0b{mask:02b}, "
                f"valid=0b{valid:02b}"
            )
        self.write(OUTPUT_RELEASE, mask)

    def run_stub(
        self, image_u8: np.ndarray, frame_id: int, *, timeout_s: float = 1.0
    ) -> LocatorResult:
        self.submit(image_u8, frame_id)
        result = self.wait_output(frame_id=frame_id, timeout_s=timeout_s)
        actual_words = result.raw_map_i32.reshape(-1).view(np.uint32)
        expected_words = expected_stub_words(image_u8, frame_id)
        if not np.array_equal(actual_words, expected_words):
            mismatch = int(np.flatnonzero(actual_words != expected_words)[0])
            raise AssertionError(
                f"Locator Stub bit-exact mismatch at output word {mismatch}: "
                f"expected 0x{int(expected_words[mismatch]):08X}, "
                f"got 0x{int(actual_words[mismatch]):08X}"
            )
        return result
