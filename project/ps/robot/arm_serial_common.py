"""Shared pyserial plumbing for the PC/PS bring-up transports.

Safety notes
------------
* Dry-run is the default: no port is opened and nothing is transmitted.
* Opening a real port requires a ``RealOutputPermit`` (``arm_backend``).
* ESP32 USB-UART bridges commonly wire DTR/RTS to reset/boot.  Opening a port
  with default settings can reset the controller and make the arm move to its
  power-on pose.  ``open_serial`` configures DTR/RTS low *before* opening, but
  this is controller-dependent: keep the e-stop in hand on every first open.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Callable, Protocol


class SerialLike(Protocol):
    def write(self, data: bytes) -> int: ...
    def read(self, size: int = 1) -> bytes: ...
    def close(self) -> None: ...
    def reset_input_buffer(self) -> None: ...


SerialFactory = Callable[[str, int, float], SerialLike]


def open_serial(port: str, baudrate: int, timeout_s: float) -> SerialLike:
    """Open an 8N1 port with DTR/RTS deasserted before the open call."""

    import serial  # pyserial; imported lazily so offline tests need no port

    handle = serial.Serial()
    handle.port = port
    handle.baudrate = baudrate
    handle.bytesize = serial.EIGHTBITS
    handle.parity = serial.PARITY_NONE
    handle.stopbits = serial.STOPBITS_ONE
    handle.timeout = timeout_s
    handle.write_timeout = 1.0
    handle.rtscts = False
    handle.dsrdtr = False
    handle.dtr = False
    handle.rts = False
    handle.open()
    return handle


@dataclass(frozen=True)
class TxRecord:
    timestamp_ns: int
    data: bytes
    transmitted: bool


@dataclass(frozen=True)
class RxRecord:
    timestamp_ns: int
    data: bytes


def monotonic_ns() -> int:
    return time.monotonic_ns()


def percentile(values: list[float], percentage: float) -> float:
    """Nearest-rank percentile, matching replay_golden_trajectory.percentile."""

    if not values:
        raise ValueError("cannot calculate a percentile of an empty sequence")
    if percentage < 0.0 or percentage > 100.0:
        raise ValueError("percentage must be in [0, 100]")
    ordered = sorted(values)
    index = max(0, math.ceil((percentage / 100.0) * len(ordered)) - 1)
    return ordered[index]
