"""
ppact.workflow - the functions a student calls

Thin orchestration over the models: evaluate, print, draw. Kept separate so
that the model modules can be imported and scripted without any output.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

import itertools
from typing import Dict, List, Optional, Sequence

from .application import APPLICATION_LIBRARY
from .compute import COMPUTE_LIBRARY
from .cpu import CPU_LIBRARY
from .memory import MEMORY_LIBRARY, evaluate
from .system import (SystemConfig, SystemResult, evaluate_system,
                     score_system, default_candidates)
from .report import (print_memory_report, print_comparison,
                     print_anchor_table,
                     print_gate, print_analysis)
from .charts import (render_spider, render_block_diagram, render_bars,
                     render_system_spider)


def run_application(app_key: str,
                    candidates: Optional[Sequence[SystemConfig]] = None,
                    show_analysis: bool = True,
                    show_bars: bool = True,
                    show_spider: bool = True) -> List[SystemResult]:
    """Evaluate one application against a slate of candidate systems."""
    if app_key not in APPLICATION_LIBRARY:
        raise KeyError(f"Unknown application '{app_key}'. "
                       f"Available: {', '.join(APPLICATION_LIBRARY)}")
    app = APPLICATION_LIBRARY[app_key]
    configs = list(candidates) if candidates else default_candidates(app_key)
    results = [evaluate_system(app, c) for c in configs]

    print_gate(results)
    if show_analysis:
        print_analysis(results)
    # Wrapped. A library note is a paragraph and was
    # printed on one line - 233 characters on the
    # widest, which no terminal shows and no reader
    # follows.
    from .visual.text import wrap_text as _wrap
    print()
    for _i, _l in enumerate(_wrap(str(app.notes), 70)):
        print(f"  Note: {_l}" if _i == 0
              else f"        {_l}")

    if show_bars:
        render_bars(results)
    if show_spider:
        render_system_spider(results)
    return results


def list_applications() -> None:
    print("=" * 78)
    print(" APPLICATIONS")
    print("=" * 78)
    for k, a in APPLICATION_LIBRARY.items():
        print(f"  {k:<14s} {a.name:<34s} {a.model}")
        print(f"  {'':<14s} {a.power_budget_w:g} W, ${a.bom_budget_usd:,.0f}, "
              f"{a.target_inferences_per_s:g} inf/s, {a.cooling}")


# A notebook cell also reports __name__ == "__main__" and carries kernel
# arguments such as "-f /.../kernel.json" in sys.argv, so the environment is


def compare_memories(selection: Optional[Sequence[str]] = None,
                     show_reports: bool = True,
                     show_comparison: bool = True,
                     show_anchors: bool = True,
                     show_schematic: bool = True):
    """Component-level view: DRAM technologies against each other."""
    names = [n.upper() for n in (selection or ["LPDDR5", "GDDR6"])]
    unknown = [n for n in names if n not in MEMORY_LIBRARY]
    if unknown:
        raise KeyError(f"Unknown memory type(s): {', '.join(unknown)}. "
                       f"Available: {', '.join(MEMORY_LIBRARY)}")
    results = [evaluate(MEMORY_LIBRARY[n]) for n in names]
    if show_reports:
        for r in results:
            print_memory_report(r)
    if show_comparison:
        print_comparison(results)
    if show_anchors:
        print_anchor_table()
    render_spider(results)
    if show_schematic:
        render_block_diagram(results[0].spec)
    return results


def list_libraries() -> None:
    """Print every library key a SystemConfig can reference."""
    print("=" * 78)
    print(" LIBRARIES")
    print("=" * 78)
    print(f"  CPU     : {', '.join(CPU_LIBRARY)}")
    print(f"  Compute : {', '.join(COMPUTE_LIBRARY)}")
    print(f"  Memory  : {', '.join(MEMORY_LIBRARY)}")
    print(f"  Apps    : {', '.join(APPLICATION_LIBRARY)}")
    from .process import NODE_LIBRARY, PROFILES
    print(f"  Nodes   : {', '.join(NODE_LIBRARY)}")
    print(f"  Profiles: {', '.join(PROFILES)}")
    print("\n  A node belongs to a die. On a monolithic SoC the accelerator is")
    print("  forced onto the host node; on separate dies they can differ.")
    print(f"\n  {'application':<15s}{'host':>6s}{'accel':>7s}   integration")
    for k, a in APPLICATION_LIBRARY.items():
        from .process import node_name as _nn
        print(f"    {k:<13s}{_nn(a.default_soc_node):>7s}{_nn(a.default_accel_node):>8s}"
              f"   {a.integration}")


def sweep(app_key: str,
          cpus: Optional[Sequence[str]] = None,
          computes: Optional[Sequence[str]] = None,
          memories: Optional[Sequence[str]] = None,
          device_counts: Sequence[int] = (1, 2, 4, 8),
          objective: str = "Energy per inference (mJ)",
          minimize: bool = True,
          top: int = 10) -> List[SystemResult]:
    """Exhaustive search over the libraries, ranked among candidates that pass.

    Design space exploration in its simplest honest form: build every
    combination, discard the ones that miss a product budget, and rank what is
    left by one objective. Ranking before gating would surface designs that
    cannot ship, which is the mistake the gate exists to prevent.
    """
    app = APPLICATION_LIBRARY[app_key]
    cpus = list(cpus or CPU_LIBRARY)
    computes = list(computes or COMPUTE_LIBRARY)
    memories = list(memories or MEMORY_LIBRARY)

    results = [evaluate_system(app, SystemConfig(c, k, m, n))
               for c, k, m, n in itertools.product(cpus, computes, memories, device_counts)]
    survivors = [r for r in results if r.passes]

    print("=" * 78)
    print(f" DESIGN SPACE SWEEP : {app.name}")
    print("=" * 78)
    print(f"  combinations evaluated : {len(results)}")
    print(f"  passed the gate        : {len(survivors)}")
    if not survivors:
        print("\n  Nothing fits. Either the budgets are too tight or the "
              "libraries lack a suitable part.")
        return []

    survivors.sort(key=lambda r: r.metrics[objective], reverse=not minimize)
    print(f"  ranked by              : {objective} "
          f"({'lower' if minimize else 'higher'} is better)\n")
    head = (f"  {'#':>2s}  {'candidate':<52s}{objective[:22]:>24s}"
            f"{'latency ms':>12s}{'power W':>10s}{'cost $':>10s}")
    print(head); print("  " + "-" * (len(head) - 2))
    for i, r in enumerate(survivors[:top], 1):
        print(f"  {i:>2d}  {r.label:<52s}{r.metrics[objective]:>24.3f}"
              f"{r.metrics['Latency (ms)']:>12.2f}"
              f"{r.metrics['System power (W)']:>10.2f}"
              f"{r.metrics['System cost (USD)']:>10.2f}")
    return survivors
