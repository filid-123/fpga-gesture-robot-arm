"""Read-only reset-state checks before the simulator board test owns PL."""
from dataclasses import asdict
import bootstrap
import arm_backend as ab
import planner_axi_driver as pd
import planner_p2p_reference as pr
import s4_task_reference as m


def read_board_state(arm, plan, s4):
    a, p, s = arm.status(), plan.status(), s4.status()
    errors = [e.name for e in plan.errors()]
    checks = {
        "s4_off": s.state == m.State.OFF,
        "owner_released": not s.owner_s4,
        "s1_off_idle": a.active_mode == ab.MODE_OFF and not a.engine_busy,
        "s1_no_fault": not a.fault,
        "s2_idle": p.state == pr.PlannerState.IDLE and not p.busy and not p.computing,
        "source_s2": p.source == pd.SOURCE_S2_PLANNER,
        "s2_no_pending": not p.planner_pending and not p.trajectory_pending,
        "s2_no_previous_motion": not p.last_valid and not p.planner_moved,
        "s1_no_open_segment": not p.trajectory_segment_open,
        "s2_no_errors": not errors,
    }
    return {
        "result": "PASS" if all(checks.values()) else "FAIL",
        "board_access": True, "motion_requested": False,
        "checks": checks, "s1": asdict(a),
        "s2": {**asdict(p), "state": p.state.name, "errors": errors},
        "s4": {"raw": s.raw, "state": s.state.name, "owner_s4": s.owner_s4},
    }


def require_fresh_overlay(report):
    failed = [key for key, passed in report["checks"].items() if not passed]
    if failed:
        raise RuntimeError(
            "Board is not freshly reset (" + ", ".join(failed) + "). "
            "S2 state=" + report["s2"]["state"] + "; reload the matching BIT with "
            "board_load.py, require PASS, and prepare a fresh stopped scene before retrying. "
            "No configuration or START was written. --check-config only validates JSON."
        )


def require_planner_startable(plan):
    """Check S2 START legality again after selecting the planner source."""
    p = plan.status()
    errors = [e.name for e in plan.errors()]
    if (p.state not in (pr.PlannerState.IDLE, pr.PlannerState.DONE)
            or p.busy or p.computing or p.source != pd.SOURCE_S2_PLANNER
            or p.planner_pending or p.trajectory_pending or p.trajectory_segment_open
            or errors):
        raise RuntimeError(
            f"S2 HOME START refused before writing: state={p.state.name}, "
            f"status={p.raw:#x}, errors={errors}; stop, preserve logs and reload BIT."
        )
