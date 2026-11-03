"""Resource / timing results from build reports (Phase 3 S8 candidate).

Accepted inputs, never mixed up:
  * gate lines written by the project's own Vivado build scripts (S4/S5):
      PHASE3_<STAGE>_IMPL_<KIND> key=value ...   e.g. PHASE3_S4_IMPL_TIMING WNS=0.227 TNS=0.000 ...
    -> kind "VIVADO_BUILD_GATE" (a real Vivado result, run by whoever produced the file);
  * Vivado report_utilization / report_timing_summary text (Slice LUTs, Slice Registers,
    Block RAM Tile, DSPs; WNS(ns) of the Design Timing Summary) -> "VIVADO_REPORT";
  * Yosys estimate JSON of this project -> "ESTIMATE_ONLY_NOT_VIVADO" (never reported as a result).
Each result keeps the file name and SHA-256 as provenance.  Designs are reported separately: the
vision (S3) and motion (S1/S2/S4) resources are NOT added into a whole-system figure; only a
single-design build (e.g. S5) gives a whole-design number, and then only as that build reports it.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

GATE = re.compile(r"^(PHASE3_\w+?)_IMPL_(\w+)\s+(.*)$")
KV = re.compile(r"(\w+)=([^\s]+)")


def _num(v: str):
    try:
        return int(v)
    except ValueError:
        try:
            return float(v)
        except ValueError:
            return v


def parse_gate_lines(path: Path) -> dict:
    data = Path(path).read_bytes()
    text = data.decode("utf-8", errors="replace")
    lines = text.splitlines()
    out = {"kind": "VIVADO_BUILD_GATE", "file": Path(path).name, "sha256": hashlib.sha256(data).hexdigest(),
           "first_line": lines[0] if lines else "", "designs": {}}
    for ln, line in enumerate(lines, start=1):
        m = GATE.match(line.strip())
        if not m:
            continue
        stage, kind, rest = m.group(1), m.group(2), m.group(3)
        kv = {k: _num(v) for k, v in KV.findall(rest)}
        d = out["designs"].setdefault(stage, {"builds": {}, "timing": None, "budget": None})
        if kind == "TIMING":
            d["timing"] = {**kv, "line": ln}
        elif kind == "BUDGET":
            d["budget"] = {**kv, "line": ln}
        else:
            build = kv.pop("build", kind.lower())
            d["builds"][f"{kind.lower()}:{build}"] = {**kv, "line": ln}
    for key in ("BIT", "HWH", "XSA"):
        m = re.search(rf"^{key} SHA-256 ([0-9a-f]{{64}})", text, re.M)
        if m:
            out[f"{key.lower()}_sha256"] = m.group(1)
    return out


_UTIL = {"LUT": r"\|\s*Slice LUTs\*?\s*\|\s*([\d.]+)", "FF": r"\|\s*Slice Registers\s*\|\s*([\d.]+)",
         "BRAM_TILE": r"\|\s*Block RAM Tile\s*\|\s*([\d.]+)", "DSP": r"\|\s*DSPs\s*\|\s*([\d.]+)"}


def parse_vivado_reports(utilization: Path | None = None, timing: Path | None = None) -> dict:
    out = {"kind": "VIVADO_REPORT"}
    if utilization is not None:
        data = Path(utilization).read_bytes()
        t = data.decode("utf-8", errors="replace")
        out["utilization"] = {k: (_num(m.group(1)) if (m := re.search(p, t)) else None) for k, p in _UTIL.items()}
        out["utilization_file"] = {"file": Path(utilization).name, "sha256": hashlib.sha256(data).hexdigest()}
    if timing is not None:
        data = Path(timing).read_bytes()
        t = data.decode("utf-8", errors="replace")
        m = re.search(r"WNS\(ns\)\s+TNS\(ns\).*?\n\s*-+.*?\n\s*(-?[\d.]+)\s+(-?[\d.]+)\s+(\d+)\s+(\d+)\s+(-?[\d.]+)\s+(-?[\d.]+)",
                      t, re.S)
        out["timing"] = ({"WNS": float(m.group(1)), "TNS": float(m.group(2)), "TNS_FAILING": int(m.group(3)),
                          "WHS": float(m.group(5)), "THS": float(m.group(6))} if m else None)
        out["timing_file"] = {"file": Path(timing).name, "sha256": hashlib.sha256(data).hexdigest()}
    return out


def parse_yosys_estimate(path: Path) -> dict:
    data = Path(path).read_bytes()
    d = json.loads(data)
    return {"kind": "ESTIMATE_ONLY_NOT_VIVADO", "file": Path(path).name, "sha256": hashlib.sha256(data).hexdigest(),
            "schema": d.get("schema"), "summary": {k: v for k, v in d.items() if k.endswith("raw_yosys") or
                                                   k.startswith("tray_patch_increment")}}
