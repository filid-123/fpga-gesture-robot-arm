"""Preview/frame binding tests with synthetic pixels. No camera or motion."""
import base64
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

import cv2
import numpy as np

from scripts.test_project_console import console, request, running
import vision


def image(value=30):
    frame = np.full((48, 64, 3), value, np.uint8)
    ok, raw = cv2.imencode('.png', frame)
    assert ok
    return frame, 'data:image/png;base64,' + base64.b64encode(raw).decode()


class Detector:
    def __init__(self): self.frames = []
    def run(self, frame, confidence):
        self.frames.append(frame.copy())
        return [{'class_name': 'eraser', 'confidence': .9, 'bbox_xyxy_raw': [1, 2, 20, 30],
                 'trained': True, 'task_id': 2}], {'backend': {'actual_backend': 'FAKE_TEST'}}


def fake_vision():
    service = vision.Vision()
    service.detector = Detector()
    service.model_info = {'confidence_threshold': .4}
    service.load = lambda: None
    return service


class PreviewTests(unittest.TestCase):
    def test_same_frame_hash_image_identity_and_historical_task_id_removed(self):
        service = fake_vision()
        for index, value in enumerate((30, 170)):
            frame, png = image(value)
            result = service.infer({'frame_id': str(index), 'source': 'photo', 'image': png})
            self.assertEqual(result['frame_id'], str(index))
            self.assertEqual(result['frame_sha256'], hashlib.sha256(frame.tobytes()).hexdigest())
            self.assertEqual(result['image_size_wh'], [64, 48])
            rendered = cv2.imdecode(np.frombuffer(base64.b64decode(result['image'].split(',')[1]), np.uint8), cv2.IMREAD_COLOR)
            self.assertTrue(np.array_equal(rendered, frame))
            self.assertNotIn('task_id', result['detections'][0])
            self.assertFalse(result['physical_execution'])
            self.assertFalse(result['metric_coordinates_enabled'])
            self.assertFalse(result['npu_accepted'])
            self.assertEqual(result['path_submissions'], 0)
        self.assertEqual(len(service.detector.frames), 2)

    def test_invalid_source_id_and_oversized_png_do_not_reach_model(self):
        service = fake_vision()
        _, png = image()
        invalid = [{'frame_id': '', 'source': 'camera', 'image': png},
                   {'frame_id': 'x', 'source': 'sample_replay', 'image': png},
                   {'frame_id': 'x', 'source': 'photo', 'image': 'data:image/png;base64,!!'}]
        raw = bytearray(base64.b64decode(png.split(',')[1]))
        raw[16:24] = struct.pack('>II', 99999, 99999)
        invalid.append({'frame_id': 'x', 'source': 'photo', 'image': 'data:image/png;base64,' + base64.b64encode(raw).decode()})
        for payload in invalid:
            with self.assertRaises(vision.VisionError): service.infer(payload)
        self.assertEqual(service.detector.frames, [])

    def test_one_inference_at_a_time_no_queue_or_retry(self):
        service = fake_vision()
        _, png = image()
        with service.lock:
            with self.assertRaises(vision.VisionError) as caught:
                service.infer({'frame_id': 'x', 'source': 'camera', 'image': png})
        self.assertEqual(caught.exception.code, 409)
        self.assertFalse(service.detector.frames)

    def test_sample_replay_uses_capture_hash_and_is_never_marked_live(self):
        service = fake_vision()
        frame, png = image()
        with tempfile.TemporaryDirectory() as directory:
            sample_dir = Path(directory)
            raw = base64.b64decode(png.split(',')[1]); path = sample_dir/'sample.png'; path.write_bytes(raw)
            record = {'used_for_training': False, 'frames': [{'image': str(path),
                'image_sha256': hashlib.sha256(raw).hexdigest(), 'pixel_sha256': hashlib.sha256(frame.tobytes()).hexdigest(),
                'received_utc': '2026-10-27T00:00:00Z'}]}
            manifest = sample_dir/'capture.json'; manifest.write_text(json.dumps(record))
            with patch.object(vision, 'SAMPLE', manifest), patch.object(service, 'status', return_value={'sample_available': True}):
                result = service.infer({'frame_id': 'replay'}, sample=True)
                self.assertEqual(result['source'], 'sample_replay')
                path.write_bytes(b'changed')
                with self.assertRaisesRegex(vision.VisionError, '校验失败'):
                    service.infer({'frame_id': 'changed'}, sample=True)
            self.assertEqual(len(service.detector.frames), 1)

    def test_http_status_is_lazy_and_preview_requires_token(self):
        server = console.make_server('127.0.0.1', 0, {}, device={})
        service = fake_vision(); server.vision = service
        with running(server) as url:
            self.assertFalse(request(url+'/api/status')[1]['connected'])
            self.assertFalse(service.detector.frames)
            _, png = image()
            payload = {'frame_id': 'camera-01', 'source': 'camera', 'image': png}
            self.assertEqual(request(url+'/api/vision/infer', payload)[0], 403)
            headers = {'X-Console-Token': server.csrf_token}
            code, result = request(url+'/api/vision/infer', payload, headers)
            self.assertEqual(code, 200)
            self.assertEqual(result['source'], 'camera')
            self.assertEqual(result['frame_id'], 'camera-01')
            self.assertFalse(server.bridge.processed)
            self.assertEqual(len(service.detector.frames), 1)


if __name__ == '__main__': unittest.main()
