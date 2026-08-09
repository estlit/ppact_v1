"""
ppact.framework - what this claims to analyse, and whether it does

WHY THIS IS A MODULE AND NOT A DOCUMENT
=======================================
A framework written down is a list of promises. Fourteen categories and a
hundred items look impressive on a slide, and nothing in a slide notices when
a promise stops being kept - or was never kept. The item stays on the list, a
reader assumes it works, and the first person to find out otherwise is a
student in a lecture.

So the map lives in code and every entry names something real: a metric the
engine reports, or a function that exists. An entry naming neither is a
defect, caught by a check, exactly as the metric boundary contracts and the
coefficient registry are. This project has now made the same mistake three
times - a contract naming "Memory energy (mJ)", a coefficient list naming
"Accel power (W)", both absent - and each time the fix was to require that a
declaration point at something.

THREE STATES, AND THEY ARE NOT THE SAME
---------------------------------------
    FULL     the engine computes it and it is verified
    PARTIAL  it exists under a stated limit, named here
    ABSENT   claimed by the framework and NOT implemented

ABSENT entries stay on the list. Deleting them would make the map agree with
the code by forgetting what was promised, which is the opposite of useful: the
gap is the most informative thing on the page.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

LINE = "=" * 78

FULL = "full"
PARTIAL = "partial"
ABSENT = "absent"


@dataclass(frozen=True)
class Item:
    name: str
    state: str
    # what makes it real: a metric key, or a dotted function path, or neither
    metric: Optional[str] = None
    function: Optional[str] = None
    note: str = ""


@dataclass(frozen=True)
class Category:
    number: int
    name: str
    purpose: str
    items: Tuple[Item, ...]


FRAMEWORK: Tuple[Category, ...] = (

    Category(1, "Performance", "how fast the work gets done", (
        Item("single-job latency", FULL, metric="Latency (ms)"),
        Item("sensor-to-control", FULL, metric="Sensor-to-control (ms)"),
        Item("stage latency", FULL, metric="Pipeline interval (ms)"),
        Item("single-job rate", FULL, metric="Single-job rate (inf/s)"),
        Item("pipeline capacity", FULL, metric="Pipeline capacity (inf/s)"),
        Item("delivered throughput", FULL,
             metric="Delivered throughput (inf/s)"),
        Item("accelerator utilisation", FULL,
             metric="Engine arithmetic utilisation (%)"),
        Item("host utilisation", FULL, metric="CPU latency share (%)"),
        Item("bottleneck class", FULL, function="ppact.system.evaluate_system",
             note="reported as bound_by, with five strength levels"),
    )),

    Category(2, "Power", "what it draws and what one job costs", (
        Item("accelerator active power", FULL,
             metric="Accelerator active power (W)"),
        Item("host active power", FULL, metric="CPU active power (W)"),
        Item("memory power", FULL, metric="Memory power (W)"),
        Item("system power", FULL, metric="System power (W)"),
        Item("static power", FULL, metric="Static power (W)"),
        Item("dynamic energy per job", FULL,
             metric="Dynamic energy per inference (mJ)"),
        Item("energy per job", FULL, metric="Energy per inference (mJ)"),
        Item("energy per token", PARTIAL,
             metric="Energy per inference (mJ)",
             note="the same figure; a token IS the job for a text workload"),
        Item("idle power", PARTIAL, metric="Static power (W)",
             note="leakage while idle is modelled; a sleep or duty-cycled "
                  "state is not"),
    )),

    Category(3, "Area", "how much silicon and board it takes", (
        Item("logic silicon", FULL, metric="Logic silicon (mm2)"),
        Item("accelerator area", FULL, metric="Accel die area (mm2)"),
        Item("on-chip SRAM area", FULL, metric="Accel SRAM area (mm2)"),
        Item("ISP area", FULL, metric="ISP area (mm2)"),
        Item("total silicon", FULL, metric="Total silicon (mm2)"),
        Item("board area", FULL, metric="Board area (mm2)"),
        Item("package area", FULL, metric="Package footprint (mm2)"),
        Item("host cache area", ABSENT,
             note="the host is modelled by cycles and traffic, not by a cache "
                  "hierarchy - see the open item on big.LITTLE and DVFS"),
    )),

    Category(4, "Cost", "what a unit costs and what the programme costs", (
        Item("logic die cost", FULL, metric="Logic die cost (USD)"),
        Item("memory subsystem cost", PARTIAL, metric="Memory silicon (mm2)",
             note="reported as an index and as silicon area; the absolute "
                  "device price is a purchased-part figure, not a modelled "
                  "one"),
        Item("system cost", FULL, metric="System cost (USD)"),
        Item("development cost", FULL,
             function="ppact.economics.break_even",
             note="mask set and effort, amortised over volume - kept OUT of "
                  "the unit cost, because a mask set is not a cost per unit"),
        Item("break-even volume", FULL, function="ppact.economics.break_even"),
    )),

    Category(5, "Thermal", "whether the heat can be got rid of", (
        Item("power density", FULL, metric="Power density (W/mm2)"),
        Item("thermal margin", FULL, metric="Thermal margin (%)"),
        Item("cooling class", FULL, function="ppact.system.evaluate_system",
             note="passive, airflow, fan, liquid - a CLASS mismatch, not a "
                  "magnitude, and not fixable by reducing anything"),
        Item("memory cooling compatibility", FULL,
             function="ppact.system.gate_causes"),
        Item("junction temperature", ABSENT,
             note="no thermal resistance network; the model reasons about "
                  "density and class, not degrees"),
    )),

    Category(6, "Memory", "capacity, bandwidth, and which one is binding", (
        Item("effective bandwidth", FULL,
             metric="Effective bandwidth (GB/s)"),
        Item("traffic", FULL, metric="DRAM traffic (MB)"),
        Item("capacity fit", FULL, function="ppact.system.evaluate_system",
             note="a model that does not fit reports NO performance figure"),
        Item("compute/memory ratio", FULL,
             function="ppact.system.evaluate_system"),
        Item("marginal benefit per stack", FULL,
             function="ppact.economics.stack_marginal_utility"),
        Item("memory cooling", FULL, function="ppact.system.gate_causes"),
        Item("generation comparison", FULL,
             function="ppact.memory_sweep.compare"),
    )),

    Category(7, "Host", "the station people forget", (
        Item("host cycles and traffic", FULL,
             metric="Host DRAM traffic (MB)"),
        Item("preprocess, dispatch, postprocess", FULL,
             metric="CPU preprocess (ms)"),
        Item("host roofline", FULL, metric="CPU active (ms)",
             note="compute and transfer with a stated overlap"),
        Item("host bottleneck state", FULL,
             function="ppact.system.evaluate_system",
             note="compute-limited, balanced, memory-limited"),
        Item("cache hierarchy", ABSENT,
             note="open item; the host is cycles and bytes"),
        Item("big.LITTLE and DVFS", ABSENT,
             note="open item; the host runs at one clock and one core type, "
                  "so a design that scales frequency with load cannot be "
                  "expressed"),
    )),

    Category(8, "Accelerator", "one engine, or two, and how they share", (
        Item("single engine roofline", FULL, metric="Compute time (ms)"),
        Item("dual engine, parallel split", FULL,
             function="ppact.system.evaluate_system"),
        Item("dual engine, alternative allocation", FULL,
             function="ppact.economics.allocation_sweep"),
        Item("hand-off and merge", FULL, metric="Handoff (ms)"),
        Item("shared-memory contention", FULL,
             function="ppact.system.evaluate_system"),
        Item("sequential dependency", FULL,
             function="ppact.system.evaluate_system"),
        Item("three or more engines", ABSENT,
             note="the model expresses one or two; a third is a structural "
                  "change, not a parameter"),
    )),

    Category(9, "Language models", "what makes a server different", (
        Item("model size", FULL, function="ppact.economics.model_size_sweep"),
        Item("context length", FULL, function="ppact.economics.context_sweep"),
        Item("KV cache", FULL, function="ppact.economics.context_sweep"),
        Item("quantisation", FULL,
             function="ppact.economics.quantisation_sweep",
             note="the ACCURACY cost is an assumption, printed with every "
                  "sweep so it can be replaced"),
        Item("batch and concurrent users", PARTIAL,
             function="ppact.economics.batch_sweep",
             note="a synchronous active batch; queueing across batches is "
                  "not modelled"),
        Item("prompt and decode balance", FULL,
             function="ppact.economics.prompt_ratio_sweep"),
        Item("mixture of experts", PARTIAL,
             function="ppact.economics.moe_comparison",
             note="storage against bandwidth is structural and represented; "
                  "routing cost is not"),
        Item("disaggregated prefill and decode", ABSENT,
             note="one accelerator path per inference, so prefill cannot go "
                  "to one machine and decode to another"),
    )),

    Category(10, "Technology", "what a process node moves and what it does not",
             (
        Item("process node scaling", FULL,
             function="ppact.process.get_node"),
        Item("node economics", FULL, function="ppact.economics.node_decision"),
        Item("migration claims", FULL,
             function="ppact.migration.check_migration",
             note="a move to the same configuration reports NO MIGRATION"),
        Item("design space sweep", FULL, function="ppact.game.compare_designs"),
        Item("chiplets and multi-die", ABSENT,
             note="open item; a single logic node is assumed"),
    )),

    Category(11, "Decisions", "the part a designer actually uses", (
        Item("bottleneck analysis", FULL, function="ppact.explain.why"),
        Item("why a number changed", FULL,
             function="ppact.explain.decision_explanation"),
        Item("sensitivity to an assumption", FULL,
             function="ppact.sensitivity.run_all"),
        Item("break-even point", FULL,
             function="ppact.sensitivity.handoff_break_even"),
        Item("rank stability and rank flip", FULL,
             function="ppact.sensitivity.ranking_stability"),
        Item("robust against conditional verdict", FULL,
             function="ppact.sensitivity.run_sweep"),
        Item("recommendation by context", FULL,
             function="ppact.explain.decision_explanation",
             note="industrial, prototype, teaching - because a design that "
                  "no factory should build can be an excellent example"),
    )),

    Category(12, "Validation", "why any of this should be believed", (
        Item("independent recomputation", FULL,
             function="ppact.system.check_metric_boundaries"),
        Item("metric boundary contracts", FULL,
             function="ppact.system.check_metric_boundaries"),
        Item("coefficient liveness", FULL,
             function="ppact.sensitivity.coefficient_liveness"),
        Item("mutation testing", FULL,
             function="ppact.reproducibility.build_manifest",
             note="tests_mutation.py; the manifest records the count"),
        Item("pre-registered predictions", FULL,
             function="ppact.reproducibility.build_manifest",
             note="holdout_predictions_v1.py, hashed and never edited"),
        Item("reproducibility evidence", FULL,
             function="ppact.reproducibility.write_package"),
        Item("certification", FULL,
             function="ppact.reproducibility.certified_run"),
        Item("independent external holdout", ABSENT,
             note="needs a predictor who does not run the engine - see the "
                  "evidence status list"),
    )),

    Category(13, "Education", "how someone learns any of it", (
        Item("mode selection", FULL, function="ppact.modes.main"),
        Item("lessons", FULL, function="ppact.lessons.print_lesson",
             note="one change per step, enforced"),
        Item("final challenge", FULL,
             function="ppact.lessons.print_final_challenge"),
        Item("design game", FULL, function="ppact.game.play"),
        Item("grading rubric", FULL, function="ppact.menu.task_rubric"),
        Item("quiz", ABSENT,
             note="not implemented; the lessons ask questions and answer "
                  "them, but nothing marks a student's answer"),
    )),

    Category(14, "Visualisation", "how the result is shown", (
        Item("tables", FULL, function="ppact.system.print_metric_boundaries"),
        Item("bar charts", FULL, function="ppact.charts.render_bars"),
        Item("design comparison", FULL, function="ppact.game.compare_designs"),
        Item("timeline and stage view", PARTIAL,
             function="ppact.runtime.simulate",
             note="stations and their busy time are reported as numbers, not "
                  "drawn"),
        Item("Pareto front", ABSENT,
             note="not implemented; the design sweep ranks on one objective "
                  "at a time and does not draw the non-dominated set"),
        Item("heat map", ABSENT,
             note="not implemented; a two-parameter sweep is printed as rows "
                  "rather than shaded"),
    )),
)


def _metric_exists(key: str) -> bool:
    from .application import APPLICATION_LIBRARY
    from .system import SystemConfig, evaluate_system
    for app, cpu, comp, mem, dev, pm in (
            ("industrial_vision", "cortex_a78_x4", "npu_32x32", "LPDDR5", 2,
             "isp_and_npu"),
            ("llm_service", "server_x86_x32", "datacenter_gpu", "HBM3E", 6,
             None)):
        kw = {} if pm is None else {"preprocessing_mode": pm}
        m = evaluate_system(APPLICATION_LIBRARY[app],
                            SystemConfig(cpu, comp, mem, dev, **kw)).metrics
        if key in m:
            return True
    return False


def _function_exists(path: str) -> bool:
    import importlib
    module, _, name = path.rpartition(".")
    try:
        mod = importlib.import_module(module)
    except ImportError:
        return False
    return hasattr(mod, name)


def framework_violations() -> List[str]:
    """Every claim must point at something, and ABSENT must claim nothing."""
    problems = []
    seen = set()
    for cat in FRAMEWORK:
        for it in cat.items:
            tag = f"{cat.name}/{it.name}"
            if tag in seen:
                problems.append(f"{tag}: listed twice")
            seen.add(tag)

            if it.state not in (FULL, PARTIAL, ABSENT):
                problems.append(f"{tag}: unknown state {it.state!r}")

            if it.state == ABSENT:
                if it.metric or it.function:
                    problems.append(
                        f"{tag}: marked absent and points at something - "
                        f"either it exists or it does not")
                if not it.note:
                    problems.append(
                        f"{tag}: absent with no explanation. A gap without a "
                        f"reason reads as an oversight")
                continue

            if not it.metric and not it.function:
                problems.append(
                    f"{tag}: claimed as {it.state} and names neither a metric "
                    f"nor a function - a claim that points at nothing is a "
                    f"claim nobody can check")
                continue
            if it.metric and not _metric_exists(it.metric):
                problems.append(
                    f"{tag}: names metric {it.metric!r}, which the engine "
                    f"does not report")
            if it.function and not _function_exists(it.function):
                problems.append(
                    f"{tag}: names {it.function}, which does not exist")
            if it.state == PARTIAL and not it.note:
                problems.append(
                    f"{tag}: partial with no stated limit. 'Partial' without "
                    f"a boundary is a word, not a status")
    return problems


def counts() -> Dict[str, int]:
    out = {FULL: 0, PARTIAL: 0, ABSENT: 0}
    for cat in FRAMEWORK:
        for it in cat.items:
            out[it.state] = out.get(it.state, 0) + 1
    return out


def print_framework(show_absent_only: bool = False) -> None:
    print(f"\n{LINE}")
    print(" WHAT THIS ANALYSES - AND WHAT IT DOES NOT")
    print(LINE)
    print("  Every line below points at a metric the engine reports or a")
    print("  function that exists, and is checked to. The gaps stay on the")
    print("  list: removing them would make this agree with the code by")
    print("  forgetting what was promised.\n")

    for cat in FRAMEWORK:
        items = [i for i in cat.items
                 if not show_absent_only or i.state == ABSENT]
        if not items:
            continue
        print(f"  {cat.number:2d}. {cat.name} - {cat.purpose}")
        for it in items:
            mark = {FULL: "  ", PARTIAL: "~ ", ABSENT: "x "}[it.state]
            print(f"      {mark}{it.name}")
            if it.note:
                for line in _wrap(it.note, 62):
                    print(f"          {line}")
        print()

    c = counts()
    total = sum(c.values())
    print(f"  {c[FULL]} implemented, {c[PARTIAL]} partial, {c[ABSENT]} not "
          f"implemented, out of {total}.")
    print(f"\n  A partial entry states its limit. An absent one states why it")
    print(f"  is absent. Neither is an apology - a model that says what it")
    print(f"  cannot express is more useful than one that quietly guesses.")
    print(LINE)


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


# ==============================================================================
# The one-screen validation summary
# ==============================================================================
#
# Four thousand checks is not a thing a student can read. What they can read
# is which areas have been checked, how, and where the evidence stops - and
# the last of those is the part that makes the first two believable.

VALIDATION_AREAS = (
    ("Engine arithmetic", "tests_independent.py",
     "quantities derived a second way from the library data"),
    ("Host and accelerator", "tests_model.py",
     "roofline, stations, bottleneck classification"),
    ("Two accelerators", "tests_dual.py",
     "reduction, allocation, dependency, hand-off, interaction"),
    ("Memory and capacity", "tests_memory.py",
     "bandwidth, capacity fit, stack marginal value, cooling class"),
    ("Language models", "tests_memory.py",
     "context, batch, quantisation, model size, mixture of experts"),
    ("Corner cases", "tests_corner.py",
     "degenerate inputs, extremes, and what must be refused"),
    ("Cross-path agreement", "tests_differential.py",
     "two routes to the same number must agree"),
    ("Scenario direction", "tests_scenarios.py",
     "predicted directions, with reversals counted"),
    ("Deliberate defects", "tests_mutation.py",
     "faults introduced and required to be caught"),
    ("Locked predictions", "tests_holdout.py",
     "written and hashed before the runs, never edited"),
)


def print_validation_summary(run: bool = False) -> None:
    """What has been checked, and where the evidence stops.

    Deliberately does NOT print a percentage. A developer who computes their
    own validation score has produced another self-assessment; a reader can
    check a list and cannot check a number.
    """
    from .reproducibility import (EVIDENCE_STATUS, best_recorded_grade,
                                  GRADES)

    print(f"\n{LINE}")
    print(" WHAT HAS BEEN CHECKED")
    print(LINE)
    print("  Four thousand individual checks is not something anyone reads.")
    print("  What follows is which areas have been checked and how.\n")
    width = max(len(n) for n, _, _ in VALIDATION_AREAS)
    for name, where, what in VALIDATION_AREAS:
        print(f"  {name:<{width}s}   {where}")
        for line in _wrap(what, 73 - width):
            print(f"  {'':<{width}s}   {line}")
    print()

    grade = best_recorded_grade()
    print(f"  Reproducibility          {grade} - {GRADES.get(grade, '')}")
    print()
    print(f"  AND WHERE IT STOPS")
    for name, state, note in EVIDENCE_STATUS:
        if state.startswith(("implemented", "achieved")):
            continue
        print(f"    {name}  [{state}]")
        for line in _wrap(note, 62):
            print(f"        {line}")
    print()
    print("  That last section is what makes the rest believable. A tool")
    print("  that lists only what it can do is an advertisement.")
    print(LINE)
