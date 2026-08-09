# UI-R2 — User Journey

**No code changed. No menu changed. No tests run.**

UI-R1 sorted thirty tasks by what they do. This one arranges them by what a
user wants next, which is a different question and produces a different
answer.

---

## What changed in the thinking

```
UI-R1   Analyze contains task_system_flow and task_runtime
UI-R2   after analysing, a user wants to know WHY - so the bottleneck
        screens end the analysis rather than sitting beside it
```

A user does not look for `task_sensitivity`. They have just been told
their design is limited by the ISP and they want to know whether that
holds if the assumptions move. The menu should be where that thought
lands.

**Three questions per entry**, as asked:

```
where does the user arrive from
what will they want next
can a first-time user reach the end without a manual
```

---

## The journey

```
START
  ↓
Create or Open a Design
  ↓
Analyze Current Design
  ↓
Understand the Bottlenecks          <- inside the analysis, not beside it
  ↓
Compare Alternatives
  ↓
Improve the Design
  ↓
Validate the Results
  ↓
Learn More
```

Each step answers the question the previous one raises. That is the test:
if a step does not answer a question the user now has, it is in the wrong
place.

---

## 1. Start

```
Start
    New Design
    Open Existing Design
    Example Designs
    Quick Start
```

| Entry | From | Task | Next |
|---|---|---|---|
| New Design | first launch | `task_game`, `task_custom` | Analyze |
| Open Existing Design | a return visit | `task_workspace` | Analyze |
| Example Designs | "show me one" | `task_designs` | Analyze |
| Quick Start | no idea where to begin | `task_quickstart` | Analyze |

**`New Design` covers two tasks.** `task_game` builds step by step with
explanation; `task_custom` takes four answers and builds. Same intent,
different pace - one entry with a *guided / direct* choice rather than two
menu items.

**Every path out of Start goes to Analyze.** That is the point of Start.

---

## 2. Analyze Current Design

Renamed from `System Flow`, which names a screen rather than an intent. A
user wants to analyse; `System Flow` is what they get.

```
Analyze Current Design
    1. System Flow
    2. Performance
    3. Traffic
    4. Power
    5. Area
    6. Cost
    7. Position in the Design Space
    8. PPACT Dashboard
    9. What Is Limiting This Design
    10. Recommendation
```

Two changes from UI-R1's grouping:

**`Understand the Bottlenecks` is section 9, not a separate menu.** By the
time a user reaches it they have seen five axes and want the verdict; a
menu entry would make them navigate away and come back.

**`Run and watch the stations`** (`task_runtime`) moves out of Analyze. It
is a demonstration of a design running, not an analysis of one - it
belongs in Learn.

---

## 3. Compare and Improve — four intents, not five tasks

UI-R1 listed eight tasks at one level. They are four intents:

```
Compare Designs         two designs, side by side
Explain This Result     why a number is what it is
Improve My Design       what to change
Explore Design Space    what else is possible
```

| Intent | Tasks | Arrives from | Wants next |
|---|---|---|---|
| **Compare Designs** | `task_memory` (absorbing `task_memory_generations`), `task_evaluate` | "is there something better" | Explain, or Improve |
| **Explain This Result** | `task_explain`, `task_decide` | a number they did not expect | Improve, or Validate |
| **Improve My Design** | `task_whatif`, `task_review`, `task_sensitivity` | the recommendation | Analyze again |
| **Explore Design Space** | `task_sweep` | "what is the range" | Compare |

**`Improve My Design` is a loop back to Analyze.** A user changes
something and wants to see the effect - the menu should return them, not
leave them at a report.

**`task_sensitivity` sits under Improve, not Validate.** A user asking
"does this hold if the assumption moves" is deciding whether to act on a
recommendation.

---

## 4. Learn — for a student

```
Learn
    Learning Path               task_lessons
    Guided Tutorial             task_guided
    Challenges                  task_challenge
    Innovation Challenge        task_innovation
    Worked Questions            task_demo
    Watch a Design Run          task_runtime
    Interpret a Result          task_interpret
    What This Model Analyses    task_framework
    About Studio                task_about
```

---

## 5. Validation — for a researcher

Separated from Learn, as instructed. Different reader, different question.

```
Validation
    Validation Status           task_validation_summary
    Reproducibility             task_reproducibility
    Gold Scenarios              task_gold
    Industry Cases              task_industry
    Migration Invariants        task_migration
    Instructor Tools            task_rubric
```

`task_rubric` is under Instructor Tools rather than on the list: a student
seeing a grading rubric in a menu is being shown the answer key.

---

## 6. Evaluation Mode

**This is a global setting, not a menu entry.**

```
Evaluation Mode   Design Assessment    (a score of 50 = meets requirement)
                  PPACT Benchmark      (a score of 50 = midpoint of range)
                  User Benchmark       (a score of 50 = your reference)
```

Shown as a header on every screen that carries a score, and changed from
there. It is the most important thing a reader needs to know about a
number, and today the user cannot see it or change it.

**Not a top-level menu**, because a user does not set out to change an
evaluation mode; they notice a score and want to know what it means.

---

## 7. English

| Current | Proposed | Why |
|---|---|---|
| System Flow: see the design, then what limits it | Analyze Current Design | names the intent, not the screen |
| Why did the number change | Explain This Result | a user has a result, not a number |
| Run a system for a while and see the dashboard | Watch a Design Run | says what they will see |
| Take the lessons, in order | Learning Path | a path is followed; lessons are taken |
| How much does this verdict depend on an assumption | How Solid Is This Result? | the question they are asking |
| Try a change and put it back | Try a Change | "put it back" is a reassurance, better in the screen |
| Sweep the whole design space and rank the survivors | Explore Design Space | "survivors" is engine vocabulary |
| Propose a change and have it reviewed | Review a Proposed Change | – |
| Explain a change: what, why, how sure, what to do | Explain a Change | the four-part promise belongs on the screen |
| Gold reference scenarios | Gold Scenarios | – |
| Grading rubric (instructor) | Instructor Tools | – |

**Titles say the intent; the screen carries the detail.** A menu entry that
lists what it contains is doing the screen's job.

---

## 8. The first-time test

Can someone reach the end without a manual?

```
1  Start           -> Quick Start                      no prior knowledge
2  Analyze         -> one question: which application  the design is supplied
3  read the report -> 10 sections, ending in a recommendation
4  Improve         -> Try a Change, then Analyze again
5  Validate        -> only if they want it
```

**Steps 1-3 need one answer from the user.** That is the path a first-time
user takes, and it works today - what does not work is finding it, since
`System Flow` is entry 2 of a flat list of thirty.

Where it still breaks:

```
"Analyze Current Design" with no design open
    - today: the task picks the application's first example
    - a user may not notice a design was chosen for them
```

That is worth a line on the screen rather than a menu change.

---

## Structure

```
Start                     4 entries
Analyze Current Design    1 entry, 10 sections
Compare and Improve       4 entries
Learn                     9 entries
Validation                6 entries
Evaluation Mode           a header, not an entry
```

```
30 flat entries  ->  5 groups, 24 entries, one of which is the main path
```

---

## What this does not establish

That a first-time user finds this easier. Nobody has been asked, and the
journey above is an argument rather than an observation. It also does not
establish that `Improve` looping back to `Analyze` is what a user expects -
that is the assumption the whole shape rests on, and it is untested.

---

*Author: Roger Kim / Copyright (c) 2026 Roger Kim & EdgeChipLab*
