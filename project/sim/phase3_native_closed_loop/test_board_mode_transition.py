import unittest
from types import SimpleNamespace
from unittest.mock import patch
import bootstrap
import arm_backend as ab
from board_loop import enter_simulator_line


class RegisterModel:
    """Independent S1 rule from arm_backend_axi_top.v REG_MODE."""
    def __init__(self):
        self.mode = ab.MODE_DRY_RUN
        self.writes = []
        self.polls = 0
        self.config_valid = True
        self.fault = False

    def set_mode(self, mode, **kwargs):
        if mode != ab.MODE_OFF and self.mode != ab.MODE_OFF and mode != self.mode:
            raise RuntimeError("AXI SLVERR: non-OFF to different non-OFF mode")
        self.writes.append((mode, kwargs))
        self.mode = mode

    def status(self):
        self.polls += 1
        return SimpleNamespace(active_mode=self.mode, engine_busy=self.polls==1,
                               config_valid=self.config_valid, fault=self.fault)


class BoardModeTransitionTests(unittest.TestCase):
    def test_old_direct_transition_is_rejected_by_register_rule(self):
        arm = RegisterModel()
        with self.assertRaisesRegex(RuntimeError, "SLVERR"):
            arm.set_mode(ab.MODE_LINE, backend=0, arm=True, permit=object())

    def test_switch_passes_off_idle_and_keeps_configuration(self):
        arm, permit = RegisterModel(), object()
        enter_simulator_line(arm, 0, permit)
        self.assertEqual([mode for mode,_ in arm.writes], [ab.MODE_OFF, ab.MODE_LINE])
        self.assertEqual(arm.polls,2)
        self.assertTrue(arm.config_valid)
        self.assertIs(arm.writes[-1][1]["permit"],permit)
        self.assertTrue(arm.writes[-1][1]["arm"])

    def test_invalid_configuration_does_not_enter_line(self):
        arm = RegisterModel()
        arm.config_valid = False
        with self.assertRaisesRegex(RuntimeError, "configuration invalid"):
            enter_simulator_line(arm, 0, object())
        self.assertEqual([m for m,_ in arm.writes],[ab.MODE_OFF])

    def test_fault_does_not_enter_line(self):
        arm = RegisterModel()
        arm.fault = True
        with self.assertRaisesRegex(RuntimeError, "S1 fault"):
            enter_simulator_line(arm, 0, object())
        self.assertEqual([m for m,_ in arm.writes],[ab.MODE_OFF])

    def test_busy_timeout_does_not_enter_line(self):
        arm = RegisterModel()
        with patch("board_loop.time.monotonic", side_effect=[0,3]):
            with self.assertRaises(TimeoutError):
                enter_simulator_line(arm, 0, object())
        self.assertEqual([m for m,_ in arm.writes],[ab.MODE_OFF])


if __name__ == "__main__":
    unittest.main()
