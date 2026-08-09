# TR-D1 — Traffic: definition before any score

**Status: DEFINITION ONLY. No code changed. No score computed.**

Traffic is the fifth PPACT axis, replacing Thermal. It is not a memory
score, and the whole risk in building it now is that it would be one.

---

## 1. What Traffic is for

**Traffic is not GB/s.** Bytes moved is an input to it, not the thing
itself - a design shifting fewer bytes through a narrower path is not
thereby healthier, and one shifting many through an ample one is not
thereby worse.

Traffic is **System Integration Quality**: how evenly the supply and
consumption of data are matched inside the system.

```
Performance   what the user gets              delivered throughput
Traffic       how evenly it was achieved      supply against consumption
```

**Traffic is not an extension of the Memory track.** Shared memory, bus,
AXI, NoC, DMA, buffers, arbitration, waiting and idle are all COMPONENTS
of Traffic. Traffic is the system-level state they add up to, and it is
not computed from any one of them - which is the whole reason no score is
computed today.

Two designs can deliver the same throughput and be different systems: one
running comfortably, one with every internal path saturated. Performance
cannot tell them apart, and Traffic exists to.

**System scope only.** A component has no traffic in this sense - traffic
is a property of parts moving data between each other, and one part alone
has nobody to move it to.

---

## 2. Why Thermal left the axes

Thermal is computed FROM two other axes:

```
power density = system power / footprint
thermal margin = 1 - power density / limit
```

It is not a thing a designer chooses; it is what the choices produce. That
makes it a verdict on a design rather than a dimension of one.

It stays as a **deployment gate**, beside the gates that already work that
way - accuracy, capacity, memory cooling. All nine applications declare
`thermal_limit_w_per_mm2` and the gate is unaffected by this change.

```
PPACT axes        Performance  Power  Area  Cost  Traffic
Deployment gates  accuracy  thermal  capacity  memory cooling  ...
```

---

## 3. What Traffic must comprise

| Component | Meaning | Status |
|---|---|---|
| Shared memory | bandwidth demanded against bandwidth available | **PARTIAL** |
| Bus / interconnect | on-chip transport between blocks | NOT MODELLED |
| AXI / NoC | topology, ports, contention | NOT MODELLED |
| DMA | transfer engines and their occupancy | NOT MODELLED |
| Cache | hierarchy, hit rates, refill traffic | NOT MODELLED |
| Buffer | queues between stages, occupancy | NOT MODELLED |
| Arbitration | how contention is resolved | **NOT ESTABLISHED** |
| Waiting | time a block cannot proceed | NOT ESTABLISHED |
| Idle | time a block has nothing to do | NOT ESTABLISHED |
| Pipeline balance | how evenly the stages are loaded | derivable |

**One of ten is implemented.** Two more have entries only because the model
records that it cannot compute them.

---

## 4. What exists today, precisely

**Shared memory — PARTIAL.** Target-rate adequacy is computed and verified
across 164,736 configurations:

```
host required at target        8.42 GB/s
accelerator required at target 6.92 GB/s
concurrent requirement        15.34 GB/s
effective bandwidth           73.73 GB/s
```

It is partial because the concurrent requirement rests on an overlap
assumption that is declared, not measured, and because 52 configurations
change verdict inside the contract's overlap range.

**Traffic volumes — reported.** `DRAM traffic 115.26 MB`, `Host DRAM
traffic`, `weight traffic`, `KV cache traffic`, `Data reuse (MAC per DRAM
byte)`. These are bytes, not quality: a design moving fewer bytes is not
thereby healthier if it moves them through a narrower path.

**Pipeline balance — derivable, not built.** The throughput stations exist
and their spread could be computed. Nothing does yet.

**Arbitration — NOT ESTABLISHED.** MEM-ARB-001: the rule gives the
accelerator its demand and hands the host what is left, and a 3.2%
aggregate over-demand halves the host's bandwidth. Any traffic quality
figure resting on it inherits that.

**Waiting and Idle — NOT ESTABLISHED.** Their sum is `1 - busy` and the
split needs the reason a block is not working. The model carries no
dependency state.

---

## 5. Why no score is computed

A normalised score built today would combine one implemented component
with nine absent ones. Whatever the weights, the output moves only when
shared memory moves:

```
Traffic = 42
```

would be `Shared memory adequacy = 42` under a name that promises nine
other things. That is the failure this project has already paid for four
times - a quantity whose name says more than its arithmetic does.

**The score comes last.** When bus, buffer and waiting exist, the
components can be combined and the combination will mean what its name
says.

---

## 6. What the Traffic screen shows now

```
TRAFFIC ANALYSIS

  Shared memory          PARTIAL     adequacy computed, overlap assumed
  Bus / interconnect     NOT MODELLED
  AXI / NoC              NOT MODELLED
  DMA                    NOT MODELLED
  Cache                  NOT MODELLED
  Buffer                 NOT MODELLED
  Arbitration            NOT ESTABLISHED   MEM-ARB-001
  Waiting                NOT ESTABLISHED   no dependency state
  Idle                   NOT ESTABLISHED   no dependency state
  Pipeline balance       derivable, not built

  Overall traffic        NOT ESTABLISHED
      One of ten components is implemented. A score built on it
      would be a memory score under another name.
```

The rows are present and empty, which is the shape used on the Power axis
for the same reason: an axis with rows missing reads as an axis with fewer
questions.

---

## 7. What Traffic will NOT recommend

Traffic recommendations are about internal structure:

```
wider or additional memory channels
a different interconnect topology
buffers between stages
arbitration policy
pipeline rebalancing
```

**Never** a faster clock or a bigger accelerator. Those raise throughput
and are the Performance axis's business; offering them here would make
Traffic a second Performance screen.

---

## 8. Failure conditions

The Traffic axis is wrong if:

- a score is reported while fewer than a majority of components exist
- a byte count is presented as a quality figure
- a traffic figure rests on the arbitration rule without saying so
- `Waiting` or `Idle` is given a number
- a recommendation raises throughput rather than improving data movement
- Traffic is computed for a component rather than a system
- Thermal is described as a PPACT axis

---

## 9. Order

```
TR-D1   this document
        then bus, buffer and waiting models - each on its own
TR-D2   the traffic screen, rows present and empty
TR-Dn   the score, when the components support one
```

Traffic is last among the axes and its score is last within it. Both
orderings are the same principle: nothing is combined before the things
being combined exist.

---

## What this document establishes

That Traffic is system-scope internal data movement, which ten components
it comprises, that one is implemented, and why no score follows from that.

## What it does not

A score, a weighting, a bus model, a queue model, or agreement with any
measured system.

---

*Author: Roger Kim / Copyright (c) 2026 Roger Kim & EdgeChipLab*
