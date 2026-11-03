"""Keep the full scene and recover small objects from overlapping square views."""
import math
import time
import numpy as np

from pc.multiobject.yolo import iou


def square_views(width, height, overlap=.25):
    if min(width, height) <= 0 or not 0 <= overlap < 1:
        raise ValueError('Positive image dimensions and bounded overlap required')
    side = min(width, height)
    longest = max(width, height)
    if width == height:
        return []  # The full frame already supplies this view.
    count = math.ceil((longest-side)/(side*(1-overlap)))+1
    if count > 16:
        raise ValueError('Image aspect ratio exceeds bounded tiled inference')
    origins = np.rint(np.linspace(0, longest-side, count)).astype(int)
    return [[int(x), 0, side, side] if width > height else [0, int(x), side, side]
            for x in origins]


class TiledDetector:
    """Reuse one model/backend, preserve raw-image boxes, and merge class-wise.

    Tiles use the detector's existing ROI coordinate mapping. An object cut by
    an internal tile edge cannot replace its full-view detection. Cross-class
    conflicts remain visible to the existing ambiguity checks.
    """
    policy = {'method':'FULL_FRAME_PLUS_OVERLAPPING_SQUARES_V1',
              'minimum_tile_overlap':.25, 'classwise_merge_iou':.5,
              'interior_edge_margin_raw_px':2, 'max_tiles':16,
              'thresholds_unchanged':True}

    def __init__(self, detector):
        if detector.spec.get('role') != 'mode_b_detector':
            raise ValueError('Explicit six-class mode B detector required')
        self.detector = detector
        self.spec = detector.spec
        self.info = {**detector.info, 'spatial_inference_policy':dict(self.policy)}

    def run(self, frame, roi=None, confidence=.4):
        if roi is not None:
            raise ValueError('Tiled detector operates on a complete raw frame')
        if (not isinstance(frame,np.ndarray) or frame.ndim!=3 or frame.shape[2]!=3
                or frame.dtype!=np.uint8):
            raise ValueError('BGR uint8 frame required')
        h,w = frame.shape[:2]
        views = [None]+square_views(w,h)
        start=time.perf_counter_ns()
        candidates, passes, rejected = [], [], []
        for index, view in enumerate(views):
            found, meta = self.detector.run(frame,view,confidence=confidence)
            passes.append({'roi_xywh_raw':view, 'timing_ms':meta.get('timing_ms',{})})
            for item in found:
                box=item['bbox_xyxy_raw']
                if view is not None:
                    x,y,side,_=view
                    # Raw-frame edges may contain legitimately truncated objects;
                    # only artificial tile boundaries trigger this exclusion.
                    if ((x>0 and box[0]<=x+2) or (y>0 and box[1]<=y+2)
                            or (x+side<w and box[2]>=x+side-2)
                            or (y+side<h and box[3]>=y+side-2)):
                        rejected.append({'class_name':item['class_name'],'pass_index':index,
                                         'bbox_xyxy_raw':box,'reason':'INTERNAL_TILE_EDGE'})
                        continue
                candidates.append({**item,'detector_pass_index':index,
                                   'detector_roi_xywh_raw':view})
        merged=[]
        for item in sorted(candidates,key=lambda d:-d['confidence']):
            if not any(other['class_id']==item['class_id'] and
                       iou(other['bbox_xyxy_raw'],item['bbox_xyxy_raw'])>.5 for other in merged):
                merged.append(item)
            if len(merged)>=100:
                break
        timing={key:sum(p['timing_ms'].get(key,0) for p in passes)
                for key in ('preprocess','model','decode_nms')}
        timing['total_spatial_inference']=(time.perf_counter_ns()-start)/1e6
        backend={**self.info,'spatial_pass_count':len(passes),
                 'spatial_views':passes,'internal_edge_rejections':rejected}
        return merged,{'backend':backend,'timing_ms':timing}

    def close(self):
        return self.detector.close()
