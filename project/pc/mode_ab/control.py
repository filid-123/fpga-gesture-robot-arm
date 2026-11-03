"""Atomic UI configuration and task identity, independent of HTTP and transport.

Only the FPGA owner thread calls process_one(). HTTP handlers enqueue a request
and await its actual device acknowledgement. A timeout is never a retry.
"""
from copy import deepcopy
from dataclasses import dataclass, field
import json
from pathlib import Path
import queue
import threading
import time
import uuid

CONTRACT = 'zhixing.console.bridge.v1'
A_CLASSES = ('red_cube', 'yellow_cube', 'blue_cube')
B_CLASSES = ('red_cube', 'eraser', 'small_canister')


class ControlError(RuntimeError):
    def __init__(self, code, reason, outcome='not_applied'):
        super().__init__(reason)
        self.code, self.outcome = code, outcome


def bindings(mode, rows):
    if mode not in ('A', 'B') or not isinstance(rows, list):
        raise ControlError(400, 'Invalid mode or binding list')
    if not 1 <= len(rows) <= 3:
        raise ControlError(400, 'Choose one to three objects')
    names = []
    for index, row in enumerate(rows, 1):
        if not isinstance(row, dict) or row.get('gesture') != index or type(row.get('gesture')) is not int:
            raise ControlError(400, 'Gesture IDs must be consecutive integers starting at one')
        name = row.get('object_id')
        if name not in (A_CLASSES if mode == 'A' else B_CLASSES) or name in names:
            raise ControlError(400, 'Unsupported or duplicate physical object')
        names.append(name)
    if mode == 'A' and tuple(names) != A_CLASSES:
        raise ControlError(400, 'Mode A uses the fixed red/yellow/blue mapping')
    return [{'gesture': i+1, 'object_id': name} for i, name in enumerate(names)]


@dataclass
class Request:
    payload: dict
    done: threading.Event = field(default_factory=threading.Event)
    response: dict | None = None
    error: ControlError | None = None


class Controller:
    def __init__(self, journal=None, stale_s=1.0, clock=time.monotonic):
        self.lock = threading.RLock()
        self.pending = queue.Queue(maxsize=1)
        self.clock, self.stale_s = clock, stale_s
        self.session_id = str(uuid.uuid4())
        self.journal = Path(journal) if journal else None
        if self.journal and self.journal.exists():
            raise FileExistsError('Use a new session directory; inspect prior robot state before restarting')
        self.revision, self.mode, self.active_bindings = 0, None, []
        self.snapshot, self.updated_at = None, None
        self.requests, self.inflight = {}, None
        self.last_request_id, self.last_request_outcome = None, None
        self.last_request_error=None
        self.mode_progress=None
        self.transition_fault = None
        self.origins = {}  # Physical object identities survive UI reorder and mode changes.
        self.frozen_task = None
        self.shared_red = dict(location='A_SLOT_OPERATOR_SETUP',a_gesture_disabled=False)

    def update(self, snapshot):
        with self.lock:
            self.snapshot, self.updated_at = deepcopy(snapshot), self.clock()

    def status(self):
        with self.lock:
            fresh = self.updated_at is not None and self.clock()-self.updated_at <= self.stale_s
            snap = self.snapshot or {}
            connected = bool(fresh and snap.get('source') == 'FPGA_REGISTER_SNAPSHOT' and snap.get('abi_verified'))
            idle = bool(connected and snap.get('state') == 'IDLE' and not snap.get('holding')
                        and snap.get('at_home') and not snap.get('arm_fault')
                        and snap.get('fault') == 'NONE' and not self.transition_fault
                        and not self.frozen_task and not self.inflight)
            blocked=[]
            if not connected:blocked.append('等待新鲜 FPGA 状态及正确 ABI')
            if self.inflight:blocked.append('正在处理模式配置')
            if snap.get('state')!='IDLE':blocked.append('FPGA 状态为 '+str(snap.get('state','未连接'))+'，需要 IDLE')
            if snap.get('holding'):blocked.append('夹爪仍持物')
            if not snap.get('at_home'):blocked.append('尚未回到当前模式 HOME')
            if snap.get('arm_fault') or snap.get('fault','NONE')!='NONE':blocked.append('设备故障：'+str(snap.get('fault')))
            if self.frozen_task:blocked.append('当前任务尚未结束')
            if self.transition_fault:blocked.append(self.transition_fault)
            return dict(contract=CONTRACT, session_id=self.session_id, connected=connected, idle=idle,
                        lock_block_reasons=blocked,last_request_error=self.last_request_error,mode_progress=deepcopy(self.mode_progress),
                        revision=self.revision, active_mode=self.mode,
                        gesture_bindings=deepcopy(self.active_bindings), recognized_classes=list(B_CLASSES),
                        grasp_supported_classes=list(B_CLASSES), last_request_id=self.last_request_id,
                        last_request_outcome=self.last_request_outcome, transition_fault=self.transition_fault,
                        inflight_request_id=self.inflight,
                        device=deepcopy(snap), task=deepcopy(self.frozen_task),
                        empty_sources=sorted(self.origins), snapshot_fresh=fresh,shared_red=deepcopy(self.shared_red))

    def red_snapshot(self):
        with self.lock:return deepcopy(self.shared_red)

    def red_origin(self,origin,reason):
        """Board-owner reconciliation of the single physical cube across modes."""
        with self.lock:
            if origin is None:self.origins.pop('red_cube',None)
            else:self.origins['red_cube']=deepcopy(origin)
            self._record('shared_red_origin',origin=origin,reason=reason)

    def _record(self, event, **values):
        if self.journal:
            self.journal.parent.mkdir(parents=True, exist_ok=True)
            with self.journal.open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(dict(event=event, session_id=self.session_id,
                                             monotonic_ns=time.monotonic_ns(), **values), allow_nan=False)+'\n')
                stream.flush()
                import os
                os.fsync(stream.fileno())

    def submit(self, payload, timeout_s=3.0):
        if not isinstance(payload, dict) or payload.get('contract') != CONTRACT:
            raise ControlError(400, 'Unknown bridge contract')
        request_id = payload.get('request_id')
        try:
            uuid.UUID(request_id)
        except (ValueError, TypeError, AttributeError):
            raise ControlError(400, 'A UUID request_id is required') from None
        normalized = dict(contract=CONTRACT, request_id=request_id,
                          expected_revision=payload.get('expected_revision'), mode=payload.get('mode'),
                          gesture_bindings=bindings(payload.get('mode'), payload.get('gesture_bindings')))
        with self.lock:
            if request_id in self.requests:
                request = self.requests[request_id]
                if request.payload != normalized:
                    raise ControlError(409, 'request_id already belongs to another configuration')
            else:
                if type(normalized['expected_revision']) is not int or normalized['expected_revision'] != self.revision:
                    raise ControlError(409, 'Configuration revision changed')
                if self.inflight or not self.status()['idle']:
                    raise ControlError(409, 'Wait for a fresh FPGA IDLE/HOME status')
                request = Request(deepcopy(normalized))
                # Journal before enqueueing: no unrecorded device transition is sent.
                self._record('mode_requested', payload=normalized)
                self.requests[request_id], self.inflight = request, request_id
                self.pending.put_nowait(request)
        if not request.done.wait(timeout_s):
            raise ControlError(504, 'FPGA outcome is pending; query status, do not repeat', 'unknown')
        if request.error:
            raise request.error
        return deepcopy(request.response)

    def process_one(self, board):
        """Called by the board owner; an acknowledged fixed HOME transition may move."""
        try:
            request = self.pending.get_nowait()
        except queue.Empty:
            return False
        payload = request.payload
        try:
            ack = board.configure_mode(payload['mode'], payload['gesture_bindings'])
            if (not isinstance(ack, dict) or ack.get('mode') != payload['mode']
                    or ack.get('gesture_bindings') != payload['gesture_bindings']
                    or ack.get('fpga_acknowledged') is not True or type(ack.get('motion_started')) is not bool):
                raise RuntimeError('Missing matching FPGA acknowledgement')
            if ack['motion_started']:
                transition = ack.get('home_transition', {})
                if transition.get('completed') is not True or transition.get('to_mode') != payload['mode']:
                    raise RuntimeError('HOME transition has not completed')
            with self.lock:
                self.revision += 1
                self.mode, self.active_bindings = payload['mode'], deepcopy(payload['gesture_bindings'])
                self.last_request_id, self.last_request_outcome = payload['request_id'], 'applied'
                self.last_request_error=None
                self.inflight = None
                self._record('mode_applied', payload=payload, revision=self.revision, ack=ack)
                request.response = dict(request_id=payload['request_id'], applied=True, status=self.status())
        except ControlError as exc:
            with self.lock:
                request.error = exc
                self.last_request_error=str(exc)
                self.last_request_id = payload['request_id']
                self.last_request_outcome = 'rejected' if exc.outcome == 'not_applied' else 'unknown'
                if exc.outcome != 'not_applied':
                    self.transition_fault = str(exc)
                self.inflight = None
                self._record('mode_failed', request_id=payload['request_id'], error=str(exc), outcome=exc.outcome)
        except Exception as exc:
            with self.lock:
                self.transition_fault = repr(exc)
                self.last_request_error=str(exc)
                self.inflight = None
                request.error = ControlError(503, 'Device transition requires inspection: '+str(exc), 'unknown')
                self.last_request_id, self.last_request_outcome = payload['request_id'], 'unknown'
                self._record('mode_unknown', request_id=payload['request_id'], error=repr(exc))
        finally:
            request.done.set()
        return True

    def select(self, gesture, task_id, frame):
        """Freeze identity at the actual PL selection, never from a browser click."""
        with self.lock:
            if self.mode != 'B' or self.frozen_task or self.inflight:
                raise ControlError(409, 'Cannot select a B task now')
            name = next((r['object_id'] for r in self.active_bindings if r['gesture'] == gesture), None)
            if not name:
                raise ControlError(400, 'Gesture is not bound to a supported object')
            origin = deepcopy(self.origins.get(name))
            task = dict(task_id=task_id, class_name=name, gesture=gesture,
                        revision=self.revision, kind='RESTOCK' if origin else 'DELIVERY',
                        origin=origin, frame=deepcopy(frame))
            self._record('task_selected', task=task)
            self.frozen_task = task
            return deepcopy(task)

    def complete(self, task_id, *, outcome, origin=None):
        with self.lock:
            task = self.frozen_task
            if not task or task['task_id'] != task_id or outcome not in ('completed', 'cancelled', 'fault'):
                raise ControlError(409, 'Completion does not match the active task')
            if outcome == 'completed':
                if task['kind'] == 'DELIVERY':
                    if not isinstance(origin, dict) or not origin.get('source_centre_mm') or not origin.get('plan_sha256'):
                        raise ControlError(400, 'Completed delivery needs its frozen grasp origin')
                    self.origins[task['class_name']] = deepcopy(origin)
                else:
                    del self.origins[task['class_name']]
            self._record('task_finished', task=task, outcome=outcome, origin=origin)
            if outcome == 'fault':
                self.transition_fault = 'Task fault; inspect actual pose and held object before a new session'
            self.frozen_task = None
