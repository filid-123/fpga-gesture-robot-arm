"""Feedback/event driven task reference. Simulation evidence is never physical evidence."""
from __future__ import annotations
import math
from .kinematics import vector
from .trajectory import quantize


class TaskMachine:
    def __init__(self, plan):
        self.plan = plan
        self.task_id = plan["task_id"]
        self.segments = plan["segments"]
        self.index = 0
        self.status = "READY"
        self.pending = None
        self.waiting = None
        self.complete = False
        self.journal = []
        self.observed_q16 = tuple(plan["start_q16"])
        self.nominal_cursor_q16 = tuple(plan["start_q16"])
        self.palm_ready_deadline_ms = None

    def next_segment(self, now_ms):
        if self.status in ("FAULT_HOLD", "CANCEL_HOLD", "COMPLETE") or self.waiting or self.pending is not None:
            return None
        if self.index >= len(self.segments):
            self.waiting = "PLACEMENT_AND_EMPTY_HOME_VERIFIED"
            return None
        s = self.segments[self.index]
        finishes_ms = now_ms+s["n"]*self.plan["period_s"]*1000
        if (s["phase"] in ("PREPLACE", "PLACE", "RELEASE") or s["phase"] == "TRANSIT_PREPLACE") and (
                self.palm_ready_deadline_ms is None or finishes_ms > self.palm_ready_deadline_ms):
            self.waiting = "PALM_READY"
            return None
        if tuple(s["start_q16"]) != self.nominal_cursor_q16:
            self.fault("PLANNED_SEGMENT_DISCONTINUITY")
            return None
        self.pending = self.index
        self.status = "RUNNING"
        self.journal.append({"event": "SEGMENT_REQUEST", "index": self.index, "phase": s["phase"]})
        return s

    def feedback(self, task_id, q_rad, *, settled, tolerance_rad=.02):
        if task_id != self.task_id or self.pending is None or self.status in ("FAULT_HOLD", "CANCEL_HOLD"):
            return False
        try:
            actual = quantize(vector(q_rad, 6, "feedback"))
        except (ValueError, TypeError):
            return False
        if not math.isfinite(tolerance_rad) or tolerance_rad < 0:
            return False
        target = self.segments[self.pending]["target_q16"]
        if not settled or any(abs(a-b) > tolerance_rad*65536 for a, b in zip(actual, target)):
            return False
        s = self.segments[self.pending]
        # Preserve measured feedback. Accepting a nominal tracking tolerance
        # never changes the measurement into the requested endpoint, nor does
        # it certify a physical swept-volume error envelope.
        self.observed_q16 = tuple(actual)
        self.nominal_cursor_q16 = tuple(s["target_q16"])
        self.journal.append({"event": "FEEDBACK_ARRIVED", "index": self.pending, "actual_q16": list(actual)})
        self.index = self.pending+1
        self.pending = None
        self.waiting = s["event_after"]
        if self.index == len(self.segments):
            self.waiting = "PLACEMENT_AND_EMPTY_HOME_VERIFIED"
        return True

    def event(self, task_id, event, now_ms, *, valid_for_ms=0, source="physical"):
        if task_id != self.task_id or self.status in ("FAULT_HOLD", "CANCEL_HOLD", "COMPLETE"):
            return False
        if event != self.waiting:
            return False
        if event == "PALM_READY":
            if not math.isfinite(valid_for_ms) or valid_for_ms <= 0 or not math.isfinite(now_ms):
                return False
            self.palm_ready_deadline_ms = now_ms+valid_for_ms
        self.journal.append({"event": event, "source": source, "now_ms": now_ms})
        self.waiting = None
        if event == "PLACEMENT_AND_EMPTY_HOME_VERIFIED":
            self.status, self.complete = "COMPLETE", True
        return True

    def cancel(self):
        # A mid-segment or unrecognised pose cannot start an endpoint branch.
        branch = None
        if self.pending is None and self.index:
            phase = self.segments[self.index-1]["phase"]
            candidate = self.plan["cancel_branches"].get(phase)
            if candidate and tuple(candidate["start_q16"]) == self.observed_q16:
                branch = candidate
        self.status = "CANCEL_HOLD"
        self.journal.append({"event": "CANCEL", "branch_available": branch is not None})
        return branch

    def fault(self, reason):
        self.status = "FAULT_HOLD"
        self.journal.append({"event": "FAULT_HOLD", "reason": reason})


def simulate_task(plan):
    machine = TaskMachine(plan)
    now = 0.
    for _ in range(len(plan["segments"])*4+10):
        if machine.waiting:
            machine.event(plan["task_id"], machine.waiting, now, valid_for_ms=3000,
                          source="SIMULATED_EVENT_NOT_PHYSICAL_EVIDENCE")
        segment = machine.next_segment(now)
        if segment:
            now += segment["n"]*plan["period_s"]*1000
            # Long traversals require a fresh delivery event before release.
            if segment["phase"] == "RELEASE" and now > machine.palm_ready_deadline_ms:
                machine.fault("SIMULATED_READY_EXPIRED_DURING_RELEASE")
                break
            machine.feedback(plan["task_id"], [v/65536 for v in segment["target_q16"]], settled=True)
        if machine.complete:
            break
    return {"complete": machine.complete, "status": machine.status, "journal": machine.journal,
            "physical_execution": False, "events_are_simulated": True}
