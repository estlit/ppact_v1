# Methodology

The authoritative technical document. What the model computes, from what,
under which assumptions, and what has and has not been established about it.

## Analytical model structure

The Studio is analytical, not cycle-accurate. A design is evaluated by
composing station models:

    host        cycles and DRAM traffic, with a stated compute/transfer overlap
    ISP         an optional preprocessing block with its own time and area
    accelerator a roofline: arithmetic against delivered bandwidth
    memory      capacity, peak and effective bandwidth, energy per bit
    package     footprint, power density, cooling class

Power, area and cost are ADDITIVE across blocks. Performance is a BOTTLENECK
— a minimum, from the roofline — and thermal is a SPATIAL property of where
the heat leaves the package. Summing all five is the classic modelling error
and the model does not do it.

## Metric boundary contracts

Twelve contracts across five families state, for every reported figure, which
stages it covers and which it excludes. They are checked bidirectionally:
anything declared in scope must be accounted for, and anything declared out
of scope must exist somewhere in the stage list.

This exists because a defect was found that 3,000 other checks had missed: an
ISP station of 10 ms sat inside a `Sensor-to-control` figure of 4.66 ms.
Every check compared numbers with numbers; none compared a number with its
own name.

## Latency and throughput

One job's latency decomposes into terms that sum exactly:

    Latency = host active
            + preprocessing offload
            + offload overhead
            + accelerator core
            + engine hand-off

Verified to zero residue across 180 configurations spanning every
application, engine, preprocessing mode and single or dual accelerator. Where
the residue is not zero it is printed and labelled a defect.

Throughput is a separate question. Pipeline capacity is set by the slowest
station's interval, not by the total latency, so a pipelined design can
deliver more than one over its latency. Delivered throughput is the smaller
of capacity and the arrival rate.

## Power, energy, area, cost and thermal

Power is the sum of host active power, accelerator active power, memory power
and static leakage. Energy per inference is system power multiplied by the
job's time, which is why a part drawing 2x the power and finishing in 1/4 of
the time uses less energy.

Area is absolute silicon across host, accelerator and every memory die, not
area per unit of bandwidth. That normalization is what makes a stacked memory
look small.

Cost is a per-unit bill of materials. Mask sets and development effort are
modelled separately and amortized over volume, because a mask set is not a
cost per unit.

Thermal is power density against the cooling class the design assumes. A
cooling-class failure is a CLASS mismatch and is not fixable by reducing
power.

## Input assumptions

- Compute and DRAM traffic overlap with a stated ratio rather than perfectly.
- Activation reload factor = working set / on-chip SRAM. A coarse stand-in
  for real tiling, and the term that makes buffer size matter.
- Budgets, energy per MAC, package costs and stack yields are engineering
  estimates from public material, not vendor data. They are meant to be
  edited.

## Estimated industrial classes

The accelerator and memory libraries contain architectural CLASSES, not
products. Each is declared in a versioned registry carrying its domain, the
evidence the estimate rests on, and which parameters are estimates.

No class carries a confidence above `medium`. No vendor publishes enough for
any figure in the library to be checked, and claiming otherwise would be the
failure the registry exists to prevent.

## Published, estimated and unknown

Industrial profiles used as validation evidence classify every fact:

    published   the vendor states it, in public, in words
    estimated   derived here from something published, and labelled
    unknown     not stated, and NOT filled in

Unknown fields stay empty. A profile with an invented number reads exactly
like a profile with a measured one, and the difference is invisible to
everybody downstream.

Comparative claims without a named baseline are excluded from evidence. So
are comparative claims whose baseline IS named but was measured by the
claimant: a benchmark of a rival, run by the rival's competitor, is not a
neutral measurement.

## Architecture Balance normalization

Five axes, each mapping a physical quantity onto 0 to 100, outward
favourable:

| Axis | Source metric | Unit | 0 at | 100 at |
|---|---|---|---:|---:|
| Performance | Throughput | inferences per second | 1 | 1000 |
| Power | Energy per inference | mJ | 2000 | 1 |
| Area | Total silicon | mm2 | 4000 | 10 |
| Cost | System BOM | USD | 20000 | 10 |
| Thermal | Power density | W per mm2 | 1 | 0.005 |

All five are logarithmic:

    score = clip(100 x (log10(value) - log10(at_zero))
                       / (log10(at_hundred) - log10(at_zero)), 0, 100)

The normalization happens once, in the builder, and each axis carries the
formula that produced it. Terminal, PNG and web renderers take the same
object; none of them computes.

A known educational weakness: the log scale compresses a 6x cost increase
into roughly 24 points. This has not been changed, because changing the
formula and the chart's role at the same time would make it impossible to
attribute what a reader is seeing.

## Axis ranges and clipping

A value outside its range is CLIPPED to 0 or 100 and marked `100+` or `0-`.
The design is further along than the chart can show, and reading a clipped
score as the best attainable would be wrong.

Where two designs score the same on every axis, the chart states that a
single line is drawn where the legend shows two.

The balance chart does not show physical values, requirement limits,
bottlenecks, or the reasons for change. That is not a caveat: an
information-transfer experiment put five design questions to it and it
answered none of them.

## Sensitivity analysis

Six assumptions are moved across their plausible ranges and the DIRECTION of
each conclusion is checked at every point. A grade names the number of runs,
the number of reversals, and which assumption caused them.

A conclusion that reverses inside the range is reported as such and the
assumption is named — that conclusion is a property of the assumption as much
as of the design.

## Validation layers

Three layers, and they are not interchangeable:

1. **Analytical invariants** — closed-form arithmetic and identities. Says
   whether a number is right. Cannot be regenerated.
2. **Golden scenarios** — fixed expected behaviour for representative
   designs. Says whether a change is right. Cannot be regenerated.
3. **Regression snapshot** — 1,296 configurations. Says only that something
   changed. CAN be regenerated, which is why it is not evidence of
   correctness on its own: an intended change followed by regenerating the
   baseline would approve a wrong result with the same keystroke.

Mutation testing disables each guard in turn and requires that a check
notices. A detector that has never fired is not known to work; every one
added since has been given input it must reject, as a positive control.

## Reproducibility

The certification writes source checksums, a coefficient snapshot and a
fingerprint, and grades a rerun R2 to R4 by how much of the environment
differed. An environment difference is the CONDITION of the test, not a
failure.

R4 evidence exists for engine 3.82.0: Linux to Windows, Python 3.12 to 3.13,
with every substantive check matching. Reproduction certifies the release
that was run, so later releases carry their own grade.

## Assumptions worth challenging

- The overlap ratio between compute and transfer is a coefficient, not a
  measurement.
- Accelerator utilization figures are engineering estimates.
- The LLM serving efficiency bracket is 0.28 to 0.64 with the precision
  unstated.
- Production volumes and mask costs move break-even conclusions and are the
  least well-grounded inputs in the model.

## Reserved, not active

`ppact/compute.py` ends with a `RESERVED_COMPUTE` placeholder for
compute-in-memory designs, deliberately not merged into the library, so
nothing in the model sees it and no result changes.

The reason it is parked rather than filled in: the area model assumes the MAC
array and the SRAM are separate blocks, which is exactly what a
compute-in-memory design stops being. The arithmetic happens inside the
bitcell array, so adding the two areas would count the same silicon twice.

## Starting points, not recommendations

PPACT Studio does not recommend architectures. It provides measured
comparisons against a starting point so that engineering trade-offs can be
interpreted consistently. Every architecture is evaluated using the same
analytical model.

A starting point is a predefined initial architecture used only to make
measured changes easier to interpret. It is not a recommendation, not an
optimal design, and not a target architecture.

## Known limitations

- No interconnect term. A host-attached accelerator over PCIe or USB has no
  link in the model, so the link cannot become the bottleneck.
- No chiplet or multi-die structure. A single logic node is assumed.
- No rack scale. A design is a single device.
- No structured sparsity. Arithmetic is dense; sparse work is data-dependent
  and the model is deterministic.
- No multi-partition execution or virtualization.
- Precision is a property of the engine, fixed at design time. One part
  supporting several formats at different rates is not expressible.
- Host connection is declared and NOT modelled. It is
  informational only: no latency, bandwidth, power, cost or gate
  reads it, and a check requires every metric to be identical at
  every setting. See HELP.md.

## Not established

- **Measured hardware accuracy.** Eleven vendor figures, no measured
  hardware. No amount of internal work raises this.
- **Educational effectiveness.** Needs the same people with and without the
  tool, and a control. This package checks that an answer is present,
  specific and correct against the engine; whether a person understands it is
  a question about people.
- **Independent external validation.** Needs a predictor who does not run the
  engine.
- **Commercial product equivalence.** The Studio does not model commercial
  products and cannot be checked as though it did.

**Logic die cost boundary (CO-BOUNDARY-001).** The metric declares
`includes=("accelerator", "secondary accelerator", "host cpu", "isp")` and
computes only the first three. The two differ by the ISP term, 0.2489 USD
on a representative design. Neither is changed: which one carries the
intent is not recoverable from either. `System cost` includes the ISP
directly and is unaffected.

**Terminal column width (WF-WIDTH-001).** Eighteen of thirty menu tasks
print at least one line past 78 columns; the widest is 218, a comparison
table with one column per memory technology. The contract suite measured
the limit on one screen and the workflow suite measures all thirty, which
is how the other seventeen surfaced.

**Power budget basis (PW-Q1).** The library declares
`power_budget_w = 120 W` and does not say whether it is a sustained
thermal limit or an instantaneous supply limit. Those constrain different
figures - the steady-state average, 1.683 W, and a peak that is not
computed - so no power verdict is issued.

**Thermal power basis (TH-Q1).** `power_density = system_power / footprint`
uses the active-window average, and heat responds to the steady-state
average. On the same design the two give 0.00744 and 0.00344 W/mm2, a
factor of 2.2. The verdict does not change there and the basis is still
unstated, so it is recorded rather than chosen.

These two are the same question - which observation window a limit belongs
to - and are answered together or not at all.

**Host memory demand.** The model has no quantity describing how much
memory bandwidth the host would draw if nothing stopped it. What it
computes is

    host_demand = host_bytes / cpu_compute_time

which is the rate at which transfers would finish exactly as compute
finishes - derived from the compute time, not from anything the host can
pull. It reads like a demand and is not one.

This was found while trying to replace the bandwidth arbitration rule.
Feeding that quantity into a demand-proportional split made host transfer
time equal host compute time to four decimal places, identically, because

    transfer = bytes / (bytes / compute) = compute

so the host could never be memory bound whatever the bus was. The change
was reverted and all 1,296 configurations returned to their previous
values.

**Memory arbitration (KNOWN DEFECT MEM-ARB-000).** The accelerator takes
the rate its own work implies and the host receives the remainder. There
is no host demand cap, so a small aggregate over-demand starves the host
disproportionately: an NPU 32x32 design at H 19.39 + A 37.80 = 57.19 GB/s
sits under a 73.73 GB/s bus, and the same design with an NPU 64x64 asks
76.07 GB/s - 3.2% over - and the host's allocation falls from 19.39 to
9.64 GB/s. The result is a design that gets 59% SLOWER for a faster
accelerator.

This is recorded rather than corrected. No arbitration rule can fix
arbitration performed on a quantity that is not a demand; the host demand
model has to exist first. Until then, sensitivity figures computed
across memory-contended configurations are STALE.

**Unified multi-runtime launcher.** The program includes two launchers, for a
terminal session and for Colab. There is no single entry point that detects
its runtime, and no Streamlit execution path: the string "streamlit" does
not appear anywhere in this package. Whether one launcher could serve
terminal, Jupyter, Colab and Streamlit identically has not been tried, so
nothing is claimed about it.

**Host memory demand.** The model has no figure for how much memory
bandwidth the host requires. What it calls `host_demand` is
`cpu_dram_bytes / cpu_compute_s` - the rate at which transfers would finish
exactly when compute finishes. That is a balance point derived FROM compute
time, not a property of the host, and the two are different quantities
wearing one name.

The consequence is measurable. Capping the host at that figure makes

    transfer = bytes / (bytes / compute) = compute

identically, so the host can never be memory bound however narrow the bus.
Applied, it produced host compute 7.2392 ms and host transfer 7.2392 ms to
four decimals on a design where they have no reason to agree.

**Memory arbitration.** The current rule gives the accelerator the rate its
own work implies and hands the host what is left. It has no host demand
cap, and a small aggregate over-demand collapses the host's share:

    NPU 32x32   H 19.39 + A 37.80 = 57.19  <= B 73.73
    NPU 64x64   H 19.39 + A 56.68 = 76.07  >  B 73.73   (3.2% over)
                host allocation 19.39 -> 9.64 GB/s      (50% cut)

Three percent of over-demand takes half the host's bandwidth, and the
design comes out 59% slower for a faster accelerator. This is a known
defect. Demand-proportional sharing was written and reverted, because
arbitrating a quantity that is not a demand replaces one unphysical rule
with another that is harder to see. It is blocked on a host memory demand
model, and until then no sensitivity or root-cause figure computed under
this policy may be used.

**Streamlit compatibility.** Not implemented and not tested. A release note
saying "Streamlit supported" would be a plan rather than an observation,
which is the distinction this project has held to throughout.
