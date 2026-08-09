# Standard Engineering Review Contract

**Revision 4 — Latency Flow.** The four open questions are decided and
recorded below. **No code has been changed to match this document.** The
contract is written first so it can be argued with before eight workflows
are migrated to it.

---

## Why this document exists

RC2 declared a three-layer result — reason breakdown, measured results,
architecture balance — in its introduction material, in `HELP.md`, and in
`METHODOLOGY.md`.

In the shipped program, `Architecture Balance` was rendered on exactly one
path out of eight, and measured bars with physical units existed only as a
PNG that no console path produced.

Nothing caught it. Every suite called the engine directly and passed. The
defect lived between the menu and the engine, where no contract existed.

That is the failure this document is written against: **a promise made in
prose and never expressed in code cannot be checked, and will drift.**

---

## Top-level requirement

> **Every completed engineering analysis shall automatically end with the
> Standard Engineering Design Review.**

> **The Standard Engineering Design Review must always provide meaningful
> visual engineering evidence, including Measured Results Bars and
> Architecture Balance.**

Two consequences follow, and both are requirements:

- A workflow **may not** ask whether to show the review. Asking implies the
  core result is optional.
- A workflow **may not** assemble its own report. There is one renderer.

---

## 1. Analysis types

The review has two variants. They differ in what a section MEANS, not in
whether it appears.

| | Single design analysis | Design comparison |
|---|---|---|
| Input | one configuration | a starting point and a current design |
| Question answered | where does this design's time go, and what limits it | what did this change buy, and what did it cost |
| Breakdown section | **Latency Flow** | **Latency Change Breakdown** |
| Balance section | **Architecture Balance** | **Architecture Balance Comparison** |

The two names per section are deliberate. One name meaning two things would
break the one-concept-one-name rule the terminology registry enforces, and a
reader who saw `Latency Breakdown` showing a composition on one screen and a
change on another would have no way to tell which they were looking at.

### Why no automatic starting point for single analysis

A single design is **not** silently compared against a starting
configuration to manufacture a change.

A starting point that appears on every screen is read as the recommended
design however often it is labelled otherwise. Removing that reading cost
this project a full release cycle at 4.15.0, and reintroducing it through
the back door of a default comparison would undo it.

A comparison happens when the user asks for one.

---

## 2. Mandatory sections and order

| # | Section ID | Canonical title | Single | Comparison |
|---|---|---|---|---|
| 1 | `architecture_summary` | Architecture Summary | required | required |
| 2 | `latency_flow` | Latency Flow | required | — |
| 2 | `latency_change` | Latency Change Breakdown | — | required |
| 3 | `limiting_factor` | Current Limiting Factor | required | required |
| 4 | `measured_bars` | Measured Results | required | required |
| 5 | `balance` | Architecture Balance | required | — |
| 5 | `balance_comparison` | Architecture Balance Comparison | — | required |

Sections 2 and 5 each appear ONCE in any given review. The two rows per
number are the two variants of one section, not two sections.
| 6 | `recommendation` | What to Explore Next | required | required |
| 7 | `deployment` | Deployment Assessment | required | required |
| 8 | `takeaway` | Engineering Takeaway | required | required |
| 9 | `boundaries` | Assumptions and Model Boundaries | required | required |

Order is fixed. Sections 2 and 5 exist in exactly one variant each; a
workflow producing the wrong variant is a contract violation, not a
stylistic difference.

### What each section must contain

**1. Architecture Summary** — the configuration under review, as separate
labelled fields rather than one packed string: application, host processor,
accelerator, memory technology, memory unit count, host and accelerator
process nodes. For a comparison, both configurations.

**2. Latency Flow** *(single)* — the stations of one job, drawn in
EXECUTION ORDER, each with its time and its share, summing to 100%.

```
host active -> preprocessing offload -> offload overhead
            -> accelerator core -> engine hand-off
```

The order is the order work happens in, not the order of size. `headroom()`
returns stations sorted largest first; a flow sorted that way would tell a
reader the accelerator runs before the host.

A station at zero is omitted rather than drawn empty. `engine hand-off` is
zero unless a second accelerator is configured, where it is real: a dual
configuration reports it at 0.8% and a single one not at all.

**Overlap inside a station.** Two stations decompose further, and in BOTH
cases the parts overlap - they run concurrently and do not sum to the
station:

```
accelerator core   arithmetic          and  memory wait
host active        host compute        and  host transfer
```

Measured: an accelerator core of 2.910 ms contains 2.519 ms of arithmetic
and 1.564 ms of memory wait, which add to 4.082 ms. A host active of 8.474
ms contains 7.239 and 4.115.

Where a station has an overlap decomposition the review states:

- both figures,
- that they OVERLAP and do not sum to the station,
- which of the two is longer **HERE**.

The last line is computed, never fixed. Across twelve representative
configurations memory wait was the longer in four of them, so a sentence
saying "arithmetic is the longer" would be false in a third of cases.

No station other than these two carries an overlap decomposition, and a
station without one shows no internal figures rather than an empty note.

**Rendering.** The text flow is REQUIRED and is drawn vertically: a
horizontal chain exceeds the 78-column limit as soon as a fourth station
appears. An image is OPTIONAL, and its absence is not a failure - the same
rule Measured Results already follows.

**2. Latency Change Breakdown** *(comparison)* — each station's contribution
to the change, summing exactly to the reported change. **Any residue is
printed, not absorbed.**

**3. Current Limiting Factor** — TWO figures, printed side by side and never
merged:

```
Dominant latency component   Accelerator core, 68.4%
Analytical limiting factor   Memory
```

They are different concepts and they disagree in practice. Across 56
representative configurations they agreed in 31 and differed in 25 — a
design can spend most of its time inside the accelerator while the
accelerator is waiting on bandwidth, so the station holding the time is the
accelerator and the limit is memory.

Neither may be hidden, and neither may be presented as the other. Treating
them as one quantity would require first proving them equivalent as a model
invariant, which the figures above show they are not.

Never an adjective on its own.

**4. Measured Results** — physical values in their own units against the
application's requirement, for: execution latency, delivered throughput,
system power, energy per job, total silicon, system cost, and thermal power
density. Rendering is defined in section 4 below.

The last row is **not** called a thermal margin. The engine computes power
density against a modelled thermal limit; it computes neither a temperature
nor a margin in watts. `Thermal Margin` may be used only after a model
based on temperature or thermal resistance exists. Naming a quantity after
something the engine does not compute is the failure this whole contract is
written against.

**Section 5 — Balance Visualization.** One section with two variants, never
two sections:

- *Single variant* — **Architecture Balance**: the current design's
  normalized profile on five axes.
- *Comparison variant* — **Architecture Balance Comparison**: both profiles
  overlaid, with the existing clipping markers (`100+`, `0-`) and the
  overlap statement.

Numbering them 5 and 6 would collide with Recommendation and would suggest a
review could carry both. It carries exactly one.

A single-design balance uses the **same fixed axis definitions and the same
normalization ranges** as a comparison balance. It does not normalize
against the current design itself — self-normalization would put every axis
at the same value and show a shape that means nothing.

Both carry the existing purpose line and caveat verbatim. Both remain
last-but-three in the order, never first, and are never described as a
performance summary or a recommendation. The roles stay fixed:

```
Latency Flow / Change Breakdown           why
Measured Results                          how much
Architecture Balance                      overall normalized shape
```

**6. What to Explore Next** — measured alternatives with their effect, not
advice. Where an upper bound exists it is reported: the most any single
change could give back.

**7. Deployment Assessment** — READY or NOT READY with the named unmet
requirement. Never a score.

**8. Engineering Takeaway** — one or two sentences true of THIS analysis,
carrying at least one figure.

**9. Assumptions and Model Boundaries** — the existing handover text: the
facts are the tool's, the decision is the designer's.

Full statement on the **first review of a session**. On later interactive
reviews, a fixed short form:

```
Analytical estimates, not measured hardware results. The decision remains
with the designer. Use View Model Boundaries for the full statement.
```

**Every exported or saved report carries the full statement regardless of
session order.** A file travels on its own, and a boundary that depended on
having read an earlier screen is a boundary that disappears the moment the
file is forwarded.

---

## 3. Applicability

Applicability comes from a **central workflow registry**. It is neither
handwritten in this document nor inferred from the menu.

The menu is a presentation. It carries help screens, About, Back, file
export, sub-menu entries and validation alongside the analyses, so treating
menu structure as the contract boundary would let a UI change silently move
the analysis scope.

```
WORKFLOW_REGISTRY

    workflow_id                  stable, never a menu label
    canonical_name
    workflow_type
    produces_engineering_analysis   bool
    review_variant               single | comparison | none
    exemption_reason             required when not an analysis
    entry_points                 the menu items that reach it
```

Examples:

```
education_guided_design
    produces_engineering_analysis = true
    review_variant               = single

research_compare
    produces_engineering_analysis = true
    review_variant               = comparison

validation_model
    produces_engineering_analysis = false
    exemption_reason = "Produces validation evidence, not an engineering
                        analysis"
```

The menu reads the registry. The registry never reads the menu.

Checks required:

```
every runnable menu analysis item      carries a registered workflow_id
every analysis workflow                uses the standard review
every non-analysis workflow            carries a specific exemption_reason
an executable path with no workflow_id fails the build
```

The last line is the one that matters. A new menu entry that nobody
registered is the exact mechanism that produced this defect in RC2, and an
unregistered path must fail rather than quietly fall outside the contract.

### Workflows in scope at RC3

```
Demo Mode
Quick Start
Education Mode        (all analysis activities)
Challenge Mode
Research Mode
What-if
Single Design Analysis
Design Comparison
```

Modes differ in how many questions they ask and how much they explain. They
do **not** differ in the structure or completeness of the final result.

Quick means fewer inputs, not a thinner conclusion.

### Explicit exceptions

These are not engineering analyses and use their own output contract:

```
Validation Mode          PASS / FAIL, evidence, reproducibility
Library Validation       coverage, gaps, alignment, confidence
Release Certification    reproduction grade and digests
Documentation Audit      pass counts and failures
```

Forcing a balance chart onto a PASS/FAIL screen would mean inventing two
designs to compare, which is precisely the kind of manufactured figure this
project refuses everywhere else.

**The exception list is closed.** Anything not on it uses the standard
review.

---

## 4. Measured Results rendering

### Text — required in every environment

```
  Execution latency       ##################|.......    11.52 ms
                                                        limit 20.00 ms

  Thermal power density   ###############|..........     0.051 W/mm2
                                                        limit 0.080 W/mm2

  Energy per job          ##########.................    40.39 mJ
                                                        no limit

  System cost             ###################|######   113.40 USD
                                                        limit 100.00 USD  OVER
```

Rules:

- `|` marks the requirement. The bar is scaled so the requirement sits at a
  fixed column, which makes "how close am I" readable across rows.
- A metric with no requirement in the application prints `no limit` and no
  `|`. **A requirement line is never invented to fill the column.**
- `Energy per job` has no requirement in any application. It is shown
  anyway, with its unit and `no limit`, because hiding a physical quantity
  for want of a threshold removes the one figure that explains the
  relationship between power and time. It is **never** used in the
  deployment verdict.
- Exceeding the requirement appends `OVER`. The marker is a word, not a
  colour, so it survives a log file and a monochrome printout.
- Units are always printed. A bar without a unit is a shape.

### PNG — additional, where the environment can show it

In Jupyter or Colab, the review additionally renders the bar chart and the
balance chart as images and displays them inline.

**A PNG failure must not fail the review.** Text output is the contract;
images are an enhancement. If matplotlib is missing, the display fails, or
the file cannot be written, the review completes and prints exactly:

```
Inline image rendering was unavailable.
The complete text-based engineering review is shown above.
```

Fixed wording, because a missing image must not read as a failed analysis or
a failed validation. It is a missing convenience above a complete result.

---

## 5. Where the contract lives

A document alone is what RC2 already had. The contract is therefore also a
code object:

```
ppact/review.py

    WORKFLOW_REGISTRY        = (Workflow(...), ...)
    STANDARD_REVIEW_CONTRACT = (Section(...), ...)

        section_id
        canonical_title
        variant            single | comparison | both
        required           bool
        renderer           callable
        needs              the data objects it consumes
        order              int

    EXEMPT_WORKFLOWS = (...)

    render_standard_engineering_review(analysis) -> None
```

Rules the code must satisfy, each of them checked:

1. Every applicable workflow delegates its **final engineering result**
   exclusively to `render_standard_engineering_review`. A workflow may
   render input guidance and progress information; it may not assemble,
   omit, reorder or duplicate review sections.
2. Every required section for the variant appears in the output.
3. The single variant emits `latency_flow` and never
   `latency_change`; the comparison variant, the reverse.
4. Every renderer consumes result objects and **calls no engine function**.
   A renderer that can compute can change a result inside a presentation
   change.
5. All sections use the same configuration identity and the same result
   objects. The bars and the balance chart describe the same designs.
6. No workflow asks whether to show the review.

---

## 6. Default policy

### Explicit choice required — no default

```
Application            Accelerator size       Priority
Host processor         Memory technology      Analysis mode
CPU core count         Memory unit count      Menu activity
Accelerator class      Process node           What-if parameter
                       Cooling class
```

An empty entry selects nothing:

```
No selection was entered.

This question requires an explicit engineering choice.
Enter one of the listed option numbers: 1, 2, 3, or 4.
Enter H for additional details.
```

Empty input is distinguished from a mistyped one. `Invalid selection: ''`
is wrong: an empty entry is not a typo, it is a decision not yet made.

### Enter permitted

Page advance only:

```
Press Enter to continue.
Press Enter to view the next section.
```

These are not decisions.

### Never a default

```
Back    Exit    Cancel    Return    any Yes/No that changes a user's choice
```

If Enter means "leave", users leave by accident.

### Starting point is not a default

An internal starting configuration remains available as a comparison anchor
**after** the user has explicitly chosen a comparison workflow. It is never
offered as a pre-selected answer to a question.

---

## 7. Failure conditions

The build fails if any of these hold:

```
A completed analysis omits the mandatory visual-evidence sections.
  Text-based measured bars and balance data ARE visual evidence. In an
  image-capable environment, failing to produce an optional PNG is not on
  its own a contract violation.
A required section is missing from any workflow's output.
A single analysis emits Latency Change Breakdown.
A flow station is drawn out of execution order.
An overlap decomposition is presented as a sum.
The "longer of the two" line disagrees with the two figures it follows.
A comparison emits Latency Flow.
Measured Results are absent from any registered engineering-analysis
  workflow.
Architecture Balance, or Architecture Balance Comparison as required by the
  registered variant, is absent from any workflow with
  produces_engineering_analysis = true.
A workflow asks whether to show the review.
An engineering question carries a default.
An empty entry selects an option.
Back, Exit, Cancel or Return is a default.
A renderer calls an engine function.
Two sections in one review describe different configurations.
An executable analysis path has no registered workflow_id.
A non-analysis workflow has no specific exemption_reason.
A measured-results row is labelled Thermal Margin.
Energy per job is used in a deployment verdict.
A single-design balance normalizes against itself.
An exported report omits the full boundary statement.
The two limiting-factor figures are merged into one.
```

Each gets a positive control: the condition is created deliberately and the
rule that owns it must be the rule that fails. A control satisfied by some
other check proves that other check.

---

## 8. What this contract does NOT establish

- **That the review is useful.** It fixes what appears and in what order.
  Whether a reader is helped is a question about readers.
- **That the visual rendering is good.** The bars are legible and carry
  units; whether the design is clear is a judgement this contract cannot
  make.
- **That every executable path has been correctly classified.** Coverage is
  derived from the central Workflow Registry. The remaining risk is not an
  omitted handwritten list but an executable entry point that bypasses the
  registry. Every runnable path must therefore carry a registered
  `workflow_id`, and any unregistered path fails the build.

The third is the weakness worth watching, and it is the reason the registry
is authoritative in one direction only: **the menu reads the registry; the
registry never reads the menu.** A registry derived from menu presentation
would let a UI change move the analysis scope, which is a different version
of the same failure.

---

## Decisions closing Phase 1

1. **Applicability** — derived from a central Workflow Registry. Not
   handwritten, and not inferred from menu presentation. An executable
   analysis path with no registered workflow_id fails the build.

2. **Thermal** — show Thermal Power Density against the modelled thermal
   limit. Do not claim a thermal margin the engine does not compute.

3. **Energy per Job** — always shown with its unit; `no limit` where no
   requirement exists; never part of the deployment verdict.

4. **Boundaries** — full statement on the first session review and on every
   exported report; fixed concise statement on later interactive reviews.

## What Phase 2 must prove about the CURRENT code

The checks are written before the implementation, and the present RC2 tree
must fail them for reasons that name the real defects:

```
Architecture Balance missing from multiple analysis workflows
Measured Results missing from console workflows
No central standard review renderer exists
Workflow applicability is not centrally registered
Engineering questions carry defaults
The Education menu defaults to Back
A completed analysis asks whether to show the review
At least one menu-driven analysis path raises an exception
```

If any of these does not reproduce, the Phase 2 checks do not yet describe
the defect they were written for.
