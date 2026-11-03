"""RoArm-M3 JSON-line serial transport for PC/PS bring-up (pyserial).

* A reader thread splits the byte stream on the line terminator, timestamps
  every complete line with ``time.monotonic_ns()`` and queues it (bounded,
  oldest dropped and counted).
* ``dry_run=True`` (default) never opens a port: ``send_line`` records the
  frame with ``transmitted=False``.
* A real port needs a ``RealOutputPermit``; purpose ``robot_readonly`` allows
  listening only (``send_line`` refuses).

This path exists to measure the official JSON interface (sustained rate,
feedback latency) before the PL takes over.  It is not the final control path.
"""

from __future__ import annotations

import collections
import threading
from dataclasses import dataclass, field

from arm_backend import RealOutputPermit
from arm_profile import RealOutputBlocked
from arm_serial_common import RxRecord, SerialFactory, SerialLike, TxRecord, monotonic_ns, open_serial


@dataclass
class TransportStats:
    tx_lines: int = 0
    rx_lines: int = 0
    rx_dropped: int = 0
    rx_overlong: int = 0


@dataclass
class RoArmSerialTransport:
    port: str | None
    baudrate: int
    permit: RealOutputPermit | None = None
    dry_run: bool = True
    line_terminator: bytes = b"\n"
    max_line_length: int = 512
    max_queue: int = 256
    serial_factory: SerialFactory = open_serial
    clock_ns: callable = monotonic_ns  # type: ignore[valid-type]
    stats: TransportStats = field(default_factory=TransportStats)
    dry_run_log: list[TxRecord] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._serial: SerialLike | None = None
        self._rx: collections.deque[RxRecord] = collections.deque()
        self._rx_ready = threading.Condition()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        if len(self.line_terminator) != 1:
            raise ValueError("single-byte line terminator expected")

    # ----------------------------------------------------------------- open
    def open(self) -> None:
        if self.dry_run:
            return
        if self.permit is None:
            raise RealOutputBlocked(["opening a real RoArm port requires a RealOutputPermit"])
        if self.permit.purpose not in ("robot", "robot_readonly", "bench_loopback"):
            raise RealOutputBlocked([f"permit purpose {self.permit.purpose!r} cannot open a port"])
        if not self.port:
            raise RealOutputBlocked(["transport.port is TBD"])
        self._serial = self.serial_factory(self.port, self.baudrate, 0.05)
        self._serial.reset_input_buffer()
        self._stop.clear()
        self._thread = threading.Thread(target=self._reader, name="roarm-rx", daemon=True)
        self._thread.start()

    def close(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None
        if self._serial is not None:
            self._serial.close()
            self._serial = None

    def __enter__(self) -> "RoArmSerialTransport":
        self.open()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    # ------------------------------------------------------------------- tx
    def send_line(self, line: bytes) -> TxRecord:
        if not line.endswith(self.line_terminator) or self.line_terminator in line[:-1]:
            raise ValueError("exactly one terminated line must be sent per call")
        stamp = self.clock_ns()
        if self.dry_run:
            record = TxRecord(stamp, bytes(line), False)
            self.dry_run_log.append(record)
            return record
        if self._serial is None:
            raise RuntimeError("transport is not open")
        if self.permit is None or self.permit.purpose == "robot_readonly":
            raise RealOutputBlocked(["this permit allows listening only"])
        written = self._serial.write(line)
        if written != len(line):
            raise TimeoutError(f"serial write incomplete: {written}/{len(line)} bytes")
        self.stats.tx_lines += 1
        return TxRecord(stamp, bytes(line), True)

    # ------------------------------------------------------------------- rx
    def _reader(self) -> None:
        buffer = bytearray()
        assert self._serial is not None
        while not self._stop.is_set():
            chunk = self._serial.read(256)
            if not chunk:
                continue
            for byte in chunk:
                if byte == self.line_terminator[0]:
                    self._push(RxRecord(self.clock_ns(), bytes(buffer) + self.line_terminator))
                    buffer.clear()
                elif len(buffer) >= self.max_line_length:
                    self.stats.rx_overlong += 1
                    buffer.clear()
                else:
                    buffer.append(byte)

    def _push(self, record: RxRecord) -> None:
        with self._rx_ready:
            if len(self._rx) >= self.max_queue:
                self._rx.popleft()
                self.stats.rx_dropped += 1
            self._rx.append(record)
            self.stats.rx_lines += 1
            self._rx_ready.notify()

    def feed_for_test(self, data: bytes) -> None:
        """Inject bytes as if received (offline tests and dry-run replays)."""

        buffer = bytearray()
        for byte in data:
            if byte == self.line_terminator[0]:
                self._push(RxRecord(self.clock_ns(), bytes(buffer) + self.line_terminator))
                buffer.clear()
            else:
                buffer.append(byte)

    def read_line(self, timeout_s: float) -> RxRecord | None:
        with self._rx_ready:
            if not self._rx:
                self._rx_ready.wait(timeout=timeout_s)
            return self._rx.popleft() if self._rx else None
