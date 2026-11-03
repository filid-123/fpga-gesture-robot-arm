"""Prepare portable class transport banks once; no serial, JTAG or camera."""
from pathlib import Path
import json
import sys
import time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from pc.mode_ab.motion import template,build_banks,compile_banks,native_with_front,restock_native,compile_restock


def main():
    base=ROOT/'candidate/mode_ab'
    for name in ('red_cube','eraser','small_canister'):
        folder=base/name
        if folder.exists():raise FileExistsError(folder)
        folder.mkdir(parents=True)
        p=template(name);start=time.perf_counter()
        banks,front=build_banks(name,p['request']['pickup']['centre_mm'],p['request']['pickup']['yaw_deg'],use_cache=False)
        for i,b in enumerate(banks):(folder/f'native_bank{i}.json').write_text(json.dumps(b))
        (folder/'front.json').write_text(json.dumps(front))
        c=compile_banks(banks,front);(folder/'normal.json').write_text(json.dumps(c))
        native=native_with_front(banks[1],front)
        (folder/'native.json').write_text(json.dumps(native))
        # This fixture is explicitly offline and is never an operational origin.
        origin=folder/'offline_origin.json';origin.write_text(json.dumps(dict(task_id='OFFLINE_FIXTURE_NOT_PL_COMPLETION')))
        rp=restock_native(native,origin);rc=compile_restock(rp)
        (folder/'restock_native.json').write_text(json.dumps(rp));(folder/'restock.json').write_text(json.dumps(rc))
        (folder/'summary.json').write_text(json.dumps(dict(class_name=name,normal_fifo=len(c['fifo']),table_segments=len(c['segments']),
            restock_fifo=len(rc['fifo']),normal_geometry=c['geometry'],restock_geometry=rc['geometry'],
            physical_test='NOT_RUN',preparation_seconds=time.perf_counter()-start),indent=2))
        print(name,'READY',len(c['fifo']),len(c['segments']),len(rc['fifo']),flush=True)


if __name__=='__main__':main()
