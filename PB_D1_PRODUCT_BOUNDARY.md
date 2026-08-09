# PB-D1 — Product Boundary and Block Capacity: definition before display

**Status: DEFINITION, REVISION 2. Section 4 was wrong and is corrected
below. The original claim is kept, not deleted.**

The proposal is not a chart. It is a claim about what a PPACT figure
belongs to, and the claim has to be settled before anything is drawn:
otherwise a block ends up with a "throughput" that is a system quantity
wearing a block's label, which is how `host_demand` came to mean a balance
point.

---

## 1. Product boundary: what it is

A **product** is a thing that is sold, budgeted and judged as a whole.

```
System product      the SoC or board a customer deploys
Component product   a part bought or built to go inside one
```

The consequence for PPACT: **a product has one figure per axis.** A system
has one delivered throughput, one system power, one system cost. A
component has its own five, which are different numbers about a different
product.

A **block** is neither. It is a stage inside a system, and it is the source
of the confusion this document exists to end.

---

## 2. Which figures belong to which boundary

**System product — all five axes present today.**

```
Performance   Delivered throughput 60 inf/s   Latency 11.523 ms
Power         System power 3.51 W
Area          Total silicon 252 mm2   Board area 180 mm2
Cost          System cost 18.82 USD
Thermal       Thermal margin (%)   Power density (W/mm2)
```

These already behave as product figures: the deployment gate uses them and
nothing else.

**Component product — the values exist, the evaluation does not.**

```
npu_32x32   peak TOPS  ·  cost 9.0 USD  ·  module max power 4.0 W
            package footprint 40.0 mm2  ·  SRAM 1024 kB
```

There is `evaluate_system`, `evaluate_proposal`, `evaluate_wafer` - and no
`evaluate_component`. Component values are INPUTS to a system calculation
and are never assembled into a product view of the component itself.

**Block — not a product, and must not be given product figures.**

---

## 3. What a block may have

Not throughput. A block does not deliver anything to a customer; the
system does.

| Quantity | Meaning |
|---|---|
| **Capacity** | the rate this block alone could sustain |
| **Busy** | the fraction of wall time it is working |
| **Idle** | not working, and not prevented from working |
| **Waiting** | not working because something else has not finished |

`Capacity` is a block property. `Throughput` is a system result. Naming a
block's capacity "throughput" invites the reader to compare two blocks'
throughputs and conclude something about the product, which is exactly
backwards.

---

## 4. What is derivable today, and the arithmetic

### RETRACTED — the original claim

> **Block capacity — derivable and verified.**
>
> ```
> capacity(block) = 1000 / station_time_ms
>
> host active         8.474 ms  ->  118.01 inf/s
> slowest station     118.01 inf/s
> pipeline capacity   118.01 inf/s      identical
> ```
>
> The derivation reproduces the engine's own pipeline capacity exactly,
> which is the check that matters.

**This was checked on ONE configuration and generalised.** It is false.

```
cpu_only       slowest FLOW station 118.01 inf/s   pipeline 118.01   agrees
isp_assisted   slowest FLOW station 343.67 inf/s   pipeline  99.73   does not
isp_and_npu    slowest FLOW station 343.67 inf/s   pipeline  99.73   does not
```

The agreement in `cpu_only` was a coincidence: the ISP was idle, so the
station that sets the rate happened to also be the slowest one drawn.

### The cause: two different decompositions

The engine computes its rate from FIVE stations, and the latency flow draws
a different set:

| | latency flow | throughput |
|---|---|---|
| host active | yes | yes |
| preprocessing offload | yes | folded into ISP |
| offload overhead | yes | folded into accelerator |
| accelerator core | yes | yes |
| engine hand-off | yes | folded into accelerator |
| **ISP** | **no** | **yes** |
| **shared memory** | **no** | **yes** |

```
isp_assisted   ISP active   10.027 ms   sets the pipeline interval
               slowest drawn station     2.910 ms
```

The ISP sets the system rate and has no box in the flow at all. Shared
memory is likewise a throughput station while being, correctly, not a
latency stage - the same component is a station in one view and not in the
other, and that is not a contradiction.

### The corrected definition

Capacity comes from the ENGINE'S OWN throughput stations, now exported as
`Throughput stations (s)`, and is not derived from flow station times.

```
capacity(block) = 1000 / throughput_station_ms

cpu_only       host  8.474 ms -> 118.01 inf/s   pipeline 118.01   agrees
isp_assisted   ISP  10.027 ms ->  99.73 inf/s   pipeline  99.73   agrees
isp_and_npu    ISP  10.027 ms ->  99.73 inf/s   pipeline  99.73   agrees
```

Verified on all three, and the verification is now a contract rule rather
than a sentence in a document.

**Busy — derivable, from the same corrected station list.**

```
busy(block) = throughput_station_ms x delivered_rate / 1000

isp_assisted   host 11.7%   accelerator 15.1%   ISP 60.2%
               shared memory 9.4%
```

**Utilisation of the shared memory — derivable.**

```
utilisation = concurrent_requirement / effective_bandwidth
```

Already computed by the memory analysis under its declared overlap
assumption.

---

## 5. What is NOT derivable

**Idle versus Waiting.** Their sum is `1 - busy` and the split is not
computable: separating them needs the REASON a block is not working, and
the model carries no dependency state. Reporting either alone would be
inventing the split.

**Overflow and Starvation.** These need a queue between blocks - arrival
rate against service rate, and a policy for what happens when they differ.
The model has no queues.

**Component product evaluation.** No entry point exists. The values are
there; assembling them into a component's own five axes is new work, not a
new view.

**Waiting attribution.** Which block a waiting block is waiting FOR is a
dependency graph the model does not have.

---

## 6. The derivation's assumption, stated

`capacity = 1000 / throughput_station_time` reads as *the rate this block
would sustain if it were the only thing running.*

That is an assumption, and it is the same SHAPE as the one that made
`host_demand` unusable: a rate back-computed from a time.

It differs in being checkable - the slowest block's capacity equals the
engine's independently computed pipeline capacity - and the first version
of this section leaned on that check while having performed it once.

**The lesson is not that the check was wrong. It is that ONE case is not a
check.** A derived quantity that agrees with the engine on a single
configuration has demonstrated nothing, because the configurations where a
derivation breaks are exactly the ones nobody picked as an example. The
verification is now a rule that runs on every preprocessing mode, and it
failed on two of the three the moment it existed.

**It must still be labelled as derived, not measured.**

---

## 7. What the screen may and may not say

**May**

```
Block          Capacity      Busy
host active    118.0 inf/s   50.8%
accelerator    328.0 inf/s   18.3%

System delivered throughput   60 inf/s
System capacity               118.0 inf/s   (set by host active)
```

**May not**

```
host active throughput 118 inf/s        a block does not deliver
accelerator idle 81.7%                  idle and waiting are not separated
host -> accelerator overflow 40 inf/s   there is no queue
component PPACT for npu_32x32           no component evaluation exists
```

Every block figure carries `derived from station time`, and every
non-derivable quantity is shown as `NOT ESTABLISHED` rather than omitted -
an absent row reads as a quantity that does not apply.

---

## 8. Failure conditions

The presentation is wrong if:

- a block figure is called throughput
- `Idle` or `Waiting` is shown as a number
- a connector carries overflow or starvation
- a component is given PPACT axes without a component evaluation
- a derived capacity is presented without saying it is derived
- the system's delivered throughput is attributed to a block
- block capacities are summed, or compared as if they added

---

## 9. Recommendation

**Implement Capacity, Busy and shared-memory utilisation. Nothing else.**

Those three are derivable from figures the model already produces, and the
capacity derivation is verified against the engine's own pipeline capacity.

`Idle`, `Waiting`, `Overflow`, `Starvation` and component-level PPACT stay
`NOT ESTABLISHED` until the model carries dependency state, queues and a
component evaluation path respectively.

This is a smaller change than the proposal asks for. The proposal's own
principle is the reason: a block that is given a throughput has been given a
product's figure, and the fix for that is not to give it more figures.

---

## Revision history

**Revision 1** claimed block capacity was derivable from latency flow
station times and verified. Verified on one configuration; false on two of
three.

**Revision 2** corrects the source to the engine's throughput stations,
records that the flow and throughput decompositions are different by
design, and moves the verification from a sentence here into a contract
rule.

The wrong claim is kept above rather than deleted. A definition document
that quietly corrects itself teaches nothing about how the error was made,
and this one was made by generalising from a single example.

## What this document establishes

Which boundary each figure belongs to, that capacity and busy are derivable
from the engine's throughput stations and verified across preprocessing
modes, and that the idle/waiting split is not.

## What it does not

It does not establish a component evaluation path, a queue model, a
dependency graph, or that any derived figure matches real hardware.

---

*Author: Roger Kim / Copyright (c) 2026 Roger Kim & EdgeChipLab*
