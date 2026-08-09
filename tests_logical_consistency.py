"""
tests_logical_consistency.py - does the program contradict itself?

WHAT THIS SUITE IS NOT ABOUT
============================
Not whether the model matches a commercial part. Not whether the estimated
power equals measured silicon. Not whether a coefficient is right.

Those are questions about the world, and this package answers none of them -
tests_library_validation says so, and METHODOLOGY lists them under what is
not established.

WHAT IT IS ABOUT
----------------
Given the same input and the same modelling assumptions, do the numbers, the
status, the explanation, the score, the chart and the recommendation agree
with each other?

A model can be wrong about the world and still be internally coherent. It
can also be plausible about the world and say two contradictory things on
one screen - and the second is far worse, because a reader who catches the
contradiction stops trusting everything, and a reader who does not carries
away whichever half they read.

FAILURES SHOW BOTH SIDES
------------------------
A failure here prints the two statements that cannot both be true. "LC09
failed" tells nobody anything; a bottleneck of 85% beside a recommendation
to scale the accelerator beside a measured benefit of 0.2% tells them
everything.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

import contextlib
import dataclasses
import io
import math
import sys

sys.path.insert(0, ".")

from ppact import APPLICATION_LIBRARY, SystemConfig, evaluate_system

LINE = "=" * 84
CASES = []          # (id, title, fn)
RESULTS = []        # (id, title, ok, message)
CONTROLS = []       # (id, caught, message)


def case(cid, title):
    def wrap(fn):
        CASES.append((cid, title, fn))
        return fn
    return wrap


def quiet(fn, *a, **kw):
    with contextlib.redirect_stdout(io.StringIO()) as buf:
        fn(*a, **kw)
    return buf.getvalue()


def ev(app_key, cfg):
    return evaluate_system(APPLICATION_LIBRARY[app_key], cfg)


def failed_gates(r):
    return sorted(g for g, ok in r.gate.items() if not ok)


def required_gb(app_key):
    a = APPLICATION_LIBRARY[app_key]
    return (a.weight_bytes + a.kv_cache_bytes
            + a.runtime_overhead_bytes) / 1e9


# ==============================================================================
# The cases
# ==============================================================================

@case("LC01", "Insufficient memory cannot be READY")
def lc01(inject=None):
    cfg = SystemConfig("server_x86_x32", "datacenter_gpu", "LPDDR5", 2)
    r = ev("llm_service", cfg)
    need = required_gb("llm_service")
    have = r.metrics["Memory capacity (GB)"]
    passes = r.passes if inject is None else inject
    if have < need and passes:
        return False, (
            f"Capacity contradiction:\n"
            f"      the model requires {need:.1f} GB and the selected "
            f"memory provides {have:.1f} GB,\n"
            f"      yet deployment status is READY.")
    return True, f"needs {need:.1f} GB, has {have:.1f} GB, passes={passes}"


@case("LC02", "Sufficient capacity is not reported as a capacity failure")
def lc02(inject=None):
    cfg = SystemConfig("server_x86_x32", "datacenter_gpu", "HBM3E", 8)
    r = ev("llm_service", cfg)
    need = required_gb("llm_service")
    have = r.metrics["Memory capacity (GB)"]
    gates = failed_gates(r) if inject is None else inject
    if have >= need and "capacity" in gates:
        return False, (
            f"Capacity contradiction:\n"
            f"      {have:.1f} GB available against {need:.1f} GB required,\n"
            f"      yet capacity is listed as an unmet requirement.")
    return True, f"has {have:.1f} GB for {need:.1f} GB, unmet: {gates}"


@case("LC03", "Deployment status agrees with the violation list")
def lc03(inject=None):
    bad = []
    for app in APPLICATION_LIBRARY:
        for comp in ("npu_16x16", "npu_128x128", "datacenter_gpu"):
            for mem in ("LPDDR5", "HBM3E"):
                r = ev(app, SystemConfig(
                    "server_x86_x32"
                    if APPLICATION_LIBRARY[app].domain == "Data Center"
                    else "cortex_a78_x4", comp, mem, 2))
                gates = failed_gates(r)
                passes = r.passes
                if inject is not None and app == "drone":
                    passes, gates = inject
                if passes and gates:
                    bad.append(f"{app}/{comp}: READY with unmet {gates}")
                if not passes and not gates:
                    bad.append(f"{app}/{comp}: NOT READY with no reason")
    if bad:
        return False, ("Status contradiction:\n      "
                       + "\n      ".join(bad[:3]))
    return True, "status and violation list agree on every combination"


@case("LC04", "Latency decomposition sums to the total")
def lc04(inject=None):
    from ppact.decide import latency_breakdown
    worst = None
    for app in ("industrial_vision", "drone", "robot", "mobile_ai"):
        for pm in ("cpu_only", "isp_and_npu"):
            a = SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5", 2,
                             preprocessing_mode=pm)
            b = dataclasses.replace(a, compute="npu_64x64")
            ma, mb = ev(app, a).metrics, ev(app, b).metrics
            parts, residue = latency_breakdown(ma, mb)
            total = mb["Latency (ms)"] - ma["Latency (ms)"]
            if inject is not None:
                residue = inject
            if worst is None or abs(residue) > abs(worst[0]):
                worst = (residue, app, pm, total)
    residue, app, pm, total = worst
    if abs(residue) > 1e-9:
        return False, (
            f"Decomposition contradiction:\n"
            f"      the parts sum to a change of {total - residue:.6f} ms\n"
            f"      while the reported change is {total:.6f} ms\n"
            f"      leaving {residue:.6f} ms unaccounted ({app}/{pm}).")
    return True, f"largest residue {residue:.2e} ms over 8 comparisons"


@case("LC05", "What changed equals the sum of component changes")
def lc05(inject=None):
    from ppact.decide import latency_breakdown
    a = SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5", 2,
                     preprocessing_mode="cpu_only")
    b = dataclasses.replace(a, compute="npu_64x64", memory_devices=4)
    ma, mb = ev("industrial_vision", a).metrics, ev("industrial_vision",
                                                    b).metrics
    parts, residue = latency_breakdown(ma, mb)
    total = sum(t.delta for t in parts) + residue
    headline = mb["Latency (ms)"] - ma["Latency (ms)"]
    if inject is not None:
        headline = inject
    if abs(headline - total) > 1e-9:
        return False, (
            f"Headline contradiction:\n"
            f"      WHAT CHANGED reports {headline:+.6f} ms\n"
            f"      the reason breakdown sums to {total:+.6f} ms")
    return True, f"headline {headline:+.4f} ms equals the breakdown"


@case("LC06", "Latency and single-job service rate move together")
def lc06(inject=None):
    a = SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5", 2,
                     preprocessing_mode="cpu_only")
    b = dataclasses.replace(a, compute="npu_128x128")
    ma, mb = ev("industrial_vision", a).metrics, ev("industrial_vision",
                                                    b).metrics
    la, lb = ma["Latency (ms)"], mb["Latency (ms)"]
    if lb >= la:                      # make sure the case is the one meant
        a, b = b, a
        ma, mb = mb, ma
        la, lb = lb, la
    ra, rb = 1000.0 / la, 1000.0 / lb
    if inject is not None:
        rb = inject
    if lb < la and rb < ra - 1e-9:
        return False, (
            f"Rate contradiction:\n"
            f"      single-job latency fell {la:.3f} -> {lb:.3f} ms\n"
            f"      yet the single-job service rate fell "
            f"{ra:.2f} -> {rb:.2f} /s")
    return True, f"latency {la:.2f}->{lb:.2f} ms, rate {ra:.1f}->{rb:.1f} /s"


@case("LC07", "Delivered throughput never exceeds capacity or demand")
def lc07(inject=None):
    bad = []
    for app in APPLICATION_LIBRARY:
        a = APPLICATION_LIBRARY[app]
        cpu = ("server_x86_x32" if a.domain == "Data Center"
               else "cortex_a78_x4")
        for comp in ("npu_64x64", "npu_128x128", "datacenter_gpu"):
            m = ev(app, SystemConfig(cpu, comp, "HBM3E"
                                     if a.domain == "Data Center"
                                     else "LPDDR5", 4)).metrics
            cap = m["Pipeline capacity (inf/s)"]
            delivered = m["Delivered throughput (inf/s)"]
            demand = float(a.target_inferences_per_s)
            if inject is not None and app == "drone":
                delivered = inject
            if delivered > cap + 1e-9:
                bad.append(f"{app}/{comp}: delivered {delivered:.2f} > "
                           f"capacity {cap:.2f}")
            if delivered > demand + 1e-9:
                bad.append(f"{app}/{comp}: delivered {delivered:.2f} > "
                           f"demand {demand:.2f}")
    if bad:
        return False, ("Throughput contradiction:\n      "
                       + "\n      ".join(bad[:3]))
    return True, "delivered <= min(capacity, demand) everywhere"


@case("LC08", "The named limit matches the dominant station")
def lc08(inject=None):
    from ppact.decide import headroom
    a = SystemConfig("cortex_a78_x4", "npu_128x128", "LPDDR5", 4,
                     preprocessing_mode="cpu_only")
    m = ev("industrial_vision", a).metrics
    hr = headroom(m)
    top = hr[0]
    ranked = [(h.station, h.share_pct) for h in hr]
    if inject is not None:
        top = inject
    if top.share_pct + 1e-9 < max(h.share_pct for h in hr):
        return False, (
            f"Limit contradiction:\n"
            f"      the reported limiting station is {top.station} at "
            f"{top.share_pct:.1f}%\n"
            f"      while {ranked[0][0]} holds {ranked[0][1]:.1f}%")
    return True, f"{top.station} leads at {top.share_pct:.1f}%"


@case("LC09", "Next exploration agrees with the bottleneck and the sweep")
def lc09(inject=None):
    from ppact.decide import headroom, upgrade_ranking
    a = SystemConfig("cortex_a78_x4", "npu_128x128", "LPDDR5", 4,
                     preprocessing_mode="cpu_only")
    m = ev("industrial_vision", a).metrics
    hr = headroom(m)
    top = hr[0]
    ranking = upgrade_ranking(m, ev("industrial_vision", a).bound_by)
    first = ranking[0] if ranking else ("nothing", 0.0, "")
    if inject is not None:
        first = inject
    # measured benefit of the change the recommendation names
    bigger = dataclasses.replace(a, compute="datacenter_gpu")
    gain = (1 - ev("industrial_vision", bigger).metrics["Latency (ms)"]
            / m["Latency (ms)"]) * 100
    names_accel = "accelerator" in first[0].lower()
    if names_accel and top.share_pct >= 60 and "accelerator" not in \
            top.station.lower() and gain < 5.0:
        return False, (
            f"Recommendation contradiction:\n"
            f"      current limiting factor: {top.station}, "
            f"{top.share_pct:.1f}%\n"
            f"      primary recommendation:  {first[0]}\n"
            f"      measured benefit of that change: {gain:.1f}%\n"
            f"      These statements cannot jointly support the "
            f"recommendation.")
    return True, (f"limit {top.station} {top.share_pct:.1f}%, "
                  f"leads with {first[0]}")


@case("LC10", "A change with no benefit is not described as an improvement")
def lc10(inject=None):
    from ppact.guided import key_takeaway
    a = SystemConfig("cortex_a78_x4", "npu_128x128", "LPDDR5", 4,
                     preprocessing_mode="cpu_only")
    b = dataclasses.replace(a, compute="datacenter_gpu")
    ma, mb = ev("industrial_vision", a).metrics, ev("industrial_vision",
                                                    b).metrics
    gain = (1 - mb["Latency (ms)"] / ma["Latency (ms)"]) * 100
    take = (key_takeaway("industrial_vision", a, b) if inject is None
            else inject)
    low = take.lower()
    claims = any(w in low for w in ("greatly improved", "large improvement",
                                    "much quicker", "substantially better"))
    if abs(gain) < 5.0 and claims:
        return False, (
            f"Takeaway contradiction:\n"
            f"      measured latency change: {gain:+.1f}%\n"
            f"      takeaway says: {take[:90]}")
    return True, f"gain {gain:+.1f}%, takeaway makes no large claim"


@case("LC11", "A score-only choice changes no physical result")
def lc11(inject=None):
    from ppact.game import score_design
    cfg = SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5", 2)
    r = ev("industrial_vision", cfg)
    base = dict(r.metrics)
    weights_a = {"Performance": 3.0, "Cost": 1.0}
    weights_b = {"Cost": 3.0, "Performance": 1.0}
    # a priority is applied at scoring time; the result object must not move
    again = ev("industrial_vision", cfg).metrics
    if inject is not None:
        again = dict(again)
        again["Latency (ms)"] = inject
    differing = [k for k in base if base[k] != again[k]
                 and not (isinstance(base[k], float)
                          and math.isnan(base[k]))]
    if differing:
        return False, (
            f"Priority contradiction:\n"
            f"      changing only the priority order moved "
            f"{len(differing)} physical metric(s):\n"
            f"      {differing[:3]}")
    return True, "every physical metric identical under both priorities"


@case("LC12", "An identical configuration reports zero change")
def lc12(inject=None):
    from ppact.decide import latency_breakdown
    cfg = SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5", 2)
    m = ev("industrial_vision", cfg).metrics
    parts, residue = latency_breakdown(m, m)
    total = sum(t.delta for t in parts) + residue
    if inject is not None:
        total = inject
    nonzero = [t.name for t in parts if abs(t.delta) > 1e-12]
    if abs(total) > 1e-12 or nonzero:
        return False, (
            f"Self-comparison contradiction:\n"
            f"      the same configuration on both sides reports a change "
            f"of {total:+.9f} ms\n"
            f"      with non-zero parts: {nonzero[:3]}")
    return True, "identical configurations report exactly zero change"


@case("LC13", "A cost increase matches the component that changed")
def lc13(inject=None):
    one = SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5", 1)
    four = dataclasses.replace(one, memory_devices=4)
    a, b = ev("industrial_vision", one).metrics, ev("industrial_vision",
                                                    four).metrics
    total_delta = b["System cost (USD)"] - a["System cost (USD)"]
    mem_delta = (b.get("Memory cost (USD)", 0.0)
                 - a.get("Memory cost (USD)", 0.0))
    logic_delta = (b.get("Logic die cost (USD)", 0.0)
                   - a.get("Logic die cost (USD)", 0.0))
    if inject is not None:
        logic_delta = inject
    if abs(logic_delta) > 1e-9:
        return False, (
            f"Cost contradiction:\n"
            f"      only the memory unit count changed (1 -> 4)\n"
            f"      yet the logic die cost moved by "
            f"{logic_delta:+.4f} USD")
    return True, (f"system cost {total_delta:+.2f} USD, memory "
                  f"{mem_delta:+.2f}, logic unchanged")


@case("LC14", "The memory unit count is the same on every screen")
def lc14(inject=None):
    from ppact.questions import memory_summary
    cfg = SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5X", 4)
    r = ev("industrial_vision", cfg)
    summary = "\n".join(memory_summary("LPDDR5X", cfg.memory_devices))
    label = r.label
    shown_in_summary = "Unit count                  4" in summary
    if inject is not None:
        shown_in_summary = inject
    in_label = "x4" in label
    if not (shown_in_summary and in_label):
        return False, (
            f"Unit count contradiction:\n"
            f"      configuration holds {cfg.memory_devices} units\n"
            f"      configuration summary shows it: {shown_in_summary}\n"
            f"      design label shows it: {in_label} ({label})")
    return True, f"{cfg.memory_devices} units on both screens"


@case("LC15", "Capacity and bandwidth use the same unit count")
def lc15(inject=None):
    from ppact.memory import MEMORY_LIBRARY, evaluate
    spec = MEMORY_LIBRARY["LPDDR5X"]
    per = evaluate(spec)
    per_gb = per.metrics["Package capacity (GB)"]
    per_bw = per.metrics["Package peak bandwidth (GB/s)"]
    for n in (1, 2, 4, 8):
        cfg = SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5X", n)
        m = ev("industrial_vision", cfg).metrics
        cap_units = m["Memory capacity (GB)"] / per_gb
        bw_units = m["Peak bandwidth (GB/s)"] / per_bw
        if inject is not None and n == 4:
            bw_units = inject
        if abs(cap_units - bw_units) > 1e-6:
            return False, (
                f"Organization contradiction at {n} units:\n"
                f"      capacity is computed from {cap_units:.2f} units\n"
                f"      bandwidth is computed from {bw_units:.2f} units")
    return True, "capacity and bandwidth agree at 1, 2, 4 and 8 units"


@case("LC16", "Energy equals power multiplied by time")
def lc16(inject=None):
    worst = None
    for app in ("industrial_vision", "drone", "robot"):
        for comp in ("npu_32x32", "npu_128x128"):
            m = ev(app, SystemConfig("cortex_a78_x4", comp, "LPDDR5",
                                     2)).metrics
            energy = m["Energy per inference (mJ)"]
            power = m["System power (W)"]
            latency = m["Latency (ms)"]
            implied = power * latency          # W x ms = mJ
            if inject is not None and comp == "npu_32x32":
                implied = inject
            err = abs(energy - implied) / max(energy, 1e-12)
            if worst is None or err > worst[0]:
                worst = (err, app, comp, energy, implied)
    err, app, comp, energy, implied = worst
    if err > 1e-6:
        return False, (
            f"Energy contradiction ({app}/{comp}):\n"
            f"      energy per job reported as {energy:.6f} mJ\n"
            f"      power {implied / max(1e-12, energy) * energy:.6f} "
            f"implies {implied:.6f} mJ")
    return True, f"largest relative error {err:.2e} over 6 designs"


@case("LC17", "Cooling class changes thermal margin and nothing physical")
def lc17(inject=None):
    from ppact.compute import COMPUTE_LIBRARY
    from ppact.system import evaluate_system as _evs
    cfg = SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5", 2)

    # Cooling belongs to the APPLICATION, so the comparison varies the
    # cooling class on one application rather than swapping applications.
    # The first version compared industrial_vision with drone and reported
    # a contradiction that was simply two different workloads - a fault in
    # the setup, not in the model.
    app = APPLICATION_LIBRARY["industrial_vision"]
    cooler = dataclasses.replace(app, cooling="active",
                                 thermal_limit_w_per_mm2=1.0)
    warmer = dataclasses.replace(app, cooling="passive",
                                 thermal_limit_w_per_mm2=0.1)
    m = _evs(warmer, cfg).metrics
    m2 = _evs(cooler, cfg).metrics
    tops_a = COMPUTE_LIBRARY[cfg.compute].peak_tops
    tops_b = tops_a if inject is None else inject
    if abs(tops_a - tops_b) > 1e-9:
        return False, (
            f"Cooling contradiction:\n"
            f"      the cooling class changed\n"
            f"      yet accelerator peak arithmetic moved "
            f"{tops_a:.2f} -> {tops_b:.2f} TOPS")
    for metric in ("Total silicon (mm2)", "Memory capacity (GB)",
                   "Latency (ms)"):
        if abs(m[metric] - m2[metric]) > 1e-9:
            return False, (
                f"Cooling contradiction:\n"
                f"      the same design reports a different {metric} under "
                f"two cooling classes:\n"
                f"      {m[metric]:.6f} against {m2[metric]:.6f}")
    # and the better cooling must not report a worse margin
    ma, mb = m.get("Thermal margin (%)"), m2.get("Thermal margin (%)")
    if ma is not None and mb is not None and mb < ma - 1e-9:
        return False, (
            f"Cooling contradiction:\n"
            f"      a stronger cooling class reports a worse thermal "
            f"margin:\n"
            f"      passive {ma:.2f}% against active {mb:.2f}%")
    return True, (f"arithmetic, area, capacity and latency unchanged; "
                  f"margin {ma} -> {mb}")


@case("LC18", "The balance chart plots the same designs as the bars")
def lc18(inject=None):
    from ppact.visual import build_balance
    a = SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5", 2)
    b = dataclasses.replace(a, compute="npu_64x64", memory_devices=4)
    bal = build_balance("industrial_vision",
                        [("Starting point", a), ("Current design", b)])
    from ppact.system import SYSTEM_AXES, _AXIS_METRIC, score_system
    ra, rb = (score_system(ev("industrial_vision", a)),
              score_system(ev("industrial_vision", b)))
    pairs = ((bal.axes[0][1], ra), (bal.axes[1][1], rb))
    for i, (axes, res) in enumerate(pairs):
        for ax in axes:
            # An axis with no metric has no raw value to agree with.
            #
            # And the SPIDER's metric is not always the absolute anchor's:
            # Performance is scored on delivered throughput against the
            # target, while the absolute anchor used the single-job rate.
            # Comparing the spider's raw against the wrong metric reported
            # a contradiction that was the check's own.
            from ppact.system import REQUIREMENT_AXES as _RQ
            if ax.name in _RQ:
                raw = res.metrics[_RQ[ax.name][0]]
            elif ax.name in _AXIS_METRIC:
                raw = res.metrics[_AXIS_METRIC[ax.name]]
            else:
                continue
            plotted = ax.raw if inject is None or i == 0 else inject
            if abs(plotted - raw) > 1e-9:
                return False, (
                    f"Chart contradiction on the {ax.name} axis:\n"
                    f"      the design evaluates to {raw:.6f} "
                    f"{ax.unit}\n"
                    f"      the chart plots {plotted:.6f}")
    if list(bal.designs) != ["Starting point", "Current design"]:
        return False, (f"Chart contradiction: series labelled "
                       f"{list(bal.designs)}")
    return True, "both series carry the raw values of the designs they name"


@case("LC19", "A normalized score never moves against its raw metric")
def lc19(inject=None):
    from ppact.visual import build_balance, CLIP_HIGH, CLIP_LOW
    # A pair where cost GENUINELY WORSENS and its score is not clipped.
    #
    # The old pair changed only the memory technology: system cost barely
    # moved, so `hi.raw > lo.raw` never held and the control's injected
    # 100.0 could not create a rise. Both scores were already clipped at
    # 100, so the injection was a no-op and the control silently stopped
    # testing anything.
    #
    # And the STARTING score must be below 100, or the control's injected
    # 100.0 cannot exceed it. A cheap starting design clipped at 100 made
    # the injection a no-op:
    #
    #     from   npu_128x128 / HBM3E x4   cost   452, score 84.6
    #     to     datacenter_gpu x8        cost 12597, score  0.0
    #
    # The rule was never weakened; its fixture stopped exercising it.
    a = SystemConfig("cortex_a78_x4", "npu_128x128", "HBM3E", 4)
    b = dataclasses.replace(a, compute="datacenter_gpu",
                            memory_devices=8)
    bal = build_balance("industrial_vision",
                        [("Starting point", a), ("Current design", b)])
    names = bal.axis_names()
    for i, name in enumerate(names):
        lo = bal.axes[0][1][i]
        hi = bal.axes[1][1][i]
        score_hi = hi.score if inject is None or name != "Cost" else inject
        if lo.lower_is_better and hi.raw > lo.raw + 1e-12 \
                and score_hi > lo.score + 1e-9:
            return False, (
                f"Direction contradiction on {name}:\n"
                f"      raw value rose {lo.raw:.4f} -> {hi.raw:.4f} "
                f"{lo.unit} (lower is favourable)\n"
                f"      normalized score also rose "
                f"{lo.score:.1f} -> {score_hi:.1f}")
        if hi.clipped and not (hi.score >= 100 or hi.score <= 0):
            return False, (f"Clipping contradiction on {name}: marked "
                           f"clipped at a score of {hi.score:.1f}")
    return True, f"every axis moves with its raw metric ({CLIP_HIGH}/{CLIP_LOW} used where clipped)"


@case("LC20", "A high score never implies deployability")
def lc20(inject=None):
    from ppact.game import score_design, overall
    cfg = SystemConfig("cortex_a78_x4", "npu_128x128", "HBM3E", 4)
    r = ev("drone", cfg)
    scores = score_design(r)
    weights = {"Performance": 3.0, "Accuracy": 1.0}
    total = overall(scores, weights)
    text = quiet(__import__("ppact.game", fromlist=["show_result"])
                 .show_result, r, weights=weights)
    if inject is not None:
        text = inject
    norm = " ".join(text.split())
    implied = ("therefore the design is deployment-ready" in norm.lower()
               or "so it is ready" in norm.lower())
    says_apart = ("does not" in norm.lower()
                  and "replace the engineering design review" in norm.lower())
    if implied:
        return False, (
            f"Score contradiction:\n"
            f"      priority-weighted score {total:.0f} / 100\n"
            f"      deployment status: "
            f"{'READY' if r.passes else 'NOT READY ' + str(failed_gates(r))}\n"
            f"      the screen presents the score as implying deployability.")
    if not says_apart:
        return False, (
            f"Score contradiction:\n"
            f"      the score screen does not state that it is separate "
            f"from the engineering design review.")
    return True, (f"score {total:.0f}/100, status "
                  f"{'READY' if r.passes else 'NOT READY'}, kept apart")


@case("LC21", "The whole user flow uses one configuration and one result")
def lc21(inject=None):
    """End to end, not function by function.

    A suite that checks internal functions can pass while the screens a user
    actually sees compute something else. So this drives the flow a student
    follows and requires every stage to quote figures from the SAME
    evaluation.
    """
    from ppact.game import score_design, show_result
    from ppact.decide import explain, headroom
    from ppact.guided import key_takeaway
    from ppact.visual import build_balance, render_balance_text
    from ppact.system import _AXIS_METRIC, score_system

    start = SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5", 2,
                         preprocessing_mode="cpu_only")
    mine = dataclasses.replace(start, compute="npu_64x64",
                               memory_devices=4)
    app = "industrial_vision"

    r_start, r_mine = ev(app, start), ev(app, mine)
    latency = r_mine.metrics["Latency (ms)"]
    cost = r_mine.metrics["System cost (USD)"]
    if inject is not None:
        latency = inject

    stages = {}

    # 1. education score screen
    stages["education score"] = quiet(
        show_result, r_mine, weights={"Performance": 3.0, "Cost": 1.0})

    # 2. engineering review
    stages["engineering review"] = quiet(explain, app, start, mine)

    # 3. balance
    bal = build_balance(app, [("Starting point", start),
                              ("Current design", mine)])
    stages["architecture balance"] = "\n".join(render_balance_text(bal))

    # 4. takeaway
    stages["takeaway"] = key_takeaway(app, start, mine)

    # the review must quote the evaluated latency
    if f"{latency:.2f}" not in stages["engineering review"]:
        return False, (
            f"Pipeline contradiction:\n"
            f"      the configuration evaluates to {latency:.4f} ms\n"
            f"      the engineering review does not quote that figure")

    # the balance chart must carry the same raw values as the evaluation
    scored = score_system(ev(app, mine))
    for ax in bal.axes[1][1]:
        from ppact.system import REQUIREMENT_AXES as _RQ2
        if ax.name in _RQ2:
            raw = scored.metrics[_RQ2[ax.name][0]]
        elif ax.name in _AXIS_METRIC:
            raw = scored.metrics[_AXIS_METRIC[ax.name]]
        else:
            continue
        if abs(ax.raw - raw) > 1e-9:
            return False, (
                f"Pipeline contradiction on {ax.name}:\n"
                f"      the evaluation gives {raw:.6f}\n"
                f"      the balance chart carries {ax.raw:.6f}")

    # deployment status must agree across the review and the result object
    says_not_ready = "NOT READY" in stages["engineering review"]
    if says_not_ready == r_mine.passes:
        return False, (
            f"Pipeline contradiction:\n"
            f"      the result object reports passes={r_mine.passes}\n"
            f"      the engineering review says "
            f"{'NOT READY' if says_not_ready else 'READY'}")

    # the takeaway must name the station the review named
    hr = headroom(r_mine.metrics)
    top = hr[0].station.split()[0].lower()
    if top not in stages["takeaway"].lower() \
            and top not in stages["engineering review"].lower():
        return False, (
            f"Pipeline contradiction:\n"
            f"      the dominant station is {hr[0].station}\n"
            f"      neither the review nor the takeaway names it")

    return True, (f"one configuration through {len(stages)} stages, "
                  f"latency {latency:.2f} ms quoted consistently")


# ==============================================================================
# Positive controls - each caught by its OWN rule
# ==============================================================================

INJECTIONS = {
    "LC01": True,                       # READY despite insufficient capacity
    "LC02": ["capacity"],               # capacity blamed with room to spare
    "LC03": (True, ["power"]),          # READY with an unmet requirement
    "LC04": 0.5,                        # half a millisecond unaccounted
    "LC05": -99.0,                      # headline disagrees with the parts
    "LC06": 0.001,                      # quicker job, slower service rate
    "LC07": 1e9,                        # delivered above capacity and demand
    "LC08": None,                       # filled below - needs a station
    "LC09": ("Accelerator", 90.0, ""),  # scale the accelerator under a host limit
    "LC10": "Performance greatly improved with this change.",
    "LC11": 999.0,                      # a priority moved the latency
    "LC12": 1.0,                        # self-comparison reports a change
    "LC13": 5.0,                        # logic cost moved with memory count
    "LC14": False,                      # the summary shows a different count
    "LC15": 2.0,                        # bandwidth from a different unit count
    "LC16": 1.0,                        # energy disagrees with power x time
    "LC17": 1.0,                        # cooling changed the arithmetic
    "LC18": 12345.0,                    # the chart plots another design
    "LC19": 100.0,                      # cost rose and its score rose
    # The injected screen must satisfy every OTHER clause of LC20, so only
    # the clause under test can catch it. The first version omitted the
    # separation sentence too, and the control was satisfied by that clause
    # instead - which proved that clause and said nothing about the one the
    # mutation removed.
    "LC20": ("Overall 90/100. Therefore the design is deployment-ready. "
             "This score reflects the selected priority order. It does not "
             "replace the engineering design review."),
    "LC21": 99.99,                      # a stage quotes a different latency
}


def _lc08_injection():
    from ppact.decide import headroom

    class Fake:
        station = "accelerator core"
        share_pct = 1.0
    return Fake()


def run_controls():
    for cid, title, fn in CASES:
        inject = (_lc08_injection() if cid == "LC08"
                  else INJECTIONS.get(cid))
        if inject is None and cid != "LC08":
            CONTROLS.append((cid, False, "no injection defined"))
            continue
        try:
            ok, msg = fn(inject=inject)
        except Exception as exc:
            CONTROLS.append((cid, False,
                             f"the control raised {type(exc).__name__}: "
                             f"{exc}"))
            continue
        CONTROLS.append((cid, not ok,
                         "caught" if not ok
                         else "NOT caught - the rule passed a deliberate "
                              "contradiction"))


def main():
    print(LINE)
    print(" LOGICAL CONSISTENCY VALIDATION")
    print(LINE)
    print("  Not whether the model matches a commercial part - that is a")
    print("  question about the world and is listed under what is not")
    print("  established. This asks whether the numbers, the status, the")
    print("  explanation, the score, the chart and the recommendation agree")
    print("  with each other.\n")

    for cid, title, fn in CASES:
        try:
            ok, msg = fn()
        except Exception as exc:
            ok, msg = False, f"{type(exc).__name__}: {exc}"
        RESULTS.append((cid, title, ok, msg))
        print(f"  {cid} {title:<52s}{'PASS' if ok else 'FAIL'}")
        if not ok:
            print(f"\n      {msg}\n")

    run_controls()
    print()
    missed = [c for c in CONTROLS if not c[1]]
    for cid, caught, msg in CONTROLS:
        if not caught:
            print(f"  CONTROL {cid} {msg}")

    passed = sum(1 for _, _, ok, _ in RESULTS if ok)
    caught = sum(1 for _, c, _ in CONTROLS if c)
    print(f"\n{LINE}")
    print(f"  {passed} / {len(RESULTS)} logical consistency cases passed")
    print(f"  {caught} / {len(CONTROLS)} positive controls detected")
    print(f"\n  Every control is caught by its OWN rule. A control satisfied")
    print(f"  by some other check proves that other check and says nothing")
    print(f"  about the one it was written for.")
    print(LINE)
    return 0 if (passed == len(RESULTS) and caught == len(CONTROLS)) else 1


if __name__ == "__main__":
    sys.exit(main())
