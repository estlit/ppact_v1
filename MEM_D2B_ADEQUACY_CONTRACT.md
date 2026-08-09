# MEM-D2-B — Target-Rate Memory Adequacy: analysis contract

**Status: CONTRACT. No code changed.**

This document fixes what the adequacy analysis means before any screen
shows it. The order matters here: the same figures, left undefined, would
be read as a latency prediction within a week of being displayed.

---

## 1. The analysis

```
TARGET-RATE MEMORY ADEQUACY
```

Never "memory bottleneck analysis", never "memory latency". Those are
different questions and this analysis answers neither.

---

## 2. What is computed

| Field | Definition |
|---|---|
| `host_bw_required_at_target` | host bytes per job × application target rate |
| `accel_bw_required_at_target` | accelerator bytes per job × application target rate |
| `concurrent_requirement` | the two combined under the declared overlap assumption |
| `effective_bandwidth` | the modelled usable bus rate |
| `headroom` | effective − concurrent requirement |
| `adequacy` | PASS when headroom ≥ 0, FAIL otherwise |

The target rate is an APPLICATION REQUIREMENT. It is never taken from the
evaluated design's delivered throughput or pipeline capacity: doing so lets
a slow design report a small requirement and declare itself uncontended,
which is how the first attempt at this analysis failed.

An application with no declared target produces:

```
Target throughput                   NOT ESTABLISHED
Target-rate bandwidth requirement   NOT COMPUTED
```

Never a substituted rate.

---

## 3. What is NOT computed

```
Actual service bandwidth      NOT ESTABLISHED
Transfer latency              NOT DERIVED FROM THIS ANALYSIS
Issue capability              NOT MODELLED
Burst behaviour               NOT MODELLED
```

The three layers, of which the model has one:

```
1  required bandwidth      minimum to sustain the target      computed
2  issue capability        the most each agent can generate    MISSING
3  allocated service       what the memory system delivered    needs 2
```

Latency needs layer 3. Deriving a transfer time from layer 1 gives

```
transfer = bytes / (bytes × R) = 1 / R
```

so every design would report the same transfer time as every other design
with the same target, whatever its memory. That was computed, observed and
rejected; it is recorded here so it is not rediscovered.

---

## 4. Mandatory wording

**PASS**

> Average bandwidth capacity is sufficient at the application target rate.

**FAIL**

> Average bandwidth capacity is insufficient under the declared
> concurrency assumption.

Both carry, always:

```
Actual service bandwidth   NOT ESTABLISHED
Transfer latency           not derived from this analysis
```

**Forbidden**

```
PASS  ->  "memory is not a bottleneck"
FAIL  ->  "predicted latency failure"
PASS  ->  "this design will meet its target"
```

A capacity floor is not a bottleneck verdict. Burst collisions, memory
latency, imperfect overlap, arbitration delay and host issue limits all sit
outside it, and a design can pass this check and still be memory bound.

---

## 5. The overlap assumption

Overlap is not a latency correction. It is the assumption that decides how
much of each agent's requirement is wanted AT THE SAME MOMENT.

```
concurrent_requirement
    = (1 − overlap) × max(H, A)        + overlap × (H + A)
```

At `overlap = 1.0` both requirements are charged in full — the conservative
end. At `overlap = 0` only the larger applies.

Every screen showing an adequacy result must show:

```
Memory activity overlap assumption   100%
Source                               Model assumption, not measured
```

**It is ASSUMED, never MEASURED.** The model carries no intra-stage time
profile and cannot say what fraction of a pipeline interval the two agents
collide for.

---

## 6. Adequacy stability

A single PASS or FAIL under one assumption is weaker than the assumption
looks. The useful output is how the verdict behaves across the range:

| Class | Meaning |
|---|---|
| **Stable PASS** | PASS at every overlap from 0.25 to 1.00 |
| **Conditional** | The verdict changes within that range |
| **Stable FAIL** | FAIL at every overlap |

`Conditional` is the honest answer for a design whose adequacy depends on a
number nobody has measured, and it must be reported as such rather than
resolved by picking a default.

Measured across the design space:

```
configurations with a target   164,736
adequacy PASS                  145,396
adequacy FAIL                   19,340
within ±5 GB/s of threshold      1,701
```

Those 1,701 are where the overlap assumption decides the answer.

---

## 7. Separation from legacy latency

The two analyses share a screen and must not share authority.

```
Legacy analytical latency
  Memory arbitration   accelerator-priority residual allocation
  Physical realism     NOT ESTABLISHED
  Usable as            an analytical reference figure
  NOT usable as        sensitivity, root cause, or design ranking
```

Neither result proves the other. An adequacy PASS does not validate a
latency figure, and a latency figure does not validate an adequacy verdict.

---

## 8. What the sweep established, stated precisely

Failure rate falls monotonically with effective bandwidth:

```
DDR4 / LPDDR4   18.0%
LPDDR4X         16.7%
DDR5            16.1%
LPDDR5          15.6%
GDDR6           14.7%
HBM2E            9.9%
HBM3E            6.7%
HBM4             3.4%
```

The correct claim:

> The adequacy model exhibits physically plausible monotonic behaviour with
> increasing effective memory bandwidth.

Not: *the model is accurate*. Direction is consistent; magnitude is
uncalibrated, and no measured hardware has been compared against it.

---

## 9. Failure conditions

The analysis is wrong if:

- a target rate is derived from delivered throughput or pipeline capacity
- a latency or transfer time is presented as an output of this analysis
- PASS is worded as an absence of a bottleneck
- FAIL is worded as a predicted latency failure
- an overlap assumption is displayed without its source
- an application without a target is given a substituted one
- a `Conditional` result is reported as PASS or FAIL

---

## What this contract establishes

What the analysis computes, what it refuses to compute, and the exact
wording of both verdicts.

## What it does not

It does not establish a service-rate model, an issue-capability model, an
overlap fraction, or agreement with any real system.

---

*Author: Roger Kim / Copyright (c) 2026 Roger Kim & EdgeChipLab*
