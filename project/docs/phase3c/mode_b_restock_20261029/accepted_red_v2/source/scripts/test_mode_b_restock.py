"""Dynamic-origin, task identity, automatic restock and real-trajectory checks."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from pc.mode_b.restock_workflow import RestockWorkflow,GraspOrigin
from prepare_mode_b_restock import create_record,bound_delivery,validate_plan,read,write,NAMES

PACKAGE=ROOT/'docs/phase3c/mode_b_teammate_handoff_20261028/objects'
PLANS=ROOT/'artifacts/phase3c/mode_b_return_20261029/plans'


def record(cls='red_cube',selection=1):
    return create_record(PACKAGE/cls/'evidence/PLAN.json',PACKAGE/cls/'evidence/RESULT.json',selection=selection)


class RestockWorkflowTests(unittest.TestCase):
    def workflow(self):
        w=RestockWorkflow();r=record('eraser',1)
        w.delivered(1,r,empty_home_completed=True);w.background()
        w.select(1,'restock-1',empty=True,at_home=True)
        return w,r

    def done(self,w):
        return w.event('restock-1','DONE',completed_phase=w.phase)

    def test_raw_source_is_frozen_and_selection_can_hold_eraser(self):
        w,r=self.workflow();expected=deepcopy(r['original_pickup']['centre_mm'])
        r['original_pickup']['centre_mm'][1]+=100
        self.assertEqual(w.active['origin'].centre_mm,tuple(expected))
        self.assertEqual(w.active['origin'].object_class,'eraser')
        self.assertEqual(w._intent()['return_centre_mm'],expected)

    def test_normal_restock_needs_no_palm_and_restores_only_after_home(self):
        w,r=self.workflow()
        self.assertEqual(w.event('restock-1','PALM_CONFIRMED'),{'intent':'NONE'})
        while w.phase!='RESTOCK_RELEASE_SOURCE':self.done(w)
        self.assertFalse(w.slots[1]['available'])
        with self.assertRaisesRegex(ValueError,'submission'):self.done(w)
        w.event('restock-1','RELEASE_SUBMITTED')
        self.done(w);self.done(w)
        self.assertEqual(w.phase,'RESTOCK_HOME')
        self.assertFalse(w.slots[1]['available'])
        result=self.done(w)
        self.assertTrue(result['inventory_restored']);self.assertFalse(result['physical_placement_verified'])
        self.assertEqual(w.restocked_tasks,1)

    def test_held_cancel_goes_public_and_keeps_original_unavailable(self):
        w,_=self.workflow()
        while w.phase!='RESTOCK_LIFT_PUBLIC':self.done(w)
        action=w.event('restock-1','FIST_CONFIRMED')
        self.assertEqual(action['intent'],'CANCEL_RETURN_PUBLIC')
        self.assertTrue(action['requires_stopped_fresh_pose'])
        self.done(w);w.event('restock-1','RELEASE_SUBMITTED');self.done(w);self.done(w)
        result=self.done(w)
        self.assertFalse(result['inventory_restored']);self.assertFalse(w.slots[1]['available'])

    def test_empty_cancel_never_closes_or_restores_stock(self):
        w,_=self.workflow()
        self.assertEqual(w.event('restock-1','FIST_CONFIRMED')['intent'],'CANCEL_EMPTY_HOME')
        self.assertFalse(self.done(w)['inventory_restored'])

    def test_release_commit_rejects_late_fist(self):
        w,_=self.workflow()
        while w.phase!='RESTOCK_RELEASE_SOURCE':self.done(w)
        w.event('restock-1','RELEASE_SUBMITTED')
        self.assertEqual(w.event('restock-1','FIST_CONFIRMED'),{'intent':'NONE'})
        self.assertEqual(w.phase,'RESTOCK_RELEASE_SOURCE')

    def test_fault_blocks_followup_and_never_restores(self):
        for fault in ('COMM_LOST','ARM_FAULT','GEOMETRY_INVALID'):
            w,_=self.workflow();w.event('restock-1',fault)
            self.assertEqual(w.event('restock-1','DONE',completed_phase='FAULT_HOLD')['intent'],'NO_FURTHER_MOTION')
            self.assertFalse(w.slots[1]['available'])

    def test_duplicate_task_phase_and_busy_selection_are_rejected(self):
        w,_=self.workflow()
        self.assertEqual(w.select(1,'other',empty=True,at_home=True)['intent'],'NONE')
        with self.assertRaisesRegex(ValueError,'Stale'):w.event('other','DONE',completed_phase=w.phase)
        old=w.phase;self.done(w)
        with self.assertRaisesRegex(ValueError,'stale'):w.event('restock-1','DONE',completed_phase=old)

    def test_rearm_and_origin_replacement_rules(self):
        r=record();w=RestockWorkflow();w.delivered(1,r,empty_home_completed=True)
        self.assertEqual(w.select(1,'new',empty=True,at_home=True)['intent'],'NONE')
        with self.assertRaisesRegex(ValueError,'replace'):w.delivered(1,record('eraser'),empty_home_completed=True)
        w.background()
        with self.assertRaisesRegex(ValueError,'empty HOME'):w.select(1,'new',empty=False,at_home=True)
        self.assertEqual(w.select(1,'new',empty=True,at_home=True)['intent'],'RESTOCK_APPROACH_PUBLIC')


class RestockOriginAndPathTests(unittest.TestCase):
    def test_origin_uses_exact_actual_grasp_feedback_separately_from_command(self):
        r=record('eraser',2);p=bound_delivery(r)
        self.assertEqual(r['original_pickup'],p['request']['pickup'])
        self.assertEqual(r['grasp_command_firmware_rad']['g'],2.95)
        self.assertIsNotNone(r['grasp_observed_firmware_rad'])
        self.assertNotEqual(r['grasp_command_firmware_rad'],r['grasp_observed_firmware_rad'])
        self.assertIn(p['request']['task_id'],r['original_task_id'])

    def test_source_or_object_or_compensation_tamper_is_rejected(self):
        for key in ('xyz','class','q','proxy'):
            r=record()
            if key=='xyz':r['original_pickup']['centre_mm'][1]+=19
            elif key=='class':r['object_class']='eraser'
            elif key=='q':r['grasp_command_firmware_rad']['s']+=.01
            else:r['original_model_source_pose'][1][3]+=10
            with self.assertRaisesRegex(ValueError,'changed|reapplied'):bound_delivery(r)

    def test_three_classes_recover_original_grasp_and_keep_local_corrections(self):
        for cls in ('red_cube','small_canister','eraser'):
            path=PLANS/cls/'RESTOCK_PLAN.json';p=read(path)
            self.assertTrue(validate_plan(path)['passed'])
            r=read(p['origin_record_file'])
            self.assertEqual(p['return_centre_mm'],r['original_pickup']['centre_mm'])
            low=next(s for s in p['stages'] if s['phase']=='RESTOCK_SOURCE_DESCEND')['stage']['target_firmware_rad']
            np.testing.assert_allclose([low[n] for n in NAMES],[r['grasp_command_firmware_rad'][n] for n in NAMES],atol=1e-9,rtol=0)
            np.testing.assert_allclose(p['released_object_pose'],r['original_model_source_pose'],atol=.002,rtol=0)
            self.assertEqual(p['public_pickup_centre_mm'][:2],[300,200])
            self.assertEqual(p['public_pickup_centre_mm'][2],{'red_cube':15,'eraser':7.5,'small_canister':23}[cls])
            self.assertFalse(p['physical_restock_accepted']);self.assertTrue(p['requires_public_area_clear'])

    def test_real_mesh_reports_match_exact_plans(self):
        from prepare_mode_b_loaded_route import digest
        for cls in ('red_cube','small_canister','eraser'):
            folder=PLANS/cls;report=read(folder/'COPPELIA_VERIFICATION.json')
            self.assertEqual(report['route_sha256'],digest(folder/'RESTOCK_PLAN.json'))
            self.assertTrue(report['passed']);self.assertEqual(report['mesh_collisions'],[])

    def test_cancel_returns_to_public_and_never_restores_original_inventory(self):
        from prepare_mode_b_loaded_route import digest
        files=list(PLANS.glob('*/cancel/*/RESTOCK_PLAN.json'))
        self.assertGreaterEqual(len(files),9)
        for path in files:
            p=read(path);self.assertTrue(validate_plan(path)['passed'])
            report=read(path.parent/'COPPELIA_VERIFICATION.json')
            self.assertEqual(report['route_sha256'],digest(path));self.assertTrue(report['passed'])
            self.assertEqual(p['return_centre_mm'][:2],[300,200])
            self.assertFalse(p['inventory_restored'])
            self.assertTrue(p['requires_stopped_fresh_pose'])
            if p['task_kind']=='RESTOCK_CANCEL_EMPTY':
                self.assertFalse(any(s['carrying'] for s in p['stages']))
                self.assertEqual(p['event_after_stage'],{})
            else:
                self.assertEqual(list(p['event_after_stage'].values())[0]['label'],'RELEASE_PUBLIC')


if __name__=='__main__':unittest.main()
