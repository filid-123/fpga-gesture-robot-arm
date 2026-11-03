import os
import random
import sys
import unittest
from pathlib import Path

import arm_fixed_point as fp


def _find_trajectory_contract():
    """Project layout: found above this file.  Version-package layout: set
    GESTURE_BASELINE_ROOT to the project (or handoff source_baseline) root."""

    roots = list(Path(__file__).resolve().parents)
    if os.environ.get("GESTURE_BASELINE_ROOT"):
        roots.insert(0, Path(os.environ["GESTURE_BASELINE_ROOT"]))
    for parent in roots:
        candidate = parent / "sim" / "phase3_robot" / "trajectory_contract.py"
        if candidate.exists():
            return candidate.parent
    return None


class RoundingTests(unittest.TestCase):
    def test_round_div_ties_away_from_zero(self):
        self.assertEqual(fp.round_div_nearest_away(3, 2), 2)
        self.assertEqual(fp.round_div_nearest_away(-3, 2), -2)
        self.assertEqual(fp.round_div_nearest_away(5, 4), 1)
        self.assertEqual(fp.round_div_nearest_away(-5, 4), -1)
        self.assertEqual(fp.round_div_nearest_away(7, 4), 2)
        with self.assertRaises(fp.FixedPointError):
            fp.round_div_nearest_away(1, 0)

    def test_matches_frozen_trajectory_contract(self):
        directory = _find_trajectory_contract()
        if directory is None:
            self.skipTest("sim/phase3_robot/trajectory_contract.py not present in this layout")
        sys.path.insert(0, str(directory))
        try:
            import trajectory_contract as tc
        finally:
            sys.path.remove(str(directory))
        rng = random.Random(3001)
        for _ in range(2000):
            numerator = rng.randint(-(1 << 40), 1 << 40)
            denominator = rng.randint(1, 1 << 20)
            self.assertEqual(
                fp.round_div_nearest_away(numerator, denominator),
                tc.round_div_nearest_away(numerator, denominator),
            )
        for value in (0.0, 1.5, -1.5, 3.14159, -2.7182818, 1e-6, -1e-6, 32767.99):
            self.assertEqual(fp.rad_to_q16_16(value), tc.float_to_q16_16(value))


class MappingTests(unittest.TestCase):
    def setUp(self):
        self.channel = fp.ChannelMap(
            soft_min_q16=-3 * 65536,
            soft_max_q16=3 * 65536,
            zero_dev=2048,
            scale_uq16_16=fp.units_per_rad_to_uq16_16(651.8986),
            dir_neg=False,
        )

    def test_forward_examples(self):
        self.assertEqual(fp.map_rad_q16_to_device(0, self.channel).device_value, 2048)
        self.assertEqual(fp.map_rad_q16_to_device(65536, self.channel).device_value, 2700)
        negated = fp.ChannelMap(**{**self.channel.__dict__, "dir_neg": True})
        self.assertEqual(fp.map_rad_q16_to_device(65536, negated).device_value, 1396)

    def test_limits_checked_before_direction(self):
        negated = fp.ChannelMap(**{**self.channel.__dict__, "dir_neg": True, "soft_min_q16": 0})
        self.assertFalse(fp.map_rad_q16_to_device(65536, negated).limit_violation)
        self.assertTrue(fp.map_rad_q16_to_device(-1, negated).limit_violation)

    def test_product_tie_rounds_away(self):
        # scale 0.5 unit/rad in UQ16.16 = 32768; 65536 * 32768 / 2^32 = 0.5 -> 1
        half = fp.ChannelMap(-(1 << 31), (1 << 31) - 1, 0, 32768, False)
        self.assertEqual(fp.map_rad_q16_to_device(65536, half).device_value, 1)
        self.assertEqual(fp.map_rad_q16_to_device(-65536, half).device_value, -1)

    def test_saturation_at_int32(self):
        huge = fp.ChannelMap(fp.INT32_MIN, fp.INT32_MAX, fp.INT32_MAX, 0xFFFF_FFFF, False)
        mapped = fp.map_rad_q16_to_device(fp.INT32_MAX, huge)
        self.assertEqual(mapped.device_value, fp.INT32_MAX)
        self.assertTrue(mapped.saturated)
        mapped = fp.map_rad_q16_to_device(fp.INT32_MIN, fp.ChannelMap(
            fp.INT32_MIN, fp.INT32_MAX, fp.INT32_MIN, 0xFFFF_FFFF, False))
        self.assertEqual(mapped.device_value, fp.INT32_MIN)
        self.assertTrue(mapped.saturated)

    def test_inverse_round_trip_within_one_device_lsb(self):
        rng = random.Random(7)
        for _ in range(500):
            device = rng.randint(0, 4095)
            rad, saturated = fp.map_device_to_rad_q16(device, self.channel)
            self.assertFalse(saturated)
            back = fp.map_rad_q16_to_device(rad, self.channel).device_value
            self.assertLessEqual(abs(back - device), 1)

    def test_tolerance_conversion(self):
        tol = fp.tolerance_rad_q16_to_device(fp.rad_to_q16_16(0.01), self.channel.scale_uq16_16)
        self.assertEqual(tol, 7)
        with self.assertRaises(fp.FixedPointError):
            fp.tolerance_rad_q16_to_device(-1, 1)

    def test_pack_unpack_signed_channels(self):
        values = (-1, 2, fp.INT32_MIN, fp.INT32_MAX, 0, -65536)
        self.assertEqual(fp.unpack_192(fp.pack_192(values)), values)
        self.assertEqual(fp.pack_192((1, 0, 0, 0, 0, 0)), 1)

    def test_channel_map_rejects_out_of_range_fields(self):
        with self.assertRaises(fp.FixedPointError):
            fp.ChannelMap(0, 0, 0, -1, False)
        with self.assertRaises(fp.FixedPointError):
            fp.ChannelMap(0, 0, 0, 1, False, device_id=256)


if __name__ == "__main__":
    unittest.main()
