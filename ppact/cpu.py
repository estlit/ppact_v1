"""
ppact.cpu - host processor library

The CPU is modelled as a dispatch-overhead and power contributor, not as a
core simulator. For PPACT purposes what matters is how long it stalls the
pipeline per inference and what it costs in area, dollars and watts.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from .process import get_node


@dataclass(frozen=True)
class CPUSpec:
    name: str
    cores: int
    clock_ghz: float
    dispatch_overhead_us: float     # per inference: job setup, DMA, sync, IRQ
    active_power_w: float
    idle_power_w: float             # while the accelerator runs, the CPU waits
    die_area_mm2: float             # cores plus caches, quoted at the reference node
    cost_usd: float
    cache_area_fraction: float = 0.45   # caches derate as SRAM, cores as logic
    automotive_grade: bool = True

    # --- Work model -----------------------------------------------------------
    #
    # Costs are quoted in CYCLES rather than in time, so that raising the clock
    # shortens the work without anyone having to remember to rescale a table.
    # Each stage splits into a fixed setup and a part proportional to the
    # workload, because that distinction is what Phase 3 needs to tell a
    # pipeline interval from a one-off cost.
    #
    # Per-pixel figures assume an ISP or camera block has already done debayer
    # and colour conversion, which is what actually happens in every product in
    # this library. What is left for the CPU is layout and normalisation.
    cycles_per_pixel: float = 2.0
    cycles_per_output_element: float = 180.0     # NMS, argmax, formatting
    cycles_per_token: float = 3000.0             # tokenise, sample, detokenise
    fixed_preprocess_cycles: float = 20_000.0
    fixed_postprocess_cycles: float = 15_000.0
    # Pre- and post-processing parallelise, but not perfectly.
    parallel_efficiency: float = 0.60

    @property
    def cycles_per_second(self) -> float:
        return self.clock_ghz * 1e9 * self.cores * self.parallel_efficiency

    def cycles_per_second_at(self, node) -> float:
        return self.cycles_per_second * get_node(node).fmax

    def die_area_at(self, node) -> float:
        n = get_node(node)
        sram = self.die_area_mm2 * self.cache_area_fraction
        logic = self.die_area_mm2 - sram
        return logic * n.logic_area + sram * n.sram_area

    def active_power_at(self, node) -> float:
        return self.active_power_w * get_node(node).energy

    def idle_power_at(self, node) -> float:
        return self.idle_power_w * get_node(node).energy

    def silicon_cost_at(self, node) -> float:
        return self.die_area_at(node) * get_node(node).usd_per_mm2


CPU_LIBRARY: Dict[str, CPUSpec] = {
    "cortex_a53_x4": CPUSpec("Cortex-A53 x4", 4, 1.4, 45.0, 0.9, 0.08, 4.0, 6.0,
                             cycles_per_pixel=5.0, cycles_per_output_element=400.0,
                             cycles_per_token=8000.0),
    "cortex_a78_x4": CPUSpec("Cortex-A78 x4", 4, 2.4, 18.0, 3.2, 0.25, 10.0, 22.0,
                             cycles_per_pixel=2.0, cycles_per_output_element=180.0,
                             cycles_per_token=3000.0),
    "riscv_rv64_x2": CPUSpec("RISC-V RV64GC x2", 2, 1.0, 80.0, 0.5, 0.04, 2.0, 3.0,
                             cycles_per_pixel=8.0, cycles_per_output_element=600.0,
                             cycles_per_token=12000.0),
    "server_x86_x32": CPUSpec("Server x86 x32", 32, 3.0, 8.0, 180.0, 20.0, 400.0, 4000.0,
                              automotive_grade=False, cycles_per_pixel=1.0,
                              cycles_per_output_element=90.0, cycles_per_token=1500.0),
}


# ==============================================================================
