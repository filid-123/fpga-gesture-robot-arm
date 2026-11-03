"""Load the all-PL gesture + HDMI debug overlay on a PYNQ-Z2.

Runtime control stays in PL.  This helper only supplies the two PS fabric clocks,
downloads the bitstream, and keeps the terminal open for the requested interval.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import Sequence


DEFAULT_BIT = Path(__file__).with_name("phase2_l2_autonomous_hdmi.bit")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "bit",
        nargs="?",
        type=Path,
        default=DEFAULT_BIT,
        help="overlay BIT; default is phase2_l2_autonomous_hdmi.bit beside this script",
    )
    parser.add_argument(
        "--seconds",
        type=float,
        default=300.0,
        help="foreground observation time; PL keeps running after the script exits",
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

    # Program the PS fabric clocks before configuring PL.  This avoids changing
    # FCLK1 after the camera/HDMI MMCMs and the autonomous init FSM have started.
    Clocks.fclk0_mhz = 50.0
    Clocks.fclk1_mhz = 100.0
    time.sleep(0.1)
    Overlay(str(bit_path), download=True)

    print("All-PL gesture + HDMI debug overlay loaded.")
    print(
        "FCLK0={:.1f} MHz, FCLK1={:.1f} MHz".format(
            float(Clocks.fclk0_mhz), float(Clocks.fclk1_mhz)
        )
    )
    print("Connect the monitor to HDMI OUT: 640x480 @ 60 Hz.")
    print("green=raw bbox, yellow=EMA bbox, cyan=18% expanded ROI")
    print("RAW=per-frame class, LED=confirmed class, top-right=locator detect")
    print("No MMIO/model transfer/start-done polling is active in this script.")

    deadline = time.monotonic() + args.seconds
    try:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            time.sleep(min(1.0, remaining))
    except KeyboardInterrupt:
        pass

    print("Observer exited; the PL pipeline and HDMI output remain active.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
