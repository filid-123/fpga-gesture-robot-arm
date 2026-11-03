"""Independent ABI3406 routed-netlist review; never connects to hardware."""
from pathlib import Path
import hashlib,json,os,subprocess
ROOT=Path(__file__).resolve().parents[1];H=ROOT/'board_evidence/mode_a_handover_v080_a1'


def main():
    built=json.loads((H/'BUILD_COMPLETED.json').read_text('utf-8'))
    for rel,digest in json.loads((H/'BUILT_SOURCE_HASHES.json').read_text('utf-8'))['files'].items():
        if hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()!=digest:raise ValueError(rel)
    out=H/'inspection_a1';out.mkdir(exist_ok=False)
    env=os.environ.copy();env.update(DIAG_PROJECT=str(Path(built['project'])/'Gesture_Roarm_ClosedLoop.xpr'),DIAG_INSPECT_OUT=str(out/'NETLIST_INSPECTION.txt'),DIAG_CDC_OUT=str(out/'CDC_DETAILS.rpt'))
    cmd=['cmd.exe','/d','/c','E:/Xilinx/2026.1/Vivado/bin/vivado.bat','-mode','batch','-notrace','-source',str(ROOT/'scripts/inspect_mode_a_v04_netlist.tcl'),'-log',str(out/'inspection.log'),'-journal',str(out/'inspection.jou')]
    with (out/'stdout.txt').open('xb') as f:r=subprocess.run(cmd,cwd=ROOT,env=env,stdout=f,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW,timeout=300)
    (out/'COMMAND.json').write_text(json.dumps(dict(exit_code=r.returncode,hardware_access=False,command=cmd),indent=2)+'\n','utf-8')
    if r.returncode:raise RuntimeError('Netlist review failed; see '+str(out))
    print('INDEPENDENT_ROUTED_NETLIST_PASS')


if __name__=='__main__':main()
