"""Numeric golden cases independent of the inference implementation."""
import unittest
import tempfile
import json
from pathlib import Path
from unittest.mock import patch
import evaluate_competition_vision as evaluation
from vision_report_metrics import average_precision, segmentation_metrics, validate_objects


def gt(name='red_cube', box=(0, 0, 10, 10)):
    return {'class_name': name, 'bbox_xyxy_raw': list(box)}


def det(score=.9, name='red_cube', box=(0, 0, 10, 10)):
    return {**gt(name, box), 'confidence': score}


class MetricsTests(unittest.TestCase):
    def test_perfect_and_missing_and_wrong_class(self):
        for predictions, value in [([det()], 1.), ([], 0.), ([det(name='eraser')], 0.)]:
            report = average_precision([{'objects': [gt()], 'detections': predictions}], ['red_cube', 'eraser'])
            self.assertEqual(report['mAP50'], value)
            self.assertEqual(report['mAP50_95'], value)
            self.assertIsNone(report['per_class']['eraser']['AP50'])

    def test_high_confidence_false_positive_reduces_ap(self):
        row = {'objects': [gt()], 'detections': [det(.99, box=(20, 20, 30, 30)), det(.8)]}
        self.assertEqual(average_precision([row], ['red_cube'])['mAP50'], .5)

    def test_one_to_one_duplicate_cannot_recover_second_object(self):
        row = {'objects': [gt(), gt(box=(20, 20, 30, 30))], 'detections': [det(.9), det(.8)]}
        self.assertAlmostEqual(average_precision([row], ['red_cube'])['mAP50'], 51/101)

    def test_iou_threshold_sweep_uses_continuous_box_area(self):
        row = {'objects': [gt()], 'detections': [det(box=(0, 0, 10, 6))]}
        report = average_precision([row], ['red_cube'])
        self.assertEqual(report['mAP50'], 1.)
        self.assertAlmostEqual(report['mAP50_95'], .3)

    def test_false_positive_on_empty_frame_counts_in_ranking(self):
        rows = [{'objects': [], 'detections': [det(.99)]}, {'objects': [gt()], 'detections': [det(.8)]}]
        self.assertEqual(average_precision(rows, ['red_cube'])['mAP50'], .5)

    def test_official_coco_float_recall_boundary(self):
        objects = [gt(box=(i*20, 0, i*20+10, 10)) for i in range(20)]
        detections = [{**o, 'confidence': .9} for o in objects[:19]]
        report = average_precision([{'objects': objects, 'detections': detections}], ['red_cube'])
        # COCO np.linspace recall at .95 is .9500000000000001; no epsilon
        # is added to recall. This catches an otherwise one-sample AP mismatch.
        self.assertAlmostEqual(report['mAP50'], 95/101)

    def test_binary_miou_is_not_foreground_iou(self):
        value = segmentation_metrics(tp=20, fp=10, fn=10, tn=60)
        self.assertEqual(value['foreground_IoU'], .5)
        self.assertEqual(value['background_IoU'], .75)
        self.assertEqual(value['binary_mIoU'], .625)
        self.assertIsNone(segmentation_metrics(0, 0, 0, 0)['binary_mIoU'])
        with self.assertRaises(ValueError):
            segmentation_metrics(-1, 1, 1, 1)

    def test_invalid_labels_are_rejected(self):
        with self.assertRaises(ValueError):
            validate_objects([gt(box=(0, 0, 11, 10))], ['red_cube'], 10, 10)
        with self.assertRaises(ValueError):
            validate_objects([gt(box=(0, 0, float('nan'), 10))], ['red_cube'], 10, 10)

    def test_overlap_includes_ancestor_hash_and_capture_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'train.json').write_text(json.dumps({'items': [
                {'split': 'train', 'source': {'parent': {'image_sha256': 'ancestor'}},
                 'session_id': 'shared'}]}))
            with patch.object(evaluation, 'ROOT', root):
                result = evaluation.check_overlap([
                    {'image': 'a', 'image_sha256': 'ancestor'},
                    {'image': 'b', 'image_sha256': 'different', 'session_id': 'shared'},
                    {'image': 'c', 'image_sha256': 'other', 'session_id': 'new'}], ['train.json'])
                self.assertEqual([m['image'] for m in result['matches']], ['a', 'b'])
                self.assertEqual(result['matches'][0]['hashes'], ['ancestor'])
                self.assertTrue(result['matches'][1]['session_overlap'])
                with self.assertRaises(ValueError):
                    evaluation.local('../escape.json')

    def test_one_pipeline_top_cannot_cover_multiple_same_class_objects(self):
        objects = [gt(), gt(box=(20, 20, 30, 30))]
        self.assertTrue(evaluation.localization_matches(gt(), objects, 0))
        self.assertFalse(evaluation.localization_matches(gt(), objects, 1))
        self.assertFalse(evaluation.localization_matches({'class_name': 'red_cube'}, objects, 0))


if __name__ == '__main__':
    unittest.main()
