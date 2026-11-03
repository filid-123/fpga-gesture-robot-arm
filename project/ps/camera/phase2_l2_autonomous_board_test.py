"""Load the autonomous Phase 2-L2 overlay and leave runtime control to PL.

This intentionally performs no MMIO, model transfer, CRC, hash, start/done
handshake, or status polling.  BIT and HWH must have the same basename so PYNQ
can load the metadata that belongs to the bitstream.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import Sequence


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bit", type=Path, help="autonomous .bit file")
    parser.add_argument(
        "--seconds",
        type=float,
        default=120.0,
        help="seconds to keep this foreground observer alive (default: 120)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    bit_path = args.bit.expanduser().resolve()
    hwh_path = bit_path.with_suffix(".hwh")
    if not bit_path.is_file():
        raise FileNotFoundError(bit_path)
    if not hwh_path.is_file():
        raise FileNotFoundError(
            f"companion HWH must share the BIT basename: {hwh_path}"
        )
    if args.seconds < 0:
        raise ValueError("--seconds must be non-negative")

    try:
        from pynq import Clocks, Overlay
    except ImportError as exc:
        raise RuntimeError("run this script on the PYNQ-Z2 image") from exc

    Overlay(str(bit_path), download=True)
    Clocks.fclk0_mhz = 50.0
    Clocks.fclk1_mhz = 100.0

    print("Autonomous overlay loaded; PS runtime control is now idle.")
    print("LED0=background, LED1=fist, LED2=mute, LED3=palm")
    print("all LEDs off=no confirmed hand; all LEDs on=fatal camera/FIFO error")
    print("Gesture classes need 2 consecutive results; background/none need 3.")

    deadline = time.monotonic() + args.seconds
    try:
        while time.monotonic() < deadline:
            time.sleep(min(1.0, deadline - time.monotonic()))
    except KeyboardInterrupt:
        pass
    print("Observer exited; the PL pipeline remains autonomous.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

