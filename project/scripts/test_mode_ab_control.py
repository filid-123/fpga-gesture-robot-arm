"""Adversarial configuration/identity tests. FakeBoard is explicitly no hardware."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pc.mode_ab.control import A_CLASSES, B_CLASSES, CONTRACT, Controller, ControlError


class FakeBoard:
    def __init__(self, fail=None):
        self.calls, self.fail = [], fail

    def configure_mode(self, mode, rows):
        self.calls.append((mode, copy.deepcopy(rows)))
        if self.fail:
            raise self.fail
        return dict(mode=mode, gesture_bindings=rows, fpga_acknowledged=True, motion_started=False)


def payload(mode='B', names=B_CLASSES, revision=0):
    return dict(contract=CONTRACT, request_id=str(uuid.uuid4()), expected_revision=revision, mode=mode,
                gesture_bindings=[dict(gesture=i+1, object_id=n) for i, n in enumerate(names)])


class Tests(unittest.TestCase):
    def setUp(self):
        self.now = 5.
        self.c = Controller(clock=lambda: self.now)
        self.snapshot = dict(source='FPGA_REGISTER_SNAPSHOT', abi_verified=True, state='IDLE',
                             holding=False, at_home=True, arm_fault=False, fault='NONE')
        self.c.update(self.snapshot)

    def enqueue(self, request):
        with self.assertRaises(ControlError) as cm:
            self.c.submit(request, timeout_s=0)
        self.assertEqual(cm.exception.outcome, 'unknown')

    def apply(self, request=None, board=None):
        request = request or payload(revision=self.c.revision)
        board = board or FakeBoard()
        self.enqueue(request)
        self.c.process_one(board)
        return self.c.submit(request, timeout_s=0), board

    def test_http_timeout_does_not_apply_or_resubmit(self):
        p = payload()
        self.enqueue(p)
        self.assertIsNone(self.c.status()['active_mode'])
        self.enqueue(p)
        b = FakeBoard()
        self.c.process_one(b)
        self.assertFalse(self.c.process_one(b))
        self.assertTrue(self.c.submit(p, 0)['applied'])
        self.assertEqual(len(b.calls), 1)

    def test_all_ordered_mapping_is_acknowledged(self):
        p = payload(names=('eraser', 'red_cube'))
        result, b = self.apply(p)
        self.assertEqual(result['status']['gesture_bindings'], p['gesture_bindings'])
        self.assertEqual(result['status']['revision'], 1)
        self.assertEqual(b.calls, [('B', p['gesture_bindings'])])

    def test_no_device_status_is_not_connected(self):
        self.assertFalse(Controller().status()['connected'])
        self.c.update(dict(self.snapshot, source='OFFLINE_REPLAY'))
        self.assertFalse(self.c.status()['connected'])

    def test_stale_status_blocks_switch(self):
        self.now += 1.01
        self.assertFalse(self.c.status()['connected'])
        with self.assertRaises(ControlError):
            self.c.submit(payload(), 0)

    def test_idle_requires_home_no_payload_and_no_fault(self):
        for change in [dict(at_home=False), dict(holding=True), dict(state='RUN'),
                       dict(arm_fault=True), dict(fault='COMM')]:
            self.c.update(dict(self.snapshot, **change))
            with self.assertRaises(ControlError):
                self.c.submit(payload(), 0)

    def test_old_revision_never_reaches_board(self):
        self.apply()
        with self.assertRaises(ControlError):
            self.c.submit(payload(revision=0), 0)

    def test_request_id_cannot_change_meaning(self):
        p = payload()
        self.apply(p)
        p['gesture_bindings'].reverse()
        p['gesture_bindings'] = [dict(gesture=i+1, object_id=r['object_id']) for i, r in enumerate(p['gesture_bindings'])]
        with self.assertRaises(ControlError):
            self.c.submit(p, 0)

    def test_reject_duplicate_boolean_or_unvalidated_classes(self):
        bad = [payload(names=('red_cube', 'red_cube')), payload(names=('scissors',)),
               payload(mode='A', names=('red_cube',)), payload(names=())]
        p = payload(); p['gesture_bindings'][0]['gesture'] = True; bad.append(p)
        for p in bad:
            with self.assertRaises(ControlError):
                self.c.submit(p, 0)

    def test_gesture_race_rejected_by_device_leaves_revision(self):
        p, b = payload(), FakeBoard(ControlError(409, 'PL selected a task before DISABLE'))
        self.enqueue(p); self.c.process_one(b)
        with self.assertRaises(ControlError):
            self.c.submit(p, 0)
        self.assertEqual(self.c.revision, 0)
        self.assertEqual(self.c.status()['last_request_outcome'], 'rejected')

    def test_lost_ack_requires_inspection_and_blocks_new_request(self):
        p = payload(); self.enqueue(p)
        self.c.process_one(FakeBoard(TimeoutError('Lost readback after write')))
        self.assertEqual(self.c.status()['last_request_outcome'], 'unknown')
        self.assertFalse(self.c.status()['idle'])
        with self.assertRaises(ControlError):
            self.c.submit(payload(), 0)

    def test_origin_tracks_physical_class_across_reordering(self):
        self.apply()
        frame = dict(frame_id=12, pixel_sha256='pixels')
        task = self.c.select(1, 7, frame)
        frame['frame_id'] = 99
        self.assertEqual(task['frame']['frame_id'], 12)
        origin = dict(source_centre_mm=[650, 250, 15], plan_sha256='bound')
        self.c.complete(7, outcome='completed', origin=origin)
        self.apply(payload(names=('eraser', 'red_cube'), revision=1))
        self.assertEqual(self.c.select(2, 8, {})['kind'], 'RESTOCK')
        self.assertEqual(self.c.frozen_task['origin'], origin)
        self.c.complete(8, outcome='cancelled')
        self.assertIn('red_cube', self.c.origins)
        self.assertEqual(self.c.select(2, 9, {})['origin'], origin)
        self.c.complete(9, outcome='completed')
        self.assertNotIn('red_cube', self.c.origins)

    def test_active_task_and_unmatched_completion_cannot_mutate_configuration(self):
        self.apply(); self.c.select(1, 41, {})
        with self.assertRaises(ControlError):
            self.c.submit(payload(revision=1), 0)
        with self.assertRaises(ControlError):
            self.c.complete(40, outcome='completed')
        self.assertEqual(self.c.frozen_task['task_id'], 41)

    def test_journal_restart_never_assumes_inventory_or_pose(self):
        with tempfile.TemporaryDirectory() as temp:
            journal = Path(temp)/'session.jsonl'
            self.c = Controller(journal=journal); self.c.update(self.snapshot)
            self.apply()
            self.assertIn('mode_applied', journal.read_text('utf-8'))
            with self.assertRaises(FileExistsError):
                Controller(journal=journal)

    def test_wrong_ack_never_reports_applied(self):
        class Wrong(FakeBoard):
            def configure_mode(self, mode, rows):
                return dict(mode='A', gesture_bindings=rows, fpga_acknowledged=True, motion_started=False)
        p = payload(); self.enqueue(p); self.c.process_one(Wrong())
        self.assertIsNone(self.c.status()['active_mode'])
        self.assertEqual(self.c.status()['revision'], 0)

    def test_fixed_home_transition_must_finish_before_configuration_applies(self):
        class Switch(FakeBoard):
            def configure_mode(self, mode, rows):
                return dict(mode=mode,gesture_bindings=rows,fpga_acknowledged=True,motion_started=True,
                            home_transition=dict(completed=True,to_mode=mode))
        self.apply(board=Switch())
        self.assertEqual(self.c.status()['revision'],1)
        self.assertEqual(self.c.status()['active_mode'],'B')

    def test_unfinished_home_transition_remains_unknown_and_blocks_new_requests(self):
        class Switch(FakeBoard):
            def configure_mode(self, mode, rows):
                return dict(mode=mode,gesture_bindings=rows,fpga_acknowledged=True,motion_started=True,
                            home_transition=dict(completed=False,to_mode=mode))
        request=payload();self.enqueue(request);self.c.process_one(Switch())
        self.assertIsNotNone(self.c.status()['transition_fault'])
        self.assertEqual(self.c.status()['revision'],0)
        with self.assertRaises(ControlError):self.c.submit(payload(),0)


if __name__ == '__main__':
    unittest.main()
