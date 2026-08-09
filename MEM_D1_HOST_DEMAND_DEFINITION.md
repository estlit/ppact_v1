# MEM-D1 — Host Memory Demand: definition before arbitration

**Status: DEFINITION ONLY. No code changed.**

This document exists because a fix was written and reverted. The fix was
demand-proportional bandwidth sharing, which is the right policy and was
applied to the wrong quantity: what the model calls `host_demand` is not a
demand. Defining it is a prerequisite, not a refinement.

---

## 1. What host memory traffic is made of

Measured, `industrial_vision` on `cortex_a78_x4 / npu_32x32 / LPDDR5 x2`,
`cpu_only`:

```
host preprocess traffic      140.378 MB
host postprocess traffic       0.002 MB
Host DRAM traffic            140.380 MB
```

Preprocessing is essentially all of it. Postprocessing is four orders of
magnitude smaller and does not affect any conclusion here.

**What the model does not separate.** Reads from writes; input fetch from
intermediate spill; CPU-issued traffic from DMA. These are one number.

---

## 2. What `host_demand` is today, and what it is not

```python
host_demand = cpu_dram_bytes / cpu_compute_s
```

Read plainly: *the rate at which the host's transfers would finish exactly
when its compute finishes.*

That is a **balance point derived from compute time**, not a property of
the host's memory system. The name says demand; the arithmetic says
break-even.

The consequence is not subtle. Cap the host at it and

```
transfer = bytes / (bytes / compute) = compute
```

identically. Applied, it produced:

```
host compute    7.2392 ms
host transfer   7.2392 ms
```

to four decimals, on a design where the two have no reason to agree. The
host becomes incapable of being memory bound however narrow the bus.

**By contrast** the accelerator's figure is a genuine rate:

```python
accel_demand = dram_bytes / core_time
```

`core_time` is the arithmetic time the array needs, computed from the array
and the workload without reference to memory. Bytes over that is what the
accelerator would pull if nothing stopped it.

**The two are not the same kind of quantity, and dividing a bus between
them is dividing unlike things.**

---

## 3. Candidate definitions for `H`

None of these is chosen here. Each implies a different arbitration result.

| Candidate | Meaning | Available today |
|---|---|---|
| **H1 CPU issue ceiling** | Peak rate the cores can generate — outstanding misses × line size ÷ latency | **No.** No memory-level-parallelism or miss-latency data in `CPU_LIBRARY` |
| **H2 Workload average** | `bytes ÷ the interval over which they are moved` | Partly — bytes are known, the interval is the open question (§4) |
| **H3 Burst rate** | Peak within preprocessing, higher than the average | **No.** No intra-stage time profile |
| **H4 Steady-state requirement** | `host bytes/job × pipeline rate` | Yes, and it needs no overlap fraction |
| **H5 Break-even (current)** | Rate making transfer equal compute | Yes, and it is circular |

`H1` is what an architect usually means by demand. `H4` is what a
throughput model can actually support. `H5` is what is implemented.

---

## 4. The time axis — and a finding that changes the question

`H` is bytes ÷ **an interval**, so the interval must be named.

Measured on the same configuration:

```
1 / latency              86.78 inf/s
Pipeline capacity       118.01 inf/s
```

Capacity exceeds the reciprocal of latency, which is only possible if
**stages already overlap across jobs**. The model is a pipeline, not a
sequence: while the accelerator works on frame *n*, the host is preparing
frame *n+1*.

This matters more than the arbitration policy:

- If the model were **serial**, the host and accelerator would never
  contend, and a faster accelerator could not slow the host at all. The
  present behaviour would be a plain defect.
- Because it is **pipelined**, contention is real and some sharing rule is
  required. The question is which, not whether.

**What is not established** is the OVERLAP FRACTION. Two stages both being
active in steady state does not mean their memory requests coincide
continuously. The model has no intra-stage time profile, so it cannot say
whether they collide for all of the interval or a tenth of it.

Full concurrency is the conservative end of that range. It should be
labelled as an assumption, not reported as a result.

---

## 5. Semantic equivalence: the actual blocker

Before any policy can be applied:

```
H and A must be rates over the SAME interval,
measured on the SAME basis,
neither derived from the other's timing.
```

Today:

```
A   bytes ÷ arithmetic time      independent of memory
H   bytes ÷ host compute time    a break-even point
```

`A` is a demand. `H` is a balance condition. **This is the blocker**, and
no arbitration policy resolves it.

---

## 6. Arbitration policies — deferred

Not a choice to make yet. Recorded so the sequence is clear:
proportional sharing, weighted QoS, host priority, accelerator priority,
time-division. Each is defensible once `H` and `A` mean the same thing;
none is defensible before.

Note that the reverted attempt was **proportional sharing**, and it failed
not because the policy was wrong but because its input was.

---

## 7. Inputs that would be needed

For `H1`, the honest target:

```
outstanding misses per core        not in CPU_LIBRARY
memory latency per technology      not in MEMORY_LIBRARY
line size                          not modelled
prefetch effectiveness             not modelled
```

For `H4`, reachable with what exists:

```
pipeline interval                  available
host bytes per job                 available
overlap fraction                   NOT ESTABLISHED
```

`H4` is achievable. `H1` requires library extensions that would themselves
need calibration.

---

## 8. What is and is not computable today

**Computable now**

- Host bytes per job, split into preprocess and postprocess
- Accelerator bytes per job
- Accelerator demand rate on an independent basis
- Pipeline interval and steady-state capacity
- Effective bus bandwidth

**Not computable**

- A host demand rate independent of host compute time
- The overlap fraction between host and accelerator memory activity
- Burst behaviour within a stage
- Read/write asymmetry, DMA share, prefetch effect
- Whether any arbitration result matches real silicon

---

## 9. The defect this document blocks

```
MEM-ARB-001
old policy      accelerator-priority residual allocation
observed        H 19.39 + A 56.68 = 76.07 against B 73.73 (3.2% over)
                host allocation 19.39 -> 9.64 GB/s (50% cut)
                a faster accelerator makes the design 59% SLOWER
attempted       demand-proportional fair sharing
reverted        its input is not a demand
blocked on      this document, then a chosen H
```

Below the contention threshold the old rule returns the right answer. That
is worse than being wrong everywhere: it looks correct until it does not.

---

## 10. Recommendation

**Pursue H4**, the steady-state requirement, as the first honest
definition. It is computable from quantities the model already has, it is a
rate over a named interval, and it does not reference host compute time.

**Correction to an earlier draft of this document.** H4 does NOT require an
overlap fraction to be computed:

    H4 = host bytes per job x pipeline rate

is a complete definition on its own. The overlap fraction is needed one
step later, when asking how much of the time H4 and A4 want the bus AT THE
SAME MOMENT. Conflating the two made a computable quantity look blocked on
an unmeasurable one.

The pipeline stages are therefore:

    host steady-state requirement          H4
    accelerator steady-state requirement   A4
    concurrent portion                     overlap fraction (ASSUMED)
    simultaneous demands                   f(H4, A4, overlap)
    arbitration                            applied to those

**And A must move with H.** Redefining the host on a steady-state basis
while leaving the accelerator at `bytes / arithmetic time` swaps one
mismatch for another: one rate over a pipeline interval, one over an ideal
issue window. If H becomes steady-state, so must A.

Name it `host_steady_state_bw_required`, not `host_demand`. "Demand" is
what H1 means - the rate the cores could issue - and reusing the word for a
throughput requirement is how the present confusion began.

**H1 is the better definition and is not reachable** without library work
that would need its own calibration against measured hardware — which this
project does not have and has never claimed.

---

## What this document establishes

That `host_demand` is misnamed, that the pipeline overlaps, and that
arbitration cannot be fixed before `H` is defined.

## What it does not

It does not choose `H`. It does not establish an overlap fraction. It does
not establish that any candidate matches real hardware. Sensitivity and
root-cause figures remain **STALE** under the current policy.

---

*Author: Roger Kim / Copyright (c) 2026 Roger Kim & EdgeChipLab*
