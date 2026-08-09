"""
tests_menu_paths.py - walk the paths a user actually takes

WHY THIS SUITE EXISTS
=====================
A user opened Education Mode, chose "Build a design step by step", and got
an UnboundLocalError on the first question.

Nothing in the release validation caught it. Every suite called the engine
functions directly - evaluate_system, explain, build_balance - and every one
of them worked. The defect was in the code BETWEEN the menu and the engine,
and no test had ever gone through the menu.

The cause is worth stating precisely, because it is a Python trap rather
than a typo: a name imported INSIDE a function is a local name for the WHOLE
function, including the lines above the import. So

    def play():
        ...
        chosen = _q("application")          # line 483
        ...
        from .questions import get as _q    # line 503

raises UnboundLocalError at line 483. Python does not complain at import
time, at definition time, or on any path that does not reach line 483 - it
raises on exactly one path, at run time, which is why every suite passed.

WHAT THIS SUITE DOES
--------------------
Drives the interactive paths with scripted input and requires that none of
them raises. It does not check what the screens say - other suites do that.
It checks that a user can get through them at all.

It also scans for the defect class directly, because a path that has not
been scripted yet is a path this suite does not cover.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

import ast
import builtins
import contextlib
import io
import os
import re
import sys
import traceback

sys.path.insert(0, ".")

LINE = "=" * 84
RESULTS = []


def check(pack, name, cond, detail=""):
    RESULTS.append((pack, name, bool(cond), detail))


class _TookTooLong(Exception):
    pass


def walk(fn, answers, label, pack="MP", require=(), limit=25):
    """Run an interactive function with scripted answers.

    Empty strings take the default, which is the path a first-time user
    takes when they press Enter through a screen they do not yet
    understand - and the path most likely to be untested.
    """
    # EXPLICIT answers, then EXIT.
    #
    # The filler was "1" repeated. A screen that returns to its own menu
    # then re-enters on every answer and never terminates: the challenge
    # task consumed two hundred prompts and was still going. That is the
    # harness looping, not the program failing, and reporting it as a
    # product defect would have been wrong.
    #
    # So the tail answers "1" enough times to walk one pass through a
    # task, then answers "0" - the exit entry on every menu in this
    # program - for as long as anything keeps asking.
    # "0" is the exit entry on the MENUS. It is not a valid option number
    # on an engineering question, which refuses it and asks again - so the
    # tail alternates: a valid choice, then an exit. Whichever kind of
    # screen is asking, one of the two answers it.
    tail = []
    for _ in range(120):
        tail += ["1", "0"]
    seq = iter(list(answers) + tail)
    real_input = builtins.input
    buf = io.StringIO()

    # A wall-clock limit, because a screen that re-enters its own menu on
    # the default answer never runs out of input - it just never stops, and
    # a suite that hangs is a suite somebody stops running.
    import signal

    def _timeout(signum, frame):
        raise _TookTooLong(f"still running after {limit}s on default input")

    previous = signal.signal(signal.SIGALRM, _timeout)
    signal.alarm(limit)
    try:
        builtins.input = lambda prompt="": next(seq)
        with contextlib.redirect_stdout(buf):
            fn()
        check(pack, f"{label}: completes without an exception", True)
    except Exception as exc:
        check(pack, f"{label}: completes without an exception", False,
              f"{type(exc).__name__}: {exc}\n"
              + "".join(traceback.format_exc().splitlines(True)[-4:-1]))
        return buf.getvalue()
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)
        builtins.input = real_input

    text = buf.getvalue()
    for marker in require:
        check(pack, f"{label}: reaches {marker!r}", marker in text,
              "the path completed but never got there")
    return text


# ==============================================================================
# MP - the interactive paths
# ==============================================================================

def mp_design_game():
    """Education Mode -> Build a design step by step.

    The exact path that failed. Driven twice: once entirely on defaults,
    once with explicit choices, because a default-only walk can miss a
    branch that only a non-default answer reaches.
    """
    from ppact.game import play

    # THE SEVEN-PANEL CONTRACT, not the retired renderer's title.
    #
    # "STANDARD ENGINEERING DESIGN REVIEW" was a heading printed by
    # `render_standard_engineering_review`, which every workflow has
    # been moved off. The report a completed workflow produces now opens
    # with ENGINEERING REPORT and carries the declared panels.
    walk(play, [], "design game, all defaults",
         require=["STEP 1", "STEP 2", "STEP 3",
                  "PRIORITY-WEIGHTED EDUCATION SCORE",
                  "ENGINEERING REPORT", "MEASURED RESULTS",
                  "ENGINEERING CONCLUSION"])

    # explicit answers: a different application, a larger engine, more
    # memory units, a different priority, and the full review
    walk(play, ["3", "5", "3", "3", "2", "4", "1", "1", "2", "1"],
         "design game, explicit choices",
         require=["STEP 3", "PRIORITY-WEIGHTED EDUCATION SCORE"])

    # and declining the review must end cleanly rather than falling through
    text = walk(play, ["1", "5", "3", "3", "2", "4", "1", "1", "2"],
                "design game, review declined")
    check("MP", "declining the review still reaches the score",
          "PRIORITY-WEIGHTED EDUCATION SCORE" in text)


# Deterministic scenarios. One per task that needs more than a walk.
#
# A tail of repeated answers is not a scenario: it cannot say what a task
# was asked to do, and a task returning to its own menu consumes answers
# forever. Each entry lists the answers in order and what must be OBSERVED,
# so "it did not crash" is never mistaken for "it completed".
class _ScenarioExhausted(BaseException):
    """The scenario ran out of meaningful answers.

    A BaseException, and deliberately so. ask() catches Exception broadly
    and falls back to its default - correct for a dead terminal, wrong
    here, where it turned "the scenario ended" into "carry on with
    defaults" and let one run reach 2,805 prompts.

    Test-only. Nothing in ppact raises or catches it.
    """


def back_option(labels):
    """The number of the Back entry, read from the menu it belongs to.

    Hardcoding produced four wrong guesses - 0, 16, 17, 18 - because the
    position moves with the number of entries, and one of them silently
    chose "All of them" and ran every demo. The contract is "choose Back";
    the number is a consequence of the menu.
    """
    for i, text in enumerate(labels, 1):
        # "Done" is What-if's exit. A menu names its way out in whatever
        # word fits the screen, and reading only "Back" made the harness
        # walk past the exit it was looking for.
        if str(text).strip().lower() in ("back", "exit", "return", "done"):
            return i
    return None


SCENARIOS = {
    "task_challenge": {
        # Answer the first challenge's fields, then leave when the
        # challenge menu comes back.
        "answers": {"Keep the current value": 1},
        "want_back": lambda log: sum(1 for k, _ in log
                                     if k == "menu-seen") >= 2,
        "must_reach": ("CHALLENGES",
                       "ENGINEERING REPORT",
                       "ARCHITECTURE SUMMARY",
                       "MEASURED RESULTS",
                       "ENGINEERING CONCLUSION"),
        "max_prompts": 40,
    },
    "task_demo": {
        # Back only AFTER the demo menu has been seen twice: once to pick a
        # demo, once when it returns. Asking for it at the first menu chose
        # the exit before anything ran, and every "reaches" check failed
        # while "terminates normally" passed - which is what a scenario
        # that does nothing looks like.
        "answers": {},
        "want_back": lambda log: sum(1 for k, _ in log
                                     if k == "menu-seen") >= 2,
        "must_reach": ("ANSWER", "BECAUSE",
                       "ENGINEERING REVIEW FOR THIS QUESTION",
                       "MEASURED RESULTS"),
        "max_prompts": 20,
    },
    "task_whatif": {
        # What-if now asks through the registry, so its knobs require an
        # explicit choice and the generic walk cannot answer them. It also
        # loops: every change returns to the same menu.
        #
        # The scenario changes one thing, reads the result, and leaves by
        # label - which is the path a user takes and the one worth
        # checking.
        "answers": {"Keep the current value": 1},
        "want_back": lambda log: sum(1 for k, _ in log
                                     if k == "menu-seen") >= 2,
        "must_reach": ("WHAT IF", "MEASURED RESULTS"),
        "max_prompts": 40,
    },
    "task_lessons": {
        # No question count anywhere. The lesson is entered, its questions
        # are answered with the first option, and Back is chosen the second
        # time a menu offering Back appears - that is, once the lesson has
        # returned to the menu it came from.
        "answers": {},
        "want_back": lambda log: sum(1 for k, _ in log
                                     if k == "menu-seen") >= 2,
        "must_reach": ("LESSON",),
        "max_prompts": 40,
    },
}


def responder(scenario, seen, log):
    """Answer by what the screen IS, not by how many answers came before.

    Counting questions produced four wrong guesses in a row. Each was
    correct until a lesson asked one more question, and then the answer
    meant for the menu landed inside a lesson instead.

    The contract is not "pass N questions then choose 16". It is:

        a menu offering Back      -> choose Back, by its label
        a known engineering       -> the answer this scenario registered
        anything else             -> FAIL, naming the prompt

    So the harness reads the options that were just printed and decides
    from those, which survives a question being added.
    """
    def answer(prompt, printed):
        options = _options_from(printed)
        seen.append((prompt.strip()[:30], len(options)))

        back = back_option(options)
        if back is not None and scenario["want_back"](log):
            log.append(("back", back))
            return str(back)

        for marker, value in scenario["answers"].items():
            if any(marker.lower() in o.lower() for o in options):
                log.append((marker, value))
                return str(value)

        if options:
            log.append(("default-first", 1))
            return "1"

        raise _ScenarioExhausted(prompt)
    return answer


def _options_from(printed: str):
    """The numbered options of the screen that was just drawn."""
    out = []
    for line in reversed(printed.splitlines()):
        m = re.match(r"\s*(\d+)\.\s+(.*)", line)
        if m:
            out.append((int(m.group(1)), m.group(2).strip()))
        elif out:
            break
    out.reverse()
    return [text for _, text in out]


def mp_scenarios():
    """Each scripted path must be OBSERVED to finish, not merely to run.

    Input exhaustion, a timeout, an exception or a review printed before a
    later failure are all distinct from completion, and none of them is a
    pass.
    """
    P = "SC"
    from ppact import menu
    import signal

    by_name = {fn.__name__: fn for _, fn in menu.TASKS}
    for name, plan in SCENARIOS.items():
        fn = by_name.get(name)
        if fn is None:
            check(P, f"{name}: exists as a menu task", False,
                  "the scenario names a task the menu does not offer")
            continue

        log, seen = [], []
        buf = io.StringIO()
        answer = responder(plan, seen, log)
        extra = [None]

        def reader(prompt="", answer=answer, buf=buf, plan=plan, log=log):
            if len(seen) > plan["max_prompts"]:
                extra[0] = prompt.strip()[:60]
                raise _ScenarioExhausted(prompt)
            printed = buf.getvalue()
            options = _options_from(printed)
            if back_option(options) is not None:
                log.append(("menu-seen", 0))
            return answer(prompt, printed)

        real = builtins.input

        def _late(signum, frame):
            raise _TookTooLong("scenario did not finish")

        prev = signal.signal(signal.SIGALRM, _late)
        signal.alarm(90)
        outcome, exc = "completed", None
        try:
            builtins.input = reader
            with contextlib.redirect_stdout(buf):
                fn()
        except _TookTooLong:
            outcome = "TIMEOUT"
        except _ScenarioExhausted:
            outcome = "UNEXPECTED PROMPT"
        except Exception as e:
            outcome, exc = "ERROR", e
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, prev)
            builtins.input = real

        text = buf.getvalue()
        # Separate observations, not one verdict. A path can reach the
        # review and still never terminate, and one PASS would hide it.
        check(P, f"{name}: entry reached", bool(seen),
              "no prompt was ever shown")
        for marker in plan["must_reach"]:
            check(P, f"{name}: reaches {marker!r}", marker in text,
                  "the scenario ran and never got there")
        check(P, f"{name}: returned to a menu offering Back",
              any(k == "menu-seen" for k, _ in log[1:]),
              "the task never came back to the menu it started from")
        check(P, f"{name}: Back was selected by label",
              any(k == "back" for k, _ in log),
              "the exit was never chosen; a number was guessed instead")
        check(P, f"{name}: terminates normally", outcome == "completed",
              f"{outcome}"
              + (f' after the scenario: "{extra[0]}"' if extra[0] else "")
              + (f": {type(exc).__name__}: {exc}" if exc else ""))


def mp_menu_tasks():
    """Every task the full tool list offers, driven on defaults.

    A task that raises is a task a user cannot use, whatever the engine
    behind it computes.
    """
    from ppact import menu

    # A few tasks run long sweeps or the full mutation runner. They are
    # exercised by their own suites; what this checks is that the MENU can
    # reach every task without raising, so the slow ones are skipped by
    # name rather than by a timeout that would make the result depend on
    # how busy the machine is.
    # Covered by SCENARIOS with deterministic input, so the generic walk
    # would only re-run them worse.
    SLOW = {"task_game"} | set(SCENARIOS)
    skipped = []
    for label, fn in menu.TASKS:
        if fn.__name__ in SLOW:
            skipped.append(fn.__name__)
            continue
        walk(fn, [], f"task {fn.__name__}", pack="MP")
    check("MP", "the skipped tasks are named, not silently dropped",
          bool(skipped), str(sorted(skipped)[:4]))


def mp_modes():
    """Each mode's own entry list, resolved and called.

    A mode entry naming a task that does not exist is a menu item that
    raises the moment somebody picks it.
    """
    from ppact import menu, modes

    names = {fn.__name__: fn for _, fn in menu.TASKS}
    for m in modes.MODES:
        for label, task in list(m.entries) + [(t, t) for t in m.auto]:
            check("MP", f"mode {m.key}: {task!r} exists",
                  task in names or hasattr(menu, task),
                  "a mode entry pointing at nothing raises when picked")


# ==============================================================================
# ND - navigation defaults
# ==============================================================================
#
# The mode menu defaulted to "Back". Pressing Enter on a mode you had just
# chosen took you out of it having done nothing.
#
# Enter is what a first-time reader presses on a screen they do not yet
# understand. Making it the exit means the one action a hesitant user is
# most likely to take is the one that undoes their last decision.

EXIT_WORDS = ("back", "exit", "cancel", "return", "quit", "leave",
              "no - ", "none of these")


def nd_no_exit_default():
    P = "ND"
    from ppact import modes

    for m in modes.MODES:
        if not m.entries:
            continue
        check(P, f"{m.key}: the default is a real entry",
              1 <= m.primary <= len(m.entries),
              f"primary={m.primary} against {len(m.entries)} entries")
        label = m.entries[min(max(m.primary, 1), len(m.entries)) - 1][0]
        check(P, f"{m.key}: Enter does not leave the mode",
              not any(w in label.lower() for w in EXIT_WORDS),
              f"default action is {label!r}")
        check(P, f"{m.key}: and the default is not the last item",
              m.primary <= len(m.entries),
              "the exit is appended after the entries; a default past the "
              "entries is the exit")

    # every question the registry holds gets the same rule
    from ppact import questions as Q
    for key, raw in sorted(Q.REGISTRY.items()):
        q = raw.resolved()
        chosen = q.default_option()
        if chosen is None:
            # An engineering question has no default at all, which is a
            # stronger version of this rule rather than an exemption from
            # it: nothing is preselected, so nothing preselected is an
            # exit. default_option() returns None for these, and reading
            # .label on it raised AttributeError.
            check(P, f"question {key}: the default is not an exit", True,
                  "no default exists")
            continue
        label = chosen.label.lower()
        check(P, f"question {key}: the default is not an exit",
              not any(w in label for w in EXIT_WORDS),
              f"default is {chosen.label!r}")

    # POSITIVE CONTROL. This rule had never fired, and a rule that has only
    # seen correct menus is not known to work.
    import dataclasses as _dc
    broken = _dc.replace(modes.MODES[1], primary=99)
    label_ok = 1 <= broken.primary <= len(broken.entries)
    check(P, "the rule rejects a default past the last entry", not label_ok,
          "a default index beyond the entries lands on the exit")
    fake = ("Back to the previous menu", "task_x")
    check(P, "and rejects an exit label as the default",
          any(w in fake[0].lower() for w in EXIT_WORDS))


# ==============================================================================
# UB - the defect class, found statically
# ==============================================================================

def ub_local_import_shadowing():
    """A name imported inside a function, used above the import.

    Python treats it as a local for the whole function and raises
    UnboundLocalError at run time on exactly one path. Scanned rather than
    walked, because a path nobody has scripted yet is a path the walk does
    not cover - and this defect is invisible until that path runs.
    """
    P = "UB"
    findings = []
    for fname in sorted(os.listdir("ppact")):
        if not fname.endswith(".py"):
            continue
        path = os.path.join("ppact", fname)
        tree = ast.parse(open(path, encoding="utf-8").read())
        for fn in [n for n in ast.walk(tree)
                   if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
            # parameters are already bound on entry and are not the defect
            bound = {a.arg for a in fn.args.args}
            bound |= {a.arg for a in fn.args.kwonlyargs}
            if fn.args.vararg:
                bound.add(fn.args.vararg.arg)
            if fn.args.kwarg:
                bound.add(fn.args.kwarg.arg)

            imported = {}
            for n in ast.walk(fn):
                if isinstance(n, (ast.Import, ast.ImportFrom)):
                    for a in n.names:
                        nm = a.asname or a.name.split(".")[0]
                        if nm not in bound:
                            imported.setdefault(nm, n.lineno)
            for n in ast.walk(fn):
                if not (isinstance(n, ast.Name)
                        and isinstance(n.ctx, ast.Load)):
                    continue
                if n.id in imported and n.lineno < imported[n.id]:
                    findings.append(
                        f"{fname}:{fn.name} uses {n.id!r} at line {n.lineno}, "
                        f"imported at {imported[n.id]}")
    seen, unique = set(), []
    for f in findings:
        if f not in seen:
            seen.add(f)
            unique.append(f)
    check(P, "no function uses a name above its own local import",
          not unique, "; ".join(unique[:3]))

    # POSITIVE CONTROL. This detector had never fired before the defect it
    # was written for, and a detector that has only seen correct code is not
    # known to work.
    broken = ast.parse(
        "def f():\n"
        "    print(_q)\n"
        "    from x import get as _q\n")
    fn = broken.body[0]
    imported = {}
    for n in ast.walk(fn):
        if isinstance(n, ast.ImportFrom):
            for a in n.names:
                imported.setdefault(a.asname or a.name, n.lineno)
    caught = any(isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)
                 and n.id in imported and n.lineno < imported[n.id]
                 for n in ast.walk(fn))
    check(P, "and the scan catches the pattern when shown it", caught,
          "the exact shape of the defect must be detected")


def main():
    print(LINE)
    print(" MENU PATH REGRESSION")
    print(LINE)
    print("  Every suite called the engine directly and passed while a user")
    print("  could not get past the first question of Education Mode. This")
    print("  walks the paths a person takes.\n")

    for fn in (nd_no_exit_default, mp_design_game, mp_modes,
               mp_menu_tasks, ub_local_import_shadowing):
        try:
            fn()
        except Exception as exc:
            check("XX", f"{fn.__name__} completes", False,
                  f"{type(exc).__name__}: {exc}")

    by_pack = {}
    for pack, name, ok, detail in RESULTS:
        p = by_pack.setdefault(pack, [0, 0])
        p[1] += 1
        if ok:
            p[0] += 1
    for pack, name, ok, detail in RESULTS:
        if not ok:
            print(f"  FAILED [{pack}] {name}")
            if detail:
                for ln in str(detail).splitlines():
                    print(f"          {ln}")

    passed = sum(1 for _, _, ok, _ in RESULTS if ok)
    labels = {"MP": "menu paths", "ND": "navigation defaults",
              "UB": "local-import shadowing"}
    print(f"\n{LINE}")
    for pack in sorted(by_pack):
        good, total = by_pack[pack]
        print(f"  {pack}  {labels.get(pack, pack):<26s}{good:>5d} / "
              f"{total:<6d}{'pass' if good == total else 'FAIL'}")
    print(f"\n  {passed} / {len(RESULTS)} checks")
    print(f"\n  This suite does not check what the screens say. It checks")
    print(f"  that a user can get through them at all, which is the one")
    print(f"  thing every other suite assumed.")
    print(LINE)
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
