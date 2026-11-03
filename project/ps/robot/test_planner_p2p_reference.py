import dataclasses
import re
import unittest
from pathlib import Path

import planner_p2p_reference as pr
from s2_test_support import ensure_s1_on_path, s1_config_root

HAVE_S1 = ensure_s1_on_path()
OPEN = (0xFFFF_FFFF,) * 6
START = (6554, -13107, 19661, 0, -98304, 98304)
TARGET = (39322, -72090, 19661, 16384, 65536, 0)


def move(n=20, na=5, profile=pr.PROFILE_TRAPEZOID, **kw):
    fields = dict(start=START, target=TARGET, n_samples=n, accel_samples=na, profile=profile,
                  period_cycles=1000, stall_timeout_cycles=4000, vmax_q16=OPEN, amax_q32=OPEN)
    fields.update(kw)
    return pr.MoveParams(**fields)


class ProfileMathTests(unittest.TestCase):
    def test_s_ends_at_d_and_is_symmetric(self):
        for n, na in ((2, 1), (16, 8), (40, 10), (33, 1), (65535, 1), (65535, 32767)):
            p = move(n, na)
            d, a, v = pr.profile_constants(p)
            self.assertEqual(d, 2 * a)
            self.assertEqual(v, n - na)
            self.assertLess(d, 1 << 31)
            if n <= 1000:
                s = pr.s_values(p)
                self.assertEqual(s[-1], d)
                self.assertEqual(s, sorted(s))
                self.assertTrue(all(s[k] + s[n - k] == d for k in range(n + 1)))
                self.assertEqual(s[na], na * na)
        s = pr.s_values(move(7, 0, pr.PROFILE_LINEAR))
        self.assertEqual(s, list(range(8)))

    def test_rounding_is_half_away_from_zero(self):
        self.assertEqual(pr.interpolate(0, 1, 1 << 31), 1)
        self.assertEqual(pr.interpolate(0, -1, 1 << 31), -1)
        self.assertEqual(pr.interpolate(10, 13, (1 << 32) // 3), 11)
        self.assertEqual(pr.interpolate(10, 7, (1 << 32) // 3), 9)
        self.assertEqual(pr.s_frac(0, 5), 0)
        with self.assertRaises(ValueError):
            pr.s_frac(5, 5)

    def test_samples_end_on_target_monotonic_and_bounded(self):
        for p in (move(), move(16, 8), move(9, 0, pr.PROFILE_LINEAR), move(1, 0, pr.PROFILE_LINEAR)):
            out = pr.samples(p)
            self.assertEqual(len(out), p.n_samples)
            self.assertEqual(out[-1], TARGET)
            for ch in range(6):
                series = [START[ch]] + [s[ch] for s in out]
                step = [b - a for a, b in zip(series, series[1:])]
                self.assertTrue(all(x >= 0 for x in step) or all(x <= 0 for x in step))
            _d, _a, v = pr.profile_constants(p)
            for ch, peak in enumerate(pr.max_step(p)):
                bound = -(-abs(TARGET[ch] - START[ch]) // v)
                self.assertLessEqual(peak, bound + 1)            # 1 LSB rounding tolerance

    def test_extreme_int32_range(self):
        p = move(1000, 100, start=(pr.INT32_MIN,) * 6, target=(pr.INT32_MAX,) * 6)
        out = pr.samples(p)
        self.assertTrue(all(pr.INT32_MIN <= v <= pr.INT32_MAX for s in out for v in s))
        self.assertEqual(out[-1], (pr.INT32_MAX,) * 6)


class ValidationTests(unittest.TestCase):
    def test_scalar_rules(self):
        bad = [move(0, 0, pr.PROFILE_LINEAR), move(10, 1, pr.PROFILE_LINEAR), move(10, 0),
               move(10, 6), move(period_cycles=pr.MIN_PERIOD_CYCLES - 1), move(stall_timeout_cycles=0)]
        for p in bad:
            self.assertEqual(pr.validate(p).error, pr.PlannerError.PARAM_INVALID)
        self.assertTrue(pr.validate(move(10, 5)).ok)
        self.assertTrue(pr.validate(move(period_cycles=pr.MIN_PERIOD_CYCLES)).ok)

    def test_order_continuity_velocity_accel(self):
        last = list(START)
        last[2] += 1
        r = pr.validate(move(), tuple(last))
        self.assertEqual((r.error, r.channel), (pr.PlannerError.START_MISMATCH, 2))
        self.assertTrue(pr.validate(move(), START).ok)
        p = move(10, 2)
        d3 = abs(TARGET[3] - START[3])
        vmax = list(OPEN)
        vmax[3] = -(-d3 // 8)
        self.assertTrue(pr.validate(dataclasses.replace(p, vmax_q16=tuple(vmax))).ok)
        vmax[3] -= 1
        r = pr.validate(dataclasses.replace(p, vmax_q16=tuple(vmax)))
        self.assertEqual((r.error, r.channel), (pr.PlannerError.VELOCITY_LIMIT, 3))
        amax = list(OPEN)
        d5 = abs(TARGET[5] - START[5])
        amax[5] = -(-(d5 << 16) // 16)                     # A = 2 * 8
        self.assertTrue(pr.validate(dataclasses.replace(p, amax_q32=tuple(amax))).ok)
        amax[5] -= 1
        r = pr.validate(dataclasses.replace(p, amax_q32=tuple(amax)))
        self.assertEqual((r.error, r.channel), (pr.PlannerError.ACCEL_LIMIT, 5))
        zero = pr.validate(move(vmax_q16=(0,) * 6))
        self.assertEqual(zero.error, pr.PlannerError.VELOCITY_LIMIT)   # reset limits refuse motion

    def test_register_ranges(self):
        with self.assertRaises(ValueError):
            move(n=70000)
        with self.assertRaises(ValueError):
            move(start=(0,) * 5)
        with self.assertRaises(ValueError):
            move(vmax_q16=(-1,) * 6)


class CoreModelTests(unittest.TestCase):
    def test_run_pause_done_and_continuity(self):
        m = pr.PlannerCoreModel()
        self.assertTrue(m.start(move(6, 2)).ok)
        m.present(); m.accept()
        m.pause()
        self.assertIsNone(m.present())
        m.resume()
        while m.present() is not None:
            m.accept()
        self.assertEqual(m.state, pr.PlannerState.DONE)
        self.assertEqual(m.delivered, pr.samples(move(6, 2)))
        r = m.start(move(6, 2))                            # start != last delivered
        self.assertEqual(r.error, pr.PlannerError.START_MISMATCH)

    def test_estop_keeps_pending_sample(self):
        m = pr.PlannerCoreModel()
        m.start(move(6, 2))
        pending = m.present()
        m.estop()
        m.accept()
        self.assertEqual(m.delivered, [pending])
        self.assertIsNone(m.present())
        with self.assertRaises(RuntimeError):
            m.start(move(6, 2))
        m.clear()
        self.assertEqual(m.state, pr.PlannerState.IDLE)


@unittest.skipUnless(HAVE_S1, "S1 v0.1.1 modules not found (set GESTURE_S1_ROOT)")
class PsConversionTests(unittest.TestCase):
    def setUp(self):
        from arm_profile import ArmProfile
        self.bench = ArmProfile.load(s1_config_root() / "arm_profiles/bench_loopback_so101.yaml")
        self.real = ArmProfile.load(s1_config_root() / "arm_profiles/so_arm101_follower.yaml")

    def test_limits_from_profile(self):
        vmax, amax = pr.limits_from_profile(self.bench, 0.02)
        self.assertEqual(vmax, (655,) * 6)                 # 0.5 rad/s * 20 ms = 0.01 rad
        self.assertEqual(amax, (1717986,) * 6)            # 1 rad/s^2 * (20 ms)^2 * 2^32
        with self.assertRaises(pr.MoveRequestError):
            pr.limits_from_profile(self.real, 0.02)        # TBD limits

    def test_plan_move_and_request(self):
        vmax, amax = pr.limits_from_profile(self.bench, 0.02)
        p = pr.plan_move(START, START, duration_s=1.0, period_s=0.02, profile_kind="trapezoid",
                         accel_time_s=0.2, vmax_q16=vmax, amax_q32=amax)
        self.assertEqual((p.n_samples, p.accel_samples, p.period_cycles), (50, 10, 2_000_000))
        request = {"schema": pr.REQUEST_SCHEMA, "target_rad": [0.1, -0.1, 0.0, 0.05, 0.0, 0.0],
                   "duration_s": 2.0, "accel_time_s": 0.5, "profile": "trapezoid", "period_s": 0.02}
        current = (0,) * 6
        mv, problems = pr.move_from_request(request, self.bench, current)
        self.assertEqual(mv.start, current)
        self.assertEqual(problems, [])
        self.assertTrue(pr.validate(mv, current).ok)
        with self.assertRaises(pr.MoveRequestError):
            pr.move_from_request(dict(request, start_q16=[1] * 6), self.bench, current)
        far = dict(request, target_rad=[3.0, 0, 0, 0, 0, 0])
        _mv, problems = pr.move_from_request(far, self.bench, current)
        self.assertTrue(any("outside" in p for p in problems))
        with self.assertRaises(pr.MoveRequestError):
            pr.move_from_request({"schema": "x"}, self.bench, current)


class ContractConsistencyTests(unittest.TestCase):
    def test_min_period_matches_rtl(self):
        rtl = Path(__file__).resolve().parents[2] / "rtl" / "robot" / "planner_p2p_core.v"
        if not rtl.exists():
            self.skipTest("RTL not in this layout")
        text = rtl.read_text(encoding="ascii")
        self.assertIn(f"parameter integer MIN_PERIOD_CYCLES = {pr.MIN_PERIOD_CYCLES}", text)
        codes = dict(re.findall(r"localparam \[2:0\] E_(\w+)\s*=\s*3'd(\d)", text))
        self.assertEqual(int(codes["VELOCITY"]), pr.PlannerError.VELOCITY_LIMIT)
        self.assertEqual(int(codes["STALL"]), pr.PlannerError.STALL_TIMEOUT)
        self.assertEqual(int(codes["ESTOP"]), pr.PlannerError.ESTOP)


if __name__ == "__main__":
    unittest.main()
