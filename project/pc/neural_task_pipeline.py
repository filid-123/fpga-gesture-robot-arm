"""Transport-compatible task preview powered by current neural observations.

Never fabricates robot-base/TCP coordinates or authorizes an uncalibrated path.
Offline one-frame review is explicit and never asserts temporal stability.
"""
import time
import math
from pc.pick_pipeline import PipelineReport


class NeuralTaskPipeline:
    def __init__(self, observation, config):
        from pc.rgb_task_preview import validate_config
        self.observation = observation
        self.config = validate_config(config)
        self.last_preview = None

    def preview(self, object_id):
        obs = self.observation
        backend = obs.get('backend', {})
        report = {'object_id': object_id, 'candidate': None, 'source': 'NEURAL_TOP',
                  'learned_model': True, 'model_sha256': backend.get('model_sha256'),
                  'actual_backend': backend.get('actual_backend'), 'physical_execution': False,
                  'robot_base_xyz_mm': None, 'joint_path': None,
                  'stability_verified': False, 'offline_snapshot': obs.get('offline_snapshot')}
        def reject(reason):
            report.update(status='REJECTED', reason=reason)
            return report
        if obs.get('schema') != 'gesture.ai_pc.neural_top_observation.v1' or not obs.get('learned_model'):
            return reject('NEURAL_OBSERVATION_REQUIRED')
        if not backend.get('model_sha256') or obs.get('source') != 'USB_RGB_NEURAL':
            return reject('NEURAL_MODEL_PROVENANCE_REQUIRED')
        if not obs['offline_snapshot']:
            age = (time.monotonic_ns()-obs['received_monotonic_ns'])/1e6
            if obs.get('clock_id') != 'HOST_MONOTONIC' or not 0 <= age <= 500:
                return reject('STALE_NEURAL_OBSERVATION')
        detections = [d for d in obs['detections'] if d['object_id'] == object_id]
        if len(detections) != 1 or detections[0]['status'] != 'FOUND':
            return reject('NEURAL_OBJECT_MISSING_AMBIGUOUS_OR_GEOMETRY_REJECTED')
        d = detections[0]
        if not obs['offline_snapshot'] and not d['stable']:
            return reject('NEURAL_POSITION_NOT_STABLE')
        top = d.get('auto_top_candidate') or {}
        table = obs['table_geometry']
        if (top.get('status') != 'AUTO_TOP_CANDIDATE' or
                top.get('source_frame_index') != obs['frame_index'] or
                top.get('object_id') != object_id or
                top.get('coordinate_system') != table['table']['table_frame_id']):
            return reject('NEURAL_SOURCE_OR_FRAME_MISMATCH')
        objects = [o for o in self.config['objects'] if o['object_id'] == object_id]
        if len(objects) != 1:
            return reject('OBJECT_ID_NOT_REGISTERED')
        obj = objects[0]
        xyz = top['table_xyz_mm']
        if (not all(math.isfinite(v) for v in xyz) or
                abs(xyz[2]-obj['size_mm']) > 1e-6 or
                abs(top['expected_cube_side_mm']-obj['size_mm']) > 1e-6):
            return reject('INVALID_SIZE_OR_POSE')
        p = self.config['preview']
        contact = p.get('contact_geometry')
        if contact:
            if contact['table_frame_id'] != top['coordinate_system'] or contact['table_sha256'] != table['table_sha256']:
                return reject('CONTACT_TABLE_MISMATCH')
            z = contact['contact_center_to_tip_mm'] + contact['nominal_tip_clearance_mm']
        else:
            z = xyz[2] - obj['size_mm']/2
        report.update(status='TABLE_GRASP_PREVIEW', reason='ROBOT_BASE_TCP_REAL_IK_AND_PHYSICAL_ACCEPTANCE_PENDING',
            stability_verified=d['stable'], candidate={
                'object_name': obj['name'], 'coordinate_system': top['coordinate_system'], 'units': 'mm',
                'top_table_xyz_mm': xyz, 'grasp_table_xyz_mm': [xyz[0], xyz[1], z],
                'approach_table_xyz_mm': [xyz[0], xyz[1], z+p['approach_clearance_mm']],
                'lift_table_xyz_mm': [xyz[0], xyz[1], z+p['lift_height_mm']],
                'table_yaw_mod90_deg': top['table_yaw_mod90_deg'],
                'requires_manual_review': True, 'arm_reach_and_collision_checked': False,
                'source_method': top['method'], 'physical_execution': False})
        return report

    def handle(self, req, limits):
        started = time.monotonic_ns()
        self.last_preview = self.preview(req.object_id)
        reason = ('NEURAL_BASE_TCP_AND_REAL_IK_PENDING' if self.last_preview['candidate']
                  else self.last_preview['reason'])
        return None, PipelineReport(req.task_id, req.object_id, reason,
                                    t_ns={'start': started, 'previewed': time.monotonic_ns()})


def rehearse_requests(observation, config, object_ids=(1, 2, 3), log_path=None):
    """Exercise the EXISTING binary codec/agent in memory. No network or board IO."""
    import phase3_link_protocol as lp
    import phase3_path_contract as contract
    from pc_task_agent import PcTaskAgent, AgentConfig
    from phase3_event_log import EventLog
    log = EventLog('pc', log_path, meta={'perception':'NEURAL_TOP',
                   'transport':'IN_MEMORY_PROTOCOL','physical_execution':False})
    pipeline = NeuralTaskPipeline(observation, config)
    agent = PcTaskAgent(pipeline, AgentConfig(watch_after_commit=False), log)
    wire, tasks = [], []
    def decode(kind, fields):
        return lp.FrameParser().feed(lp.encode(kind, len(wire)+1, fields))[0]
    def record(messages):
        for kind, fields in messages:
            message = decode(kind, fields)
            wire.append({'direction':'PC_TX_LOCAL','type':message.type.name,
                         'fields':list(message.fields)})
    try:
        # Zero limits are ONLY a codec/session fixture; no planner uses them.
        limits = contract.MotionLimits((0,)*6,(0,)*6,(0,)*6,(0,)*6,1,0,'TBD')
        for task_id, oid in enumerate(object_ids, 1):
            record(agent.on_connect())
            agent.on_message(decode(lp.MsgType.HELLO,(2,contract.INTERP_VERSION,contract.CONTRACT_VERSION)))
            agent.on_message(decode(lp.MsgType.LIMITS,lp.limits_fields(limits)))
            fields = (task_id,oid,2,*((0,)*12),1,1000)
            wire.append({'direction':'PS_RX_FIXTURE','type':'TARGET_REQUEST','fields':list(fields)})
            out = agent.on_message(decode(lp.MsgType.TARGET_REQUEST,fields))
            record(out)
            tasks.append({'task_id':task_id,'object_id':oid,'preview':pipeline.last_preview,
                          'messages':[kind.name for kind,_ in out]})
            agent.on_disconnect('local boundary; no board acknowledgment fabricated')
        return {'schema':'gesture.ai_pc.neural_task_rehearsal.v1','tasks':tasks,
                'transport':'IN_MEMORY_PROTOCOL','wire':wire,
                'path_submissions':agent.submissions,'physical_execution':False}
    finally:
        log.close()
