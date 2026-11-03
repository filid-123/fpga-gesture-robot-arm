"""Interchange tests: split leakage, tampering, frame identity and unmatched objects."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pc.mode_b.deployment import (POLICY, SCHEMA, RecordedDetector, compare, inside,
                                  load_inputs, polygon_iou, save, validate_detector_record)
from pc.mode_b.profile import CLASSES
from pc.multiobject.dataset import write_image
from pc.multiobject.yolo import digest, image_digest
from verify_deployment_archive import verify_zip


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.frame = np.full((40, 60, 3), 91, np.uint8)
        self.train = np.full_like(self.frame, 170)
        rows = []
        for name, frame, split in [('check', self.frame, 'replay'), ('train', self.train, 'train')]:
            file = self.root/(name+'.png')
            write_image(file, frame)
            rows.append({'id': name, 'image': file.name, 'image_sha256': digest(file),
                         'pixel_sha256': image_digest(frame), 'image_size_wh': [60, 40],
                         'split': split, 'session_id': name})
        rows[1]['source_image'] = 'train.png'
        self.data = {'schema': SCHEMA, 'classes': CLASSES, 'policy': POLICY,
                     'physical_execution': False, 'profile': 'profile.json',
                     'assets_sha256': {}, 'replay': [rows[0]],
                     'calibration': {'source_manifest': 'source.json', 'items': [rows[1]]}}
        save(self.root/'profile.json', json.loads((ROOT/'config/ai_pc/mode_b_six_objects_v1.json').read_bytes()))
        self.source = {'schema': 'gesture.ai_pc.mode_b_dataset.v1', 'classes': CLASSES,
                       'items': [deepcopy(rows[1])]}
        self.inputs = self.root/'inputs.json'
        self.flush()

    def tearDown(self):
        self.tmp.cleanup()

    def flush(self):
        save(self.root/'source.json', self.source)
        save(self.inputs, self.data)

    def test_valid_inputs_and_image_tampering(self):
        load_inputs(self.inputs, self.root)
        write_image(self.root/'check.png', self.train)
        with self.assertRaisesRegex(ValueError, 'hash/pixels'):
            load_inputs(self.inputs, self.root)

    def test_calibration_cannot_be_validation_content(self):
        self.source['items'][0]['split'] = 'validation'
        self.flush()
        with self.assertRaisesRegex(ValueError, 'source TRAIN'):
            load_inputs(self.inputs, self.root)

    def test_source_session_cannot_cross_splits(self):
        other = deepcopy(self.source['items'][0])
        other.update(split='validation', image='other.png', image_sha256='other', pixel_sha256='other')
        self.source['items'].append(other)
        self.flush()
        with self.assertRaisesRegex(ValueError, 'split leakage'):
            load_inputs(self.inputs, self.root)

    def test_replay_pixels_cannot_enter_calibration(self):
        self.source['items'][0]['pixel_sha256'] = self.data['replay'][0]['pixel_sha256']
        self.flush()
        with self.assertRaisesRegex(ValueError, 'Replay pixels'):
            load_inputs(self.inputs, self.root)

    def test_paths_cannot_escape_package(self):
        with self.assertRaisesRegex(ValueError, 'escapes'):
            inside(self.root, '../outside.png')

    def test_recorded_detection_requires_same_original_pixels(self):
        row = {'pixel_sha256': image_digest(self.frame), 'detections': [],
               'meta': {'backend': {'actual_backend': 'npu'}}}
        replay = RecordedDetector({}, row)
        self.assertEqual(replay.run(self.frame)[0], [])
        with self.assertRaisesRegex(ValueError, 'frame/policy'):
            replay.run(self.train)

    def test_missing_or_reordered_detector_frames_rejected(self):
        result = {'schema': 'gesture.ai_pc.mode_b_detector_stage.v1', 'status': 'COMPLETED',
                  'inputs_sha256': digest(self.inputs), 'policy': POLICY,
                  'physical_execution': False, 'records': []}
        with self.assertRaisesRegex(ValueError, 'frame set/order'):
            validate_detector_record(result, self.data, self.inputs)

    def test_comparison_reports_missing_extra_and_top_regression(self):
        def det(name, box):
            return {'class_name': name, 'bbox_xyxy_raw': box, 'confidence': .9}
        def obs(detections, top):
            return {'frame_sha256': image_digest(self.frame), 'recognitions': detections,
                    'localizations': [{'task_id': 1, 'class_name': 'red_cube',
                                       'status': 'PIXEL_SURFACE_ONLY' if top else 'NOT_FOUND',
                                       'pixel_surface': top}]}
        top = {'quad_pixel_uv': [[1, 1], [10, 1], [10, 10], [1, 10]], 'pixel_uv': [5.5, 5.5]}
        self.assertEqual(polygon_iou(top, top), 1)
        ref = obs([det('red_cube', [1, 1, 10, 10]), det('eraser', [20, 1, 30, 10])], top)
        new = obs([det('red_cube', [2, 1, 11, 10]), det('blue_cube', [40, 1, 50, 10])], None)
        for name, observation in [('ref', ref), ('new', new)]:
            save(self.root/(name+'.json'), {'schema': 'gesture.ai_pc.mode_b_surface_stage.v1',
                 'status': 'COMPLETED', 'inputs_sha256': digest(self.inputs),
                 'records': [{'id': 'check', 'observation': observation}]})
        result = compare(self.root/'ref.json', self.root/'new.json', self.inputs,
                         self.root, self.root/'comparison.json')
        row = result['records'][0]
        self.assertEqual(row['missing_relative_to_cpu'], ['eraser'])
        self.assertEqual(row['extra_relative_to_cpu'], ['blue_cube'])
        self.assertFalse(row['localizations'][0]['candidate_available'])
        self.assertFalse(result['hardware_acceptance'])

    def test_archive_rejects_modified_bytes(self):
        manifest = {'files': [{'path': 'data.txt', 'sha256': '0'*64}]}
        file = self.root/'bad.zip'
        with zipfile.ZipFile(file, 'w') as z:
            z.writestr('FILE_MANIFEST.json', json.dumps(manifest))
            z.writestr('data.txt', 'modified')
        with self.assertRaisesRegex(ValueError, 'content mismatch'):
            verify_zip(file)


if __name__ == '__main__':
    unittest.main(verbosity=2)
