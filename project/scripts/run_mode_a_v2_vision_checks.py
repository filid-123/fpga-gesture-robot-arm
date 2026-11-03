"""Optimized hardware against frozen Rain v3 integers, isolated from V1 evidence."""
import sys
from pathlib import Path
import run_mode_a_v3_checks as v
v.H=v.W/'board_evidence/mode_a_v2_vision_a3'
v.H.mkdir(parents=True,exist_ok=True)
OriginalJob=v.Job
class V2Job(OriginalJob):
 def compile(self,benches):
  benches=[p.replace('mode_a_v3/tb_pipeline_v2.sv','mode_a_v2/tb_pipeline_v2.sv').replace('mode_a_v3/tb_final_top_v2.sv','mode_a_v2/tb_final_top_v2.sv') for p in benches]
  return super().compile(benches)
v.Job=V2Job
# Ten real frames span the production PALM 300ms dwell; no timer reduction.
if len(sys.argv)>1 and sys.argv[1]=='final':
 original_run=v.subprocess.run
 def extended_run(*args,**kwargs):
  kwargs['timeout']=1200
  return original_run(*args,**kwargs)
 v.subprocess.run=extended_run
if __name__=='__main__':v.main()
