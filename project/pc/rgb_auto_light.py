"""Bounded brightness normalisation for an opt-in colour preview, not camera exposure."""
from __future__ import annotations

import math
import cv2
import numpy as np

SCHEMA = 'gesture.ai_pc.rgb_auto_light.v1'
RECIPE = {'schema': SCHEMA, 'method': 'GLOBAL_BGR_GAIN_FROM_CHROMATIC_V_P90',
          'target_v': 205, 'gain_range': [0.65, 1.4], 'time_constant_s': 0.8,
          'hardware_properties_written': False, 'white_balance_changed': False}


class AutoLight:
    def __init__(self):
        self.gain = 1.0
        self.last_ns = None
        self.frozen = False

    def process(self, frame, roi, received_ns):
        if frame.dtype != np.uint8 or frame.ndim != 3 or frame.shape[2] != 3:
            raise ValueError('Expected uint8 BGR image')
        x, y, w, h = roi
        if min(x, y) < 0 or min(w, h) < 10 or x+w > frame.shape[1] or y+h > frame.shape[0]:
            raise ValueError('ROI outside image or too small')
        if self.last_ns is not None and received_ns < self.last_ns:
            raise ValueError('Timestamps must be monotonic')
        # Analyse a small grid only; do not let a large black cloth set the target.
        hsv = cv2.cvtColor(frame[y:y+h:4, x:x+w:4], cv2.COLOR_BGR2HSV)
        sat, val = hsv[:, :, 1], hsv[:, :, 2]
        colour = (sat >= 45) & (val >= 40)
        count = int(np.count_nonzero(colour))
        enough = count >= max(24, math.ceil(colour.size * .002))
        p90 = float(np.percentile(val[colour], 90)) if enough else None
        target = float(np.clip(205 / p90, .65, 1.4)) if enough else 1.0
        dt = min(1.0, max(0.0, (received_ns-self.last_ns)/1e9)) if self.last_ns is not None else 0
        if not self.frozen:
            self.gain += (1-math.exp(-dt/.8)) * (target-self.gain)
        self.last_ns = received_ns
        lut = np.clip(np.rint(np.arange(256, dtype=float)*self.gain), 0, 255).astype(np.uint8)
        adjusted = cv2.LUT(frame, lut)
        # Bright low-saturation pixels can be glare or simply white material.
        # This warning is a review aid, never proof of recovered/missing colour.
        highlight_fraction = float(np.mean((val >= 250) & (sat < 45)))
        near_clip_fraction = float(np.mean(val[colour] >= 250)) if enough else None
        status = 'NO_COLOUR_REFERENCE' if not enough else 'NORMALISING'
        if highlight_fraction >= .005 or (near_clip_fraction is not None and near_clip_fraction >= .05):
            status = 'CHECK_RAW_HIGHLIGHTS'
        metrics = {'schema': SCHEMA, 'roi_xywh': list(roi), 'gain': float(self.gain),
                   'target_gain': target, 'raw_chromatic_v_p90': p90,
                   'chromatic_grid_samples': count, 'highlight_fraction_roi': highlight_fraction,
                   'near_clip_fraction_chromatic': near_clip_fraction,
                   'status': status, 'frozen': self.frozen,
                   'received_monotonic_ns': received_ns,
                   'hardware_exposure_changed': False, 'colour_recovery_claimed': False}
        return adjusted, metrics


def save_pair(directory, frame_index, raw, adjusted, metrics, received_ns, log):
    """Save exact unannotated input/output plus hashes and processing provenance."""
    import hashlib
    import json
    from pathlib import Path
    directory = Path(directory)
    stem = f'frame_{frame_index:06d}'
    paths = [directory/(stem+'.png'), directory/(stem+'_adjusted.png'),
             directory/(stem+'_light.json')]
    if any(path.exists() for path in paths):
        raise FileExistsError('Snapshot already exists; refusing overwrite')
    records = []
    for path, image, kind in zip(paths[:2], (raw, adjusted), ('RAW_CAMERA_BGR', 'SOFTWARE_ADJUSTED_BGR')):
        ok, encoded = cv2.imencode('.png', image)
        if not ok:
            raise RuntimeError('PNG encoding failed')
        data = encoded.tobytes()
        with path.open('xb') as stream:
            stream.write(data)
        records.append({'file': path.name, 'sha256': hashlib.sha256(data).hexdigest(),
                        'image_kind': kind, 'size_wh': [image.shape[1], image.shape[0]]})
    record = {'schema': SCHEMA, 'frame_index': frame_index,
              'received_monotonic_ns': received_ns, 'recipe': RECIPE,
              'metrics': metrics, 'images': records,
              'physical_execution': False, 'hardware_settings_written': False}
    with paths[2].open('x', encoding='utf-8') as stream:
        json.dump(record, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
    log.emit('rgb_auto_light_snapshot', **record)
    return paths[0], paths[1]
