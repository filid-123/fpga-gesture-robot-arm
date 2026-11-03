"""Known-height RGB table previews consumed by the existing S7 task agent.

This adapter always returns no PathPlan. Table points never enter Detection.top_base_mm.
The existing agent cancels the local request while robot-base calibration/IK are pending.
"""
from __future__ import annotations

import math
import time
from copy import deepcopy

from grasp import GraspParams
from pick_pipeline import PipelineReport

CONFIG_SCHEMA = 'gesture.ai_pc.rgb_task_preview_config.v1'


def validate_config(config):
    if config.get('schema') != CONFIG_SCHEMA:
        raise ValueError('Not an RGB task preview configuration')
    objects = config['objects']
    if sorted(o['object_id'] for o in objects) != [1, 2, 3]:
        raise ValueError('Register exactly object IDs 1, 2, 3')
    values = [o['size_mm'] for o in objects] + [
        config['preview']['approach_clearance_mm'], config['preview']['lift_height_mm']]
    if not all(math.isfinite(v) and v > 0 for v in values):
        raise ValueError('Object sizes and preview clearances must be finite and positive')
    contact = config['preview'].get('contact_geometry')
    if contact is not None:
        if contact.get('finger_direction') != 'VERTICALLY_DOWN_ASSUMED':
            raise ValueError('Contact geometry requires the vertical-finger assumption')
        tip_distance = contact['contact_center_to_tip_mm']
        tip_gap = contact['nominal_tip_clearance_mm']
        if not all(math.isfinite(v) and v > 0 for v in (tip_distance, tip_gap)):
            raise ValueError('Contact distance and nominal tip clearance must be positive')
        if any(tip_distance + tip_gap >= o['size_mm'] for o in objects):
            raise ValueError('Contact height must be inside each upright cube')
        if not contact.get('table_frame_id') or not contact.get('table_sha256'):
            raise ValueError('Contact preview must bind to a table frame and geometry hash')
    return config


class RGBTaskPreview:
    """A frozen saved RGB frame, selected by object ID through PcTaskAgent.handle()."""

    def __init__(self, saved_frame, config, log, source=None):
        self.frame = deepcopy(saved_frame)
        self.config = deepcopy(validate_config(config))
        self.log, self.source = log, source or {}
        self.last_preview = None

    def preview(self, object_id):
        report = {
            'schema': 'gesture.ai_pc.rgb_table_grasp_preview.v1',
            'object_id': object_id, 'status': 'REJECTED', 'reason': None,
            'source': self.source, 'source_frame_index': self.frame.get('frame_index'),
            'input_kind': 'SAVED_RGB_KNOWN_HEIGHT', 'physical_execution': False,
            'robot_base_xyz_mm': None, 'joint_path': None,
            'independent_metric_accuracy': 'NOT_ACCEPTED', 'depth_measured': False,
            'candidate': None,
        }

        def reject(reason):
            report['reason'] = reason
            return report

        objects = [o for o in self.config['objects'] if o['object_id'] == object_id]
        if not objects:
            return reject('UNREGISTERED_OBJECT')
        matches = [d for d in self.frame['detections'] if d['object_id'] == object_id]
        if len(matches) != 1:
            return reject('OBJECT_MISSING_OR_AMBIGUOUS')
        detection = matches[0]
        if detection.get('status') != 'FOUND' or not detection.get('stable'):
            return reject('OBJECT_NOT_FOUND_OR_NOT_STABLE')
        top = detection.get('auto_top_candidate') or {}
        if top.get('status') != 'AUTO_TOP_CANDIDATE':
            return reject('TOP_NOT_ACCEPTED_CANDIDATE')
        if top.get('source_frame_index') != self.frame['frame_index'] or top.get('object_id') != object_id:
            return reject('CANDIDATE_SOURCE_MISMATCH')
        table = self.frame['table_geometry']['table']
        if top.get('coordinate_system') != table['table_frame_id']:
            return reject('COORDINATE_SYSTEM_MISMATCH')
        xyz, yaw = top.get('table_xyz_mm'), top.get('table_yaw_mod90_deg')
        if not isinstance(xyz, (list, tuple)) or len(xyz) != 3 or yaw is None:
            return reject('INVALID_TOP_POSE')
        if not all(math.isfinite(v) for v in (*xyz, yaw)) or not 0 <= yaw < 90:
            return reject('INVALID_TOP_POSE')
        size = objects[0]['size_mm']
        if any(v is None or not math.isfinite(v) or abs(v - size) > 1e-6 for v in (
                xyz[2], top.get('assumed_top_height_mm'), top.get('expected_cube_side_mm'))):
            return reject('CUBE_SIZE_HEIGHT_MISMATCH')
        p = self.config['preview']
        params = GraspParams(approach_clearance_mm=p['approach_clearance_mm'],
                             lift_height_mm=p['lift_height_mm'])
        # The optional measured-contact policy is explicit and local to this preview.
        # Existing configurations retain the centre-height rule in the TABLE frame.
        contact = p.get('contact_geometry')
        if contact is not None:
            if (contact['table_frame_id'] != table['table_frame_id'] or
                    contact['table_sha256'] != self.frame['table_geometry'].get('table_sha256')):
                return reject('CONTACT_GEOMETRY_TABLE_MISMATCH')
            zg = contact['contact_center_to_tip_mm'] + contact['nominal_tip_clearance_mm']
        else:
            zg = max(0.25 * size, xyz[2] - 0.5 * size)
        report.update(status='TABLE_GRASP_PREVIEW', reason='ROBOT_BASE_AND_REAL_IK_PENDING',
                      candidate={
            'object_name': objects[0]['name'], 'size_mm': size,
            'coordinate_system': top['coordinate_system'], 'units': 'mm',
            'top_table_xyz_mm': list(xyz), 'grasp_table_xyz_mm': [xyz[0], xyz[1], zg],
            'approach_table_xyz_mm': [xyz[0], xyz[1], zg + params.approach_clearance_mm],
            'lift_table_xyz_mm': [xyz[0], xyz[1], zg + params.lift_height_mm],
            'table_yaw_mod90_deg': yaw, 'table_yaw_mod90_rad': math.radians(yaw),
            'square_symmetry_period_deg': 90, 'gripper_command': None,
            'clearance_basis': 'PREVIEW_DEFAULTS_NOT_MEASURED',
            'approach_clearance_mm': params.approach_clearance_mm,
            'lift_height_mm': params.lift_height_mm,
            'source_method': top.get('method'),
            'source_fit_method': top.get('quadrilateral_fit_method'),
            'requires_manual_review': True, 'arm_reach_and_collision_checked': False,
        })
        if contact is not None:
            report['candidate'].update(
                reference_point_kind='CUBE_SECTION_CENTRE_AT_CONTACT_HEIGHT',
                object_center_table_xyz_mm=[xyz[0], xyz[1], size / 2],
                contact_reference_table_xyz_mm=[xyz[0], xyz[1], zg],
                contact_height_above_object_center_mm=zg - size / 2,
                nominal_finger_tip_height_mm=contact['nominal_tip_clearance_mm'],
                finger_direction=contact['finger_direction'],
                contact_center_to_tip_mm=contact['contact_center_to_tip_mm'],
                contact_height_basis='USER_APPROVED_NOMINAL_GEOMETRY',
                physical_tip_clearance_verified=False,
                P_to_grasp_center_transform=None,
            )
        return report

    def handle(self, req, limits):
        start = time.monotonic_ns()
        self.last_preview = self.preview(req.object_id)  # Rejection replaces any old preview.
        self.log.emit('rgb_table_grasp_preview', req.task_id, preview=self.last_preview)
        outcome = ('RGB_BASE_AND_REAL_IK_PENDING' if self.last_preview['candidate'] is not None
                   else 'RGB_' + self.last_preview['reason'])
        return None, PipelineReport(req.task_id, req.object_id, outcome,
                                    t_ns={'start': start, 'previewed': time.monotonic_ns()})
