import unittest

import trajectory_axi_driver as td


class FakeTrajectoryMMIO:
    def __init__(self):
        self.words = {
            td.ABI_VERSION: td.TRAJECTORY_ABI_VERSION,
            td.MIN_PERIOD_CYCLES: 256,
            td.STATUS: td.STATUS_CMD_READY,
            td.ERROR_STATUS: 0,
            td.IRQ_ENABLE: 0,
        }
        self.writes = []
        self.committed = None

    def read(self, offset):
        return self.words.get(offset, 0)

    def write(self, offset, value):
        value &= 0xFFFF_FFFF
        self.writes.append((offset, value))
        if offset == td.CONTROL:
            if value == td.CTRL_COMMIT:
                self.committed = (
                    tuple(self.words[td.START_CH0 + 4 * i] for i in range(6)),
                    tuple(self.words[td.TARGET_CH0 + 4 * i] for i in range(6)),
                    self.words[td.PERIOD_SHADOW],
                )
                self.words[td.STATUS] = td.STATUS_BUSY
            elif value == td.CTRL_SAMPLE_POP:
                self.words[td.SAMPLE_META] &= ~td.META_VALID
                self.words[td.STATUS] &= ~td.STATUS_SAMPLE_VALID
            elif value == td.CTRL_DONE_CLEAR:
                self.words[td.STATUS] &= ~td.STATUS_DONE
            return
        self.words[offset] = value

    def publish_sample(self, joints, *, index, last):
        for channel, value in enumerate(joints):
            self.words[td.SAMPLE_CH0 + 4 * channel] = value & 0xFFFF_FFFF
        self.words[td.SAMPLE_META] = (
            td.META_VALID | td.META_BUSY | index | (td.META_LAST if last else 0)
        )
        self.words[td.STATUS] = (
            td.STATUS_BUSY
            | td.STATUS_SAMPLE_VALID
            | (td.STATUS_SAMPLE_LAST if last else 0)
            | (index << 8)
        )


class TrajectoryAxiDriverTests(unittest.TestCase):
    def setUp(self):
        self.mmio = FakeTrajectoryMMIO()
        self.driver = td.TrajectoryAxiDriver(self.mmio, sleeper=lambda _delay: None)

    def test_submit_is_shadow_then_single_commit(self):
        self.driver.assert_abi()
        start = (-1, 2, -3, 4, -5, 6)
        target = (10, 20, 30, 40, 50, 60)
        self.driver.submit_q16_16(start, target, 272)

        self.assertEqual(
            self.mmio.committed,
            (
                tuple(value & 0xFFFF_FFFF for value in start),
                tuple(target),
                272,
            ),
        )
        self.assertEqual(self.mmio.writes[-1], (td.CONTROL, td.CTRL_COMMIT))
        self.assertEqual(len(self.mmio.writes), 14)

    def test_submit_rejects_invalid_data_before_shadow_write(self):
        with self.assertRaisesRegex(ValueError, "six joints"):
            self.driver.submit_q16_16((0,) * 5, (0,) * 6, 272)
        with self.assertRaisesRegex(ValueError, "period_cycles"):
            self.driver.submit_q16_16((0,) * 6, (0,) * 6, 255)
        self.assertEqual(self.mmio.writes, [])

    def test_read_and_pop_sample_preserves_signed_channel_order(self):
        joints = (-65536, -1, 0, 1, 65536, td.INT32_MAX)
        self.mmio.publish_sample(joints, index=5, last=False)
        sample = self.driver.read_sample()
        self.assertEqual(sample.index, 5)
        self.assertFalse(sample.last)
        self.assertEqual(sample.joints_q16_16, joints)

        self.driver.pop_sample()
        self.assertEqual(self.mmio.writes[-1], (td.CONTROL, td.CTRL_SAMPLE_POP))
        with self.assertRaisesRegex(RuntimeError, "empty"):
            self.driver.pop_sample()

    def test_status_error_decode_and_done_clear(self):
        self.mmio.words[td.ERROR_STATUS] = (1 << 2) | (1 << 4)
        self.mmio.words[td.STATUS] = td.STATUS_ERROR | td.STATUS_DONE
        with self.assertRaisesRegex(
            td.TrajectoryAxiError, "deadline_miss, commit_while_busy"
        ):
            self.driver.raise_for_error()
        self.driver.clear_done()
        self.assertFalse(self.driver.status().done)


if __name__ == "__main__":
    unittest.main()

