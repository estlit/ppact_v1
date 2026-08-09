# PPACT Studio — Public Preview

**Constraint-based design assessment for AI hardware systems.**

Analyze. Compare. Improve.

---

## What PPACT Studio Is

PPACT Studio is an analytical model of AI hardware systems. It takes an
application and a configuration - host processor, accelerator, memory,
preprocessing placement, process node - and reports where the time goes,
what limits the design, and what a change would have to address.

Five axes, one interface:

```
Performance    Power    Area    Cost    Traffic
```

Every figure it reports is measured against a stated constraint. Every
figure it cannot establish says so, in those words, rather than
substituting a number.

### Status

This is a **public preview**. It is released to gather feedback, not as
a finished product.

```
Core analytical engine              validated
Streamlit visual interface          available
Fifteen live engineering demos      available
System Flow and Bottleneck Map      preview
Comparison Closure                  preview
External industrial validation      not yet established
```

**What "validated" means here.** The engine passes 5,128 model checks,
a 1,376-rule review contract, and a mutation suite in which 162 seeded
defects were all detected. Those are internal checks: they establish that
the model does what it says, not that it matches measured hardware.

**What is not established.** No figure in this tool has been compared
against a measured system. The library figures are vendor-published and
architectural-class estimates. No external party has reviewed the model,
and no industrial design has been checked against it. Where the model
cannot answer, it prints `NOT ESTABLISHED` rather than a number, and the
list of open questions is in `DEFERRED.md`.

---

## Typical Workflow

```
Starting point  ->  Current design  ->  Evidence  ->  Conclusion
                                                            |
                            Recommended next comparisons  <-+
                                          |
                                          v
                                    a new comparison
```

A comparison does not end with a result. It ends by proposing what to
compare next, ordered by where the engine says the limit currently sits.

### Recommendations are comparisons, not answers

When a comparison finishes, Studio proposes what to compare next. Those
proposals are ordered by where the engine says the limit currently sits.

> **Recommendations identify structurally relevant comparisons. They do
> not predict a winning design until the comparison is executed.**

A proposal marked `DIRECT` addresses the element the engine reports as
limiting. It does not mean the change will help most, or help at all —
Studio runs no counterfactual, so nothing in the interface estimates how
much a change would gain. Running the comparison is what answers that.

Proposals marked `CONTRAST` deliberately do **not** address the limiting
element. They are control experiments: useful for showing that a change
somewhere else does little, which is often the point.

---

## Quick Start

```bash
streamlit run streamlit_app.py     # visual interface
python3 run_jupyter.py             # notebook interface
python3 -m ppact                   # terminal interface
```

All three read the same computed results. The Streamlit front end
displays; it does not compute, and a contract rule checks that it calls
no engine entry point.

`run_jupyter.py` is written for a notebook cell - `%run run_jupyter.py` -
and finds the package from its own location, repairs a flat extraction
and refuses to run against a stale copy. On Google Colab use
`run_colab.py`, which can also fetch the archive from Drive.

The three entry points are independent. None of them calls another, and
the notebook launcher has no part in a Streamlit deployment.

### Hosting it

Cloning the repository does not make the app open in a browser: the
Streamlit interface is a server, and something has to run it. On
Streamlit Community Cloud, point the deployment at `streamlit_app.py`;
`requirements.txt` pins the three libraries it needs.

`runtime.txt` pins the interpreter to the line this was verified on.
Whether a hosted build resolves the pinned libraries against its own
Python has not been observed - `DEP-PY-001` records that, and a failure
would appear as a version conflict in the build log rather than as a
running app drawing different figures.

A hosted copy is public. Every screen carries the release status, the
engine version and the model digest, and the sidebar states what has not
been established - so a reader who arrives at a figure without reading
this file still sees the limits.

---

## Main Modes

```
Start      Create or open a design.
Analyze    Understand how your design performs and what limits it.
Improve    Try changes and see whether they help.
Compare    Put designs side by side and see what differs.
Learn      Work through the material, from first lesson to challenge.
Verify     Confirm the analysis is sound and reproducible.
```

### The fifteen demonstrations

Each one asks a question a designer actually asks, and most of the
answers are "no":

```
001  Does much faster memory produce a proportional system speedup?
002  Does a bigger engine always help?
003  Are two engines twice as fast?
004  Does a finer process node make it faster?
005  Three ways to spend money. Which one works?
006  Is the finest process node the fastest?
007  When is a second engine worth having?
008  Does better traffic balance mean the design passes every check?
009  Which should you upgrade first?
010  Where should the preprocessing run?
011  Does more memory make it faster?
012  What happens when the model does not fit?
013  Can a cheaper memory be the right answer?
014  Does splitting a job between two engines help?
015  Is the newest process node the cheapest to make?
```

**A demonstration stores a scenario, never a figure.** The numbers, the
charts and the explanations are regenerated from the current engine, so
improving the model updates every demonstration rather than leaving stale
figures in a document. Each screen records the engine version and model
digest that produced it.

---

## Documentation

```
METHODOLOGY.md      how the model computes what it computes
DEFERRED.md         the open-question register
HELP.md             in-tool help, by screen
STUDENT_GUIDE.md    the teaching path
ABOUT.md            what the project is, and what it is not
```

Definition documents carry a prefix and a number - `PB_D1`, `SF_D1`,
`TR_D1`, `SP_D1`, `PPACT_D1` - and each records what was decided, what
was retracted, and why.

### What we would like feedback on

1. **Do the recommendations read as sensible next experiments?** They are
   computed from the limiting element, and whether that ordering matches
   an engineer's instinct is exactly what we cannot test internally.
2. **Does the System Flow and Bottleneck Map communicate more directly
   than the numbers alone?** It is built on the assumption that it does,
   and nobody outside this project has been watched reading it.
3. **Where does a figure look wrong?** The model is analytical throughout,
   and a figure that contradicts your experience is the most useful thing
   you can report.
4. **What is missing from the configuration space?** Scheduling, cache
   hierarchy and bus width are not fields in this model.

Please open an issue. A report that a number looks wrong is more valuable
than a feature request.

---

## How to Read the Results

**A limiting element is not a violation.** The lowest-throughput stage
sets the system rate; whether that rate meets the requirement is a
separate statement, and the screen makes both.

**Latency and throughput are different decompositions.** A change can
improve one and worsen the other, and several demonstrations show exactly
that. They are reported separately and never combined.

**A link is not a module.** A system whose modules are all comfortable can
still be held up by the path between two of them, and the System Flow and
Bottleneck Map names which kind of element is limiting.

**`NOT ESTABLISHED` is a result.** It means the model can compute the
constraint but not the quantity, and printing a number there would invite
a comparison the model cannot support.

**Percentages of a percentage are percentage points.** A utilisation
moving from 50.8% to 43.8% is `-7.0 pp`, not `-14%`.

---

## Engineering Estimates and Boundaries

These are the ones that would change conclusions, not a full list —
`DEFERRED.md` has the register.

**Memory arbitration (`MEM-ARB-001`).** The host memory demand model is
not established. Any result involving contention between the host and the
accelerator inherits this, and the confidence ceiling on those inferences
is MEDIUM.

**Power measurement basis (`PW-Q1`).** Whether the power budget is a
sustained or an instantaneous limit is unanswered, so no power verdict is
issued anywhere. Power figures are ratios of active-window averages.

**Traffic (`TR-D1`).** Traffic balance is established. The other nine
components of the traffic definition are not, and there is no traffic
efficiency score, because that would need an ideal architecture to
measure against and no such starting point is established.

**Terminal column width (`WF-WIDTH-001`).** A majority of terminal menu
entries print past 78 columns; the widest are comparison tables that wrap
into nonsense in a narrow terminal. `tests_workflow.py` reports the
current count.

**Browser visual review.** The Streamlit interface has been launched,
screenshotted and inspected at 1440, 1024 and 768 pixels. It has not been
reviewed by anyone outside this project.

---

### Verification

```bash
python3 tests_model.py             # the analytical model
python3 tests_review_contract.py --enforce
python3 tests_streamlit.py         # the two front ends agree
python3 tests_mutation.py          # seeded defects, all detected
python3 tests_workflow.py          # every menu entry runs
```

Each prints its own count. `tests_workflow` records the known
column-width defects rather than asserting them, so a green run does not
mean the terminal screens are clean.

Each suite states what it establishes and what it does not; the register
is `ppact/test_registry.py`. Release evidence is **NOT READY** — the full
governance audit has two steps that require manual review and have not
been performed.

Reproducibility: `python3 certify.py` rebuilds the evidence and compares
it against the recorded run.

---

## Copyright

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab

If you cite this in academic work, please cite the engine version and
model digest shown in the interface rather than "PPACT Studio", since the
figures are regenerated from whichever engine produced them.
