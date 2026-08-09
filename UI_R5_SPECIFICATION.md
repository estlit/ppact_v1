# UI-R5 — Studio UI Specification v1.0

**No code changed. No menu changed. No tests run.**

UI-R1 to R4 settled what the menus are. This one specifies how they appear
on screen, at the level someone could implement from.

---

## 1. Welcome Screen

Shown before any menu, once per session.

```
==============================================================================
                              PPACT STUDIO

                  Constraint-Based Design Assessment
                       for AI Hardware Systems

                       Analyze.  Compare.  Improve.
==============================================================================

  Every figure in Studio is measured against a stated constraint, and
  every figure says what it does not establish.

  What would you like to do today?

    1. Start a New Design          Build a system from scratch.
    2. Open an Existing Design     Return to a design you built earlier.
    3. Analyze an Example Design   Start from a design that already works.
    4. Learn PPACT                 Work through the material from the
                                   beginning.

    5. All Tools                   Everything Studio can do.

  [1]
```

**Four choices, not thirty.** The fifth is the escape hatch for someone who
knows what they want; it leads to the seven-verb workflow menu.

**The two lines under the rule are the philosophy statement**, and they are
two lines rather than a paragraph because nobody reads a paragraph on a
launch screen. They say the one thing that distinguishes Studio: figures
carry their constraint, and absent figures say so.

**No version number, no copyright, no build date on this screen.** They
belong in `About Studio`. A launch screen crowded with provenance reads as
a tool that is proud of itself rather than useful.

---

## 2. Top Navigation

Reached from `All Tools`, or after the first task completes.

```
==============================================================================
  PPACT STUDIO                              Evaluation Mode: Design Assessment
==============================================================================

    1. Start        Create or open a design.
    2. Analyze      Understand how your design performs and what limits it.
    3. Improve      Try changes and see whether they help.
    4. Compare      Put designs side by side and see what differs.
    5. History      See how your design changed.            [Planned]
    6. Learn        Work through the material, from first lesson to
                    challenge.
    7. Verify       Confirm the analysis is sound and reproducible.

    0. Back
  [2]
```

**The evaluation mode sits in the header of every screen carrying a
score.** Here it is informational; on a scored screen it is selectable.

**`[Planned]` is a required marker, not a courtesy.** A menu entry that
looks available and is not costs the user a click and some trust; one that
says so costs neither. It is right-aligned so the eye finds it before the
description.

**Default is 2, `Analyze`** - after the first pass through Start, the
common next action.

---

## 3. Analyze Report Navigation

`Analyze Current Design` is one report with a tree, not nine menu entries.

```
==============================================================================
  ANALYZE CURRENT DESIGN                    Evaluation Mode: Design Assessment
  Industrial Vision  ·  Cortex-A78 x4  ·  NPU 32x32  ·  LPDDR5 x2
==============================================================================

    >  1. Overview           Where one job's time goes.
       2. Performance        Requirements, and which stage binds first.
       3. Traffic            How evenly the internal stages are matched.
       4. Power              What the design draws, and over which window.
       5. Area               Silicon and board area against the budget.
       6. Cost               System cost against the BOM budget.
       7. Design Space       Whether this design is unusual.
       8. PPACT Dashboard    All five axes, side by side.
       9. Recommendation     What to change next, and how sure that is.

    N. Next section       A. Read all in order       0. Back
  [N]
```

**Two ways through, both first-class.** `N` walks the report in order for a
first read; a number jumps for a reader who knows what they want.

**`>` marks position.** A nine-section report needs the reader to know
where they are, and a scrollback is not a location.

**The design line under the title is not decoration.** Every figure below
depends on it, and a reader returning after a change needs to see which
design they are looking at without navigating away.

**`A. Read all in order` prints the whole report** - the current
behaviour, kept because it is what a user wants the first time and what
gets pasted into a document.

---

## 4. Section screen

```
==============================================================================
  2. PERFORMANCE                            Evaluation Mode: Design Assessment
==============================================================================

  [ the section's content, unchanged from today ]

------------------------------------------------------------------------------
    N. Next: Traffic       P. Previous: Overview       T. Tree       0. Back
  [N]
```

**`Next` names the destination.** `N. Next` makes a reader guess; `N. Next:
Traffic` does not.

---

## 5. Help and Tooltips

Studio is a terminal application, so a tooltip is a keystroke.

```
H       explain this screen - what it computes and what it does not
?       explain the current question - what the answer changes
F       show the formula behind the figure under the cursor
```

**`H` already exists** for the normalisation method on the balance chart.
This generalises it: every screen answers `H`, and the answer includes what
the screen does NOT establish.

**Rule: help text says what the screen cannot do, not only what it can.**
That is the habit the whole engine was built on, and a help system that
only advertises would undo it on the one screen a confused user reads.

---

## 6. Style

```
Titles          UPPER CASE, no trailing punctuation
Menu entries    Verb first, title case
One-liners      Sentence case, full stop, one line
Body            Sentence case, wrapped at 78 columns
Figures         value then unit, aligned right
Absent figures  NOT ESTABLISHED in body, n/e in tables
Status          MET / VIOLATED / NOT CONSTRAINED
```

**The four wording rules from UI-R4 stand**, with a fifth:

```
1  The name promises a result the user will get.
2  The one-line says what they get, not what the screen contains.
3  Second person for actions, third for facts.
4  No engine vocabulary in a title.
5  A question mark only where the user is asking the question.
6  A screen that cannot answer something says so on the screen, not
   only in a document.
```

---

## 7. What a first-time user sees

```
launch      Welcome, four choices
choose 3    Analyze an Example Design
            -> one question: which application
            -> the report tree, positioned at Overview
press A     the whole report, ending in a Recommendation
press 0     back to the tree
choose 3    Improve -> Try a Change
            -> change one thing
            -> back to Analyze
```

**Two answers from the user before a full analysis is on screen.** That is
the measure this specification is written against.

---

## 8. Implementation order

```
1  Welcome screen                       new
2  Top navigation, seven verbs          rearranges the flat menu
3  Analyze report tree                  wraps the existing 13 sections
4  Section navigation                   new
5  Evaluation Mode header               module exists, screen does not
6  H / ? / F help                       generalises what exists
7  Renames, all screens                 mechanical, last
```

**Renames last.** They touch every screen and every menu-path test; doing
them before the structure settles means doing them twice.

---

## 9. What must not regress

The existing suites check things this specification could break:

```
78-column limit               every new screen
menu paths complete           every new navigation route
questions through registry    the welcome screen's four choices
no engine vocabulary          every new title and one-liner
NOT ESTABLISHED preserved     the help text especially
```

**The last one is the risk.** A help system written to be reassuring is
the natural place for a caveat to quietly disappear, and `R15`, `R21`,
`R25`, `R27` and `R32` all guard wording that a rewrite could smooth away.

---

## What this specification does not establish

That any of it is easier to use. Five documents and no user; the welcome
screen in particular is written to a theory about first impressions that
nobody has tested here.

`Revision History` remains a menu entry for a feature that does not exist,
marked `[Planned]` so the screen says so.

---

*Author: Roger Kim / Copyright (c) 2026 Roger Kim & EdgeChipLab*
