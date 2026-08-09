"""
ppact.review - one analysis object, one registry, one contract

WHY THIS MODULE EXISTS
======================
RC2 promised a three-layer result in its documentation and delivered it on
one path out of eight. Nothing caught that, because the promise lived in
prose and the assembly lived in each workflow separately.

So the contract is here, as objects a check can read:

    ReviewAnalysis            everything a review needs, computed ONCE
    WORKFLOW_REGISTRY         which paths are analyses, and which variant
    STANDARD_REVIEW_CONTRACT  which sections, in which order, per variant

THE ORDER OF THESE THREE IS NOT ARBITRARY
-----------------------------------------
The data object comes first because it is what makes renderer purity
possible. A renderer that has to compute something will compute it, and then
a presentation change can move a result. Everything a section needs is
finished before any renderer runs, and a check requires that no renderer
calls the engine.

The registry comes before the menu because the menu is a presentation. It
carries help screens, About, Back and file export beside the analyses, so
deriving scope from menu structure would let a UI change move the analysis
boundary. The menu reads the registry; the registry never reads the menu.

IDENTITY
--------
Every section records which configurations it described. A chart that
renders successfully while describing a different design than the bars
beside it is the worst defect available here - it is invisible, and it is
wrong in the direction of confidence.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

SINGLE = "single"
COMPARISON = "comparison"
NONE = "none"


# ==============================================================================
# Workflow registry
# ==============================================================================

@dataclass(frozen=True)
class Workflow:
    workflow_id: str
    canonical_name: str
    workflow_type: str                  # analysis / validation / utility
    produces_engineering_analysis: bool
    review_variant: str                 # single | comparison | none
    entry_points: Tuple[str, ...]       # menu task function names
    exemption_reason: str = ""

    def __post_init__(self):
        if self.produces_engineering_analysis:
            if self.review_variant not in (SINGLE, COMPARISON):
                raise ValueError(
                    f"{self.workflow_id}: an analysis must declare a review "
                    f"variant")
            if self.exemption_reason:
                raise ValueError(
                    f"{self.workflow_id}: an analysis cannot carry an "
                    f"exemption reason")
        else:
            if self.review_variant != NONE:
                raise ValueError(
                    f"{self.workflow_id}: a non-analysis must declare "
                    f"variant 'none'")
            if len(self.exemption_reason) < 25:
                raise ValueError(
                    f"{self.workflow_id}: a non-analysis must say WHY it is "
                    f"exempt. 'Not an analysis' is a restatement, not a "
                    f"reason")


WORKFLOW_REGISTRY: Tuple[Workflow, ...] = (

    # --- engineering analyses --------------------------------------------
    Workflow("education_step_by_step", "Build a design step by step",
             "analysis", True, SINGLE, ("task_game",)),
    Workflow("education_guided_design",
             "Think like an architect: a guided comparison",
             "analysis", True, COMPARISON, ("task_guided",)),
    Workflow("education_why_changed", "Ask why a number changed",
             "analysis", True, COMPARISON, ("task_decide",)),
    Workflow("design_review", "Propose a change and have it reviewed",
             "analysis", True, COMPARISON, ("task_review",)),
    Workflow("what_if", "Try a change and put it back",
             "analysis", True, COMPARISON, ("task_whatif",)),
    Workflow("challenge", "Meet a target with a design",
             "analysis", True, SINGLE, ("task_challenge",)),
    Workflow("demo", "Watch a question answered",
             "analysis", True, COMPARISON, ("task_demo",)),
    # The canonical name is the name on the menu. A workflow called one
    # thing in the menu and another in its own heading gives a user two
    # screens where there is one.
    Workflow("quick_start", "Quick Start",
             "analysis", True, SINGLE, ("task_quickstart",)),

    # A WORKFLOW, NOT A UTILITY.
    #
    # `task_custom` takes several decisions from the reader, builds a
    # configuration and produces an engineering analysis, which is what
    # a workflow does. It had no registry entry, so a report built from
    # it was refused - and filing it under utilities would have said a
    # thing that makes an analysis is not an analysis workflow.
    #
    # SINGLE, because the reader builds the design from nothing: there
    # is no earlier design to compare against, and manufacturing one
    # from an application default is exactly the silent reference this
    # project has ruled out elsewhere.
    Workflow("custom_design", "Build a Custom Design",
             "analysis", True, SINGLE, ("task_custom",)),

    # --- exempt: these produce evidence, not an engineering analysis -----
    Workflow("validation_model", "Check the model", "validation", False,
             NONE, ("task_validation",),
             "Produces PASS or FAIL against the model's own invariants and "
             "the evidence behind them. There are no two designs to "
             "compare and no architecture to balance; a spider chart here "
             "would require inventing designs to draw."),
    Workflow("library_validation", "Check the library against industry",
             "validation", False, NONE, ("task_library",),
             "Reports coverage, gaps and confidence for the architecture "
             "library. Its subject is the library, not a system, so it has "
             "no latency to decompose."),
    Workflow("certification", "Certify this copy", "validation", False,
             NONE, ("task_reproducibility",),
             "Reports a reproduction grade and digests for a build. Its "
             "subject is an archive rather than an architecture."),
    Workflow("documentation_audit", "Check the documents", "validation",
             False, NONE, ("task_framework",),
             "Compares the documentation against the program. It analyses "
             "text, not a system, and has no configuration to review."),
    Workflow("lessons", "Take the lessons, in order", "utility", False,
             NONE, ("task_lessons",),
             "A guided course whose steps each produce their own worked "
             "comparison. The lesson itself is a sequence, not a single "
             "analysis with one result to review."),
    Workflow("workspace", "Save, open and export designs", "utility", False,
             NONE, ("task_workspace",),
             "Manages saved configurations. It stores and retrieves; it "
             "computes nothing and has no result to present."),
    Workflow("about", "About this program", "utility", False, NONE,
             ("task_about",),
             "Describes the purpose, method and boundaries of the "
             "program. It carries no configuration and no result."),
)

BY_WORKFLOW = {w.workflow_id: w for w in WORKFLOW_REGISTRY}
BY_ENTRY = {e: w for w in WORKFLOW_REGISTRY for e in w.entry_points}

ANALYSIS_WORKFLOWS = tuple(w for w in WORKFLOW_REGISTRY
                           if w.produces_engineering_analysis)
EXEMPT_WORKFLOWS = tuple(w for w in WORKFLOW_REGISTRY
                         if not w.produces_engineering_analysis)


def workflow_registry_violations() -> List[str]:
    problems = []
    seen = set()
    for w in WORKFLOW_REGISTRY:
        if w.workflow_id in seen:
            problems.append(f"{w.workflow_id}: registered twice")
        seen.add(w.workflow_id)
        if not w.entry_points:
            problems.append(f"{w.workflow_id}: no entry point, so nothing "
                            f"can reach it")
    entries = [e for w in WORKFLOW_REGISTRY for e in w.entry_points]
    dupes = {e for e in entries if entries.count(e) > 1}
    if dupes:
        problems.append(f"entry points claimed by two workflows: "
                        f"{sorted(dupes)}")
    return problems


# ==============================================================================
# Section contract
# ==============================================================================

@dataclass(frozen=True)
class Section:
    section_id: str
    canonical_title: str
    variant: str                 # single | comparison | both
    order: int
    required: bool = True
    needs: Tuple[str, ...] = ()  # ReviewAnalysis fields it consumes


STANDARD_REVIEW_CONTRACT: Tuple[Section, ...] = (
    Section("architecture_summary", "Architecture Summary", "both", 1,
            needs=("current_config", "starting_config")),
    Section("latency_flow", "Latency Flow", SINGLE, 2,
            needs=("latency_composition",)),
    Section("latency_change", "Latency Change Breakdown", COMPARISON, 2,
            needs=("latency_change",)),
    Section("limiting_factor", "Current Limiting Factor", "both", 3,
            needs=("dominant_component", "analytical_limit")),
    Section("measured_bars", "Measured Results", "both", 4,
            needs=("measured_metrics",)),
    Section("balance", "Architecture Balance", SINGLE, 5,
            needs=("balance_data",)),
    Section("balance_comparison", "Architecture Balance Comparison",
            COMPARISON, 5, needs=("balance_data",)),
    Section("recommendation", "What to Explore Next", "both", 6,
            needs=("exploration_options",)),
    Section("deployment", "Deployment Assessment", "both", 7,
            needs=("deployment",)),
    Section("takeaway", "Engineering Takeaway", "both", 8,
            needs=("takeaway",)),
    Section("boundaries", "Assumptions and Model Boundaries", "both", 9),
)


def sections_for(variant: str) -> Tuple[Section, ...]:
    return tuple(sorted(
        (s for s in STANDARD_REVIEW_CONTRACT
         if s.variant in ("both", variant)),
        key=lambda s: s.order))


def contract_violations() -> List[str]:
    problems = []
    for variant in (SINGLE, COMPARISON):
        orders = [s.order for s in sections_for(variant)]
        if len(orders) != len(set(orders)):
            problems.append(
                f"{variant}: two sections share an order number, so a "
                f"review could carry both variants of one section")
        if orders != sorted(orders):
            problems.append(f"{variant}: sections are not orderable")
    ids = [s.section_id for s in STANDARD_REVIEW_CONTRACT]
    if len(ids) != len(set(ids)):
        problems.append("a section id is used twice")
    return problems


# ==============================================================================
# Measured metric definitions
# ==============================================================================

@dataclass(frozen=True)
class MeasuredMetric:
    label: str
    metric_key: str
    unit: str
    budget_attr: Optional[str]      # application field holding the limit
    lower_is_better: bool = True
    in_deployment_verdict: bool = True


# Energy per job carries in_deployment_verdict=False deliberately. No
# application states a requirement for it, and a metric with no requirement
# cannot decide a verdict - but hiding it would remove the one figure that
# explains the relationship between power and time.
MEASURED_METRICS: Tuple[MeasuredMetric, ...] = (
    MeasuredMetric("Execution latency", "Latency (ms)", "ms",
                   "latency_budget_ms"),
    MeasuredMetric("Delivered throughput", "Delivered throughput (inf/s)",
                   "inf/s", "target_inferences_per_s",
                   lower_is_better=False),
    MeasuredMetric("System power", "System power (W)", "W",
                   "power_budget_w"),
    MeasuredMetric("Energy per job", "Energy per inference (mJ)", "mJ",
                   None, in_deployment_verdict=False),
    # THREE ROWS, not one.
    #
    # "Total silicon" carried soc_silicon_budget_mm2, so a design with 12
    # mm2 of logic and 880 mm2 of DRAM read "EXCEEDS by 78.4%" while the
    # deployment gate - correctly checking the SoC budget - said READY.
    # The gate was right and the row was wrong: an SoC die budget does not
    # govern DRAM die area, and one HBM stack would blow it on its own.
    MeasuredMetric("SoC silicon", "SoC silicon (mm2)", "mm2",
                   "soc_silicon_budget_mm2"),
    MeasuredMetric("Memory silicon", "Memory silicon (mm2)", "mm2", None,
                   in_deployment_verdict=False),
    MeasuredMetric("Total silicon", "Total silicon (mm2)", "mm2", None,
                   in_deployment_verdict=False),
    MeasuredMetric("System cost", "System cost (USD)", "USD",
                   "bom_budget_usd"),
    # NOT "thermal margin". The engine computes power density against a
    # modelled limit; it computes neither a temperature nor a margin in
    # watts, and naming a quantity after something the engine does not
    # compute is the failure this contract exists to prevent.
    MeasuredMetric("Thermal power density", "Power density (W/mm2)",
                   "W/mm2", "thermal_limit_w_per_mm2"),
)


@dataclass(frozen=True)
class MetricReading:
    label: str
    value: float
    unit: str
    limit: Optional[float]
    lower_is_better: bool
    in_deployment_verdict: bool
    starting_value: Optional[float] = None

    @property
    def over(self) -> bool:
        if self.limit is None:
            return False
        return (self.value > self.limit if self.lower_is_better
                else self.value < self.limit)


# ==============================================================================
# The analysis object
# ==============================================================================

@dataclass(frozen=True)
class LimitingFactor:
    """Two figures, never merged.

    Across 56 representative configurations these agreed in 31 and differed
    in 25: a design can spend most of its time inside the accelerator while
    the accelerator is waiting on bandwidth. Collapsing them to one
    'bottleneck' line would report the wrong one half the time.
    """
    dominant_component: str
    dominant_share_pct: float
    analytical_limit: str
    analytical_limit_plain: str = ""


@dataclass(frozen=True)
class ReviewAnalysis:
    """Everything a review needs, computed before any renderer runs."""
    analysis_id: str
    workflow_id: str
    variant: str

    app_key: str
    app_name: str
    current_config: Any
    starting_config: Optional[Any]
    current_result: Any
    starting_result: Optional[Any]

    latency_composition: Tuple[Tuple[str, float, float], ...]  # name, ms, %
    latency_change: Tuple[Tuple[str, float], ...]
    latency_change_total: float
    latency_change_residue: float

    limiting: LimitingFactor
    measured: Tuple[MetricReading, ...]
    balance: Any
    exploration: Tuple[Tuple[str, float, str], ...]
    deployment_ready: bool
    deployment_unmet: Tuple[str, ...]
    takeaway: str

    current_config_id: str = ""
    starting_config_id: str = ""
    result_digest: str = ""


def _config_id(cfg) -> str:
    if cfg is None:
        return ""
    return hashlib.sha256(repr(cfg).encode("utf-8")).hexdigest()[:16]


def build_review(workflow_id: str, app_key: str, current_cfg,
                 starting_cfg=None) -> ReviewAnalysis:
    """Compute the whole review ONCE.

    Every figure a section will show is finished here. That is what lets a
    renderer be pure: it has nothing left to work out, so it cannot change
    a result while formatting one.
    """
    import dataclasses as _dc
    from .application import APPLICATION_LIBRARY
    from .system import evaluate_system
    from .decide import (headroom, upgrade_ranking, latency_breakdown,
                         BOTTLENECK_PLAIN)
    from .visual import build_balance

    wf = BY_WORKFLOW.get(workflow_id)
    if wf is None:
        raise ValueError(
            f"{workflow_id!r} is not in WORKFLOW_REGISTRY. An analysis path "
            f"that is not registered is a path outside the contract.")
    if not wf.produces_engineering_analysis:
        raise ValueError(
            f"{workflow_id!r} is exempt from the standard review: "
            f"{wf.exemption_reason}")

    variant = wf.review_variant
    if variant == COMPARISON and starting_cfg is None:
        raise ValueError(
            f"{workflow_id!r} is a comparison workflow and was given no "
            f"starting configuration. A comparison is never manufactured "
            f"from a default.")
    if variant == SINGLE and starting_cfg is not None:
        raise ValueError(
            f"{workflow_id!r} is a single-design workflow and was given a "
            f"starting configuration. A single analysis does not silently "
            f"become a comparison.")

    app = APPLICATION_LIBRARY[app_key]
    cur = evaluate_system(app, current_cfg)
    start = evaluate_system(app, starting_cfg) if starting_cfg else None

    # -- composition (single) ------------------------------------------
    comp = []
    if variant == SINGLE:
        total = cur.metrics.get("Latency (ms)", 0.0)
        for h in headroom(cur.metrics):
            comp.append((h.station, total * h.share_pct / 100.0,
                         h.share_pct))

    # -- change (comparison) -------------------------------------------
    change, change_total, residue = (), 0.0, 0.0
    if variant == COMPARISON:
        terms, residue = latency_breakdown(start.metrics, cur.metrics)
        change = tuple((t.name, t.delta) for t in terms)
        change_total = (cur.metrics["Latency (ms)"]
                        - start.metrics["Latency (ms)"])

    # -- limiting factor, two figures ----------------------------------
    hr = headroom(cur.metrics)
    top = hr[0] if hr else None
    limiting = LimitingFactor(
        dominant_component=top.station if top else "unknown",
        dominant_share_pct=top.share_pct if top else 0.0,
        analytical_limit=cur.bound_by,
        analytical_limit_plain=BOTTLENECK_PLAIN.get(cur.bound_by, ""))

    # -- measured metrics ----------------------------------------------
    readings = []
    for m in MEASURED_METRICS:
        value = cur.metrics.get(m.metric_key)
        if value is None:
            continue
        limit = getattr(app, m.budget_attr, None) if m.budget_attr else None
        readings.append(MetricReading(
            label=m.label, value=float(value), unit=m.unit,
            limit=float(limit) if limit is not None else None,
            lower_is_better=m.lower_is_better,
            in_deployment_verdict=m.in_deployment_verdict,
            starting_value=(float(start.metrics[m.metric_key])
                            if start is not None
                            and m.metric_key in start.metrics else None)))

    # -- balance: one profile or two, never self-normalised -------------
    if variant == SINGLE:
        balance = build_balance(app_key, [("Current design", current_cfg)])
    else:
        balance = build_balance(app_key, [("Starting point", starting_cfg),
                                          ("Current design", current_cfg)])

    # -- exploration ----------------------------------------------------
    exploration = tuple(upgrade_ranking(cur.metrics, cur.bound_by))

    unmet = tuple(sorted(g for g, ok in cur.gate.items() if not ok))

    # -- takeaway --------------------------------------------------------
    if variant == COMPARISON:
        from .guided import key_takeaway
        takeaway = key_takeaway(app_key, starting_cfg, current_cfg)
        takeaway += _cost_of_the_gain(start.metrics, cur.metrics)
    else:
        takeaway = _single_takeaway(cur, limiting, unmet)

    digest = hashlib.sha256(
        repr(sorted(cur.metrics.items())).encode("utf-8")).hexdigest()[:16]

    return ReviewAnalysis(
        analysis_id=f"{workflow_id}:{_config_id(current_cfg)}",
        workflow_id=workflow_id, variant=variant,
        app_key=app_key, app_name=app.name,
        current_config=current_cfg, starting_config=starting_cfg,
        current_result=cur, starting_result=start,
        latency_composition=tuple(comp),
        latency_change=change, latency_change_total=change_total,
        latency_change_residue=residue,
        limiting=limiting, measured=tuple(readings), balance=balance,
        exploration=exploration,
        deployment_ready=bool(cur.passes), deployment_unmet=unmet,
        takeaway=takeaway,
        current_config_id=_config_id(current_cfg),
        starting_config_id=_config_id(starting_cfg),
        result_digest=digest)


def _cost_of_the_gain(before: Dict, after: Dict) -> str:
    """What was paid, per unit of what was bought.

    "latency fell 14.4% for +94.22 USD" states both figures and leaves the
    reader to divide them. The rate is the thing a designer compares
    against another option, and a demo whose answer is "no, not worth it"
    is answering exactly that question.
    """
    la, lb = before.get("Latency (ms)"), after.get("Latency (ms)")
    ca, cb = before.get("System cost (USD)"), after.get("System cost (USD)")
    if None in (la, lb, ca, cb) or la <= 0:
        return ""
    gain_pct = (1 - lb / la) * 100.0
    spend = cb - ca
    if abs(gain_pct) < 0.05:
        return (f" The change cost {spend:+.2f} USD and moved latency by "
                f"{gain_pct:+.1f}%.")
    if spend <= 0:
        return (f" It cost {spend:+.2f} USD, so the gain was not bought.")
    return (f" That is {spend / gain_pct:.2f} USD for each 1% of latency "
            f"removed - the figure to compare against any other change.")


# Which station an analytical limit lives in. "compute" and "memory" are
# both mechanisms INSIDE the accelerator, so a design whose dominant
# station is the accelerator and whose limit is compute is not pointing at
# two different places - and saying "not the same station" there was
# simply wrong.
LIMIT_STATION = {
    "compute": "accelerator core",
    "memory": "accelerator core",
}


def limit_points_at(dominant: str, limit: str) -> bool:
    """True when the limit lives in the station holding the time."""
    station = LIMIT_STATION.get(limit)
    if station is None:
        return False
    return station in dominant or dominant in station


def _single_takeaway(result, limiting, unmet) -> str:
    """One or two sentences true of THIS design, carrying a figure."""
    m = result.metrics
    text = (f"One job takes {m['Latency (ms)']:.2f} ms, and "
            f"{limiting.dominant_component} holds "
            f"{limiting.dominant_share_pct:.1f}% of it.")
    if limiting.analytical_limit:
        if limit_points_at(limiting.dominant_component,
                           limiting.analytical_limit):
            text += (f" The analytical limit is "
                     f"{limiting.analytical_limit}, a mechanism inside that "
                     f"same station: they are different quantities pointing "
                     f"at one part of the architecture here.")
        else:
            text += (f" The analytical limit is "
                     f"{limiting.analytical_limit}, which is elsewhere - "
                     f"the time is spent in one place and constrained by "
                     f"another.")
    if unmet:
        text += f" It does not deploy: {', '.join(unmet)} unmet."
    return text


# ==============================================================================
# Renderers
# ==============================================================================
#
# Every function below takes a finished ReviewAnalysis and returns lines.
# None of them calls the engine, and a check enforces that: a renderer that
# can compute can change a result inside a presentation change, and the
# change would arrive in a commit nobody thought to verify numerically.

LINE = "=" * 78
RULE = "-" * 78


def _wrap(text: str, width: int) -> List[str]:
    from .visual import wrap_text
    return wrap_text(text, width)


def _heading(n: int, title: str) -> List[str]:
    return [f"  {n}. {title.upper()}", ""]


def render_architecture_summary(a: ReviewAnalysis) -> List[str]:
    """Separate labelled fields, never one packed string.

    A configuration compressed into a single line is unreadable at exactly
    the moment it matters - when somebody is checking whether the review
    describes the design they think it does.
    """
    from .application import APPLICATION_LIBRARY
    from .compute import COMPUTE_LIBRARY
    from .cpu import CPU_LIBRARY
    from .memory import MEMORY_LIBRARY
    from .questions import unit_name

    app = APPLICATION_LIBRARY[a.app_key]
    app_soc = getattr(app, "default_soc_node", None)
    app_accel = getattr(app, "default_accel_node", None)

    def fields(cfg):
        return [
            ("Application", a.app_name),
            ("Host processor", CPU_LIBRARY[cfg.cpu].name),
            ("AI accelerator", COMPUTE_LIBRARY[cfg.compute].name),
            ("Memory technology", MEMORY_LIBRARY[cfg.memory].name),
            ("Memory unit count",
             f"{cfg.memory_devices} "
             f"{unit_name(cfg.memory, cfg.memory_devices != 1)}"),
            # The real node, and where it came from. "product default"
            # named neither: a reader could not tell that area, power and
            # die cost had been computed on 16nm and 12nm, nor whether the
            # two designs beside each other were even on the same process.
            ("Host process node", _node_field(cfg.soc_node, app_soc)),
            ("Accelerator process node",
             _node_field(cfg.accel_node, app_accel)),
            ("Preprocessing location", cfg.preprocessing_mode),
        ]

    out = _heading(1, "Architecture Summary")
    if a.variant == SINGLE:
        for k, v in fields(a.current_config):
            out.append(f"     {k:<26s}{v}")
    else:
        # The value column is wide enough for "16nm  (application default)".
        # It was 24 characters, which truncated the origin to "(application
        # defau" - and the origin is half of what the field says.
        W = 30
        out.append(f"     {'':<26s}{'starting point':<{W}s}current design")
        s_f, c_f = fields(a.starting_config), fields(a.current_config)
        for (k, sv), (_, cv) in zip(s_f, c_f):
            mark = "  " if sv == cv else "* "
            if sv == cv:
                # Printed ONCE when the two agree. Repeating "16nm
                # (application default)" in both columns reached 88
                # characters and told the reader nothing the first column
                # had not already said.
                out.append(f"  {mark} {k:<26s}{sv}  (same in both)")
            else:
                out.append(f"  {mark} {k:<26s}{str(sv):<{W}s}{cv}")
        out.append("")
        out.append("     * marks a field that differs between the two.")
        out.append("")
        # Said to the USER, on the screen where the starting point appears.
        # In RC2 this sentence lived in the code that offered the review and
        # went with it; the label was left on screen without the statement
        # that stops it being read as the recommended architecture.
        for line in _wrap(
                "A starting point exists only to make a measured change "
                "easier to interpret. It is NOT a recommended architecture, "
                "not an optimal design, and not a target - a design that "
                "differs from it is not thereby wrong.", 68):
            out.append(f"     {line}")
    out.append("")
    return out


def _node_field(chosen, application_default) -> str:
    """The node in use, with its origin.

    A value the user picked and one the application supplied are different
    facts, and a screen that shows only the number invites the reader to
    assume they chose it.
    """
    from .process import node_name
    if chosen:
        return f"{node_name(chosen)}  (selected)"
    if application_default:
        return f"{node_name(application_default)}  (application default)"
    return "not specified"


def render_latency_flow(a: ReviewAnalysis) -> List[str]:
    """Where this design's time goes, in the order it happens.

    Replaces the composition list, which sorted stations by size. That is
    the right order for "what should I change next" and the wrong order
    for "what happens to a job" - drawn that way, a flow tells a reader
    the accelerator runs before the host.
    """
    from .visual import build_flow, render_flow_text

    out = _heading(2, "Latency Flow")
    out.append("     Scope: the current design only")
    out.append("")
    data = build_flow(a)
    problems = data.consistent()
    # Section 3 states the limiting factor and does it more fully. Printed
    # here as well, the same two lines appeared twice on one screen with
    # nothing to say why - so the flow shows the path and section 3 keeps
    # the verdict.
    for line in render_flow_text(data, show_limits=False):
        out.append(f"   {line}" if line.strip() else "")
    if problems:
        # Reported, not hidden. A flow whose shares do not close, or whose
        # stations are out of order, is still drawn - with the fault named
        # beside it, because silently correcting it would leave a reader
        # trusting a picture nobody checked.
        out.append("")
        out.append("     FLOW DEFECT:")
        for p in problems:
            out.append(f"       {p}")
    out.append("")
    return out


def render_latency_change(a: ReviewAnalysis) -> List[str]:
    """What the change did, decomposed, with the residue printed."""
    out = _heading(2, "Latency Change Breakdown")
    # Sections 2 and 3 describe different things and sit next to each other.
    # Section 2 is the CHANGE between two designs; section 3 is the CURRENT
    # design's own composition. Without saying so, "host active -0.319 ms"
    # above "host active, 90.0%" reads as a contradiction.
    out.append("     Scope: change between the starting point and the "
               "current design")
    out.append("")
    out.append(f"     Where the {abs(a.latency_change_total):.3f} ms went:")
    out.append("")
    for name, delta in a.latency_change:
        if abs(delta) < 1e-12:
            continue
        out.append(f"     {name:<26s}{delta:+10.3f} ms")
    out.append(f"     {'-' * 38}")
    out.append(f"     {'net':<26s}{a.latency_change_total:+10.3f} ms")
    if abs(a.latency_change_residue) > 1e-9:
        out.append("")
        out.append(f"     {'UNACCOUNTED':<26s}"
                   f"{a.latency_change_residue:+10.6f} ms")
        out.append("     A breakdown that quietly absorbed this would look")
        out.append("     complete, which is why it is printed.")
    out.append("")
    return out


def render_limiting_factor(a: ReviewAnalysis) -> List[str]:
    """Two figures, side by side, never merged."""
    out = _heading(3, "Current Limiting Factor")
    out.append("     Scope: the current design only")
    out.append("")
    lim = a.limiting
    out.append(f"     {'Dominant latency component':<30s}"
               f"{lim.dominant_component}, "
               f"{lim.dominant_share_pct:.1f}%")
    out.append(f"     {'Analytical limiting factor':<30s}"
               f"{lim.analytical_limit}")
    if lim.analytical_limit_plain:
        # Wrapped at 44 into a 35-column indent, which reaches 79 for the
        # longest plain-language limit. Narrowed so the deepest indent in
        # this section still fits the rule everything else obeys.
        for line in _wrap(lim.analytical_limit_plain, 42):
            out.append(f"     {'':<30s}{line}")
    if True:
        out.append("")
        # Written from THIS analysis. The generic sentence described an
        # accelerator waiting on bandwidth under a review whose limit was
        # compute and whose dominant station was the host - a reader
        # checking the explanation against the two lines above it found it
        # described neither.
        # Which sentence depends on WHERE the limit lives, not on whether
        # two strings differ. "compute" is a mechanism inside the
        # accelerator, so an accelerator-dominant design limited by compute
        # points at one part of the architecture - and the old wording
        # called that "not the same station".
        same = limit_points_at(lim.dominant_component, lim.analytical_limit)
        if same:
            sentence = (
                f"The dominant station is {lim.dominant_component}, and the "
                f"analytical limiting factor is {lim.analytical_limit} "
                f"within that station. They are different quantities, but "
                f"they point to the same part of the architecture here. "
                f"Relieving {lim.analytical_limit} is what raises the "
                f"ceiling.")
        else:
            sentence = (
                f"The dominant latency component and the analytical "
                f"limiting factor point to different parts of the "
                f"architecture here. "
                f"{lim.dominant_component.capitalize()} holds "
                f"{lim.dominant_share_pct:.1f}% of one job, so that is "
                f"where the time is; {lim.analytical_limit} is what stops "
                f"the design going faster once the time is spent.")
        for line in _wrap(sentence, 68):
            out.append(f"     {line}")
    out.append("")
    return out


def render_measured_results(a: ReviewAnalysis) -> List[str]:
    from .visual import (render_measured_bars, measured_bars_legend,
                         margin_legend)

    out = _heading(4, "Measured Results")
    for line in render_measured_bars(a.measured):
        out.append(f"     {line}" if line.strip() else "")
    out.append(f"     {measured_bars_legend()}")
    for line in margin_legend().splitlines():
        out.append(f"     {line}")
    out.append("")
    return out


def render_balance_section(a: ReviewAnalysis) -> List[str]:
    from .visual import render_balance_text

    title = ("Architecture Balance" if a.variant == SINGLE
             else "Architecture Balance Comparison")
    out = _heading(5, title)
    for line in render_balance_text(a.balance, show_title=False):
        out.append(f"   {line}" if line.strip() else "")
    out.append("")
    return out


def render_exploration(a: ReviewAnalysis) -> List[str]:
    """Measured alternatives, not advice."""
    out = _heading(6, "What to Explore Next")
    if not a.exploration:
        out.append("     No station holds enough of the time for a change")
        out.append("     to it to be worth measuring.")
        out.append("")
        return out
    # The bound is quoted from THIS analysis. A fixed "a station that is
    # 6% of the time" appeared under a review whose smallest station was
    # 26.5%, and a reader checking the sentence against the table below it
    # finds no 6% anywhere.
    # Shares can be NaN when the model could not time this design at all.
    # min() over NaNs returns one, and no entry then compares equal to it,
    # so the lookup raised IndexError - on the one path where the review
    # most needs to say what it does not know.
    import math as _mx
    usable = [(n, sh) for n, sh, _ in a.exploration
              if sh is not None and not _mx.isnan(sh)]
    if not usable:
        out.append("     The model could not time this design, so there is")
        out.append("     no share to bound a change by.")
        out.append("")
        for i, (name, share, why) in enumerate(a.exploration, 1):
            out.append(f"     {i}. {name}")
        out.append("")
        return out
    name_of_smallest, smallest = min(usable, key=lambda kv: kv[1])
    out.append("     Ranked by how much of one job each holds. A station")
    out.append(f"     cannot give back more than the share it holds: "
               f"{name_of_smallest.lower()}")
    out.append(f"     is {smallest:.1f}% here, so no change to it can save")
    out.append(f"     more than {smallest:.1f}%, however much is spent.")
    out.append("")
    for i, (name, share, why) in enumerate(a.exploration, 1):
        # The reason wraps under the station rather than trailing it: at
        # 92 characters the explanation was the part that ran off, which
        # is the part a reader needs.
        out.append(f"     {i}. {name:<24s}{share:5.1f}%")
        for line in _wrap(why, 58):
            out.append(f"        {line}")
    out.append("")
    return out


def render_deployment(a: ReviewAnalysis) -> List[str]:
    out = _heading(7, "Deployment Assessment")
    if a.deployment_ready:
        out.append("     READY")
        out.append("     Every requirement is satisfied: latency,")
        out.append("     throughput, power, cost, thermal, cooling class")
        out.append("     and capacity.")
    else:
        out.append("     NOT READY")
        out.append(f"     Unmet: {', '.join(a.deployment_unmet)}")
        out.append("")
        for r in a.measured:
            if r.over and r.in_deployment_verdict:
                out.append(f"     {r.label:<24s}{r.value:>10.3g} "
                           f"{r.unit} against {r.limit:.2f}")
    out.append("")
    return out


def render_takeaway(a: ReviewAnalysis) -> List[str]:
    out = _heading(8, "Engineering Takeaway")
    for line in _wrap(a.takeaway, 68):
        out.append(f"     {line}")
    out.append("")
    return out


# The full statement, and the concise repeat. A file travels on its own, so
# an exported report always carries the full text whatever the session order.
BOUNDARY_FULL = (
    "Everything above is an analytical engineering estimate, computed from "
    "models rather than measured on hardware. What none of it contains is "
    "what the latency is worth, what the schedule allows, what a competitor "
    "is shipping, or what the customer will pay. Those decide the answer as "
    "much as the numbers do, and this tool does not know any of them. The "
    "facts are the tool's. The decision is the designer's.")

BOUNDARY_SHORT = (
    "Analytical estimates, not measured hardware results. The decision "
    "remains with the designer. Use View Model Boundaries for the full "
    "statement.")

_SESSION_SEEN = {"shown": False}


def render_boundaries(a: ReviewAnalysis, force_full: bool = False
                      ) -> List[str]:
    out = _heading(9, "Assumptions and Model Boundaries")
    first = force_full or not _SESSION_SEEN["shown"]
    text = BOUNDARY_FULL if first else BOUNDARY_SHORT
    for line in _wrap(text, 68):
        out.append(f"     {line}")
    _SESSION_SEEN["shown"] = True
    out.append("")
    return out


SECTION_RENDERERS: Dict[str, Callable] = {
    "architecture_summary": render_architecture_summary,
    "latency_flow": render_latency_flow,
    "latency_change": render_latency_change,
    "limiting_factor": render_limiting_factor,
    "measured_bars": render_measured_results,
    "balance": render_balance_section,
    "balance_comparison": render_balance_section,
    "recommendation": render_exploration,
    "deployment": render_deployment,
    "takeaway": render_takeaway,
    "boundaries": render_boundaries,
}


# ==============================================================================
# The one entry point
# ==============================================================================

def review_lines(a: ReviewAnalysis, force_full_boundaries: bool = False
                 ) -> Tuple[List[str], Dict[str, str]]:
    """Assemble every required section, and record what each described.

    The identity map is returned rather than merely checked, so a caller -
    an export, a test - can verify that every section described the same
    design without re-deriving anything.
    """
    lines: List[str] = []
    identity: Dict[str, str] = {}
    for section in sections_for(a.variant):
        fn = SECTION_RENDERERS[section.section_id]
        if section.section_id == "boundaries":
            lines += fn(a, force_full=force_full_boundaries)
        else:
            lines += fn(a)
        identity[section.section_id] = (
            f"{a.current_config_id}/{a.starting_config_id}")
    return lines, identity


def identity_violations(identity: Dict[str, str], a: ReviewAnalysis
                        ) -> List[str]:
    """Every section must have described the same designs.

    A chart that renders correctly while describing a different design from
    the bars beside it is the worst defect available here: invisible, and
    wrong in the direction of confidence.
    """
    expected = f"{a.current_config_id}/{a.starting_config_id}"
    return [f"{sid}: described {got!r}, expected {expected!r}"
            for sid, got in identity.items() if got != expected]


def render_standard_engineering_review(analysis: ReviewAnalysis,
                                       images: bool = True,
                                       force_full_boundaries: bool = False,
                                       heading: Optional[str] = None,
                                       subheading: Optional[str] = None
                                       ) -> Dict:
    """The single exit point of every engineering analysis.

    A workflow may render input guidance and progress. It may not assemble,
    omit, reorder or duplicate review sections, and it never asks whether to
    show this - asking implies the core result is optional.
    """
    wf = BY_WORKFLOW[analysis.workflow_id]
    lines, identity = review_lines(analysis, force_full_boundaries)

    # A caller may name the screen it is continuing. A demo's title is its
    # QUESTION, and repeating the workflow name below it turned one screen
    # into two - the reader has to work out that the second is the answer
    # to the first rather than a new topic.
    print(f"\n{LINE}")
    print(f" {heading or 'STANDARD ENGINEERING DESIGN REVIEW'}")
    print(f" {subheading or (wf.canonical_name + '  -  ' + analysis.app_name)}")
    print(LINE)
    for line in lines:
        print(line)

    bad = identity_violations(identity, analysis)
    if bad:
        print(f"  IDENTITY DEFECT - sections describe different designs:")
        for b in bad:
            print(f"     {b}")

    # Images are attempted only where the environment can show them. A
    # terminal has never displayed one, so reporting their absence there
    # announces a deficiency that is not one - and a user reads "something
    # failed" under a complete result.
    images_shown = False
    images_expected = False
    if images:
        try:
            from .core import in_notebook
            images_expected = bool(in_notebook())
        except Exception:
            images_expected = False
        if images_expected:
            images_shown = _render_images(analysis)
    if images_expected and not images_shown:
        print("     Inline image rendering was unavailable.")
        print("     The complete text-based engineering review is shown "
              "above.")
    print(LINE)
    return {"sections": [s.section_id for s in sections_for(analysis.variant)],
            "identity": identity, "identity_violations": bad,
            "images": images_shown}


# THE NOTEBOOK PANELS, in the order the analysis makes them.
#
# Every renderer exists and the notebook path called ONE of them, so a
# reader in Jupyter saw the Architecture Balance and nothing else - and
# reasonably concluded Jupyter could not draw the rest. Streamlit named
# each panel explicitly; the notebook relied on a single call and got a
# single picture.

NOTEBOOK_PANELS = (
    ("Measured Results", "measured"),
    ("System Flow and Bottleneck Map", "flow_map"),
    ("Bottleneck Analysis", "bottleneck"),
    ("Architecture Balance", "balance"),
)


def notebook_panels(a: "ReviewAnalysis") -> List[Dict]:
    """Build every panel and report what happened to each.

    Returns one record per panel so a caller - or a check - can see
    which were created, which were displayed and which do not apply,
    rather than inferring it from what appeared on screen.
    """
    import os

    out: List[Dict] = []
    for title, kind in NOTEBOOK_PANELS:
        rec = {"panel": title, "kind": kind, "status": "MISSING",
               "figure_created": False, "displayed": False,
               "path": "", "note": ""}
        try:
            path = _build_panel(a, kind)
            if path is None:
                rec["status"] = "NOT APPLICABLE"
                rec["note"] = "this analysis has no such panel"
            elif os.path.isfile(path):
                rec["figure_created"] = True
                rec["path"] = path
                rec["status"] = "CREATED"
            else:
                rec["note"] = "the renderer returned a path that is not "\
                              "on disk"
        except Exception as exc:
            rec["status"] = "FAILED"
            rec["note"] = f"{type(exc).__name__}: {exc}"
        out.append(rec)
    return out


def _balance_note(a: "ReviewAnalysis") -> str:
    """What the blank and pinned axes on the balance chart mean."""
    try:
        series = a.balance.axes[0][1]
    except Exception:
        return ""
    absent = [x.name for x in series if x.score is None]
    pinned = [x.name for x in series
              if getattr(x, "clipped", False)]
    parts = []
    if absent:
        parts.append(
            f"*{', '.join(absent)} carry no score. Power has no "
            f"established measurement basis (PW-Q1) and traffic has one "
            f"established component of ten (TR-D1), so the polygon "
            f"breaks rather than plotting a zero - a gap is not a "
            f"score of nothing.*")
    if pinned:
        parts.append(
            f"*{', '.join(pinned)} sit at the rim. This chart scores "
            f"against the application's requirement, where 50 means "
            f"meeting it exactly, and a design far above its budget "
            f"pins at 100. Use Benchmark Comparison to see the "
            f"difference between two designs above their "
            f"requirements.*")
    return "  \n".join(parts)


def _build_panel(a: "ReviewAnalysis", kind: str):
    """One panel. Returns a path, or None when it does not apply."""
    if kind == "balance":
        from .visual import render_balance_png
        return render_balance_png(a.balance, "review_balance.png")
    if kind == "measured":
        from .visual.balance import render_measured_bars_png
        readings = getattr(a, "measured", None) or getattr(
            a, "readings", None)
        if not readings:
            return None
        return render_measured_bars_png(readings,
                                        "review_measured.png")
    if kind == "flow_map":
        from .flow_map import build_flow_map, render_flow_map_png
        return render_flow_map_png(build_flow_map(a),
                                   "review_flow_map.png")
    if kind == "bottleneck":
        from .visual import build_flow, render_flow_png
        return render_flow_png(build_flow(a), "review_flow.png")
    return None


def _render_images(a: "ReviewAnalysis") -> bool:
    """Optional. A PNG failure must never fail the review.

    EVERY PANEL IS DISPLAYED EXPLICITLY. Relying on the last figure, or
    on one global show(), is how three of four pictures went missing
    without anything reporting it.
    """
    try:
        from .core import in_notebook
        if not in_notebook():
            return False
        from IPython.display import Image, display, Markdown
    except Exception:
        return False

    shown = 0
    for rec in notebook_panels(a):
        try:
            if rec["status"] == "CREATED" and rec["path"]:
                display(Markdown(f"**{rec['panel']}**"))
                display(Image(filename=rec["path"]))
                # WHY AN AXIS IS BLANK OR PINNED.
                #
                # `n/e` and `100+` are the documented behaviour, not a
                # fault, and a reader who is not told that reasonably
                # reads a half-empty chart as a broken one.
                if rec["kind"] == "balance":
                    note = _balance_note(a)
                    if note:
                        display(Markdown(note))
                rec["displayed"] = True
                rec["status"] = "DISPLAYED"
                shown += 1
            elif rec["status"] == "NOT APPLICABLE":
                display(Markdown(f"*{rec['panel']}: not applicable to "
                                 f"this analysis.*"))
            else:
                # A PANEL THAT FAILED SAYS SO. Silence reads as "this
                # interface cannot draw it".
                display(Markdown(f"*{rec['panel']}: not shown - "
                                 f"{rec['note'] or rec['status']}.*"))
        except Exception:
            continue
    return shown > 0

