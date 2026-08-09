"""
ppact.engineering_report - one report, built from one thing

THE BUILDER OWNS THE CONTRACT
=============================
The screen used to display whatever a task printed, so a task that drew
no System Flow left the screen without one - four workflows produced
four of seven panels and each was missing something different.

    workflow    asks questions and returns a WorkflowOutcome
    builder     computes everything the panels need
    renderer    displays, and computes nothing

Adding a panel means changing this file and nothing else. Under the old
arrangement it meant editing every workflow, and the ones nobody
remembered kept the old shape.

ONE PUBLIC ENTRY POINT
----------------------
`build_engineering_report(outcome)`. Not a config, not two configs, not
an analysis. Which design is the reference and which is current is a
fact the outcome carries; a builder taking two positional configurations
invites the caller to swap them, and nothing downstream could tell.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .outcome import (WorkflowOutcome, WorkflowStatus, WorkflowVariant)


class PanelKey(str, Enum):
    """The seven panels. Fixed names, fixed order."""
    ARCHITECTURE = "architecture_summary"
    MEASURED = "measured_results"
    FLOW = "system_flow"
    BOTTLENECK = "bottleneck_analysis"
    BALANCE = "architecture_balance"
    CONCLUSION = "engineering_conclusion"
    NEXT = "recommended_next_comparisons"


PANEL_ORDER: Tuple[PanelKey, ...] = (
    PanelKey.ARCHITECTURE, PanelKey.MEASURED, PanelKey.FLOW,
    PanelKey.BOTTLENECK, PanelKey.BALANCE, PanelKey.CONCLUSION,
    PanelKey.NEXT,
)

PANEL_TITLE: Dict[PanelKey, str] = {
    PanelKey.ARCHITECTURE: "Architecture Summary",
    PanelKey.MEASURED: "Measured Results",
    PanelKey.FLOW: "System Flow",
    PanelKey.BOTTLENECK: "Bottleneck Analysis",
    PanelKey.BALANCE: "Architecture Balance",
    PanelKey.CONCLUSION: "Engineering Conclusion",
    PanelKey.NEXT: "Recommended Next Comparisons",
}


class PanelStatus(str, Enum):
    READY = "ready"
    NOT_ESTABLISHED = "not_established"
    FAILED = "failed"


@dataclass(frozen=True)
class PanelRow:
    """One line of a panel. `starting` is empty on a single design.

    THE DISPLAYED STRING AND THE VALUE BEHIND IT ARE DIFFERENT THINGS.

    The semantic digest was built from the formatted text, so changing
    a number's format from four significant figures to six changed the
    digest - a formatting edit read as a change of meaning, and every
    picture would have been re-judged for nothing. `raw_starting` and
    `raw_current` carry the values; the digest uses those.
    """
    label: str
    starting: str = ""
    current: str = ""
    delta: str = ""
    mark: str = ""
    raw_starting: Any = None
    raw_current: Any = None
    # WHAT THIS ROW IS, independent of what it is called.
    #
    # `label` is display text: renaming "Memory packages" to "Memory
    # modules" changed the digest, and a wording edit read as a change
    # of meaning. The key is the field the row reports.
    key: str = ""
    # WHERE THE VALUE CAME FROM.
    #
    # Provenance, not formatting. The same 7 nm chosen by the reader and
    # arrived at by an application default mean different things to a
    # review, so this belongs in the digest.
    provenance: str = ""

    def semantic_parts(self) -> Tuple[str, ...]:
        """What this row means, independent of how it is printed."""
        def one(raw, shown):
            if raw is None:
                return shown
            if isinstance(raw, float):
                # Rounded so a float differing in the last bit is not a
                # different meaning; wide enough that a real change is.
                return f"{raw:.10g}"
            return str(raw)
        return (self.key or self.label,
                one(self.raw_starting, self.starting),
                one(self.raw_current, self.current),
                self.provenance)


# WHAT EACH PANEL ACTUALLY DEPENDS ON.
#
# Two designs with different configurations produced the same
# Architecture Balance PNG, and a check comparing configurations called
# that a defect. It is not: the balance scores against the application's
# requirement, so two designs both far above budget pin at the same
# value and the picture is correctly identical. The conclusion for two
# host-limited designs is correctly the same sentence.
#
# Comparing configurations asks the wrong question. What decides whether
# two pictures should match is whether the panel's OWN INPUT matched,
# and that differs per panel:
#
#     Measured Results       the figures it prints
#     System Flow            modules, links, and which element limits
#     Architecture Balance   the axis scores, not the parts
#     Conclusion             the sentences, which are a summary
#     Recommendations        the rules that fired and their order
#
# The registry is declared so the question can be asked correctly, and
# so a panel added later has to say what it depends on.
# THREE CONTRACTS, JUDGED SEPARATELY.
#
# Semantic correctness and human readability are different claims, and a
# single verdict over both is wrong in whichever direction it is
# collapsed: "everything passed" overstates a screen that is complete
# and too small to read, and a readability warning would drag down
# arithmetic that is sound.
#
#     Semantic evidence        does the screen claim what the engine
#                              computed, and is that traceable
#     Rendering completeness   is every panel whole
#     Readability              can a person read it at this width
#
# The System Flow at 768 px is PASS / PASS / WARNING: whole, correct,
# and small.
RELEASE_AXES: Tuple[Tuple[str, str], ...] = (
    ("semantic_evidence",
     "the screen's claim matches the engine's result, and every figure "
     "traces back through scenario, configuration, view data and "
     "figure digests"),
    ("rendering_completeness",
     "every declared panel is present and whole"),
    ("readability",
     "a person can read the figure at this width. Separate from "
     "completeness: a panel can be entire and still too small"),
)


# WHAT IS MEANING AND WHAT IS PRESENTATION.
#
# A semantic digest hashes what a screen CLAIMS, not how it looks. The
# distinction was learnt the hard way: changing a number's format from
# four significant figures to six changed the digest, and a wording edit
# from "Memory packages" to "Memory modules" did too - both read as
# changes of meaning, and every picture would have been re-judged for
# nothing.
#
# Declared as a table so a new item has to be classified rather than
# defaulting into the digest by being nearby.
SEMANTIC_ITEMS: Tuple[Tuple[str, bool, str], ...] = (
    ("raw value", True,
     "the number or key behind the display string"),
    ("requirement", True,
     "what the value is judged against"),
    ("limiting element", True,
     "which module or link holds the system"),
    ("provenance", True,
     "selected by the reader, or an application default. The same 7 nm "
     "means different things to a review depending on which"),
    ("panel status", True,
     "READY, NOT ESTABLISHED or FAILED"),
    ("field key", True,
     "which configuration field a row reports"),

    ("display label", False,
     "the row's printed name; renaming it changes no claim"),
    ("unit suffix", False, "GB/s, ms, mm2 as printed"),
    ("decimal places", False, "4g against 6g is one value"),
    ("thousands separator", False, "1,024 against 1024"),
    ("column width", False,
     "how wide a column is printed; the same figures either way"),
    ("colour", False, "the value band is derived from the value"),
    ("legend position", False,
     "where the key sits; the bands it names are unchanged"),
    ("figure size", False,
     "the same figure at 1440 and 768 makes the same claim"),
)

SEMANTIC_ITEM = {name: is_meaning for name, is_meaning, _why
                 in SEMANTIC_ITEMS}


PANEL_DEPENDS_ON: Dict[str, str] = {
    "architecture_summary":
        "the configuration fields of both designs",
    "measured_results":
        "the metric values printed, for both designs",
    "system_flow":
        "module utilisations, link loads, and which element limits the "
        "system - not the parts that produced them",
    "bottleneck_analysis":
        "the per-module utilisations and the limiting element",
    "architecture_balance":
        "the axis scores. These are measured against the application's "
        "requirement, so two designs both far above budget score the "
        "same and the chart is correctly identical",
    "engineering_conclusion":
        "the sentences produced. Two designs limited by the same "
        "element yield the same conclusion, which is a fact about the "
        "designs and not a defect",
    "recommended_next_comparisons":
        "the rules that fired, their order and their priority classes",
}


@dataclass(frozen=True)
class Panel:
    key: PanelKey
    title: str
    status: PanelStatus
    variant: WorkflowVariant
    rows: Tuple[PanelRow, ...] = ()
    lines: Tuple[str, ...] = ()
    image: str = ""
    note: str = ""
    # WHAT DROVE THE FIGURE, for panels whose content is a picture.
    #
    # System Flow and Architecture Balance carry everything in an image
    # and have no rows, so a digest over rows would call every one of
    # them identical. The values behind the drawing are recorded here.
    semantic_input: Tuple[Tuple[str, str], ...] = ()

    def semantic_digest(self) -> str:
        """What this panel was asked to show.

        Not the picture and not the configuration: the values the panel
        itself received. Two panels with one semantic digest must draw
        the same thing, and two with different digests must not.
        """
        import hashlib
        parts = [self.key.value, self.status.value, self.note]
        parts += list(self.lines)
        for r in self.rows:
            # `delta` is derived from the two values and `mark` from
            # their comparison, so neither adds meaning the values do
            # not already carry - and both are formatted text.
            parts.append("\x1e".join(r.semantic_parts()))
        for k, v in self.semantic_input:
            parts.append(f"{k}\x1e{v}")
        return hashlib.sha256(
            "\x1f".join(parts).encode()).hexdigest()[:16]


@dataclass(frozen=True)
class EngineeringReportViewData:
    """Everything seven panels need, computed. Nothing displayed.

    A renderer reads this and formats it. A renderer that computes has
    put the engine back into the interface, which is the arrangement
    this file exists to end.
    """
    workflow_id: str
    variant: WorkflowVariant
    app_key: str
    app_name: str
    starting_label: str
    current_label: str
    panels: Tuple[Panel, ...]
    engine_version: str = ""
    model_digest: str = ""

    def by_key(self) -> Dict[PanelKey, Panel]:
        return {p.key: p for p in self.panels}

    @property
    def comparative(self) -> bool:
        return self.variant is WorkflowVariant.COMPARISON

    @property
    def missing(self) -> Tuple[str, ...]:
        return tuple(p.title for p in self.panels
                     if p.status is PanelStatus.FAILED)

    def digest(self) -> str:
        """A digest of what the report SAYS, not of how it looks.

        Two builds of one outcome must agree; if they do not, something
        non-deterministic reached the report.
        """
        import hashlib
        parts = [self.workflow_id, self.variant.value, self.app_key,
                 self.starting_label, self.current_label]
        for p in self.panels:
            parts.append(f"{p.key.value}:{p.status.value}:{p.note}")
            parts += [f"{r.label}|{r.starting}|{r.current}|{r.delta}|"
                      f"{r.mark}" for r in p.rows]
            parts += list(p.lines)
        return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()


def build_engineering_report(
        outcome: WorkflowOutcome) -> EngineeringReportViewData:
    """The seven panels for one completed workflow.

    THE ONLY PUBLIC ENTRY POINT, and it takes one argument.
    """
    if not isinstance(outcome, WorkflowOutcome):
        raise TypeError(
            "build_engineering_report takes a WorkflowOutcome. A "
            "configuration or a pair of them leaves the caller to say "
            "which is the reference, and nothing downstream could tell "
            "if they swapped: "
            f"got {type(outcome).__name__}")
    if outcome.status is not WorkflowStatus.COMPLETED:
        raise ValueError(
            f"{outcome.workflow_id}: a report needs a completed "
            f"workflow, not {outcome.status.value}")

    from .application import APPLICATION_LIBRARY
    from .review import build_review

    comparative = outcome.comparative
    current = build_review(outcome.workflow_id, outcome.app_key,
                           outcome.current_config,
                           outcome.starting_config if comparative
                           else None)
    starting = (build_review("education_step_by_step", outcome.app_key,
                             outcome.starting_config)
                if comparative else None)

    app = APPLICATION_LIBRARY.get(outcome.app_key)
    panels = [
        _architecture(outcome, comparative),
        _measured(outcome, current, starting, comparative),
        _flow(outcome, current, starting, comparative),
        _bottleneck(outcome, current, starting, comparative),
        _balance(outcome, current, starting, comparative),
        _conclusion(outcome, current, starting, comparative),
        _next(outcome, current, starting, comparative),
    ]
    order = {k: i for i, k in enumerate(PANEL_ORDER)}
    panels.sort(key=lambda p: order[p.key])

    prov = _provenance()
    return EngineeringReportViewData(
        workflow_id=outcome.workflow_id, variant=outcome.variant,
        app_key=outcome.app_key,
        app_name=getattr(app, "name", outcome.app_key),
        starting_label=(_label(outcome.starting_config)
                        if comparative else ""),
        current_label=_label(outcome.current_config),
        panels=tuple(panels), engine_version=prov[0],
        model_digest=prov[1])


# ==============================================================================
# One function per panel. Each computes; none displays.
# ==============================================================================

def _panel(key, variant, status=PanelStatus.READY, **kw) -> Panel:
    return Panel(key=key, title=PANEL_TITLE[key], status=status,
                 variant=variant, **kw)


def _application_default(field: str, outcome):
    """The value the application supplies when the reader chose none."""
    try:
        from .application import APPLICATION_LIBRARY
        app = APPLICATION_LIBRARY.get(outcome.app_key)
        return getattr(app, f"default_{field}", None)
    except Exception:
        return None


def _default_for(field: str, outcome) -> bool:
    """Whether this field was left to the application's default."""
    if field not in ("soc_node", "accel_node"):
        return False
    try:
        from .application import APPLICATION_LIBRARY
        app = APPLICATION_LIBRARY.get(outcome.app_key)
        return getattr(app, f"default_{field}", None) is not None
    except Exception:
        return False


def _mark_for(comparative, r, c) -> str:
    return "changed" if comparative and r != c else ""


def _architecture(outcome, comparative) -> Panel:
    cur, ref = outcome.current_config, outcome.starting_config
    rows = []
    for f in dataclasses.fields(cur):
        c = getattr(cur, f.name, None)
        r = getattr(ref, f.name, None) if comparative else None

        # A FIELD LEFT UNSET IS STILL A DECISION THE DESIGN RESTS ON.
        #
        # An unset process node was skipped entirely, so the summary did
        # not say which node the figures were computed at - and the
        # provenance the digest carries could never read "application
        # default", because the row was not there to carry it.
        # BOTH SIDES, OR NEITHER.
        #
        # The default was filled in for the current design only, so a
        # comparison where neither design set a process node reported
        # "- -> 16 nm  changed" - a change that never happened, on the
        # screen a reader uses to see what changed.
        via_default = False
        if _default_for(f.name, outcome):
            fill = _application_default(f.name, outcome)
            if c is None and fill is not None:
                c = fill
                via_default = True
            if comparative and r is None and fill is not None:
                r = fill
        if c is None and r is None:
            continue
        rows.append(PanelRow(
            label=FIELD_LABEL.get(f.name,
                                  f.name.replace("_", " ").capitalize()),
            # PROVENANCE IS ITS OWN COLUMN.
            #
            # Appended to the value, "16 nm (scaling reference)
            # (application default)" overran the cell at 1440 px and was
            # cut to "...(application defau". Provenance is declared
            # semantic in the registry, so a reader who cannot see it
            # cannot tell a chosen node from a defaulted one - the
            # distinction the column exists to make.
            starting=("" if not comparative
                      else _pretty(f.name, r)),
            current=_pretty(f.name, c),
            raw_starting=r if comparative else None, raw_current=c,
            key=f.name,
            mark=("application default" if via_default
                  else _mark_for(comparative, r, c)),
            provenance=("application default" if via_default
                        else "selected")))
    return _panel(PanelKey.ARCHITECTURE, outcome.variant,
                  rows=tuple(rows),
                  note=f"application: {outcome.app_key}")


# WHERE THE MARGINS COME FROM.
#
# This panel had its own list of six metric names and printed the raw
# numbers. The terminal was showing nine readings with the requirement,
# the direction, the margin and a COMFORTABLE / TIGHT / CRITICAL
# verdict beside each - so the same screen said less in the browser than
# in a shell, and a reader could not tell whether a figure passed.
#
# `analysis.measured` is what the terminal renders. The panel reads it
# instead of assembling a second, poorer list.
MARGIN_CRITICAL = 2.0
MARGIN_TIGHT = 10.0


def _verdict(reading) -> Tuple[str, str]:
    """The margin against the requirement, and what to call it."""
    v, lim = reading.value, reading.limit
    if v is None or lim in (None, 0):
        return "", "no requirement stated"
    if reading.lower_is_better:
        if v > lim:
            return f"{(v - lim) / lim * 100.0:.0f}% over",  "EXCEEDS"
        margin = (lim - v) / lim * 100.0
    else:
        if v < lim:
            return f"{(lim - v) / lim * 100.0:.0f}% short", "EXCEEDS"
        margin = (v - lim) / lim * 100.0 if lim else 0.0
    band = ("CRITICAL" if margin < MARGIN_CRITICAL
            else "TIGHT" if margin < MARGIN_TIGHT else "COMFORTABLE")
    return f"{margin:.0f}% margin", band


def _measured(outcome, current, starting, comparative) -> Panel:
    readings = getattr(current, "measured", None) or ()
    ref = {r.label: r for r in
           (getattr(starting, "measured", None) or ())} \
        if comparative else {}

    rows = []
    for reading in readings:
        prev = ref.get(reading.label)
        amount, band = _verdict(reading)
        limit = ("—" if reading.limit is None else
                 f"{'max' if reading.lower_is_better else 'min'} "
                 f"{reading.limit:,.4g} {reading.unit}")
        rows.append(PanelRow(
            label=f"{reading.label} ({reading.unit})",
            starting=(_num(prev.value) if comparative and prev
                      else ""),
            current=_num(reading.value),
            delta=(_delta(prev.value, reading.value)
                   if comparative and prev else ""),
            mark=f"{limit}  {band}  {amount}".strip(),
            raw_starting=(prev.value if comparative and prev
                          else None),
            raw_current=reading.value, key=reading.label))
    return _panel(PanelKey.MEASURED, outcome.variant,
                  status=PanelStatus.READY if rows
                  else PanelStatus.NOT_ESTABLISHED,
                  rows=tuple(rows),
                  note="'max' is a ceiling, 'min' a floor. The margin "
                       "is measured against the requirement, not "
                       "against another design.")


def _flow(outcome, current, starting, comparative) -> Panel:
    import os
    import tempfile
    from .flow_map import (build_flow_map, render_flow_map_png,
                           build_compared_flow_map,
                           render_compared_flow_map_png)
    work = tempfile.mkdtemp(prefix="ppact_report_")
    path = os.path.join(work, "flow.png")
    try:
        if comparative:
            cm = build_compared_flow_map(
                starting, current, _label(outcome.starting_config),
                _label(outcome.current_config))
            made = render_compared_flow_map_png(cm, path)
        else:
            made = render_flow_map_png(build_flow_map(current), path)
        # THE VALUES BEHIND THE DRAWING, so two flow maps can be
        # compared without comparing pixels.
        fm_now = build_flow_map(current)
        sem = [("limiting", f"{fm_now.limiting}/{fm_now.limiting_kind}")]
        for mod in fm_now.modules:
            sem.append((f"module/{mod.name}",
                        f"{mod.utilisation_pct}/"
                        f"{mod.latency_share_pct}/{mod.is_bottleneck}"))
        for lk in fm_now.links:
            sem.append((f"link/{lk.source}->{lk.target}",
                        f"{lk.load_pct}/{lk.demand_gbs}/"
                        f"{lk.available_gbs}/{lk.is_bottleneck}"))
        if comparative:
            fm_ref = build_flow_map(starting)
            sem.append(("limiting_before",
                        f"{fm_ref.limiting}/{fm_ref.limiting_kind}"))
            for mod in fm_ref.modules:
                sem.append((f"before/module/{mod.name}",
                            f"{mod.utilisation_pct}/"
                            f"{mod.latency_share_pct}"))
        return _panel(PanelKey.FLOW, outcome.variant,
                      status=PanelStatus.READY if made
                      else PanelStatus.FAILED,
                      image=made or "",
                      semantic_input=tuple(sem))
    except Exception as exc:
        return _panel(PanelKey.FLOW, outcome.variant,
                      status=PanelStatus.FAILED,
                      note=f"{type(exc).__name__}: {exc}")


def _bottleneck(outcome, current, starting, comparative) -> Panel:
    from .flow_map import build_flow_map, bottleneck_migration
    try:
        fm = build_flow_map(current)
        ref = build_flow_map(starting) if comparative else None
        rows = []
        for mod in fm.modules:
            was = ""
            if comparative and ref is not None:
                prev = next((x for x in ref.modules
                             if x.name == mod.name), None)
                was = _pct(prev.utilisation_pct) if prev else ""
            rows.append(PanelRow(
                label=mod.name, starting=was,
                current=_pct(mod.utilisation_pct),
                mark="LIMITING" if mod.is_bottleneck else ""))
        note = f"{fm.limiting} ({fm.limiting_kind})"
        if comparative:
            mig = bottleneck_migration(starting, current)
            note = mig.reason
        return _panel(PanelKey.BOTTLENECK, outcome.variant,
                      rows=tuple(rows), note=note)
    except Exception as exc:
        return _panel(PanelKey.BOTTLENECK, outcome.variant,
                      status=PanelStatus.FAILED,
                      note=f"{type(exc).__name__}: {exc}")


def _not_established_note(current, starting, comparative) -> str:
    """The blank-axis reasons for whichever chart was drawn."""
    from .visual.balance import not_established_note
    try:
        if comparative:
            axes = _comparison_axes(starting, current)
            names = [a.name for a in (axes.axes if axes else ())
                     if not a.established]
            if not names:
                return ""
            from .visual.balance import NOT_ESTABLISHED_REASON
            parts = ["**n/e = not established**"]
            for n in names:
                r = NOT_ESTABLISHED_REASON.get(n)
                if r:
                    parts.append(f"**{n}** - {r}")
            return "  \n".join(parts)
        return not_established_note(current.balance)
    except Exception:
        return ""


def _balance(outcome, current, starting, comparative) -> Panel:
    import os
    import tempfile
    work = tempfile.mkdtemp(prefix="ppact_report_")
    path = os.path.join(work, "balance.png")
    try:
        if comparative:
            # A COMPARISON USES THE RELATIVE CHART. The
            # requirement-centred one pins two designs above budget at
            # the same value and draws them identically.
            made = _relative_spider(starting, current, outcome, path)
        else:
            from .visual import render_balance_png
            made = render_balance_png(current.balance, path)
        # THE AXIS FIGURES. Two designs both far above the same budget
        # pin at the same score and the picture is correctly identical -
        # comparing their configurations would call that a defect.
        sem = []
        if comparative:
            cmp_axes = _comparison_axes(starting, current)
            for ax in (cmp_axes.axes if cmp_axes else ()):
                sem.append((f"ratio/{ax.name}", str(ax.ratio)))
        else:
            try:
                for _name, series in current.balance.axes:
                    for ax in series:
                        sem.append((f"score/{ax.name}", str(ax.score)))
                    break
            except Exception:
                pass
        return _panel(
            PanelKey.BALANCE, outcome.variant,
            status=PanelStatus.READY if made else PanelStatus.FAILED,
            image=made or "",
            semantic_input=tuple(sem),
            # THE REASONS TRAVEL WITH THE PANEL.
            #
            # They were written in the text renderer and in the
            # notebook path, and this panel attached nothing - so the
            # shipped screen showed two gaps marked `n/e` with no
            # expansion. A reader could not tell not-evaluated from
            # not-applicable from zero from a failure.
            note=(_not_established_note(current, starting, comparative)
                  if made else "the relative comparison chart could "
                               "not be built; no other chart is "
                               "shown in its place"))
    except Exception as exc:
        return _panel(PanelKey.BALANCE, outcome.variant,
                      status=PanelStatus.FAILED,
                      note=f"{type(exc).__name__}: {exc}")


def _conclusion(outcome, current, starting, comparative) -> Panel:
    from .closure import build_closure
    from .flow_map import build_flow_map
    try:
        if comparative:
            changed = [f.name for f in
                       dataclasses.fields(outcome.current_config)
                       if getattr(outcome.current_config, f.name)
                       != getattr(outcome.starting_config, f.name)]
            cl = build_closure(starting, current, changed)
            return _panel(PanelKey.CONCLUSION, outcome.variant,
                          lines=tuple(cl.conclusion),
                          note=cl.key_insight)
        fm = build_flow_map(current)
        return _panel(
            PanelKey.CONCLUSION, outcome.variant,
            lines=(f"The limiting element is the {fm.limiting} "
                   f"{fm.limiting_kind}.",
                   "This is one design, so no change has been "
                   "measured. A statement about what a change does "
                   "needs two designs."))
    except Exception as exc:
        return _panel(PanelKey.CONCLUSION, outcome.variant,
                      status=PanelStatus.FAILED,
                      note=f"{type(exc).__name__}: {exc}")


def _next(outcome, current, starting, comparative) -> Panel:
    from .closure import build_closure
    try:
        if comparative:
            changed = [f.name for f in
                       dataclasses.fields(outcome.current_config)
                       if getattr(outcome.current_config, f.name)
                       != getattr(outcome.starting_config, f.name)]
            cl = build_closure(starting, current, changed)
        else:
            cl = build_closure(current, current, [])
        rows = tuple(
            PanelRow(label=p.title, current=p.priority,
                     delta=p.reason,
                     mark=" + ".join(p.origin_rule_ids))
            for p in cl.next_comparisons)
        return _panel(PanelKey.NEXT, outcome.variant, rows=rows,
                      note="Structurally relevant comparisons, not "
                           "predicted winners. Run each one to "
                           "quantify its effect.")
    except Exception as exc:
        return _panel(PanelKey.NEXT, outcome.variant,
                      status=PanelStatus.FAILED,
                      note=f"{type(exc).__name__}: {exc}")


# ==============================================================================
# Small helpers. None of these display anything.
# ==============================================================================

def _relative_spider(starting, current, outcome, path):
    """The relative chart, or nothing.

    NO SUBSTITUTE CHART.

    This fell back to the requirement-centred balance when the relative
    one could not be built - a different chart under the same panel
    name. The two answer different questions, and a reader told
    "Architecture Balance" would have been shown the other one without
    being told. A panel that cannot be built is FAILED.
    """
    from .demo_visual import render_relative_spider

    cmp = _comparison_axes(starting, current)
    if cmp is None:
        return None
    return render_relative_spider(cmp, path)


def _comparison_axes(starting, current):
    """The five relative axes, built the way a demonstration builds them.

    THE SAME FUNCTION, not a second copy. Two constructions of one chart
    would drift, and a chart is the one place a difference is invisible.
    """
    from .demo_visual import DemoComparison, relative_axes

    axes = relative_axes(starting, current)
    if not axes:
        return None
    return DemoComparison(
        demo_key="workflow", demo_number=0, question="",
        # THE DECISION THAT SEPARATES THEM, on the legend.
        #
        # `compute / memory` alone made two designs differing only in a
        # second engine, or only in where preprocessing runs, read as
        # identical on the legend of the chart drawn to compare them.
        # The decision is named, not its fields: `secondary_compute`,
        # `execution_mode` and `work_split` are one decision and
        # listing three internal parameters helps nobody.
        baseline_label=_decision_label(starting.current_config,
                                       current.current_config,
                                       starting.current_config),
        comparison_label=_decision_label(starting.current_config,
                                         current.current_config,
                                         current.current_config),
        axes=tuple(axes), flow_relevant=True, changed_fields=())


def _decision_label(base_cfg, comp_cfg, cfg) -> str:
    """This design's name, with the decision that separates the pair.

    `compute / memory` alone hid every change to a second engine or to
    where preprocessing runs: two designs differing only in those read
    as identical on the legend of the chart drawn to compare them.

    The DECISION is named, not its fields. `secondary_compute`,
    `execution_mode` and `work_split` move together as one decision,
    and printing three internal parameters on a legend helps nobody.
    """
    from .decisions import BY_ID, config_of, decisions_between

    base = _label(cfg)
    here = config_of(cfg)
    extra = []
    for did in decisions_between(config_of(base_cfg),
                                 config_of(comp_cfg)):
        if did.startswith("UNCLASSIFIED:"):
            field = did.split(":", 1)[1]
            val = here.get(field)
            if val is not None:
                extra.append(f"{field.replace('_', ' ')} "
                             f"{_pretty(field, val)}")
            continue
        if did == "ADD_SECOND_ENGINE":
            extra.append("two engines"
                         if here.get("secondary_compute")
                         else "one engine")
        elif did == "MOVE_PREPROCESSING":
            extra.append(_pretty("preprocessing_mode",
                                 here.get("preprocessing_mode")))
        elif did == "CHANGE_PACKAGE_COUNT":
            extra.append(_pretty("memory_devices",
                                 here.get("memory_devices")))
        elif did == "CHANGE_PROCESS_NODE":
            node = here.get("accel_node")
            if node:
                extra.append(_pretty("accel_node", node))
        elif did == "CHANGE_HOST":
            cpu = here.get("cpu")
            if cpu:
                extra.append(_pretty("cpu", cpu))
        # Accelerator and memory already appear in `_label`.
    extra = [e for e in extra if e and e != "—"]
    return base + ("  /  " + " / ".join(extra) if extra else "")


def _label(cfg) -> str:
    """A design's name, in product terms."""
    if cfg is None:
        return ""
    return (f"{_pretty('compute', getattr(cfg, 'compute', None))} / "
            f"{_pretty('memory', getattr(cfg, 'memory', None))}")


# THE PRODUCT NAME, NOT THE INTERNAL KEY.
#
# `npu_32x32`, `cortex_a78_x4` and `cpu_only` are how the code stores a
# choice. A result screen printing them is a debug view - the same
# defect that was removed from the process-node options and then shipped
# again through the report tables.
FIELD_LABEL = {
    "cpu": "Host processor", "compute": "Accelerator",
    "secondary_compute": "Second accelerator",
    "memory": "Memory technology", "memory_devices": "Memory packages",
    "preprocessing_mode": "Preprocessing",
    "soc_node": "SoC process node", "accel_node": "Accelerator node",
    "execution_mode": "Execution mode", "work_split": "Work split",
    "secondary_enabled": "Second accelerator enabled",
    "host_connection": "Host connection",
    "offload_batching": "Offload batching",
    "alternative_share": "Alternative share",
    "overlap_ratio": "Overlap ratio", "profile": "Profile",
    "integration": "Integration",
    "bandwidth_efficiency": "Bandwidth efficiency",
    "interface_bandwidth_gbytes_s": "Interface bandwidth",
}

VALUE_LABEL = {
    "cpu_only": "CPU only", "isp_assisted": "ISP assisted",
    "isp_and_npu": "ISP and NPU assisted",
    "npu_assisted": "NPU assisted",
    "sequential": "Sequential", "parallel": "Parallel",
}

# HOW EACH FIELD IS RENDERED, declared per field.
#
# `bool` is a subclass of `int` in Python, so `1 == True` and a lookup
# keyed on the value alone rendered a memory package count of 1 as
# "Enabled". Reordering the checks fixes that one field and leaves the
# same collision waiting in the next numeric field somebody adds.
#
# The field says which kind it is, so the value's type cannot decide.
COUNT_FIELDS = {"memory_devices": ("package", "packages")}
FLAG_FIELDS = frozenset((
    "secondary_enabled", "offload_batching", "closed_loop",
    "requires_automotive_grade", "uses_nms"))
RATIO_FIELDS = frozenset((
    "work_split", "alternative_share", "overlap_ratio",
    "bandwidth_efficiency"))


def _pretty(field: str, value) -> str:
    """A value as a reader should see it.

    THE FIELD DECIDES, NOT THE VALUE'S TYPE.
    """
    if value is None or value == "":
        return "—"

    if field in FLAG_FIELDS:
        if not isinstance(value, bool):
            return str(value)
        return "Enabled" if value else "Disabled"

    if field in COUNT_FIELDS:
        one, many = COUNT_FIELDS[field]
        try:
            n = int(value)
        except (TypeError, ValueError):
            return str(value)
        return f"{n} {one if n == 1 else many}"

    if field in RATIO_FIELDS:
        try:
            return f"{float(value):g}"
        except (TypeError, ValueError):
            return str(value)

    # An undeclared field: booleans first, because otherwise 1 and True
    # are the same key.
    if isinstance(value, bool):
        return "Enabled" if value else "Disabled"
    if isinstance(value, (int, float)):
        return f"{value:g}"
    if value in VALUE_LABEL:
        return VALUE_LABEL[value]
    try:
        from .closure import _label as _closure_label
        text = _closure_label(field, value)
        if text and text != str(value):
            return text
    except Exception:
        pass
    return VALUE_LABEL.get(value, str(value))


def _cell(v) -> str:
    return "—" if v is None else str(v)


def _num(v) -> str:
    import math
    if v is None:
        return "—"
    if isinstance(v, float) and not math.isfinite(v):
        return "NOT ESTABLISHED"
    return f"{v:,.4g}"


def _pct(v) -> str:
    import math
    if v is None or (isinstance(v, float) and not math.isfinite(v)):
        return "—"
    return f"{v:.1f}%"


def _delta(a, b) -> str:
    import math
    if a is None or b is None:
        return ""
    if not (isinstance(a, (int, float)) and isinstance(b, (int, float))):
        return ""
    if not (math.isfinite(a) and math.isfinite(b)) or a == 0:
        return ""
    pct = (b - a) / a * 100.0
    return "" if abs(pct) < 0.05 else f"{pct:+.1f}%"


def _provenance():
    try:
        from . import __version__
        from .view_data import engine_provenance
        p = engine_provenance()
        return str(__version__), p.get("digest", "")
    except Exception:
        return "", ""
