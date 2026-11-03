"""Explicit labels, session isolation and auditable YOLO dataset compilation."""
from pathlib import Path
from collections import Counter
import json
import cv2
import numpy as np
from pc.multiobject.registry import Registry, TASKS
from pc.multiobject.yolo import digest, image_digest


def read_image(path, flags=cv2.IMREAD_COLOR):
    im = cv2.imdecode(np.fromfile(path, np.uint8), flags)
    if im is None:
        raise ValueError(f'Invalid image: {path}')
    return im


def write_image(path, image):
    ok, data = cv2.imencode('.png', image)
    if not ok:
        raise ValueError('Image encoding failed')
    Path(path).write_bytes(data.tobytes())


def validate_annotation(record, folder, registry):
    if record.get('schema') != 'gesture.ai_pc.multiobject_annotation.v1':
        raise ValueError('Explicit multiobject annotation required')
    if record.get('split') not in ('train', 'validation', 'test'):
        raise ValueError('Explicit session split required')
    if not isinstance(record.get('session_id'), str) or not record['session_id'].strip():
        raise ValueError('Nonempty session ID required')
    image = (Path(folder)/record['image']).resolve()
    if not image.is_relative_to(Path(folder).resolve()) or digest(image) != record['image_sha256']:
        raise ValueError('Annotation source path/hash mismatch')
    im = read_image(image)
    h, w = im.shape[:2]
    if record.get('image_size_wh') != [w, h]:
        raise ValueError('Annotation frame size mismatch')
    objects = record.get('objects')
    if not isinstance(objects, list) or (not objects and record.get('empty_scene_confirmed') is not True):
        raise ValueError('Empty scene must be explicitly confirmed')
    for obj in objects:
        if obj.get('class_name') not in registry.objects:
            raise ValueError('Unknown annotation class')
        box = np.asarray(obj.get('bbox_xyxy_raw'), dtype=float)
        if (box.shape != (4,) or not np.isfinite(box).all() or min(box[:2]) < 0 or
                box[2] > w or box[3] > h or box[2] <= box[0] or box[3] <= box[1]):
            raise ValueError('Invalid annotation box')
        poly = obj.get('top_polygon_raw')
        if poly is not None:
            a = np.asarray(poly, np.float32)
            if (obj['class_name'] not in TASKS.values() or a.shape != (4, 2) or
                    not np.isfinite(a).all() or not cv2.isContourConvex(a) or cv2.contourArea(a) < 25 or
                    np.any(a < box[:2]) or np.any(a > box[2:])):
                raise ValueError('Only cube tops may have valid four-corner surface labels')
    return im


def compile_dataset(annotations, registry_file, out):
    import yaml
    registry = Registry.load(registry_file)
    names = list(registry.objects)
    out = Path(out).resolve()
    if out.exists():
        raise ValueError('Dataset destination already exists')
    records, sessions, images, pixels = [], {}, {}, set()
    for path in map(Path, annotations):
        r = json.loads(path.read_bytes())
        im = validate_annotation(r, path.parent, registry)
        session, split, sha = r['session_id'], r['split'], r['image_sha256']
        if session in sessions and sessions[session] != split:
            raise ValueError('Session leakage across splits')
        pixel = image_digest(im)
        if sha in images or pixel in pixels:
            raise ValueError('Duplicate source image/pixels or cross-split image leakage')
        sessions[session], images[sha] = split, split
        pixels.add(pixel)
        records.append((r, im, digest(path)))
    if not records or not any(r['split'] == 'train' for r, _, _ in records):
        raise ValueError('Training annotations required')
    out.mkdir(parents=True)
    items, counts = [], {s: Counter() for s in ('train', 'validation', 'test')}
    for i, (r, im, anno_hash) in enumerate(records):
        split = r['split']; w, h = r['image_size_wh']
        for kind in ('images', 'labels'):
            (out/kind/split).mkdir(parents=True, exist_ok=True)
        name = f'item_{i:06d}'
        image_rel = f'images/{split}/{name}.png'
        write_image(out/image_rel, im)
        labels = []
        for obj in r['objects']:
            x, y, x2, y2 = obj['bbox_xyxy_raw']
            labels.append(f'{names.index(obj["class_name"])} {(x+x2)/2/w:.9f} {(y+y2)/2/h:.9f} {(x2-x)/w:.9f} {(y2-y)/h:.9f}')
            counts[split][obj['class_name']] += 1
        (out/f'labels/{split}/{name}.txt').write_text('\n'.join(labels)+'\n', encoding='utf8')
        items.append({**r, 'image': image_rel, 'source_image_sha256': r['image_sha256'],
                      'image_sha256': digest(out/image_rel), 'annotation_sha256': anno_hash})
    manifest = {'schema': 'gesture.ai_pc.multiobject_dataset.v1', 'classes': names,
                'registry_sha256': digest(registry_file), 'items': items,
                'split_policy': 'WHOLE_SESSION_HASH_DEDUPLICATED',
                'counts_by_split': {s: dict(c) for s, c in counts.items()},
                'trained_classes': [n for n in names if counts['train'][n] > 0]}
    (out/'dataset.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf8')
    (out/'data.yaml').write_text(yaml.safe_dump({'path': str(out), 'train': 'images/train',
        'val': 'images/validation', 'test': 'images/test', 'names': dict(enumerate(names))}, sort_keys=False), encoding='utf8')
    return manifest
