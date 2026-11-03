"""Replaceable RGB-D device interface + offline recording / replay (Phase 3 S6 candidate).

* RGBDFrame: color (H, W, 3) uint8 BGR, depth (H', W') uint16 millimetres (0 = invalid), timestamps.
* RGBDDevice: the interface every camera adapter implements (open / read / close / info).
* RecordedRGBDDevice + RGBDRecorder: a recording directory = manifest.json + frame_NNNNNN.npz
  (lossless numpy arrays); replay returns the frames bit-exactly in order.
* VendorSDKDevice: placeholder for Orbbec SDK v2 / RealSense adapters.  The SDKs, device model and
  firmware are not installed / not measured here, so it refuses to open (BLOCKED_EXTERNAL_INPUT);
  it never fabricates frames.
"""

from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

RECORDING_SCHEMA = "gesture.phase3.s6_rgbd_recording.v1"


@dataclass(frozen=True)
class RGBDFrame:
    index: int
    color: np.ndarray            # (H, W, 3) uint8, BGR
    depth: np.ndarray            # (H', W') uint16, millimetres, 0 = invalid
    color_ts_ns: int
    depth_ts_ns: int

    def check(self) -> None:
        if self.color.dtype != np.uint8 or self.color.ndim != 3 or self.color.shape[2] != 3:
            raise ValueError("color must be (H, W, 3) uint8")
        if self.depth.dtype != np.uint16 or self.depth.ndim != 2:
            raise ValueError("depth must be (H, W) uint16 millimetres")


class DeviceUnavailable(RuntimeError):
    """The requested camera / SDK is not available in this environment."""


class RGBDDevice(ABC):
    @abstractmethod
    def open(self) -> None: ...

    @abstractmethod
    def read(self) -> Optional[RGBDFrame]:
        """Next frame, or None at the end of a recording."""

    @abstractmethod
    def close(self) -> None: ...

    @abstractmethod
    def info(self) -> dict: ...

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *exc):
        self.close()


class RecordedRGBDDevice(RGBDDevice):
    def __init__(self, directory: Path):
        self.dir = Path(directory)
        self.manifest: dict = {}
        self._i = 0

    def open(self) -> None:
        self.manifest = json.loads((self.dir / "manifest.json").read_text(encoding="utf-8"))
        if self.manifest.get("schema") != RECORDING_SCHEMA:
            raise ValueError(f"not an S6 RGB-D recording: {self.dir}")
        self._i = 0

    def read(self) -> Optional[RGBDFrame]:
        frames = self.manifest["frames"]
        if self._i >= len(frames):
            return None
        rec = frames[self._i]
        with np.load(self.dir / rec["file"]) as z:
            frame = RGBDFrame(rec["index"], z["color"].copy(), z["depth"].copy(), rec["color_ts_ns"], rec["depth_ts_ns"])
        self._i += 1
        frame.check()
        return frame

    def close(self) -> None:
        self._i = 0

    def info(self) -> dict:
        return {"kind": "recording", "path": str(self.dir), "source": self.manifest.get("source"),
                "frames": len(self.manifest.get("frames", [])), "calib_id": self.manifest.get("calib_id")}


class RGBDRecorder:
    def __init__(self, directory: Path, source: str, calib_id: int):
        self.dir = Path(directory)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.manifest = {"schema": RECORDING_SCHEMA, "source": source, "calib_id": calib_id, "frames": []}

    def add(self, frame: RGBDFrame) -> None:
        frame.check()
        name = f"frame_{frame.index:06d}.npz"
        np.savez_compressed(self.dir / name, color=frame.color, depth=frame.depth)
        self.manifest["frames"].append({"index": frame.index, "file": name, "color_ts_ns": frame.color_ts_ns,
                                        "depth_ts_ns": frame.depth_ts_ns})

    def close(self) -> None:
        (self.dir / "manifest.json").write_bytes((json.dumps(self.manifest, indent=2) + "\n").encode("utf-8"))


class VendorSDKDevice(RGBDDevice):
    """Integration point for a real camera (Orbbec Gemini 2 via Orbbec SDK v2, or RealSense D435i).

    Status: BLOCKED_EXTERNAL_INPUT - the camera, SDK version, stream profiles, alignment mode and
    intrinsics are not available here.  Implement read() with the vendor SDK and return RGBDFrame
    with depth in millimetres; keep calibration in calibration.CalibrationSet, not in this class."""

    SUPPORTED = ("orbbec_sdk_v2", "realsense")

    def __init__(self, sdk: str):
        if sdk not in self.SUPPORTED:
            raise ValueError(f"unknown SDK {sdk}")
        self.sdk = sdk

    def open(self) -> None:
        module = {"orbbec_sdk_v2": "pyorbbecsdk", "realsense": "pyrealsense2"}[self.sdk]
        try:
            __import__(module)
        except ImportError as exc:
            raise DeviceUnavailable(f"{self.sdk}: Python module {module} not installed (BLOCKED_EXTERNAL_INPUT)") from exc
        raise DeviceUnavailable(f"{self.sdk}: adapter not implemented until the camera and SDK are measured")

    def read(self) -> Optional[RGBDFrame]:
        raise DeviceUnavailable(self.sdk)

    def close(self) -> None:
        pass

    def info(self) -> dict:
        return {"kind": "vendor_sdk", "sdk": self.sdk, "status": "BLOCKED_EXTERNAL_INPUT"}


def now_ns() -> int:
    return time.monotonic_ns()
