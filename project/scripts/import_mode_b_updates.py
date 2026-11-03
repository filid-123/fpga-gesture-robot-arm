"""Import the reviewed Giao update without touching A or frozen visual inputs."""
from pathlib import Path
import hashlib
import json
import subprocess
ROOT=Path(__file__).resolve().parents[1]
SOURCE='1d3fa84de81d05b846d2b9f30998e16a84f4eee3'
BASE='a345624f5f345c28d0915b38aa45bb307a64bec8'


def main():
    report=ROOT/'board_evidence/mode_ab_v0_1_0/upstream_import.json'
    previous=json.loads(report.read_bytes());known=previous['source_files']
    for name,digest in known.items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=digest:raise ValueError('Previous upstream file changed: '+name)
    freeze=json.loads((ROOT/'artifacts/multiobject/eraser_top_repair_20261027/candidate_freeze_v2.json').read_bytes())['files_sha256']
    changed=subprocess.check_output(['git','diff','--name-only',BASE,SOURCE],cwd=ROOT,text=True).splitlines()
    selected=[n for n in changed if not n.endswith('.zip') and n.startswith(('config/ai_pc/','pc/mode_b/','scripts/',
        'docs/phase3c/mode_b_optimized_handoff_20261030/',
        'artifacts/phase3c/mode_b_red_retry_20261030/return_fast_v3/','artifacts/phase3c/mode_b_speed_release_20261030/'))]
    pending=[]
    for name in selected:
        data=subprocess.check_output(['git','show',SOURCE+':'+name],cwd=ROOT);digest=hashlib.sha256(data).hexdigest()
        if name in freeze and freeze[name]!=digest:raise ValueError('Frozen visual dependency cannot change: '+name)
        path=(ROOT/name).resolve()
        if not path.is_relative_to(ROOT):raise ValueError('Invalid upstream path')
        if path.exists() and name not in known and path.read_bytes()!=data:raise ValueError('Untracked local conflict: '+name)
        pending.append((name,data,digest))
    for name,data,digest in pending:
        path=ROOT/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data);known[name]=digest
    previous.update(source_commit=SOURCE,source_base_commit=BASE,source_files=known,
        reviewed_update_files=len(pending),bound_upstream_files=len(known),hardware_access=False)
    report.write_text(json.dumps(previous,indent=2)+'\n')
    out=ROOT/'board_evidence/mode_ab_p3';out.mkdir(parents=True,exist_ok=True)
    (out/'upstream_update.json').write_text(json.dumps(dict(source_commit=SOURCE,base_commit=BASE,files={n:d for n,_,d in pending},frozen_visual_dependencies_unchanged=True,hardware_access=False),indent=2)+'\n')
    print(json.dumps(dict(imported=len(pending),source_commit=SOURCE,total_bound_upstream_files=len(known))))


if __name__=='__main__':main()
