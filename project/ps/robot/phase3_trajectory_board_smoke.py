"""PYNQ smoke test for the isolated Phase 3 trajectory overlay.

This test exercises only PS MMIO -> PL trajectory -> PS MMIO.  It does not
touch UART, GPIO, servos or the physical robot.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from trajectory_axi_driver import TrajectoryAxiDriver


TRAJECTORY_BASE_ADDRESS = 0x43C2_0000


def unpack_word(line: str) -> tuple[int, int, int, int, int, int]:
    packed = int(line.strip(), 16)
    channels = []
    for channel in range(6):
        raw = (packed >> (channel * 32)) & 0xFFFF_FFFF
        channels.append(raw - (1 << 32) if raw & 0x8000_0000 else raw)
    return tuple(channels)  # type: ignore[return-value]


def load_first_segment(path: Path) -> tuple[tuple[int, ...], ...]:
    lines = [line.strip() for line in path.read_text(encoding="ascii").splitlines() if line.strip()]
    if len(lines) < 33:
        raise ValueError(f"golden MEM must contain at least 33 words, got {len(lines)}")
    samples = tuple(unpack_word(line) for line in lines[:33])
    return samples


def main() -> int:
    parser = argparse.ArgumentParser()
    here = Path(__file__).resolve().parent
    parser.add_argument("--bit", type=Path, default=here / "phase3_trajectory.bit")
    parser.add_argument(
        "--mem",
        type=Path,
        default=here / "pick_place_phase3_trajectory_q16_16_v1.mem",
    )
    parser.add_argument("--period-cycles", type=int, default=1_000_000)
    parser.add_argument("--timeout", type=float, default=2.0)
    args = parser.parse_args()

    try:
        from pynq import Overlay
    except ImportError as exc:
        raise RuntimeError("this smoke test must run on the PYNQ board") from exc

    golden = load_first_segment(args.mem)
    Overlay(str(args.bit), download=True)
    driver = TrajectoryAxiDriver.from_pynq(TRAJECTORY_BASE_ADDRESS)
    driver.assert_abi()
    driver.configure_irq(done=True, error=True)
    driver.submit_q16_16(golden[0], golden[32], args.period_cycles)

    observed = []
    for expected_index in range(1, 33):
        sample = driver.consume_sample(timeout_s=args.timeout)
        if sample.index != expected_index:
            raise RuntimeError(
                f"sample index mismatch: got {sample.index}, expected {expected_index}"
            )
        if sample.last != (expected_index == 32):
            raise RuntimeError(f"sample LAST mismatch at index {expected_index}")
        if sample.joints_q16_16 != golden[expected_index]:
            raise RuntimeError(f"sample payload mismatch at index {expected_index}")
        observed.append(sample.index)

    deadline = time.monotonic() + args.timeout
    while not driver.status().done:
        driver.raise_for_error()
        if time.monotonic() >= deadline:
            raise TimeoutError("timeout waiting for trajectory DONE")
        time.sleep(0.0001)

    final_status = driver.status()
    if final_status.busy:
        raise RuntimeError("trajectory block remained busy after final sample")
    driver.clear_done()
    driver.raise_for_error()

    print(
        json.dumps(
            {
                "result": "PASS",
                "abi": "0x00003001",
                "base_address": "0x43C20000",
                "period_cycles": args.period_cycles,
                "samples_checked": len(observed),
                "physical_outputs_used": False,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

