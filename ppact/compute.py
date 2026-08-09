"""
ppact.compute - accelerator library

Systolic NPUs described by array size, plus non-array engines given a peak
rate directly. sram_kb matters as much as the array: it sets how often
activations spill to DRAM.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from .process import ProcessNode, get_node, REFERENCE_NODE


# Technology constants for the area model. Roughly a 12-16 nm class process.
# These are strong functions of the node, so they are named rather than buried:
# a student who changes MAC_AREA_UM2 is making a process assumption explicit.
#
# A systolic array is essentially MAC cells plus SRAM, and that is the point of
# the architecture. Data moves neighbour to neighbour through pipeline registers
# inside the PE, so there is no network-on-chip, no crossbar and no per-PE
# instruction decode - the whole array runs off one shared sequencer. What
# remains outside the array is small and fixed in character: DMA to DRAM,
# address generation, the accumulator and requantisation path, and clocking.
# Hence a modest periphery factor rather than the 1.5-1.7x that a shader array
# or a VLIW DSP would need.
# All three are quoted AT THE REFERENCE NODE (see ppact.process). A system
# built on another node derates them rather than redefining them.
MAC_AREA_UM2 = 700.0          # INT8 MAC with weight register, accumulator, pipeline regs
SRAM_MM2_PER_MB = 1.4         # 6T array plus decoders, sense amps, ECC and redundancy
SYSTOLIC_PERIPHERY = 1.15     # DMA, address generation, requant/activation, clocking


# One buffer means the array waits for the next tile; three means a transfer is
# almost always already in flight. Tiling quality is the compiler's half of the
# same problem: buffers only help if the schedule keeps them full.
BUFFERING_FACTOR = {"single": 0.20, "double": 0.75, "triple": 0.90}
TILING_FACTOR = {"poor": 0.60, "normal": 0.85, "optimised": 1.00}


@dataclass(frozen=True)
class ComputeSpec:
    name: str
    category: str
    mac_array: int                  # NxN systolic array; 0 for non-array engines
    peak_mac_per_s_override: float  # used when mac_array is 0
    clock_ghz: float
    utilization: float              # realistic fraction of peak MACs retired
    energy_pj_per_mac: float
    sram_kb: float                  # on-chip buffer; larger means less DRAM traffic

    # How well the architecture converts that buffer into reuse. Buffer size
    # alone does not decide DRAM traffic: a systolic array with a weight- or
    # row-stationary schedule keeps operands resident and walks them past the
    # PEs many times, while a shader array reloads through a cache hierarchy it
    # does not control and a SIMD CPU spills constantly. Without this term two
    # engines with the same SRAM produce identical traffic, which is exactly
    # the difference between a GPU and an NPU that matters most.
    dataflow_efficiency: float = 0.90
    dataflow: str = "weight-stationary systolic"

    # --- Accuracy cost of deploying on this engine ---------------------------
    #
    # Accuracy is a property of the model, not of the silicon. What the silicon
    # decides is how much of the trained model's accuracy survives deployment:
    # the arithmetic it can represent, whether every operator in the graph has
    # a native implementation, and what the toolchain substitutes when it does
    # not. Writing "GPU accuracy = 98%" into a hardware table would be wrong;
    # writing down what deployment COSTS is not.
    # Quantisation loss is NOT stored here. It depends on the model as much as
    # on the engine - a transformer under post-training quantisation loses far
    # more than a CNN does - so a single per-engine figure would tie medical
    # imaging and LLM serving to the same number. What the engine determines is
    # the METHOD it can support and how much of the operator set it covers
    # natively; the loss is looked up from those in ppact.accuracy.
    precision: str = "INT8"
    quantization_method: str = "PTQ"    # none | PTQ | QAT | QAT_FP16
    operator_loss_pp: float = 0.5       # points lost to unsupported ops and rewrites

    # Market price is not manufacturing cost. A mature toolchain, compilers,
    # drivers, framework coverage and support are all paid for in the sticker
    # price, and they are a real part of what a planner is buying.
    platform_premium: float = 1.05

    # --- Execution overlap ----------------------------------------------------
    #
    # How much of the DRAM transfer can be hidden behind arithmetic. This was
    # previously assumed perfect - the model took max(compute, memory) - which
    # made every stall figure zero by construction. It is derived rather than
    # entered, because it is a property of the design: how many buffers the
    # accelerator can keep in flight, and how well the compiler tiles the work
    # to keep them full.
    buffering: str = "double"           # single | double | triple
    tiling_quality: str = "normal"      # poor | normal | optimised

    # --- Small-workload behaviour --------------------------------------------
    #
    # The utilisation above is what an engine reaches on work large enough to
    # fill it. A detector at 320x320 does not: kernels launch and drain before
    # the array is busy, and a general-purpose engine suffers more than a
    # systolic one because it has more to schedule. Modelling utilisation as a
    # constant made an embedded GPU appear to run YOLOv8s in 0.26 ms, roughly
    # twenty times faster than such a part measures.
    #
    # efficient_work_ms is how much work, expressed as time at peak rate, an
    # engine needs before it reaches the utilisation above. Below that,
    # utilisation falls in proportion.
    # --- Power states ---------------------------------------------------------
    #
    # A part rated "25 TOPS, 5 W" states a MODULE figure, and comparing it with
    # a chip static-power number mixes two boundaries. Three separate terms,
    # with a ceiling:
    #   static_power_w        leakage of the compute die
    #   module_idle_power_w   the module doing nothing: die, DRAM, PMIC, PHY
    #   module_max_power_w    the design limit the module is rated to
    # Average module power can never exceed the maximum, and two modules at low
    # utilisation do not draw twice the maximum.
    module_idle_power_w: float = 0.0    # 0 means "not stated, use static only"
    module_max_power_w: float = 0.0     # 0 means "no ceiling stated"

    efficient_work_ms: float = 0.5
    # Fixed software cost per inference: graph launch, runtime, driver.
    framework_overhead_ms: float = 0.3

    package_footprint_mm2: float = 0.0
    cost_usd: float = 0.0
    static_power_w: float = 0.0
    die_area_override_mm2: float = 0.0   # non-zero pins the area instead of deriving it
    # (mac, sram, other) fractions, used only with die_area_override_mm2. A
    # shader array spends silicon on schedulers, caches, texture and raster
    # blocks that a systolic array simply does not have; pinning the total
    # without splitting it would hide that.
    area_split: tuple = ()
    automotive_grade: bool = True
    uses_host_cpu: bool = False    # True when the host CPU IS the compute engine
    cost_is_purchased: bool = False  # True for a bought part priced as a whole
    notes: str = ""

    @property
    def peak_mac_per_s(self) -> float:
        if self.mac_array:
            return self.mac_array ** 2 * self.clock_ghz * 1e9
        return self.peak_mac_per_s_override

    @property
    def peak_tops(self) -> float:
        return self.peak_mac_per_s * 2 / 1e12

    # --- Area, built from parts rather than asserted --------------------------
    #
    # A single lumped die area cannot answer the question every accelerator
    # designer actually asks: how much of this chip is memory? Deriving the
    # number instead makes the buffer/array trade visible, and it keeps the
    # library honest - doubling sram_kb now costs silicon, as it must.

    @property
    def mac_area_mm2(self) -> float:
        if self.die_area_override_mm2 and self.area_split:
            return self.die_area_override_mm2 * self.area_split[0]
        macs = self.mac_array ** 2 if self.mac_array else 0
        return macs * MAC_AREA_UM2 / 1e6

    @property
    def sram_area_mm2(self) -> float:
        if self.die_area_override_mm2 and self.area_split:
            return self.die_area_override_mm2 * self.area_split[1]
        return self.sram_kb / 1024.0 * SRAM_MM2_PER_MB

    @property
    def control_area_mm2(self) -> float:
        return max(0.0, self.die_area_mm2 - self.mac_area_mm2 - self.sram_area_mm2)

    # --- Node-derated views ---------------------------------------------------
    #
    # Logic and SRAM are derated separately on purpose. They have not scaled
    # together for several nodes, so an accelerator that is 57% SRAM gains much
    # less from a shrink than its MAC count suggests - a result the student
    # should be able to reproduce rather than be told.

    def mac_area_at(self, node) -> float:
        return self.mac_area_mm2 * get_node(node).logic_area

    def sram_area_at(self, node) -> float:
        return self.sram_area_mm2 * get_node(node).sram_area

    def control_area_at(self, node) -> float:
        return self.control_area_mm2 * get_node(node).logic_area

    def die_area_at(self, node) -> float:
        return (self.mac_area_at(node) + self.sram_area_at(node)
                + self.control_area_at(node))

    def energy_pj_per_mac_at(self, node) -> float:
        return self.energy_pj_per_mac * get_node(node).energy

    def clock_ghz_at(self, node) -> float:
        return self.clock_ghz * get_node(node).fmax

    def effective_utilization(self, total_mac: float, node) -> float:
        """Utilisation actually reached on a workload of this size.

        The stored figure is what an engine reaches on work large enough to
        fill it. A detector at 320x320 does not fill an embedded GPU: kernels
        launch and drain before the array is busy. Treating utilisation as a
        constant had such a part running YOLOv8s in 0.26 ms, roughly twenty
        times faster than one measures.
        """
        peak = self.peak_mac_per_s_at(node)
        full = peak * self.efficient_work_ms * 1e-3
        if full <= 0:
            return self.utilization
        return self.utilization * min(1.0, total_mac / full)

    def peak_mac_per_s_at(self, node) -> float:
        f = get_node(node).fmax
        if self.mac_array:
            return self.mac_array ** 2 * self.clock_ghz_at(node) * 1e9
        return self.peak_mac_per_s_override * f

    def static_power_at(self, node) -> float:
        # Leakage tracks area far more than it tracks logic count.
        return self.static_power_w * self.die_area_at(node) / max(self.die_area_mm2, 1e-9)

    def silicon_cost_at(self, node) -> float:
        """Marginal silicon cost of this block on the given node.

        Used for blocks that are integrated into the SoC the planner is
        specifying. A purchased part (a GPU board, say) carries its own price
        in cost_usd instead, because what is being bought there is not a piece
        of someone else's die.
        """
        base = (self.cost_usd if self.cost_is_purchased
                else self.die_area_at(node) * get_node(node).usd_per_mm2)
        return base * self.platform_premium

    def accuracy_loss_pp(self, model_family: str = "cnn",
                         precision: Optional[str] = None) -> float:
        """Points lost deploying a model of this family on this engine."""
        from .accuracy import quantisation_loss_pp
        return (quantisation_loss_pp(model_family, self.quantization_method,
                                     precision or self.precision)
                + self.operator_loss_pp)

    @property
    def overlap_ratio(self) -> float:
        """Fraction of the shorter of compute/transfer that can be hidden.

        0.0 is fully serial - fetch, then compute, then fetch again.
        1.0 is the perfect double-buffering the model used to assume.
        """
        return min(1.0, BUFFERING_FACTOR[self.buffering]
                   * TILING_FACTOR[self.tiling_quality])

    @property
    def effective_sram_kb(self) -> float:
        """Buffer weighted by how well the schedule actually exploits it."""
        return self.sram_kb * self.dataflow_efficiency

    @property
    def die_area_mm2(self) -> float:
        if self.die_area_override_mm2:
            return self.die_area_override_mm2
        return (self.mac_area_mm2 + self.sram_area_mm2) * SYSTOLIC_PERIPHERY

    @property
    def sram_area_fraction(self) -> float:
        return self.sram_area_mm2 / self.die_area_mm2 if self.die_area_mm2 else 0.0


COMPUTE_LIBRARY: Dict[str, ComputeSpec] = {
    "npu_16x16": ComputeSpec(
        name="NPU 16x16", module_idle_power_w=0.15, module_max_power_w=2.0, efficient_work_ms=0.25, framework_overhead_ms=0.25, buffering="double", tiling_quality="normal", category="Edge NPU", mac_array=16, peak_mac_per_s_override=0.0,
        precision="INT8 (post-training quantised)",
        quantization_method="PTQ", operator_loss_pp=0.5, platform_premium=1.05,
        clock_ghz=0.8, utilization=0.75, energy_pj_per_mac=0.35, sram_kb=256,
        dataflow_efficiency=0.90, dataflow="weight-stationary systolic",
        package_footprint_mm2=25.0, cost_usd=4.0, static_power_w=0.15,
        notes="256 MAC. Smallest array that still runs MobileNet-class models."),
    "npu_20x20": ComputeSpec(
        name="NPU 20x20", module_idle_power_w=0.2, module_max_power_w=2.5, efficient_work_ms=0.25, framework_overhead_ms=0.25, buffering="double", tiling_quality="normal", category="Edge NPU", mac_array=20, peak_mac_per_s_override=0.0,
        precision="INT8 (post-training quantised)",
        quantization_method="PTQ", operator_loss_pp=0.45, platform_premium=1.05,
        clock_ghz=0.8, utilization=0.74, energy_pj_per_mac=0.34, sram_kb=384,
        dataflow_efficiency=0.90, dataflow="weight-stationary systolic",
        package_footprint_mm2=30.0, cost_usd=5.5, static_power_w=0.20,
        notes="400 MAC. Sits deliberately near a closed-loop safety boundary: "
              "fast enough for the sensor frame rate, not fast enough for the "
              "reaction distance."),
    "npu_24x24": ComputeSpec(
        name="NPU 24x24", module_idle_power_w=0.25, module_max_power_w=3.0, efficient_work_ms=0.25, framework_overhead_ms=0.25, buffering="double", tiling_quality="normal", category="Edge NPU", mac_array=24, peak_mac_per_s_override=0.0,
        precision="INT8 (post-training quantised)",
        quantization_method="PTQ", operator_loss_pp=0.45, platform_premium=1.05,
        clock_ghz=0.8, utilization=0.72, energy_pj_per_mac=0.33, sram_kb=512,
        dataflow_efficiency=0.90, dataflow="weight-stationary systolic",
        package_footprint_mm2=34.0, cost_usd=7.0, static_power_w=0.24,
        notes="576 MAC. The other side of that boundary."),
    "npu_32x32": ComputeSpec(
        name="NPU 32x32", module_idle_power_w=0.35, module_max_power_w=4.0, efficient_work_ms=0.25, framework_overhead_ms=0.25, buffering="double", tiling_quality="optimised", category="Edge NPU", mac_array=32, peak_mac_per_s_override=0.0,
        precision="INT8 (quantisation-aware trained)",
        quantization_method="QAT", operator_loss_pp=0.3, platform_premium=1.05,
        clock_ghz=0.8, utilization=0.70, energy_pj_per_mac=0.32, sram_kb=1024,
        dataflow_efficiency=0.90, dataflow="weight-stationary systolic",
        package_footprint_mm2=40.0, cost_usd=9.0, static_power_w=0.30,
        notes="1024 MAC. The most common commercial edge NPU granularity."),
    "npu_64x64": ComputeSpec(
        name="NPU 64x64", module_idle_power_w=0.7, module_max_power_w=8.0, efficient_work_ms=0.25, framework_overhead_ms=0.25, buffering="double", tiling_quality="optimised", category="Edge NPU", mac_array=64, peak_mac_per_s_override=0.0,
        precision="INT8 (quantisation-aware trained)",
        quantization_method="QAT", operator_loss_pp=0.25, platform_premium=1.05,
        clock_ghz=0.8, utilization=0.60, energy_pj_per_mac=0.30, sram_kb=4096,
        dataflow_efficiency=0.88, dataflow="weight-stationary systolic",
        package_footprint_mm2=90.0, cost_usd=28.0, static_power_w=0.90,
        notes="4096 MAC. Utilization drops: harder to keep a wide array fed."),
    "npu_128x128": ComputeSpec(
        name="NPU 128x128", module_idle_power_w=1.4, module_max_power_w=15.0, efficient_work_ms=0.25, framework_overhead_ms=0.25, buffering="triple", tiling_quality="optimised", category="Automotive NPU", mac_array=128,
        precision="INT8 QAT with FP16 fallback",
        quantization_method="QAT_FP16", operator_loss_pp=0.2, platform_premium=1.10,
        peak_mac_per_s_override=0.0, clock_ghz=1.0, utilization=0.55,
        energy_pj_per_mac=0.28, sram_kb=16384,
        dataflow_efficiency=0.88, dataflow="row-stationary systolic",
        package_footprint_mm2=320.0, cost_usd=120.0, static_power_w=6.0,
        notes="16384 MAC. Automotive-class accelerator: multi-camera ADAS needs "
              "an order of magnitude more than a phone-class NPU."),
    "mobile_gpu": ComputeSpec(
        name="Mobile GPU", module_idle_power_w=0.25, module_max_power_w=3.0, efficient_work_ms=0.8, framework_overhead_ms=1.0, buffering="double", tiling_quality="poor", category="Mobile GPU", mac_array=0,
        precision="FP16",
        quantization_method="none", operator_loss_pp=0.0, platform_premium=1.15,
        peak_mac_per_s_override=0.9e12, clock_ghz=1.0, utilization=0.45,
        energy_pj_per_mac=1.10, sram_kb=512,
        dataflow_efficiency=0.45, dataflow="cache hierarchy, no explicit schedule",
        package_footprint_mm2=60.0,
        cost_usd=16.0, static_power_w=0.60, die_area_override_mm2=22.0,
        cost_is_purchased=True,
        area_split=(0.22, 0.28, 0.50),
        notes="Flexible but roughly 3x the energy per MAC of a systolic NPU. "
              "Area is pinned rather than derived: a shader array is not a "
              "systolic array and the MAC-cell model does not describe it."),
    "cpu_only": ComputeSpec(
        name="CPU only (SIMD)", efficient_work_ms=0.2, framework_overhead_ms=0.5, buffering="single", tiling_quality="poor", category="No accelerator", mac_array=0,
        precision="FP32",
        quantization_method="none", operator_loss_pp=0.0, platform_premium=1.00,
        peak_mac_per_s_override=0.05e12, clock_ghz=2.0, utilization=0.60,
        energy_pj_per_mac=9.00, sram_kb=256,
        dataflow_efficiency=0.20, dataflow="SIMD over a general cache hierarchy",
        package_footprint_mm2=0.0,
        cost_usd=0.0, static_power_w=0.0, uses_host_cpu=True,
        notes="No accelerator die, and no accelerator cost or area either - the "
              "work runs on the host cores. Included so students can measure "
              "what the accelerator actually buys, in TOPS and in joules."),
    # Added after the industry cases showed the library topping out well below
    # the parts those products actually use. The largest NPU here reached 49
    # TOPS while an edge box in the field carries 80, and "Mobile GPU" at 2.5
    # TOPS was standing in for an edge module of tens of TOPS - so a
    # GPU-to-NPU comparison was measuring an 18-fold compute jump that does not
    # exist in the products being described.
    "edge_gpu": ComputeSpec(
        name="Edge GPU module class", module_idle_power_w=4.5, module_max_power_w=40.0, efficient_work_ms=1.0, framework_overhead_ms=1.5, category="Edge GPU", mac_array=0,
        buffering="double", tiling_quality="poor",
        precision="FP16", quantization_method="none", operator_loss_pp=0.0,
        platform_premium=1.20,
        peak_mac_per_s_override=25e12,      # about 50 dense TOPS
        utilization=0.42, energy_pj_per_mac=1.05, sram_kb=6144,
        clock_ghz=1.3, static_power_w=3.2,
        die_area_override_mm2=185.0, package_footprint_mm2=380.0,
        cost_usd=420.0, cost_is_purchased=True,
        dataflow="general-purpose SIMT", dataflow_efficiency=0.55,
        automotive_grade=True,
        notes="An embedded GPU module, not a phone GPU. Estimated."),

    "npu_160x160": ComputeSpec(
        name="NPU 160x160", module_idle_power_w=1.8, module_max_power_w=25.0, efficient_work_ms=0.25, framework_overhead_ms=0.25, category="Edge NPU", mac_array=160,
        buffering="triple", tiling_quality="optimised",
        precision="INT8 QAT with FP16 fallback",
        quantization_method="QAT_FP16", operator_loss_pp=0.2,
        platform_premium=1.10,
        peak_mac_per_s_override=0.0,
        utilization=0.52, energy_pj_per_mac=0.27, sram_kb=12288,
        clock_ghz=1.0, static_power_w=1.9,
        package_footprint_mm2=340.0,
        dataflow="weight-stationary systolic", dataflow_efficiency=0.90,
        automotive_grade=True,
        notes="An 80 TOPS class edge box. Estimated."),

    # ------------------------------------------------------------------
    # ARCHITECTURAL CLASSES, not products
    # ------------------------------------------------------------------
    #
    # The library gap these close was found by measuring it against
    # published automotive accelerator specifications: it ran from 51 TOPS
    # straight to 600, and the band where every shipping automotive part
    # sits was empty. An engineer familiar with those parts would open the
    # Studio and conclude it models hardware from several years ago, and
    # they would be right.
    #
    # Each entry is a CLASS - a performance point the industry has settled
    # around - and not a part. No vendor is named, no proprietary
    # organisation is inferred, and nothing here reproduces a commercial
    # product. What is copied from the industry is the SHAPE of the class:
    # roughly this much arithmetic, in roughly this power envelope, at
    # roughly this price.
    #
    # EVERY PARAMETER BELOW IS AN ENGINEERING ESTIMATE. They are derived by
    # scaling the measured entries above, and no vendor publishes enough for
    # any of them to be checked. That is acceptable here for the same reason
    # the rest of the model is acceptable: the Studio computes from
    # analytical models rather than from hardware measurements, and says so.
    # It would NOT be acceptable to present them as anything else.

    "class_10_tops_soc": ComputeSpec(
        name="10 TOPS on-device SoC class",
        category="On-device AI SoC class",
        module_idle_power_w=0.4, module_max_power_w=3.0,
        efficient_work_ms=0.15, framework_overhead_ms=0.2,
        mac_array=71, buffering="double", tiling_quality="optimised",
        precision="INT8 (post-training quantised)",
        quantization_method="PTQ", operator_loss_pp=0.6,
        platform_premium=1.05, peak_mac_per_s_override=0.0,
        utilization=0.48, energy_pj_per_mac=0.32, sram_kb=4096,
        clock_ghz=1.0, static_power_w=0.35,
        package_footprint_mm2=289.0,
        dataflow="weight-stationary systolic", dataflow_efficiency=0.86,
        automotive_grade=False, uses_host_cpu=False,
        notes="ESTIMATED architectural class, not a product. The design "
              "point that was missing entirely: about ten INT8 TOPS inside "
              "a three-watt envelope, in a package small enough to sit on a "
              "drone or a camera. Published parts in this class integrate "
              "the host cores, an ISP and a video codec on the same die - "
              "which the Studio treats as a bare accelerator, and that is a "
              "recorded gap rather than something this entry fixes."),

    "class_25_tops_module": ComputeSpec(
        name="25 TOPS module class", category="Embedded module class",
        module_idle_power_w=0.9, module_max_power_w=8.0,
        efficient_work_ms=0.2, framework_overhead_ms=0.3,
        mac_array=112, buffering="triple", tiling_quality="optimised",
        precision="INT8 (post-training quantised)",
        quantization_method="PTQ", operator_loss_pp=0.5,
        platform_premium=1.08, peak_mac_per_s_override=0.0,
        utilization=0.50, energy_pj_per_mac=0.26, sram_kb=8192,
        clock_ghz=1.0, static_power_w=0.85,
        package_footprint_mm2=324.0,
        dataflow="weight-stationary systolic", dataflow_efficiency=0.88,
        automotive_grade=False,
        notes="ESTIMATED architectural class, not a product. Added at 4.4.0 "
              "when a published module of about 25 TOPS in 5 W was found to "
              "fall between the 10 TOPS SoC class and the next entry up: "
              "the first class closed a gap and exposed a narrower one. A "
              "carrier-mounted module rather than a card or a bare die."),

    "class_80_tops_card": ComputeSpec(
        name="80 TOPS accelerator card class",
        category="Edge accelerator card class",
        module_idle_power_w=3.0, module_max_power_w=25.0,
        efficient_work_ms=0.3, framework_overhead_ms=0.5,
        mac_array=200, buffering="triple", tiling_quality="optimised",
        precision="INT8 (post-training quantised)",
        quantization_method="PTQ", operator_loss_pp=0.5,
        platform_premium=1.12, peak_mac_per_s_override=0.0,
        utilization=0.50, energy_pj_per_mac=0.20, sram_kb=16384,
        clock_ghz=1.0, static_power_w=3.2,
        package_footprint_mm2=380.0,
        dataflow="weight-stationary systolic", dataflow_efficiency=0.89,
        automotive_grade=False,
        notes="ESTIMATED architectural class, not a product. A low-profile "
              "card in a 25 W envelope: an on-premises inference band that "
              "sits between an embedded SoC and a data-centre card, and "
              "which the library skipped. Paired with mainstream low-power "
              "memory rather than stacked, because the bandwidth that "
              "matters at this scale is affordable without it."),

    "class_64_tops": ComputeSpec(
        name="64 TOPS class", category="Server vision NPU class",
        module_idle_power_w=6.0, module_max_power_w=60.0,
        efficient_work_ms=0.4, framework_overhead_ms=0.6,
        mac_array=127, buffering="triple", tiling_quality="optimised",
        precision="INT8 (post-training quantised)",
        quantization_method="PTQ", operator_loss_pp=0.6,
        platform_premium=1.15, peak_mac_per_s_override=0.0,
        utilization=0.50, energy_pj_per_mac=0.55, sram_kb=32768,
        clock_ghz=2.0, static_power_w=6.5,
        package_footprint_mm2=420.0,
        dataflow="weight-stationary systolic", dataflow_efficiency=0.88,
        automotive_grade=False,
        notes="ESTIMATED architectural class, not a product. A half-height "
              "inference card for computer vision in a server or an edge "
              "rack: passively cooled, tens of watts, mainstream memory "
              "rather than stacked. Published parts in this class run near "
              "2 GHz on a mature node, which is why the clock is high and "
              "the energy per operation is not."),

    "class_dc_inference_card": ComputeSpec(
        name="Datacenter inference card class",
        category="Datacenter inference class",
        module_idle_power_w=25.0, module_max_power_w=150.0,
        efficient_work_ms=0.8, framework_overhead_ms=1.2,
        mac_array=0, buffering="triple", tiling_quality="optimised",
        precision="BF16 / FP8 / INT8 / INT4",
        quantization_method="PTQ", operator_loss_pp=0.3,
        platform_premium=1.25,
        peak_mac_per_s_override=256e12, clock_ghz=1.0,
        utilization=0.55, energy_pj_per_mac=0.10, sram_kb=262144,
        dataflow="tensor contraction over a large on-chip buffer",
        dataflow_efficiency=0.80,
        package_footprint_mm2=900.0,
        cost_usd=6000.0, static_power_w=30.0, die_area_override_mm2=620.0,
        cost_is_purchased=True,
        area_split=(0.28, 0.46, 0.26),
        automotive_grade=False,
        notes="ESTIMATED architectural class, not a product. The shape that "
              "has appeared across inference accelerators: a passively "
              "cooled card inside a 150 W envelope, a very large on-chip "
              "buffer measured in hundreds of megabytes rather than tens, "
              "and stacked memory. The buffer is the distinguishing "
              "feature - it is what lets the part hold a working set that a "
              "smaller cache would stream. Price is an estimate; no card in "
              "this class publishes one."),

    "class_100_tops": ComputeSpec(
        name="100 TOPS class", category="Automotive NPU class",
        module_idle_power_w=2.5, module_max_power_w=35.0,
        efficient_work_ms=0.25, framework_overhead_ms=0.25,
        mac_array=224, buffering="triple", tiling_quality="optimised",
        precision="INT8 QAT with FP16 fallback",
        quantization_method="QAT_FP16", operator_loss_pp=0.2,
        platform_premium=1.10, peak_mac_per_s_override=0.0,
        utilization=0.50, energy_pj_per_mac=0.26, sram_kb=24576,
        clock_ghz=1.0, static_power_w=2.6,
        package_footprint_mm2=420.0,
        dataflow="weight-stationary systolic", dataflow_efficiency=0.90,
        automotive_grade=True,
        notes="ESTIMATED architectural class, not a product. An entry "
              "automotive inference part: single-camera ADAS or a driver "
              "monitor. Every parameter is an engineering estimate scaled "
              "from the measured entries above."),

    "class_150_tops": ComputeSpec(
        name="150 TOPS class", category="Automotive NPU class",
        module_idle_power_w=3.2, module_max_power_w=45.0,
        efficient_work_ms=0.25, framework_overhead_ms=0.25,
        mac_array=274, buffering="triple", tiling_quality="optimised",
        precision="INT8 QAT with FP16 fallback",
        quantization_method="QAT_FP16", operator_loss_pp=0.2,
        platform_premium=1.10, peak_mac_per_s_override=0.0,
        utilization=0.50, energy_pj_per_mac=0.25, sram_kb=32768,
        clock_ghz=1.0, static_power_w=3.4,
        package_footprint_mm2=500.0,
        dataflow="weight-stationary systolic", dataflow_efficiency=0.90,
        automotive_grade=True,
        notes="ESTIMATED architectural class, not a product. Multi-camera "
              "ADAS without a language model."),

    "class_250_tops": ComputeSpec(
        name="250 TOPS class", category="Automotive NPU class",
        module_idle_power_w=4.5, module_max_power_w=65.0,
        efficient_work_ms=0.25, framework_overhead_ms=0.25,
        mac_array=354, buffering="triple", tiling_quality="optimised",
        precision="INT8 QAT with FP16 fallback",
        quantization_method="QAT_FP16", operator_loss_pp=0.2,
        platform_premium=1.15, peak_mac_per_s_override=0.0,
        utilization=0.50, energy_pj_per_mac=0.24, sram_kb=49152,
        clock_ghz=1.0, static_power_w=4.8,
        package_footprint_mm2=650.0,
        dataflow="weight-stationary systolic", dataflow_efficiency=0.90,
        automotive_grade=True,
        notes="ESTIMATED architectural class, not a product. The band where "
              "current automotive AI accelerators sit: ADAS with a language "
              "or vision-language model alongside it."),

    "class_300_tops": ComputeSpec(
        name="300 TOPS class", category="Automotive NPU class",
        module_idle_power_w=5.5, module_max_power_w=80.0,
        efficient_work_ms=0.25, framework_overhead_ms=0.25,
        mac_array=388, buffering="triple", tiling_quality="optimised",
        precision="INT8 QAT with FP16 fallback",
        quantization_method="QAT_FP16", operator_loss_pp=0.2,
        platform_premium=1.15, peak_mac_per_s_override=0.0,
        utilization=0.50, energy_pj_per_mac=0.24, sram_kb=57344,
        clock_ghz=1.0, static_power_w=5.8,
        package_footprint_mm2=760.0,
        dataflow="weight-stationary systolic", dataflow_efficiency=0.90,
        automotive_grade=True,
        notes="ESTIMATED architectural class, not a product. In industry "
              "this point is usually reached by pairing two dies rather "
              "than building one - which the Studio cannot yet express, and "
              "that gap is recorded rather than hidden by this entry."),

    "class_500_tops": ComputeSpec(
        name="500 TOPS class", category="Automotive NPU class",
        module_idle_power_w=9.0, module_max_power_w=130.0,
        efficient_work_ms=0.30, framework_overhead_ms=0.30,
        mac_array=500, buffering="triple", tiling_quality="optimised",
        precision="INT8 QAT with FP16 fallback",
        quantization_method="QAT_FP16", operator_loss_pp=0.2,
        platform_premium=1.20, peak_mac_per_s_override=0.0,
        utilization=0.50, energy_pj_per_mac=0.23, sram_kb=81920,
        clock_ghz=1.0, static_power_w=9.5,
        package_footprint_mm2=1100.0,
        dataflow="weight-stationary systolic", dataflow_efficiency=0.90,
        automotive_grade=True,
        notes="ESTIMATED architectural class, not a product. A central "
              "compute unit rather than a zone controller."),

    "class_800_tops": ComputeSpec(
        name="800 TOPS class", category="Automotive NPU class",
        module_idle_power_w=14.0, module_max_power_w=200.0,
        efficient_work_ms=0.30, framework_overhead_ms=0.30,
        mac_array=632, buffering="triple", tiling_quality="optimised",
        precision="INT8 QAT with FP16 fallback",
        quantization_method="QAT_FP16", operator_loss_pp=0.2,
        platform_premium=1.20, peak_mac_per_s_override=0.0,
        utilization=0.50, energy_pj_per_mac=0.22, sram_kb=131072,
        clock_ghz=1.0, static_power_w=15.0,
        package_footprint_mm2=1600.0,
        dataflow="weight-stationary systolic", dataflow_efficiency=0.90,
        automotive_grade=True,
        notes="ESTIMATED architectural class, not a product. In industry "
              "this is a multi-die part; here it is one die, and reading "
              "the two as equivalent would be the mistake this note "
              "exists to prevent."),

    "datacenter_gpu": ComputeSpec(
        name="Datacenter GPU", module_idle_power_w=45.0, module_max_power_w=400.0, efficient_work_ms=1.2, framework_overhead_ms=2.0, buffering="double", tiling_quality="normal", category="Datacenter", mac_array=0,
        precision="FP16 / BF16",
        quantization_method="none", operator_loss_pp=0.0, platform_premium=1.30,
        peak_mac_per_s_override=300e12, clock_ghz=1.8, utilization=0.55,
        energy_pj_per_mac=0.12, sram_kb=51200,
        dataflow_efficiency=0.65, dataflow="tensor cores over a cache hierarchy",
        package_footprint_mm2=1600.0,
        cost_usd=9000.0, static_power_w=90.0, die_area_override_mm2=810.0,
        cost_is_purchased=True,
        area_split=(0.30, 0.32, 0.38),
        automotive_grade=False,
        notes="Approximate, and area pinned for the same reason as the mobile "
              "GPU. Included as the upper bound of the design space."),
}


# ==============================================================================


# ==============================================================================
# RESERVED - compute-in-memory. Not active.
# ==============================================================================
#
# Placeholder only. These entries are deliberately NOT merged into
# COMPUTE_LIBRARY, so nothing in the model, the gates or the reports sees them.
# Enabling one means finishing the area model first, because the assumption the
# current one rests on does not hold for CIM.
#
# In a systolic design the MAC array and the SRAM are separate blocks, which is
# why die area is (mac_area + sram_area) * periphery. In a compute-in-memory
# design the multiply-accumulate happens inside the bitcell array itself: the
# weights live in the cells and the array IS the arithmetic. Adding the two
# areas would then double-count the same silicon.
#
# What has to be decided before switching one on:
#
#   1. Area      MAC and SRAM share silicon. Needs a CIM_MM2_PER_MB constant
#                covering the modified bitcell plus its adder tree (digital CIM)
#                or its DAC/ADC converters (analog CIM). Converter overhead is
#                not a rounding error - it can exceed half the macro.
#   2. Utilization  Weights are resident rather than streamed, so a model larger
#                than the macro pays a reload penalty the current roofline does
#                not represent. `utilization` alone cannot express that.
#   3. Precision Analog CIM degrades with bit width. A single INT8 energy figure
#                would flatter it.
#
# Rough figures to start from, from published macros (research silicon, not
# production parts): all-digital SRAM CIM around 89 TOPS/W at 22 nm, and a
# foundry 6T-bitcell digital macro at 3 nm reporting about 32.5 TOPS/W with
# INT12 support. Analog macros report higher still, at lower precision.
#
# Commercial edge NPUs - Edge TPU, Arm Ethos, Hexagon, Apple ANE - are all
# conventional MAC array plus SRAM today. CIM belongs in this file as the
# contrast case, not yet as a candidate.

RESERVED_COMPUTE: Dict[str, str] = {
    "npu_dcim_32x32": "Digital compute-in-memory, 32x32 equivalent. Area model pending.",
    "npu_acim_32x32": "Analog compute-in-memory, 32x32 equivalent. Area and precision model pending.",
    "dram_pim": "Near-memory compute in DRAM (HBM-PIM / AiM class). Memory-side model pending.",
}
