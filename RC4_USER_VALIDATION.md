# RC4 User Validation — Protocol

## Status

```
Instrument verification     PASS
Study protocol              FROZEN candidate at 1.0
Freeze record               NOT YET SIGNED
Pilot infrastructure        READY
Pilot results               NOT ESTABLISHED
Main-study results          NOT ESTABLISHED
Human effectiveness claim   NOT ESTABLISHED
```

A protocol is a candidate until the freeze is signed. Writing `FROZEN`
before `freeze_rc4.py` has run would claim the one thing the freeze
record exists to prove - and `--check` currently reports:

```
NOT FROZEN - no freeze record at study_freeze.json; the instrument has
not been frozen and a pilot run now cannot be told apart from a later
one
```

The first three lines are about a tool. The last three are about
people, and no person outside this project has used the interface.

**A passing test suite is not a passing study.** The suites establish
that the instrument measures what it says it measures; whether a reader
reaches the engine's conclusion is the question the instrument exists to
ask, and it has not been asked.

**Not run. There are no results.**

This document describes a study, and the code to run it exists. What
does not exist is a participant. Nobody outside this project has used
the interface, and no number in this file has been measured.

The instrument is written now so that when the study is run, the
questions, the stimulus and the marking key cannot be adjusted after
seeing the answers.

---

## What the study asks

The claim this project has been making without evidence is that the
System Flow and Bottleneck Map helps an engineer reach a correct design
judgement faster. That is a claim about people, and the verification
built so far cannot test it: every check to date establishes that the
screen says what the engine computed, which is a different thing from
whether a reader understands it.

Three questions, in order of what they would change:

1. **Do readers reach the engine's conclusion from the figures alone?**
   The engine's recommendation is hidden. If agreement is low, either
   the figures do not carry the argument or the engine's argument is
   wrong — and which of those it is matters more than the number.
2. **Does the bottleneck highlighting do any work?**
   Arm B removes the red box, the badge and the colour bands, leaving
   every figure. If accuracy and time do not change, the highlighting is
   decoration.
3. **Does the System Flow do any work?**
   Arm C removes the panel entirely. This is the killer-feature claim,
   and it is the one most likely to be flattering to assume.

---

## Freeze checklist

Signed once, before the pilot. Each item carries a digest of the thing
it claims to freeze, because ten ticks on a date establish what someone
believed that morning and nothing about the afternoon.

```
□ Engine version          the engine the figures come from
□ Study protocol          raising it invalidates pooled responses
□ Stimulus set            the eight cases and their configurations
□ Question wording        the exact words of the five questions
□ Scoring method          how a response is marked against the engine
□ Treatment registry      what each study style removes and keeps
□ Semantic registry       which items are meaning, which presentation
□ Evidence chain          how a figure traces back to its run
□ UI layout               the renderers a participant sees
□ Timer behaviour         when the clock starts and what it excludes
```

Signed with:

```bash
python3 freeze_rc4.py --signed-by "..."     # once, before recruiting
python3 freeze_rc4.py --check               # any time after
```

It writes `study_freeze.json` and `RC4_FREEZE_CERTIFICATE.md`. The
certificate is rendered from a live recomputation, not transcribed from
the record: one written from the signed file alone would keep asserting
a frozen instrument after it had changed, which is the failure the
freeze exists to prevent. A moved item appears in the certificate under
**"This certificate does not certify a frozen instrument."**

`freeze()` records every digest and **refuses to overwrite**: a freeze
that can be re-signed is a freeze that can be moved after the fact.
`verify()` recomputes them and names what changed.

Changing one question's wording mid-pilot moves two items — the wording
and the stimulus digest that contains it — and both are reported with
their previous values.

An unsigned instrument reports itself unfrozen: **a pilot run now could
not be told apart from a later one.**

---

## Order: pilot, then the main run

Two or three participants first, and their responses are **not pooled
into the main run**.

The pilot is not statistics — three people cannot measure an effect, and
treating them as if they could is how a pilot becomes a result. It
answers four questions about the instrument:

```
Do the questions read as intended, or does one invite a different
    reading than the one being marked?
Does the timing record what it should - thinking time, not the time
    a page took to render?
Does any screen give the answer away?
Does a participant know when they have finished a case?
```

If any of those turns out wrong, the instrument changes, and responses
collected against the old one cannot be compared with responses
collected against the new one.

Kept apart by the folder rather than by a flag:

```
study/pilot/session_*.json
study/main/session_*.json
```

`score()` takes one phase at a time and refuses an unknown one. A flag
is one forgotten argument away from being pooled.

---

## Participants

10–20 people with semiconductor, FPGA or SoC design experience, and none
of them involved in building this tool. Background is recorded — years of
experience and whether they have done system-level performance work —
because a result that holds only for the very experienced is a different
finding from one that holds generally.

**Nobody has been recruited.**

---

## Stimulus set

Eight cases, each verified to produce the condition it claims. A
stimulus set whose host-limited case is not host-limited marks every
participant against the wrong answer, and that error is invisible once
the numbers exist.

```
BN-HOST          bottleneck: host
BN-MEM           bottleneck: shared memory
BN-ACCEL         bottleneck: accelerator
BN-ISP           bottleneck: ISP
MOVE-1           the bottleneck moves (host -> accelerator)
MARGIN-TIGHT     just inside every requirement
MARGIN-WIDE      far inside every requirement
NEAR-IDENTICAL   two designs one memory package apart
```

The last three are the cases where a reader is most likely to go wrong.
`MARGIN-WIDE` asks whether a reader proposes a change to a design that
needs none; `NEAR-IDENTICAL` asks whether a reader reports a large
difference from a chart when the figures differ barely at all.

---

## Product and study are separate

The shipped screen names the limiting element in its subtitle and marks
it with a badge. That is right for a reader and fatal for a study asking
where the bottleneck is, so the suppression lives in the study styles
and the product keeps its subtitle.

**Trading the tool's explanatory power for a measurement would be the
wrong way round.**

| Style | Subtitle | Answer label | Highlight | Values | Layout | Purpose |
|---|---|---|---|---|---|---|
| `PRODUCT_NORMAL` | yes | yes | yes | yes | yes | the commercial screen |
| `STUDY_FULL` | no | no | yes | yes | yes | baseline arm |
| `STUDY_NO_HIGHLIGHT` | no | no | no | yes | yes | isolates the emphasis |
| `STUDY_NO_FLOW` | — | — | — | — | — | removes the panel |

`STUDY_FULL` is **not** "the current product screen". It is a
full-information stimulus with the answer-revealing labels suppressed,
and calling it the product screen would misdescribe what the arms
compare.

---

## Evidence chain for a session

```
protocol_version + stimulus_set_digest + render_digest
   -> treatment_digest        what the experimenter removed
      -> figure digest
         -> response + timing
            -> session_digest
```

The treatment digest hashes only the manipulation, so a study can show
that **only the treatment changed**: the engineering fact is one flow
map rendered three ways, and the digests that move are the ones that
should.

Between the two study arms exactly one treatment differs:

```
STUDY_FULL          subtitle_removed, answer_label_removed
STUDY_NO_HIGHLIGHT  subtitle_removed, answer_label_removed,
                    highlight_removed
```

---

## Timing

Measured from **render-complete to submission**, never from the request.
Timing from the request makes a slow machine look like a slow
participant, and the machine is not what the study is about.

The clock refuses to report before the stimulus says it is drawn, and
render time is recorded separately. A reading whose basis is not
`render_complete` is counted and excluded from the median rather than
averaged in.

---

## Sessions

```
complete       every case answered; only these are scored
incomplete     kept and listed, never pooled
attempt        a refresh or a back-navigation is a new attempt;
               only the first is marked, the rest are counted
drifted        recorded against a different instrument; excluded
```

Discarding an incomplete session hides that someone stopped. Averaging a
repeat blends a first impression with a considered revision.

---

## Pilot stop criteria, fixed in advance

```
question_misread     a participant answers a different question
timer_wrong          recorded time does not match observed thinking time
answer_leaked        any arm states the limiting element
completion_unclear   a participant does not know when a case is done
```

If any is met: change the instrument, **raise the protocol version,
discard the pilot responses and start again**.

Nothing else is a reason to change the interface between pilot and main
run — in particular, **a result that looks disappointing is not**.

---

## Arms

```
A   the current screen
B   the same screen with the bottleneck highlighting removed
C   the same screen without the System Flow panel
```

B and C each remove exactly one thing. An arm that changed two would not
say which one mattered.

Assignment is a Latin square, not random per participant: with twenty
people, one arm drawing the easy cases by chance would go unnoticed.

---

## Hidden from participants

```
Engineering Conclusion
Recommended Next Comparisons
```

Showing the conclusion first measures whether a participant can read
English.

---

## Questions

Fixed wording, asked in the same order of every participant:

```
Q1  Where is the bottleneck?
Q2  Which module would you improve first?
Q3  Would adding memory help?
Q4  Would a larger accelerator help?
Q5  Which change gives the most for its cost?
```

Each answer carries a self-reported confidence (1–5) and the time taken.
After Q5 the participant is asked to explain their reasoning in their own
words, which is compared with the engine's stated reason rather than with
its conclusion.

---

## Marking

The key is **computed from the engine at scoring time, never stored**.
A stored key drifts from the model: improving the engine would leave a
study marked against the old one.

Q1 and Q2 are marked against the engine. Q3, Q4 and Q5 are recorded and
not marked, because the engine runs no counterfactual — it says which
element limits the design, not how much a change would gain. Marking
them against the engine would score participants on a claim the tool
does not make.

---

## The table this produces

Empty by construction until the study is run:

| Measure | Result |
|---|---|
| Bottleneck identified correctly (Q1) | — |
| First module agrees with the engine (Q2) | — |
| Median time to first answer | — |
| Mean self-reported confidence | — |
| Arm A against Arm B (highlighting) | — |
| Arm A against Arm C (System Flow) | — |

`score()` raises rather than returning zeros for an empty study. A table
of zeros reads as a finding.

---

## What a result would and would not establish

**Would.** That readers using this interface reach, or fail to reach,
the engine's conclusion; and whether removing the System Flow changes
that.

**Would not.** That the engine is right. If participants agree with it
and the model is wrong, the study measures agreement with a wrong
answer — which is why `DEFERRED.md` still records that no figure here
has been compared against measured hardware.

*Author: Roger Kim / Copyright (c) 2026 Roger Kim & EdgeChipLab*
