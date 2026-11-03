"""Align fixed same-frame neural crop probabilities; retain the original backend and thresholds."""
import time
import numpy as np


class AlignedSurfaceEnsemble:
    policy={'method':'FIVE_FIXED_SAME_FRAME_CROP_SHIFTS_EQUAL_PROBABILITY_MEAN',
            'relative_shift':.04,'shifts_xy':[[0,0],[-1,-1],[-1,1],[1,-1],[1,1]],
            'uses_temporal_history':False,'thresholds_unchanged':True}

    def __init__(self,surface):
        if not isinstance(surface.spec,dict) or surface.spec.get('schema')!='gesture.ai_pc.surface_package.v1':
            raise ValueError('Explicit neural surface package required')
        self.surface=surface
        self.spec=surface.spec
        self.info={**surface.info,'spatial_surface_policy':self.policy}

    def run(self,frame,box):
        start=time.perf_counter_ns()
        box=np.asarray(box,float)
        if (not isinstance(frame,np.ndarray) or frame.ndim!=3 or frame.shape[2]!=3
                or frame.dtype!=np.uint8 or box.shape!=(4,) or not np.isfinite(box).all()):
            raise ValueError('BGR uint8 frame and finite raw-pixel box required')
        h,w=frame.shape[:2]
        lo=np.floor(box[:2]).astype(int);hi=np.ceil(box[2:]).astype(int)
        if np.any(lo<0) or np.any(hi>[w,h]) or np.any(hi<=lo):raise ValueError('Invalid input ROI')
        span=hi-lo
        summed=np.zeros((span[1],span[0]),np.float64)
        counts=np.zeros_like(summed)
        passes=[];seen=set()
        for shift in self.policy['shifts_xy']:
            delta=np.rint(np.asarray(shift)*span*self.policy['relative_shift']).astype(int)
            lower=np.maximum(lo+delta,0);upper=np.minimum(hi+delta,[w,h])
            # Small or edge-clipped crops can coincide. Never count identical
            # input pixels twice as if they were additional predictions.
            key=tuple(np.r_[lower,upper])
            if key in seen:continue
            seen.add(key)
            p,offset,meta=self.surface.run(frame,np.r_[lower,upper].tolist())
            if p.shape!=(upper[1]-lower[1],upper[0]-lower[0]) or list(offset)!=lower.tolist():
                raise ValueError('Surface output does not map to requested raw pixels')
            if p.ndim!=2 or not np.isfinite(p).all() or np.any(p<0) or np.any(p>1):raise ValueError('Invalid probabilities')
            begin=np.maximum(lo,lower);end=np.minimum(hi,upper)
            target=(slice(begin[1]-lo[1],end[1]-lo[1]),slice(begin[0]-lo[0],end[0]-lo[0]))
            source=(slice(begin[1]-lower[1],end[1]-lower[1]),slice(begin[0]-lower[0],end[0]-lower[0]))
            summed[target]+=p[source];counts[target]+=1
            passes.append({'roi_xyxy_raw':np.r_[lower,upper].tolist(),'total_ms':meta['total_ms']})
        if np.any(counts==0):raise ValueError('Uncovered output pixel')
        return (summed/counts).astype(np.float32),lo.tolist(),{
            'backend':self.info,'total_ms':(time.perf_counter_ns()-start)/1e6,
            'spatial_surface_policy':self.policy,'passes':passes}
