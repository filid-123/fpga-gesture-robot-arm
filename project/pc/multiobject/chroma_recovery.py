"""RETIRED EXPERIMENT: do not use in acquisition, inference or training.

Live frames showed background hue contamination and wrong cube classes. This
module is retained only to reproduce historical failed results. Unit tests of
its pixel operations do not establish colour accuracy.

Historical description: neural-input normalization for bright, low-chroma cube tops.

The detector remains the source of object regions and final class decisions.
This pass only uses saturated pixels already inside neural detector boxes to
restore a representative chroma on clipped-looking top pixels before a second
neural inference. It never emits a class or a grasp candidate by itself.
"""
from __future__ import annotations

import cv2
import numpy as np

SCHEMA = "gesture.ai_pc.neural_chroma_recovery.v1"
RECIPE = {"schema": SCHEMA, "method": "NEURAL_BOX_OBSERVED_CHROMA_SECOND_NEURAL_PASS",
          "saturation_min": 80, "value_min": 60, "minimum_support_pixels": 100,
          "minimum_hue_concentration": .60, "hue_radius_opencv": 6,
          "minimum_neutral_fraction": .20, "reconstructed_saturation": 180,
          "hardware_settings_written": False, "lost_colour_recovered": False}


def _dominant_hue(hue, saturation, value):
    mask = (saturation >= 80) & (value >= 60)
    if int(np.count_nonzero(mask)) < 100:
        return None, 0, 0.
    hist = np.bincount(hue[mask].astype(np.uint8), minlength=180).astype(np.float64)
    # Circular smoothing makes red's 179/0 split a single mode.
    smooth = sum(np.roll(hist, k) for k in range(-6, 7))
    dominant = int(np.argmax(smooth))
    concentration = float(smooth[dominant] / hist.sum())
    if concentration < .60:
        return None, int(mask.sum()), concentration
    distance = np.abs(hue.astype(int) - dominant)
    support = mask & (np.minimum(distance, 180-distance) <= 6)
    # Use the circular mean of the supported pixels, including red across 179/0.
    angles = hue[support].astype(float) * (2*np.pi/180)
    dominant = int(np.rint(np.arctan2(np.sin(angles).mean(),
                                     np.cos(angles).mean()) * 180/(2*np.pi))) % 180
    return dominant, int(mask.sum()), concentration


def recover_highlight_chroma(frame, detections, *, min_neutral_fraction=.20):
    """Return a neural-friendly frame and an auditable recovery record.

    Only candidate cube boxes from the detector are edited. Low-saturation
    bright pixels are assigned the dominant hue observed on the candidate's
    saturated perimeter; the second detector pass still decides the class.
    """
    if frame.dtype != np.uint8 or frame.ndim != 3 or frame.shape[2] != 3:
        raise ValueError("Expected uint8 BGR frame")
    output = frame.copy()
    records, skipped = [], []
    for index, detection in enumerate(detections):
        if (detection.get("class_id") not in (0, 1, 2) or
                detection.get("model_role") != "cube_detector"):
            continue
        box = np.asarray(detection.get("bbox_xyxy_raw", []), dtype=float)
        if box.shape != (4,) or not np.isfinite(box).all():
            continue
        if np.any(box[2:] <= box[:2]):
            continue
        x1, y1, x2, y2 = np.rint(box).astype(int).tolist()
        pad = 8
        x1, y1 = max(0, x1-pad), max(0, y1-pad)
        x2, y2 = min(frame.shape[1], x2+pad), min(frame.shape[0], y2+pad)
        if x2-x1 < 20 or y2-y1 < 20:
            continue
        crop = cv2.cvtColor(frame[y1:y2, x1:x2], cv2.COLOR_BGR2HSV)
        hue, sat, val = crop[:, :, 0], crop[:, :, 1], crop[:, :, 2]
        neutral = (sat < 100) & (val > 100)
        neutral_fraction = float(np.mean(neutral))
        if neutral_fraction < min_neutral_fraction:
            continue
        dominant, saturated_count, concentration = _dominant_hue(hue, sat, val)
        if dominant is None:
            skipped.append({"detection_index": index, "reason": "INSUFFICIENT_OR_MIXED_OBSERVED_CHROMA",
                            "saturated_pixels": saturated_count, "hue_concentration": concentration})
            continue
        target = neutral
        edited = crop.copy()
        edited[:, :, 0][target] = dominant
        edited[:, :, 1][target] = 180
        # Preserve every unedited BGR pixel exactly, including saturated sides.
        patch = output[y1:y2, x1:x2]
        patch[target] = cv2.cvtColor(edited, cv2.COLOR_HSV2BGR)[target]
        records.append({
            "detection_index": index,
            "proposal_bbox_xyxy_raw": box.tolist(),
            "bbox_xyxy_raw": [int(x1), int(y1), int(x2), int(y2)],
            "dominant_hue": dominant,
            "mode": "OBSERVED_SIDE_CHROMA",
            "saturated_pixels": saturated_count,
            "hue_concentration": concentration,
            "neutral_fraction": neutral_fraction,
            "edited_pixels": int(np.count_nonzero(target)),
        })
    return output, {"schema": SCHEMA, "recipe": RECIPE, "applied": bool(records), "regions": records,
                    "skipped": skipped,
                    "final_class_source": "SECOND_NEURAL_DETECTOR_PASS",
                    "color_class_fallback": False}
