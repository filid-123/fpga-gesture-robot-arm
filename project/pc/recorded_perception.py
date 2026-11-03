"""Auditable offline perception over the existing S6 RGB-D recording contract."""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict
from pathlib import Path

import cv2

from alignment import align_depth_to_color
from calibration import CalibrationSet
from detector import ColorBlobDetector, DetStatus
from grasp import GraspParams, top_down_grasp
from phase3_event_log import EventLog
from rgbd_device import RGBDDevice, RecordedRGBDDevice
from scene_config import SceneConfig


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class AuditedRecording(RGBDDevice):
    """Delegate decoding to S6; check each consumed frame against its provenance."""

    def __init__(self, directory: Path, calibration: CalibrationSet):
        self.inner = RecordedRGBDDevice(directory)
        self.calibration = calibration
        self.last_frame = None
        self.last_source = None
        self.reads = 0
        self.event_log = None

    def open(self):
        self.inner.open()
        manifest = self.inner.manifest
        if manifest.get("calib_id") != self.calibration.calib_id:
            raise ValueError("recording calib_id does not match calibration")
        acquisition = manifest.get("acquisition", {})
        if acquisition.get("depth_unit") != "mm" or acquisition.get("color_encoding") != "BGR":
            raise ValueError("recording must declare uint16 millimetres and BGR colour")
        if acquisition.get("geometry") != "undistorted_unaligned":
            raise ValueError("declare undistorted, unaligned camera frames before using S6 alignment")
        if self.calibration.depth_scale_mm != 1.0:
            raise ValueError("millimetre recording requires depth_scale_mm=1; do not scale twice")
        self.reads = 0
        self.last_frame = self.last_source = None

    def read(self):
        if self.reads >= len(self.inner.manifest["frames"]):
            self.last_frame = self.last_source = None
            return None
        record = self.inner.manifest["frames"][self.reads]
        path = (self.inner.dir / record["file"]).resolve()
        if not path.is_relative_to(self.inner.dir.resolve()):
            raise ValueError("recording frame path escapes its directory")
        actual = sha256(path)
        if actual != record.get("sha256"):
            raise ValueError(f"frame provenance mismatch: {record['file']}")
        frame = self.inner.read()
        calib = self.calibration
        if frame.color.shape[:2] != (calib.color.height, calib.color.width) or \
                frame.depth.shape != (calib.depth.height, calib.depth.width):
            raise ValueError("frame dimensions do not match calibration intrinsics")
        self.last_frame = frame
        self.last_source = {"file": record["file"], "sha256": actual,
                            "frame_index": frame.index, "color_ts_ns": frame.color_ts_ns,
                            "depth_ts_ns": frame.depth_ts_ns}
        self.reads += 1
        if self.event_log is not None:
            self.event_log.emit("recording_frame", **self.last_source)
        return frame

    def close(self):
        self.inner.close()

    def info(self):
        return {**self.inner.info(), "reads": self.reads,
                "acquisition": self.inner.manifest.get("acquisition", {}),
                "simulation": self.inner.manifest.get("simulation")}


def open_session(recording: Path, calibration: Path, scene: Path):
    """Load explicit input provenance before generating any robot-base coordinates."""
    recording, calibration, scene = map(Path, (recording, calibration, scene))
    calib = CalibrationSet.load(calibration)
    config = SceneConfig.load(scene)
    device = AuditedRecording(recording, calib)
    device.open()
    meta = device.inner.manifest
    for key, path in (("calibration_sha256", calibration), ("scene_sha256", scene)):
        if meta.get(key) != sha256(path):
            device.close()
            raise ValueError(f"recording {key} does not match supplied file")
    simulation = meta.get("simulation")
    if not isinstance(simulation, bool):
        raise ValueError("recording must declare simulation=true or false")
    if simulation is False and (calib.status == "SYNTHETIC" or config.status == "SYNTHETIC"):
        raise ValueError("real recording cannot use synthetic geometry as real coordinates")
    return device, calib, config, {
        "simulation": simulation, "recording_manifest_sha256": sha256(recording / "manifest.json"),
        "calibration_sha256": sha256(calibration), "scene_sha256": sha256(scene),
        "calibration_status": calib.status, "scene_status": config.status,
        "backend": "opencv_color_blob_cpu", "learned_model": False,
        "accelerator_tested": False, "physical_execution": False,
    }


def replay(recording, calibration, scene, output, object_ids=(1, 2, 3)):
    output = Path(output)
    device, calib, config, metadata = open_session(recording, calibration, scene)
    try:
        for object_id in object_ids:
            config.by_id(object_id)
        output.mkdir(parents=True, exist_ok=False)
        log = EventLog("pc", output / "perception.jsonl", meta=metadata)
        detector = ColorBlobDetector()
        reports = []
        with (output / "detections.jsonl").open("w", encoding="utf-8", newline="\n") as results:
            try:
                while True:
                    start = time.monotonic_ns()
                    frame = device.read()
                    if frame is None:
                        log.emit("recording_eof", frames=device.reads)
                        break
                    depth = align_depth_to_color(frame.depth, calib)
                    aligned = time.monotonic_ns()
                    overlay = frame.color.copy()
                    for object_id in object_ids:
                        det = detector.detect(frame.color, depth, calib, config, object_id)
                        # Defaults are synthetic: a grasp here is only a preview, never an executable plan.
                        grasp = top_down_grasp(det, config, GraspParams())
                        record = {"schema": "gesture.ai_pc.offline_detection.v1",
                                  "source": device.last_source, "object_id": object_id,
                                  "detection": asdict(det), "grasp_preview": asdict(grasp),
                                  "grasp_parameters_status": "SYNTHETIC",
                                  "calib_id": calib.calib_id, **metadata,
                                  "timing_ns": {"read_align": aligned - start,
                                                "through_detection": time.monotonic_ns() - start}}
                        results.write(json.dumps(record, default=str, allow_nan=False) + "\n")
                        reports.append(record)
                        log.emit("offline_detection", frame_index=frame.index, object=object_id,
                                 outcome=det.status.value, frame_sha256=device.last_source["sha256"],
                                 top_base_mm=det.top_base_mm, backend=metadata["backend"])
                        if det.status == DetStatus.FOUND:
                            u, v = (int(round(value)) for value in det.pixel_uv)
                            cv2.circle(overlay, (u, v), 7, (0, 255, 255), 2)
                            cv2.putText(overlay, f"ID {object_id}", (u + 9, v - 9),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
                    name = f"frame_{frame.index:06d}.png"
                    encoded, pixels = cv2.imencode(".png", overlay)
                    if not encoded:
                        raise RuntimeError("PNG encoding failed")
                    # imencode handles Windows paths with non-ASCII names without imwrite path issues.
                    (output / name).write_bytes(pixels.tobytes())
                summary = {"status": "PASS", "frames": device.reads, "detections": len(reports),
                           "data_kind": "SIMULATION" if metadata["simulation"] else "RECORDED_INPUT",
                           "physical_success": "NOT_MEASURED", **metadata}
                (output / "SUMMARY.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
                return reports, summary
            except Exception as exc:
                log.emit("offline_failure", error=str(exc), frames=device.reads)
                raise
            finally:
                log.close()
    finally:
        device.close()
