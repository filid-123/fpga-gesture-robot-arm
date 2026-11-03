"""Same-frame learned detection -> cube-only surface/geometry observations."""
import time
from copy import deepcopy
import cv2
import numpy as np
from pc.multiobject.registry import TASKS
from pc.multiobject.yolo import image_digest, iou
from pc.rgb_auto_top import _quad
from pc.rgb_color_preview import Stability


class Perception:
    def __init__(self, detector, surface, registry, geometry, workspace=None, generic=None,
                 confidence=.4, surface_confidence=.7, max_frame_age_ms=500,
                 highlight_chroma=False, recognition_only=False, pixel_top=False):
        if highlight_chroma:
            raise ValueError('Highlight recolouring retired: background contamination caused wrong cube classes. Use raw acquisition.')
        if recognition_only and workspace is not None:
            raise ValueError('Uncalibrated recognition must not display a metric workspace')
        if pixel_top and (not recognition_only or surface is None):
            raise ValueError('Pixel-only tops require uncalibrated mode and a neural surface model')
        if detector.spec['role'] != 'cube_detector' or (generic and generic.spec['role'] != 'object_recognizer'):
            raise ValueError('Detector roles cannot be swapped')
        if not .01 <= confidence < 1 or not .5 <= surface_confidence < 1 or max_frame_age_ms <= 0:
            raise ValueError('Invalid perception thresholds')
        if workspace and workspace.geometry.record['table_sha256'] != geometry.record['table_sha256']:
            raise ValueError('Workspace calibration mismatch')
        self.detector, self.surface, self.registry = detector, surface, registry
        self.geometry, self.workspace, self.generic = geometry, workspace, generic
        self.confidence, self.surface_confidence, self.age_ms = confidence, surface_confidence, max_frame_age_ms
        self.last_index = -1
        self.stability = Stability()
        self.last_detector_frame = None
        self.recognition_only = recognition_only
        self.pixel_top = pixel_top

    def _detect(self, frame, roi):
        cubes, meta = self.detector.run(frame, roi=roi, confidence=self.confidence)
        input_hash = image_digest(frame)
        self.last_detector_frame = frame
        for detection in cubes:
            detection.update(detector_pass=1, detector_input_sha256=input_hash)
        return cubes, meta, {'enabled': False, 'applied': False, 'pass_count': 1,
                             'status': 'RETIRED_BACKGROUND_CONTAMINATION',
                             'final_input_sha256': input_hash}

    def infer(self, frame, frame_index, received_ns, roi=None, offline=False, selected_task=None,
              recognize_others=True, now_ns=None):
        start = time.perf_counter_ns()
        if not self.recognition_only:
            self.geometry.check_frame(frame.shape)
        if type(frame_index) is not int or frame_index <= self.last_index:
            self.stability = Stability()
            raise ValueError('Frame index must increase')
        if type(received_ns) is not int or received_ns < 0:
            raise ValueError('Invalid host timestamp')
        self.last_index = frame_index
        if selected_task is not None:
            self.registry.task(selected_task)
        def freshness():
            if not offline:
                now = time.monotonic_ns() if now_ns is None else now_ns
                if not 0 <= (now-received_ns)/1e6 <= self.age_ms:
                    self.stability = Stability()
                    raise ValueError('Frame stale or became stale during inference')
        freshness()
        frame_hash = image_digest(frame)
        cubes, meta, recovery = self._detect(frame, roi)
        others, generic_meta = ([], None)
        if self.generic and recognize_others:
            others, generic_meta = self.generic.run(frame, roi=roi, confidence=self.confidence)
        recognition = []
        for det in cubes+others:
            rule = self.registry.classify(det['class_name'], det['model_role'])
            # Recognition-only includes untrained proposed custom labels.
            enabled = rule['grasp_enabled'] and det['trained']
            recognition.append({**det, 'task_id': rule['task_id'] if enabled else None,
                'grasp_enabled': enabled, 'frame_index': frame_index, 'frame_sha256': frame_hash})
        results, surface_runs = [], []
        for oid, name in TASKS.items():
            rule = self.registry.task(oid)
            matches = [d for d in recognition if d['class_name'] == name and d['grasp_enabled']]
            result = {'object_id': oid, 'class_name': name, 'stable': False, 'instances': len(matches),
                'status': 'NOT_FOUND', 'pixel_uv': None, 'confidence': None, 'auto_top_candidate': None,
                'source_frame_index': frame_index, 'frame_sha256': frame_hash, 'model_role': 'cube_detector'}
            if len(matches) > 1:
                result['status'] = 'MULTIPLE_INSTANCES'
            elif matches:
                d = matches[0]
                result.update(bbox_xyxy_raw=d['bbox_xyxy_raw'], confidence=d['confidence'])
                conflicts = [o for o in recognition if o is not d and iou(o['bbox_xyxy_raw'], d['bbox_xyxy_raw']) > .35]
                if conflicts:
                    result['status'] = 'OVERLAPPING_OBJECT_OR_CLASS_AMBIGUITY'
                elif self.recognition_only:
                    if self.pixel_top:
                        result.update(self._top_pixels(frame, d, rule, surface_runs))
                    else:
                        result['status'] = 'RECOGNITION_ONLY_POSITIONING_DISABLED'
                elif selected_task is not None and selected_task != oid:
                    result['status'] = 'RECOGNIZED_NOT_SELECTED'
                else:
                    result.update(self._top(frame, d, rule, frame_index, roi, surface_runs))
            results.append(result)
        freshness()
        if offline:
            self.stability = Stability()
        else:
            self.stability.update(results, received_ns)
        return {'schema': 'gesture.ai_pc.multiobject_observation.v1', 'source': 'USB_RGB_MULTIOBJECT_NEURAL',
                'learned_model': True, 'frame_index': frame_index, 'frame_sha256': frame_hash,
                'received_monotonic_ns': received_ns,
                'clock_id': 'OFFLINE_SAVED_IMAGE' if offline else 'HOST_MONOTONIC',
                'offline_snapshot': offline, 'physical_execution': False, 'path_submissions': 0,
                'depth_available': False, 'backend': meta['backend'],
                'generic_backend': generic_meta['backend'] if generic_meta else None,
                'generic_recognition_this_frame': bool(self.generic and recognize_others),
                'recognitions': recognition, 'detections': results, 'surface_runs': surface_runs,
                'chroma_recovery': recovery,
                'table_geometry': None if self.recognition_only else deepcopy(self.geometry.record),
                'localization_mode': ('NEURAL_TOP_PIXELS_ONLY_UNCALIBRATED' if self.pixel_top else
                                      'PIXEL_BOXES_ONLY_UNCALIBRATED' if self.recognition_only else 'CALIBRATED_TOP_PREVIEW'),
                'timing_ms': {'detector': meta['timing_ms'],
                    'generic': generic_meta['timing_ms'] if generic_meta else None,
                    'total_perception': (time.perf_counter_ns()-start)/1e6},
                'hardware_acceptance': 'PENDING_NPU_INTERNAL_PLACEMENT_ROCM_AND_PHYSICAL_CHECKS'}

    def _top_pixels(self, frame, detection, rule, runs):
        from pc.multiobject.pixel_top import fit_pixel_quad
        box = np.asarray(detection['bbox_xyxy_raw'], float)
        pad = max(box[2:]-box[:2])*.18
        expanded = [max(0, box[0]-pad), max(0, box[1]-pad),
                    min(frame.shape[1], box[2]+pad), min(frame.shape[0], box[3]+pad)]
        probabilities, offset, meta = self.surface.run(frame, expanded)
        runs.append({'task_id': rule['task_id'], **meta})
        mask = np.where(probabilities >= self.surface_confidence, 255, 0).astype(np.uint8)
        n, labels, stats, _ = cv2.connectedComponentsWithStats(mask)
        valid = [j for j in range(1, n) if stats[j, cv2.CC_STAT_AREA] >= 100]
        if len(valid) != 1:
            return {'status': 'SURFACE_EMPTY_OR_AMBIGUOUS'}
        mask = np.where(labels == valid[0], 255, 0).astype(np.uint8)
        fit = fit_pixel_quad(mask, offset, box)
        if fit is None:
            return {'status': 'PIXEL_TOP_GEOMETRY_REJECTED'}
        return {'status': 'PIXEL_TOP_ONLY', 'pixel_uv': fit['pixel_uv'],
                'pixel_top': fit, 'auto_top_candidate': None}

    def _top(self, frame, detection, rule, index, roi, runs):
        box = np.asarray(detection['bbox_xyxy_raw'], float)
        pad = max(box[2]-box[0], box[3]-box[1])*.18
        expanded = [max(0, box[0]-pad), max(0, box[1]-pad), min(frame.shape[1], box[2]+pad), min(frame.shape[0], box[3]+pad)]
        probabilities, offset, meta = self.surface.run(frame, expanded)
        runs.append({'task_id': rule['task_id'], **meta})
        mask = np.where(probabilities >= self.surface_confidence, 255, 0).astype(np.uint8)
        n, labels, stats, _ = cv2.connectedComponentsWithStats(mask)
        valid = [j for j in range(1, n) if stats[j, cv2.CC_STAT_AREA] >= 100]
        if len(valid) != 1:
            return {'status': 'SURFACE_EMPTY_OR_AMBIGUOUS'}
        mask = np.where(labels == valid[0], 255, 0).astype(np.uint8)
        fit = _quad(mask, offset, self.geometry, rule['known_top_height_mm'], rule['cube_side_mm'])
        if fit is None:
            return {'status': 'TOP_GEOMETRY_REJECTED'}
        quad = np.asarray(fit['quad_pixel_uv'])
        x, y, rw, rh = roi if roi is not None else (0, 0, frame.shape[1], frame.shape[0])
        if np.any(quad <= [x+1, y+1]) or np.any(quad >= [x+rw-1, y+rh-1]):
            return {'status': 'INFERENCE_ROI_EDGE'}
        # Segmentation may not supply a top outside the detector's supported area.
        centre = np.asarray(fit['pixel_uv'])
        if np.any(centre < box[:2]) or np.any(centre > box[2:]):
            return {'status': 'SURFACE_DETECTOR_DISAGREEMENT'}
        calibrated = all(self.geometry.manual_top(p, rule['known_top_height_mm'])[
                         'inside_intrinsics_observed_corner_bounds'] for p in quad)
        in_workspace = True
        if self.workspace:
            c = np.asarray(self.workspace.config['centre_table_xy_mm'])
            half = np.asarray(self.workspace.config['size_wh_mm'])/2
            xy = np.asarray(fit['quad_table_xyz_mm'])[:, :2]
            in_workspace = bool(np.all(xy >= c-half) and np.all(xy <= c+half))
        accepted = calibrated and in_workspace
        top = {**fit, 'status': 'AUTO_TOP_CANDIDATE' if accepted else 'TOP_REJECTED',
               'object_id': rule['task_id'], 'source_frame_index': index,
               'coordinate_system': self.geometry.table['table_frame_id'],
               'assumed_top_height_mm': rule['known_top_height_mm'], 'expected_cube_side_mm': rule['cube_side_mm'],
               'method': 'YOLO_CUBE_DETECTION_NEURAL_BINARY_SURFACE_KNOWN_HEIGHT',
               'physical_execution': False, 'depth_measured': False, 'robot_base_xyz_mm': None,
               'top_centre_automatically_validated': False, 'independent_metric_validation': 'PENDING'}
        return {'status': 'FOUND' if accepted else ('OUTSIDE_WORKSPACE' if not in_workspace else 'CALIBRATION_EXTRAPOLATION'),
                'pixel_uv': fit['pixel_uv'], 'auto_top_candidate': top}


def draw(frame, obs, workspace=None):
    out = frame.copy()
    if workspace:
        workspace.draw(out)
    stability_by_id = {d['object_id']: d for d in obs.get('detections', [])}
    for det in obs['recognitions']:
        x, y, x2, y2 = np.rint(det['bbox_xyxy_raw']).astype(int)
        color = (40, 220, 80) if det['grasp_enabled'] else (200, 180, 80)
        cv2.rectangle(out, (x, y), (x2, y2), color, 2)
        suffix = f"task{det['task_id']}" if det['grasp_enabled'] else 'recognition only'
        if not det['trained']:
            suffix = 'UNTRAINED - no task'
        if det['grasp_enabled']:
            stability = stability_by_id.get(det['task_id'], {})
            if stability.get('stable'):
                suffix += ' | STABLE'
            elif stability.get('stability_hits') is not None:
                suffix += (f" | TRACK {stability['stability_hits']}/"
                           f"{stability['stability_window']}")
            elif stability.get('status') not in (None, 'FOUND'):
                suffix += ' | ' + stability['status']
        cv2.putText(out, f"{det['class_name']} {det['confidence']:.2f} {suffix}",
                    (x, max(25, y-8)), cv2.FONT_HERSHEY_SIMPLEX, .6, color, 2)
    for d in obs['detections']:
        top = d.get('auto_top_candidate') or d.get('pixel_top')
        if top:
            cv2.polylines(out, [np.rint(top['quad_pixel_uv']).astype(np.int32)], True, (255, 255, 255), 2)
            cv2.drawMarker(out, tuple(np.rint(top['pixel_uv']).astype(int)), (255,255,255), cv2.MARKER_CROSS, 16, 2)
    cv2.putText(out, f"DEVELOPMENT / NO MOTION | {obs['backend']['actual_backend']} | {obs['timing_ms']['total_perception']:.0f} ms",
                (20, 35), cv2.FONT_HERSHEY_SIMPLEX, .8, (0, 220, 255), 2)
    if obs.get('table_geometry') is None:
        cv2.putText(out, 'PIXELS ONLY / TABLE COORDINATES UNAVAILABLE',
                    (20, 68), cv2.FONT_HERSHEY_SIMPLEX, .7, (0, 220, 255), 2)
    return out
