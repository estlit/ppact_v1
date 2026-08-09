"""
tests_memory_review.py - three hundred screens, for eyes

WHY THIS IS NOT MORE RULES
==========================
R15 passes 218 checks. That establishes the screen obeys its contract and
says nothing about whether a person reading it understands where the
reasoning stopped and why.

    logically correct  is not  intuitively understood

The specific worry is the shape of the chain:

    ADEQUACY          PASS
    STABILITY         Stable PASS
    SERVICE RATE      NOT ESTABLISHED

A reader may take PASS as the answer and the rest as hedging. Whether they
do is not measurable by any rule that could be written here, which is why
three hundred of them are laid out to be looked at.

PAIRED, NOT ALONE
-----------------
Each panel shows the latency flow beside the memory analysis. The flow says
where the time goes; the memory screen says how far the reasoning about
memory can go. Seen together the second explains the first's silence about
cause - and that pairing is the thing to judge.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

import csv
import json
import os
import sys
from typing import Dict, List, Optional

sys.path.insert(0, ".")

LINE = "=" * 86
OUT_DIR = "memory_review"

# The mix asked for. Conditional is over-represented on purpose: it is the
# class whose meaning is least likely to survive contact with a reader.
# Conditional is capped at what EXISTS. The whole design space contains 52
# of them out of 164,736, so asking for 80 would report "3 of 80 SHORT"
# forever and say nothing about the product. The remainder is redistributed
# rather than left as a permanent shortfall.
TARGET = {
    "Stable PASS": 95,
    "Conditional": 52,
    "Stable FAIL": 95,
    "boundary": 30,
    "dual": 30,
}


def candidates():
    from ppact import (SystemConfig, APPLICATION_LIBRARY, COMPUTE_LIBRARY,
                       MEMORY_LIBRARY)
    import itertools
    for app_key, app in APPLICATION_LIBRARY.items():
        if not getattr(app, "target_inferences_per_s", 0):
            continue
        cpus = (["server_x86_x32"] if app.domain == "Data Center"
                else ["cortex_a53_x4", "cortex_a78_x4"])
        for cpu, comp, mem, units, pm, sc in itertools.product(
                cpus, COMPUTE_LIBRARY, MEMORY_LIBRARY, (1, 2, 4, 8),
                ("cpu_only", "isp_assisted", "isp_and_npu"),
                (None, "npu_32x32", "npu_64x64")):
            yield app_key, SystemConfig(
                cpu, comp, mem, units, preprocessing_mode=pm,
                secondary_compute=sc,
                execution_mode="parallel" if sc else "single",
                work_split=0.5 if sc else 0.0)


def bucket(mem, cfg) -> Optional[str]:
    """Which slot a case fills.

    CONDITIONAL FIRST, because it is the scarcest by an order of magnitude
    and the other slots were taking it. Checking boundary first left three
    Conditional cases in a review whose whole purpose is to find out
    whether Conditional means anything to a reader.
    """
    if mem.headroom is None:
        return None
    if mem.stability == "Conditional":
        return "Conditional"
    if abs(mem.headroom) < 2.0:
        return "boundary"
    if cfg.secondary_compute:
        return "dual"
    return mem.stability


def build_cases() -> List[Dict]:
    from ppact.review import build_review
    from ppact.visual import build_flow
    from ppact.memory_analysis import analyse_memory

    taken = {k: 0 for k in TARGET}
    seen = set()
    cases: List[Dict] = []

    for app_key, cfg in candidates():
        if all(taken[k] >= TARGET[k] for k in taken):
            break
        try:
            analysis = build_review("education_step_by_step", app_key, cfg)
            mem = analyse_memory(analysis)
            flow = build_flow(analysis)
        except Exception:
            continue
        slot = bucket(mem, cfg)
        if slot is None or taken[slot] >= TARGET[slot]:
            continue
        sig = (slot, app_key, cfg.compute, cfg.memory,
               cfg.memory_devices, cfg.preprocessing_mode,
               cfg.secondary_compute,
               round(mem.headroom, 1) if mem.headroom else None)
        # Conditional bypasses the duplicate filter. There are 52 in the
        # entire space and the filter was removing half of them, which
        # trades variety for coverage in the one class where coverage
        # matters most.
        if slot != "Conditional":
            if sig in seen:
                continue
            seen.add(sig)
        taken[slot] += 1
        cases.append(dict(
            case_id=f"{slot.replace(' ', '')}-{taken[slot]:03d}",
            slot=slot, app=app_key, cfg=cfg, mem=mem, flow=flow,
            analysis=analysis))
    return cases


def contact_sheets(cases, per_sheet: int = 4) -> List[str]:
    """Flow and memory side by side, twelve to a page.

    Six rather than twelve. At twelve the memory text rendered at 4.6pt -
    present on the page and unreadable, which is a sheet that looks like a
    review and is not one. The whole purpose is eyes, so the text has to be
    legible even at the cost of more sheets.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.image as mpimg
    except ImportError:
        return []
    from ppact.visual import render_flow_png
    from ppact.memory_analysis import render_memory_analysis

    sheets = []
    for n, start in enumerate(range(0, len(cases), per_sheet), 1):
        chunk = cases[start:start + per_sheet]
        rows = len(chunk)
        fig, axes = plt.subplots(rows, 2, figsize=(19, 10.5 * rows),
                                 gridspec_kw={"width_ratios": [1, 1.15]})
        if rows == 1:
            axes = [axes]
        for (ax_flow, ax_mem), case in zip(axes, chunk):
            ax_flow.axis("off")
            ax_mem.axis("off")
            png = os.path.join(OUT_DIR, f"{case['case_id']}_flow.png")
            try:
                render_flow_png(case["flow"], png)
                if os.path.isfile(png):
                    ax_flow.imshow(mpimg.imread(png))
            except Exception:
                pass
            # WITH the flow, so the panel names what the picture beside
            # it shows. Rendered without it the two halves referred to
            # nothing in common.
            text = "\n".join(render_memory_analysis(case["mem"],
                                                    case["flow"]))
            ax_mem.text(0, 1, text, ha="left", va="top", fontsize=7.6,
                        family="monospace", transform=ax_mem.transAxes)
            cfg = case["cfg"]
            head = (f"{case['case_id']}   {case['slot']}   "
                    f"{case['app']} / {cfg.compute}"
                    + (f" + {cfg.secondary_compute}"
                       if cfg.secondary_compute else "")
                    + f" / {cfg.memory} x{cfg.memory_devices} / "
                      f"{cfg.preprocessing_mode}")
            # On the FLOW panel only, and above it. Titling both columns
            # put the heading over the memory text and the two overlapped.
            ax_flow.set_title(head, fontsize=9, loc="left",
                              fontweight="bold", pad=10)
        fig.suptitle(f"Memory Review Contact Sheet {n}  -  "
                     f"latency flow (left) and memory analysis (right)",
                     fontsize=13, fontweight="bold")
        fig.text(0.5, 0.004,
                 "Judge whether a reader follows the chain to where it "
                 "stops, and whether NOT ESTABLISHED reads as a finding "
                 "rather than as hedging. No rule here can answer that.",
                 ha="center", fontsize=8, color="#555555")
        # Extra vertical room between panels: the closing caveat of one
        # memory screen was landing on the heading of the next, and the
        # sentence it collided with is the one saying a PASS is not a
        # bottleneck verdict.
        fig.tight_layout(rect=(0, 0.012, 1, 0.985))
        # Widened again after the cross-link was added: the memory panel
        # grew by ten lines and the closing caveat landed on the next
        # heading. Panel height has to follow the text, not the other way
        # round - shrinking the text to fit was how it became unreadable
        # the first time.
        fig.subplots_adjust(hspace=0.30)
        out = os.path.join(OUT_DIR, f"memory_review_sheet_{n:02d}.png")
        fig.savefig(out, dpi=80)
        plt.close(fig)
        sheets.append(out)
    return sheets


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    print(LINE)
    print(" MEMORY ANALYSIS VISUAL REVIEW")
    print(LINE)
    print("  R15 establishes the screen obeys its contract. It says")
    print("  nothing about whether a person understands where the")
    print("  reasoning stopped, which is what these sheets are for.\n")

    cases = build_cases()
    got: Dict[str, int] = {}
    for c in cases:
        got[c["slot"]] = got.get(c["slot"], 0) + 1
    for slot, want in TARGET.items():
        have = got.get(slot, 0)
        print(f"  {slot:<16s}{have:>4d} of {want:<4d}"
              f"{'ok' if have >= want else 'SHORT'}")
    print(f"  {'total':<16s}{len(cases):>4d}\n")

    sheets = contact_sheets(cases)

    with open(os.path.join(OUT_DIR, "memory_review_300.csv"), "w",
              newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["case_id", "slot", "application", "cpu", "compute",
                    "secondary", "memory", "units", "preprocessing",
                    "target", "host_required", "accel_required",
                    "concurrent", "effective_bw", "headroom", "adequacy",
                    "stability", "critical_overlap"])
        for c in cases:
            m, cfg = c["mem"], c["cfg"]
            w.writerow([c["case_id"], c["slot"], c["app"], cfg.cpu,
                        cfg.compute, cfg.secondary_compute or "-",
                        cfg.memory, cfg.memory_devices,
                        cfg.preprocessing_mode, m.target_rate,
                        round(m.host_required, 3),
                        round(m.accel_required, 3),
                        round(m.concurrent_requirement, 3),
                        round(m.effective_bandwidth, 3),
                        round(m.headroom, 3), m.adequacy, m.stability,
                        round(m.critical_overlap, 4)
                        if m.critical_overlap else ""])

    json.dump({
        "total_cases": len(cases),
        "by_slot": got,
        "targets": TARGET,
        "contact_sheets": sheets,
        "manual_review_status": "NOT REVIEWED",
        "what_the_sheets_are_for": [
            "Does a reader follow the chain to where it stops?",
            "Does NOT ESTABLISHED read as a finding or as hedging?",
            "Does a critical overlap of 0.98 mean anything to a reader?",
            "Is the screen too long once seen three hundred times?",
        ],
        "not_established": [
            "That any of the above is true. No rule in this file can "
            "answer them; that is why the sheets exist.",
        ],
    }, open(os.path.join(OUT_DIR, "review_manifest.json"), "w"), indent=2)

    print(f"{LINE}")
    print(f"  cases {len(cases)}   contact sheets {len(sheets)}")
    print(f"  manual review NOT REVIEWED")
    print(LINE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
