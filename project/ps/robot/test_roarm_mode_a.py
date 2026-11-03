"""Offline commissioning tests; all angles/evidence here are SYNTHETIC, never deploy."""
import unittest,json,tempfile
from unittest.mock import Mock,patch
from pathlib import Path
import roarm_mode_a as a
import roarm_json_reference as rj
import arm_frame_template as aft
class CommissionTests(unittest.TestCase):
 def setUp(self):
  root=(a.ROOT/'runs').resolve();root.mkdir(exist_ok=True)
  self.tmp=tempfile.TemporaryDirectory(prefix='SYNTHETIC_roarm_test_',dir=root)
  target=Path(self.tmp.name).resolve();assert target.is_relative_to(root)
  self.addCleanup(self.tmp.cleanup);self.path=target/'session.json';a.template(self.path)
  self.c=json.loads(self.path.read_text(encoding='utf-8'))
 def complete(self):
  c=self.c;c.update(firmware_version='SYNTHETIC_OFFLINE_ONLY',serial_number='SYNTHETIC',operator='offline_test',palm_window_locator_xyxy=[20,25,100,100])
  c['measured_limits_rad']=[[-2.9,2.9],[-1.4,1.4],[.1,2.9],[-1.4,1.4],[-2.9,2.9],[1.2,3.0]]
  for i,name in enumerate(a.POSES):c['poses'][name]=[.05*(i%3),.1,1.,-.2,0.,2.8]
  for name in ['delivery_open','retreat','tray_open','tray_retreat']+[f'obj{k}_{s}' for k in (1,2,3) for s in ('above','pick')]:c['poses'][name][5]=1.4
  c['feedback_evidence']=[dict(status='SYNTHETIC_TEST_ONLY')];c['verified']={k:True for k in a.CHECKS};a.dump(self.path,c)
 def test_unknown_blocks(self):
  with self.assertRaisesRegex(ValueError,'Calibration incomplete'):a.compile_session(self.path,Path(self.tmp.name)/'instance')
 def test_native_compile_and_partial_retrace_starts(self):
  self.complete();result=a.compile_session(self.path,Path(self.tmp.name)/'instance');self.assertEqual(result['segments'],24)
  profile=a.ArmProfile.load(Path(self.tmp.name)/'instance/profile.yaml');proto=a.RoArmJsonProtocol.load(Path(self.tmp.name)/'instance/protocol.yaml')
  self.assertFalse(profile.missing_for_real_output());a.ab.require_real_output(profile,proto,purpose='robot')
  cfg,tables=a.build_tables(self.c)
  for k in (1,2,3):
   paths=[tables.approach[k],tables.grasp[k],tables.lift[k],tables.deliver,tables.release,tables.retreat]
   start=tables.keypoints[cfg.home_kp]
   for first,count in paths:
    for kp,n,na,prof,flags in tables.segments[first:first+count]:
     target=tables.keypoints[kp]
     for partial in (start,tuple((x+y)//2 for x,y in zip(start,target)),target):
      for end in (target,start):
       move=a.pr.MoveParams(partial,end,n,na,prof,cfg.period_cycles,cfg.stall_cycles,cfg.vmax,cfg.amax)
       verdict=a.pr.validate(move);self.assertIsNone(verdict.error,str(verdict))
     start=target
  backend=a.ab.build_pl_config(profile,proto,prime_period_ms=100)
  self.assertEqual(backend.prime_period_cycles,10000000)
  command=json.loads(rj.encode_command(proto,'set_joints',[0,1000,10000,-2000,0,28000]))
  self.assertEqual(command,dict(T=102,base=0,shoulder=.1,elbow=1,wrist=-.2,roll=0,hand=2.8,spd=200,acc=10))
  feedback=rj.parse_feedback_line(proto,b'{"T":1051,"b":0.1,"s":0.2,"e":1.23,"t":-0.3,"r":0,"g":2.8}\n')
  self.assertEqual(feedback.valid_mask,63)
 def test_gripper_direction_and_vendor_limits(self):
  self.complete();self.c['poses']['delivery_open'][5]=2.9;a.dump(self.path,self.c)
  with self.assertRaisesRegex(ValueError,'decrease to open'):a.compile_session(self.path,Path(self.tmp.name)/'instance')
  self.complete();self.c['measured_limits_rad'][2]=[-.2,2.9];a.dump(self.path,self.c)
  with self.assertRaisesRegex(ValueError,'native documented envelope'):a.compile_session(self.path,Path(self.tmp.name)/'instance')
 def test_commission_requires_stop_limits_and_feedback(self):
  self.complete();self.c['verified']['surrogate_palm_tested']=False;a.dump(self.path,self.c)
  with self.assertRaises(ValueError):a.compile_session(self.path,Path(self.tmp.name)/'instance')
  a.compile_session(self.path,Path(self.tmp.name)/'instance',commission=True)
  self.c['verified']['power_stop_tested']=False;a.dump(self.path,self.c)
  with self.assertRaises(ValueError):a.compile_session(self.path,Path(self.tmp.name)/'instance',commission=True)
 def test_readonly_monitor_and_mode_drain(self):
  arm=Mock();task=Mock();task.status.return_value.owner_s4=False
  with patch.object(a,'board',return_value=(arm,Mock(),task,Mock())):
   a.monitor(0)
  args=arm.set_mode.call_args
  self.assertEqual(args.args[0],a.ab.MODE_MONITOR)
  self.assertEqual(args.kwargs['permit'].purpose,'robot_readonly')
  self.assertNotIn('arm',args.kwargs)
  arm.status.side_effect=[Mock(active_mode=a.ab.MODE_MONITOR,engine_busy=True),Mock(active_mode=a.ab.MODE_OFF,engine_busy=False)]
  a.stop_backend(arm)
  self.assertEqual(arm.status.call_count,2)
 def test_failed_recompile_blocks_both_motion_entrypoints(self):
  self.complete();out=Path(self.tmp.name)/'instance';a.compile_session(self.path,out)
  self.assertFalse((out/'COMPILATION_INCOMPLETE').exists())
  self.c['poses']['delivery_open'][5]=2.9;a.dump(self.path,self.c)
  with self.assertRaises(ValueError):a.compile_session(self.path,out)
  with patch.object(a,'board') as hardware:
   with self.assertRaisesRegex(ValueError,'compile failed/incomplete'):a.run(out,0)
   with self.assertRaisesRegex(ValueError,'compile failed/incomplete'):a.route_test(out,'empty',1)
   hardware.assert_not_called()
  self.complete();a.compile_session(self.path,out)
  self.assertFalse((out/'COMPILATION_INCOMPLETE').exists())
 def test_without_tray_keeps_all_real_motion_prerequisites(self):
  self.complete();out=Path(self.tmp.name)/'instance';a.compile_session(self.path,out)
  with patch.object(a,'board',side_effect=RuntimeError('OFFLINE_BOARD_BOUNDARY')) as hardware:
   with self.assertRaisesRegex(RuntimeError,'OFFLINE_BOARD_BOUNDARY'):a.run(out,0,without_tray=True)
   hardware.assert_called_once()
  self.c['verified']['tray_route_tested']=False;a.dump(self.path,self.c)
  a.compile_session(self.path,out,commission=True)
  with patch.object(a,'board') as hardware:
   with self.assertRaisesRegex(ValueError,'checks incomplete'):a.run(out,0,without_tray=True)
   hardware.assert_not_called()
 def test_empty_tray_visits_tray_with_open_gripper_without_claiming_empty_pass(self):
  self.complete();self.c['poses']['home'][5]=self.c['poses']['delivery_open'][5]
  self.c['verified']['all_empty_routes_tested']=False;a.dump(self.path,self.c)
  out=Path(self.tmp.name)/'instance';a.compile_session(self.path,out,commission=True)
  arm=Mock();plan=Mock();task=Mock();task.status.return_value.state=a.m.State.OFF
  arm.status.return_value.permission=True
  arm.snapshot.return_value=Mock(valid_mask=63,age_max_ticks=0,servo_fault_mask=0,arrival_mask=63,
    fb_dev=tuple(round(v*10000) for v in self.c['poses']['home']))
  delivered=[tuple(a.rad_to_q16_16(v) for v in self.c['poses']['home'])];targets=[]
  def move(params,**kwargs):targets.append(params.target);delivered[0]=params.target
  plan.run_move.side_effect=move;plan.last_delivered.side_effect=lambda:delivered[0]
  with patch.object(a,'board',return_value=(arm,plan,task,Mock())),patch.object(a,'stop_backend'),patch.object(a,'drain_delivered'),patch.object(a.time,'sleep'):
   a.route_test(out,'empty-tray',1)
  opened=a.rad_to_q16_16(self.c['poses']['delivery_open'][5])
  self.assertTrue(all(p[5]==opened for p in targets))
  tray=tuple(a.rad_to_q16_16(v) for v in self.c['poses']['tray_drop'][:5])+(opened,)
  self.assertIn(tray,targets)
  self.assertEqual(targets[-1],tuple(a.rad_to_q16_16(v) for v in self.c['poses']['home']))
  self.assertFalse(json.loads(self.path.read_text())['verified']['all_empty_routes_tested'])
  plan.estop.assert_called_once();arm.stop.assert_called()
 def test_empty_route_requires_taught_open_home_before_any_hardware_access(self):
  self.complete();out=Path(self.tmp.name)/'instance';a.compile_session(self.path,out,commission=True)
  with patch.object(a,'board') as hardware:
   with self.assertRaisesRegex(ValueError,'HOME.*open'):a.route_test(out,'empty-tray',1)
   hardware.assert_not_called()
if __name__=='__main__':unittest.main()
