# SP-D1 — Spider Chart: a viewer, not a calculator

**Status: DEFINITION. Records what exists and what must change.**

The spider chart is the one screen that shows all five axes at once, which
makes it the one screen most likely to acquire a calculation of its own.
This document says it may not have one.

---

## 1. What it is

```
each Track     metric -> constraint -> slack -> status -> normalised score
Spider         normalised score -> a shape
```

The spider consumes. If an axis has no score, the spider shows that it has
no score - it does not derive one, interpolate one, or borrow a nearby
figure.

**Why this matters more here than elsewhere.** A spider with a gap looks
broken and a spider with five points looks finished, so the pressure to
fill the gap comes from the picture itself rather than from anyone
deciding to.

---

## 2. The five axes

```
Performance   Power   Area   Cost   Traffic
```

**Thermal is not among them.** It is computed from power and area, which
makes it a verdict on a design rather than a dimension of one, and it
belongs with the deployment gates.

---

## 3. What already exists

Normalisation is not new work. `SYSTEM_ANCHORS` already defines it, per
axis, with an explicit rationale:

```
Performance   at_zero 1.0        at_hundred 1000.0    log
Power         at_zero 2000.0     at_hundred 1.0       log
Area          at_zero 4000.0     at_hundred 10.0      log
Cost          at_zero 20000.0    at_hundred 10.0      log
Thermal       at_zero 1.0        at_hundred 0.005     log
```

The anchors are the Tracks' business and the spider reads them. Two things
must change:

```
Thermal   remove from the axes
Traffic   add, with no score until its components exist
```

---

## 4. What the spider may not do

- compute a score from a metric
- substitute one axis's figure for another's
- omit an axis that has no score
- interpolate, average or default a missing point
- include a deployment gate as an axis
- rescale an axis to make a shape look better

The last is not hypothetical. An axis whose anchors are chosen so that the
current design scores well is an axis that has been fitted to an answer.

---

## 5. Missing scores

```
Performance      92
Power            NOT ESTABLISHED
Area             81
Cost             95
Traffic          NOT ESTABLISHED
```

Rendered as a gap, labelled, at the axis's own position. Not dropped, not
zero - zero is a score and means the design is as bad as the anchor allows.

**Two axes have no score today** and both have a stated reason:

```
Power     PW-Q1: the budget's measurement basis is not established
Traffic   one of ten components is modelled
```

---

## 6. Traffic in particular

Shared memory adequacy is available and must NOT be shown as Traffic. It is
one component of ten, and a spider point labelled Traffic that moves only
when memory moves would be the clearest possible version of the mistake
this project has made four times.

---

## 7. Deployment gates

```
accuracy   thermal   capacity   memory cooling
```

Not spider axes. They are pass/fail verdicts and a radial plot of them
would suggest a design can be partly cooled.

Shown in a separate deployment report.

---

## 8. Failure conditions

The spider is wrong if:

- it produces a number no Track produced
- an axis is missing from the chart because it has no score
- a gate appears as an axis
- Thermal appears as an axis
- Traffic shows a shared-memory figure
- anchors are changed to alter a shape rather than a scale

---

## 9. Order

```
SP-D1   this document
SP-D2   the data contract - what a Track hands the spider
SP-D3   the renderer, reading only that contract
SP-D4   Traffic connected, last, when it has a score
```

---

## What this document establishes

That the spider is a viewer, which five axes it has, that normalisation
already exists and belongs to the Tracks, and that two axes have no score
today for stated reasons.

## What it does not

A Traffic score, a Power score, or agreement between the anchors and any
external judgement of what a good design looks like.

---

*Author: Roger Kim / Copyright (c) 2026 Roger Kim & EdgeChipLab*
