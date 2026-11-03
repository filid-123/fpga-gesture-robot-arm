import contextlib
import io
import json
import unittest

import arm_bringup_cli as cli
from arm_profile import find_config_root


CONFIG = find_config_root()
PROFILES = CONFIG / "arm_profiles"


def run(*argv):
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = cli.main([str(a) for a in argv])
    return code, buffer.getvalue()


class BringupCliTests(unittest.TestCase):
    def test_check_reports_blockers_for_real_profiles(self):
        for name in ("roarm_m3_pro.yaml", "so_arm101_follower.yaml"):
            code, out = run("check", PROFILES / name)
            payload = json.loads(out)
            self.assertEqual(code, 3)
            self.assertEqual(payload["status"], "BLOCKED_EXTERNAL_INPUT")
            self.assertTrue(payload["blockers"])

    def test_gated_commands_refuse_without_opening_a_port(self):
        for command in ("listen", "rate-test"):
            code, out = run(command, PROFILES / "roarm_m3_pro.yaml", "--seconds", "0.1")
            self.assertEqual(code, 3, command)
            self.assertIn("BLOCKED_EXTERNAL_INPUT", out)

    def test_pl_config_for_bench_profile(self):
        code, out = run("pl-config", PROFILES / "bench_loopback_so101.yaml")
        payload = json.loads(out)
        self.assertEqual(code, 0)
        self.assertEqual(payload["backend_sel"], 1)
        self.assertEqual(payload["reads_per_cycle"], 6)
        code, _ = run("pl-config", PROFILES / "roarm_m3_pro.yaml")
        self.assertEqual(code, 3)

    def test_preview_with_tbd_protocol_is_not_sendable(self):
        samples = [tuple([0] * 6)] * 32
        profile, protocol = cli.load(PROFILES / "roarm_m3_pro.yaml")
        preview = cli.cmd_preview(profile, protocol, samples)
        self.assertTrue(all(not f["sendable"] for f in preview["frames"]))
        profile, protocol = cli.load(PROFILES / "so_arm101_follower.yaml")
        preview = cli.cmd_preview(profile, protocol, samples)
        self.assertTrue(all(not f["sendable"] and f["blockers"] for f in preview["frames"]))


if __name__ == "__main__":
    unittest.main()
