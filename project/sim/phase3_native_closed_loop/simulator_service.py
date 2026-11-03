"""BENCH paths may drive UART only when its receiver is the simulator.

The production service and its physical-arm admission gate stay byte-identical.
This adapter labels the destination as virtual during admission only; all path,
digest, ownership, duplicate and PL commit checks run in the original service.
Hardware status, S4 LINE arrival monitoring and subsequent reporting stay LINE.
"""
from dataclasses import replace
import bootstrap
import s4_task_reference as m
from ps_path_service import PathServiceCore


class _AdmissionPort:
    def __init__(self, inner):
        self.inner = inner

    def status(self):
        return replace(self.inner.status(), s1_mode=m.S1_MODE_DRY_RUN)

    def __getattr__(self, name):
        return getattr(self.inner, name)


class SimulatorPathService(PathServiceCore):
    def __init__(self, *args, simulation_only=False, fixture=False, confirm_no_robot=False, **kwargs):
        if not (simulation_only and fixture and confirm_no_robot):
            raise ValueError("Simulator admission requires fixture, simulation_only and no physical robot")
        super().__init__(*args, **kwargs)
        if self.cfg.limits.status != "BENCH" or self.cfg.accepted_calibrations:
            raise ValueError("Simulator admission accepts BENCH limits without physical calibration only")

    def _on_submit(self, payload):
        actual = self.port
        self.port = _AdmissionPort(actual)
        try:
            return super()._on_submit(payload)
        finally:
            self.port = actual
