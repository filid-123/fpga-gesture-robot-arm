"""Auditable box AP and binary-mask metrics; no training/runtime side effects.

AP uses class-aware greedy matching per image, continuous XYXY areas, up to
100 detections per image, and the mean of 101 interpolated precision samples.
No crowd/ignore/area subsets are implemented: this is COCO-style AP for our
fully labelled scenes, not the complete official COCO evaluator.
"""
import math


def box_iou(a, b):
    inter = max(0., min(a[2], b[2])-max(a[0], b[0])) * max(
        0., min(a[3], b[3])-max(a[1], b[1]))
    union = (a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-inter
    return inter/union if union > 0 else 0.


def average_precision(records, classes):
    # Match numpy.linspace in official COCO, including float sample boundaries.
    thresholds = [.50+((.95-.50)/9)*i for i in range(10)]
    thresholds[-1] = .95
    rows = {}
    for name in classes:
        ground = [[o['bbox_xyxy_raw'] for o in r['objects']
                   if o['class_name'] == name] for r in records]
        n = sum(map(len, ground))
        predictions = [(d['confidence'], image, d['bbox_xyxy_raw'])
                       for image, r in enumerate(records)
                       for d in sorted(r['detections'], key=lambda x: -x['confidence'])[:100]
                       if d['class_name'] == name]
        predictions.sort(key=lambda p: -p[0])  # Stable confidence ties.
        aps = []
        for threshold in thresholds:
            used = [set() for _ in records]
            precision, recall = [], []
            tp = 0
            for count, (_, image, box) in enumerate(predictions, 1):
                available = [(box_iou(box, g), j) for j, g in enumerate(ground[image])
                             if j not in used[image]]
                overlap, match = max(available, default=(0., -1))
                if overlap >= threshold:
                    used[image].add(match)
                    tp += 1
                precision.append(tp/count)
                recall.append(tp/n if n else 0.)
            if not n:
                aps.append(None)
                continue
            # Right-to-left precision envelope, then sample recall 0:0.01:1.
            for i in range(len(precision)-2, -1, -1):
                precision[i] = max(precision[i], precision[i+1])
            values = []
            cursor = 0
            for i in range(101):
                while cursor < len(recall) and recall[cursor] < i*.01:
                    cursor += 1
                values.append(precision[cursor] if cursor < len(precision) else 0.)
            aps.append(sum(values)/101)
        rows[name] = {'ground_truth_instances': n, 'predictions': len(predictions),
                      'AP50': aps[0], 'AP50_95': sum(aps)/10 if n else None,
                      'AP_by_iou': dict(zip((str(round(t, 2)) for t in thresholds), aps))}
    present = [r for r in rows.values() if r['ground_truth_instances']]
    return {'definition': 'COCO_STYLE_101_POINT_NO_CROWD_NO_AREA_SUBSETS_MAXDET100',
            'IoU_thresholds': thresholds, 'per_class': rows,
            'mAP50': sum(r['AP50'] for r in present)/len(present) if present else None,
            'mAP50_95': sum(r['AP50_95'] for r in present)/len(present) if present else None,
            'absent_classes_excluded_from_mean': [n for n, r in rows.items()
                                                 if not r['ground_truth_instances']]}


def segmentation_metrics(tp, fp, fn, tn):
    if any(type(v) is not int or v < 0 for v in (tp, fp, fn, tn)):
        raise ValueError('Nonnegative integer pixel counts required')
    foreground = tp/(tp+fp+fn) if tp+fp+fn else None
    background = tn/(tn+fp+fn) if tn+fp+fn else None
    valid = [x for x in (foreground, background) if x is not None]
    return {'TP_pixels': tp, 'FP_pixels': fp, 'FN_pixels': fn, 'TN_pixels': tn,
            'foreground_IoU': foreground, 'background_IoU': background,
            'binary_mIoU': sum(valid)/len(valid) if valid else None}


def validate_objects(objects, classes, width, height):
    for obj in objects:
        box = obj.get('bbox_xyxy_raw', [])
        if (obj.get('class_name') not in classes or len(box) != 4
                or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in box)
                or not 0 <= box[0] < box[2] <= width
                or not 0 <= box[1] < box[3] <= height):
            raise ValueError('Invalid class/box in ground truth')
