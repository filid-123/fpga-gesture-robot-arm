"""Mode-A live register viewer. JTAG/PYNQ reads only; demo/replay need no board."""
import argparse
import datetime
import json
import math
from pathlib import Path
import queue
import subprocess
import threading
import time

ARM=0x43c30000;PLAN=0x43c40000;TASK=0x43c50000;VIS=0x43c60000
MODEL=('BG','ONE','TWO','THREE','FIST','PALM','GATED','NO_DETECTION')
GESTURE=('BG','OBJECT_1','OBJECT_2','OBJECT_3','PALM_READY','FIST_CANCEL','INVALID','NO_DETECTION')
STATES=('OFF','IDLE','WAIT_PATH','PRECHECK','RUN','WAIT_PALM','PAUSED','STOPPING','RETRACE','HALT','FAULT')
PHASES=('NONE','OUT','DELIVER','RELEASE','RETREAT','TRAY')
FAULTS=('NONE','D5_PERMISSION','ARM_FAULT','ARM_PERMISSION','PLANNER','MOVE_TIMEOUT','ARRIVAL','COMM','BUS','TARGET_MISMATCH','OPERATOR_ABORT')
REFUSE=('NONE','D5_PERMISSION','ARM_NOT_READY','ARM_MODE','PLANNER','NOT_HOME','TABLE','RANGE','DUPLICATE','PATH','LINK','EMPTY_SLOT')
ADDRS=([ARM+a for a in (0x8,0xc,0x10,0x200,0x204,0x208,0x20c,0x210,0x214,0x218,0x21c,0x300,0x304,0x308,0x30c)]+
       [PLAN+a for a in (4,8,12,0x200,0x204,0x208,0x20c,0x210,0x214)]+
       [TASK+a for a in (4,8,12,0x10,0x1c,0x20,0x240,0x244,0x248,0x24c,0x25c)]+
       [VIS+a for a in (4,8,0x28,0x2c,0x38,0x5c,0x60,0x68,0x6c,0x70,0x78,0x80,0x84)])


def signed(n):
    return n-(1<<32) if n&(1<<31) else n


def decode(raw,task_abi=0x3404,planner_abi=0x3202,vision_abi=0x3505):
    r={int(k,0) if isinstance(k,str) else k:int(v) for k,v in raw.items()}
    for addr,value in [(ARM+0x10,0x3101),(PLAN+12,planner_abi),(TASK+0x10,task_abi),
                       (VIS+8,vision_abi),(VIS+0x70,0x022267a9)]:
        if r[addr]!=value:raise ValueError(f'Build mismatch at {addr:08x}: {r[addr]:08x}, expected {value:08x}')
    st=r[TASK+4];fault=r[TASK+8];vs=r[VIS+4]
    state=st&15;phase=(st>>4)&7;obj=(st>>20)&3
    fc=fault&255;rc=(fault>>16)&255
    result=dict(timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        source='FPGA_REGISTER_SNAPSHOT',model=MODEL[(r[VIS+0x68]>>16)&7],
        gesture=GESTURE[(vs>>5)&7],qualified=bool(r[VIS+0x38]&1),
        vision_valid=bool(vs&1),palm_window_ok=bool(vs&16),
        frame=r[VIS+0x28],image_age_ms=(r[VIS+0x84]-r[VIS+0x5c])&0xffffffff,
        state=STATES[state] if state<len(STATES) else f'UNKNOWN_{state}',
        phase=PHASES[phase] if phase<len(PHASES) else f'UNKNOWN_{phase}',object=obj,
        owner=bool(st&128),holding=bool(st&(1<<9)),released=bool(st&(1<<10)),
        inventory_mask=(st>>26)&7,fault=FAULTS[fc] if fc<len(FAULTS) else f'UNKNOWN_{fc}',
        refusal=REFUSE[rc] if rc<len(REFUSE) else f'UNKNOWN_{rc}',
        D5_ok=bool(r[ARM+8]&8),arm_fault=bool(r[ARM+8]&16),
        arm_errors=r[ARM+12],planner_errors=r[PLAN+8],events=r[TASK+12],
        command_result=r[TASK+0x1c],progress_raw=r[TASK+0x20],
        last_delivered_rad=[signed(r[PLAN+0x200+4*i])/65536 for i in range(6)],
        feedback_rad=[signed(r[ARM+0x200+4*i])/10000 for i in range(6)],
        feedback_mask=r[ARM+0x218]&63,arrival_mask=(r[ARM+0x218]>>8)&63,
        feedback_seq=(r[ARM+0x21c]>>16)&65535,feedback_age_at_snapshot_ms=r[ARM+0x21c]&65535,
        motion_frames=r[ARM+0x300],feedback_packets=r[ARM+0x304],
        feedback_errors=r[ARM+0x308],feedback_timeouts=r[ARM+0x30c],
        poll_count=r[TASK+0x25c],raw={f'0x{k:08x}':v for k,v in r.items()})
    if result['fault']!='NONE':reason='FAULT:'+result['fault']
    elif result['refusal']!='NONE' and result['state']=='IDLE':reason='LAST_REFUSAL:'+result['refusal']
    elif result['state']=='WAIT_PALM':reason='WAIT_STABLE_PALM_AND_VALID_WINDOW'
    elif result['state'] in ('RUN','RETRACE','STOPPING'):reason='EXECUTING_'+result['phase']
    elif result['state']=='IDLE' and not result['qualified']:reason='WAIT_QUALIFIED_GESTURE'
    elif result['object'] and not(result['inventory_mask']&(1<<(result['object']-1))):reason='SELECTED_SLOT_RESERVED_OR_EMPTY'
    else:reason='SEE_RAW_STATUS_AND_EVENTS'
    result['software_status_explanation']=reason
    return result


def line(s):
    err=[math.degrees(a-b) for a,b in zip(s['last_delivered_rad'],s['feedback_rad'])]
    return (f"{s['source']} frame={s['frame']} model={s['model']} gesture={s['gesture']} "
        f"qualified={int(s['qualified'])} age={s['image_age_ms']}ms | "
        f"FPGA={s['state']}/{s['phase']} obj={s['object']} stock={s['inventory_mask']:03b} "
        f"hold={int(s['holding'])} release={int(s['released'])} | "
        f"judgment={s['software_status_explanation']} D5={int(s['D5_ok'])} "
        f"tx={s['motion_frames']} fb_seq={s['feedback_seq']} "
        f"snapshot_age={s['feedback_age_at_snapshot_ms']}ms delta_snapshot_deg="+
        ','.join(f'{v:+.2f}' for v in err)+
        ' cmd_rad='+','.join(f'{v:.3f}' for v in s['last_delivered_rad'])+
        ' measured_rad='+','.join(f'{v:.3f}' for v in s['feedback_rad']))


class JtagReader:
    def __init__(self):
        self.q=queue.Queue()
        here=Path(__file__).resolve().parent
        self.p=subprocess.Popen(['cmd.exe','/d','/c','E:/Xilinx/2026.1/Vivado/bin/xsdb.bat',
                                  str(here/'mode_a_terminal_readonly.tcl')],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,
            encoding='utf-8',errors='replace',creationflags=subprocess.CREATE_NO_WINDOW)
        def reader():
            for row in self.p.stdout:self.q.put(row.rstrip())
            self.q.put(None)
        threading.Thread(target=reader,daemon=True).start()
        try:
            while True:
                row=self.q.get(timeout=30)
                if row=='MODE_A_READONLY_READY':break
                if row is None or row.startswith('READONLY_ERROR'):raise RuntimeError(row)
        except BaseException:
            self.close()
            raise
    def sample(self):
        self.p.stdin.write('S\n');self.p.stdin.flush()
        while True:
            row=self.q.get(timeout=30)
            if row is None:raise RuntimeError('XSDB stopped')
            if row.startswith('READONLY_ERROR'):raise RuntimeError(row)
            if row.startswith('REGISTERS '):
                tokens=row.split()[1:]
                if len(tokens)!=len(ADDRS):raise ValueError('Short JTAG snapshot')
                return dict(zip(ADDRS,(int(t,0) for t in tokens)))
    def close(self):
        if self.p.poll() is None:
            try:
                self.p.stdin.write('Q\n');self.p.stdin.flush()
                self.p.wait(timeout=15)
            except (BrokenPipeError,OSError,subprocess.TimeoutExpired):
                # End only this viewer's process tree, never the shared server.
                subprocess.run(['taskkill','/PID',str(self.p.pid),'/T','/F'],
                    stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW,timeout=10,check=False)


class PynqReader:
    def __init__(self):
        from pynq import MMIO
        self.maps={b:MMIO(b,0x1000) for b in [ARM,PLAN,TASK,VIS]}
    def sample(self):return {a:int(self.maps[a&0xfffff000].read(a&4095)) for a in ADDRS}
    def close(self):pass


def demo():
    r={a:0 for a in ADDRS}
    for a,v in [(ARM+16,0x3101),(PLAN+12,0x3202),(TASK+16,0x3404),(VIS+8,0x3505),(VIS+0x70,0x022267a9)]:r[a]=v
    for index,(state,phase,cls,stock,refused) in enumerate([
        (1,0,1,7,0),(4,1,1,6,0),(5,0,5,6,0),(4,2,5,6,0),
        (4,3,5,6,0),(1,0,0,6,0),(1,0,1,6,11)]):
        r[TASK+4]=state|(phase<<4)|(1<<20)|(stock<<26)
        r[TASK+8]=refused<<16;r[VIS+0x68]=cls<<16
        task_cls={4:5,5:4}.get(cls,cls);r[VIS+4]=1|(task_cls<<5)|16;r[VIS+0x38]=1
        r[VIS+0x28]=index;r[VIS+0x84]=1000+index*100;r[VIS+0x5c]=950+index*100
        result=decode(r);result['source']='SYNTHETIC_TERMINAL_DEMO';yield result


def main():
    ap=argparse.ArgumentParser(description=__doc__);g=ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--demo',action='store_true');g.add_argument('--replay',type=Path)
    g.add_argument('--jtag-readonly',action='store_true');g.add_argument('--pynq-readonly',action='store_true')
    ap.add_argument('--out',type=Path,required=True);ap.add_argument('--seconds',type=float,default=0)
    ap.add_argument('--interval',type=float,default=.2);args=ap.parse_args()
    if not math.isfinite(args.seconds) or args.seconds<0 or not .05<=args.interval<=10:raise ValueError('duration/interval')
    args.out.parent.mkdir(parents=True,exist_ok=True)
    reader=None
    with args.out.open('x',encoding='utf-8') as log:
        try:
            if args.demo:rows=demo()
            elif args.replay:rows=(json.loads(v) for v in args.replay.read_text('utf-8').splitlines() if v.strip())
            else:
                reader=JtagReader() if args.jtag_readonly else PynqReader()
                def live():
                    start=time.monotonic()
                    while not args.seconds or time.monotonic()-start<args.seconds:
                        yield decode(reader.sample());time.sleep(args.interval)
                rows=live()
                print('READ_ONLY_VIEWER: Ctrl+C closes viewer; PL remains autonomous. Use D5/power for physical stop.',flush=True)
            for s in rows:
                if 'model' not in s:s=decode(s.get('raw',s))
                print(line(s),flush=True);log.write(json.dumps(s,ensure_ascii=False)+'\n');log.flush()
        except KeyboardInterrupt:print('VIEWER_STOPPED; no motion command issued.',flush=True)
        finally:
            if reader:reader.close()


if __name__=='__main__':main()
