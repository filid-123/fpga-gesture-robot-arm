"""Interactive RGB-only colour sampling and pixel localisation; no robot coordinates."""
from __future__ import annotations

import json
import time
from pathlib import Path

import cv2
import numpy as np

SCHEMA = "gesture.ai_pc.rgb_color_profile.v1"
PALETTE = {1: (40, 80, 255), 2: (255, 170, 30), 3: (30, 220, 220)}


def make_profile(width, height):
    return {"schema": SCHEMA, "image_size": [width, height],
            "roi_xywh": [int(width * .15), int(height * .12), int(width * .70), int(height * .71)],
            "objects": [], "coordinates": "raw_image_pixels", "calibration": None,
            "min_area_fraction": .001, "max_area_fraction": .25}


def validate_profile(profile, shape):
    height, width = shape[:2]
    if profile.get("schema") != SCHEMA or profile.get("image_size") != [width, height]:
        raise ValueError("颜色配置的分辨率与实际图像不符，请重新取色")
    roi = profile["roi_xywh"]
    if len(roi) != 4 or any(type(v) is not int for v in roi):
        raise ValueError("ROI must contain four integer pixel coordinates")
    x, y, w, h = roi
    if min(x, y) < 0 or min(w, h) < 10 or x + w > width or y + h > height:
        raise ValueError("ROI is outside the image or too small")
    low, high = profile["min_area_fraction"], profile["max_area_fraction"]
    if not 0 < low < high < 1:
        raise ValueError("Invalid colour area limits")
    seen = set()
    for obj in profile["objects"]:
        oid = obj["object_id"]
        if oid not in (1, 2, 3) or oid in seen:
            raise ValueError("Colour IDs must be unique values 1, 2, 3")
        seen.add(oid)
        if not obj["hsv_ranges"]:
            raise ValueError("Empty colour range")
        for pair in obj["hsv_ranges"]:
            if len(pair) != 2 or any(len(row) != 3 for row in pair):
                raise ValueError("HSV range needs two triplets")
            a, b = np.array(pair[0]), np.array(pair[1])
            if np.any(a < 0) or np.any(b > [179, 255, 255]) or np.any(a > b):
                raise ValueError("Invalid HSV bounds")


def sample_color(frame, profile, object_id, u, v):
    validate_profile(profile, frame.shape)
    x, y, w, h = profile["roi_xywh"]
    if not (x + 5 <= u < x + w - 5 and y + 5 <= v < y + h - 5):
        raise ValueError("请点击工作区内的物体顶部，避开边缘")
    patch = cv2.cvtColor(frame[v-4:v+5, u-4:u+5], cv2.COLOR_BGR2HSV).reshape(-1, 3)
    sat, val = np.median(patch[:, 1:], axis=0)
    if val < 60:
        raise ValueError("取色点过暗，请点击明亮的物体表面")
    if sat < 45:
        # White is a provisional demonstration profile, not a colour identity.
        ranges = [[[0, 0, int(max(80, val - 55))], [179, int(min(80, sat + 35)), 255]]]
        mode = "low_saturation_demo"
    else:
        angles = patch[:, 0].astype(float) * (2 * np.pi / 180)
        mean = np.mean(np.exp(1j * angles))
        if abs(mean) < .85:
            raise ValueError("取色区域颜色不均匀，请点击纯色顶部中央")
        hue = int(round((np.angle(mean) % (2 * np.pi)) * 180 / (2 * np.pi))) % 180
        lo, hi = hue - 12, hue + 12
        spans = [(lo, hi)] if 0 <= lo and hi <= 179 else (
            [(0, hi), (lo + 180, 179)] if lo < 0 else [(lo, 179), (0, hi - 180)])
        ranges = [[[a, int(max(55, sat - 75)), int(max(40, val - 100))], [b, 255, 255]] for a, b in spans]
        mode = "chromatic"
    obj = {"object_id": object_id, "sample_uv": [u, v], "mode": mode,
           "hsv_ranges": ranges, "sample_median_sv": [float(sat), float(val)]}
    profile["objects"] = sorted([o for o in profile["objects"] if o["object_id"] != object_id] + [obj],
                                key=lambda o: o["object_id"])
    return obj


def detect_colors(frame, profile):
    validate_profile(profile, frame.shape)
    x, y, w, h = profile["roi_xywh"]
    hsv = cv2.cvtColor(frame[y:y+h, x:x+w], cv2.COLOR_BGR2HSV)
    configured = {o["object_id"]: o for o in profile["objects"]}
    results, selections = [], {}
    for oid in (1, 2, 3):
        result = {"object_id": oid, "status": "UNCONFIGURED", "pixel_uv": None,
                  "candidates": [], "coordinate_system": "raw_image_pixels",
                  "base_xyz_mm": None, "depth_available": False, "physical_execution": False}
        if oid in configured:
            mask = np.zeros((h, w), np.uint8)
            for lo, hi in configured[oid]["hsv_ranges"]:
                mask |= cv2.inRange(hsv, np.array(lo, np.uint8), np.array(hi, np.uint8))
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
            count, labels, stats, centers = cv2.connectedComponentsWithStats(mask, connectivity=8)
            valid = [k for k in range(1, count)
                     if w*h*profile["min_area_fraction"] <= stats[k, cv2.CC_STAT_AREA] <= w*h*profile["max_area_fraction"]]
            result["status"] = "NOT_FOUND" if not valid else "MULTIPLE_INSTANCES"
            for k in valid:
                bx, by, bw, bh, area = map(int, stats[k])
                result["candidates"].append({"bbox_xywh": [bx+x, by+y, bw, bh], "area_px": area,
                    "pixel_uv": [float(centers[k][0]+x), float(centers[k][1]+y)]})
            if len(valid) == 1:
                candidate = result["candidates"][0]
                bx, by, bw, bh = candidate["bbox_xywh"]
                edge = bx <= x or by <= y or bx+bw >= x+w or by+bh >= y+h
                result["status"] = "ROI_EDGE" if edge else "FOUND"
                if not edge:
                    result["pixel_uv"] = candidate["pixel_uv"]
                    selections[oid] = labels == valid[0]
        results.append(result)
    for a in selections:
        for b in selections:
            if a < b:
                overlap = np.count_nonzero(selections[a] & selections[b])
                if overlap > .3 * min(np.count_nonzero(selections[a]), np.count_nonzero(selections[b])):
                    for result in results:
                        if result["object_id"] in (a, b):
                            result["status"], result["pixel_uv"] = "PROFILE_CONFLICT", None
    return results


class Stability:
    """Pixel-position consistency only; never claims the hand has left or a grasp is safe."""
    def __init__(self):
        self.history = {}

    def update(self, detections, received_ns):
        for result in detections:
            oid = result["object_id"]
            result["stable"] = False
            if result["status"] != "FOUND":
                self.history.pop(oid, None)
                continue
            uv = np.array(result["pixel_uv"])
            old = self.history.get(oid)
            if (old is None or received_ns <= old["last_ns"] or received_ns-old["last_ns"] > 1_000_000_000
                    or np.linalg.norm(uv-old["anchor"]) > 10):
                old = {"anchor": uv, "first_ns": received_ns, "count": 0}
            old.update(last_ns=received_ns, count=old["count"]+1)
            self.history[oid] = old
            result["stable"] = old["count"] >= 3 and received_ns-old["first_ns"] >= 300_000_000
        return detections


class ColorPreview:
    def __init__(self, frame, directory, log, profile_path=None, table_geometry=None, top_height_mm=30,
                 auto_top=False, cube_side_mm=30, image_processing=None):
        self.directory, self.log = directory, log
        self.profile = (json.loads(Path(profile_path).read_text(encoding="utf-8")) if profile_path
                        else make_profile(frame.shape[1], frame.shape[0]))
        if profile_path and self.profile.get("image_processing") != image_processing:
            raise ValueError("颜色配置的图像处理方式不匹配，请在当前工具中重新取色")
        if image_processing is not None:
            self.profile["image_processing"] = image_processing
        validate_profile(self.profile, frame.shape)
        self.active_id, self.revision = 1, 0
        self.frame, self.display_shape, self.frame_index = frame.copy(), None, 0
        self.stability, self.results = Stability(), []
        self._last_logged, self._last_log_ns = None, 0
        self._processed_key = None
        self.table_geometry, self.top_height_mm = table_geometry, top_height_mm
        self.top_mode, self.top_points = False, {}
        self.auto_top, self.cube_side_mm = auto_top, cube_side_mm
        if auto_top and table_geometry is None:
            raise ValueError("自动顶部预览需要桌面标定")
        if auto_top:
            self.log.emit("rgb_auto_top_enabled", assumed_top_height_mm=top_height_mm,
                          expected_cube_side_mm=cube_side_mm, physical_execution=False,
                          scope="Heuristic candidates; user reviews polygon and centre")
            print("自动顶部候选已开启：无需点击中心；请核审轮廓与圆点，S 保存。T 仍可切换人工点选作对照。", flush=True)
        if table_geometry is not None:
            table_geometry.check_frame(frame.shape)
            (self.directory / "table_geometry.json").write_text(
                json.dumps(table_geometry.record, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
            self.log.emit("rgb_table_geometry_loaded", table_sha256=table_geometry.record["table_sha256"],
                          geometry=table_geometry.record, assumed_top_height_mm=top_height_mm)
            if not auto_top:
                print("毫米预览：取色并等待 STABLE 后，按 T 切换到顶部点模式，再选 1/2/3 点击对应木块顶部中心。", flush=True)
        self._save_profile()
        print("颜色预览：按 1/2/3 选择编号，再点击对应方块顶部取色；R 调整工作区；S 保存；Q 退出。", flush=True)

    def _save_profile(self):
        path = self.directory / "color_profile.json"
        path.write_text(json.dumps(self.profile, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
        self.log.emit("rgb_color_profile", revision=self.revision, profile=self.profile)

    def mouse(self, event, x, y, flags, param):
        if event != cv2.EVENT_LBUTTONDOWN or self.display_shape is None:
            return
        dh, dw = self.display_shape[:2]
        h, w = self.frame.shape[:2]
        u, v = int(x*w/dw), int(y*h/dh)
        try:
            if self.top_mode:
                result = next(d for d in self.results if d["object_id"] == self.active_id)
                if result["status"] != "FOUND" or not result["stable"]:
                    raise ValueError("该物体尚未 FOUND STABLE，请先取色并等待停稳")
                bx, by, bw, bh = result["candidates"][0]["bbox_xywh"]
                if not (bx <= u < bx+bw and by <= v < by+bh):
                    raise ValueError("请点击当前编号检测框内的木块顶部中心")
                point = self.table_geometry.manual_top([u, v], self.top_height_mm)
                point.update(object_id=self.active_id, selected_frame_index=self.frame_index,
                             profile_revision=self.revision, selected_received_monotonic_ns=self.received_ns,
                             retained_under_max_centroid_drift_px=3)
                self.top_points[self.active_id] = {"point": point, "anchor": result["pixel_uv"].copy()}
                result["manual_top_candidate"] = point
                self.log.emit("rgb_manual_top_selected", frame_index=self.frame_index, **point)
                print(f"物体 {self.active_id} 顶部候选桌面坐标(mm): {point['table_xyz_mm']}", flush=True)
                return
            sample_color(self.frame, self.profile, self.active_id, u, v)
            self.revision += 1
            self.stability = Stability()
            self._save_profile()
            self.log.emit("rgb_color_sample", object_id=self.active_id, frame_index=self.frame_index,
                          sample_uv=[u, v], revision=self.revision)
            print(f"已为物体 {self.active_id} 取色；换位置后仍按颜色寻找。", flush=True)
        except ValueError as exc:
            self.log.emit("rgb_manual_top_rejected" if self.top_mode else "rgb_color_sample_rejected", message=str(exc))
            print(str(exc), flush=True)

    def process(self, frame, frame_index, received_ns):
        self.frame, self.frame_index = frame.copy(), frame_index
        self.received_ns = received_ns
        key = (frame_index, received_ns, self.revision)
        if key == self._processed_key:
            return
        self._processed_key = key
        self.results = self.stability.update(detect_colors(frame, self.profile), received_ns)
        auto_elapsed_ms = None
        if self.auto_top:
            from pc.rgb_auto_top import estimate_top
            start = time.perf_counter()
            for result in self.results:
                point = estimate_top(frame, self.profile, result, self.table_geometry,
                                     self.top_height_mm, self.cube_side_mm)
                point.update(source_frame_index=frame_index, received_monotonic_ns=received_ns,
                             profile_revision=self.revision)
                result["auto_top_candidate"] = point
            auto_elapsed_ms = (time.perf_counter()-start)*1000
        if self.table_geometry is not None:
            for result in self.results:
                result["manual_top_candidate"] = None
                saved = self.top_points.get(result["object_id"])
                if saved is None:
                    continue
                if (result["status"] != "FOUND" or not result["stable"]
                        or saved["point"]["profile_revision"] != self.revision
                        or np.linalg.norm(np.array(result["pixel_uv"])-saved["anchor"]) > 3):
                    self.top_points.pop(result["object_id"])
                    self.log.emit("rgb_manual_top_invalidated", object_id=result["object_id"],
                                  frame_index=frame_index, reason="DETECTION_PROFILE_OR_POSITION_CHANGED")
                else:
                    result["manual_top_candidate"] = saved["point"]
        signature = [(d["status"], d["stable"], d.get("auto_top_candidate", {}).get("status")) for d in self.results]
        if signature != self._last_logged or received_ns-self._last_log_ns >= 1_000_000_000:
            self.log.emit("rgb_color_detections", frame_index=frame_index, received_monotonic_ns=received_ns,
                          profile_revision=self.revision, detections=self.results,
                          auto_top_elapsed_ms=auto_elapsed_ms)
            self._last_logged, self._last_log_ns = signature, received_ns

    def draw(self, display, interactive=True, *, show_analysis_roi=True, show_top_outline=True):
        if interactive:
            self.display_shape = display.shape
        sx, sy = display.shape[1]/self.frame.shape[1], display.shape[0]/self.frame.shape[0]
        def box(rect, color):
            x, y, w, h = rect
            cv2.rectangle(display, (round(x*sx), round(y*sy)), (round((x+w)*sx), round((y+h)*sy)), color, 2)
        if show_analysis_roi:
            box(self.profile["roi_xywh"], (0, 220, 0))
        lines = [f"Select: {self.active_id} | 1/2/3 then click top | R: work area"]
        if self.table_geometry is not None:
            lines = [f"Select: {self.active_id} | T: switch | Click: {'TOP CENTRE' if self.top_mode else 'COLOUR'}"]
        if self.auto_top:
            lines.append("AUTO TOP: review polygon + circle | T: manual comparison | S: save"
                         if show_top_outline else "AUTO TOP: coordinates retained | outline hidden")
        for result in self.results:
            oid = result["object_id"]
            lines.append(f"{oid}: {result['status']} {'STABLE' if result['stable'] else ''}")
            for candidate in result["candidates"]:
                box(candidate["bbox_xywh"], PALETTE[oid])
            if result["pixel_uv"] is not None:
                u, v = result["pixel_uv"]
                pos = (round(u*sx), round(v*sy))
                cv2.drawMarker(display, pos, PALETTE[oid], cv2.MARKER_CROSS, 15, 2)
                cv2.putText(display, f"{oid}: ({u:.0f},{v:.0f}) px", (pos[0]+8, pos[1]-8),
                            cv2.FONT_HERSHEY_SIMPLEX, .5, PALETTE[oid], 2)
            point = result.get("manual_top_candidate")
            if point is not None:
                u, v = point["pixel_uv"]
                pos = (round(u*sx), round(v*sy))
                cv2.circle(display, pos, 8, PALETTE[oid], 2)
                x, y, z = point["table_xyz_mm"]
                lines.append(f"  Top: X={x:.1f} Y={y:.1f} mm | Z assumed {z:.0f}")
                if not point["inside_intrinsics_observed_corner_bounds"]:
                    lines.append("  Top outside observed calibration area")
            auto = result.get("auto_top_candidate")
            if auto is not None:
                if auto["pixel_uv"] is None:
                    lines.append(f"  Auto: {auto['status']}")
                else:
                    if show_top_outline:
                        quad = np.array(auto["quad_pixel_uv"])*[sx, sy]
                        cv2.polylines(display, [np.rint(quad).astype(np.int32)], True, (255,255,255), 2)
                        u,v = auto["pixel_uv"]
                        cv2.circle(display,(round(u*sx),round(v*sy)),6,(255,255,255),2)
                    x,y,z = auto["table_xyz_mm"]
                    lines.append(f"  Auto: X={x:.1f} Y={y:.1f} mm | Z assumed {z:.0f}")
                    lines.append(f"  Yaw(mod90): {auto['table_yaw_mod90_deg']:.1f} deg | REVIEW")
                    if not auto["inside_intrinsics_observed_corner_bounds"]:
                        lines.append("  Auto outside observed calibration area")
        for i, text in enumerate(lines):
            xy = (12, 60+i*23)
            cv2.putText(display, text, xy, cv2.FONT_HERSHEY_SIMPLEX, .5, (0, 0, 0), 3, cv2.LINE_AA)
            cv2.putText(display, text, xy, cv2.FONT_HERSHEY_SIMPLEX, .5, (255, 255, 255), 1, cv2.LINE_AA)

    def key(self, key):
        if key in (ord("t"), ord("T")) and self.table_geometry is not None:
            self.top_mode = not self.top_mode
            print("点击模式：" + ("顶部中心毫米候选" if self.top_mode else "颜色取样"), flush=True)
        if key in (ord("1"), ord("2"), ord("3")):
            self.active_id = key-ord("0")
        if key in (ord("r"), ord("R")):
            name = "Work area - drag then Enter; C cancels"
            h, w = self.frame.shape[:2]
            dh, dw = self.display_shape[:2]
            preview = cv2.resize(self.frame, (dw, dh))
            rect = cv2.selectROI(name, preview, showCrosshair=False, fromCenter=False)
            cv2.destroyWindow(name)
            if rect[2] > 0 and rect[3] > 0:
                x, y, rw, rh = rect
                candidate = [round(x*w/dw), round(y*h/dh), round(rw*w/dw), round(rh*h/dh)]
                old = self.profile["roi_xywh"]
                self.profile["roi_xywh"] = candidate
                try:
                    validate_profile(self.profile, self.frame.shape)
                except ValueError as exc:
                    self.profile["roi_xywh"] = old
                    print(str(exc), flush=True)
                else:
                    self.revision += 1
                    self.stability = Stability()
                    self._save_profile()

    def save_result(self, raw_path, received_ns, *, render_options=None, workspace_overlay=None):
        result = {"schema": "gesture.ai_pc.rgb_color_result.v1", "source": "USB_RGB",
                  "simulation": False, "physical_execution": False, "depth_available": False,
                  "raw_image": raw_path.name, "received_monotonic_ns": received_ns,
                  "profile_revision": self.revision, "profile": self.profile,
                  "detections": self.results, "coordinates": "raw_image_pixels", "calibration": None}
        result["frame_index"] = self.frame_index
        if self.table_geometry is not None:
            result["table_geometry"] = self.table_geometry.record
            result["manual_top_scope"] = "User-picked points on assumed height plane; not automatic grasp centres"
        if self.auto_top:
            result["auto_top_scope"] = "Heuristic top quadrilaterals on known height; visual review required, no robot execution"
            result["expected_cube_side_mm"] = self.cube_side_mm
        if workspace_overlay is not None:
            result["workspace_overlay"] = workspace_overlay.record
        if render_options is not None:
            result["render_options"] = dict(render_options)
        raw_path.with_suffix(".json").write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
        annotated = self.frame.copy()
        self.draw(annotated, interactive=False, **(render_options or {}))
        if workspace_overlay is not None:
            workspace_overlay.draw(annotated)
        ok, data = cv2.imencode(".png", annotated)
        if not ok:
            raise RuntimeError("识别预览 PNG 编码失败")
        raw_path.with_name(raw_path.stem+"_detected.png").write_bytes(data.tobytes())
        self.log.emit("rgb_color_snapshot", raw_image=raw_path.name, result=raw_path.with_suffix(".json").name,
                      detections=self.results, profile_revision=self.revision)
