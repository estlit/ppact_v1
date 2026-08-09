# LIB-R1 — Demonstration Library Review

**No demo changed. No code changed. This is a review of the fifteen as one
thing.**

QA-1 to QA-3 examined each demonstration on its own. This looks at what
they are together: a Studio library, a fifteen-part video series and a set
of book figures sharing one numbering.

---

## The fifteen in one line each

```
001  A stage improvement does not become a system improvement of the
     same size.
002  Buying more of a stage moves the limit somewhere else, and it can
     land worse than it started.
003  Parallel compute does not parallelise a shared resource.
004  A process node moves fabricated logic and not a purchased part.
005  Find the limiting stage before choosing what to buy.
006  There is a node beyond which cost and performance stop moving
     together.
007  Two upgrades have an order, and the wrong order is worse than
     neither.
008  Internal balance and product constraints are different questions.
009  The limiting part is not necessarily the part the design is named
     after.
010  Where work runs is a design decision with its own cost.
011  More packages buy bandwidth as well as memory capacity.
012  A capacity failure has no performance figure at all.
013  When neither option touches the limiting stage, other axes decide.
014  A parallel pair cannot finish before its slower half.
015  The cheapest node to manufacture is not the newest one.
```

**Fifteen distinct sentences.** No two could be swapped without losing
something.

---

## 1. Overlap by engineering decision

Three decisions appear more than once:

```
3x   Change the process node          004, 006, 015
2x   Change the memory technology     001, 013
2x   Change how many packages fitted  011, 012
```

**Repeating a decision is not repetition.** What matters is whether the
LESSON repeats.

**The three node demos are distinct**, and deliberately so:

```
004   the node does not move a purchased part      (memory-limited)
006   there is a speed turning point               (compute-limited)
015   there is a cost turning point                (die cost isolated)
```

004 answers "does it move the system"; 006 and 015 both answer "where is
the turn", on different axes. **006 and 015 are the closest pair in the
library.** They are separable — one is about time and one about money, and
a reader can want either without the other — but they are the pair to
watch if a sixteenth node demo is ever proposed.

**001 and 013** both change memory technology and could not be more
different: one is about proportionality, the other about what decides when
nothing touches the limit.

**011 and 012** both change package count: bandwidth against capacity, and
capacity failure. Adjacent and distinct.

---

## 2. Difficulty and family

Declared per demonstration, not derived - nothing in the data says a
demonstration is advanced, and deriving a family from the changed field
would call 011 and 012 the same thing.

```
        demo   family      complexity a reader must hold
Easy    001    Memory      one decision, two designs
        002    Parallel    one decision, three designs, a turn
        009    Host        one decision, two designs

Medium  003    Parallel    one decision, a shared resource
        004    Node        one decision, three designs
        005    Placement   three options against a baseline
        008    Traffic     one decision, four gates
        010    Placement   one decision, a new stage
        011    Packaging   one decision, two effects at once
        013    Memory      one decision, no performance change
        014    Parallel    one decision, an unequal pair

Advanced 006   Node        three designs, a turn in performance
        007    Parallel    TWO decisions, four designs
        012    Packaging   one decision, an ABSENT figure
        015    Node        four designs, a turn in cost
```

```
Easy 3    Medium 8    Advanced 4
```

**The opening is Easy and the closing is Advanced**, and the four
Advanced entries are spread rather than stacked: 006, 007, 012, 015.

### Families

```
Parallel     002 003 007 014     four
Node         004 006 015         three
Memory       001 013             two
Packaging    011 012             two
Placement    005 010             two
Host         009                 one
Traffic      008                 one
```

**Parallel is the largest family at four** and holds a third of the
library. That is the boundary a sixth parallel demonstration would cross.

### Learning progression

```
001   one decision, two designs
002   + a turning point
005   + three options to choose between
007   + a second decision, and their order
012   + a question with no answer
015   + a turn on an axis the reader did not expect to turn
```

Each adds one thing to what the reader already had.

---

## 3. Axis coverage

Panels drawn across the fifteen measured charts:

```
Performance    14
Cost           10
Area            5
Traffic         3
Power           3
```

The axis carrying the LARGEST change per demo:

```
Area        5
Cost        3
Traffic     3
Performance 3
Power       1
```

**Performance appears almost everywhere and dominates almost nowhere.**
That is the right shape: it is the axis a designer arrives with, and the
demonstrations are mostly about something else turning out to matter more.

**Power is thin, and should stay thin.** Power carries no established
measurement basis (PW-Q1), so no power verdict is issued anywhere. A
demonstration built around power would rest its conclusion on an open
question. **Three appearances, none of them load-bearing, is the honest
amount** — and it should grow when PW-Q1 closes, not before.

**Traffic is thin because Traffic is one component of ten.** Traffic
balance is established; the other nine components of TR-D1 are not. Demo
008 is the only demonstration where Traffic carries the argument, and it
does so by contrast with the deployment gates rather than on its own.

**This is a coverage gap that reflects the model, not the library.** Two
axes are under-represented because two axes are under-established.

### Primary against secondary

A count of appearances says which axis is DRAWN most. A count of primary
appearances says which axis each demonstration is ABOUT, and they are
different numbers:

```
axis          primary   secondary
Area                5           0
Traffic             4           0
Performance         3           9
Cost                2           8
Power               1           2
```

**Performance is the subject of three demonstrations and the supporting
evidence in nine.** That inversion is the library's shape in one table: a
designer arrives asking about performance, and the demonstrations are
mostly about what else turns out to decide it.

Every axis is the subject of at least one demonstration, including Power -
Demo 013, where neither memory option touches the limiting stage and the
choice falls to power against cost.

---

## 3. Order

Current numbering is publication order, and it happens to work:

```
001  two rows, no turning point          a comparison
002  three rows, a turning point         a curve
003  two rows                            a comparison
004  three rows                          a comparison across three
005  four rows                           three options against a baseline
...
015  four rows, a turning point          a curve, on cost
```

**001 is the right opening.** Two designs, one change, and an answer that
is neither yes nor no — it sets the expectation that Studio answers "how
much" rather than "which".

**002 is the right second.** A turning point on the third demonstration
would be too early; on the second, after one straight comparison, it lands.

**015 is the right ending.** Four rows, a turning point, and the one axis a
reader will not have expected to turn.

**012 is the outlier and should stay where it is.** It is the only
demonstration whose answer is an absent figure, and it needs a reader who
already trusts the figures — which is why it sits eleventh rather than
second.

No reordering is recommended.

---

## 4. Difficulty

```
two rows        001 003 008 009 010 011 012 013 014     nine
three rows      002 004 006                             three
four rows       005 007 015                             three
turning point   002 006 015                             three
```

**Difficulty rises but not monotonically**, and that is deliberate: a
series where every entry is harder than the last has no rest. The
four-row demonstrations (005, 007, 015) are spread across the run rather
than clustered at the end.

**007 is the hardest.** It is the only demonstration making two
engineering decisions, and its answer is about their ORDER. A reader
arriving at 007 without 002 and 003 would have to hold three ideas at
once.

---

## 5. As a fifteen-part series

A viewer watching one a day:

```
week 1   001-005   what limits a system, and how to find it
week 2   006-010   where the obvious answer is wrong
week 3   011-015   what the figures do and do not say
```

That grouping is a reading of the existing order, not a change to it. It
holds because the demonstrations were written to the same shape rather
than to a curriculum.

**The series has no summary episode.** Nothing ties the fifteen together
at the end, and the strongest candidate — "what limits a system" — is
Demo 005's subject rather than a sixteenth demonstration.

---

## 6. Ordering dependencies (LIB-R2)

A demonstration may POINT at a later one; it may not DEPEND on one.

```
003 -> 007, 014     in "what this does not establish"
004 -> 015          in "what this does not establish"
005 -> 009          in "what this does not establish"
```

**All three are pointers, and all three sit in the limits section.** A
reader at Demo 003 is told where the opposite case is answered; they do
not need it to follow 003.

Backward references, which cost nothing:

```
006 <- 004      009 <- 002      012 <- 011      015 <- 004
```

A forward reference landing in the evidence or the reasoning would be an
ordering fault, and it is now a contract rule rather than something a
reader has to notice.

---

## 7. What this review does not establish

That the order is best for a learner. **Nobody has watched anyone use it**
— the difficulty reading above is a count of rows and turning points,
which is a proxy for difficulty and not a measurement of it.

That the coverage is right. Performance appears fourteen times because the
model computes it best, and a library shaped by what a model computes well
is a library shaped by the model.

That fifteen is the right number. Nothing here identifies a missing
demonstration, and an absence is exactly what a review of the present set
is worst at finding.

---

## Recommendation

```
Order                no change
Overlap              no change; watch 006/015 if a node demo is added
Coverage             Power and Traffic grow when PW-Q1 and TR-D1 close
Difficulty           no change; Advanced entries are spread, not stacked
Families             Parallel is at four of fifteen - the boundary
Ordering             no forward dependencies; three forward pointers
Series grouping      usable as written
```

The library is releasable as a library. What it is short of is not
demonstrations but **a reader outside this project**, and that is the one
thing no further review here can supply.

---

*Author: Roger Kim / Copyright (c) 2026 Roger Kim & EdgeChipLab*
