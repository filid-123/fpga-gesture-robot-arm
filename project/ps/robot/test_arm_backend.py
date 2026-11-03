import unittest

import arm_backend as ab
import arm_frame_template as aft
import so101_feetech_reference as ft
from arm_fixed_point import ChannelMap
from arm_profile import ArmProfile, ProfileError, RealOutputBlocked, find_config_root
from roarm_json_reference import RoArmJsonProtocol, encode_command


CONFIG = find_config_root()
PROFILES = CONFIG / "arm_profiles"
RJ_FIXTURE = RoArmJsonProtocol.load(CONFIG / "protocols/fixtures/roarm_json_FIXTURE_NOT_OFFICIAL.yaml")
FT_FIXTURE = ft.FeetechProtocol.load(CONFIG / "protocols/fixtures/feetech_FIXTURE_NOT_OFFICIAL.yaml")
RJ_OFFICIAL = RoArmJsonProtocol.load(CONFIG / "protocols/roarm_m3_json_protocol.yaml")
FT_OFFICIAL = ft.FeetechProtocol.load(CONFIG / "protocols/feetech_sts_protocol.yaml")
BENCH_RJ = ArmProfile.load(PROFILES / "bench_loopback_roarm_json.yaml")
BENCH_FT = ArmProfile.load(PROFILES / "bench_loopback_so101.yaml")


class TimingConversionTests(unittest.TestCase):
    def test_baud_divisors(self):
        self.assertEqual(ab.baud_divisor(115200), 868)
        self.assertEqual(ab.baud_divisor(1_000_000), 100)
        with self.assertRaises(ProfileError):
            ab.baud_divisor(10_000_000)          # divisor 10 < 16
        with self.assertRaises(ProfileError):
            ab.baud_divisor(1000)                # divisor > 65535
        with self.assertRaises(ProfileError):
            ab.baud_divisor(6_060_606)           # divisor 17 -> 2.9 % error exceeds the 2 % limit

    def test_round_robin_helpers(self):
        self.assertEqual(ab.first_required(0b101000), 3)
        self.assertEqual(ab.next_required(3, 0b101000), 5)
        self.assertEqual(ab.next_required(5, 0b101000), 3)
        self.assertEqual(ab.next_required(2, 0), 2)


class PlConfigTests(unittest.TestCase):
    def test_roarm_bench_config(self):
        config = ab.build_pl_config(BENCH_RJ, RJ_FIXTURE)
        self.assertEqual(config.backend_sel, ab.BACKEND_ROARM)
        self.assertEqual(config.baud_div_roarm, 868)
        self.assertEqual(config.required_mask, 0)
        self.assertTrue(config.template.req_enable)
        self.assertIsNotNone(config.json)
        self.assertEqual(config.channel_maps[2].zero_dev, 150)
        self.assertTrue(config.channel_maps[2].dir_neg)

    def test_so101_bench_config(self):
        config = ab.build_pl_config(BENCH_FT, FT_FIXTURE)
        self.assertEqual(config.backend_sel, ab.BACKEND_SO101)
        self.assertEqual((config.hd_lead_cycles, config.hd_lag_cycles), (200, 200))
        self.assertEqual(config.response_timeout_cycles, 200_000)
        self.assertEqual(config.required_mask, 0x3F)
        self.assertEqual(config.feedback_timeout_ticks, 100)
        self.assertEqual(config.device_ids, (21, 22, 23, 24, 25, 26))
        self.assertEqual(config.sts.word() & 0xFFFF, 0xE2E1)

    def test_pl_register_widths_are_enforced(self):
        config = ab.build_pl_config(BENCH_FT, FT_FIXTURE)
        for label, value in (("response_timeout_cycles", 1 << 24), ("prime_period_cycles", 1 << 24),
                             ("wd_prescale", 1 << 20), ("wd_prescale", 0)):
            with self.assertRaises(ProfileError, msg=label):
                ab.PlBackendConfig(**{**config.__dict__, label: value})

    def test_real_profiles_cannot_build_pl_config(self):
        with self.assertRaises(ProfileError):
            ab.build_pl_config(ArmProfile.load(PROFILES / "roarm_m3_pro.yaml"), RJ_OFFICIAL)
        with self.assertRaises(ProfileError):
            ab.build_pl_config(ArmProfile.load(PROFILES / "so_arm101_follower.yaml"), FT_OFFICIAL)


class PlModelTests(unittest.TestCase):
    def test_roarm_frames_and_seq(self):
        model = ab.ArmBackendPlModel(ab.build_pl_config(BENCH_RJ, RJ_FIXTURE))
        result = model.process_sample((65536, -32768, 100000, 5, -1, 98304))
        self.assertIsNone(result.fault)
        self.assertEqual(result.cmd, encode_command(RJ_FIXTURE, "set_joints", result.device_values))
        self.assertEqual(result.req, b'{"type":7}\n')
        self.assertEqual(model.frames_tx, 1)

    def test_so101_round_robin_requests(self):
        config = ab.build_pl_config(BENCH_FT, FT_FIXTURE)
        self.assertEqual(config.reads_per_cycle, 6)
        model = ab.ArmBackendPlModel(config)
        result = model.process_sample((0,) * 6)
        self.assertEqual(result.rr_channels, (0, 1, 2, 3, 4, 5))
        self.assertEqual(result.req, b"".join(ft.read(FT_FIXTURE, i, "present_position")
                                              for i in (21, 22, 23, 24, 25, 26)))
        one = ab.ArmBackendPlModel(ab.PlBackendConfig(**{**config.__dict__, "reads_per_cycle": 1}))
        channels = [one.process_sample((0,) * 6).rr_channel for _ in range(8)]
        self.assertEqual(channels, [0, 1, 2, 3, 4, 5, 0, 1])
        self.assertEqual(one.log[-1].req, ft.read(FT_FIXTURE, 22, "present_position"))

    def test_poll_cycle_reads_like_a_motion_cycle_without_command(self):
        model = ab.ArmBackendPlModel(ab.build_pl_config(BENCH_FT, FT_FIXTURE))
        data, channels = model.poll_cycle()
        self.assertEqual(channels, (0, 1, 2, 3, 4, 5))
        self.assertEqual(len(data), 6 * 8)
        self.assertEqual(model.frames_tx, 0)
        roarm = ab.ArmBackendPlModel(ab.build_pl_config(BENCH_RJ, RJ_FIXTURE))
        self.assertEqual(roarm.poll_cycle(), (b'{"type":7}\n', (0,)))

    def test_feedback_refresh_feasibility(self):
        config = ab.build_pl_config(BENCH_FT, FT_FIXTURE)          # timeout 100 ms
        self.assertTrue(ab.feedback_refresh_ok(config, 2_000_000))  # 50 Hz, all six per cycle
        one = ab.PlBackendConfig(**{**config.__dict__, "reads_per_cycle": 1})
        self.assertFalse(ab.feedback_refresh_ok(one, 2_000_000))    # 6 x 20 ms > 50 ms budget
        self.assertTrue(ab.feedback_refresh_ok(ab.build_pl_config(BENCH_RJ, RJ_FIXTURE), 1))

    def test_last_gate_cancels_without_consuming(self):
        model = ab.ArmBackendPlModel(ab.build_pl_config(BENCH_FT, FT_FIXTURE))
        sample = (1000, -2000, 3000, 0, 0, 0)
        held = model.process_sample(sample, permitted=False)
        self.assertFalse(held.accepted)
        self.assertIsNone(held.fault)
        self.assertEqual((held.cmd, held.req, model.frames_tx, model.log), (b"", b"", 0, []))
        fresh = ab.ArmBackendPlModel(ab.build_pl_config(BENCH_FT, FT_FIXTURE))
        self.assertEqual(model.process_sample(sample), fresh.process_sample(sample))
        # errors are still detected before the gate, as in the RTL
        bad = model.process_sample((0, 0, 0, 0, 0, 2 * 65536), permitted=False)
        self.assertEqual(bad.fault, "limit_violation")

    def test_limit_violation_faults_without_frame(self):
        model = ab.ArmBackendPlModel(ab.build_pl_config(BENCH_FT, FT_FIXTURE))
        result = model.process_sample((0, 0, 0, 0, 0, 2 * 65536))
        self.assertEqual(result.fault, "limit_violation")
        self.assertEqual(result.limit_mask, 0b100000)
        self.assertEqual(result.cmd, b"")
        self.assertEqual(model.frames_tx, 0)
        self.assertFalse(result.accepted)
        self.assertEqual(model.process_sample((0,) * 6).accepted, False)

    def test_encode_saturation_faults_before_emission(self):
        config = ab.build_pl_config(BENCH_FT, FT_FIXTURE)
        # 1 rad -> 40000 device units, which cannot fit the 16-bit position field
        wide = ChannelMap(-(1 << 30), 1 << 30, 0, 40000 << 16, False, 21, 0)
        bad = ab.PlBackendConfig(**{**config.__dict__, "channel_maps": (wide,) + config.channel_maps[1:]})
        model = ab.ArmBackendPlModel(bad)
        result = model.process_sample((65536, 0, 0, 0, 0, 0))
        self.assertEqual(result.fault, "encode_saturation")
        self.assertEqual(result.cmd, b"")


class RealOutputGateTests(unittest.TestCase):
    def test_robot_purpose_blocked_for_shipped_profiles(self):
        for name, protocol in (("roarm_m3_pro.yaml", RJ_OFFICIAL), ("so_arm101_follower.yaml", FT_OFFICIAL)):
            with self.assertRaises(RealOutputBlocked) as ctx:
                ab.require_real_output(ArmProfile.load(PROFILES / name), protocol, purpose="robot")
            self.assertTrue(any("TBD" in reason for reason in ctx.exception.reasons))

    def test_fixture_protocol_never_allows_robot(self):
        with self.assertRaises(RealOutputBlocked) as ctx:
            ab.require_real_output(BENCH_FT, FT_FIXTURE, purpose="robot")
        self.assertTrue(any("FIXTURE_NOT_OFFICIAL" in r for r in ctx.exception.reasons))

    def test_bench_loopback_needs_confirmation(self):
        with self.assertRaises(RealOutputBlocked):
            ab.require_real_output(BENCH_RJ, RJ_FIXTURE, purpose="bench_loopback")
        permit = ab.require_real_output(BENCH_RJ, RJ_FIXTURE, purpose="bench_loopback", confirm_no_robot=True)
        self.assertEqual(permit.purpose, "bench_loopback")
        with self.assertRaises(RealOutputBlocked):
            ab.require_real_output(ArmProfile.load(PROFILES / "roarm_m3_pro.yaml"), RJ_OFFICIAL,
                                   purpose="bench_loopback", confirm_no_robot=True)

    def test_readonly_and_unknown_purposes(self):
        with self.assertRaises(RealOutputBlocked):
            ab.require_real_output(ArmProfile.load(PROFILES / "roarm_m3_pro.yaml"), RJ_OFFICIAL,
                                   purpose="robot_readonly")
        with self.assertRaises(RealOutputBlocked):
            ab.require_real_output(BENCH_RJ, RJ_FIXTURE, purpose="anything")

    def test_binary_bridge_blocked_in_s1(self):
        profile = ArmProfile.load(PROFILES / "roarm_m3_binary_bridge.yaml")
        with self.assertRaises(RealOutputBlocked) as ctx:
            ab.require_real_output(profile, None, purpose="robot")
        self.assertIn("binary bridge firmware is not delivered/validated in S1", ctx.exception.reasons)


class TemplateCapacityTests(unittest.TestCase):
    def test_bench_templates_fit_and_validate(self):
        for config in (ab.build_pl_config(BENCH_RJ, RJ_FIXTURE), ab.build_pl_config(BENCH_FT, FT_FIXTURE)):
            image = config.template
            self.assertLessEqual(image.cmd_words + image.req_words, aft.TEMPLATE_DEPTH)
            aft.validate_program(image.ram, image.cmd_base)
            aft.validate_program(image.ram, image.req_base)


if __name__ == "__main__":
    unittest.main()
