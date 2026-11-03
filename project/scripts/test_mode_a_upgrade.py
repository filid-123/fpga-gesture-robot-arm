"""PC-only ABI3408 loader, guards and native table checks; no hardware."""
from pathlib import Path
import argparse,json,math,sys,tempfile,unittest,contextlib,io
from unittest.mock import patch
from mode_a_upgrade_config import ROOT,ARM,PLAN,TASK,VIS,backend_config,backend_writes,task_writes,protocol
from mode_a_upgrade_profile import profile
from prepare_mode_a_upgrade_bridge import generate
from arm_frame_template import run_program
from arm_fixed_point import map_joint_vector
from run_mode_a_upgrade import configure,stop_motion,load,start_motion

CANDIDATE=ROOT/'candidate/bank1'
if not CANDIDATE.exists():CANDIDATE=ROOT/'board_evidence/mode_a_upgrade_plan_a3/bank1'


class FakeBoard:
    """Stateful backend contract: OFF acknowledgement, fresh snapshots, D5."""
    def __init__(self,plan):
        self.mode=0;self.d5=True;self.arm=False;self.off_delay=0;self.off_reads=0
        self.rows=[];self.batches=[];self.phases=[];self.seq=0
        self.actual=[v+.05 for v in plan['home_native_rad']]
        self.qdev=[round(v*10000) for v in self.actual]
        self.feedback=dict(arm_errors=0,arm_fault=False,feedback_live_valid=True,feedback_mask=63,feedback_age_at_snapshot_ms=1)
    def read(self,a,count=1):
        if a==ARM+8:
            if self.off_reads:
                self.off_reads-=1
                if not self.off_reads:self.mode=0
            return [1|32|64|(8 if self.d5 else 0)|(self.mode<<12)|(2 if self.off_reads else 0)]
        if a==TASK+0x314:return [3]
        if a==TASK+0x12c:return [63]
        if a==TASK+0x330:return [dict(self.batches)[TASK+0x330+4*i] for i in range(count)]
        if a==ARM+12:return [self.feedback['arm_errors']]
        if a==ARM+0x200:return [v&0xffffffff for v in self.qdev]+[63,(self.seq<<16)|1]
        raise ValueError(a)
    def write(self,a,v):
        if a==ARM+4:
            requested=v&3
            if requested and self.mode and requested!=self.mode:raise RuntimeError('AXI SLVERR: non-OFF mode transition')
            if not requested and self.mode and self.off_delay:self.off_reads=self.off_delay
            else:self.mode=requested
            self.arm=bool(v&256)
        self.rows.append((a,v))
    def batch(self,rows):
        self.batches.extend(rows)
        for a,v in rows:self.write(a,v)
    def observe(self,phase):
        self.phases.append(phase);self.seq+=1
        return dict(self.feedback,D5_ok=self.d5,motion_frames=0,feedback_seq=self.seq,
            planner_errors=0,raw={f'0x{PLAN+4:08x}':4})
class BoardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan=json.loads((CANDIDATE/'PLAN_NATIVE.json').read_text('utf-8'));cls.table=json.loads((CANDIDATE.parent/'S4_BANKED_CANDIDATE.json').read_text('utf-8'))
    def test_native_packet_speed_acceleration_and_all_axes(self):
        c=backend_config(self.plan);q=self.plan['paths'][0]['legs'][5]['target_q16'];values,limits,saturated=map_joint_vector(q,c.channel_maps)
        self.assertEqual((limits,saturated),(0,0))
        actual=json.loads(run_program(c.template.ram,c.template.cmd_base,device_values=values).data)
        self.assertEqual((actual['T'],actual['spd'],actual['acc']),(102,1320,66));self.assertEqual(len(actual),9)
        self.assertEqual([actual[k] for k in ('base','shoulder','elbow','wrist','roll','hand')],[v/10000 for v in values])
    def test_table_register_image_roundtrip(self):
        kps=[];segments=[]
        for address,value in task_writes(self.plan,self.table):
            if address==TASK+0x114:kps.append(value)
            if address==TASK+0x11c:segments.append(value)
        self.assertEqual(kps,[v&0xffffffff for bank in self.table['keypoint_banks'] for v in ([a for q in bank for a in q+[0,0]]+[0]*(512-8*len(bank)))])
        for i,(kp,n,na,p,flags) in enumerate(self.table['segments']):self.assertEqual(segments[2*i:2*i+2],[(flags<<24)|(p<<16)|kp,(na<<16)|n])
    def test_all_waypoint_masks_are_observe_only(self):
        w=dict(task_writes(self.plan,self.table));self.assertEqual(w[TASK+0x54]&63,0);self.assertEqual(w[TASK+0x30],0)
        self.assertEqual(self.table['abi']['task'],0x340a);self.assertEqual(profile()['arrival_mask'],0)
    def test_fixed_settle_flags_have_fast_subdivisions_and_grip_pause(self):
        values=[s[4]>>2 for s in self.table['segments']]
        self.assertIn(0,values);self.assertIn(22,values);self.assertIn(50,values)
        self.assertTrue(all(s[4]>>2==50 for s in self.table['segments'] if s[4]&1))
    def test_entire_delivery_corridor_is_already_raised(self):
        c=self.plan['layout']['common_D_mm'];self.assertEqual([c[k][2] for k in ('B','PRE','H','H_CLEAR')],[160,180,175,195])
        for r in self.plan['paths']:
            legs=r['legs'];pre=next(i for i,l in enumerate(legs) if l['label']=='PRE')
            self.assertEqual(legs[pre]['target_D_mm'],[350,215,180]);self.assertTrue(all(l['target_D_mm'][2]>=175 for l in legs[pre+1:] if l['label'].startswith('HANDOVER')))
    def test_generated_tcl_guards_and_real_images(self):
        import tkinter
        text,meta=generate(self.plan,self.table);t=tkinter.Tcl()
        t.eval('proc exit {args} {error OFFLINE_EXIT}; set argv {--check-only}')
        try:t.eval(text)
        except tkinter.TclError as e:self.assertIn('OFFLINE_EXIT',str(e))
        for a,v in backend_writes(self.plan)+task_writes(self.plan,self.table):t.call('host_guard',a,v)
        for a in meta['telemetry_addresses']:t.call('host_read_guard',a)
    def test_start_from_large_home_error_does_not_gate(self):
        f=FakeBoard(self.plan)
        with patch('run_mode_a_upgrade.time.sleep'),contextlib.redirect_stdout(io.StringIO()):
            configure(f,self.plan,self.table,lambda:None,f.observe)
        self.assertIn((TASK,1),f.rows)
        modes=[v for a,v in f.rows if a==ARM+4]
        self.assertEqual(modes,[0,3,259])
        starts=dict(f.batches);self.assertEqual(starts[PLAN+0x100],round(f.qdev[0]/10000*65536)&0xffffffff)
        self.assertEqual(f.off_reads,0)
    def test_legacy_monitor_to_line_is_rejected_by_contract(self):
        f=FakeBoard(self.plan);f.mode=2
        with self.assertRaisesRegex(RuntimeError,'SLVERR'):f.write(ARM+4,259)
    def test_query_only_keeps_arm_disabled_with_d5_already_high(self):
        f=FakeBoard(self.plan)
        with patch('run_mode_a_upgrade.time.sleep'),contextlib.redirect_stdout(io.StringIO()):
            started=configure(f,self.plan,self.table,lambda:None,f.observe,monitor_only=True)
        self.assertFalse(started);self.assertTrue(f.d5);self.assertFalse(f.arm)
        self.assertEqual([v for a,v in f.rows if a==ARM+4],[0,3])
        self.assertNotIn((PLAN,1),f.rows);self.assertNotIn((TASK,1),f.rows)
    def test_prewired_full_run_needs_no_keyboard_or_reconnection(self):
        f=FakeBoard(self.plan);arm_at_precheck=[]
        def observe(phase):
            if phase=='PRECHECK_LINE_UNARMED':arm_at_precheck.append(f.arm)
            return f.observe(phase)
        with patch('run_mode_a_upgrade.time.sleep'),patch('builtins.input',side_effect=AssertionError('No Enter allowed')),contextlib.redirect_stdout(io.StringIO()):
            self.assertTrue(configure(f,self.plan,self.table,lambda:None,observe))
        self.assertEqual(arm_at_precheck,[False]*3);self.assertIn((PLAN,1),f.rows)
    def test_feedback_faults_stop_before_motion(self):
        for change in [dict(feedback_mask=31),dict(feedback_live_valid=False),dict(feedback_age_at_snapshot_ms=501),dict(arm_errors=1)]:
            with self.subTest(change=change):
                f=FakeBoard(self.plan);f.feedback.update(change)
                with patch('run_mode_a_upgrade.time.sleep'),contextlib.redirect_stdout(io.StringIO()):
                    with self.assertRaisesRegex(RuntimeError,'PRECHECK|backend'):configure(f,self.plan,self.table,lambda:None,f.observe,monitor_only=True)
                self.assertNotIn((PLAN,1),f.rows)
    def test_d5_low_at_launch_is_rejected_without_writes(self):
        f=FakeBoard(self.plan);f.d5=False
        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(RuntimeError,'not high at launch'):configure(f,self.plan,self.table,lambda:None,f.observe,monitor_only=True)
        self.assertEqual(f.rows,[])
    def test_wrong_active_mode_times_out_without_switching_rx(self):
        f=FakeBoard(self.plan);f.mode=2
        with patch('run_mode_a_upgrade.time.sleep'),patch('run_mode_a_upgrade.time.monotonic',side_effect=range(30)):
            with self.assertRaisesRegex(RuntimeError,'transition/feedback timeout'):start_motion(f,self.plan,lambda:None,f.observe)
        self.assertEqual(f.rows,[])
    def test_d5_loss_before_arm_does_not_start(self):
        f=FakeBoard(self.plan);f.mode=3;f.d5=False
        with self.assertRaisesRegex(RuntimeError,'D5 removed'):start_motion(f,self.plan,lambda:None,f.observe)
        self.assertEqual(f.rows,[])
    def test_uart_framing_is_named_and_not_silently_cleared(self):
        f=FakeBoard(self.plan);f.feedback['arm_errors']=64
        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(RuntimeError,'0x00000040.*UART_FRAMING'):
                configure(f,self.plan,self.table,lambda:None,f.observe)
        self.assertNotIn((ARM,2),f.rows);self.assertNotIn((PLAN,1),f.rows)
    def test_d5_loss_during_query_does_not_arm(self):
        f=FakeBoard(self.plan)
        def observe(phase):f.d5=False;return f.observe(phase)
        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(RuntimeError,'D5 removed'):
                configure(f,self.plan,self.table,lambda:None,observe)
        self.assertNotIn((ARM+4,259),f.rows)
    def test_tcl_boot_guard_requires_prewired_d5_and_unarmed_off(self):
        import tkinter
        text,_=generate(self.plan,self.table);t=tkinter.Tcl()
        t.eval('proc exit {args} {error OFFLINE_EXIT};set argv {--check-only}')
        try:t.eval(text)
        except tkinter.TclError:pass
        t.call('board_boot_guard',8,0,0)
        for status,mode,task in [(0,0,0),(8,259,0),(0x3008,0,0),(8,0,128),(12,0,0),(10,0,0)]:
            with self.subTest(status=status,mode=mode,task=task):
                with self.assertRaises(tkinter.TclError):t.call('board_boot_guard',status,mode,task)
    def test_tcl_snapshot_refresh_respects_pl_ownership(self):
        import tkinter
        text,_=generate(self.plan,self.table);t=tkinter.Tcl()
        t.eval('proc exit {args} {error OFFLINE_EXIT};set argv {--check-only}')
        try:t.eval(text)
        except tkinter.TclError:pass
        t.eval('set owner 0;set captures {};proc rd {a} {global owner;if {$a==0x43c50004} {return $owner};return 0};proc wr {a v} {global captures;lappend captures [list $a $v]}')
        result=t.call('board_telemetry_snapshot')
        self.assertEqual(len(result),len(__import__('prepare_mode_a_upgrade_bridge').ADDRS))
        self.assertEqual(t.eval('llength $captures'),'1')
        self.assertEqual(t.eval('lindex $captures 0'),'0x43C30000 4')
        t.eval('set owner 128;set captures {}');t.call('board_telemetry_snapshot')
        self.assertEqual(t.eval('llength $captures'),'0')
    def test_shutdown_releases_owner_before_backend_write(self):
        class Fake:
            def __init__(self):self.state=128|4;self.rows=[]
            def read(self,a):return [self.state]
            def write(self,a,v):
                if a==ARM+4:self.assert_off()
                self.rows.append((a,v))
                if (a,v)==(TASK,64):self.state=128|10
                if (a,v)==(TASK,2):self.state=0
            def assert_off(self):
                if self.state&128:raise AssertionError('Backend touched while owned')
        f=Fake();stop_motion(f);self.assertEqual(f.rows,[(TASK,64),(TASK,2),(ARM+4,0)])
    def test_no_fabricated_firmware_or_new_calibration(self):
        self.assertIsNone(protocol().firmware_version);self.assertFalse(self.plan['physical_validated'])
    def test_interaction_timers_are_pre_only_and_fist_continuous(self):
        w=dict(task_writes(self.plan,self.table));pr=profile()
        self.assertEqual([w[TASK+x] for x in (0x28,0x124,0x128,0x2c,0x34)],[100000,1000,2000,500,0])
        self.assertTrue(pr['blind_after_pre_palm'])
        self.assertGreater(w[TASK+0xb0+20],w[TASK+0xb0])
        self.assertGreater(w[TASK+0xc8+20],w[TASK+0xc8])
    def test_grip_and_transit_timing_are_faster_within_native_envelope(self):
        route=self.plan['paths'][0];legs={l['label']:l for l in route['legs']}
        self.assertLess(legs['HOME_OPEN']['seconds'],5)
        self.assertLess(legs['GRASP']['seconds'],3)
        self.assertLess(route['seconds'],55)
        self.assertLess(self.plan['validation']['max_velocity_deg_s'],profile()['native_speed_deg_s'])
    def test_time_units_cover_planned_profile(self):
        p=profile();self.assertGreater(p['native_speed_deg_s'],p['planned_speed_deg_s']);self.assertGreater(p['native_acceleration_deg_s2'],self.plan['validation']['max_acceleration_difference_deg_s2'])

    def test_decode_bank_lock_and_pixel_fields_from_pl(self):
        from mode_a_terminal import demo
        from run_mode_a_upgrade import decode_v2
        raw=next(demo())['raw'];raw[f'0x{TASK+16:08x}']=0x340a
        fields={TASK+0x31c:(2<<2)|(1<<11),TASK+0x320:(1<<31)|(1<<30)|(2<<16)|(2<<8),TASK+0x318:123,VIS+0x20:20|(30<<16),VIS+0x24:40|(70<<16)}
        fields.update({PLAN+12:0x3203,VIS+8:0x3506,TASK+0x324:32|(48<<8),**{VIS+x:0 for x in (0x200,0x204,0x208,0x20c,0x210,0x214)}});raw.update({f'0x{k:08x}':v for k,v in fields.items()});v=decode_v2(raw)
        self.assertEqual((v['align_bank'],v['align_locked_cell'],v['align_candidate_cell'],v['hand_map_revision']),(2,2,2,123))
        self.assertTrue(v['align_locked']);self.assertEqual(v['bbox_center_px'],[30,50])

    def test_failed_map_commit_or_incomplete_bank_never_arms(self):
        for flags,banks in ((9,63),(3,30)):
            f=FakeBoard(self.plan);original=f.read
            def read(a,count=1):
                if a==TASK+0x314:return [flags]
                if a==TASK+0x12c:return [banks]
                return original(a,count)
            f.read=read
            with patch('run_mode_a_upgrade.time.sleep'),contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(RuntimeError,'hand-map rejected|banks not ready'):configure(f,self.plan,self.table,lambda:None,f.observe)
            self.assertNotIn((ARM+4,259),f.rows);self.assertNotIn((PLAN,1),f.rows)

    def test_shared_table_duration_and_geometry_banks(self):
        base=[]
        for bank in range(4):
            p=json.loads((CANDIDATE.parent/('bank'+str(bank))/'PLAN_NATIVE.json').read_text('utf-8'))
            self.assertEqual(p['layout']['common_D_mm']['H'],[285,[135,195,255,255][bank],175])
            self.assertEqual(p['layout']['common_D_mm']['PRE'],[350,[155,215,275,275][bank],180])
            self.assertEqual(p['layout']['slots_D_mm'],self.plan['layout']['slots_D_mm'])
            for route in p['paths']:
                self.assertEqual(sum(l['n'] for l in route['legs']),len(route['samples']))
                for leg in route['legs']:self.assertEqual(leg['period_cycles'],2_000_000)
            base.append([l['target_q16'] for l in p['paths'][0]['legs'][:14]])
        self.assertEqual(base[0],base[1]);self.assertEqual(base[1],base[2])

    def test_fixed_thresholds_need_no_sampling(self):
        from mode_a_upgrade_config import default_map,validate_map
        from mode_a_upgrade_profile import image_step
        m=default_map();self.assertFalse(m['calibrated']);self.assertIs(validate_map(m),m)
        self.assertEqual([image_step(y) for y in (16,44,54,64,74,84,111)],[64,64,48,32,16,0,0])
        self.assertEqual([c['bank'] for c in m['cells']],[1])
        self.assertEqual(m['steps'],64)

    def test_four_bank_map_rejects_changed_thresholds(self):
        from mode_a_upgrade_config import default_map,validate_map
        m=default_map();m['cells'][0]['y0']=87
        with self.assertRaises(ValueError):validate_map(m)

    def test_all_sixteen_pair_timings_roundtrip(self):
        w=dict(task_writes(self.plan,self.table))
        for i,p in enumerate(self.table['align_pairs']):self.assertEqual(w[TASK+0x330+4*i],(p['na']<<16)|p['n'])
        self.assertLess(self.table['align_pairs'][1]['n'],self.table['align_n'])

    def test_startup_and_task_limits_cover_the_new_speed(self):
        f=FakeBoard(self.plan)
        with patch('run_mode_a_upgrade.time.sleep'),contextlib.redirect_stdout(io.StringIO()):
            configure(f,self.plan,self.table,lambda:None,f.observe)
        writes=dict(f.batches)
        vmax=math.ceil(math.radians(74.25)*.02*65536)+2
        amax=math.ceil(math.radians(326.7)*.02**2*(1<<32))+2
        for ch in range(6):
            self.assertEqual(writes[PLAN+0x108+32*ch],vmax)
            self.assertEqual(writes[PLAN+0x10c+32*ch],amax)

    def test_held_cancellation_selects_return_instead_of_hold(self):
        w=dict(task_writes(self.plan,self.table))
        self.assertEqual(w[TASK+0x24],0x000e8102)
        self.assertFalse(self.table['hold_policy'])
        self.assertEqual(profile()['cancel_policy'],'RETRACE_RETURN_TO_SLOT_THEN_HOME')

    def test_only_pre_shift_and_other_common_points_retained(self):
        points=self.plan['layout']['common_D_mm']
        self.assertEqual(points['B'],[360,200,160]);self.assertEqual(points['PRE'],[350,215,180])
        self.assertEqual(points['H'],[285,195,175]);self.assertEqual(points['H_CLEAR'],[285,195,195])
        for route in self.plan['paths']:
            pre=next(l for l in route['legs'] if l['label']=='PRE')
            self.assertEqual(pre['tool_tilt_deg'],40)

    def test_return_telemetry_overrides_forward_delivery_label(self):
        from run_mode_a_upgrade import cancel_return_view
        s=dict(state='RETRACE',object=1,cancel_pending=True,progress_raw=8<<24,
            software_status_explanation='BLIND_DELIVERY_PALM_NOT_REQUIRED')
        cancel_return_view(s,self.plan)
        self.assertEqual(s['software_status_explanation'],'CANCEL_RETURN_TO_SLOT_THEN_HOME')
        self.assertTrue(s['planned_waypoint'].startswith('RETURN_'))
        self.assertEqual(s['return_stack_depth'],8)

    def test_retrace_to_idle_split_snapshot_does_not_require_waypoint(self):
        from run_mode_a_upgrade import cancel_return_view
        # v013_flow_03: RETRACE status followed by an already cleared cancel bit.
        for pending in (False,True):
            s=dict(state='RETRACE',object=0,cancel_pending=pending,progress_raw=0)
            cancel_return_view(s,self.plan)
            self.assertEqual(s['planned_waypoint'],'TRANSITION_PENDING_NEXT_SAMPLE')
            self.assertIsNone(s['planned_D_mm'])
            self.assertEqual(s['software_status_explanation'],'RETRACE_TRANSITION_SAMPLE')

    def test_cpu_memory_binding_survives_other_current_target(self):
        import tkinter
        text,_=generate(self.plan,self.table);t=tkinter.Tcl()
        t.eval('proc exit {args} {error OFFLINE_EXIT};set argv {--check-only}')
        try:t.eval(text)
        except tkinter.TclError:pass
        t.eval('proc targets {args} {return [list [dict create target_id 7 name {Cortex-A9 MPCore #0}]]};set accesses 0')
        t.eval('proc mrd {args} {if {[lrange $args 0 1] ne {-target-id 7}} {error BAD_TARGET};incr ::accesses;return 123}')
        t.eval('proc mwr {args} {if {[lrange $args 0 1] ne {-target-id 7}} {error BAD_TARGET};incr ::accesses}')
        self.assertEqual(int(t.call('rd',ARM+8)),123);t.call('wr',ARM+4,0)
        self.assertEqual(int(t.eval('set accesses')),2)

    def test_bus_failure_has_no_automatic_write_retry(self):
        import tkinter
        text,_=generate(self.plan,self.table);t=tkinter.Tcl()
        t.eval('proc exit {args} {error OFFLINE_EXIT};set argv {--check-only}')
        try:t.eval(text)
        except tkinter.TclError:pass
        t.eval('set board_cpu_target 7;set accesses 0;proc mwr {args} {incr ::accesses;error AXI_ABORT}')
        with self.assertRaises(tkinter.TclError):t.call('wr',ARM+4,0)
        self.assertEqual(int(t.eval('set accesses')),1);self.assertEqual(int(t.eval('set bus_fault')),1)

    def test_runtime_delta_buckets_are_safe_with_production_limits(self):
        from mode_a_upgrade_profile import BUCKETS,align_steps
        from mode_a_upgrade_profile import p2p
        w=dict(task_writes(self.plan,self.table))
        for upper,n in BUCKETS:
            self.assertEqual(align_steps(upper),n)
            cfg=p2p.MoveParams((0,)*6,(upper,)*6,n,n//4,1,2000000,50000000,tuple(w[TASK+0xb0+4*i] for i in range(6)),tuple(w[TASK+0xc8+4*i] for i in range(6)))
            self.assertTrue(p2p.validate(cfg,last_delivered=cfg.start).ok)

    def test_three_active_bands_keep_twelve_cm_span(self):
        from mode_a_upgrade_config import default_map
        m=default_map();w=dict(task_writes(self.plan,self.table))
        self.assertEqual(m['thresholds'],[44,64,84]);self.assertEqual(w[TASK+0x308],2)
        self.assertEqual(m['physical_H_D_mm'][-1][1]-m['physical_H_D_mm'][0][1],120)
        self.assertEqual(self.table['keypoint_banks'][2],self.table['keypoint_banks'][3])

    def test_raw_locator_preview_and_spatial_semantic_config(self):
        from mode_a_upgrade_config import vision_writes
        w=dict(vision_writes());self.assertEqual(w[VIS+0xc]&2,0)
        self.assertEqual(w[VIS+0xc]&1,1)

    def test_speed_units_match_planning_and_native_template(self):
        p=profile();self.assertAlmostEqual(p['native_speed_deg_s'],116.015625)
        self.assertEqual((p['speed_steps_s'],p['acceleration_100_steps_s2']),(1320,66))

    def test_live_locator_detected_bit_and_retarget_counter_decode(self):
        from run_mode_a_upgrade import ADDRS,decode_v2
        r={a:0 for a in ADDRS};r.update({ARM+0x10:0x3101,PLAN+12:0x3203,TASK+0x10:0x340a,VIS+8:0x3506,VIS+0x70:0x022267a9,VIS+4:1<<11,TASK+0x31c:5<<24})
        d=decode_v2(r);self.assertTrue(d['locator_detected']);self.assertEqual(d['align_retarget_count'],5)
        r[VIS+4]=1<<12;self.assertFalse(decode_v2(r)['locator_detected'])


if __name__=='__main__':unittest.main()
