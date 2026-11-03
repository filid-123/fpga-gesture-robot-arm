"""Mode B full-window policy, independent of historical calibration evidence."""
import json
import math
from pathlib import Path
import numpy as np

PATH = Path(__file__).resolve().parents[2]/'config/ai_pc/mode_b_full_workspace_20261030.json'


def policy():
    value=json.loads(PATH.read_text(encoding='utf-8-sig'))
    if value.get('schema')!='gesture.mode_b.full_workspace.v1' or value.get('workspace_xy_mm')!=[490,690,215,355]:
        raise ValueError('Invalid full-workspace policy')
    return value


def validate_source(name,centre):
    p=policy();point=np.asarray(centre,float);box=p['workspace_xy_mm']
    if (point.shape!=(3,) or not np.isfinite(point).all() or name not in p['height_by_class_mm']):
        raise ValueError('Finite registered desktop source required')
    if not(box[0]<=point[0]<=box[1] and box[2]<=point[1]<=box[3]):
        raise ValueError(f'WORKSPACE: {name} centre {point.tolist()} outside X={box[:2]}, Y={box[2:]} mm')
    if abs(point[2]-p['height_by_class_mm'][name])>p['height_tolerance_mm']:
        raise ValueError(f'HEIGHT: {name} requires object centre Z={p["height_by_class_mm"][name]} mm')
    return point


def upright_yaw(name,yaw):
    if not math.isfinite(yaw):raise ValueError('Finite yaw required')
    if name=='small_canister':return 0.
    # The user places objects square to desk axes. Preserve the eraser's X/Y
    # long-axis choice; discard noisy corner-fit angles instead of following them.
    return float((90*round(yaw/90))%180) if name=='eraser' else 0.
