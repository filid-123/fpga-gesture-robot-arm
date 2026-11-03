import os
import unittest
from pathlib import Path

import arm_backend as ab
import arm_bench_tools as bt
import so101_feetech_reference as ft
from arm_profile import ArmProfile, ProfileError, find_config_root
from roarm_json_reference import parse_feedback_line


def golden_mem():
    roots = list(Path(__file__).resolve().parents)
    if os.environ.get("GESTURE_BASELINE_ROOT"):
        roots.insert(0, Path(os.environ["GESTURE_BASELINE_ROOT"]))
    for root in roots:
        candidate = root / "sim" / "phase3_robot" / "golden" / "pick_place_phase3_trajectory_q16_16_v1.mem"
        if candidate.exists():
            return candidate
    return None


class BenchToolTests(unittest.TestCase):
    def test_only_bench_profiles_are_accepted(self):
        profile, _protocol, config = bt.load_bench("so101")
        self.assertTrue(profile.bench_only)
        self.assertEqual(config.backend_sel, ab.BACKEND_SO101)
        original = bt.BENCH_PROFILES["so101"]
        try:
            bt.BENCH_PROFILES["so101"] = ("arm_profiles/so_arm101_follower.yaml", original[1])
            with self.assertRaises(ProfileError):
                bt.load_bench("so101")
        finally:
            bt.BENCH_PROFILES["so101"] = original

    def test_so101_emulator_reports_last_goal(self):
        _profile, protocol, config = bt.load_bench("so101")
        model = ab.ArmBackendPlModel(config)
        result = model.process_sample((65536, -32768, 0, 5000, 0, 20000))
        emulator = bt.So101Emulator(protocol, config.device_ids)
        replies = emulator.feed(result.cmd + result.req[:5])      # partial READ buffered
        replies += emulator.feed(result.req[5:])
        self.assertEqual(emulator.replies, 6)
        parser = ft.StatusStreamParserModel(ft.StatusParserConfig.from_protocol(protocol))
        values = []
        for channel, device_id in enumerate(config.device_ids):
            parser.expected_id = device_id
            events = parser.feed(replies[channel * 8:(channel + 1) * 8])
            self.assertEqual(events[0].kind, "packet")
            values.append(events[0].value)
        self.assertEqual(tuple(values), result.device_values)

    def test_roarm_emulator_echoes_positions(self):
        _profile, protocol, config = bt.load_bench("roarm")
        model = ab.ArmBackendPlModel(config)
        result = model.process_sample((65536, -32768, 100000, 5, -1, 98304))
        emulator = bt.RoArmEmulator(protocol)
        reply = emulator.feed(result.cmd + result.req)             # request line is ignored
        self.assertEqual(emulator.replies, 1)
        self.assertEqual(parse_feedback_line(protocol, reply).device_values, result.device_values)

    def test_compare_stream(self):
        self.assertTrue(bt.compare_stream(b"abc", b"abcd").passed)
        self.assertEqual(bt.compare_stream(b"abc", b"abx").first_mismatch, 2)
        self.assertFalse(bt.compare_stream(b"abc", b"ab").passed)

    def test_expected_stream_from_golden_segment(self):
        mem = golden_mem()
        if mem is None:
            self.skipTest("baseline golden MEM not present (set GESTURE_BASELINE_ROOT)")
        _profile, _protocol, config = bt.load_bench("roarm")
        samples = bt.load_segment(mem, 2)
        line = bt.expected_stream(config, samples, line_mode=True)
        dry = bt.expected_stream(config, samples, line_mode=False)
        self.assertEqual(line, b'{"type":7}\n' + dry)
        self.assertEqual(dry.count(b"\n"), 64)
        with self.assertRaises(ValueError):
            bt.load_segment(mem, 10)


if __name__ == "__main__":
    unittest.main()
