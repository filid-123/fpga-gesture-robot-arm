"""Recompute public saved-prediction metrics with the Python standard library."""
import hashlib
import json
from pathlib import Path
from vision_report_metrics import average_precision, segmentation_metrics

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT/'metrics/evidence/vision_20261103'


def verify(base=EVIDENCE):
    base = Path(base).resolve()
    index = json.loads((base/'evidence_index.json').read_bytes())
    for name, expected in index['files_sha256'].items():
        path = (base/name).resolve()
        if not path.is_relative_to(base) or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError('Saved evidence hash differs: '+name)
    results = []
    for name in ('final_development_validation', 'final_one_layout_check'):
        report = json.loads((base/name/'report.json').read_bytes())
        records = json.loads((base/name/'predictions.json').read_bytes())
        ap = average_precision(records, list(report['detection']['per_class']))
        if ap != report['detection']:
            raise ValueError('Detection AP does not reproduce')
        keys = ('TP_pixels', 'FP_pixels', 'FN_pixels', 'TN_pixels')
        counts = [sum(r[k] for r in report['segmentation']['per_object']) for k in keys]
        binary = segmentation_metrics(*counts)
        if binary != report['segmentation']['pooled_pixels']:
            raise ValueError('Binary mIoU does not reproduce')
        if report['independent_test_accepted'] or report['millimetre_accuracy_measured']:
            raise ValueError('Evidence scope unexpectedly changed')
        results.append({'scope': report['scope'], 'mAP50': ap['mAP50'],
                        'mAP50_95': ap['mAP50_95'], 'binary_mIoU': binary['binary_mIoU']})
    return {'passed': True, 'scope': 'SAVED_NUMERIC_PREDICTIONS_NOT_NEW_MODEL_INFERENCE',
            'results': results, 'hardware_access': False}


if __name__ == '__main__':
    print(json.dumps(verify(), ensure_ascii=False, indent=2))
