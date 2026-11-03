"""The board owner consumes PL selections and commits one frozen B path."""
from concurrent.futures import ThreadPoolExecutor,Future
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import time
import shutil
import numpy as np
from pc.mode_ab.control import ControlError
from pc.mode_ab.motion import build_banks,compile_banks,native_with_front,restock_native,compile_restock
from pc.mode_ab.registers import TASK
from pc.mode_ab.shared_red import A_SOURCE,at_a_slot,compile_path
from pc.mode_ab.motion import profile_id
from pc.mode_ab.workspace import upright_yaw

LABELS={'red_cube':'红色方块','eraser':'橡皮','small_canister':'小圆罐'}


def selected_pose(camera,name):
    s=camera.snapshot()
    if not s['ready']:
        raise ControlError(503,f'RGB_NOT_READY：已选择{LABELS[name]}，需要 1 秒内的新鲜 RGB 推理。'+(s.get('error') or '请连接标定相机并等待画面更新。'))
    obs=s['observation']
    row=next((r for r in obs['localizations'] if r['class_name']==name),None)
    if not row or not row.get('geometry_gate_pass'):
        status=row.get('status','NOT_FOUND') if row else 'NOT_FOUND'
        reasons={'NOT_FOUND':'没有检测到所选物品；检查数字与物品映射、遮挡和相机画面。',
            'MULTIPLE_INSTANCES':'出现多个同类物品；每类仅保留一个。',
            'METRIC_GEOMETRY_REJECTED':'顶面尺寸或形状未通过标定几何检查。',
            'CENTRE_OUTSIDE_WORKSPACE':'识别中心超出取物框，请核对桌面坐标和相机标定。',
            'SHAPE_OR_DIMENSIONS_REJECTED':'顶面尺寸或形状未通过；已取消历史半径限制。'}
        top=(row or {}).get('top') or {}
        details={k:top[k] for k in ('opposite_edge_mean_mm','max_abs_adjacent_edge_cosine','diameter_mm','circle_residual_p95_fraction_radius') if k in top}
        details['centre_desktop_xy_mm']=(row or {}).get('measured_centre_desktop_xy_mm',top.get('centre_desktop_xyz_mm'))
        details['rejection_reasons']=(row or {}).get('rejection_reasons',[])
        raise ControlError(409,f'{status}：{LABELS[name]}；{reasons.get(status,"当帧识别或表面分割未通过；请查看视觉诊断。")} 测量={json.dumps(details,ensure_ascii=False)}')
    yaw=upright_yaw(name,row['top'].get('long_axis_yaw_mod180_deg',0.))
    return deepcopy(obs),row['object_centre_desktop_xyz_mm'],yaw


def plan_delivery(folder,name,centre,yaw,observation,progress=None):
    folder.mkdir(parents=True,exist_ok=False)
    (folder/'frame.json').write_text(json.dumps(observation))
    (folder/'source_request.json').write_text(json.dumps(dict(class_name=name,centre_mm=centre,yaw_deg=yaw)))
    started=time.perf_counter();timings={}
    def stage(text):
        if progress:progress(text)
    stage('全取物框残差外推与抓取路径生成')
    if name=='red_cube' and at_a_slot(centre,yaw):
        compiled=compile_path();native=dict(schema='gesture.mode_ab.frozen_a_shared_red.v1',provenance=compiled['provenance'])
    else:
        from pc.mode_ab.native_routes import build,compile_routes
        banks,front,native=build(name,centre,yaw);timings['source_ik_ms']=(time.perf_counter()-started)*1000
        stage('保留 Giao 分段速度与周期，检查原生源位轨迹')
        compiled=compile_routes(banks,front)
        timings['compile_ms']=(time.perf_counter()-started)*1000-timings['source_ik_ms']
        from pc.mode_ab.native_family import verify
        stage('校验交付轨迹证明；超出证明范围时完整检查')
        compiled['fresh_handover_family']=verify(compiled,banks[1])
        timings['family_ms']=(time.perf_counter()-started)*1000-sum(timings.values())
    compiled['task_abi']=0x340e
    timings['total_ms']=(time.perf_counter()-started)*1000;compiled['planning_timings_ms']=timings
    (folder/'native.json').write_text(json.dumps(native))
    (folder/'compiled.json').write_text(json.dumps(compiled))
    stage('规划完成，等待 FPGA 提交')
    return dict(compiled=compiled,native=native,folder=str(folder),source_centre_mm=centre,source_yaw_deg=yaw,origin_kind=compiled.get('origin_kind','B_DYNAMIC'),
                profile_id='A_FIXED' if name=='red_cube' and at_a_slot(centre,yaw) else profile_id(name,centre),
                plan_sha256=hashlib.sha256((folder/'compiled.json').read_bytes()).hexdigest())


def plan_restock(folder,origin):
    folder.mkdir(parents=True,exist_ok=False)
    if origin.get('origin_kind')=='A_FIXED':
        compiled=compile_path(restock=True);compiled['task_abi']=0x340e
        (folder/'compiled.json').write_text(json.dumps(compiled));return dict(compiled=compiled,native=None,folder=str(folder))
    p=Path(origin['native_file'])
    if hashlib.sha256(p.read_bytes()).hexdigest()!=origin['native_sha256']:raise ValueError('Frozen delivery native plan changed')
    native=restock_native(json.loads(p.read_bytes()),Path(origin['origin_file']))
    compiled=compile_restock(native);compiled['task_abi']=0x340e
    (folder/'native.json').write_text(json.dumps(native));(folder/'compiled.json').write_text(json.dumps(compiled))
    return dict(compiled=compiled,native=native,folder=str(folder))


class Runtime:
    def __init__(self,board,camera,controller,out):
        self.board,self.camera,self.control,self.out=board,camera,controller,Path(out)
        self.executor=ThreadPoolExecutor(max_workers=2,thread_name_prefix='local_planning')
        self.future=None;self.prepared=None;self.task=None;self.before=None;self.committed=False
        self.planning_error=None;self.eventlog=(self.out/'tasks.jsonl').open('x',encoding='utf-8')
        self.previous=None;self.red_bbox=None;board.reconcile_red=self.reconcile_red
        self.cache={};self.precompute=None;self.precompute_name=None;self.precompute_count=0
        self.failed_sources={};self.precompute_pose=None;self.last_selection=None
        self.progress={};self.job_key=None;self.background_key=None

    def progress_for(self,key,name,background=False):
        self.progress[key]=dict(class_name=name,background=background,started=time.monotonic(),stage='等待规划线程')
        def update(stage):self.progress[key]['stage']=stage
        return update

    def planning_status(self):
        key=self.job_key if self.task else self.background_key
        p=deepcopy(self.progress.get(key))
        if p:p['elapsed_s']=round(time.monotonic()-p.pop('started'),1)
        return p

    def record(self,event,**values):
        self.eventlog.write(json.dumps(dict(event=event,monotonic_ns=time.monotonic_ns(),**values))+'\n');self.eventlog.flush()

    def cancel_unstarted(self,reason):
        self.planning_error=reason;self.record('path_rejected',reason=reason,task=self.task)
        s=self.board.observe('B_PATH_REJECTED')
        if s['state'] not in ('WAIT_PATH','IDLE'):
            self.control.transition_fault='Path outcome unknown; inspect FPGA/arm before restarting'
            raise RuntimeError('Path may have started; refusing to label it cancelled: '+reason)
        if s['state']=='WAIT_PATH' and s['selected_task_id']==self.task['task_id']:self.board.b.write(TASK,8)
        self.control.complete(self.task['task_id'],outcome='cancelled')
        self.task=None;self.prepared=None;self.committed=False

    def tick(self):
        self.board.heartbeat();s=self.board.observe()
        if s['fault']!='NONE' or s['arm_fault']:raise RuntimeError('Real FPGA fault: '+s['fault']+('；'+s['fault_detail'] if s.get('fault_detail') else ''))
        self.observe_a_red(s)
        if self.precompute and self.precompute.done():
            try:
                self.cache[self.precompute_name]=self.precompute.result()
                self.failed_sources.pop(self.precompute_name,None)
            except Exception as exc:
                if self.precompute_pose:self.failed_sources[self.precompute_name]=self.precompute_pose
                self.record('background_path_rejected',class_name=self.precompute_name,reason=repr(exc))
            self.precompute=None;self.precompute_name=None;self.precompute_pose=None;self.background_key=None
        if self.task and self.committed:
            if s['done_counter']!=self.before['done_counter'] or s['restocked_tasks']!=self.before['restocked_tasks']:
                origin=None
                if self.task['kind']=='DELIVERY':
                    folder=Path(self.prepared['folder']);native=folder/'native.json'
                    obs=self.task['frame'];det=next(d for d in obs['recognitions'] if d['class_name']==self.task['class_name'])
                    origin=dict(task_id=self.task['task_id'],class_name=self.task['class_name'],source_centre_mm=self.prepared['source_centre_mm'],origin_kind=self.prepared['origin_kind'],
                        source_yaw_deg=self.prepared['source_yaw_deg'],source_bbox=det['bbox_xyxy_raw'],
                        plan_sha256=self.prepared['plan_sha256'],native_file=str(native),
                        native_sha256=hashlib.sha256(native.read_bytes()).hexdigest(),
                        inventory_semantics='PL_PROGRAM_COMPLETION_PHYSICAL_SUCCESS_REQUIRES_OPERATOR_OBSERVATION',
                        origin_file=str(folder/'origin.json'),completion_snapshot=s)
                    (folder/'origin.json').write_text(json.dumps(origin,indent=2))
                if self.task['class_name']=='red_cube':
                    at_slot=self.task['kind']=='RESTOCK' and self.task['origin'].get('origin_kind')=='A_FIXED'
                    self.board.set_red_available(at_slot)
                    self.control.shared_red.update(location='A_SLOT' if at_slot else ('OUT' if self.task['kind']=='DELIVERY' else 'B_SOURCE'))
                self.control.complete(self.task['task_id'],outcome='completed',origin=origin)
                self.record('pl_completed',task=self.task,physical_success=None,snapshot=s)
                self.task=None;self.prepared=None;self.committed=False
            elif s['cancelled_counter']!=self.before['cancelled_counter']:
                self.control.complete(self.task['task_id'],outcome='cancelled');self.record('pl_cancelled_returned',task=self.task,snapshot=s)
                self.task=None;self.prepared=None;self.committed=False
            elif s['state']=='IDLE':
                # A coherent counter may follow the state in the next snapshot.
                if time.monotonic()-self.commit_time>2 and s['refusal']!='NONE':
                    self.cancel_unstarted('FPGA refused path: '+s['refusal'])
        if self.future and self.future.done():
            future=self.future;self.future=None
            try:
                prepared=future.result()
                if self.task is None:return
                if 'preplans' in Path(prepared['folder']).parts:
                    folder=self.out/'plans'/str(self.task['task_id']);folder.mkdir(parents=True,exist_ok=False)
                    for name in ('native.json','compiled.json','frame.json'):
                        source=Path(prepared['folder'])/name
                        if source.exists():shutil.copyfile(source,folder/name)
                    prepared=deepcopy(prepared);prepared['folder']=str(folder)
                if self.task['kind']=='DELIVERY':
                    obs,centre,yaw=selected_pose(self.camera,self.task['class_name'])
                    symmetry=180 if self.task['class_name']=='eraser' else 90
                    dyaw=abs((yaw-prepared['source_yaw_deg']+symmetry/2)%symmetry-symmetry/2)
                    if np.linalg.norm(np.array(centre)-prepared['source_centre_mm'])>3 or (self.task['class_name']!='small_canister' and dyaw>3):
                        distance=float(np.linalg.norm(np.array(centre)-prepared['source_centre_mm']))
                        raise ControlError(409,f'SOURCE_CHANGED：{LABELS[self.task["class_name"]]}位置变化 {distance:.2f} mm / 朝向变化 {dyaw:.2f}°，允许 3 mm / 3°；请稳定物品、撤去手势后重新选择。')
                else:self.check_source_clear(self.task['origin'])
                self.prepared=prepared;self.before=self.board.observe('B_BEFORE_COMMIT')
                if self.job_key in self.progress:self.progress[self.job_key]['stage']='向 FPGA 上传路径并核对任务身份'
                self.board.commit(prepared['compiled'],self.task);self.committed=True;self.commit_time=time.monotonic()
                self.record('path_committed',task=self.task,compiled_sha256=hashlib.sha256((Path(prepared['folder'])/'compiled.json').read_bytes()).hexdigest())
            except Exception as exc:
                if self.task:self.cancel_unstarted(repr(exc))
                # s predates cancellation. Never consume that selection again.
                return
        if (s['state']=='WAIT_PATH' and self.task is None and self.future is None
                and s['selected_task_id']!=self.last_selection):
            self.last_selection=s['selected_task_id']
            try:
                current=self.control.status();gesture=s['selected_gesture']
                name=next(r['object_id'] for r in current['gesture_bindings'] if r['gesture']==gesture)
                origin=self.control.origins.get(name)
                if origin:
                    self.check_source_clear(origin);obs=self.camera.snapshot()['observation']
                    centre=yaw=None
                else:obs,centre,yaw=selected_pose(self.camera,name)
                self.task=self.control.select(gesture,s['selected_task_id'],obs)
                self.planning_error=None;self.record('planning_started',task=self.task)
                folder=self.out/'plans'/str(s['selected_task_id'])
                self.job_key=str(folder);callback=self.progress_for(self.job_key,name)
                if origin:self.future=self.executor.submit(plan_restock,folder,deepcopy(origin))
                elif self.cached(name,centre,yaw):
                    self.future=Future();self.future.set_result(self.cache[name])
                elif (self.precompute and self.precompute_name==name
                      and self.same_source(name,self.precompute_pose,centre,yaw,.5,.5)):
                    self.future=self.precompute;self.job_key=self.background_key
                else:self.future=self.executor.submit(plan_delivery,folder,name,centre,yaw,obs,callback)
            except Exception as exc:
                self.planning_error=repr(exc);self.record('selection_rejected',reason=repr(exc),snapshot=s)
                self.board.b.write(TASK,8)
        self.control.process_one(self.board)
        if self.control.transition_fault:
            raise RuntimeError(self.control.transition_fault)
        if self.board.mode=='B' and s['state']=='IDLE' and not self.task and not self.precompute:
            for row in self.control.active_bindings:
                name=row['object_id']
                if name in self.control.origins:continue
                try:obs,centre,yaw=selected_pose(self.camera,name)
                except ControlError:continue
                if self.cached(name,centre,yaw):continue
                if self.same_source(name,self.failed_sources.get(name),centre,yaw,3.,3.):continue
                self.precompute_count+=1;self.precompute_name=name
                self.precompute_pose=dict(source_centre_mm=deepcopy(centre),source_yaw_deg=yaw,
                    profile_id='A_FIXED' if name=='red_cube' and at_a_slot(centre,yaw) else profile_id(name,centre),
                    origin_kind='A_FIXED' if name=='red_cube' and at_a_slot(centre,yaw) else 'B_DYNAMIC')
                folder=self.out/'preplans'/(name+'_'+str(self.precompute_count))
                self.background_key=str(folder)
                callback=self.progress_for(self.background_key,name,background=True)
                self.precompute=self.executor.submit(plan_delivery,folder,name,centre,yaw,obs,callback);break

    def cached(self,name,centre,yaw):
        return self.same_source(name,self.cache.get(name),centre,yaw,.5,.5)

    def same_source(self,name,p,centre,yaw,position_mm,yaw_deg):
        if not p:return False
        if name=='red_cube' and (p.get('origin_kind')=='A_FIXED')!=at_a_slot(centre,yaw):return False
        if p.get('profile_id') and p['profile_id'] not in ('A_FIXED',profile_id(name,centre)):return False
        symmetry=180 if name=='eraser' else 90
        return (np.linalg.norm(np.array(centre)-p['source_centre_mm'])<=position_mm and
            (name=='small_canister' or abs((yaw-p['source_yaw_deg']+symmetry/2)%symmetry-symmetry/2)<=yaw_deg))

    def check_source_clear(self,origin):
        s=self.camera.snapshot()
        if not s['ready']:raise ControlError(503,'Fresh RGB frame required before restock')
        from pc.multiobject.yolo import iou
        target='red_cube' if origin.get('origin_kind')=='A_FIXED' else origin.get('class_name',self.task['class_name'] if self.task else None)
        if target and any(r['class_name']==target and r.get('geometry_gate_pass') for r in s['observation']['localizations']):
            raise ControlError(409,'The returned object is still in the source workspace; place it at public (300,200) mm')
        for d in s['observation']['recognitions']:
            if origin.get('source_bbox') and iou(d['bbox_xyxy_raw'],origin['source_bbox'])>.2:
                raise ControlError(409,'Frozen original source is occupied; clear it before restock')
        if not origin.get('source_bbox'):
            for row in s['observation']['localizations']:
                if row.get('geometry_gate_pass') and np.linalg.norm(np.array(row['object_centre_desktop_xyz_mm'])[:2]-np.array(origin['source_centre_mm'])[:2])<45:
                    raise ControlError(409,'Original shared red slot is occupied')

    def observe_a_red(self,s):
        cam=self.camera.snapshot()
        if cam['ready']:
            for row in cam['observation']['localizations']:
                if row['class_name']=='red_cube' and row.get('geometry_gate_pass') and at_a_slot(row['object_centre_desktop_xyz_mm'],upright_yaw('red_cube',row['top'].get('long_axis_yaw_mod180_deg',0))):
                    det=next((d for d in cam['observation']['recognitions'] if d['class_name']=='red_cube'),None)
                    if det:self.red_bbox=det['bbox_xyxy_raw']
        prev=self.previous;self.previous=deepcopy(s)
        if not prev or s['fpga_mode']!='A' or prev['fpga_mode']!='A' or s['object']!=1:return
        if s['done_counter']!=prev['done_counter']:
            path=self.out/'shared_red'/('a_delivery_'+str(s['done_counter'])+'.json');path.parent.mkdir(exist_ok=True)
            table=self.board.root/'candidate/S4_BANKED_CANDIDATE.json'
            origin=dict(task_id='A:'+str(s['done_counter']),origin_kind='A_FIXED',source_centre_mm=A_SOURCE,
                source_yaw_deg=0.,source_bbox=self.red_bbox,plan_sha256=hashlib.sha256(table.read_bytes()).hexdigest(),
                origin_file=str(path),completion_snapshot=s,inventory_semantics='PL_PROGRAM_COMPLETION_NOT_PHYSICAL_SUCCESS')
            path.write_text(json.dumps(origin,indent=2));self.control.red_origin(origin,'A_DELIVERY_COMPLETED')
            self.control.shared_red.update(location='OUT')
        elif s['restocked_tasks']!=prev['restocked_tasks']:
            self.control.red_origin(None,'A_RED_RESTOCK_COMPLETED');self.control.shared_red.update(location='A_SLOT')

    def reconcile_red(self,mode):
        cam=self.camera.snapshot();elsewhere=False
        if cam['ready']:
            red=next((r for r in cam['observation']['localizations'] if r['class_name']=='red_cube' and r.get('geometry_gate_pass')),None)
            if red:
                if at_a_slot(red['object_centre_desktop_xyz_mm'],upright_yaw('red_cube',red['top'].get('long_axis_yaw_mod180_deg',0))):
                    self.board.set_red_available(True);self.control.red_origin(None,'FRESH_RGB_RED_AT_A_SLOT')
                    self.control.shared_red.update(location='A_SLOT')
                else:
                    elsewhere=True;self.board.set_red_available(False);self.control.shared_red.update(location='B_SOURCE')
        if 'red_cube' in self.control.origins:self.board.set_red_available(False)
        disabled=mode=='A' and elsewhere
        self.control.shared_red['a_gesture_disabled']=disabled
        return disabled

    def close(self):
        self.executor.shutdown(wait=False,cancel_futures=True);self.eventlog.close()
