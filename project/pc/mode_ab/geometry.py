"""Batched equivalent of the frozen URDF/OBB collision checks.

No mesh, clearance, intended contact, joint envelope or tilt threshold changes.
Batching removes Python loops over individual 20 ms trajectory samples.
"""
import math
import numpy as np
from scipy.spatial.transform import Rotation
from pc.mode_b.motion.kinematics import ORDER


def frames(robot,q):
    q=q+robot.bias
    n=len(q);out={'world':np.broadcast_to(robot.world,(n,4,4)).copy()}
    for joint in robot.joints:
        name=joint.attrib['name'];m=out[robot.parents[name]]@robot.origins[name]
        if name in ORDER:
            r=np.broadcast_to(np.eye(4),(n,4,4)).copy()
            r[:,:3,:3]=Rotation.from_rotvec(q[:,ORDER.index(name),None]*robot.axes[name]).as_matrix()
            m=m@r
        out[robot.children[name]]=m
    out['grasp']=out['link5']@robot.grasp@robot.tool_residual
    return out


def box(m,lo,hi):
    lo=np.asarray(lo);hi=np.asarray(hi)
    return (np.einsum('nij,j->ni',m[:,:3,:3],(lo+hi)/2)+m[:,:3,3],m[:,:3,:3],(hi-lo)/2)


def gap(a,b):
    ac,aa,ah=a;bc,ba,bh=b
    n=len(ac)
    aa=np.broadcast_to(aa,(n,3,3));ba=np.broadcast_to(ba,(n,3,3))
    av=aa.transpose(0,2,1);bv=ba.transpose(0,2,1)
    cross=np.cross(av[:,:,None,:],bv[:,None,:,:]).reshape(n,9,3)
    d=np.concatenate((av,bv,cross),axis=1);norm=np.linalg.norm(d,axis=2)
    d=d/np.maximum(norm[:,:,None],1e-30)
    radius=(abs(d@aa)@ah)+(abs(d@ba)@bh)
    values=abs(np.einsum('nkj,nj->nk',d,bc-ac))-radius
    values=np.where(norm>1e-8,values,-np.inf)
    sat=values.max(axis=1)
    sphere=np.linalg.norm(bc-ac,axis=1)-np.linalg.norm(ah)-np.linalg.norm(bh)
    return np.where(sphere>4,sphere,sat)


def bottom(a):
    c,axes,half=a
    return c[:,2]-abs(axes[:,2,:])@half


def validate(plan,qs,carrying,phase,cached, *, empty=False):
    from prepare_mode_b_loaded_route import payload_spec
    robot,world=cached
    qs=np.asarray(qs,float)
    if qs.ndim!=2 or qs.shape[1]!=6 or not np.isfinite(qs).all():
        raise ValueError('Finite six-channel sample matrix required')
    pre=phase in plan.get('stationary_source_phases',[])
    minimum=float('inf');checks=0;payload_margin=float('inf');tilt_margin=float('inf')
    def bound(values,limit,name,payload=False):
        nonlocal minimum,payload_margin
        minimum=min(minimum,float(values.min()))
        if payload:payload_margin=min(payload_margin,float(values.min())-limit)
        if np.any(values<limit):
            i=int(np.argmin(values));raise ValueError(f'{phase}: {name} sample {i}: {values[i]:.5f} < {limit}')
    hand_bounds=plan.get('object_adapter',{}).get('loaded_hand_command_bounds_rad',[2.50,2.75])
    if carrying and (qs[:,5].min()<hand_bounds[0] or qs[:,5].max()>hand_bounds[1]):
        raise ValueError('Loaded hand outside the original class bounds')
    for hand in (0.,.75,1.5):
        model=qs.copy();model[:,5]=hand
        if np.any(model<robot.limits[:,0]-1e-8) or np.any(model>robot.limits[:,1]+1e-8):
            raise ValueError('Original model joint limit exceeded')
        ff=frames(robot,model);boxes={name:box(ff[name],*bounds) for name,bounds in robot.boxes.items()}
        obstacles=[(o.name,(o.centre[None,:],o.axes,o.half),o is world.support) for o in world.obstacles+([world.support] if world.support else [])]
        for name,b in boxes.items():
            if name!='base_link':bound(bottom(b),float(world.table_clearance_by_link.get(name,world.margin)),'TABLE:'+name)
            for oname,o,_ in obstacles:bound(gap(b,o),world.margin,'OBSTACLE:'+name+':'+oname)
        for a,b in world.self_pairs:bound(gap(boxes[a],boxes[b]),world.margin,'SELF:'+a+':'+b)
        if empty:
            checks+=len(qs)
            continue
        pose=(ff['grasp']@np.array(plan['tcp_from_object'])) if carrying else np.broadcast_to(
            np.array(plan['initial_source_object_pose'] if pre else plan['released_object_pose']),(len(qs),4,4))
        if not carrying and '_ab_static_object_poses' in plan:
            pose=np.asarray(plan['_ab_static_object_poses'])
            if pose.shape!=(len(qs),4,4):raise ValueError('Static-payload batch length mismatch')
        size=np.array(payload_spec(plan)['size_mm']);payload=box(pose,-size/2,size/2)
        bp=bottom(payload);bound(bp,-.15,'PAYLOAD_TABLE',True)
        if carrying and phase in ('BUFFER','PREPLACE','HANDOVER_ALIGN'):
            bound(bp,62.,'TRANSIT_PAYLOAD_BOTTOM',True)
        for name,b in boxes.items():
            if name not in ('link5','gripper_link'):bound(gap(payload,b),world.margin,'PAYLOAD_ARM:'+name,True)
        for oname,o,support in obstacles:
            if support and not carrying and not pre:
                bound(bp,plan['request']['destination']['support_centre_mm'][2]-.15,'PAYLOAD_SUPPORT',True)
            else:bound(gap(payload,o),world.margin,'PAYLOAD_OBSTACLE:'+oname,True)
        if carrying:
            tilt=np.degrees(np.arccos(np.clip(pose[:,2,2],-1,1)))
            tilt_margin=min(tilt_margin,plan['commissioning_tolerance_profile']['loaded_pitch_limit_from_vertical_deg']+.1-float(tilt.max()))
            if tilt_margin<0:
                raise ValueError('Original loaded tilt cone exceeded')
        checks+=len(qs)
    return dict(samples_checked=checks,minimum_model_clearance_mm=minimum,
                payload_margin_mm=payload_margin,loaded_tilt_margin_deg=tilt_margin)
