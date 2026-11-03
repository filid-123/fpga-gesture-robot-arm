"""Small DirectShow exposure probe and bounded chroma preview; neither restores lost colour."""
from __future__ import annotations

import math
import cv2
import numpy as np

SCHEMA = 'gesture.ai_pc.rgb_camera_tuning.v1'
RECIPE = {'schema': SCHEMA, 'method': 'HSV_BOUNDED_CHROMA_AND_VALUE',
          'saturation_gain_range': [1.0, 1.6], 'value_gain_range': [.8, 1.15],
          'target_s': 105, 'target_v_p90': 225, 'time_constant_s': .8,
          'colour_recovery_claimed': False}


def read_property(cap, prop):
    value = float(cap.get(prop))
    return value if math.isfinite(value) else None


def brighten(frame, gain, gamma=1.):
    """Apply a fixed equal BGR gain; keep source and spatial geometry unchanged."""
    if not math.isfinite(gain) or not .8 <= gain <= 1.6:
        raise ValueError('Brightness gain must be within [0.8, 1.6]')
    if not math.isfinite(gamma) or not .5<=gamma<=1.5:
        raise ValueError('Brightness gamma must be within [0.5, 1.5]')
    if gain == 1:
        output=frame.copy()
    else:
        lut=np.clip(np.rint(np.arange(256,dtype=np.float32)*gain),0,255).astype(np.uint8)
        output=cv2.LUT(frame,lut)
    if gamma != 1:
        # Lift dark values without deliberately changing H/S or clipping an
        # entire bright range to white. This cannot recover missing signal.
        hsv=cv2.cvtColor(output,cv2.COLOR_BGR2HSV)
        lut=np.rint(255*(np.arange(256,dtype=np.float32)/255)**gamma).astype(np.uint8)
        hsv[:,:,2]=cv2.LUT(hsv[:,:,2],lut)
        output=cv2.cvtColor(hsv,cv2.COLOR_HSV2BGR)
    return output


def processing_signature(enhanced, brightness_gain, brightness_gamma=1.):
    if not enhanced and brightness_gain == 1 and brightness_gamma == 1:
        return None
    return {'schema':SCHEMA,'method':'CAMERA_TUNING_PIPELINE',
            'colour_clarity':RECIPE.copy() if enhanced else None,
            'brightness_gain':brightness_gain,'brightness_gamma':brightness_gamma,
            'colour_recovery_claimed':False}


class ExposureProbe:
    """DSHOW exposure units are log2 seconds; only probe one stop from a plausible readback.

    Do not write unknown automatic-mode flags. A set/get match is recorded as API
    acceptance only; compare acquired frames separately. Restore on every exit.
    """
    def __init__(self, cap):
        self.cap = cap
        self.original = read_property(cap, cv2.CAP_PROP_EXPOSURE)
        self.auto_original = read_property(cap, cv2.CAP_PROP_AUTO_EXPOSURE)
        self.attempted = False
        self.record = {'schema': SCHEMA, 'original_exposure_readback': self.original,
                       'original_auto_readback_unverified': self.auto_original,
                       'automatic_mode_written': False, 'attempts': [],
                       'frame_effect_verified': False, 'restore': None}
        self.record['frame_effect_verified_scope'] = 'Exposure-only causality, not brightness response'

    def try_one_stop_lower(self):
        # -1/0 are often unsupported-property sentinels. Never invent a camera range.
        if self.original is None or not (-11 <= self.original <= -2):
            self.record['status'] = 'NO_PLAUSIBLE_EXPOSURE_READBACK'
            return False
        target = self.original - 1
        self.attempted = True
        accepted = bool(self.cap.set(cv2.CAP_PROP_EXPOSURE, target))
        readback = read_property(self.cap, cv2.CAP_PROP_EXPOSURE)
        matched = readback is not None and abs(readback-target)<.1
        self.record['attempts'].append({'target':target,'set_accepted':accepted,
                                        'readback':readback,'readback_matched':matched})
        self.record['status'] = 'API_ACCEPTED_FRAME_CHECK_PENDING' if accepted and matched else 'EXPOSURE_CONTROL_NOT_CONFIRMED'
        return accepted and matched

    def restore(self):
        if not self.attempted:
            self.record['restore'] = {'attempted':False,'reason':'No exposure write attempted'}
            return self.record['restore']
        accepted = bool(self.cap.set(cv2.CAP_PROP_EXPOSURE,self.original))
        value = read_property(self.cap,cv2.CAP_PROP_EXPOSURE)
        # Some drivers can also change mode when setting exposure. Restore a mode
        # only if the original reports exactly the DirectShow bool convention.
        mode_result = None
        if self.auto_original in (0.0,1.0):
            mode_result = {'requested':self.auto_original,
                           'accepted':bool(self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE,self.auto_original)),
                           'readback':read_property(self.cap,cv2.CAP_PROP_AUTO_EXPOSURE)}
        self.record['restore'] = {'attempted':True,'set_accepted':accepted,'readback':value,
            'exposure_value_matched':value is not None and abs(value-self.original)<.1,
            'auto_mode_restore':mode_result,
            'auto_mode_restore_unverified':mode_result is None or not mode_result['accepted'] or mode_result['readback']!=self.auto_original}
        return self.record['restore']


def reference_mask(frame, roi):
    x,y,w,h = roi
    hsv = cv2.cvtColor(frame[y:y+h,x:x+w],cv2.COLOR_BGR2HSV)
    return (hsv[:,:,1]>=40) & (hsv[:,:,2]>=60)


def exposure_metrics(frame, roi, fixed_mask):
    x,y,w,h = roi
    hsv = cv2.cvtColor(frame[y:y+h,x:x+w],cv2.COLOR_BGR2HSV)
    if fixed_mask.shape != hsv.shape[:2]:
        raise ValueError('Reference mask/frame shape changed')
    enough = int(np.count_nonzero(fixed_mask)) >= 500
    values = hsv[:,:,2][fixed_mask]
    return {'reference_pixels':int(values.size),
            'v_p90':float(np.percentile(values,90)) if enough else None,
            's_median':float(np.median(hsv[:,:,1][fixed_mask])) if enough else None,
            'near_clip_fraction':float(np.mean(values>=250)) if enough else None,
            'dark_fraction':float(np.mean(values<50)) if enough else None}


def compare_exposure(before, after):
    enough = before['v_p90'] is not None and after['v_p90'] is not None
    dimmed = bool(enough and after['v_p90'] <= before['v_p90']*.95)
    retained = bool(dimmed and after['v_p90'] >= 90)
    # A fixed reference mask can include tinted black cloth. Its dark fraction
    # is diagnostic information, not a reason to reject readable foreground.
    return {'before': before, 'after': after,
            'frame_dimming_observed': dimmed,
            'candidate_retained_for_visual_review': retained,
            'dark_reference_fraction_increased': bool(enough and
                after['dark_fraction'] > before['dark_fraction']+.15),
            'colour_accuracy_improvement_verified': False,
            'exposure_only_causality_proven': False,
            'status': ('CANDIDATE_RETAINED_FOR_VISUAL_REVIEW' if retained else
                       'DIMMING_OBSERVED_BUT_REFERENCE_TOO_DARK' if dimmed else
                       'NO_DIMMING_OBSERVED' if enough else 'INSUFFICIENT_REFERENCE')}


def check_exposure_effect(before,after):
    return compare_exposure(before,after)['candidate_retained_for_visual_review']


class ColourClarity:
    def __init__(self):
        self.s_gain=1.0
        self.v_gain=1.0
        self.last_ns=None
        self.frozen=False

    def process(self,frame,roi,received_ns,enabled=True):
        if frame.dtype!=np.uint8 or frame.ndim!=3 or frame.shape[2]!=3:
            raise ValueError('Expected uint8 BGR frame')
        x,y,w,h=roi
        if min(x,y)<0 or min(w,h)<10 or x+w>frame.shape[1] or y+h>frame.shape[0]:
            raise ValueError('Invalid ROI')
        hsv = cv2.cvtColor(frame,cv2.COLOR_BGR2HSV)
        grid=hsv[y:y+h:4,x:x+w:4]
        ref=(grid[:,:,1]>=40)&(grid[:,:,2]>=60)
        enough=int(np.count_nonzero(ref))>=max(24,math.ceil(ref.size*.002))
        s_median=float(np.median(grid[:,:,1][ref])) if enough else None
        v_p90=float(np.percentile(grid[:,:,2][ref],90)) if enough else None
        s_target=float(np.clip(105/s_median,1,1.6)) if enough else 1.0
        v_target=float(np.clip(225/v_p90,.8,1.15)) if enough else 1.0
        if self.last_ns is not None and received_ns<self.last_ns:
            raise ValueError('Timestamps must be monotonic')
        dt=min(1,max(0,(received_ns-self.last_ns)/1e9)) if self.last_ns is not None else 0
        if not self.frozen:
            amount=1-math.exp(-dt/.8)
            self.s_gain+=amount*(s_target-self.s_gain)
            self.v_gain+=amount*(v_target-self.v_gain)
        self.last_ns=received_ns
        if not enabled:
            output=frame.copy()
        else:
            # Smoothly taper enhancement at low saturation: avoid colourising grey
            # noise and white objects. Hue is never deliberately changed.
            sat=hsv[:,:,1].astype(np.float32)
            weight=np.clip((sat-25)/30,0,1)
            hsv[:,:,1]=np.clip(np.rint(sat*(1+(self.s_gain-1)*weight)),0,255).astype(np.uint8)
            hsv[:,:,2]=np.clip(np.rint(hsv[:,:,2].astype(np.float32)*self.v_gain),0,255).astype(np.uint8)
            output=cv2.cvtColor(hsv,cv2.COLOR_HSV2BGR)
        return output,{'schema':SCHEMA,'recipe':RECIPE,'roi_xywh':list(roi),
            'enabled':enabled,'s_gain':float(self.s_gain),'v_gain':float(self.v_gain),
            'raw_reference_s_median':s_median,'raw_reference_v_p90':v_p90,
            'status':'COLOUR_PREVIEW' if enough else 'NO_COLOUR_REFERENCE',
            'frozen':self.frozen,'received_monotonic_ns':received_ns,
            'colour_recovery_claimed':False,'metric_colour_accuracy_claimed':False}
