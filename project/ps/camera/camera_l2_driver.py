"""Phase 2-L2 OpenSOC OV5640 control and frame-readback driver.

The camera control ABI is intentionally independent of the sealed Phase 2-L1
Locator ABI.  It supports safe power sequencing, SCCB register read/write,
128x128 ping/pong buffer ownership and slow diagnostic MMIO readback.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Sequence, Tuple

import numpy as np


CAMERA_CTRL_BASE = 0x43C1_0000
CAMERA_CTRL_SIZE = 0x0000_1000
CAMERA_ABI_VERSION = 0x0000_0403
OV5640_SCCB_ADDRESS = 0x3C
OV5640_CHIP_ID = 0x5640

CONTROL = 0x00
STATUS = 0x04
ABI_VERSION = 0x08
FRAME_ID_0 = 0x0C
FRAME_ID_1 = 0x10
LATEST_FRAME_ID = 0x14
DROP_COUNT = 0x18
FORMAT_ERROR_COUNT = 0x1C
SCCB_ADDRESS = 0x20
SCCB_DATA = 0x24
BUFFER_RELEASE = 0x28
SCCB_START = 0x2C
CLEAR_STATUS = 0x30
DEBUG_WORD_ADDRESS = 0x34
DEBUG_WORD_DATA = 0x38
ROI_XY = 0x3C
ROI_SIZE = 0x40
ROI_TAG = 0x44
ROI_CONTROL = 0x48
ROI_STATUS = 0x4C
ROI_DONE_TAG = 0x50
ROI_SOURCE_FRAME_ID = 0x54

CTRL_CAPTURE_ENABLE = 1 << 0
CTRL_SOURCE_CAMERA = 1 << 1
CTRL_RESET_N = 1 << 2
CTRL_PWDN = 1 << 3

STATUS_CAPTURE_ENABLE = 1 << 0
STATUS_SOURCE_CAMERA = 1 << 1
STATUS_SCCB_BUSY = 1 << 2
STATUS_SCCB_DONE = 1 << 3
STATUS_SCCB_ACK_ERROR = 1 << 4
STATUS_FIFO_OVERFLOW = 1 << 5
STATUS_BUFFER_VALID_SHIFT = 6
STATUS_LATEST_BUFFER = 1 << 8
STATUS_FRAME_PUBLISHED = 1 << 9
STATUS_SCCB_READ_VALID = 1 << 10
STATUS_XCLK_LOCKED = 1 << 11
STATUS_RESET_N = 1 << 12
STATUS_PWDN = 1 << 13

FRAME_WORDS = 4096
FRAME_PIXELS = 128 * 128
BUFFER_STRIDE_WORDS = 4096

ROI_CTRL_ARM = 1 << 0
ROI_CTRL_CLASSIFIER_SOURCE = 1 << 1
ROI_CTRL_SAME_FRAME = 1 << 2
ROI_CTRL_BUFFER_ID = 1 << 3
ROI_STATUS_CLASSIFIER_SOURCE = 1 << 0
ROI_STATUS_ARMED = 1 << 1
ROI_STATUS_BUSY = 1 << 2
ROI_STATUS_DONE = 1 << 3
ROI_STATUS_ERROR = 1 << 4
ROI_STATUS_CLASSIFIER_BUSY = 1 << 5
ROI_STATUS_SAME_FRAME_BUSY = 1 << 6


# Conservative VGA/YUYV bring-up sequence for the parallel DVP port. The base
# analog/ISP values follow the upstream Linux OV5640 initialization; the DVP
# pad/PLL values follow STMicroelectronics' parallel-interface component
# driver. The output is 640x480 YUYV, matching RTL Y_BYTE_PHASE=0. Board-level
# byte order and polarities remain explicit first-silicon checks.
# Sources inspected 2026-08-24:
# https://github.com/torvalds/linux/blob/master/drivers/media/i2c/ov5640.c
# https://github.com/STMicroelectronics/stm32-ov5640/blob/main/ov5640.c
OV5640_VGA_YUYV_REGS: Tuple[Tuple[int, int], ...] = (
    (0x3103, 0x11), (0x3103, 0x03),
    (0x3630, 0x36), (0x3631, 0x0E), (0x3632, 0xE2), (0x3633, 0x12),
    (0x3621, 0xE0), (0x3704, 0xA0), (0x3703, 0x5A), (0x3715, 0x78),
    (0x3717, 0x01), (0x370B, 0x60), (0x3705, 0x1A), (0x3905, 0x02),
    (0x3906, 0x10), (0x3901, 0x0A), (0x3731, 0x12), (0x3600, 0x08),
    (0x3601, 0x33), (0x302D, 0x60), (0x3620, 0x52), (0x371B, 0x20),
    (0x471C, 0x50), (0x3A13, 0x43), (0x3A18, 0x00), (0x3A19, 0xF8),
    (0x3635, 0x13), (0x3636, 0x03), (0x3634, 0x40), (0x3622, 0x01),
    (0x3C01, 0x34), (0x3C04, 0x28), (0x3C05, 0x98), (0x3C06, 0x00),
    (0x3C07, 0x08), (0x3C08, 0x00), (0x3C09, 0x1C), (0x3C0A, 0x9C),
    (0x3C0B, 0x40),

    # DVP pads and 24 MHz XCLK clock tree. Board A/B testing on 2026-09-04
    # fixed 0x4740[5]=0 for stable sampling by the PL rising-edge receiver.
    (0x3017, 0xFF), (0x3018, 0xF3), (0x300E, 0x58), (0x302E, 0x00),
    (0x3034, 0x18), (0x3035, 0x41), (0x3036, 0x60), (0x3037, 0x13),
    (0x3108, 0x01), (0x4740, 0x00),

    # 2592x1944 sensor window, 2x subsampling/scaling to 640x480.
    (0x3820, 0x41), (0x3821, 0x07), (0x3814, 0x31), (0x3815, 0x31),
    (0x3800, 0x00), (0x3801, 0x00), (0x3802, 0x00), (0x3803, 0x04),
    (0x3804, 0x0A), (0x3805, 0x3F), (0x3806, 0x07), (0x3807, 0x9B),
    (0x3808, 0x02), (0x3809, 0x80), (0x380A, 0x01), (0x380B, 0xE0),
    (0x380C, 0x07), (0x380D, 0x68), (0x380E, 0x04), (0x380F, 0x38),
    (0x3810, 0x00), (0x3811, 0x10), (0x3812, 0x00), (0x3813, 0x06),
    (0x3618, 0x00), (0x3612, 0x29), (0x3708, 0x64), (0x3709, 0x52),
    (0x370C, 0x03),

    # Auto exposure/banding and black-level correction for VGA.
    (0x3A02, 0x03), (0x3A03, 0xD8), (0x3A08, 0x01), (0x3A09, 0x27),
    (0x3A0A, 0x00), (0x3A0B, 0xF6), (0x3A0E, 0x03), (0x3A0D, 0x04),
    (0x3A14, 0x03), (0x3A15, 0xD8), (0x4001, 0x02), (0x4004, 0x02),

    # Enable ISP/YUV path, select YUYV and set the DVP divider.
    (0x3000, 0x00), (0x3002, 0x1C), (0x3004, 0xFF), (0x3006, 0xC3),
    (0x4300, 0x30), (0x501F, 0x00), (0x440E, 0x00), (0x460B, 0x35),
    (0x460C, 0x23), (0x4837, 0x22), (0x3824, 0x02),
    (0x5000, 0xA7), (0x5001, 0xA3),

    # Basic automatic white-balance and gamma settings used by the reference
    # initialization. Locator consumes only Y, but these avoid a poor preview.
    (0x5180, 0xFF), (0x5181, 0xF2), (0x5182, 0x00), (0x5183, 0x14),
    (0x5184, 0x25), (0x5185, 0x24), (0x5186, 0x09), (0x5187, 0x09),
    (0x5188, 0x09), (0x5189, 0x88), (0x518A, 0x54), (0x518B, 0xEE),
    (0x518C, 0xB2), (0x518D, 0x50), (0x518E, 0x34), (0x518F, 0x6B),
    (0x5190, 0x46), (0x5191, 0xF8), (0x5192, 0x04), (0x5193, 0x70),
    (0x5194, 0xF0), (0x5195, 0xF0), (0x5196, 0x03), (0x5197, 0x01),
    (0x5198, 0x04), (0x5199, 0x6C), (0x519A, 0x04), (0x519B, 0x00),
    (0x519C, 0x09), (0x519D, 0x2B), (0x519E, 0x38),
    (0x5480, 0x01), (0x5481, 0x08), (0x5482, 0x14), (0x5483, 0x28),
    (0x5484, 0x51), (0x5485, 0x65), (0x5486, 0x71), (0x5487, 0x7D),
    (0x5488, 0x87), (0x5489, 0x91), (0x548A, 0x9A), (0x548B, 0xAA),
    (0x548C, 0xB8), (0x548D, 0xCD), (0x548E, 0xDD), (0x548F, 0xEA),
    (0x5490, 0x1D),
    (0x3A0F, 0x30), (0x3A10, 0x28), (0x3A1B, 0x30), (0x3A1E, 0x26),
    (0x3A11, 0x60), (0x3A1F, 0x14),
)


@dataclass(frozen=True)
class CameraFrame:
    buffer_id: int
    frame_id: int
    image_u8: np.ndarray


@dataclass(frozen=True)
class CameraRoiResult:
    descriptor_tag: int
    source_frame_id: int


class CameraL2Driver:
    def __init__(self, ctrl_mmio, *, sleeper: Callable[[float], None] = time.sleep):
        if not hasattr(ctrl_mmio, "read") or not hasattr(ctrl_mmio, "write"):
            raise TypeError("ctrl_mmio must provide read(offset) and write(offset, value)")
        self.ctrl = ctrl_mmio
        self._sleep = sleeper

    @classmethod
    def from_pynq(cls):
        try:
            from pynq import Clocks, MMIO
        except ImportError as exc:  # pragma: no cover - only available on PYNQ
            raise RuntimeError("from_pynq() must run on a PYNQ image") from exc
        Clocks.fclk0_mhz = 50.0
        Clocks.fclk1_mhz = 100.0
        return cls(MMIO(CAMERA_CTRL_BASE, CAMERA_CTRL_SIZE))

    def read(self, offset: int) -> int:
        return int(self.ctrl.read(offset)) & 0xFFFF_FFFF

    def write(self, offset: int, value: int) -> None:
        self.ctrl.write(offset, int(value) & 0xFFFF_FFFF)

    def assert_abi(self) -> None:
        actual = self.read(ABI_VERSION)
        if actual != CAMERA_ABI_VERSION:
            raise RuntimeError(
                f"Camera ABI mismatch: expected 0x{CAMERA_ABI_VERSION:08X}, "
                f"got 0x{actual:08X}"
            )

    def status(self) -> dict:
        value = self.read(STATUS)
        return {
            "raw": value,
            "capture_enabled": bool(value & STATUS_CAPTURE_ENABLE),
            "source_camera": bool(value & STATUS_SOURCE_CAMERA),
            "sccb_busy": bool(value & STATUS_SCCB_BUSY),
            "sccb_done": bool(value & STATUS_SCCB_DONE),
            "sccb_ack_error": bool(value & STATUS_SCCB_ACK_ERROR),
            "fifo_overflow": bool(value & STATUS_FIFO_OVERFLOW),
            "buffer_valid_mask": (value >> STATUS_BUFFER_VALID_SHIFT) & 0x3,
            "latest_buffer_id": 1 if value & STATUS_LATEST_BUFFER else 0,
            "frame_published": bool(value & STATUS_FRAME_PUBLISHED),
            "sccb_read_valid": bool(value & STATUS_SCCB_READ_VALID),
            "xclk_locked": bool(value & STATUS_XCLK_LOCKED),
            "reset_n": bool(value & STATUS_RESET_N),
            "pwdn": bool(value & STATUS_PWDN),
        }

    def _control(self, *, capture: bool, camera_source: bool, reset_n: bool, pwdn: bool) -> None:
        value = (
            (CTRL_CAPTURE_ENABLE if capture else 0)
            | (CTRL_SOURCE_CAMERA if camera_source else 0)
            | (CTRL_RESET_N if reset_n else 0)
            | (CTRL_PWDN if pwdn else 0)
        )
        self.write(CONTROL, value)

    def power_down(self) -> None:
        self._control(capture=False, camera_source=False, reset_n=False, pwdn=True)

    def power_on(self) -> None:
        """Apply the reset/PWDN sequence while capture remains disabled."""

        self.assert_abi()
        if not self.status()["xclk_locked"]:
            raise RuntimeError("24 MHz camera XCLK MMCM is not locked")
        self.power_down()
        self._sleep(0.005)
        self._control(capture=False, camera_source=False, reset_n=False, pwdn=False)
        self._sleep(0.001)
        self._control(capture=False, camera_source=False, reset_n=True, pwdn=False)
        self._sleep(0.020)

    def _wait_sccb(self, timeout_s: float) -> int:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            status = self.read(STATUS)
            if status & STATUS_SCCB_DONE:
                if status & STATUS_SCCB_ACK_ERROR:
                    raise IOError("OV5640 did not acknowledge the SCCB transaction")
                return status
            self._sleep(0.0001)
        raise TimeoutError("Timeout while waiting for OV5640 SCCB transaction")

    def write_reg(self, register: int, value: int, *, timeout_s: float = 0.05) -> None:
        self.write(CLEAR_STATUS, 1)
        self.write(SCCB_ADDRESS, (OV5640_SCCB_ADDRESS << 16) | (register & 0xFFFF))
        self.write(SCCB_DATA, value & 0xFF)
        self.write(SCCB_START, 1)
        self._wait_sccb(timeout_s)

    def read_reg(self, register: int, *, timeout_s: float = 0.05) -> int:
        self.write(CLEAR_STATUS, 1)
        self.write(SCCB_ADDRESS, (OV5640_SCCB_ADDRESS << 16) | (register & 0xFFFF))
        self.write(SCCB_START, 3)
        status = self._wait_sccb(timeout_s)
        if not status & STATUS_SCCB_READ_VALID:
            raise IOError("SCCB read completed without valid data")
        return self.read(SCCB_DATA) & 0xFF

    def read_chip_id(self) -> int:
        return (self.read_reg(0x300A) << 8) | self.read_reg(0x300B)

    def assert_chip_id(self) -> int:
        chip_id = self.read_chip_id()
        if chip_id != OV5640_CHIP_ID:
            raise RuntimeError(
                f"Unexpected camera chip ID 0x{chip_id:04X}; expected 0x{OV5640_CHIP_ID:04X}"
            )
        return chip_id

    def configure_vga_yuyv(self, registers: Sequence[Tuple[int, int]] = OV5640_VGA_YUYV_REGS) -> None:
        """Program the first-board 640x480 YUYV/DVP profile and start streaming."""

        self.write_reg(0x3008, 0x82)
        self._sleep(0.005)
        for register, value in registers:
            self.write_reg(register, value)
        self.write_reg(0x3008, 0x02)
        self._sleep(0.300)

    def enable_capture(self, *, camera_source: bool = False) -> None:
        state = self.status()
        if not state["xclk_locked"] or not state["reset_n"] or state["pwdn"]:
            raise RuntimeError("Camera must be powered and out of reset before capture")
        self._control(capture=True, camera_source=camera_source, reset_n=True, pwdn=False)

    def prepare_capture(self, *, camera_source: bool = False) -> None:
        """Discard stale ownership/status and start a fresh capture session."""

        self.release_all_buffers()
        self.clear_status()
        self.enable_capture(camera_source=camera_source)

    def disable_capture(self, *, camera_source: Optional[bool] = None) -> None:
        state = self.status()
        source = state["source_camera"] if camera_source is None else bool(camera_source)
        self._control(capture=False, camera_source=source, reset_n=True, pwdn=False)

    def select_camera_source(self, enabled: bool = True) -> None:
        state = self.status()
        self._control(
            capture=state["capture_enabled"], camera_source=enabled,
            reset_n=state["reset_n"], pwdn=state["pwdn"],
        )

    def wait_frame(self, *, timeout_s: float = 2.0) -> Tuple[int, int]:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            state = self.status()
            if state["fifo_overflow"]:
                raise RuntimeError("Camera PCLK-to-system FIFO overflowed")
            if state["buffer_valid_mask"]:
                buffer_id = state["latest_buffer_id"]
                if not (state["buffer_valid_mask"] & (1 << buffer_id)):
                    buffer_id = 0 if state["buffer_valid_mask"] & 1 else 1
                frame_reg = FRAME_ID_0 if buffer_id == 0 else FRAME_ID_1
                return buffer_id, self.read(frame_reg)
            self._sleep(0.001)
        raise TimeoutError("Timeout while waiting for a camera frame")

    def read_buffer(self, buffer_id: int) -> np.ndarray:
        if buffer_id not in (0, 1):
            raise ValueError("buffer_id must be 0 or 1")
        if not (self.status()["buffer_valid_mask"] & (1 << buffer_id)):
            raise RuntimeError(f"Camera buffer {buffer_id} is not valid")
        words = np.empty(FRAME_WORDS, dtype=np.uint32)
        base = buffer_id * BUFFER_STRIDE_WORDS
        for index in range(FRAME_WORDS):
            self.write(DEBUG_WORD_ADDRESS, base + index)
            words[index] = self.read(DEBUG_WORD_DATA)
        return words.astype("<u4", copy=False).view(np.uint8).reshape(128, 128).copy()

    def acquire(self, *, timeout_s: float = 2.0) -> CameraFrame:
        buffer_id, frame_id = self.wait_frame(timeout_s=timeout_s)
        return CameraFrame(buffer_id, frame_id, self.read_buffer(buffer_id))

    def release_buffer(self, buffer_id: int) -> None:
        if buffer_id not in (0, 1):
            raise ValueError("buffer_id must be 0 or 1")
        self.write(BUFFER_RELEASE, 1 << buffer_id)

    def release_all_buffers(self) -> int:
        mask = int(self.status()["buffer_valid_mask"])
        if mask:
            self.write(BUFFER_RELEASE, mask)
        return mask

    def clear_status(self) -> None:
        self.write(CLEAR_STATUS, 1)

    def roi_status(self) -> dict:
        value = self.read(ROI_STATUS)
        return {
            "raw": value,
            "classifier_source": bool(value & ROI_STATUS_CLASSIFIER_SOURCE),
            "armed": bool(value & ROI_STATUS_ARMED),
            "busy": bool(value & ROI_STATUS_BUSY),
            "done": bool(value & ROI_STATUS_DONE),
            "error": bool(value & ROI_STATUS_ERROR),
            "classifier_busy": bool(value & ROI_STATUS_CLASSIFIER_BUSY),
            "same_frame_busy": bool(value & ROI_STATUS_SAME_FRAME_BUSY),
        }

    def select_classifier_source(self, camera_roi: bool) -> None:
        self.write(ROI_CONTROL, ROI_CTRL_CLASSIFIER_SOURCE if camera_roi else 0)

    def arm_roi(self, crop_box_xyxy, *, descriptor_tag: int) -> None:
        """Arm an integer square crop for the next accepted VGA SOF."""

        if len(crop_box_xyxy) != 4:
            raise ValueError("crop_box_xyxy must contain x0, y0, x1, y1")
        x0, y0, x1, y1 = (int(value) for value in crop_box_xyxy)
        side = x1 - x0
        if side != y1 - y0:
            raise ValueError("PL ROI must be square")
        if side < 32:
            raise ValueError("PL streaming ROI requires a side of at least 32 pixels")
        if x0 < 0 or y0 < 0 or x1 > 640 or y1 > 480:
            raise ValueError("PL ROI must fit inside the 640x480 source frame")
        state = self.roi_status()
        if state["armed"] or state["busy"] or state["classifier_busy"]:
            raise RuntimeError(f"ROI/classifier is not idle: {state}")

        self.clear_status()
        self.write(ROI_XY, ((y0 & 0x3FF) << 16) | (x0 & 0x3FF))
        self.write(ROI_SIZE, side)
        self.write(ROI_TAG, descriptor_tag)
        self.write(ROI_CONTROL, ROI_CTRL_ARM | ROI_CTRL_CLASSIFIER_SOURCE)

    def arm_same_frame_roi(
        self, buffer_id: int, crop_box_xyxy, *, descriptor_tag: int
    ) -> None:
        """Crop the held 128x128 Locator input frame into classifier ROI BRAM."""

        if buffer_id not in (0, 1):
            raise ValueError("buffer_id must be 0 or 1")
        if len(crop_box_xyxy) != 4:
            raise ValueError("crop_box_xyxy must contain x0, y0, x1, y1")
        x0, y0, x1, y1 = (int(value) for value in crop_box_xyxy)
        side = x1 - x0
        if side != y1 - y0 or side < 1:
            raise ValueError("same-frame ROI must be a non-empty square")
        if x0 < 0 or y0 < 0 or x1 > 128 or y1 > 128:
            raise ValueError("same-frame ROI must fit inside the 128x128 buffer")
        state = self.roi_status()
        if state["armed"] or state["busy"] or state["classifier_busy"]:
            raise RuntimeError(f"ROI/classifier is not idle: {state}")
        if not (self.status()["buffer_valid_mask"] & (1 << buffer_id)):
            raise RuntimeError(f"Camera buffer {buffer_id} is not valid")

        self.clear_status()
        self.write(ROI_XY, ((y0 & 0x3FF) << 16) | (x0 & 0x3FF))
        self.write(ROI_SIZE, side)
        self.write(ROI_TAG, descriptor_tag)
        control = (
            ROI_CTRL_ARM
            | ROI_CTRL_CLASSIFIER_SOURCE
            | ROI_CTRL_SAME_FRAME
            | (ROI_CTRL_BUFFER_ID if buffer_id else 0)
        )
        self.write(ROI_CONTROL, control)

    def wait_roi(
        self,
        *,
        descriptor_tag: Optional[int] = None,
        source_frame_id: Optional[int] = None,
        timeout_s: float = 2.0,
    ) -> CameraRoiResult:
        expected_tag = None if descriptor_tag is None else descriptor_tag & 0xFFFF_FFFF
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            state = self.roi_status()
            if state["error"]:
                raise RuntimeError(f"PL ROI extraction failed: {state}")
            if state["done"]:
                tag = self.read(ROI_DONE_TAG)
                if expected_tag is not None and tag != expected_tag:
                    raise RuntimeError(
                        f"ROI descriptor tag mismatch: expected 0x{expected_tag:08X}, "
                        f"got 0x{tag:08X}"
                    )
                actual_frame_id = self.read(ROI_SOURCE_FRAME_ID)
                if (
                    source_frame_id is not None
                    and actual_frame_id != (source_frame_id & 0xFFFF_FFFF)
                ):
                    raise RuntimeError(
                        f"ROI source frame mismatch: expected {source_frame_id & 0xFFFF_FFFF}, "
                        f"got {actual_frame_id}"
                    )
                return CameraRoiResult(tag, actual_frame_id)
            self._sleep(0.0005)
        raise TimeoutError("Timeout while waiting for PL ROI completion")

    def shutdown(self) -> None:
        """Return camera control and ping/pong ownership to the safe state."""

        self.disable_capture(camera_source=False)
        self.release_all_buffers()
        self.clear_status()
        self.power_down()


def write_pgm(path, image_u8: np.ndarray) -> Path:
    image = np.asarray(image_u8)
    if image.dtype != np.uint8 or image.shape != (128, 128):
        raise ValueError("PGM image must be uint8 with shape 128x128")
    output = Path(path)
    output.write_bytes(b"P5\n128 128\n255\n" + np.ascontiguousarray(image).tobytes())
    return output
