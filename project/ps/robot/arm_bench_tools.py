"""PC-side bench tools for S1 board tests (3.3 V USB-UART, NO robot, NO servo bus).

Every command refuses non-bench profiles.  Wiring and the stop rules are in
board/BOARD_TEST_CN.md.

* ``expected``        : print/save the byte stream the PL must emit for a
                        golden segment (ArmBackendPlModel), no port needed.
* ``capture``         : read bytes from a USB-UART RX wired to a PL TX pin and
                        compare them with the expected stream.
* ``emulate-so101``   : answer the PL's Feetech-fixture READ requests with
                        status packets that report the last sync-written goal
                        (a direct 3.3 V UART pair, no transceiver).
* ``emulate-roarm``   : answer command lines with fixture feedback lines that
                        echo the commanded positions.

Usage examples (Windows)::

    python arm_bench_tools.py expected --backend roarm --segment 2 --mem <golden.mem>
    python arm_bench_tools.py capture --port COM9 --backend roarm --segment 2 --mem <golden.mem>
    python arm_bench_tools.py emulate-so101 --port COM9
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Sequence

import arm_backend as ab
import so101_feetech_reference as ft
from arm_fixed_point import unpack_192
from arm_profile import ArmProfile, ProfileError, find_config_root
from roarm_json_reference import RoArmJsonProtocol, encode_command, parse_feedback_line


BENCH_PROFILES = {
    "roarm": ("arm_profiles/bench_loopback_roarm_json.yaml",
              "protocols/fixtures/roarm_json_FIXTURE_NOT_OFFICIAL.yaml"),
    "so101": ("arm_profiles/bench_loopback_so101.yaml",
              "protocols/fixtures/feetech_FIXTURE_NOT_OFFICIAL.yaml"),
}


def load_bench(backend: str, config_root: Path | None = None):
    root = config_root or find_config_root()
    profile_rel, protocol_rel = BENCH_PROFILES[backend]
    profile = ArmProfile.load(root / profile_rel)
    if not profile.bench_only:
        raise ProfileError("bench tools only accept bench_only profiles")
    protocol = (RoArmJsonProtocol.load(root / protocol_rel) if backend == "roarm"
                else ft.FeetechProtocol.load(root / protocol_rel))
    return profile, protocol, ab.build_pl_config(profile, protocol)


def load_segment(mem_path: Path, segment: int) -> list[tuple[int, ...]]:
    lines = [l.strip() for l in mem_path.read_text(encoding="ascii").splitlines() if l.strip()]
    if len(lines) != 321:
        raise ValueError(f"expected the 321-sample golden MEM, got {len(lines)} lines")
    if not 0 <= segment < 10:
        raise ValueError("segment must be 0..9")
    return [unpack_192(int(lines[segment * 32 + i], 16)) for i in range(1, 33)]


def expected_stream(config: ab.PlBackendConfig, samples: Sequence[Sequence[int]], *,
                    line_mode: bool) -> bytes:
    """Pin byte stream for one segment: LINE mode starts with the entry poll."""

    model = ab.ArmBackendPlModel(config)
    data = model.poll_cycle()[0] if line_mode else b""
    for sample in samples:
        result = model.process_sample(sample)
        if result.fault:
            raise RuntimeError(f"model fault {result.fault} (bench profile mismatch)")
        data += result.cmd + result.req
    return data


@dataclass
class CaptureResult:
    expected: int
    received: int
    first_mismatch: int | None

    @property
    def passed(self) -> bool:
        return self.first_mismatch is None and self.received >= self.expected


def compare_stream(expected: bytes, received: bytes) -> CaptureResult:
    for index, (a, b) in enumerate(zip(expected, received)):
        if a != b:
            return CaptureResult(len(expected), len(received), index)
    return CaptureResult(len(expected), len(received), None)


@dataclass
class So101Emulator:
    """Answers fixture READs with the last sync-written goal of that id."""

    protocol: ft.FeetechProtocol
    device_ids: Sequence[int]
    positions: dict[int, int] = field(default_factory=dict)
    buffer: bytearray = field(default_factory=bytearray)
    replies: int = 0

    def __post_init__(self) -> None:
        for channel, device_id in enumerate(self.device_ids):
            self.positions.setdefault(device_id, 0)

    def feed(self, data: bytes) -> bytes:
        """Consume received bytes; return reply bytes to transmit."""

        self.buffer += data
        out = bytearray()
        header = bytes(self.protocol.header)  # type: ignore[arg-type]
        while True:
            start = self.buffer.find(header)
            if start < 0:
                del self.buffer[:-1]
                break
            del self.buffer[:start]
            if len(self.buffer) < 4:
                break
            length = self.buffer[3]
            total = length + 4
            if len(self.buffer) < total:
                break
            packet = bytes(self.buffer[:total])
            del self.buffer[:total]
            body = packet[2:-1]
            if ft.checksum(self.protocol, body) != packet[-1]:
                continue
            device_id, instruction, params = packet[2], packet[4], packet[5:-1]
            if instruction == self.protocol.instructions["sync_write"]:
                size = params[1]
                for offset in range(2, len(params), size + 1):
                    target = params[offset]
                    self.positions[target] = ft.decode_position(self.protocol, params[offset + 1: offset + 1 + size])
            elif instruction == self.protocol.instructions["read"] and device_id in self.positions:
                value, _ = ft.encode_position(self.protocol, self.positions[device_id])
                out += ft.encode_status_packet(self.protocol, device_id, 0, value)
                self.replies += 1
        return bytes(out)


@dataclass
class RoArmEmulator:
    """Answers fixture command lines with feedback lines echoing positions."""

    protocol: RoArmJsonProtocol
    buffer: bytearray = field(default_factory=bytearray)
    replies: int = 0

    def feed(self, data: bytes) -> bytes:
        self.buffer += data
        out = bytearray()
        while b"\n" in self.buffer:
            line, _, rest = bytes(self.buffer).partition(b"\n")
            self.buffer = bytearray(rest)
            record = parse_feedback_line(self.protocol, line + b"\n")
            if record is not None and all(v is not None for v in record.device_values):
                out += encode_command(self.protocol, "set_joints", record.device_values)  # type: ignore[arg-type]
                self.replies += 1
        return bytes(out)


def run_emulator(port: str, baudrate: int, emulator, *, seconds: float,
                 serial_factory: Callable | None = None) -> int:
    from arm_serial_common import open_serial

    handle = (serial_factory or open_serial)(port, baudrate, 0.001)
    deadline = time.monotonic() + seconds
    try:
        while time.monotonic() < deadline:
            data = handle.read(256)
            if data:
                reply = emulator.feed(data)
                if reply:
                    handle.write(reply)
    finally:
        handle.close()
    return emulator.replies


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("expected", "capture"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--backend", choices=sorted(BENCH_PROFILES), required=True)
        cmd.add_argument("--segment", type=int, default=2)
        cmd.add_argument("--mem", type=Path, required=True)
        cmd.add_argument("--dry-run-stream", action="store_true", help="no LINE entry poll")
        if name == "capture":
            cmd.add_argument("--port", required=True)
            cmd.add_argument("--baud", type=int, default=None)
            cmd.add_argument("--seconds", type=float, default=30.0)
        else:
            cmd.add_argument("--out", type=Path)
    for name in ("emulate-so101", "emulate-roarm"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--port", required=True)
        cmd.add_argument("--baud", type=int, default=None)
        cmd.add_argument("--seconds", type=float, default=120.0)
    args = parser.parse_args(argv)

    if args.command in ("expected", "capture"):
        profile, _protocol, config = load_bench(args.backend)
        stream = expected_stream(config, load_segment(args.mem, args.segment),
                                 line_mode=not args.dry_run_stream)
        if args.command == "expected":
            if args.out:
                args.out.write_bytes(stream)
            print(json.dumps({"backend": args.backend, "segment": args.segment, "bytes": len(stream),
                              "head_hex": stream[:32].hex(" ")}, indent=2))
            return 0
        from arm_serial_common import open_serial

        handle = open_serial(args.port, args.baud or profile.transport.baudrate, 0.05)
        received = bytearray()
        deadline = time.monotonic() + args.seconds
        try:
            while time.monotonic() < deadline and len(received) < len(stream):
                received += handle.read(4096)
        finally:
            handle.close()
        result = compare_stream(stream, bytes(received))
        print(json.dumps({"result": "PASS" if result.passed else "FAIL", "expected_bytes": result.expected,
                          "received_bytes": result.received, "first_mismatch": result.first_mismatch}, indent=2))
        return 0 if result.passed else 1

    backend = "so101" if args.command == "emulate-so101" else "roarm"
    profile, protocol, config = load_bench(backend)
    emulator = So101Emulator(protocol, config.device_ids) if backend == "so101" else RoArmEmulator(protocol)
    replies = run_emulator(args.port, args.baud or profile.transport.baudrate, emulator, seconds=args.seconds)
    print(json.dumps({"emulator": backend, "replies": replies}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
