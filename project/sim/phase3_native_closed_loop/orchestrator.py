"""Retain S8 events arriving between service and supervisor polls.

The original mode-B supervisor drains again after PathServiceCore.step(). A
SELECTED event arriving in that gap can reach only the supervisor (task id 0)
and never generate TARGET_REQUEST. Drain once through the path service, then
consume its copy. Later hardware events remain queued until the next step.
"""
from task_orchestrator import TaskOrchestrator, EventTap


class ServiceEventTap(EventTap):
    def take(self):
        out, self.pending = self.pending, []
        return out


class SimulatorOrchestrator(TaskOrchestrator):
    def __init__(self, mode, port, service=None, **kwargs):
        super().__init__(mode, port, service, **kwargs)
        if service is not None:
            self.tap = ServiceEventTap(port)
            service.port = self.tap
