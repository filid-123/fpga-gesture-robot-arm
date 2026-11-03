import unittest

import arm_feedback as af
from arm_fixed_point import ChannelMap


class ErrorTaxonomyTests(unittest.TestCase):
    def test_pl_bits_are_unique_and_decode(self):
        pl_codes = [code for code in af.ArmError if int(code) < 16]
        self.assertEqual(len({int(c) for c in pl_codes}), len(pl_codes))
        raw = (1 << af.ArmError.FEEDBACK_TIMEOUT) | (1 << af.ArmError.LIMIT_VIOLATION)
        self.assertEqual(af.decode_pl_errors(raw), [af.ArmError.LIMIT_VIOLATION, af.ArmError.FEEDBACK_TIMEOUT])
        self.assertTrue(af.PL_FATAL_MASK & (1 << af.ArmError.ESTOP_EVENT))
        self.assertFalse(af.PL_FATAL_MASK & (1 << af.ArmError.RESPONSE_TIMEOUT))


class FeedbackRecordTests(unittest.TestCase):
    def test_device_to_rad_conversion(self):
        maps = [ChannelMap(-10, 10, 2048, 651 << 16, False)] * 6
        record = af.ArmFeedback.from_device(
            sample_seq=1, rx_tick=5, position_device=(2048, 2699, None, 1397, 2048, 2048),
            channel_maps=maps,
        )
        self.assertEqual(record.valid_mask, 0b111011)
        self.assertEqual(record.position_q16_16[0], 0)
        self.assertEqual(record.position_q16_16[1], 65536)
        self.assertIsNone(record.position_q16_16[2])
        self.assertEqual(record.position_q16_16[3], -65536)


class WatchdogModelTests(unittest.TestCase):
    def setUp(self):
        self.model = af.FeedbackWatchdogModel(af.WatchdogConfig(3, 2, 0b000011, (5,) * 6))

    def test_disabled_ignores_events(self):
        self.model.tick()
        self.model.update(0b1, (1,) * 6)
        state = self.model.state()
        self.assertEqual((state.valid_mask, state.timeout, state.fb_seq), (0, False, 0))

    def test_timeout_only_on_required_channels(self):
        self.model.set_enable(True)
        for _ in range(3):
            self.model.tick()
        self.assertFalse(self.model.state().timeout)
        self.model.update(0b100, (0,) * 6)          # channel 2 is not required
        self.model.tick()
        state = self.model.state()
        self.assertTrue(state.timeout)
        self.assertEqual(state.age_max, 4)
        self.model.update(0b11, (0,) * 6)
        self.assertFalse(self.model.state().timeout)

    def test_arrival_needs_consecutive_hits_after_command(self):
        self.model.set_enable(True)
        self.model.command((100,) * 6)
        self.model.update(0b1, (104,) + (0,) * 5)
        self.assertEqual(self.model.state().arrival_mask, 0)
        self.model.update(0b1, (95,) + (0,) * 5)
        self.assertEqual(self.model.state().arrival_mask, 1)
        self.model.update(0b1, (94,) + (0,) * 5)       # outside tolerance resets
        self.assertEqual(self.model.state().arrival_mask, 0)
        self.model.update(0b1, (100,) + (0,) * 5)
        self.model.update(0b1, (100,) + (0,) * 5)
        self.assertEqual(self.model.state().arrival_mask, 1)
        self.model.command((0,) * 6)                   # new command clears arrival
        self.assertEqual(self.model.state().arrival_mask, 0)

    def test_age_saturates(self):
        self.model.set_enable(True)
        self.model.ages = [0xFFFE] * 6
        self.model.tick()
        self.model.tick()
        self.assertEqual(self.model.state().ages, (0xFFFF,) * 6)


class PermissionGateModelTests(unittest.TestCase):
    def test_debounce_and_immediate_drop(self):
        gate = af.PermissionGateModel(debounce_cycles=4)
        trace = []
        for raw in [1] * 8 + [0] + [1] * 3:
            gate.step(raw, line_mode=1, arm=1)
            trace.append((gate.estop_ok, gate.estop_event))
        # two sync stages, then four stable cycles before OK
        self.assertEqual([ok for ok, _ in trace[:8]], [0, 0, 0, 0, 0, 1, 1, 1])
        self.assertEqual([ok for ok, _ in trace[8:]], [1, 1, 0, 0])
        self.assertEqual([ev for _, ev in trace], [0] * 10 + [1, 0])

    def test_permission_requires_every_condition(self):
        self.assertEqual(af.PermissionGateModel.permission(1, line_mode=1, arm=1, config_valid=1, fault=0), 1)
        for kwargs in ({"line_mode": 0}, {"arm": 0}, {"config_valid": 0}, {"fault": 1}):
            base = {"line_mode": 1, "arm": 1, "config_valid": 1, "fault": 0}
            base.update(kwargs)
            self.assertEqual(af.PermissionGateModel.permission(1, **base), 0)
        self.assertEqual(af.PermissionGateModel.permission(0, line_mode=1, arm=1, config_valid=1, fault=0), 0)


if __name__ == "__main__":
    unittest.main()
