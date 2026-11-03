"""Same preconnected-D5 guards; add read-only metrics and trace snapshot control."""
from pathlib import Path
from mode_a_upgrade_config import ROOT,ARM,PLAN,TASK,VIS,backend_writes,task_writes,vision_writes
from run_mode_a_upgrade import ADDRS
from prepare_mode_a_follow_bridge import generate as parent_generate
import prepare_mode_a_follow_bridge as parent
def generate(plan,table):
 old={k:getattr(parent,k) for k in ('ADDRS','backend_writes','task_writes','vision_writes')}
 try:
  parent.ADDRS=ADDRS;parent.backend_writes=backend_writes;parent.task_writes=task_writes;parent.vision_writes=vision_writes
  text,meta=parent_generate(plan,table)
 finally:
  for k,v in old.items():setattr(parent,k,v)
 text=text.replace('0x3409','0x340a').replace('0x3202','0x3203').replace('0x3505','0x3506').replace('v0.11.0','v0.13.0')
 # Extend read whitelist for all eight trace words; write controls affect only the observer.
 text=text.replace('set board_read {','set board_read {'+' '.join(hex(VIS+o) for o in (0x23c,0x240,*range(0x244,0x264,4)))+' ')
 text=text.replace('set board_write {',f'set board_write {{{hex(VIS+0x23c)} {hex(VIS+0x240)} ')
 marker='    if {$a==0x43c30004'
 idx=text.index(marker)
 text=text[:idx]+'''    if {$a==0x43c6023c && $v ni {0 1}} {error "Trace freeze must be0/1"}
    if {$a==0x43c60240 && $v>255} {error "Trace index range"}
'''+text[idx:]
 meta.update(version='0.13.0',task_abi=0x340a,planner_abi=0x3203,vision_abi=0x3506,trace='256x256b snapshot; freeze does not stop stage timers or motion',handalign='64 steps; fresh rawY44..84; clamp16..111; PRE2s/PALM500ms')
 return text,meta
