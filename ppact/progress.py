"""
ppact.progress - what the student has done, and what that says about them

WHY THIS IS SEPARATE FROM THE LESSONS
=====================================
A lesson is a claim about how systems behave. It should be the same claim for
everyone, and it should not know or care who is reading it. Everything that
varies by student lives here: which lessons they have done, what they
predicted, how many hints they took, and whether they are being shown the
easy version or the hard one.

Keeping them apart means a lesson cannot quietly become easier because
someone got it wrong, which would defeat the exercise.

WHAT A SCORE IS ALLOWED TO MEAN
-------------------------------
Prediction accuracy is not a mark. A student who gets everything right on
first sight learnt nothing here - they already knew it. A student who gets
the first half wrong and the second half right has done exactly what the
course is for.

So two numbers are kept and reported separately:

    prediction accuracy   how often the guess was right
    improvement           second half accuracy minus first half

and neither is summed into a single figure, because they answer different
questions and averaging them would hide the interesting one.

ON THE STATISTICS FEATURE
-------------------------
Showing a student "71% of students chose option 2" is powerful and requires
having asked 71% of students something. This copy has no cohort data and none
is invented: the distribution shown is of answers recorded ON THIS MACHINE,
labelled as such, and it is empty until somebody answers something. A made-up
percentage would be a lie told in the one place a student has no way to
check.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple

LINE = "=" * 78

EASY = "easy"
MEDIUM = "medium"
ADVANCED = "advanced"
DIFFICULTIES = (EASY, MEDIUM, ADVANCED)

DIFFICULTY_NOTE = {
    EASY: "directions only - which way each number moves, and no figures to "
          "read",
    MEDIUM: "the numbers, the bottleneck, and the reasoning",
    ADVANCED: "the above, plus what the result rests on and where it stops "
              "being true",
}

# How many wrong answers before the answer is given. Below this a HINT is
# offered instead: showing the answer immediately removes the reason to
# think, and the thinking is the lesson.
ATTEMPTS_BEFORE_ANSWER = 3

PROGRESS_FILE = "ppact_progress.json"


@dataclass
class Attempt:
    lesson: int
    chosen: int          # 0-based
    correct: bool
    hints_used: int = 0
    attempt_number: int = 1


@dataclass
class Progress:
    """One student's history. Written to disk so a session can be resumed."""
    difficulty: str = MEDIUM
    instructor: bool = False
    show_answers: bool = False
    attempts: List[Attempt] = field(default_factory=list)
    completed: List[int] = field(default_factory=list)
    exam_passed: bool = False
    exam_tries: int = 0

    # ---------------------------------------------------------------- state

    def first_attempts(self) -> Dict[int, Attempt]:
        """The FIRST answer for each lesson.

        Later attempts are the student working it out, which is the point of
        the exercise; scoring them would mark persistence as ignorance.
        """
        out: Dict[int, Attempt] = {}
        for a in self.attempts:
            if a.lesson not in out:
                out[a.lesson] = a
        return out

    def attempts_for(self, lesson: int) -> int:
        return sum(1 for a in self.attempts if a.lesson == lesson)

    def hints_for(self, lesson: int) -> int:
        return max((a.hints_used for a in self.attempts
                    if a.lesson == lesson), default=0)

    def record(self, lesson: int, chosen: int, correct: bool,
               hints_used: int = 0) -> None:
        self.attempts.append(Attempt(
            lesson=lesson, chosen=chosen, correct=correct,
            hints_used=hints_used,
            attempt_number=self.attempts_for(lesson) + 1))
        if correct and lesson not in self.completed:
            self.completed.append(lesson)
            self.completed.sort()

    # --------------------------------------------------------------- scores

    def accuracy(self, lessons: Optional[List[int]] = None
                 ) -> Optional[float]:
        firsts = self.first_attempts()
        keys = sorted(firsts) if lessons is None else [
            k for k in sorted(firsts) if k in lessons]
        if not keys:
            return None
        return sum(1 for k in keys if firsts[k].correct) / len(keys) * 100

    def improvement(self, total: int) -> Optional[Tuple[float, float, float]]:
        """First half against second half, on FIRST guesses.

        Needs at least two lessons in each half to say anything - a single
        answer either side is a coin, and reporting it as a trend would be
        inventing a trend.
        """
        firsts = self.first_attempts()
        half = total // 2
        early = [k for k in firsts if k <= half]
        late = [k for k in firsts if k > half]
        if len(early) < 2 or len(late) < 2:
            return None
        a = self.accuracy(early)
        b = self.accuracy(late)
        return a, b, b - a

    # ----------------------------------------------------------- persistence

    def save(self, folder: str = ".") -> Optional[str]:
        path = os.path.join(folder, PROGRESS_FILE)
        try:
            with open(path, "w") as fh:
                json.dump({"difficulty": self.difficulty,
                           "instructor": self.instructor,
                           "show_answers": self.show_answers,
                           "attempts": [asdict(a) for a in self.attempts],
                           "completed": self.completed,
                           "exam_passed": self.exam_passed,
                           "exam_tries": self.exam_tries}, fh, indent=1)
            return path
        except OSError:
            # A read-only folder must not lose a lesson. The session
            # continues; only the resume is unavailable.
            return None

    @classmethod
    def load(cls, folder: str = ".") -> "Progress":
        path = os.path.join(folder, PROGRESS_FILE)
        if not os.path.isfile(path):
            return cls()
        try:
            with open(path) as fh:
                raw = json.load(fh)
        except (OSError, ValueError):
            return cls()
        p = cls(difficulty=raw.get("difficulty", MEDIUM),
                instructor=bool(raw.get("instructor", False)),
                show_answers=bool(raw.get("show_answers", False)),
                completed=list(raw.get("completed", [])),
                exam_passed=bool(raw.get("exam_passed", False)),
                exam_tries=int(raw.get("exam_tries", 0)))
        for a in raw.get("attempts", []):
            try:
                p.attempts.append(Attempt(**a))
            except TypeError:
                continue
        return p


# ==============================================================================
# Display
# ==============================================================================

def progress_bar(done: int, total: int, width: int = 28) -> str:
    """One line, from the shared renderer - see ppact.visual.text."""
    from .visual import render_progress
    return render_progress(done, total, width)


def print_progress(p: Progress, total: int, current: Optional[int] = None
                   ) -> None:
    done = len(p.completed)
    pct = 0 if total == 0 else done / total * 100
    where = f"Lesson {current} of {total}" if current else \
            f"{done} of {total} lessons"
    print(f"  {where:<22s}{progress_bar(done, total)}  {pct:.0f}%")


def distribution(p: Progress, lesson: int, options: int) -> List[int]:
    """How answers to one lesson were spread - ON THIS MACHINE ONLY."""
    counts = [0] * options
    for a in p.first_attempts().values():
        if a.lesson == lesson and 0 <= a.chosen < options:
            counts[a.chosen] += 1
    return counts


def print_distribution(p: Progress, lesson: int, options: int,
                       correct: int) -> None:
    counts = distribution(p, lesson, options)
    total = sum(counts)
    print(f"\n  HOW THIS QUESTION HAS BEEN ANSWERED")
    if total == 0:
        print(f"     No answers recorded on this machine yet.")
        print(f"     This is a LOCAL count, not a cohort. A percentage from")
        print(f"     students who were never asked would be a number invented")
        print(f"     in the one place a reader cannot check it.")
        return
    for i, n in enumerate(counts):
        mark = " (correct)" if i == correct else ""
        share = n / total * 100
        print(f"     {i + 1}. {n:>3d}  {share:5.1f}%{mark}")
    print(f"     {total} answer(s), recorded on this machine only.")


def print_score(p: Progress, total: int) -> None:
    print(f"\n{LINE}")
    print(" WHAT YOUR ANSWERS SAY")
    print(LINE)
    firsts = p.first_attempts()
    if not firsts:
        print("  Nothing answered yet.")
        print(LINE)
        return

    print(f"  {'lesson':<10s}{'first guess':<14s}{'attempts':<11s}hints")
    print("  " + "-" * 44)
    for k in sorted(firsts):
        a = firsts[k]
        print(f"  {k:<10d}{('right' if a.correct else 'wrong'):<14s}"
              f"{p.attempts_for(k):<11d}{p.hints_for(k)}")

    acc = p.accuracy()
    print(f"\n  Prediction accuracy   {acc:.0f}%  "
          f"({sum(1 for a in firsts.values() if a.correct)} of {len(firsts)} "
          f"first guesses)")

    imp = p.improvement(total)
    if imp is None:
        print(f"  Improvement           not yet - needs at least two lessons")
        print(f"                        answered in each half of the course")
    else:
        early, late, delta = imp
        print(f"  First half            {early:.0f}%")
        print(f"  Second half           {late:.0f}%")
        print(f"  Change                {delta:+.0f} points")

    print(f"\n  These are two different questions and are not averaged into")
    print(f"  one. Getting everything right first time means you knew this")
    print(f"  already; getting the first half wrong and the second half right")
    print(f"  is what the course is for.")
    print(LINE)


def print_certificate(p: Progress, total: int, name: str = "") -> None:
    done = len(p.completed)
    acc = p.accuracy()
    print(f"\n{LINE}")
    print(f"{'PPACT STUDIO':^78}")
    print(f"{'Education Certificate':^78}")
    print(LINE)
    if name:
        print(f"\n{name:^78}")
    print(f"\n{'completed ' + str(done) + ' of ' + str(total) + ' lessons':^78}")
    if acc is not None:
        print(f"{'first-guess accuracy ' + f'{acc:.0f}%':^78}")
    imp = p.improvement(total)
    if imp:
        print(f"{'improved ' + f'{imp[2]:+.0f} points across the course':^78}")
    print(f"{'final design challenge: ' + ('passed' if p.exam_passed else 'not passed'):^78}")
    print()
    print(f"  This records what was done in this copy of the program. It is")
    print(f"  not an assessment by anyone, and it is worth exactly what the")
    print(f"  person reading it knows about how it was produced.")
    print(LINE)
