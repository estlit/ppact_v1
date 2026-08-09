"""
ppact.reference_space - the design space, scored on one basis

WHY A SPACE AND NOT A LIST
==========================
A single design's PPACT figures say what it is. They do not say whether it
is unusual: 25.1% traffic balance means nothing until something else has
been scored the same way.

    2,841,696 combinations across nine applications

Enumerating that is affordable in principle and answers a question nobody
asked. What matters is COVERAGE OF THE STRUCTURAL CLASSES - VD-1's rule -
so the sample is stratified rather than random or exhaustive.

WHAT A PERCENTILE HERE IS AND IS NOT
------------------------------------
It is a position within THIS sample of THIS library. It is not a position
among products, and the library is not a market survey. A design in the
90th percentile for cost is cheap relative to what this model can build,
which is a statement about the model.

THE SPACE IS SCORED PER APPLICATION
-----------------------------------
Requirement-centred scoring means a design's score depends on what it is
asked for, so ranking across applications would compare answers to
different questions. Every comparison here is within one application.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

NOT_ESTABLISHED = "NOT ESTABLISHED"

# The strata. Chosen so each class of design appears rather than each
# combination: a thousand samples of one shape teach less than ten of
# each.
STRATA = ("preprocessing", "accelerator class", "memory technology",
          "memory units", "second accelerator")


@dataclass(frozen=True)
class SpacePoint:
    app: str
    cpu: str
    compute: str
    secondary: str
    memory: str
    units: int
    preprocessing: str

    throughput: Optional[float]
    limit: Optional[float]
    bottleneck: str
    traffic_balance: Optional[float]
    soc_mm2: Optional[float]
    cost_usd: Optional[float]
    deployable: bool


@dataclass(frozen=True)
class ReferenceSpace:
    app: str
    points: Tuple[SpacePoint, ...]
    sampled: int
    considered: int

    def percentile(self, value: Optional[float], attr: str,
                   higher_is_better: bool) -> Optional[float]:
        """Where a value sits in THIS sample. Not a market position."""
        if value is None:
            return None
        vals = [getattr(p, attr) for p in self.points
                if getattr(p, attr) is not None]
        if not vals:
            return None
        below = sum(1 for v in vals
                    if (v < value if higher_is_better else v > value))
        return below / len(vals) * 100.0


def _sample_configs(app_key: str, per_stratum: int = 2
                    ) -> Iterable[Tuple]:
    """One CPU per domain, every accelerator class, every memory, a
    spread of units and preprocessing modes, with and without a second
    engine.

    Not random. A random sample of a space this shape is dominated by its
    largest dimension - twenty-three secondary options - and would report
    dual-accelerator designs as typical.
    """
    from .application import APPLICATION_LIBRARY
    from .system import COMPUTE_LIBRARY, MEMORY_LIBRARY

    app = APPLICATION_LIBRARY[app_key]
    cpu = ("server_x86_x32" if app.domain == "Data Center"
           else "cortex_a78_x4")
    computes = list(COMPUTE_LIBRARY)
    memories = list(MEMORY_LIBRARY)
    seconds = [None] + computes[::max(1, len(computes) // 3)]

    for comp, mem, units, pm, sc in itertools.product(
            computes, memories, (1, 2, 4, 8),
            ("cpu_only", "isp_assisted", "isp_and_npu"), seconds):
        yield (cpu, comp, mem, units, pm, sc)


def build_reference_space(app_key: str, limit: int = 4000
                          ) -> ReferenceSpace:
    from .system import SystemConfig
    from .review import build_review
    from .perf_bottleneck import find_bottleneck
    from .traffic import build_traffic_balance

    # STRIDE, not truncate.
    #
    # Taking the first `limit` entries of a product() keeps the outermost
    # loop's first value and nothing else: a 600-point sample contained
    # ONE accelerator class of twenty-two, and reported that design as
    # the worst in the space because it was the only kind in it.
    #
    # A stride keeps the spread. It is still not random, and that is
    # deliberate - random sampling here is dominated by the
    # twenty-three secondary options.
    all_configs = list(_sample_configs(app_key))
    considered = len(all_configs)
    step = max(1, considered // limit)
    chosen = all_configs[::step][:limit]

    points: List[SpacePoint] = []
    for cpu, comp, mem, units, pm, sc in chosen:
        cfg = SystemConfig(cpu, comp, mem, units, preprocessing_mode=pm,
                           secondary_compute=sc,
                           execution_mode="parallel" if sc else "single",
                           work_split=0.5 if sc else 0.0)
        try:
            a = build_review("education_step_by_step", app_key, cfg)
            b = find_bottleneck(a)
            t = build_traffic_balance(a)
            m = a.current_result.metrics
        except Exception:
            # A configuration the model refuses is not a data point. It
            # is also not silently a zero.
            continue
        points.append(SpacePoint(
            app=app_key, cpu=cpu, compute=comp,
            secondary=sc or "-", memory=mem, units=units,
            preprocessing=pm,
            throughput=b.delivered_inf_s, limit=b.limit_inf_s,
            bottleneck=b.bottleneck,
            traffic_balance=t.balance_pct,
            soc_mm2=m.get("SoC silicon (mm2)"),
            cost_usd=m.get("System cost (USD)"),
            deployable=a.current_result.passes))
    return ReferenceSpace(app_key, tuple(points), len(points), considered)


def render_position(space: ReferenceSpace, analysis) -> List[str]:
    """Where one design sits in the space, and what that does not mean."""
    from .visual.text import wrap_text
    from .perf_bottleneck import find_bottleneck
    from .traffic import build_traffic_balance

    b = find_bottleneck(analysis)
    t = build_traffic_balance(analysis)
    m = analysis.current_result.metrics

    out = ["POSITION IN THE DESIGN SPACE", ""]
    out.append(f"  Application                 {space.app}")
    out.append(f"  Designs sampled             {space.sampled:,} of "
               f"{space.considered:,} considered")
    out.append("")

    rows = (("throughput limit", b.limit_inf_s, "limit", True),
            ("traffic balance", t.balance_pct, "traffic_balance", True),
            ("SoC silicon", m.get("SoC silicon (mm2)"), "soc_mm2", False),
            ("system cost", m.get("System cost (USD)"), "cost_usd",
             False))
    out.append(f"  {'quantity':<22s}{'this design':>14s}"
               f"{'percentile':>12s}")
    out.append("  " + "-" * 50)
    for label, value, attr, higher in rows:
        pct = space.percentile(value, attr, higher)
        shown = f"{value:,.1f}" if value is not None else NOT_ESTABLISHED
        pct_s = f"{pct:.0f}" if pct is not None else "n/e"
        out.append(f"  {label:<22s}{shown:>14s}{pct_s:>12s}")
    out.append("")

    deployable = sum(1 for p in space.points if p.deployable)
    out.append(f"  Deployable in this sample   {deployable:,} of "
               f"{space.sampled:,}")
    out.append("")

    for line in wrap_text(
            "A percentile here is a position within THIS sample of THIS "
            "library. It is not a position among products, and the "
            "library is not a market survey. A design in the 90th "
            "percentile for cost is cheap relative to what this model "
            "can build.", 66):
        out.append(f"  {line}")
    out.append("")
    for line in wrap_text(
            "The sample is stratified, not exhaustive and not random. "
            "Random sampling of this space is dominated by its largest "
            "dimension and would report dual-accelerator designs as "
            "typical.", 66):
        out.append(f"  {line}")
    return out
