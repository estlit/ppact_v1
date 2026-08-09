# SF-D1 — Performance Constraints for System Flow: definition before display

**Status: DEFINITION ONLY. No code changed.**

The design came from reading System Flow the way a static timing report is
read: paths, slack, a critical path. The analogy shaped the view and its
vocabulary is deliberately not used.

**Why the name was dropped.** A chip designer reads "static timing" as
clock edges, setup and hold, and cycle-accurate paths - none of which
exists here. A system architect reads the same words and imports the same
wrong model.

**The naming that replaced it.**

```
Performance Constraints   the analysis
Throughput constraint     against the application target rate
Latency constraint        against the application latency budget
Slack                     how much room is left in one of them
```

`Constraint` says WHAT is evaluated; `slack` says HOW MUCH is left. The
screen is named for the first: a reader arriving at it wants to know which
requirements are being checked before being handed a margin.

What carries over and what does not still has to be settled, because the
concepts remain even though the name is gone.

---

## 1. What the analogy borrows correctly

| timing report | System Flow |
|---|---|
| a path | a sequence of stations a job passes through |
| a constraint | the application's requirement |
| slack | requirement minus what the path takes |
| the critical path | the path with the least slack |
| a violation | negative slack |

All five have meaning here. The model computes the times and the
application declares the constraints, so slack is arithmetic on figures
that already exist.

---

## 2. What the analogy must NOT borrow

**Setup and hold.** There is no clock edge and nothing arrives too early.
Borrowing the words would import a failure mode the model does not have.

**Cycle-accurate anything.** Station times are analytical estimates over a
whole job, not per-cycle behaviour.

**The name itself.** See above.

**A single path.** STA has one timing graph. This model has TWO, and they
disagree - which is the substance of section 3.

**Path exhaustiveness.** STA enumerates every path. Here the paths are the
two the model computes; there is no search, and none is claimed.

---

## 3. TWO timing graphs, not one

This is the finding that makes the analogy non-trivial.

**The latency path** — one job, end to end, against the latency budget.

```
industrial_vision / npu_32x32 / LPDDR5 x2 / isp_assisted

host active        1.947 ms
accelerator core   2.910 ms
                   -------
total              4.857 ms      budget 20 ms      slack +15.143 ms
```

**The throughput path** — steady state, each station against the interval
the target rate demands.

```
target 60 inf/s  ->  required interval 16.667 ms

station           time      capacity      slack     slack%
host              1.947 ms  513.6 inf/s   14.720    88.3
accelerator       2.519 ms  397.0 inf/s   14.148    84.9
ISP              10.027 ms   99.7 inf/s    6.640    39.8   <- least
shared memory     1.563 ms  639.6 inf/s   15.103    90.6
```

**They do not share stations.** The ISP has the least throughput slack and
does not appear in the latency path at all; shared memory is a throughput
station and correctly not a latency stage.

An STA report has one critical path. This system has two, and they can name
different blocks. A view that reported one "critical path" would be picking
one of two answers and hiding the choice.

**Not from one example.** VD-1 requires structural coverage rather than a
demonstration, so the throughput-critical station was measured across 81
configurations spanning every application with a declared target, three
accelerator classes and three preprocessing modes:

```
accelerator     42
shared memory   28      not a latency stage
ISP              8      no box in the latency flow
host             3
```

**Thirty-six of eighty-one are throughput-critical on a block the latency
flow does not draw.** The disagreement is a property of the model, not of
the example that first showed it - which is the check the retracted PB-D1
claim did not perform.

---

## 4. Slack: the definitions

**Throughput slack**, per station:

```
required_interval = 1000 / target_rate
slack = required_interval - station_time
```

Negative means the station cannot sustain the target rate on its own.

**Latency slack**, per path:

```
slack = latency_budget - total_path_time
```

Negative means the job does not finish in time.

**Not defined: latency slack per station.** Splitting a path's slack across
its stations requires deciding how much of the budget each one owns, and
nothing in the model says that. A per-station latency slack would be an
allocation invented at display time - the shape that made `host_demand`
unusable.

---

## 5. What may be called critical

```
throughput-critical station   least throughput slack
latency-critical path         least latency slack
```

Never "the critical path" unqualified. The two may name different things,
and in the measured case above they do: the ISP is throughput-critical and
appears nowhere in the latency path.

---

## 6. What is computable today

**Computable**

- throughput slack per station, in ms and as a percentage
- latency slack for the job path
- which station is throughput-critical
- violations: negative slack on either

**Not computable**

- per-station latency slack (no budget allocation exists)
- path enumeration (there are two paths, not a searched set)
- setup/hold equivalents (no clock)
- worst-case versus typical (one estimate, no distribution)
- slack under contention (the arbitration rule is MEM-ARB-001)

---

## 7. What the screen may and may not say

**May**

```
Throughput slack   ISP  +6.640 ms of 16.667 ms required   39.8%
                   least slack of four stations
Latency slack      +15.143 ms of 20 ms budget
Throughput-critical station   ISP
Latency-critical path         host active -> accelerator core
```

**May not**

```
Critical path: ISP                    unqualified, and the ISP is not on
                                      the latency path
Setup slack / hold slack              there is no clock
host active slack +8.1 ms             per-station latency slack is not
                                      defined
Slack under contention                arbitration is not established
```

Every slack figure names WHICH constraint it is against. A slack without
its constraint is a number with no meaning.

---

## 8. Failure conditions

The view is wrong if:

- a single critical path is reported
- throughput slack and latency slack are compared or added
- a per-station latency slack appears
- setup, hold or clock language appears
- a slack is shown without naming its constraint
- an application with no target or no budget is given a slack anyway
- a station absent from a path is given that path's slack

---

## 9. Recommendation

Implement both slacks, side by side, **named apart**, with the critical
station and critical path reported separately and the fact that they can
differ stated on the screen rather than left for the reader to notice.

The value of the analogy is not the vocabulary - which is why the
vocabulary was dropped. It is that timing engineers already expect slack to
be against a named constraint, and expect a report to say which path it is
talking about. Those two habits are what this view borrows.

---

## What this document establishes

That both slacks are computable, that there are two timing graphs rather
than one, and that per-station latency slack is not defined.

## What it does not

It does not establish agreement with measured hardware, a contention-aware
slack, or that either path is exhaustive.

---

*Author: Roger Kim / Copyright (c) 2026 Roger Kim & EdgeChipLab*
