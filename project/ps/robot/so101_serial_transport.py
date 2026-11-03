"""Feetech half-duplex bus transport for SO-ARM101 PC bring-up (pyserial).

Used with a USB bus adapter that already handles the half-duplex direction
(the PL path uses ``arm_half_duplex_dir_ctrl`` instead).  Each call is one
request/response transaction; dry-run (default) never opens a port.

``echo="discard"`` supports adapters that return the transmitted bytes; the
echo must match the request exactly or the transaction fails.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from arm_backend import RealOutputPermit
from arm_profile import RealOutputBlocked
from arm_serial_common import SerialFactory, SerialLike, TxRecord, monotonic_ns, open_serial
from so101_feetech_reference import (
    FeetechProtocol,
    StatusParserConfig,
    StatusParserEvent,
    StatusStreamParserModel,
)


@dataclass(frozen=True)
class Transaction:
    tx: TxRecord
    rx_timestamp_ns: int | None
    reply: StatusParserEvent | None
    error: str | None


@dataclass
class FeetechSerialTransport:
    port: str | None
    baudrate: int
    protocol: FeetechProtocol
    permit: RealOutputPermit | None = None
    dry_run: bool = True
    echo: str = "none"                  # "none" | "discard"
    serial_factory: SerialFactory = open_serial
    clock_ns: callable = monotonic_ns  # type: ignore[valid-type]
    dry_run_log: list[TxRecord] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.echo not in ("none", "discard"):
            raise ValueError("echo must be 'none' or 'discard'")
        self._serial: SerialLike | None = None
        self._parser_config = StatusParserConfig.from_protocol(self.protocol) if not \
            self.protocol.codec_blockers() else None

    def open(self) -> None:
        if self.dry_run:
            return
        if self.permit is None or self.permit.purpose not in ("robot", "robot_readonly", "bench_loopback"):
            raise RealOutputBlocked(["opening a real servo bus requires a RealOutputPermit"])
        if not self.port:
            raise RealOutputBlocked(["transport.port is TBD"])
        self._serial = self.serial_factory(self.port, self.baudrate, 0.002)

    def close(self) -> None:
        if self._serial is not None:
            self._serial.close()
            self._serial = None

    def transact(
        self,
        packet: bytes,
        *,
        expect_reply: bool,
        expected_id: int | None = None,
        timeout_s: float = 0.01,
        writes_motion: bool = False,
    ) -> Transaction:
        stamp = self.clock_ns()
        if self.dry_run:
            record = TxRecord(stamp, bytes(packet), False)
            self.dry_run_log.append(record)
            return Transaction(record, None, None, "dry_run")
        if self._serial is None:
            raise RuntimeError("transport is not open")
        if writes_motion and (self.permit is None or self.permit.purpose == "robot_readonly"):
            raise RealOutputBlocked(["this permit does not allow writes"])
        self._serial.reset_input_buffer()
        written = self._serial.write(packet)
        record = TxRecord(stamp, bytes(packet), written == len(packet))
        if written != len(packet):
            return Transaction(record, None, None, "write_incomplete")
        if self.echo == "discard":
            echo = self._read_exact(len(packet), timeout_s)
            if echo != packet:
                return Transaction(record, None, None, "echo_mismatch")
        if not expect_reply:
            return Transaction(record, None, None, None)
        if self._parser_config is None or expected_id is None:
            raise ValueError("replies need a complete protocol and expected_id")
        parser = StatusStreamParserModel(self._parser_config, expected_id=expected_id)
        deadline = self.clock_ns() + int(timeout_s * 1e9)
        while self.clock_ns() < deadline:
            data = self._serial.read(1)
            if not data:
                continue
            events = parser.feed(data)
            if events:
                event = events[0]
                error = None if event.kind == "packet" else event.kind
                return Transaction(record, self.clock_ns(), event, error)
        return Transaction(record, None, None, "response_timeout")

    def _read_exact(self, count: int, timeout_s: float) -> bytes:
        assert self._serial is not None
        data = bytearray()
        deadline = self.clock_ns() + int(timeout_s * 1e9)
        while len(data) < count and self.clock_ns() < deadline:
            data += self._serial.read(count - len(data))
        return bytes(data)
