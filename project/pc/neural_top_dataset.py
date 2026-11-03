"""Hash-checked session splits and image IO; usable without a training framework."""
from pathlib import Path
import hashlib
import json
import cv2
import numpy as np


def read_image(path, mode=1):
    image = cv2.imdecode(np.frombuffer(Path(path).read_bytes(), np.uint8), mode)
    if image is None:
        raise ValueError('Image decode failed: ' + str(path))
    return image


def load_dataset(manifest):
    manifest = Path(manifest).resolve()
    data = json.loads(manifest.read_bytes())
    if data.get('schema') != 'gesture.ai_pc.neural_top_dataset.v1':
        raise ValueError('Unknown dataset schema')
    if data.get('classes') != ['background','red_cube','yellow_cube','blue_cube']:
        raise ValueError('Dataset class map mismatch')
    seen, sessions = {}, {}
    for item in data['items']:
        split = item['split']
        if split not in ('train', 'validation', 'test'):
            raise ValueError('Invalid split')
        session = item['session_id']
        if session in sessions and sessions[session] != split:
            raise ValueError('Session leakage')
        sessions[session] = split
        for kind in ('image', 'mask'):
            path = (manifest.parent / item[kind]).resolve()
            if not path.is_relative_to(manifest.parent):
                raise ValueError('Dataset path escape')
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest != item[kind + '_sha256']:
                raise ValueError('Dataset image/mask hash mismatch')
        digest = item['image_sha256']
        if digest in seen and seen[digest] != split:
            raise ValueError('Duplicate image across splits')
        seen[digest] = split
        image = read_image(manifest.parent / item['image'])
        mask = read_image(manifest.parent / item['mask'], 0)
        if image.shape[:2] != mask.shape or not set(np.unique(mask)).issubset({0,1,2,3}):
            raise ValueError('Dataset mask shape/classes mismatch')
    return data
