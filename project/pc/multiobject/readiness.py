"""Count reviewed live examples separately from historical bootstrap material."""
from collections import Counter
from pathlib import Path
import json
from pc.multiobject.dataset import validate_annotation
from pc.multiobject.registry import TASKS, Registry
from pc.multiobject.yolo import digest, image_digest


def audit_dataset(path, registry_path, policy):
    path = Path(path).resolve()
    data = json.loads(path.read_bytes())
    if data.get('schema') != 'gesture.ai_pc.multiobject_dataset.v1': raise ValueError('Compiled dataset required')
    registry = Registry.load(registry_path)
    if data.get('registry_sha256') != digest(registry_path): raise ValueError('Dataset registry hash mismatch')
    sessions, hashes, pixels = {}, set(), set()
    counts = {s: {'images': 0, 'eligible_live_manual_images': 0, 'negative_images': 0,
        'classes': Counter(), 'tops': Counter(), 'sessions': set(), 'lighting': set()}
        for s in ('train', 'validation', 'test')}
    excluded = Counter()
    historical = {s: {'images': 0, 'classes': Counter()} for s in counts}
    for item in data['items']:
        image = validate_annotation(item, path.parent, registry)
        sha, pixel, session, split = item['image_sha256'], image_digest(image), item['session_id'], item['split']
        if session in sessions and sessions[session] != split: raise ValueError('Session crosses dataset splits')
        if sha in hashes or pixel in pixels: raise ValueError('Duplicate encoded image or duplicate pixels')
        sessions[session] = split; hashes.add(sha); pixels.add(pixel)
        c = counts[split]; c['images'] += 1
        if (item.get('collection_source_kind') == 'HISTORICAL_CAMERA_ORIGINAL' and
                item.get('annotation_kind') == 'AI_VISUAL_REVIEWED_HISTORICAL_BOXES_NOT_HUMAN_GROUND_TRUTH'):
            historical[split]['images'] += 1
            historical[split]['classes'].update(o['class_name'] for o in item['objects'])
        eligible = (item.get('annotation_kind') == 'INDEPENDENT_MANUAL_NO_PREDICTIONS' and
                    item.get('collection_source_kind') == 'LIVE_CAMERA' and item.get('capture_provenance'))
        if not eligible:
            excluded[item.get('annotation_kind', 'UNSPECIFIED')+'|'+item.get('collection_source_kind', 'UNVERIFIED_SOURCE')] += 1
            continue
        provenance = item['capture_provenance']
        if (provenance.get('pixel_sha256') != pixel or
                not isinstance(provenance.get('session_manifest_sha256'), str) or
                len(provenance['session_manifest_sha256']) != 64):
            raise ValueError('Live manual annotation lost its capture pixel/session binding')
        c['eligible_live_manual_images'] += 1; c['sessions'].add(session)
        lighting = item.get('lighting_description', '').strip()
        if lighting: c['lighting'].add(lighting)
        if not item['objects']: c['negative_images'] += 1
        for obj in item['objects']:
            c['classes'][obj['class_name']] += 1
            if obj.get('top_polygon_raw'): c['tops'][obj['class_name']] += 1
    deficits = []
    def check(split, metric, actual, required, name=None):
        if actual < required:
            deficits.append({'split': split, 'metric': metric, 'class_name': name,
                'actual': actual, 'required': required, 'missing': required-actual})
    for split, c in counts.items():
        spec = policy['minimums'][split]
        check(split, 'negative_images', c['negative_images'], spec['negative_images'])
        check(split, 'sessions', len(c['sessions']), spec['sessions'])
        check(split, 'lighting_conditions', len(c['lighting']), spec['lighting_conditions'])
        for name in TASKS.values():
            check(split, 'positive_instances', c['classes'][name], spec['positive_instances_per_cube'], name)
            check(split, 'top_polygons', c['tops'][name], spec['top_polygons_per_cube'], name)
    serial = {s: {**c, 'classes': dict(c['classes']), 'tops': dict(c['tops']),
                  'sessions': sorted(c['sessions']), 'lighting': sorted(c['lighting'])} for s, c in counts.items()}
    return {'schema': 'gesture.ai_pc.multiobject_data_readiness.v1', 'dataset_sha256': digest(path),
        'policy': policy, 'counts': serial, 'excluded_from_independent_live_counts': dict(excluded),
        'reviewed_historical_material': {s: {**c, 'classes': dict(c['classes'])} for s, c in historical.items()},
        'deficits': deficits, 'status': 'COLLECTION_TARGETS_MET' if not deficits else 'MORE_DATA_REQUIRED',
        'automatic_accuracy_claim': False, 'final_acceptance': False,
        'scope': 'COLLECTION_COMPLETENESS_NOT_LABEL_CORRECTNESS_OR_MODEL_QUALITY', 'physical_execution': False}
