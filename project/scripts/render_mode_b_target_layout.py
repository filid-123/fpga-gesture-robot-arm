"""Render a requested destination layout without inventing an executable path."""
from __future__ import annotations
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def render(request_path, output):
    request = json.loads(request_path.read_text(encoding="utf8"))
    config = json.loads((ROOT/"config/ai_pc/mode_b_motion_nominal_v1.json").read_text(encoding="utf8"))
    target = np.array(request["destination"]["support_centre_mm"])
    size = np.array(request["destination"]["size_xy_mm"])
    pickup = np.array(request["pickup"]["centre_mm"])
    buffer = np.array(config["buffer_candidates_xy_mm"][0])
    plt.rcParams.update({"font.family": "Microsoft YaHei", "axes.unicode_minus": False, "svg.fonttype": "none"})
    fig = plt.figure(figsize=(14, 9), facecolor="#f7f9fc")
    fig.text(.06, .95, f"当前交付点布局 · ({target[0]:g}, {target[1]:g}, {target[2]:g}) mm", fontsize=21, weight="bold", color="#20354a")
    fig.text(.06, .90, "坐标已按用户要求更新；当前名义模型未找到满足放置约束的整程。虚线只表示任务意图。", fontsize=11, color="#a64335")
    ax = fig.add_axes([.065, .18, .62, .66], facecolor="white")
    ax.set(xlim=(0,800), ylim=(0,600), xlabel="桌面 X / mm（向右）", ylabel="桌面 Y / mm（向桌内）")
    ax.set_aspect("equal"); ax.set_xticks(np.arange(0,801,100)); ax.set_yticks(np.arange(0,601,100)); ax.grid(alpha=.15)
    regions = [("手势预留", [60,240,210,390], "#eee9fa"),
               ("左侧缓冲（仅持物）", config["buffer_bounds_xy_mm"], "#fff0c6"),
               ("取物区 200×140", config["pickup_bounds_xy_mm"], "#e0edfc"),
               ("板卡安装预留", [40,240,450,570], "#f0f2f5")]
    overlaps = []
    for label,bounds,color in regions:
        x0,x1,y0,y1 = bounds
        ax.add_patch(Rectangle((x0,y0),x1-x0,y1-y0,fc=color,ec="#9cabbc",lw=1.1))
        ax.text((x0+x1)/2,(y0+y1)/2 if "手势" in label or "板卡" in label else y1+13,label,ha="center",va="center",fontsize=10,color="#526879")
        low=np.maximum(target[:2]-size/2,[x0,y0]); high=np.minimum(target[:2]+size/2,[x1,y1])
        if np.all(high>low):
            overlaps.append((label,(high-low).tolist()))
            ax.add_patch(Rectangle(low,*(high-low),fc="none",ec="#c8463a",hatch="xxxx",lw=1.2,zorder=5))
    ax.add_patch(Rectangle((450,355),280,245,fc="#f4f7fa",ec="#c9d4df",hatch="//",alpha=.6))
    ax.text(590,545,"取物区后方保持净空",ha="center",fontsize=10,color="#64798c")
    ax.add_patch(Rectangle(target[:2]-size/2,*size,fc="#f6d8d2",ec="#b83930",lw=2,alpha=.8,zorder=3))
    for a,b in ((pickup[:2],buffer),(buffer,target[:2])):
        ax.annotate("",xy=b,xytext=a,arrowprops={"arrowstyle":"-|>","color":"#c67b33","lw":1.7,"linestyle":"--"},zorder=4)
    for xy,label,color,offset,align in [
        (pickup[:2],f"G 示例取物\n({pickup[0]:g}, {pickup[1]:g})","#bd493f",(16,-30),"left"),
        (buffer,f"B 缓冲候选\n({buffer[0]:g}, {buffer[1]:g})","#99721f",(0,-48),"center"),
        (target[:2],f"D 当前目标\n({target[0]:g}, {target[1]:g}, {target[2]:g})","#b83930",(-10,-75),"right")]:
        ax.scatter(*xy,s=65,c=color,edgecolors="white",lw=1.2,zorder=6)
        ax.annotate(label,xy,xytext=offset,textcoords="offset points",ha=align,fontsize=10,color=color,
                    arrowprops={"arrowstyle":"-","color":color},bbox={"boxstyle":"round,pad=.3","fc":"white","ec":"none","alpha":.95},zorder=7)
    base=np.array(config["table_from_urdf_world"]["xyz_mm"])
    ax.scatter(*base[:2],marker="+",s=100,lw=2,color="#20354a")
    ax.text(base[0]+15,base[1]+12,f"底座 ({base[0]:g},{base[1]:g})",fontsize=9,color="#20354a")
    ax.legend(handles=[Line2D([0],[0],ls="--",color="#c67b33",label="任务意图连线，非通过检查的运动轨迹"),
                       Rectangle((0,0),1,1,fc="none",ec="#c8463a",hatch="xxxx",label="承托占地与预留区域交叠")],
              loc="upper left",bbox_to_anchor=(0,-.12),frameon=False,fontsize=9)
    panel=fig.add_axes([.73,.2,.24,.62]); panel.axis("off")
    panel.text(0,1,"新目标检查结果",fontsize=15,weight="bold",color="#20354a")
    lines=["D 为承托面中心",f"上表面高度：{target[2]:g} mm",f"承托平顶假设：{size[0]:g}×{size[1]:g} mm",f"距底座轴水平约 {np.linalg.norm(target[:2]-base[:2]):.0f} mm","", "当前放置倾角限制：5°", "红块 / 橡皮 / 圆柱：", "均未找到有效末端反解", "尚未生成可执行整程", "", "25°范围诊断可找到末端解", "尚未检查完整路径与接触", "未采用此倾角改变执行约束", "", "按当前承托占地假设："]
    lines += [f"与{label}交叠 {extent[0]:g}×{extent[1]:g} mm" for label,extent in overlaps]
    panel.text(0,.94,"\n".join(lines),va="top",fontsize=10.2,linespacing=1.75,color="#43586b")
    fig.text(.06,.035,"桌面左下角为原点，Z轴向上。物体中心高度需叠加半个物高；旧交付点的通过结果不能用于新坐标。",fontsize=9,color="#64798c")
    output.mkdir(parents=True,exist_ok=True)
    for suffix in ("png","svg"):
        fig.savefig(output/("delivery_layout_current."+suffix),dpi=180,facecolor=fig.get_facecolor())
    plt.close(fig)


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request",type=Path,default=ROOT/"config/ai_pc/mode_b_motion_red_demo_v1.json")
    parser.add_argument("--output",type=Path,default=ROOT/"docs/phase3c/mode_b_motion_20261027/delivery_230_200_120")
    args=parser.parse_args(); render(args.request,args.output)
