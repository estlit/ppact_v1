# Help

What the things on screen mean.

## Modes

| Mode | For | You leave with |
|---|---|---|
| Quick Start | anyone opening this for the first time | a worked example, nothing to fill in |
| Education Mode | students meeting these ideas | the reasoning behind a design, one step at a time |
| Challenge Mode | students with an assignment | a result that can be marked, and a reason it should be |
| Research Mode | researchers and graduate students | the full model, nothing hidden |
| Demo Mode | a lecture, a talk, a recording | one question, one comparison, one answer |
| Validation Mode | whoever has to trust the numbers | the evidence, including what is missing from it |

## Metric definitions

| Name | Unit | What it counts |
|---|---|---|
| Single-job latency | ms | one job, first byte in to last byte out |
| Sensor-to-control | ms | capture through to a control output, including the image pipeline |
| Pipeline capacity | inf/s | what the machine COULD finish per second |
| Delivered throughput | inf/s | what it is ASKED to finish |
| System power | W | host, accelerator, memory and interfaces together |
| Energy per inference | mJ | power multiplied by the time one job takes |
| Total silicon | mm2 | host, accelerator and every memory die |
| System cost | USD | bill of materials per unit; mask sets are not per-unit |
| Power density | W/mm2 | system power over package footprint |

## Latency versus throughput

They are different questions and a change can move one and not the other.

Latency is how long ONE job takes. Throughput is how many finish per second.
A pipeline with four stations can start a new job before the last has
finished, so throughput can exceed one divided by latency — the two are not
reciprocals and a design can improve one while the other stands still.

Capacity is what the machine could do. Delivered throughput is the smaller of
that and what is asked of it. Raising capacity changes nothing if work arrives at the
same rate.

## Energy versus average power

A part that draws 2x the power and finishes in 1/4 of the time uses half
the energy. Energy is power multiplied by time, and for anything running on a
battery it is energy that matters.

The Studio reports both. Where they disagree about which design to prefer,
the disagreement is the finding.

## READY and NOT READY

READY means every deployment constraint is satisfied: latency, throughput,
power, cost, thermal, cooling class and capacity.

NOT READY means one of them is unmet, and the screen names which. It does not
mean the design has a long latency — a quick design that needs airflow in a sealed case
is still not a product. Cooling class is a CLASS, not a quantity, and no
reduction elsewhere fixes it.

## Starting points, not recommendations

PPACT Studio does not recommend architectures. It provides measured
comparisons against a starting point so that engineering trade-offs can be
interpreted consistently. Every architecture is evaluated using the same
analytical model.

A starting point is a predefined initial architecture used only to make
measured changes easier to interpret. It is not a recommendation, not an
optimal design, and not a target architecture.

## Reason Breakdown

Where one job's time went, decomposed into stations that sum exactly to the
whole:

    host active            preparing the frame, dispatching, formatting
    preprocessing offload  preparation moved off the host and still waited on
    offload overhead       handing preparation to another block and back
    accelerator core       the arithmetic, plus data-wait it could not hide
    engine hand-off        splitting one job between two engines and merging

If the parts do not sum to the difference, the residue is printed and marked
a defect rather than a rounding. A breakdown that silently absorbs a
millisecond looks complete, which is the danger.

## Measured Bar Charts

Physical values in their own units, against the product budget. This is
where an absolute figure and a requirement limit are read.

A bar that exceeds its budget line is drawn in the alternate colour and
labelled. That view is the one a normalized chart cannot give.

## Architecture Balance

A summary of the relative balance among normalized dimensions. Outward is
favourable on every axis.

It does NOT show physical values, requirement limits, bottlenecks, or the
reasons for change. An information-transfer experiment put five design
questions to it and it answered none of them: single-job latency is not one
of its axes, and a 21% latency change appeared as three points on a different
axis. Use it to see whether a change was even across the design, and read the
bars and the breakdown for everything else.

## Clipping markers

`100+` and `0-` mark a value that reached the end of its axis. The design is
further along than the chart can show, and reading `100+` as "as good as it
gets" would be wrong.

Where two designs score the same on every axis, the chart says so — a single
line is drawn where the legend shows two.

## Host Connection

On-board, USB 3.x, PCIe Gen4, PCIe Gen5, Ethernet or UCIe.

This is informational only. The analytical model does not use it in this
release: no latency, bandwidth, power, cost or gate reads it, and a check
requires that every metric is identical at every setting. It is shown because
a modern deployment style should be nameable, and saying plainly that it is
not yet modelled costs a reader less than omitting it or implying analysis.

## Invalid input

A refused value names the field, says what range is allowed, and does so in a
sentence. For example a work split outside 0 to 1 is refused rather than
clamped, because clamping would answer a different question from the one
asked.

A design whose model does not fit in memory reports NOT EVALUATED for every
performance figure, and still reports cost, area and capacity. A board that
cannot run its model still costs what it costs.
