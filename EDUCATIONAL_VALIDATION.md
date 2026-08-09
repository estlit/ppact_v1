# Educational validation protocol

A procedure, not a result. Nothing in this package has measured whether
PPACT Studio helps anybody understand anything, and no part of it should be
read as though it had.

## What is already established, and what is not

The suites check that an answer is PRESENT, SPECIFIC, and CORRECT against
the engine, that four statements about a design agree with each other, and
that the same input produces the same output. All of that is about the
program.

Whether a person reads the answer, believes it, and reasons more soundly
because of it is a question about people. The only instrument for it is people.

## Design

Ten or more participants who have not used the Studio.

Each is given the same set of design questions twice: once unaided, once
with the Studio. Order is counterbalanced — half do the unaided set first —
because a participant who has thought about a problem for twenty minutes
answers the second set more accurately whatever they were
given.

A control group answering both sets unaided separates learning-by-repetition
from learning-by-tool. Without it, an improvement means only that people
improve when they try something twice.

## What to measure

| Measure | How |
|---|---|
| Correctness | against the engine, on questions with a determinate answer |
| Reasoning quality | does the stated reason match the stated conclusion |
| Bottleneck identification | does the participant name the station holding the time |
| Confidence calibration | stated confidence against correctness |
| Time | to a first answer, and to a defended one |

Reasoning quality needs a second marker who has not seen which condition a
script came from. A single marker who knows which answers came from the
tool will find the tool helped.

## Suggested questions

Drawn from the same shapes the validation suite uses, because they behave
differently from one another:

1. A change that helps.
2. A change that does not help despite sounding as though it should.
3. A change that helps and costs.
4. A change that breaks a requirement.
5. A design that cannot run at all.

## What would count as a result

A difference in correctness between conditions, larger than the difference
between the two question sets in the control group, with the sample size
stated.

## What would NOT count

- A single group improving on a second attempt.
- Participant satisfaction. A tool people enjoy and learn nothing from is a
  tool people enjoy.
- Time saved, on its own. A wrong answer produced in half the time is
  not an improvement.
- Any measure collected by whoever built the tool, unblinded.

## Where the result goes

Into `METHODOLOGY.md` under "Not established", replacing the entry there —
with the sample size, the effect, and the conditions. If the result is null
or negative it goes in the same place, in the same detail. A protocol that
only has somewhere to put a positive result is not a protocol.
