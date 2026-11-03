"""Display a known-size table-plane outline; no robot access or motion permission."""
from pathlib import Path
import hashlib
import json

import cv2
import numpy as np

from pc.rgb_table_geometry import RGBTableGeometry


class RGBWorkspaceOverlay:
    def __init__(self, config_path, project_root=None):
        root = Path(project_root or Path(__file__).resolve().parents[1])
        config_path = Path(config_path).resolve()
        raw = config_path.read_bytes()
        config = json.loads(raw)
        if config.get("schema") != "gesture.ai_pc.rgb_workspace_overlay.v1":
            raise ValueError("Unknown workspace overlay schema")
        table_path = root / config["table_file"]
        if hashlib.sha256(table_path.read_bytes()).hexdigest() != config["table_sha256"]:
            raise ValueError("Workspace/table hash mismatch")
        self.geometry = RGBTableGeometry(table_path, root)
        if config["table_frame_id"] != self.geometry.table["table_frame_id"]:
            raise ValueError("Workspace/table frame mismatch")
        centre = np.asarray(config["centre_table_xy_mm"], dtype=float)
        size = np.asarray(config["size_wh_mm"], dtype=float)
        if (centre.shape != (2,) or size.shape != (2,) or
                not np.isfinite(centre).all() or not np.isfinite(size).all() or (size <= 0).any()):
            raise ValueError("Invalid workspace centre or size")
        self.config = config
        half = size / 2
        self.corners = np.column_stack((centre + np.array([
            [-half[0], -half[1]], [half[0], -half[1]],
            [half[0], half[1]], [-half[0], half[1]]]), np.zeros(4)))
        # Sample each edge: lens distortion can curve a straight physical boundary.
        self.boundary = np.concatenate([
            a[None, :] + np.linspace(0, 1, 33, endpoint=False)[:, None] * (b-a)
            for a, b in zip(self.corners, np.roll(self.corners, -1, axis=0))])
        self.pixels = self.project(self.boundary)
        if not ((self.pixels >= 0).all() and
                (self.pixels < np.array(self.geometry.size)).all()):
            raise ValueError("Workspace outline leaves image; review placement before preview")
        self.centre_pixel = self.project([[*centre, 0]])[0]
        self.record = {"config": config, "config_file": str(config_path),
                       "config_sha256": hashlib.sha256(raw).hexdigest(),
                       "geometry": self.geometry.record,
                       "metric_validation": "PENDING_INDEPENDENT_RULER",
                       "physical_execution": False}

    def project(self, points):
        geometry = self.geometry
        points = np.asarray(points, dtype=np.float64)
        camera = points @ geometry.R.T + geometry.t
        if not np.isfinite(camera).all() or (camera[:, 2] <= 0).any():
            raise ValueError("Workspace points behind camera or invalid")
        return cv2.projectPoints(points, cv2.Rodrigues(geometry.R)[0], geometry.t,
                                 geometry.K, geometry.dist)[0].reshape(-1, 2)

    def draw(self, display):
        scale = np.array([display.shape[1], display.shape[0]]) / self.geometry.size
        pixels = np.rint(self.pixels * scale).astype(np.int32)
        cv2.polylines(display, [pixels], True, (0, 255, 0), 2, cv2.LINE_AA)
        for p in self.project(self.corners):
            cv2.circle(display, tuple(np.rint(p * scale).astype(int)), 5, (0, 255, 255), 2)
        cv2.drawMarker(display, tuple(np.rint(self.centre_pixel * scale).astype(int)),
                       (0, 255, 255), cv2.MARKER_CROSS, 18, 2)
        width, height = self.config["size_wh_mm"]
        lines = [f"TABLE outline: {width:g} x {height:g} mm | z=0",
                 "CANDIDATE: verify with ruler | RAW PNG saved without overlay"]
        for index, text in enumerate(lines):
            point = (12, display.shape[0] - 38 + index * 23)
            cv2.putText(display, text, point, cv2.FONT_HERSHEY_SIMPLEX, .5,
                        (0, 0, 0), 3, cv2.LINE_AA)
            cv2.putText(display, text, point, cv2.FONT_HERSHEY_SIMPLEX, .5,
                        (0, 255, 0), 1, cv2.LINE_AA)
