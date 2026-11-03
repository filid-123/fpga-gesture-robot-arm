"""Pure offline FK/IK for the saved RoArm reference geometry.

This is NOT an IKSolver implementation and cannot authorize physical execution.
Only the firmware mathematical endpoint is used, never the arbitrary marker P.
"""
from __future__ import annotations
import math
from dataclasses import dataclass

class ReferenceIKError(ValueError):
    pass

def finite(values):
    try:
        if not all(math.isfinite(v) for v in values):
            raise ReferenceIKError('NONFINITE_INPUT')
    except TypeError as exc:
        raise ReferenceIKError('INVALID_NUMERIC_INPUT') from exc

@dataclass(frozen=True)
class ReferenceGeometry:
    l2a: float
    l2b: float
    l3a: float
    l3b: float
    l4a: float
    l4b: float

    def __post_init__(self):
        finite((self.l2a, self.l2b, self.l3a, self.l3b, self.l4a, self.l4b))
        if min(self.l2a, self.l3a, self.l4a) <= 0:
            raise ReferenceIKError('NONPOSITIVE_LINK_LENGTH')

    @property
    def lengths(self):
        return (math.hypot(self.l2a, self.l2b), math.hypot(self.l3a, self.l3b),
                math.hypot(self.l4a, self.l4b))

    @property
    def offsets(self):
        return (math.atan2(self.l2b, self.l2a), math.atan2(self.l3b, self.l3a),
                math.atan2(self.l4b, self.l4a))

def forward(q, geometry):
    """Return reference endpoint x/y/z (mm) and firmware tit (radians)."""
    if len(q) != 4:
        raise ReferenceIKError('EXPECT_B_S_E_T')
    finite(q)
    b, s, e, t = q
    l2, l3, l4 = geometry.lengths
    d2, d3, d4 = geometry.offsets
    angles = (math.pi / 2 - s - d2, math.pi / 2 - s - e - d3,
              math.pi / 2 - s - e - t - d4)
    radial = sum(length * math.cos(a) for length, a in zip((l2, l3, l4), angles))
    z = sum(length * math.sin(a) for length, a in zip((l2, l3, l4), angles))
    return (radial * math.cos(b), radial * math.sin(b), z, s + e + t - math.pi / 2)

def inverse_endpoint(xyz, pitch, geometry, reference_limits):
    """Solve the forward-radial branch; report both elbow branches without clamping.

    pitch is the model's firmware tit, not an independently established jaw angle.
    Limits are reference-source clamps only; physical reachability is not asserted.
    """
    if len(xyz) != 3:
        raise ReferenceIKError('EXPECT_ENDPOINT_XYZ')
    finite((*xyz, pitch))
    x, y, z = xyz
    radial = math.hypot(x, y)
    if radial < 1e-8:
        raise ReferenceIKError('BASE_AXIS_SINGULARITY')
    b = math.atan2(y, x)
    l2, l3, l4 = geometry.lengths
    d2, d3, d4 = geometry.offsets
    wx = radial - l4 * math.cos(pitch + d4)
    wz = z + l4 * math.sin(pitch + d4)
    c = (wx * wx + wz * wz - l2 * l2 - l3 * l3) / (2 * l2 * l3)
    if c < -1 - 1e-10 or c > 1 + 1e-10:
        raise ReferenceIKError('WRIST_POINT_OUTSIDE_REFERENCE_REACH')
    if math.hypot(wx, wz) < 1e-8:
        raise ReferenceIKError('WRIST_POINT_SINGULARITY')
    # Clamp floating roundoff only after reachability rejection.
    alpha = math.acos(max(-1., min(1., c)))
    solutions = []
    for branch, relative in [('negative_relative_elbow', -alpha),
                             ('positive_relative_elbow', alpha)]:
        a2 = math.atan2(wz, wx) - math.atan2(l3 * math.sin(relative),
                                           l2 + l3 * math.cos(relative))
        s = math.pi / 2 - d2 - a2
        s = (s + math.pi) % (2 * math.pi) - math.pi
        e = d2 - d3 - relative
        t = pitch + math.pi / 2 - s - e
        q = (b, s, e, t)
        violations = [name for name, value in zip(('b', 's', 'e', 't'), q)
                      if not reference_limits[name][0] - 1e-9 <= value <= reference_limits[name][1] + 1e-9]
        fk = forward(q, geometry)
        position_error = math.dist(fk[:3], xyz)
        pitch_error = abs(fk[3] - pitch)
        solutions.append({'branch': branch, 'joint_rad': dict(zip(('b', 's', 'e', 't'), q)),
            'joint_deg': dict(zip(('b', 's', 'e', 't'), map(math.degrees, q))),
            'reference_limit_violations': violations,
            'position_roundtrip_error_mm': position_error,
            'pitch_roundtrip_error_rad': pitch_error,
            'reference_limit_compatible': not violations,
            'physical_execution': False})
    return solutions
