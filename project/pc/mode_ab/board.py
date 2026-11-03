"""Single-owner real FPGA transport, mode transitions and dynamic path commits."""
from copy import deepcopy
import json
import math
from pathlib import Path
import time
import sys
from pc.mode_ab.motion import ROOT,home
from pc.mode_ab.registers import ARM,PLAN,TASK,VIS,ADDRS,snapshot,mode_word,b_writes,fifo_writes
sys.path.insert(0,str(ROOT/'scripts'))
import run_mode_a_restock as legacy
from mode_a_restock_config import task_writes,descriptor_words
from mode_a_upgrade_profile import segment
from pc.mode_ab.control import ControlError
from pc.mode_ab.uploads import TableImage,home_b_writes


def bridge_text(plan,table):
    import prepare_mode_a_restock_bridge as parent
    saved=parent.ADDRS
    try:
        parent.ADDRS=ADDRS;text,meta=parent.generate(plan,table)
    finally:parent.ADDRS=saved
    text=text.replace('0x340b','0x340e').replace('$v ni {1 2 8 64 2048}','$v ni {1 2 8 64 256 512 1024 2048 4096}')
    writes=[TASK+0x38c,TASK+0x5c,TASK+0x68]
    text=text.replace('set board_write {','set board_write {'+' '.join(hex(a) for a in writes)+' ')
    # Mode and planner writes remain independently locked by the real PL owner.
    # Host path uploads only occur at stationary WAIT_PATH; prevent an accidental
    # partial upload from crossing into an active task between batches.
    anchor='    if {$a==0x43c30004'
    i=text.index(anchor)
    guard='''    if {$a in {0x43c5005c 0x43c50068 0x43c5038c}} {
        set s [rd 0x43c50004]
        if {($s & 15)!=2 || !([rd 0x43c50024]&1)} {error "B path requires stationary WAIT_PATH"}
    }
'''
    text=text[:i]+guard+text[i:]
    from pc.mode_ab.native_upload import extend_bridge
    text=extend_bridge(text)
    meta.update(task_abi=0x340e,version='ab0.1.0',native_route_abi=0xb001)
    return text,meta


class Board:
    def __init__(self,root,out,controller,plan,table,transitions,stop):
        self.root,self.out,self.control,self.plan,self.table=root,out,controller,plan,table
        self.transitions,self.stop=transitions,stop
        self.mode='A';self.rows=[];self.b=None;self.server=None;self.exposure=None
        self.reconcile_red=None
        self.sensor_result={};self.last=None;self.last_hb=0
        self.image=TableImage();self.upload_stats=None
        self.telemetry=(out/'telemetry.jsonl').open('x',encoding='utf-8')
        self.communication=(out/'communication.jsonl').open('x',encoding='utf-8')

    def alive(self):
        if self.stop.is_set():raise InterruptedError('Operator stopped session')

    def observe(self,phase='AUTONOMOUS'):
        self.alive();s=snapshot(self.b.telemetry())
        q=home(self.mode)
        # Exact commanded HOME is the PL permission check; actual error remains
        # visible under the inherited observe_all policy.
        s['at_home']=s['state']=='IDLE' and max(abs(a-b) for a,b in zip(s['last_delivered_rad'],q))<2/65536
        s['session_phase']=phase;s['physical_success']=None
        self.last=s;self.control.update(s)
        self.telemetry.write(json.dumps(s)+'\n');self.telemetry.flush()
        return s

    def heartbeat(self):
        if self.mode=='B' and time.monotonic()-self.last_hb>.1:
            self.b.write(TASK,1024);self.last_hb=time.monotonic()

    def batch(self,rows):
        for start in range(0,len(rows),32):
            self.alive();self.heartbeat();self.b.batch(rows[start:start+32])

    def upload(self,rows):
        sparse,image=self.image.plan(rows);started=time.perf_counter()
        try:self.batch(sparse)
        except Exception:
            self.image=TableImage();raise
        self.image=image
        self.upload_stats=dict(full_register_writes=len(rows),actual_register_writes=len(sparse),
                               elapsed_ms=(time.perf_counter()-started)*1000)

    def start(self,query_only=False):
        legacy.ADDRS=ADDRS
        Bridge,Server,self.exposure=legacy.setup_tools(self.root,self.out)
        text,meta=bridge_text(self.plan,self.table)
        (self.out/'tools/jtag_bridge.tcl').write_text(text,encoding='utf-8')
        (self.out/'tools/bridge_contract.json').write_text(json.dumps(meta,indent=2))
        self.server=Server();self.server.start();self.b=Bridge();self.b.wait_ready()
        original_call=self.b.call
        def measured(command):
            started=time.perf_counter_ns();record=dict(operation=command.split()[0],request_bytes=len(command.encode()),started_monotonic_ns=started)
            try:
                response=original_call(command);record.update(ok=True,response_bytes=len(response.encode()));return response
            except Exception as exc:
                record.update(ok=False,error=repr(exc));raise
            finally:
                record['roundtrip_ms']=(time.perf_counter_ns()-started)/1e6
                self.communication.write(json.dumps(record)+'\n');self.communication.flush()
        self.b.call=measured
        deadline=time.monotonic()+12
        while not self.b.read(VIS+0x78)[0]&2:
            self.alive()
            if time.monotonic()>deadline:raise RuntimeError('PL camera initialization incomplete')
            time.sleep(.1)
        result=self.sensor_result
        result['vts']=(self.exposure.command(self.b,result,0x380e)<<8)|self.exposure.command(self.b,result,0x380f)
        result['original_sensor']=self.exposure.freeze(self.b,result)
        result['selected_sensor']=self.exposure.apply(self.b,result,result['original_sensor'],984,80)
        from pc.mode_ab.native_backend import backend_writes as native_backend_writes
        # Existing startup owns the single board transport. Extend its OFF-only
        # configuration callback before COMMIT; restore the original afterwards.
        saved_backend=legacy.backend_writes
        try:
            legacy.backend_writes=native_backend_writes
            legacy.prepare_line_queries(self.b,self.plan,self.table,self.alive,self.observe)
        finally:legacy.backend_writes=saved_backend
        # A startup is reused; no tasks can start until the HTML configuration
        # has received a matching acknowledgement.
        self.b.write(TASK+0x24,0x8102)
        if query_only:return self.observe('QUERY_ONLY_NO_MOTION')
        legacy.start_motion(self.b,self.plan,self.alive,self.observe)
        # The inherited startup has just loaded exactly these A RAM words.
        _,self.image=self.image.plan(task_writes(self.plan,self.table))
        return self.observe('READY_FOR_HTML_LOCK')

    def await_state(self,state,timeout=5):
        deadline=time.monotonic()+timeout
        while True:
            s=self.observe('MODE_SWITCH')
            if s['arm_fault'] or s['fault']!='NONE':raise RuntimeError('Mode transition fault')
            if s['state']==state:return s
            if time.monotonic()>deadline:raise TimeoutError('FPGA state transition timeout')
            time.sleep(.02)

    def move(self,leg):
        from run_mode_a_restock import math_ceil_velocity,math_ceil_acceleration
        writes=[[PLAN+0x40,leg['n']],[PLAN+0x44,leg['na']],[PLAN+0x48,1],
                [PLAN+0x4c,2_000_000],[PLAN+0x50,50_000_000]]
        for i in range(6):
            writes += [[PLAN+0x100+32*i,leg['start_q16'][i]&0xffffffff],
                       [PLAN+0x104+32*i,leg['target_q16'][i]&0xffffffff],
                       [PLAN+0x108+32*i,math_ceil_velocity()],[PLAN+0x10c+32*i,math_ceil_acceleration()]]
        self.b.batch(writes);self.b.write(PLAN,1);deadline=time.monotonic()+leg['seconds']+10
        while True:
            s=self.observe('SWITCHING_HOME')
            if s['arm_errors'] or s['planner_errors'] or not s['D5_ok']:raise RuntimeError('HOME transition error')
            raw=s['raw'][f'0x{PLAN+4:08x}']
            if raw&7==4 and not raw&32:return
            if time.monotonic()>deadline:raise TimeoutError('HOME transition timed out')
            time.sleep(.05)

    def configure_mode(self,mode,rows):
        self.control.mode_progress='检查空夹爪 HOME 与设备状态'
        s=self.observe('MODE_REQUEST')
        if s['state']!='IDLE' or not s['at_home'] or s['holding'] or s['arm_fault'] or s['fault']!='NONE':
            raise ControlError(409,'Only a verified empty HOME may switch mode')
        if mode=='B' and not self.control.status().get('device',{}).get('abi_verified'):
            raise ControlError(503,'FPGA ABI not verified')
        disabled=bool(self.reconcile_red(mode)) if self.reconcile_red else False
        oldmode=self.mode
        word=mode_word(mode,rows)&(~(1<<17) if mode=='A' and disabled else 0xffffffff)
        if oldmode==mode:
            self.control.mode_progress='更新当前模式的手势映射'
            # Rebinding at the same verified HOME needs no table reload or motion.
            self.b.write(TASK+0x24,word)
            s=self.observe('MODE_MAPPING_ACK')
            if self.b.read(TASK+0x24)[0]!=word or not s['at_home']:raise RuntimeError('FPGA mapping acknowledgement mismatch')
            self.rows=deepcopy(rows)
            return dict(mode=mode,gesture_bindings=deepcopy(rows),fpga_acknowledged=True,motion_started=False,
                        reused_mode_tables=True)
        self.b.write(TASK,2);self.await_state('OFF')
        moved=oldmode!=mode
        if moved:
            self.control.mode_progress=f'执行 {oldmode} HOME → {mode} HOME 固定过渡'
            transition=self.transitions[oldmode+'_to_'+mode]
            for leg in transition['legs']:self.move(leg)
        if mode=='A':
            self.control.mode_progress='恢复 A 模式轨迹表；仅上传发生变化的字'
            self.upload(task_writes(self.plan,self.table))
        else:
            self.control.mode_progress='设置 B 模式 HOME 与动态路径入口'
            # Keep the fixed image window and A interaction timing. Only the
            # trajectory bundle is replaced when a PL digit selects an object.
            self.b.write(TASK+0x40,65000);self.b.write(TASK+0x44,1500)
            self.b.write(TASK+0x54,0)
            q=[round(v*65536)&0xffffffff for v in home('B')]+[0,0]
            self.upload(home_b_writes(q[:6]))
        self.b.write(TASK+0x24,word);self.mode=mode
        self.control.mode_progress='等待 FPGA 模式与 HOME 确认'
        self.b.write(TASK,1);s=self.await_state('IDLE')
        if self.b.read(TASK+0x24)[0]!=word or not s['at_home']:
            raise RuntimeError('FPGA mode/HOME acknowledgement mismatch')
        self.rows=deepcopy(rows)
        return dict(mode=mode,gesture_bindings=deepcopy(rows),fpga_acknowledged=True,motion_started=moved,
                    home_transition=dict(completed=True,to_mode=mode,from_mode=oldmode))

    def set_red_available(self,available):
        s=self.observe('SHARED_RED_INVENTORY')
        if s['state'] not in ('OFF','IDLE') or s['holding'] or s['fault']!='NONE':raise RuntimeError('Shared red inventory requires stationary empty HOME')
        self.b.write(TASK+0x58,1);self.b.write(TASK,2048 if available else 4096)
        deadline=time.monotonic()+2
        while bool(self.b.read(TASK+4)[0]&(1<<26))!=available:
            if time.monotonic()>deadline:raise RuntimeError('Shared red inventory acknowledgement failed')
            time.sleep(.01)

    def commit(self,compiled,task):
        s=self.observe('B_PATH_PREPARED')
        if s['state']!='WAIT_PATH' or s['selected_task_id']!=task['task_id'] or s['selected_gesture']!=task['gesture']:
            raise ControlError(409,'The PL selection expired or changed')
        native_stats=None
        if compiled.get('native_program'):
            from pc.mode_ab.native_upload import upload
            native_stats=upload(self,compiled['native_program'])
        if not compiled.get('restock'):self.upload(b_writes(compiled))
        elif compiled.get('origin_kind')=='A_FIXED':
            q=[round(v*65536)&0xffffffff for v in home('B')]+[0,0]
            self.upload([[TASK+0x54,0]]+home_b_writes(q[:6]))
        self.batch(fifo_writes(compiled,task['gesture'],task['task_id']))
        if native_stats:
            self.upload_stats=dict(self.upload_stats or {},native_program=native_stats)
        status=self.b.read(TASK+0x64)[0]
        if status&0x3ff != len(compiled['fifo']):raise RuntimeError('Partial or overflowing FPGA FIFO')
        if self.b.read(TASK+0x5c)[0]!=(task['task_id']<<16)|task['gesture']:
            raise RuntimeError('FPGA path identity readback mismatch')
        self.b.write(TASK,256)

    def close(self):
        result={}
        try:
            if self.b and self.b.ready and not self.b.failed:
                legacy.stop_motion(self.b);self.exposure.restore_sensor(self.b,self.sensor_result)
                from mode_a_upgrade_trace import dump_trace
                result['pl_trace']=dump_trace(self.b,self.out/'pl_trace.json')
            if self.b:self.b.close()
            result['PS_CPU_restore']='CONFIRMED' if self.b else 'NOT_OPENED'
        except Exception as exc:result.update(shutdown_error=repr(exc),requires_operator_power_cycle=True)
        finally:
            if self.server:
                try:self.server.close()
                except Exception as exc:result['service_close_error']=repr(exc)
            self.telemetry.close()
            self.communication.close()
        (self.out/'shutdown.json').write_text(json.dumps(result,indent=2))
        return result
