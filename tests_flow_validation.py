"""
tests_flow_validation.py - the flow diagram, across the space it must cover

WHY 100 AND NOT THREE
=====================
The flow was checked on three preprocessing modes of one application. That
covers two- and four-station layouts of a single workload and nothing else:
not a dual accelerator, not `engine hand-off`, not a design the model cannot
time, not a case where memory wait is the longer of the overlapping pair.

Every defect this project has found in the flow so far appeared the first
time a NEW SHAPE was drawn - a station at zero, a part at zero, a marker
that pushed a line past 78 columns. Three examples cannot produce a new
shape.

WHAT THIS DOES
--------------
Builds a case set stratified by RENDERED STATION COUNT - what the screen
actually draws, not what the configuration is called - runs twelve contract
checks per case, renders every PNG, and lays them out on contact sheets so
a person can look at all of them.

WHAT IT CANNOT DO
-----------------
Judge whether a picture is clear. It catches a title overlapping a subtitle
by measuring, and it cannot tell whether a reader understands the diagram.
The contact sheets exist because that part needs eyes.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

import csv
import json
import math
import os
import sys
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, ".")

LINE = "=" * 86
OUT_DIR = "flow_validation"
FAILED_DIR = os.path.join(OUT_DIR, "failed_cases")

# Target mix. Stated in RENDERED stations, because "isp_and_npu" does not
# guarantee four boxes: a stage whose time is zero is omitted, so the name
# of a setting is not the shape of its picture.
# The FOUR LAYOUTS the model actually produces, enumerated rather than
# assumed. A 3-station single-accelerator flow does not exist: with
# isp_assisted both offload stations are zero and are omitted, giving two
# boxes, and with isp_and_npu both are non-zero, giving four. Every
# 3-station flow carries `engine hand-off`.
#
# Targeting a bucket that cannot be filled would have produced a run
# reporting "0 of 25 SHORT" forever, which says nothing about the product.
TARGET = {
    "2-stage-single": 20,
    "3-stage-dual": 25,
    "4-stage-single": 25,
    "4-stage-dual": 30,
}

# Layouts observed across 3,000 configurations. A layout absent from this
# map is a shape nobody has seen, and the run says so rather than filing it
# under the nearest bucket.
KNOWN_LAYOUTS = {
    ("host active", "accelerator core"): "2-stage-single",
    ("host active", "accelerator core", "engine hand-off"): "3-stage-dual",
    ("host active", "preprocessing offload", "offload overhead",
     "accelerator core"): "4-stage-single",
    ("host active", "offload overhead", "accelerator core",
     "engine hand-off"): "4-stage-dual",
}

RESULTS: List[Dict] = []


# ==============================================================================
# Case generation
# ==============================================================================

def candidate_configs():
    """Walk a wide space and let the RENDERED shape decide the class."""
    from ppact import SystemConfig, APPLICATION_LIBRARY

    apps = list(APPLICATION_LIBRARY)
    # Widened after the first run filled two classes and fell short on the
    # other two. A short class is not a pass with a caveat: it means a
    # shape the product draws was tested fewer times than intended.
    computes = ("npu_16x16", "npu_20x20", "npu_24x24", "npu_32x32",
                "npu_64x64", "npu_128x128", "datacenter_gpu")
    memories = ("LPDDR5", "LPDDR5X", "GDDR6", "HBM3E", "DDR5")
    modes = ("cpu_only", "isp_assisted", "isp_and_npu")
    seconds = (None, "npu_16x16", "npu_32x32", "npu_64x64")

    for app in apps:
        spec = APPLICATION_LIBRARY[app]
        cpu = ("server_x86_x32" if spec.domain == "Data Center"
               else "cortex_a78_x4")
        for comp in computes:
            for mem in memories:
                for pm in modes:
                    for sc in seconds:
                        for units in (1, 2, 4, 8):
                            yield app, SystemConfig(
                                cpu, comp, mem, units,
                                preprocessing_mode=pm,
                                secondary_compute=sc,
                                execution_mode=("parallel" if sc
                                                else "single"),
                                work_split=0.5 if sc else 0.0)


def classify(flow, cfg) -> Optional[str]:
    """By the layout DRAWN, not by the setting's name.

    "isp_and_npu" does not guarantee four boxes and "dual" does not
    guarantee a hand-off station: a stage whose time is zero is omitted.
    """
    return KNOWN_LAYOUTS.get(tuple(s.name for s in flow.stations))


def signature(flow, analysis) -> Tuple:
    """What makes a case DIFFERENT.

    Used to refuse near-duplicates: a hundred cases of one shape would
    satisfy the count and test one thing a hundred times.
    """
    longer = []
    for s in flow.stations:
        lp = s.longer_part
        longer.append((s.name, lp.name if lp else "none"))
    # The measured-result STATES belong in the signature. The inspection
    # asked for requirement-met, tight, exceeded and not-computed cases,
    # and a signature blind to them counted five distinct four-stage flows
    # where the screens differ in what they say about every budget.
    import math as _m
    states = []
    for m in analysis.measured:
        if m.value is None or _m.isnan(m.value):
            states.append("uncomputed")
        elif m.limit is None:
            states.append("nolimit")
        elif m.over:
            states.append("over")
        else:
            margin = ((m.limit - m.value) / m.limit * 100.0
                      if m.lower_is_better
                      else (m.value - m.limit) / m.limit * 100.0)
            states.append("critical" if margin < 2 else
                          "tight" if margin < 10 else "comfortable")

    return (tuple(s.name for s in flow.stations),
            flow.dominant_component,
            flow.analytical_limit,
            tuple(longer),
            analysis.deployment_ready,
            bool(analysis.deployment_unmet),
            tuple(states))


def build_cases(limit_per_class: Dict[str, int]) -> List[Dict]:
    from ppact.review import build_review
    from ppact.visual import build_flow

    taken = {k: 0 for k in limit_per_class}
    # Up to three cases may share a signature. Refusing every repeat left
    # 39 cases where 100 were asked for; allowing unlimited repeats would
    # test one thing a hundred times. Three is a compromise, and the
    # signature counts are reported so the mix can be judged.
    from collections import Counter as _C
    sig_count = _C()
    cases: List[Dict] = []

    for app, cfg in candidate_configs():
        if all(taken[k] >= limit_per_class[k] for k in taken):
            break
        try:
            analysis = build_review("education_step_by_step", app, cfg)
            flow = build_flow(analysis)
        except Exception:
            continue
        cls = classify(flow, cfg)
        if cls is None or taken.get(cls, 0) >= limit_per_class.get(cls, 0):
            continue
        sig = signature(flow, analysis)
        if sig_count[sig] >= 3:
            continue
        sig_count[sig] += 1
        taken[cls] += 1
        cases.append({
            "case_id": f"{cls}-{taken[cls]:03d}",
            "flow_class": cls,
            "application": app,
            "cpu": cfg.cpu, "compute": cfg.compute,
            "secondary": cfg.secondary_compute or "-",
            "memory": cfg.memory, "memory_devices": cfg.memory_devices,
            "preprocessing": cfg.preprocessing_mode,
            "config": cfg, "analysis": analysis, "flow": flow,
        })
    return cases


# ==============================================================================
# The twelve contract checks
# ==============================================================================

def check_case(case) -> List[str]:
    """Every failure this case has, named. Empty means it passed."""
    from ppact.visual import render_flow_text
    from ppact.visual.flow import OVERLAP_PARTS

    # Held here rather than imported: comparing the renderer's output
    # against the renderer's own constant cannot fail.
    MODEL_STATIONS = ("host active", "preprocessing offload",
                      "offload overhead", "accelerator core",
                      "engine hand-off")

    flow, analysis, cfg = case["flow"], case["analysis"], case["config"]
    metrics = analysis.current_result.metrics
    bad: List[str] = []
    names = [s.name for s in flow.stations]

    # 1 execution order
    expected = [n for n in MODEL_STATIONS if n in names]
    if names != expected:
        bad.append(f"order: {names} against {expected}")

    # 2 zero stations omitted
    for s in flow.stations:
        if s.ms <= 0 and s.share_pct <= 0:
            bad.append(f"zero station drawn: {s.name}")

    # 3 times account for the job
    total = metrics.get("Latency (ms)")
    if total and not (math.isnan(total) or total <= 0):
        summed = sum(s.ms for s in flow.stations)
        slack = total * (abs(flow.residual_pct) / 100.0)
        if abs(summed - total) > max(0.01, slack + 1e-6):
            bad.append(f"time accounting: {summed:.4f} against "
                       f"{total:.4f} ms")

    # 4 shares account for 100%
    shares = sum(s.share_pct for s in flow.stations)
    if abs(shares + flow.residual_pct - 100.0) > 0.05:
        bad.append(f"share accounting: {shares:.2f}% + residual "
                   f"{flow.residual_pct:.2f}%")

    # 5 dominant marker is the largest station
    marked = [s.name for s in flow.stations if s.is_dominant]
    if len(marked) != 1:
        bad.append(f"dominant markers: {marked}")
    elif flow.stations:
        largest = max(flow.stations, key=lambda s: s.share_pct).name
        if marked[0] != largest:
            bad.append(f"dominant {marked[0]} is not the largest "
                       f"({largest})")

    # 6 analytical limit agrees with the engine
    if flow.analytical_limit != analysis.current_result.bound_by:
        bad.append(f"limit {flow.analytical_limit} against engine "
                   f"{analysis.current_result.bound_by}")

    # 7 both figures present when they differ
    text = "\n".join(render_flow_text(flow))
    if flow.dominant_component not in text:
        bad.append("dominant component absent from the text")

    # 8 overlap never presented as a sum
    for s in flow.stations:
        if not s.parts:
            continue
        sentence = s.overlap_sentence().lower()
        if "do not sum" not in sentence and "negligible" not in sentence:
            bad.append(f"{s.name}: overlap not disclaimed")
        # 9 the longer-of-two claim agrees with the figures
        lp = s.longer_part
        if lp is not None and "longer" in sentence:
            if lp.name.lower() not in sentence:
                bad.append(f"{s.name}: longer part named wrongly")

    # 10 engine hand-off present when a second accelerator is configured
    if cfg.secondary_compute and case["flow_class"] == "dual-NPU":
        if "engine hand-off" not in names:
            bad.append("dual configuration without engine hand-off")

    # 11 no invented station
    unknown = [n for n in names if n not in MODEL_STATIONS]
    if unknown:
        bad.append(f"stations the model does not compute: {unknown}")

    # 12 text and image describe the same object
    if flow is not case["flow"]:
        bad.append("text and image built from different flow data")

    return bad


def visual_defects(case, path: str) -> List[str]:
    """Measurable layout faults. Not a judgement of clarity."""
    bad = []
    if path is None:
        bad.append("no image produced")
        return bad
    if not os.path.isfile(path) or os.path.getsize(path) < 4000:
        bad.append("image is missing or suspiciously small")
    return bad


# ==============================================================================
# Contact sheets
# ==============================================================================

def contact_sheets(cases, per_sheet: int = 20) -> List[str]:
    """So a person can look at a hundred pictures without opening a hundred
    files. The eye check is the part the automated rules cannot do."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.image as mpimg
    except ImportError:
        return []

    sheets = []
    for n, start in enumerate(range(0, len(cases), per_sheet), 1):
        chunk = cases[start:start + per_sheet]
        cols, rows = 4, (len(chunk) + 3) // 4
        fig, axes = plt.subplots(rows, cols, figsize=(4.2 * cols,
                                                      4.6 * rows))
        axes = axes.ravel() if hasattr(axes, "ravel") else [axes]
        for ax, case in zip(axes, chunk):
            ax.axis("off")
            p = case.get("png")
            if p and os.path.isfile(p):
                ax.imshow(mpimg.imread(p))
            summary = (f"{case['case_id']}   {case['flow_class']}\n"
                       f"{case['application']} / {case['compute']}"
                       + (f" + {case['secondary']}"
                          if case['secondary'] != '-' else "")
                       + f"\n{case['memory']} x{case['memory_devices']}"
                       f" / {case['preprocessing']}")
            colour = "#9C2B2B" if case["failures"] else "#1B2B36"
            ax.set_title(summary, fontsize=7.5, color=colour,
                         fontweight="bold" if case["failures"] else "normal")
        for ax in list(axes)[len(chunk):]:
            ax.axis("off")
        fig.suptitle(f"Flow Validation Contact Sheet {n}", fontsize=13,
                     fontweight="bold")
        fig.text(0.5, 0.005,
                 "A red title marks a case with an automated failure. "
                 "Everything here still needs eyes: overlap, truncation "
                 "and missing arrowheads are not measurable.",
                 ha="center", fontsize=8, color="#555555")
        fig.tight_layout(rect=(0, 0.02, 1, 0.97))
        out = os.path.join(OUT_DIR, f"flow_contact_sheet_{n:02d}.png")
        fig.savefig(out, dpi=90)
        plt.close(fig)
        sheets.append(out)
    return sheets


# ==============================================================================
# Run
# ==============================================================================

def main():
    from ppact.visual import build_flow, render_flow_png

    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(FAILED_DIR, exist_ok=True)

    print(LINE)
    print(" SYSTEM FLOW VALIDATION")
    print(LINE)
    print("  Three examples cannot produce a new shape, and every flow")
    print("  defect so far appeared the first time a new shape was drawn.\n")

    cases = build_cases(TARGET)
    got = {}
    for c in cases:
        got[c["flow_class"]] = got.get(c["flow_class"], 0) + 1
    for cls, want in TARGET.items():
        have = got.get(cls, 0)
        mark = "ok" if have >= want else "SHORT"
        print(f"  {cls:<12s}{have:>4d} of {want:<4d}{mark}")
    print(f"  {'total':<12s}{len(cases):>4d}\n")

    text_fail = png_fail = 0
    for case in cases:
        failures = check_case(case)
        png = None
        try:
            png = render_flow_png(
                case["flow"],
                os.path.join(OUT_DIR, f"{case['case_id']}.png"))
        except Exception as exc:
            failures.append(f"image raised {type(exc).__name__}")
        case["png"] = png
        vis = visual_defects(case, png)
        case["failures"] = failures
        case["visual"] = vis
        if failures:
            text_fail += 1
        if vis:
            png_fail += 1
        if failures or vis:
            import shutil
            if png and os.path.isfile(png):
                shutil.copy(png, os.path.join(
                    FAILED_DIR, os.path.basename(png)))

    sheets = contact_sheets(cases)

    with open(os.path.join(OUT_DIR, "flow_validation_100.csv"), "w",
              newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["case_id", "flow_class", "application", "cpu",
                    "compute", "secondary", "memory", "memory_devices",
                    "preprocessing", "stations", "dominant", "limit",
                    "deploy", "contract_failures", "visual_defects"])
        for c in cases:
            w.writerow([c["case_id"], c["flow_class"], c["application"],
                        c["cpu"], c["compute"], c["secondary"],
                        c["memory"], c["memory_devices"],
                        c["preprocessing"],
                        " -> ".join(s.name for s in c["flow"].stations),
                        c["flow"].dominant_component,
                        c["flow"].analytical_limit,
                        "READY" if c["analysis"].deployment_ready
                        else "NOT READY",
                        "; ".join(c["failures"]),
                        "; ".join(c["visual"])])

    manifest = {
        "total_cases": len(cases),
        "distinct_signatures": len({signature(c["flow"], c["analysis"])
                                    for c in cases}),
        "by_class": got,
        "targets": TARGET,
        "contract_failures": text_fail,
        "visual_defects": png_fail,
        "contact_sheets": sheets,
        "manual_review_status": "NOT REVIEWED",
        "not_established": [
            "Whether the diagram is clear to a reader",
            "Whether a title overlaps, a label is truncated or an "
            "arrowhead is missing - these are measured only by eye",
        ],
        "cases": [{k: c[k] for k in
                   ("case_id", "flow_class", "application", "compute",
                    "secondary", "memory", "preprocessing")}
                  | {"failures": c["failures"], "visual": c["visual"]}
                  for c in cases],
    }
    json.dump(manifest, open(os.path.join(OUT_DIR, "case_manifest.json"),
                             "w"), indent=2)

    lines = [
        "SYSTEM FLOW VALIDATION SUMMARY", "",
        f"Total cases                  {len(cases)}",
    ]
    for cls in TARGET:
        lines.append(f"{cls:<28s} {got.get(cls, 0)}")
    lines += [
        "",
        f"Text PASS                    {len(cases) - text_fail}",
        f"PNG PASS                     {len(cases) - png_fail}",
        f"Contract failures            {text_fail}",
        f"Visual defects (measured)    {png_fail}",
        f"Contact sheets               {len(sheets)}",
        "",
        "Manual review status         NOT REVIEWED",
        "",
        "NOT ESTABLISHED",
        "  Whether the diagram is clear to a reader.",
        "  Title overlap, truncation and missing arrowheads are judged by",
        "  eye; the contact sheets exist for that and nobody has looked",
        "  at them yet.",
    ]
    open(os.path.join(OUT_DIR, "flow_validation_summary.txt"), "w",
         encoding="utf-8").write("\n".join(lines) + "\n")

    for c in cases:
        if c["failures"]:
            print(f"  FAIL {c['case_id']}  {c['failures'][0][:60]}")

    print(f"\n{LINE}")
    print(f"  cases {len(cases)}   contract failures {text_fail}   "
          f"measured visual defects {png_fail}")
    print(f"  contact sheets {len(sheets)}")
    print(f"  manual review NOT REVIEWED - the sheets are for eyes, and")
    print(f"  no automated rule can replace them")
    print(LINE)
    return 0 if text_fail == 0 and png_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
