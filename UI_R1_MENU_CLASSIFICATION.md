# UI-R1 — Menu Classification

**No code changed. No menu changed. No tests run.**

Classification only, as requested. Every row below is read from the
running system, not from an intended design.

---

## The finding UI-R0 pointed at

There are two menu systems, not one.

```
flat menu    30 entries, numbered, all at one level
modes         6 modes, 29 tasks, different titles for the same functions
```

A task can appear in three modes under three names and once more on the
flat list under a fourth. `task_decide` is in Education, Research and Demo,
and on the flat list as *"Explain a change: what, why, how sure, what to
do"*.

**The problem is not too few features. It is that every feature is exposed
at the same level.**

---

## Classification

```
A  Start                 create and run a design
B  Analyze               PPACT analysis of the current design
C  Compare and Improve   comparison, explanation, sensitivity, exploration
D  Learn and Validate    teaching, examples, verification, instructor tools
```

| # | Title | Task ID | Modes | Cat | Dup | Input | Output | Action |
|---|---|---|---|---|---|---|---|---|
| 1 | Quick Start: one worked design, reviewed | `task_quickstart` | quick (auto) | A | unique | application | one worked review | **Keep** |
| 2 | System Flow: see the design, then what limits it | `task_system_flow` | **none** | B | unique | application | 13-section report | **Keep**, rename *Analyze Current Design* |
| 3 | About: what this is and how to read it | `task_about` | demo, validation | D | unique | – | prose | **Move** under Learn |
| 4 | Think like an architect: a guided comparison | `task_guided` | education | D | unique | – | guided comparison | **Keep** under Learn |
| 5 | Take the lessons, in order | `task_lessons` | education | D | unique | – | lesson sequence | **Keep** under Learn |
| 6 | Take a set challenge | `task_challenge` | challenge | D | unique | – | challenge + marking | **Keep** under Learn |
| 7 | Pick a question and watch it answered | `task_demo` | demo | D | unique | – | worked answer | **Keep** under Learn |
| 8 | Explain a change: what, why, how sure, what to do | `task_decide` | education, research, demo | C | **3 modes** | – | change report | **Keep** under Compare |
| 9 | Propose a change and have it reviewed | `task_review` | education, research | C | 2 modes | – | review of a proposal | **Merge** with 8 |
| 10 | Try a change and put it back | `task_whatif` | education, research | C | 2 modes | – | reversible what-if | **Keep** under Compare |
| 11 | What is analysed, and what is not | `task_framework` | demo, validation | D | 2 modes | – | scope statement | **Move** under Learn |
| 12 | What was checked, and what is still missing | `task_validation_summary` | validation | D | unique | – | validation status | **Keep** under Validate |
| 13 | Recent designs, saved designs, search and export | `task_workspace` | research | A | unique | – | saved design list | **Keep** under Start |
| 14 | Design a system step by step (start here) | `task_game` | education | A | unique | – | a built design | **Keep** under Start |
| 15 | Run a system for a while and see the dashboard | `task_runtime` | education, research | B | 2 modes | application, accelerator, memory | runtime dashboard | **Keep** under Analyze |
| 16 | Starting point and design examples | `task_designs` | demo | A | unique | – | example designs | **Move** under Start |
| 17 | Compare HBM3E and HBM4 on an LLM workload | `task_memory_generations` | research | C | unique | application | memory generation comparison | **Merge** with 29 |
| 18 | Why did the number change | `task_explain` | **none** | C | unique | application, baseline/comparison accel + memory | attribution report | **Move** under Compare |
| 19 | Reproducibility: what ran, and does a rerun agree | `task_reproducibility` | validation | D | unique | – | rerun agreement | **Move** under Validate |
| 20 | How much does this verdict depend on an assumption | `task_sensitivity` | education, research, validation | C | **3 modes** | model_assumption | sensitivity report | **Move** under Compare |
| 21 | Migration: what must hold when a design moves | `task_migration` | research | D | unique | – | migration invariants | **Move** under Validate |
| 22 | Gold reference scenarios | `task_gold` | validation | D | unique | – | expected results | **Move** under Validate |
| 23 | Interpret a result against its application domain | `task_interpret` | challenge | D | unique | application | domain interpretation | **Move** under Learn |
| 24 | Industry cases: what the model can and cannot express | `task_industry` | demo, validation | D | 2 modes | – | case commentary | **Keep** under Validate |
| 25 | Innovation Challenge: starting point, your change, report | `task_innovation` | challenge | D | unique | accelerator, memory | student report | **Keep** under Learn |
| 26 | Grading rubric (instructor) | `task_rubric` | challenge | D | unique | – | rubric | **Hide** behind an instructor entry |
| 27 | Evaluate an application against the default candidates | `task_evaluate` | research | C | unique | application | candidate ranking | **Keep** under Compare |
| 28 | Sweep the whole design space and rank the survivors | `task_sweep` | research | C | unique | application, sweep_objective | ranked survivors | **Keep** under Compare |
| 29 | Compare memory technologies on their own | `task_memory` | research | C | unique | memory_comparison_set | memory comparison | **Keep**, absorb 17 |
| 30 | Build one candidate by hand | `task_custom` | research | A | unique | application, host, accelerator, memory | one design | **Keep** under Start |

---

## Category totals

```
A  Start                  5     1, 13, 14, 16, 30
B  Analyze                2     2, 15
C  Compare and Improve    8     8, 9, 10, 17, 18, 20, 27, 28, 29
D  Learn and Validate    15     3, 4, 5, 6, 7, 11, 12, 19, 21, 22, 23, 24, 25, 26
```

**Half the top-level menu is teaching and validation material.** That is
not wrong for a teaching tool; it is wrong that it sits at the same level
as *"analyse this design"*.

---

## The two unreachable tasks

```
task_system_flow    in no mode
task_explain        in no mode
```

`task_system_flow` is the thirteen-screen analysis built over this whole
session - the most developed function in Studio, and the only route to it
is entry 2 of a flat list of thirty.

`task_explain` answers *"why did the number change"* and is reachable only
the same way.

---

## Duplicates

Same task, several modes, different titles each time:

| Task | Modes | Titles seen |
|---|---|---|
| `task_decide` | 3 | *Explain a change...* / *Ask why a number changed* / *Why did that number change?* |
| `task_sensitivity` | 3 | *How much does this verdict depend...* / *See how much a conclusion depends...* / *Test how far a verdict survives...* |
| `task_whatif` | 2 | *Try a change and put it back* (same both) |
| `task_review` | 2 | *Propose a change and have it reviewed* (same both) |
| `task_runtime` | 2 | *Run a system for a while...* / *Run a design and watch the stations* |
| `task_about`, `task_framework`, `task_industry` | 2 each | differ |

**Six tasks carry more than one name.** A user who learns one name does not
recognise the same function elsewhere.

---

## Near-duplicate functions

```
17  Compare HBM3E and HBM4 on an LLM workload      one fixed comparison
29  Compare memory technologies on their own       general comparison
```

17 is a special case of 29 with the choices pre-made. **Merge**: keep 29
and offer 17's pairing as a preset within it.

```
 8  Explain a change ... what to do
 9  Propose a change and have it reviewed
```

Both take a change and report on it. 8 explains one that happened, 9 judges
one proposed. **Merge** into a single *Evaluate a change* with a direction
question, or keep both and make the titles say which is which - they do
not today.

---

## System Flow as one report

The thirteen screens are one document, not thirteen menu entries. Proposed
top-level shape:

```
Analyze Current Design
    1. System Flow
    2. Performance          (constraints, block throughput, bottleneck)
    3. Traffic              (memory analysis, traffic balance)
    4. Power
    5. Area
    6. Cost
    7. Position in the design space
    8. PPACT Summary
    9. Recommendation
```

Thirteen internal sections collapse to nine headings by grouping the four
Performance screens and the two Traffic screens. **The internal order is
unchanged** - it is the reading order the analysis chain requires, and
`Recommendation` stays last.

---

## Input burden

18 registered questions, **every one `requires_explicit_choice=True`**.

For the most common path - *analyse this design* - a user answers
`application` and nothing else, because `task_system_flow` takes the
application's first example design. That is one question and it is fine.

For `task_custom` it is four: application, host, accelerator, memory. Also
fine.

**Three things discussed and not present as inputs:**

```
Evaluation Mode   module exists, no screen and no question
Reference         user benchmark values - not implemented
Clock             not an input at any level
```

`Evaluation Mode` is the notable one: the scoring already defaults to
Design Assessment and the user cannot see or change that.

---

## Recommended structure

```
Start
    Quick Start
    Build a design step by step
    Build one candidate by hand
    Starting points and examples
    Saved designs

Analyze
    Analyze Current Design      (the 13-screen report)
    Run and watch the stations

Compare and Improve
    Evaluate a change           (merge 8 + 9)
    Try a change and put it back
    Why did the number change
    How much does this depend on an assumption
    Compare memory technologies (absorb 17)
    Evaluate an application against candidates
    Sweep the design space

Learn and Validate
    Lessons
    Guided comparison
    Challenges
    Innovation challenge
    Worked questions
    Interpret a result
    What is analysed, and what is not
    About

    Validation
        What was checked, and what is missing
        Reproducibility
        Gold scenarios
        Industry cases
        Migration invariants
        Instructor rubric
```

```
30 flat entries  ->  4 groups, 5 top-level entries under Analyze and Start
```

---

## What this document does not do

It does not change a menu, merge a task, or rename anything. It does not
establish that the proposed grouping is better than the current one for a
user - nobody has been asked. It records what is there and what appears
duplicated, and every Keep/Merge/Move/Hide above is an opinion for review.

---

*Author: Roger Kim / Copyright (c) 2026 Roger Kim & EdgeChipLab*
