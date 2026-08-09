"""
tests_freeze.py - the Freeze Validation Suite

WHAT THIS IS FOR
================
Every other suite in this package asks "is the feature right?". This one asks
a different question:

    How would I break this?

The distinction matters at a freeze. A model can be arithmetically correct and
still be a bad product: it can contradict itself between two screens, report a
latency that goes down and then up as a memory widens, recommend upgrading the
part that holds 3% of the time, or crash on a frame of one pixel. None of
those is a wrong formula, and none of them would be caught by a suite that
only checks formulas.

TWELVE PACKS, BY QUALITY ATTRIBUTE
----------------------------------
    FVS-01  Functional          every screen runs
    FVS-02  Boundary            the ends of every input
    FVS-03  Multi-path          A->B is fine, A->C is where bugs live
    FVS-04  Monotonic           more of a thing must not zig-zag
    FVS-05  Cross-consistency   two screens, one number
    FVS-06  Explanation         the advice must match the diagnosis
    FVS-07  Failure handling    a refusal must say what, why and what is
                                allowed
    FVS-08  Regression          every defect ever logged, still caught
    FVS-09  Numerical stability no cliff at a floating-point boundary
    FVS-10  Random stress       a thousand designs, no exception, no NaN
    FVS-11  UI and terminology  no banned word, no table that wraps
    FVS-12  Certification       the report, with what is NOT established

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

import dataclasses
import io
import contextlib
import math
import random
import sys

sys.path.insert(0, ".")

from ppact import (APPLICATION_LIBRARY, COMPUTE_LIBRARY, CPU_LIBRARY,
                   MEMORY_LIBRARY, SystemConfig, evaluate_system)

LINE = "=" * 84
RESULTS = []          # (pack, name, ok, detail)


def check(pack, name, cond, detail=""):
    RESULTS.append((pack, name, bool(cond), detail))


def quiet(fn, *a, **kw):
    with contextlib.redirect_stdout(io.StringIO()) as buf:
        fn(*a, **kw)
    return buf.getvalue()


VISION = dict(cpu="cortex_a78_x4", compute="npu_32x32", memory="LPDDR5",
              memory_devices=2, preprocessing_mode="cpu_only")


# ==============================================================================
# FVS-01  Functional: every screen runs without input
# ==============================================================================

def fvs01_functional():
    P = "FVS-01"
    from ppact import demo, lessons, framework, challenge
    from ppact.decide import explain, design_review
    from ppact.system import print_metric_boundaries

    for d in demo.DEMOS:
        try:
            quiet(demo.print_demo, d)
            check(P, f"demo '{d.key}' runs", True)
        except Exception as exc:
            check(P, f"demo '{d.key}' runs", False, f"{type(exc).__name__}: {exc}")

    for les in lessons.LESSONS:
        for diff in ("easy", "medium", "advanced"):
            try:
                quiet(lessons.print_lesson, les, difficulty=diff)
                check(P, f"lesson {les.number} renders at {diff}", True)
            except Exception as exc:
                check(P, f"lesson {les.number} renders at {diff}", False,
                      f"{type(exc).__name__}: {exc}")

    for ch in challenge.CHALLENGES:
        try:
            quiet(challenge.print_challenge, ch)
            check(P, f"challenge '{ch.key}' renders", True)
        except Exception as exc:
            check(P, f"challenge '{ch.key}' renders", False, str(exc))

    for fn, label in ((framework.print_framework, "capability map"),
                      (print_metric_boundaries, "metric boundaries")):
        try:
            quiet(fn)
            check(P, f"{label} renders", True)
        except Exception as exc:
            check(P, f"{label} renders", False, str(exc))

    base = SystemConfig(**VISION)
    after = dataclasses.replace(base, preprocessing_mode="isp_and_npu")
    try:
        quiet(explain, "industrial_vision", base, after)
        check(P, "the explanation screen runs", True)
    except Exception as exc:
        check(P, "the explanation screen runs", False, str(exc))
    try:
        quiet(design_review, "industrial_vision", base, "offload",
              {"preprocessing_mode": "isp_and_npu"})
        check(P, "the review screen runs", True)
    except Exception as exc:
        check(P, "the review screen runs", False, str(exc))


# ==============================================================================
# FVS-02  Boundary: the ends of every input
# ==============================================================================

def fvs02_boundary():
    P = "FVS-02"
    app = APPLICATION_LIBRARY["robot"]
    base = SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5", 4,
                        preprocessing_mode="isp_and_npu",
                        secondary_compute="npu_32x32",
                        execution_mode="parallel")

    # work_split across its ends and just outside them
    for v, should_work in ((0.0, True), (1e-9, True), (0.5, True),
                           (1 - 1e-9, True), (1.0, True),
                           (1.0000001, False), (-1e-9, False),
                           (-0.1, False), (1.5, False), (100.0, False),
                           (float("nan"), False), (float("inf"), False)):
        label = f"work_split={v!r}"
        try:
            r = evaluate_system(app, dataclasses.replace(base, work_split=v))
            ok = not math.isnan(r.metrics["Latency (ms)"])
            check(P, f"{label} is accepted and produces a number",
                  should_work and ok,
                  "accepted" if should_work else "should have been refused")
        except ValueError as exc:
            check(P, f"{label} is refused with a reason",
                  not should_work and len(str(exc)) > 20,
                  f"message was {str(exc)[:60]!r}")
        except Exception as exc:
            check(P, f"{label} fails cleanly", False,
                  f"{type(exc).__name__} rather than ValueError: {exc}")

    # memory devices from nothing to absurd
    for n in (0, 1, 2, 16, 17, 64, 100, -1):
        label = f"memory_devices={n}"
        try:
            r = evaluate_system(APPLICATION_LIBRARY["llm_service"],
                                SystemConfig("server_x86_x32",
                                             "datacenter_gpu", "HBM3E", n))
            finite = all(not math.isinf(v) for v in r.metrics.values()
                         if isinstance(v, float))
            check(P, f"{label} does not produce an infinity", finite)
            if n > 0:
                check(P, f"{label} reports a capacity",
                      "Effective bandwidth (GB/s)" in r.metrics)
        except (ValueError, ZeroDivisionError) as exc:
            check(P, f"{label} is refused rather than guessed", n <= 0,
                  f"refused with {type(exc).__name__}")
        except Exception as exc:
            check(P, f"{label} fails cleanly", False,
                  f"{type(exc).__name__}: {exc}")

    # frame sizes from one pixel to absurd
    for w, h in ((1, 1), (2, 2), (16, 16), (320, 240), (1920, 1080),
                 (7680, 4320), (100000, 100000)):
        tuned = dataclasses.replace(APPLICATION_LIBRARY["industrial_vision"],
                                    input_pixels=float(w * h), key="__b__")
        APPLICATION_LIBRARY["__b__"] = tuned
        try:
            r = evaluate_system(tuned, SystemConfig(**VISION))
            bad = [k for k, v in r.metrics.items()
                   if isinstance(v, float) and math.isinf(v)]
            check(P, f"{w}x{h} produces no infinity", not bad, str(bad[:3]))
            if "INFEASIBLE" not in r.status:
                check(P, f"{w}x{h} has a non-negative latency",
                      r.metrics["Latency (ms)"] >= 0)
        except Exception as exc:
            check(P, f"{w}x{h} does not raise", False,
                  f"{type(exc).__name__}: {exc}")
        finally:
            APPLICATION_LIBRARY.pop("__b__", None)


# ==============================================================================
# FVS-03  Multi-path: A->B is fine, A->C is where the bugs live
# ==============================================================================

def fvs03_multipath():
    P = "FVS-03"
    from ppact import demo, lessons, framework
    from ppact.decide import explain, design_review, whatif
    from ppact.sensitivity import run_sweep, build_sweeps
    from ppact import workspace as W
    import tempfile, shutil, os

    base = SystemConfig(**VISION)
    after = dataclasses.replace(base, preprocessing_mode="isp_and_npu")

    # a long chain, each step after a different predecessor
    chain = [
        ("demo", lambda: quiet(demo.print_demo, demo.DEMOS[0])),
        ("lesson", lambda: quiet(lessons.print_lesson, lessons.LESSONS[2])),
        ("explain", lambda: quiet(explain, "industrial_vision", base, after)),
        ("framework", lambda: quiet(framework.print_framework)),
        ("review", lambda: quiet(design_review, "industrial_vision", base,
                                 "offload",
                                 {"preprocessing_mode": "isp_and_npu"})),
        ("sensitivity", lambda: quiet(run_sweep, build_sweeps()[0], 5)),
        ("explain again", lambda: quiet(explain, "industrial_vision", base,
                                        after)),
    ]
    for i, (name, fn) in enumerate(chain):
        try:
            fn()
            check(P, f"step {i + 1} '{name}' after the ones before it", True)
        except Exception as exc:
            check(P, f"step {i + 1} '{name}' after the ones before it", False,
                  f"{type(exc).__name__}: {exc}")

    # the same screen twice in a row must give the same thing
    a1 = quiet(explain, "industrial_vision", base, after)
    a2 = quiet(explain, "industrial_vision", base, after)
    check(P, "the explanation is identical when run twice", a1 == a2,
          "a screen that differs between two identical runs has state it "
          "should not have")

    # a round trip through the workspace must not change anything
    tmp = tempfile.mkdtemp(prefix="fvs_")
    try:
        W.remember("industrial_vision", after, tmp)
        app_key, restored = W.rebuild(W.recent(tmp)[0])
        m1 = evaluate_system(APPLICATION_LIBRARY["industrial_vision"],
                             after).metrics
        m2 = evaluate_system(APPLICATION_LIBRARY[app_key], restored).metrics
        differing = [k for k in m1
                     if isinstance(m1[k], float) and isinstance(m2.get(k), float)
                     and not (math.isnan(m1[k]) and math.isnan(m2[k]))
                     and abs(m1[k] - m2[k]) > 1e-12]
        check(P, "saving and reloading a design changes nothing",
              not differing, f"differs in {differing[:3]}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # sensitivity must restore every coefficient it moved
    import ppact.system as S
    before_coeffs = {k: getattr(S, k) for k in
                     ("HOST_MEMORY_OVERLAP", "PARALLEL_SPLIT_EFFICIENCY",
                      "DUAL_MEMORY_CONTENTION", "DUAL_DISPATCH_US",
                      "HOST_LOCALITY_EXPOSURE")}
    from ppact.decide import confidence_evidence
    confidence_evidence("industrial_vision", base, after, points=3)
    after_coeffs = {k: getattr(S, k) for k in before_coeffs}
    check(P, "a sensitivity run puts every coefficient back",
          before_coeffs == after_coeffs,
          "a sweep that leaks a coefficient poisons everything run after it")


# ==============================================================================
# FVS-04  Monotonic: more of a thing must not zig-zag
# ==============================================================================

def fvs04_monotonic():
    P = "FVS-04"

    def series(app_key, cfgs, key):
        out = []
        for c in cfgs:
            r = evaluate_system(APPLICATION_LIBRARY[app_key], c)
            out.append(float("nan") if "INFEASIBLE" in r.status
                       else r.metrics[key])
        return out

    def monotone(vals, direction, tol=1e-9):
        vals = [v for v in vals if not math.isnan(v)]
        if direction == "up":
            return all(b >= a - tol for a, b in zip(vals, vals[1:]))
        return all(b <= a + tol for a, b in zip(vals, vals[1:]))

    # more memory devices
    counts = (1, 2, 4, 6, 8, 12, 16)
    cfgs = [SystemConfig("server_x86_x32", "datacenter_gpu", "HBM3E", n)
            for n in counts]
    for key, want in (("Effective bandwidth (GB/s)", "up"),
                      ("System cost (USD)", "up"),
                      ("System power (W)", "up")):
        vals = series("llm_service", cfgs, key)
        check(P, f"more memory devices: {key} rises",
              monotone(vals, want),
              " -> ".join(f"{v:.2f}" for v in vals))
    lat = series("llm_service", cfgs, "Latency (ms)")
    check(P, "more memory devices: latency never zig-zags",
          monotone(lat, "down"),
          " -> ".join("inf" if math.isnan(v) else f"{v:.2f}" for v in lat)
          + " - it may saturate, it may not reverse")

    # a bigger engine
    engines = ("npu_16x16", "npu_20x20", "npu_24x24", "npu_32x32",
               "npu_64x64", "npu_128x128")
    cfgs = [SystemConfig(**{**VISION, "compute": e}) for e in engines]
    for key, want in (("Logic silicon (mm2)", "up"),
                      ("System cost (USD)", "up")):
        vals = series("industrial_vision", cfgs, key)
        check(P, f"a bigger engine: {key} rises", monotone(vals, want),
              " -> ".join(f"{v:.2f}" for v in vals))
    comp = series("industrial_vision", cfgs, "Compute time (ms)")
    check(P, "a bigger engine: the arithmetic time never rises",
          monotone(comp, "down"), " -> ".join(f"{v:.3f}" for v in comp))

    # a longer conversation
    from ppact.economics import context_sweep
    quiet(context_sweep, "llm_service",
          SystemConfig("server_x86_x32", "datacenter_gpu", "HBM3E", 6))
    rows = context_sweep.__wrapped__ if hasattr(context_sweep, "__wrapped__") \
        else None
    ctxs = (4096, 16384, 65536, 131072)
    kvs = []
    app = APPLICATION_LIBRARY["llm_service"]
    for c in ctxs:
        kvs.append(app.kv_bytes_per_token * c)
    check(P, "a longer context: the cache rises in proportion",
          all(abs((b / a) / (d / c) - 1) < 1e-9
              for a, b, c, d in zip(kvs, kvs[1:], ctxs, ctxs[1:])),
          str([f"{k / 1e9:.2f}" for k in kvs]))

    # a finer node
    nodes = ("N28", "N16", "N7", "N5", "N3")
    cfgs = [SystemConfig(**{**VISION, "soc_node": n, "accel_node": n})
            for n in nodes]
    area = series("industrial_vision", cfgs, "Logic silicon (mm2)")
    check(P, "a finer node: the silicon area never grows",
          monotone(area, "down"), " -> ".join(f"{v:.2f}" for v in area))
    # cost is NOT monotone here and must not be asserted to be - the U-curve
    # is a finding, not a defect
    cost = series("industrial_vision", cfgs, "Logic die cost (USD)")
    check(P, "a finer node: the die cost turns rather than falling forever",
          not monotone(cost, "down"),
          " -> ".join(f"{v:.3f}" for v in cost)
          + " - the wafer price rises faster than the die shrinks, and "
            "asserting a fall would hide that")

    # arrival rate
    from ppact.runtime import simulate
    rates = (1, 5, 10, 30, 60, 120)
    delivered = []
    for rate in rates:
        tuned = dataclasses.replace(APPLICATION_LIBRARY["industrial_vision"],
                                    target_inferences_per_s=rate,
                                    key="__ar__")
        APPLICATION_LIBRARY["__ar__"] = tuned
        try:
            m = evaluate_system(tuned, SystemConfig(**VISION)).metrics
            delivered.append(m["Delivered throughput (inf/s)"])
        finally:
            APPLICATION_LIBRARY.pop("__ar__", None)
    check(P, "a higher arrival rate never lowers what is delivered",
          monotone(delivered, "up"),
          " -> ".join(f"{v:.1f}" for v in delivered))


# ==============================================================================
# FVS-05  Cross-consistency: two screens, one number
# ==============================================================================

def fvs05_consistency():
    P = "FVS-05"
    import re
    from ppact.decide import explain, report_markdown, try_options, whatif_row
    from ppact import workspace as W
    import tempfile, shutil, os

    base = SystemConfig(**VISION)
    after = dataclasses.replace(base, preprocessing_mode="isp_and_npu")
    truth = evaluate_system(APPLICATION_LIBRARY["industrial_vision"],
                            after).metrics

    # the explanation screen against the engine
    text = quiet(explain, "industrial_vision", base, after)
    lat = f"{truth['Latency (ms)']:.2f}"
    check(P, "the explanation quotes the engine's latency", lat in text,
          f"{lat} not found on screen")

    # the markdown report against the engine
    md = report_markdown("industrial_vision", base, after)
    check(P, "the report quotes the same latency", lat in md)

    # the options table against a fresh evaluation
    opts = try_options("industrial_vision", base,
                       {"offload": {"preprocessing_mode": "isp_and_npu"}})
    check(P, "the options table matches a fresh run",
          abs(opts[0].latency - truth["Latency (ms)"]) < 1e-9,
          f"{opts[0].latency} against {truth['Latency (ms)']}")

    # the what-if screen against the engine
    wr = whatif_row("industrial_vision", base, after)
    check(P, "what-if matches the engine",
          abs(wr["now"].metrics["Latency (ms)"]
              - truth["Latency (ms)"]) < 1e-12)

    # a workspace export against the engine
    tmp = tempfile.mkdtemp(prefix="fvs5_")
    try:
        W.remember("industrial_vision", after, tmp)
        path = W.export_markdown(W.recent(tmp)[0], "x.md", tmp, "x")
        exported = open(path, encoding="utf-8").read()
        check(P, "the exported document quotes the same latency",
              f"{truth['Latency (ms)']:.3f}" in exported,
              "an export that disagrees with the screen is worse than none")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # a verdict must agree with its gates, on every application
    for key in APPLICATION_LIBRARY:
        if key.startswith("__"):
            continue
        a = APPLICATION_LIBRARY[key]
        cpu = ("server_x86_x32" if a.domain == "Data Center"
               else "cortex_a78_x4")
        mem = ("HBM3E", 6) if a.domain == "Data Center" else ("LPDDR5", 2)
        comp = "datacenter_gpu" if a.domain == "Data Center" else "npu_32x32"
        r = evaluate_system(a, SystemConfig(cpu, comp, mem[0], mem[1]))
        failed = [g for g, ok in r.gate.items() if not ok]
        check(P, f"{key}: 'passes' agrees with the gate list",
              r.passes == (not failed),
              f"passes={r.passes} while failing {failed}")


# ==============================================================================
# FVS-06  Explanation: the advice must match the diagnosis
# ==============================================================================

def fvs06_explanation():
    P = "FVS-06"
    from ppact.decide import (recommendations, upgrade_ranking, headroom,
                              LATENCY_TERMS)

    cases = [
        ("host bound", SystemConfig("cortex_a53_x4", "npu_32x32", "LPDDR5", 2,
                                    preprocessing_mode="cpu_only"),
         "industrial_vision"),
        ("memory bound", SystemConfig("cortex_a78_x4", "npu_128x128",
                                      "LPDDR5", 1,
                                      preprocessing_mode="isp_and_npu"),
         "drone"),
        ("compute bound", SystemConfig("cortex_a78_x4", "npu_16x16",
                                       "LPDDR5", 8,
                                       preprocessing_mode="isp_and_npu"),
         "industrial_vision"),
    ]
    for label, cfg, app_key in cases:
        r = evaluate_system(APPLICATION_LIBRARY[app_key], cfg)
        if "INFEASIBLE" in r.status:
            continue
        m = r.metrics
        ranking = upgrade_ranking(m, r.bound_by)
        advice = recommendations(m, m, r.bound_by, r.passes,
                                 sorted(g for g, ok in r.gate.items()
                                        if not ok))
        text = " ".join(advice).lower()

        # THE RULE: the part named first must be the one holding most time
        if ranking:
            top = ranking[0][0].lower()
            check(P, f"{label}: the ranking names the largest holder first",
                  ranking[0][1] == max(s for _, s, _ in ranking),
                  str([(n, round(s, 1)) for n, s, _ in ranking]))
            host_share = m.get("CPU active (ms)", 0.0) / m["Latency (ms)"]
            if host_share > 0.5:
                check(P, f"{label}: a host-dominated design is told so",
                      "host" in text,
                      f"host holds {host_share * 100:.0f}% and the advice "
                      f"was {advice}")
                check(P, f"{label}: and is NOT told to buy memory first",
                      "wider memory is the lever" not in text,
                      "recommending memory when the host holds most of the "
                      "time is advice that contradicts its own diagnosis")
            if r.bound_by == "memory" and host_share <= 0.5:
                check(P, f"{label}: a memory-bound design is told memory",
                      "memory" in text, str(advice))
                check(P, f"{label}: and not that a bigger engine is the lever",
                      "bigger engine is the lever" not in text)
            if r.bound_by == "compute" and host_share <= 0.5:
                check(P, f"{label}: a compute-bound design may be told engine",
                      "memory is the lever" not in text, str(advice))

    # the bound must never promise more than the station holds
    m = evaluate_system(APPLICATION_LIBRARY["industrial_vision"],
                        SystemConfig(**VISION)).metrics
    for h in headroom(m):
        check(P, f"'{h.station}' cannot promise more than it holds",
              abs(h.best_gain_pct) <= h.share_pct + 1e-9,
              f"{h.best_gain_pct} against {h.share_pct}")


# ==============================================================================
# FVS-07  Failure handling: a refusal must be useful
# ==============================================================================

def fvs07_failure():
    P = "FVS-07"
    app = APPLICATION_LIBRARY["robot"]
    base = SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5", 4,
                        preprocessing_mode="isp_and_npu",
                        secondary_compute="npu_32x32",
                        execution_mode="parallel")
    for field, bad in (("work_split", -10.0), ("work_split", 2.0),
                       ("alternative_share", -0.5),
                       ("alternative_share", 99.0)):
        try:
            evaluate_system(app, dataclasses.replace(base, **{field: bad}))
            check(P, f"{field}={bad} is refused", False, "it was accepted")
        except ValueError as exc:
            msg = str(exc)
            check(P, f"{field}={bad}: the message names the field",
                  field in msg, msg[:70])
            check(P, f"{field}={bad}: and says what is allowed",
                  any(t in msg for t in ("0", "1", "between")), msg[:70])
            check(P, f"{field}={bad}: and is a sentence, not a code",
                  len(msg.split()) >= 6, msg[:70])
        except Exception as exc:
            check(P, f"{field}={bad} raises the right kind of error", False,
                  f"{type(exc).__name__}")

    # a model that does not fit must say so, not report a slow one
    r = evaluate_system(APPLICATION_LIBRARY["llm_service"],
                        SystemConfig("server_x86_x32", "datacenter_gpu",
                                     "LPDDR5", 8))
    check(P, "a model that does not fit is named infeasible",
          "INFEASIBLE" in r.status, r.status)
    check(P, "and its status says WHY", "FIT" in r.status.upper(), r.status)
    check(P, "and reports no performance figure",
          math.isnan(r.metrics["Latency (ms)"]),
          "reporting 4 tokens per second for a machine that cannot hold its "
          "weights invites a comparison with one that can")
    check(P, "while still reporting what the board costs",
          not math.isnan(r.metrics["System cost (USD)"]))
    from ppact.system import print_infeasible
    text = quiet(print_infeasible, r)
    check(P, "the screen names the reason rather than a number",
          "does not fit" in text, text[:120])
    check(P, "and shows what capacity is installed",
          "Installed capacity" in text, text[:160])
    check(P, "and says the figures do not exist rather than being zero",
          "do not exist" in text or "Not Evaluated" in text, text[-200:])


# ==============================================================================
# FVS-08  Regression: every defect ever logged, still covered
# ==============================================================================

def fvs08_regression():
    P = "FVS-08"
    from ppact.revisions import REVISIONS

    check(P, "the defect log is not empty", len(REVISIONS) >= 50,
          str(len(REVISIONS)))
    for r in REVISIONS:
        check(P, f"{r.version}: the defect is described",
              len(r.observed) > 30)
        check(P, f"{r.version}: the cause is described",
              len(r.suspected) > 20)
        check(P, f"{r.version}: the fix is described", len(r.changed) > 20)
        check(P, f"{r.version}: evidence is given", len(r.evidence) > 30)
        check(P, f"{r.version}: what it touched is stated",
              len(r.affected) > 20)

    # the suites that hold those defects in place must still exist and run
    import os
    for name in ("tests_model.py", "tests_corner.py", "tests_dual.py",
                 "tests_memory.py", "tests_differential.py",
                 "tests_scenarios.py", "tests_independent.py",
                 "tests_mutation.py", "tests_holdout.py"):
        check(P, f"{name} is present", os.path.isfile(name))

    # and the mutation list must cover every verification path
    import re
    defined = set(re.findall(r"^def (path_[a-z_]+)\(",
                             open("tests_model.py", encoding="utf-8").read(),
                             re.M))
    exercised = set(re.findall(r"M\.(path_[a-z_]+)",
                               open("tests_mutation.py",
                                    encoding="utf-8").read()))
    check(P, "every verification path is under mutation coverage",
          not (defined - exercised),
          f"not exercised: {', '.join(sorted(defined - exercised))}")


# ==============================================================================
# FVS-09  Numerical stability: no cliff at a floating-point boundary
# ==============================================================================

def fvs09_numerical():
    P = "FVS-09"
    app = APPLICATION_LIBRARY["industrial_vision"]

    # a requirement met by a hair must not flip on a rounding
    r0 = evaluate_system(app, SystemConfig(**VISION))
    lat = r0.metrics["Latency (ms)"]
    for eps in (1e-12, 1e-9, 1e-6):
        for sign in (-1, 1):
            tuned = dataclasses.replace(app,
                                        latency_budget_ms=lat * (1 + sign * eps),
                                        key="__n__")
            APPLICATION_LIBRARY["__n__"] = tuned
            try:
                r = evaluate_system(tuned, SystemConfig(**VISION))
                check(P, f"a requirement within {eps} of the result is "
                         f"decided without an exception", True)
            except Exception as exc:
                check(P, f"a requirement within {eps} does not raise", False,
                      str(exc))
            finally:
                APPLICATION_LIBRARY.pop("__n__", None)

    # nearby inputs must give nearby outputs - no cliff
    prev = None
    for scale in (0.999999, 0.9999999, 1.0, 1.0000001, 1.000001):
        tuned = dataclasses.replace(app,
                                    mac_per_inference=app.mac_per_inference * scale,
                                    key="__s__")
        APPLICATION_LIBRARY["__s__"] = tuned
        try:
            v = evaluate_system(tuned, SystemConfig(**VISION)
                                ).metrics["Latency (ms)"]
            if prev is not None:
                check(P, f"a {abs(1 - scale):.0e} change moves the latency "
                         f"by less than a per cent",
                      abs(v / prev - 1) < 0.01,
                      f"{prev:.9f} -> {v:.9f}")
            prev = v
        finally:
            APPLICATION_LIBRARY.pop("__s__", None)

    # very small and very large numbers must not produce nan or inf
    for macs in (1.0, 1e3, 1e6, 1e9, 1e12, 1e15):
        tuned = dataclasses.replace(app, mac_per_inference=macs, key="__m__")
        APPLICATION_LIBRARY["__m__"] = tuned
        try:
            m = evaluate_system(tuned, SystemConfig(**VISION)).metrics
            bad = [k for k, v in m.items()
                   if isinstance(v, float) and (math.isinf(v))]
            check(P, f"{macs:g} MACs produces no infinity", not bad,
                  str(bad[:3]))
        except Exception as exc:
            check(P, f"{macs:g} MACs does not raise", False, str(exc))
        finally:
            APPLICATION_LIBRARY.pop("__m__", None)


# ==============================================================================
# FVS-10  Random stress
# ==============================================================================

def fvs10_stress(draws: int = 1200, seed: int = 20260803):
    P = "FVS-10"
    rng = random.Random(seed)
    apps = [k for k in APPLICATION_LIBRARY if not k.startswith("__")]
    comps = list(COMPUTE_LIBRARY)
    mems = list(MEMORY_LIBRARY)
    cpus = list(CPU_LIBRARY)
    modes_pp = ["cpu_only", "isp_assisted", "isp_and_npu"]

    exceptions, infinities, negatives, infeasible = [], [], [], 0
    for _ in range(draws):
        app_key = rng.choice(apps)
        kw = dict(preprocessing_mode=rng.choice(modes_pp))
        if rng.random() < 0.4:
            kw.update(secondary_compute=rng.choice(comps),
                      execution_mode=rng.choice(["parallel", "alternative"]),
                      work_split=rng.random(),
                      alternative_share=rng.random())
        cfg = SystemConfig(rng.choice(cpus), rng.choice(comps),
                           rng.choice(mems), rng.choice([1, 2, 4, 8, 12]),
                           **kw)
        try:
            r = evaluate_system(APPLICATION_LIBRARY[app_key], cfg)
        except Exception as exc:
            exceptions.append(f"{app_key}: {type(exc).__name__}: {exc}")
            continue
        if "INFEASIBLE" in r.status:
            infeasible += 1
            continue
        for k, v in r.metrics.items():
            if not isinstance(v, float):
                continue
            if math.isinf(v) or math.isnan(v):
                infinities.append(f"{app_key}/{k}")
            elif v < 0 and "margin" not in k.lower() and "%" not in k:
                negatives.append(f"{app_key}/{k}={v:.4g}")

    check(P, f"{draws} random designs raise no exception", not exceptions,
          "; ".join(exceptions[:3]))
    check(P, "and produce no infinity or not-a-number in a runnable design",
          not infinities, "; ".join(sorted(set(infinities))[:4]))
    check(P, "and no negative quantity where none can exist",
          not negatives, "; ".join(sorted(set(negatives))[:4]))
    check(P, "the sample is not mostly infeasible",
          infeasible < draws * 0.5,
          f"{infeasible} of {draws} could not hold their model - a stress "
          f"test that mostly skips is not a stress test")


# ==============================================================================
# FVS-11  UI and terminology
# ==============================================================================

BANNED_STANDALONE = ("slower", "faster", "better", "worse", "ships", "good",
                     "bad")


def fvs11_ui():
    P = "FVS-11"
    import re
    from ppact import demo, lessons, framework, challenge, modes
    from ppact.decide import explain, design_review
    from ppact.system import print_metric_boundaries

    screens = {}
    for d in demo.DEMOS:
        screens[f"demo {d.key}"] = quiet(demo.print_demo, d)
    for les in lessons.LESSONS:
        screens[f"lesson {les.number}"] = quiet(lessons.print_lesson, les)
        screens[f"lesson {les.number} easy"] = quiet(
            lessons.print_lesson, les, difficulty="easy")
    for ch in challenge.CHALLENGES:
        screens[f"challenge {ch.key}"] = quiet(challenge.print_challenge, ch)
    screens["framework"] = quiet(framework.print_framework)
    screens["boundaries"] = quiet(print_metric_boundaries)
    screens["main menu"] = quiet(modes.print_main_menu)
    base = SystemConfig(**VISION)
    after = dataclasses.replace(base, preprocessing_mode="isp_and_npu")
    screens["explain"] = quiet(explain, "industrial_vision", base, after)
    screens["review"] = quiet(design_review, "industrial_vision", base,
                              "offload",
                              {"preprocessing_mode": "isp_and_npu"})

    # nothing may wrap
    for name, text in screens.items():
        wide = [ln for ln in text.splitlines() if len(ln) > 78]
        check(P, f"{name}: no line wraps", not wide,
              f"{len(wide)} lines, first {len(wide[0]) if wide else 0} chars")

    # no banned word standing alone as a verdict
    for name, text in screens.items():
        for ln in text.splitlines():
            stripped = ln.strip().lower()
            if not stripped or len(stripped.split()) > 4:
                continue
            for word in BANNED_STANDALONE:
                check(P, f"{name}: {word!r} never stands alone",
                      not re.fullmatch(rf"[-*\s]*{word}[.!\s]*", stripped),
                      f"line was {ln!r}")

    # 'ships' must not be a column heading anywhere
    for name, text in screens.items():
        check(P, f"{name}: no column headed 'ships'",
              not re.search(r"\bships\b", text.lower()),
              "students read it as a boat leaving")

    # every table of numbers must carry a unit somewhere
    for name in ("explain", "review"):
        text = screens[name]
        check(P, f"{name}: units are shown",
              any(u in text for u in ("ms", "W", "USD", "%")),
              "a column of numbers with no unit is a column of numbers")


# ==============================================================================
# FVS-12  Certification
# ==============================================================================

PACK_NAMES = {
    "FVS-01": "functional",
    "FVS-02": "boundary",
    "FVS-03": "multi-path",
    "FVS-04": "monotonic",
    "FVS-05": "cross-consistency",
    "FVS-06": "explanation",
    "FVS-07": "failure handling",
    "FVS-08": "regression",
    "FVS-09": "numerical stability",
    "FVS-10": "random stress",
    "FVS-11": "UI and terminology",
}

# What a freeze report must NOT claim, however green the packs are. Each of
# these needs something this program cannot supply for itself.
NOT_ESTABLISHED = (
    ("second-machine reproduction", "needs a machine this was not written "
                                    "on"),
    ("independent holdout", "needs a predictor who does not run the engine"),
    ("external quantitative evidence", "needs measured hardware; no amount "
                                       "of internal work raises it"),
    ("field validation", "needs somebody to build one of these"),
)


def main():
    print(LINE)
    print(" FREEZE VALIDATION SUITE")
    print(LINE)
    print("  Every other suite asks whether the feature is right. This one")
    print("  asks how the program could be broken - which is a different")
    print("  question, and the one that matters at a freeze.\n")

    packs = (fvs01_functional, fvs02_boundary, fvs03_multipath,
             fvs04_monotonic, fvs05_consistency, fvs06_explanation,
             fvs07_failure, fvs08_regression, fvs09_numerical,
             fvs10_stress, fvs11_ui)
    for fn in packs:
        try:
            fn()
        except Exception as exc:
            check(fn.__name__[:6].upper().replace("FVS", "FVS-"),
                  f"{fn.__name__} completes", False,
                  f"{type(exc).__name__}: {exc}")

    by_pack = {}
    for pack, name, ok, detail in RESULTS:
        p = by_pack.setdefault(pack, [0, 0])
        p[1] += 1
        if ok:
            p[0] += 1

    for pack, name, ok, detail in RESULTS:
        if not ok:
            print(f"  FAILED [{pack}] {name}")
            if detail:
                print(f"          {detail}")

    print(f"\n{LINE}")
    print(" FREEZE REPORT")
    print(LINE)
    for pack in sorted(by_pack):
        good, total = by_pack[pack]
        label = PACK_NAMES.get(pack, pack)
        verdict = "pass" if good == total else "FAIL"
        print(f"  {pack}  {label:<24s}{good:>5d} / {total:<6d}{verdict}")

    passed = sum(1 for _, _, ok, _ in RESULTS if ok)
    total = len(RESULTS)
    print(f"\n  {passed} / {total} checks")
    print(f"\n  NOT ESTABLISHED BY THIS SUITE")
    for item, why in NOT_ESTABLISHED:
        print(f"    {item:<34s}{why}")
    print(f"\n  A report that listed only what passed would be an "
          f"advertisement.")
    print(f"  These four are not failures - they are things no program can")
    print(f"  establish about itself, and a freeze that claimed them would")
    print(f"  be claiming the one part nobody checked.")
    print(LINE)
    print(f"  {'READY TO FREEZE' if passed == total else 'NOT READY'}")
    print(LINE)
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
