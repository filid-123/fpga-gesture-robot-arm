"""Train-only manual cube-top ROI samples, independent of detector predictions."""
from pathlib import Path
import json
import cv2
import numpy as np
from pc.multiobject.dataset import validate_annotation, read_image
from pc.multiobject.registry import TASKS


class ManualSurfaceTraining:
    def __init__(self, manifest, registry, length, side=256, seed=20261025):
        self.path = Path(manifest).resolve()
        self.data = json.loads(self.path.read_bytes())
        if self.data.get('schema') != 'gesture.ai_pc.multiobject_dataset.v1':
            raise ValueError('Manual surface training requires compiled session-split data')
        sessions, hashes = {}, set()
        self.samples, self.negatives = [], []
        for item in self.data['items']:
            s, split = item['session_id'], item['split']
            if (s in sessions and sessions[s] != split) or item['image_sha256'] in hashes:
                raise ValueError('Surface dataset session/image leakage')
            sessions[s] = split; hashes.add(item['image_sha256'])
            if split != 'train': continue
            validate_annotation(item, self.path.parent, registry)
            if not item['objects']: self.negatives.append(item)
            for obj in item['objects']:
                if obj['class_name'] in TASKS.values() and obj.get('top_polygon_raw'):
                    self.samples.append((item, obj))
        if not self.samples: raise ValueError('No training-side manual cube top polygons')
        self.length, self.side, self.seed = length, side, seed
    def __len__(self): return self.length
    def __getitem__(self, index):
        import torch
        rng = np.random.default_rng(self.seed+index)
        negative = bool(self.negatives and rng.random() < .2)
        if negative:
            item = self.negatives[int(rng.integers(len(self.negatives)))]; obj = None
        else:
            item, obj = self.samples[int(rng.integers(len(self.samples)))]
        image = read_image(self.path.parent/item['image']); h, w = image.shape[:2]
        mask = np.zeros((h, w), np.uint8)
        if obj:
            cv2.fillConvexPoly(mask, np.rint(obj['top_polygon_raw']).astype(np.int32), 1)
            box = np.asarray(obj['bbox_xyxy_raw'], float)
            pad = max(box[2:]-box[:2])*rng.uniform(.15, .30)
            x, y = np.maximum(np.floor(box[:2]-pad), 0).astype(int)
            x2, y2 = np.minimum(np.ceil(box[2:]+pad), [w, h]).astype(int)
        else:
            size = int(min(h, w)*rng.uniform(.15, .5))
            x, y = int(rng.integers(w-size+1)), int(rng.integers(h-size+1))
            x2, y2 = x+size, y+size
        rgb = cv2.cvtColor(cv2.resize(image[y:y2, x:x2], (self.side, self.side)), cv2.COLOR_BGR2RGB)
        label = cv2.resize(mask[y:y2, x:x2], (self.side, self.side), interpolation=cv2.INTER_NEAREST)
        rgb = np.clip(rgb.astype(np.float32)/255*rng.uniform(.65, 1.3), 0, 1)
        # Camera placement can rotate any colour: mask and image rotate together.
        turns = int(rng.integers(4))
        rgb, label = np.rot90(rgb, turns), np.rot90(label, turns)
        if rng.random() < .5: rgb, label = rgb[:, ::-1], label[:, ::-1]
        return torch.from_numpy(np.ascontiguousarray(rgb.transpose(2, 0, 1))), torch.from_numpy(np.ascontiguousarray(label)).long()
