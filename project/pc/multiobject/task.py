"""Strict adapter to existing candidate/CANCEL contract, never physical paths."""
from copy import deepcopy
from pc.multiobject.registry import TASKS
from pc.neural_task_pipeline import NeuralTaskPipeline


def legacy_observation(obs, registry):
    if (obs.get('schema') != 'gesture.ai_pc.multiobject_observation.v1' or
            obs.get('source') != 'USB_RGB_MULTIOBJECT_NEURAL' or obs.get('learned_model') is not True):
        raise ValueError('Learned multiobject observation required')
    backend = obs.get('backend', {})
    if (backend.get('role') != 'cube_detector' or not backend.get('model_sha256') or
            not set(TASKS.values()).issubset(backend.get('trained_classes', []))):
        raise ValueError('Trained cube detector provenance required')
    if not obs.get('frame_sha256'):
        raise ValueError('Frame identity required')
    for d in obs.get('detections', []):
        rule = registry.task(d.get('object_id'))
        if (d.get('class_name') != rule['name'] or d.get('model_role') != 'cube_detector' or
                d.get('frame_sha256') != obs['frame_sha256'] or
                d.get('source_frame_index') != obs['frame_index']):
            raise ValueError('Task mapping/role/frame mismatch')
    if sorted(d['object_id'] for d in obs['detections']) != [1, 2, 3]:
        raise ValueError('Exactly three task results required')
    converted = deepcopy(obs)
    converted.update(schema='gesture.ai_pc.neural_top_observation.v1', source='USB_RGB_NEURAL')
    return converted


class TaskPipeline(NeuralTaskPipeline):
    def __init__(self, observation, config, registry):
        self.registry = registry
        for obj in config.get('objects', []):
            rule = registry.task(obj.get('object_id'))
            if obj.get('name') != rule['name'] or obj.get('size_mm') != rule['cube_side_mm']:
                raise ValueError('Task configuration must keep registered cube colour and size')
        super().__init__(legacy_observation(observation, registry), config)

    def preview(self, object_id):
        self.registry.task(object_id)
        return super().preview(object_id)
