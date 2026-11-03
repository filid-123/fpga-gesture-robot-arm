"""Verify the complete ABI3405 board package without opening hardware."""
from pathlib import Path
import hashlib,json,zipfile
from run_mode_a_board_v07 import load


def check(root):
    root=root.resolve();sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();count=0
    for row in (root/'SHA256SUMS').read_text('utf-8').splitlines():
        digest,name=row.split('  ',1);p=(root/name).resolve()
        if not p.is_relative_to(root) or sha(p)!=digest:raise ValueError('Package file changed '+name)
        count+=1
    plan,table,manifest=load(root)
    binding=root/'evidence/BUILT_SOURCE_HASHES.json'
    if sha(binding)!=manifest['hardware_source_binding_sha256']:raise ValueError('Source binding manifest')
    data=json.loads(binding.read_text('utf-8'))
    if data['parameters']['TIMED_WALKTHROUGH']!=1:raise ValueError('Wrong compiled policy')
    for name,digest in data['files'].items():
        if sha(root/name)!=digest:raise ValueError('Built source mismatch '+name)
    for name,d in manifest['artifacts'].items():
        if sha(root/'hardware'/name)!=d['sha256']:raise ValueError('Hardware '+name)
    with zipfile.ZipFile(root/'hardware/roarm_closed_loop.xsa') as z:
        if z.testzip():raise ValueError('XSA CRC')
        for ext in ('bit','hwh'):
            name='roarm_closed_loop.'+ext
            if hashlib.sha256(z.read(name)).hexdigest()!=manifest['artifacts'][name]['sha256']:raise ValueError('XSA internal binding')
    if '<PARAMETER NAME="TIMED_WALKTHROUGH" VALUE="1"/>' not in (root/'hardware/roarm_closed_loop.hwh').read_text('utf-8'):raise ValueError('HWH feature selection')
    return dict(result='BOARD_ALL_FILES_SOURCE_MODEL_TABLE_XSA_BINDING_PASS',version=manifest['version'],files=count,task_abi='3405',
        arrival_policy='observe_all',capacity=table['capacity'],hardware_access=False,physical_board_test='NOT_RUN')


if __name__=='__main__':print(json.dumps(check(Path(__file__).resolve().parents[1]),indent=2))
