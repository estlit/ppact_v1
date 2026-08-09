"""
ppact.sensitivity - which conclusions survive their assumptions

A verdict computed from one coefficient value is a verdict about that value.
Some of this model's conclusions would survive any plausible figure and some
reverse if an assumption moves by half a point, and reporting both the same
way is the most misleading thing a simulator can do.

This module moves ONE coefficient at a time across a stated range, records
what the verdict does, and finds where it flips. Four outcomes:

    ROBUST PASS        passes everywhere in the range
    ROBUST FAIL        fails everywhere in the range
    CONDITIONAL        flips inside the range, and the flip point is far
                       from the nominal value
    BOUNDARY-ADJACENT  flips inside the range CLOSE to the nominal value -
                       the verdict is a property of the assumption rather
                       than of the design

The last is the one worth finding, and the one a single-value report hides.

A coefficient that changes nothing is also worth finding: a registry entry
that the code never reads is decoration, and decoration in a coefficient
registry is a claim that something was considered when it was not.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

LINE = "=" * 80

ROBUST_PASS = "ROBUST PASS"
ROBUST_FAIL = "ROBUST FAIL"
CONDITIONAL = "CONDITIONAL"
BOUNDARY_ADJACENT = "BOUNDARY-ADJACENT"
NO_INFLUENCE = "NO INFLUENCE"

# How close a flip point has to be, as a fraction of the range, before the
# verdict is called a property of the assumption rather than of the design.
# A judgement, stated here rather than buried in a comparison.
ADJACENCY_FRACTION = 0.20


@dataclass
class Sweep:
    sid: str
    coefficient: str
    description: str
    low: float
    nominal: float
    high: float
    # set the coefficient, run, and return (verdict, headline value)
    probe: Callable[[float], Tuple[bool, float]]
    verdict_name: str
    value_name: str
    basis: str = "ENGINEERING ASSUMPTION"
    note: str = ""


def _samples(low, nominal, high, n=21):
    step = (high - low) / (n - 1)
    pts = [low + i * step for i in range(n)]
    if not any(abs(p - nominal) < step / 100 for p in pts):
        pts.append(nominal)
        pts.sort()
    return pts


def run_sweep(sw: Sweep, points: int = 21) -> Dict:
    """Move one coefficient and record what the verdict does."""
    pts = _samples(sw.low, sw.nominal, sw.high, points)
    rows = []
    for v in pts:
        try:
            passes, value = sw.probe(v)
        except Exception as exc:
            rows.append((v, None, float("nan"), f"{type(exc).__name__}"))
            continue
        rows.append((v, passes, value, ""))

    verdicts = [r[1] for r in rows if r[1] is not None]
    values = [r[2] for r in rows if r[1] is not None]
    nominal_pass = next((r[1] for r in rows
                         if abs(r[0] - sw.nominal) < 1e-12), None)

    # a coefficient that moves nothing at all
    spread = (max(values) - min(values)) if values else 0.0
    scale = abs(values[0]) if values and values[0] else 1.0
    if values and spread <= abs(scale) * 1e-9:
        outcome = NO_INFLUENCE
        flip = None
    elif all(verdicts):
        outcome, flip = ROBUST_PASS, None
    elif not any(verdicts):
        outcome, flip = ROBUST_FAIL, None
    else:
        # the flip lies between the last agreeing pair
        flip = None
        for (v1, p1, _, _), (v2, p2, _, _) in zip(rows, rows[1:]):
            if p1 is not None and p2 is not None and p1 != p2:
                flip = (v1 + v2) / 2.0
                break
        span = sw.high - sw.low
        near = (flip is not None
                and abs(flip - sw.nominal) <= span * ADJACENCY_FRACTION)
        outcome = BOUNDARY_ADJACENT if near else CONDITIONAL

    return {"sweep": sw, "rows": rows, "outcome": outcome, "flip": flip,
            "nominal_pass": nominal_pass}


def print_sweep(result: Dict, show_rows: int = 8) -> None:
    sw = result["sweep"]
    print(f"\n{LINE}")
    print(f" {sw.sid}  {sw.description}")
    print(LINE)
    print(f"  coefficient   {sw.coefficient}")
    print(f"  basis         {sw.basis}")
    print(f"  range         {sw.low:g} to {sw.high:g}, nominal {sw.nominal:g}")
    if sw.note:
        print(f"  {sw.note}")
    print()
    head = f"  {sw.coefficient[:26]:<28s}{sw.value_name:>16s}   {sw.verdict_name}"
    print(head); print("  " + "-" * (len(head) - 2))
    rows = result["rows"]
    step = max(1, len(rows) // show_rows)
    shown = rows[::step]
    if rows[-1] not in shown:
        shown.append(rows[-1])
    for v, passes, value, err in shown:
        mark = "  <- nominal" if abs(v - sw.nominal) < 1e-12 else ""
        state = err or ("PASS" if passes else "FAIL")
        print(f"  {v:<28g}{value:>16.3f}   {state}{mark}")

    print(f"\n  outcome   {result['outcome']}")
    if result["flip"] is not None:
        d = abs(result["flip"] - sw.nominal)
        span = sw.high - sw.low
        print(f"  flips at  {result['flip']:g}, which is {d:g} from the "
              f"nominal value")
        print(f"            ({d / span * 100:.0f}% of the range)")
    if result["outcome"] == BOUNDARY_ADJACENT:
        print(f"\n  This verdict is a property of the ASSUMPTION rather than "
              f"of the")
        print(f"  design. It should not be quoted without a measured figure "
              f"for")
        print(f"  {sw.coefficient}.")
    elif result["outcome"] == NO_INFLUENCE:
        print(f"\n  Moving this coefficient across its whole range changed "
              f"nothing.")
        print(f"  Either the result does not depend on it - in which case the")
        print(f"  registry entry is decoration - or the code does not read "
              f"it.")
    elif result["outcome"] in (ROBUST_PASS, ROBUST_FAIL):
        print(f"\n  The verdict holds across the whole assumed range, so it "
              f"does")
        print(f"  not rest on this coefficient. That is worth stating: most "
              f"do")
        print(f"  not, and a reader cannot tell which without being told.")
    print(LINE)


# ==============================================================================
# Phase S1 - the four where a conclusion is already suspected to be fragile
# ==============================================================================

def build_sweeps() -> List[Sweep]:
    from .application import APPLICATION_LIBRARY
    from .system import evaluate_system, SystemConfig
    import ppact.system as S
    from .economics import QUANT_ACCURACY_COST_PP

    sweeps = []

    # --- S-01: INT4 accuracy loss ----------------------------------------
    #
    # The quantisation sweep found INT4 the only width that fits a two-stack
    # board and clearing the accuracy requirement by 0.4 points. That margin
    # is smaller than the uncertainty in the assumption behind it.
    def int4_probe(loss_pp):
        app = APPLICATION_LIBRARY["llm_service"]
        tuned = dataclasses.replace(
            app,
            weight_bytes=app.weight_bytes * 0.25,
            kv_cache_bytes=app.kv_cache_bytes * 0.25,
            kv_bytes_per_token=app.kv_bytes_per_token * 0.25,
            reference_accuracy_pct=app.reference_accuracy_pct - loss_pp,
            key="__s01__")
        APPLICATION_LIBRARY["__s01__"] = tuned
        try:
            r = evaluate_system(tuned, SystemConfig(
                "server_x86_x32", "datacenter_gpu", "HBM3E", 2))
            acc = r.metrics["Deployment accuracy (%)"]
            return r.gate.get("accuracy", True), acc
        finally:
            APPLICATION_LIBRARY.pop("__s01__", None)

    sweeps.append(Sweep(
        "S-01", "INT4 accuracy loss (pp)",
        "Does the INT4 verdict survive its accuracy assumption?",
        low=2.0, nominal=QUANT_ACCURACY_COST_PP["INT4"], high=5.0,
        probe=int4_probe, verdict_name="accuracy gate",
        value_name="deployment accuracy",
        note="The model has no basis for this figure. It depends on the "
             "network, the calibration and the method."))

    # --- S-02: LLM serving efficiency ------------------------------------
    def serving_probe(eff):
        saved = S.LLM_SINGLE_STREAM_SERVING_EFFICIENCY
        S.LLM_SINGLE_STREAM_SERVING_EFFICIENCY = eff
        try:
            app = APPLICATION_LIBRARY["llm_service"]
            r = evaluate_system(app, SystemConfig(
                "server_x86_x32", "datacenter_gpu", "HBM3E", 6))
            return (r.gate.get("throughput", True),
                    r.metrics["Single-job rate (inf/s)"])
        finally:
            S.LLM_SINGLE_STREAM_SERVING_EFFICIENCY = saved

    sweeps.append(Sweep(
        "S-02", "LLM serving efficiency",
        "Does the token-rate verdict survive the serving overhead assumption?",
        low=0.28, nominal=S.LLM_SINGLE_STREAM_SERVING_EFFICIENCY, high=0.64,
        probe=serving_probe, verdict_name="throughput gate",
        value_name="tokens/s",
        note="The published evidence brackets this between 0.28 and 0.64 "
             "because the precision is not stated in either source. Only a "
             "measurement narrows it."))

    # --- S-03: dual-accelerator contention -------------------------------
    def contention_probe(coef):
        saved = S.DUAL_MEMORY_CONTENTION
        S.DUAL_MEMORY_CONTENTION = coef
        try:
            app = APPLICATION_LIBRARY["robot"]
            base = SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5", 4,
                                preprocessing_mode="isp_and_npu")
            dual = dataclasses.replace(base, secondary_compute="npu_32x32",
                                       execution_mode="parallel",
                                       work_split=0.5)
            a = evaluate_system(app, base).metrics["Latency (ms)"]
            b = evaluate_system(app, dual).metrics["Latency (ms)"]
            # the "verdict" here is whether the pair beats the single engine
            return b < a, (1 - b / a) * 100
        finally:
            S.DUAL_MEMORY_CONTENTION = saved

    sweeps.append(Sweep(
        "S-03", "Dual-accelerator memory contention",
        "Does the second engine still win under any contention estimate?",
        low=0.0, nominal=S.DUAL_MEMORY_CONTENTION, high=0.40,
        probe=contention_probe,
        verdict_name="dual beats single", value_name="latency gain %",
        note="At zero this coefficient is switched off entirely, so any "
             "remaining loss is structural saturation rather than an assumed "
             "penalty."))

    # --- S-04: memory controller efficiency ------------------------------
    def controller_probe(eff):
        from .memory import MEMORY_LIBRARY
        saved = MEMORY_LIBRARY["HBM3E"]
        MEMORY_LIBRARY["HBM3E"] = dataclasses.replace(
            saved, bandwidth_efficiency=eff)
        try:
            app = APPLICATION_LIBRARY["llm_service"]
            r = evaluate_system(app, SystemConfig(
                "server_x86_x32", "datacenter_gpu", "HBM3E", 6))
            return (r.gate.get("throughput", True),
                    r.metrics["Single-job rate (inf/s)"])
        finally:
            MEMORY_LIBRARY["HBM3E"] = saved

    from .memory import MEMORY_LIBRARY as _ML
    sweeps.append(Sweep(
        "S-04", "HBM controller efficiency",
        "Does the HBM token rate survive the controller efficiency estimate?",
        low=0.60, nominal=_ML["HBM3E"].bandwidth_efficiency, high=0.95,
        probe=controller_probe, verdict_name="throughput gate",
        value_name="tokens/s",
        note="What fraction of the interface rate a real controller achieves "
             "on this access pattern. Vendors quote the interface rate."))

    return sweeps


def run_all(points: int = 21, verbose: bool = True) -> List[Dict]:
    results = [run_sweep(sw, points) for sw in build_sweeps()]
    if verbose:
        for r in results:
            print_sweep(r)
        print(f"\n{LINE}")
        print(" SENSITIVITY SUMMARY")
        print(LINE)
        head = f"  {'id':<7s}{'coefficient':<34s}{'outcome':<20s}flip"
        print(head); print("  " + "-" * (len(head) - 2))
        for r in results:
            flip = f"{r['flip']:g}" if r["flip"] is not None else "-"
            print(f"  {r['sweep'].sid:<7s}{r['sweep'].coefficient[:33]:<34s}"
                  f"{r['outcome']:<20s}{flip}")
        adjacent = [r for r in results if r["outcome"] == BOUNDARY_ADJACENT]
        print()
        if adjacent:
            print(f"  {len(adjacent)} verdict(s) are properties of an "
                  f"ASSUMPTION rather than")
            print(f"  of a design. Those should not be quoted without a "
                  f"measured")
            print(f"  figure behind the coefficient.")
        robust = [r for r in results
                  if r["outcome"] in (ROBUST_PASS, ROBUST_FAIL)]
        if robust:
            print(f"  {len(robust)} hold across the whole assumed range and do "
                  f"not depend")
            print(f"  on the coefficient at all - which is worth stating, "
                  f"because a")
            print(f"  reader cannot tell the two kinds apart from the number.")
        print(LINE)
    return results


# ==============================================================================
# Phase S2 - break-even points and design rankings
# ==============================================================================
#
# S1 asked whether a verdict survives its assumption. S2 asks a different
# question: does the WINNER change? A ranking that holds across a coefficient's
# whole range is a design decision; one that flips inside it is a coefficient
# decision wearing a design decision's clothes.

STABLE = "STABLE"
PARTIALLY_STABLE = "PARTIALLY STABLE"
RANK_FLIP = "RANK FLIP"
UNRANKABLE = "UNRANKABLE"


def ranking_stability(coefficient_name: str, setter: Callable[[float], None],
                      restore: Callable[[], None], values: List[float],
                      designs: Dict[str, Tuple[str, object]],
                      metric: str = "Latency (ms)",
                      lower_is_better: bool = True) -> Dict:
    """Does the winner change as one coefficient moves?

    Designs that fail their requirements or cannot run are excluded from the
    ranking rather than placed last - a design that does not exist has no
    position, and one that does not ship is not competing for first.
    """
    from .application import APPLICATION_LIBRARY
    from .system import evaluate_system

    rows = []
    try:
        for v in values:
            setter(v)
            scores, excluded = {}, []
            for label, (app_key, cfg) in designs.items():
                r = evaluate_system(APPLICATION_LIBRARY[app_key], cfg)
                if "INFEASIBLE" in r.status:
                    excluded.append((label, "infeasible"))
                    continue
                if not r.passes:
                    excluded.append((label, "fails requirements"))
                    continue
                scores[label] = r.metrics[metric]
            order = sorted(scores, key=scores.get, reverse=not lower_is_better)
            rows.append({"v": v, "order": order, "scores": scores,
                         "excluded": excluded})
    finally:
        restore()

    winners = [r["order"][0] if r["order"] else None for r in rows]
    named = [w for w in winners if w is not None]
    # The ORDER can move while the winner does not, and that is worth saying
    # separately: second place changing is a real result and it is not a
    # different answer to "which should we build".
    orders = {tuple(r["order"]) for r in rows if r["order"]}
    if not named:
        outcome = UNRANKABLE
    elif len(set(named)) == 1 and len(named) == len(winners):
        outcome = STABLE
    elif len(set(named)) == 1:
        outcome = PARTIALLY_STABLE
    else:
        outcome = RANK_FLIP

    return {"coefficient": coefficient_name, "rows": rows,
            "outcome": outcome, "metric": metric,
            "order_changed": len(orders) > 1}


def print_ranking(result: Dict) -> None:
    print(f"\n{LINE}")
    print(f" RANKING STABILITY - {result['coefficient']}")
    print(LINE)
    print(f"  ranked on {result['metric']}, "
          f"lower is better\n")
    head = f"  {result['coefficient'][:22]:<24s}winner            order"
    print(head); print("  " + "-" * (len(head) - 2))
    for r in result["rows"]:
        win = r["order"][0] if r["order"] else "-"
        rest = " > ".join(r["order"]) if r["order"] else "nothing rankable"
        print(f"  {r['v']:<24g}{win:<18s}{rest}")
        if r["excluded"]:
            for label, why in r["excluded"]:
                print(f"  {'':<24s}{'':<18s}({label} excluded: {why})")

    print(f"\n  outcome   {result['outcome']}")
    if result["outcome"] == RANK_FLIP:
        firsts = []
        for r in result["rows"]:
            w = r["order"][0] if r["order"] else None
            if not firsts or firsts[-1][1] != w:
                firsts.append((r["v"], w))
        print(f"  The winner changes inside the range:")
        for v, w in firsts:
            print(f"     from {v:g}: {w or 'nothing rankable'}")
        print(f"\n  A ranking that flips inside a coefficient's range is a")
        print(f"  COEFFICIENT decision wearing a design decision's clothes.")
        print(f"  Quoting the winner without the coefficient states half of "
              f"it.")
    elif result["outcome"] == STABLE:
        print(f"  The same design wins across the whole range, so the choice")
        print(f"  does not rest on this coefficient - which is worth saying,")
        print(f"  because most of the interesting ones do.")
        if result["order_changed"]:
            print(f"\n  The ORDER below first place does change. Second place "
                  f"is a")
            print(f"  real result and it is not an answer to 'which should we")
            print(f"  build', so it does not make this a rank flip.")
    elif result["outcome"] == PARTIALLY_STABLE:
        print(f"  One design wins wherever anything is rankable, but some")
        print(f"  points have nothing to rank - a design that cannot run or")
        print(f"  cannot ship is excluded rather than placed last.")
    print(LINE)


def handoff_break_even(sizes=((320, 240), (640, 480), (1920, 1080),
                              (2592, 1944)),
                       overheads=(0.0, 25.0, 100.0, 250.0, 600.0,
                                  1500.0)) -> Dict:
    """At what input size does moving the preprocessing off the host pay?

    Two costs pull against each other: the host's per-pixel work, which grows
    with the frame, and the hand-off, which does not. Their crossing is a
    frame SIZE, and it moves with the hand-off assumption.
    """
    from .application import APPLICATION_LIBRARY
    from .system import evaluate_system, SystemConfig
    import ppact.preprocess as pp
    import dataclasses

    app = APPLICATION_LIBRARY["industrial_vision"]
    saved = pp.NPU_PREPROCESS_DISPATCH_US
    table = {}
    try:
        for oh in overheads:
            pp.NPU_PREPROCESS_DISPATCH_US = oh
            row = {}
            for w, h in sizes:
                tuned = dataclasses.replace(app, input_pixels=float(w * h),
                                            key="__be__")
                APPLICATION_LIBRARY["__be__"] = tuned
                try:
                    base = SystemConfig("cortex_a78_x4", "npu_32x32",
                                        "LPDDR5", 2,
                                        preprocessing_mode="cpu_only")
                    off = dataclasses.replace(
                        base, preprocessing_mode="isp_and_npu")
                    a = evaluate_system(tuned, base).metrics["Latency (ms)"]
                    b = evaluate_system(tuned, off).metrics["Latency (ms)"]
                    row[(w, h)] = (a, b, b < a)
                finally:
                    APPLICATION_LIBRARY.pop("__be__", None)
            table[oh] = row
    finally:
        pp.NPU_PREPROCESS_DISPATCH_US = saved

    print(f"\n{LINE}")
    print(" OFFLOAD BREAK-EVEN AGAINST HAND-OFF COST")
    print(LINE)
    print("  The host's per-pixel work grows with the frame. The hand-off does")
    print("  not. Where they cross is a frame SIZE, and it moves with an")
    print("  assumption nobody has measured.\n")
    head = f"  {'handoff us':>12s}" + "".join(
        f"{f'{w}x{h}':>14s}" for w, h in sizes)
    print(head); print("  " + "-" * (len(head) - 2))
    for oh, row in table.items():
        line = f"  {oh:>12g}"
        for size in sizes:
            a, b, wins = row[size]
            line += f"{('offload' if wins else 'host'):>14s}"
        print(line)

    print(f"\n  -- reading it ---------------------------------------------")
    flips = []
    for size in sizes:
        winners = [table[oh][size][2] for oh in overheads]
        if len(set(winners)) > 1:
            first_loss = next(oh for oh in overheads
                              if not table[oh][size][2])
            flips.append((size, first_loss))
    if flips:
        for (w, h), oh in flips:
            print(f"     At {w}x{h} the offload wins below {oh:g} us of "
                  f"hand-off")
            print(f"     and loses above it. That is a CONDITIONAL result: "
                  f"which")
            print(f"     design is better depends on a coefficient, not on the "
                  f"design.")
    stable_win = [s for s in sizes
                  if all(table[oh][s][2] for oh in overheads)]
    stable_lose = [s for s in sizes
                   if not any(table[oh][s][2] for oh in overheads)]
    if stable_win:
        print(f"     At {', '.join(f'{w}x{h}' for w, h in stable_win)} the "
              f"offload wins at every")
        print(f"     hand-off cost in the range - a structural result.")
    if stable_lose:
        print(f"     At {', '.join(f'{w}x{h}' for w, h in stable_lose)} the "
              f"host wins at every")
        print(f"     hand-off cost - also structural, in the other direction.")
    print(f"\n  Three kinds of answer in one table: two that do not depend on")
    print(f"  the coefficient and one that does. Only the last needs a "
          f"measured")
    print(f"  hand-off figure before it is quoted.")
    print(LINE)
    return table


def handoff_ranking(pixels: float = 320 * 240,
                    include_dual: bool = True) -> Dict:
    """Design ranking against the hand-off cost, at a chosen frame size.

    At five megapixels the offload wins at any hand-off cost in the range and
    the ranking is STABLE. At a small frame the same three designs change
    order, and which of them is "best" turns out to be a statement about a
    coefficient rather than about the designs.
    """
    from .application import APPLICATION_LIBRARY
    from .system import SystemConfig
    import ppact.preprocess as pp
    import dataclasses

    app = APPLICATION_LIBRARY["industrial_vision"]
    tuned = dataclasses.replace(app, input_pixels=float(pixels), key="__rk__")
    APPLICATION_LIBRARY["__rk__"] = tuned

    base = SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5", 2,
                        preprocessing_mode="cpu_only")
    designs = {
        "host": ("__rk__", base),
        "offload": ("__rk__", dataclasses.replace(
            base, preprocessing_mode="isp_and_npu")),
    }
    if include_dual:
        designs["dual"] = ("__rk__", dataclasses.replace(
            base, secondary_compute="npu_32x32", execution_mode="parallel",
            work_split=0.5))
    saved = pp.NPU_PREPROCESS_DISPATCH_US

    def setter(v):
        pp.NPU_PREPROCESS_DISPATCH_US = v

    def restore():
        pp.NPU_PREPROCESS_DISPATCH_US = saved
        APPLICATION_LIBRARY.pop("__rk__", None)

    return ranking_stability(
        f"hand-off overhead (us) at {int(pixels):,} pixels",
        setter, restore, [0.0, 50.0, 150.0, 400.0, 900.0, 2000.0], designs)


# ==============================================================================
# Coefficient liveness: is every registry entry actually read?
# ==============================================================================
#
# Two failures, opposite in kind:
#
#   DECORATIVE   a coefficient the code never reads. Its presence claims
#                something was considered when it was not.
#   LEAKING      a coefficient that changes a result it has no business
#                touching. A hand-off cost that moves the accuracy is a wire
#                crossed somewhere.
#
# Both need a DECLARED dependency to test against, which is the point: writing
# down what a coefficient should affect is what makes either detectable.

# Memory energy coefficients may affect energy, power, and derived thermal
# results. They must NOT affect latency, throughput, capacity, accuracy or
# cost - which is the cleanest leakage test in the package, because an
# energy-per-bit figure changes what a transfer costs and not how long it
# takes.
COEFFICIENT_DEPENDENCIES = {
    "LPDDR5.energy_pj_per_bit": {
        "module": "ppact.memory", "delta": None, "library_field": True,
        "affects": ("Energy per inference (mJ)", "System power (W)"),
        "must_not_affect": ("Latency (ms)", "Pipeline capacity (inf/s)",
                            "Delivered throughput (inf/s)",
                            "System cost (USD)", "Deployment accuracy (%)",
                            "DRAM traffic (MB)"),
        "config": dict(app="mobile_ai", cpu="cortex_a78_x4",
                       compute="npu_64x64", memory="LPDDR5", devices=4,
                       preprocessing_mode="isp_and_npu"),
    },
    "DUAL_DISPATCH_US": {
        "module": "ppact.system", "delta": 4.0,
        "affects": ("Latency (ms)",),
        "must_not_affect": ("Deployment accuracy (%)", "DRAM traffic (MB)",
                            "Logic silicon (mm2)"),
        "config": dict(app="robot", cpu="cortex_a78_x4", compute="npu_32x32",
                       memory="LPDDR5", devices=4,
                       preprocessing_mode="isp_and_npu",
                       secondary_compute="npu_32x32",
                       execution_mode="parallel", work_split=0.5),
    },
    "HOST_MEMORY_OVERLAP": {
        "module": "ppact.system", "delta": -0.4,
        "affects": ("CPU active (ms)", "Latency (ms)"),
        "must_not_affect": ("Deployment accuracy (%)",
                            "Host DRAM traffic (MB)",
                            "System cost (USD)"),
        "config": dict(app="industrial_vision", cpu="cortex_a78_x4",
                       compute="npu_32x32", memory="LPDDR5", devices=2,
                       preprocessing_mode="cpu_only"),
    },
    "HOST_LOCALITY_EXPOSURE": {
        "module": "ppact.system", "delta": -0.6,
        "affects": ("Host DRAM traffic (MB)", "CPU active (ms)"),
        "must_not_affect": ("Deployment accuracy (%)", "Compute time (ms)",
                            "System cost (USD)"),
        "config": dict(app="industrial_vision", cpu="cortex_a78_x4",
                       compute="npu_32x32", memory="LPDDR5", devices=2,
                       preprocessing_mode="cpu_only"),
    },
    "PARALLEL_SPLIT_EFFICIENCY": {
        "module": "ppact.system", "delta": -0.3,
        "affects": ("Compute time (ms)", "Latency (ms)"),
        "must_not_affect": ("Deployment accuracy (%)", "DRAM traffic (MB)",
                            "System cost (USD)"),
        "config": dict(app="robot", cpu="cortex_a78_x4", compute="npu_32x32",
                       memory="LPDDR5", devices=4,
                       preprocessing_mode="isp_and_npu",
                       secondary_compute="npu_32x32",
                       execution_mode="parallel", work_split=0.5),
    },
    "DUAL_MEMORY_CONTENTION": {
        "module": "ppact.system", "delta": 0.3,
        "affects": ("Memory time (ms)", "Latency (ms)"),
        "must_not_affect": ("Deployment accuracy (%)", "Compute time (ms)",
                            "Logic silicon (mm2)"),
        "config": dict(app="robot", cpu="cortex_a78_x4", compute="npu_32x32",
                       memory="LPDDR5", devices=4,
                       preprocessing_mode="isp_and_npu",
                       secondary_compute="npu_32x32",
                       execution_mode="parallel", work_split=0.5),
    },
    "NPU_PREPROCESS_DISPATCH_US": {
        "module": "ppact.preprocess", "delta": 500.0,
        "affects": ("Latency (ms)",),
        "must_not_affect": ("Deployment accuracy (%)", "System cost (USD)",
                            "Logic silicon (mm2)"),
        "config": dict(app="industrial_vision", cpu="cortex_a78_x4",
                       compute="npu_32x32", memory="LPDDR5", devices=2,
                       preprocessing_mode="isp_and_npu"),
    },
}


def _library_field_liveness(name: str, spec: Dict) -> Dict:
    """Liveness for a field on a library entry rather than a module constant."""
    from .application import APPLICATION_LIBRARY
    from .memory import MEMORY_LIBRARY
    from .system import evaluate_system, SystemConfig
    import dataclasses

    entry, field = name.split(".", 1)
    cfgspec = dict(spec["config"])
    app_key = cfgspec.pop("app")
    cfg = SystemConfig(cfgspec.pop("cpu"), cfgspec.pop("compute"),
                       cfgspec.pop("memory"), cfgspec.pop("devices"),
                       **cfgspec)
    before = evaluate_system(APPLICATION_LIBRARY[app_key], cfg).metrics
    saved = MEMORY_LIBRARY[entry]
    try:
        MEMORY_LIBRARY[entry] = dataclasses.replace(
            saved, **{field: getattr(saved, field) * 1.5})
        after = evaluate_system(APPLICATION_LIBRARY[app_key], cfg).metrics
    finally:
        MEMORY_LIBRARY[entry] = saved
    dead = [m for m in spec["affects"]
            if m in before and abs(before[m] - after[m]) < 1e-12]
    leaks = [m for m in spec["must_not_affect"]
             if m in before and abs(before[m] - after[m]) > 1e-9]
    return {"coefficient": name, "value": getattr(saved, field),
            "delta": getattr(saved, field) * 0.5, "dead": dead,
            "leaks": leaks, "ok": not dead and not leaks}


def coefficient_liveness(verbose: bool = True) -> List[Dict]:
    """Every declared coefficient must move what it claims and nothing else."""
    import importlib
    from .application import APPLICATION_LIBRARY
    from .system import evaluate_system, SystemConfig

    findings = []
    for name, spec in COEFFICIENT_DEPENDENCIES.items():
        if spec.get("library_field"):
            findings.append(_library_field_liveness(name, spec))
            continue
        mod = importlib.import_module(spec["module"])
        cfgspec = dict(spec["config"])
        app_key = cfgspec.pop("app")
        cfg = SystemConfig(cfgspec.pop("cpu"), cfgspec.pop("compute"),
                           cfgspec.pop("memory"), cfgspec.pop("devices"),
                           **cfgspec)
        before = evaluate_system(APPLICATION_LIBRARY[app_key], cfg).metrics
        saved = getattr(mod, name)
        try:
            setattr(mod, name, saved + spec["delta"])
            after = evaluate_system(APPLICATION_LIBRARY[app_key], cfg).metrics
        finally:
            setattr(mod, name, saved)

        dead = [m for m in spec["affects"]
                if m in before and abs(before[m] - after[m]) < 1e-12]
        leaks = [m for m in spec["must_not_affect"]
                 if m in before and abs(before[m] - after[m]) > 1e-9]
        findings.append({"coefficient": name, "value": saved,
                         "delta": spec["delta"], "dead": dead,
                         "leaks": leaks,
                         "ok": not dead and not leaks})

    if verbose:
        print(f"\n{LINE}")
        print(" COEFFICIENT LIVENESS")
        print(LINE)
        print("  Every coefficient must move what it declares and nothing")
        print("  else. A coefficient the code never reads claims something was")
        print("  considered when it was not; one that moves an unrelated")
        print("  result is a wire crossed somewhere.\n")
        head = f"  {'coefficient':<32s}{'nominal':>10s}{'delta':>10s}   verdict"
        print(head); print("  " + "-" * (len(head) - 2))
        for f in findings:
            verdict = ("live" if f["ok"] else
                       ("DECORATIVE" if f["dead"] else "LEAKING"))
            print(f"  {f['coefficient']:<32s}{f['value']:>10g}"
                  f"{f['delta']:>+10g}   {verdict}")
            for m in f["dead"]:
                print(f"  {'':<32s}{'':<20s}   declares {m} and does not move "
                      f"it")
            for m in f["leaks"]:
                print(f"  {'':<32s}{'':<20s}   moves {m}, which it declares it "
                      f"must not")
        bad = [f for f in findings if not f["ok"]]
        print(f"\n  {len(findings) - len(bad)} of {len(findings)} coefficients "
              f"move exactly what they declare.")
        if not bad:
            print("  No decoration and no leakage. The declared dependencies "
                  "are")
            print("  what makes both detectable - a coefficient with no "
                  "declared")
            print("  effect cannot be found to have none.")
        print(LINE)
    return findings


# ==============================================================================
# S-07 - memory energy: the coefficient that must move only some things
# ==============================================================================
#
# Unlike a hand-off cost, an energy-per-bit figure does not change how long
# anything takes. It changes what a transfer COSTS, which moves energy,
# average power, and - as a consequence rather than as an independent finding
# - the thermal verdict.
#
# That makes it the best test for dependency leakage in the package: a
# coefficient which should touch exactly three quantities and must not touch
# six others.

# The first version of this list named "Memory energy (mJ)", which the model
# does not report - the same error the boundary contract caught at 3.76.0,
# and caught the same way: by requiring that a declaration name something
# real.
MEMORY_ENERGY_MAY_AFFECT = ("Dynamic energy per inference (mJ)",
                            "Energy per inference (mJ)",
                            "System power (W)")
MEMORY_ENERGY_MUST_NOT_AFFECT = ("Latency (ms)", "Pipeline capacity (inf/s)",
                                 "Delivered throughput (inf/s)",
                                 "Compute time (ms)", "Memory time (ms)",
                                 "System cost (USD)",
                                 "Deployment accuracy (%)",
                                 "DRAM traffic (MB)")


def memory_energy_common_scale(scales=(0.7, 0.85, 1.0, 1.15, 1.3)) -> Dict:
    """S-07A: every memory's energy moved by the SAME factor.

    Nothing about time or money may move. If anything does, a coefficient is
    wired into a quantity it has no business touching - and a common scale is
    the cleanest way to see it, because a relative change could plausibly
    reorder something and a common one cannot.
    """
    from .application import APPLICATION_LIBRARY
    from .memory import MEMORY_LIBRARY
    from .system import evaluate_system, SystemConfig
    import dataclasses

    cases = {
        "memory-bound mobile": ("mobile_ai", SystemConfig(
            "cortex_a78_x4", "npu_64x64", "LPDDR5", 4,
            preprocessing_mode="isp_and_npu")),
        "compute-bound inspection": ("industrial_vision", SystemConfig(
            "cortex_a78_x4", "npu_32x32", "LPDDR5", 2,
            preprocessing_mode="isp_and_npu")),
    }
    saved = {k: v for k, v in MEMORY_LIBRARY.items()}
    rows = []
    try:
        for sc in scales:
            for key, spec in saved.items():
                MEMORY_LIBRARY[key] = dataclasses.replace(
                    spec, energy_pj_per_bit=spec.energy_pj_per_bit * sc)
            entry = {"scale": sc, "cases": {}}
            for label, (app_key, cfg) in cases.items():
                m = evaluate_system(APPLICATION_LIBRARY[app_key], cfg).metrics
                entry["cases"][label] = m
            rows.append(entry)
    finally:
        for k, v in saved.items():
            MEMORY_LIBRARY[k] = v

    print(f"\n{LINE}")
    print(" S-07A  MEMORY ENERGY, ALL DEVICES SCALED TOGETHER")
    print(LINE)
    print("  An energy-per-bit figure does not change how long anything")
    print("  takes. It changes what a transfer COSTS. Nothing about time or")
    print("  money may move here, and a common scale is the cleanest way to")
    print("  see it - a relative change could plausibly reorder something and")
    print("  a common one cannot.\n")

    for label in cases:
        print(f"  {label}")
        head = (f"    {'scale':>7s}{'energy/job mJ':>15s}{'system W':>11s}"
                f"{'latency ms':>13s}{'cost USD':>11s}")
        print(head); print("    " + "-" * (len(head) - 4))
        for r in rows:
            m = r["cases"][label]
            print(f"    {r['scale']:>7g}{m['Energy per inference (mJ)']:>15.3f}"
                  f"{m['System power (W)']:>11.3f}{m['Latency (ms)']:>13.4f}"
                  f"{m['System cost (USD)']:>11.3f}")
        print()

    leaks = []
    for label in cases:
        base = rows[0]["cases"][label]
        for r in rows[1:]:
            m = r["cases"][label]
            for metric in MEMORY_ENERGY_MUST_NOT_AFFECT:
                if metric in base and abs(base[metric] - m[metric]) > 1e-9:
                    leaks.append((label, metric, r["scale"]))
    moved = []
    for label in cases:
        base, last = rows[0]["cases"][label], rows[-1]["cases"][label]
        for metric in MEMORY_ENERGY_MAY_AFFECT:
            if metric in base and abs(base[metric] - last[metric]) > 1e-9:
                moved.append((label, metric))

    print(f"  -- what moved and what did not ----------------------------")
    print(f"     declared to move, and did:  "
          f"{len(moved)} of {len(cases) * len(MEMORY_ENERGY_MAY_AFFECT)}")
    if leaks:
        print(f"     LEAKAGE: {len(leaks)} case(s) where a quantity that must "
              f"not move did")
        for label, metric, sc in leaks[:5]:
            print(f"       {label}: {metric} at scale {sc:g}")
    else:
        print(f"     no leakage: latency, capacity, delivered throughput,")
        print(f"     traffic, cost and accuracy are identical at every scale,")
        print(f"     to the last decimal place the model carries.")
    print(f"\n     The thermal verdict may follow from the power. That is a")
    print(f"     CONSEQUENCE, not a second finding, and is not counted as an")
    print(f"     independent sensitivity.")
    print(LINE)
    return {"rows": rows, "leaks": leaks, "moved": moved}


def memory_energy_relative(scales=(0.6, 0.8, 1.0, 1.2, 1.4, 1.6)) -> Dict:
    """S-07B: only HBM's energy moves. Rankings may legitimately reorder."""
    from .application import APPLICATION_LIBRARY
    from .memory import MEMORY_LIBRARY
    from .system import evaluate_system, SystemConfig
    import dataclasses

    app_key = "mobile_ai"
    designs = {
        "LPDDR5 x8": SystemConfig("cortex_a78_x4", "npu_64x64", "LPDDR5", 8,
                                  preprocessing_mode="isp_and_npu"),
        "HBM3E x1": SystemConfig("cortex_a78_x4", "npu_64x64", "HBM3E", 1,
                                 preprocessing_mode="isp_and_npu"),
    }
    saved = MEMORY_LIBRARY["HBM3E"]
    rows = []
    try:
        for sc in scales:
            MEMORY_LIBRARY["HBM3E"] = dataclasses.replace(
                saved, energy_pj_per_bit=saved.energy_pj_per_bit * sc)
            entry = {"scale": sc, "designs": {}}
            for label, cfg in designs.items():
                r = evaluate_system(APPLICATION_LIBRARY[app_key], cfg)
                entry["designs"][label] = {
                    "energy": r.metrics["Energy per inference (mJ)"],
                    "power": r.metrics["System power (W)"],
                    "power_gate": r.gate.get("power", True),
                    "latency": r.metrics["Latency (ms)"],
                }
            rows.append(entry)
    finally:
        MEMORY_LIBRARY["HBM3E"] = saved

    print(f"\n{LINE}")
    print(" S-07B  MEMORY ENERGY, HBM ONLY")
    print(LINE)
    print("  Now a ranking CAN legitimately reorder, because the two memories")
    print("  are no longer being moved together.\n")
    head = (f"  {'HBM scale':>10s}{'LPDDR mJ':>11s}{'HBM mJ':>10s}"
            f"{'energy winner':>16s}{'LPDDR W':>10s}{'HBM W':>9s}"
            f"{'HBM power gate':>16s}")
    print(head); print("  " + "-" * (len(head) - 2))
    energy_winners, power_verdicts = [], []
    for r in rows:
        lp, hb = r["designs"]["LPDDR5 x8"], r["designs"]["HBM3E x1"]
        win = "LPDDR5" if lp["energy"] < hb["energy"] else "HBM3E"
        energy_winners.append(win)
        power_verdicts.append(hb["power_gate"])
        print(f"  {r['scale']:>10g}{lp['energy']:>11.2f}{hb['energy']:>10.2f}"
              f"{win:>16s}{lp['power']:>10.2f}{hb['power']:>9.2f}"
              f"{('PASS' if hb['power_gate'] else 'FAIL'):>16s}")

    print(f"\n  -- reading it ---------------------------------------------")
    if len(set(energy_winners)) > 1:
        flip = next(r["scale"] for r, w in zip(rows, energy_winners)
                    if w != energy_winners[0])
        print(f"     ENERGY PER JOB: CONDITIONAL. The winner changes at a "
              f"scale of")
        print(f"     {flip:g} - which memory is more efficient per job depends "
              f"on a")
        print(f"     coefficient, not on the design.")
    else:
        print(f"     ENERGY PER JOB: the same memory wins at every scale.")
    if all(power_verdicts):
        print(f"     AVERAGE POWER: robust PASS across the whole range.")
    elif not any(power_verdicts):
        print(f"     AVERAGE POWER: ROBUST FAIL across the whole range. No "
              f"energy")
        print(f"     figure in this range makes the HBM design fit the power")
        print(f"     budget.")
    else:
        print(f"     AVERAGE POWER: conditional.")
    if len(set(energy_winners)) > 1 and not any(power_verdicts):
        print(f"\n     The two answer DIFFERENTLY. Energy per job depends on "
              f"the")
        print(f"     assumption and average power does not, so a report giving "
              f"one")
        print(f"     number for 'efficiency' would be right about half of it "
              f"and")
        print(f"     silent about which half.")
    print(LINE)
    return {"rows": rows, "energy_winners": energy_winners,
            "power_verdicts": power_verdicts}
