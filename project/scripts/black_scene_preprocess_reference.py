"""Independent integer PIL-BILINEAR and fixed-point ROI reference (no training)."""
from pathlib import Path
import argparse, json
import numpy as np
from PIL import Image
import cv2

ROOT=Path(__file__).resolve().parent.parent
PKG=ROOT/'model_package/candidates/black_scene_vision_v1_int8_20261013'

def coefficients(side):
    support=max(64,2*side); rows=[]
    for dst in range(32):
        center=(2*dst+1)*side
        taps=[(src,support-abs((2*src+1)*32-center)) for src in range(side)]
        taps=[(src,w) for src,w in taps if w>0]
        total=sum(w for _,w in taps)
        rows.append([(src,((w<<22)+(total//2))//total) for src,w in taps])
    return rows

def resize_integer(gray):
    side=gray.shape[0]; assert gray.shape==(side,side)
    co=coefficients(side)
    horiz=np.empty((side,32),dtype=np.uint8)
    for x,taps in enumerate(co):
        accum=np.full(side,1<<21,dtype=np.int64)
        for src,w in taps:accum+=gray[:,src].astype(np.int64)*w
        horiz[:,x]=np.clip(accum>>22,0,255)
    result=np.empty((32,32),dtype=np.uint8)
    for y,taps in enumerate(co):
        accum=np.full(32,1<<21,dtype=np.int64)
        for src,w in taps:accum+=horiz[src].astype(np.int64)*w
        result[y]=np.clip(accum>>22,0,255)
    return result

def emit_mem(path, values, bits=32):
    values=np.asarray(values)
    if values.dtype==np.uint8:
        values=np.frombuffer(values.tobytes(),dtype='<u4')
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(''.join(f'{int(v)&((1<<bits)-1):0{bits//4}x}\n' for v in values.reshape(-1)),encoding='ascii')

def verify():
    out=ROOT/'native_motion/sim/black_scene/generated'; out.mkdir(parents=True,exist_ok=True)
    items=json.loads((PKG/'golden_integer/index.json').read_text())['samples']
    checked=0;cases=[]
    for item in items:
        frame=cv2.imread(str(PKG/item['image']));gray=cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY)
        emit_mem(out/(item['id']+'_gray_vga.mem'),gray)
        roi=item['pipeline']['roi_source']
        if roi:
            x0,y0,x1,y1=roi; crop=gray[y0:y1,x0:x1]
            actual=resize_integer(crop)
            pil=np.asarray(Image.fromarray(crop).resize((32,32),Image.Resampling.BILINEAR))
            if not np.array_equal(actual,pil):
                raise ValueError(f'{item["id"]}: integer resampler differs from PIL by {np.max(np.abs(actual.astype(int)-pil.astype(int)))}')
            words=np.array([int(v,16) for v in (PKG/'golden_integer'/item['id']/'pipeline_classifier_input_u8.mem').read_text().splitlines()],dtype='<u4')
            if not np.array_equal(actual,np.frombuffer(words.tobytes(),dtype=np.uint8).reshape(32,32)):
                raise ValueError(f'{item["id"]}: pipeline classifier input differs')
            emit_mem(out/(item['id']+'_roi_expected.mem'),actual)
            cases.append((item['id'],gray,roi,actual))
            checked+=1
    # Cover geometry boundaries, upsample, non-divisible sides, high contrast and noise.
    rng=np.random.default_rng(14); extra=0
    for side in [1,2,3,7,16,31,32,33,47,63,64,95,127,128,129,237,319,471,479,480]:
        for source in [rng.integers(0,256,(side,side),dtype=np.uint8),
                       ((np.indices((side,side)).sum(axis=0)&1)*255).astype(np.uint8)]:
            actual=resize_integer(source)
            pil=np.asarray(Image.fromarray(source).resize((32,32),Image.Resampling.BILINEAR))
            assert np.array_equal(actual,pil),f'side={side}'
            extra+=1
    for side in [1,31,32,33,237,479]:
        frame=rng.integers(0,256,(480,640),dtype=np.uint8)
        roi=[640-side,480-side,640,480]
        cases.append((f'boundary_{side}',frame,roi,resize_integer(frame[480-side:,640-side:])))
    configs=[]
    for i,(name,frame,roi,expected) in enumerate(cases):
        x0,y0,x1,y1=roi
        configs.append(x0|(y0<<10)|((x1-x0)<<20))
        emit_mem(out/f'roi_case_{i:02d}_source.mem',frame)
        emit_mem(out/f'roi_case_{i:02d}_expected.mem',expected)
    emit_mem(out/'roi_cases.mem',np.array(configs,dtype=np.uint32))
    (out/'roi_cases.json').write_text(json.dumps([{'id':i,'source':c[0],'roi':c[2]} for i,c in enumerate(cases)],indent=2)+'\n')
    result={'status':'PASS','pipeline_roi_samples':checked,'PIL_boundary_cases':extra,'RTL_cases':len(cases),
            'coefficient_precision':22,'max_taps':max(len(t) for t in coefficients(480)),
            'training_performed':False,'RTL_verified':False}
    (ROOT/'reports/roarm_mode_a/preprocess_reference.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))

if __name__=='__main__':verify()
