"""
ppact.industry_profiles - published specifications, as validation evidence

WHAT THIS IS, AND WHAT IT IS NOT
================================
This is NOT a product catalogue. Nothing here appears in the Studio menu, and
no student sees a vendor name. PPACT Studio is an architecture exploration
tool, and a tool that shipped a list of commercial parts would be inviting
the one comparison it cannot support: "is this what the real thing does?"

What these profiles ARE is a test of the LIBRARY. A published specification
is a sample of what the industry actually builds. If the Studio library
cannot express a concept that a shipping product is built around, that is a
gap in the library - and a gap nobody has written down is a gap nobody will
close.

THREE KINDS OF INFORMATION, KEPT APART
--------------------------------------
    PUBLISHED   the vendor states it, in public, in words
    ESTIMATED   derived here from something published, and labelled
    UNKNOWN     not stated, and NOT filled in

The third is the one that matters. A profile with an invented number reads
exactly like a profile with a measured one, and the difference is invisible
to everybody downstream. So an unknown field stays unknown, and confidence is
the ratio of published to estimated - not a feeling.

THE SAMPLE IS SMALL, AND SAYING SO IS PART OF THE OUTPUT
--------------------------------------------------------
At the time of writing this holds three parts from one vendor. That is enough
to find gaps - it already found four - and nowhere near enough to call a
trend. Every report says how many profiles it rests on, because a trend drawn
from one vendor is that vendor's roadmap, not the industry's.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

LINE = "=" * 78

PUBLISHED = "published"
ESTIMATED = "estimated"
UNKNOWN = "unknown"

# The architectural categories the library is measured against. Coverage is
# reported per category rather than as one number: "68% covered" hides which
# 32%, and which 32% is the whole question.
CATEGORIES = ("host cpu", "accelerator", "memory", "interconnect", "chiplet",
              "virtualization", "safety", "security", "packaging",
              "quantization", "sparsity", "deployment")


@dataclass
class Fact:
    """One stated thing, with where it came from."""
    category: str
    concept: str
    value: str
    status: str              # published / estimated / unknown
    note: str = ""

    def __post_init__(self):
        if self.status == UNKNOWN and self.value not in ("", "unknown"):
            raise ValueError(
                f"{self.concept}: an unknown fact carries a value "
                f"({self.value!r}). Unknown means not stated, and filling it "
                f"in makes an estimate indistinguishable from a measurement.")


@dataclass
class Profile:
    key: str
    name: str
    vendor: str
    source: str              # where the text came from
    retrieved: str
    facts: Tuple[Fact, ...]
    note: str = ""

    def by_status(self, status: str) -> List[Fact]:
        return [f for f in self.facts if f.status == status]

    def confidence(self) -> Optional[float]:
        """Published over published-plus-estimated. Unknowns are not counted.

        Counting unknowns would let a profile improve its confidence by
        listing fewer of them, which is the opposite of what should happen.
        """
        p = len(self.by_status(PUBLISHED))
        e = len(self.by_status(ESTIMATED))
        return None if (p + e) == 0 else p / (p + e) * 100


# ==============================================================================
# The profiles
# ==============================================================================
#
# Every fact below is either quoted from the vendor's own public product page
# or marked as an estimate derived here. Where the page is silent the field is
# UNKNOWN and stays that way - the temptation to fill in a plausible LPDDR5X
# width or a plausible die area is exactly the temptation this file exists to
# refuse.

_BOS_SOURCE = "BOS Semiconductors public product page"
_BOS_DATE = "2026-08"

PROFILES: Tuple[Profile, ...] = (

    Profile(
        "bos_eagle_n", "Eagle-N", "BOS Semiconductors",
        source=_BOS_SOURCE, retrieved=_BOS_DATE,
        facts=(
            Fact("accelerator", "peak arithmetic", "250 INT8 TOPS (dense)",
                 PUBLISHED),
            Fact("accelerator", "core family", "Tenstorrent Tensix NPU",
                 PUBLISHED),
            Fact("accelerator", "programmable cores",
                 "RISC-V cores for future models", PUBLISHED),
            Fact("quantization", "supported formats",
                 "TF32, FP16, BF16, FP8, MXFP, MXINT, INT8", PUBLISHED,
                 "the page states performance varies by format and gives no "
                 "figure for any format but INT8"),
            Fact("quantization", "per-format throughput", "", UNKNOWN,
                 "stated to vary; no numbers given"),
            Fact("sparsity", "structured sparsity", "supported", PUBLISHED),
            Fact("sparsity", "sparse throughput", "", UNKNOWN,
                 "the 250 TOPS figure is explicitly dense"),
            Fact("host cpu", "host core", "Arm Cortex-A53", PUBLISHED),
            Fact("host cpu", "core count", "", UNKNOWN),
            Fact("interconnect", "host attach", "PCIe Gen5", PUBLISHED),
            Fact("interconnect", "die-to-die", "UCIe", PUBLISHED),
            Fact("interconnect", "link bandwidth", "", UNKNOWN),
            Fact("memory", "external memory", "LPDDR5X", PUBLISHED),
            Fact("memory", "capacity and width", "", UNKNOWN),
            Fact("chiplet", "architecture", "open chiplet", PUBLISHED),
            Fact("virtualization", "partitioning",
                 "4-way physical partition, freedom from interference",
                 PUBLISHED),
            Fact("safety", "grade", "ASIL-B, AEC-Q100 Grade 2", PUBLISHED),
            Fact("security", "security engine", "present", PUBLISHED),
            Fact("packaging", "process node", "", UNKNOWN),
            Fact("deployment", "role", "co-processor to a host AP",
                 PUBLISHED),
            Fact("deployment", "production", "2027", PUBLISHED),
            Fact("accelerator", "power", "", UNKNOWN,
                 "the page claims 1.5x TOPS/W 'compared to existing "
                 "solution' and names no baseline, so neither the ratio nor "
                 "an absolute figure can be used as evidence"),
            Fact("accelerator", "cost", "", UNKNOWN,
                 "same: 2x TOPS/$ against an unnamed baseline"),
        ),
        note="The TOPS/W and TOPS/$ claims are excluded from evidence because "
             "the baseline is not named. A ratio without a baseline is not a "
             "measurement of anything.",
    ),

    Profile(
        "bos_n1501", "N1501", "BOS Semiconductors",
        source=_BOS_SOURCE, retrieved=_BOS_DATE,
        facts=(
            Fact("accelerator", "peak arithmetic", "250 INT8 TOPS (dense)",
                 PUBLISHED),
            Fact("host cpu", "host core", "Arm Cortex-A53", PUBLISHED),
            Fact("interconnect", "host attach", "PCIe", PUBLISHED),
            Fact("memory", "external memory", "LPDDR5X", PUBLISHED),
            Fact("security", "security", "included", PUBLISHED),
            Fact("safety", "target", "automotive", PUBLISHED),
            Fact("deployment", "role", "co-processor to a host system",
                 PUBLISHED),
            Fact("chiplet", "architecture", "", UNKNOWN),
            Fact("packaging", "process node", "", UNKNOWN),
            Fact("quantization", "supported formats", "", UNKNOWN),
            Fact("sparsity", "structured sparsity", "", UNKNOWN),
            Fact("virtualization", "partitioning", "", UNKNOWN),
        ),
    ),

    Profile(
        "bos_n1301", "N1301", "BOS Semiconductors",
        source=_BOS_SOURCE, retrieved=_BOS_DATE,
        facts=(
            Fact("accelerator", "peak arithmetic", "190 INT8 TOPS (dense)",
                 PUBLISHED),
            Fact("deployment", "role", "co-processor to a host system",
                 PUBLISHED),
            Fact("safety", "target", "automotive", PUBLISHED),
            Fact("deployment", "production", "2028", PUBLISHED),
            Fact("host cpu", "host core", "", UNKNOWN,
                 "the page for this part does not repeat the CPU"),
            Fact("memory", "external memory", "", UNKNOWN),
            Fact("interconnect", "host attach", "", UNKNOWN),
            Fact("chiplet", "architecture", "", UNKNOWN),
            Fact("packaging", "process node", "", UNKNOWN),
            Fact("quantization", "supported formats", "", UNKNOWN),
            Fact("sparsity", "structured sparsity", "", UNKNOWN),
            Fact("virtualization", "partitioning", "", UNKNOWN),
        ),
        note="Listed separately from N1501 despite the similar description, "
             "because two parts described alike are still two parts and "
             "merging them would invent a shared specification.",
    ),
)

# A second vendor, and a different market. The first three profiles are
# automotive; these are data-centre and edge-server inference, which is the
# other half of where AI silicon is being built. Coverage measured against
# one market is coverage of one market.
#
# This datasheet is far more specific than the first, which changes what can
# be used: process node, clock, per-format throughput, memory capacity and
# bandwidth, on-chip buffer, host interface, TDP and form factor are all
# stated outright.
#
# Its comparative claims are excluded for a DIFFERENT reason from the first
# vendor's. That one named no baseline at all. This one names its baselines -
# and states in its own disclaimer that the competitor figures were measured
# by itself. A benchmark of a rival, run by the rival's competitor, is not a
# neutral measurement, and using it would put one vendor's view of another
# into this library.

_F_SOURCE = "FuriosaAI public datasheets and product pages"
_F_DATE = "2026-08"

MORE_PROFILES = (

    Profile(
        "dc_inference_card_gen2", "Gen 2 data-centre inference card",
        "FuriosaAI", source=_F_SOURCE, retrieved=_F_DATE,
        facts=(
            Fact("accelerator", "peak arithmetic", "512 TOPS INT8",
                 PUBLISHED),
            Fact("accelerator", "alternate formats",
                 "256 TFLOPS BF16, 512 TFLOPS FP8, 1024 TOPS INT4",
                 PUBLISHED),
            Fact("accelerator", "clock", "1.0 GHz", PUBLISHED),
            Fact("accelerator", "on-chip buffer", "256 MB SRAM", PUBLISHED),
            Fact("packaging", "process node", "5 nm", PUBLISHED),
            Fact("memory", "external memory", "HBM3", PUBLISHED),
            Fact("memory", "capacity", "48 GB", PUBLISHED),
            Fact("memory", "bandwidth", "1.5 TB/s", PUBLISHED),
            Fact("interconnect", "host attach", "PCIe Gen5 x16", PUBLISHED),
            Fact("deployment", "form factor",
                 "PCIe dual-slot full-height", PUBLISHED),
            Fact("deployment", "role", "host-attached accelerator card",
                 PUBLISHED),
            Fact("packaging", "thermal solution", "passive", PUBLISHED),
            Fact("accelerator", "power", "150 W TDP", PUBLISHED),
            Fact("virtualization", "multi-instance", "8 instances",
                 PUBLISHED),
            Fact("virtualization", "sr-iov", "supported", PUBLISHED),
            Fact("security", "secure boot", "root of trust", PUBLISHED),
            Fact("memory", "ecc", "supported", PUBLISHED),
            Fact("quantization", "supported formats",
                 "BF16, FP8, INT8, INT4", PUBLISHED),
            Fact("sparsity", "structured sparsity", "", UNKNOWN),
            Fact("chiplet", "architecture", "", UNKNOWN),
            Fact("host cpu", "host core", "", UNKNOWN,
                 "the card attaches to somebody else's host"),
            Fact("accelerator", "cost", "", UNKNOWN),
            Fact("accelerator", "measured throughput", "", UNKNOWN,
                 "throughput figures are published against named competitor "
                 "parts, but the datasheet states the competitor "
                 "measurements were taken by this vendor. A benchmark of a "
                 "rival run by its competitor is not a neutral measurement."),
        ),
        note="The most specific profile held. Its comparative charts are "
             "excluded from evidence: the baselines ARE named, unlike the "
             "automotive profiles, but the vendor measured them itself.",
    ),

    Profile(
        "edge_vision_card_gen1", "Gen 1 server vision accelerator",
        "FuriosaAI", source=_F_SOURCE, retrieved=_F_DATE,
        facts=(
            Fact("accelerator", "peak arithmetic", "64 TOPS INT8",
                 PUBLISHED),
            Fact("accelerator", "clock", "2.0 GHz", PUBLISHED),
            Fact("accelerator", "on-chip buffer", "32 MB SRAM", PUBLISHED),
            Fact("packaging", "process node", "14 nm", PUBLISHED),
            Fact("memory", "external memory", "LPDDR4X", PUBLISHED),
            Fact("memory", "capacity", "16 GB", PUBLISHED),
            Fact("memory", "bandwidth", "66 GB/s", PUBLISHED),
            Fact("interconnect", "host attach", "PCIe Gen4 x8", PUBLISHED),
            Fact("deployment", "form factor",
                 "PCIe single-slot half-height", PUBLISHED),
            Fact("deployment", "role", "host-attached accelerator card",
                 PUBLISHED),
            Fact("packaging", "thermal solution", "passive", PUBLISHED),
            Fact("accelerator", "power", "40-60 W TDP, configurable",
                 PUBLISHED),
            Fact("virtualization", "supported", "yes", PUBLISHED),
            Fact("memory", "ecc", "supported", PUBLISHED),
            Fact("quantization", "supported formats", "INT8", PUBLISHED),
            Fact("sparsity", "structured sparsity", "", UNKNOWN),
            Fact("chiplet", "architecture", "", UNKNOWN),
            Fact("safety", "grade", "", UNKNOWN),
            Fact("accelerator", "cost", "", UNKNOWN),
        ),
        note="A previous-generation part on a mature node. Useful precisely "
             "because it is not the newest: it fixes the low end of the "
             "server inference band, which one flagship alone cannot.",
    ),

    Profile(
        "rack_inference_server", "8-card inference server", "FuriosaAI",
        source=_F_SOURCE, retrieved=_F_DATE,
        facts=(
            Fact("deployment", "role", "rack-mounted multi-card server",
                 PUBLISHED),
            Fact("deployment", "accelerators per server", "8 cards",
                 PUBLISHED),
            Fact("deployment", "form factor", "4U rackmount", PUBLISHED),
            Fact("accelerator", "aggregate arithmetic",
                 "4096 TOPS INT8 across 8 cards", PUBLISHED),
            Fact("memory", "aggregate capacity", "384 GB HBM3", PUBLISHED),
            Fact("memory", "aggregate bandwidth", "12 TB/s", PUBLISHED),
            Fact("host cpu", "host core",
                 "dual server x86, 64 cores total", PUBLISHED),
            Fact("memory", "host memory", "1 TB DDR5", PUBLISHED),
            Fact("accelerator", "power", "3 kW per server", PUBLISHED),
            Fact("deployment", "servers per rack",
                 "up to 5 in a 15 kW rack", PUBLISHED),
            Fact("interconnect", "networking", "2x 25G dual-port",
                 PUBLISHED),
            Fact("packaging", "process node", "", UNKNOWN),
            Fact("deployment", "cost", "", UNKNOWN),
            Fact("deployment", "measured tokens per rack", "", UNKNOWN,
                 "rack throughput is published beside a competitor rack, "
                 "measured by this vendor"),
        ),
        note="The scale the Studio is furthest from. A design here is a "
             "single device; this is eight accelerators, a host, a chassis "
             "power budget and a rack power budget, and none of those four "
             "is expressible today.",
    ),
)

PROFILES = PROFILES + MORE_PROFILES

# A third vendor, and the widest one yet. The first two showed a market
# each; this portfolio shows a DEPLOYMENT SPECTRUM - the same accelerator
# core appearing as a bare SoC, a USB stick, a low-profile card, a module,
# a desktop box and a vehicle-mounted box.
#
# That is the most useful thing reviewed so far, because it is the axis the
# Studio is weakest on. A design here is one accelerator with one host. Six
# of these products differ in almost nothing EXCEPT how they are deployed,
# and the model cannot tell them apart at all.

_M_SOURCE = "Mobilint public product pages"
_M_DATE = "2026-08"

SPECTRUM_PROFILES = (

    Profile(
        "ondevice_ai_soc", "On-device AI SoC", "Mobilint",
        source=_M_SOURCE, retrieved=_M_DATE,
        facts=(
            Fact("accelerator", "peak arithmetic", "10 TOPS INT8",
                 PUBLISHED),
            Fact("accelerator", "power", "3 W TDP", PUBLISHED),
            Fact("host cpu", "host core",
                 "quad Arm Cortex-A53 plus Cortex-M0+", PUBLISHED),
            Fact("host cpu", "clock", "up to 1.2 GHz", PUBLISHED),
            Fact("memory", "external memory", "DDR4, LPDDR4/4X", PUBLISHED),
            Fact("memory", "capacity", "up to 8 GB", PUBLISHED),
            Fact("memory", "interface rate", "4266 MT/s", PUBLISHED),
            Fact("packaging", "package size", "17 x 17 mm", PUBLISHED),
            Fact("deployment", "role", "standalone on-device SoC",
                 PUBLISHED),
            Fact("deployment", "integrated blocks",
                 "ISP, video codec, CPU on one die", PUBLISHED),
            Fact("packaging", "process node", "", UNKNOWN),
            Fact("accelerator", "on-chip buffer", "", UNKNOWN),
            Fact("accelerator", "cost", "", UNKNOWN),
            Fact("chiplet", "architecture", "", UNKNOWN),
            Fact("virtualization", "partitioning", "", UNKNOWN),
        ),
        note="An accelerator that is also the host, the image pipeline and "
             "the codec. The Studio treats every design as a bare "
             "accelerator beside a separate host, and cannot express this "
             "at all.",
    ),

    Profile(
        "usb_ai_accelerator", "USB AI accelerator", "Mobilint",
        source=_M_SOURCE, retrieved=_M_DATE,
        facts=(
            Fact("accelerator", "peak arithmetic", "10 TOPS INT8",
                 PUBLISHED),
            Fact("accelerator", "power", "3 W TDP", PUBLISHED),
            Fact("host cpu", "host core", "quad Arm Cortex-A53 to 1.2 GHz",
                 PUBLISHED),
            Fact("memory", "external memory", "LPDDR4X at 4266 MT/s",
                 PUBLISHED),
            Fact("memory", "capacity", "4 GB or 8 GB", PUBLISHED),
            Fact("interconnect", "host attach", "USB 3.1 Gen1", PUBLISHED),
            Fact("deployment", "role",
                 "host-attached accelerator over USB", PUBLISHED),
            Fact("deployment", "host architectures", "x86, Arm, RISC-V",
                 PUBLISHED),
            Fact("deployment", "form factor", "90 x 40 x 16 mm stick",
                 PUBLISHED),
            Fact("packaging", "process node", "", UNKNOWN),
            Fact("accelerator", "cost", "", UNKNOWN),
        ),
        note="The same silicon as the SoC above, deployed differently. USB "
             "is an order of magnitude narrower than PCIe and would "
             "dominate a design the model currently assumes has no link at "
             "all.",
    ),

    Profile(
        "edge_accelerator_card", "Low-profile accelerator card", "Mobilint",
        source=_M_SOURCE, retrieved=_M_DATE,
        facts=(
            Fact("accelerator", "peak arithmetic", "80 TOPS", PUBLISHED),
            Fact("accelerator", "power", "25 W TDP", PUBLISHED),
            Fact("memory", "external memory", "LPDDR4X", PUBLISHED),
            Fact("memory", "capacity", "16 GB, optional 32 GB", PUBLISHED),
            Fact("memory", "bandwidth", "66.7 GB/s", PUBLISHED),
            Fact("interconnect", "host attach", "PCIe Gen4 x8", PUBLISHED),
            Fact("deployment", "role", "host-attached accelerator card",
                 PUBLISHED),
            Fact("deployment", "concurrent models",
                 "up to 32 models at once", PUBLISHED),
            Fact("packaging", "process node", "", UNKNOWN),
            Fact("accelerator", "on-chip buffer", "", UNKNOWN),
            Fact("accelerator", "cost", "", UNKNOWN),
            Fact("accelerator", "measured frame rates", "", UNKNOWN,
                 "per-model frame rates are published, but on models the "
                 "Studio does not carry and without the batch size, input "
                 "resolution or precision that would make them comparable"),
        ),
        note="The 25 W card band, which the library skipped entirely: "
             "between an embedded SoC and a data-centre card.",
    ),

    Profile(
        "edge_ai_appliance", "Desktop edge AI appliance", "Mobilint",
        source=_M_SOURCE, retrieved=_M_DATE,
        facts=(
            Fact("accelerator", "peak arithmetic", "80 TOPS", PUBLISHED),
            Fact("accelerator", "power", "70 W TDP for the whole box",
                 PUBLISHED),
            Fact("host cpu", "host core", "mobile-class x86 with integrated "
                 "graphics", PUBLISHED),
            Fact("memory", "host memory", "32 GB DDR5", PUBLISHED),
            Fact("deployment", "role", "complete AI system, not a part",
                 PUBLISHED),
            Fact("deployment", "form factor", "178 x 116 x 67 mm, 1.3 kg",
                 PUBLISHED),
            Fact("deployment", "environment",
                 "-20 to 60 C with 0.5 m/s airflow", PUBLISHED),
            Fact("packaging", "process node", "", UNKNOWN),
            Fact("deployment", "cost", "", UNKNOWN),
        ),
        note="A whole system rather than a component: host, accelerator, "
             "memory, storage, chassis and a thermal envelope for all of "
             "them. The Studio's unit of design is a part.",
    ),

    Profile(
        "industrial_ai_box", "Vehicle-mounted industrial AI box", "Mobilint",
        source=_M_SOURCE, retrieved=_M_DATE,
        facts=(
            Fact("accelerator", "peak arithmetic", "10 TOPS INT8",
                 PUBLISHED),
            Fact("accelerator", "power", "10 W TDP", PUBLISHED),
            Fact("host cpu", "host core",
                 "quad Arm Cortex-A53 at 1.2 GHz plus Cortex-M0+",
                 PUBLISHED),
            Fact("memory", "external memory", "LPDDR4/4X", PUBLISHED),
            Fact("memory", "capacity", "4 GB or 8 GB", PUBLISHED),
            Fact("deployment", "role", "standalone system on a vehicle",
                 PUBLISHED),
            Fact("deployment", "input power", "9-36 V DC", PUBLISHED),
            Fact("deployment", "cooling", "fanless", PUBLISHED),
            Fact("deployment", "environment", "-20 to 60 C, IP50",
                 PUBLISHED),
            Fact("security", "secure boot", "present", PUBLISHED),
            Fact("packaging", "process node", "", UNKNOWN),
            Fact("deployment", "cost", "", UNKNOWN),
        ),
        note="Deployment constraints the Studio has no axis for: vehicle "
             "power, fanless operation, an ingress rating and an ambient "
             "range. Each of those decides a design before any arithmetic "
             "does.",
    ),
)

PROFILES = PROFILES + SPECTRUM_PROFILES

BY_KEY = {p.key: p for p in PROFILES}


# ==============================================================================
# What the library can express
# ==============================================================================
#
# For each category: can the Studio library represent this concept at all?
# Written by hand and checked against the code, in the same way the capability
# map is - a claim that points at nothing is a claim nobody can check.

@dataclass
class Capability:
    category: str
    state: str               # "expressed", "partial", "absent"
    how: str                 # what in the library carries it, or why not
    evidence: str = ""       # a module or metric that proves it


LIBRARY_CAPABILITY: Tuple[Capability, ...] = (
    Capability("host cpu", "expressed",
               "the host is a first-class station with its own roofline",
               "ppact.cpu.CPU_LIBRARY"),
    Capability("accelerator", "partial",
               "engines are expressed from 0.4 to 600 TOPS, but the "
               "automotive band around 200-300 TOPS is empty: the library "
               "jumps from 51 to 600",
               "ppact.compute.COMPUTE_LIBRARY"),
    Capability("memory", "partial",
               "LPDDR5, GDDR6 and four HBM generations are expressed; "
               "LPDDR5X is not",
               "ppact.memory.MEMORY_LIBRARY"),
    Capability("interconnect", "absent",
               "a host-attached accelerator over PCIe has no link in the "
               "model - the host and the accelerator are assumed to be on "
               "one die, so the link cannot become the bottleneck"),
    Capability("chiplet", "absent",
               "a single logic node is assumed; this is already an open item "
               "in the capability map",
               "ppact.framework.FRAMEWORK"),
    Capability("virtualization", "absent",
               "no notion of partitioning an engine between isolated "
               "workloads"),
    Capability("safety", "partial",
               "an application can require automotive grade, but grades are "
               "not distinguished and carry no area or cost",
               "ppact.application.Application.requires_automotive_grade"),
    Capability("security", "absent",
               "no security engine, and no area or power for one"),
    Capability("packaging", "partial",
               "package footprint and cooling class are expressed; advanced "
               "packaging and interposers are priced but not structural",
               "ppact.memory.MemorySpec.interposer_cost_usd"),
    Capability("quantization", "partial",
               "INT8, FP16 and a quantisation sweep down to INT4 exist; the "
               "microscaling formats MXFP and MXINT do not",
               "ppact.economics.QUANT_BYTES"),
    Capability("sparsity", "absent",
               "arithmetic is dense; a structured-sparsity mode would make "
               "the work data-dependent, which the deterministic model does "
               "not express"),
    Capability("deployment", "partial",
               "a design is a whole system; a co-processor attached to "
               "somebody else's host is not expressible",
               "ppact.system.SystemConfig"),
)

CAPABILITY_BY_CATEGORY = {c.category: c for c in LIBRARY_CAPABILITY}


# ==============================================================================
# Alignment: does the model explain WHY these products look like this?
# ==============================================================================
#
# Coverage asks whether a concept can be named. Alignment asks something
# harder: does the Studio model give the same reason the industry gives for
# doing it? A library that can express a memory choice but predicts the
# opposite one has coverage and no alignment, and coverage alone would call
# that a pass.

@dataclass
class AlignmentCase:
    observation: str         # what the products do
    model_says: str          # what the Studio model predicts, and from what
    verdict: str             # "explains", "silent", "contradicts"
    basis: str               # how this was decided


ALIGNMENT: Tuple[AlignmentCase, ...] = (
    AlignmentCase(
        "an automotive AI accelerator is attached to an existing host "
        "processor rather than replacing it",
        "the model's host is a separate station whose preparation work can "
        "dominate a job - lesson 2 shows a system running at the host's "
        "speed with the accelerator idle",
        "explains",
        "the host-bound case is reproduced by the model and is the subject "
        "of a lesson and a demo"),
    AlignmentCase(
        "LPDDR rather than HBM on an automotive part",
        "the model refuses HBM on a passively cooled product on cooling "
        "CLASS, not on cost or power - and shows the same part gaining "
        "little where the design is not memory-bound",
        "explains",
        "ppact.decide cooling-class gate; the drone lesson"),
    AlignmentCase(
        "chiplets used to build 300, 400 and 800 TOPS parts from two dies",
        "the model expresses at most two engines ON ONE DIE and has no "
        "die-to-die link",
        "silent",
        "no interconnect station exists; the model neither predicts nor "
        "contradicts this"),
    AlignmentCase(
        "structured sparsity offered alongside a dense TOPS figure",
        "the model computes dense arithmetic only",
        "silent",
        "sparsity would make the work data-dependent"),
    AlignmentCase(
        "four-way physical partitioning for virtualization",
        "the model has no notion of isolating workloads on one engine",
        "silent",
        "no partitioning concept"),
    AlignmentCase(
        "a wide range of numeric formats offered on one engine",
        "the model treats precision as a property of the engine, fixed at "
        "design time, and prices a change in accuracy",
        "partial",
        "the axis exists; a single engine supporting seven formats at "
        "different rates does not"),
)
