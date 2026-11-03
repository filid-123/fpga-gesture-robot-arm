"""Archive new restock routes, exact events, source identity and real mesh proofs."""
import argparse
from pathlib import Path
import json
import shutil
import zipfile
from verify_mode_b_restock_review import verify,sequence,sha,read

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'artifacts/phase3c/mode_b_return_20261029/plans'
DEST=ROOT/'docs/phase3c/mode_b_restock_20261029/review'


def copy(source,target):
    target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)


def write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8')


def build(dest=DEST):
    if dest.exists() and any(dest.iterdir()):raise ValueError('Use a fresh review directory')
    dest.mkdir(parents=True,exist_ok=True)
    routes=[]
    for cls in ('red_cube','eraser','small_canister'):
        record=read(SOURCE/cls/'ORIGIN.json')
        for source,name in [(SOURCE/cls/'ORIGIN.json','ORIGIN.json'),(Path(record['delivery_plan_file']),'DELIVERY_PLAN.json'),
                            (Path(record['delivery_result_file']),'DELIVERY_RESULT.json')]:
            copy(source,dest/'baseline'/cls/name)
        plans=[SOURCE/cls/'RESTOCK_PLAN.json',*sorted((SOURCE/cls/'cancel').glob('*/RESTOCK_PLAN.json'))]
        for plan in plans:
            p=read(plan);name='normal' if p['task_kind']=='RESTOCK' else plan.parent.name
            folder=Path('routes')/cls/name;where=dest/folder
            copy(plan,where/'PLAN.json');copy(plan.parent/'COPPELIA_VERIFICATION.json',where/'COPPELIA.json')
            (where/'sequence.jsonl').write_text(''.join(json.dumps(x,separators=(',',':'))+'\n' for x in sequence(p)),encoding='utf8')
            profile={'object_class':cls,'kind':p['task_kind'],'public_xy_mm':[300,200],
                     'public_yaw_deg':p['request']['pickup'].get('yaw_deg'),
                     'original_return_centre_mm':p['original_pickup']['centre_mm'],
                     'this_route_return_centre_mm':p['return_centre_mm'],'nominal_motion_seconds':p['nominal_motion_seconds'],
                     'motion_frames':sum(len(s['stage']['stream_frames']) for s in p['stages']),
                     'physical_test':'NOT_RUN','fpga_adapter':'NOT_IMPLEMENTED'}
            write(where/'PROFILE.json',profile)
            routes.append({'folder':folder.as_posix(),**profile})
    source_files=['pc/mode_b/restock_workflow.py','scripts/prepare_mode_b_restock.py','scripts/run_mode_b_restock.ps1',
                  'scripts/try_mode_b_loaded_route.ps1','scripts/test_mode_b_restock.py','config/ai_pc/mode_b_restock_20261029.json',
                  'sim/phase3_robot/verify_mode_b_loaded_route.py']
    for path in source_files:copy(ROOT/path,dest/'source_snapshot'/path)
    refs=ROOT/'artifacts/phase3c/mode_b_return_20261029/filid_reference_480f3e6'
    for p in refs.rglob('*'):
        if p.is_file():copy(p,dest/'filid_reference'/p.relative_to(refs))
    copy(ROOT/'scripts/verify_mode_b_restock_review.py',dest/'verify.py')
    copy(ROOT/'docs/phase3c/mode_b_restock_20261029/README_CN.md',dest/'README_CN.md')
    write(dest/'REVIEW.json',{'schema':'gesture.mode_b.restock_review.v1','date':'2026-10-29',
                            'filid_commit':'480f3e600bc9465d9a1fec361e6781c2b2eb59a0',
                            'hardware_accessed':False,'physical_restock_accepted':False,'routes':routes})
    write(dest/'MANIFEST.json',{'files_sha256':{p.relative_to(dest).as_posix():sha(p) for p in sorted(dest.rglob('*')) if p.is_file()}})
    report=verify(dest)
    archive=dest.parent/'MODE_B_RESTOCK_REVIEW_20261029.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in sorted(dest.rglob('*')):
            if p.is_file():z.write(p,(Path('review')/p.relative_to(dest)).as_posix())
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        import hashlib
        for name,h in read(dest/'MANIFEST.json')['files_sha256'].items():assert hashlib.sha256(z.read('review/'+name)).hexdigest()==h,name
    print(json.dumps({'verification':report,'zip_bytes':archive.stat().st_size,'zip_sha256':sha(archive)}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=DEST);args=parser.parse_args();build(args.output)
