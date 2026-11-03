import unittest

import arm_backend as ab
import arm_backend_axi_driver as drv
from arm_feedback import ArmError
from arm_profile import ArmProfile, RealOutputBlocked, find_config_root
from roarm_json_reference import RoArmJsonProtocol


CONFIG = find_config_root()
RJ_FIXTURE = RoArmJsonProtocol.load(CONFIG / "protocols/fixtures/roarm_json_FIXTURE_NOT_OFFICIAL.yaml")
BENCH_RJ = ArmProfile.load(CONFIG / "arm_profiles/bench_loopback_roarm_json.yaml")


class FakeArmMMIO:
    """Minimal register model: write-lock, template/key auto-increment, commit."""

    def __init__(self):
        self.regs = {drv.ABI_VERSION: drv.ARM_BACKEND_ABI_VERSION, drv.CAPABILITIES: 0x0104_7803}
        self.template = [0] * 256
        self.keys = [0] * 128
        self.mode = 0
        self.config_valid = False
        self.writes = []
        self.snapshots = 0

    def read(self, offset):
        if offset == drv.STATUS:
            return int(self.config_valid) | ((self.mode & 3) << 12)
        if offset == drv.MODE:
            return self.mode
        return self.regs.get(offset, 0)

    def write(self, offset, value):
        self.writes.append((offset, value))
        if offset == drv.MODE:
            self.mode = value
            return
        if offset == drv.CONTROL:
            if value == drv.CTRL_CONFIG_COMMIT:
                self.config_valid = True
            elif value == drv.CTRL_FB_SNAPSHOT:
                self.snapshots += 1
            return
        if offset == drv.TEMPLATE_DATA:
            address = self.regs.get(drv.TEMPLATE_ADDR, 0)
            self.template[address] = value
            self.regs[drv.TEMPLATE_ADDR] = (address + 1) & 0xFF
        elif offset == drv.KEY_DATA:
            address = self.regs.get(drv.KEY_ADDR, 0)
            self.keys[address] = value
            self.regs[drv.KEY_ADDR] = (address + 1) & 0x7F
        else:
            self.regs[offset] = value
        self.config_valid = False


class DriverTests(unittest.TestCase):
    def setUp(self):
        self.mmio = FakeArmMMIO()
        self.driver = drv.ArmBackendAxiDriver(self.mmio, sleeper=lambda _s: None)
        self.config = ab.build_pl_config(BENCH_RJ, RJ_FIXTURE)

    def test_abi_and_capabilities(self):
        self.driver.assert_abi()
        caps = self.driver.capabilities()
        self.assertTrue(caps["has_roarm"] and caps["has_so101"])
        self.assertEqual((caps["template_depth"], caps["json_slots"], caps["min_baud_div"]), (256, 7, 16))
        self.mmio.regs[drv.ABI_VERSION] = 0x3001
        with self.assertRaises(RuntimeError):
            self.driver.assert_abi()

    def test_load_config_register_image(self):
        self.driver.load_config(self.config)
        self.driver.commit_config()
        self.assertEqual(self.mmio.template, self.config.template.ram)
        self.assertEqual(self.mmio.keys, self.config.json.parser.key_ram())
        regs = self.mmio.regs
        self.assertEqual(regs[drv.BAUD_DIV_ROARM], 868)
        self.assertEqual(regs[drv.PROGRAM_CFG], (self.config.template.req_base << 8) | (1 << 16) | (1 << 17))
        ch2 = drv.CH_BASE + 2 * drv.CH_STRIDE
        self.assertEqual(regs[ch2 + drv.CH_ZERO], 150)
        self.assertEqual(regs[ch2 + drv.CH_FLAGS], 1)
        self.assertEqual(regs[ch2 + drv.CH_SOFT_MIN], (-78643) & 0xFFFF_FFFF)
        self.assertEqual(regs[drv.JSON_DISC], 101)
        self.assertEqual(regs[drv.JSON_KEY_LEN], 0x4222222)
        self.assertTrue(self.driver.status().config_valid)

    def test_line_and_monitor_require_permit(self):
        self.driver.set_mode(ab.MODE_DRY_RUN, backend=ab.BACKEND_ROARM)
        self.assertEqual(self.mmio.mode, ab.MODE_DRY_RUN)
        for mode in (ab.MODE_MONITOR, ab.MODE_LINE):
            with self.assertRaises(RealOutputBlocked):
                self.driver.set_mode(mode, backend=ab.BACKEND_ROARM, arm=True)
        permit = ab.require_real_output(BENCH_RJ, RJ_FIXTURE, purpose="bench_loopback", confirm_no_robot=True)
        self.driver.set_mode(ab.MODE_LINE, backend=ab.BACKEND_SO101, arm=True, permit=permit)
        self.assertEqual(self.mmio.mode, 3 | (1 << 4) | (1 << 8))
        self.driver.stop()
        self.assertEqual(self.mmio.mode, 1 << 4)

    def test_snapshot_and_error_decode(self):
        regs = self.mmio.regs
        for ch in range(6):
            regs[drv.SNAP_FB_DEV + 4 * ch] = (-ch) & 0xFFFF_FFFF
            regs[drv.SNAP_CMD_DEV + 4 * ch] = 1000 + ch
        regs[drv.SNAP_FB_MASKS] = 0x3F | (0x05 << 8) | (0x20 << 16)
        regs[drv.SNAP_FB_AGE] = 7 | (9 << 16)
        regs[drv.SNAP_FB_ERR] = 0x20 | (26 << 8)
        snap = self.driver.snapshot()
        self.assertEqual(self.mmio.snapshots, 1)
        self.assertEqual(snap.fb_dev, (0, -1, -2, -3, -4, -5))
        self.assertEqual(snap.cmd_dev, tuple(1000 + ch for ch in range(6)))
        self.assertEqual((snap.valid_mask, snap.arrival_mask, snap.servo_fault_mask), (0x3F, 5, 0x20))
        self.assertEqual((snap.age_max_ticks, snap.fb_seq, snap.last_servo_error_id), (7, 9, 26))
        regs[drv.ERROR_STATUS] = (1 << ArmError.ESTOP_EVENT) | (1 << ArmError.RX_CHECKSUM)
        self.assertEqual(self.driver.errors(), [ArmError.RX_CHECKSUM, ArmError.ESTOP_EVENT])
        with self.assertRaises(drv.ArmBackendAxiError):
            self.driver.raise_for_error()
        regs[drv.LIMIT_MASK] = 0xFFFF_FF24
        self.assertEqual(self.driver.limit_mask(), 0x24)


if __name__ == "__main__":
    unittest.main()
