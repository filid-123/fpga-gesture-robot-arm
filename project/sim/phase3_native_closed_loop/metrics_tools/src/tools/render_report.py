"""Render metrics.json into the Markdown report template (Phase 3 S8 candidate).

  python src/tools/render_report.py --metrics metrics.json [--template templates/REPORT_TEMPLATE_CN.md] --out REPORT.md

Pure formatting: every number printed comes from metrics.json; NOT_MEASURED / INSUFFICIENT_SAMPLES are
printed as such; a SIMULATION run gets a banner on top and in every section heading line.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_TEMPLATE = HERE.parents[1] / "templates" / "REPORT_TEMPLATE_CN.md"


def _v(x) -> str:
    if isinstance(x, float):
        return f"{x:.3f}"
    return str(x)


def _rate(r: dict) -> str:
    if not isinstance(r, dict) or r.get("status"):
        return (r or {}).get("status", "NOT_MEASURED") + (f"（{r['reason']}）" if isinstance(r, dict) and r.get("reason") else "")
    lo, hi = r["wilson95"]
    return f"{r['k']}/{r['n']} = {r['rate']:.3f}（Wilson 95%：{lo:.3f}–{hi:.3f}）"


def _dist(d: dict) -> str:
    if not isinstance(d, dict) or d.get("status"):
        return (d or {}).get("status", "NOT_MEASURED") + (f"（{d['reason']}）" if isinstance(d, dict) and d.get("reason") else "")
    return (f"n={d['n']}，min {_v(d['min'])}，P50 {_v(d['p50'])}，P90 {_v(d['p90'])}，P95 {_v(d['p95'])}，"
            f"P99 {_v(d['p99'])}，max {_v(d['max'])} {d['unit']}")


def render(m: dict, template: str) -> str:
    sim = m["data_kind"] == "SIMULATION"
    banner = ("> **SIMULATION —— 以下数字来自仿真（S4 参考模型 + 合成 RGB-D + 内存链路），不是测量，不得作为成功率、"
              "时延或精度结果引用。**" if sim else
              "> 数据来自实际运行的日志；物理成功率只来自人工标注。" if m["data_kind"] == "MEASUREMENT" else
              "> 没有任务日志。")
    inputs = "\n".join(["| 角色 | 文件 | 字节 | SHA-256 |", "|---|---|---|---|"] +
                       [f"| {f['role']} | `{f['file']}` | {f['bytes']} | `{f['sha256']}` |" for f in m["bundle"]["files"]])
    g = m["gesture"]["classification"]
    if g.get("status"):
        gesture = f"- 分类：{g['status']}（{g.get('reason', '')}）"
    else:
        per = "\n".join(f"| {c} | {v.get('support', 0)} | " + (f"{v['precision']:.3f} | {v['recall']:.3f} | {v['f1']:.3f} |"
                                                              if "f1" in v else "no support | | |")
                        for c, v in g["per_class"].items())
        gesture = (f"- 样本 n = {g['n']}；准确率 {_rate(g['accuracy'])}；Macro-F1 = {g['macro_f1']:.3f}"
                   f"（{g['macro_f1_classes']} 个有支持的类别）\n\n| 类别 | 支持 | 精确率 | 召回率 | F1 |\n|---|---|---|---|---|\n{per}")
    ft = m["gesture"]["false_triggers"]
    gesture += "\n- 误触发：" + (f"{ft['status']}（{ft.get('reason', '')}）" if ft.get("status") else
                               f"{ft['false_triggers']} 次 / {ft['non_command_hours']:.3f} h 非指令时间")
    tasks, fist = [], []
    tk = m["tasks"]
    if tk.get("status"):
        tasks.append(f"- {tk['status']}（{tk.get('reason', '')}）")
        fist.append(f"- {tk['status']}")
    else:
        for mode, t in tk.items():
            tasks.append(f"### {mode}\n- 任务数 {t['tasks']}；结果分布 {t['outcomes']}\n"
                         f"- 日志层成功率（DONE / 非主动取消的任务）：{_rate(t['delivery_success_log_level'])}\n"
                         f"- 物理成功率（人工标注）：{_rate(t['delivery_success_physical'])}\n"
                         f"- 取消原因：{t['cancel_sources']}")
            f = t["fist_return"]
            fist.append(f"### {mode}\n- FIST 取消 {f['fist_cancels']} 次；已归还 {_rate(f['returned'])}；其中托盘 "
                        f"{f['tray_returns']} 次；停止保持（未归还）{f['halted_stop_and_hold']} 次；分布 {f['by_outcome']}\n"
                        f"- 物理归还（人工标注）：{_rate(f['physical'])}")
    lat = m["latency"]
    if lat.get("status"):
        latency = f"- {lat['status']}（{lat.get('reason', '')}）"
    else:
        rows = []
        for key, label in (("select_to_commit_ms", "选择→提交"), ("commit_to_end_ms", "提交→结束"),
                           ("select_to_end_ms", "选择→结束")):
            v = lat[key]
            if v.get("status"):
                rows.append(f"- {label}：{v['status']}")
            else:
                rows += [f"- {label}（{mode}）：{_dist(d)}" for mode, d in v.items()]
        rows += [f"- PC 处理（PC 时钟）：{_dist(lat['pc_processing_ms'])}",
                 f"- PS 往返（PS 时钟）：{_dist(lat['ps_round_trip_ms'])}",
                 f"- 网络往返估计：{_dist(lat['network_rtt_estimate_ms'])}"]
        st = lat["pc_pipeline_stages_host_ms"]
        if not st.get("status"):
            rows += [f"- PC 流水线 {k}（主机时钟）：{_dist(v)}" for k, v in st.items()]
        rows += [f"- PL 内部：{lat['pl_internal']['status']}（{lat['pl_internal']['reason']}）",
                 f"- 机械臂运动：{lat['arm_motion']['status']}（{lat['arm_motion']['reason']}）"]
        pt = m["pl_trace"]
        rows.append("- PL 轨迹：" + (pt["status"] if pt.get("status") else "; ".join(f"{k} {_dist(v)}" for k, v in pt.items())))
        latency = "\n".join(rows)
    dl = m["deadlines"]
    deadlines = (f"- {dl['status']}（{dl.get('reason', '')}）" if dl.get("status") else
                 f"- 路径等待超时 {dl['path_wait_timeouts']} 次（模式 B 任务 {dl['mode_b_tasks']}）；PC 规划超过期限 "
                 f"{dl['pc_deadline_misses']} 次\n- 配置的期限：" +
                 ("; ".join(f"{k} ≤ {v.get('limit_ms')} ms：{_rate(v)}" for k, v in dl["configured"].items())
                  if not dl["configured"].get("status") else dl["configured"]["status"]))
    cr = m["continuous_runs"]
    continuous = (f"- {cr['status']}（{cr.get('reason', '')}）" if cr.get("status") else "\n".join(
        f"- `{k}`：任务 {v['tasks']}，最长无故障/无 HALT 连续 {v['longest_streak_without_fault_or_halt']}，故障 {v['faults']}，"
        f"HALT {v['halts']}，跨度 {_v(v['span_s'])} s" for k, v in cr.items()))
    hwm = m["hardware"]
    hw_lines = []
    gates = hwm["vivado_build_gates"]
    if isinstance(gates, dict):
        hw_lines.append(f"- Vivado 构建结果：{gates['status']}（{gates['reason']}）")
    else:
        hw_lines.append("- 以下是输入文件中记录的 Vivado 构建结果：由生成该文件的一方运行，本工具只解析，不运行 Vivado，"
                        "也不把不同设计的资源相加")
        for gate in gates:
            hw_lines.append(f"- `{gate['file']}`（SHA-256 `{gate['sha256'][:16]}…`）：{gate['first_line']}")
            for design, d in gate["designs"].items():
                for build, v in d["builds"].items():
                    hw_lines.append(f"  - {design} {build}：" + "，".join(f"{k} {v[k]}" for k in v if k != "line"))
                if d["timing"]:
                    hw_lines.append(f"  - {design} 时序：WNS {d['timing'].get('WNS')} ns，TNS {d['timing'].get('TNS')}，"
                                    f"WHS {d['timing'].get('WHS')} ns")
    for e in hwm["estimates_not_results"]:
        hw_lines.append(f"- 估计（不是 Vivado 结果）：`{e['file']}` {e['summary']}")
    hw_lines.append(f"- 规则：{hwm['rule']}")
    nm = []

    def walk(x, path):
        if isinstance(x, dict):
            if x.get("status") in ("NOT_MEASURED",):
                nm.append(f"- {path}：{x.get('reason', '')}")
            for k, v in x.items():
                walk(v, f"{path}.{k}" if path else k)
        elif isinstance(x, str) and x.startswith("INSUFFICIENT_SAMPLES"):
            nm.append(f"- {path}：{x}")

    walk({k: m[k] for k in ("gesture", "tasks", "latency", "pl_trace", "deadlines", "continuous_runs", "hardware")}, "")
    subs = {"BANNER": banner, "GENERATED": m["generated_utc"], "DATA_KIND": m["data_kind"], "INPUTS": inputs,
            "GESTURE": gesture, "TASKS": "\n".join(tasks), "FIST": "\n".join(fist), "LATENCY": latency,
            "DEADLINES": deadlines, "CONTINUOUS": continuous, "HARDWARE": "\n".join(hw_lines),
            "NOT_MEASURED": "\n".join(nm) or "- 无"}
    text = template
    for k, v in subs.items():
        text = text.replace("{{" + k + "}}", v)
    if sim:
        text = text.replace("\n## ", "\n## [SIMULATION] ")
    return text


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--metrics", type=Path, required=True)
    ap.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    m = json.loads(args.metrics.read_text(encoding="utf-8"))
    text = render(m, args.template.read_text(encoding="utf-8"))
    args.out.write_bytes(text.encode("utf-8"))
    print(f"report written: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
