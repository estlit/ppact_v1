"""
ppact.explain - why the number changed

Most simulators print latency, power, area and cost. A student reads them and
learns which design won, not why, and cannot transfer that to a design the
tool has never shown them.

This module carries the second half: the causal chain behind a result, and a
plain reading of what a change achieved and what it cost. Nothing here
computes anything - it reads figures the model already produced and says what
they mean.

WHAT AN EXPLANATION MAY AND MAY NOT DO
--------------------------------------
It may say what the model found and why the mechanism produces it. It may not
recommend a product decision, because the model does not know the market, the
schedule, the competition or what the customer will pay. Where a
recommendation is given it is qualified by CONTEXT - a design that no factory
should build can be a good research prototype and an excellent teaching
example, and saying so is more useful than a verdict.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

LINE = "=" * 78


# ==============================================================================
# Causal chains
# ==============================================================================
#
# Each is the mechanism behind a result the simulator produces, written as the
# steps a person would say them in. They are not derived from the run - they
# are the reason the run comes out as it does, and a student who reads only
# the numbers has to reconstruct them.

CHAINS: Dict[str, Tuple[str, Tuple[str, ...]]] = {
    "long_prompt": (
        "Why a longer prompt makes the first answer slow",
        ("the prompt became N times longer",
         "prefill attends every token to every earlier one, so its "
         "arithmetic grew with it",
         "prefill is COMPUTE bound - the weights are read once for the whole "
         "prompt",
         "so the time to the first token grew with the prompt",
         "decode did not change: it reads the same weights again for every "
         "token, whatever the prompt was",
         "the conversation feels slow to start and then runs at its usual "
         "speed"),
    ),
    "moe_storage": (
        "Why an MoE reads 24 GB and stores 240",
        ("a token arrives and the router chooses which experts it needs",
         "the router cannot know that before the token arrives",
         "so every expert has to be resident already",
         "STORAGE follows the total parameters",
         "only the chosen experts are read and multiplied",
         "BANDWIDTH and ARITHMETIC follow the active parameters",
         "the token rate looks like a small model and the board has to be "
         "sized for a large one"),
    ),
    "long_context": (
        "Why the same model runs out of memory on a longer conversation",
        ("the weights did not change - it is the same network",
         "every token generated adds its keys and values to a cache",
         "the cache grows LINEARLY with the conversation",
         "at some length the cache is larger than the weights",
         "total memory is weights plus cache, and the board holds a fixed "
         "amount",
         "the model did not get bigger; the conversation did"),
    ),
    "batching": (
        "Why a server batches and a phone does not",
        ("the weights are read once per step however many users are served",
         "each user carries their own KV cache, which is not shared",
         "so traffic PER USER falls as the batch grows",
         "aggregate throughput rises and each individual user waits longer",
         "a server is paid for aggregate throughput and a phone for one "
         "user's latency",
         "the same machine is the right answer to one and the wrong answer to "
         "the other"),
    ),
    "memory_no_help": (
        "Why a faster memory changed nothing",
        ("the accelerator was not waiting for data",
         "the slowest station was the CPU, the ISP, or the arrival of work",
         "a faster memory shortens a wait that was not being paid",
         "capacity rose and delivered throughput did not",
         "the cost, the power and the cooling class rose anyway"),
    ),
    "second_engine_no_help": (
        "Why a second accelerator made things worse",
        ("the design was limited by something other than arithmetic",
         "the second engine adds its own dispatch and its own graph launch",
         "those land on the host, which was already the constraint",
         "and both engines now share one memory system",
         "so the pipeline got slower while the silicon and the price rose"),
    ),
    "quantisation": (
        "Why a narrower number format changes so much at once",
        ("each parameter occupies fewer bytes",
         "so the model needs less CAPACITY - it may fit where it did not",
         "and each token moves fewer bytes - so it needs less BANDWIDTH",
         "both effects arrive together, which is why this lever is reached "
         "for first",
         "the network computes something slightly different and its accuracy "
         "falls",
         "how far it falls depends on the network and the method, and is not "
         "something this model can tell you"),
    ),
    "finer_node": (
        "Why a finer process node is not simply better",
        ("cells are smaller, so the die is smaller and clocks higher",
         "energy per switch falls",
         "but SRAM shrinks at about half the rate of logic",
         "and the wafer costs several times more and yields worse",
         "so between adjacent nodes an SRAM-heavy die often gets DEARER",
         "parts move anyway - for power and speed, and because a competitor "
         "will"),
    ),
}


def why(key: str, substitutions: Optional[Dict[str, str]] = None) -> None:
    """Print the mechanism behind a result."""
    if key not in CHAINS:
        print(f"  No explanation registered for '{key}'. "
              f"Available: {', '.join(sorted(CHAINS))}")
        return
    title, steps = CHAINS[key]
    print(f"\n  WHY: {title}")
    for i, step in enumerate(steps):
        text = step
        for k, v in (substitutions or {}).items():
            text = text.replace(k, v)
        prefix = "     " if i == 0 else "      -> "
        print(f"{prefix}{text}")


# ==============================================================================
# Decision explanation
# ==============================================================================

# What a design is FOR changes whether its failures matter. A cost gate is
# decisive for a product and irrelevant for a prototype; an accuracy gate is
# decisive for both. These are the gates each context genuinely cannot ignore.
CONTEXT_BINDING_GATES = {
    "industrial deployment": ("cost", "power", "thermal", "memory_cooling",
                              "accuracy", "capacity", "throughput", "latency",
                              "reaction", "board", "soc_die", "area"),
    "research prototype": ("accuracy", "capacity"),
    "teaching example": (),
}

CONTEXT_NOTE = {
    "industrial deployment": "every gate binds - a product that fails one "
                             "does not ship",
    "research prototype": "only correctness and feasibility bind; cost, "
                          "power and cooling can be worked around on a bench",
    "teaching example": "no gate binds - a design that fails is often the "
                        "more instructive one",
}


# Which chain fits which OUTCOME. An explanation that contradicts the result
# it is attached to is worse than none: it teaches a mechanism and an example
# that disagree, and the student cannot tell which to believe.
# What counts as "changed nothing". Even a compute-bound design gains one to
# three percent from a wider bus, so an exact test would reject every real
# example of a chain about a change that did not help. Five percent is a
# judgement, and it is written here rather than buried in a comparison.
NEGLIGIBLE = 0.05

CHAIN_APPLIES = {
    # "Changed nothing" has to mean the LATENCY too. A first version tested
    # only the delivered rate, and passed on a run where the latency improved
    # 88% - delivered was capped by arrivals, which is a different story with
    # a different lesson.
    "memory_no_help": lambda am, bm: (
        bm["Delivered throughput (inf/s)"]
        <= am["Delivered throughput (inf/s)"] * 1.01
        and bm["Latency (ms)"] >= am["Latency (ms)"] * (1 - NEGLIGIBLE)
        and bm["Effective bandwidth (GB/s)"]
        > am["Effective bandwidth (GB/s)"] * 1.05),
    "second_engine_no_help": lambda am, bm: (
        bm["Pipeline capacity (inf/s)"]
        <= am["Pipeline capacity (inf/s)"] * 1.01
        and bm["Logic silicon (mm2)"] > am["Logic silicon (mm2)"] * 1.01),
    "finer_node": lambda am, bm: (
        bm["Logic silicon (mm2)"] < am["Logic silicon (mm2)"] * 0.99),
    "quantisation": lambda am, bm: (
        bm["Deployment accuracy (%)"] < am["Deployment accuracy (%)"] - 1e-9),
}


def chain_contradicts(key: str, am, bm) -> bool:
    """True when a named chain does not describe what actually happened."""
    test = CHAIN_APPLIES.get(key)
    return test is not None and not test(am, bm)


def suggest_chain(am, bm) -> Optional[str]:
    """The chain that matches what actually happened, if any does.

    Only chains with a registered test can be suggested. A chain nobody can
    check against a run is a chain nobody should attach to one automatically.
    """
    for key, test in CHAIN_APPLIES.items():
        try:
            if test(am, bm):
                return key
        except KeyError:
            continue
    return None


def decision_explanation(app_key: str, before, after,
                         chain: Optional[str] = None,
                         auto_chain: bool = True) -> None:
    """What the change achieved, what it cost, and for whom that matters."""
    from .application import APPLICATION_LIBRARY
    from .system import evaluate_system, gate_causes

    app = APPLICATION_LIBRARY[app_key]
    a, b = evaluate_system(app, before), evaluate_system(app, after)
    am, bm = a.metrics, b.metrics

    print(f"\n{LINE}")
    print(f" DECISION EXPLANATION - {app.name}")
    print(LINE)

    achieved, cost = [], []
    infeasible_before = "INFEASIBLE" in a.status
    infeasible_after = "INFEASIBLE" in b.status

    if infeasible_after:
        cost.append("the model no longer fits in memory - there is no "
                    "performance to report")
    elif infeasible_before:
        achieved.append("the model now fits, where before it did not - this "
                        "is the difference between a product and no product")
    else:
        for label, key, lower_better in (
                ("latency", "Latency (ms)", True),
                ("pipeline capacity", "Pipeline capacity (inf/s)", False),
                ("delivered throughput", "Delivered throughput (inf/s)", False),
                ("energy per job", "Energy per inference (mJ)", True),
                ("accuracy", "Deployment accuracy (%)", False)):
            x, y = am[key], bm[key]
            if x == 0 or abs(y / x - 1) < 0.005:
                continue
            chg = (y / x - 1) * 100
            better = (y < x) if lower_better else (y > x)
            line = f"{label} {chg:+.1f}%"
            (achieved if better else cost).append(line)

    for label, key in (("average power", "System power (W)"),
                       ("system cost", "System cost (USD)"),
                       ("silicon area", "Logic silicon (mm2)")):
        x, y = am[key], bm[key]
        if x and abs(y / x - 1) >= 0.005:
            chg = (y / x - 1) * 100
            (cost if y > x else achieved).append(f"{label} {chg:+.1f}%")

    print(f"  What it achieved")
    for line in achieved or ["nothing measurable"]:
        print(f"    + {line}")
    print(f"\n  What it cost")
    for line in cost or ["nothing measurable"]:
        print(f"    - {line}")

    failed = [g for g, ok in b.gate.items() if not ok]
    if failed:
        causes = gate_causes(b)
        print(f"\n  Requirements not met")
        for g in causes["independent"]:
            note = causes["kinds"].get(g, "")
            print(f"    x {g}" + (f"   {note}" if note else ""))
        for g, parent in causes["derived"].items():
            print(f"    x {g}   follows from {parent}")

    # --- who this design is for -------------------------------------------
    print(f"\n  Whether that matters depends on what the design is FOR")
    for context, binding in CONTEXT_BINDING_GATES.items():
        blocking = [g for g in failed if g in binding]
        verdict = "no" if blocking else "yes"
        detail = (f"blocked by {', '.join(blocking)}" if blocking
                  else CONTEXT_NOTE[context])
        print(f"    {context:<24s}{verdict:<5s}{detail}")

    print(f"\n  This is a reading of what the model computed. It does not "
          f"know")
    print(f"  the market, the schedule, the competition or what a customer "
          f"will")
    print(f"  pay, and none of those is a smaller part of the decision than "
          f"the")
    print(f"  numbers above.")

    if chain is None and auto_chain:
        chain = suggest_chain(am, bm)
    if chain:
        if chain_contradicts(chain, am, bm):
            print(f"\n  The chain '{chain}' was requested and does NOT "
                  f"describe this run.")
            print(f"  It is not printed. An explanation that contradicts its "
                  f"own example")
            print(f"  teaches a mechanism and a counter-example at once, and a "
                  f"student")
            print(f"  cannot tell which to believe.")
        else:
            why(chain)
    print(LINE)
