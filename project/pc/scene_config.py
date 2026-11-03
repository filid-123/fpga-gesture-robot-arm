"""Registered objects and the limited workspace (Phase 3 S6 candidate).

Exactly three REGISTERED objects, mapped to gestures 1/2/3; one instance each; limited table
workspace; fixed return tray.  No unknown categories, stacking or arbitrary poses are handled.
Every physical value (colour ranges, sizes, workspace bounds, tray pose) is TBD until the objects,
the RGB-D camera and the arm are measured; the bundled config/scene_registered_objects.json holds
SYNTHETIC values used only by the synthetic-scene tests.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

SCHEMA = "gesture.phase3.s6_scene.v1"


@dataclass(frozen=True)
class RegisteredObject:
    object_id: int               # 1..3 = gesture OBJECT_1..3
    name: str
    hsv_low: tuple               # OpenCV HSV (H 0..179)
    hsv_high: tuple
    size_mm: float               # nominal edge / diameter
    min_area_px: int
    max_area_px: int


@dataclass(frozen=True)
class Workspace:
    x_mm: tuple                  # robot-base frame bounds (min, max)
    y_mm: tuple
    table_z_mm: float
    max_object_height_mm: float
    tray_xyz_mm: tuple           # fixed return tray (cancel in mode B)
    status: str = "TBD"          # MEASURED | SYNTHETIC | TBD

    def contains(self, x: float, y: float) -> bool:
        return self.x_mm[0] <= x <= self.x_mm[1] and self.y_mm[0] <= y <= self.y_mm[1]


@dataclass(frozen=True)
class SceneConfig:
    status: str
    objects: tuple
    workspace: Workspace

    def by_id(self, object_id: int) -> RegisteredObject:
        for o in self.objects:
            if o.object_id == object_id:
                return o
        raise KeyError(object_id)

    @classmethod
    def load(cls, path: Path) -> "SceneConfig":
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        if d.get("schema") != SCHEMA:
            raise ValueError(f"{path}: not an S6 scene config")
        objs = tuple(RegisteredObject(o["object_id"], o["name"], tuple(o["hsv_low"]), tuple(o["hsv_high"]), o["size_mm"],
                                      o["min_area_px"], o["max_area_px"]) for o in d["objects"])
        if sorted(o.object_id for o in objs) != [1, 2, 3]:
            raise ValueError("exactly three registered objects with ids 1, 2, 3 are required")
        w = d["workspace"]
        ws = Workspace(tuple(w["x_mm"]), tuple(w["y_mm"]), w["table_z_mm"], w["max_object_height_mm"],
                       tuple(w["tray_xyz_mm"]), w["status"])
        return cls(d["status"], objs, ws)
