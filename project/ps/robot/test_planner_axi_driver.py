import re
import unittest
from pathlib import Path

import planner_axi_driver as drv
import planner_p2p_reference as pr

OPEN = (0xFFFF_FFFF,) * 6
MOVE = pr.MoveParams((-5, 6, -7, 8, -9, 10), (100, -200, 300, -400, 500, -600), 12, 3, pr.PROFILE_TRAPEZOID,
                     2_000_000, 100_000, OPEN, OPEN)


class FakePlannerMMIO:
    """Register-level fake: lock while busy, commands, SOURCE rule, LAST_DELIVERED."""

    def __init__(self):
        self.regs = {drv.ABI_VERSION: drv.PLANNER_ABI_VERSION, drv.CAPABILITIES: 0x0200_1036}
        self.state = pr.PlannerState.IDLE
        self.source = 0
        self.last = None
        self.writes = []
        self.pending_other = False

    def read(self, offset):
        if offset == drv.STATUS and drv.STATUS in self.regs:
            return self.regs[drv.STATUS]
        if offset == drv.STATUS:
            busy = self.state in (pr.PlannerState.VALIDATE, pr.PlannerState.RUN, pr.PlannerState.PAUSED)
            return (int(self.state) | (busy << 3) | ((self.last is not None) << 7) | (self.source << 8)
                    | ((self.state == pr.PlannerState.DONE) << 9))
        if offset == drv.SOURCE_SELECT:
            return self.source
        if drv.LAST_DELIVERED <= offset < drv.LAST_DELIVERED + 24:
            return self.last[(offset - drv.LAST_DELIVERED) // 4] & 0xFFFF_FFFF
        return self.regs.get(offset, 0)

    def write(self, offset, value):
        self.writes.append((offset, value))
        if offset == drv.SOURCE_SELECT:
            if not self.pending_other:
                self.source = value & 1
        elif offset == drv.CONTROL:
            if value == drv.CMD_START and self.source == 1:
                self.state = pr.PlannerState.DONE          # completes instantly in the fake
                self.last = MOVE.target
            elif value == drv.CMD_ESTOP:
                self.state = pr.PlannerState.ESTOP
                self.regs[drv.ERROR_STATUS] = 1 << pr.PlannerError.ESTOP
            elif value == drv.CMD_CLEAR:
                self.state = pr.PlannerState.IDLE
                self.regs[drv.ERROR_STATUS] = 0
        else:
            self.regs[offset] = value


class DriverTests(unittest.TestCase):
    def setUp(self):
        self.mmio = FakePlannerMMIO()
        self.driver = drv.PlannerAxiDriver(self.mmio, sleeper=lambda _s: None)

    def test_abi_capabilities(self):
        self.driver.assert_abi()
        self.assertEqual(self.driver.capabilities(),
                         {"channels": 6, "profiles_mask": 3, "sample_bits": 16, "min_period_cycles": 512})
        self.mmio.regs[drv.ABI_VERSION] = 0x3101
        with self.assertRaises(RuntimeError):
            self.driver.assert_abi()

    def test_move_register_image(self):
        writes = dict(drv.move_register_writes(MOVE))
        self.assertEqual(writes[drv.N_SAMPLES], 12)
        self.assertEqual(writes[drv.ACCEL_SAMPLES], 3)
        self.assertEqual(writes[drv.PROFILE], 1)
        self.assertEqual(writes[drv.PERIOD_CYCLES], 2_000_000)
        ch4 = drv.CH_BASE + 4 * drv.CH_STRIDE
        self.assertEqual(writes[ch4 + drv.CH_START], (-9) & 0xFFFF_FFFF)
        self.assertEqual(writes[ch4 + drv.CH_TARGET], 500)
        self.assertEqual(len(writes), 5 + 6 * 4)

    def test_run_move_and_last_delivered(self):
        self.assertIsNone(self.driver.last_delivered())
        self.driver.select_source(drv.SOURCE_S2_PLANNER)
        status = self.driver.run_move(MOVE, timeout_s=1.0)
        self.assertEqual(status.state, pr.PlannerState.DONE)
        self.assertEqual(self.driver.last_delivered(), MOVE.target)
        self.assertEqual(self.mmio.writes[-1], (drv.CONTROL, drv.CMD_START))

    def test_source_refused_and_estop(self):
        self.mmio.pending_other = True
        with self.assertRaisesRegex(RuntimeError, "S1 segment still running"):
            self.driver.select_source(drv.SOURCE_S2_PLANNER)
        self.mmio.regs[drv.STATUS] = (1 << 6) | (1 << 12)      # stale S1 sample after a planner move
        self.mmio.source = 1
        with self.assertRaisesRegex(RuntimeError, "PL reset"):
            self.driver.select_source(drv.SOURCE_S1_TRAJECTORY)
        self.mmio.regs.pop(drv.STATUS)
        self.mmio.source = 0
        self.driver.estop()
        self.assertEqual(self.driver.status().state, pr.PlannerState.ESTOP)
        with self.assertRaises(drv.PlannerAxiError):
            self.driver.raise_for_fatal()
        self.driver.clear()
        self.assertEqual(self.driver.errors(), [])
        with self.assertRaises(ValueError):
            self.driver.select_source(2)

    def test_load_refused_while_busy(self):
        self.mmio.state = pr.PlannerState.RUN
        with self.assertRaises(RuntimeError):
            self.driver.load_move(MOVE)


class RtlConsistencyTests(unittest.TestCase):
    def test_register_offsets_match_rtl(self):
        rtl = Path(__file__).resolve().parents[2] / "rtl" / "robot" / "planner_axi_top.v"
        if not rtl.exists():
            self.skipTest("RTL not in this layout")
        text = rtl.read_text(encoding="ascii")
        regs = {name: int(value, 16) for name, value in re.findall(r"localparam \[11:0\] REG_(\w+)\s*=\s*12'h(\w+)", text)}
        expected = {"CONTROL": drv.CONTROL, "STATUS": drv.STATUS, "ERROR_STATUS": drv.ERROR_STATUS,
                    "ABI_VERSION": drv.ABI_VERSION, "CAPABILITIES": drv.CAPABILITIES, "IRQ_ENABLE": drv.IRQ_ENABLE,
                    "SOURCE_SELECT": drv.SOURCE_SELECT, "SAMPLE_INDEX": drv.SAMPLE_INDEX,
                    "LATE_COUNT": drv.LATE_COUNT, "N_SAMPLES": drv.N_SAMPLES, "ACCEL_SAMPLES": drv.ACCEL_SAMPLES,
                    "PROFILE": drv.PROFILE, "PERIOD": drv.PERIOD_CYCLES, "STALL_TIMEOUT": drv.STALL_TIMEOUT}
        self.assertEqual(regs, expected)
        self.assertIn("32'h0000_3201", text)
        errors = dict(re.findall(r"localparam integer E_(\w+)\s*=\s*(\d+);", text))
        self.assertEqual(int(errors["CONFIG_LOCKED"]), pr.PlannerError.CONFIG_LOCKED)
        self.assertEqual(int(errors["SOURCE"]), pr.PlannerError.SOURCE_CONFLICT)
        self.assertEqual(int(errors["AXI_ACCESS"]), pr.PlannerError.AXI_ACCESS)


if __name__ == "__main__":
    unittest.main()
