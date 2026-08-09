# UI-R4 — Workflow

**No code changed. No menu changed. No tests run.**

Final structure. Seven top-level entries, every one a verb, arranged as
the loop a designer actually runs rather than as a list of what the tool
contains.

---

## The rule that decides everything below

> **A menu entry names a result the user will get. If it names a thing the
> project built, it is wrong.**

```
good    Analyze Current Design    Compare Designs    Verify Results
bad     System Flow    Workspace    Validation Summary    Challenge
```

The first set says what the user will have done. The second names
functions - accurate to the code and silent about the user.

That rule is what turned `System Flow` into `Analyze Current Design`, and
it is why `Validation` becomes `Verify`: a noun describes a discipline, a
verb describes what the user is about to do.

---

## Top level

```
Start      Create or open a design.
Analyze    Understand how your design performs and what limits it.
Improve    Try changes and see whether they help.
Compare    Put designs side by side and see what differs.
History    See how your design changed, and what each change bought.
Learn      Work through the material, from first lesson to challenge.
Verify     Confirm the analysis is sound and reproducible.
```

**Seven, in the order they are used.** Not alphabetical, not by size.
`Learn` and `Verify` sit last because a student reaches them late and a
researcher starts there deliberately - neither arrives by accident.

---

## The loop

```
Start
  ↓
Analyze  ───────────┐
  ↓                 │
Recommendation      │
  ↓                 │
Improve  ───────────┘
  ↓
Compare
  ↓
Verify
```

`Analyze → Recommendation → Improve → Analyze` is the cycle Studio exists
for. Everything else is entered from it or leads back to it.

**History records the loop.** Without it a designer on their fourth
revision has no account of the first three.

---

## Start

```
Start
Create or open a design.

    New Design
    Build a system from scratch, guided or direct.

    Open Design
    Return to a design you built earlier.

    Example Designs
    Start from a design that already works.

    Quick Start
    See one design analysed end to end, with nothing to choose.
```

---

## Analyze

```
Analyze Current Design
Understand how your design performs and what limits it.

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

Watch a Design Run
Watch a design execute and see where the time goes.
```

Order unchanged from UI-R3 and confirmed in review. `Recommendation` last
because it rests on everything above it.

---

## Improve

Separated from Compare. They were one group and are two intents: improving
acts on THIS design, comparing sets it against another.

```
Improve My Design
Try changes and see whether they help.

    Try a Change
    Change one thing; put it back at any point.

    Review a Proposed Change
    Have a change assessed before you make it.

    Explain This Result
    Find out why a figure is what it is.

    How Solid Is This Result?
    See how far the verdict survives its assumptions.

    Explore Design Space
    Search the space and rank what meets the requirements.
```

`Explain This Result` moves here from Compare. A user asking why a figure
is what it is has usually just changed something.

---

## Compare

Every entry a verb, as asked.

```
Compare
Put designs side by side and see what differs.

    Compare Designs
    Two designs you have built.

    Compare with Benchmark
    Your design against a reference.

    Compare Memory Technologies
    Memory technologies on their own.
```

---

## History

```
Revision History
See how your design changed, and what each change bought.

    Revision 1   npu_32x32 / LPDDR5 x2     Performance  50   Cost 100
    Revision 2   npu_64x64 / LPDDR5 x2     Performance  70   Cost  84
    Revision 3   npu_64x64 / HBM3E x2      Performance  70   Cost  61
```

Named `Revision History` rather than `History`, which could mean a
browsing history.

**Not implemented.** It needs a revision store the model does not have.
The arrows a designer wants - `Performance up, Cost down` - are
comparisons between two evaluated designs, which Studio can do one pair at
a time; what is missing is the record of which designs those were.

---

## Learn

```
Learning Center
Work through the material, from first lesson to challenge.

    Learning Path
    Work through the material in order.

    Guided Tutorial
    Think through a comparison with the reasoning shown.

    Take a Challenge
    Solve a set problem and see how it is marked.

    Innovation Challenge
    Start from a given design, make your change, and produce a report.

    Watch a Question Answered
    Pick a question and see it worked through.

    Interpret a Result
    Read a result against what its application actually needs.

    What This Model Analyses
    What is inside the model, and what is not.

    About Studio
    What this is and how to read it.
```

`Challenges` became `Take a Challenge` and `Worked Questions` became
`Watch a Question Answered` - both were nouns naming content rather than
verbs promising a result.

---

## Verify

```
Verify Results
Confirm the analysis is sound and reproducible.

    Check What Was Verified
    What has been checked, and what has not.

    Reproduce a Run
    Confirm a rerun agrees with the recorded one.

    Check Gold Scenarios
    Reference cases and the results they must produce.

    Read Industry Cases
    What the model can and cannot express about real products.

    Check Migration Invariants
    What must still hold when a design moves platform.

    Instructor Tools
    Grading rubric and marking guidance.
```

`Validation Status` became `Check What Was Verified`. The old name was
the clearest example of the rule: it named a report, not an action.

---

## Evaluation Mode

A header on every screen carrying a score. Not an entry - a user does not
set out to change an evaluation mode; they see a score and want to know
what it is relative to.

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

## Wording rules, final

```
1  The name promises a result the user will get.
2  The one-line says what they get, not what the screen contains.
3  Second person for actions, third for facts.
4  No engine vocabulary in a title.
5  A question mark only where the user is asking the question.
```

Rule 1 was added in this round and is the one that decides the others.

---

## Structure

```
Start       4
Analyze     2   (one with a 9-item tree)
Improve     5
Compare     3
History     1   not implemented
Learn       8
Verify      6
```

```
30 flat entries  ->  7 verbs, 29 entries, one main path
```

The entry count barely fell. **What changed is that there is now one route
through them**, and a user who follows it does not choose between thirty
peers at any point.

---

## What this does not establish

That any of it is easier. Five documents of argument and no user. The
rules are internally consistent and untested against a person, and the
loop `Improve → Analyze` is an assumption about what a designer wants
next, not an observation of what they do.

`Revision History` is a menu entry for a feature that does not exist.

---

*Author: Roger Kim / Copyright (c) 2026 Roger Kim & EdgeChipLab*
