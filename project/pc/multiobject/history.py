"""Reuse reviewed historical originals while preserving frozen holdout families."""
from pathlib import Path
import json
import numpy as np
from pc.multiobject.dataset import read_image, write_image, validate_annotation, compile_dataset
from pc.multiobject.registry import Registry
from pc.multiobject.yolo import digest, image_digest


def build_history(review_file, baseline_file, registry_file, root, out):
    root, out = Path(root).resolve(), Path(out).resolve()
    if out.exists(): raise ValueError('Fresh history output required')
    review = json.loads(Path(review_file).read_bytes())
    baseline = json.loads(Path(baseline_file).read_bytes())
    if review.get('schema') != 'gesture.ai_pc.historical_review.v1': raise ValueError('Explicit historical review required')
    registry = Registry.load(registry_file)
    protected_sessions = {i['session_id'] for i in baseline['items'] if i['split'] != 'train'}
    protected_pixels = {image_digest(read_image(Path(baseline_file).parent/i['image']))
                        for i in baseline['items'] if i['split'] != 'train'}
    protected_groups = set(review['frozen_holdout_groups'])
    seen, groups, prepared = set(), {}, []
    for row in review['items']:
        source = (root/row['source']).resolve()
        if not source.is_relative_to(root) or digest(source) != row['source_sha256']:
            raise ValueError('Historical source path/hash mismatch')
        frame = read_image(source); pixel = image_digest(frame)
        if pixel in seen: raise ValueError('Duplicate historical source pixels')
        seen.add(pixel)
        group, split = row['scene_group'], row['split']
        if split not in ('train', 'validation'): raise ValueError('Frozen tests are not re-labelled by this tool')
        if (group in groups and groups[group] != split): raise ValueError('Scene family crosses splits')
        groups[group] = split
        if split == 'train' and (group in protected_groups or source.parent.name in protected_sessions or pixel in protected_pixels):
            raise ValueError('Frozen holdout family cannot supply training pixels')
        if row.get('review_kind') != 'AI_VISUAL_REVIEW_NO_MODEL_PREDICTIONS':
            raise ValueError('Review provenance must be explicit; not human ground truth')
        h, w = frame.shape[:2]
        x, y, cw, ch = row.get('crop_xywh', [0, 0, w, h])
        if (any(type(v) is not int for v in (x, y, cw, ch)) or min(x, y) < 0 or min(cw, ch) <= 0 or x+cw > w or y+ch > h):
            raise ValueError('Historical crop lies outside original')
        objects = []
        for obj in row['objects_raw']:
            box = np.asarray(obj['bbox_xyxy_raw'], dtype=float)-[x, y, x, y]
            if np.any(box[:2] < 0) or np.any(box[2:] > [cw, ch]):
                raise ValueError('Reviewed object must be fully inside selected crop')
            objects.append({'class_name': obj['class_name'], 'bbox_xyxy_raw': box.tolist()})
        prepared.append((row, frame[y:y+ch, x:x+cw].copy(), objects))
    # Validate all sources and holdout boundaries before any outputs are created.
    out.mkdir(parents=True)
    labels = out/'annotations'; labels.mkdir()
    annotations = []
    for index, (row, frame, objects) in enumerate(prepared):
        folder = labels/f'history_{index:03d}'; folder.mkdir()
        write_image(folder/'image.png', frame)
        record = {'schema': 'gesture.ai_pc.multiobject_annotation.v1', 'session_id': row['scene_group'],
            'split': row['split'], 'image': 'image.png', 'image_sha256': digest(folder/'image.png'),
            'image_size_wh': [frame.shape[1], frame.shape[0]], 'objects': objects,
            'empty_scene_confirmed': not objects,
            'annotation_kind': 'AI_VISUAL_REVIEWED_HISTORICAL_BOXES_NOT_HUMAN_GROUND_TRUTH',
            'collection_source_kind': 'HISTORICAL_CAMERA_ORIGINAL',
            'historical_provenance': {'source': row['source'], 'source_sha256': row['source_sha256'],
                'review_manifest_sha256': digest(review_file), 'crop_xywh': row.get('crop_xywh'),
                'scene_group': row['scene_group'], 'ignored_distractors': row.get('ignored_distractors', [])}}
        validate_annotation(record, folder, registry)
        path = folder/'annotation.json'; path.write_text(json.dumps(record, indent=2)+'\n', encoding='utf8')
        annotations.append(path)
    # Existing synthetic TRAIN material remains labelled as weak bootstrap, never independent data.
    for index, item in enumerate(baseline['items']):
        if item['split'] != 'train' or item['image_size_wh'] != [384, 384]: continue
        source = Path(baseline_file).parent/item['image']
        frame = validate_annotation(item, Path(baseline_file).parent, registry)
        folder = labels/f'bootstrap_{index:03d}'; folder.mkdir()
        write_image(folder/'image.png', frame)
        record = {**item, 'image': 'image.png', 'image_sha256': digest(folder/'image.png')}
        path = folder/'annotation.json'; path.write_text(json.dumps(record, indent=2)+'\n', encoding='utf8')
        annotations.append(path)
    data = compile_dataset(annotations, registry_file, out/'dataset')
    summary = {'schema': 'gesture.ai_pc.historical_reuse_summary.v1',
        'historical_originals_reviewed': len(prepared), 'counts_by_split': data['counts_by_split'],
        'image_counts': {s: sum(i['split'] == s for i in data['items']) for s in ('train', 'validation', 'test')},
        'frozen_baseline_sha256': digest(baseline_file), 'review_sha256': digest(review_file),
        'protected_sessions': sorted(protected_sessions), 'test_images_copied_to_training': 0,
        'test_images_evaluated_this_run': 0, 'independent_human_labels': False,
        'physical_execution': False, 'final_acceptance': False}
    (out/'summary.json').write_text(json.dumps(summary, indent=2)+'\n', encoding='utf8')
    return summary
