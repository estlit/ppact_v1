"""
ppact.modes - the first screen: choose a purpose, not a feature

WHY THIS EXISTS
===============
The simulator grew a menu of seventeen entries named after what they do:
"Compare HBM3E and HBM4 on an LLM workload", "Sweep the whole design space".
Every one of those is a good name for someone who already knows what HBM is.
A student opening this for the first time knows none of it, and a screen that
demands vocabulary before it offers anything is a screen that teaches nothing.

So the first question is not WHICH FEATURE but WHAT FOR. The same engine
serves a student on their first day, a student handing in an assignment, a
researcher sweeping parameters, someone presenting at a conference, and
someone checking the model itself. Those are five different programs sharing
one set of numbers, and the mode is how a person says which one they want.

THE RULE THAT MATTERS MOST
--------------------------
This module NEVER computes anything. It reads a choice and calls into the
engine. If a number appears on screen it came from ppact.system, and it is
the same number whichever mode asked for it - otherwise a student and a
researcher would be looking at two different simulators and neither would
know it.

WHAT DOES NOT BELONG ON THE FIRST SCREEN
----------------------------------------
  - technical vocabulary: CPU, NPU, HBM, LLM, node, batch
  - any parameter at all
  - more than one line per entry
  - anything that changes when a feature is added

That last one is the reason the main menu is fixed at six modes. New
capabilities go INSIDE Research, where the audience already has the
vocabulary. A first screen that grows every release is a first screen nobody
learns.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple

LINE = "=" * 78
RULE = "-" * 78

# Words that must not appear on the first screen. Not a style preference: a
# student who does not know what an NPU is cannot choose a menu entry that
# assumes they do, and will pick at random or stop.
FORBIDDEN_ON_FIRST_SCREEN = (
    "cpu", "npu", "hbm", "llm", "dram", "lpddr", "gddr", "sram",
    "node", "batch", "kv", "quantis", "quantiz", "roofline", "tops",
    "bandwidth", "latency", "throughput", "mutation", "coefficient",
)


@dataclass(frozen=True)
class Mode:
    key: str
    number: int
    title: str
    one_line: str          # exactly one line, no vocabulary
    audience: str          # who this is for, shown inside the mode
    purpose: str           # what they will have when they leave
    # entries are (label, task-name) resolved lazily against ppact.menu, so
    # this module does not import the engine at load time
    entries: Tuple[Tuple[str, str], ...] = ()
    auto: Tuple[str, ...] = ()      # tasks run without asking, in order
    # WHICH ENTRY ENTER SELECTS. 1-based, and never the exit.
    #
    # The menu used to default to "Back": pressing Enter on a mode you had
    # just chosen took you straight out of it, having done nothing. Enter is
    # what a first-time reader presses on a screen they do not yet
    # understand, so the default has to be the thing that screen exists for.
    primary: int = 1


MODES: Tuple[Mode, ...] = (
    Mode(
        "quick", 1, "Quick Start",
        "See what this does, without deciding anything",
        audience="anyone opening this for the first time",
        purpose="a worked example from end to end, with nothing to fill in",
        auto=("task_quickstart",),
    ),
    Mode(
        "education", 2, "Education Mode",
        "Learn how the parts of a system decide each other",
        audience="students meeting these ideas for the first time",
        purpose="the reasoning behind a design, one step at a time",
        entries=(
            ("Take the lessons, in order", "task_lessons"),
            ("Think like an architect: a guided comparison", "task_guided"),
            ("Build a design step by step", "task_game"),
            ("Watch a design run, and see where the time goes", "task_runtime"),
            ("Ask why a number changed", "task_decide"),
            ("Try a change and put it back", "task_whatif"),
            ("Propose a change and have it reviewed", "task_review"),
            ("See how much a conclusion depends on an assumption",
             "task_sensitivity"),
        ),
    ),
    Mode(
        "challenge", 3, "Challenge Mode",
        "Change one thing in a working design, and defend it",
        audience="students with an assignment",
        purpose="a result that can be marked, and a reason it should be",
        entries=(
            ("Take a set challenge", "task_challenge"),
            ("Start from a starting point and change it",
             "task_innovation"),
            ("See how the work is marked", "task_rubric"),
            ("Check a result against what the application needs",
             "task_interpret"),
        ),
    ),
    Mode(
        "research", 4, "Research Mode",
        "Set every value yourself and sweep whatever you like",
        audience="researchers and graduate students",
        purpose="the full model, with nothing hidden and nothing assumed",
        entries=(
            ("Build one candidate by hand", "task_custom"),
            ("Sweep the design space and rank what survives", "task_sweep"),
            ("Explain a change and get a report", "task_decide"),
            ("Try a change and put it back", "task_whatif"),
            ("Propose a change and have it reviewed", "task_review"),
            ("Evaluate an application against the candidates",
             "task_evaluate"),
            ("Compare memory technologies", "task_memory"),
            ("Compare memory generations on a language model",
             "task_memory_generations"),
            ("Check what must hold when a design moves", "task_migration"),
            ("Test how far a verdict survives its assumptions",
             "task_sensitivity"),
            ("Run a design and watch the stations", "task_runtime"),
            ("Recent designs, saved designs, search and export",
             "task_workspace"),
            ("All tools, listed by what they do", "task_all_tools"),
        ),
    ),
    Mode(
        "demo", 5, "Demo Mode",
        "Pick a question and watch it answered",
        audience="an audience - a lecture, a talk, a recording",
        purpose="one question, one comparison, one answer",
        entries=(
            ("Pick a question and watch it answered", "task_demo"),
            ("What do the starting points look like?", "task_designs"),
            ("Why did that number change?", "task_decide"),
            ("What can this model NOT say?", "task_industry"),
            ("What does this analyse at all?", "task_framework"),
            ("About: what this is and how to read it", "task_about"),
        ),
    ),
    Mode(
        "validation", 6, "Validation Mode",
        "Check the model itself, and the evidence behind it",
        audience="whoever has to trust the numbers",
        purpose="the evidence, including what is missing from it",
        entries=(
            ("What was checked, and what is missing",
             "task_validation_summary"),
            ("What ran, and does a rerun agree", "task_reproducibility"),
            ("Reference scenarios and their expected results", "task_gold"),
            ("Industry cases: what the model can and cannot express",
             "task_industry"),
            ("How much a verdict depends on an assumption",
             "task_sensitivity"),
            ("What is analysed, and what is not", "task_framework"),
            ("About: what this is and how to read it", "task_about"),
        ),
    ),
)

BY_NUMBER = {m.number: m for m in MODES}
BY_KEY = {m.key: m for m in MODES}


def first_screen_violations(modes: Optional[Tuple[Mode, ...]] = None
                            ) -> List[str]:
    """Vocabulary that must not be on the first screen, if any leaked in.

    Takes the modes as an argument so a test can hand it a deliberately bad
    one. A detector that has only ever been shown correct input is not known
    to work - which this project has now found five times.
    """
    problems = []
    for m in (MODES if modes is None else modes):
        text = f"{m.title} {m.one_line}".lower()
        for word in FORBIDDEN_ON_FIRST_SCREEN:
            if word in text:
                problems.append(
                    f"mode {m.number} ({m.key}): '{word}' appears in the "
                    f"first-screen text, which assumes vocabulary a new "
                    f"reader does not have")
        if "\n" in m.one_line:
            problems.append(f"mode {m.number}: description is not one line")
        # The RENDERED line, not the description alone. A first version
        # limited the description to 62 characters and let mode 6 print at
        # 84, because the prefix - number, dot, padded title - was not
        # counted. A line that wraps is two lines whatever the field was
        # measured as.
        rendered = f"    {m.number}. {m.title:<18s}{m.one_line}"
        if len(rendered) > 78:
            problems.append(
                f"mode {m.number}: the rendered line is {len(rendered)} "
                f"characters and wraps at 78")
    return problems


_BANNER_SHOWN = False


def print_main_menu(with_banner: bool = True) -> None:
    """The first screen.

    The banner is printed once per session rather than above every return to
    the menu - a claim repeated ten times reads as noise and stops being
    read, which is the opposite of what a claim is for.
    """
    global _BANNER_SHOWN
    from .branding import print_banner
    from . import __version__
    first = with_banner and not _BANNER_SHOWN
    if first:
        print_banner(__version__)
        _BANNER_SHOWN = True
    else:
        # The title is not repeated under the banner - a heading printed
        # twice in eight lines reads as a fault, not as emphasis.
        print(f"\n{LINE}")
        print(f"{'PPACT Studio':^78}")
        from .branding import AXES as _AXES
        print(f"{_AXES:^78}")
        print(LINE)
    print("\n  Choose what you are here to do.\n")
    for m in MODES:
        print(f"    {m.number}. {m.title:<18s}{m.one_line}")
    print(f"\n    0. Exit")
    print(f"\n{RULE}")


def _resolve(task_name: str) -> Optional[Callable]:
    """Find a task by name, without importing the engine until needed."""
    from . import menu
    return getattr(menu, task_name, None)


def run_mode(mode: Mode, ask_fn: Callable) -> None:
    """Show one mode. Every screen looks the same, so nothing is learned."""
    from . import menu

    if mode.auto:
        print(f"\n{LINE}")
        print(f" {mode.title}")
        print(LINE)
        print(f"  {mode.purpose}\n")
        for name in mode.auto:
            fn = _resolve(name)
            if fn is None:
                print(f"  (this part of the tour is unavailable: {name})")
                continue
            fn()
        return

    while True:
        print(f"\n{LINE}")
        print(f" {mode.title}")
        print(LINE)
        print(f"  for {mode.audience}")
        print(f"  you will leave with {mode.purpose}\n")
        labels = [label for label, _ in mode.entries]
        default = mode.primary
        if not 1 <= default <= len(labels):
            default = 1
        from .menu import ask_nav
        choice = ask_nav("Activity",
                         "Choose what to do in this mode.",
                         labels + ["Back"], default)
        if choice > len(labels):
            return
        fn = _resolve(mode.entries[choice - 1][1])
        if fn is None:
            print(f"\n  That part is not available in this build.")
            continue
        fn()


def _select(prompt: str, highest: int, default: int) -> int:
    """Read a number. Does NOT reprint the options.

    The shared ask() helper renders its own list, which printed the six modes
    a second time directly under the first screen. A first screen shown twice
    is a first screen that looks broken.
    """
    while True:
        try:
            raw = input(f"\n  {prompt} [{default}]: ").strip()
        except Exception:
            # No input at all: a bare terminal raises EOFError, a piped stdin
            # runs out, and a notebook kernel raises ipykernel's
            # StdinNotImplementedError, which shares no useful base class.
            #
            # STOP rather than take the default. The default here is 1, so
            # taking it means running Quick Start, returning to this menu,
            # taking it again - forever. A launcher run with no stdin hung
            # for the whole of a 300-second deployment check that way, and a
            # student whose notebook cannot prompt would have seen the same.
            # A menu that cannot be answered should end, not loop.
            print(f"  (no input available - stopping)")
            return 0
        if not raw:
            return default
        if raw.isdigit() and 0 <= int(raw) <= highest:
            return int(raw)
        print(f"  Enter a number from 0 to {highest}.")


def main(loop: bool = True) -> int:
    """The front door. Reads a choice; computes nothing."""
    from .menu import ask

    while True:
        print_main_menu()
        choice = _select("Select", len(MODES), 1)
        if choice == 0:
            print("\n  Done.")
            return 0
        run_mode(BY_NUMBER[choice], ask)
        if not loop:
            return 0
