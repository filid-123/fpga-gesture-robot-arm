"""Task IDs are user requirements, never inferred from detector class indices."""
from copy import deepcopy
import json
import math
from pathlib import Path

TASKS = {1: 'red_cube', 2: 'yellow_cube', 3: 'blue_cube'}


class Registry:
    def __init__(self, record):
        record = deepcopy(record)
        if (record.get('schema') != 'gesture.ai_pc.multiobject_registry.v1' or
                record.get('task_mapping_locked') is not True):
            raise ValueError('Locked multiobject registry required')
        self.objects = {}
        for obj in record.get('objects', []):
            name, task, enabled = obj.get('name'), obj.get('task_id'), obj.get('grasp_enabled')
            if not isinstance(name, str) or not name or name in self.objects or type(enabled) is not bool:
                raise ValueError('Duplicate or invalid registry object')
            expected = next((k for k, v in TASKS.items() if v == name), None)
            if expected is None:
                if task is not None or enabled:
                    raise ValueError('Other objects must be recognition-only')
            else:
                if type(task) is not int or task != expected or enabled is not True:
                    raise ValueError('Red1/yellow2/blue3 mapping cannot change')
                for key in ('known_top_height_mm', 'cube_side_mm'):
                    value = obj.get(key)
                    if type(value) not in (int, float) or not math.isfinite(value) or not 0 < value < 100:
                        raise ValueError('Known cube dimensions required')
            self.objects[name] = obj
        if not set(TASKS.values()).issubset(self.objects):
            raise ValueError('All three cube tasks required')
        self.record = record

    @classmethod
    def load(cls, path):
        return cls(json.loads(Path(path).read_bytes()))

    def task(self, task_id):
        if type(task_id) is not int or task_id not in TASKS:
            raise ValueError('Only integer task IDs 1, 2 and 3 are allowed')
        return deepcopy(self.objects[TASKS[task_id]])

    def classify(self, name, role):
        """Even a generic model emitting 'red_cube' cannot obtain grasp rights."""
        if role == 'cube_detector' and name in TASKS.values():
            return deepcopy(self.objects[name])
        return {'name': name, 'task_id': None, 'grasp_enabled': False}
