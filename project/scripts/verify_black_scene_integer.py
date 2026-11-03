"""Read-only audit of every frozen file and the full integer CNN goldens.

Uses NumPy and the supplied integer reference; no torch, training or inference
framework provider is required for the CNN checks.
"""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
DEFAULT = ROOT/'model_package/candidates/black_scene_vision_v3_int8_targeted600_B_gate030_20261027'

def verify(pkg):
    checked=0
    for line in (pkg/'CHECKSUMS.sha256').read_text(encoding='utf-8').splitlines():
        if not line.strip(): continue
        digest, name = line.split(None,1)
        path=pkg/name.lstrip('*').strip()
        if hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
            raise ValueError(f'Frozen input checksum mismatch: {name}')
        checked+=1
    spec=importlib.util.spec_from_file_location('frozen_integer_reference',pkg/'reference/integer_vision_reference.py')
    ref=importlib.util.module_from_spec(spec); spec.loader.exec_module(ref)
    lp=dict(np.load(pkg/'quantized/locator/parameters.npz',allow_pickle=False))
    cp=dict(np.load(pkg/'quantized/classifier/parameters.npz',allow_pickle=False))
    samples=json.loads((pkg/'golden_integer/index.json').read_text(encoding='utf-8'))['samples']
    layers=0
    for item in samples:
        vectors=np.load(pkg/item['vectors'],allow_pickle=False)
        _,ls,_=ref.forward_locator(vectors['locator_input_u8'],lp)
        _,cs,_=ref.forward_classifier(vectors['classifier_input_u8'],cp)
        _,lo,_=ref.forward_locator(vectors['locator_input_u8'],lp,oracle=True)
        _,co,_=ref.forward_classifier(vectors['classifier_input_u8'],cp,oracle=True)
        for prefix, stages, oracle in [('locator',ls,lo),('classifier',cs,co)]:
            for name,value in stages.items():
                if not np.array_equal(value,vectors[prefix+'_'+name]):
                    raise ValueError(f'{item["id"]}/{prefix}/{name}: golden mismatch')
                if not np.array_equal(value,oracle[name]):
                    raise ValueError(f'{item["id"]}/{prefix}/{name}: independent oracle mismatch')
                layers+=1
        print(f'PASS {item["id"]}: every CNN layer and independent oracle',flush=True)
    manifest=json.loads((pkg/'quantized/manifest.json').read_text(encoding='utf-8'))
    return {'status':'PASS','files':checked,'samples':len(samples),'layer_checks':layers,
            'Rain_commit':'022267a939c892d73ae278ceddee1a3e856a8dee',
            'class_order':['background','one','two','three','fist','palm'],
            'confidence_threshold_i32':manifest['confidence_threshold_raw_i32'],
            'training_performed':False,'RTL_verified':False}

if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--package',type=Path,default=DEFAULT)
    ap.add_argument('--out',type=Path,default=ROOT/'reports/roarm_mode_a/integer_audit.json')
    args=ap.parse_args(); result=verify(args.package)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))
