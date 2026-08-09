# Exercise sheet

Twelve exercises. Each has a determinate answer the model can produce, and
each is worth doing because the obvious answer is wrong at least as often as
it is right.

Write your prediction down BEFORE you run anything. An exercise you read the
answer to is an exercise you have watched somebody else do.

## A. Reading one design

**A1.** Evaluate `industrial_vision` with `cortex_a78_x4`, `npu_32x32`,
`LPDDR5` x2. Which station holds most of one job? Predict first.

**A2.** Same design. Is it READY? If not, which requirement is unmet, and is
that requirement a quantity or a class?

**A3.** What is the largest saving any single change could produce, and
which station would have to become free to produce it?

## B. Changes that do not do what they look like

**B1.** Take the A1 design and replace `npu_32x32` with `npu_64x64`. Predict
the latency before running it. Explain the result using the reason
breakdown.

**B2.** Take the A1 design and add a second `npu_32x32` in parallel with a
0.5 work split. Predict, run, explain.

**B3.** Take the A1 design and change `LPDDR5` x2 to `HBM3E` x1. How much
latency did you buy, and for how many dollars? Compute the rate.

**B4.** Take the A1 design and change the host to `cortex_a53_x4`. The
accelerator is identical. Predict the latency.

## C. Finding the lever

**C1.** For the A1 design, move preprocessing from `cpu_only` to
`isp_and_npu`. Compare the gain per dollar against B3. Which buys more latency per
dollar, and by what factor?

**C2.** `drone` with `npu_24x24`, `LPDDR5` x2, `isp_and_npu`. Find the
smallest engine that still passes every gate. Which constraint stops you
going smaller?

**C3.** Repeat C2 for `robot` and explain why the answer differs.

## D. Requirements

**D1.** `mobile_ai` with `npu_64x64`, `LPDDR5` x2, `isp_and_npu`, at N16.
Move both nodes to N3. What moved, and what did not? Why is the answer not
"it got quicker"?

**D2.** `llm_service` with `datacenter_gpu` and `LPDDR5` x8. What does the
screen report, and why is that not a design with a long latency?

## E. Defending a choice

**E1.** Take Challenge Mode's inspection challenge. Find a design meeting
all three targets. Then find a second one. Explain which you would build and
what you traded away — the tool will not tell you, and cannot.

---

## Marking

For each answer, a marker should look for:

- the figure, with its unit;
- the station holding the time, named;
- a reason that matches the conclusion.

An answer that reaches the right verdict with the wrong reason should not
score higher than one that reaches the wrong verdict with a sound reason and
a stated assumption. The first is a guess that landed.
