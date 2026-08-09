"""
ppact.text_capture - run a terminal task and hand back what it printed

WHY THIS EXISTS
===============
Thirty menu tasks are written against `print` and `ask_nav`. Rewriting
each one for Streamlit would give two implementations of the same
analysis, and the moment one is edited they disagree - which is exactly
the defect this project spent a release cycle removing from the demo
review.

So the task runs unchanged and its output is captured. What the terminal
prints and what the browser shows are then the same text by
construction, not by anyone remembering to update both.

WHAT THIS IS NOT
----------------
It is not a rewrite and it is not a rendering layer. A task that asks a
question still asks it; the answers are supplied by the caller, and a
task that runs out of answers stops where it stopped rather than
guessing.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

import builtins
import contextlib
import glob
import io
import os
import tempfile
import traceback
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple


# HOW MANY QUESTIONS BEFORE A TASK IS ASSUMED NOT TO END.
#
# `task_lessons` puts Back last, so a caller taking the first option
# re-enters lesson one forever. In the terminal that killed the process;
# here it hangs the page, and one task hanging the page is one task
# taking the whole interface down.
#
# Forty is far more than any task asks in a real session and low enough
# that a runaway is caught in seconds.
MAX_QUESTIONS = 40


@dataclass
class TaskRun:
    """One task, run to completion or to the point it needed an answer."""
    task_id: str
    text: str
    images: Tuple[str, ...]
    questions: Tuple[str, ...]
    completed: bool
    error: str = ""
    # WHAT THE WORKFLOW RETURNED.
    #
    # A WorkflowOutcome for a registered workflow, None otherwise. The
    # report is built from this and never from what the task printed: a
    # task that draws no System Flow used to leave the screen without
    # one, and the renderer now owns that.
    outcome: object = None
    # STOPPED, not failed and not finished. A third outcome, because
    # calling it either of the other two would be wrong.
    truncated: bool = False

    @property
    def needs_input(self) -> bool:
        return not self.completed and not self.error and \
            not self.truncated


def run_task(task_id: str, answers: Sequence[str] = (),
             out_dir: str = "",
             max_questions: int = MAX_QUESTIONS) -> TaskRun:
    """Run a terminal task and capture everything it produced.

    `answers` are fed to its questions in order. A task that asks more
    than it is given stops there - the run is incomplete, and the caller
    is told which questions were asked so it can render them.
    """
    from . import menu

    fn = dict((f.__name__, f) for _t, f in menu.TASKS).get(task_id)
    if fn is None:
        return TaskRun(task_id, "", (), (), False,
                       f"no task named {task_id!r}")

    work = out_dir or tempfile.mkdtemp(prefix=f"ppact_{task_id}_")
    os.makedirs(work, exist_ok=True)
    before = set(glob.glob(os.path.join(work, "*.png")))

    # Imported once, above every use. Two local imports of one name in
    # one function is how a use ends up above its import.
    from .questions import NonInteractiveEnvironmentError

    asked: List[str] = []
    supplied = list(answers)
    overrun = {"hit": False}
    buf = io.StringIO()
    seen = {"text": ""}

    # A QUESTION ENDS WHERE THE TASK ASKS. It does not end after some
    # number of characters.
    #
    # This kept a rolling 6000-character buffer and handed the last 1200
    # to the parser. The accelerator list prints 22 options and did not
    # fit: the window began part-way through option 2, the parser saw 20
    # options and numbered them from 1, and a reader choosing
    # "6.6 TOPS NPU 64x64" - printed as 5 - submitted 3. The engine
    # evaluated its option 3, "0.9 TOPS NPU 24x24", and every figure
    # downstream described a design the reader had not chosen.
    #
    # Twelve further questions sat exactly at the 1200 cap and happened
    # not to lose an option. They were already being cut; the cut simply
    # fell somewhere harmless. Any larger constant moves the cliff
    # rather than removing it.
    #
    # `_reply` is called when the task has finished printing a question,
    # so everything written since the previous call IS this question.
    seen = {"text": "", "mark": 0}

    class _Tee(io.StringIO):
        def write(self, s):
            seen["text"] += s
            return super().write(s)

    buf = _Tee()

    def _reply(prompt: str = "") -> str:
        # THE PROMPT IS WHAT WAS PRINTED, not what was passed.
        #
        # These tasks print the question and call input() with an empty
        # prompt, so recording the argument would record nothing.
        asked.append(seen["text"][seen["mark"]:])
        seen["mark"] = len(seen["text"])
        if len(asked) > max_questions:
            # A TASK THAT KEEPS ASKING IS NOT A TASK THAT IS WORKING.
            #
            # Raised as the one exception the prompt loop lets through.
            # A custom exception was swallowed by `ask_question`, which
            # then fell back to a default and carried on looping - the
            # ceiling was there and did nothing.
            overrun["hit"] = True
            raise NonInteractiveEnvironmentError(
                f"stopped after {max_questions} questions")
        if len(asked) <= len(supplied):
            return supplied[len(asked) - 1]
        # THE ONE EXCEPTION THE PROMPT LOOP LETS THROUGH.
        #
        # `ask_question` catches everything except
        # NonInteractiveEnvironmentError - anything else and it falls
        # back to a default, so a task asking an unanswered question
        # reported itself complete having chosen for the reader.
        raise NonInteractiveEnvironmentError(
            "a Streamlit caller supplies answers one at a time")

    real_input = builtins.input
    cwd = os.getcwd()
    completed, error = True, ""
    # THE WORKFLOW'S OWN RETURN, not an interception.
    #
    # This used to replace `build_review` and `evaluate_system` while
    # the task ran and read the arguments. Every registered workflow now
    # returns a WorkflowOutcome, so nothing has to be inferred from
    # which module bound which name.
    outcome = None
    try:
        builtins.input = _reply
        os.chdir(work)
        with contextlib.redirect_stdout(buf):
            outcome = fn()
    except Exception as exc:
        if isinstance(exc, NonInteractiveEnvironmentError):
            completed = False
        else:
            completed = False
            error = traceback.format_exc().strip().splitlines()[-1]
    finally:
        builtins.input = real_input
        os.chdir(cwd)

    made = sorted(set(glob.glob(os.path.join(work, "*.png"))) - before)
    return TaskRun(task_id, buf.getvalue(), tuple(made),
                   tuple(asked), completed, error, outcome,
                   overrun["hit"])


# No custom exception: the prompt loop catches everything except
# NonInteractiveEnvironmentError, so anything else is silently absorbed.


def options_from(prompt_text: str) -> List[str]:
    """The numbered choices of the LAST question, and only those.

    The captured text spans more than one screen. Taking every numbered
    line merged the previous menu with the current question, so a
    four-option prompt was rendered with fourteen and the third choice
    sent an answer meant for a different question.

    A run of options is a block that starts at 1 and counts up. The last
    such block is the one the task is waiting on.
    """
    import re

    numbered: List[Tuple[int, str, int]] = []
    for i, line in enumerate(prompt_text.splitlines()):
        m = re.match(r"\s*(\d+)[.)]\s+(\S.*)", line)
        if m:
            numbered.append((int(m.group(1)), m.group(2).strip(), i))

    blocks: List[List[Tuple[int, str, int]]] = []
    for entry in numbered:
        n = entry[0]
        # A NEW BLOCK STARTS AT 1, or where the count does not follow on.
        if n == 1 or not blocks or blocks[-1][-1][0] != n - 1:
            blocks.append([entry])
        else:
            blocks[-1].append(entry)

    if not blocks:
        return []
    return [text for _n, text, _i in blocks[-1]]


@dataclass
class Question:
    """A prompt, split into the parts a screen shows separately.

    The whole transcript used to go on screen as one block, and the
    options were then rendered again as radio buttons - the same nine
    items twice, which makes a reader check whether they are the same
    list.
    """
    title: str
    prose: Tuple[str, ...]
    options: Tuple[str, ...]
    preamble: Tuple[str, ...] = ()

    @property
    def has_options(self) -> bool:
        return bool(self.options)


def parse_question(prompt_text: str) -> Question:
    """Title, explanation and options, from what a task printed.

    The options are the last block that starts at 1 and counts up; the
    prose is what sits between the title and that block. Everything
    earlier is the preamble - previous screens, which a reader has
    already seen.
    """
    import re

    lines = prompt_text.splitlines()

    numbered = []
    for i, line in enumerate(lines):
        m = re.match(r"\s*(\d+)[.)]\s+(\S.*)", line)
        if m:
            numbered.append((int(m.group(1)), m.group(2).strip(), i))

    blocks = []
    for entry in numbered:
        n = entry[0]
        if n == 1 or not blocks or blocks[-1][-1][0] != n - 1:
            blocks.append([entry])
        else:
            blocks[-1].append(entry)

    if not blocks:
        body = [l.rstrip() for l in lines if l.strip()]
        return Question(title=body[-1] if body else "",
                        prose=tuple(body[:-1][-4:]), options=())

    block = blocks[-1]
    first_opt = block[0][2]
    options = tuple(text for _n, text, _i in block)

    # INDENTATION SEPARATES THE HEADING FROM THE PROSE.
    #
    # These prompts print a heading at one indent and its explanation at
    # a deeper one. Taking the last line before a blank picked up the
    # final sentence of the prose instead - "therefore can affect the
    # physical estimates." was being shown as the question.
    def indent(line):
        return len(line) - len(line.lstrip())

    body = [(i, lines[i]) for i in range(first_opt)
            if lines[i].strip()
            and not lines[i].strip().startswith(("=", "-"))]
    prose, title, i = [], "", 0
    if body:
        opt_indent = indent(lines[first_opt])
        # Walk back collecting lines indented at least as deep as the
        # options; the first shallower line is the heading.
        for idx, line in reversed(body):
            if indent(line) < opt_indent:
                title = line.strip()
                i = idx
                break
            prose.insert(0, line.strip())
        if not title and prose:
            title, prose = prose[0], prose[1:]

    return Question(title=title, prose=tuple(prose), options=options,
                    preamble=tuple(l.rstrip()
                                   for l in lines[:max(0, i - 1)]
                                   if l.strip())[-6:])
