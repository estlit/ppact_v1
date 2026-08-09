"""
ppact.arch_classes - the architectural class registry

WHY A REGISTRY AND NOT JUST LIBRARY ENTRIES
===========================================
Six accelerator classes were added to the compute library in one sitting.
That closed a gap, and it also created a maintenance problem: a number typed
into a library entry looks exactly like a number that was measured, and in a
year nobody will remember which of them was which or where it came from.

So every architectural class is declared HERE as well, with three things the
library entry cannot carry:

    confidence   how much is actually known about this class
    evidence     what the estimate was derived from
    domain       what kind of system it belongs to

The library entry is the parameters. This is the provenance. Neither is
complete without the other, and a class present in one and absent from the
other is a defect that a check reports.

TOPS IS A PARAMETER, NOT A CLASSIFICATION
-----------------------------------------
The first pass named the classes after their arithmetic - "250 TOPS class" -
which is how a datasheet is indexed and not how a system is chosen. Somebody
building an automotive controller does not start from a TOPS figure; they
start from a domain with a power envelope, a memory class and a deployment
model, and the arithmetic follows from what fits.

So the registry carries DOMAIN classes as the primary organisation, and the
TOPS figure sits inside one as a parameter. The performance-named entries
remain because they are useful for a sweep, but they are not the way in.

VENDOR NEUTRALITY IS NOT NEGOTIABLE
-----------------------------------
No vendor is named here, no trademark appears, and no proprietary
organisation is inferred. Commercial products validate this library through
ppact.industry_profiles; they never become entries in it. A user who knows
the industry should find a class that corresponds to what they know, without
ever meeting a product name.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

LINE = "=" * 78

# The version of this registry, moved when a class is added, removed or
# retuned. A library that changes silently is a library nobody can cite.
REGISTRY_VERSION = "1.0"

# How much is known about a class. Nothing here is HIGH: no vendor publishes
# enough about any of these for a figure to be checked, and claiming
# otherwise would be the whole failure this file exists to avoid.
CONFIDENCE_LEVELS = ("medium", "low", "very low")

CONFIDENCE_MEANING = {
    "medium": "the shape is constrained by several public figures and a "
              "standard; the parameters are still estimates",
    "low": "derived by scaling measured entries; no public figure confirms "
           "any single parameter",
    "very low": "the class is known to exist and little else is public",
}

DOMAINS = ("entry", "edge", "automotive", "cloud inference", "training")

DOMAIN_MEANING = {
    "entry": "one sensor, a battery or a small supply, and a shelf price",
    "edge": "a box on a wall or a pole - mains power, passive cooling, a "
            "handful of streams",
    "automotive": "a sealed enclosure, a shared supply, a safety grade and a "
                  "unit price multiplied by a production run",
    "cloud inference": "a rack, airflow, and a cost measured per served "
                       "request rather than per unit",
    "training": "the same rack, sized for throughput on one enormous job "
                "rather than for many small ones",
}


@dataclass(frozen=True)
class ArchClass:
    key: str                      # the library key it corresponds to
    name: str
    domain: str
    confidence: str
    evidence: str                 # what the estimate rests on
    estimated: Tuple[str, ...]    # which parameters are estimates
    typical_memory: Tuple[str, ...]
    typical_deployment: str
    note: str = ""


# ==============================================================================
# Accelerator classes
# ==============================================================================
#
# 'estimated' lists what is an estimate rather than a standard. It is the
# whole list for every entry here, and writing that out each time is
# deliberate: a reader skimming should not have to infer it.

_ALL_ACCEL = ("peak arithmetic", "power envelope", "silicon area",
              "unit cost", "SRAM capacity", "energy per operation")

ACCELERATOR_CLASSES: Tuple[ArchClass, ...] = (

    ArchClass(
        "npu_16x16", "Entry inference", "entry", "low",
        evidence="scaled from the systolic-array model; the arithmetic "
                 "follows from the array size and clock, which are chosen "
                 "rather than measured",
        estimated=_ALL_ACCEL,
        typical_memory=("LPDDR5",), typical_deployment="standalone SoC",
        note="A single-sensor part. Small enough that the host usually costs "
             "more than it does."),

    ArchClass(
        "class_10_tops_soc", "On-device AI SoC", "entry", "medium",
        evidence="two published on-device parts state 10 INT8 TOPS in a 3 W "
                 "envelope with quad Arm application cores and LPDDR4X at "
                 "4266 MT/s, which constrains the arithmetic and the power; "
                 "area, buffer and cost remain estimates",
        estimated=("silicon area", "unit cost", "SRAM capacity",
                   "energy per operation"),
        typical_memory=("LPDDR4", "LPDDR4X"),
        typical_deployment="standalone SoC",
        note="Published parts in this class put the host cores, an ISP and "
             "a video codec on the same die. The Studio treats every design "
             "as a bare accelerator beside a separate host, so this entry "
             "carries the arithmetic and not the integration."),

    ArchClass(
        "class_25_tops_module", "Embedded accelerator module", "edge",
        "medium",
        evidence="a published module states about 25 TOPS in 5 W, which "
                 "fixes the arithmetic and the envelope of this band; area, "
                 "buffer and cost are estimates",
        estimated=("silicon area", "unit cost", "SRAM capacity",
                   "energy per operation"),
        typical_memory=("LPDDR4X", "LPDDR5"),
        typical_deployment="accelerator module on a carrier",
        note="Found by a check rather than by a review: adding the 10 TOPS "
             "class made this the nearest entry to a published 5 W module "
             "and its envelope did not reach. Closing one gap exposed a "
             "narrower one."),

    ArchClass(
        "class_80_tops_card", "Edge accelerator card", "edge", "medium",
        evidence="a published low-profile card states 80 TOPS in 25 W with "
                 "LPDDR4X at 66.7 GB/s over PCIe Gen4 x8; the arithmetic, "
                 "power and memory class are constrained, the area and cost "
                 "are not",
        estimated=("silicon area", "unit cost", "SRAM capacity",
                   "energy per operation"),
        typical_memory=("LPDDR4X", "LPDDR5"),
        typical_deployment="host-attached accelerator",
        note="The band between an embedded SoC and a data-centre card, "
             "which the library skipped."),

    ArchClass(
        "npu_64x64", "Mid-range inference", "edge", "low",
        evidence="the same systolic-array model with a larger array; the "
                 "arithmetic follows from array size and clock, both chosen",
        estimated=_ALL_ACCEL,
        typical_memory=("LPDDR5", "LPDDR5X"),
        typical_deployment="standalone SoC"),

    ArchClass(
        "npu_160x160", "Edge AI box", "edge", "low",
        evidence="same model; the power envelope is chosen to match a "
                 "fanless enclosure rather than derived",
        estimated=_ALL_ACCEL,
        typical_memory=("LPDDR5X", "GDDR6"),
        typical_deployment="standalone SoC"),

    ArchClass(
        "class_64_tops", "Server vision inference", "edge", "medium",
        evidence="a published server vision accelerator states 64 INT8 TOPS "
                 "at 2.0 GHz on a mature node with 32 MB of on-chip buffer, "
                 "which constrains the arithmetic and the clock of this "
                 "band; the power, area and cost remain estimates",
        estimated=("power envelope", "silicon area", "unit cost",
                   "energy per operation"),
        typical_memory=("LPDDR4X", "LPDDR5"),
        typical_deployment="host-attached accelerator",
        note="A half-height card for computer vision in a server or an edge "
             "rack. Fixes the low end of the server inference band, which a "
             "flagship alone cannot."),

    ArchClass(
        "class_dc_inference_card", "Datacenter inference card",
        "cloud inference", "medium",
        evidence="a published inference card states 512 INT8 TOPS, 256 MB "
                 "on-chip buffer, HBM3 at 1.5 TB/s and a 150 W passive "
                 "envelope; those constrain the shape of this class. Price "
                 "and silicon area are estimates - no card in this class "
                 "publishes either",
        estimated=("unit cost", "silicon area", "energy per operation"),
        typical_memory=("HBM3", "HBM3E"),
        typical_deployment="host-attached accelerator",
        note="The distinguishing feature is the buffer: hundreds of "
             "megabytes rather than tens, which is what lets the part hold a "
             "working set a smaller cache would stream."),

    ArchClass(
        "class_100_tops", "Automotive entry", "automotive", "low",
        evidence="the performance band is constrained by published "
                 "automotive accelerator specifications; every parameter is "
                 "scaled from the measured entries",
        estimated=_ALL_ACCEL,
        typical_memory=("LPDDR5X",),
        typical_deployment="host-attached accelerator",
        note="Single-camera ADAS or a driver monitor."),

    ArchClass(
        "class_150_tops", "Automotive mid", "automotive", "low",
        evidence="the performance band is constrained by published "
                 "automotive specifications; the parameters are scaled from "
                 "the measured entries",
        estimated=_ALL_ACCEL,
        typical_memory=("LPDDR5X",),
        typical_deployment="host-attached accelerator",
        note="Multi-camera ADAS without a language model."),

    ArchClass(
        "class_250_tops", "Automotive high", "automotive", "medium",
        evidence="two published automotive parts state 250 dense INT8 TOPS, "
                 "which constrains the arithmetic of this band; the power, "
                 "area and cost remain estimates",
        estimated=("power envelope", "silicon area", "unit cost",
                   "SRAM capacity", "energy per operation"),
        typical_memory=("LPDDR5X",),
        typical_deployment="host-attached accelerator",
        note="Where current automotive AI accelerators sit: ADAS with a "
             "language or vision-language model beside it."),

    ArchClass(
        "class_300_tops", "Automotive central", "automotive", "low",
        evidence="the band is reached in industry by pairing dies, which "
                 "this library cannot express - so the class is a single die "
                 "with the arithmetic of a pair, and that is not the same "
                 "thing",
        estimated=_ALL_ACCEL,
        typical_memory=("LPDDR5X",),
        typical_deployment="chiplet companion",
        note="Recorded as a coverage gap rather than solved by this entry."),

    ArchClass(
        "class_500_tops", "Automotive central, large", "automotive", "very low",
        evidence="extrapolated beyond any published automotive figure",
        estimated=_ALL_ACCEL,
        typical_memory=("LPDDR5X", "GDDR6"),
        typical_deployment="chiplet companion"),

    ArchClass(
        "class_800_tops", "Automotive central, multi-die", "automotive",
        "very low",
        evidence="extrapolated; in industry a multi-die part, here one die",
        estimated=_ALL_ACCEL,
        typical_memory=("LPDDR5X", "GDDR6"),
        typical_deployment="multi-accelerator system",
        note="Reading this as equivalent to a real multi-die part is the "
             "mistake this note exists to prevent."),

    ArchClass(
        "datacenter_gpu", "Cloud inference and training", "cloud inference",
        "low",
        evidence="the arithmetic and memory are pinned to a plausible class "
                 "rather than derived; the area is pinned for the same "
                 "reason",
        estimated=_ALL_ACCEL,
        typical_memory=("HBM3", "HBM3E", "HBM4_36"),
        typical_deployment="host-attached accelerator",
        note="Serves both cloud inference and training in this library. "
             "Those are different classes in industry and separating them "
             "is a coverage gap."),
)


# ==============================================================================
# Memory classes
# ==============================================================================

@dataclass(frozen=True)
class MemoryClass:
    key: str
    generation: str
    confidence: str
    evidence: str
    standard_figures: Tuple[str, ...]   # what comes from a standard
    estimated: Tuple[str, ...]


MEMORY_CLASSES: Tuple[MemoryClass, ...] = (
    MemoryClass("DDR4", "mainstream host, previous", "medium",
                "rate from the standard; an industrial host class still "
                "ships with this generation",
                ("interface rate", "bus width", "supply voltage"),
                ("energy per bit", "die area", "wafer price",
                 "controller efficiency")),
    MemoryClass("LPDDR4", "mobile and edge, previous", "medium",
                "rate from the standard; published on-device SoCs specify "
                "this alongside LPDDR4X",
                ("interface rate", "bus width", "supply voltage"),
                ("energy per bit", "die area", "wafer price",
                 "controller efficiency")),
    MemoryClass("DDR5", "mainstream host", "medium",
                "the interface rate is the JEDEC class rate",
                ("interface rate", "bus width", "supply voltage"),
                ("energy per bit", "die area", "wafer price",
                 "controller efficiency")),
    MemoryClass("LPDDR4X", "mobile and edge, previous", "medium",
                "the 4267 MT/s rate is the JEDEC class rate; a published "
                "inference card uses this generation for capacity rather "
                "than bandwidth",
                ("interface rate", "bus width", "supply voltage"),
                ("energy per bit", "die area", "wafer price",
                 "controller efficiency")),
    MemoryClass("LPDDR5", "mobile and edge", "medium",
                "the interface rate is the JEDEC class rate",
                ("interface rate", "bus width", "supply voltage"),
                ("energy per bit", "die area", "wafer price",
                 "controller efficiency")),
    MemoryClass("LPDDR5X", "mobile and edge, current", "medium",
                "the 8533 MT/s rate is the JEDEC class rate; every "
                "automotive profile reviewed uses this generation",
                ("interface rate", "bus width", "supply voltage"),
                ("energy per bit", "die area", "wafer price",
                 "controller efficiency")),
    MemoryClass("GDDR6", "graphics and edge accelerator", "low",
                "rate from the standard; the rest scaled",
                ("interface rate", "bus width"),
                ("energy per bit", "die area", "wafer price",
                 "controller efficiency", "cooling class")),
    MemoryClass("HBM2E", "stacked, previous generation", "low",
                "rate from the standard; assembly yield and interposer cost "
                "are estimates nobody publishes",
                ("interface rate", "bus width", "stack height"),
                ("energy per bit", "assembly yield", "interposer cost",
                 "wafer price")),
    MemoryClass("HBM3", "stacked, current", "low",
                "as above",
                ("interface rate", "bus width", "stack height"),
                ("energy per bit", "assembly yield", "interposer cost",
                 "wafer price")),
    MemoryClass("HBM3E", "stacked, current high", "low",
                "as above",
                ("interface rate", "bus width", "stack height"),
                ("energy per bit", "assembly yield", "interposer cost",
                 "wafer price")),
    MemoryClass("HBM4_36", "stacked, next", "very low",
                "the generation is announced; the figures are extrapolated",
                ("bus width",),
                ("interface rate", "energy per bit", "assembly yield",
                 "interposer cost", "wafer price")),
)


# ==============================================================================
# What is NOT here, and is a separate phase
# ==============================================================================
#
# Data expansion adds entries and changes no equation. Structural expansion
# adds a station to the timing decomposition and changes the identity that is
# verified to zero residue across 180 configurations. Mixing them would mean
# shipping a library change and an engine change under one version, and the
# first thing to fail would be impossible to attribute.

# The deployment spectrum found by reviewing a portfolio that spans it: the
# same accelerator core appears as a bare SoC, a USB stick, a low-profile
# card, a module, a desktop box and a vehicle-mounted box. Six products
# differing in almost nothing EXCEPT deployment, and the model cannot tell
# them apart.
DEPLOYMENT_CLASSES = (
    ("standalone SoC", "expressible in part",
     "the arithmetic is expressible; the integration of host, ISP and codec "
     "on one die is not"),
    ("host-attached accelerator", "absent",
     "the link to somebody else's host has no term in the model"),
    ("USB accelerator", "absent",
     "an order of magnitude narrower than PCIe, and would dominate a design "
     "the model assumes has no link at all"),
    ("accelerator module", "absent",
     "a die on a carrier board that plugs into a host - the same missing "
     "link as a card, with a different connector and a different thermal "
     "path"),
    ("edge appliance", "absent",
     "a whole system - host, accelerator, memory, storage, chassis and one "
     "thermal envelope over all of them. The unit of design here is a part"),
    ("industrial box", "absent",
     "adds vehicle power, fanless operation, an ingress rating and an "
     "ambient range, each of which decides a design before any arithmetic "
     "does"),
    ("multi-card server", "absent",
     "eight accelerators, a host and a chassis power budget"),
    ("rack-scale", "absent",
     "servers per rack against a rack power budget"),
)


STRUCTURAL_BACKLOG = (
    ("deployment model",
     "standalone SoC / host-attached / chiplet companion / "
     "multi-accelerator",
     "adds a link between the host and the accelerator that can become the "
     "bottleneck; today they are assumed to be on one die"),
    ("interconnect class",
     "PCIe Gen4/5/6, UCIe, on-chip NoC",
     "a new term in the latency decomposition, which must then be "
     "re-verified across every configuration"),
    ("chiplet packaging",
     "die-to-die links, per-die yield and assembly",
     "changes both the timing and the cost model"),
    ("structured sparsity",
     "arithmetic that depends on the data",
     "the model is deterministic; work that varies with the input is a "
     "different kind of model"),
    ("multi-partition execution",
     "one engine divided between isolated workloads",
     "needs a notion of isolation the model does not have"),
    ("mixed precision within one engine",
     "several numeric formats at different rates on one part",
     "precision is currently a property of the engine, fixed at design "
     "time"),
)


BY_KEY = {c.key: c for c in ACCELERATOR_CLASSES}
MEM_BY_KEY = {c.key: c for c in MEMORY_CLASSES}


def registry_violations() -> List[str]:
    """A class in one place and not the other is a defect."""
    from .compute import COMPUTE_LIBRARY
    from .memory import MEMORY_LIBRARY

    problems = []
    for c in ACCELERATOR_CLASSES:
        if c.key not in COMPUTE_LIBRARY:
            problems.append(f"{c.key}: declared here and absent from the "
                            f"compute library")
        if c.domain not in DOMAINS:
            problems.append(f"{c.key}: unknown domain {c.domain!r}")
        if c.confidence not in CONFIDENCE_LEVELS:
            problems.append(f"{c.key}: unknown confidence {c.confidence!r}")
        if not c.evidence or len(c.evidence) < 25:
            problems.append(f"{c.key}: no evidence stated")
        if not c.estimated:
            problems.append(f"{c.key}: claims nothing is estimated, which "
                            f"cannot be true of an entry in this file")
        for m in c.typical_memory:
            if m not in MEMORY_LIBRARY:
                problems.append(f"{c.key}: names memory {m!r} that does not "
                                f"exist")
    for m in MEMORY_CLASSES:
        if m.key not in MEMORY_LIBRARY:
            problems.append(f"{m.key}: declared here and absent from the "
                            f"memory library")
        if not m.estimated:
            problems.append(f"{m.key}: claims nothing is estimated")
        overlap = set(m.standard_figures) & set(m.estimated)
        if overlap:
            problems.append(f"{m.key}: {', '.join(overlap)} listed as both "
                            f"standard and estimated")
    # every performance-named class must belong to a domain
    unclassified = [k for k in COMPUTE_LIBRARY
                    if k.startswith("class_") and k not in BY_KEY]
    if unclassified:
        problems.append(
            f"performance-named entries with no domain: "
            f"{', '.join(unclassified)} - TOPS is a parameter, not a "
            f"classification")
    return problems


def coverage_metrics() -> Dict:
    """The long-term quality numbers, reported together and never summed."""
    from .compute import COMPUTE_LIBRARY
    from .memory import MEMORY_LIBRARY

    by_domain = {}
    for c in ACCELERATOR_CLASSES:
        by_domain.setdefault(c.domain, []).append(c.key)
    by_confidence = {}
    for c in ACCELERATOR_CLASSES:
        by_confidence[c.confidence] = by_confidence.get(c.confidence, 0) + 1
    return {
        "accelerator classes": len(ACCELERATOR_CLASSES),
        "memory classes": len(MEMORY_CLASSES),
        "domains covered": len(by_domain),
        "domains defined": len(DOMAINS),
        "by domain": by_domain,
        "by confidence": by_confidence,
        "structural backlog": len(STRUCTURAL_BACKLOG),
        "compute library entries": len(COMPUTE_LIBRARY),
        "memory library entries": len(MEMORY_LIBRARY),
    }


def print_registry() -> None:
    print(f"\n{LINE}")
    print(f" ARCHITECTURAL CLASS REGISTRY  v{REGISTRY_VERSION}")
    print(LINE)
    print("  Classes, not products. No vendor is named here and none ever")
    print("  will be: commercial specifications validate this library, they")
    print("  do not become entries in it.\n")

    for domain in DOMAINS:
        members = [c for c in ACCELERATOR_CLASSES if c.domain == domain]
        if not members:
            print(f"  {domain.upper()}  - no class yet")
            continue
        print(f"  {domain.upper()}")
        for line in _wrap(DOMAIN_MEANING[domain], 68):
            print(f"    {line}")
        for c in members:
            print(f"      {c.name:<30s}{c.confidence:<10s}{c.key}")
            print(f"        memory: {', '.join(c.typical_memory)}"
                  f"   deployment: {c.typical_deployment}")
        print()

    print(f"  MEMORY CLASSES")
    for m in MEMORY_CLASSES:
        print(f"      {m.key:<12s}{m.generation:<28s}{m.confidence}")
    print()

    print(f"  EVERY PARAMETER IN THIS FILE IS AN ESTIMATE unless it is")
    print(f"  listed as coming from a standard. Confidence means:")
    for level in CONFIDENCE_LEVELS:
        for i, line in enumerate(_wrap(CONFIDENCE_MEANING[level], 60)):
            print(f"    {level + ':' if i == 0 else '':<12s}{line}")
    print(f"\n  Nothing here is HIGH. No vendor publishes enough about any of")
    print(f"  these for a figure to be checked, and claiming otherwise would")
    print(f"  be the whole failure this file exists to avoid.")

    print(f"\n  NOT IN THIS LIBRARY - STRUCTURAL, A SEPARATE PHASE")
    for name, what, why in STRUCTURAL_BACKLOG:
        print(f"    {name}")
        print(f"      {what}")
        for line in _wrap(why, 62):
            print(f"      {line}")
    print(f"\n  Data expansion adds entries and changes no equation.")
    print(f"  Structural expansion changes the timing decomposition, which")
    print(f"  is verified to zero residue across 180 configurations. Shipping")
    print(f"  both under one version would make the first failure impossible")
    print(f"  to attribute.")
    print(LINE)


def print_coverage_metrics() -> None:
    """Counts of what exists. Deliberately NOT percentages.

    A percentage-based coverage report was written at 4.3.0 and removed at
    4.4.0. The objection was right: a percentage needs a denominator, and
    the denominator implied by "industrial coverage" is the world's
    semiconductor industry. Every number below is a count of something in
    this registry, which is a thing a reader can go and look at.
    """
    m = coverage_metrics()
    print(f"\n{LINE}")
    print(" LIBRARY CONTENTS")
    print(LINE)
    print(f"  accelerator classes      {m['accelerator classes']}")
    print(f"  memory classes           {m['memory classes']}")
    print(f"  domains with a class     {m['domains covered']}")
    print(f"  domains declared         {m['domains defined']}")
    print(f"  structural backlog       {m['structural backlog']}")
    print()
    print(f"  by domain")
    for d in DOMAINS:
        keys = m["by domain"].get(d, [])
        print(f"    {d:<18s}{len(keys)}"
              + ("" if keys else "   <- no class yet"))
    print()
    print(f"  by confidence")
    for level in CONFIDENCE_LEVELS:
        print(f"    {level:<18s}{m['by confidence'].get(level, 0)}")
    print(f"\n  These are counts, not coverage. Nothing here is expressed")
    print(f"  as a fraction of the industry, because this registry is not a")
    print(f"  sample of the industry and a percentage would say it was.")
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
    return lines or [""]


# ==============================================================================
# Host connection - declared, not modelled
# ==============================================================================
#
# Phase 1: the library recognises how an accelerator reaches its host, and the
# analytical model does not use it. Phase 2, when there is a link term in the
# latency decomposition and it has been verified, may switch it on.
#
# The order matters. A parameter that appears in a report before it appears in
# an equation is honest if it says so. A parameter that appears in an equation
# before it has been verified is not, however carefully it was written.

HOST_CONNECTIONS = (
    ("on_board", "On-board", "the accelerator and its host are on one board "
                             "or one die; there is no link to speak of"),
    ("usb3", "USB 3.x", "a stick or dongle - about an order of magnitude "
                        "narrower than a PCIe slot"),
    ("pcie_gen4", "PCIe Gen4", "the common card and module attachment"),
    ("pcie_gen5", "PCIe Gen5", "current cards, roughly twice the lane rate "
                               "of Gen4"),
    ("ethernet", "Ethernet", "a box on a network rather than a part in a "
                             "chassis"),
    ("ucie", "UCIe", "die-to-die inside one package, for chiplets"),
)

HOST_CONNECTION_KEYS = tuple(k for k, _, _ in HOST_CONNECTIONS)
HOST_CONNECTION_NAME = {k: n for k, n, _ in HOST_CONNECTIONS}
HOST_CONNECTION_NOTE = {k: d for k, _, d in HOST_CONNECTIONS}

HOST_CONNECTION_STATUS = (
    "Informational only. The analytical model does not use this in this "
    "release: no latency, bandwidth, power, cost or gate reads it, and a "
    "check requires that every metric is identical at every setting."
)


def describe_host_connection(key: str) -> List[str]:
    """The lines a report prints. Always includes the status."""
    name = HOST_CONNECTION_NAME.get(key, key)
    out = [f"Host connection    {name}"]
    note = HOST_CONNECTION_NOTE.get(key)
    if note:
        out += [f"                   {line}" for line in _wrap(note, 56)]
    out += [f"                   {line}"
            for line in _wrap(HOST_CONNECTION_STATUS, 56)]
    return out


def print_host_connection(key: str, indent: str = "  ") -> None:
    for line in describe_host_connection(key):
        print(f"{indent}{line}")
