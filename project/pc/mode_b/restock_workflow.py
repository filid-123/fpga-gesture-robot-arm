"""Mode B automatic public pickup -> original dynamic source, without transport.

Unlike Mode A fixed slots, a selection owns an immutable grasp-origin record.
The executor must associate completion/fault events with the active task ID.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
import math

CLASSES = ('red_cube', 'eraser', 'small_canister')


@dataclass(frozen=True)
class GraspOrigin:
    task_id: str
    object_class: str
    centre_mm: tuple
    yaw_deg: float
    grasp_command_rad: tuple
    plan_sha256: str

    @classmethod
    def from_record(cls, record):
        source = record['original_pickup']
        xyz = tuple(source['centre_mm'])
        q = tuple(record['grasp_command_firmware_rad'][n] for n in ('b', 's', 'e', 't', 'r', 'g'))
        yaw = source['yaw_deg']
        if (record['object_class'] not in CLASSES or not record['original_task_id'] or
                len(xyz) != 3 or any(type(v) not in (int, float) or not math.isfinite(v) for v in (*xyz, *q, yaw))):
            raise ValueError('Finite original grasp record required')
        if len(record['delivery_plan_sha256']) != 64:
            raise ValueError('Bound delivery plan hash required')
        return cls(record['original_task_id'], record['object_class'], xyz, yaw, q, record['delivery_plan_sha256'])


@dataclass
class RestockWorkflow:
    """Small adapter for the task/gesture bridge; emits intents, never motion.

    Inventory is program completion state, not a claim of actual object presence.
    Unknown state after process/device reset needs explicit reconciliation.
    """
    slots: dict = field(default_factory=dict)
    phase: str = 'IDLE'
    active: dict | None = None
    armed: bool = True
    restocked_tasks: int = 0
    completed_task_ids: set = field(default_factory=set)

    def delivered(self, selection, record, *, empty_home_completed):
        if self.phase != 'IDLE' or not empty_home_completed:
            raise ValueError('Completed delivery and empty HOME required')
        if selection not in (1,2,3) or record['selection'] != selection:
            raise ValueError('Selection must match the frozen task mapping')
        origin = GraspOrigin.from_record(record)
        previous = self.slots.get(selection)
        if previous and previous['available'] is False:
            raise ValueError('Cannot replace the return origin of an absent object')
        self.slots[selection] = {'origin': origin, 'record': deepcopy(record), 'available': False}
        self.armed = False

    def background(self):
        if self.phase == 'IDLE':
            self.armed = True

    def select(self, selection, task_id, *, empty, at_home):
        if self.phase != 'IDLE' or not self.armed:
            return {'intent': 'NONE', 'reason': 'BUSY_OR_NOT_REARMED'}
        if not empty or not at_home:
            raise ValueError('Restock selection requires empty HOME')
        if selection not in self.slots:
            return {'intent': 'DYNAMIC_VISION_PICKUP', 'selection': selection}
        if not task_id or task_id in self.completed_task_ids:
            raise ValueError('Fresh unique task ID required')
        slot = self.slots[selection]
        if slot['available']:
            return {'intent': 'DYNAMIC_VISION_PICKUP', 'selection': selection}
        self.armed = False
        self.phase = 'RESTOCK_APPROACH_PUBLIC'
        self.active = {'selection': selection, 'task_id': task_id, 'origin': slot['origin'],
                       'holding': False, 'release_committed': False, 'cancelled': False}
        return self._intent()

    def _intent(self):
        a = self.active
        return {'intent': self.phase, 'task_id': a['task_id'],
                'original_task_id': a['origin'].task_id, 'object_class': a['origin'].object_class,
                'public_xy_mm': [300, 200], 'return_centre_mm': list(a['origin'].centre_mm),
                'requires_palm': False, 'requires_source_vacant': True}

    def event(self, task_id, event, *, completed_phase=None):
        if self.active is None or task_id != self.active['task_id']:
            raise ValueError('Stale or unrelated restock task event')
        a = self.active
        if event in ('COMM_LOST', 'ARM_FAULT', 'GEOMETRY_INVALID'):
            self.phase = 'FAULT_HOLD'
            return {'intent': 'NO_FURTHER_MOTION', 'task_id': task_id, 'inventory_restored': False}
        if self.phase == 'FAULT_HOLD':
            return {'intent': 'NO_FURTHER_MOTION', 'task_id': task_id}
        if event == 'RELEASE_SUBMITTED':
            if self.phase not in ('RESTOCK_RELEASE_SOURCE', 'CANCEL_RELEASE_PUBLIC'):
                raise ValueError('Release outside restock release stage')
            a['release_committed'] = True
            return {'intent': 'WAIT_RELEASE_FEEDBACK', 'task_id': task_id}
        if event == 'FIST_CONFIRMED':
            if a['release_committed'] or a['cancelled']:
                return {'intent': 'NONE'}
            a['cancelled'] = True
            self.phase = 'CANCEL_RETURN_PUBLIC' if a['holding'] else 'CANCEL_EMPTY_HOME'
            return {**self._intent(), 'requires_stopped_fresh_pose': True,
                    'unknown_or_midmotion_requires_replan': True}
        if event != 'DONE':
            return {'intent': 'NONE'}  # PALM never authorizes or delays a restock.
        if completed_phase != self.phase:
            raise ValueError('Missing, duplicate or stale restock phase completion')
        transitions = {
            'RESTOCK_APPROACH_PUBLIC': 'RESTOCK_DESCEND_PUBLIC',
            'RESTOCK_DESCEND_PUBLIC': 'RESTOCK_CLOSE_PUBLIC',
            'RESTOCK_CLOSE_PUBLIC': 'RESTOCK_LIFT_PUBLIC',
            'RESTOCK_LIFT_PUBLIC': 'RESTOCK_RETURN_SOURCE_HIGH',
            'RESTOCK_RETURN_SOURCE_HIGH': 'RESTOCK_DESCEND_SOURCE',
            'RESTOCK_DESCEND_SOURCE': 'RESTOCK_RELEASE_SOURCE',
            'RESTOCK_RELEASE_SOURCE': 'RESTOCK_WITHDRAW_SOURCE',
            'RESTOCK_WITHDRAW_SOURCE': 'RESTOCK_HOME',
            'CANCEL_RETURN_PUBLIC': 'CANCEL_RELEASE_PUBLIC',
            'CANCEL_RELEASE_PUBLIC': 'CANCEL_WITHDRAW_PUBLIC',
            'CANCEL_WITHDRAW_PUBLIC': 'CANCEL_EMPTY_HOME',
        }
        if self.phase == 'RESTOCK_CLOSE_PUBLIC':
            a['holding'] = True
        if self.phase in ('RESTOCK_RELEASE_SOURCE', 'CANCEL_RELEASE_PUBLIC'):
            if not a['release_committed']:
                raise ValueError('Release submission must precede its completion')
            a['holding'] = False
        if self.phase in ('RESTOCK_HOME', 'CANCEL_EMPTY_HOME'):
            restored = self.phase == 'RESTOCK_HOME' and not a['cancelled'] and a['release_committed']
            self.slots[a['selection']]['available'] = restored
            self.restocked_tasks += int(restored)
            self.completed_task_ids.add(task_id)
            self.phase = 'IDLE'
            self.active = None
            return {'intent': 'WAIT_NEW_GESTURE', 'inventory_restored': restored,
                    'physical_placement_verified': False, 'requires_background_rearm': True}
        if self.phase not in transitions:
            raise ValueError('Unexpected restock completion at '+self.phase)
        self.phase = transitions[self.phase]
        return self._intent()
