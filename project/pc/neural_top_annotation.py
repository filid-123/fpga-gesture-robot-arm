"""Independent manual top-label validation; no model/HSV-assisted labels."""
import cv2
import numpy as np


def make_top_mask(size_wh, objects):
    width,height=size_wh
    if min(width,height)<=0:
        raise ValueError('Invalid annotation dimensions')
    mask=np.zeros((height,width),np.uint8)
    seen=set()
    for obj in objects:
        oid=obj['object_id']
        if type(oid) is not int or oid not in (1,2,3) or oid in seen:
            raise ValueError('Require unique registered IDs 1/2/3')
        seen.add(oid)
        poly=np.asarray(obj['polygon_raw'],np.float32)
        if (poly.shape!=(4,2) or not np.isfinite(poly).all() or (poly<0).any() or
                (poly[:,0]>=width).any() or (poly[:,1]>=height).any() or
                not cv2.isContourConvex(poly) or abs(cv2.contourArea(poly))<25):
            raise ValueError('Require four bounded convex top corners in perimeter order')
        region=np.zeros_like(mask)
        cv2.fillConvexPoly(region,np.rint(poly).astype(np.int32),1)
        if np.any((region>0)&(mask>0)):
            raise ValueError('Top annotations overlap')
        mask[region>0]=oid
    return mask
