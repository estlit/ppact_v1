"""
ppact.memory - DRAM library and component-level PPACT

Every entry is described at the PACKAGE level, the unit a system designer
actually places on a board. Add a technology by adding one MemorySpec to
MEMORY_LIBRARY; no branching code needs editing.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List

import numpy as np

from .core import Anchor


# Cost index reference: one LPDDR5 package = 100. A comparison survives being
# wrong about absolute prices; a dollar figure quoted with false precision does
# not, and a student will read $112 as a price rather than as an estimate.
COST_INDEX_BASE = 8.93

COOLING_RANK = {"passive": 0, "airflow": 1, "active": 2}


@dataclass(frozen=True)
class MemorySpec:
    """One DRAM technology, described at the PACKAGE level.

    A package is the unit a system designer actually places on a board, so it
    is the only basis on which bandwidth, area and cost can be compared fairly.
    """

    name: str
    category: str

    # --- Interface -----------------------------------------------------------
    package_io_width_bits: int     # total data pins presented by the package
    pin_speed_gbps: float          # per-pin data rate
    dies_per_package: int          # PHYSICAL core dies fabricated (drives cost + capacity)
    die_density_gbit: int          # per-die density

    # --- Electrical ----------------------------------------------------------
    energy_pj_per_bit: float       # I/O + core energy, peak traffic
    vddq_volt: float
    io_standard: str
    error_handling: str

    # --- Physical ------------------------------------------------------------
    die_area_mm2: float
    board_area_mm2: float          # package footprint + keep-out + thermal area
    package_footprint_mm2: float   # package BODY only - the surface heat leaves through
    packaging: str
    cooling_class: str

    # --- Manufacturing -------------------------------------------------------
    wafer_price_usd: float
    defect_density_per_cm2: float
    redundancy_repair_rate: float  # fraction of defective dies rescued by spare rows/cols
    stack_assembly_yield: float    # probability a finished package survives assembly


    # --- System context ------------------------------------------------------
    typical_system_devices: int    # packages a real product places around the SoC

    notes: str = ""

    # Peak bandwidth is a pin-rate calculation and no controller ever delivers
    # it. Refresh, bank conflicts, read/write turnaround and row activation all
    # take their share, and the shortfall is large enough - a quarter or more -
    # that using peak numbers silently makes every design look compute-bound.
    # Wide, many-banked stacks hide the overhead better than a narrow bus does,
    # which is why the three differ.
    bandwidth_efficiency: float = 0.75

    # Packaging cost, split rather than lumped. HBM's price is not mostly its
    # DRAM: it is the interposer, the advanced package and the test flow around
    # a known-good-die stack. A single number hid that, and hiding it makes HBM
    # look like expensive memory rather than what it is - ordinary memory in a
    # very expensive package.
    # What the package needs to be cooled by. Judging an HBM stack against a
    # passively cooled phone gave a memory thermal margin of -398%, which is
    # arithmetically correct and says nothing: the same stack has +30% margin
    # under a datacenter cooling class. The useful statement is not a large
    # negative number but a compatibility one - this memory needs cooling this
    # product does not have.
    # Power drawn whatever the traffic: refresh across every die, the PHY, and
    # I/O termination. Modelling only pJ/bit made HBM look CHEAPER to run than
    # LPDDR5 - 3.9 pJ/bit against 5.0 - and produced a system power that FELL
    # when a drone swapped LPDDR for HBM. Per bit moved HBM is more efficient;
    # per second sitting there it is not, and a design that is not moving many
    # bits pays the second figure.
    background_power_w: float = 0.0         # per package, traffic-independent

    cooling_requirement: str = "passive"    # passive | airflow | active
    # The component ceiling, kept separate from the rate products actually run.
    # HBM3E is specified to 9.6 Gbps, and an H200 runs its stacks at about
    # 6.25 - shipping designs back off for power and thermal reasons. Using the
    # ceiling as if it were the operating point overstated HBM bandwidth by 54%
    # against a published product, which biases every HBM comparison the wrong
    # way in a tool meant to show that HBM is not always the answer.
    peak_pin_speed_gbps: float = 0.0        # 0 means the same as pin_speed
    # Confidence in the cost figures below. HBM wafer prices and die areas are
    # contract-dependent and not publicly verifiable, so they are estimates and
    # are labelled as such rather than quoted as if measured.
    cost_confidence: str = "MEDIUM"         # HIGH | MEDIUM | LOW

    interposer_cost_usd: float = 0.0        # silicon interposer or bridge
    advanced_package_cost_usd: float = 0.0  # substrate, TSV, redistribution
    assembly_test_cost_usd: float = 0.0     # stacking, KGD test, burn-in


    # --- Derived -------------------------------------------------------------
    @property
    def package_io_width(self) -> int:
        return self.package_io_width_bits

    @property
    def package_cost_usd(self) -> float:
        return (self.interposer_cost_usd + self.advanced_package_cost_usd
                + self.assembly_test_cost_usd)

    @property
    def bandwidth_gbytes_s(self) -> float:
        """Package PEAK bandwidth in GB/s - the pin-rate figure."""
        return self.package_io_width * self.pin_speed_gbps / 8.0

    @property
    def effective_bandwidth_gbytes_s(self) -> float:
        """What a controller actually delivers."""
        return self.bandwidth_gbytes_s * self.bandwidth_efficiency

    @property
    def capacity_gbyte(self) -> float:
        return self.die_density_gbit * self.dies_per_package / 8.0

    @property
    def bus_config(self) -> str:
        return (f"{self.package_io_width}-bit x {self.pin_speed_gbps:.1f} Gbps "
                f"({self.dies_per_package} core die)")


MEMORY_LIBRARY: Dict[str, MemorySpec] = {

    "LPDDR5": MemorySpec(
        name="LPDDR5",
        background_power_w=0.15,
        cooling_requirement="passive",
        cost_confidence="MEDIUM",
        bandwidth_efficiency=0.72,   # narrow bus, refresh and turnaround are a large share
        category="Low Power / Mobile-Edge",
        package_io_width_bits=64,     # 2 dies x 32-bit (2 ch x 16-bit each)
        pin_speed_gbps=6.4,
        dies_per_package=2,
        die_density_gbit=16,
        energy_pj_per_bit=5.0,
        vddq_volt=0.5,
        io_standard="LVSTL (low-swing)",
        error_handling="On-die ECC + Link ECC",
        die_area_mm2=60.0,
        board_area_mm2=90.0,          # PoP: stacked on the AP, shares its footprint
        package_footprint_mm2=225.0,  # ~15 x 15 mm package body
        packaging="PoP / adjacent placement, stackable",
        cooling_class="Passive (chassis spreading)",
        wafer_price_usd=3500.0,
        defect_density_per_cm2=0.08,
        redundancy_repair_rate=0.55,
        stack_assembly_yield=0.98,     # 2-die stack: low risk
        interposer_cost_usd=0.0,          # none: wires on the board
        advanced_package_cost_usd=0.9,    # ordinary PoP substrate
        assembly_test_cost_usd=1.3,       # 2-die stack assembly and test
        typical_system_devices=2,
        notes="Short traces enable 0.5 V swing; power and area win, bandwidth capped.",
    ),

    # ------------------------------------------------------------------
    # ARCHITECTURAL CLASSES, not products
    # ------------------------------------------------------------------
    #
    # Two gaps found by measuring the library against published automotive
    # specifications: LPDDR5X, which every current automotive AI part uses,
    # and DDR5, which every host beside one uses. Both were absent, so a
    # design built here had to pretend to be a generation behind.
    #
    # Parameters are ENGINEERING ESTIMATES scaled from the entries around
    # them. The interface rates are the published JEDEC class rates - those
    # are standards, not vendor claims - and everything else is estimated.

    "LPDDR4": MemorySpec(
        name="LPDDR4", category="Low Power / Mobile-Edge",
        package_io_width_bits=64, pin_speed_gbps=3.2,
        dies_per_package=2, die_density_gbit=8,
        energy_pj_per_bit=7.0, vddq_volt=1.1,
        io_standard="LVSTL (low-swing)",
        error_handling="None on die",
        die_area_mm2=52.0, board_area_mm2=90.0,
        package_footprint_mm2=225.0,
        packaging="PoP / adjacent placement, stackable",
        cooling_class="Passive (chassis spreading)",
        wafer_price_usd=2700.0, defect_density_per_cm2=0.08,
        redundancy_repair_rate=0.55, stack_assembly_yield=0.98,
        typical_system_devices=2, bandwidth_efficiency=0.68,
        background_power_w=0.20, cooling_requirement="passive",
        cost_confidence="LOW",
        advanced_package_cost_usd=0.7, assembly_test_cost_usd=1.1,
        notes="ESTIMATED architectural class. Still specified alongside "
              "LPDDR4X on published on-device SoCs, where the choice is "
              "about what a customer can source rather than about speed."),

    "DDR4": MemorySpec(
        name="DDR4", category="Mainstream / Host",
        package_io_width_bits=64, pin_speed_gbps=3.2,
        dies_per_package=1, die_density_gbit=8,
        energy_pj_per_bit=8.0, vddq_volt=1.2,
        io_standard="POD (pseudo-open-drain)",
        error_handling="None on die",
        die_area_mm2=60.0, board_area_mm2=130.0,
        package_footprint_mm2=280.0,
        packaging="DIMM or soldered-down",
        cooling_class="Passive (chassis spreading)",
        wafer_price_usd=2600.0, defect_density_per_cm2=0.08,
        redundancy_repair_rate=0.55, stack_assembly_yield=0.99,
        typical_system_devices=2, bandwidth_efficiency=0.68,
        background_power_w=0.40, cooling_requirement="passive",
        cost_confidence="LOW",
        advanced_package_cost_usd=0.3, assembly_test_cost_usd=0.9,
        notes="ESTIMATED architectural class. The host memory an industrial "
              "PC still ships with, and the reason a design can be cheap "
              "and slow at the same time."),

    "LPDDR4X": MemorySpec(
        name="LPDDR4X", category="Low Power / Mobile-Edge",
        package_io_width_bits=64, pin_speed_gbps=4.267,
        dies_per_package=2, die_density_gbit=16,
        energy_pj_per_bit=6.0, vddq_volt=0.6,
        io_standard="LVSTL (low-swing)",
        error_handling="On-die ECC",
        die_area_mm2=58.0, board_area_mm2=90.0,
        package_footprint_mm2=225.0,
        packaging="PoP / adjacent placement, stackable",
        cooling_class="Passive (chassis spreading)",
        wafer_price_usd=3000.0, defect_density_per_cm2=0.08,
        redundancy_repair_rate=0.55, stack_assembly_yield=0.98,
        typical_system_devices=2, bandwidth_efficiency=0.70,
        background_power_w=0.18, cooling_requirement="passive",
        cost_confidence="LOW",
        advanced_package_cost_usd=0.8, assembly_test_cost_usd=1.2,
        notes="ESTIMATED architectural class. The generation still shipping "
              "on inference cards that need capacity and a low bill of "
              "materials rather than bandwidth. The 4267 MT/s rate is the "
              "JEDEC class rate; everything else is an estimate."),

    "LPDDR5X": MemorySpec(
        name="LPDDR5X", category="Low Power / Mobile-Edge",
        package_io_width_bits=64, pin_speed_gbps=8.533,
        dies_per_package=2, die_density_gbit=16,
        energy_pj_per_bit=4.4, vddq_volt=0.5,
        io_standard="LVSTL (low-swing)",
        error_handling="On-die ECC + Link ECC",
        die_area_mm2=62.0, board_area_mm2=90.0,
        package_footprint_mm2=225.0,
        packaging="PoP / adjacent placement, stackable",
        cooling_class="Passive (chassis spreading)",
        wafer_price_usd=3700.0, defect_density_per_cm2=0.08,
        redundancy_repair_rate=0.55, stack_assembly_yield=0.98,
        typical_system_devices=2, bandwidth_efficiency=0.72,
        background_power_w=0.16, cooling_requirement="passive",
        cost_confidence="LOW",
        advanced_package_cost_usd=1.0, assembly_test_cost_usd=1.4,
        notes="ESTIMATED architectural class. The 8533 MT/s rate is the "
              "JEDEC class rate; the energy, area and price are estimates "
              "scaled from LPDDR5 and are not published by anyone."),

    "DDR5": MemorySpec(
        name="DDR5", category="Mainstream / Host",
        package_io_width_bits=64, pin_speed_gbps=4.8,
        dies_per_package=1, die_density_gbit=16,
        energy_pj_per_bit=6.2, vddq_volt=1.1,
        io_standard="POD (pseudo-open-drain)",
        error_handling="On-die ECC",
        die_area_mm2=70.0, board_area_mm2=130.0,
        package_footprint_mm2=280.0,
        packaging="DIMM or soldered-down",
        cooling_class="Passive (chassis spreading)",
        wafer_price_usd=3200.0, defect_density_per_cm2=0.08,
        redundancy_repair_rate=0.55, stack_assembly_yield=0.99,
        typical_system_devices=2, bandwidth_efficiency=0.70,
        background_power_w=0.35, cooling_requirement="passive",
        cost_confidence="LOW",
        advanced_package_cost_usd=0.4, assembly_test_cost_usd=1.0,
        notes="ESTIMATED architectural class. What a host processor uses "
              "when it is not a mobile part. Higher voltage than LPDDR and "
              "correspondingly more energy per bit, which is the reason a "
              "battery product does not use it."),

    "GDDR6": MemorySpec(
        name="GDDR6",
        background_power_w=0.85,
        cooling_requirement="airflow",
        cost_confidence="MEDIUM",
        bandwidth_efficiency=0.8,   # more banks and a graphics-tuned controller
        category="High Bandwidth / Graphics-Accelerator",
        package_io_width_bits=32,
        pin_speed_gbps=16.0,
        dies_per_package=1,
        die_density_gbit=16,
        energy_pj_per_bit=8.0,
        vddq_volt=1.35,
        io_standard="POD135 (high-margin)",
        error_handling="CRC-based EDC (retransmit)",
        die_area_mm2=70.0,
        board_area_mm2=420.0,         # BGA + thermal keep-out on the GPU board
        package_footprint_mm2=168.0,  # ~14 x 12 mm package body
        packaging="Discrete BGA, heat sink required",
        cooling_class="Heat sink plus board airflow",
        wafer_price_usd=3500.0,
        defect_density_per_cm2=0.08,
        redundancy_repair_rate=0.55,
        stack_assembly_yield=0.995,    # single die, standard BGA
        interposer_cost_usd=0.0,          # none: routed on the PCB, which is why
                                          # its BOARD area is the largest here
        advanced_package_cost_usd=0.7,
        assembly_test_cost_usd=0.5,
        typical_system_devices=8,     # 256-bit class GPU
        notes="Buys bandwidth with pin speed; pays in voltage, heat and board area.",
    ),

    "HBM2E": MemorySpec(
        name="HBM2E", category="High Bandwidth",
        package_io_width_bits=1024, pin_speed_gbps=3.2,
        dies_per_package=8, die_density_gbit=16,
        energy_pj_per_bit=4.6, vddq_volt=0.4,
        io_standard="Wide parallel over an interposer",
        error_handling="On-die ECC",
        die_area_mm2=92.0, board_area_mm2=140.0,
        package_footprint_mm2=110.0,
        packaging="2.5D on a silicon interposer",
        cooling_class="Active (directed airflow or cold plate)",
        wafer_price_usd=3200.0, defect_density_per_cm2=0.08,
        redundancy_repair_rate=0.55, stack_assembly_yield=0.86,
        typical_system_devices=4, bandwidth_efficiency=0.85,
        background_power_w=4.0, cooling_requirement="active",
        cost_confidence="LOW",
        interposer_cost_usd=15.0, advanced_package_cost_usd=12.0,
        assembly_test_cost_usd=10.0,
        notes="ESTIMATED architectural class. The generation an accelerator "
              "uses when it needs the bandwidth of a stack and not the "
              "newest one - still shipping, and cheaper than HBM3."),

    "HBM3": MemorySpec(
        name="HBM3", category="High Bandwidth",
        package_io_width_bits=1024, pin_speed_gbps=5.2,
        dies_per_package=8, die_density_gbit=16,
        energy_pj_per_bit=4.1, vddq_volt=0.4,
        io_standard="Wide parallel over an interposer",
        error_handling="On-die ECC",
        die_area_mm2=100.0, board_area_mm2=140.0,
        package_footprint_mm2=116.0,
        packaging="2.5D on a silicon interposer",
        cooling_class="Active (directed airflow or cold plate)",
        wafer_price_usd=3400.0, defect_density_per_cm2=0.08,
        redundancy_repair_rate=0.55, stack_assembly_yield=0.85,
        typical_system_devices=6, bandwidth_efficiency=0.85,
        background_power_w=4.6, cooling_requirement="active",
        cost_confidence="LOW",
        interposer_cost_usd=17.0, advanced_package_cost_usd=14.0,
        assembly_test_cost_usd=11.0,
        notes="ESTIMATED architectural class. Between HBM2E and HBM3E, "
              "which is where a great deal of installed silicon sits."),

    "HBM3E": MemorySpec(
        name="HBM3E 24GB",
        background_power_w=5.0,
        peak_pin_speed_gbps=9.6,            # component specification
        cooling_requirement="active",
        cost_confidence="LOW",
        bandwidth_efficiency=0.85,   # 16 independent channels absorb conflicts well
        category="Ultra Bandwidth / AI-HPC",
        package_io_width_bits=1024,   # the whole stack presents 1024 bits
        pin_speed_gbps=6.4,   # deployed operating point, not the 9.6 ceiling
        dies_per_package=8,           # 8-high stack: 8 core dies to pay for
        die_density_gbit=24,
        energy_pj_per_bit=3.9,
        vddq_volt=0.4,
        io_standard="Wide parallel over silicon interposer",
        error_handling="On-die ECC + link protection",
        die_area_mm2=110.0,           # per core die
        board_area_mm2=140.0,
        package_footprint_mm2=121.0,  # ~11 x 11 mm stack
        packaging="TSV stack on 2.5D interposer (CoWoS class)",
        cooling_class="Accelerator cold plate; bottom die is the hot spot",
        wafer_price_usd=3500.0,
        defect_density_per_cm2=0.08,
        redundancy_repair_rate=0.55,
        stack_assembly_yield=0.85,     # 8-high TSV stack: one failure scraps every die in it
        interposer_cost_usd=18.0,         # share of the silicon interposer
        advanced_package_cost_usd=15.0,   # base die, TSV, redistribution
        assembly_test_cost_usd=12.0,      # stacking and known-good-die test
        typical_system_devices=6,
        notes="Approximate. Stack cost model is simplified; ASP is far above cost.",
    ),

    "HBM3E_36": MemorySpec(
        name="HBM3E 36GB",
        background_power_w=6.5,
        peak_pin_speed_gbps=9.6,
        cooling_requirement="active",
        cost_confidence="LOW",
        bandwidth_efficiency=0.85,   # 16 independent channels absorb conflicts well
        category="Ultra Bandwidth / AI-HPC",
        package_io_width_bits=1024,   # the whole stack presents 1024 bits
        pin_speed_gbps=6.4,   # deployed operating point, not the 9.6 ceiling
        dies_per_package=12,           # 8-high stack: 8 core dies to pay for
        die_density_gbit=24,
        energy_pj_per_bit=3.9,
        vddq_volt=0.4,
        io_standard="Wide parallel over silicon interposer",
        error_handling="On-die ECC + link protection",
        die_area_mm2=110.0,           # per core die
        board_area_mm2=140.0,
        package_footprint_mm2=121.0,  # ~11 x 11 mm stack
        packaging="TSV stack on 2.5D interposer (CoWoS class)",
        cooling_class="Accelerator cold plate; bottom die is the hot spot",
        wafer_price_usd=3500.0,
        defect_density_per_cm2=0.08,
        redundancy_repair_rate=0.55,
        stack_assembly_yield=0.78,     # 8-high TSV stack: one failure scraps every die in it
        interposer_cost_usd=18.0,         # share of the silicon interposer
        advanced_package_cost_usd=15.0,   # base die, TSV, redistribution
        assembly_test_cost_usd=17.0,      # stacking and known-good-die test
        typical_system_devices=6,
        notes="Approximate. Stack cost model is simplified; ASP is far above cost.",
    ),

    "HBM4_36": MemorySpec(
        name="HBM4 36GB",
        background_power_w=6.0,
        cooling_requirement="active",
        cost_confidence="LOW",
        peak_pin_speed_gbps=11.0,     # Micron cites >11 Gbps, >2.8 TB/s per stack
        category="Ultra Bandwidth / AI-HPC",
        package_io_width_bits=2048,   # doubled, across 32 channels
        # The generation's own lesson: HBM4 widens the pipe rather than raising
        # the clock. SK hynix demonstrated 1.6 TB/s per stack at a pin rate no
        # higher than HBM3E deploys at - which is where the power saving comes
        # from. Using the 11 Gbps ceiling as an operating point would repeat
        # exactly the error corrected at 3.17.0.
        pin_speed_gbps=6.4,
        dies_per_package=12,
        die_density_gbit=24,
        energy_pj_per_bit=2.6,        # 30-40% better per bit, vendor claim
        vddq_volt=0.8,                # 0.7-0.9 V, vendor-selectable
        io_standard="2048-bit over silicon interposer, 32 channels",
        error_handling="On-die ECC + link protection",
        die_area_mm2=115.0,
        board_area_mm2=140.0,
        package_footprint_mm2=126.0,
        packaging="TSV stack with logic base die on a foundry node",
        cooling_class="Accelerator cold plate; logic base die adds to the load",
        wafer_price_usd=3500.0,
        defect_density_per_cm2=0.08,
        redundancy_repair_rate=0.55,
        stack_assembly_yield=0.75,
        interposer_cost_usd=26.0,     # 2048 bits needs far more routing
        advanced_package_cost_usd=24.0,   # logic base die on a foundry process
        assembly_test_cost_usd=18.0,
        typical_system_devices=8,
        notes="Estimated. Not controller-compatible with HBM3E: the doubled "
              "interface needs new PHY IP. Cost and power are estimates.",
        bandwidth_efficiency=0.88),   # 32 channels absorb conflicts better

    "HBM4_48": MemorySpec(
        name="HBM4 48GB",
        background_power_w=7.5,
        cooling_requirement="active",
        cost_confidence="LOW",
        peak_pin_speed_gbps=11.0,
        category="Ultra Bandwidth / AI-HPC",
        package_io_width_bits=2048,
        pin_speed_gbps=6.4,
        dies_per_package=16,          # 16-high, demonstrated at CES 2026
        die_density_gbit=24,
        energy_pj_per_bit=2.6,
        vddq_volt=0.8,
        io_standard="2048-bit over silicon interposer, 32 channels",
        error_handling="On-die ECC + link protection",
        die_area_mm2=115.0,
        board_area_mm2=140.0,
        package_footprint_mm2=126.0,
        packaging="16-high TSV stack with logic base die",
        cooling_class="Accelerator cold plate; 16 layers in the same height",
        wafer_price_usd=3500.0,
        defect_density_per_cm2=0.08,
        redundancy_repair_rate=0.55,
        stack_assembly_yield=0.68,    # sixteen layers stack worse than twelve
        interposer_cost_usd=26.0,
        advanced_package_cost_usd=24.0,
        assembly_test_cost_usd=24.0,
        typical_system_devices=8,
        notes="Estimated. Capacity comes from stack height, not from the "
              "interface - same bandwidth as the 12-high part.",
        bandwidth_efficiency=0.88)

}


# ==============================================================================
ANCHORS: Dict[str, Anchor] = {
    "Performance (BW)": Anchor(
        "Package bandwidth", "GB/s", at_zero=10.0, at_hundred=2000.0, log_scale=True,
        rationale="Log scale: DRAM bandwidth spans 25 GB/s to 2 TB/s. "
                  "A linear axis would flatten LPDDR5 and GDDR6 into the origin "
                  "once HBM is on the same chart.",
    ),
    "Power Efficiency": Anchor(
        "Energy per bit", "pJ/bit", at_zero=9.0, at_hundred=3.0,
        rationale="3 pJ/bit is the practical floor for stacked DRAM today; "
                  "9 pJ/bit is high-swing GDDR territory. Lower is better.",
    ),
    "Area Efficiency": Anchor(
        "Board area per bandwidth", "mm2 per GB/s", at_zero=20.0, at_hundred=0.1, log_scale=True,
        rationale="Board area, not die area. Die area is already priced into "
                  "Cost; what a system designer runs out of is board real estate. "
                  "The 20 mm2 per GB/s floor is a discrete package with a thermal "
                  "solution; a DDR5 DIMM sits near 107, so this is not the worst "
                  "case, only the worst case worth plotting.",
    ),
    "Cost Advantage": Anchor(
        "Manufacturing cost per package", "USD", at_zero=200.0, at_hundred=2.0, log_scale=True,
        rationale="ABSOLUTE cost, not cost per GB/s. A BOM has a hard ceiling: a "
                  "part that cannot be afforded is not a candidate however good "
                  "its cost per unit bandwidth is. The normalized figures "
                  "(USD/GB/s, USD/GB) stay in the report for value comparison.",
    ),
    "Thermal Headroom": Anchor(
        "Power density over package footprint", "W per mm2", at_zero=1.0, at_hundred=0.005, log_scale=True,
        rationale="Watts divided by the PACKAGE BODY area, not the board area. "
                  "Dividing by board area would credit GDDR6 for the very "
                  "keep-out space its heat sink forces it to reserve, which is "
                  "circular. 1 W/mm2 is beyond what air or cold plates handle "
                  "today; a high-end GPU die runs near 0.35.",
    ),
}

AXIS_ORDER: List[str] = list(ANCHORS.keys())


# ==============================================================================
@dataclass(frozen=True)
class WaferResult:
    gross_dpw: int
    poisson_yield: float
    effective_yield: float
    net_dpw: int
    die_cost_usd: float


def evaluate_wafer(spec: MemorySpec, wafer_diameter_mm: float = 300.0) -> WaferResult:
    """Dies per wafer, yield, and cost of one known-good die.

    Yield combines the Poisson defect model with DRAM redundancy repair. This
    second term is the reason DRAM yields sit far above logic yields at the
    same defect density: spare rows and columns rescue a large share of dies
    that a logic process would have to scrap.
    """
    if spec.die_area_mm2 <= 0:
        raise ValueError(f"{spec.name}: die area must be positive.")

    r = wafer_diameter_mm / 2.0
    gross = (math.pi * r ** 2 / spec.die_area_mm2) - (math.pi * 2 * r / math.sqrt(2 * spec.die_area_mm2))
    gross_dpw = max(1, math.floor(gross))

    area_cm2 = spec.die_area_mm2 / 100.0
    poisson = math.exp(-spec.defect_density_per_cm2 * area_cm2)
    effective = poisson + (1.0 - poisson) * spec.redundancy_repair_rate

    net_dpw = max(1, math.floor(gross_dpw * effective))
    return WaferResult(gross_dpw, poisson, effective, net_dpw, spec.wafer_price_usd / net_dpw)


# ==============================================================================
# 4. PPACT EVALUATION
# ==============================================================================

@dataclass
class PPACTResult:
    spec: MemorySpec
    wafer: WaferResult
    metrics: Dict[str, float] = field(default_factory=dict)
    scores: Dict[str, float] = field(default_factory=dict)

    @property
    def score_vector(self) -> List[float]:
        return [self.scores[a] for a in AXIS_ORDER]


def evaluate(spec: MemorySpec) -> PPACTResult:
    wafer = evaluate_wafer(spec)

    bw = spec.bandwidth_gbytes_s
    # Peak power: GB/s -> bit/s -> pJ/s -> W
    peak_power_w = (bw * 1e9 * 8 * spec.energy_pj_per_bit) / 1e12

    silicon_cost = wafer.die_cost_usd * spec.dies_per_package

    # Assembly yield must be applied to the WHOLE package, not to each die.
    # A stack that fails during bonding scraps every die inside it plus the
    # substrate, so the surviving packages carry that loss. Omitting this term
    # makes a tall TSV stack look as cheap per GB/s as a single-die BGA, which
    # inverts the real cost ranking.
    package_cost = (silicon_cost + spec.package_cost_usd) / spec.stack_assembly_yield

    area_per_bw = spec.board_area_mm2 / bw
    cost_per_bw = package_cost / bw
    cost_per_gb = package_cost / spec.capacity_gbyte
    system_bw = bw * spec.typical_system_devices

    # Heat has to leave through the package body. Board area is deliberately
    # not used here: it already contains the thermal keep-out that exists
    # BECAUSE the part runs hot, so dividing by it would reward the problem.
    power_density = peak_power_w / spec.package_footprint_mm2

    metrics = {
        "Package peak bandwidth (GB/s)": bw,
        "Package effective bandwidth (GB/s)": spec.effective_bandwidth_gbytes_s,
        "Bandwidth efficiency (%)": spec.bandwidth_efficiency * 100.0,
        "Package bandwidth (GB/s)": bw,
        "System bandwidth (GB/s)": system_bw,
        "Package capacity (GB)": spec.capacity_gbyte,
        "Peak power (W)": peak_power_w,
        "Energy (pJ/bit)": spec.energy_pj_per_bit,
        "Board area (mm2)": spec.board_area_mm2,
        "Board area per BW (mm2 per GB/s)": area_per_bw,
        "Silicon cost (USD)": silicon_cost,
        "Assembly yield (%)": spec.stack_assembly_yield * 100.0,
        "Package cost (USD)": package_cost,
        "  memory silicon (USD)": silicon_cost,
        "  interposer (USD)": spec.interposer_cost_usd,
        "  advanced package (USD)": spec.advanced_package_cost_usd,
        "  assembly and test (USD)": spec.assembly_test_cost_usd,
        "Cost index": package_cost / COST_INDEX_BASE * 100.0,
        "  packaging share (%)": (spec.package_cost_usd
                                  / max(silicon_cost + spec.package_cost_usd, 1e-9)
                                  * 100.0),
        "Cost per BW (USD per GB/s)": cost_per_bw,
        "Cost per capacity (USD per GB)": cost_per_gb,
        "Package footprint (mm2)": spec.package_footprint_mm2,
        "Power density (W per mm2)": power_density,
    }

    scores = {
        "Performance (BW)": ANCHORS["Performance (BW)"].score(bw),
        "Power Efficiency": ANCHORS["Power Efficiency"].score(spec.energy_pj_per_bit),
        "Area Efficiency": ANCHORS["Area Efficiency"].score(area_per_bw),
        "Cost Advantage": ANCHORS["Cost Advantage"].score(package_cost),
        "Thermal Headroom": ANCHORS["Thermal Headroom"].score(power_density),
    }

    return PPACTResult(spec=spec, wafer=wafer, metrics=metrics, scores=scores)


# ==============================================================================
