"""S1 additions to the trajectory driver; the original 4 baseline tests are unchanged."""

import unittest

import trajectory_axi_driver as td


class FakeMMIO:
    def __init__(self, abi):
        self.words = {td.ABI_VERSION: abi, td.MIN_PERIOD_CYCLES: 256, td.STATUS: td.STATUS_CMD_READY,
                      td.SAMPLE_META: td.META_VALID | 1}
        self.writes = []

    def read(self, offset):
        return self.words.get(offset, 0)

    def write(self, offset, value):
        self.writes.append((offset, value))
        self.words[offset] = value


class ExternalSinkTests(unittest.TestCase):
    def test_default_abi_is_unchanged(self):
        driver = td.TrajectoryAxiDriver(FakeMMIO(td.TRAJECTORY_ABI_VERSION))
        driver.assert_abi()
        self.assertFalse(driver.external_sink)
        with self.assertRaises(RuntimeError):
            td.TrajectoryAxiDriver(FakeMMIO(td.TRAJECTORY_ABI_VERSION_EXT_SINK)).assert_abi()

    def test_ext_sink_accepts_3002_and_refuses_pop(self):
        mmio = FakeMMIO(td.TRAJECTORY_ABI_VERSION_EXT_SINK)
        driver = td.TrajectoryAxiDriver(mmio, expected_abi=td.TRAJECTORY_ABI_VERSION_EXT_SINK)
        driver.assert_abi()
        self.assertTrue(driver.external_sink)
        driver.submit_q16_16((0,) * 6, (1,) * 6, 1_000_000)
        self.assertEqual(mmio.writes[-1], (td.CONTROL, td.CTRL_COMMIT))
        sample = driver.read_sample()          # monitor read is still allowed
        self.assertEqual(sample.index, 1)
        with self.assertRaises(RuntimeError):
            driver.pop_sample()
        with self.assertRaises(ValueError):
            td.TrajectoryAxiDriver(mmio, expected_abi=0x1234)


if __name__ == "__main__":
    unittest.main()
