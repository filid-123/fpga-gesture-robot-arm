"""Lazy, read-only adapter for the existing frozen six-object detector.

No camera/robot imports. PNG bytes come from an explicitly selected browser
camera or photo. Offline sample replay is always identified as replay.
"""
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
import struct
import sys
import threading
import time

REPO = Path(__file__).resolve().parents[2]
FREEZE = REPO / 'artifacts/multiobject/eraser_top_repair_20261027/candidate_freeze_v2.json'
SAMPLE = REPO / 'artifacts/multiobject/eraser_top_repair_20261027/fresh_confirmation_capture/capture.json'
CLASSES = ['red_cube', 'yellow_cube', 'blue_cube', 'eraser', 'small_canister', 'scissors']
MAX_PNG = 8 * 1024 * 1024


class VisionError(Exception):
    def __init__(self, code, message):
        self.code, self.message = code, message
        super().__init__(message)


def png_bytes(value):
    if not isinstance(value, str) or not value.startswith('data:image/png;base64,'):
        raise VisionError(400, '请提供PNG图像。')
    if len(value) > MAX_PNG * 4 // 3 + 64:
        raise VisionError(413, '照片过大，请使用不超过1920×1080的图像。')
    try:
        raw = base64.b64decode(value.split(',', 1)[1], validate=True)
    except ValueError:
        raise VisionError(400, '图像编码无效。') from None
    # Bound decoded memory before OpenCV allocates an image.
    if len(raw) < 33 or raw[:8] != b'\x89PNG\r\n\x1a\n' or raw[12:16] != b'IHDR':
        raise VisionError(400, 'PNG图像不完整。')
    width, height = struct.unpack('>II', raw[16:24])
    if not (32 <= width <= 1920 and 32 <= height <= 1920 and width * height <= 1920 * 1080):
        raise VisionError(413, '图像尺寸应介于32像素与1920×1080像素范围内。')
    return raw


class Vision:
    def __init__(self, config=None):
        self.enabled = (config or {}).get('local_enabled', True) is True
        self.lock = threading.Lock()
        self.detector = None
        self.model_info = None
        self.last_error = None

    def status(self):
        available = self.enabled and FREEZE.is_file() and (REPO/'model_package/mode_b/detector_background_v2/model.onnx').is_file()
        return {'available': available, 'loaded': self.detector is not None,
                'backend': 'onnx_cpu', 'classes': CLASSES, 'sample_available': available and SAMPLE.is_file(),
                'npu_accepted': False, 'physical_execution': False, 'last_error': self.last_error}

    def load(self):
        if not self.status()['available']:
            raise VisionError(503, '本机六类识别模型未安装，请按接入说明配置模型。')
        if self.detector is not None:
            return
        freeze = json.loads(FREEZE.read_bytes())
        for name, expected in freeze['files_sha256'].items():
            path = (REPO/name).resolve()
            if not path.is_relative_to(REPO) or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                raise VisionError(503, '冻结识别文件校验失败，请核对原识别环境。')
        if str(REPO) not in sys.path:
            sys.path.insert(0, str(REPO))
        # Keep the frozen inference code untouched. This adapter only needs the
        # detector, not the old fixed task mapping or grasp/surface pipeline.
        from pc.multiobject.yolo import Detector
        from pc.mode_b.tiled_detector import TiledDetector
        detector = Detector(REPO/freeze['detector_package'], backend='onnx_cpu')
        if detector.spec['classes'] != CLASSES:
            raise VisionError(503, '模型类别不匹配。')
        if freeze['tiled_inference']:
            detector = TiledDetector(detector)
        self.model_info = {'freeze_sha256': hashlib.sha256(FREEZE.read_bytes()).hexdigest(),
                           'model_sha256': freeze['files_sha256']['model_package/mode_b/detector_background_v2/model.onnx'],
                           'frozen_files_verified': len(freeze['files_sha256']),
                           'confidence_threshold': freeze['detector_confidence']}
        self.detector = detector

    def infer(self, payload, *, sample=False):
        if not isinstance(payload, dict):
            raise VisionError(400, '识别请求格式无效。')
        frame_id = payload.get('frame_id')
        if not isinstance(frame_id, str) or not 1 <= len(frame_id) <= 80:
            raise VisionError(400, '缺少图像编号。')
        sample_row = None
        if sample:
            if not self.status()['sample_available']:
                raise VisionError(503, '本机尚未配置识别样例。')
            try:
                record = json.loads(SAMPLE.read_bytes())
                sample_row = record['frames'][0]
                path = (REPO/sample_row['image']).resolve()
                if not path.is_relative_to(SAMPLE.parent) or record['used_for_training'] is not False:
                    raise VisionError(503, '识别样例来源无效。')
                raw = path.read_bytes()
                if hashlib.sha256(raw).hexdigest() != sample_row['image_sha256']:
                    raise VisionError(503, '识别样例文件校验失败。')
            except (OSError, ValueError, KeyError, IndexError, TypeError):
                raise VisionError(503, '识别样例证据不完整，请核对原采集文件。') from None
            source = 'sample_replay'
            raw = png_bytes('data:image/png;base64,' + base64.b64encode(raw).decode())
        else:
            source = payload.get('source')
            if source not in ('camera', 'photo'):
                raise VisionError(400, '请选择相机或照片来源。')
            raw = png_bytes(payload.get('image'))
        if not self.lock.acquire(blocking=False):
            raise VisionError(409, '识别服务正在处理上一帧，请稍后再试。')
        try:
            started = time.perf_counter()
            self.load()
            import cv2
            import numpy as np
            from pc.multiobject.yolo import image_digest
            frame = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
            if frame is None:
                raise VisionError(400, '无法解码图像。')
            height, width = frame.shape[:2]
            if frame.shape != (height, width, 3) or width * height > 1920 * 1080:
                raise VisionError(400, '图像像素格式无效。')
            pixel_hash = image_digest(frame)
            if sample_row and pixel_hash != sample_row['pixel_sha256']:
                raise VisionError(503, '识别样例像素校验失败。')
            detections, meta = self.detector.run(frame, confidence=self.model_info['confidence_threshold'])
            # Exclude the historical hardcoded task IDs. The browser assigns
            # preview gesture labels from its current ordered selection.
            detections = [{k: row[k] for k in ('class_name', 'confidence', 'bbox_xyxy_raw', 'trained')}
                          for row in detections]
            ok, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
            if not ok:
                raise VisionError(500, '识别图像输出失败。')
            self.last_error = None
            return {'schema': 'zhixing.console.vision.v1', 'frame_id': frame_id, 'source': source,
                    'frame_sha256': pixel_hash, 'input_file_sha256': hashlib.sha256(raw).hexdigest(),
                    'image_size_wh': [width, height], 'detections': detections,
                    'image': 'data:image/jpeg;base64,' + base64.b64encode(jpeg).decode(),
                    'backend': meta['backend'], 'model': self.model_info,
                    'sample_captured_utc': sample_row['received_utc'] if sample_row else None,
                    'total_ms': round((time.perf_counter() - started) * 1000, 1),
                    'metric_coordinates_enabled': False, 'physical_execution': False,
                    'path_submissions': 0, 'npu_accepted': False}
        except VisionError:
            raise
        except ImportError:
            self.last_error = 'RUNTIME_MISSING'
            raise VisionError(503, '识别依赖未就绪，请使用项目六类识别环境启动网页。') from None
        except Exception as exc:
            self.last_error = type(exc).__name__
            raise VisionError(503, '识别服务未能完成本帧，请核对模型与运行环境。') from exc
        finally:
            self.lock.release()
