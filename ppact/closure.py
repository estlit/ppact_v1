"""
ppact.closure - a comparison ends by proposing the next one

WHY THIS IS ONE COMPONENT AND NOT A DEMO FEATURE
================================================
Every screen in Studio that puts two designs side by side ends the same
way today: with a result and nothing after it. The user has learnt
something and has to go back to a menu to use it.

    reference -> current -> evidence -> conclusion -> next comparisons

Demo, Design Review, What-if, Why Changed, Quick Start and anything added
later call THE SAME closure. A recommendation rule implemented per screen
is a rule that drifts per screen, and this project has already spent a
release cycle removing seven copies of a progress bar.

THE RECOMMENDATIONS ARE COMPUTED, NOT WRITTEN
---------------------------------------------
Ordering comes from where the limit currently sits. Nothing here is
phrased by a language model, and nothing is a fixed menu: a design limited
by its host gets host proposals first, and a design limited by a memory
link gets memory proposals first, because that is what the engine says.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

# PRIORITY CLASS, NOT CONFIDENCE.
#
# "HIGH" and five stars read as a probability, a quality score or a
# predicted gain. None of those is what the engine computed. What it
# computed is whether a proposal addresses the element it says is
# limiting, so the label says exactly that and nothing more.
DIRECT = "DIRECT"          # addresses the current limiting element
CONTEXTUAL = "CONTEXTUAL"  # applies whatever the limit is
CONTRAST = "CONTRAST"      # does not address the limit; a control
COMPLETED = "COMPLETED"    # this comparison already made the change

PRIORITY_ORDER = {DIRECT: 0, CONTEXTUAL: 1, CONTRAST: 2, COMPLETED: 3}

PRIORITY_MEANING = {
    DIRECT: "addresses the element the engine says is limiting; a "
            "structurally relevant comparison, not a predicted winner",
    CONTEXTUAL: "applies whatever the limiting element is",
    CONTRAST: "does not address the limiting element; a control "
              "experiment rather than a proposal",
    COMPLETED: "this comparison already made this change",
}

# NO COMPATIBILITY ALIASES. `HIGH = DIRECT` would let new code keep
# writing the term this change exists to retire, and the retirement
# would never finish.


@dataclass(frozen=True)
class NextComparison:
    """One proposal, with the reason it is being made.

    THE ORIGIN RULE IS NEVER OVERWRITTEN.

    Relabelling a candidate as explored or as a contrast used to replace
    its rule id, so `EXPLORED_001` on screen could not be traced to the
    rule that proposed it - the trace was built and the one thing it
    existed to preserve was dropped in the middle of it.
    """
    # EVERY ORIGIN, not the first.
    #
    # Merging used to keep one rule id and drop the rest, so a design
    # under power AND thermal pressure recorded one of them - which is
    # the opposite of what the trace exists for.
    origin_rule_ids: Tuple[str, ...]
    classification_rule_id: str
    action_id: str
    title: str
    reason: str
    priority: str
    field: str = ""
    already_explored: bool = False
    recommended: bool = True
    suppressed_because: str = ""
    display_rank: int = 0
    would_appear_if: str = ""
    # WHAT IT WOULD CHANGE TO. A field name alone cannot start a
    # comparison; the engine does not pick a target, and the screen
    # cannot offer one it has not been given.
    current_value: str = ""
    alternatives: Tuple[str, ...] = ()

    # WHICH DIE. `soc_node` and `accel_node` are different fields, and
    # pressure on the accelerator proposing a change to the SoC node is
    # a proposal about the wrong silicon.
    target_die: str = ""
    # WHY THE SECOND REASON IS NOT IN THE SENTENCE.
    #
    # The origins survived the merge and their reasons did not, so the
    # audit could see that ISP_LIMIT_002 contributed and not what it
    # said or why it was left out.
    # WHICH ARCHITECTURAL FAMILY. Needed so a screen can show one
    # contrast per family and a check can verify it - the title's last
    # word was standing in for this and "accelerators" did not match
    # "accelerator".
    family: str = ""
    origin_reasons: Tuple[Tuple[str, str], ...] = ()
    omitted_reasons: Tuple[Tuple[str, str, str], ...] = ()

    @property
    def origin_rule_id(self) -> str:
        """The first origin, for callers that want one name."""
        return self.origin_rule_ids[0] if self.origin_rule_ids else ""

    @property
    def rule_id(self) -> str:
        """The rule shown to a reader: the classification if there was
        one, and otherwise the origin."""
        return self.classification_rule_id or self.origin_rule_id


@dataclass(frozen=True)
class TraceStep:
    """One stage of the pipeline, with what entered and what left.

    A recommendation that cannot be traced is a recommendation nobody can
    disagree with usefully - "it appeared" is not a reason. Each stage
    records its own count so the drop from generated to displayed can be
    read rather than reconstructed.
    """
    stage: str
    before: int
    after: int
    removed: Tuple[str, ...] = ()
    note: str = ""


@dataclass(frozen=True)
class Closure:
    conclusion: Tuple[str, ...]
    key_insight: str
    next_comparisons: Tuple[NextComparison, ...]
    modify_prompt: str
    free_question_prompt: str
    # WHAT WAS CONSIDERED AND NOT SHOWN.
    #
    # A list of five proposals cannot be audited for omissions. The rules
    # that fired and were then dropped are the other half of the record.
    not_recommended: Tuple[NextComparison, ...] = ()
    limiting_element: str = ""
    limiting_kind: str = ""
    trace: Tuple[TraceStep, ...] = ()


# WHAT TO TRY, BY WHERE THE LIMIT IS.
#
# Declared, not inferred. The engine says which element limits the
# design; which knobs address that element is engineering knowledge, and
# writing it here is what keeps it out of a prompt.
@dataclass(frozen=True)
class Rule:
    """One proposal rule.

    `action_id` identifies WHAT WOULD CHANGE, and two rules proposing the
    same action are two reasons for one experiment. Deduplicating on the
    title string worked until a title was reworded.
    """
    rule_id: str
    action_id: str
    title: str
    reason: str
    field: str


PROPOSALS: Dict[str, Tuple[Rule, ...]] = {
    "host": (
        Rule("HOST_LIMIT_001", "ACT_CPU",
             "Compare alternative host processors",
             "the host is the limiting element", "cpu"),
        Rule("HOST_LIMIT_002", "ACT_PREPROC",
             "Move preprocessing off the host",
             "expected to reduce host activity", "preprocessing_mode"),
    ),
    "ISP": (
        Rule("ISP_LIMIT_001", "ACT_PREPROC",
             "Move preprocessing back to the host",
             "the ISP is now the limiting element", "preprocessing_mode"),
        Rule("ISP_LIMIT_002", "ACT_CPU",
             "Compare alternative host processors",
             "the host would take the work back", "cpu"),
    ),
    "accelerator": (
        Rule("ACCEL_LIMIT_001", "ACT_COMPUTE",
             "Compare alternative accelerators",
             "the accelerator is the limiting element", "compute"),
        Rule("ACCEL_LIMIT_002", "ACT_SECOND",
             "Compare with a second accelerator",
             "more arithmetic against the same limit",
             "secondary_compute"),
    ),
    "secondary accelerator": (
        Rule("SPLIT_LIMIT_001", "ACT_SECOND",
             "Compare second-accelerator sizes",
             "the smaller engine sets the pair's rate",
             "secondary_compute"),
        Rule("SPLIT_LIMIT_002", "ACT_SINGLE",
             "Return to a single accelerator",
             "an unequal pair finishes with its slower half",
             "secondary_compute"),
    ),
    "shared memory": (
        Rule("MEM_LIMIT_001", "ACT_MEMORY",
             "Change the memory technology",
             "the memory stage is the limiting element", "memory"),
        Rule("MEM_LIMIT_002", "ACT_PACKAGES",
             "Compare memory package counts",
             "package count buys bandwidth as well as capacity",
             "memory_devices"),
    ),
}

# A LINK limit is not a module limit, and the proposals differ.
LINK_PROPOSALS: Tuple[Rule, ...] = (
    Rule("LINK_LIMIT_001", "ACT_MEMORY", "Change the memory technology",
         "the link is asking for more bandwidth than it has", "memory"),
    Rule("LINK_LIMIT_002", "ACT_PACKAGES",
         "Compare memory package counts",
         "more packages widen the link", "memory_devices"),
)

# A PROCESS NODE PROPOSAL IS CONDITIONAL, NOT UNIVERSAL.
#
# `NODE_ANY_001` appeared in 21 of 21 cases, which made it a fixed menu
# item rather than a reading of the design. A node changes power, area,
# cost and speed together, so it needs a REASON: some axis under pressure
# that a node could act on, fabricated logic to act on, and a node to
# move to.
#
# Five rules, one action. Two can fire at once and both origins are kept
# - "power and thermal are tight" is a better reason than either alone.
# TWO ACTIONS, NOT ONE. `soc_node` and `accel_node` are different
# fields on different silicon, and a rule fired by accelerator pressure
# proposing a change to the SoC node is a proposal about the wrong die.
NODE_RULES: Tuple[Rule, ...] = (
    Rule("NODE_POWER_001", "ACT_SOC_NODE",
         "Change the SoC process node",
         "system power is close to its budget", "soc_node"),
    Rule("NODE_THERMAL_001", "ACT_SOC_NODE",
         "Change the SoC process node",
         "the thermal margin is thin", "soc_node"),
    Rule("NODE_AREA_001", "ACT_SOC_NODE",
         "Change the SoC process node",
         "silicon area is close to its budget", "soc_node"),
    Rule("NODE_COST_001", "ACT_SOC_NODE",
         "Change the SoC process node",
         "system cost is close to the bill-of-materials budget",
         "soc_node"),
    Rule("NODE_ACCEL_PERF_001", "ACT_ACCEL_NODE",
         "Change the accelerator process node",
         "throughput is close to the requirement and the accelerator "
         "is fabricated logic", "accel_node"),
)

# Not a proposal rule. It exists so a node change the reader just made is
# recorded rather than silently absent, and attributing that to
# NODE_POWER_001 would say they changed it for a reason they did not
# have.
NODE_COMPLETED = Rule(
    "NODE_CHANGED_001", "ACT_SOC_NODE",
    "Change the SoC process node",
    "this comparison changed the process node", "soc_node")

# Retained for callers that referenced the old name.
ALWAYS: Tuple[Rule, ...] = ()

# How close to a limit counts as pressure. A threshold, not a
# measurement: below it a node comparison has no stated purpose.
PRESSURE_PCT = 70.0

# Modules whose silicon this model fabricates. A design with none of
# them has no logic a node could move.
FABRICATED = ("host", "accelerator", "ISP", "secondary accelerator")

# CLASSIFICATION RULES are not proposal rules.
#
# They relabel a candidate that a proposal rule produced; counting them
# alongside proposals would say a rule "fired" when what fired was the
# relabelling of somebody else's candidate.
CLASSIFICATION_RULES: Tuple[str, ...] = ("EXPLORED_001",
                                         "NOT_LIMITING_001")

# A THIRD KIND. NODE_CHANGED_001 neither proposes nor relabels: it
# records that the reader made the change. Filed under classification it
# counted zero while the document said five, because it appears as an
# ORIGIN and the classification counter reads the other field.
COMPLETION_RULES: Tuple[str, ...] = ("NODE_CHANGED_001",)

PROPOSAL_RULES: Tuple[str, ...] = tuple(
    r.rule_id for group in list(PROPOSALS.values())
    + [LINK_PROPOSALS, NODE_RULES] for r in group)

# NODE_CHANGED_001 records rather than proposes, so it is counted with
# the classification rules and not with the rules that recommend.

ALL_RULES: Tuple[str, ...] = (PROPOSAL_RULES + CLASSIFICATION_RULES
                              + COMPLETION_RULES)



def build_closure(ref_analysis, cur_analysis,
                  changed_fields: Sequence[str] = (),
                  key_insight: str = "") -> Closure:
    """The four sections every comparison ends with.

    `changed_fields` is what the comparison just varied. Proposing it
    again as the first thing to try would send the user round the loop
    they have just come out of.
    """
    from .flow_map import build_compared_flow_map, build_flow_map

    a, b = build_flow_map(ref_analysis), build_flow_map(cur_analysis)
    am = ref_analysis.current_result.metrics
    bm = cur_analysis.current_result.metrics

    # --- Engineering conclusion: what the engine computed ---------------
    import math as _m
    lines_out: List[str] = []
    for label, key, unit, lower_better in (
            ("Latency", "Latency (ms)", "ms", True),
            # `terminology.py` declares "Pipeline capacity" canonical
            # and forbids the looser forms; this label predated it.
            ("Pipeline capacity", "Pipeline capacity (inf/s)",
             "inf/s", False),
            ("System cost", "System cost (USD)", "USD", True),
            ("System power", "System power (W)", "W", True)):
        x, y = am.get(key), bm.get(key)
        # A ZERO IS A VALUE. `not x` treated it as missing, so a figure
        # that genuinely reached zero was silently dropped from the
        # conclusion.
        if x is None or y is None:
            continue
        if not (_m.isfinite(x) and _m.isfinite(y)) or x == 0:
            continue
        pct = (y - x) / x * 100.0
        if abs(pct) < 0.5:
            continue
        word = ("improved" if (pct < 0) == lower_better else "worsened")
        lines_out.append(f"{label} {word} {abs(pct):.0f}%, "
                         f"{x:,.2f} to {y:,.2f} {unit}.")

    # NAME AND KIND, both. A link and a module can share a name, and
    # comparing only the name reported "unchanged" across exactly the
    # migration the demonstration exists to show.
    same_limit = (a.limiting == b.limiting
                  and a.limiting_kind == b.limiting_kind)
    if same_limit:
        lines_out.append(f"The limiting element remained the "
                         f"{a.limiting} {a.limiting_kind}.")
    else:
        lines_out.append(f"The limiting element moved from the "
                         f"{a.limiting} {a.limiting_kind} to the "
                         f"{b.limiting} {b.limiting_kind}.")

    # --- Next comparisons: evaluate, merge, filter, classify, cut ------
    changed = set(changed_fields)
    present = {m.name for m in b.modules}
    trace: List[TraceStep] = []
    owners: Dict[str, str] = {}
    cur_cfg = cur_analysis.current_config
    app_key = cur_analysis.app_key

    # STAGE 1 - evaluate every rule in the table.
    attempts: List[Tuple[Rule, str, str]] = []   # rule, owner, priority
    seen_rules = set()

    def attempt(rule, owner, prio):
        # A RULE EVALUATED TWICE IS NOT A DUPLICATE OF ITSELF.
        #
        # Direct proposals and the contrast sweep both walk the same
        # table, so the trace read "HOST_LIMIT_001 (kept
        # HOST_LIMIT_001)" - a rule merged into itself, which explains
        # nothing. The second evaluation is dropped before it becomes an
        # attempt.
        if rule.rule_id in seen_rules:
            return
        seen_rules.add(rule.rule_id)
        attempts.append((rule, owner, prio))

    if b.limiting_kind == "link":
        for r in LINK_PROPOSALS:
            attempt(r, "link", DIRECT)
    else:
        for r in PROPOSALS.get(b.limiting, ()):
            attempt(r, b.limiting, DIRECT)
    for name, entries in PROPOSALS.items():
        for r in entries:
            attempt(r, name, CONTRAST)
    node_rules = _node_rules_that_fire(cur_analysis, present)
    if not node_rules and "soc_node" in changed:
        # THE COMPARISON JUST CHANGED THE NODE.
        #
        # No pressure justifies proposing it, but the reader did it and
        # the record should show that rather than staying silent - the
        # completed section is what makes the loop visible. Recorded,
        # never proposed.
        node_rules = (NODE_COMPLETED,)
    for r in node_rules:
        attempt(r, "any", CONTEXTUAL)
    n_direct = len(LINK_PROPOSALS if b.limiting_kind == "link"
                   else PROPOSALS.get(b.limiting, ()))
    n_sweep = sum(len(v) for v in PROPOSALS.values())
    n_node = len(node_rules)
    trace.append(TraceStep(
        "rules inspected", len(PROPOSAL_RULES), n_direct + n_sweep,
        note=f"{n_direct} for the limiting element, {n_sweep} in the "
             f"contrast sweep - the node rules are evaluated separately "
             f"because they are conditional"))
    trace.append(TraceStep(
        "conditional node rules that fired", len(NODE_RULES), n_node,
        note="a node rule needs an axis under pressure, fabricated "
             "logic and an alternative node"))
    trace.append(TraceStep(
        "duplicate rule evaluations suppressed",
        n_direct + n_sweep + n_node, len(attempts),
        note="a rule reached by both the direct list and the contrast "
             "sweep is one evaluation, not two"))

    # STAGE 2 - merge attempts that would change the same thing.
    #
    # DEDUPLICATION IS BY ACTION, NOT BY TITLE. Two rules proposing one
    # experiment are two reasons for it; the title string was standing in
    # for the action and would have stopped matching on a reword.
    # MERGING COMBINES REASONS. It used to keep the first rule and
    # discard the rest, so a design under power AND thermal pressure
    # recorded one of them.
    merged: List[NextComparison] = []
    by_action: Dict[str, int] = {}
    combined: List[str] = []
    for r, owner, prio in attempts:
        if r.action_id in by_action:
            i = by_action[r.action_id]
            prev = merged[i]
            # THE REASON IS ONLY COMBINED WHEN THE RULES AGREE.
            #
            # Appending a contrast rule's reason to a direct one produced
            # "the host is the limiting element; the ISP is now the
            # limiting element" - two rules for one experiment, and a
            # sentence that contradicts itself. The origins are always
            # kept; the prose is joined only within one priority class.
            same_class = prev.priority == prio
            merged[i] = dataclasses.replace(
                prev,
                origin_rule_ids=prev.origin_rule_ids + (r.rule_id,),
                reason=(f"{prev.reason}; {r.reason}" if same_class
                        else prev.reason),
                origin_reasons=prev.origin_reasons
                + ((r.rule_id, r.reason),),
                omitted_reasons=(
                    prev.omitted_reasons if same_class
                    else prev.omitted_reasons
                    + ((r.rule_id, r.reason,
                        f"originated as a {prio} rule while this "
                        f"proposal is {prev.priority}; combining them "
                        f"would contradict the sentence"),)),
                # The strongest class wins: a rule that addresses the
                # limit is not weakened by a contrast rule agreeing.
                priority=(prev.priority
                          if PRIORITY_ORDER[prev.priority]
                          <= PRIORITY_ORDER[prio] else prio))
            combined.append(f"{r.rule_id} into "
                            f"{prev.origin_rule_ids[0]} "
                            f"({r.action_id})")
            continue
        by_action[r.action_id] = len(merged)
        merged.append(NextComparison(
            origin_rule_ids=(r.rule_id,), classification_rule_id="",
            action_id=r.action_id, title=r.title, reason=r.reason,
            priority=prio, field=r.field,
            target_die=("accelerator" if r.field == "accel_node"
                        else ("SoC" if r.field == "soc_node" else "")),
            origin_reasons=((r.rule_id, r.reason),),
            current_value=_current_label(r.field, cur_cfg, app_key),
            alternatives=_alternatives(r.field, cur_cfg, app_key)))
        owners[r.action_id] = owner
    trace.append(TraceStep("reasons combined per action", len(attempts),
                           len(merged), tuple(combined),
                           "two rules proposing one experiment are two "
                           "reasons for it; both origins are kept"))

    # STAGE 3 - remove candidates about parts this design does not have.
    kept, absent = [], []
    for p in merged:
        owner = owners.get(p.action_id, "any")
        if owner in PROPOSALS and owner not in present:
            article = "an" if owner[0].upper() in "AEIOU" else "a"
            absent.append(NextComparison(
                p.origin_rule_ids, "", p.action_id, p.title, p.reason,
                CONTRAST, p.field, False, recommended=False,
                origin_reasons=p.origin_reasons,
                omitted_reasons=p.omitted_reasons,
                suppressed_because=f"the design has no {owner}",
                would_appear_if=f"the design included {article} {owner}",
                current_value=p.current_value,
                alternatives=p.alternatives))
        else:
            kept.append(p)
    trace.append(TraceStep("removed - part absent", len(merged),
                           len(kept),
                           tuple(p.title for p in absent),
                           "proposing a change to a part the design does "
                           "not have is advice about a different system"))

    # STAGE 4 - classify. THE ORIGIN RULE IS PRESERVED.
    classified, n_expl = [], 0
    for p in kept:
        if p.field and p.field in changed:
            n_expl += 1
            classified.append(NextComparison(
                p.origin_rule_ids, "EXPLORED_001", p.action_id, p.title,
                "this comparison already made this change", COMPLETED,
                p.field, True, target_die=p.target_die,
                origin_reasons=p.origin_reasons,
                omitted_reasons=p.omitted_reasons,
                would_appear_if=(f"{p.field} had not changed in this "
                                 f"comparison"),
                current_value=p.current_value,
                alternatives=p.alternatives))
        elif p.priority == CONTRAST:
            owner = owners.get(p.action_id, "any")
            classified.append(NextComparison(
                p.origin_rule_ids, "NOT_LIMITING_001", p.action_id,
                p.title,
                # NOT "the benefit is low". No counterfactual was run,
                # and a change away from the limit can still move cost,
                # power or area a great deal.
                f"does not directly address the current limiting "
                f"element ({b.limiting}); its benefit has not been "
                f"evaluated in this closure",
                CONTRAST, p.field, False, target_die=p.target_die,
                origin_reasons=p.origin_reasons,
                omitted_reasons=p.omitted_reasons,
                current_value=p.current_value,
                alternatives=p.alternatives))
        else:
            classified.append(p)
    trace.append(TraceStep("classified", len(kept), len(classified),
                           note=f"{n_expl} candidate(s) address a field "
                                f"this comparison just changed"))

    # STAGE 5 - sort, then cut. Order is decided here and only here.
    classified.sort(key=lambda p: PRIORITY_ORDER[p.priority])

    # ONE CONTRAST PER FAMILY, unless nothing else is left.
    #
    # Two accelerator contrasts filled both slots, so the reader saw the
    # same architectural family twice and a narrower search than the
    # rules had produced.
    def family(p):
        return owners.get(p.action_id, "any")

    classified = [dataclasses.replace(p, family=family(p))
                  for p in classified]
    picked, used_families, overflow = [], set(), []
    for p in classified:
        if p.priority == CONTRAST and family(p) in used_families:
            overflow.append(p)
            continue
        if p.priority == CONTRAST:
            used_families.add(family(p))
        picked.append(p)
    picked += overflow
    classified = picked

    shown = [dataclasses.replace(p, display_rank=i + 1)
             for i, p in enumerate(classified[:4])]
    tail = [p for p in classified[4:] if p.already_explored][:1]
    shown += [dataclasses.replace(p, display_rank=len(shown) + 1)
              for p in tail]
    trace.append(TraceStep(
        "sorted and cut to five", len(classified), len(shown),
        tuple(p.title for p in classified
              if p.action_id not in {q.action_id for q in shown}),
        "a list long enough to need reading reintroduces the choice it "
        "was meant to remove"))

    shown_actions = {p.action_id for p in shown}
    hidden = tuple(
        dataclasses.replace(
            p, recommended=False,
            suppressed_because=("already explored, and five are shown"
                                if p.already_explored
                                else "ranked below the five shown"),
            would_appear_if=(p.would_appear_if
                             or "a higher-ranked candidate were absent"))
        for p in classified if p.action_id not in shown_actions)

    return Closure(tuple(lines_out), key_insight, tuple(shown),
                   "Modify this design and compare again",
                   "Need another comparison? "
                   "Ask your own engineering question.",
                   hidden + tuple(absent), b.limiting, b.limiting_kind,
                   tuple(trace))


def _node_rules_that_fire(analysis, present) -> Tuple[Rule, ...]:
    """Which node rules have a stated purpose in THIS design.

    All four conditions must hold: fabricated logic exists, an axis is
    under pressure, an alternative node exists, and the comparison did
    not just change the node. Otherwise the proposal has no reason and
    the screen says nothing rather than offering a menu item.
    """
    import math as _m

    if not any(n in present for n in FABRICATED):
        return ()
    if not _alternatives("soc_node", analysis.current_config,
                         analysis.app_key):
        return ()

    from .application import APPLICATION_LIBRARY
    app = APPLICATION_LIBRARY[analysis.app_key]
    m = analysis.current_result.metrics
    out: List[Rule] = []

    def tight(value, budget):
        if value is None or budget in (None, 0):
            return False
        if isinstance(value, float) and not _m.isfinite(value):
            return False
        return value / budget * 100.0 >= PRESSURE_PCT

    by_id = {r.rule_id: r for r in NODE_RULES}
    if tight(m.get("System power (W)"),
             getattr(app, "power_budget_w", None)):
        out.append(by_id["NODE_POWER_001"])
    margin = m.get("Thermal margin (%)")
    if margin is not None and margin == margin and margin <= 30.0:
        out.append(by_id["NODE_THERMAL_001"])
    if tight(m.get("SoC silicon (mm2)"),
             getattr(app, "soc_silicon_budget_mm2", None)):
        out.append(by_id["NODE_AREA_001"])
    if tight(m.get("System cost (USD)"),
             getattr(app, "bom_budget_usd", None)):
        out.append(by_id["NODE_COST_001"])
    # Written as a utilisation, like the other axes: the requirement is
    # at least 70% of what the design can sustain. The equivalent form
    # `capacity <= requirement / 0.70` reads as "close to requirement"
    # while admitting 42.9% headroom.
    cap = m.get("Pipeline capacity (inf/s)")
    target = getattr(app, "target_inferences_per_s", None)
    if (cap and target and "accelerator" in present
            and target / cap * 100.0 >= PRESSURE_PCT):
        out.append(by_id["NODE_ACCEL_PERF_001"])
    return tuple(out)


def _tables():
    """One table at a time.

    A single try block around five imports meant one missing module
    returned an empty list for all of them, and every proposal silently
    lost its options.
    """
    import importlib
    out = {}
    for key, mod, name in (
            ("cpu", ".cpu", "CPU_LIBRARY"),
            ("compute", ".compute", "COMPUTE_LIBRARY"),
            ("secondary_compute", ".compute", "COMPUTE_LIBRARY"),
            ("memory", ".memory", "MEMORY_LIBRARY"),
            ("preprocessing_mode", ".preprocess", "MODES"),
            ("soc_node", ".process", "NODE_LIBRARY"),
            ("accel_node", ".process", "NODE_LIBRARY")):
        try:
            m = importlib.import_module(mod, package=__package__)
            out[key] = getattr(m, name)
        except (ImportError, AttributeError):
            continue
    return out


def _label(field: str, key) -> str:
    """The product name, not the internal key.

    `N3` and `class_100_tops` are how the code stores a choice. A screen
    printing them is a debug view, and the audit document was printing
    them too.
    """
    if key in (None, ""):
        return ""
    table = _tables().get(field)
    entry = table.get(key) if isinstance(table, dict) else None
    if entry is None:
        return str(key)
    for attr in ("label", "name"):
        v = getattr(entry, attr, None)
        if isinstance(v, str) and v:
            return v
    if isinstance(entry, dict):
        for attr in ("label", "name"):
            if entry.get(attr):
                return str(entry[attr])
    return str(key)


def _effective(field: str, cfg, app_key: str):
    """What the design is actually using.

    A node left unset is not "None" - it is whatever the application
    defaults to, and the engine uses that value. Printing None says the
    design has no process node.
    """
    v = getattr(cfg, field, None)
    if v is not None:
        return v, False
    if field in ("soc_node", "accel_node"):
        try:
            from .application import APPLICATION_LIBRARY
            app = APPLICATION_LIBRARY[app_key]
            return getattr(app, f"default_{field.split('_')[0]}_node"
                           if field == "soc_node"
                           else "default_accel_node", None), True
        except Exception:
            return None, False
    return None, False


def _current_label(field: str, cfg, app_key: str = "") -> str:
    """The current value as a reader should see it."""
    value, defaulted = _effective(field, cfg, app_key)
    if value is None:
        if field == "secondary_compute":
            return "Not installed"
        return "not set"
    text = _label(field, value)
    return f"{text} (application default)" if defaulted else text


# WHICH WAY THE OPTIONS GO.
#
# `_alternatives` returned the whole library, so "Upgrade the host
# processor" offered slower parts alongside faster ones. Titles are now
# neutral, and where an ordering exists the options are sorted by it so
# the reader can see which direction they are moving.
ORDERINGS = {
    "cpu": lambda e: (getattr(e, "cores", 0)
                      * getattr(e, "clock_ghz", 0.0)),
    "compute": lambda e: getattr(e, "mac_array", 0) or 0,
    "secondary_compute": lambda e: getattr(e, "mac_array", 0) or 0,
}


def _alternatives(field: str, cfg, app_key: str = "") -> Tuple[str, ...]:
    """What this field could be set to, excluding what it is.

    The engine does not pick a target - that is the reader's decision -
    but a proposal with no options cannot start a comparison, so the
    valid list is offered and the choice is left open.
    """
    current, _ = _effective(field, cfg, app_key)
    if field == "memory_devices":
        return tuple(str(n) for n in (1, 2, 4, 6, 8) if n != current)
    table = _tables().get(field)
    if table is None:
        return ()
    keys = [k for k in table if k != current]
    rank = ORDERINGS.get(field)
    if rank is not None:
        keys.sort(key=lambda k: rank(table[k]))
    else:
        keys.sort()
    return tuple(_label(field, k) for k in keys)



def render_closure(c: "Closure") -> List[str]:
    """The four sections, grouped by priority class.

    This path was never called by a test and kept `STARS[p.confidence]`
    after both names had gone - it raised NameError on the first line it
    reached. A rendering path with no check is a rendering path that is
    already broken.
    """
    from .visual.text import wrap_text

    out = ["ENGINEERING CONCLUSION", ""]
    for line in c.conclusion:
        for w in wrap_text(line, 68):
            out.append(f"  {w}")
    if c.key_insight:
        out += ["", "KEY INSIGHT", ""]
        for w in wrap_text(c.key_insight, 68):
            out.append(f"  {w}")

    GROUPS = (
        (DIRECT, "RECOMMENDED NEXT COMPARISONS",
         "These address the element the engine says is limiting. They "
         "are structurally relevant comparisons, not predicted "
         "winners - run each one to quantify its actual effect."),
        (CONTEXTUAL, "APPLIES WHATEVER THE LIMIT IS", ""),
        (CONTRAST, "USEFUL CONTRAST EXPERIMENTS",
         "These do not address the limiting element. Their benefit has "
         "not been evaluated here."),
        (COMPLETED, "COMPLETED IN THIS COMPARISON",
         "Already made. Shown so the loop is visible, not as something "
         "to run again."),
    )
    for prio, heading, blurb in GROUPS:
        rows = [p for p in c.next_comparisons if p.priority == prio]
        if not rows:
            continue
        out += ["", heading, ""]
        if blurb:
            for w in wrap_text(blurb, 66):
                out.append(f"  {w}")
            out.append("")
        for p in rows:
            out.append(f"  {p.title}")
            for w in wrap_text(p.reason, 62):
                out.append(f"      {w}")
            origin = " + ".join(p.origin_rule_ids)
            tag = f"      rule {origin}"
            if p.classification_rule_id:
                tag += f" -> {p.classification_rule_id}"
            out.append(tag)
            if p.target_die:
                out.append(f"      target die  {p.target_die}")
            if p.alternatives and p.priority != COMPLETED:
                alts = ", ".join(p.alternatives[:4])
                if len(p.alternatives) > 4:
                    alts += ", ..."
                out.append(f"      change {p.current_value} to one of:")
                for w in wrap_text(alts, 58):
                    out.append(f"          {w}")
            out.append("")

    out.append(f"  {c.modify_prompt}")
    out += ["", f"  {c.free_question_prompt}"]
    return out
