"""Gesture classification metrics from LABELLED samples (Phase 3 S8 candidate).

Input: an evaluation file with one row per sample - CSV with columns sample_id,truth,pred[,session]
or JSON lines {"sample_id", "truth", "pred", "session"} - class names of the seven-class contract
(BACKGROUND, OBJECT_1, OBJECT_2, OBJECT_3, PALM_READY, FIST_CANCEL, OTHER_INVALID).  NO_DETECTION
(code 7 of the S3/S4 interface) is accepted as a prediction and counted as its own column.
Output: confusion matrix, accuracy, per-class precision/recall/F1 with support, Macro-F1 over the
classes that have support (a class with no support is listed as "no support", not averaged as 0 or 1).

False triggers (continuous operation): selection events (task_start of the PS log) that fall inside
an annotated interval whose truth label is not an object command (BACKGROUND / OTHER_INVALID /
PALM_READY / FIST_CANCEL / NO_HAND), reported per hour of annotated non-command time.
No labelled data -> NOT_MEASURED.  The shipped repository has NO real seven-class data.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from stats import NOT_MEASURED, rate

CLASSES = ("BACKGROUND", "OBJECT_1", "OBJECT_2", "OBJECT_3", "PALM_READY", "FIST_CANCEL", "OTHER_INVALID")
PRED_EXTRA = ("NO_DETECTION",)
COMMANDS = ("OBJECT_1", "OBJECT_2", "OBJECT_3")


def load_samples(path: Path) -> list:
    path = Path(path)
    text = path.read_bytes().decode("utf-8")
    if path.suffix.lower() == ".csv":
        rows = list(csv.DictReader(text.splitlines()))
    else:
        rows = [json.loads(l) for l in text.splitlines() if l.strip()]
    out = []
    for i, r in enumerate(rows, start=2 if path.suffix.lower() == ".csv" else 1):
        t, p = r["truth"].strip(), r["pred"].strip()
        if t not in CLASSES:
            raise ValueError(f"{path}:{i}: truth {t!r} is not a seven-class label")
        if p not in CLASSES + PRED_EXTRA:
            raise ValueError(f"{path}:{i}: prediction {p!r} is not a class")
        out.append({"sample_id": r.get("sample_id", str(i)), "truth": t, "pred": p, "session": r.get("session", ""),
                    "line": i})
    return out


def classification(samples: list) -> dict:
    if not samples:
        return {"status": NOT_MEASURED}
    cols = CLASSES + PRED_EXTRA
    cm = {t: {p: 0 for p in cols} for t in CLASSES}
    for s in samples:
        cm[s["truth"]][s["pred"]] += 1
    n = len(samples)
    correct = sum(cm[c][c] for c in CLASSES)
    per, f1s = {}, []
    for c in CLASSES:
        tp = cm[c][c]
        support = sum(cm[c].values())
        predicted = sum(cm[t][c] for t in CLASSES)
        if support == 0:
            per[c] = {"support": 0, "status": "no support", "predicted": predicted}
            continue
        precision = tp / predicted if predicted else 0.0
        recall = tp / support
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per[c] = {"support": support, "tp": tp, "predicted": predicted, "precision": precision, "recall": recall, "f1": f1}
        f1s.append(f1)
    return {"n": n, "accuracy": rate(correct, n), "macro_f1": sum(f1s) / len(f1s), "macro_f1_classes": len(f1s),
            "per_class": per, "confusion": cm, "columns": list(cols)}


def false_triggers(intervals: list, selections: list) -> dict:
    """intervals: [{"start_ns", "end_ns", "label"}] on the PS clock; selections: [{"t_ns", "task", "line"}]."""

    quiet = [iv for iv in intervals if iv["label"] not in COMMANDS]
    if not quiet:
        return {"status": NOT_MEASURED, "reason": "no annotated non-command interval"}
    quiet_ns = sum(iv["end_ns"] - iv["start_ns"] for iv in quiet)
    hits = [s for s in selections if any(iv["start_ns"] <= s["t_ns"] < iv["end_ns"] for iv in quiet)]
    hours = quiet_ns / 3.6e12
    return {"false_triggers": len(hits), "non_command_hours": hours, "per_hour": len(hits) / hours if hours else None,
            "selections_total": len(selections), "evidence": [{"task": s["task"], "t_ns": s["t_ns"], "line": s["line"]}
                                                              for s in hits]}
