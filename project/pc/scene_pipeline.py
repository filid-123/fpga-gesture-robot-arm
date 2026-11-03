"""S7 additions on the PC side, built on the unchanged S6 modules:
ScenePipeline  = S6 PickPipeline + detect_only() (one fresh frame, detection only) for the scene checks;
ScriptedSceneDevice = SYNTHETIC RGB-D device whose cube layout follows a script of the simulated time
                      (for the S7 scene-change scenarios; frames are rendered once per layout and reused).
"""

from __future__ import annotations

from typing import Callable

from alignment import align_depth_to_color
from pick_pipeline import PickPipeline
from rgbd_device import RGBDDevice


class ScenePipeline(PickPipeline):
    def detect_only(self, object_id: int):
        frame = self.device.read()
        if frame is None:
            from detector import Detection, DetStatus
            return Detection(object_id, DetStatus.NOT_FOUND)
        depth = align_depth_to_color(frame.depth, self.calib)
        return self.detector.detect(frame.color, depth, self.calib, self.scene, object_id)


class ScriptedSceneDevice(RGBDDevice):
    """layout_at(t) -> tuple of CubePose; clock() -> simulated seconds."""

    def __init__(self, layout_at: Callable[[float], tuple], clock: Callable[[], float], seed: int = 7):
        import synthetic_scene as ss
        self.ss, self.layout_at, self.clock, self.seed = ss, layout_at, clock, seed
        self._cache: dict = {}
        self.reads = 0

    def open(self) -> None:
        pass

    def read(self):
        layout = tuple(self.layout_at(self.clock()))
        if layout not in self._cache:
            self._cache[layout] = self.ss.render_frame(list(layout), index=len(self._cache), seed=self.seed + len(self._cache))
        self.reads += 1
        return self._cache[layout]

    def close(self) -> None:
        pass

    def info(self) -> dict:
        return {"kind": "synthetic_scripted", "layouts": len(self._cache), "reads": self.reads, "status": "SYNTHETIC"}
