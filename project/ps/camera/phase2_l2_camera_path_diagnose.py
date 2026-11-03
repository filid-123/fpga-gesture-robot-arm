"""Diagnose OV5640 SCCB, DVP capture, frame format and FIFO behavior."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Optional, Sequence

import numpy as np

from camera_l2_driver import (
    CAMERA_CTRL_BASE,
    CAMERA_CTRL_SIZE,
    DROP_COUNT,
    FORMAT_ERROR_COUNT,
    LATEST_FRAME_ID,
    CameraL2Driver,
    write_pgm,
)


ROOT = Path(__file__).resolve().parent
DEFAULT_BIT = ROOT / "phase2_l2_ov5640.bit"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bit", type=Path, default=DEFAULT_BIT)
    parser.add_argument("--frames", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=3.0)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "diagnostic_output")
    return parser


def emit(event: str, **payload: Any) -> None:
    print(event + " " + json.dumps(payload, sort_keys=True), flush=True)


def snapshot(camera: CameraL2Driver, label: str) -> None:
    emit(
        "CAMERA_STATUS",
        label=label,
        status=camera.status(),
        drop_count=camera.read(DROP_COUNT),
        format_error_count=camera.read(FORMAT_ERROR_COUNT),
        latest_frame_id=camera.read(LATEST_FRAME_ID),
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.frames < 1:
        raise ValueError("--frames must be positive")
    if args.timeout <= 0:
        raise ValueError("--timeout must be positive")

    bit_path = args.bit.expanduser().resolve()
    hwh_path = bit_path.with_suffix(".hwh")
    if not bit_path.is_file() or not hwh_path.is_file():
        raise FileNotFoundError("paired BIT/HWH files are required")
    if bit_path.stem != hwh_path.stem:
        raise ValueError("BIT and HWH must have the same basename")

    try:
        from pynq import Clocks, MMIO, Overlay
    except ImportError as exc:
        raise RuntimeError("run this script on the PYNQ-Z2 image") from exc

    Clocks.fclk0_mhz = 50.0
    Clocks.fclk1_mhz = 100.0
    time.sleep(0.1)
    Overlay(str(bit_path), download=True)
    emit(
        "CLOCKS",
        fclk0_mhz=float(Clocks.fclk0_mhz),
        fclk1_mhz=float(Clocks.fclk1_mhz),
    )

    camera = CameraL2Driver(MMIO(CAMERA_CTRL_BASE, CAMERA_CTRL_SIZE))
    held_buffer: Optional[int] = None
    try:
        snapshot(camera, "after_overlay")
        camera.power_on()
        snapshot(camera, "after_power_on")

        chip_id = camera.assert_chip_id()
        emit("SCCB_CHIP_ID", value=f"0x{chip_id:04X}")

        camera.configure_vga_yuyv()
        register_4740 = camera.read_reg(0x4740)
        emit("SCCB_REGISTER", address="0x4740", value=f"0x{register_4740:02X}")
        snapshot(camera, "after_configuration")

        args.output_dir.mkdir(parents=True, exist_ok=True)
        camera.prepare_capture(camera_source=False)
        for index in range(args.frames):
            frame = camera.acquire(timeout_s=args.timeout)
            held_buffer = frame.buffer_id
            output_path = args.output_dir / f"frame_{index:02d}.pgm"
            write_pgm(output_path, frame.image_u8)
            emit(
                "FRAME",
                index=index,
                frame_id=frame.frame_id,
                buffer_id=frame.buffer_id,
                minimum=int(frame.image_u8.min()),
                maximum=int(frame.image_u8.max()),
                mean=round(float(frame.image_u8.mean()), 3),
                standard_deviation=round(float(frame.image_u8.std()), 3),
                output=str(output_path),
            )
            camera.release_buffer(frame.buffer_id)
            held_buffer = None
            snapshot(camera, f"after_frame_{index}")

        snapshot(camera, "final")
        print("DIAG_PASS", flush=True)
        return 0
    except Exception as exc:
        emit("DIAG_ERROR", exception=type(exc).__name__, message=str(exc))
        try:
            snapshot(camera, "on_error")
        except Exception as status_exc:
            emit(
                "STATUS_READ_ERROR",
                exception=type(status_exc).__name__,
                message=str(status_exc),
            )
        return 1
    finally:
        if held_buffer is not None:
            try:
                camera.release_buffer(held_buffer)
            except Exception:
                pass
        try:
            camera.shutdown()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
