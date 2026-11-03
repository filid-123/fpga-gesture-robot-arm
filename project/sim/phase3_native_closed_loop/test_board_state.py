import json
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import bootstrap
import arm_backend_axi_driver as ad
import planner_axi_driver as pd
import planner_p2p_reference as pr
import s4_task_axi_driver as sd
from board_state import read_board_state, require_fresh_overlay, require_planner_startable
import board_loop


def devices():
    arm = Mock(spec=ad.ArmBackendAxiDriver)
    arm.status.return_value = ad.ArmBackendStatus(
        raw=8, config_valid=False, engine_busy=False, permission=False,
        estop_ok=True, fault=False, feedback_valid=False, snapshot_valid=False,
        irq=False, core_state=0, active_mode=0, active_backend=0)
    plan = Mock(spec=pd.PlannerAxiDriver)
    plan.status.return_value = pd.PlannerStatus(
        raw=0, state=pr.PlannerState.IDLE, busy=False, computing=False,
        planner_pending=False, trajectory_pending=False, last_valid=False,
        source=1, done=False, irq=False, trajectory_segment_open=False,
        planner_moved=False, error_channel=0)
    plan.errors.return_value = []
    s4 = Mock(spec=sd.S4TaskAxiDriver)
    s4.status.return_value = sd.S4Status(0x3000)
    return arm, plan, s4


class BoardStateTests(unittest.TestCase):
    def test_reset_state_passes_without_writes_or_clearing_events(self):
        arm, plan, s4 = devices()
        report = read_board_state(arm, plan, s4)
        require_fresh_overlay(report)
        self.assertEqual(report["result"], "PASS")
        self.assertFalse(report["motion_requested"])
        arm.write.assert_not_called()
        plan.clear.assert_not_called()
        s4.events.assert_not_called()

    def test_previous_run_estop_is_rejected_even_with_s4_off_and_s1_off(self):
        arm, plan, s4 = devices()
        plan.status.return_value = replace(plan.status.return_value,
            state=pr.PlannerState.ESTOP, source=1, last_valid=True, planner_moved=True)
        plan.errors.return_value = [pr.PlannerError.ESTOP]
        report = read_board_state(arm, plan, s4)
        with self.assertRaisesRegex(RuntimeError, "S2 state=ESTOP"):
            require_fresh_overlay(report)
        self.assertEqual(report["s2"]["errors"], ["ESTOP"])

    def test_block_pending_motion_busy_error_and_wrong_source(self):
        for changes in ({"planner_pending":True}, {"trajectory_pending":True},
                        {"trajectory_segment_open":True}, {"busy":True},
                        {"computing":True}, {"source":0}, {"last_valid":True},
                        {"state":pr.PlannerState.DONE}):
            with self.subTest(changes=changes):
                arm, plan, s4 = devices()
                plan.status.return_value = replace(plan.status.return_value, **changes)
                with self.assertRaises(RuntimeError):
                    require_fresh_overlay(read_board_state(arm, plan, s4))

    def test_block_s1_active_fault_and_s4_owned(self):
        for changes in ({"active_mode":1}, {"engine_busy":True}, {"fault":True}):
            with self.subTest(changes=changes):
                arm, plan, s4 = devices()
                arm.status.return_value = replace(arm.status.return_value, **changes)
                with self.assertRaises(RuntimeError):
                    require_fresh_overlay(read_board_state(arm, plan, s4))
        arm, plan, s4 = devices()
        s4.status.return_value = sd.S4Status(1 << 7)
        with self.assertRaises(RuntimeError):
            require_fresh_overlay(read_board_state(arm, plan, s4))

    def test_start_guard_accepts_idle_and_done_only_with_selected_empty_source(self):
        for state in (pr.PlannerState.IDLE, pr.PlannerState.DONE):
            _, plan, _ = devices()
            plan.status.return_value = replace(plan.status.return_value, source=1, state=state)
            require_planner_startable(plan)
        for state in (pr.PlannerState.ESTOP, pr.PlannerState.ERROR, pr.PlannerState.RUN):
            _, plan, _ = devices()
            plan.status.return_value = replace(plan.status.return_value, source=1, state=state)
            with self.assertRaisesRegex(RuntimeError, "before writing"):
                require_planner_startable(plan)
            plan.start.assert_not_called()

    def run_rejected_main(self, check_only):
        arm, plan, s4 = devices()
        plan.status.return_value = replace(plan.status.return_value, state=pr.PlannerState.ESTOP)
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)/"rejected"
            argv = ["board_loop.py", "--config", str(bootstrap.HERE/"examples/SIMULATION_CONFIG.json"),
                    "--mode", "A", "--out", str(out)]
            argv += ["--check-board"] if check_only else ["--confirm-no-robot"]
            with patch("sys.argv", argv), patch.object(ad.ArmBackendAxiDriver, "from_pynq", return_value=arm), \
                    patch.object(pd.PlannerAxiDriver, "from_pynq", return_value=plan), \
                    patch.object(sd.S4TaskAxiDriver, "from_pynq", return_value=s4), patch("builtins.print"):
                if check_only:
                    with self.assertRaises(SystemExit) as caught:
                        board_loop.main()
                    self.assertEqual(caught.exception.code,1)
                else:
                    with self.assertRaisesRegex(RuntimeError, "S2 state=ESTOP"):
                        board_loop.main()
                    self.assertTrue((out/"FAILURE.json").exists())
                self.assertEqual(json.loads((out/"BOARD_PREFLIGHT.json").read_text())["result"], "FAIL")
            arm.load_config.assert_not_called()
            arm.set_mode.assert_not_called()
            arm.stop.assert_not_called()
            plan.run_move.assert_not_called()
            plan.estop.assert_not_called()
            s4.command.assert_not_called()

    def test_main_rejects_before_configuration_start_and_cleanup_writes(self):
        self.run_rejected_main(False)

    def test_check_board_is_read_only_and_returns_nonzero_on_estop(self):
        self.run_rejected_main(True)


if __name__ == "__main__":
    unittest.main()
