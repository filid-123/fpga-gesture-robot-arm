"""Class-preserving detector differences; no hardware proof is inferred."""
import numpy as np
from pc.multiobject.yolo import iou


def average_precision(records, name, threshold):
    truth = {i: [o for o in row['truth'] if o['class_name'] == name] for i, row in enumerate(records)}
    total = sum(map(len, truth.values()))
    if total == 0: return None
    seen, hits = {i: set() for i in truth}, []
    predictions = sorted([(d['confidence'], i, d) for i, row in enumerate(records)
        for d in row['detections'] if d['class_name'] == name], key=lambda x: -x[0])
    for _, i, d in predictions:
        overlap, j = max([(iou(d['bbox_xyxy_raw'], obj['bbox_xyxy_raw']), j)
            for j, obj in enumerate(truth[i]) if j not in seen[i]], default=(0, -1))
        hit = overlap >= threshold
        if hit: seen[i].add(j)
        hits.append(int(hit))
    if not hits: return 0.
    tp = np.cumsum(hits); fp = np.cumsum(1-np.asarray(hits))
    recall, precision = tp/total, tp/(tp+fp)
    return float(np.mean([max(precision[recall >= value], default=0.) for value in np.linspace(0, 1, 101)]))


def compare_detections(reference, candidate, threshold=.5):
    remaining = set(range(len(candidate))); matches, missing = [], []
    for ref in sorted(reference, key=lambda d: -d['confidence']):
        overlap, index = max([(iou(ref['bbox_xyxy_raw'], candidate[j]['bbox_xyxy_raw']), j)
            for j in remaining if candidate[j]['class_name'] == ref['class_name']], default=(0, -1))
        if overlap < threshold:
            missing.append(ref); continue
        remaining.remove(index); other = candidate[index]
        a, b = np.asarray(ref['bbox_xyxy_raw']), np.asarray(other['bbox_xyxy_raw'])
        matches.append({'class_name': ref['class_name'], 'iou': overlap,
            'confidence_delta': other['confidence']-ref['confidence'],
            'centre_shift_pixels': float(np.linalg.norm((a[:2]+a[2:]-b[:2]-b[2:])/2))})
    return {'matched': matches, 'reference_missing_in_candidate': missing,
            'candidate_extra': [candidate[j] for j in sorted(remaining)]}
