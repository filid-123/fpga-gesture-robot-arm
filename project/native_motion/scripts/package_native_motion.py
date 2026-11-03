"""Assemble the final native motion source/BIT/HWH/PC/PYNQ package."""
from __future__ import annotations
import argparse
import ast
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

ROOT=Path(__file__).resolve().parents[2]
NATIVE=ROOT/"native_motion"
SIM=ROOT/"sim/phase3_native_closed_loop"
REPORTS=NATIVE/"reports/phase3_s5_vision_motion_implemented"

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--scene",type=Path,required=True)
    p.add_argument("--evidence",type=Path,required=True)
    args=p.parse_args()
    if args.out.exists() or Path(str(args.out)+".zip").exists():raise FileExistsError(args.out)
    result=json.loads((NATIVE/"RESOURCE_COMPARISON.json").read_text())
    if result["implementation_gate"]!="PASS":raise RuntimeError("Final implementation gate failed")
    args.out.mkdir(parents=True)
    copied={}
    def copy(source,rel):
        target=args.out/rel;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,target);copied[Path(rel).as_posix()]=sha(target)
    def tree(base,rel):
        for f in sorted(base.rglob("*")):
            if f.is_file() and not any(x in f.parts for x in ("__pycache__",".Xil")) and f.suffix not in (".pyc",".pb",".jou",".log") and f.name not in (".keep",):
                copy(f,Path(rel)/f.relative_to(base))
    for d in ("rtl","scripts","constraints","test_gesture7_package","quantized_locator_v16_failure_adaptation","sim"):
        tree(NATIVE/d,Path("native_motion")/d)
    for n in ("README_CN.md","BASELINE.json","TEST_RESULTS.json","RESOURCE_COMPARISON.json","BUILD_MANIFEST.json",".gitattributes"):
        copy(NATIVE/n,Path("native_motion")/n)
    tree(SIM,Path("sim/phase3_native_closed_loop"))
    # Last definition wins, matching bootstrap's native adapters > frozen S8 > PS > robot.
    roots=[ROOT/"sim/phase3_robot",ROOT/"ps/robot",SIM,SIM/"s8_baseline",SIM/"adapters"]
    modules={f.stem:f for r in roots for f in r.glob("*.py")}
    pending=list(SIM.rglob("*.py"));seen=set()
    while pending:
        f=pending.pop()
        if f in seen:continue
        seen.add(f)
        if not f.is_relative_to(SIM):copy(f,f.relative_to(ROOT))
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8-sig"))):
            names=[n.name for n in node.names] if isinstance(node,ast.Import) else [node.module] if isinstance(node,ast.ImportFrom) and node.module else []
            pending.extend(modules[n.split(".")[0]] for n in names if n.split(".")[0] in modules)
    for n in ("bench_loopback_roarm_json.yaml","bench_loopback_so101.yaml"):
        copy(ROOT/"config/arm_profiles"/n,Path("config/arm_profiles")/n)
    for n in ("roarm_json_FIXTURE_NOT_OFFICIAL.yaml","feetech_FIXTURE_NOT_OFFICIAL.yaml"):
        copy(ROOT/"config/protocols/fixtures"/n,Path("config/protocols/fixtures")/n)
    for ext in ("bit","hwh"):
        copy(REPORTS/("phase3_s5_vision_motion."+ext),Path("hardware")/("phase3_native_motion."+ext))
    copy(args.scene,"scenes/roarm_m3_phase3.ttt")
    guide=ROOT/"docs/PHASE3_NATIVE_MOTION_BOARD_GUIDE_v0.1.0_CN.md"
    copy(guide,guide.relative_to(ROOT));copy(guide,"README_CN.md")
    copy(NATIVE/"TEST_RESULTS.json","TEST_RESULTS.json")
    copy(NATIVE/"RESOURCE_COMPARISON.json","RESOURCE_COMPARISON.json")
    copy(NATIVE/"BUILD_MANIFEST.json","BUILD_MANIFEST.json")
    for f in REPORTS.glob("*.rpt"):copy(f,Path("evidence/implementation")/f.name)
    copy(REPORTS/"S5_BUILD_INFO.json","evidence/implementation/S5_BUILD_INFO.json")
    for f in (NATIVE/"reports/native_xsim").glob("*.run.log"):copy(f,Path("evidence/rtl")/f.name)
    for name in ("native_python_tests.log","scene_tests.log"):
        copy(NATIVE/name,Path("evidence")/name)
    for f in args.evidence.rglob("*"):
        if f.is_file():copy(f,Path("evidence/coppelia")/f.relative_to(args.evidence))
    audit=ROOT/"runs/native_scene_final_001/PATH_SUPPORT_AUDIT_DETAIL.json"
    copy(audit,"evidence/PATH_SUPPORT_AUDIT_DETAIL.json")
    rollback={"intermediate":{"path":"backups/native_motion_unified_source_v0.1.0_BOARD_NOT_RUN.zip","board":"NOT_RUN","contains_bit":False},"baseline":{"path":"deliverables/Gesture_Phase3_PreDemo_Frozen_v0.1.0_20261003.zip","this_round_board":"NOT_RUN","history":"S7 BIT and old software have seven historical Coppelia/UART cases; restore old software/ABI with old BIT"},"patches":["Gesture_Phase3_CoppeliaModeHotfix_v0.1.1_20261006.zip","Gesture_Phase3_CoppeliaStartupGuard_v0.1.2_20261006.zip"]}
    for v in (rollback["intermediate"],rollback["baseline"]):
        f=ROOT/v["path"];v["sha256"]=sha(f) if f.exists() else None;v["available_on_this_host"]=f.exists()
    (args.out/"ROLLBACK_VERSIONS.json").write_text(json.dumps(rollback,indent=2)+"\n",encoding="utf-8")
    copied["ROLLBACK_VERSIONS.json"]=sha(args.out/"ROLLBACK_VERSIONS.json")
    sums="".join(f"{digest}  {rel}\n" for rel,digest in sorted(copied.items()))
    (args.out/"SHA256SUMS").write_text(sums,encoding="utf-8")
    archive=Path(str(args.out)+".zip")
    with zipfile.ZipFile(archive,"w",zipfile.ZIP_DEFLATED) as z:
        for f in sorted(args.out.rglob("*")):
            if f.is_file():z.write(f,f.relative_to(args.out))
    # One packaging integrity check, not a new hardware detector.
    with zipfile.ZipFile(archive) as z:
        if z.testzip() is not None:raise RuntimeError("ZIP CRC failed")
        for rel,digest in copied.items():
            if hashlib.sha256(z.read(rel)).hexdigest()!=digest:raise RuntimeError("ZIP member mismatch: "+rel)
    descriptor={"version":"0.1.0","zip":str(archive.resolve()),"sha256":sha(archive),"bytes":archive.stat().st_size,"files":len(copied)+1,"state":"IMPLEMENTATION_AND_SIMULATION_PASS_BOARD_NOT_RUN"}
    archive.with_suffix(".json").write_text(json.dumps(descriptor,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(descriptor))

if __name__=="__main__":main()
