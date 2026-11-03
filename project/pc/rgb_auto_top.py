"""Heuristic cube-top quadrilaterals for fixed-camera RGB review, never execution."""
from __future__ import annotations

import math
import cv2
import numpy as np


def _fit_quad(contour, area, mask, offset, geometry, height, side, minimum_support):
    perimeter = cv2.arcLength(contour, True)
    for epsilon in (.015, .025, .035):
        poly = cv2.approxPolyDP(contour, epsilon*perimeter, True)
        if len(poly) != 4 or not cv2.isContourConvex(poly):
            continue
        quad = poly.reshape(4, 2).astype(float) + np.array(offset)
        centre = quad.mean(axis=0)
        quad = quad[np.argsort(np.arctan2(quad[:, 1]-centre[1], quad[:, 0]-centre[0]))]
        polygon_area = abs(cv2.contourArea(quad.astype(np.float32)))
        agreement = min(area, polygon_area)/max(area, polygon_area)
        if agreement < .88:
            continue
        polygon_mask = np.zeros_like(mask)
        cv2.fillConvexPoly(polygon_mask, np.rint(quad-np.array(offset)).astype(np.int32), 255)
        union = np.count_nonzero(mask | polygon_mask)
        support = np.count_nonzero(mask & polygon_mask)/union if union else 0
        if support < minimum_support:
            continue
        try:
            corners = np.array([geometry.project(uv, height) for uv in quad])
        except ValueError:
            continue
        edges = np.roll(corners[:, :2], -1, axis=0)-corners[:, :2]
        lengths = np.linalg.norm(edges, axis=1)
        if not np.all((lengths >= .75*side) & (lengths <= 1.25*side)):
            continue
        angles = []
        for i in range(4):
            cosine = np.dot(-edges[i-1], edges[i])/(lengths[i-1]*lengths[i])
            angles.append(float(np.degrees(np.arccos(np.clip(cosine, -1, 1)))))
        if any(abs(angle-90) > 20 for angle in angles):
            continue
        # Intersection of diagonals preserves the centre under perspective.
        matrix = np.column_stack((quad[2]-quad[0], -(quad[3]-quad[1])))
        if abs(np.linalg.det(matrix)) < 1e-8:
            continue
        t, _ = np.linalg.solve(matrix, quad[1]-quad[0])
        uv = quad[0]+t*(quad[2]-quad[0])
        xyz = geometry.project(uv, height)
        yaw = math.degrees(math.atan2(edges[0, 1], edges[0, 0])) % 90
        return {'pixel_uv':uv.tolist(), 'table_xyz_mm':xyz, 'quad_pixel_uv':quad.tolist(),
                'quad_table_xyz_mm':corners.tolist(), 'edge_lengths_mm':lengths.tolist(),
                'corner_angles_deg':angles, 'contour_polygon_area_agreement':agreement,
                'mask_polygon_iou':float(support),
                'table_yaw_mod90_deg':yaw, 'square_symmetry_period_deg':90,
                'contour_area_px':area}
    return None


def _quad(mask, offset, geometry, height, side):
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    contour = max(contours, key=cv2.contourArea)
    area = cv2.contourArea(contour)
    if area < 25:
        return None
    fit = _fit_quad(contour, area, mask, offset, geometry, height, side, .88)
    if fit is not None:
        fit.update(quadrilateral_fit_method='DIRECT_CONTOUR', contour_repaired=False)
        return fit
    # Repair only a nearly filled convex outline. A hull alone is not evidence.
    hull = cv2.convexHull(contour)
    hull_area = cv2.contourArea(hull)
    if hull_area <= 0 or area/hull_area < .94:
        return None
    hull_mask = np.zeros_like(mask)
    cv2.fillConvexPoly(hull_mask, hull, 255)
    hull_pixels = np.count_nonzero(hull_mask)
    coverage = np.count_nonzero(mask & hull_mask)/hull_pixels if hull_pixels else 0
    if coverage < .94:
        return None
    # Hull coverage gates missing pixels separately; polygon approximation also
    # introduces corner rounding, so its IoU tolerance is slightly wider.
    fit = _fit_quad(hull, area, mask, offset, geometry, height, side, .90)
    if fit is not None:
        fit.update(quadrilateral_fit_method='SUPPORTED_CONVEX_HULL_REPAIR', contour_repaired=True,
                   hull_missing_area_fraction=float(1-area/hull_area),
                   hull_missing_pixel_fraction=float(1-coverage))
    return fit


def estimate_top(frame, profile, detection, geometry, top_height_mm=30, cube_side_mm=30):
    """Return a fresh candidate for this frame; ambiguous colour/shape is unresolved."""
    result = {'status':'WAITING_STABLE', 'pixel_uv':None, 'table_xyz_mm':None,
              'object_id':detection['object_id'], 'assumed_top_height_mm':float(top_height_mm),
              'expected_cube_side_mm':float(cube_side_mm), 'depth_measured':False,
              'physical_execution':False, 'robot_base_xyz_mm':None,
              'top_centre_automatically_validated':False, 'requires_manual_review':True,
              'coordinate_system':geometry.table['table_frame_id']}
    if detection['status'] != 'FOUND' or not detection['stable']:
        result['reason'] = detection['status'] if detection['status'] != 'FOUND' else 'POSITION_NOT_STABLE'
        return result
    obj = next(o for o in profile['objects'] if o['object_id']==detection['object_id'])
    if obj['mode'] != 'chromatic':
        result.update(status='TOP_UNRESOLVED', reason='CHROMATIC_CUBE_REQUIRED')
        return result
    x,y,w,h = detection['candidates'][0]['bbox_xywh']
    hsv = cv2.cvtColor(frame[y:y+h, x:x+w], cv2.COLOR_BGR2HSV)
    mask = np.zeros((h,w),np.uint8)
    for lo,hi in obj['hsv_ranges']:
        mask |= cv2.inRange(hsv,np.array(lo,np.uint8),np.array(hi,np.uint8))
    mask = cv2.morphologyEx(mask,cv2.MORPH_OPEN,np.ones((3,3),np.uint8))
    count,labels,stats,_ = cv2.connectedComponentsWithStats(mask,connectivity=8)
    if count <= 1:
        result.update(status='TOP_UNRESOLVED',reason='EMPTY_COMPONENT')
        return result
    label = 1+np.argmax(stats[1:,cv2.CC_STAT_AREA])
    mask = np.where(labels==label,255,0).astype(np.uint8)
    values = hsv[:,:,2][mask>0]
    fit = None
    method = 'COLOUR_QUADRILATERAL_TOP_APPROXIMATION'
    # Otsu on object pixels only: background and the white box cannot set this threshold.
    threshold,_ = cv2.threshold(values.reshape(-1,1),0,255,cv2.THRESH_BINARY|cv2.THRESH_OTSU)
    bright_fraction = float(np.mean(values>threshold))
    if .55 <= bright_fraction <= .95:
        low,high = values[values<=threshold],values[values>threshold]
        contrast = float(np.mean(high)-np.mean(low))
        if contrast >= 25:
            bright = np.where((mask>0)&(hsv[:,:,2]>threshold),255,0).astype(np.uint8)
            bright = cv2.morphologyEx(bright,cv2.MORPH_CLOSE,np.ones((3,3),np.uint8))
            bright &= mask
            fit = _quad(bright,[x,y],geometry,top_height_mm,cube_side_mm)
            if fit is not None and fit['contour_area_px'] < .55*np.count_nonzero(mask):
                fit = None
            if fit is not None:
                method = 'BRIGHT_REGION_QUADRILATERAL_TOP_HEURISTIC'
    if fit is None:
        fit = _quad(mask,[x,y],geometry,top_height_mm,cube_side_mm)
    if fit is None:
        result.update(status='TOP_UNRESOLVED', reason='NO_SQUARE_QUADRILATERAL_AT_EXPECTED_SIZE')
        return result
    point = geometry.manual_top(fit['pixel_uv'],top_height_mm)
    result.update(fit, status='AUTO_TOP_CANDIDATE' if point['inside_intrinsics_observed_corner_bounds'] else 'AUTO_TOP_EXTRAPOLATED',
                  method=method, inside_intrinsics_observed_corner_bounds=point['inside_intrinsics_observed_corner_bounds'],
                  height_source='USER_REPORTED_CUBE_HEIGHT',
                  independent_metric_validation='NOT_ACCEPTED',
                  limitation='Heuristic may include painted side faces or occluders. Square and size checks do not prove a top surface or a clear workspace.')
    return result
