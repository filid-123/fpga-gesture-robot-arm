"""Minimal Phase 3 event log (JSON lines), shared by the PS services, the PC side and the simulations.

Line 1 is a header, every further line one record:
  header  {"schema": "gesture.phase3.event_log.v1", "host": "ps", "clock": "monotonic_ns",
           "clock_id": "<host>-<pid>-<start>", "wall_utc_at_start": "...", "meta": {...}}
  record  {"t_ns": <int, the host's monotonic clock>, "ev": "<name>", "task": <int|null>, ...fields}
Timestamps are raw integers of ONE host clock per file (no conversion, no rounding), so every
duration is computed later from two records of the same clock_id.  Cross-host durations need a
measured clock offset and are reported as such by the S8 tools, never silently mixed.
Simulated runs use host "sim" and a simulated clock; their numbers are simulation time, not
wall-clock latency.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

SCHEMA = "gesture.phase3.event_log.v1"


class EventLog:
    def __init__(self, host: str, path: Optional[Path] = None, clock: Callable[[], int] = time.monotonic_ns,
                 clock_name: str = "monotonic_ns", meta: Optional[dict] = None):
        self.host, self.clock = host, clock
        self.records: list = []
        self.header = {"schema": SCHEMA, "host": host, "clock": clock_name,
                       "clock_id": f"{host}-{os.getpid()}-{clock()}",
                       "wall_utc_at_start": datetime.now(timezone.utc).isoformat(), "meta": meta or {}}
        self._fh = None
        if path is not None:
            self._fh = open(path, "wb")
            self._write(self.header)

    def _write(self, obj: dict) -> None:
        self._fh.write((json.dumps(obj, sort_keys=True) + "\n").encode("utf-8"))
        self._fh.flush()

    def emit(self, ev: str, task: Optional[int] = None, **fields) -> dict:
        rec = {"t_ns": int(self.clock()), "ev": ev, "task": task, **fields}
        self.records.append(rec)
        if self._fh is not None:
            self._write(rec)
        return rec

    def find(self, ev: str) -> list:
        return [r for r in self.records if r["ev"] == ev]

    def close(self) -> None:
        if self._fh is not None:
            self._fh.close()
            self._fh = None


def read_log(path: Path) -> tuple:
    """(header, records) of one JSON-lines log; raises ValueError on a foreign file."""

    lines = Path(path).read_bytes().decode("utf-8").splitlines()
    if not lines:
        raise ValueError(f"{path}: empty log")
    header = json.loads(lines[0])
    if header.get("schema") != SCHEMA:
        raise ValueError(f"{path}: not a {SCHEMA} file")
    return header, [json.loads(l) for l in lines[1:] if l.strip()]
