"""Build a one-time discrete image-Y map from three stationary PALM monitor logs."""
import argparse,hashlib,json,statistics
from pathlib import Path
from mode_a_v091_config import validate_map

def samples(path):
 rows=[json.loads(s) for s in path.read_text('utf-8').splitlines() if s.strip()];seen=set();points=[]
 for r in rows:
  if r.get('model')!='PALM' or not r.get('qualified') or r.get('image_age_ms',9999)>250 or r.get('motion_frames',1)!=0:continue
  if r['frame'] in seen:continue
  seen.add(r['frame']);points.append(r['bbox_center_px'])
 if len(points)<12:raise ValueError(str(path)+': need at least 12 distinct fresh qualified PALM frames with tx=0')
 return points

def make(paths):
 pts=[samples(p) for p in paths];cy=[statistics.median(p[1] for p in rows) for rows in pts]
 order=sorted(range(3),key=lambda i:cy[i])
 if order[1]!=1 or min(abs(cy[a]-cy[b]) for a,b in zip(order,order[1:]))<3:raise ValueError('Three vertical-image PALM centers must be distinct (>=3px) and center between sides; repeat capture at desk-Y front/center/back at -20/0/+20mm')
 a,b,c=[cy[i] for i in order];bound0=int((a+b)//2);bound1=int((b+c)//2)
 ranges=[(max(16,int(a-(b-a)/2)),bound0),(bound0+1,bound1),(bound1+1,min(111,int(c+(c-b)/2)))]
 cells=[dict(bank=bank,x0=0,x1=127,y0=ranges[k][0],y1=ranges[k][1]) for k,bank in enumerate(order)]
 result=dict(schema='gesture.mode_a.handmap.v1',revision=1,calibrated=True,image_axis='Y',desk_axis='Y',method='THREE_OPERATOR_PLACED_PALM_CENTERS_DISCRETE_Y_ONLY',cells=cells,source_hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},median_bbox_centers_px=[[statistics.median(p[0] for p in pts[i]),cy[i]] for i in range(3)],frame_counts=list(map(len,pts)),physical_H_D_mm=[[240,135,175],[240,155,175],[240,175,175]],continuous_XY=False)
 return validate_map(result,True)

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--front',type=Path,required=True);ap.add_argument('--center',type=Path,required=True);ap.add_argument('--back',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
 m=make([a.front,a.center,a.back])
 with a.out.open('x',encoding='utf-8') as f:f.write(json.dumps(m,indent=2)+'\n')
 print(json.dumps(m,indent=2))
