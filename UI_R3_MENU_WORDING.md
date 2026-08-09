# UI-R3 — Menu Wording

**No code changed. No menu changed. No tests run.**

Structure settled in UI-R2 and adjusted by the four points raised. This
document fixes the words.

---

## Adjustments from the review

```
Workspace       folded into Open Design - a user opens, they do not
                visit a workspace
Analyze         given a navigation tree; it is most of Studio and had
                two entries
Compare         opened out to three, since Design vs Benchmark is
                coming
Validation      placed last in the journey, not fourth
History         added
```

---

## The cycle

```
Create  ->  Analyze  ->  Recommendation  ->  Improve  ->  Analyze
```

Not a line with an end. A user who acts on a recommendation immediately
wants to know whether it worked, and the menu returns them to Analyze.
**History exists because that loop runs several times** and nothing today
records what changed between passes.

---

## Every entry: name and one line

### Start

```
New Design
Build a system from scratch, guided or direct.

Open Design
Return to a design you built earlier.

Example Designs
Start from a design that already works.

Quick Start
See one design analysed end to end, with nothing to choose.
```

### Analyze

```
Analyze Current Design
Understand how your design performs and what limits it.
```

Inside it, a navigation tree rather than ten menu entries:

```
    Overview            Where one job's time goes.
    Performance         Whether the design meets its throughput and
                        latency requirements, and which stage binds first.
    Traffic             How evenly the internal stages are matched.
    Power               What the design draws, and over which window.
    Area                Silicon and board area against the SoC budget.
    Cost                System cost against the bill-of-materials budget.
    Design Space        Whether this design is unusual among what the
                        model can build.
    PPACT Dashboard     All five axes, side by side.
    Recommendation      What to change next, and how sure that is.
```

**Read in order it is a report; entered from the tree it is a reference.**
Both work, and the order is the analysis chain's - `Recommendation` last
because it rests on everything above it.

```
Watch a Design Run
Watch a design execute and see where the time goes.
```

### Compare and Improve

```
Compare Designs
Put two designs side by side and see what differs.

    Design vs Design        Two designs you have built.
    Design vs Benchmark     Your design against a reference.
    Memory Comparison       Memory technologies on their own.

Explain This Result
Find out why a figure is what it is.

Improve My Design
Try a change, review a proposal, and see how solid the result is.

    Try a Change            Change one thing; put it back at any point.
    Review a Proposed Change  Have a change assessed before you make it.
    How Solid Is This Result?  How far the verdict survives its
                            assumptions.

Explore Design Space
Search the space and rank what meets the requirements.
```

### History

```
History
See how your design changed, and what each change bought.
```

```
    Revision 1   npu_32x32 / LPDDR5 x2        Performance 50  Cost 100
    Revision 2   npu_64x64 / LPDDR5 x2        Performance 70  Cost  84
    Revision 3   npu_64x64 / HBM3E x2         Performance 70  Cost  61
```

**Not implemented.** It needs a revision store the model does not have,
and the arrows a designer wants - `Performance up, Cost down` - are
comparisons between two evaluated designs, which Studio can already do
one pair at a time. Listed here so the menu has a place for it.

### Learn

```
Learning Path
Work through the material in order.

Guided Tutorial
Think through a comparison with the reasoning shown.

Challenges
Take a set problem and see how it is marked.

Innovation Challenge
Start from a given design, make your change, and produce a report.

Worked Questions
Pick a question and watch it answered.

Interpret a Result
Read a result against what its application actually needs.

What This Model Analyses
What is inside the model, and what is not.

About Studio
What this is and how to read it.
```

### Validation

Last in the journey. A student rarely arrives; a researcher starts here.

```
Validation Status
What has been checked, and what has not.

Reproducibility
Whether a rerun agrees with the recorded run.

Gold Scenarios
Reference cases and the results they must produce.

Industry Cases
What the model can and cannot express about real products.

Migration Invariants
What must still hold when a design moves to another process or platform.

Instructor Tools
Grading rubric and marking guidance.
```

### Evaluation Mode

A header on every screen carrying a score, not a menu entry.

```
Evaluation Mode: Design Assessment
A score of 50 means the design meets its requirement exactly.

Evaluation Mode: PPACT Benchmark
A score of 50 is the midpoint of the range. This is a comparison, not a
pass mark.

Evaluation Mode: User Benchmark
A score of 50 equals the reference you set.
```

---

## Wording rules used

**The name is the intent; the line says what the user gets.** Not what the
screen contains - *"Explain a change: what, why, how sure, what to do"*
lists four sections in a menu entry, and the sections are on the screen
anyway.

**Second person for actions, third for facts.** *"Try a change"* is
something the user does. *"What has been checked"* is a fact about the
system.

**No engine vocabulary in a title.** `survivors`, `stations`, `sweep` and
`workspace` are words from inside the model. They stay on the screens
where they are defined.

**No question mark in an entry that is not a question.** *"How Solid Is
This Result?"* keeps one because the user is asking it.

---

## Renames, with the reason

| Was | Is | Reason |
|---|---|---|
| System Flow: see the design, then what limits it | Analyze Current Design | named a screen; the user wants to analyse |
| Why did the number change | Explain This Result | they have a result, not a number |
| Run a system for a while and see the dashboard | Watch a Design Run | says what they will see |
| Take the lessons, in order | Learning Path | a path is followed |
| How much does this verdict depend on an assumption | How Solid Is This Result? | the question actually being asked |
| Sweep the whole design space and rank the survivors | Explore Design Space | `sweep` and `survivors` are engine words |
| Recent designs, saved designs, search and export | Open Design | a user opens; they do not visit a workspace |
| Grading rubric (instructor) | Instructor Tools | – |
| Propose a change and have it reviewed | Review a Proposed Change | – |
| Compare HBM3E and HBM4 on an LLM workload | *(a preset inside Memory Comparison)* | a special case, not a peer |

---

## Structure

```
Start                   4
Analyze                 2   (one with a 9-item tree)
Compare and Improve     4   (two with sub-entries)
History                 1   not implemented
Learn                   8
Validation              6
Evaluation Mode         a header
```

```
30 flat entries  ->  6 groups, 25 entries
```

---

## What this does not establish

That the wording is clearer to a first-time user. It is written to a set
of rules, and the rules are an argument. Nobody outside this project has
read any of it.

`History` is a menu entry for a feature that does not exist, which is worth
saying plainly: listing it here does not make it available.

---

*Author: Roger Kim / Copyright (c) 2026 Roger Kim & EdgeChipLab*
