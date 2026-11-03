import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

import planner_axi_driver as drv
import planner_p2p_reference as pr
from s2_test_support import ensure_s1_on_path, s1_config_root
from test_planner_axi_driver import FakePlannerMMIO

HAVE_S1 = ensure_s1_on_path()
REQUEST = {"schema": pr.REQUEST_SCHEMA, "target_rad": [0.1, -0.1, 0.0, 0.05, 0.0, 0.0],
           "duration_s": 2.0, "accel_time_s": 0.5, "profile": "trapezoid", "period_s": 0.02}


def run_cli(cli, argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        rc = cli.main(argv)
    text = out.getvalue()
    return rc, json.loads(text) if text.strip() else None


@unittest.skipUnless(HAVE_S1, "S1 v0.1.1 modules not found (set GESTURE_S1_ROOT)")
class MoveCliTests(unittest.TestCase):
    def setUp(self):
        import phase3_s2_move_cli as cli
        self.cli = cli
        self.tmp = tempfile.TemporaryDirectory()
        self.bench = str(s1_config_root() / "arm_profiles/bench_loopback_so101.yaml")
        self.real = str(s1_config_root() / "arm_profiles/so_arm101_follower.yaml")

    def tearDown(self):
        self.tmp.cleanup()

    def request(self, **changes) -> str:
        path = Path(self.tmp.name) / f"req{len(changes)}.json"
        path.write_text(json.dumps(dict(REQUEST, **changes)), encoding="utf-8")
        return str(path)

    def test_plan_offline(self):
        rc, report = run_cli(self.cli, ["plan", self.request(), "--profile", self.bench, "--current-q16", *["0"] * 6])
        self.assertEqual(rc, 0)
        self.assertEqual((report["n_samples"], report["accel_samples"]), (100, 25))
        self.assertEqual(len(report["samples_q16"]), 100)
        self.assertEqual(report["samples_q16"][-1], [6554, -6554, 0, 3277, 0, 0])
        self.assertIsNone(report["validation"])

    def test_plan_refusals(self):
        rc, report = run_cli(self.cli, ["plan", self.request(duration_s=0.1, accel_time_s=0.04), "--profile",
                                        self.bench, "--current-q16", *["0"] * 6])
        self.assertEqual(rc, 3)
        self.assertEqual(report["validation"]["error"], "VELOCITY_LIMIT")
        rc, report = run_cli(self.cli, ["plan", self.request(), "--profile", self.real, "--current-q16", *["0"] * 6])
        self.assertEqual(rc, 3)
        self.assertEqual(report["result"], "REFUSED")              # TBD physical limits

    def fake_board(self, source=drv.SOURCE_S2_PLANNER, arm_mode=1):
        mmio = FakePlannerMMIO()
        mmio.source = source
        mmio.last = (0,) * 6
        planner = drv.PlannerAxiDriver(mmio, sleeper=lambda _s: None)
        self.cli._drivers = lambda: (drv, planner)
        self.cli._arm_mode = lambda: arm_mode
        return mmio

    def test_apply_gates(self):
        import importlib
        mmio = self.fake_board(source=drv.SOURCE_S1_TRAJECTORY)
        rc, report = run_cli(self.cli, ["apply", self.request(), "--profile", self.bench, "--start"])
        self.assertEqual((rc, report["result"]), (3, "REFUSED"))
        mmio = self.fake_board(arm_mode=3)                          # LINE: motion needs confirmation
        rc, report = run_cli(self.cli, ["apply", self.request(), "--profile", self.bench, "--start"])
        self.assertEqual(rc, 3)
        self.assertNotIn((drv.CONTROL, drv.CMD_START), mmio.writes)
        self.assertEqual(mmio.writes, [])                          # nothing loaded either
        rc, report = run_cli(self.cli, ["apply", self.request(target_rad=[3.0, 0, 0, 0, 0, 0]),
                                        "--profile", self.bench, "--start", "--confirm-arm-motion"])
        self.assertEqual(rc, 3)
        self.assertIn("soft_limit_problems", report)
        rc, report = run_cli(self.cli, ["apply", self.request(), "--profile", self.bench, "--start",
                                        "--confirm-arm-motion"])
        self.assertEqual((rc, report["result"]), (0, "STARTED"))
        self.assertEqual(mmio.writes[-1], (drv.CONTROL, drv.CMD_START))
        self.assertEqual(len(mmio.writes), 29 + 1)
        importlib.reload(self.cli)                                 # restore the real hooks

    def test_apply_load_only_and_commands(self):
        import importlib
        mmio = self.fake_board()
        rc, report = run_cli(self.cli, ["apply", self.request(), "--profile", self.bench])
        self.assertEqual((rc, report["result"]), (0, "LOADED"))
        self.assertNotIn((drv.CONTROL, drv.CMD_START), mmio.writes)
        rc, report = run_cli(self.cli, ["estop"])
        self.assertEqual(report["state"], "ESTOP")
        rc, report = run_cli(self.cli, ["status"])
        self.assertEqual(report["errors"], ["ESTOP"])
        rc, report = run_cli(self.cli, ["clear"])
        self.assertEqual(report["state"], "IDLE")
        importlib.reload(self.cli)


@unittest.skipUnless(HAVE_S1, "S1 v0.1.1 modules not found (set GESTURE_S1_ROOT)")
class BoardSmokeTests(unittest.TestCase):
    def test_requires_pynq_and_small_target(self):
        import sys
        import phase3_s2_board_smoke as smoke
        from arm_profile import ArmProfile
        argv = sys.argv
        sys.argv = ["phase3_s2_board_smoke.py", "--step", "readonly"]
        try:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = smoke.main()
        finally:
            sys.argv = argv
        self.assertEqual(rc, 2)                                    # no PYNQ on the PC
        self.assertEqual(json.loads(out.getvalue())["result"], "FAIL")
        profile = ArmProfile.load(s1_config_root() / "arm_profiles/bench_loopback_so101.yaml")
        start = tuple(round(j.soft_max_rad * 65536) - 10 for j in profile.joints)
        target = smoke.small_target(profile, start)
        self.assertTrue(all(abs(t - s) == smoke.STEP_Q16 for t, s in zip(target, start)))
        self.assertEqual(pr.check_soft_limits(profile, (target, target)), [])


if __name__ == "__main__":
    unittest.main()
