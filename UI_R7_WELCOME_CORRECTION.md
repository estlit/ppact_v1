# UI-R7 — Welcome Default and Demo Metadata

**No code changed. No menu changed. No tests run.**

Two corrections to UI-R6, and one finding that changes what the demo
metadata proposal can be.

---

## 1. The welcome default was wrong

UI-R6 made `D` the default: press Enter, get today's demonstration. The
objection is correct and I should have seen it.

```
user launches Studio
presses Enter
gets  "Does a faster memory always help?"
```

**A user who has not chosen anything is shown a memory analysis.** The
reasonable inference is that Studio is a memory tool. It is a fifteenth of
what Studio does, chosen by the calendar.

Corrected:

```
Enter  ->  Quick Start        the basic flow, whole
D      ->  today's demo       one keystroke, always available
```

**Quick Start is the right default because it is the shortest complete
path**: one design, analysed end to end, ending in a recommendation. A
user who presses Enter without reading has seen what Studio is for.

---

## 2. Welcome Screen, corrected

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

  What would you like to do today?

    1. Quick Start                 One design, analysed end to end.
    2. Start a New Design          Build a system from scratch.
    3. Open an Existing Design     Return to a design you built earlier.
    4. Explore Demonstrations      Fifteen questions, worked through.
    5. Learn PPACT                 Work through the material in order.
    6. All Tools                   Everything Studio can do.

------------------------------------------------------------------------------

  Today's Featured Demonstration                                   Demo 001

  Does a faster memory always help?                              Press D

------------------------------------------------------------------------------
  [1]
```

**The demo is below the rule, not above it.** Featured content sits after
the choices it does not replace. Recommended, not imposed.

**`Analyze an Example` is gone.** UI-R6 dropped it for `Explore
Demonstrations` and then the review listed both - they are the same thing
under two names, which is the duplication UI-R1 found everywhere else.
Examples are reached through `Start a New Design`, where a user choosing
where to begin is already standing.

---

## 3. Demos belong under Explore, not Learn

Agreed, and the demos themselves show why. Each is:

```
question -> setup -> rows -> watch -> answer -> because
```

That is a hypothesis and an experiment, not a lesson. `Does a bigger
engine always help?` has the answer `No`, and the value is in finding out
why - which is curiosity, not study.

**In the seven-verb workflow this puts demos under `Compare`**, whose
entries are all "put things side by side and see what differs". A demo is
a comparison someone else set up.

Alternatively a demo entry sits on the welcome screen and in `Compare`,
reached from both. That is duplication of a route, not of a function, and
it is the kind worth having.

---

## 4. Demo metadata — what the data supports

The proposal was two tags per demo:

```
difficulty    Beginner / Intermediate / Advanced
axis          Performance / Traffic / Power / Area / Cost
```

**Neither exists in the demo data**, and one of them cannot be derived.

Every demo declares which metrics it watches. Across all fifteen:

```
14 of 15 watch   Latency (ms), System power (W), System cost (USD)
 1 of 15 watch   a set without power
```

**Fourteen demos would carry the same three axis tags.** An axis filter
built on that separates nothing - a user choosing "today let's look at a
Performance demo" would be offered fourteen.

The reason is that the demos are honest: a bigger engine changes latency,
power and cost together, and a demo showing only latency would be teaching
the habit this project spent a release cycle removing.

**A useful axis tag would have to say what the demo is ABOUT, not what it
watches** - `memory` is about Traffic even though it reports latency,
power and cost. That is an editorial judgement, one line per demo, and it
cannot be computed.

`difficulty` is the same: not present, not derivable, and a judgement.

### Recommendation

```
Add two declared fields to each demo:

    topic        the axis the QUESTION is about, chosen not derived
    difficulty   Beginner / Intermediate / Advanced, chosen not derived
```

Fifteen editorial decisions, written into the demo definitions where they
can be reviewed, rather than a filter computed from data that does not
distinguish them.

**Until those are written, no filter.** A `topic` column showing
`Performance, Power, Cost` on fourteen rows is worse than no column: it
looks like information.

---

## 5. Demo numbering

Confirmed, unchanged from UI-R6.

```
Demo 001 .. Demo 015     permanent, never reused
```

One identifier across Studio, video, book and paper. A demo withdrawn
keeps its number reserved.

---

## 6. Proposed demo listing

Once `topic` and `difficulty` exist:

```
  EXPLORE DEMONSTRATIONS                            Fifteen worked questions

    Demo 001   Does a faster memory always help?
               Traffic          Beginner

    Demo 002   Does a bigger engine always help?
               Performance      Beginner

    Demo 005   Three ways to spend money. Which one works?
               Cost             Intermediate

    ...

    F. Filter by topic    G. Filter by difficulty    0. Back
```

**Filters only once the tags are real.** Listed here so the screen has a
shape to grow into, not as something available.

---

## What this corrects

```
UI-R6   Enter -> today's demo          a memory analysis for a user who
                                       chose nothing
UI-R7   Enter -> Quick Start           the shortest complete path

UI-R6   Analyze an Example AND Explore Demonstrations
UI-R7   one entry; examples live under Start a New Design

UI-R6   demo tags implied to be available
UI-R7   neither tag exists; one cannot be derived at all
```

---

## What this does not establish

That Quick Start is a better default than a demo. It is an argument about
what a user infers from a first screen, and nobody has been watched
inferring anything.

The `topic` and `difficulty` fields do not exist. Nothing here creates
them, and the listing above is a mock-up of a screen that cannot be built
until fifteen editorial judgements are made and written down.

---

*Author: Roger Kim / Copyright (c) 2026 Roger Kim & EdgeChipLab*
