"""Selective LVIS import. Full-instance masks are never promoted to top labels."""
from collections import Counter, defaultdict
from pathlib import Path
import hashlib
import json
import zipfile

LVIS_CLASSES = {425: 'eraser', 199: 'small_canister', 923: 'scissors'}
MODE_B_CLASSES = ['red_cube', 'yellow_cube', 'blue_cube', 'eraser', 'small_canister', 'scissors']


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def iter_lvis(archive, key):
    import ijson
    with zipfile.ZipFile(archive) as z:
        members = [n for n in z.namelist() if n.endswith('.json')]
        if len(members) != 1:
            raise ValueError('One official LVIS JSON expected')
        with z.open(members[0]) as stream:
            yield from ijson.items(stream, key+'.item', use_float=True)


def index_lvis(archive):
    """Keep the three genuine upstream categories; no cans/bottles relabelling."""
    annotations = defaultdict(list)
    categories = {c['id']: c['name'] for c in iter_lvis(archive, 'categories')}
    expected = {425: 'eraser', 199: 'canister', 923: 'scissors'}
    if any(categories.get(k) != v for k, v in expected.items()):
        raise ValueError('Unexpected LVIS category IDs')
    for a in iter_lvis(archive, 'annotations'):
        if a['category_id'] in LVIS_CLASSES:
            annotations[a['image_id']].append(a)
    images = {im['id']: im for im in iter_lvis(archive, 'images') if im['id'] in annotations}
    return {'schema': 'gesture.ai_pc.lvis_subset_index.v1',
            'upstream_annotation_sha256': sha256(archive),
            'category_mapping': {str(k): v for k, v in LVIS_CLASSES.items()},
            'images': images, 'annotations': dict(annotations),
            'counts': dict(Counter(LVIS_CLASSES[a['category_id']] for aa in annotations.values() for a in aa))}


def select_instances(index, limit_per_class):
    images = {int(k): v for k, v in index['images'].items()}
    chosen, count = [], Counter()
    # Stable order; large enough targets to review and fine-tune.
    anns = [a for aa in index['annotations'].values() for a in aa]
    anns.sort(key=lambda a: (-a['area'], a['id']))
    for a in anns:
        name = LVIS_CLASSES[a['category_id']]
        im = images[a['image_id']]
        x, y, w, h = a['bbox']
        if (count[name] >= limit_per_class or min(w, h) < 28 or
                w*h/(im['width']*im['height']) > .85 or
                a['category_id'] in im.get('not_exhaustive_category_ids', [])):
            continue
        # A short cylinder/eraser target cannot be identified by aspect alone;
        # these are broad proposal limits, followed by visual review.
        if name == 'small_canister' and not .45 < h/w < 2.3:
            continue
        if name == 'eraser' and max(h/w, w/h) > 5:
            continue
        chosen.append({'annotation': a, 'image': im, 'class_name': name})
        count[name] += 1
    return chosen


def complete_scissors(rows, image_annotations):
    """Once an image is used, label every annotated scissors instance in it."""
    if not rows:
        return []
    result=list(rows);known={row['annotation']['id'] for row in result}
    for other in image_annotations:
        if other['category_id']==923 and other['id'] not in known:
            result.append({**rows[0],'annotation':other,'class_name':'scissors'})
            known.add(other['id'])
    return result
