"""Build versioned Giao routes and bound geometry proofs, without devices."""
import json
from pathlib import Path
import sys
import time
import argparse
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from pc.mode_ab.motion import template,build_banks,compile_banks,native_with_front,restock_native,compile_restock
from pc.mode_ab.family import verify,fingerprint


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--reuse-family-proof',action='store_true');args=ap.parse_args()
    results=[]
    for profile,name in [('red_legacy','red_cube'),('red_depth12','red_cube'),('eraser','eraser'),('small_canister','small_canister')]:
        folder=ROOT/'candidate/mode_ab/profiles'/profile
        folder.mkdir(parents=True,exist_ok=True);started=time.perf_counter()
        p=template(name,profile);source=p['request']['pickup']
        banks,front=build_banks(name,source['centre_mm'],source['yaw_deg'],use_cache=args.reuse_family_proof,selected_profile=profile)
        for i,b in enumerate(banks):(folder/f'native_bank{i}.json').write_text(json.dumps(b))
        (folder/'front.json').write_text(json.dumps(front))
        c=compile_banks(banks,front)
        print(profile,'COMPILED',len(c['fifo']),len(c['segments']),flush=True)
        cert_file=folder/'family_certificate.json'
        old=json.loads(cert_file.read_bytes()) if args.reuse_family_proof and cert_file.exists() else None
        proof=old['proof'] if old and old['fingerprint']==fingerprint(c,banks[1]) else verify(c,banks[1],use_certificate=False)
        cert=dict(schema='gesture.mode_ab.family_certificate.v1',fingerprint=fingerprint(c,banks[1]),
                  tcp_from_object=banks[1]['tcp_from_object'],proof=proof)
        (folder/'family_certificate.json').write_text(json.dumps(cert,indent=2))
        c['fresh_handover_family']=verify(c,banks[1]);(folder/'normal.json').write_text(json.dumps(c))
        native=native_with_front(banks[1],front);(folder/'native.json').write_text(json.dumps(native))
        origin=folder/'offline_origin.json';origin.write_text(json.dumps(dict(task_id='OFFLINE_NOT_PL_COMPLETION')))
        rp=restock_native(native,origin);rc=compile_restock(rp)
        (folder/'restock_native.json').write_text(json.dumps(rp));(folder/'restock.json').write_text(json.dumps(rc))
        result=dict(profile=profile,class_name=name,normal_fifo=len(c['fifo']),table_segments=len(c['segments']),
            restock_fifo=len(rc['fifo']),normal_geometry=c['geometry'],restock_geometry=rc['geometry'],
            family=proof,certificate=c['fresh_handover_family'],seconds=time.perf_counter()-started,physical_test='NOT_RUN')
        (folder/'summary.json').write_text(json.dumps(result,indent=2));results.append(result)
        print(profile,'PASS',result['seconds'],flush=True)
    out=ROOT/'board_evidence/mode_ab_p3/profiles.json'
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(dict(passed=True,profiles=results),indent=2))


if __name__=='__main__':main()
