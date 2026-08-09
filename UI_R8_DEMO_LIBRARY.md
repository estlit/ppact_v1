# UI-R8 — Demonstration Library

**No code changed. No menu changed. No tests run.**

The fifteen demonstrations, documented from what they contain. Every
question, setup and answer below is read from the demo definitions, not
written for this document.

**No `Topic`, `Difficulty` or `Axis` fields.** They do not exist in the
data, one of them cannot be derived at all, and adding them here would put
an editorial judgement in a reference document as though it had been
computed.

---

## What a demonstration is

```
question  ->  setup  ->  rows  ->  watch  ->  answer  ->  because
```

A hypothesis and an experiment. **Fourteen of the fifteen answers begin
with "No"** or "Not", which is the point: each demo takes something a
designer reasonably assumes and shows the conditions under which it fails.

---

## The library

### Demo 001 — `memory`

```
Question    Does a faster memory always help?
Setup       The same engine, the same workload. Only the memory changes.
Answer      No. Sixteen times the bandwidth for a fraction of the time,
            at six times the price.
Because     This design was computing, not waiting. A faster memory
            shortens a wait, and there was very little wait to shorten.
```

**Learns:** an upgrade only helps the thing that is limiting.
**Studio:** Analyze > Traffic; Compare > Compare Memory Technologies.

### Demo 002 — `engine`

```
Question    Does a bigger engine always help?
Setup       The same memory, the same workload. Only the engine changes.
Answer      No. It helps, then it stops, then it reverses - the large
            engine is SLOWER than the medium one.
Because     The large engine multiplies faster than the memory can feed
            it, so the extra multipliers wait.
```

**Learns:** the limit moves when you relieve it, and buying more of what
was limiting cannot move it again.
**Studio:** Analyze > Performance; Analyze > Recommendation.

### Demo 003 — `dual`

```
Question    Are two engines twice as fast?
Setup       One accelerator, then two, sharing one memory system.
Answer      No. Here they are SLOWER than one.
Because     Each engine does half the arithmetic, but both read the same
            memory - so the transfers did not halve, they queued.
```

**Learns:** parallel compute does not parallelise a shared resource.
**Studio:** Analyze > Traffic; Analyze > Overview.

### Demo 004 — `node`

```
Question    Does a finer process node make it faster?
Setup       The identical design, fabricated at three different nodes.
Answer      Barely. Two node generations move the time by under one per
            cent.
Because     A node makes arithmetic faster and does nothing to a memory
            bought off a shelf.
```

**Learns:** a process node moves logic, not purchased parts.
**Studio:** Analyze > Area; Analyze > Performance.

### Demo 005 — `order`

```
Question    Three ways to spend money. Which one works?
Setup       Three ways to spend money on the same design. Only one of
            them is worth doing.
Answer      The cheapest change is the best one, and the obvious hardware
            upgrade makes it worse.
Because     The host was the slowest station. Moving its work elsewhere
            costs almost nothing and removes the actual constraint.
```

**Learns:** find the constraint before spending.
**Studio:** Analyze > Recommendation; Improve > Try a Change.

### Demo 006 — `finest`

```
Question    Is the finest process node the fastest?
Setup       A compute-bound design fabricated at three nodes.
Answer      No. The 3 nm part is slower than the 7 nm one, and dearer.
Because     Below a certain point the memory arrays stop shrinking with
            the logic, so the die does not get proportionally smaller and
            the wafer costs far more.
```

**Learns:** scaling is not monotonic below a point.
**Studio:** Analyze > Area; Analyze > Cost.

### Demo 007 — `together`

```
Question    When is a second engine worth having?
Setup       The same pair of engines, on a narrow memory and a wide one.
Answer      Only once the memory can feed it. On the narrow bus the pair
            is slower; on the wide one it is faster.
Because     The second engine was never short of work - it was short of
            data. The order the two purchases are made in matters.
```

**Learns:** upgrades have an order, and the wrong order is worse than
neither.
**Studio:** Analyze > Traffic; Improve > Try a Change.

### Demo 008 — `shipping`

```
Question    Is the fastest design the one you ship?
Setup       The quickest configuration available, against its
            requirements.
Answer      No. The quick one is eight times faster and fails four
            requirements.
Because     Speed is one axis. Power, cost and the cooling class are three
            others, and a product has to clear all of them.
```

**Learns:** what PPACT is for.
**Studio:** Analyze > PPACT Dashboard.

### Demo 009 — `host`

```
Question    Which should you upgrade first?
Setup       Identical accelerator and memory. Only the host changes.
Answer      The host, here. Three times faster, and the accelerator was
            never touched.
Because     The host prepares every frame before the accelerator sees it.
            On the modest one that preparation takes longer than the
            inference.
```

**Learns:** the accelerator is not automatically the bottleneck.
**Studio:** Analyze > Performance; Analyze > Overview.

### Demo 010 — `offload`

```
Question    Where should the preprocessing run?
Setup       Same parts throughout. Only WHERE the frame is prepared
            changes.
Answer      Not on the host. Moving it cuts the time by nearly two thirds
            and the power with it.
Because     A general-purpose core doing per-pixel work is the most
            expensive way to do per-pixel work.
```

**Learns:** placement is a design decision, not a detail.
**Studio:** Analyze > Overview; Improve > Try a Change.

### Demo 011 — `capacity`

```
Question    Does more memory make it faster?
Setup       The same memory type. Only how much of it changes.
Answer      Here yes - but not because of the capacity. Eight packages
            cost seven times as much.
Because     More packages buy BANDWIDTH as well as capacity, and this
            design was memory-limited.
```

**Learns:** the right answer for the wrong reason is still fragile.
**Studio:** Analyze > Traffic; Analyze > Cost.

### Demo 012 — `fit`

```
Question    What happens when the model does not fit?
Setup       A large language model on two memory configurations.
Answer      Nothing. Not slow - absent. The row reports no timing at all.
Because     A model that does not fit cannot run at any speed. Reporting
            a latency would invite a comparison between a machine that
            works and one that does not.
```

**Learns:** why Studio refuses to report some figures.
**Studio:** Analyze > Current Design; Verify > Check What Was Verified.

### Demo 013 — `cheaper`

```
Question    Can a cheaper memory be the right answer?
Setup       A drone, with two memory types at the same package count.
Answer      The graphics memory is 41% cheaper and the same speed - and
            it doubles the power.
Because     This design is compute-limited, so neither memory is holding
            it up. The choice comes down to price against power.
```

**Learns:** when an axis stops mattering, another decides.
**Studio:** Analyze > Cost; Analyze > Power.

### Demo 014 — `split`

```
Question    Does splitting a job between two engines help?
Setup       Two engines of different sizes, one job divided between them.
Answer      Not evenly. Half the work on a quarter of the engine takes
            longer than all of it on the whole one.
Because     A parallel pair cannot finish before its slower half.
```

**Learns:** a split must match the parts it is split across.
**Studio:** Analyze > Performance; Improve > Try a Change.

### Demo 015 — `nodecost`

```
Question    Is the newest process node the cheapest to make?
Setup       The same design at four nodes. Watch the LOGIC die cost - the
            part a node actually moves.
Answer      No. The cost falls to 7 nm and then RISES again - 3 nm is
            dearer than 7 nm here, and slower.
Because     A finer node shrinks the die, which lowers cost, and raises
            the wafer price and lowers the yield, which raises it. The
            two cross.
```

**Learns:** there is an economic optimum node, and it is not the newest.
**Studio:** Analyze > Cost; Compare > Compare Designs.

---

## Numbering

```
Demo 001 .. Demo 015     permanent, never reused
```

One identifier across Studio, video, book and paper. A withdrawn demo
keeps its number reserved.

**Studio does not know a video exists.** Nothing in the code enforces the
correspondence; it holds because whoever publishes keeps it.

---

## Presentation

The question comes first, the number second - people remember questions
and click on questions.

```
  Today's Featured Demonstration

  Does a faster memory always help?                    Demo 001

                                       Press D    ·    View all (V)
```

`View all` opens the library: fifteen questions, no filters, because there
is nothing yet to filter on.

---

## Related YouTube episode / book chapter

**Empty for all fifteen.** The fields belong in this document once
episodes exist; recording them now would be recording an intention.

---

## What this document does not do

It does not add `Topic`, `Difficulty` or `Axis`. Fourteen of fifteen demos
watch the same three metrics, so an axis tag derived from the data
distinguishes nothing, and a tag that looks like information and carries
none is worse than no tag.

`What the user learns` above IS an editorial judgement - one line each,
written here where it can be argued with, rather than as a field
implying it was computed.

---

*Author: Roger Kim / Copyright (c) 2026 Roger Kim & EdgeChipLab*
