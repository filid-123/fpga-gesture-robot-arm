"""Draw the reviewed nominal trajectory and a proposed delivery support location."""
from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pc.mode_b.motion.export import load_package
from pc.mode_b.motion.kinematics import Robot
from pc.mode_b.motion.trajectory import dequantize, regenerate


def render(task_path: Path, output: Path):
    plan, config = load_package(task_path)
    robot = Robot(ROOT, config, grasp_width_mm=plan["grasp_model"]["object_width_mm"])
    rows = [(s, q) for s, samples in regenerate(plan["start_q16"], plan["segments"], config) for q in samples]
    points = np.array([robot.fk(dequantize(q))[:3, 3] for _, q in rows])
    phases = np.array([s["phase"] for s, _ in rows])
    markers = plan["milestones"]
    pickup = np.array(plan["request"]["pickup"]["centre_mm"])
    support = np.array(plan["request"]["destination"]["support_centre_mm"])
    buffer = np.array(markers["BUFFER"]["grasp_xyz_mm"])
    home = robot.fk(dequantize(plan["start_q16"]))[:3, 3]
    carrying = np.array([s["payload_attached"] for s, _ in rows])
    attachment = np.array(plan["attachment"]["grasp_from_object"])
    proposal_path = output/"delivery_candidate.json"
    previous = json.loads(proposal_path.read_text(encoding="utf8")) if proposal_path.exists() else {}
    footprint = np.array(plan["request"]["destination"]["size_xy_mm"])
    accepted = (previous.get("status") == "USER_ACCEPTED_PROVISIONAL" and
                previous.get("support_centre_mm") == support.tolist() and
                previous.get("support_size_xy_mm") == footprint.tolist())
    size = np.array(config["objects"][plan["object_class"]]["size_mm"])
    def coords(values):
        return "("+", ".join(f"{value:.1f}".removesuffix(".0") for value in values)+")"
    def milestone_xyz(phase):
        return np.array(markers[phase]["grasp_xyz_mm"])
    nominal_bottom = plan["transport_object_bottom_mm"]
    nominal_centre = nominal_bottom+size[2]/2
    corners = np.array(list(itertools.product([-1, 1], repeat=3)))*size/2
    indices = np.where(carrying)[0]
    centres, bottoms = [], []
    for i in indices:
        matrix = robot.fk(dequantize(rows[i][1])) @ attachment
        centres.append(matrix[2, 3])
        bottoms.append(np.min((corners @ matrix[:3, :3].T+matrix[:3, 3])[:, 2]))

    plt.rcParams.update({"font.family": "Microsoft YaHei", "axes.unicode_minus": False,
                         "svg.fonttype": "none", "font.size": 10})
    colors = {"ink": "#20354a", "muted": "#697b8e", "carry": "#de7c16", "green": "#168065"}
    fig = plt.figure(figsize=(15, 9.6), facecolor="#f7f9fc")
    title = "模式二路径规划 · 当前交付点（红块示例）" if accepted else "模式二路径规划 · 交付点审核（红块示例）"
    fig.text(.055, .96, title, fontsize=22, weight="bold", color=colors["ink"])
    fig.text(.055, .918, f"承托面中心 D = {coords(support)} mm　|　先竖直抬升，再向左转运　|　缓冲区只持物等待", fontsize=11, color=colors["muted"])
    ax = fig.add_axes([.06, .19, .59, .67], facecolor="white")
    ax.set(xlim=(0, 800), ylim=(0, 600), xlabel="桌面 X / mm（向右）", ylabel="桌面 Y / mm（向桌内）")
    ax.set_aspect("equal")
    ax.set_xticks(np.arange(0, 801, 100)); ax.set_yticks(np.arange(0, 601, 100))
    ax.grid(color="#e6ebf2", linewidth=.7, zorder=0)
    for spine in ax.spines.values():
        spine.set_color("#9eacbb")

    regions = [([60, 240, 210, 390], "#eceafa", "#b5a8ce", "手势区\n沿用预留", False),
               ([40, 240, 450, 570], "#f1f3f6", "#b8c2cc", "板卡安装预留", True),
               ([270, 450, 215, 355], "#fff0c6", "#c9ac58", "", False),
               ([490, 690, 215, 355], "#e0edfc", "#7c9fc6", "", False)]
    for bounds, fill, stroke, text, dashed in regions:
        x0, x1, y0, y1 = bounds
        ax.add_patch(Rectangle((x0, y0), x1-x0, y1-y0, facecolor=fill, edgecolor=stroke,
                               linewidth=1.2, linestyle="--" if dashed else "-", zorder=1))
        if text:
            ax.text((x0+x1)/2, (y0+y1)/2, text, ha="center", va="center", color=colors["muted"], fontsize=10)
    ax.add_patch(Rectangle((450, 355), 280, 245, facecolor="#f5f8fb", edgecolor="#c7d2df", hatch="//", lw=.8, alpha=.45, zorder=.8))
    ax.text(590, 550, "取物区后方保持净空\n不布置固定物品", ha="center", va="center", fontsize=10, color=colors["muted"])
    ax.text(360, 368, "缓冲区 180×140", ha="center", fontsize=10, color="#8b6b13")
    ax.text(590, 368, "取物区 200×140", ha="center", fontsize=10, color="#3c648a")
    ax.add_patch(Rectangle(support[:2]-footprint/2, *footprint, facecolor="#dcf2e8", edgecolor=colors["green"], lw=1.8, zorder=2))

    for mask, color, dashed, width in [(~carrying, "#8a9daf", True, 1.4), (carrying, colors["carry"], False, 2.7)]:
        plotted = points[:, :2].copy()
        plotted[~mask] = np.nan
        ax.plot(*plotted.T, color=color, lw=width, ls="--" if dashed else "-", zorder=3)
    for phase in ("BUFFER", "PREPLACE"):
        path = points[phases == phase, :2]
        j = max(1, len(path)//2)
        lo, hi = max(0, j-3), min(len(path)-1, j+3)
        ax.annotate("", xy=path[hi], xytext=path[lo], arrowprops={"arrowstyle": "-|>", "color": colors["carry"], "lw": 2.4, "mutation_scale": 16}, zorder=4)

    for point, label, color, offset, align in [
        (pickup, f"G 夹取中心\n{coords(pickup[:2])}\n① 下降夹取\n② 原地竖直抬升", "#c74440", (30, -7), "left"),
        (buffer, f"B 缓冲持物\n{coords(buffer[:2])}", "#b3790d", (14, -36), "left"),
        (support, f"D 交付候选\n{coords(support)}\n承托平顶 {footprint[0]:g}×{footprint[1]:g}", colors["green"], (-15, -30), "right"),
        (home, f"H 仿真 HOME 投影\n{coords(home[:2])}", colors["muted"], (16, 13), "left")]:
        ax.scatter(*point[:2], s=60, c=color, edgecolors="white", lw=1.2, zorder=6)
        ax.annotate(label, point[:2], xytext=offset, textcoords="offset points", ha=align, va="center", fontsize=9,
                    color=color, arrowprops={"arrowstyle": "-", "color": color, "lw": .9}, zorder=6,
                    bbox={"boxstyle": "round,pad=.25", "fc": "white", "ec": "none", "alpha": .92})
    base = np.array(config["table_from_urdf_world"]["xyz_mm"])
    ax.scatter(*base[:2], marker="+", s=95, linewidths=2, color=colors["ink"], zorder=6)
    ax.text(base[0]+14, base[1]+13, f"底座轴投影 {coords(base[:2])}", fontsize=9, color=colors["ink"])
    ax.text(0, -42, "原点 O=(0,0,0)；Z 轴竖直向上", fontsize=9, color=colors["muted"])
    ax.legend(handles=[Line2D([0], [0], color=colors["carry"], lw=2.6, label="持物路径（实际规划投影）"),
                       Line2D([0], [0], color="#8a9daf", lw=1.4, ls="--", label="空夹接近 / 返回（仿真）")],
              loc="upper left", bbox_to_anchor=(0, -.13), frameon=False, ncol=2, fontsize=9)

    elev = fig.add_axes([.72, .58, .25, .26], facecolor="white")
    relative_time = (indices+1)*config["period_s"]-(markers["GRASP"]["sample_index"]+1)*config["period_s"]
    elev.plot(relative_time, centres, color=colors["carry"], lw=2, label="红块中心")
    elev.plot(relative_time, bottoms, color="#527f9b", lw=1.3, ls="--", label="红块底面")
    elev.axhline(support[2], color=colors["green"], ls=":", lw=1)
    elev.text(relative_time[-1]*.04, support[2]+6, f"承托面 Z={support[2]:g}", color=colors["green"], fontsize=8)
    elev.set(title="持物阶段高度（红块示例）", xlabel="持物运动时间 / s（不含等待）", ylabel="桌面高度 Z / mm", ylim=(0, max(190, nominal_centre+30)))
    elev.set_yticks(sorted(set([0, float(support[2]), 80, float(nominal_bottom), float(nominal_centre)]))); elev.grid(alpha=.15)
    elev.legend(loc="upper center", ncol=2, frameon=False, fontsize=8)
    elev.text(.5, -.33, f"抬升 / 缓冲名义值：中心 {nominal_centre:g}，底面 {nominal_bottom:g} mm", transform=elev.transAxes, ha="center", fontsize=9, color=colors["muted"])

    table_ax = fig.add_axes([.71, .16, .27, .28]); table_ax.axis("off")
    table_ax.text(0, 1.08, "审核用关键点 / mm", fontsize=13, weight="bold", color=colors["ink"])
    table = table_ax.table(cellText=[
        ["G", "抓取中心", coords(pickup)],
        ["L", "抬升结束", coords(milestone_xyz("LIFT"))],
        ["B", "缓冲持物", coords(buffer)],
        ["P", "交付上方", coords(milestone_xyz("PREPLACE"))],
        ["D", "承托面中心", coords(support)],
        ["R", "松爪前中心", coords(milestone_xyz("PLACE"))]],
        colLabels=["点", "含义", "(X, Y, Z)"], colWidths=[.1, .33, .57], cellLoc="left", bbox=[0, .05, 1, .95])
    table.auto_set_font_size(False); table.set_fontsize(9)
    for (r, col), cell in table.get_celld().items():
        cell.set_edgecolor("#d8e0e9"); cell.set_linewidth(.65)
        cell.set_facecolor("#e8eef5" if r == 0 else "#dcf2e8" if r == 5 else "white")
        cell.set_text_props(color=colors["ink"], weight="bold" if r == 0 else "normal")
    table_ax.text(0, -.06, "G/L/B/P/R 按红块中心表达；D 是承托面。", fontsize=8.5, color=colors["muted"])

    status_text = "用户已接受当前交付点，允许后续调整。" if accepted else "审核候选，尚未冻结实体位置。"
    fig.text(.06, .047, status_text+"图示路径通过当前名义模型检查；HOME 为仿真姿态，实体关节 / 工具变换仍待标定。", fontsize=9, color=colors["muted"])
    fig.text(.06, .022, "手势区 / 板卡区沿用平面预留；尚未作为实测三维障碍验证。交付含 2.5 mm 名义释放间隙，接触与落稳待实体核对。", fontsize=8.5, color=colors["muted"])
    output.mkdir(parents=True, exist_ok=True)
    fig.savefig(output/"delivery_path_review.png", dpi=180, facecolor=fig.get_facecolor())
    fig.savefig(output/"delivery_path_review.svg", facecolor=fig.get_facecolor())
    plt.close(fig)

    proposal = {"schema": "gesture.mode_b.delivery_review.v1", "status": "USER_ACCEPTED_PROVISIONAL" if accepted else "PROPOSED_FOR_USER_REVIEW",
        "frame": "desk_global_mm", "support_centre_mm": support.tolist(), "support_size_xy_mm": footprint.tolist(),
        "support_rim_height_mm": 0, "red_cube_pickup_centre_mm": pickup.tolist(),
        "red_cube_buffer_centre_mm": buffer.tolist(), "nominal_transport_cube_bottom_mm": nominal_bottom,
        "base_axis_projection_mm": base[:2].tolist(), "base_to_support_xy_distance_mm": float(np.linalg.norm(support[:2]-base[:2])),
        "buffer_to_support_xy_distance_mm": float(np.linalg.norm(support[:2]-buffer[:2])),
        "evidence_plan_sha256": plan["plan_sha256"], "physical_execution_allowed": False,
        "planning_destination_accepted": accepted, "hardware_configuration_changed": False}
    if accepted:
        proposal["acceptance"] = previous["acceptance"]
    (output/"delivery_candidate.json").write_text(json.dumps(proposal, ensure_ascii=False, indent=2), encoding="utf8")
    print(json.dumps(proposal, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", type=Path, default=ROOT/"docs/phase3c/mode_b_motion_20261027/examples/red_cube/complete_task.json")
    parser.add_argument("--output", type=Path, default=ROOT/"docs/phase3c/mode_b_motion_20261027/delivery_review_v1")
    args = parser.parse_args()
    render(args.task, args.output)
