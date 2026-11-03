"""First-board Phase 2-L2 OV5640 bring-up and optional Locator smoke test."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import numpy as np
from pynq import Overlay

from camera_l2_driver import CameraL2Driver, write_pgm


ROOT = Path(__file__).resolve().parent
LOCATOR_DIR = ROOT.parent / "locator"
sys.path.insert(0, str(LOCATOR_DIR))


def require_autostart_stopped() -> None:
    active = subprocess.run(
        ["systemctl", "is-active", "gesture-demo.service"],
        text=True, capture_output=True, check=False,
    )
    enabled = subprocess.run(
        ["systemctl", "is-enabled", "gesture-demo.service"],
        text=True, capture_output=True, check=False,
    )
    active_state = active.stdout.strip()
    enabled_state = enabled.stdout.strip()
    if active_state == "active" or enabled_state not in {"disabled", "masked", "not-found"}:
        raise RuntimeError(
            "gesture-demo.service must be stopped and disabled before loading L2 "
            f"(active={active_state!r}, enabled={enabled_state!r})"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bit", type=Path, default=ROOT / "phase2_l2_ov5640.bit")
    parser.add_argument("--hwh", type=Path, default=ROOT / "phase2_l2_ov5640.hwh")
    parser.add_argument("--output", type=Path, default=ROOT / "camera_128x128.pgm")
    parser.add_argument("--id-only", action="store_true")
    parser.add_argument("--run-locator", action="store_true")
    parser.add_argument("--locator-package", type=Path, default=LOCATOR_DIR / "locator_v16")
    args = parser.parse_args()

    require_autostart_stopped()
    if not args.bit.is_file() or not args.hwh.is_file():
        raise FileNotFoundError("copy the paired Phase 2-L2 .bit/.hwh files beside this script")
    if args.bit.stem != args.hwh.stem:
        raise ValueError("PYNQ requires the .bit and .hwh to use the same basename")

    camera = None
    held_camera_buffer = None
    locator = None
    held_locator_mask = 0
    try:
        Overlay(str(args.bit), download=True)
        camera = CameraL2Driver.from_pynq()
        camera.power_on()
        chip_id = camera.assert_chip_id()
        print("PASS: OV5640 chip ID = 0x{:04X}".format(chip_id), flush=True)
        if args.id_only:
            return 0

        camera.configure_vga_yuyv()
        camera.prepare_capture(camera_source=args.run_locator)
        frame = camera.acquire(timeout_s=3.0)
        held_camera_buffer = frame.buffer_id
        write_pgm(args.output, frame.image_u8)
        top_pad_nonzero = int(np.count_nonzero(frame.image_u8[:16]))
        bottom_pad_nonzero = int(np.count_nonzero(frame.image_u8[112:]))
        print(
            "PASS: frame={} buffer={} min={} max={} mean={:.2f} padding_nonzero={}/{} output={}".format(
                frame.frame_id, frame.buffer_id, int(frame.image_u8.min()),
                int(frame.image_u8.max()), float(frame.image_u8.mean()),
                top_pad_nonzero, bottom_pad_nonzero, args.output,
            ),
            flush=True,
        )

        if args.run_locator:
            from locator_driver import LocatorDriver

            locator = LocatorDriver.from_pynq()
            locator.assert_abi()
            locator.soft_reset()
            locator.load_v16_package(args.locator_package, timeout_s=2.0)
            camera.select_camera_source(True)
            locator.submit_preloaded(frame.buffer_id, frame.frame_id)
            result = locator.wait_output(frame_id=frame.frame_id, timeout_s=2.0)
            held_locator_mask = 1 << result.buffer_id
            raw_path = args.output.with_suffix(".locator_i32.bin")
            result.raw_map_i32.astype("<i4", copy=False).tofile(raw_path)
            locator.release_output(held_locator_mask)
            held_locator_mask = 0
            print(
                "PASS: camera-to-Locator frame={} output_buffer={} raw_map={}".format(
                    result.frame_id, result.buffer_id, raw_path
                ),
                flush=True,
            )

        camera.release_buffer(frame.buffer_id)
        held_camera_buffer = None
        return 0
    finally:
        try:
            if locator is not None and held_locator_mask:
                locator.release_output(held_locator_mask)
        finally:
            if camera is not None:
                try:
                    if held_camera_buffer is not None:
                        camera.release_buffer(held_camera_buffer)
                finally:
                    camera.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
