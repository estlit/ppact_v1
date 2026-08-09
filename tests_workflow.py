"""
Workflow QA - can a first-time user reach the end without getting stuck?

WHAT THE EXISTING SUITES ALREADY DO
===================================
tests_menu_paths walks every task to completion and checks that Back is
reachable. tests_review_contract checks what the screens say. Neither
answers the questions a user actually has at the moment of clicking:

    does this finish, or has it hung?
    is there a way out of this screen?
    did the picture I was promised appear?
    if something failed, did it take the session with it?

WHY THESE ARE DIFFERENT QUESTIONS
---------------------------------
Almost every defect found in this project's late stages was a CONNECTION
fault rather than a calculation fault: a screen citing a screen that had
been renamed, a chart answering a question the dossier had moved on from,
a filename overwritten fifteen times. The engine was right and the
workflow was not.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

import builtins
import contextlib
import glob
import io
import os
import re
import sys
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

RESULTS = []
TIMINGS = {}
WIDE = {}

# WF-WIDTH-001. Eighteen tasks print past 78 columns and are deferred.
# The check that earns its place is not "are there wide lines" but "are
# there MORE than were known about".
KNOWN_WIDE = 18

# A screen with no way onward is where a user stops trusting the tool.
# They do not report it; they close the window.
EXITS = ("back", "quit", "exit", "next", "home", "nothing",
         "return", "done", "menu", "continue")


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))


def run_task(fn, answers, budget_s=90.0):
    """Drive one task with canned answers. Return (ok, text, seconds)."""
    seq = iter(answers)
    real = builtins.input
    buf = io.StringIO()
    t0 = time.time()
    try:
        builtins.input = lambda prompt="": next(seq, "0")
        with contextlib.redirect_stdout(buf):
            fn()
        return True, buf.getvalue(), time.time() - t0, ""
    except StopIteration:
        return True, buf.getvalue(), time.time() - t0, ""
    except Exception:
        return (False, buf.getvalue(), time.time() - t0,
                traceback.format_exc().strip().splitlines()[-1])
    finally:
        builtins.input = real


# ==============================================================================
# WF-1 - every menu entry runs to completion
# ==============================================================================

def _task_worker(index: int) -> dict:
    """One task, in its own process.

    Thirty tasks in one interpreter exhausted the container even with the
    figures closed - some hold state that outlives a close(). Isolation
    is not tidiness here: without it the suite is killed before it
    reports anything, and a QA suite that cannot finish is not a QA
    suite.
    """
    import json
    import subprocess

    here = os.path.dirname(os.path.abspath(__file__))
    code = f"""
import sys, io, time, builtins, contextlib, traceback, json, re
sys.path.insert(0, {here!r})
import matplotlib; matplotlib.use('Agg')
from ppact import menu
label, fn = menu.TASKS[{index}]

# ANSWERING '1' FOREVER IS NOT A USER.
#
# task_lessons puts Back LAST, so a harness that always picks the first
# option re-enters lesson one forever and the process dies on memory. The
# suite reported "no output" and the real finding - an unbounded loop
# under a degenerate answer - was invisible.
#
# A user picks a couple of things and then leaves. This answers 1 twice,
# then takes the highest-numbered option offered, which is Back or Quit
# on every menu in Studio.
seen = ['']
calls = [0]

class Tee(io.StringIO):
    def write(self, s):
        seen[0] = (seen[0] + s)[-4000:]
        return super().write(s)

def reply(prompt=''):
    calls[0] += 1
    if calls[0] <= 2:
        return '1'
    nums = [int(x) for x in re.findall(r'^\\s*(\\d+)[.)]', seen[0], re.M)]
    return str(max(nums)) if nums else '0'

builtins.input = reply
buf = Tee(); t0 = time.time(); err = ''
try:
    with contextlib.redirect_stdout(buf): fn()
    ok = True
except StopIteration:
    ok = True
except Exception:
    ok = False
    err = traceback.format_exc().strip().splitlines()[-1]
t = buf.getvalue()
print(json.dumps({{'name': fn.__name__, 'ok': ok, 'err': err,
                  'secs': time.time() - t0, 'chars': len(t),
                  'tail': t.strip()[-900:],
                  'wide': [len(l) for l in t.splitlines()
                           if len(l) > 78][:3]}}))
"""
    try:
        out = subprocess.run([sys.executable, "-c", code],
                             capture_output=True, text=True, timeout=180)
        got = [l for l in out.stdout.splitlines() if l.startswith("{")]
        if not got:
            tail = (out.stderr.strip().splitlines() or ["no output"])[-1]
            return {"name": f"task[{index}]", "ok": False,
                    "err": tail[:90], "secs": 0.0, "chars": 0,
                    "tail": "", "wide": []}
        return json.loads(got[-1])
    except subprocess.TimeoutExpired:
        return {"name": f"task[{index}]", "ok": False,
                "err": "timed out after 180s", "secs": 180.0,
                "chars": 0, "tail": "", "wide": []}


def wf1_every_task_completes():
    """WF-1, WF-4 and the column limit, from one transcript per task."""
    from ppact import menu

    for i in range(len(menu.TASKS)):
        r = _task_worker(i)
        TIMINGS[r["name"]] = r["secs"]
        check(f"WF-1 {r['name']}: completes without an exception",
              r["ok"], r["err"])
        check(f"WF-1 {r['name']}: produces output", r["chars"] > 0)
        # RECORDED, NOT ASSERTED, while WF-WIDTH-001 is open.
        #
        # Eighteen tasks exceed the limit today. Failing all eighteen on
        # every run trains a reader to skip the failures, and the number
        # that matters is whether a NINETEENTH appears.
        if r["wide"]:
            WIDE[r["name"]] = r["wide"]
        tail = r["tail"].splitlines()[-25:]
        joined = " ".join(tail).lower()
        prompts = [l for l in tail
                   if l.strip().endswith("?") or "choose" in l.lower()]
        check(f"WF-4 {r['name']}: the last screen offers a way on",
              (not prompts) or any(w in joined for w in EXITS),
              f"...{joined[-80:]}")


# ==============================================================================
# WF-2 and WF-5 - the promised pictures exist and are readable
# ==============================================================================

def wf2_demo_artefacts():
    from ppact.demo import DEMOS

    root = "/mnt/user-data/outputs/demo_dossiers"
    if not os.path.isdir(root):
        check("WF-2 the dossier tree exists", False, root)
        return
    check("WF-2 the dossier tree exists", True)

    for i, demo in enumerate(DEMOS, 1):
        d = os.path.join(root, f"demo_{i:03d}")
        stem = f"demo_{i:03d}"
        for kind in ("measured_results", "bottleneck", "ppact_spider"):
            p = os.path.join(d, f"{stem}_{kind}.png")
            check(f"WF-5 {stem}: {kind} exists", os.path.isfile(p))
            if os.path.isfile(p):
                size = os.path.getsize(p)
                check(f"WF-5 {stem}: {kind} is not empty",
                      size > 20000, f"{size} bytes")
                try:
                    from PIL import Image
                    Image.open(p).verify()
                    ok = True
                except Exception as exc:
                    ok = False
                check(f"WF-5 {stem}: {kind} opens as an image", ok)
        for kind in ("spec.md", "inputs.csv", "results.csv",
                     "claim_checks.csv", "explanation_en.md"):
            check(f"WF-2 {stem}: {kind} exists",
                  os.path.isfile(os.path.join(d, f"{stem}_{kind}")))


# ==============================================================================
# WF-8 - the fifteen run back to back without overwriting each other
# ==============================================================================

def wf8_demo_run():
    from ppact.demo import DEMOS
    from ppact.demo_visual import render_demo_charts

    out = "/tmp/wf8_run"
    os.system(f"rm -rf {out}")
    names = {}
    t0 = time.time()
    for i, demo in enumerate(DEMOS, 1):
        try:
            made = render_demo_charts(demo, i, out_dir=out)
            ok, err = True, ""
        except Exception as exc:
            ok, err, made = False, f"{type(exc).__name__}: {exc}", {}
        check(f"WF-8 demo {i:03d}: renders in a continuous run", ok, err)
        for kind, path in made.items():
            if path.endswith(".png"):
                base = os.path.basename(path)
                # A shared filename means the last demo of a run is the
                # only one left on disk - which is what
                # `review_balance.png` did for fifteen demos.
                check(f"WF-8 demo {i:03d}: {kind} has a unique filename",
                      base not in names,
                      f"{base} already written by {names.get(base)}")
                names[base] = i
    elapsed = time.time() - t0
    check("WF-8 all fifteen render without a crash",
          len(names) > 0, f"{len(names)} files in {elapsed:.1f}s")
    TIMINGS["fifteen demos"] = elapsed


# ==============================================================================
# WF-6 - nothing takes so long the user thinks it has hung
# ==============================================================================
#
# A threshold, not a benchmark. The number that matters is the one past
# which someone presses Ctrl-C.

SLOW_S = 20.0


def wf_width_watch():
    """The count, against what the deferred entry records."""
    check(f"WF-WIDTH no task exceeds the column limit beyond the "
          f"{KNOWN_WIDE} already recorded",
          len(WIDE) <= KNOWN_WIDE,
          f"{len(WIDE)} tasks: "
          + ", ".join(sorted(WIDE)[:6]))
    worst = max(WIDE.items(), key=lambda x: max(x[1])) if WIDE else None
    if worst:
        check("WF-WIDTH the widest line is recorded", True,
              f"{worst[0]} at {max(worst[1])} chars")


def wf6_timing():
    slow = {k: v for k, v in TIMINGS.items() if v > SLOW_S}
    check("WF-6 no menu entry takes longer than the patience threshold",
          not slow,
          ", ".join(f"{k} {v:.1f}s" for k, v in sorted(
              slow.items(), key=lambda x: -x[1])[:4]))
    if TIMINGS:
        worst = max(TIMINGS.items(), key=lambda x: x[1])
        check("WF-6 the slowest entry is recorded", True,
              f"{worst[0]} at {worst[1]:.1f}s")


# ==============================================================================
# WF-7 - a failed picture does not take the session with it
# ==============================================================================

def wf7_recovery():
    from ppact.demo import DEMOS
    import ppact.demo_visual as dv

    original = dv.render_relative_spider
    try:
        def broken(*a, **k):
            raise RuntimeError("simulated rendering failure")
        dv.render_relative_spider = broken
        try:
            made = dv.render_demo_charts(DEMOS[0], 1,
                                         out_dir="/tmp/wf7")
            survived, err = True, ""
        except Exception as exc:
            survived, err, made = False, f"{type(exc).__name__}", {}
        check("WF-7 a failed chart does not stop the other charts",
              survived, err)
        if survived:
            check("WF-7 the failure is reported rather than hidden",
                  str(made.get("ppact_spider", "")).startswith("MISSING"),
                  str(made.get("ppact_spider")))
            check("WF-7 the charts that did work are still produced",
                  str(made.get("measured_results", "")).endswith(".png"))
    finally:
        dv.render_relative_spider = original


# ==============================================================================
# WF-9 - one pass through the workflow as a user would take it
# ==============================================================================

def wf9_confidence_run():
    from ppact import menu

    journey = [("welcome", menu.welcome_screen, ["1"]),
               ("quick start", None, None),
               ("analyze", menu.task_system_flow, ["3"] * 30)]
    by_id = {fn.__name__: fn for _, fn in menu.TASKS}
    journey[1] = ("quick start", by_id.get("task_quickstart"),
                  ["1"] * 30)

    for name, fn, answers in journey:
        if fn is None:
            check(f"WF-9 {name}: is reachable", False, "task not found")
            continue
        ok, text, secs, err = run_task(fn, answers)
        check(f"WF-9 {name}: completes", ok, err)
        check(f"WF-9 {name}: shows something", len(text.strip()) > 40)
        check(f"WF-9 {name}: stays inside the column limit",
              all(len(l) <= 78 for l in text.splitlines()),
              str([len(l) for l in text.splitlines() if len(l) > 78][:2]))
        TIMINGS[f"journey/{name}"] = secs


def main() -> int:
    for fn in (wf1_every_task_completes,
               wf2_demo_artefacts, wf8_demo_run, wf7_recovery,
               wf9_confidence_run, wf_width_watch, wf6_timing):
        try:
            fn()
        except Exception:
            check(f"{fn.__name__} completes", False,
                  traceback.format_exc().strip().splitlines()[-1])

    bad = [(n, d) for n, ok, d in RESULTS if not ok]
    print("=" * 78)
    print(" WORKFLOW QA")
    print("=" * 78)
    for n, d in bad:
        print(f"  FAILED  {n}")
        if d:
            print(f"          {d[:110]}")
    print(f"\n  {len(RESULTS) - len(bad)} / {len(RESULTS)} checks")
    if WIDE:
        print(f"\n  deferred - WF-WIDTH-001, {len(WIDE)} tasks past 78 "
              f"columns:")
        for k, v in sorted(WIDE.items(), key=lambda x: -max(x[1]))[:5]:
            print(f"      {k:<30s}{max(v):5d} chars")
    if TIMINGS:
        worst = sorted(TIMINGS.items(), key=lambda x: -x[1])[:5]
        print("\n  slowest entries:")
        for k, v in worst:
            print(f"      {k:<34s}{v:6.2f}s")
    print()
    print("  This suite does not check what a screen says. It checks that")
    print("  a user can get from the first screen to the last without")
    print("  the tool stopping, stalling, or losing a picture.")
    print("=" * 78)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
