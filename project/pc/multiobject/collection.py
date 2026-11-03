"""Raw-image collection with fixed session split; scene intent is not a label."""
from datetime import datetime, timezone
from pathlib import Path
import json
import re
import cv2
import numpy as np
from pc.multiobject.dataset import write_image
from pc.multiobject.yolo import digest, image_digest


class CaptureSession:
    def __init__(self, out, session_id, split, scene, lighting, size_wh, roi,
                 calibration, source_kind='LIVE_CAMERA', min_change=.01):
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}', session_id):
            raise ValueError('Session ID must use 1-64 ASCII letters, digits, hyphen or underscore')
        if split not in ('train', 'validation', 'test') or scene not in ('red', 'yellow', 'blue', 'mixed', 'empty', 'distractors'):
            raise ValueError('Explicit session split and scene required')
        if source_kind not in ('LIVE_CAMERA', 'OFFLINE_REPLAY') or not str(lighting).strip():
            raise ValueError('Source kind and lighting required')
        if not 0 <= min_change <= .2:
            raise ValueError('Invalid near-duplicate threshold')
        w, h = size_wh
        x, y, rw, rh = roi
        if (any(type(v) is not int for v in [w, h, x, y, rw, rh]) or
                min(w, h, rw, rh) <= 0 or min(x, y) < 0 or x+rw > w or y+rh > h):
            raise ValueError('Invalid calibrated image size/ROI')
        self.out = Path(out)
        self.out.mkdir(parents=True, exist_ok=False)
        self.roi, self.min_change = list(roi), min_change
        self.fingerprints, self.hashes = [], set()
        self.record = {'schema': 'gesture.ai_pc.multiobject_capture_session.v1',
            'session_id': session_id, 'split': split, 'scene_intent': scene,
            'lighting_description': lighting, 'source_kind': source_kind,
            'image_size_wh': list(size_wh), 'roi_xywh_raw': list(roi),
            'calibration': calibration, 'min_roi_mean_change_0_1': min_change,
            'created_utc': datetime.now(timezone.utc).isoformat(), 'items': [],
            'status': 'COLLECTING', 'labels_generated': False,
            'annotation_status': 'UNANNOTATED', 'physical_execution': False,
            'timestamp_basis': 'HOST_READ_COMPLETE_NOT_SENSOR_EXPOSURE'}
        self._commit()

    def _commit(self):
        temporary = self.out/'session.json.tmp'
        temporary.write_text(json.dumps(self.record, indent=2)+'\n', encoding='utf8')
        temporary.replace(self.out/'session.json')

    def save(self, frame, received_ns, source_file=None):
        if self.record['status'] != 'COLLECTING': raise ValueError('Session already closed')
        if (not isinstance(frame, np.ndarray) or frame.dtype != np.uint8 or
                frame.shape != (self.record['image_size_wh'][1], self.record['image_size_wh'][0], 3)):
            raise ValueError('Frame must match calibrated BGR uint8 dimensions')
        if type(received_ns) is not int or received_ns < 0: raise ValueError('Host timestamp required')
        sha = image_digest(frame)
        if sha in self.hashes: return {'saved': False, 'reason': 'EXACT_DUPLICATE'}
        x, y, w, h = self.roi; roi = frame[y:y+h, x:x+w]
        fp = cv2.resize(roi, (96, 64), interpolation=cv2.INTER_AREA).astype(np.float32)/255
        change = min((float(np.mean(np.abs(fp-old))) for old in self.fingerprints), default=None)
        if change is not None and change < self.min_change:
            return {'saved': False, 'reason': 'NEAR_DUPLICATE_ROI', 'roi_change_0_1': change}
        index = len(self.record['items'])
        filename = f'frame_{index:06d}.png'
        write_image(self.out/filename, frame)
        grey = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        row = {'image': filename, 'image_sha256': digest(self.out/filename), 'pixel_sha256': sha,
            'received_monotonic_ns': received_ns, 'source_file': str(source_file) if source_file else None,
            'roi_change_0_1': change, 'roi_quality': {
                'mean_luminance': float(grey.mean()),
                'laplacian_variance': float(cv2.Laplacian(grey, cv2.CV_64F).var()),
                'clipped_bright_channel_fraction': float(np.mean(np.max(roi, axis=2) >= 250))},
            'annotation_status': 'UNANNOTATED'}
        self.record['items'].append(row)
        self._commit()
        self.hashes.add(sha); self.fingerprints.append(fp)
        return {'saved': True, 'image': str(self.out/filename), 'count': index+1, 'quality': row['roi_quality']}

    def close(self, status='COMPLETED'):
        if status not in ('COMPLETED', 'ERROR', 'INTERRUPTED'): raise ValueError('Invalid terminal status')
        self.record['status'] = status; self._commit()


def load_session(path):
    path = Path(path).resolve()
    data = json.loads(path.read_bytes())
    if data.get('schema') != 'gesture.ai_pc.multiobject_capture_session.v1': raise ValueError('Unknown capture session')
    if data.get('split') not in ('train', 'validation', 'test'): raise ValueError('Invalid capture split')
    seen = set()
    for item in data['items']:
        file = (path.parent/item['image']).resolve()
        if not file.is_relative_to(path.parent) or digest(file) != item['image_sha256']:
            raise ValueError('Capture source path/hash mismatch')
        if item['pixel_sha256'] in seen: raise ValueError('Duplicate capture pixels')
        seen.add(item['pixel_sha256'])
    return data
