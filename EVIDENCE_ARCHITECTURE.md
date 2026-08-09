# Engineering Evidence Architecture

A simulator can be right and still be untrustworthy. What makes a result
believable is not that the arithmetic is correct — it is that a reader
can tell which run produced a figure, what that figure claims, and what
would have to change for it to change.

This chapter describes the layer that answers those questions. It exists
because of defects found in this project, and each section says which.

---

## 7.1 Dependency Registry

Every panel declares what it depends on.

```
architecture_summary          the configuration fields of both designs
measured_results              the metric values printed, for both designs
system_flow                   module utilisations, link loads, and which
                              element limits the system - not the parts
                              that produced them
bottleneck_analysis           per-module utilisations and the limiting element
architecture_balance          the axis scores, measured against the
                              application's requirement
engineering_conclusion        the sentences produced
recommended_next_comparisons  the rules that fired, their order and priorities
```

**Found as.** Two designs with different parts produced the same
Architecture Balance figure, and a check comparing configurations called
that a defect. It is not one: the balance scores against the
application's requirement, so two designs both far above budget pin at
the same value and the chart is correctly identical. Comparing
configurations asked the wrong question.

A panel added later has to declare its dependency; the registry is
checked for completeness rather than consulted when someone remembers.

---

## 7.2 Semantic Digest

> **A semantic digest hashes what a screen claims, not how it looks.**

Each panel produces a digest over its own inputs. Two panels with one
digest must draw the same thing; two with different digests must not.

### What is meaning and what is presentation

| Item | Semantic | In the digest |
|---|---|---|
| Raw value | **yes** | yes |
| Requirement | **yes** | yes |
| Limiting element | **yes** | yes |
| Provenance — selected or application default | **yes** | yes |
| Panel status | **yes** | yes |
| Field key | **yes** | yes |
| Display label | no | no |
| Unit suffix | no | no |
| Decimal places | no | no |
| Thousands separator | no | no |
| Column width | no | no |
| Colour | no | no |
| Legend position | no | no |
| Figure size | no | no |

The table is declared in code, so a new item has to be classified rather
than defaulting into the digest by being nearby.

**Found as, three times.**

*Formatting read as meaning.* Changing a number's format from four
significant figures to six changed the digest. The digest was built from
the printed string; it is now built from the value behind it.

*A label read as meaning.* Renaming "Memory packages" to "Memory
modules" changed the digest. A row's identity is the configuration field
it reports, not its printed name.

*Provenance was disappearing.* A process node left unset was skipped
from the summary entirely, so the report did not say which node the
figures were computed at. The same 7 nm chosen by the reader and arrived
at by an application default mean different things to a review, and the
row now appears with its provenance in both the display and the digest.

---

## 7.3 Visual Regression

Panels are captured as elements, not as viewport crops, and each capture
is judged on two axes that are not combined:

```
Completeness   PASS / FAIL      is the panel whole
Readability    PASS / WARNING   can it be read at this width
```

At 768 px the System Flow renders complete and small. That is
`Completeness PASS, Readability WARNING` — collapsing the two into one
verdict loses the distinction a reader needs.

**Found as.** Fixed-height clips from a heading took the next panel's
top and cut this one's bottom off. Three capture attempts failed for
three different reasons before the scroll owner was measured rather than
assumed: Streamlit scrolls `section.stMain`, not the window, so the
document stays one screen tall and a page-coordinate clip lands outside
the image.

---

## 7.4 Mutation Validation

Every rule in this layer has a control that breaks exactly one thing and
must be caught by exactly that rule.

```
different semantic input -> same figure     the renderer ignores its input
same semantic input      -> different figure  the drawing is not a function
                                              of what it was given
same value, different provenance            a meaning change
same provenance, different value            also a meaning change
a renamed label                             not a meaning change
a reformatted number                        not a meaning change
```

**Found as.** A first attempt at the second control changed the number
of semantic inputs as well as the figure, so the digest differed for a
second reason and the control proved nothing about the direction it was
meant to test. **One control must break exactly one rule.**

---

## 7.5 Evidence Chain

Every captured image links back through named digests:

```
scenario_digest
   -> config_digest
      -> semantic_digest (per panel)
         -> view_data_digest
            -> figure_digest
               -> png_digest
```

with `workflow_id` recorded alongside. When a picture changes, the first
digest that differs says which stage moved.

**Found as.** The browser harness clicked the first option while the
manifest's outcome came from a separate text walk following a scenario.
The two records described two different runs: the configuration digests
said the designs differed and the pictures beside them were identical.
Neither record was wrong about its own run, and together they were
evidence of nothing. One `Scenario.option_for()` now serves both.

---

## Accounting

```
defined checks = registered checks = executed checks = reported checks
```

**Found as.** A check sat in the runner under a name that did not exist
while the one that did was never called. The suite reported a clean run
for a rule that had never fired. A check that is written but not
executed is worse than one that is missing, because the count says it
ran.

---

## Release verdict, on three axes

Semantic correctness and human readability are different contracts, and
a single verdict over both is wrong in whichever direction it is
collapsed.

```
Semantic evidence         PASS      15/15 captures
Rendering completeness    PASS      15/15 captures
Narrow-width readability  WARNING    9/15 captures
```

The nine warnings are the 1024 px and 768 px captures, where every panel
is whole and the labels are small. Reporting one verdict would either
overstate the screens or understate the arithmetic.

---

## What this layer does not establish

That the figures are right. It establishes that a figure can be traced
to the run that produced it, that two identical pictures are identical
for a stated reason, and that a change of wording is not mistaken for a
change of result.

Whether the model matches measured hardware is a separate question, and
`DEFERRED.md` records that it is open.

*Author: Roger Kim / Copyright (c) 2026 Roger Kim & EdgeChipLab*
