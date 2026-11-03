"""Coherent frozen PL trace export; no motion or selection commands."""
import json
from mode_a_upgrade_config import VIS
def dump_trace(board,path):
 board.write(VIS+0x23c,1)
 try:
  total=board.read(VIS+0x208)[0];wr=board.read(VIS+0x214)[0]&255
  count=min(total,256);rows=[]
  for n in range(count):
   index=(wr-count+n)&255;board.write(VIS+0x240,index)
   values=board.read(VIS+0x244,8);head=values[1]
   rows.append(dict(index=index,cycles_u32=values[0],event=head>>28,tag=head&0xfffffff,last_delivered_q16=[v-(1<<32) if v&0x80000000 else v for v in values[2:]]))
  result=dict(clock_hz=100000000,cycle_wrap_seconds=42.94967296,event_codes={1:'CAPTURE_PUBLISHED',2:'LOCATOR_START',3:'LOCATOR_DONE',4:'CLASSIFIER_START',5:'CLASSIFIER_DONE',6:'RESULT',7:'TASK_STATUS_CHANGE',8:'TX_FRAME_COUNT_CHANGE'},total=total,retained=count,overwritten=max(0,total-256),simultaneous_events_not_stored=board.read(VIS+0x20c)[0],last_delivered='Commanded Q16.16 native joint radians, not measured feedback or ESP32 ACK',rows=rows)
  path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n','utf-8');return dict(file=path.name,total=total,retained=count)
 finally:board.write(VIS+0x23c,0)
