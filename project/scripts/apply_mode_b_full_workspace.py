"""Install a verified host-only overlay on a sealed p3 package, without devices.

Default is a read-only preflight. --apply backs up every replaced file and
reseals only host inputs; BIT/HWH, frozen models, calibration and runs stay put.
"""
import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import tempfile
import zipfile


PATCH_ID='full_workspace_policy_p4'
sha=lambda data:hashlib.sha256(data).hexdigest()


def member(root,name):
    p=(root/name).resolve()
    if not p.is_relative_to(root.resolve()):raise ValueError('Invalid package member: '+name)
    return p


def install(bundle,target,*,apply=False,profile='full_frame'):
    bundle=Path(bundle).resolve();target=Path(target).resolve()
    patch=json.loads((bundle/'patch_manifest.json').read_bytes())
    original=(target/'mode_ab_manifest.json').read_bytes();base=json.loads(original)
    if base.get('patch_id')!='planning_ux_giao_p3' or base['task_abi']!=0x340d:
        raise ValueError('This overlay requires the complete planning_ux_giao_p3 package; do not apply it to p2')
    for name,digest in base['inputs'].items():
        if sha(member(target,name).read_bytes())!=digest:raise ValueError('Base package changed: '+name)
    writes={}
    for name,meta in patch['files'].items():
        data=member(bundle/'payload',name).read_bytes()
        if sha(data)!=meta['sha256']:raise ValueError('Overlay SHA mismatch: '+name)
        current=member(target,name)
        if meta['base_sha256'] is not None:
            if not current.exists() or sha(current.read_bytes().replace(b'\r\n',b'\n'))!=meta['base_lf_sha256']:
                raise ValueError('Overlay requires a different p3 source: '+name)
        elif current.exists():raise ValueError('New overlay member already exists: '+name)
        writes[name]=data
    config_name='config/ai_pc/mode_b_full_workspace_20261030.json'
    if profile=='strict':
        config=json.loads(writes[config_name]);config['maximum_additional_grasp_tilt_deg']=10
        config['maximum_grasp_tcp_raise_mm']=0
        config['profile_status']='STRICT_10_DEGREE_COMPARISON_PROFILE'
        writes[config_name]=(json.dumps(config,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
    report=dict(patch_id=PATCH_ID,profile=profile,source_files=len(writes),base_integrity_passed=True,
        hardware_access=False,physical_test='NOT_RUN',applied=False)
    if not apply:return report
    stamp=datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    backup=target/'backups'/('before_'+PATCH_ID+'_'+stamp+'.zip');backup.parent.mkdir(parents=True,exist_ok=True)
    extra='evidence/'+PATCH_ID+'/'
    writes[extra+'base_manifest.json']=original
    writes[extra+'pc_tests.json']=(bundle/'pc_tests.json').read_bytes()
    receipt=dict(patch_id=PATCH_ID,profile=profile,base_manifest_sha256=sha(original),
        base_patch_id=base['patch_id'],changed_files={n:sha(d) for n,d in writes.items()},
        full_workspace_physical_validated=False,hardware_access=False)
    writes[extra+'receipt.json']=(json.dumps(receipt,indent=2)+'\n').encode()
    updated=dict(base);updated['patch_id']=PATCH_ID
    updated['inputs']={**base['inputs'],**{n:sha(d) for n,d in writes.items()}}
    updated['full_workspace_policy']=dict(profile=profile,historical_anchor_radius_gate=False,
        physical_full_workspace_validated=False)
    writes['mode_ab_manifest.json']=(json.dumps(updated,indent=2)+'\n').encode()
    sums={**updated['inputs'],'mode_ab_manifest.json':sha(writes['mode_ab_manifest.json'])}
    writes['sha256sums.txt']=(''.join(d+'  '+n+'\n' for n,d in sorted(sums.items()))).encode()
    before={n:member(target,n).read_bytes() if member(target,n).exists() else None for n in writes}
    saved={n:d for n,d in before.items() if d is not None}
    with zipfile.ZipFile(backup,'x',zipfile.ZIP_DEFLATED) as z:
        for n,d in saved.items():z.writestr(n,d)
        z.writestr('backup_manifest.json',json.dumps({n:sha(d) for n,d in saved.items()},indent=2))
    with zipfile.ZipFile(backup) as z:
        if z.testzip() is not None or not saved:raise ValueError('Backup CRC/empty failure')
        for n,d in saved.items():
            if sha(z.read(n))!=sha(d):raise ValueError('Backup SHA failure: '+n)
    try:
        for n,d in writes.items():
            p=member(target,n);p.parent.mkdir(parents=True,exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=p.parent,delete=False) as f:f.write(d);tmp=f.name
            os.replace(tmp,p)
        for n,d in sums.items():
            if sha(member(target,n).read_bytes())!=d:raise ValueError('Installed input SHA mismatch: '+n)
    except Exception:
        for n,d in before.items():
            p=member(target,n)
            if d is None:p.unlink(missing_ok=True)
            else:p.write_bytes(d)
        raise
    report.update(applied=True,backup=str(backup),backup_sha256=sha(backup.read_bytes()),
        installed_input_files=len(updated['inputs']))
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--bundle',type=Path,required=True)
    p.add_argument('--target',type=Path,required=True);p.add_argument('--apply',action='store_true')
    p.add_argument('--profile',choices=['full_frame','strict'],default='full_frame')
    a=p.parse_args();print(json.dumps(install(a.bundle,a.target,apply=a.apply,profile=a.profile),ensure_ascii=False,indent=2))
