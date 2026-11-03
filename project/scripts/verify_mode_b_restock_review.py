"""Portable stdlib-only restock review: hashes, source identity, events and mesh proof."""
import argparse
import hashlib
import json
from pathlib import Path


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(test, reason):
    if not test:raise ValueError(reason)


def sequence(plan):
    rows=[]
    def event(item):
        if item:rows.append({'index':len(rows),'label':item['label'],'kind':'gripper_event','wire_json':item['wire_json']})
    event(plan.get('initial_event'))
    for stage in plan['stages']:
        for index, frame in enumerate(stage['stage']['stream_frames']):
            rows.append({'index':len(rows),'label':stage['phase'],'kind':'motion','sample_in_stage':index,
                         'period_s':stage['stage']['period_s'],'wire_json':frame['wire_json']})
        event(plan['event_after_stage'].get(stage['phase']))
    event(plan['final_event'])
    return rows


def verify(root):
    root=Path(root).resolve();manifest=read(root/'MANIFEST.json')['files_sha256']
    actual={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
    require(actual==set(manifest)|{'MANIFEST.json'},'Manifest file set mismatch')
    for path,h in manifest.items():
        target=(root/path).resolve();require(target.is_relative_to(root),'Unsafe manifest path')
        require(sha(target)==h,'SHA256 mismatch: '+path)
    summary=read(root/'REVIEW.json');cases=[];samples=0
    for case in summary['routes']:
        folder=root/case['folder'];p=read(folder/'PLAN.json');sim=read(folder/'COPPELIA.json')
        cls=p['request']['object_class'];base=root/'baseline'/cls
        record=read(base/'ORIGIN.json');original=read(base/'DELIVERY_PLAN.json')
        require(p['origin_record_sha256']==sha(base/'ORIGIN.json'),'Origin hash mismatch')
        require(record['delivery_plan_sha256']==sha(base/'DELIVERY_PLAN.json'),'Delivery hash mismatch')
        require(record['delivery_result_sha256']==sha(base/'DELIVERY_RESULT.json'),'Actual delivery hash mismatch')
        require(record['original_pickup']==original['request']['pickup'],'Original source overwritten')
        require(p['original_pickup']==record['original_pickup'],'Restock source overwritten')
        require(sim['route_sha256']==sha(folder/'PLAN.json') and sim['passed'] and not sim['mesh_collisions'],
                'Mesh proof/plan mismatch')
        require(not p['physical_restock_accepted'] and not p['fpga_trajectory'],'Unverified acceptance claim')
        require(p['requires_public_area_clear'] and p['removed_delivery_fixture']['support_centre_mm']==[285,195,150],
                'Missing public fixture conflict precondition')
        if p['task_kind']=='RESTOCK':
            require(p['return_centre_mm']==record['original_pickup']['centre_mm'],'Wrong dynamic return target')
            low=next(s for s in p['stages'] if s['phase']=='RESTOCK_SOURCE_DESCEND')['stage']['target_firmware_rad']
            require(max(abs(low[n]-record['grasp_command_firmware_rad'][n]) for n in ('b','s','e','t','r','g'))<1e-9,
                    'Original successful grasp command differs')
            require(p['public_pickup_centre_mm']==[300,200,original['local_scene_config']['objects'][cls]['size_mm'][2]/2],
                    'Public object height differs')
        else:
            require(not p['inventory_restored'] and p['requires_stopped_fresh_pose'],'Invalid cancellation inventory/state')
            require(p['cancel_of_plan_sha256']==sha(root/'routes'/cls/'normal/PLAN.json'),'Cancellation forward plan differs')
            require(p['return_centre_mm'][:2]==[300,200],'Cancel did not return public object')
        expected=sequence(p)
        actual=[json.loads(line) for line in (folder/'sequence.jsonl').read_text(encoding='utf8').splitlines()]
        require(actual==expected,'Native stream/events mismatch')
        require(all(0<json.loads(x['wire_json'])['acc']<=254 for x in actual),'Wire acceleration overflow')
        releases=[x for x in actual if x['label'].startswith('RELEASE_')]
        count=0 if p['task_kind']=='RESTOCK_CANCEL_EMPTY' else 1
        require(len(releases)==count and all(json.loads(x['wire_json'])['T']==106 for x in releases),'Release event count/type differs')
        require(not any(x['label']=='PLACE' for x in actual),'Restock replayed normal delivery stage')
        samples+=sim['samples_checked'];cases.append({'class':cls,'kind':p['task_kind'],'requests':len(actual),'passed':True})
    return {'passed':True,'files':len(manifest),'routes':len(cases),'mesh_samples':samples,
            'normal':sum(c['kind']=='RESTOCK' for c in cases),'cancel':sum(c['kind'].startswith('RESTOCK_CANCEL') for c in cases),
            'hardware_accessed':False,'physical_restock_accepted':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parent)
    args=parser.parse_args()
    try:print(json.dumps(verify(args.root)))
    except (ValueError,OSError,KeyError,StopIteration) as exc:parser.exit(1,'RESTOCK_REVIEW_FAILED: '+str(exc)+'\n')
