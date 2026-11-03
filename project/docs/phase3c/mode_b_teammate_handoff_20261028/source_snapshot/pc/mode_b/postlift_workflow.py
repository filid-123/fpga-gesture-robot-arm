"""Transport-independent Mode B workflow using the reviewed Mode A phase order.

Emits intents only. A serial/FPGA executor supplies completion events; perception
runs at HOME and supplies a dynamic source, never one of Mode A's fixed slots.
"""
from __future__ import annotations
from dataclasses import dataclass,field
import math


@dataclass
class Workflow:
    phase: str = 'IDLE'
    holding: bool = False
    released: bool = False
    release_committed: bool = False
    source: tuple | None = None
    pending: list = field(default_factory=list)

    def start(self, *, empty):
        if self.phase!='IDLE':raise ValueError('A task is already active')
        if not empty:
            self.holding=True;self.phase='HOLDING_RECOVERY_REVIEW'
            return {'intent':'HOLD','reason':'CURRENT_PAYLOAD_MUST_BE_RESOLVED_BEFORE_EMPTY_HOME'}
        self.phase='HOME';return {'intent':'HOME'}

    def target(self, xyz, object_class):
        if self.phase!='WAIT_VISION':raise ValueError('Acquire a new target at HOME only')
        if object_class not in ('red_cube','eraser','small_canister'):raise ValueError('Unsupported grasp object')
        if len(xyz)!=3 or any(type(v) not in (int,float) or not math.isfinite(v) for v in xyz):
            raise ValueError('Finite metric source required')
        self.source=tuple(xyz);self.phase='APPROACH_CORRECTED';self.released=False;self.release_committed=False
        return {'intent':self.phase,'source':self.source,'object_class':object_class,'correction':'CURRENT_OPERATOR_ACCEPTED_GRASP_PROFILE'}

    def event(self, event):
        if event in ('COMM_LOST','ARM_FAULT','GEOMETRY_INVALID'):
            self.phase='FAULT_HOLD';self.pending=[]
            return {'intent':'NO_FURTHER_MOTION','payload_released':self.released}
        if self.phase=='FAULT_HOLD':return {'intent':'NO_FURTHER_MOTION'}
        if self.phase=='HOLDING_RECOVERY_REVIEW':return {'intent':'HOLD','reason':'SOURCE_AND_RECOVERY_NOT_ESTABLISHED'}
        if event=='RELEASE_SUBMITTED':
            if self.phase!='RELEASE':raise ValueError('Release outside delivery phase')
            self.release_committed=True;return {'intent':'WAIT_RELEASE_FEEDBACK'}
        if event=='FIST_CONFIRMED':
            if self.holding and not self.released and not self.release_committed:
                self.phase='RETURN_ORIGINAL_SOURCE'
                return {'intent':self.phase,'source':self.source,'vertical_final_descent':True}
            return {'intent':'NONE'}
        if self.phase=='PRE_WAIT':
            if event=='PRE_2S_AND_PALM_500MS':
                self.phase='DELIVER';return {'intent':'DELIVER'}
            return {'intent':'HOLD'}
        if event!='DONE':return {'intent':'NONE'}
        if self.phase=='HOME':
            self.phase='WAIT_VISION';return {'intent':'CAPTURE_AND_LOCALIZE'}
        transitions={'APPROACH_CORRECTED':'DESCEND','DESCEND':'CLOSE','CLOSE':'VERTICAL_LIFT',
                     'VERTICAL_LIFT':'INNER_HOLD','INNER_HOLD':'BUFFER','BUFFER':'PRE',
                     'PRE':'PRE_WAIT','DELIVER':'RELEASE','RELEASE':'RELEASE_CLEARANCE',
                     'RELEASE_CLEARANCE':'HAND_CLEAR','HAND_CLEAR':'RETURN_CLEAR',
                     'RETURN_CLEAR':'INNER_RETURN','INNER_RETURN':'RETURN_HOME','RETURN_HOME':'WAIT_VISION',
                     'RETURN_ORIGINAL_SOURCE':'CANCEL_RELEASE','CANCEL_RELEASE':'CANCEL_VERTICAL_CLEAR',
                     'CANCEL_VERTICAL_CLEAR':'RETURN_HOME'}
        if self.phase not in transitions:raise ValueError('Unexpected completion in '+self.phase)
        if self.phase=='CLOSE':self.holding=True
        if self.phase in ('RELEASE','CANCEL_RELEASE'):self.holding=False;self.released=True
        self.phase=transitions[self.phase]
        if self.phase=='WAIT_VISION':return {'intent':'CAPTURE_AND_LOCALIZE','previous_task_finished':True}
        return {'intent':self.phase,'source':self.source}
