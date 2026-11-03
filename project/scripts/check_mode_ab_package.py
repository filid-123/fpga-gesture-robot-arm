"""Standalone complete-package integrity and portable entry/dependency checks."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import zipfile
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def check(root):
    root=root.resolve()
    from run_mode_ab import load
    manifest,plan,table,transitions=load(root)
    baseline_inputs=None;patch_sources=set()
    if manifest.get('patch_id')=='full_workspace_policy_p4':
        folder=root/'evidence/full_workspace_policy_p4'
        receipt=json.loads((folder/'receipt.json').read_bytes())
        baseline=json.loads((folder/'base_manifest.json').read_bytes())
        if receipt['base_manifest_sha256']!=sha(folder/'base_manifest.json') or baseline.get('patch_id')!='planning_ux_giao_p3':
            raise ValueError('P4 baseline receipt differs')
        baseline_inputs=baseline['inputs'];patch_sources=set(receipt['changed_files'])
        for name,digest in receipt['changed_files'].items():
            if sha(root/name)!=digest:raise ValueError('P4 source changed: '+name)
        proof=json.loads((folder/'pc_tests.json').read_bytes())
        if not proof['passed'] or proof['hardware_access']:raise ValueError('P4 PC regression proof missing')
        for name,digest in proof['source_hashes'].items():
            if sha(root/name)!=digest:raise ValueError('P4 PC proof source changed: '+name)
    binding=json.loads((root/'evidence/implementation/built_source_hashes.json').read_bytes())
    for name,digest in binding['files'].items():
        if sha(root/name)!=digest:raise ValueError('Hardware source binding differs: '+name)
    impl=json.loads((root/'evidence/implementation/implementation_summary.json').read_bytes())
    native=manifest.get('patch_id')=='native_giao_full_workspace_p4'
    if impl['task_abi']!=(0x340e if native else 0x340d) or min(impl['timing_ns']['WNS'],impl['timing_ns']['WHS'])<0:raise ValueError('Wrong hardware timing/ABI')
    for name,meta in impl['artifacts'].items():
        if sha(root/'hardware'/name)!=meta['sha256']:raise ValueError('Hardware artifact differs')
    with zipfile.ZipFile(root/'hardware/roarm_closed_loop.xsa') as z:
        if z.testzip():raise ValueError('XSA CRC')
        for ext in ('bit','hwh'):
            n='roarm_closed_loop.'+ext
            if hashlib.sha256(z.read(n)).hexdigest()!=sha(root/'hardware'/n):raise ValueError('XSA member differs')
    from verify_mode_b_visual_bundle import verify_current
    current,freeze,work=verify_current(root)
    if native:
        from check_mode_ab_p4 import verify
        return verify(root,manifest,binding,impl,freeze,current)
    for name in ('profiles/red_depth12','profiles/red_legacy','profiles/eraser','profiles/small_canister','shared_red'):
        for kind in ('normal','restock'):
            c=json.loads((root/'candidate/mode_ab'/name/(kind+'.json')).read_bytes())
            if c['task_abi']!=0x340d or not 0<len(c['fifo'])<=63:raise ValueError('B path ABI/capacity')
            if sum(bool(x['flags']&1) for x in c['fifo'])!=1:raise ValueError('B path grasp semantics')
    expected=manifest['inputs']
    for line in (root/'sha256sums.txt').read_text().splitlines():
        digest,name=line.split('  ',1)
        if sha(root/name)!=digest:raise ValueError('Member SHA mismatch '+name)
    # Check sealed payload names; real Vivado/XSDB sessions also create .Xil
    # caches in this directory, which are runtime output rather than ZIP members.
    names=list(expected)+['mode_ab_manifest.json','sha256sums.txt']
    if any(name!=name.lower() or not all(re.fullmatch('[a-z0-9_.-]+',p) for p in Path(name).parts) for name in names):raise ValueError('Package member names must be lowercase ASCII')
    from pc.mode_ab.motion import ROOT as module_root
    if module_root.resolve()!=root:raise ValueError('Loaded a development-directory module')
    if manifest.get('patch_id')=='planning_hdmi_p2':
        for name in ('planning_hdmi_p2/pc_tests_a2/result.json','planning_hdmi_p2/scene_replay_a2/result.json','hdmi_p2/result.json'):
            proof=json.loads((root/'evidence'/name).read_bytes())
            if not proof['passed']:raise ValueError('P2 validation did not pass: '+name)
            for source,digest in proof.get('source_hashes',{}).items():
                if sha(root/source)!=digest:raise ValueError('P2 proof source changed: '+source)
    if manifest.get('patch_id') in ('planning_ux_giao_p3','full_workspace_policy_p4'):
        for name in ('pc_final_a4/result.json','replay_a4/result.json','gpu_a1/result.json','profiles.json'):
            proof=json.loads((root/'evidence/planning_ux_giao_p3'/name).read_bytes())
            if not proof['passed']:raise ValueError('P3 validation did not pass: '+name)
            for source,digest in proof.get('source_hashes',{}).items():
                actual=baseline_inputs.get(source) if source in patch_sources else sha(root/source)
                if actual!=digest:raise ValueError('P3 historical proof source changed: '+source)
        from pc.mode_ab.family import certificate
        for name in ('red_depth12','red_legacy','eraser','small_canister'):
            folder=root/'candidate/mode_ab/profiles'/name
            c=json.loads((folder/'normal.json').read_bytes());p=json.loads((folder/'native_bank1.json').read_bytes())
            if certificate(c,p) is None:raise ValueError('P3 family proof binding differs: '+name)
        for name in ('mode_ab_paths_p3a2','mode_ab_s2_p3a2'):
            proof=json.loads((root/'board_evidence'/name/'result.json').read_bytes())
            if not proof['passed']:raise ValueError('P3 RTL proof failed: '+name)
            for source,digest in proof['inputs'].items():
                if sha(root/source)!=digest:raise ValueError('P3 RTL vector differs: '+source)
    import tempfile
    from run_mode_a_restock import setup_tools
    with tempfile.TemporaryDirectory(prefix='mode_ab_factory_') as temp:
        bridge,server,exposure=setup_tools(root,Path(temp))
        if bridge.__name__!='BoardBridge' or not hasattr(exposure,'restore_sensor'):raise ValueError('Transport factory incomplete')
    return dict(result='COMPLETE_PACKAGE_HASH_BINDING_AND_ENTRY_PASS',version='0.1.0',patch_id=manifest.get('patch_id'),task_abi='340D',
        input_files=len(expected),built_sources=len(binding['files']),b_frozen_dependencies=len(freeze['files_sha256']),
        current_table_sha256=current['current_table_sha256'],transport_factory_imported=True,hardware_access=False,physical_test='NOT_RUN')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);a=p.parse_args();print(json.dumps(check(a.root),indent=2))
