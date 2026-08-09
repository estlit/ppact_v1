"""
ppact.decide - what changed, by how much, why, and what to do about it

THE RULE THIS MODULE ENFORCES
============================
No abstract adjective ever stands alone.

"SLOWER" tells a student nothing. Slower at what - one job, the frame rate,
the response to a sensor? Slower by a millisecond or by a factor of three?
Slower because the arithmetic grew, or because two engines are queueing for
one memory? Five different facts hide behind one word, and the word is the
part a student remembers.

So every comparison this module prints has the same four parts, in the same
order:

    1  WHAT CHANGED     the named metric, both values, the percentage
    2  WHY              a breakdown that SUMS to the difference
    3  HOW SURE         robust, conditional, or resting on an assumption
    4  WHAT TO DO       a recommendation, last, after its evidence

The conclusion comes last on purpose. A verdict printed first is a verdict
the reader accepts before seeing the reason, and the reason is the lesson.

THE BREAKDOWN HAS TO ADD UP
---------------------------
A "reason breakdown" whose parts do not sum to the difference is a story
about a number rather than an account of it. The decomposition used here is
an identity the engine actually satisfies:

    Latency = host active
            + accelerator core time
            + hand-off between engines
            + offload overhead
            + exposed preprocessing

verified to zero residue across every configuration in the library. If a
future change breaks it, the residue is printed rather than hidden, because a
breakdown that silently absorbs a millisecond is worse than none.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

LINE = "=" * 78
RULE = "-" * 78

# Words that must never appear as a verdict on their own. Each is banned
# because it names a direction without naming what moved, by how much, or
# why - and a student cannot carry any of those three home from one word.
BANNED_ALONE = ("faster", "slower", "better", "worse", "improved", "degraded",
                "ships", "wins", "loses", "good", "bad")

# The additive decomposition of one job's latency. Order is the order a frame
# passes through them, so the breakdown reads as a journey rather than a list.
LATENCY_TERMS = (
    ("host active", "CPU active (ms)",
     "preparing the frame, dispatching it, and formatting the result"),
    ("preprocessing offload", "Preprocess exposed (ms)",
     "preparation moved off the host that the host still waits for"),
    ("offload overhead", "Offload overhead (ms)",
     "handing the preparation to another block and getting it back"),
    ("accelerator core", "Delivered core time (ms)",
     "the arithmetic, plus whatever data-wait it could not hide"),
    ("engine hand-off", "Handoff (ms)",
     "splitting one job between two engines and merging the halves"),
)

# What a bottleneck label means in words a student has not met before.
BOTTLENECK_PLAIN = {
    "compute": "the accelerator is busy multiplying",
    "memory": "the accelerator is waiting for data",
    "not evaluated": "the design cannot run, so nothing is waiting",
}

HOST_STATE_PLAIN = {
    "compute": "the host is busy processing",
    "memory": "the host is waiting for memory",
    "balanced": "the host splits its time between processing and waiting",
}


@dataclass
class Term:
    name: str
    before: float
    after: float
    note: str

    @property
    def delta(self) -> float:
        return self.after - self.before


def latency_breakdown(before: Dict, after: Dict) -> Tuple[List[Term], float]:
    """The parts, and whatever the parts fail to account for.

    The residue is returned rather than swallowed. A breakdown that quietly
    absorbs a millisecond is worse than no breakdown, because it looks
    complete.
    """
    terms = [Term(name, before.get(key, 0.0), after.get(key, 0.0), note)
             for name, key, note in LATENCY_TERMS]
    total = sum(t.delta for t in terms)
    actual = after["Latency (ms)"] - before["Latency (ms)"]
    return terms, actual - total


def _pct(before: float, after: float) -> str:
    if before == 0:
        return "from zero"
    return f"{(after / before - 1) * 100:+.1f}%"


def _times(before: float, after: float) -> str:
    if before == 0 or after == 0:
        return ""
    r = after / before
    if r >= 2:
        return f"  ({r:.1f} times as much)"
    if r <= 0.5:
        return f"  ({1 / r:.1f} times less)"
    return ""


# ==============================================================================
# 1. WHAT CHANGED
# ==============================================================================

MEASURES = (
    ("Single-job latency", "Latency (ms)", "ms", True),
    ("Sensor-to-control", "Sensor-to-control (ms)", "ms", True),
    ("Pipeline capacity", "Pipeline capacity (inf/s)", "/s", False),
    ("Delivered throughput", "Delivered throughput (inf/s)", "/s", False),
    ("System power", "System power (W)", "W", True),
    ("Energy per job", "Energy per inference (mJ)", "mJ", True),
    ("System cost", "System cost (USD)", "USD", True),
)


def print_what_changed(before: Dict, after: Dict) -> List[str]:
    """Every measure by name. No single figure called 'performance'.

    There is no one performance number here. Single-job latency, pipeline
    capacity and delivered throughput are three different questions, and a
    change can move one, both or neither - so each is named and none is
    summarised.
    """
    print(f"  1. WHAT CHANGED")
    moved = []
    for label, key, unit, lower_better in MEASURES:
        if key not in before or key not in after:
            continue
        a, b = before[key], after[key]
        if a == b:
            print(f"     {label:<22s}{a:>10.2f} {unit:<4s} unchanged")
            continue
        moved.append(label)
        print(f"     {label:<22s}{a:>10.2f} -> {b:.2f} {unit}"
              f"   {_pct(a, b)}{_times(a, b)}")
    if not moved:
        print(f"     nothing measurable moved")
    return moved


# ==============================================================================
# 2. WHY
# ==============================================================================

def print_why(before: Dict, after: Dict, before_bound: str,
              after_bound: str) -> None:
    print(f"\n  2. WHY")
    terms, residue = latency_breakdown(before, after)
    actual = after["Latency (ms)"] - before["Latency (ms)"]

    if abs(actual) < 1e-9 and all(abs(t.delta) < 1e-9 for t in terms):
        print(f"     Nothing in the timing moved.")
    else:
        print(f"     Where the {abs(actual):.3f} ms "
              f"{'came from' if actual > 0 else 'went'}:\n")
        for t in terms:
            if abs(t.delta) < 5e-4:
                continue
            head = f"     {t.name:<24s}{t.delta:+9.3f} ms   "
            wrapped = _wrap(t.note, 78 - len(head))
            print(f"{head}{wrapped[0]}")
            for extra in wrapped[1:]:
                print(f"{' ' * len(head)}{extra}")
        print(f"     {'-' * 24}{'-' * 12}")
        print(f"     {'net':<24s}{actual:+9.3f} ms")
        if abs(residue) > 1e-6:
            print(f"     {'UNACCOUNTED':<24s}{residue:+9.3f} ms   "
                  f"the parts do not sum to the whole - this is a defect, "
                  f"not a rounding")

    if before_bound != after_bound:
        print(f"\n     The limit moved: {before_bound} -> {after_bound}")
        for b in (before_bound, after_bound):
            if b in BOTTLENECK_PLAIN:
                print(f"       {b:<16s}{BOTTLENECK_PLAIN[b]}")
    else:
        plain = BOTTLENECK_PLAIN.get(after_bound, "")
        text = (f"The limit did not move: still {after_bound}"
                + (f" - {plain}" if plain else ""))
        print()
        for line in _wrap(text, 70):
            print(f"     {line}")


def print_bottleneck_bars(metrics: Dict, label: str = "") -> None:
    """Where the time goes, drawn. Stations, not components.

    A number tells a student which station is largest. A bar tells them by
    how much, and 'by how much' is the difference between 'the host is the
    limit' and 'the host is nine tenths of the answer'.
    """
    total = metrics.get("Latency (ms)", 0.0)
    if total <= 0:
        return
    rows = [(name, metrics.get(key, 0.0))
            for name, key, _ in LATENCY_TERMS]
    rows = [(n, v) for n, v in rows if v > 0]
    if not rows:
        return
    if label:
        print(f"     {label}")
    from .visual import render_labelled_bars
    for line in render_labelled_bars(rows, total=total, label_width=22,
                                     width=34):
        print(f"       {line}")


# ==============================================================================
# 3. HOW SURE
# ==============================================================================

ROBUST = "ROBUST"
CONDITIONAL = "CONDITIONAL"
BOUNDARY = "BOUNDARY"

CONFIDENCE_MEANING = {
    ROBUST: "the direction holds across every value the assumptions could "
            "plausibly take",
    CONDITIONAL: "the direction reverses somewhere inside the assumed range, "
                 "but not near the value used",
    BOUNDARY: "the direction reverses CLOSE to the value used - this "
              "conclusion is a property of the assumption, not of the design",
}


def confidence(before: Dict, after: Dict, margin_fraction: float = 0.05
               ) -> Tuple[str, str]:
    """How much room the conclusion has.

    Not a sweep - that is what ppact.sensitivity does, and it is slower. This
    is the cheap version: how large is the change against the size of the
    things that could move it? A latency difference of a tenth of a per cent
    is inside the noise of any coefficient in the model and should not be
    reported as a finding.
    """
    a, b = before.get("Latency (ms)", 0.0), after.get("Latency (ms)", 0.0)
    if a == 0:
        return CONDITIONAL, "no baseline to compare against"
    change = abs(b / a - 1)
    if change < margin_fraction:
        return BOUNDARY, (
            f"the latency moved {change * 100:.1f}%, which is inside the "
            f"range a single coefficient could account for")
    if change < margin_fraction * 4:
        return CONDITIONAL, (
            f"the latency moved {change * 100:.1f}% - real, but small enough "
            f"that a different assumption could narrow it")
    return ROBUST, (
        f"the latency moved {change * 100:.1f}%, far outside what an "
        f"assumption could account for")


# ==============================================================================
# 4. WHAT TO DO
# ==============================================================================

def recommendations(before: Dict, after: Dict, after_bound: str,
                    after_passes: bool, failed_gates: List[str]) -> List[str]:
    """Advice derived from the numbers above it, never from a preference."""
    out = []
    lat_a, lat_b = before["Latency (ms)"], after["Latency (ms)"]
    cost_a, cost_b = before["System cost (USD)"], after["System cost (USD)"]
    pw_a, pw_b = before["System power (W)"], after["System power (W)"]

    faster = lat_b < lat_a * 0.99
    dearer = cost_b > cost_a * 1.01
    hungrier = pw_b > pw_a * 1.01

    if not after_passes:
        out.append(f"Do not adopt this change: it fails "
                   f"{', '.join(failed_gates)}.")
        if "memory_cooling" in failed_gates:
            out.append("The cooling failure is a class, not a quantity - "
                       "reducing power will not fix it.")
    elif faster and not dearer and not hungrier:
        out.append("Adopt this change: it is quicker and costs nothing "
                   "extra.")
    elif faster and dearer:
        ratio = (cost_b / cost_a - 1) / max(1e-9, 1 - lat_b / lat_a)
        out.append(f"Adopt only if the latency is worth the money: each "
                   f"1% of time costs {ratio:.1f}% of the bill.")
    elif not faster:
        out.append("Do not adopt this change for speed: it does not "
                   "deliver any.")

    # what to try instead, from where the time actually is
    host_share = after.get("CPU active (ms)", 0.0) / max(1e-9, lat_b)
    core_share = after.get("Delivered core time (ms)", 0.0) / max(1e-9, lat_b)
    if host_share > 0.5:
        out.append(f"The host is {host_share * 100:.0f}% of the remaining "
                   f"time. Upgrade it, or move the preparation off it, "
                   f"before touching the accelerator.")
    elif after_bound == "memory":
        out.append("The accelerator is waiting for data. A wider memory is "
                   "the lever here; a bigger engine is not.")
    elif after_bound == "compute" and core_share > 0.5:
        out.append("The accelerator is busy computing. A bigger engine is "
                   "the lever here; a wider memory is not.")
    return out


def upgrade_ranking(metrics: Dict, bound: str) -> List[Tuple[str, float, str]]:
    """Which part to spend on next, ordered by how much time it holds.

    The order is not an opinion: it is the share of one job's latency each
    station occupies. A part that is 3% of the time cannot give back more
    than 3%, however much is spent on it.
    """
    total = metrics.get("Latency (ms)", 0.0)
    if total <= 0:
        return []
    parts = [
        ("Host processor", metrics.get("CPU active (ms)", 0.0),
         "prepares every frame before the accelerator sees it"),
        ("Accelerator", metrics.get("Delivered core time (ms)", 0.0),
         "does the arithmetic"),
        ("Preprocessing path", metrics.get("Offload overhead (ms)", 0.0)
         + metrics.get("Preprocess exposed (ms)", 0.0),
         "moves preparation to another block and back"),
        ("Engine hand-off", metrics.get("Handoff (ms)", 0.0),
         "splits and merges work between two engines"),
    ]
    parts = [(n, v / total * 100, why) for n, v, why in parts if v > 0]
    return sorted(parts, key=lambda x: -x[1])


# ==============================================================================
# The whole thing
# ==============================================================================

def explain(app_key: str, before_cfg, after_cfg, title: str = "",
            with_ceilings: bool = True) -> Dict:
    """Measurement, cause, confidence, advice. In that order, every time."""
    from .application import APPLICATION_LIBRARY
    from .system import evaluate_system

    app = APPLICATION_LIBRARY[app_key]
    ra, rb = evaluate_system(app, before_cfg), evaluate_system(app, after_cfg)
    a, b = ra.metrics, rb.metrics
    failed = sorted(g for g, ok in rb.gate.items() if not ok)

    print(f"\n{LINE}")
    print(f" {title or 'WHAT THIS CHANGE DID'}")
    print(LINE)

    if "INFEASIBLE" in rb.status:
        print(f"  The model no longer fits in memory, so there is no timing")
        print(f"  to compare. Capacity is not a speed - a design that cannot")
        print(f"  hold its weights has no latency, fast or slow.")
        # The deployment verdict is still printed. "Can it ship?" has an
        # answer here and it is the most definite one on the page; leaving
        # it out because the timing is missing sends a reader looking for it
        # elsewhere, and there is nowhere else.
        print(f"\n  DEPLOYMENT STATUS   NOT READY")
        print(f"     Reason: does not meet {', '.join(failed) or 'capacity'}.")
        print(f"     The physical figures below are still computed - a board")
        print(f"     that cannot run its model still costs what it costs.")
        import math as _mth
        for m in ("System cost (USD)", "Total silicon (mm2)",
                  "Memory capacity (GB)"):
            if m in b and not _mth.isnan(b[m]):
                print(f"       {m:<26s}{b[m]:>10.2f}")
        print_handover()
        print(LINE)
        return {"feasible": False, "passes": False}

    print_what_changed(a, b)
    print_why(a, b, ra.bound_by, rb.bound_by)

    print(f"\n     Where the time goes now:")
    print_bottleneck_bars(b)

    conf, reason = confidence(a, b)
    print(f"\n  3. HOW SURE")
    print(f"     {conf}")
    for line in _wrap(reason + ".", 70):
        print(f"     {line}")
    for line in _wrap(CONFIDENCE_MEANING[conf], 68):
        print(f"     {line}")

    print(f"\n  4. WHAT TO DO")
    advice = recommendations(a, b, rb.bound_by, rb.passes, failed)
    for line in advice:
        for i, w in enumerate(_wrap(line, 68)):
            print(f"     {'- ' if i == 0 else '  '}{w}")

    print(f"\n     The most any one change could give back:")
    print_headroom(b)

    if with_ceilings:
        print(f"\n     And how close a real part actually gets:")
        print_ceilings(app_key, after_cfg)

    ranking = upgrade_ranking(b, rb.bound_by)
    if ranking:
        print(f"\n     Where to spend next, by how much time each holds:")
        for i, (name, share, why) in enumerate(ranking, 1):
            head = f"       {i}. {name:<20s}{share:5.1f}%   "
            wrapped = _wrap(why, 78 - len(head))
            print(f"{head}{wrapped[0]}")
            for extra in wrapped[1:]:
                print(f"{' ' * len(head)}{extra}")
        print(f"\n     A station that is {ranking[-1][1]:.1f}% of the time "
              f"cannot give back")
        print(f"     more than {ranking[-1][1]:.1f}%, however much is spent "
              f"on it.")

    print(f"\n  DEPLOYMENT STATUS   "
          f"{'READY' if rb.passes else 'NOT READY'}")
    if failed:
        print(f"     Reason: does not meet {', '.join(failed)}.")
        print(f"     'Not ready' means a requirement is unmet, not that the")
        print(f"     design is slow. A quick design that fails a cooling")
        print(f"     class is still not a product.")
    else:
        print(f"     Reason: every deployment constraint is satisfied -")
        print(f"     latency, throughput, power, cost, thermal, cooling")
        print(f"     class and capacity.")
    # Descriptive, and said so. A reader who selected PCIe should see that
    # the Studio noticed, and should not be able to conclude it was used.
    from .arch_classes import print_host_connection, HOST_CONNECTION_KEYS
    hc = getattr(after_cfg, "host_connection", "on_board")
    if hc in HOST_CONNECTION_KEYS:
        print()
        print_host_connection(hc, "  ")

    print_handover()
    print(LINE)
    return {"feasible": True, "confidence": conf, "advice": advice,
            "ranking": ranking, "passes": rb.passes}


# The tool supplies facts. The designer decides. That distinction is printed
# rather than assumed, because a student who watches a program produce a
# verdict learns that programs produce verdicts - and the ones they will use
# later do, confidently and wrongly.
DECISION_HANDOVER = (
    "Everything above is measured or derived from a measurement. What none "
    "of it contains is what the latency is worth, what the schedule allows, "
    "what a competitor is shipping, or what the customer will pay. Those "
    "decide the answer as much as the numbers do, and this tool does not "
    "know any of them.",
    "The facts are the tool's. The decision is the designer's.",
)


def print_handover(indent: str = "  ") -> None:
    print(f"\n{indent}DECISION")
    for para in DECISION_HANDOVER:
        for line in _wrap(para, 70):
            print(f"{indent}   {line}")
        print()


def _wrap(text: str, width: int) -> List[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return lines


def report_markdown(app_key: str, before_cfg, after_cfg) -> str:
    """The same content as a file someone can put in a document."""
    from .application import APPLICATION_LIBRARY
    from .system import evaluate_system

    app = APPLICATION_LIBRARY[app_key]
    ra, rb = evaluate_system(app, before_cfg), evaluate_system(app, after_cfg)
    a, b = ra.metrics, rb.metrics
    conf, reason = confidence(a, b)
    failed = sorted(g for g, ok in rb.gate.items() if not ok)
    terms, residue = latency_breakdown(a, b)

    out = [f"# Design change: {app.name}", ""]
    out.append("## What changed")
    out.append("")
    out.append("| measure | before | after | change |")
    out.append("|---|---|---|---|")
    for label, key, unit, _ in MEASURES:
        if key in a and key in b:
            out.append(f"| {label} | {a[key]:.2f} {unit} | {b[key]:.2f} "
                       f"{unit} | {_pct(a[key], b[key])} |")
    out += ["", "## Why", "", "| part | change |", "|---|---|"]
    for t in terms:
        if abs(t.delta) >= 5e-4:
            out.append(f"| {t.name} | {t.delta:+.3f} ms |")
    out.append(f"| **net** | **{b['Latency (ms)'] - a['Latency (ms)']:+.3f} "
               f"ms** |")
    if abs(residue) > 1e-6:
        out.append(f"| UNACCOUNTED | {residue:+.3f} ms |")
    out += ["", f"Limit before: {ra.bound_by}. Limit after: {rb.bound_by}.",
            "", "## How sure", "", f"**{conf}** - {reason}.", "",
            CONFIDENCE_MEANING[conf], "", "## What to do", ""]
    for line in recommendations(a, b, rb.bound_by, rb.passes, failed):
        out.append(f"- {line}")
    out += ["", f"**Deployment status:** "
                f"{'ready' if rb.passes else 'NOT READY'}"]
    if failed:
        out.append(f"Unmet requirements: {', '.join(failed)}.")
    out += ["", "---", "",
            "Produced by PPACT Studio. Every figure above is computed; the "
            "recommendation is derived from those figures and from nothing "
            "else."]
    return "\n".join(out)


# ==============================================================================
# The upper bound: what a station could give back if it were free
# ==============================================================================
#
# "Upgrade the host" is advice. "The host owns 84.7% of one job, so even an
# infinitely fast accelerator saves at most 14.9%" is a LIMIT, and a limit is
# the more useful of the two: it survives every choice of part, every price
# and every generation, because it follows from where the time is rather than
# from what is for sale.
#
# This is Amdahl's argument applied to one job. It is exact here because the
# decomposition is exact - each station's share IS the most removing it
# entirely could return.

@dataclass
class Headroom:
    station: str
    share_pct: float
    best_latency: float
    best_gain_pct: float
    note: str


def headroom(metrics: Dict) -> List[Headroom]:
    """The most each station could give back, if it took no time at all."""
    total = metrics.get("Latency (ms)", 0.0)
    if total <= 0:
        return []
    out = []
    for name, key, note in LATENCY_TERMS:
        v = metrics.get(key, 0.0)
        if v <= 0:
            continue
        out.append(Headroom(name, v / total * 100, total - v,
                            -v / total * 100, note))
    return sorted(out, key=lambda h: h.share_pct, reverse=True)


def print_headroom(metrics: Dict) -> List[Headroom]:
    rows = headroom(metrics)
    if not rows:
        return rows
    total = metrics["Latency (ms)"]
    print(f"     If a station took NO time at all, one job would take:")
    print(f"       {'station':<24s}{'share':>8s}{'best case':>12s}"
          f"{'most it could give':>20s}")
    for h in rows:
        print(f"       {h.station:<24s}{h.share_pct:>7.1f}%"
              f"{h.best_latency:>11.2f} ms{h.best_gain_pct:>19.1f}%")
    top = rows[0]
    rest = 100 - top.share_pct
    print(f"\n     Everything except {top.station} adds up to "
          f"{rest:.1f}% of the time,")
    print(f"     so no change to any of it can save more than that. This is")
    print(f"     a limit, not an estimate: it holds for any part at any "
          f"price.")
    return rows


# ==============================================================================
# What a proposal would actually do, and what the alternative would
# ==============================================================================

@dataclass
class Option:
    label: str
    change: Dict
    latency: float
    gain_pct: float
    cost: float
    cost_delta: float
    passes: bool
    failed: List[str]
    feasible: bool


def try_options(app_key: str, base_cfg, options: Dict[str, Dict]
                ) -> List[Option]:
    """Run each proposal. Measured, never estimated.

    An 'expected benefit' worked out from a share would be a guess dressed
    as a figure. Each option is built and evaluated, so the number quoted is
    the number the design produces.
    """
    import dataclasses as _dc
    from .application import APPLICATION_LIBRARY
    from .system import evaluate_system

    app = APPLICATION_LIBRARY[app_key]
    base = evaluate_system(app, base_cfg)
    b_lat = base.metrics["Latency (ms)"]
    b_cost = base.metrics["System cost (USD)"]

    out = []
    for label, change in options.items():
        try:
            r = evaluate_system(app, _dc.replace(base_cfg, **change))
        except Exception:
            continue
        if "INFEASIBLE" in r.status:
            out.append(Option(label, change, float("nan"), float("nan"),
                              float("nan"), float("nan"), False,
                              ["capacity"], False))
            continue
        lat = r.metrics["Latency (ms)"]
        cost = r.metrics["System cost (USD)"]
        out.append(Option(label, change, lat, (1 - lat / b_lat) * 100, cost,
                          cost - b_cost, r.passes,
                          sorted(g for g, ok in r.gate.items() if not ok),
                          True))
    return sorted(out, key=lambda o: (not o.feasible, -o.gain_pct))


def print_options(app_key: str, base_cfg, options: Dict[str, Dict]
                  ) -> List[Option]:
    rows = try_options(app_key, base_cfg, options)
    if not rows:
        return rows
    width = 30
    print(f"       {'proposal':<{width}s}{'latency':>9s}{'gain':>8s}"
          f"{'cost':>9s}{'deploy':>8s}")
    for o in rows:
        label = o.label if len(o.label) <= width - 1 else o.label[:width - 2] + "."
        if not o.feasible:
            print(f"       {label:<{width}s}{'does not fit':>34s}")
            continue
        print(f"       {label:<{width}s}{o.latency:>9.2f}{o.gain_pct:>7.1f}%"
              f"{o.cost_delta:>+9.2f}{('yes' if o.passes else 'no'):>8s}")
    return rows


# ==============================================================================
# Confidence, with the evidence behind it
# ==============================================================================

def confidence_evidence(app_key: str, before_cfg, after_cfg,
                        points: int = 9) -> Dict:
    """Move the coefficients and see whether the DIRECTION survives.

    The cheap confidence() grades by how large the change is. This is the
    expensive one: it actually moves the assumptions and counts how often the
    conclusion reverses. A student who is told ROBUST deserves to know what
    was tried.
    """
    import dataclasses as _dc
    import ppact.system as S
    import ppact.preprocess as pp
    from .application import APPLICATION_LIBRARY
    from .system import evaluate_system

    app = APPLICATION_LIBRARY[app_key]
    knobs = [
        ("host memory overlap", S, "HOST_MEMORY_OVERLAP", 0.4, 0.95),
        ("host locality exposure", S, "HOST_LOCALITY_EXPOSURE", 0.3, 1.0),
        ("split efficiency", S, "PARALLEL_SPLIT_EFFICIENCY", 0.6, 1.0),
        ("dual memory contention", S, "DUAL_MEMORY_CONTENTION", 0.0, 0.4),
        ("hand-off cost (us)", S, "DUAL_DISPATCH_US", 0.0, 400.0),
        ("offload dispatch (us)", pp, "NPU_PREPROCESS_DISPATCH_US", 0.0,
         600.0),
    ]

    base_a = evaluate_system(app, before_cfg).metrics["Latency (ms)"]
    base_b = evaluate_system(app, after_cfg).metrics["Latency (ms)"]
    baseline_sign = 1 if base_b > base_a else (-1 if base_b < base_a else 0)

    runs, flips, flipped_by = 0, 0, []
    for name, mod, attr, lo, hi in knobs:
        if not hasattr(mod, attr):
            continue
        saved = getattr(mod, attr)
        try:
            for i in range(points):
                v = lo + (hi - lo) * i / (points - 1)
                setattr(mod, attr, v)
                a = evaluate_system(app, before_cfg).metrics["Latency (ms)"]
                b = evaluate_system(app, after_cfg).metrics["Latency (ms)"]
                sign = 1 if b > a else (-1 if b < a else 0)
                runs += 1
                if sign != baseline_sign:
                    flips += 1
                    if name not in flipped_by:
                        flipped_by.append(name)
        finally:
            setattr(mod, attr, saved)

    if runs == 0:
        return {"runs": 0, "flips": 0, "grade": CONDITIONAL,
                "flipped_by": [], "stars": 0}
    rate = flips / runs
    if rate == 0:
        grade, stars = ROBUST, 5
    elif rate < 0.1:
        grade, stars = ROBUST, 4
    elif rate < 0.35:
        grade, stars = CONDITIONAL, 3
    elif rate < 0.6:
        grade, stars = CONDITIONAL, 2
    else:
        grade, stars = BOUNDARY, 1
    return {"runs": runs, "flips": flips, "grade": grade, "stars": stars,
            "flipped_by": flipped_by, "knobs": len(knobs)}


def print_confidence_evidence(ev: Dict) -> None:
    """A count, not a rating.

    Stars invite comparison with things that have nothing to do with this -
    a five-star grade reads like a review. The count says what was done and
    what happened, and a reader can decide what it is worth.
    """
    held = ev["runs"] - ev["flips"]
    print(f"     Decision robustness   {held} / {ev['runs']}")
    print(f"     {ev['runs']} runs across {ev.get('knobs', 0)} assumptions; "
          f"the direction reversed in {ev['flips']}.")
    print(f"     Grade: {ev['grade']}")
    if ev["flipped_by"]:
        print(f"     Reversed by: {', '.join(ev['flipped_by'])}.")
        print(f"     That conclusion is a property of those assumptions as")
        print(f"     much as of the design.")
    else:
        print(f"     No assumption in the ranges tried reverses it. That is")
        print(f"     what makes this a finding about the DESIGN rather than")
        print(f"     about a coefficient.")


# ==============================================================================
# Design review: a proposal, and a reviewer's answer
# ==============================================================================

def design_review(app_key: str, base_cfg, proposal_label: str,
                  proposal: Dict, alternatives: Optional[Dict] = None
                  ) -> Dict:
    """The student proposes; the Studio reviews. Reasons first, verdict last."""
    import dataclasses as _dc
    from .application import APPLICATION_LIBRARY
    from .system import evaluate_system

    app = APPLICATION_LIBRARY[app_key]
    after_cfg = _dc.replace(base_cfg, **proposal)
    ra = evaluate_system(app, base_cfg)
    rb = evaluate_system(app, after_cfg)
    a, b = ra.metrics, rb.metrics

    print(f"\n{LINE}")
    print(f" DESIGN REVIEW - {app.name}")
    print(LINE)
    print(f"  Your proposal:  {proposal_label}")
    print(f"                  {', '.join(f'{k}={v}' for k, v in proposal.items())}")

    if "INFEASIBLE" in rb.status:
        print(f"\n  REASON 1  the model no longer fits in memory")
        print(f"\n  VERDICT   reject - a design that cannot hold its weights")
        print(f"            has no speed to discuss")
        print(LINE)
        return {"accepted": False}

    reasons = []
    lat_gain = (1 - b["Latency (ms)"] / a["Latency (ms)"]) * 100
    cost_delta = b["System cost (USD)"] - a["System cost (USD)"]
    failed = sorted(g for g, ok in rb.gate.items() if not ok)

    reasons.append(f"the limit before the change was {ra.bound_by} - "
                   f"{BOTTLENECK_PLAIN.get(ra.bound_by, '')}")
    reasons.append(f"single-job latency {a['Latency (ms)']:.2f} -> "
                   f"{b['Latency (ms)']:.2f} ms ({lat_gain:+.1f}%)")
    reasons.append(f"system cost {a['System cost (USD)']:.2f} -> "
                   f"{b['System cost (USD)']:.2f} USD "
                   f"({cost_delta:+.2f})")
    if failed:
        reasons.append(f"the result does not meet {', '.join(failed)}")
        if "memory_cooling" in failed:
            reasons.append("the cooling failure is a class rather than a "
                           "quantity, so no reduction elsewhere fixes it")

    hr = headroom(a)
    if hr:
        top = hr[0]
        reasons.append(f"{top.station} holds {top.share_pct:.1f}% of one "
                       f"job, so everything else together cannot save more "
                       f"than {100 - top.share_pct:.1f}%")

    print(f"\n  WHY:")
    for i, r in enumerate(reasons, 1):
        wrapped = _wrap(r, 62)
        print(f"    REASON {i}  {wrapped[0]}")
        for extra in wrapped[1:]:
            print(f"              {extra}")

    if alternatives:
        print(f"\n  WHAT ELSE WAS TRIED:")
        print_options(app_key, base_cfg,
                      {proposal_label: proposal, **alternatives})

    accepted = rb.passes and lat_gain > 1.0 and cost_delta <= 0
    marginal = rb.passes and lat_gain > 1.0
    print(f"\n  VERDICT")
    if not rb.passes:
        print(f"    Reject. It does not meet {', '.join(failed)}, and a")
        print(f"    design that cannot ship has no performance to weigh.")
    elif lat_gain <= 1.0:
        print(f"    Reject on these grounds. The latency moved "
              f"{lat_gain:+.1f}%,")
        print(f"    which is not worth {cost_delta:+.2f} USD.")
    elif cost_delta > 0:
        rate = lat_gain / cost_delta
        print(f"    NO FREE IMPROVEMENT")
        print(f"      Gain      {lat_gain:.1f}% of single-job latency")
        print(f"      Cost      {cost_delta:+.2f} USD per unit")
        print(f"      Rate      {rate:.2f}% per USD")
        print(f"      Decision  engineering trade-off - somebody has to")
        print(f"                decide the exchange rate, and this tool")
        print(f"                cannot: it does not know what the latency")
        print(f"                is worth to the customer.")
    else:
        print(f"    ACCEPT")
        print(f"      Gain      {lat_gain:.1f}% of single-job latency")
        print(f"      Cost      {cost_delta:+.2f} USD per unit")
        print(f"      Decision  no trade to make - it is quicker and no "
              f"dearer.")
    print_handover("  ")
    print(LINE)
    return {"accepted": accepted, "marginal": marginal,
            "reasons": reasons, "gain_pct": lat_gain,
            "cost_delta": cost_delta, "passes": rb.passes}


# ==============================================================================
# The bound, and how close anything actually gets to it
# ==============================================================================
#
# A bound on its own teaches half the lesson. "The accelerator can give back
# at most 14.9%" is the limit; "and the best engine in the library gives 11.8%"
# is the reality, and the gap between them is where engineering lives.
#
# The two are computed differently and must not be confused:
#
#   BOUND     arithmetic. Remove a station's time entirely and see what is
#             left. It cannot be beaten and it cannot be reached.
#   MEASURED  a search. Build every part the library offers and run it. It
#             can be beaten tomorrow by a part nobody has made yet.
#
# So the bound is reported as a limit and the measured figure as a best-so-far,
# and the ratio between them is labelled for what it is: how much of the
# available headroom real parts manage to collect.

UNLIMITED_LEVERS = {
    "host processor": ("cpu", ["cortex_a53_x4", "cortex_a78_x4",
                               "server_x86_x32"], "host active"),
    "accelerator": ("compute", ["npu_16x16", "npu_24x24", "npu_32x32",
                                "npu_64x64", "npu_128x128", "npu_160x160",
                                "datacenter_gpu"], "accelerator core"),
    "preprocessing path": ("preprocessing_mode",
                           ["cpu_only", "isp_assisted", "isp_and_npu"],
                           "host active"),
}

# Memory is deliberately absent from the bound table. It is not a station in
# the latency decomposition - its time sits inside the accelerator's core
# figure as data-wait - so there is no "if memory took no time" row to
# compute. Claiming one would be inventing a limit, and the whole value of a
# limit is that it was not invented.
NO_BOUND_LEVERS = {
    "memory": ("memory", ["LPDDR5", "GDDR6", "HBM3E"],
               "memory time is inside the accelerator's core figure as "
               "data-wait, so there is no station to remove"),
}


@dataclass
class Ceiling:
    lever: str
    bound_gain_pct: Optional[float]   # None where no bound can be computed
    bound_latency: Optional[float]
    best_gain_pct: float
    best_latency: float
    best_choice: str
    efficiency_pct: Optional[float]     # ACHIEVABILITY: how much of the
                                        # limit real parts collect
    note: str

    @property
    def gap_pct(self) -> Optional[float]:
        """What the limit offers and nothing on the market delivers.

        Limit minus best real. This is the RESEARCH VALUE of a station: a
        large gap says the physics allows something nobody has built, and a
        small one says the available parts have very nearly finished the job.
        A student reading it learns where effort is still worth spending,
        which is a different question from where money is.
        """
        if self.bound_gain_pct is None:
            return None
        return self.bound_gain_pct - self.best_gain_pct


def ceilings(app_key: str, base_cfg) -> List[Ceiling]:
    """For each lever: the limit, the best a real part reaches, and the gap."""
    import dataclasses as _dc
    from .application import APPLICATION_LIBRARY
    from .system import evaluate_system

    app = APPLICATION_LIBRARY[app_key]
    base = evaluate_system(app, base_cfg).metrics
    total = base["Latency (ms)"]
    station_time = {name: base.get(key, 0.0)
                    for name, key, _ in LATENCY_TERMS}

    out = []
    for lever, (field, choices, station) in UNLIMITED_LEVERS.items():
        bound_lat = total - station_time.get(station, 0.0)
        bound_gain = (1 - bound_lat / total) * 100 if total else 0.0
        best_lat, best_choice = total, "unchanged"
        for c in choices:
            try:
                r = evaluate_system(app, _dc.replace(base_cfg, **{field: c}))
            except Exception:
                continue
            if "INFEASIBLE" in r.status:
                continue
            if r.metrics["Latency (ms)"] < best_lat:
                best_lat, best_choice = r.metrics["Latency (ms)"], c
        best_gain = (1 - best_lat / total) * 100 if total else 0.0
        eff = (best_gain / bound_gain * 100) if bound_gain > 1e-9 else None
        out.append(Ceiling(lever, bound_gain, bound_lat, best_gain, best_lat,
                           best_choice, eff, ""))

    for lever, (field, choices, why) in NO_BOUND_LEVERS.items():
        best_lat, best_choice = total, "unchanged"
        for c in choices:
            try:
                r = evaluate_system(app, _dc.replace(base_cfg, **{field: c}))
            except Exception:
                continue
            if "INFEASIBLE" in r.status:
                continue
            if r.metrics["Latency (ms)"] < best_lat:
                best_lat, best_choice = r.metrics["Latency (ms)"], c
        best_gain = (1 - best_lat / total) * 100 if total else 0.0
        out.append(Ceiling(lever, None, None, best_gain, best_lat,
                           best_choice, None, why))

    return sorted(out, key=lambda c: -c.best_gain_pct)


def print_ceilings(app_key: str, base_cfg) -> List[Ceiling]:
    rows = ceilings(app_key, base_cfg)
    print(f"     {'lever':<20s}{'limit':>8s}{'best real':>11s}"
          f"{'gap':>8s}{'achievable':>12s}")
    for c in rows:
        lim = f"{c.bound_gain_pct:.1f}%" if c.bound_gain_pct is not None \
            else "none"
        gap = f"{c.gap_pct:.1f}%" if c.gap_pct is not None else "-"
        eff = f"{c.efficiency_pct:.0f}%" if c.efficiency_pct is not None \
            else "-"
        print(f"     {c.lever:<20s}{lim:>8s}{c.best_gain_pct:>10.1f}%"
              f"{gap:>8s}{eff:>12s}")
    print()
    print(f"     limit        what one job would take if that station took NO")
    print(f"                  time at all - arithmetic, not a forecast")
    print(f"     best real    the quickest part in the library, measured")
    print(f"     gap          what the limit offers and nothing on the market")
    print(f"                  delivers - the RESEARCH value of that station")
    print(f"     achievable   how much of the limit real parts collect")
    biggest = max((c for c in rows if c.gap_pct is not None),
                  key=lambda c: c.gap_pct, default=None)
    if biggest is not None:
        print(f"\n     The largest gap is {biggest.lever} at "
              f"{biggest.gap_pct:.1f}%. The physics allows")
        print(f"     something nobody has built there. A small gap would mean")
        print(f"     the opposite: the available parts have nearly finished")
        print(f"     the job, and effort is better spent elsewhere.")
    for c in rows:
        if c.note:
            print()
            for line in _wrap(f"No limit is shown for {c.lever}: {c.note}.",
                              66):
                print(f"     {line}")
            print(f"     A limit that was invented would be worth nothing,")
            print(f"     and the value of a limit is that it was not.")
    return rows


# ==============================================================================
# What a gain costs
# ==============================================================================

def cost_effectiveness(options: List["Option"]) -> List[Tuple[str, float,
                                                              float, float]]:
    """Latency per cent, per dollar. The rate, not the total.

    A student without a sense of what a chip costs cannot weigh 14% against
    ninety-four dollars. A rate makes the comparison arithmetic instead of
    intuition - and the arithmetic is brutal: two designs an order of
    magnitude apart look similar until it is divided out.
    """
    out = []
    for o in options:
        if not o.feasible or o.gain_pct <= 0:
            continue
        if o.cost_delta <= 0:
            out.append((o.label, o.gain_pct, o.cost_delta, float("inf")))
        else:
            out.append((o.label, o.gain_pct, o.cost_delta,
                        o.gain_pct / o.cost_delta))
    return sorted(out, key=lambda x: -x[3])


def print_cost_effectiveness(options: List["Option"]) -> None:
    rows = cost_effectiveness(options)
    if not rows:
        print(f"     Nothing on this list makes the design quicker.")
        return
    print(f"     {'proposal':<30s}{'gain':>8s}{'cost':>10s}"
          f"{'gain per USD':>15s}")
    for label, gain, cost, rate in rows:
        r = "free" if rate == float("inf") else f"{rate:.2f}%"
        short = label if len(label) <= 29 else label[:28] + "."
        print(f"     {short:<30s}{gain:>7.1f}%{cost:>+10.2f}{r:>15s}")
    if len(rows) >= 2 and rows[0][3] != float("inf") and rows[-1][3] > 0:
        ratio = rows[0][3] / rows[-1][3]
        print(f"\n     The best rate is {ratio:.0f} times the worst. Both are")
        print(f"     improvements; they are not comparable purchases.")
    elif rows[0][3] == float("inf"):
        print(f"\n     The first costs nothing, so it has no rate - it is not")
        print(f"     a purchase, it is a different way of arranging the same")
        print(f"     parts.")


# ==============================================================================
# What-if: change one thing, see everything, change it back
# ==============================================================================
#
# A slider is a way of asking "and if it were a bit more?" without paying for
# the question. On a console the same thing is a loop: pick a knob, pick a
# value, and every figure is recomputed and shown beside where it started.
#
# The point is not convenience. A student who can undo a change explores; one
# who cannot, commits early and defends. So the baseline is never lost, every
# screen shows the distance from it, and there is always a way back.

WHATIF_KNOBS = {
    "host processor": ("cpu", ["cortex_a53_x4", "cortex_a78_x4",
                               "server_x86_x32"]),
    "accelerator": ("compute", ["npu_16x16", "npu_20x20", "npu_24x24",
                                "npu_32x32", "npu_64x64", "npu_128x128"]),
    "second accelerator": ("secondary_compute", [None, "npu_16x16",
                                                 "npu_32x32", "npu_64x64"]),
    "memory": ("memory", ["LPDDR5", "GDDR6", "HBM3E"]),
    "memory devices": ("memory_devices", [1, 2, 4, 8]),
    "preprocessing": ("preprocessing_mode", ["cpu_only", "isp_assisted",
                                             "isp_and_npu"]),
    "process node": ("accel_node", ["N28", "N16", "N7", "N3"]),
}

WHATIF_WATCH = (
    ("Single-job latency", "Latency (ms)", "ms", True),
    ("Pipeline capacity", "Pipeline capacity (inf/s)", "/s", False),
    ("Delivered throughput", "Delivered throughput (inf/s)", "/s", False),
    ("System power", "System power (W)", "W", True),
    ("System cost", "System cost (USD)", "USD", True),
)


def whatif_row(app_key: str, base_cfg, cfg) -> Dict:
    from .application import APPLICATION_LIBRARY
    from .system import evaluate_system

    app = APPLICATION_LIBRARY[app_key]
    base = evaluate_system(app, base_cfg)
    now = evaluate_system(app, cfg)
    return {"base": base, "now": now,
            "feasible": "INFEASIBLE" not in now.status}


def print_whatif(app_key: str, base_cfg, cfg, changed: Dict) -> None:
    r = whatif_row(app_key, base_cfg, cfg)
    a, b = r["base"].metrics, r["now"].metrics

    print(f"\n{RULE}")
    if changed:
        print(f"  Changed from the starting design:")
        for k, v in changed.items():
            print(f"     {k:<24s}{v}")
    else:
        print(f"  Unchanged from the starting design.")
    print()

    if not r["feasible"]:
        print(f"  The model no longer fits in memory. There is no timing to")
        print(f"  show - a design that cannot hold its weights has no speed.")
        return

    print(f"     {'':<22s}{'start':>12s}{'now':>12s}{'change':>11s}")
    for label, key, unit, lower_better in WHATIF_WATCH:
        if key not in a:
            continue
        chg = "-" if a[key] == 0 else f"{(b[key] / a[key] - 1) * 100:+.1f}%"
        if a[key] == b[key]:
            chg = "same"
        print(f"     {label:<22s}{a[key]:>12.2f}{b[key]:>12.2f}{chg:>11s}")

    print(f"\n     limited by            {r['base'].bound_by:>12s}"
          f"{r['now'].bound_by:>12s}")
    failed = sorted(g for g, ok in r["now"].gate.items() if not ok)
    print(f"     deployment            "
          f"{('ready' if r['base'].passes else 'not ready'):>12s}"
          f"{('ready' if r['now'].passes else 'not ready'):>12s}")
    if failed:
        print(f"     unmet: {', '.join(failed)}")

    # MEASURED RESULTS, from the SAME readings the standard review uses.
    #
    # This screen showed a change table and nothing else: no bars, no
    # requirement line, no margin band. "System cost +3.5%" says how far a
    # value moved and not how far it is from failing, and What-if is the
    # one screen where that is the question - a change looks harmless at
    # 3% of a budget and is a different matter at 98%.
    #
    # Section 4 only. The full nine-section review belongs at the END of an
    # analysis; this is an intermediate screen a user returns to after
    # every change, and repeating all of it would bury the comparison it
    # exists to show.
    from .review import build_review
    from .visual import (render_measured_bars, measured_bars_legend,
                         margin_legend)
    try:
        analysis = build_review("what_if", app_key, cfg, base_cfg)
    except Exception:
        analysis = None
    if analysis is not None:
        print()
        print(f"  MEASURED RESULTS")
        print()
        for line in render_measured_bars(analysis.measured):
            print(f"     {line}" if line.strip() else "")
        print(f"     {measured_bars_legend()}")
        print(f"     {margin_legend()}")


def whatif(app_key: str, base_cfg, ask_fn):
    """Change one thing at a time, and always be able to change it back.

    RETURNS WHAT IT ENDED WITH.

    It used to return None on Done, so a caller could not tell a
    comparison from an abandoned one and reported IN_PROGRESS for a
    workflow the user had finished. Three exits, each named:

        Done with changes     the base and the modified design
        Done with no change   nothing to compare - the user left
        anything else         still running
    """
    import dataclasses as _dc

    cfg = base_cfg
    changed: Dict = {}
    names = list(WHATIF_KNOBS)

    print(f"\n{LINE}")
    print(f" WHAT IF")
    print(LINE)
    print(f"  Change one thing and every figure is recomputed against where")
    print(f"  you started. Nothing is committed - the starting design is")
    print(f"  always there, and you can put anything back.")

    while True:
        print_whatif(app_key, base_cfg, cfg, changed)
        print()
        pick = ask_fn("Change what", names + ["Put everything back",
                                              "Explain what I have now",
                                              "Done"], len(names) + 3)
        if pick == len(names) + 3:
            # DONE. Which kind of Done depends on whether anything
            # changed, and saying so is the point of returning at all.
            if changed:
                return {"base": base_cfg, "now": cfg,
                        "changed": dict(changed)}
            return {"base": base_cfg, "now": None, "changed": {}}
        if pick == len(names) + 1:
            cfg, changed = base_cfg, {}
            continue
        if pick == len(names) + 2:
            if changed:
                explain(app_key, base_cfg, cfg,
                        title="WHAT YOUR CHANGES DID", with_ceilings=False)
            else:
                print(f"\n  Nothing has been changed yet.")
            continue

        name = names[pick - 1]
        field, options = WHATIF_KNOBS[name]
        current = getattr(cfg, field, None)

        # Through the registry. This printed str(o) for every option, so a
        # memory question offered "1  2  4  8" and a process node offered
        # "N28  N16  N7  N3" - bare values under a bare field name, in the
        # one screen whose whole purpose is trying a change and seeing what
        # it does.
        #
        # It survived four rounds of prompt migration because Q9 watched
        # game.py, menu.py, challenge.py and lessons.py, and decide.py was
        # not on the list.
        from .questions import field_question, ask_question
        value = ask_question(field_question(field, options, current))
        if value == "__keep__":
            continue
        extra = {field: value}
        # a second accelerator needs to be told how to work, or it is a die
        # that does nothing - and reporting that as a result would be wrong.
        if field == "secondary_compute":
            if value is None:
                extra.update(execution_mode="single", work_split=0.0)
            else:
                extra.update(execution_mode="parallel", work_split=0.5)
        try:
            cfg = _dc.replace(cfg, **extra)
        except Exception as exc:
            print(f"\n  That combination cannot be built: {exc}")
            continue
        if value == getattr(base_cfg, field, None):
            changed.pop(name, None)
        else:
            changed[name] = "none" if value is None else value
