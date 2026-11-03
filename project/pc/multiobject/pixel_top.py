"""Fit a neural top mask in raw pixels, without assuming a valid table calibration."""
import cv2
import numpy as np


def fit_pixel_quad(mask, offset, detector_box):
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if len(contours) != 1:
        return None
    contour = contours[0]
    area = cv2.contourArea(contour)
    if area < 100:
        return None
    # An incomplete mask at the crop edge is not a supported top estimate.
    x, y, w, h = cv2.boundingRect(contour)
    if x <= 1 or y <= 1 or x+w >= mask.shape[1]-1 or y+h >= mask.shape[0]-1:
        return None
    perimeter = cv2.arcLength(contour, True)
    for epsilon in (.01, .015, .02, .025, .03, .04):
        polygon = cv2.approxPolyDP(contour, epsilon*perimeter, True)
        if len(polygon) != 4 or not cv2.isContourConvex(polygon):
            continue
        fitted = np.zeros_like(mask)
        cv2.fillConvexPoly(fitted, polygon, 255)
        agreement = np.count_nonzero((fitted > 0) & (mask > 0))/np.count_nonzero((fitted > 0) | (mask > 0))
        if agreement < .85:
            continue
        quad = polygon.reshape(4,2).astype(float)+offset
        points = np.column_stack((quad, np.ones(4)))
        centre = np.cross(np.cross(points[0], points[2]), np.cross(points[1], points[3]))
        if abs(centre[2]) < 1e-8:
            continue
        centre = centre[:2]/centre[2]
        box = np.asarray(detector_box)
        if np.any(centre < box[:2]) or np.any(centre > box[2:]):
            continue
        return {'quad_pixel_uv': quad.tolist(), 'pixel_uv': centre.tolist(),
                'mask_quad_iou': float(agreement), 'units': 'raw_pixels',
                'method': 'NEURAL_TOP_MASK_QUADRILATERAL_DIAGONALS',
                'metric_localization_verified': False, 'physical_execution': False}
    return None
