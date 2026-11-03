from pathlib import Path
import cv2 as cv
import numpy as np

def read_bgr_image(path):
    image=cv.imdecode(np.fromfile(Path(path),np.uint8),cv.IMREAD_COLOR)
    if image is None:raise ValueError('Cannot decode image')
    return image

def preprocess_bgr_to_locator_input(frame):
    if frame.dtype!=np.uint8 or frame.shape!=(480,640,3):raise ValueError('Actual640x480BGRrequired;no resize')
    gray=cv.cvtColor(frame,cv.COLOR_BGR2GRAY)
    small=np.zeros((128,128),np.uint8)
    small[16:112]=gray[0:480:5,0:640:5]
    return small

def small_roi_descriptor(roi):
    if len(roi)!=4 or any(not isinstance(v,(int,np.integer)) for v in roi):raise ValueError('ROI edges must be integers')
    x0,y0,x1,y1=map(int,roi);side=x1-x0
    if not(0<=x0<x1<=640 and 0<=y0<y1<=480 and y1-y0==side):raise ValueError('Illegal squareROI')
    sx,sy,ss=x0//5,16+y0//5,(side+4)//5
    if not(0<=sx and 16<=sy and sx+ss<=128 and sy+ss<=112):raise ValueError('Illegal smallROI')
    return {'sx':sx,'sy':sy,'ss':ss}

def classifier_from_small(small,roi):
    if small.dtype!=np.uint8 or small.shape!=(128,128):raise ValueError('Expected small128')
    d=small_roi_descriptor(roi);idx=np.arange(32,dtype=np.int64)*d['ss']//32
    return small[d['sy']+idx[:,None],d['sx']+idx[None,:]]

def classifier_input(frame,roi):return classifier_from_small(preprocess_bgr_to_locator_input(frame),roi)

def clipped_int_box(box: tuple[float, float, float, float], width: int, height: int) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = box
    left = int(np.clip(round(x1), 0, max(0, width - 1)))
    top = int(np.clip(round(y1), 0, max(0, height - 1)))
    right = int(np.clip(round(x2), left + 1, width))
    bottom = int(np.clip(round(y2), top + 1, height))
    return left, top, right, bottom

def square_roi_from_source_box(
    box: tuple[int, int, int, int], width: int, height: int, margin: float
) -> tuple[int, int, int, int]:
    """Build the square ROI used by the classifier training pipeline."""
    if not 0.0 <= margin <= 0.5:
        raise ValueError("margin must be in [0, 0.5]")
    x1, y1, x2, y2 = box
    box_width = max(1, x2 - x1)
    box_height = max(1, y2 - y1)
    side = max(box_width, box_height) * (1.0 + 2.0 * margin)
    side_i = max(1, min(width, height, int(round(side))))
    center_x = (x1 + x2) / 2.0
    center_y = (y1 + y2) / 2.0
    left = int(round(center_x - side_i / 2.0))
    top = int(round(center_y - side_i / 2.0))
    left = min(max(0, left), width - side_i)
    top = min(max(0, top), height - side_i)
    return left, top, left + side_i, top + side_i
