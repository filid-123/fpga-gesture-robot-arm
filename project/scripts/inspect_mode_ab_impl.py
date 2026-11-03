"""Reproducible offline routed-netlist inspection and complete implementation seal."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
from review_mode_ab_impl import ROOT,main as review


def main(attempt,inspection):
    if not re.fullmatch('[a-z0-9]+',attempt) or not re.fullmatch('a[0-9]+',inspection):raise ValueError('Use a fresh named build/inspection')
    out=ROOT/('board_evidence/mode_ab_impl_'+attempt)/('inspection_'+inspection);out.mkdir(exist_ok=False)
    env=os.environ.copy();env.update(
        DIAG_PROJECT='D:/FPGA_Projects/Gesture/builds/mode_ab_v0_1_0_'+attempt+'/Gesture_Roarm_ClosedLoop.xpr',
        DIAG_INSPECT_OUT=str(out/'NETLIST_INSPECTION.txt'),DIAG_CDC_OUT=str(out/'CDC_DETAILS.rpt'))
    command=['E:/Xilinx/2026.1/Vivado/bin/vivado.bat','-mode','batch','-notrace','-source',
        str(ROOT/('scripts/inspect_mode_ab_p4_netlist.tcl' if attempt not in ('a7','a8') else 'scripts/inspect_mode_a_restock_netlist.tcl')),'-log',str(out/'inspect.log'),'-journal',str(out/'inspect.jou')]
    with (out/'stdout.txt').open('xb') as stream:
        p=subprocess.run(command,env=env,stdout=stream,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW,timeout=300)
    (out/'command.json').write_text(json.dumps(dict(command=command,environment={k:v for k,v in env.items() if k.startswith('DIAG_')},exit_code=p.returncode,hardware_access=False),indent=2))
    if p.returncode:raise RuntimeError('Netlist inspection failed; retain this attempt')
    review(attempt,inspection)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--attempt',required=True);p.add_argument('--inspection',default='a1');a=p.parse_args();main(a.attempt,a.inspection)
