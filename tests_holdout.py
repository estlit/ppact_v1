"""
tests_holdout.py - run the locked predictions and classify the disagreements

The prediction file is never edited. When a result disagrees, the
disagreement is CLASSIFIED, because "failed" as a single category throws away
the only thing worth learning:

    ALIGNED               direction and range both hold
    DIRECTIONALLY ALIGNED right direction, outside the stated range
    PREDICTION DEFECT     the model is right and the prediction was wrong
    MODEL DEFECT          the prediction is right and the model is wrong
    BOUNDARY MISMATCH     the two measured different things; no comparison
    MODEL LIMITATION      the model cannot express what was predicted
    NOT EXPRESSIBLE       the scenario cannot be built at all

A high alignment rate is not the goal. Everything aligning would mean the
predictions were easy, or made after seeing neighbouring results.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

import dataclasses
import sys

sys.path.insert(0, ".")

from ppact import (APPLICATION_LIBRARY, MEMORY_LIBRARY, SystemConfig,
                   evaluate_system)
from ppact.runtime import simulate
from holdout_predictions_v1 import PREDICTIONS, _hash

LINE = "=" * 84
OUTCOMES = []


def record(pid, outcome, detail):
    OUTCOMES.append((pid, outcome, detail))


def _build(cfg):
    """Turn a prediction's config into a before/after pair."""
    app_key = cfg["app"]
    app = APPLICATION_LIBRARY[app_key]

    if "scale_weights_to_gb" in cfg or "context_tokens" in cfg:
        kw = {}
        if "scale_weights_to_gb" in cfg:
            kw["weight_bytes"] = cfg["scale_weights_to_gb"] * 1e9
        if "context_tokens" in cfg:
            ctx = cfg["context_tokens"]
            kw["context_tokens"] = ctx
            kw["kv_cache_bytes"] = app.kv_bytes_per_token * ctx
        app = dataclasses.replace(app, key="__hold__", **kw)
        APPLICATION_LIBRARY["__hold__"] = app
        app_key = "__hold__"

    base = SystemConfig(cfg["cpu"], cfg["compute"], cfg["memory"],
                        cfg["devices"],
                        preprocessing_mode=cfg.get("preprocessing_mode",
                                                   "cpu_only"))
    after = (dataclasses.replace(base, **cfg["change"])
             if "change" in cfg else base)
    return app_key, app, base, after


def _direction(a, b, tol=0.005):
    if a == 0:
        return "same" if b == 0 else ("up" if b > 0 else "down")
    chg = (b - a) / abs(a)
    if abs(chg) < tol:
        return "same"
    return "up" if chg > 0 else "down"


def run_one(p):
    app_key, app, base, after = _build(p.config)
    try:
        ra = evaluate_system(app, base)
        rb = evaluate_system(app, after) if after is not base else ra

        # --- feasibility predictions ---------------------------------------
        if p.directions == {}:
            got = "INFEASIBLE" not in rb.status
            if got == p.feasible:
                mem = MEMORY_LIBRARY[after.memory]
                record(p.pid, "ALIGNED",
                       f"predicted {'fits' if p.feasible else 'does not fit'}, "
                       f"got the same on "
                       f"{mem.capacity_gbyte * after.memory_devices:.0f} GB")
            else:
                record(p.pid, "PREDICTION DEFECT" if got else "MODEL DEFECT",
                       f"predicted {'fits' if p.feasible else 'does not fit'}, "
                       f"got the opposite - status {rb.status}")
            return

        if "INFEASIBLE" in rb.status:
            record(p.pid, "NOT EXPRESSIBLE",
                   "the configuration cannot hold its model, so the predicted "
                   "metrics do not exist")
            return

        am, bm = ra.metrics, rb.metrics
        wrong_direction, out_of_range, changed = [], [], []

        for metric, want in p.directions.items():
            if metric not in am:
                record(p.pid, "BOUNDARY MISMATCH",
                       f"the prediction names '{metric}', which the model does "
                       f"not report - the two are not measuring the same thing")
                return
            got = _direction(am[metric], bm[metric])
            if want != "any" and got != want:
                wrong_direction.append(
                    f"{metric}: predicted {want}, got {got} "
                    f"({(bm[metric] / am[metric] - 1) * 100:+.1f}%)"
                    if am[metric] else f"{metric}: predicted {want}, got {got}")

        for metric, (lo, hi) in p.ranges.items():
            chg = (bm[metric] / am[metric] - 1) * 100 if am[metric] else 0.0
            if not (lo <= chg <= hi):
                out_of_range.append(
                    f"{metric}: predicted {lo:+g}..{hi:+g}%, got {chg:+.1f}%")

        for metric in p.must_not_change:
            if metric in am and abs(am[metric] - bm[metric]) > 1e-9:
                changed.append(
                    f"{metric} moved "
                    f"{(bm[metric] / am[metric] - 1) * 100:+.2f}%"
                    if am[metric] else f"{metric} moved")

        if changed:
            record(p.pid, "MODEL DEFECT",
                   "a metric declared invariant moved: " + "; ".join(changed))
        elif wrong_direction:
            record(p.pid, "PREDICTION DEFECT" if p.basis == "JUDGEMENT"
                   else "DIRECTION DISAGREEMENT", "; ".join(wrong_direction))
        elif out_of_range:
            record(p.pid, "DIRECTIONALLY ALIGNED", "; ".join(out_of_range))
        else:
            record(p.pid, "ALIGNED", "direction and range both hold")

    finally:
        APPLICATION_LIBRARY.pop("__hold__", None)


def main():
    print(LINE)
    print(" BLIND HOLDOUT - LOCKED PREDICTIONS")
    print(LINE)
    print(f"  prediction file sha256  {_hash()[:32]}...")
    print(f"  predictions             {len(PREDICTIONS)}")
    print()
    print("  The prediction file is not edited after this runs. A "
          "disagreement")
    print("  is classified, not corrected - 'failed' as one category throws")
    print("  away the only thing worth learning from it.\n")

    for p in PREDICTIONS:
        try:
            run_one(p)
        except Exception as exc:
            record(p.pid, "NOT EXPRESSIBLE",
                   f"{type(exc).__name__}: {exc}")

    by_pid = {p.pid: p for p in PREDICTIONS}
    head = f"  {'id':<7s}{'basis':<11s}{'outcome':<24s}detail"
    print(head); print("  " + "-" * (len(head) - 2))
    for pid, outcome, detail in OUTCOMES:
        p = by_pid[pid]
        print(f"  {pid:<7s}{p.basis:<11s}{outcome:<24s}{detail[:38]}")
        if len(detail) > 38:
            print(f"  {'':<42s}{detail[38:120]}")

    counts = {}
    for _, outcome, _ in OUTCOMES:
        counts[outcome] = counts.get(outcome, 0) + 1
    print(f"\n{LINE}")
    for k in sorted(counts):
        print(f"  {k:<26s}{counts[k]}")
    print(LINE)
    aligned = counts.get("ALIGNED", 0)
    if aligned == len(OUTCOMES):
        print("  EVERYTHING ALIGNED. That is a reason for suspicion rather")
        print("  than satisfaction: either the predictions were easy, or they")
        print("  were made after seeing results from neighbouring runs. Both")
        print("  are contamination and neither shows in the numbers.")
    else:
        print("  Disagreements are the point. A prediction defect says the")
        print("  model was right and I was not; a model defect says the")
        print("  reverse; a boundary mismatch says the comparison was never")
        print("  valid. Only the third means nothing was learned.")
    print(LINE)
    # A holdout does not fail a build. It reports.
    return 0


if __name__ == "__main__":
    sys.exit(main())
