"""Compile four finite alignment banks with one shared S4 segment topology."""
from pathlib import Path
import argparse,contextlib,copy,io,json,math,csv,hashlib
import numpy as np
from scipy.spatial.transform import Rotation
from plan_mode_a_delivery_layout import AXES
from plan_mode_a_delivery_layout import prepare,scene_export,ROOT
from prepare_mode_a_cancel_shift_v082 import ShiftedPreModel
from mode_a_follow_profile import profile,retime
from mode_a_board_profile import p2p,waypoint_group
from compile_mode_a_sim_tables import compile_plan


class LocalModel(ShiftedPreModel):
    def __init__(self,pre_x,max_tilt=40):
        super().__init__();self.pre_x=pre_x;self.max_tilt=max_tilt
    def tilt(self,p):
        if p[0]>=360:return super().tilt(p)
        angle=min(40,20+(360-p[0])*20/(360-self.pre_x))
        # Far-Y bank: reduce held-block tilt, then restore 40deg over the
        # already-planned clearance lift. TCP positions/heights stay fixed.
        cap=min(40,self.max_tilt+max(0,p[2]-175)*(40-self.max_tilt)/20)
        return min(angle,cap)


def table(plan):
    t=compile_plan(dict(plan,home_sim_rad=plan['home_native_rad']));pos=0
    def mark(legs):
        nonlocal pos
        for i,l in enumerate(legs):
            same=i+1<len(legs) and waypoint_group(l['label'])==waypoint_group(legs[i+1]['label'])
            units=0 if same else (50 if l['phase'] in ('grasp','release') else 22)
            t['segments'][pos][4]|=2|(units<<2);pos+=1
    for r in plan['paths']:
        for ph in ('approach','grasp','lift'):mark([l for l in r['legs'] if l['phase']==ph])
    for ph in ('deliver','release','retreat'):mark([l for l in plan['paths'][0]['legs'] if l['phase']==ph])
    t.update(abi=dict(arm=0x3101,planner=0x3202,task=0x3409,vision=0x3505,model=0x022267a9),hold_policy=False,
        arrival_mask=0,tray_exit=False,layout_id=plan['layout_id'],execution_profile=profile())
    return t


def export_final(folder,p,t,model):
    count=0;maxv=maxa=maxerr=maxrot=maxchord=0.
    for route in p['paths']+p['hover_paths']+p['return_paths']:
        for i,leg in enumerate(route['legs']):
            vals=np.array([leg['start_q16']]+[r['q16'] for r in route['samples'] if r['segment']==i])/65536
            for q in vals:model.check(q)
            maxv=max(maxv,float(np.abs(np.diff(vals,axis=0)).max())/.02)
            if len(vals)>2:maxa=max(maxa,float(np.abs(np.diff(vals,n=2,axis=0)).max())/.02**2)
            if leg.get('target_D_mm') is not None:
                f=model.native_fk(vals[-1])[0]
                maxerr=max(maxerr,float(np.linalg.norm(f[:3,3]-model.world(leg['target_D_mm'])))*1000)
                maxrot=max(maxrot,float(np.linalg.norm(Rotation.from_matrix(model.desired_rotation(leg['target_D_mm']).T@f[:3,:3]).as_rotvec())))
            if leg['label'].startswith(('DESCEND','LIFT','RETURN_DESCEND','RETURN_CLEAR','HANDOVER','HAND_CLEAR')):
                pa=np.array(model.desk(vals[0]));pb=np.array(model.desk(vals[-1]));d=pb-pa
                for q in vals:
                    actual=np.array(model.desk(q));u=np.clip(np.dot(actual-pa,d)/max(1e-12,np.dot(d,d)),0,1)
                    maxchord=max(maxchord,float(np.linalg.norm(actual-pa-u*d)))
            count+=len(vals)-1
    p['validation']=dict(routes=9,samples=count,max_velocity_deg_s=math.degrees(maxv),max_acceleration_difference_deg_s2=math.degrees(maxa),max_target_position_after_quantization_mm=maxerr,max_target_orientation_after_quantization_rad=maxrot,max_cartesian_chord_mm=maxchord)
    with (folder/'JOINT_TARGETS_NATIVE.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.writer(f);w.writerow(['object','trial','label','phase','X_mm','Y_mm','Z_mm',*AXES,'seconds','tilt_deg'])
        for route in p['paths']+p['hover_paths']+p['return_paths']:
            for leg in route['legs']:w.writerow([route['object'],route['kind'],leg['label'],leg['phase'],*(leg.get('target_D_mm') or ['','','']),*[v/65536 for v in leg['target_q16']],leg['seconds'],leg['tool_tilt_deg']])
    preview=[];timing=[]
    for route in p['paths']:
        rows=[]
        for i,row in enumerate(route['samples']):
            if i%10 and i+1<len(route['samples']) and route['samples'][i+1]['segment']==row['segment']:continue
            q=[v/65536 for v in row['q16']];leg=route['legs'][row['segment']]
            rows.append(dict(interpolation_s=(i+1)*.02,phase=leg['phase'],label=leg['label'],D_mm=model.desk(q),native_rad=q))
        preview.append(dict(object=route['object'],rows=rows))
        settle=sum(0 if i+1<len(route['legs']) and waypoint_group(l['label'])==waypoint_group(route['legs'][i+1]['label']) else (.8 if l['phase'] in ('grasp','release') else .352) for i,l in enumerate(route['legs']))
        timing.append(dict(object=route['object'],interpolation_s=route['seconds'],fixed_settle_s=settle,nominal_without_operator_wait_s=route['seconds']+settle))
    (folder/'PATH_PREVIEW.json').write_text(json.dumps(dict(source='Final shared-duration S2 samples, every tenth plus endpoints',paths=preview),indent=2)+'\n')
    (folder/'SUMMARY.json').write_text(json.dumps(dict(result='V2_FINAL_SHARED_BANK_REFERENCE_PASS',validation=p['validation'],capacity=t['capacity'],timing=timing,layout=p['layout'],profile=profile(),physical_robot=False),indent=2)+'\n')


def main(out):
    out.mkdir(parents=True,exist_ok=False);plans=[];tables=[]
    for bank,y in enumerate((135,195,255,255)):
        layout=json.loads((ROOT/'planning/mode_a_layout_v082.json').read_text('utf-8'))
        layout['layout_id']='mode_a_follow_y_'+str(y)
        layout['camera']['reported_view_D_xy_mm']=[[0,0],[390,390]]
        layout['camera']['height_dependent_pixel_mapping']='NOMINAL_PINHOLE_APPROXIMATION_NOT_PHYSICALLY_CALIBRATED'
        layout['common_D_mm']['PRE']=[350,y+20,180]
        layout['common_D_mm']['H']=[285,y,175]
        layout['common_D_mm']['H_CLEAR']=[285,y,195]
        layout['delivery_pose']=dict(type='Radial tilt',held_H_deg=35 if bank>=2 else 40,clear_deg=40,method='HEIGHT_BLEND_175_TO_195_MM' if bank>=2 else 'CONSTANT')
        lp=out/('layout_bank'+str(bank)+'.json');lp.write_text(json.dumps(layout,indent=2)+'\n','utf-8')
        folder=out/('bank'+str(bank));model=LocalModel(layout['common_D_mm']['PRE'][0],35 if bank>=2 else 40)
        with contextlib.redirect_stdout(io.StringIO()):prepare(lp,folder,model,retime,profile(),'0.11.0')
        p=json.loads((folder/'PLAN_NATIVE.json').read_text('utf-8'))
        # Eight 10mm handover subdivisions give all banks the same topology.
        for ri,route in enumerate(p['paths']):
            old=route['legs'];first=next(i for i,l in enumerate(old) if l['phase']=='deliver');last=next(i for i,l in enumerate(old) if l['phase']=='release')
            seed=[q/65536 for q in old[first]['start_q16']];added=[];a=layout['common_D_mm']['PRE'];b=layout['common_D_mm']['H']
            for k in range(1,9):
                point=[x+(y-x)*k/8 for x,y in zip(a,b)];goal=model.native_ik(point,seed);goal[5]=p['hold_native_rad']
                leg=copy.deepcopy(old[first]);leg.update(label='HANDOVER_'+str(k),start_q16=[round(v*65536) for v in seed],target_q16=[round(v*65536) for v in goal],target_D_mm=point,tool_tilt_deg=model.tilt(point))
                added.append(leg);seed=goal
            route['legs']=old[:first]+added+old[last:]
            for i in range(first+8,len(route['legs'])):
                route['legs'][i]['start_q16']=route['legs'][i-1]['target_q16'][:]
                if route['legs'][i]['phase']=='release':route['legs'][i]['target_q16'][:5]=route['legs'][i]['start_q16'][:5]
            # Normalize the 20mm clearance to two identical 10mm steps in all banks.
            legs=route['legs'];c0=next(i for i,l in enumerate(legs) if l['label'].startswith('HAND_CLEAR'));c1=next(i for i,l in enumerate(legs) if i>c0 and not l['label'].startswith('HAND_CLEAR'))
            seed=[q/65536 for q in legs[c0]['start_q16']];clears=[];a=layout['common_D_mm']['H'];b=layout['common_D_mm']['H_CLEAR']
            for k in (1,2):
                point=[x+(y-x)*k/2 for x,y in zip(a,b)];goal=model.native_ik(point,seed);goal[5]=p['open_native_rad']
                leg=copy.deepcopy(legs[c0]);leg.update(label='HAND_CLEAR_'+str(k),start_q16=[round(v*65536) for v in seed],target_q16=[round(v*65536) for v in goal],target_D_mm=point,tool_tilt_deg=model.tilt(point))
                clears.append(leg);seed=goal
            route['legs']=legs[:c0]+clears+legs[c1:]
            for i in range(c0+2,len(route['legs'])):route['legs'][i]['start_q16']=route['legs'][i-1]['target_q16'][:]
            p['paths'][ri]=retime(route)
        plans.append(p);tables.append(table(p))
    base=tables[1]
    # Same keypoint IDs and phase ranges in every bank; one shared segment RAM.
    for t in tables:
        assert t['descriptors']==base['descriptors'] and t['capacity']==base['capacity']
        assert [(s[0],s[3],s[4]) for s in t['segments']]==[(s[0],s[3],s[4]) for s in base['segments']]
    common=[]
    for ss in zip(*(t['segments'] for t in tables)):
        n=max(s[1] for s in ss);common.append([ss[0][0],n,max(1,n//4),ss[0][3],ss[0][4]])
    # Regenerate exact samples with the shared duration used by the hardware.
    durations={}
    for obj in (1,2,3):
        route=plans[1]['paths'][obj-1]
        for ph in ('approach','grasp','lift'):
            first,count=base['descriptors'][f'{ph}_{obj}']
            for i,l in enumerate([l for l in route['legs'] if l['phase']==ph]):durations[(obj,l['label'])]=common[first+i][1:3]
        for ph in ('deliver','release','retreat'):
            first,count=base['descriptors'][ph]
            for i,l in enumerate([l for l in route['legs'] if l['phase']==ph]):durations[(obj,l['label'])]=common[first+i][1:3]
    max_align_n=20;pairs=[]
    for ai,a in enumerate(tables):
        for bi,b in enumerate(tables):
            qa=a['keypoints'][a['predelivery_kp']];qb=b['keypoints'][b['predelivery_kp']]
            from mode_a_follow_profile import segment
            meta,_=segment(qa,qb,'HANDOVER_ALIGN','deliver');max_align_n=max(max_align_n,meta['n']);pairs.append(dict(from_bank=ai,to_bank=bi,n=meta['n'],na=meta['na'],seconds=meta['seconds']))
    summary=[]
    for bank,(p,t) in enumerate(zip(plans,tables)):
        for r in p['paths']:
            r['samples']=[]
            for i,l in enumerate(r['legs']):
                l['n'],l['na']=durations[(r['object'],l['label'])];l['seconds']=l['n']*.02
                cfg=p2p.MoveParams(tuple(l['start_q16']),tuple(l['target_q16']),l['n'],l['na'],1,2000000,50000000,
                    (math.ceil(math.radians(49.5)*.02*65536)+2,)*6,(math.ceil(math.radians(163.35)*.02**2*(1<<32))+2,)*6)
                assert p2p.validate(cfg,last_delivered=cfg.start).ok
                r['samples'].extend(dict(segment=i,tick=k+1,q16=list(q)) for k,q in enumerate(p2p.samples(cfg)))
            r['seconds']=sum(l['seconds'] for l in r['legs'])
        t['segments']=copy.deepcopy(common);folder=out/('bank'+str(bank));export_final(folder,p,t,LocalModel(p['layout']['common_D_mm']['PRE'][0],35 if bank>=2 else 40))
        (folder/'PLAN_NATIVE.json').write_text(json.dumps(p,indent=2)+'\n','utf-8')
        (folder/'SCENE_PLAN.json').write_text(json.dumps(scene_export(p,LocalModel(p['layout']['common_D_mm']['PRE'][0],35 if bank>=2 else 40)),indent=2)+'\n','utf-8')
        (folder/'S4_NATIVE_CANDIDATE.json').write_text(json.dumps(t,indent=2)+'\n','utf-8')
        summary.append(dict(bank=bank,desk_Y_mm=(135,195,255,255)[bank],PRE=p['layout']['common_D_mm']['PRE'],H=p['layout']['common_D_mm']['H'],capacity=t['capacity']))
    combined=copy.deepcopy(base);combined['keypoint_banks']=[t['keypoints'] for t in tables];combined['segments']=common
    combined.update(default_bank=1,active_banks=[0,1,2],spare_bank=3,align_n=max_align_n,align_na=max(1,max_align_n//4),banks=summary,align_pairs=pairs,camera_projection=dict(model='NOMINAL_DOWNWARD_PINHOLE',table_side_mm=390,camera_z_mm=333,palm_z_mm=150,palm_side_mm=390*(333-150)/333,nominal_y_centers_mm=[195+(k/4+.125-.5)*390*(333-150)/333 for k in range(4)],rounded_H_y_mm=[135,195,255],image_thresholds=[54,74],image_up_is_desk_plus_y=True))
    (out/'S4_BANKED_CANDIDATE.json').write_text(json.dumps(combined,indent=2)+'\n','utf-8')
    print('FOUR_BANKS_PASS',summary,'ALIGN_N',max_align_n)


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);main(ap.parse_args().out)
