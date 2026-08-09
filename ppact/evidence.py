"""
ppact.evidence - how much weight each figure can carry

Every number this simulator prints came from somewhere, and the somewheres are
not equivalent. A vendor's published bandwidth, a profile fitted to that
bandwidth, a simulator output, a cost estimate and a coefficient chosen to make
a teaching point are five different kinds of claim, and presenting them in the
same typeface invites them to be read as one.

    PUBLISHED REFERENCE     a vendor or standards body states it
    REFERENCE-ALIGNED       the model was fitted to a published figure
    SIMULATED               the simulator computed it from the model
    ESTIMATED               a quantity nobody publishes, chosen plausibly
    ENGINEERING ASSUMPTION  a coefficient chosen to make the model behave

Note what is absent: VERIFIED. Comparing a model against a datasheet and
adjusting it until they agree is alignment, not verification. Verification
would mean measuring hardware, or checking against a golden model, and none of
that happened here. The word would have been the strongest claim in the
project and the least supported one.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

# A source that cannot be looked up cannot be a PUBLISHED REFERENCE, whatever
# its standing. Internal reviews, proposals and signed assessments are recorded
# as non-public and take a weaker level, because the property that matters for
# a reference is whether a reader can check it - not who signed it.
NON_PUBLIC_MARKERS = ("review sheet", "proposal", "internal", "signed",
                      "company-reported", "relayed", "not public",
                      "advisory review")


# Ordered strongest first.
LEVELS = (
    "PUBLISHED REFERENCE",
    "REFERENCE-ALIGNED",
    "SIMULATED",
    "ESTIMATED",
    "ENGINEERING ASSUMPTION",
)

LEVEL_MEANING: Dict[str, str] = {
    "PUBLISHED REFERENCE":
        "PUBLICLY AVAILABLE and stated by a vendor or standards body. A reader "
        "can look it up and disagree. Authority is not the test - a signed "
        "internal document may be more authoritative than a datasheet and "
        "still cannot go here, because nobody outside can check it.",
    "REFERENCE-ALIGNED":
        "The model was fitted so that it agrees with a published figure. The "
        "agreement is by construction, not by independent confirmation.",
    "SIMULATED":
        "Computed by the model from its own inputs. As good as the inputs and "
        "the equations, and no better.",
    "ESTIMATED":
        "A quantity nobody publishes - contract prices, stack yields - chosen "
        "to be plausible. Expect it to be wrong in detail and right in order.",
    "ENGINEERING ASSUMPTION":
        "A coefficient chosen so the model behaves as the physics suggests it "
        "should. Where a conclusion depends on one, the conclusion inherits "
        "its standing.",
}


@dataclass(frozen=True)
class Evidence:
    quantity: str
    level: str
    basis: str


EVIDENCE: List[Evidence] = [
    # --- published --------------------------------------------------------
    Evidence("Industry case baselines and targets", "ESTIMATED",
             "Company-reported figures relayed as summaries, not read from the "
             "source proposals. Targets are aims rather than observations, and "
             "no built system has been measured."),
    Evidence("HBM4 interface width (2048 bit)", "PUBLISHED REFERENCE",
             "JEDEC specification, April 2025."),
    Evidence("HBM3E interface width (1024 bit)", "PUBLISHED REFERENCE",
             "JEDEC specification, sixteen channels across the stack."),
    Evidence("H200 capacity and bandwidth", "PUBLISHED REFERENCE",
             "Vendor product page: 141 GB, 4.8 TB/s."),
    Evidence("HBM4 specification bandwidth per stack", "PUBLISHED REFERENCE",
             "Vendor material: over 2.8 TB/s at over 11 Gbps."),
    Evidence("Memory-bound decode arithmetic", "PUBLISHED REFERENCE",
             "A published technical example: 19 tokens per second at 300 GB/s "
             "and 94 at 1.5 TB/s for the same model. Publicly checkable, and "
             "it is arithmetic rather than a measurement."),
    Evidence("Development cost by node", "ESTIMATED",
             "Mask sets, physical implementation, verification, IP porting, "
             "EDA and a re-spin allowance. Mask prices vary by a factor of two "
             "between public sources, effort depends on a team and a re-spin "
             "probability is a judgement. The SHAPE - rising steeply with the "
             "node, amortising away with volume - is not in doubt."),
    Evidence("Node wafer prices and yields", "ESTIMATED",
             "Contract-dependent and not publicly verifiable. They decide "
             "which node comes out cheapest, so that result belongs to this "
             "library rather than to the industry - and a real programme also "
             "weighs volume, mask cost and schedule, none of which is here."),
    Evidence("Process node scaling headline figures", "PUBLISHED REFERENCE",
             "Foundry statements on density, speed and power per node."),

    # --- aligned -----------------------------------------------------------
    Evidence("HBM3E deployed pin rate (6.4 Gbps)", "REFERENCE-ALIGNED",
             "Chosen so six stacks reproduce a published 4.8 TB/s. The "
             "specification allows 9.6; shipping parts do not run there."),
    Evidence("HBM4 deployed pin rate (6.4 Gbps)", "REFERENCE-ALIGNED",
             "Chosen so one stack reproduces a demonstrated 1.6 TB/s."),
    Evidence("HBM3E stack capacity profiles", "REFERENCE-ALIGNED",
             "24 GB 8-high and 36 GB 12-high, as published."),
    Evidence("Memory bandwidth efficiency (LPDDR/GDDR)", "REFERENCE-ALIGNED",
             "Set within the range reported in the DRAM literature."),

    # --- simulated ---------------------------------------------------------
    Evidence("Latency, throughput, utilisation", "SIMULATED",
             "Computed from the roofline, the overlap model and the pipeline."),
    Evidence("Token rate and time to first token", "SIMULATED",
             "From the decode traffic model and the compute rate."),
    Evidence("Energy per inference and average power", "SIMULATED",
             "From per-operation and per-bit energies over the run."),
    Evidence("PPACT scores", "SIMULATED",
             "From the anchors, which are themselves chosen. A score is a "
             "reading of the model, never a verdict on a design."),
    Evidence("Die area from MAC count and SRAM", "SIMULATED",
             "From block areas at the reference node, derated by process."),

    # --- estimated ---------------------------------------------------------
    Evidence("HBM stack cost", "ESTIMATED",
             "Wafer price and die area are contract-dependent and not "
             "publicly checkable. Reported with a cost index so a comparison "
             "survives the absolute figure being wrong."),
    Evidence("Interposer, package and assembly cost", "ESTIMATED",
             "Split into three terms to show that HBM's price is mostly not "
             "its DRAM. The split is plausible, not sourced."),
    Evidence("Stack assembly yield", "ESTIMATED",
             "0.85 at 8-high, 0.78 at 12-high, 0.68 at 16-high. Direction "
             "certain, magnitude not."),
    Evidence("Passive cooling limit (W/mm2)", "ENGINEERING ASSUMPTION",
             "One number standing in for heatsink area and resistance, "
             "ambient temperature, natural against forced convection, "
             "chassis, sustained against burst load, junction temperature and "
             "the host's own heat. It decides every cooling-compatibility "
             "verdict and has NO external confirmation: a case that appeared "
             "to provide one was withdrawn when the vendor's own "
             "documentation turned out to recommend airflow for the part."),
    Evidence("Accelerator power range across product classes", "ESTIMATED",
             "Published bands for three classes - 6-8 W, 15-60 W, 100-450 W - "
             "span 39x end to end and the library spans 15x. The ordering is "
             "right and the range is compressed, with larger parts understated "
             "more. Recorded, not corrected."),
    Evidence("Memory background power", "ESTIMATED",
             "Refresh, PHY and termination per package. Vendors publish active "
             "figures under chosen conditions and rarely publish idle ones."),
    Evidence("Memory and accelerator power", "ESTIMATED",
             "From pJ/bit and pJ/MAC figures that vendors publish only "
             "sometimes and only under chosen conditions."),
    Evidence("Latency measurement boundaries", "ESTIMATED",
             "Where each company KPI starts and ends. Taken from "
             "non-public programme review documents, so it cannot be cited or "
             "checked from outside - recorded here as an estimate for that "
             "reason, not because the source is weak."),
    Evidence("Application-domain metric bands", "ESTIMATED",
             "Typical ranges for TOPS, TOPS per watt, latency, throughput, "
             "accuracy, bandwidth and utilisation across five product domains. "
             "The source workbook states the ranges are a synthesis of "
             "published references rather than measurements, and they describe "
             "accelerators while this model computes whole systems."),
    Evidence("Accuracy cost of a smaller network", "ENGINEERING ASSUMPTION",
             "NOT MODELLED. The accuracy table covers quantisation only. "
             "Pruning, distillation and a smaller architecture all reduce "
             "bytes and cost different amounts of accuracy, and the model has "
             "no basis for any of them - so a model-size change is reported "
             "with its accuracy UNPRICED until someone supplies a figure."),
    Evidence("Mixture-of-experts routing cost", "ENGINEERING ASSUMPTION",
             "NOT MODELLED. The memory-against-compute asymmetry is "
             "structural and is represented; the cost of choosing experts, "
             "and how much consecutive tokens reuse the same ones, is not. An "
             "MoE's real traffic sits between the active and the total, and "
             "where depends on the router."),
    Evidence("Quantisation accuracy cost by width", "ENGINEERING ASSUMPTION",
             "FP16 0, FP8 0.3, INT8 0.8, INT4 3.5 points. NOT computed - what "
             "a network loses depends on the network, the calibration and the "
             "method, and the model has no basis for any of them. Printed "
             "with every sweep so a reader can replace them before quoting "
             "any verdict that rests on them."),
    Evidence("Quantisation loss by model family", "ESTIMATED",
             "From the published quantisation literature, as a central value "
             "rather than a measurement."),

    # --- assumption --------------------------------------------------------
    Evidence("Small-workload utilisation derating", "ENGINEERING ASSUMPTION",
             "How far below its stated utilisation an engine falls on a model "
             "too small to fill it. Sets the absolute latency scale."),
    Evidence("Framework overhead per inference", "ENGINEERING ASSUMPTION",
             "Graph launch, runtime and driver cost. Dominates small models on "
             "general-purpose engines."),
    Evidence("Module idle power", "ESTIMATED",
             "A module rating covers die, DRAM, PMIC and interface. Vendors "
             "publish a rating, rarely an idle figure."),
    Evidence("Sensor capture and control latency", "ENGINEERING ASSUMPTION",
             "Chosen so that a sensor-to-control figure can be reported "
             "beside a pure inference one. Not from the proposals."),
    Evidence("LLM serving-stack efficiency (0.55)", "ENGINEERING ASSUMPTION",
             "What a serving stack delivers against the memory ceiling. "
             "Two published deployments bracket it at 0.28-0.32 under FP8 or "
             "0.54-0.64 under FP16, and neither states its precision. The "
             "value used sits at the FP16 end. This is the largest single "
             "uncertainty in the model and it cannot be narrowed from public "
             "sources - only by measuring."),
    Evidence("Bottleneck strength thresholds", "ENGINEERING ASSUMPTION",
             "The compute-to-memory ratio is computed; the five names it maps "
             "to are not. Whether 1.61 counts as weakly or strongly compute-"
             "bound is a threshold chosen by hand, and the ratio is reported "
             "beside the label so a reader can disagree with the boundary "
             "without disagreeing with the model."),
    Evidence("Host memory overlap (0.70)", "ENGINEERING ASSUMPTION",
             "How much of the host's own traffic hides behind its arithmetic. "
             "No external figure; the value was checked across 0.70 to 0.92 "
             "and no starting-point design changes verdict, so the conclusions do "
             "not rest on it."),
    Evidence("Controller contention coefficient (0.12)",
             "ENGINEERING ASSUMPTION",
             "No bank or arbitration model stands behind it. The dual-engine "
             "reversal on a narrow bus depends entirely on this number."),
    Evidence("HBM4 controller efficiency (0.88 vs 0.85)",
             "ENGINEERING ASSUMPTION",
             "32 channels plausibly absorb conflicts better than 16. The "
             "equal-bandwidth comparison's residual 3.5% is this figure."),
    Evidence("Parallel split efficiency (0.85)", "ENGINEERING ASSUMPTION",
             "Partition, synchronise and merge cost. Sets how much of a 2x "
             "speedup a balanced split delivers."),
    Evidence("Offload dispatch overheads", "ENGINEERING ASSUMPTION",
             "Fixes where preprocessing offload breaks even by frame size."),
    Evidence("Application requirement figures", "ENGINEERING ASSUMPTION",
             "Frame rates, accuracy budgets, power and cost limits. Chosen to "
             "make each application a distinct design problem."),
    Evidence("Grading weights", "ENGINEERING ASSUMPTION",
             "What each application values. A pedagogical choice."),
]


def by_level() -> Dict[str, List[Evidence]]:
    out: Dict[str, List[Evidence]] = {lv: [] for lv in LEVELS}
    for e in EVIDENCE:
        out[e.level].append(e)
    return out


def print_evidence(detail: bool = True) -> None:
    line = "=" * 80
    print(line)
    print(" EVIDENCE LEVELS")
    print(line)
    print("  How far each figure can be trusted, and why. The word VERIFIED is")
    print("  deliberately absent: matching a model to a datasheet is alignment,")
    print("  not verification, and nothing here was measured on hardware.\n")
    grouped = by_level()
    for level in LEVELS:
        items = grouped[level]
        if not items:
            continue
        print(f"  {level}  ({len(items)})")
        print(f"    {LEVEL_MEANING[level]}\n")
        for e in items:
            print(f"      {e.quantity}")
            if detail:
                print(f"        {e.basis}")
        print()


def level_of(quantity: str) -> str:
    """Best-effort lookup by substring, defaulting to the weakest claim."""
    low = quantity.lower()
    for e in EVIDENCE:
        if e.quantity.lower() in low or low in e.quantity.lower():
            return e.level
    return "ENGINEERING ASSUMPTION"
