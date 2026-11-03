"""Bit-exact fixed-point helpers shared by the Phase 3 S1 arm adapters.

These helpers deliberately repeat the rounding rule of
``sim/phase3_robot/trajectory_contract.py`` (nearest, exact ties away from
zero) so PS/PC code does not depend on the simulation directory.  A unit test
cross-checks both implementations.

Contract name for the rad <-> device-unit conversion: ``arm_unit_map_v1``.
The PL module ``rtl/robot/arm_joint_unit_mapper.v`` implements the forward
direction bit-exactly; the inverse is PS/PC-only in S1.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence


UNIT_MAP_CONTRACT = "arm_unit_map_v1"
CHANNEL_COUNT = 6
Q16_SCALE = 1 << 16
INT32_MIN = -(1 << 31)
INT32_MAX = (1 << 31) - 1
UINT32_MAX = (1 << 32) - 1
PRODUCT_SHIFT = 32


class FixedPointError(ValueError):
    """A value violates the fixed-point contract."""


def check_int32(value: int, *, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise FixedPointError(f"{name} must be an integer, got {type(value).__name__}")
    if value < INT32_MIN or value > INT32_MAX:
        raise FixedPointError(f"{name}={value} is outside signed 32-bit range")
    return value


def check_uint32(value: int, *, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise FixedPointError(f"{name} must be an integer, got {type(value).__name__}")
    if value < 0 or value > UINT32_MAX:
        raise FixedPointError(f"{name}={value} is outside unsigned 32-bit range")
    return value


def round_div_nearest_away(numerator: int, denominator: int) -> int:
    """Integer division rounded to nearest, with exact ties away from zero."""

    if denominator <= 0:
        raise FixedPointError("denominator must be greater than zero")
    sign = -1 if numerator < 0 else 1
    quotient, remainder = divmod(abs(int(numerator)), int(denominator))
    if remainder * 2 >= denominator:
        quotient += 1
    return sign * quotient


def float_to_fixed(value: float, fraction_bits: int, *, name: str) -> int:
    """Quantize a finite float with nearest/ties-away rounding."""

    normalized = float(value)
    if not math.isfinite(normalized):
        raise FixedPointError(f"{name} is not finite: {value}")
    scaled = normalized * (1 << fraction_bits)
    return math.floor(scaled + 0.5) if scaled >= 0.0 else math.ceil(scaled - 0.5)


def rad_to_q16_16(value_rad: float, *, name: str = "rad") -> int:
    return check_int32(float_to_fixed(value_rad, 16, name=name), name=name)


def q16_16_to_rad(value: int) -> float:
    return check_int32(value, name="q16_16") / Q16_SCALE


def units_per_rad_to_uq16_16(value: float, *, name: str = "device_units_per_rad") -> int:
    quantized = float_to_fixed(value, 16, name=name)
    return check_uint32(quantized, name=name)


def saturate_int32(value: int) -> tuple[int, bool]:
    if value < INT32_MIN:
        return INT32_MIN, True
    if value > INT32_MAX:
        return INT32_MAX, True
    return value, False


def signed32(word: int) -> int:
    word = int(word) & UINT32_MAX
    return word - (1 << 32) if word & 0x8000_0000 else word


@dataclass(frozen=True)
class ChannelMap:
    """PL-loadable per-channel mapping parameters (all integers)."""

    soft_min_q16: int
    soft_max_q16: int
    zero_dev: int
    scale_uq16_16: int
    dir_neg: bool
    device_id: int = 0
    arrival_tol_dev: int = 0

    def __post_init__(self) -> None:
        check_int32(self.soft_min_q16, name="soft_min_q16")
        check_int32(self.soft_max_q16, name="soft_max_q16")
        check_int32(self.zero_dev, name="zero_dev")
        check_uint32(self.scale_uq16_16, name="scale_uq16_16")
        if not 0 <= self.device_id <= 0xFF:
            raise FixedPointError("device_id must fit in 8 bits")
        if not 0 <= self.arrival_tol_dev <= 0xFFFF:
            raise FixedPointError("arrival_tol_dev must fit in 16 bits")


@dataclass(frozen=True)
class MappedChannel:
    device_value: int
    limit_violation: bool
    saturated: bool


def map_rad_q16_to_device(rad_q16: int, channel: ChannelMap) -> MappedChannel:
    """Forward mapping, bit-exact with ``arm_joint_unit_mapper``.

    ``dev = sat32(zero_dev + round_away((dir * rad_q16 * scale_uq16_16) / 2^32))``
    The soft-limit check uses the logical value before direction mapping.
    """

    rad = check_int32(rad_q16, name="rad_q16")
    limit = rad < channel.soft_min_q16 or rad > channel.soft_max_q16
    signed_rad = -rad if channel.dir_neg else rad
    product = signed_rad * channel.scale_uq16_16
    increment = round_div_nearest_away(product, 1 << PRODUCT_SHIFT)
    device, saturated = saturate_int32(channel.zero_dev + increment)
    return MappedChannel(device, limit, saturated)


def map_device_to_rad_q16(device_value: int, channel: ChannelMap) -> tuple[int, bool]:
    """Inverse mapping for PS/PC feedback conversion (not implemented in PL S1).

    ``rad_q16 = dir * round_away((device - zero) * 2^32 / scale_uq16_16)``
    """

    if channel.scale_uq16_16 == 0:
        raise FixedPointError("scale_uq16_16 must be non-zero for inverse mapping")
    delta = int(device_value) - channel.zero_dev
    rad = round_div_nearest_away(delta << PRODUCT_SHIFT, channel.scale_uq16_16)
    if channel.dir_neg:
        rad = -rad
    return saturate_int32(rad)


def tolerance_rad_q16_to_device(tol_q16: int, scale_uq16_16: int) -> int:
    """Convert a non-negative tolerance to device units with the forward rule."""

    if tol_q16 < 0:
        raise FixedPointError("tolerance must be non-negative")
    return round_div_nearest_away(tol_q16 * scale_uq16_16, 1 << PRODUCT_SHIFT)


def map_joint_vector(
    joints_q16: Sequence[int], channels: Sequence[ChannelMap]
) -> tuple[tuple[int, ...], int, int]:
    """Map six channels. Returns ``(device_values, limit_mask, saturation_mask)``."""

    if len(joints_q16) != CHANNEL_COUNT or len(channels) != CHANNEL_COUNT:
        raise FixedPointError("exactly six joints and six channel maps are required")
    devices: list[int] = []
    limit_mask = 0
    sat_mask = 0
    for index, (value, channel) in enumerate(zip(joints_q16, channels, strict=True)):
        mapped = map_rad_q16_to_device(value, channel)
        devices.append(mapped.device_value)
        if mapped.limit_violation:
            limit_mask |= 1 << index
        if mapped.saturated:
            sat_mask |= 1 << index
    return tuple(devices), limit_mask, sat_mask


def pack_192(values: Sequence[int]) -> int:
    """Pack six signed 32-bit values, channel 0 in bits [31:0]."""

    if len(values) != CHANNEL_COUNT:
        raise FixedPointError("exactly six values are required")
    packed = 0
    for index, value in enumerate(values):
        packed |= (check_int32(value, name=f"ch{index}") & UINT32_MAX) << (32 * index)
    return packed


def unpack_192(packed: int) -> tuple[int, ...]:
    return tuple(signed32(packed >> (32 * index)) for index in range(CHANNEL_COUNT))
