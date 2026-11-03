"""Keep detector class indices, gesture IDs and registered grasp geometry distinct."""
from copy import deepcopy
from pathlib import Path
import hashlib
import json
import math

CLASSES = ['red_cube', 'yellow_cube', 'blue_cube', 'eraser', 'small_canister', 'scissors']
TASKS = {1: 'red_cube', 2: 'eraser', 3: 'small_canister'}
PROFILE_ID = 'mode_b_red_eraser_canister_v1'


class Profile:
    def __init__(self, record):
        self.record = deepcopy(record)
        if (record.get('schema') != 'gesture.ai_pc.mode_b_profile.v1' or
                record.get('profile_id') != PROFILE_ID or record.get('classes') != CLASSES or
                record.get('task_mapping') != {str(k):v for k,v in TASKS.items()} or
                record.get('physical_execution') is not False):
            raise ValueError('Explicit approved mode B profile required; motion is unavailable')
        self.objects = {o['name']:o for o in record['objects']}
        if set(self.objects) != set(CLASSES) or len(record['objects']) != 6:
            raise ValueError('Exactly the six approved classes required')
        for name,o in self.objects.items():
            expected = next((k for k,v in TASKS.items() if v==name),None)
            if o['task_id'] != expected or o['grasp_target'] is not (expected is not None):
                raise ValueError('Mode B task binding mismatch')
        self.sha256 = hashlib.sha256(json.dumps(record,sort_keys=True,separators=(',',':')).encode()).hexdigest()

    @classmethod
    def load(cls,path):
        return cls(json.loads(Path(path).read_bytes()))

    def task(self,task_id):
        if type(task_id) is not int or task_id not in TASKS:
            raise ValueError('Integer gesture 1/2/3 required')
        return deepcopy(self.objects[TASKS[task_id]])

    def classify(self,name,trained):
        if name not in self.objects:
            raise ValueError('Class outside selected six')
        rule=self.objects[name]
        return {'task_id':rule['task_id'] if trained else None,
                'grasp_target':bool(rule['grasp_target'] and trained),
                'physical_grasp_enabled':False}

    def metric_rule(self,name):
        rule=deepcopy(self.objects[name]);dims=rule.get('dimensions_mm')
        if not rule['grasp_target'] or not isinstance(dims,dict) or rule.get('dimensions_verified') is not True:
            raise ValueError('Measured registered dimensions needed for metric localization')
        keys={'square':('side','height'),'rectangle':('length','width','height'),
              'circle':('top_diameter','body_diameter','height')}[rule['shape']]
        if any(type(dims.get(k)) not in (float,int) or not math.isfinite(dims[k]) or dims[k]<=0 for k in keys):
            raise ValueError('Positive finite measured dimensions required')
        return rule
