"""Neural segmentation -> top geometry -> explicit TABLE-frame observations.

Learned probabilities are the only class/region source. Geometry validates a
30 mm square and known-height ray intersections; it never supplies a missing ID.
"""
import time
import cv2
import numpy as np
from pc.rgb_auto_top import _quad
from pc.rgb_color_preview import Stability
from pc.neural_top_runtime import CLASSES


class NeuralTopPerception:
    def __init__(self, runtime, geometry, workspace=None, confidence=.75,
                 minimum_area_px=200, top_height_mm=30., cube_side_mm=30., max_frame_age_ms=500):
        if not .5 <= confidence < 1 or not np.isfinite([minimum_area_px, top_height_mm, cube_side_mm, max_frame_age_ms]).all():
            raise ValueError('Invalid perception thresholds')
        if min(minimum_area_px, top_height_mm, cube_side_mm, max_frame_age_ms) <= 0:
            raise ValueError('Perception dimensions must be positive')
        if workspace is not None and workspace.geometry.record['table_sha256'] != geometry.record['table_sha256']:
            raise ValueError('Workspace and top geometry differ')
        self.runtime, self.geometry, self.workspace = runtime, geometry, workspace
        self.confidence, self.min_area = confidence, minimum_area_px
        self.height, self.side, self.age_ms = top_height_mm, cube_side_mm, max_frame_age_ms
        self.stability = Stability()
        self.last_index = -1

    def infer(self, frame, frame_index, received_ns, *, offline=False, now_ns=None, roi=None):
        inference_started = time.perf_counter_ns()
        self.geometry.check_frame(frame.shape)
        if type(frame_index) is not int or frame_index <= self.last_index:
            self.stability = Stability()
            raise ValueError('Non-increasing frame index')
        if type(received_ns) is not int or received_ns < 0:
            raise ValueError('Invalid frame timestamp')
        self.last_index = frame_index
        if not offline:
            age = ((time.monotonic_ns() if now_ns is None else now_ns) - received_ns) / 1e6
            if not 0 <= age <= self.age_ms:
                self.stability = Stability()
                raise ValueError('Frame stale or from another clock domain')
        probabilities, metadata = self.runtime.run(frame, roi)
        if probabilities.shape != (4, *frame.shape[:2]) or not np.isfinite(probabilities).all():
            raise ValueError('Invalid restored class probabilities')
        started = time.perf_counter_ns()
        classes = probabilities.argmax(axis=0)
        results = []
        for oid in (1, 2, 3):
            mask = np.where((classes == oid) & (probabilities[oid] >= self.confidence), 255, 0).astype(np.uint8)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
            n, labels, stats, _ = cv2.connectedComponentsWithStats(mask)
            good = [k for k in range(1, n) if stats[k, cv2.CC_STAT_AREA] >= self.min_area]
            result = {'object_id': oid, 'class_name': CLASSES[oid], 'status': 'NOT_FOUND',
                      'stable': False, 'pixel_uv': None, 'confidence': None,
                      'auto_top_candidate': None, 'instances': len(good)}
            if len(good) > 1:
                result['status'] = 'MULTIPLE_INSTANCES'
            elif good:
                label = good[0]
                x, y, w, h, area = map(int, stats[label])
                result.update(bbox_xyxy_raw=[x, y, x+w, y+h], area_px=area,
                              confidence=float(np.mean(probabilities[oid][labels == label])))
                component = np.where(labels[y:y+h, x:x+w] == label, 255, 0).astype(np.uint8)
                fit = _quad(component, [x, y], self.geometry, self.height, self.side)
                if x <= 0 or y <= 0 or x+w >= frame.shape[1] or y+h >= frame.shape[0]:
                    result['status'] = 'IMAGE_EDGE'
                elif roi is not None and (x <= roi[0] or y <= roi[1] or
                        x+w >= roi[0]+roi[2] or y+h >= roi[1]+roi[3]):
                    result['status'] = 'INFERENCE_ROI_EDGE'
                elif fit is None:
                    result['status'] = 'TOP_GEOMETRY_REJECTED'
                else:
                    inside = self.geometry.manual_top(fit['pixel_uv'], self.height)['inside_intrinsics_observed_corner_bounds']
                    in_workspace = self._inside_workspace(fit['quad_table_xyz_mm'])
                    result.update(status='FOUND' if inside and in_workspace else
                                  ('OUTSIDE_WORKSPACE' if not in_workspace else 'CALIBRATION_EXTRAPOLATION'),
                                  pixel_uv=fit['pixel_uv'])
                    result['auto_top_candidate'] = {
                        **fit, 'status': 'AUTO_TOP_CANDIDATE' if inside and in_workspace else 'TOP_REJECTED',
                        'object_id': oid, 'source_frame_index': frame_index,
                        'coordinate_system': self.geometry.table['table_frame_id'],
                        'assumed_top_height_mm': self.height, 'expected_cube_side_mm': self.side,
                        'depth_measured': False, 'robot_base_xyz_mm': None, 'physical_execution': False,
                        'method': 'NEURAL_TOP_SEGMENTATION_KNOWN_HEIGHT_GEOMETRY',
                        'top_centre_automatically_validated': False, 'independent_metric_validation': 'PENDING'}
            results.append(result)
        if not offline:
            # Deadline covers model and geometry, not merely input acquisition.
            finished_ns = time.monotonic_ns() if now_ns is None else now_ns
            if not 0 <= (finished_ns-received_ns)/1e6 <= self.age_ms:
                self.stability = Stability()
                raise ValueError('Frame became stale during inference')
            self.stability.update(results, received_ns)
        else:
            # A saved snapshot is never relabelled as three temporally stable frames.
            self.stability = Stability()
        end = time.perf_counter_ns()
        metadata['timing_ms']['geometry'] = (end-started)/1e6
        metadata['timing_ms']['total_perception'] = (end-inference_started)/1e6
        return {'schema': 'gesture.ai_pc.neural_top_observation.v1', 'source': 'USB_RGB_NEURAL',
                'frame_index': frame_index, 'received_monotonic_ns': received_ns,
                'clock_id': 'OFFLINE_SAVED_IMAGE' if offline else 'HOST_MONOTONIC',
                'offline_snapshot': offline, 'physical_execution': False,
                'learned_model': True, 'depth_available': False,
                'table_geometry': self.geometry.record, 'detections': results, **metadata}

    def _inside_workspace(self, corners):
        if self.workspace is None:
            return True
        centre = np.asarray(self.workspace.config['centre_table_xy_mm'])
        half = np.asarray(self.workspace.config['size_wh_mm']) / 2
        p = np.asarray(corners)[:, :2]
        return bool(np.all(p >= centre-half) and np.all(p <= centre+half))


def draw_observation(frame, observation, workspace=None, hide_top=False):
    display = frame.copy()
    colors = {1: (80, 80, 255), 2: (0, 255, 255), 3: (255, 180, 50)}
    if workspace is not None:
        workspace.draw(display)
    for d in observation['detections']:
        box = d.get('bbox_xyxy_raw')
        color = colors[d['object_id']]
        if box:
            x, y, x2, y2 = box
            cv2.rectangle(display, (x, y), (x2, y2), color, 2)
            cv2.putText(display, f"{d['class_name']}: {d['status']}", (x, max(24, y-8)),
                        cv2.FONT_HERSHEY_SIMPLEX, .7, color, 2)
        top = d.get('auto_top_candidate')
        if top and not hide_top:
            cv2.polylines(display, [np.rint(top['quad_pixel_uv']).astype(np.int32)], True, (255, 255, 255), 2)
            cv2.circle(display, tuple(np.rint(top['pixel_uv']).astype(int)), 6, color, 2)
    return display
