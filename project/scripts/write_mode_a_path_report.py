"""Readable trajectory report from the exact generated native table."""
from pathlib import Path
import argparse,json,math


def write(candidate,out):
    plan=json.loads((candidate/'PLAN_NATIVE.json').read_text('utf-8'));summary=json.loads((candidate/'SUMMARY.json').read_text('utf-8'))
    version=plan['version'];layout=plan['layout'];points=layout['common_D_mm'];tilt=layout['delivery_pose']['tilt_deg_at_x_le_270'];palm=layout['palm_surface_candidate_z_mm']
    handover=version in ('0.8.0','0.8.1','0.8.2');pr=plan['execution_profile']
    text=['# 模式A最新路径规划 v'+version,'',
        '单位：桌面坐标mm，关节原生rad。基座和三块保持原位；OV5640=(195,195,333)，视域(0,0)～(310,310)。',
        f'交付H={points["H"]}，掌面参考Z={palm}；B/PRE/H末端倾角为{tilt/2:g}°/{tilt:g}°/{tilt:g}°。本轮六轴到位误差只记录。','',
        ('PL从新反馈接入HOME后：开爪 → INNER → 各槽上方Z80 → 下降至中心Z15 → 夹取 → 原XY抬升Z80 → INNER → B → PRE固定停2秒再确认0.5秒PALM → 盲递送至H → 盲释放 → H_CLEAR → INNER → HOME。PALM仅在PRE触发，之前及触发后不作PALM判断。' if handover else ('PL从新反馈接入HOME后：开爪 → INNER → 各槽上方Z80 → 下降至中心Z15 → 夹取 → 原XY抬升Z80 → INNER → B → PRE等待真实PALM_READY（无超时） → H → 释放 → 上抬至H_CLEAR → INNER → HOME。' if version=='0.7.0' else '从新反馈开爪 → INNER → 各槽上方Z80 → 下降至中心Z15 → 夹取 → 原XY抬升Z80 → INNER → B → PRE等待Enter（无超时） → H → 释放 → 上抬至H_CLEAR → INNER → HOME。')),'',
        f'{tilt:g}°表示工具沿基座到目标的径向向外倾斜，抓取段仍竖直。转运为关节插补；下降、抬升、递送和退爪作自适应直线细分。',
        '下表列出三色所有实际下发关键点；完整50Hz样本在PLAN_NATIVE.json，CSV可直接导入表格。','']
    for route,timing in zip(plan['paths'],summary['timing']):
        name={1:'红',2:'黄',3:'蓝'}[route['object']]
        text += [f'## {name}块 / object {route["object"]}','',
            f'纯插补{route["seconds"]:.2f}s，含固定停留约{timing["nominal_without_operator_wait_s"]:.2f}s，另加掌心等待、启动姿态差异及调度延迟。','',
            '| 阶段 | Q桌面XYZ mm | b | s | e | t | r | g | 插补s |','|---|---|---:|---:|---:|---:|---:|---:|---:|']
        for leg in route['legs']:
            p=leg['target_D_mm'];xyz='保持' if p is None else '('+','.join(f'{v:.1f}' for v in p)+')'
            text.append('| '+leg['label']+' | '+xyz+' | '+' | '.join(f'{v/65536:.6f}' for v in leg['target_q16'])+f' | {leg["seconds"]:.2f} |')
        text.append('')
    text += ['本规划采用历史A高位的固定关节残差假设。反解数值、S2和Coppelia通过不代表实体坐标误差已校准；本轮现场结果由操作者观察记录。',
        ((('板端ABI3406表41关键点、53段、栈17。v0.8.1复用已通过测试的v0.8.0同次BIT/HWH/XSA；载入加速表及参数。' if version=='0.8.1' else '板端ABI3406表41关键点、53段、栈17。新BIT包含FIST连续计时、PRE固定等待及确认后盲交付；必须配套新BIT。')+f'普通{pr["planned_speed_deg_s"]:g}°/s、夹取{pr["gripper_speed_deg_s"]:g}°/s、近手{pr["handover_speed_deg_s"]:g}°/s、释放{pr["release_speed_deg_s"]:g}°/s，T102{pr["speed_steps_s"]}/{pr["acceleration_100_steps_s2"]}，50Hz。上述时长另加PRE固定2秒和至少0.5秒PALM稳定确认。') if handover else ('板端ABI3405表41关键点、53段、栈17。新BIT支持按时序推进及固定停留，运行时一次载入新表，之后PL自主执行。' if version=='0.7.0' else '板端候选表41关键点、53段、栈17。当前旧BIT尚未装入新表及observe_all策略；本包PC三色流程用于确认实体点位。')),'']
    if version=='0.8.2':
        text[-2]=f'板端ABI3406表{summary["capacity"]["keypoints"]}关键点、{summary["capacity"]["segments"]}段、栈{summary["capacity"]["stack_max"]}。复用v080硬件与v081速度33/45/18/30°/s、T102600/27、50Hz；仅PRE由(270,175,180)移到(320,175,180)mm，B/H/H_CLEAR不变。FIST连续1秒后由PL回退执行栈，在原槽反向执行GRASP开爪，再抬升回HOME，成功归还恢复库存；释放已提交后的FIST仍忽略，D5/通信故障仍停止。PRE固定2秒、PALM至少0.5秒和所有精度只观察策略保持。'
    with out.open('x',encoding='utf-8') as f:f.write('\n'.join(text))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--candidate',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();write(a.candidate,a.out)
