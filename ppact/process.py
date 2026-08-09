"""
ppact.process - process nodes, derating factors, and node economics

A process node is a property of a DIE, not of a system. A monolithic SoC runs
its CPU, GPU and NPU on one node because they share silicon; a standalone
accelerator on its own die may sit one or two nodes behind the host it serves,
and often does, because its economics differ.

    monolithic SoC     CPU node = GPU node = NPU node = the SoC node
    separate dies      each die carries its own node

Getting this wrong in either direction is a real modelling error. Treating the
node as a system property forces an integrated NPU onto the wrong process;
treating it as a per-block property lets a student put a 3 nm NPU next to a
16 nm CPU on one die, which nobody can manufacture.

TWO REFERENCES, DELIBERATELY SEPARATE
-------------------------------------
Physical scaling (area, energy, Fmax) is quoted relative to N16, because that is
where the block libraries were calibrated. Node names are generation labels,
not dimensions - the gate length at "3 nm" is nowhere near 3 nm - so the
factors here matter and the names do not. Cost is not a ratio: wafer price,
yield and mask cost are absolute, because a ratio would hide the fact that a
shrink can make a die smaller and more expensive at the same time.

    good silicon cost per mm2 = wafer price / (usable area x die yield)

All figures are engineering estimates for teaching. Foundries do not publish
per-customer wafer pricing; public numbers are market estimates that move with
contract, volume and yield maturity. Every value here is meant to be edited.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


REFERENCE_NODE = "N16"          # physical scaling reference
COST_REFERENCE_NODE = "N4"      # wafer-price reference, factor 1.00

WAFER_PRICE_N4_USD = 16000.0    # 300 mm wafer at the cost reference node
USABLE_WAFER_MM2 = 60000.0      # 70686 mm2 gross, less edge exclusion and scribe
MASK_SET_N3_USD = 60.0e6        # full mask set at N3; other nodes scale from it


@dataclass(frozen=True)
class ProcessNode:
    name: str
    label: str

    # --- Physical scaling, relative to REFERENCE_NODE -------------------------
    logic_area: float
    sram_area: float
    energy: float
    fmax: float

    # --- Economics, absolute --------------------------------------------------
    wafer_cost_factor: float    # relative to COST_REFERENCE_NODE
    yield_factor: float         # good-die fraction for a block of this class
    mask_factor: float          # mask set cost relative to N3

    notes: str = ""
    # What a student sees. Node names are GENERATION labels and have not
    # described a physical dimension for many years, so anything below about
    # 3 nm carries "-class" to stop the number being read as a measurement.
    display: str = ""

    # --- User-facing naming ---------------------------------------------------
    #
    # The keys "N7", "A16" and the rest follow one foundry's naming. This
    # package models a generalized scaling trend and no foundry's process, so
    # borrowing a vendor's names both misdescribes what is here and sits
    # against the vendor-neutrality rule the architecture library already
    # enforces on itself.
    #
    # The user-facing name is the DIMENSION, which is an industry-wide
    # descriptor belonging to nobody: 7nm, 5nm, 1.6nm.
    #
    # Keys are unchanged in this step. Changing them touches saved files,
    # golden data and the revision log, and mixing that with a display change
    # would make a numeric regression and a storage migration fail together
    # with no way to tell which caused what.
    display_name: str = ""      # "7nm"
    node_nm: float = 0.0        # 7.0 - the sort key, never a string sort
    description: str = ""       # "Cost reference" - NOT folded into the name

    @property
    def user_name(self) -> str:
        """What every screen, chart and exported file must print."""
        return self.display_name or self.name

    @property
    def wafer_price_usd(self) -> float:
        return WAFER_PRICE_N4_USD * self.wafer_cost_factor

    @property
    def sort_key(self) -> float:
        """Largest node first. A STRING sort gives 1.6nm, 12nm, 16nm, 2nm."""
        return -self.node_nm

    @property
    def usd_per_mm2(self) -> float:
        """Cost of one mm2 of GOOD silicon: wafer price and yield together."""
        return self.wafer_price_usd / (USABLE_WAFER_MM2 * self.yield_factor)

    @property
    def mask_set_usd(self) -> float:
        return MASK_SET_N3_USD * self.mask_factor


NODE_LIBRARY: Dict[str, ProcessNode] = {
    "N28": ProcessNode(
        "N28", "28 nm", display_name="28nm", node_nm=28.0,
        description="Legacy embedded", logic_area=2.20, sram_area=2.00, energy=2.10, fmax=0.75,
        wafer_cost_factor=0.19, yield_factor=0.99, mask_factor=0.035,
        notes="Legacy embedded accelerators. Long product life, tiny NRE."),
    "N16": ProcessNode(
        "N16", "16 nm (scaling reference)", display_name="16nm",
        node_nm=16.0, description="Scaling reference", logic_area=1.00, sram_area=1.00,
        energy=1.00, fmax=1.00,
        wafer_cost_factor=0.28, yield_factor=0.96, mask_factor=0.09,
        notes="Where the block libraries are calibrated, and a common host-CPU "
              "node for cost-driven embedded systems."),
    "N12": ProcessNode(
        "N12", "12 nm", display_name="12nm", node_nm=12.0,
        description="Cost-optimised edge", logic_area=0.80, sram_area=0.85, energy=0.82, fmax=1.08,
        wafer_cost_factor=0.30, yield_factor=0.98, mask_factor=0.20,
        notes="Cost-optimised edge NPU. Industrial vision and value products."),
    "N7": ProcessNode(
        "N7", "7 nm", display_name="7nm", node_nm=7.0,
        description="Mainstream edge and automotive", logic_area=0.36, sram_area=0.47, energy=0.46, fmax=1.25,
        wafer_cost_factor=0.55, yield_factor=0.94, mask_factor=0.45,
        notes="Mainstream standalone edge NPU, and the node automotive SoCs sit "
              "on while mobile has moved ahead."),
    "N5": ProcessNode(
        "N5", "5 nm", display_name="5nm", node_nm=5.0,
        description="Premium edge and datacenter", logic_area=0.24, sram_area=0.38, energy=0.35, fmax=1.40,
        wafer_cost_factor=0.85, yield_factor=0.90, mask_factor=0.70,
        notes="Premium standalone edge NPU and the datacenter GPU class."),
    "N4": ProcessNode(
        "N4", "4 nm (cost reference)", display_name="4nm", node_nm=4.0,
        description="Wafer-price reference", logic_area=0.20, sram_area=0.35,
        energy=0.31, fmax=1.45,
        wafer_cost_factor=1.00, yield_factor=0.88, mask_factor=0.85,
        notes="The wafer-price reference. A refined 5 nm rather than a new node."),
    "N3": ProcessNode(
        "N3", "3 nm", display_name="3nm", node_nm=3.0,
        description="Leading-edge mobile", logic_area=0.16, sram_area=0.33, energy=0.28, fmax=1.50,
        wafer_cost_factor=1.30, yield_factor=0.82, mask_factor=1.00,
        notes="Leading-edge mobile SoC. SRAM scaling has essentially stopped, so "
              "an SRAM-heavy accelerator gains far less here than its logic "
              "count implies."),
    "N2": ProcessNode(
        "N2", "2 nm (GAA nanosheet)", display="2 nm-class",
        display_name="2nm", node_nm=2.0,
        description="First gate-all-around nanosheet node", logic_area=0.12, sram_area=0.30,
        energy=0.24, fmax=1.58,
        wafer_cost_factor=1.88, yield_factor=0.80, mask_factor=1.50,
        notes="The first gate-all-around nanosheet node rather than another "
              "FinFET shrink: the gate wraps the channel on all four sides "
              "instead of three, cutting leakage. In volume production since "
              "4Q25. Roughly 10-15% more performance at equal power, or 25-30% "
              "less power at equal performance, against N3E. Wafer price near "
              "USD 30k - the largest single-node jump in the table, and the "
              "clearest illustration that a shrink is no longer automatically "
              "a cost reduction."),
    "A16": ProcessNode(
        "A16", "1.6 nm (backside power rail)",
        display_name="1.6nm", node_nm=1.6,
        description="Backside power delivery",
        display="1.6 nm-class (representative)", logic_area=0.10, sram_area=0.29,
        energy=0.19, fmax=1.75,
        wafer_cost_factor=2.20, yield_factor=0.72, mask_factor=1.80,
        notes="The naming convention changes here: A is angstrom, so A16 means "
              "16 A = 1.6 nm. The substance is backside power delivery - the "
              "power rails move underneath the transistors, freeing the front "
              "side for signal routing and improving logic density beyond what "
              "the transistor alone gives. Roughly 10% more speed and 20% less "
              "power than N2P. Volume production targeted for 2H26, so the "
              "figures here are the least settled in this table. Note the SRAM "
              "column barely moves: a backside rail helps logic routing, not "
              "bitcells, so an SRAM-heavy accelerator gains almost nothing."),
}


# Named starting points rather than product names. Each is a plausible
# combination of host node, accelerator node and integration style.
PROFILES: Dict[str, Dict[str, str]] = {
    "leading_edge_soc": {
        "label": "Leading-edge mobile SoC, monolithic",
        "soc_node": "N3", "accel_node": "N3", "integration": "monolithic",
        "notes": "CPU, GPU and NPU share one die, so one node covers all three."},
    "premium_edge_npu": {
        "label": "Premium standalone edge NPU",
        "soc_node": "N7", "accel_node": "N5", "integration": "separate_die",
        "notes": "Accelerator ahead of its host: the NPU justifies the node, the "
                 "host does not."},
    "mainstream_edge_npu": {
        "label": "Mainstream standalone edge NPU",
        "soc_node": "N12", "accel_node": "N7", "integration": "separate_die",
        "notes": "The common price and power point for edge accelerators."},
    "cost_optimised_edge": {
        "label": "Cost-optimised edge NPU",
        "soc_node": "N16", "accel_node": "N12", "integration": "separate_die",
        "notes": "Industrial vision and value products."},
    "automotive_soc": {
        "label": "Automotive ADAS SoC, monolithic",
        "soc_node": "N7", "accel_node": "N7", "integration": "monolithic",
        "notes": "A node behind mobile: qualification and temperature range "
                 "matter more than density."},
    "datacenter": {
        "label": "Datacenter accelerator",
        "soc_node": "N5", "accel_node": "N5", "integration": "separate_die",
        "notes": "Host and accelerator are separate packages entirely."},
}


def get_node(name: str) -> ProcessNode:
    if name not in NODE_LIBRARY:
        raise KeyError(f"Unknown process node '{name}'. "
                       f"Available: {', '.join(NODE_LIBRARY)}")
    return NODE_LIBRARY[name]


def print_node_table() -> None:
    print("=" * 82)
    print(" PROCESS NODES")
    print("=" * 82)
    print(f"  Physical scaling relative to {REFERENCE_NODE}; "
          f"wafer cost relative to {COST_REFERENCE_NODE}")
    head = (f"\n  {'node':<6s}{'logic':>7s}{'SRAM':>7s}{'energy':>8s}{'Fmax':>7s}"
            f"{'wafer x':>9s}{'yield':>7s}{'$/mm2':>8s}{'mask $M':>9s}")
    print(head); print("  " + "-" * (len(head) - 3))
    for n in NODE_LIBRARY.values():
        print(f"  {n.name:<6s}{n.logic_area:>7.2f}{n.sram_area:>7.2f}{n.energy:>8.2f}"
              f"{n.fmax:>7.2f}{n.wafer_cost_factor:>9.2f}{n.yield_factor:>7.2f}"
              f"{n.usd_per_mm2:>8.3f}{n.mask_set_usd / 1e6:>9.1f}")

    print("\n  Why a shrink is not automatically cheaper:")
    print("    the die gets smaller, but each good mm2 costs more and yield falls")
    for a, b in (("N7", "N5"), ("N5", "N4"), ("N4", "N3"), ("N3", "N2"),
                 ("N2", "A16")):
        x, y = NODE_LIBRARY[a], NODE_LIBRARY[b]
        print(f"    {a} -> {b}: logic area {y.logic_area / x.logic_area:.2f}x, "
              f"cost per good mm2 {y.usd_per_mm2 / x.usd_per_mm2:.2f}x")

    print("\n  SRAM scaling lags logic - the gap that decides an NPU shrink:")
    for n in NODE_LIBRARY.values():
        if n.name == REFERENCE_NODE:
            continue
        print(f"    {n.name:<5s} SRAM shrinks {n.sram_area / n.logic_area:.2f}x "
              f"as much as logic")


def print_profiles() -> None:
    print("=" * 82)
    print(" NODE PROFILES")
    print("=" * 82)
    for key, p in PROFILES.items():
        integ = "one die" if p["integration"] == "monolithic" else "separate dies"
        print(f"  {key:<22s}{p['label']}")
        print(f"  {'':<22s}host {p['soc_node']}, accelerator {p['accel_node']} "
              f"({integ})")
        print(f"  {'':<22s}{p['notes']}\n")


def node_name(key: Optional[str]) -> str:
    """The user-facing name of a process node, from its internal key.

    ONE function, because eight screens printed the key directly and each
    would have had to be found again the next time the naming changed. A
    key that is not in the library is returned unchanged rather than
    hidden - a missing entry is a defect, and printing nothing would make
    it look like a design with no node.
    """
    if not key:
        return "not specified"
    spec = NODE_LIBRARY.get(key)
    return spec.user_name if spec else key


def node_description(key: Optional[str]) -> str:
    """The one-line note, kept OUT of the name.

    "7nm (cost reference)" reads as though the parenthesis were part of the
    node's name. It is a remark about why the node is in the table.
    """
    spec = NODE_LIBRARY.get(key or "")
    return spec.description if spec else ""


def nodes_in_order() -> List[str]:
    """Largest node first, by DIMENSION - never by string."""
    return [k for k, _ in sorted(NODE_LIBRARY.items(),
                                 key=lambda kv: kv[1].sort_key)]
