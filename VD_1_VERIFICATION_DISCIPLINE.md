# VD-1 — Verification Discipline: why one example is not a check

**Status: DISCIPLINE DOCUMENT. It changes no code and constrains every
future change.**

This is not a testing guide. It is a record of how wrong claims were made
in this project, written because the same shape produced them each time and
recognising the shape is cheaper than rediscovering it.

---

## 1. The failure

```
verified on one example  ->  stated as general
```

Every instance below passed its example. That is what made each of them
survive: a claim that fails its own demonstration gets noticed
immediately.

**The configurations where a derivation breaks are the ones nobody picks as
an example.** An example is chosen because it is simple, and simple means
the interacting parts are absent.

---

## 2. What happened, four times

### PB-D1 block capacity

```
claimed   capacity = 1000 / flow_station_ms reproduces the engine's
          pipeline capacity exactly
checked   cpu_only
result    118.01 against 118.01, identical

reality   isp_assisted   343.67 against 99.73
          isp_and_npu    343.67 against 99.73
```

The ISP sets the pipeline rate and has no box in the latency flow. In
`cpu_only` the ISP is idle, so the slowest drawn station happened to also
set the rate. **The agreement was a property of the example, not of the
derivation.**

### MEM-D2 contention

```
claimed   no configuration is contended at its application target
checked   six configurations
result    all PASS, headroom at least 58 GB/s

reality   19,340 of 164,736 configurations FAIL
```

Six were chosen and all six were roomy. The sample produced the
conclusion.

### MEM-ARB-001 host demand

```
claimed   demand-proportional sharing is the right fix
checked   the arithmetic, on paper
result    the formula is standard and correct

reality   host_demand = bytes / compute_time is not a demand. Capping the
          host there makes transfer = compute identically:
          7.2392 ms and 7.2392 ms to four decimals
```

The policy was right and the input was not. Reasoning about a formula is
not checking its inputs.

### R14 station check

```
claimed   no stage appears that the model does not compute
written   compare flow.stations against STATION_ORDER

reality   build_flow ITERATES STATION_ORDER, so the check compared a
          list against itself and could never fail
```

A tautology passes every example.

---

## 3. Why examples are unrepresentative

An example is chosen to be clear. Clarity comes from absence:

```
cpu_only         the ISP is idle, so one station set is a subset of the
                 other and two decompositions look like one
six roomy cases  contention never arises, so an arbitration rule is
                 never exercised
a formula        inputs are symbols, so a symbol that means the wrong
                 thing looks like any other symbol
```

In every case the thing that would have exposed the error was the thing
the example was chosen to avoid.

---

## 4. What counts as verification

A single agreeing case is **not** verification. It is a demonstration that
the claim is not obviously false.

Verification requires, at minimum:

**Coverage of the structural classes.** Not more cases - DIFFERENT ones.
Twenty `cpu_only` configurations would not have caught the capacity error;
one `isp_assisted` would.

**A negative control.** A rule that has only seen correct inputs is not
known to work. R14's station check passed everything until a fabricated
stage was injected into the output - and even then the first control
failed to produce one, because it changed a constant the renderer read
rather than the output the rule inspected.

**An independent oracle.** The derived figure must agree with something the
model computes another way. `capacity` now agrees with `Pipeline capacity`;
`host_demand` had nothing to agree with, and its circularity surfaced only
when someone used it.

**Execution, not inspection.** R2 confirmed `build_review` appeared in the
source and the call raised `TypeError` the moment it ran. Seeing a call is
not seeing it succeed.

---

## 5. Where a claim belongs

```
a sentence in a document   nobody re-runs
a rule in a suite          runs on every change
```

PB-D1 said the capacity derivation was verified. That sentence was true of
one configuration on the day it was written and stayed on the page while
becoming false. Moving it into a contract rule made it fail on two of three
preprocessing modes the moment it existed.

**A verification claim that lives in prose is a claim nobody checks.**

---

## 6. Required practice

Before a derived quantity is displayed:

1. State what it means in words that do not mention how it is computed. If
   the only available description is the formula, the quantity has no
   meaning yet - that is what `host_demand` was.
2. Name an independent quantity it must agree with.
3. Run the agreement across every structural class, not every example.
4. Write it as a rule, not as a sentence.
5. Break the rule deliberately and confirm it fails.

Before a general claim is made from evidence:

1. State how many cases were examined and how they were chosen.
2. State which classes were absent.
3. If the sample was convenient rather than designed, say so in the claim.

---

## 7. Wording

**Not permitted**

```
verified          from one case
always            from a sample
the model does X  from an example where X held
```

**Required**

```
verified across <classes>, failing in <n> of <m>
observed in <n> configurations of <m>; <class> was not represented
NOT ESTABLISHED
```

The last one is not a hedge. It is the accurate statement whenever
verification has not been performed, and it costs nothing to write.

---

## 8. What this document does not claim

It does not claim these are all the errors, nor that the practice above
would have caught all four - the `host_demand` case needed someone to ask
what a name meant, and no procedure enforces that.

It does not claim the current suites are sufficient. They are what has been
written down so far.

---

## What this establishes

That four wrong claims in this project shared one shape, and what the shape
is.

## What it does not

That recognising the shape prevents it. This document is a record, not a
guarantee.

---

*Author: Roger Kim / Copyright (c) 2026 Roger Kim & EdgeChipLab*
