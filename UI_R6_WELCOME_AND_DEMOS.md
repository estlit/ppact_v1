# UI-R6 — Welcome, Demos, and Help

**No code changed. No menu changed. No tests run.**

UI-R5 specified the screens. This revises three of them and corrects one
figure I should have checked before it was quoted.

---

## The demo count

The review referred to "about 20 demos". **There are 15**, and they are
better than that number suggests - each is a question a designer actually
asks:

```
 1  memory      Does a faster memory always help?
 2  engine      Does a bigger engine always help?
 3  dual        Are two engines twice as fast?
 4  node        Does a finer process node make it faster?
 5  order       Three ways to spend money. Which one works?
 6  finest      Is the finest process node the fastest?
 7  together    When is a second engine worth having?
 8  shipping    Is the fastest design the one you ship?
 9  host        Which should you upgrade first?
10  offload     Where should the preprocessing run?
11  capacity    Does more memory make it faster?
12  fit         What happens when the model does not fit?
13  cheaper     Can a cheaper memory be the right answer?
14  split       Does splitting a job between two engines help?
15  nodecost    Is the newest process node the cheapest to make?
```

**Fifteen is the number a content plan should be built on.** A fortnight
of daily videos, not three weeks.

Two of the suggested demo titles do not exist as demos: `HBM3E vs HBM4`
is `task_memory_generations`, a comparison tool, and `Traffic Balance` is
an analysis section. They could become demos; they are not ones today.

---

## 1. Welcome Screen, revised

Value, then feature, then philosophy - as instructed.

```
==============================================================================
                              PPACT STUDIO

                  Constraint-Based Design Assessment
                       for AI Hardware Systems

                       Analyze.  Compare.  Improve.
==============================================================================

  Design better AI hardware through constraint-driven analysis.

  Every reported result is evaluated against explicit design constraints.

  Studio also tells you what it cannot establish.

------------------------------------------------------------------------------

  Today's Demonstration                                          Demo 001

  Does a faster memory always help?

------------------------------------------------------------------------------

  What would you like to do today?

    1. Start a New Design          Build a system from scratch.
    2. Open an Existing Design     Return to a design you built earlier.
    3. Explore Demonstrations      Fifteen questions, worked through.
    4. Learn PPACT                 Work through the material in order.
    5. All Tools                   Everything Studio can do.

    D. Run today's demonstration

  [D]
```

**Default is `D`.** A first-time user pressing Enter gets a worked example
rather than a menu, which is the shortest path from launch to something
worth seeing.

**`Explore Demonstrations` replaces `Analyze an Example Design`.** An
example is a thing to copy; a demonstration answers a question. The demos
already have the questions.

**"Fifteen questions, worked through"** states the count. A menu entry
promising demonstrations without saying how many invites the reader to
imagine either three or three hundred.

---

## 2. Demo numbering

```
Demo 001    Does a faster memory always help?
Demo 002    Does a bigger engine always help?
...
Demo 015    Is the newest process node the cheapest to make?
```

**One number, used by Studio and by the video.** A student watching Demo
007 opens Demo 007 in Studio and gets the same design, the same figures
and the same conclusion.

That only works if the numbers are stable. **A demo's number is fixed on
first publication and never reused**, even if the demo is later withdrawn -
a video referring to Demo 007 must not find a different scenario there.

New demos take the next free number. `HBM3E vs HBM4` becoming Demo 016
would be a natural first addition, since the comparison already exists as
a tool.

**Today's demonstration rotates by date**, `day-of-year modulo 15`, so the
screen changes without anyone maintaining a schedule.

---

## 3. Help, specified

```
H       explain this screen
?       explain the current question
F       show the formula behind a figure
```

`H` answers three things, in this order:

```
  What this screen shows
      The throughput each stage could sustain on its own, and which one
      sets the system rate.

  What it does not establish
      Whether the stage times match real hardware. They are analytical
      estimates, not measurements.

  When to use something else
      To find out whether a change would help, use Improve > Try a
      Change. This screen describes the design as it is.
```

**The third part is new and is the useful one.** A user reading a screen
that cannot answer their question needs to be told where to go, not only
that they are in the wrong place.

**Rule: every `H` answers all three.** A screen with nothing to say about
the second has not been thought about.

---

## 4. Planned features

```
    5. History      See how your design changed.
                    Coming in a future release.
```

Replaces `[Planned]`. A bracketed tag reads as a status code; a sentence
reads as a sentence.

---

## 5. Analyze tree, revised

`Current Design` added as section 1, as suggested.

```
    >  1. Current Design      What is being analysed.
       2. Overview            Where one job's time goes.
       3. Performance         Requirements, and which stage binds first.
       4. Traffic             How evenly the internal stages are matched.
       5. Power               What the design draws, and over which window.
       6. Area                Silicon and board area against the budget.
       7. Cost                System cost against the BOM budget.
       8. Design Space        Whether this design is unusual.
       9. PPACT Dashboard     All five axes, side by side.
      10. Recommendation      What to change next, and how sure that is.
```

**Ten sections, and the first says what the other nine are about.** The
header line already carries the configuration, but a reader arriving mid-
report from the tree has not seen it - and a design's own summary deserves
more than one line.

---

## 6. About Studio

```
About Studio

    What Studio does
    What PPACT means
    How to read a Studio figure
    What Studio does not establish
    Version, licence, and how to cite this
```

**`What Studio does not establish` is a section of About**, not a
footnote. It is the shortest honest summary of the project: no measured
hardware, no educational-effectiveness study, no external holdout, and
several axes with open definitions.

---

## Structure

```
Welcome         5 choices + today's demo
Top nav         7 verbs
Analyze         1 entry, 10-section tree
Demos          15, numbered, shared with the video series
Help            H / ? / F, three-part answers
```

---

## What this does not establish

That a welcome screen defaulting to a demo is better than one defaulting
to a menu. It is an argument about first impressions, and no one has
launched this and been watched.

The demo-video pairing is a content plan, not a feature: **Studio does not
know a video exists**, and nothing here makes the numbers agree except the
discipline of whoever publishes them.

---

*Author: Roger Kim / Copyright (c) 2026 Roger Kim & EdgeChipLab*
