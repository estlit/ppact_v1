# PPACT-D1 — The Analysis Framework, and five axes within it

**Status: FRAMEWORK DEFINITION. No code changed.**

PPACT is one analysis structure applied five times. The axes differ in how
far that structure has been built, not in what the structure is - and
writing this down first is what stops Performance becoming the special axis
that the others are compared against.

Performance happens to be furthest along. That is an implementation fact
about today, not a statement about the framework.

---

## 1. The product boundary

```
Product = one deployed system
```

Every PPACT figure is a system figure. A block does not have a cost, an
area or a power in the PPACT sense; it has a contribution to one.

The exception is throughput, and it is not an exception to the rule so much
as a different question: a block's throughput is the rate it alone could
sustain, and the system's throughput is the LOWEST of them. Both are work
over time; what differs is the scope.

---

## 2. The analysis chain — the same for every axis

```
Product metric
    -> Constraint
    -> Breakdown
    -> Bottleneck
    -> Recommendation
    -> Verification status
```

Every axis has all six. What differs is which stages are IMPLEMENTED,
which are PARTIAL, and which are NOT ESTABLISHED - and a stage that is not
established is still part of the chain, reported as absent rather than
omitted.

**"Complete" is not used for an axis.** Area sums today and will not once
TSVs, chiplets or package substrates are modelled; calling it complete
would make a future addition look like a broken promise. The word used is
`current implementation status`, and it is a statement about today.

### Status vocabulary

```
IMPLEMENTED       the stage produces a figure and a verdict
PARTIAL           the figure exists, the verdict does not
NOT ESTABLISHED   the model does not carry what the stage needs
```

---

## 3. Current implementation status, per axis and per stage

| axis | metric | constraint | breakdown | bottleneck | recommendation |
|---|---|---|---|---|---|
| Performance | IMPLEMENTED | IMPLEMENTED | IMPLEMENTED | IMPLEMENTED | IMPLEMENTED |
| Area | IMPLEMENTED | IMPLEMENTED | IMPLEMENTED | NOT BUILT | NOT BUILT |
| Cost | IMPLEMENTED | IMPLEMENTED | IMPLEMENTED | NOT BUILT | NOT BUILT |
| Power | IMPLEMENTED | PARTIAL (PW-Q1) | NOT ESTABLISHED | NOT BUILT | NOT BUILT |
| Traffic | PARTIAL | NOT BUILT | PARTIAL | NOT BUILT | NOT BUILT |

`NOT BUILT` and `NOT ESTABLISHED` are different states. Area's bottleneck
stage is not built and could be tomorrow; Power's breakdown is not
established and needs a model that does not exist.

### Performance — chain complete

```
figure          delivered throughput 60 inf/s, latency 4.857 ms
decomposition   throughput stations, latency flow (two, and they differ)
constraint      target_inferences_per_s, latency_budget_ms
verdict         MET / VIOLATED, per constraint
```

Two decompositions rather than one, and they name different critical
blocks in 36 of 81 configurations. That is settled and documented in
SF-D1.

### Area — metric, constraint and breakdown implemented

```
figure          Total silicon 255.22 mm2, Board area 220.00 mm2
decomposition   CPU 10.00 + Accel 2.02 + ISP 3.20 = SoC 15.22
                Memory silicon 240.00
constraint      soc_silicon_budget_mm2
verdict         computable
```

The only axis whose block decomposition sums exactly. The SoC budget
governs SoC silicon, NOT total silicon - a DRAM die is not constrained by
an SoC die budget, and attaching it there produced a screen reading EXCEEDS
by 78.4% while the deployment gate correctly said READY.

No board-area budget is declared. Board area is reported and not judged.

### Cost — metric, constraint and breakdown implemented

```
figure          System cost 19.066 USD
decomposition   accelerator silicon + secondary + ISP area x usd_per_mm2
                + CPU silicon + memory package x n
constraint      bom_budget_usd
verdict         computable
```

`Mask/NRE per unit` (348.00 USD) is REPORTED ONLY and deliberately outside
the BOM gate. The engine states why: a team buying an existing SoC pays
none of it and a team taping one out pays it whatever the BOM says, so
charging it to the gate answers a different question than the gate asks.

`Memory cost index` is an index, not USD. It does not belong in a cost
decomposition and must not be summed with the USD terms.

**A correction to an earlier reading of this document's author.** These
three figures were reported as a decomposition that did not sum. They were
never meant to sum: one is amortised over volume, one is dimensionless, one
is a BOM. Reading unlike quantities as a broken total is its own kind of
error.

### Power — metric implemented, constraint partial

```
figure          three, over three windows
                  steady-state average    1.683 W
                  active-window average   3.643 W
                  peak                    NOT ESTABLISHED
decomposition   NOT ESTABLISHED per block
constraint      power_budget_w = 120.0 W, basis NOT ESTABLISHED
verdict         NOT ISSUED
```

The engine's `System power` is `energy / latency` - the average while a job
runs. At 60 inf/s with 4.857 ms latency that covers 4.857 ms of every
16.667 ms and excludes the idle.

The steady-state figure is NOT that scaled by duty cycle: static power does
not stop between jobs. Charged correctly it is 1.683 W; the naive scaling
gives 1.062 W and understates by 37%, worst for the designs that idle most.

**Block-level average power is NOT ESTABLISHED.** Active-state powers exist
per block and do not sum to any system average - CPU 3.200 + memory 3.881 +
compute 0.961 + static 0.877 = 8.919 W against a system figure of 3.643 W.
They are active-state reference values, not a decomposition.

**No verdict is issued** until the library says whether the budget is a
sustained thermal limit or an instantaneous supply limit. Those constrain
different figures above.

### Traffic — one component of ten implemented

The fifth axis, replacing Thermal. Internal data movement quality: what
distinguishes two designs that deliver the same throughput, one running
comfortably and one with every internal path saturated.

Ten components, one implemented - shared memory adequacy, and that
partially. A score built on it would be a memory score under another name,
so none is computed. TR-D1 holds the full inventory.

**Thermal is now a deployment gate**, not an axis. It is computed FROM
power and area rather than chosen, which makes it a verdict on a design
rather than a dimension of one. All nine applications still declare
`thermal_limit_w_per_mm2` and the gate is unchanged.

### Thermal — retained as a gate, no longer an axis

```
figure          Power density 0.007435 W/mm2, Thermal margin 97.52%
decomposition   compute margin 91.99%, memory margin 94.45%
constraint      thermal_limit_w_per_mm2, declared by every application
verdict         computable, once the power basis is fixed
```

Limits are declared for all nine applications and scale sensibly with the
domain: smart camera 0.03, drone 0.06, industrial vision 0.30, datacenter
0.45 W/mm2.

The arithmetic verifies: `0.007435 / 0.3` gives 97.52%, matching the
engine.

**The open question is which power.** `power_density = system_power /
footprint` uses the active-window average, and heat responds to the
steady-state average:

```
active-window   3.643 W  ->  0.00744 W/mm2  ->  margin 97.52%
steady-state    1.683 W  ->  0.00344 W/mm2  ->  margin 98.85%
```

The verdict does not change here and the figure is 2.2x apart. This is the
SAME open question as the power budget basis, which is why both were found
before either was built.

**Margin is not temperature.** A junction figure needs thermal resistance,
ambient and a time-domain power trace. A negative margin means a cooling
assumption was exceeded, not that a temperature was computed.

---

## 4. The two open questions, and that they are one

```
PW-Q1   is power_budget_w a sustained limit or an instantaneous one?
TH-Q1   should power density use the steady-state or active-window power?
```

Both ask which observation window a limit belongs to. Answering one
without the other would leave a thermal margin computed on one basis and a
power verdict on another, in a tool whose whole subject is that a figure
without its window is not comparable to anything.

**Neither axis issues a verdict until both are answered.**

---

## 5. What each axis must always say

| Axis | Never omitted |
|---|---|
| Performance | which constraint, and which of the two decompositions |
| Power | the observation window, and that the budget basis is open |
| Area | that the SoC budget governs SoC silicon, not total |
| Cost | that NRE is outside the gate, and that the index is not USD |
| Traffic | how many of its ten components exist, and that no score follows from one |

Thermal is no longer an axis. As a gate it must still say that margin is
not temperature, and which power the density used.

---

## 6. Failure conditions

The axis presentation is wrong if:

- a block is given a system-level cost, area or power figure
- active-state powers are summed and called a system power
- a power figure appears without its observation window
- `Mask/NRE` is added to the BOM, or the memory cost index is summed
- the SoC silicon budget is applied to total silicon
- a thermal margin is described as a temperature
- a verdict is issued on power or thermal before PW-Q1 and TH-Q1 are
  answered

---

## 7. What is NOT ESTABLISHED

```
Block-level average power decomposition
Peak power
Power budget basis                        PW-Q1
Thermal power basis                       TH-Q1
Board area budget
Agreement with measured hardware, on any axis
```

---

## 8. Build order

**Area first.** Its breakdown sums exactly, its budget is declared, and it
carries no measurement-basis question - so it tests whether the analysis
chain generalises without the test being confounded by an open definition.
If the chain fits Area cleanly, the framework is a framework; if it does
not, that is worth knowing before three more axes are built on it.

**Cost second.** Same shape, with one extra thing to get right: NRE stays
outside the gate and the memory index stays out of the sum.

**Power and Thermal last**, after PW-Q1 and TH-Q1 are answered together.
Building them first would produce two axes whose verdicts rest on a choice
nobody made.

The order is not a ranking of importance. It is the order in which each
axis can be built without inventing something.

---

## What this document establishes

That PPACT is one analysis chain applied five times; which stage of that
chain each axis has reached today; which breakdowns sum; and that two axes
share one unanswered question.

## What it does not

Agreement with real hardware, a block-level power model, a peak power
model, or the answer to PW-Q1 and TH-Q1.

---

*Author: Roger Kim / Copyright (c) 2026 Roger Kim & EdgeChipLab*
