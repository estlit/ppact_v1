# Student guide

Ten minutes to your first result.

## Getting it running

### Google Colab

Upload `PPACT_Simulator.zip` to your Colab session, then in a cell:

```
!unzip -q PPACT_Simulator.zip
%cd PPACT_Simulator
%run run_colab.py
```

A menu appears. Pick a number.

If the runtime restarts, run the cell again — nothing is lost.

### Jupyter on your own machine

Extract the archive into a NEW, EMPTY folder, then:

```
%run run_jupyter.py
```

Extracting over an old folder leaves a mixture of two versions and fails in
ways that look like faults in the model. If a message says the folder holds
two releases, that is what happened.

## Your first five minutes

Choose `1. Quick Start`. It runs a worked example and asks you nothing.

Then choose `2. Education Mode` and take Lesson 1. Every lesson asks you to
commit to an answer before it shows you anything. Answer honestly rather
than carefully — being wrong is the part that teaches you something, and
nobody sees your answer.

## Reading a result

Three views, in this order:

**Reason Breakdown** — why the number changed. One job's time is split into
stations that add up exactly, and the thing holding most of the time is
where the next change belongs.

**Measured bars** — the physical figures against the product's budget.

**Architecture Balance** — whether a change was even across the five axes.
It shows no physical value and no limit. It is a summary, not a result.

## If something goes wrong

| What you see | What it means |
|---|---|
| `THE FOLDER HOLDS TWO RELEASES` | extract into a new empty folder |
| `NOT READY` | a requirement is unmet — the screen names which. It does not mean the design has a long latency. |
| `NOT EVALUATED` for every timing | the model does not fit in memory. A design that cannot hold its weights has no latency at all. |
| a value refused | the message names the field and the range. It is refused rather than clamped, because clamping would answer a different question. |
| `(no input available - stopping)` | the notebook could not prompt. Run the cell again in an interactive kernel. |

## What the numbers are

Engineering estimates, computed from analytical models. They are for
comparing architectures, not for predicting a part. `METHODOLOGY.md` lists
the assumptions and what has NOT been established.

The tool gives you facts. What a millisecond is worth, what the schedule
allows, what the customer will pay — those decide an answer too, and it does
not know any of them.
