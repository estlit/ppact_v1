# About PPACT Studio

## Purpose

PPACT Studio is a platform for exploring AI system architecture. It exists
for the part of a project that happens before anything is built: choosing
what kind of system to make, and finding out what each choice costs on the
axes that decide whether a product can be built and sold at
all.

Those axes are performance, power, area, cost and thermal. A design is not
quick or otherwise in the abstract. It sits at some combination of five
figures, and the interesting question is always what a change buys on one and
charges on another.

## Method

The Studio works from analytical engineering models. It computes each design
from its parts — the arithmetic a workload needs, the data it moves, what the
host does before the accelerator sees anything, what the memory can deliver —
and compares designs on the same basis.

Every conclusion is traced back to a measurement. A change is reported as
what moved, by how much, why, and only then what to do about it. Where a
result depends on an assumption, the Studio names the assumption and reports
how far the conclusion survives moving it.

It also states what it cannot tell you. A limit — the most a station could
give back if it took no time at all — is worth more than a recommendation,
because it holds for any part at any price.

## Educational and research use

The Studio is used for teaching, for research, and for the earliest stage of
architectural work, where the alternatives are still open and the cost of
exploring one is a few minutes rather than a tape-out.

For teaching it asks before it tells. A lesson takes a prediction, then shows
the comparison, then explains why the prediction was right or wrong. A reader
who agrees with a result has spent nothing; a reader who committed to an
answer and turned out to be wrong has learned something.

## Continuous library refinement

The architectural library is not fixed. It is reviewed against publicly
available industrial information and grows when that review finds a concept
it cannot express.

The review works one way only. Public specifications are read, the
architectural concepts behind them are extracted, and generalized CLASSES are
added — a performance band, a memory generation, a deployment shape. What is
never added is the product itself.

Where the library falls short, the gap is written down rather than filled
with something that resembles a solution. A recorded gap is useful. A class
invented to close one is not, and it looks like progress.

## Vendor-neutral architectural classes

No vendor name and no product name appears among the things a user can
select. A check enforces that across every library file, and permits those
names only in the evidence files, where they are the thing being cited.

Every class carries the level of confidence behind it and the evidence the
estimate rests on. No class carries a confidence above `medium`, because no
vendor publishes enough for any figure in the library to be checked.

## Commercial-product boundary

PPACT Studio does not model commercial products. It models AI system
architectural design spaces, informed by publicly available industrial
information.

Commercial products are validation sources, not library contents.

This follows from everything above rather than standing on its own. A tool
built to explore architecture, using analytical models, refined by public
information, could not reproduce a commercial part even if it wanted to — the
figures that would be needed are not public, and inventing them would make an
estimate indistinguishable from a measurement.

## Starting points, not recommendations

PPACT Studio does not recommend architectures. It provides measured
comparisons against a starting point so that engineering trade-offs can be
interpreted consistently. Every architecture is evaluated using the same
analytical model.

A starting point is a predefined initial architecture used only to make
measured changes easier to interpret. It is not a recommendation, not an
optimal design, and not a target architecture.

Example published configurations are illustrative examples derived from
publicly available technical information. They are provided for comparison
and education, not as recommended system designs.

## Interpretation of estimates

Every number the Studio reports is an analytical engineering estimate. It is
computed, not measured, and it is intended for comparing architectures rather
than for predicting a part.

A result here narrows the question. It does not answer it. Implementation,
measurement and silicon remain necessary, and no amount of work inside this
program substitutes for any of them.

What the Studio does not know matters as much as what it computes: what a
millisecond is worth, what the schedule allows, what a competitor has
announced, what a customer will pay. Those decide an answer as much as the
arithmetic does. The facts are the tool's; the decision is the designer's.

## Core principles

- Architecture before implementation.
- Engineering evidence before intuition.
- Vendor-neutral architectural exploration.
- Continuous refinement through public industrial information.

---

Copyright (C) EdgeChipLab. All rights reserved.
YouTube — https://www.youtube.com/@EdgeChipLab
