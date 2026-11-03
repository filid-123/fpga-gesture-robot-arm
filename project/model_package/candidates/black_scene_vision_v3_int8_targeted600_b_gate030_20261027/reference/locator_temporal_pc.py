"""Optional timestamp-based PC geometry filter; confidence gating is unchanged."""
from __future__ import annotations
from dataclasses import asdict, dataclass
import math

import numpy as np


@dataclass(frozen=True)
class StabilizerConfig:
    version: str = 'black_scene_geometry_stabilizer_v1'
    ema_tau_seconds: float = .06
    fast_tau_seconds: float = .025
    jump_fraction_of_diagonal: float = .20
    agreement_fraction_of_diagonal: float = .10
    max_pending_seconds: float = .20
    lost_display_hold_seconds: float = .20
    reset_gap_seconds: float = .25


CONFIG=StabilizerConfig()


def config_dict():return asdict(CONFIG)


def center_size(box):
    x1,y1,x2,y2=box
    return np.array([(x1+x2)/2,(y1+y2)/2,x2-x1,y2-y1],dtype=np.float64)


class GeometryStabilizer:
    """EMA for small changes, two consistent observations for isolated jumps.

    Lost detections can retain only the display box for up to .2s; they remain
    rejected and must never produce a classifier input or gesture result.
    """
    def __init__(self):self.reset()

    def reset(self):
        self.state=None;self.last_time=None;self.last_accepted=None
        self.shape=None;self.pending=None;self.pending_time=None;self.pending_since=None

    def _box(self,width,height):
        cx,cy,w,h=self.state
        return [float(np.clip(cx-w/2,0,width)),float(np.clip(cy-h/2,0,height)),
                float(np.clip(cx+w/2,0,width)),float(np.clip(cy+h/2,0,height))]

    def update(self,box,detected,width,height,timestamp):
        raw=np.asarray(box,dtype=float)
        result={'version':CONFIG.version,'effective_box':list(box),'state':'raw',
                'accepted':bool(detected),'classifier_allowed':bool(detected),'display_hold':False}
        if raw.shape!=(4,) or not np.isfinite(raw).all() or raw[2]<=raw[0] or raw[3]<=raw[1]:
            self.reset();return {**result,'state':'invalid_reset','classifier_allowed':False}
        if (self.shape!=(height,width) or (self.last_time is not None and
                (timestamp<=self.last_time or timestamp-self.last_time>CONFIG.reset_gap_seconds))):self.reset()
        dt=0. if self.last_time is None else timestamp-self.last_time
        self.shape=(height,width);self.last_time=timestamp
        if not detected:
            self.pending=None;self.pending_time=None;self.pending_since=None
            if self.state is not None and self.last_accepted is not None and timestamp-self.last_accepted<=CONFIG.lost_display_hold_seconds:
                return {**result,'effective_box':self._box(width,height),'state':'loss_display_hold',
                        'display_hold':True,'classifier_allowed':False}
            self.state=None;self.last_accepted=None
            return {**result,'state':'loss_reset','classifier_allowed':False}
        observation=center_size(raw)
        if self.state is None:
            self.state=observation;state='initialized'
        else:
            normalizer=max(32.,float(np.hypot(self.state[2],self.state[3])))
            change=float(np.max(np.abs(observation-self.state)))/normalizer
            tau=CONFIG.ema_tau_seconds
            if change>CONFIG.jump_fraction_of_diagonal:
                agrees=(self.pending is not None and timestamp-self.pending_time<=CONFIG.max_pending_seconds
                        and float(np.max(np.abs(observation-self.pending)))/normalizer<=CONFIG.agreement_fraction_of_diagonal)
                if not agrees:
                    if self.pending_since is None:self.pending_since=timestamp
                    if timestamp-self.pending_since+dt < CONFIG.max_pending_seconds:
                        self.pending=observation.copy();self.pending_time=timestamp
                        self.last_accepted=timestamp
                        return {**result,'effective_box':self._box(width,height),'state':'jump_pending'}
                    state='jump_timeout_follow'
                else:state='confirmed_jump'
                tau=CONFIG.fast_tau_seconds
            else:state='ema'
            self.pending=None;self.pending_time=None;self.pending_since=None
            alpha=1.-math.exp(-max(dt,1e-6)/tau)
            self.state=(1.-alpha)*self.state+alpha*observation
        self.last_accepted=timestamp
        return {**result,'effective_box':self._box(width,height),'state':state}
