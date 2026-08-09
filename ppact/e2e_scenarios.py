"""
ppact.e2e_scenarios - how each workflow is finished

WHY A SCENARIO AND NOT "ALWAYS PICK 1"
======================================
A harness answering 1 to every question does not walk a user's journey.
It re-entered lesson one forever, never reached "Done" in what-if, and
reported four workflows as having no completion path - none of which was
true of a person using them.

Each entry says how that workflow is FINISHED, in the words the screen
shows, so the walk survives an option being reordered or reworded.

    exact       choose the option whose label starts with this
    otherwise   choose the first option

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Sequence, Tuple


@dataclass(frozen=True)
class Scenario:
    """ONE DEFINITION, EVERY CONSUMER.

    A browser harness clicking option one while the manifest recorded a
    text walk following `choices` described two different runs: the
    configuration digests said the designs differed and the pictures
    beside them were identical. Neither was wrong about its own run, and
    together they were evidence of nothing.

    The UI walk, the text walk and the expected configuration all derive
    from this object.
    """
    """One completing path through a workflow.

    `choices` names the option to take at a given step, by position.
    Answering 1 everywhere made `task_guided` compare a design against
    itself - both the baseline and the comparison accelerator were
    option one - so the evidence showed a comparison with nothing to
    compare, and two workflows produced byte-identical panels.
    """
    task_id: str
    # Words that END the workflow when they appear as an option.
    finish_labels: Tuple[str, ...] = ()
    # How many ordinary choices to make before looking for a finish.
    lead_in: int = 1
    note: str = ""
    # step (1-based) -> which option to take. Anything unlisted takes 1.
    choices: Dict[int, int] = field(default_factory=dict)
    # A COMPARISON MUST COMPARE TWO THINGS.
    #
    # Answering one everywhere made two workflows compare a design
    # against itself, and the screen showed a comparison with nothing
    # compared. Declared here so the absence of a declaration is a
    # failure rather than a silent default.
    comparative: bool = False

    def digest(self) -> str:
        """What this scenario is, so a capture can name its source."""
        import hashlib
        import json as _json
        payload = _json.dumps(
            {"task": self.task_id, "finish": list(self.finish_labels),
             "lead_in": self.lead_in,
             "choices": {str(k): v for k, v in self.choices.items()},
             "comparative": self.comparative}, sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    def option_for(self, step: int, n_options: int) -> int:
        """The 1-based option this scenario takes at `step`."""
        wanted = self.choices.get(step)
        if wanted and wanted <= n_options:
            return wanted
        return 1


# Comparison workflows must reach two different designs. A scenario for
# one of them that leaves every choice at option 1 is not a scenario,
# and a check below fails rather than letting the evidence show a
# comparison of a design against itself.
COMPARISON_TASKS = ("task_whatif", "task_review", "task_decide",
                    "task_guided", "task_demo")

SCENARIOS: Dict[str, Scenario] = {
    "task_quickstart": Scenario(
        "task_quickstart", (), 0,
        "one question: which application"),
    "task_game": Scenario(
        "task_game", ("Finish", "Done", "Build it", "Analyse"), 6,
        "a decision per component, then build"),
    "task_custom": Scenario(
        "task_custom", (), 0,
        "five questions, no exit option"),
    "task_whatif": Scenario(
        "task_whatif", ("Done",), 3,
        # application, which component, the new value, THEN Done.
        # At 2 the walk chose Done before changing anything, the
        # workflow correctly returned CANCELLED, and the missing report
        # looked like a product defect.
        "application, component, value, then Done", comparative=True,
        # A COMPARISON THAT MOVES THE BOTTLENECK.
        #
        # Every declared walk changed something the limiting element did
        # not depend on, so nine comparisons all reported the same
        # limit before and after - the System Flow's central claim was
        # never exercised. Adding a second accelerator moves it from the
        # accelerator to the secondary accelerator.
        choices={2: 3, 3: 2}),
    "task_review": Scenario(
        "task_review", (), 0,
        "pick a design and a proposal", comparative=True),
    "task_decide": Scenario(
        "task_decide", (), 0,
        "application, baseline and comparison accelerator, baseline "
        "and comparison memory, then the optional extras",
        # A COMPARISON NEEDS TWO DIFFERENT DESIGNS.
        #
        # Steps 2/3 are the baseline and comparison accelerator and 4/5
        # the two memories. Answering 1 to all of them produced a
        # comparison of a design against itself, and the evidence showed
        # a comparison with nothing to compare.
        choices={3: 4, 5: 3}, comparative=True),
    "task_challenge": Scenario(
        "task_challenge", ("Submit", "Done"), 3,
        "attempt, then submit"),
    "task_guided": Scenario(
        "task_guided", ("Done", "Finish"), 3,
        # "Back" was a finish label here. Separating exits from answers
        # gave the screen a navigation button of the same name, so the
        # walk clicked it at step 3 and left the workflow instead of
        # finishing it - a harness matching a word, not a meaning.
        "application, baseline accelerator, comparison accelerator",
        # A COMPARISON NEEDS TWO DIFFERENT DESIGNS. Step 2 is the
        # baseline accelerator and step 3 the comparison one; taking
        # option 1 for both compared a design against itself.
        choices={3: 4}, comparative=True),
    "task_demo": Scenario(
        "task_demo", (), 1,
        "pick a demonstration; the report follows the selection",
        comparative=True),
}


def next_answer(options: Sequence[str], step: int,
                scenario: Optional[Scenario]) -> str:
    """Which option number a user would choose at this step.

    Returns a 1-based index as a string, because that is what the
    prompts read.
    """
    if scenario is None:
        return "1"
    if step >= scenario.lead_in:
        for i, label in enumerate(options, 1):
            text = label.strip().lower()
            for want in scenario.finish_labels:
                if text.startswith(want.lower()):
                    return str(i)
    # A DECLARED CHOICE, where taking the first option would make the
    # evidence say nothing.
    wanted = scenario.choices.get(step + 1)
    if wanted and wanted <= len(options):
        return str(wanted)
    return "1"


def walk(task_id: str, max_steps: int = 40):
    """Drive a workflow the way its scenario says a user would."""
    from .text_capture import run_task, options_from

    scenario = SCENARIOS.get(task_id)
    answers = []
    for step in range(max_steps):
        run = run_task(task_id, answers)
        if run.error or run.truncated or run.completed:
            return run, answers
        opts = options_from(run.questions[-1])
        if not opts:
            return run, answers
        answers.append(next_answer(opts, step, scenario))
    return run_task(task_id, answers), answers


def scenario_digest(task_id: str) -> str:
    """A digest of the walk itself.

    The first link in the chain. Without it a config digest says what
    was built and nothing says which walk built it - which is how the
    manifest came to describe one run while the pictures came from
    another.
    """
    import hashlib

    sc = SCENARIOS.get(task_id)
    if sc is None:
        return ""
    payload = "|".join([
        sc.task_id, ",".join(sc.finish_labels), str(sc.lead_in),
        ";".join(f"{k}={v}" for k, v in sorted(sc.choices.items()))])
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def ui_choice(options: Sequence[str], step: int,
              task_id: str) -> int:
    """Which option index (0-based) a UI harness should click.

    ONE SOURCE FOR BOTH HARNESSES.

    The browser clicked option one while the text walk followed the
    scenario, so the manifest recorded a different run from the one the
    screenshots came from. Both now derive from here.
    """
    answer = next_answer(options, step, SCENARIOS.get(task_id))
    try:
        return max(0, int(answer) - 1)
    except ValueError:
        return 0


def comparison_reaches_two_designs(task_id: str):
    """Whether a comparison workflow's scenario builds two designs.

    Returns (ok, starting_digest, current_digest). A comparison whose
    two designs are identical has nothing to compare, and a screen for
    it should not be produced at all.
    """
    import builtins
    import contextlib
    import dataclasses
    import hashlib
    import io

    from . import menu as _menu
    from .outcome import WorkflowOutcome, WorkflowVariant
    from .questions import NonInteractiveEnvironmentError

    _run, answers = walk(task_id)
    seq = iter(answers)

    def reply(prompt=""):
        try:
            return next(seq)
        except StopIteration:
            raise NonInteractiveEnvironmentError("stop")

    real = builtins.input
    try:
        builtins.input = reply
        with contextlib.redirect_stdout(io.StringIO()):
            outcome = getattr(_menu, task_id)()
    except Exception:
        return False, "", ""
    finally:
        builtins.input = real

    if not isinstance(outcome, WorkflowOutcome):
        return False, "", ""
    if outcome.variant is not WorkflowVariant.COMPARISON:
        return False, "", ""

    def digest(cfg):
        if cfg is None:
            return ""
        return hashlib.sha256(
            repr(dataclasses.asdict(cfg)).encode()).hexdigest()[:16]

    a, b = digest(outcome.starting_config), digest(
        outcome.current_config)
    return a != b and bool(a) and bool(b), a, b
