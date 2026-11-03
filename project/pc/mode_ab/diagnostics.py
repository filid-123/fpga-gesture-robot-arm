"""Operator-facing explanations for real device/perception gates."""
import numpy as np
from pc.mode_ab.motion import boundaries,profile_id

STATUS={
    'NOT_FOUND':'未检测到该物品；检查手势映射、画面和遮挡',
    'MULTIPLE_INSTANCES':'同类有多个实例；每类仅保留一个',
    'OVERLAP_OR_CLASS_AMBIGUITY':'检测框重叠或类别有歧义；请分开物品并清除遮挡',
    'SURFACE_CLASS_NOT_TRAINED':'该类别没有可用的冻结顶面模型',
    'NEURAL_SURFACE_GEOMETRY_REJECTED':'神经网络顶面分割未通过像素几何检查',
    'METRIC_GEOMETRY_REJECTED':'标定后的尺寸、形状或工作区边界未通过',
    'CENTRE_OUTSIDE_WORKSPACE':'物品中心超出取物框，请核对坐标与相机标定',
    'SHAPE_OR_DIMENSIONS_REJECTED':'顶面尺寸或形状未通过；历史锚点半径已取消',
    'DESKTOP_CANDIDATE_ONLY':'当帧视觉几何通过；实际任务仍需路径校验',
}


def metric_failures(name,top):
    """Explain the frozen projector's thresholds; never change gate decisions."""
    errors=[]
    edges=top.get('opposite_edge_mean_mm')
    if edges and name in ('red_cube','eraser'):
        measured=np.sort(edges);expected=np.array([30,30] if name=='red_cube' else [15,65]);tolerance=.2 if name=='red_cube' else .22
        if np.any(abs(measured/expected-1)>tolerance):
            errors.append('边长 '+', '.join(f'{x:.1f}' for x in measured)+' mm，要求 '+', '.join(f'{x*(1-tolerance):.1f}～{x*(1+tolerance):.1f}' for x in expected)+' mm')
        cosine=top.get('max_abs_adjacent_edge_cosine',0)
        allowed=.15 if name=='red_cube' else .25
        if cosine>allowed and not (name=='eraser' and top.get('rectangle_residual',{}).get('within2mm')):
            errors.append(f'边角非正交指标 {cosine:.3f} > {allowed}')
    if name=='small_canister':
        diameter=top.get('diameter_mm');residual=top.get('circle_residual_p95_fraction_radius')
        if diameter is not None and abs(diameter/25-1)>.22:errors.append(f'圆罐顶面直径 {diameter:.1f} mm，要求 19.5～30.5 mm')
        if residual is not None and residual>.09:errors.append(f'圆形拟合残差 {residual*100:.1f}% > 9%')
    if top.get('centre_desktop_xyz_mm'):
        xy=np.asarray(top['centre_desktop_xyz_mm'])[:2]
        if np.any(xy<[490,215]) or np.any(xy>[690,355]):errors.append('物品中心超出 X=490～690、Y=215～355 mm')
    return errors
REASONS={
    'Wait for a fresh FPGA IDLE/HOME status':'配置被拒绝：需要新鲜 FPGA IDLE、空夹爪及当前 HOME 状态；请查看锁定条件。',
    'Only a verified empty HOME may switch mode':'配置被拒绝：机械臂尚未确认空夹爪 HOME。',
    'The PL selection expired or changed':'PL_SELECTION_CHANGED：规划完成前 FPGA 任务已取消或超时；撤去手势后重新选择。',
    'FPGA outcome is pending; query status, do not repeat':'配置正在处理，请等待真实回报；请勿重复发送切换。',
    'Configuration revision changed':'配置修订已变化，请等待页面刷新后重新锁定。',
    'Camera already started; restart the session to change devices':'相机已启动；更换设备需结束当前会话并重启。',
    'Original loaded tilt cone exceeded':'物体持稳姿态超过已验证倾角限制；请调整物品朝向。',
    'Fresh RGB frame required before restock':'补回前需要新鲜 RGB 画面，以确认原位已清空。',
    'Frozen original source is occupied; clear it before restock':'原位有物品占用；请清空原位，并把待补物品放在公共点 (300,200) mm。',
    'The returned object is still in the source workspace; place it at public (300,200) mm':'待补物品仍在源工作区；请放到公共点 (300,200) mm 后再选对应数字。',
}


def explain(error):
    text=str(error)
    for key,value in REASONS.items():
        if key in text:return value+' ['+text+']'
    if any(x in text for x in ('TABLE:','SELF:','PAYLOAD_','OBSTACLE:')):
        return '路径几何检查未通过：'+text+'；请按所示阶段、部位和净空值调整物品位置或朝向。'
    if 'IK' in text:return '抓取姿态求解未通过：'+text+'；已取消锚点半径限制，此处是反解或净空未满足。'
    return text


def vision_rows(camera):
    obs=camera.get('observation') or {};out=[];b=boundaries()
    for name in ('red_cube','eraser','small_canister'):
        row=next((x for x in obs.get('localizations',[]) if x['class_name']==name),{})
        top=row.get('top') or {};centre=row.get('object_centre_desktop_xyz_mm') or top.get('centre_desktop_xyz_mm')
        status=row.get('status','NOT_FOUND');reason=STATUS.get(status,status)
        if status in ('METRIC_GEOMETRY_REJECTED','SHAPE_OR_DIMENSIONS_REJECTED','CENTRE_OUTSIDE_WORKSPACE'):
            reason='；'.join(metric_failures(name,top)) or reason
        profile=None;allowed=bool(camera.get('ready') and row.get('geometry_gate_pass'))
        if not camera.get('ready'):reason='RGB 未就绪或图像超过 1 秒；配置仍可锁定，抓取需等待新鲜画面'
        if centre and row.get('geometry_gate_pass'):
            profile=profile_id(name,centre)
            if not (490<=centre[0]<=690 and 215<=centre[1]<=355):allowed=False;reason='中心超出 X=490～690、Y=215～355 mm 工作区'
        details={k:top[k] for k in ('opposite_edge_mean_mm','max_abs_adjacent_edge_cosine','diameter_mm','circle_residual_p95_fraction_radius') if k in top}
        out.append(dict(class_name=name,status=status,reason=reason,centre_mm=centre,profile_id=profile,
                        task_vision_ready=allowed,measurements=details))
    return out
