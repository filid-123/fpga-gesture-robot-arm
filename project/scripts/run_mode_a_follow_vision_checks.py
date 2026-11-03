"""Bind unchanged v3 vision to the new four-bank production top."""
import sys
from pathlib import Path
import run_mode_a_v3_checks as v
v.H=v.W/'board_evidence/mode_a_follow_vision_a2';v.H.mkdir(parents=True,exist_ok=True)
OriginalJob=v.Job
class FourJob(OriginalJob):
 def compile(self,benches):
  return super().compile([p.replace('mode_a_v3/tb_final_top_v2.sv','mode_a_follow/tb_final_top_four.sv') for p in benches])
v.Job=FourJob
if len(sys.argv)>1 and sys.argv[1]=='final':
 original_run=v.subprocess.run
 def extended(*args,**kwargs):kwargs['timeout']=1200;return original_run(*args,**kwargs)
 v.subprocess.run=extended
# Base final runner derives its top from original file name: preserve the top alias.
if __name__=='__main__':v.main()
