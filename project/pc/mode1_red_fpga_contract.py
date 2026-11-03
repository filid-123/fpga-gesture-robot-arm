"""Offline fixed-red route -> S4 tables. No hardware/network I/O.

All coordinates here are the saved firmware mathematical endpoint F, not desk Q
or marker P. Board timing/mapping is supplied by the FPGA teammate, never inferred
from Wi-Fi receipt intervals. Generated tables require physical commissioning.
"""
from __future__ import annotations

import math
from copy import deepcopy
import importlib.util
from pathlib import Path
import sys

from pc.roarm_reference_kinematics import ReferenceGeometry, forward, inverse_endpoint

def load_local_reference(name):
    """Avoid collision with the real PYNQ library's installed 'pynq' package."""
    if name not in ('planner_p2p_reference','s4_task_reference'):
        raise ValueError('Unknown local reference module.')
    key='_gesture_red_'+name
    if key not in sys.modules:
        path=Path(__file__).resolve().parents[1]/'pynq'/(name+'.py')
        spec=importlib.util.spec_from_file_location(key,path)
        module=importlib.util.module_from_spec(spec)
        sys.modules[key]=module
        spec.loader.exec_module(module)
    return sys.modules[key]


planner=load_local_reference('planner_p2p_reference')

AXES = ('b', 's', 'e', 't', 'r', 'g')
Q = 65536
PHASES = ('approach', 'grasp', 'lift', 'deliver', 'release', 'retreat')
BOARD_SCHEMA = 'gesture.mode_a.red_board_binding.v1'


def numeric(v):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise ValueError('Expected finite numeric value.')
    return v


def q16(v):
    v = numeric(v) * Q
    n = math.floor(v + .5) if v >= 0 else -math.floor(-v + .5)
    if not -(1 << 31) <= n < 1 << 31:
        raise ValueError('Q16.16 overflow.')
    return n


def fk(q, geo):
    return forward(tuple(q[k] for k in AXES[:4]), geo)


def solve(endpoint, previous, geo, limits):
    choices = [s['joint_rad'] for s in inverse_endpoint(endpoint[:3], endpoint[3], geo, limits)
               if s['reference_limit_compatible']]
    if not choices:
        raise ValueError('No reference IK branch inside vendor limits.')
    return min(choices, key=lambda q: sum((q[k] - previous[k]) ** 2 for k in AXES[:4]))


def cartesian_knots(start, endpoint, roll, grip, geo, limits, tolerance_mm=.75):
    """Adapt Cartesian reference to S2 straight joint segments; check each chord.

    The error is relative to the ideal firmware endpoint line. It says nothing
    about tracking error, tool/obstacle clearance or whole-arm swept volume.
    """
    origin = fk(start, geo)
    cache = {0.: dict(start)}

    def at(u):
        if u not in cache:
            p = tuple(origin[i] + u * (endpoint[i] - origin[i]) for i in range(4))
            q = solve(p, start, geo, limits)
            cache[u] = dict(q, r=start['r'] + u * (roll - start['r']), g=grip)
        return cache[u]

    def split(a, b, depth=0):
        qa, qb = at(a), at(b)
        error = 0.
        for j in range(1, 32):
            v = j / 32
            joint = {k: qa[k] + v * (qb[k] - qa[k]) for k in AXES}
            actual = fk(joint, geo)
            u = a + v * (b - a)
            expected = tuple(origin[i] + u * (endpoint[i] - origin[i]) for i in range(4))
            error = max(error, math.dist(actual[:3], expected[:3]))
        if error <= tolerance_mm:
            return [(b, qb)]
        if depth >= 12:
            raise ValueError('Cartesian subdivision did not converge.')
        middle = (a + b) / 2
        return split(a, middle, depth + 1) + split(middle, b, depth + 1)

    return split(0., 1.)


def build_route(home, practical, successful_requests, geometry):
    """Freeze the successful procedural rules at nominal commanded poses.

    Pure grip/base operations retain PREVIOUS TARGET axes. Recorded observations
    stay in the separate evidence file, and are not relabelled as commands.
    """
    geo = ReferenceGeometry(**geometry['geometry_mm'])
    limits = geometry['vendor_reference_position_limits_rad']
    home = {k: numeric(home[k]) for k in AXES}
    current = dict(home)
    rows, segments = [], []
    keypoints = [dict(id=0, name='HOME', joint_rad=home,
                      joint_q16=[q16(home[k]) for k in AXES])]
    next_id = 1

    def add(name, phase, motion, target=None, endpoint=None, grip=None, roll=None,
            native_source=None, physical_status='DERIVED_NOT_PHYSICALLY_TESTED', tolerance_mm=.75):
        nonlocal current, next_id
        start = dict(current)
        grip = current['g'] if grip is None else grip
        if motion == 'CARTESIAN_REFERENCE':
            knots = cartesian_knots(start, endpoint, current['r'] if roll is None else roll,
                                    grip, geo, limits, tolerance_mm)
        else:
            target = dict(current, **(target or {}))
            if motion == 'GRIPPER_ONLY':
                target['g'] = grip
            knots = [(1., target)]
        first = len(segments)
        for u, q in knots:
            for k in AXES[:4]:
                if not limits[k][0] <= q[k] <= limits[k][1]:
                    raise ValueError('Target outside vendor reference limits: ' + name)
            is_home = name == 'HOME_GRIPPER'
            kid = 0 if is_home else next_id
            if not is_home:
                keypoints.append(dict(id=kid, name=f'{name}_{u:g}', joint_rad=q,
                                      joint_q16=[q16(q[k]) for k in AXES]))
                next_id += 1
            flags = 1 if phase == 'grasp' else (2 if phase == 'approach' else 0)
            segments.append(dict(id=len(segments), stage=name, phase=phase,
                                 keypoint=kid, flags=flags,
                                 start_joint_rad=current, target_joint_rad=q,
                                 line_fraction=u))
            current = dict(q)
        rows.append(dict(name=name, phase=phase, motion=motion,
                         start_joint_rad=start, target_joint_rad=dict(current),
                         target_joint_q16=[q16(current[k]) for k in AXES],
                         endpoint_F=list(fk(current, geo)), first_segment=first,
                         segment_count=len(segments)-first, native_request_source=native_source,
                         physical_status=physical_status,
                         cartesian_chord_tolerance_mm=tolerance_mm if endpoint else None))

    high = (*[practical['high_endpoint_mm'][k] for k in ('x', 'y', 'z')], practical['high_pitch_rad'])
    pick = practical['final_command']
    add('APPROACH_HIGH', 'approach', 'CARTESIAN_REFERENCE', endpoint=high, roll=pick['r'],
        native_source='PRACTICAL_HIGH', physical_status='SOURCE_REQUEST_ARRIVED_NOMINAL_REBINDING_REQUIRED')
    add('OPEN_HIGH', 'approach', 'GRIPPER_ONLY', grip=pick['g'], native_source='PRACTICAL_OPEN_HIGH',
        physical_status='SOURCE_PURE_GRIP_REQUEST_ARRIVED')
    add('DESCEND', 'approach', 'CARTESIAN_REFERENCE', endpoint=tuple(pick[k] for k in ('x','y','z','t')),
        grip=pick['g'], roll=pick['r'], native_source='PRACTICAL_DESCEND',
        physical_status='SOURCE_REQUEST_ARRIVED_ORIGINAL_RED_ALIGNMENT_ACCEPTED', tolerance_mm=.5)
    add('CLOSE', 'grasp', 'GRIPPER_ONLY', grip=2.6, native_source='CLOSE_FOR_HIGH_LIFT',
        physical_status='SOURCE_CONTACT_AND_LIFT_SUCCEEDED_CLOSURE_ARRIVAL_WAS_STOPPED')
    low = fk(current, geo)
    radius = math.hypot(*low[:2]); angle = current['b']
    lift_endpoint = (low[0], low[1], low[2]+100, low[3])
    finish = ((radius-35)*math.cos(angle), (radius-35)*math.sin(angle), low[2]+145, low[3])
    add('LIFT_VERTICAL100', 'lift', 'CARTESIAN_REFERENCE', endpoint=lift_endpoint, grip=2.6,
        native_source='HIGH_VERTICAL100', physical_status='SOURCE_RULE_LIFT_OBSERVED_NEW_NOMINAL_START')
    add('HIGH_FINISH', 'lift', 'CARTESIAN_REFERENCE', endpoint=finish, grip=2.6,
        native_source='HIGH_FINISH', physical_status='SOURCE_RULE_LIFT_OBSERVED_NEW_NOMINAL_START')
    high_base = current['b']
    for name, delta, phase in [('BUFFER',32.64989987379047,'lift'),('PRE',45.,'deliver'),('DELIVERY_HIGH',60.,'deliver')]:
        add(name, phase, 'BASE_ONLY', target={'b':high_base+math.radians(delta)},
            native_source={'BUFFER':'buffer','PRE':'pre','DELIVERY_HIGH':'high'}[name],
            physical_status='SOURCE_BASE_REQUEST_ARRIVED_NEW_NOMINAL_ARM_HOLD')
    place = successful_requests['place']
    endpoint = tuple(place[k] for k in ('x','y','z','t'))
    add('PLACE', 'deliver', 'CARTESIAN_REFERENCE', endpoint=endpoint, grip=2.6, roll=place['r'],
        native_source='place', physical_status='SOURCE_FIXED_ENDPOINT_REQUEST_ARRIVED', tolerance_mm=.5)
    add('RELEASE', 'release', 'GRIPPER_ONLY', grip=pick['g'], native_source='release',
        physical_status='SOURCE_OPEN_REQUEST_SENT_COMPLETION_UNCONFIRMED')
    add('CLEAR', 'retreat', 'CARTESIAN_REFERENCE', endpoint=(*endpoint[:2],endpoint[2]+20,endpoint[3]),
        grip=pick['g'], tolerance_mm=.5)
    add('BASE_BACK', 'retreat', 'BASE_ONLY', target={'b':high_base})
    add('HOME_ARM', 'retreat', 'CARTESIAN_REFERENCE', endpoint=fk(home,geo), roll=home['r'], grip=pick['g'])
    add('HOME_GRIPPER', 'retreat', 'GRIPPER_ONLY', grip=home['g'])
    # Numerical IK may have tiny residuals; the last complete target is EXACT HOME.
    final = segments[-1]
    if max(abs(final['target_joint_rad'][k]-home[k]) for k in AXES) > 1e-8:
        raise ValueError('Route does not finish at HOME.')
    final['target_joint_rad'] = dict(home)
    rows[-1]['target_joint_rad'] = dict(home)
    rows[-1]['target_joint_q16'] = [q16(home[k]) for k in AXES]
    descriptors = {}
    for phase in PHASES:
        indexes = [s['id'] for s in segments if s['phase']==phase]
        if not indexes or indexes != list(range(indexes[0],indexes[-1]+1)):
            raise ValueError('Invalid phase descriptor.')
        descriptors[phase] = [indexes[0],len(indexes)]
    stacked = sum(descriptors[p][1] for p in ('approach','grasp','lift','deliver'))
    if len(keypoints)>64 or len(segments)>64 or stacked>32:
        raise ValueError(f'S4 capacity exceeded: KP={len(keypoints)}, SEG={len(segments)}, STACK={stacked}.')
    # S4's logical PRE_DELIVERY keypoint is the accepted BUFFER holding point.
    # This implements "buffer is held waiting only" using existing WAIT_PALM;
    # geometric PRE is traversed after the actual board gate accepts delivery.
    predelivery = next(r for r in rows if r['name']=='BUFFER')
    pre_kp = segments[predelivery['first_segment']+predelivery['segment_count']-1]['keypoint']
    return dict(schema='gesture.mode_a.red_frozen_route_candidate.v1', joint_order=list(AXES),
                units='rad; signed int32 Q16.16; channel0 low192-bit word',
                coordinate_semantics='Firmware mathematical endpoint F only; no desk/tool transform inferred.',
                physical_execution_validated=False, whole_mode_accepted=False,
                home_keypoint=0,predelivery_keypoint=pre_kp,
                keypoints=keypoints,stages=rows,segments=segments,descriptors=descriptors,
                capacity=dict(keypoints=len(keypoints),segments=len(segments),retrace_entries=stacked),
                model_adaptation='Canonical nominal-command start, adaptive reference Cartesian chords. Pure-grip/base axes retain last TARGET, not old observed positions. This is a new joint-space candidate requiring real testing.',
                nominal_lift=dict(vertical_first_mm=100,total_rise_mm=145,radial_return_mm=35),
                event_contract=dict(object_id=1,gesture_code=1,select_mask=2,rearm_mask=129,
                                    palm_ready_code=4,fist_cancel_code=5,home_required=True,
                                    wait_palm_after='BUFFER',hold_policy=True,buffer_release=False,
                                    successful_delivery_consumes_red_slot=True,
                                    stock_rearm='One physical trial; disable selection after completion until manual restock.'),
                release_contract='Fixed support first. PALM_READY/window must be a real commissioned board gate; do not turn manual PC RELEASE into a fake always-ready event. Mechanical support/placement must be verified before first automatic release.',
                home_semantics='Exact INITIAL target from successful source; seed planner LAST_DELIVERED only after actual empty startup HOME verification. Never fake feedback or set HOME to the current arbitrary pose.')


def binding_template():
    return dict(schema=BOARD_SCHEMA, joint_order=list(AXES),
                source='Fill with FPGA teammate actual build/profile; null values are not defaults.',
                clock_hz=None,period_cycles=None,stall_cycles=None,tick_prescale=None,
                soft_min_rad=[None]*6,soft_max_rad=[None]*6,
                vmax_rad_s=[None]*6,amax_rad_s2=[None]*6,
                arrival_tolerance_deg=[1.5,4.5,2.5,3.,1.5,4.],
                arrival_consecutive_samples=None,t_arrival_ticks=None,t_comm_ticks=None,
                t_palm_hold_ticks=None,t_palm_wait_ticks=None,blind_periods=None,
                move_margin_periods=None,s1_abi_version=None,s2_abi_version=None,s4_abi_version=None,
                backend_and_feedback_verified=False,joint_mapping_verified=False,
                initial_home_verified=False,fixed_red_and_support_setup_verified=False,
                gate_source=None,
                note='Arrival recommendations are prior practical tolerances, not measured drive accuracy. Gripper closes with INCREASING g: open1.587670115, hold2.60. Do not use BENCH CLOSED=0.')


def bind_route(route, board):
    """Fill S2 timing from teammate limits; validate with actual reference validator.

    Returns only data for offline/loading review, never writes registers or moves.
    """
    if board.get('schema') != BOARD_SCHEMA or board.get('joint_order') != list(AXES):
        raise ValueError('Wrong board schema/joint order.')
    required_bool=('backend_and_feedback_verified','joint_mapping_verified','initial_home_verified','fixed_red_and_support_setup_verified')
    if any(board.get(k) is not True for k in required_bool):
        raise ValueError('Board backend/mapping/HOME/setup verification fields incomplete.')
    if board.get('gate_source') not in ('real_palm_pipeline_with_verified_support','commissioned_fixed_support_gate'):
        raise ValueError('Specify an actual commissioned release gate; no always-ready stub.')
    def uint(name,minimum=1):
        v=board.get(name)
        if isinstance(v,bool) or not isinstance(v,int) or not minimum<=v<=0xffffffff:
            raise ValueError('Missing/invalid board integer: '+name)
        return v
    clock=uint('clock_hz');period=uint('period_cycles',planner.MIN_PERIOD_CYCLES)
    stall=uint('stall_cycles');tick=uint('tick_prescale')
    if board.get('s1_abi_version')!=0x3101 or board.get('s2_abi_version')!=0x3201:
        raise ValueError('Unsupported S1/S2 ABI; teammate must adapt actual bitstream.')
    if board.get('s4_abi_version') not in (0x3401,0x3402):
        raise ValueError('Unsupported S4 ABI; teammate must adapt actual bitstream.')
    for k in ('arrival_consecutive_samples','t_arrival_ticks','t_comm_ticks','t_palm_hold_ticks',
              't_palm_wait_ticks','blind_periods','move_margin_periods'):
        uint(k)
    def vector(name):
        values=board.get(name)
        if not isinstance(values,list) or len(values)!=6:
            raise ValueError('Missing six-channel board field: '+name)
        return [numeric(v) for v in values]
    low=vector('soft_min_rad');high=vector('soft_max_rad')
    vel=vector('vmax_rad_s');acc=vector('amax_rad_s2');tol=vector('arrival_tolerance_deg')
    if any(lo>=hi for lo,hi in zip(low,high)) or min(vel+acc+tol)<=0:
        raise ValueError('Invalid board limits/dynamics/tolerances.')
    if any(a>b+1e-9 for a,b in zip(tol,[1.5,4.5,2.5,3,1.5,4])):
        raise ValueError('Arrival tolerances wider than reviewed practical bounds.')
    dt=period/clock
    vq=[math.floor(v*dt*Q) for v in vel]
    aq=[math.floor(a*dt*dt*(1<<32)) for a in acc]
    if min(vq+aq)<=0 or max(vq+aq)>0xffffffff:
        raise ValueError('Board limits underflow/overflow S2 registers.')
    lowq=[math.ceil(v*Q) for v in low];highq=[math.floor(v*Q) for v in high]
    if any(not -(1<<31)<=v<(1<<31) for v in lowq+highq):
        raise ValueError('Board joint limits overflow signed Q16.16.')
    kp={k['id']:k['joint_q16'] for k in route['keypoints']}
    for pos in kp.values():
        if any(not lo<=v<=hi for lo,v,hi in zip(lowq,pos,highq)):
            raise ValueError('Route keypoint outside actual board joint limits.')
    rows=[];last=tuple(kp[route['home_keypoint']])
    for s in route['segments']:
        target=tuple(kp[s['keypoint']])
        # Slow commissioning ceilings are design choices, not measured device
        # capability. Keep requested speed <= half the teammate measured maximum.
        is_grip=s['phase'] in ('grasp','release') or s['stage'] in ('OPEN_HIGH','HOME_GRIPPER')
        ceiling=math.radians(15 if is_grip else 3)
        seconds=max(abs(b-a)/Q/min(v/2,ceiling) for a,b,v in zip(last,target,vel))*1.5
        n=max(4,math.ceil(seconds/dt))
        while n<=planner.MAX_SAMPLES:
            na=max(1,n//4)
            p=planner.MoveParams(last,target,n,na,1,period,stall,tuple(vq),tuple(aq))
            valid=planner.validate(p,last)
            if valid.ok:
                break
            n+=max(1,n//20)
        else:
            raise ValueError('Segment timing exceeds S2 16-bit sample capacity.')
        rows.append(dict(id=s['id'],stage=s['stage'],phase=s['phase'],keypoint=s['keypoint'],
                         n=n,na=na,profile=1,flags=s['flags'],duration_s=n*dt))
        last=target
    desc=deepcopy(route['descriptors'])
    # S4 blind budget starts at READY and includes DELIVER+RELEASE. Avoid a table
    # that must time out on every run; retain arrival/communication margins too.
    gated=[s for s in rows if s['phase'] in ('deliver','release')]
    arrival_periods=math.ceil(board['t_arrival_ticks']*tick/period)
    blind_required=sum(s['n'] for s in gated)+len(gated)*(arrival_periods+board['move_margin_periods'])
    if board['blind_periods']<blind_required:
        raise ValueError(f'blind_periods too short: need at least {blind_required} with supplied timing/margins.')
    config=dict(mode_b=False,require_line=True,hold_policy=True,
                rearm_mask=129,select_mask=2,tick_prescale=tick,period_cycles=period,stall_cycles=stall,
                home_kp=route['home_keypoint'],predelivery_kp=route['predelivery_keypoint'],
                arrival_mask=0x3f,joint_min=lowq,joint_max=highq,vmax=vq,amax=aq,
                t_arrival=board['t_arrival_ticks'],t_comm=board['t_comm_ticks'],
                t_palm_hold=board['t_palm_hold_ticks'],t_palm_wait=board['t_palm_wait_ticks'],
                blind_periods=board['blind_periods'],move_margin=board['move_margin_periods'],
                t_heartbeat=0,tray_exit=False)
    return dict(schema='gesture.mode_a.red_s4_bound_tables.v1',keypoints=kp,segments=rows,
                descriptors=desc,config=config,minimum_blind_periods=blind_required,
                arrival_backend=dict(tolerance_q16=[q16(math.radians(v)) for v in tol],
                                     consecutive_samples=board['arrival_consecutive_samples'],
                                     must_be_programmed_in_actual_S1=True),
                physical_execution_validated=False,
                status='OFFLINE_BOUND_FOR_TEAMMATE_COMMISSIONING_NOT_A_PHYSICAL_PASS')


def as_s4_tables(bound, s4_module):
    """Build existing S4Tables dataclass; caller owns real table loading/ENABLE."""
    tables=s4_module.S4Tables()
    for k,values in bound['keypoints'].items():
        tables.keypoints[int(k)]=tuple(values)
    for s in bound['segments']:
        tables.segments[s['id']]=(s['keypoint'],s['n'],s['na'],s['profile'],s['flags'])
    for name in ('approach','grasp','lift'):
        setattr(tables,name,{1:tuple(bound['descriptors'][name]),2:(0,0),3:(0,0)})
    for name in ('deliver','release','retreat'):
        setattr(tables,name,tuple(bound['descriptors'][name]))
    return tables
