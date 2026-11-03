"""Batch-one real HIP inference and frozen CPU comparison on measured images."""
import argparse
import json
import os
from pathlib import Path
import sys
import time
os.environ.setdefault('MIOPEN_FIND_MODE','FAST')
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import cv2
import numpy as np
import torch
from pc.mode_ab.gpu import RocmDetector,RocmSurface
from pc.multiobject.yolo import Detector
from pc.multiobject.surface import SurfaceRuntime
from pc.mode_b.tiled_detector import TiledDetector
from pc.mode_b.surface_ensemble import AlignedSurfaceEnsemble
from pc.mode_b.perception import Perception
from pc.mode_b.profile import Profile
from pc.rgb_table_geometry import RGBTableGeometry
from verify_mode_b_visual_bundle import verify_current,local
from replay_mode_b_visual_bundle import load_projection
from pc.mode_ab.vision_workspace import project_rows,WorkspaceDetector


def main(out):
    out.mkdir(parents=True,exist_ok=False);torch.set_num_threads(4)
    c,f,w=verify_current(ROOT)
    det=RocmDetector(local(ROOT,f['detector_package']))
    cpu=Detector(local(ROOT,f['detector_package']),'onnx_cpu')
    surface=RocmSurface(local(ROOT,f['surface_package']))
    reference=SurfaceRuntime(local(ROOT,f['surface_package']),'torch_cpu')
    geometry=RGBTableGeometry(local(ROOT,w['table_file']),ROOT)
    perception=Perception(WorkspaceDetector(TiledDetector(det),geometry,c['localization_dimensions']),AlignedSurfaceEnsemble(surface),Profile.load(local(ROOT,f['profile'])))
    xy=np.array(w['pattern_outer_corners_desktop_xyz_mm'])[:,:2];bounds=np.r_[xy.min(0),xy.max(0)]
    records=[]
    for fixture in c['successful_pose_reference_fixtures']:
        for fi in fixture['frames']:
            image=ROOT/fi['image'];frame=cv2.imread(str(image))
            found,meta=TiledDetector(det).run(frame);expected,_=TiledDetector(cpu).run(frame)
            if [r['class_name'] for r in found]!=[r['class_name'] for r in expected]:
                raise ValueError('GPU detector class comparison failed')
            score_error=max([abs(a['confidence']-b['confidence']) for a,b in zip(found,expected)]+[0])
            box_error=max([max(abs(np.array(a['bbox_xyxy_raw'])-b['bbox_xyxy_raw'])) for a,b in zip(found,expected)]+[0])
            if score_error>.002 or box_error>.1:
                raise ValueError('GPU detector output differs from frozen CPU beyond tolerance')
            selected=next((r for r in found if r['class_name']==fixture['class_name']),None)
            if not selected:raise ValueError('Measured object was not detected')
            p,_,sm=surface.run(frame,selected['bbox_xyxy_raw']);q,_,_=reference.run(frame,selected['bbox_xyxy_raw'])
            max_probability_error=float(np.max(abs(p-q)))
            if max_probability_error>.002:raise ValueError('Fused GPU surface comparison failed')
            obs=perception.infer(frame)
            rows=project_rows(obs,geometry,c['localization_dimensions'],bounds,load_projection())
            row=next(r for r in rows if r['class_name']==fixture['class_name'])
            if not row.get('geometry_gate_pass'):raise ValueError('Actual GPU metric geometry gate failed')
            record=dict(class_name=fixture['class_name'],image=fi['image'],image_sha256=fi['image_sha256'],
                        detector_timing_ms=meta.get('timing_ms',{}),detector_spatial_passes=meta['backend'].get('spatial_views'),detector_score_error=score_error,
                        detector_box_error_px=box_error,surface_max_probability_error=max_probability_error,
                        surface_total_ms=sm['total_ms'],surface_timing_ms=sm.get('timing_ms'),pipeline_total_ms=obs['total_ms'],localization=row)
            records.append(record);print(fixture['class_name'],row['object_centre_desktop_xyz_mm'],round(obs['total_ms'],2),flush=True)
            (out/'progress.json').write_text(json.dumps(records,indent=2))
    report=dict(passed=True,physical_execution=False,detector=det.info,surface=surface.info,
                samples=len(records),records=records,quantiles_ms={k:dict(zip(('p50','p95','p99','max'),
                map(float,np.percentile([r[k] for r in records],[50,95,99,100])))) for k in ('surface_total_ms','pipeline_total_ms')},
                caveat='Nine saved measured frames. First calls are recorded; pipeline measurements follow numerical comparisons and use warm models. Not live physical latency or task success rate',
                source_hashes={p.relative_to(ROOT).as_posix():__import__('hashlib').sha256(p.read_bytes()).hexdigest() for p in (ROOT/'pc/mode_ab/gpu.py',Path(__file__))})
    (out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS: frozen models on real HIP device, CPU numerical comparison and all nine metric frames')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);main(p.parse_args().out)
