"""Export a trajectory plot and a self-contained interactive nominal replay."""
from __future__ import annotations
import argparse
import itertools
import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pc.mode_b.motion.kinematics import Robot
from pc.mode_b.motion.export import load_package
from pc.mode_b.motion.trajectory import dequantize, regenerate


def render(task_path, output):
    plan, config = load_package(task_path)
    robot = Robot(ROOT, config, grasp_width_mm=plan["grasp_model"]["object_width_mm"])
    sequence = [(s, row) for s, rows in regenerate(plan["start_q16"], plan["segments"], config) for row in rows]
    positions = np.array([robot.fk(dequantize(q))[:3, 3] for _, q in sequence])
    output.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.5), layout="constrained")
    ax = axes[0]
    ax.add_patch(Rectangle((0, 0), 800, 600, fc="#f6f7fa", ec="#c5ccd6"))
    for bounds, color, label in [(config["pickup_bounds_xy_mm"], "#dceaf9", "Pickup"),
                                  (config["buffer_bounds_xy_mm"], "#fff0c5", "Holding buffer")]:
        x0, x1, y0, y1 = bounds
        ax.add_patch(Rectangle((x0, y0), x1-x0, y1-y0, fc=color, ec="#94a3b8"))
        ax.text((x0+x1)/2, y1+9, label, ha="center", fontsize=9)
    ax.plot(positions[:, 0], positions[:, 1], color="#52779a", lw=1.5, label="Grasp reference")
    source = plan["request"]["pickup"]["centre_mm"]
    target = plan["request"]["destination"]["support_centre_mm"]
    for xy, color, label in [(source, "#cf4141", "Source"), (target, "#22996c", "Delivery support"),
                             (config["table_from_urdf_world"]["xyz_mm"], "#323d4b", "Base")]:
        ax.scatter(*xy[:2], c=color, s=42, zorder=5)
        ax.annotate(label, xy[:2], xytext=(6, -17), textcoords="offset points", fontsize=9)
    ax.set(xlim=(0, 800), ylim=(0, 600), xlabel="Desk X (mm)", ylabel="Desk Y (mm)", title="Complete task / top view")
    ax.set_aspect("equal")
    ax.grid(alpha=.15)
    ax = axes[1]
    time = np.arange(1, len(positions)+1)*config["period_s"]
    ax.plot(time, positions[:, 2], color="#52779a", lw=2)
    labels = {"GRASP": (0, 10), "LIFT": (-20, 23), "BUFFER": (12, -22),
              "PLACE": (-24, 22), "RELEASE": (25, -23), "RETURN_HOME": (-20, -23)}
    for phase, offset in labels.items():
        m = plan["milestones"][phase]
        i = m["sample_index"]
        ax.scatter(time[i], positions[i, 2], s=25)
        ax.annotate(phase.replace("_", " "), (time[i], positions[i, 2]), xytext=offset,
                    textcoords="offset points", ha="center", fontsize=7,
                    arrowprops={"arrowstyle": "-", "color": "#94a3b8", "lw": .7})
    ax.set(xlabel="Nominal motion time, excludes waits (s)", ylabel="Grasp reference Z (mm)",
           title="Vertical lift before left transfer")
    ax.grid(alpha=.2)
    fig.suptitle("Mode B / nominal simulation / "+plan["object_class"], fontsize=15)
    fig.savefig(output/"trajectory_preview.png", dpi=160)
    plt.close(fig)

    frames = []
    chosen = set(np.unique(np.linspace(0, len(sequence)-1, min(450, len(sequence))).astype(int)))
    shape = np.array(config["objects"][plan["object_class"]]["size_mm"])
    corners = np.array(list(itertools.product([-1, 1], repeat=3)))*shape/2
    from pc.mode_b.motion.kinematics import transform
    payload = transform(source, [0, 0, np.radians(plan["request"]["pickup"]["yaw_deg"])])
    for i, (segment, q) in enumerate(sequence):
        f = robot.frames(dequantize(q))
        if segment["payload_attached"]:
            payload = f["grasp"] @ np.array(plan["attachment"]["grasp_from_object"])
        if i not in chosen:
            continue
        points = [f[name][:3, 3].tolist() for name in ("base_link", "link1", "link2", "link3", "link4", "link5", "grasp")]
        frames.append({"t":round((int(i)+1)*config["period_s"], 2), "phase":segment["phase"], "points":points,
                       "payload_corners":(corners @ payload[:3, :3].T+payload[:3, 3]).tolist()})
    data = json.dumps({"frames":frames, "source":source, "target":target,
                       "pickup":config["pickup_bounds_xy_mm"], "buffer":config["buffer_bounds_xy_mm"]})
    html = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>模式二轨迹预览</title>
<style>body{font:16px system-ui;background:#f4f6fa;color:#263347;max-width:1100px;margin:30px auto;padding:20px}canvas{background:white;border-radius:12px;width:48%;border:1px solid #d9e0e9}input{width:75%}button{padding:8px 20px}p{line-height:1.7}</style>
<h2>模式二：完整任务轨迹预览</h2><p>名义运动学仿真。左：桌面俯视；右：X–Z侧视。蓝线为机械臂骨架，红框为物体包围体，红点为夹取位置，绿点为承托面中心。等待时间未计入播放。</p>
<canvas id="top" width="520" height="420"></canvas> <canvas id="side" width="520" height="420"></canvas>
<p><button id="play">播放 / 暂停</button> <input id="slider" type="range" min="0" value="0"><span id="label"></span></p>
<p>此预览不连接机械臂。接触力、摩擦和滑落需要后续实测验证。</p><script>const data=DATA;
const slider=document.getElementById('slider');slider.max=data.frames.length-1;let playing=false;
function draw(canvas,frame,side){let points=frame.points,c=canvas.getContext('2d');c.clearRect(0,0,520,420);let xy=p=>[35+p[0]*.58,390-p[side?2:1]*.55];c.strokeStyle='#d8e0eb';c.strokeRect(35,60,464,330);
if(!side){for(let [b,color] of [[data.pickup,'#dceaf9'],[data.buffer,'#fff0c5']]){c.fillStyle=color;c.fillRect(35+b[0]*.58,390-b[3]*.55,(b[1]-b[0])*.58,(b[3]-b[2])*.55)}}
c.strokeStyle='#52779a';c.lineWidth=7;c.lineCap='round';c.beginPath();points.forEach((p,i)=>{let a=xy(p);i?c.lineTo(...a):c.moveTo(...a)});c.stroke();for(let p of points){c.fillStyle='#263347';c.beginPath();c.arc(...xy(p),5,0,7);c.fill()}
for(let [p,color] of [[data.source,'#cf4141'],[data.target,'#22996c']]){c.fillStyle=color;c.beginPath();c.arc(...xy(p),6,0,7);c.fill()}
c.strokeStyle='#cf4141';c.lineWidth=2;let corners=frame.payload_corners;for(let i=0;i<8;i++){for(let bit of [1,2,4]){let j=i^bit;if(j>i){c.beginPath();c.moveTo(...xy(corners[i]));c.lineTo(...xy(corners[j]));c.stroke()}}}}
function update(){let f=data.frames[+slider.value];draw(document.getElementById('top'),f,false);draw(document.getElementById('side'),f,true);document.getElementById('label').textContent=f.t+' s · '+f.phase}
slider.oninput=update;document.getElementById('play').onclick=()=>playing=!playing;setInterval(()=>{if(playing){slider.value=(+slider.value+1)%data.frames.length;update()}},60);update();</script></html>'''
    (output/"interactive_replay.html").write_text(html.replace("DATA", data), encoding="utf8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    render(args.task, args.output)
