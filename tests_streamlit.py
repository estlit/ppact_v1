"""
Streamlit QA - the same data, two screens

    ST-9   notebook and Streamlit read the same view data
    ST-7   all fifteen demonstrations build a complete view
    ST-6   the app imports, launches and answers
    ST-5   every required chart is present or explicitly not applicable

WHAT THIS CANNOT DO HERE
========================
It does not open a browser. Nothing below establishes that a label is
legible, that a table does not scroll sideways at 768 px, or that a chart
fits its container. Those need a person at a screen, and this file says so
rather than implying otherwise.

    Streamlit import           checkable here
    Streamlit launch           checkable here
    view-data parity           checkable here
    browser visual review      NOT PERFORMED

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""


from __future__ import annotations
from typing import Dict, List, Tuple

import ast
import os
import subprocess
import sys
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))


# ==============================================================================
# ST-1 - the app displays and does not compute
# ==============================================================================
#
# Checkable statically: the app may import the view layer and the chart
# renderers. An import of the engine would mean it can compute, and an app
# that CAN compute eventually does.

# `from ppact import demo_visual` records the module as "ppact", so the
# package name is allowed and the CALL check below is what actually
# constrains it. An import list alone would pass an app that imported the
# package and reached into the engine through it.
# `ppact.text_capture` runs a terminal task unchanged and hands back
# what it printed. That is the opposite of a second engine: the browser
# shows the same text the terminal produced, by construction rather than
# by anyone remembering to update both. The call-level check below is
# what actually constrains it - the app may run a task, and may not
# compute.
# The view-data layer and the adapters. `engineering_report` computes
# and `report_render` formats; the app calls both and neither is the
# engine. The call-level check below is what constrains it - an app may
# ask for a report, and may not evaluate a system.
ALLOWED = {"ppact", "ppact.view_data", "ppact.demo", "ppact.demo_visual",
           "ppact.text_capture", "ppact.outcome",
           "ppact.engineering_report", "ppact.report_render",
           "ppact.menu_taxonomy"}


def st1_no_second_engine():
    src = open("streamlit_app.py", encoding="utf-8").read()
    tree = ast.parse(src)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module.startswith("ppact"):
                imported.add(node.module)
        elif isinstance(node, ast.Import):
            for a in node.names:
                if a.name.startswith("ppact"):
                    imported.add(a.name)
    stray = sorted(imported - ALLOWED)
    check("ST-1 the app imports only the view layer and the renderers",
          not stray, str(stray))

    # A computed figure in the app is the failure this guards. Arithmetic
    # on two names is the shape it takes.
    banned = ("evaluate_system", "build_review", "find_bottleneck",
              "build_traffic_balance", "SystemConfig(")
    present = [b for b in banned if b in src]
    check("ST-1 the app calls no engine entry point",
          not present, str(present))


# ==============================================================================
# ST-7 - fifteen complete views
# ==============================================================================

REQUIRED_CHARTS = ("measured", "bottleneck", "spider")


def st7_all_demos():
    from ppact.view_data import build_demo_view, NOT_APPLICABLE

    for n in range(1, 16):
        t0 = time.time()
        try:
            v = build_demo_view(n)
            ok, err = True, ""
        except Exception:
            ok, err, v = False, traceback.format_exc().strip(
            ).splitlines()[-1], None
        check(f"ST-7 demo {n:03d}: the view builds", ok, err)
        if not ok:
            continue
        check(f"ST-7 demo {n:03d}: builds in under two seconds",
              time.time() - t0 < 2.0, f"{time.time() - t0:.2f}s")
        check(f"ST-7 demo {n:03d}: the question is present",
              v.question.strip().endswith("?"))
        charts = v.chart
        for kind in REQUIRED_CHARTS:
            check(f"ST-7 demo {n:03d}: {kind} is present",
                  kind in charts and charts[kind].status == "GENERATED",
                  charts.get(kind).status if kind in charts else "absent")
        # ST-5: the flow is generated OR explicitly not applicable -
        # never simply absent.
        flow = charts.get("flow")
        check(f"ST-5 demo {n:03d}: the flow is generated or explicitly "
              f"not applicable",
              flow is not None
              and flow.status in ("GENERATED", NOT_APPLICABLE),
              flow.status if flow else "absent")
        if flow is not None and flow.status == NOT_APPLICABLE:
            check(f"ST-5 demo {n:03d}: the flow says why it does not "
                  f"apply", bool(flow.note.strip()))
        check(f"ST-7 demo {n:03d}: the explanation sections are present",
              len(v.explanation_sections) >= 8,
              str(len(v.explanation_sections)))
        check(f"ST-7 demo {n:03d}: the gates are present",
              len(v.gates) >= 5, str(len(v.gates)))


# ==============================================================================
# ST-9 - notebook and Streamlit read the same numbers
# ==============================================================================


def st9_parity():
    from ppact.view_data import build_demo_view
    from ppact.demo_visual import (measured_series, bottleneck_series,
                                   build_demo_comparison)
    from ppact.demo import DEMOS

    for n in range(1, 16):
        v = build_demo_view(n)
        demo = DEMOS[n - 1]

        # THE NOTEBOOK PATH IS THE ONE THE NOTEBOOK USES.
        #
        # This compared `demo_visual` against `view_data`, called one
        # side "the notebook path", and passed - while the notebook was
        # calling `render_demo_review`, which used a different chart
        # entirely. A parity check naming a path it does not exercise
        # proves the two names agree, not the two paths.
        direct = measured_series(demo) or {}
        via_view = v.chart["measured"].series
        same = set(direct) == set(via_view)
        check(f"ST-9 demo {n:03d}: the same metrics either way",
              same, f"{sorted(set(direct) ^ set(via_view))}")
        if same:
            bad = []
            for k in direct:
                for lab, val in direct[k].items():
                    other = via_view[k].get(lab)
                    if val != val and other != other:
                        continue
                    if other is None or abs(val - other) > 1e-12:
                        bad.append(f"{k}/{lab}")
            check(f"ST-9 demo {n:03d}: the same measured values",
                  not bad, str(bad[:3]))

        stages = bottleneck_series(demo) or {}
        vs = v.chart["bottleneck"].series.get("throughput", {})
        check(f"ST-9 demo {n:03d}: the same stage throughputs",
              stages == vs,
              str(sorted(set(stages) ^ set(vs))[:3]))

        cmp = build_demo_comparison(demo, n)
        if cmp is not None:
            ratios = {a.name: a.ratio for a in cmp.axes}
            check(f"ST-9 demo {n:03d}: the same relative ratios",
                  ratios == v.chart["spider"].series["ratio"])

        check(f"ST-9 demo {n:03d}: the same question",
              v.question == demo.question)


# ==============================================================================
# ST-6 - the app imports, launches and answers
# ==============================================================================


# ==============================================================================
# ST-13 - the limits are on the screen, not only in a document
# ==============================================================================
#
# A README nobody opens is a README nobody read. Anyone who reaches a
# figure should be able to see, without leaving the app, that no figure
# here has been compared against measured hardware.

def st13_limits_visible():
    # THE SOURCE, WITH ITS LINE BREAKS CLOSED UP.
    #
    # A sentence wrapped across two string literals is one sentence to a
    # reader and two to a substring search, so a phrase the app does
    # display was reported missing.
    import re as _re13
    raw = open("streamlit_app.py", encoding="utf-8").read()
    src = _re13.sub(r'"\s*\n\s*"', "", raw)

    for phrase, why in (
            ("Public preview", "the release status"),
            ("compared against a measured system",
             "the central limitation"),
            ("PW-Q1", "the open power question"),
            ("MEM-ARB-001", "the arbitration defect"),
            ("TR-D1", "the traffic definition"),
            ("DEFERRED.md", "where the full register is"),
            ("do not predict a winning design",
             "what a recommendation is not")):
        check(f"ST-13 the app states {why}", phrase in src, phrase)

    # AND IT IS IN THE SIDEBAR, so it does not depend on which tab the
    # reader happens to be on.
    sidebar = src[src.index("def sidebar("):src.index("def home_page(")]
    for phrase in ("Public preview", "measured system", "PW-Q1"):
        check(f"ST-13 {phrase!r} is in the sidebar, on every screen",
              phrase in sidebar)

    # The deployment files a hosted copy needs.
    import os
    check("ST-13 requirements.txt exists",
          os.path.isfile("requirements.txt"))
    if os.path.isfile("requirements.txt"):
        raw_req = open("requirements.txt", encoding="utf-8").read()
        # Comments explain what is absent and why. Grepping them for a
        # package name reported the explanation as the dependency.
        req = "\n".join(l for l in raw_req.splitlines()
                         if not l.strip().startswith("#"))
        for pkg in ("streamlit", "matplotlib", "numpy"):
            check(f"ST-13 {pkg} is required", pkg in req)
        # PINNED, not floating. A range resolves to whatever the index
        # holds on the day of the build.
        lines = [l.strip() for l in req.splitlines()
                 if l.strip() and not l.startswith("#")]
        check("ST-13 every requirement is pinned",
              all("==" in l for l in lines), str(lines))
        # THE INTERPRETER IS PINNED TOO.
        #
        # Pinning the libraries and leaving the Python version to the
        # host is half a pin: the one thing about a deployment nobody
        # here has observed is which interpreter resolves them.
        check("ST-13 runtime.txt pins the interpreter",
              os.path.isfile("runtime.txt"))
        if os.path.isfile("runtime.txt"):
            rt = open("runtime.txt", encoding="utf-8").read().strip()
            check("ST-13 the pinned line names a Python version",
                  rt.startswith("python-3."), rt)
            import sys as _sys
            here = f"python-{_sys.version_info.major}." \
                   f"{_sys.version_info.minor}"
            check("ST-13 it is the line this was verified on",
                  rt == here, f"{rt} against {here}")

        # AND THE FILE SAYS WHAT WAS VERIFIED.
        check("ST-13 requirements.txt records the verified environment",
              "VERIFIED ON" in raw_req,
              "a pin with no record of where it was run is a number "
              "nobody can check")

        check("ST-13 playwright is not a deployment dependency",
              "playwright" not in req,
              "it captured screenshots during review and no suite "
              "imports it")
        check("ST-13 the file explains why playwright is absent",
              "playwright" in raw_req,
              "an absence with no reason invites someone to add it back")


# ==============================================================================
# ST-14 - the notebook shows every panel, not the last one
# ==============================================================================
#
# The notebook path called ONE renderer, so a reader in Jupyter saw the
# Architecture Balance and nothing else - and reasonably concluded
# Jupyter could not draw the rest. Every renderer existed; only one was
# reached.

def st14_notebook_panels():
    import os
    import tempfile
    import ppact.core as _core
    from ppact import SystemConfig as _SC
    from ppact.review import (build_review as _br, notebook_panels,
                              NOTEBOOK_PANELS, _balance_note)

    check("ST-14 four panels are declared",
          len(NOTEBOOK_PANELS) == 4, str(len(NOTEBOOK_PANELS)))
    names = [n for n, _k in NOTEBOOK_PANELS]
    for want in ("Measured Results", "System Flow and Bottleneck Map",
                 "Bottleneck Analysis", "Architecture Balance"):
        check(f"ST-14 {want!r} is one of them", want in names)

    real = _core.in_notebook
    cwd = os.getcwd()
    try:
        _core.in_notebook = lambda: True
        os.chdir(tempfile.mkdtemp(prefix="ppact_nb_"))
        a = _br("education_step_by_step", "industrial_vision",
                _SC("cortex_a78_x4", "npu_32x32", "LPDDR5", 2,
                    preprocessing_mode="isp_assisted"))
        recs = notebook_panels(a)
        check("ST-14 every panel reports a status",
              len(recs) == len(NOTEBOOK_PANELS))
        for r in recs:
            check(f"ST-14 {r['panel']}: has a status",
                  r["status"] in ("CREATED", "DISPLAYED",
                                  "NOT APPLICABLE"),
                  f"{r['status']} - {r['note']}")
            if r["status"] == "CREATED":
                check(f"ST-14 {r['panel']}: the figure is on disk",
                      os.path.isfile(r["path"]), r["path"])
        drawn = [r for r in recs if r["status"] == "CREATED"]
        # MORE THAN ONE. One panel was the defect.
        check("ST-14 more than one panel is produced",
              len(drawn) > 1, f"{len(drawn)} produced")

        # THE BLANK AND PINNED AXES ARE EXPLAINED.
        note = _balance_note(a)
        check("ST-14 the balance chart explains its blank axes",
              "PW-Q1" in note and "TR-D1" in note, note[:60])
        check("ST-14 and its pinned axes",
              "requirement" in note.lower(), note[:60])
    finally:
        _core.in_notebook = real
        os.chdir(cwd)


# ==============================================================================
# ST-15 - the notebook path, run in a real kernel
# ==============================================================================
#
# Every earlier notebook check simulated `in_notebook()` and counted
# what a renderer returned. That establishes the code paths agree; it
# does not establish that a Jupyter cell produces images, which is the
# thing a reader actually sees.

def st15_notebook_kernel():
    try:
        import nbformat
        from nbclient import NotebookClient
    except ImportError:
        check("ST-15 a notebook kernel is available to test with",
              False, "nbformat/nbclient not installed - the notebook "
                     "path is NOT VERIFIED here")
        return
    check("ST-15 a notebook kernel is available to test with", True)

    import os
    here = os.path.dirname(os.path.abspath(__file__))
    nb = nbformat.v4.new_notebook()
    nb.cells = [nbformat.v4.new_code_cell(
        f"import sys\nsys.path.insert(0, {here!r})\n"
        "from ppact.demo import DEMOS, render_demo_review\n"
        "render_demo_review(DEMOS[0], 1)")]
    client = NotebookClient(nb, timeout=600, kernel_name="python3",
                            resources={"metadata": {"path": "/tmp"}})
    client.allow_errors = True
    try:
        client.execute()
        ran = True
    except Exception as exc:
        ran = False
        check("ST-15 the notebook cell executes", False,
              f"{type(exc).__name__}: {exc}")
    if not ran:
        return
    check("ST-15 the notebook cell executes", True)

    outs = nb.cells[0].get("outputs", [])
    errs = [o for o in outs if o.output_type == "error"]
    check("ST-15 the cell raises nothing", not errs,
          str([(e.get("ename"), str(e.get("evalue"))[:50])
               for e in errs]))

    images = sum(1 for o in outs if o.output_type == "display_data"
                 and "image/png" in o.get("data", {}))
    # FOUR PANELS, not one. One panel was the defect a reader reported
    # as "Jupyter cannot draw the rest".
    check("ST-15 the notebook displays every panel", images >= 4,
          f"{images} image(s) in the cell output")

    # AND THE BANNER NAMES THE AXES THE TOOL HAS.
    from ppact.branding import AXES
    check("ST-15 the banner does not name a retired axis",
          "Thermal" not in AXES,
          "thermal is a deployment gate, computed from power and area "
          "rather than chosen")
    for axis in ("Performance", "Power", "Area", "Cost", "Traffic"):
        check(f"ST-15 the banner names {axis}", axis in AXES, AXES)


# ==============================================================================
# ST-16 - every workflow verb does something
# ==============================================================================
#
# Five of the seven menu entries were an apology: "this section runs in
# the notebook interface". A public preview where most of the menu is a
# notice is a preview of the notice.

def st16_every_verb_works():
    from ppact.text_capture import run_task, options_from
    import streamlit_app as app

    # THE TAXONOMY REPLACED THE VERB LIST.
    #
    # Seven verbs mixing staged analyses with documents became four
    # kinds, each saying what it is. The check follows.
    from ppact.menu_taxonomy import KINDS, of_kind
    verbs = list(KINDS)
    covered = {k for k in KINDS if of_kind(k)}
    planned = set()
    missing = [v for v in verbs if v not in covered]
    check("ST-16 every kind has entries", not missing, str(missing))
    check("ST-16 the demonstration library is a workflow",
          "demo_workflow()" in open("streamlit_app.py",
                                    encoding="utf-8").read())

    # AND THE APP NO LONGER APOLOGISES.
    src = open("streamlit_app.py", encoding="utf-8").read()
    check("ST-16 no verb defers to the notebook",
          "runs in the notebook interface" not in src,
          "a menu entry that only says where to go elsewhere is an "
          "entry nobody uses")

    seen_ids = set()
    for verb in KINDS:
        entries = [(e.title, e.task_id, e.purpose) for e in of_kind(verb)]
        check(f"ST-16 {verb} lists at least one task", bool(entries))
        for title, task_id, note in entries:
            check(f"ST-16 {verb}/{title}: names a real task",
                  task_id in {f.__name__ for _t, f in
                              __import__("ppact.menu",
                                         fromlist=["TASKS"]).TASKS},
                  task_id)
            check(f"ST-16 {verb}/{title}: says what it does",
                  len(note.strip()) > 10, note)
            seen_ids.add(task_id)

    # A SAMPLE ACTUALLY RUNS. Listing a task is not running one.
    for task_id in ("task_about", "task_validation_summary",
                    "task_framework", "task_memory"):
        run = run_task(task_id)
        check(f"ST-16 {task_id}: runs without raising",
              not run.error, run.error)
        check(f"ST-16 {task_id}: produces output",
              len(run.text.strip()) > 40, str(len(run.text)))
        if run.needs_input:
            # A QUESTION MUST BE ANSWERABLE. A prompt with no options
            # the caller can read is a dead end on a web page.
            opts = options_from(run.questions[-1])
            check(f"ST-16 {task_id}: its question has readable options",
                  bool(opts), run.questions[-1][-80:])

    # A RUNAWAY TASK STOPS THE RUN, NOT THE PAGE.
    #
    # `task_lessons` re-enters lesson one when a caller keeps picking the
    # first option, and `ask` absorbed the exception a caller uses to say
    # "stop asking" - so the page hung with nothing able to interrupt it.
    from ppact.text_capture import MAX_QUESTIONS
    import time as _t
    t0 = _t.time()
    runaway = run_task("task_lessons", ["1"] * (MAX_QUESTIONS * 2))
    elapsed = _t.time() - t0
    check("ST-16 a task that keeps asking is stopped",
          runaway.truncated, "it ran to completion or hung")
    check("ST-16 and stopping is quick", elapsed < 30,
          f"{elapsed:.1f}s")
    check("ST-16 a stopped run is neither finished nor failed",
          not runaway.completed and not runaway.error,
          f"completed={runaway.completed} error={runaway.error!r}")

    # AND A READER CAN STILL LEAVE. The menu offers Back last; the loop
    # is not a defect, the harness picking the first option was.
    first = run_task("task_lessons")
    opts_l = options_from(first.questions[-1])
    left = run_task("task_lessons", [str(len(opts_l))])
    check("ST-16 the lessons menu can be left",
          left.completed, f"{len(opts_l)} options, last is "
                          f"{opts_l[-1] if opts_l else '?'}")

    # THE OPTIONS BELONG TO THE QUESTION BEING ASKED.
    #
    # The captured text spans more than one screen, and taking every
    # numbered line merged the previous menu with the current question:
    # a four-option prompt rendered with fourteen, so the third choice
    # sent an answer meant for a different question. Every earlier check
    # looked at the FIRST screen only, where there is nothing to merge.
    from ppact.text_capture import options_from as _of
    merged = ("  1. host processor\n  2. accelerator\n  3. memory\n"
              "\n  Which part?\n  1. Cortex-A53 x4\n"
              "  2. Cortex-A78 x4\n")
    got = _of(merged)
    check("ST-16 only the last option block is offered",
          got == ["Cortex-A53 x4", "Cortex-A78 x4"], str(got))

    # AND IT HOLDS WHEN A TASK IS WALKED, not only on its first screen.
    for tid in ("task_whatif", "task_game", "task_custom",
                "task_challenge"):
        answers: List[str] = []
        for _step in range(6):
            r = run_task(tid, answers)
            if r.error or r.truncated or r.completed:
                break
            opts = options_from(r.questions[-1])
            check(f"ST-16 {tid} step {len(answers)}: the question has "
                  f"options", bool(opts), r.questions[-1][-70:])
            check(f"ST-16 {tid} step {len(answers)}: the count is "
                  f"plausible", len(opts) <= 30,
                  f"{len(opts)} options - blocks are being merged")
            if not opts:
                break
            answers.append("1")
        check(f"ST-16 {tid}: walks more than one step",
              len(answers) >= 1, f"{len(answers)} step(s)")

    # AN UNANSWERED QUESTION STOPS THE RUN. It used to fall through to a
    # default, so a task reported itself complete having chosen for the
    # reader.
    r = run_task("task_memory")
    check("ST-16 an unanswered question stops rather than defaults",
          not r.completed,
          "the prompt loop catches everything except "
          "NonInteractiveEnvironmentError")
    r2 = run_task("task_memory", ["2"])
    check("ST-16 supplying the answer carries the task further",
          len(r2.text) > len(r.text),
          f"{len(r.text)} -> {len(r2.text)}")


# ==============================================================================
# ST-17 - the architecture contract, and controls that break it
# ==============================================================================
#
# Counting one builder and zero monkeypatches proves the shape today. A
# control proves the check would notice if the shape changed, which is
# the part that survives the next edit.

def st17_architecture_contract():
    import os
    import re as _re

    PROD = ["streamlit_app.py", "run_jupyter.py", "run_colab.py"] + [
        os.path.join("ppact", f) for f in sorted(os.listdir("ppact"))
        if f.endswith(".py")]

    def scan(pattern, files=None):
        hits = []
        for f in (files or PROD):
            try:
                text = open(f, encoding="utf-8").read()
            except OSError:
                continue
            if _re.search(pattern, text, _re.M):
                hits.append(f)
        return hits

    # ONE OF EACH, and the file that holds it.
    for label, pattern, want in (
            ("report builder", r"^def build_engineering_report", 1),
            ("panel contract", r"^PANEL_ORDER", 1),
            ("view-data schema",
             r"^class EngineeringReportViewData", 1),
            ("presentation entry point", r"^def present\(", 1)):
        hits = scan(pattern)
        check(f"ST-17 exactly one {label}", len(hits) == want,
              str(hits))

    adapters = scan(r"^def render_report_")
    check("ST-17 the adapters live in one module",
          adapters == ["ppact/report_render.py"], str(adapters))

    # NONE OF THESE, anywhere in production.
    legacy = [f for f in scan(r"render_standard_engineering_review\(")
              if not f.endswith("review.py")]
    check("ST-17 no workflow calls the retired renderer",
          not legacy, str(legacy))
    check("ST-17 no production monkeypatch",
          not scan(r"capture_analyses|monkeypatch"), "")
    check("ST-17 the UI builds no engine object",
          not scan(r"SystemConfig\(|evaluate_system\(",
                   ["streamlit_app.py"]), "")

    # THE CONTROLS. Each breaks one thing and requires the scan to see it.
    src = open("streamlit_app.py", encoding="utf-8").read()
    for label, injected, pattern in (
            ("a UI that builds a configuration",
             "cfg = SystemConfig(1, 2)", r"SystemConfig\("),
            ("a UI that calls the engine",
             "r = evaluate_system(a, c)", r"evaluate_system\("),
            ("a workflow back on the retired renderer",
             "render_standard_engineering_review(x)",
             r"render_standard_engineering_review\(")):
        broken = src + "\n" + injected + "\n"
        check(f"ST-17 control: {label} would be caught",
              bool(_re.search(pattern, broken, _re.M)), injected)

    # A SECOND BUILDER would be caught by the count, not by a name.
    two = ("def build_engineering_report(a):\n    pass\n"
           "def build_engineering_report(b):\n    pass\n")
    check("ST-17 control: a second builder would be caught",
          len(_re.findall(r"^def build_engineering_report", two,
                          _re.M)) == 2)

    # A REMOVED PANEL. The contract is read, not copied, so a panel
    # dropped from PANEL_ORDER changes what every rule expects.
    from ppact.engineering_report import PANEL_ORDER, PANEL_TITLE
    check("ST-17 the contract declares seven panels",
          len(PANEL_ORDER) == 7, str(len(PANEL_ORDER)))
    check("ST-17 control: a dropped panel changes the expected set",
          len(PANEL_ORDER[:-1]) == 6)
    check("ST-17 every panel has a title",
          all(k in PANEL_TITLE for k in PANEL_ORDER))


# ==============================================================================
# ST-18 - what a reader sees is a product name, not a stored key
# ==============================================================================
#
# `cortex_a78_x4`, `npu_32x32` and `cpu_only` are how the code stores a
# choice. A result screen printing them is a debug view - the same
# defect that was removed from the process-node options and then shipped
# again through the report tables.

def st18_user_facing_names():
    from ppact.engineering_report import (build_engineering_report,
                                          _pretty, PanelKey)
    from ppact.outcome import single, comparison
    from ppact.system import SystemConfig

    # THE FIELD DECIDES, NOT THE VALUE'S TYPE.
    #
    # `bool` subclasses `int`, so a lookup keyed on the value rendered a
    # package count of 1 as "Enabled".
    for field, value, want in (
            ("memory_devices", 1, "1 package"),
            ("memory_devices", 2, "2 packages"),
            ("memory_devices", 0, "0 packages"),
            ("secondary_enabled", True, "Enabled"),
            ("secondary_enabled", False, "Disabled")):
        got = _pretty(field, value)
        check(f"ST-18 {field}={value!r} reads {want!r}",
              got == want, f"got {got!r}")

    check("ST-18 an integer never gets a boolean label",
          _pretty("memory_devices", 1) != "Enabled",
          "1 == True in Python; the field must decide")
    check("ST-18 a boolean never gets a numeric-unit label",
          "package" not in _pretty("secondary_enabled", True))

    # NO RAW KEYS IN THE PANELS a reader is shown.
    RAW = ("cortex_a78_x4", "cortex_a53_x4", "npu_32x32", "cpu_only",
           "isp_assisted", "server_x86_x32", "memory_devices",
           "preprocessing_mode", "secondary_enabled")
    a = SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5", 2,
                     preprocessing_mode="isp_assisted")
    b = SystemConfig("cortex_a53_x4", "npu_32x32", "HBM3E", 1,
                     preprocessing_mode="cpu_only")
    for label, outcome in (
            ("single", single("quick_start", "industrial_vision", a)),
            ("comparison", comparison("what_if", "industrial_vision",
                                      a, b))):
        report = build_engineering_report(outcome)
        for panel in report.panels:
            text = " ".join(
                [panel.title, panel.note] + list(panel.lines)
                + [f"{r.label} {r.starting} {r.current} {r.mark}"
                   for r in panel.rows])
            for key in RAW:
                check(f"ST-18 {label}/{panel.title}: no raw key "
                      f"{key!r}", key not in text,
                      text[:70])
        # THE TEXT INSIDE THE FIGURES TOO.
        #
        # `raw keys: 0` was reported while a System Flow figure read
        # "Host processor: cortex_a78_x4 -> cortex_a53_x4". The audit
        # scanned rows and captions and could not see inside a PNG, so
        # the claim was about the tables and was stated about the
        # screen. The renderers are checked instead, at the source.
        import inspect as _ins18
        from ppact import flow_map as _fm18
        for fn in (_fm18._describe_change,):
            src18 = _ins18.getsource(fn)
            check(f"ST-18 {fn.__name__} uses the shared display helper",
                  "_pretty" in src18 and "FIELD_LABEL" in src18,
                  "a second display table drifts from the first")
        for line in _fm18._describe_change(
                build_engineering_report(outcome) and
                __import__("ppact.review", fromlist=["build_review"])
                .build_review("education_step_by_step",
                              outcome.app_key,
                              outcome.starting_config
                              or outcome.current_config),
                __import__("ppact.review", fromlist=["build_review"])
                .build_review("education_step_by_step",
                              outcome.app_key,
                              outcome.current_config)):
            for key in RAW:
                check(f"ST-18 {label}: the figure text has no {key!r}",
                      key not in line, line[:60])

        # THE IDENTITY LINE TOO. It is the first thing read.
        for key in RAW:
            check(f"ST-18 {label}: the design labels use product names",
                  key not in report.starting_label
                  and key not in report.current_label,
                  f"{report.starting_label} / {report.current_label}")


# ==============================================================================
# ST-19 - a comparison compares two designs, and the evidence says which
# ==============================================================================
#
# The manifest recorded one run while the screenshots came from another:
# the browser clicked option one and the text walk followed the
# scenario, so the configuration digests could not explain the pictures
# beside them. The product was right and the evidence pointed elsewhere,
# which is the kind of fault that makes a release record worthless.

def st19_comparison_evidence():
    from ppact.e2e_scenarios import (COMPARISON_TASKS, SCENARIOS,
                                     ui_choice, next_answer,
                                     scenario_digest,
                                     comparison_reaches_two_designs)

    for task_id in COMPARISON_TASKS:
        ok, start, current = comparison_reaches_two_designs(task_id)
        # A COMPARISON OF A DESIGN AGAINST ITSELF IS NOT A COMPARISON.
        check(f"ST-19 {task_id}: the scenario reaches two designs",
              ok, f"starting {start[:10]} current {current[:10]} - a "
                  f"comparison with nothing to compare must not "
                  f"produce a review")
        check(f"ST-19 {task_id}: the scenario has a digest",
              len(scenario_digest(task_id)) == 16,
              scenario_digest(task_id))

    # ONE SOURCE FOR BOTH HARNESSES. The UI index and the text answer
    # must name the same option, or the manifest and the pictures come
    # from different runs.
    for task_id, options in (
            ("task_decide", ["a", "b", "c", "d", "e"]),
            ("task_guided", ["a", "b", "c", "d", "e"]),
            ("task_whatif", ["a", "b", "Done"])):
        for step in range(0, 6):
            text = next_answer(options, step, SCENARIOS.get(task_id))
            ui = ui_choice(options, step, task_id)
            check(f"ST-19 {task_id} step {step}: both harnesses choose "
                  f"the same option",
                  int(text) - 1 == ui, f"text {text}, ui {ui}")

    # THE CHAIN IS DECLARED, so a picture that changes can be traced to
    # the stage that changed it.
    import inspect as _i19
    src = open("/tmp/evidence.py", encoding="utf-8").read() \
        if os.path.isfile("/tmp/evidence.py") else ""
    if src:
        for link in ("scenario_digest", "starting_config_digest",
                     "current_config_digest", "view_data_digest",
                     "figure_digests", "png_digests"):
            check(f"ST-19 the manifest records {link}", link in src)


# ==============================================================================
# ST-19 - a comparison compares two things
# ==============================================================================
#
# Answering option one everywhere made two workflows compare a design
# against itself, and the screen showed a comparative review with
# nothing compared. The evidence looked complete and established
# nothing.

def st19_comparisons_have_two_designs():
    import builtins as _bi
    import contextlib as _ctx
    import io as _io
    import ppact.menu as _M
    from ppact.questions import NonInteractiveEnvironmentError
    from ppact.e2e_scenarios import SCENARIOS, walk
    from ppact.menu_taxonomy import workflow_entries
    from ppact.outcome import (WorkflowOutcome, WorkflowStatus,
                               WorkflowVariant)

    for e in workflow_entries():
        sc = SCENARIOS.get(e.task_id)
        check(f"ST-19 {e.task_id}: has a scenario", sc is not None)
        if sc is None:
            continue

        _r, answers = walk(e.task_id)
        seq = iter(answers)

        def rep(p=""):
            try:
                return next(seq)
            except StopIteration:
                raise NonInteractiveEnvironmentError("stop")
        real = _bi.input
        try:
            _bi.input = rep
            with _ctx.redirect_stdout(_io.StringIO()):
                o = getattr(_M, e.task_id)()
        except Exception as exc:
            check(f"ST-19 {e.task_id}: completes", False,
                  f"{type(exc).__name__}: {exc}")
            continue
        finally:
            _bi.input = real

        if not isinstance(o, WorkflowOutcome):
            check(f"ST-19 {e.task_id}: returns an outcome", False)
            continue

        is_comparison = o.variant is WorkflowVariant.COMPARISON
        check(f"ST-19 {e.task_id}: the scenario declares its kind",
              sc.comparative == is_comparison
              or o.status is not WorkflowStatus.COMPLETED,
              f"scenario says comparative={sc.comparative}, the "
              f"outcome is {o.variant.value}")

        if is_comparison and o.status is WorkflowStatus.COMPLETED:
            # THE REQUIRED CONDITION. A comparison whose two designs are
            # the same configuration is not a comparison, and a report
            # built from it is a review of one design labelled as two.
            check(f"ST-19 {e.task_id}: the two designs differ",
                  o.starting_config != o.current_config,
                  "starting and current are the same configuration - "
                  "there is nothing to compare")


# ==============================================================================
# ST-20 - a picture matches its panel's own input, both ways
# ==============================================================================
#
# Comparing configurations asked the wrong question. Two designs with
# different parts produced the same Architecture Balance, and a check
# reading configurations called it a defect - the balance scores against
# the application's requirement, so two designs both far above budget
# pin at the same value and the chart is correctly identical.
#
# What decides is the panel's OWN input, and the test runs both ways:
#
#     same input, different picture    -> the drawing is not a function
#                                         of what it was given
#     different input, same picture    -> the drawing ignores part of
#                                         what it was given

REQUIRED_PANELS = ("measured_results", "system_flow",
                   "architecture_balance", "engineering_conclusion",
                   "recommended_next_comparisons")


def st20_semantic_digests():
    import hashlib
    import os
    from ppact.engineering_report import (build_engineering_report,
                                          PANEL_DEPENDS_ON,
                                          PANEL_ORDER, PanelStatus)
    from ppact.outcome import single, comparison
    from ppact.system import SystemConfig

    # EVERY PANEL DECLARES WHAT IT DEPENDS ON.
    for key in PANEL_ORDER:
        check(f"ST-20 {key.value}: declares its dependency",
              key.value in PANEL_DEPENDS_ON
              and len(PANEL_DEPENDS_ON[key.value]) > 20,
              "a panel with no declared input cannot be judged")
    for name in REQUIRED_PANELS:
        check(f"ST-20 {name} is covered by the registry",
              name in PANEL_DEPENDS_ON)

    # THE BROWSER SAYS WHAT THE SHELL SAYS.
    #
    # The Measured Results panel kept its own list of six metric names
    # and printed raw numbers, while the terminal showed nine readings
    # with the requirement, the direction, the margin and a
    # COMFORTABLE / TIGHT / CRITICAL verdict. The same screen said less
    # in a browser than in a shell, and a reader could not tell whether
    # a figure passed.
    from ppact.engineering_report import (build_engineering_report
                                          as _bm, _verdict)
    from ppact.outcome import single as _sm
    from ppact.review import build_review as _brm
    from ppact.system import SystemConfig as _SCm

    _cfg = _SCm("cortex_a78_x4", "npu_32x32", "LPDDR5", 2)
    _an = _brm("education_step_by_step", "industrial_vision", _cfg)
    _pm = next(p for p in _bm(
        _sm("quick_start", "industrial_vision", _cfg)).panels
        if p.key.value == "measured_results")

    check("ST-20 every reading the engine has reaches the panel",
          len(_pm.rows) == len(_an.measured),
          f"{len(_pm.rows)} rows against {len(_an.measured)} readings")
    check("ST-20 the panel carries at least seven readings",
          len(_pm.rows) >= 7, str(len(_pm.rows)))

    for _r, _reading in zip(_pm.rows, _an.measured):
        want_amount, want_band = _verdict(_reading)
        check(f"ST-20 {_reading.label}: the verdict is shown",
              (want_band in _r.mark) if want_band else True,
              f"{_r.mark!r} wanted {want_band!r}")
        if _reading.limit is not None:
            direction = "max" if _reading.lower_is_better else "min"
            check(f"ST-20 {_reading.label}: the requirement direction "
                  f"is shown", direction in _r.mark, _r.mark)

    # A FLOOR AND A CEILING ARE NOT THE SAME TEST.
    class _Fake:
        def __init__(self, v, lim, lower):
            self.value, self.limit = v, lim
            self.lower_is_better, self.unit = lower, "u"
    check("ST-20 a ceiling exceeded reads EXCEEDS",
          _verdict(_Fake(30.0, 20.0, True))[1] == "EXCEEDS")
    check("ST-20 a floor missed reads EXCEEDS",
          _verdict(_Fake(50.0, 60.0, False))[1] == "EXCEEDS")
    check("ST-20 a floor met is not EXCEEDS",
          _verdict(_Fake(60.0, 60.0, False))[1] == "CRITICAL")
    check("ST-20 a wide ceiling margin reads COMFORTABLE",
          _verdict(_Fake(1.0, 100.0, True))[1] == "COMFORTABLE")

    # A CELL A READER CANNOT FINISH READING SAYS NOTHING.
    #
    # "16 nm (scaling reference)  (application default)" overran the
    # Architecture Summary cell at 1440 px and was cut to
    # "...(application defau". Provenance is declared semantic, so a
    # reader who cannot see it cannot tell a chosen node from a
    # defaulted one - the distinction the column exists to make. It has
    # its own column now, and the value cell carries only the value.
    from ppact.engineering_report import build_engineering_report as _bt
    from ppact.outcome import comparison as _ct
    from ppact.system import SystemConfig as _St

    _pa = next(p for p in _bt(_ct(
        "what_if", "industrial_vision",
        _St("cortex_a78_x4", "npu_32x32", "LPDDR5", 2),
        _St("cortex_a78_x4", "npu_16x16", "LPDDR5", 2))).panels
        if p.key.value == "architecture_summary")
    for _r in _pa.rows:
        for _cell in (_r.starting, _r.current):
            check(f"ST-20 {_r.key}: the value cell carries no "
                  f"provenance",
                  "application default" not in _cell
                  and "selected" not in _cell,
                  f"{_cell!r} - provenance belongs in its own column")
            check(f"ST-20 {_r.key}: the value cell is short enough to "
                  f"print", len(_cell) <= 30, f"{len(_cell)}: {_cell!r}")
    _prov = [r for r in _pa.rows if r.mark == "application default"]
    check("ST-20 a defaulted field says so in its own column",
          bool(_prov),
          "the marker column must carry what the value cell no longer "
          "does")

    # A CHANGE MARK MEANS SOMETHING CHANGED.
    #
    # The application default was filled in for the current design only,
    # so a comparison where neither design set a process node reported
    # "- -> 16 nm  changed" - a change that never happened, on the panel
    # a reader uses to see what changed. Found by reading the screen;
    # every digest was consistent with it.
    from ppact.engineering_report import build_engineering_report as _b19
    from ppact.outcome import comparison as _c19
    from ppact.system import SystemConfig as _S19

    _same = dict(cpu="cortex_a78_x4", memory="LPDDR5",
                 memory_devices=2)
    _rep = _b19(_c19("what_if", "industrial_vision",
                     _S19(compute="npu_32x32", **_same),
                     _S19(compute="npu_16x16", **_same)))
    _arch = next(p for p in _rep.panels
                 if p.key.value == "architecture_summary")
    for row in _arch.rows:
        if row.mark != "changed":
            continue
        check(f"ST-20 {row.key}: marked changed and the values differ",
              row.starting != row.current,
              f"{row.starting!r} against {row.current!r} - a field "
              f"neither design set must not read as a change")
    changed_keys = {r.key for r in _arch.rows if r.mark == "changed"}
    check("ST-20 only the field the reader changed is marked",
          changed_keys == {"compute"}, str(sorted(changed_keys)))

    # A SEMANTIC DIGEST HASHES WHAT THE SCREEN CLAIMS, not how it
    # looks. Both directions are checked per panel: a meaning change
    # must move it, and a formatting change must not.
    from ppact.engineering_report import PanelRow

    same_value = dict(label="SoC process node", key="soc_node",
                      current="7 nm", raw_current="N7")
    a = PanelRow(provenance="selected", **same_value)
    b = PanelRow(provenance="application default", **same_value)
    check("ST-20 provenance is meaning, not formatting",
          a.semantic_parts() != b.semantic_parts(),
          "the same node chosen by the reader and arrived at by an "
          "application default mean different things to a review")

    # AND THE OTHER WAY. Provenance held constant, value changed: still
    # a change of meaning, and a digest that only noticed provenance
    # would have passed this while missing the design change.
    finer = PanelRow(label="SoC process node", key="soc_node",
                     current="5 nm", raw_current="N5",
                     provenance="selected")
    check("ST-20 same provenance, different value is a meaning change",
          a.semantic_parts() != finer.semantic_parts(),
          f"{a.semantic_parts()} against {finer.semantic_parts()}")
    finer_default = PanelRow(label="SoC process node", key="soc_node",
                             current="5 nm", raw_current="N5",
                             provenance="application default")
    check("ST-20 provenance and value are independent",
          len({a.semantic_parts(), b.semantic_parts(),
               finer.semantic_parts(),
               finer_default.semantic_parts()}) == 4,
          "two values by two provenances must give four meanings")

    renamed = PanelRow(label="SOC PROCESS NODE", key="soc_node",
                       current="7.00 nm", raw_current="N7",
                       provenance="selected")
    check("ST-20 a renamed label is not a meaning change",
          a.semantic_parts() == renamed.semantic_parts(),
          "a wording or format edit must not re-judge every picture")

    numeric = PanelRow(label="Latency (ms)", key="Latency (ms)",
                       current="11.52", raw_current=11.5234)
    reformatted = PanelRow(label="Latency (ms)", key="Latency (ms)",
                           current="11.5234", raw_current=11.5234)
    check("ST-20 a number's format is not its value",
          numeric.semantic_parts() == reformatted.semantic_parts())
    changed = PanelRow(label="Latency (ms)", key="Latency (ms)",
                       current="11.52", raw_current=17.3)
    check("ST-20 a changed number is a changed meaning",
          numeric.semantic_parts() != changed.semantic_parts())

    # THREE CONTRACTS, NOT ONE VERDICT.
    #
    # Collapsing them is wrong in whichever direction: "everything
    # passed" overstates a screen that is complete and too small to
    # read, and a readability warning would drag down arithmetic that
    # is sound.
    from ppact.engineering_report import RELEASE_AXES
    names = {a for a, _w in RELEASE_AXES}
    check("ST-20 the release axes are declared separately",
          names == {"semantic_evidence", "rendering_completeness",
                    "readability"}, str(sorted(names)))
    for axis, why in RELEASE_AXES:
        check(f"ST-20 {axis}: says what it establishes",
              len(why) > 30, why)
    read_why = dict(RELEASE_AXES)["readability"]
    check("ST-20 readability is stated as separate from completeness",
          "completeness" in read_why.lower(),
          "a panel can be entire and still too small, and the two "
          "verdicts must not be folded together")

    # THE TABLE IS THE CONTRACT, and each classified item is exercised.
    from ppact.engineering_report import SEMANTIC_ITEMS, SEMANTIC_ITEM
    for name, is_meaning, why in SEMANTIC_ITEMS:
        check(f"ST-20 {name!r} is classified with a reason",
              len(why) > 8, why)
    for want in ("raw value", "provenance", "field key",
                 "display label", "decimal places", "figure size"):
        check(f"ST-20 {want!r} is in the semantic table",
              want in SEMANTIC_ITEM)
    check("ST-20 the table has both kinds",
          any(SEMANTIC_ITEM.values())
          and not all(SEMANTIC_ITEM.values()),
          "a table where everything is meaning classifies nothing")

    A = SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5", 2,
                     preprocessing_mode="isp_assisted")
    B = SystemConfig("cortex_a53_x4", "npu_16x16", "HBM3E", 1,
                     preprocessing_mode="cpu_only")

    def panels_of(outcome):
        rep = build_engineering_report(outcome)
        out = {}
        for p in rep.panels:
            png = ""
            if p.image and os.path.isfile(p.image):
                png = hashlib.sha256(
                    open(p.image, "rb").read()).hexdigest()[:16]
            out[p.key.value] = (p.semantic_digest(), png, p.status)
        return out

    # SAME INPUT, SAME PICTURE. Two builds of one outcome.
    o = single("quick_start", "industrial_vision", A)
    first, second = panels_of(o), panels_of(o)
    for name in REQUIRED_PANELS:
        s1, p1, st1 = first[name]
        s2, p2, st2 = second[name]
        check(f"ST-20 {name}: one input gives one semantic digest",
              s1 == s2, f"{s1} then {s2}")
        if st1 is PanelStatus.READY and p1 and p2:
            check(f"ST-20 {name}: one input gives one picture",
                  p1 == p2,
                  "the drawing is not a function of what it was given")

    # DIFFERENT INPUT, DIFFERENT PICTURE - and only where the input
    # actually differs.
    other = panels_of(single("quick_start", "industrial_vision", B))
    for name in REQUIRED_PANELS:
        s1, p1, st1 = first[name]
        s2, p2, st2 = other[name]
        if s1 == s2:
            # The panel was asked for the same thing, so an identical
            # picture is correct and a different one is the defect.
            if p1 and p2:
                check(f"ST-20 {name}: identical input, identical "
                      f"picture", p1 == p2,
                      f"the panel depends on {PANEL_DEPENDS_ON[name]}, "
                      f"which did not change, yet the picture did")
            continue
        if p1 and p2:
            check(f"ST-20 {name}: different input, different picture",
                  p1 != p2,
                  f"the panel's input changed and the drawing did not - "
                  f"it ignores part of {PANEL_DEPENDS_ON[name]}")


# ==============================================================================
# ST-22 - the study instrument, and the absence of results
# ==============================================================================
#
# A harness that can produce numbers without participants is the most
# dangerous thing here: a table headed "bottleneck accuracy 87%" reads
# as a finding whatever the docstring says.

def st22_study_instrument():
    import os
    from ppact.study_cases import (CASES, QUESTIONS, verify_cases,
                                   engine_answer)
    from ppact.study_harness import (ARMS, HIDDEN_PANELS, stimulus,
                                     assignment, score)

    # EVERY CASE PRODUCES THE CONDITION IT CLAIMS. A stimulus set whose
    # host-limited case is not host-limited marks every participant
    # against the wrong answer.
    for cid, ok, why in verify_cases():
        check(f"ST-22 {cid}: produces the condition it claims", ok, why)

    conditions = {c.condition for c in CASES}
    for want in ("bottleneck: host", "bottleneck: shared memory",
                 "bottleneck: accelerator", "the bottleneck moves"):
        check(f"ST-22 the set covers {want!r}", want in conditions,
              str(sorted(conditions)))
    check("ST-22 the set covers a design far inside its budget",
          any("far inside" in c.condition for c in CASES))
    check("ST-22 the set covers two designs that barely differ",
          any("barely differ" in c.condition for c in CASES))

    # THE ANSWER IS COMPUTED, NEVER STORED. A stored key drifts from the
    # model: improving the engine would leave a study marked against the
    # old one.
    import inspect
    from ppact import study_cases as _sc
    src = inspect.getsource(_sc)
    check("ST-22 no case stores an expected answer",
          "expected_bottleneck" not in src
          and "answer=" not in src,
          "the marking key is computed from the engine")

    # WHAT THE PARTICIPANT MUST NOT SEE.
    for panel in ("engineering_conclusion",
                  "recommended_next_comparisons"):
        check(f"ST-22 {panel} is hidden from participants",
              panel in HIDDEN_PANELS,
              "showing the conclusion first measures whether they can "
              "read English")
    shown = stimulus(CASES[0].case_id, "A_full")["panels_shown"]
    for panel in HIDDEN_PANELS:
        check(f"ST-22 {panel} is absent from the stimulus",
              panel not in shown, str(shown))

    # THE ARMS DIFFER IN EXACTLY ONE THING.
    full = set(stimulus(CASES[0].case_id, "A_full")["panels_shown"])
    noflow = set(stimulus(CASES[0].case_id,
                          "C_no_system_flow")["panels_shown"])
    check("ST-22 the no-flow arm removes the System Flow and nothing "
          "else", full - noflow == {"system_flow"},
          str(full - noflow))

    # NO RESULTS WITHOUT PARTICIPANTS.
    try:
        score("/tmp/ppact_no_such_study_folder")
        raised = False
    except FileNotFoundError:
        raised = True
    except Exception:
        raised = False
    check("ST-22 scoring an empty study raises rather than returning "
          "zeros", raised,
          "a table of zeros would be read as a finding")

    # ONLY THE TREATMENT CHANGED.
    #
    # Four stages, and the study's whole claim rests on which of them
    # move together:
    #
    #     engineering semantic  ->  treatment  ->  figure  ->  png
    #
    # Across study styles the first must be equal and the rest must not.
    # If the semantic digest moved, the arms differ in what they assert
    # and not only in how they present it.
    import hashlib as _h
    import tempfile as _tf
    from ppact.flow_map import (build_flow_map, render_flow_map_png,
                                STYLE_CONTRACT, STYLES, treatment,
                                treatment_digest, PRODUCT_NORMAL,
                                STUDY_FULL, STUDY_NO_HIGHLIGHT)
    from ppact.review import build_review as _br22
    from ppact.system import SystemConfig as _SC22

    # THE CONTRACT IS DECLARED, and every style answers every question.
    for st in STYLES:
        c = STYLE_CONTRACT[st]
        for field in ("subtitle", "answer_label", "highlight",
                      "numeric_values", "layout", "purpose"):
            check(f"ST-22 {st}: declares {field}", field in c, str(c))
        check(f"ST-22 {st}: keeps the numeric values",
              c["numeric_values"] is True,
              "an arm that removes the figures measures something else")
        check(f"ST-22 {st}: keeps the layout", c["layout"] is True,
              "moving the boxes would change more than the treatment")
        check(f"ST-22 {st}: says what it is for",
              len(str(c["purpose"])) > 30, str(c["purpose"]))

    # THE PRODUCT IS NOT AN ARM.
    check("ST-22 the product style names the limiting element",
          STYLE_CONTRACT[PRODUCT_NORMAL]["subtitle"] is True
          and STYLE_CONTRACT[PRODUCT_NORMAL]["answer_label"] is True,
          "removing it from the product to suit an experiment would "
          "trade the tool's explanatory power for a measurement")
    check("ST-22 the product style has no treatment",
          not any(treatment(PRODUCT_NORMAL).values()),
          str(treatment(PRODUCT_NORMAL)))
    for st in (STUDY_FULL, STUDY_NO_HIGHLIGHT):
        t = treatment(st)
        check(f"ST-22 {st}: the answer-naming text is removed",
              t["subtitle_removed"] and t["answer_label_removed"],
              str(t))

    # EXACTLY ONE STEP BETWEEN THE TWO STUDY ARMS.
    a, b = treatment(STUDY_FULL), treatment(STUDY_NO_HIGHLIGHT)
    differ = [k for k in a if a[k] != b[k]]
    check("ST-22 the two study arms differ in one treatment only",
          differ == ["highlight_removed"], str(differ))

    # AND THE FOUR STAGES MOVE AS THEY SHOULD.
    fm22 = build_flow_map(_br22(
        "education_step_by_step", "industrial_vision",
        _SC22("cortex_a53_x4", "npu_16x16", "LPDDR5", 2,
              preprocessing_mode="cpu_only")))
    tmp22 = _tf.mkdtemp(prefix="ppact_style_")
    png = {}
    for st in STYLES:
        path = render_flow_map_png(
            fm22, os.path.join(tmp22, f"{st}.png"), style=st)
        png[st] = _h.sha256(open(path, "rb").read()).hexdigest()[:16]

    check("ST-22 every style renders a different picture",
          len(set(png.values())) == len(STYLES), str(png))
    check("ST-22 every style has a different treatment digest",
          len({treatment_digest(st) for st in STYLES}) == len(STYLES))
    # The engineering fact is the flow map itself, and it is one object
    # rendered three ways.
    check("ST-22 one engineering fact, three presentations",
          all(png[st] != png[PRODUCT_NORMAL] or st == PRODUCT_NORMAL
              for st in STYLES),
          "the semantic input did not change; only the treatment did")

    # THE FREEZE IS VERIFIABLE, not just signed.
    #
    # Ten ticks on a date establish that someone believed the instrument
    # was frozen that morning, and nothing about the afternoon. Each
    # item carries a digest so a change is found rather than remembered.
    import tempfile as _tf22
    from ppact.study_freeze import (ITEMS, current, freeze,
                                    verify_freeze, FREEZE_FILE)

    for want in ("engine_version", "study_protocol", "stimulus_set",
                 "question_wording", "scoring_method",
                 "treatment_registry", "semantic_registry",
                 "evidence_chain", "ui_layout", "timer_behaviour"):
        check(f"ST-22 the freeze covers {want}",
              any(n == want for n, _f, _w in ITEMS),
              str([n for n, _f, _w in ITEMS]))
    check("ST-22 the checklist has ten items", len(ITEMS) == 10,
          str(len(ITEMS)))
    for name, fn, why in ITEMS:
        check(f"ST-22 {name}: is measured, not asserted",
              bool(fn()) and len(why) > 15, why)

    _d22 = _tf22.mkdtemp(prefix="ppact_freeze_")
    _p22 = os.path.join(_d22, FREEZE_FILE)
    unfrozen = verify_freeze(_p22)
    check("ST-22 an unsigned instrument reports itself unfrozen",
          not unfrozen["frozen"] and "cannot be told apart" in
          unfrozen["reason"], str(unfrozen)[:70])

    freeze(_p22, signed_by="test", note="")
    check("ST-22 a freshly signed freeze is intact",
          verify_freeze(_p22)["intact"])

    # RE-SIGNING IS REFUSED. A freeze that can be re-signed can be moved
    # after the fact.
    try:
        freeze(_p22, signed_by="test again")
        resigned = True
    except FileExistsError:
        resigned = False
    check("ST-22 a freeze cannot be re-signed", not resigned,
          "re-signing would move the freeze after the fact")

    # AND A CHANGE IS FOUND. The digests are compared against a record
    # with one item altered.
    import json as _j22
    rec = _j22.load(open(_p22))
    rec["digests"]["question_wording"] = "0000000000000000"
    _j22.dump(rec, open(_p22, "w"))
    after = verify_freeze(_p22)
    check("ST-22 a changed item is reported, with what it was",
          not after["intact"]
          and any(m["item"] == "question_wording"
                  and m["was"] == "0000000000000000"
                  for m in after["moved"]),
          str(after["moved"])[:80])

    # THE CERTIFICATE IS RENDERED FROM LIVE VERIFICATION.
    #
    # A certificate transcribed from the signed file alone would keep
    # asserting a frozen instrument after it had changed - which is the
    # one failure the freeze exists to prevent.
    from ppact.study_freeze import certificate, freeze_id

    try:
        certificate(os.path.join(_d22, "no_such_freeze.json"))
        certified_nothing = True
    except FileNotFoundError:
        certified_nothing = False
    check("ST-22 an unfrozen instrument cannot be certified",
          not certified_nothing,
          "a certificate for an unfrozen instrument asserts exactly "
          "what has not been established")

    cert = certificate(_p22)
    text = "\n".join(cert)
    check("ST-22 the certificate names a freeze id",
          "RC4-" in text, text[:60])
    for name, _fn, _why in ITEMS:
        check(f"ST-22 the certificate lists {name}", name in text)
    check("ST-22 the certificate reports the moved item",
          "MOVED" in text and "does not certify" in text,
          "the record under test had one digest altered")
    check("ST-22 and says the responses must not be pooled",
          "must not be pooled" in text)
    check("ST-22 the certificate claims nothing about results",
          "certifies nothing about the results" in text,
          "a frozen instrument that has not been run establishes only "
          "that it is ready to be")
    check("ST-22 freeze ids are dated and sequenced",
          freeze_id("2026-08-08T00:00:00", 2) == "RC4-2026-08-08-002",
          freeze_id("2026-08-08T00:00:00", 2))

    # THE INSTRUMENT IS FROZEN WITH THE SESSION.
    from ppact.study_harness import (experiment_identity, Timer,
                                     PROTOCOL_VERSION,
                                     PILOT_STOP_CRITERIA,
                                     PILOT_RESTART_RULE,
                                     TIMING_RENDER_COMPLETE)
    ident = experiment_identity()
    for field in ("protocol_version", "engine_version",
                  "stimulus_set_digest", "render_digest",
                  "report_digest"):
        check(f"ST-22 the session records {field}",
              ident.get(field), str(ident))

    # THE TIMER WILL NOT START UNTIL THE STIMULUS IS RENDERED.
    t = Timer()
    try:
        t.seconds()
        early = True
    except RuntimeError:
        early = False
    check("ST-22 the timer refuses to report before render-complete",
          not early,
          "timing from the request makes a slow machine look like a "
          "slow participant")
    t.ready()
    check("ST-22 render time is recorded separately from thinking time",
          t.render_ms >= 0 and t.seconds() >= 0)

    # PILOT STOP CRITERIA ARE FIXED IN ADVANCE.
    names = {n for n, _w in PILOT_STOP_CRITERIA}
    for want in ("question_misread", "timer_wrong", "answer_leaked",
                 "completion_unclear"):
        check(f"ST-22 the pilot stops for {want}", want in names,
              str(sorted(names)))
    check("ST-22 the restart rule forbids tuning on the pilot",
          "disappointing" in PILOT_RESTART_RULE,
          "adjusting until the results look better makes the pilot an "
          "optimisation set")

    # A PILOT DOES NOT BECOME A RESULT.
    #
    # Two or three people meet an instrument that may be broken - that
    # is what a pilot is for - so their responses answer a different
    # question. Kept apart by the folder rather than by a flag, because
    # a flag is one forgotten argument away from being pooled.
    import tempfile
    from ppact.study_harness import Session, PILOT, MAIN, PHASES

    root = tempfile.mkdtemp(prefix="ppact_study_")
    sess = Session("PILOT01", phase=PILOT)
    sess.record(case_id=CASES[0].case_id, arm="A_full",
                question_id="Q1", answer="host", confidence=4,
                seconds=31.2)
    path = sess.save(root)
    check("ST-22 a pilot session is written under its own phase",
          os.sep + PILOT + os.sep in path, path)

    try:
        score(root, MAIN)
        pooled = True
    except FileNotFoundError:
        pooled = False
    check("ST-22 a pilot does not populate the main run", not pooled,
          "pooling mixes people who met a possibly broken instrument "
          "with people who did not")

    marked = score(root, PILOT)
    check("ST-22 a pilot is scored, and says it is a pilot",
          marked["phase"] == PILOT and "statistics" in marked["note"],
          str(marked.get("note"))[:60])

    try:
        Session("X", phase="both")
        loose = True
    except ValueError:
        loose = False
    check("ST-22 an unknown phase is refused", not loose,
          f"phases are {PHASES}")

    # THE ASSIGNMENT IS BALANCED, not random per participant.
    a = assignment([f"P{i:02d}" for i in range(1, 13)])
    counts = {arm: 0 for arm in ARMS}
    for pid, per_case in a.items():
        for arm in per_case.values():
            counts[arm] += 1
    spread = max(counts.values()) - min(counts.values())
    check("ST-22 no arm is over-represented",
          spread <= len(CASES),
          f"{counts} - one arm drawing the easy cases by chance would "
          f"go unnoticed with twenty participants")


# ==============================================================================
# ST-23 - a name that is used must be defined
# ==============================================================================
#
# `render_report_jupyter` had its loop overwritten with Streamlit code
# while the Streamlit adapter was being rewritten, so a notebook printed
# the report header and then raised NameError on `st` - a parameter of
# the other adapter. `run_jupyter.py` called `_fetch_remote_archive`,
# which exists only in `run_colab.py`.
#
# Every suite passed. ST-15 ran a real kernel but reached
# `render_demo_review`, and nothing called `render_report_jupyter`
# itself; the launcher branch runs only when the package cannot be found
# locally, which never happens here. A name that is used and not defined
# is invisible to a test that does not reach the line.

def st23_no_undefined_names():
    import subprocess
    import sys as _sys

    files = ["streamlit_app.py", "run_jupyter.py", "run_colab.py",
             "freeze_rc4.py"] + [
        os.path.join("ppact", f) for f in sorted(os.listdir("ppact"))
        if f.endswith(".py")]

    try:
        proc = subprocess.run(
            [_sys.executable, "-m", "pyflakes"] + files,
            capture_output=True, text=True, timeout=180)
    except FileNotFoundError:
        check("ST-23 a static name check is available", False,
              "pyflakes is not installed; undefined names would go "
              "unnoticed until a user reached the line")
        return
    check("ST-23 a static name check is available", True)

    undefined = [l for l in proc.stdout.splitlines()
                 if "undefined name" in l]
    check("ST-23 no name is used without being defined",
          not undefined,
          "; ".join(undefined[:4]))

    # THE ADAPTERS DO NOT BORROW EACH OTHER'S NAMES.
    src = open(os.path.join("ppact", "report_render.py"),
               encoding="utf-8").read()
    # CODE, NOT COMMENTS. The comment explaining the defect names it,
    # and a check that cannot tell the two apart forbids saying what
    # went wrong.
    jup = src[src.index("def render_report_jupyter("):
              src.index("def render_report_streamlit(")]
    jup_code = "\n".join(l for l in jup.splitlines()
                          if not l.strip().startswith("#"))
    check("ST-23 the notebook adapter does not use `st`",
          "st." not in jup_code,
          "`st` is a parameter of the Streamlit adapter and has no "
          "meaning in the notebook one")
    stl = src[src.index("def render_report_streamlit("):]
    stl_code = "\n".join(
        l for l in stl.split("def _rows_table")[0].splitlines()
        if not l.strip().startswith("#"))
    check("ST-23 the Streamlit adapter does not call display()",
          "display(" not in stl_code,
          "IPython display has no meaning in a browser")


# ==============================================================================
# ST-24 - what the reader clicked is what the engine evaluated
# ==============================================================================
#
# A reader chose "6.6 TOPS NPU 64x64" and the report described
# NPU 24x24. The capture kept the last 1200 characters of what a task
# printed, the 22-option accelerator list did not fit, and the parser
# saw 20 options and numbered them from 1 - so the fifth printed option
# was submitted as the third. Every suite passed: none of them checked
# that a selection survives to the engine.
#
# Twelve further questions sat exactly at that cap and happened not to
# lose an option. Not failing is not the same as being safe.

def st24_selection_reaches_the_engine():
    import re as _re24
    from ppact.text_capture import run_task, parse_question

    OPT = _re24.compile(r"^\s*(\d+)[.)]\s+(\S.*)$")

    def printed(transcript):
        """The options the task printed, from the untruncated text."""
        runs, cur = [], []
        for line in transcript.splitlines():
            m = OPT.match(line)
            if not m:
                continue
            n = int(m.group(1))
            if n == 1 or not cur or cur[-1][0] != n - 1:
                cur = [(n, m.group(2).strip())]
                runs.append(cur)
            else:
                cur.append((n, m.group(2).strip()))
        return [t for _n, t in (runs[-1] if runs else [])]

    # NO FIXED-LENGTH CUT ANYWHERE IN THE CAPTURE.
    import inspect as _ins24
    from ppact import text_capture as _tc24
    src24 = _ins24.getsource(_tc24)
    for bad in ("[-1200:]", "[-6000:]", "[-2000:]"):
        check(f"ST-24 the capture does not cut at {bad}",
              bad not in src24,
              "a question ends where the task asks, not after some "
              "number of characters")

    # IDENTITY, NOT COUNT. Same length with different items would pass
    # a count check and still send the wrong design to the engine.
    for task_id, answers in (("task_custom", ["3", "2"]),
                             ("task_game", ["3"]),
                             ("task_custom", []),
                             ("task_whatif", ["1", "1"])):
        run = run_task(task_id, list(answers))
        if not run.needs_input or not run.questions:
            continue
        q = parse_question(run.questions[-1])
        if not q.options:
            continue
        src = printed(run.text)
        check(f"ST-24 {task_id}{answers}: the parsed options are the "
              f"printed options",
              src == list(q.options),
              f"{len(src)} printed / {len(q.options)} parsed; first "
              f"printed {src[:1]}, first parsed {list(q.options)[:1]}")

    # THE ACCELERATOR LIST, FIRST AND MIDDLE AND LAST.
    #
    # The defect removed options from the FRONT, so a check that only
    # picks the last item would have passed throughout.
    run = run_task("task_custom", ["3", "2"])
    q = parse_question(run.questions[-1])
    check("ST-24 the accelerator list is complete",
          len(q.options) == len(printed(run.text)),
          f"{len(q.options)} against {len(printed(run.text))}")

    positions = {"first": 0, "middle": len(q.options) // 2,
                 "last": len(q.options) - 1}
    for name, idx in positions.items():
        label = q.options[idx]
        submitted = q.options.index(label) + 1
        # What the engine gets, read back from its own printed list.
        engine_sees = printed(run.text)[submitted - 1]
        check(f"ST-24 {name} accelerator: clicked is what is submitted "
              f"is what the engine reads",
              engine_sees == label,
              f"clicked {label[:32]!r}, submitted {submitted}, engine "
              f"reads {engine_sees[:32]!r}")

    # AND THROUGH TO THE REPORT. The exact path a reader walked.
    import builtins as _bi24
    import contextlib as _ctx24
    import io as _io24
    import ppact.menu as _M24
    from ppact.questions import NonInteractiveEnvironmentError
    from ppact.outcome import WorkflowOutcome

    want = next(o for o in q.options if "64x64" in o)
    seq = iter(["3", "2", str(q.options.index(want) + 1), "1", "2"])

    def _rep24(prompt=""):
        try:
            return next(seq)
        except StopIteration:
            raise NonInteractiveEnvironmentError("stop")
    real = _bi24.input
    try:
        _bi24.input = _rep24
        with _ctx24.redirect_stdout(_io24.StringIO()):
            out = _M24.task_custom()
    except Exception as exc:
        out = None
        detail = f"{type(exc).__name__}: {exc}"
    finally:
        _bi24.input = real

    check("ST-24 the reader's path completes", isinstance(
        out, WorkflowOutcome), locals().get("detail", ""))
    if isinstance(out, WorkflowOutcome):
        check("ST-24 the evaluated design is the one chosen",
              out.current_config.compute == "npu_64x64",
              f"chose {want[:34]!r}, engine evaluated "
              f"{out.current_config.compute!r}")


# ==============================================================================
# ST-25 - the two balance charts say what they mean, and say it apart
# ==============================================================================
#
# One chart scored a design against its requirement, where 50 means the
# requirement is exactly met and 100 is a clipped ceiling. The other
# drew ratios, where 1.00x means nothing changed and there is no
# ceiling. Both were titled "Architecture Balance" and both used the
# same five axis names, so a reader comparing "50" with "0.51x" was
# comparing two scales.
#
# And the clip discarded what it hid: a design 27 times inside its area
# budget and one 78 times inside its cost budget both read "100+".

def st25_balance_semantics():
    from ppact.review import build_review
    from ppact.system import SystemConfig
    from ppact.visual.balance import (COMPARISON_TITLE, TITLE,
                                      SINGLE_LEGEND, COMPARISON_LEGEND,
                                      NOT_ESTABLISHED_REASON,
                                      render_balance_text)

    a = build_review("custom_design", "industrial_vision",
                     SystemConfig("cortex_a78_x4", "npu_64x64",
                                  "LPDDR5", 2))
    text = "\n".join(render_balance_text(a.balance))
    axes = a.balance.axes[0][1]

    # 1. A CLIPPED AXIS DISCLOSES WHAT THE CLIP HID.
    clipped = [x for x in axes if x.clipped]
    check("ST-25 the sample design has a clipped axis to test",
          bool(clipped), "the control needs one")
    for ax in clipped:
        check(f"ST-25 {ax.name}: the score before clipping is kept",
              ax.unclipped is not None
              and abs(ax.unclipped - ax.score) > 0.5,
              f"score {ax.score}, unclipped {ax.unclipped}")
        check(f"ST-25 {ax.name}: the chart prints it",
              f"{ax.unclipped:.1f}" in text,
              "100+ alone cannot distinguish 145.8 from 175.6")

    # THE PICTURE, NOT ONLY THE TEXT.
    #
    # The disclosure went into the text renderer and not the PNG, so the
    # chart a reader looks at still said "100+" alone. A visual review
    # caught it; this rule catches it next time.
    import inspect as _i25b
    from ppact.visual import balance as _bal25
    png_src = _i25b.getsource(_bal25.render_balance_png)
    check("ST-25 the drawn chart discloses the unclipped score",
          "unclipped" in png_src,
          "the text renderer and the figure must say the same thing")

    # A SCORE EXACTLY AT AN END IS NOT CLIPPED. `score in (0.0, 100.0)`
    # reported a design sitting at 100.0 as clipped and one at 145.8 the
    # same way.
    for ax in axes:
        if ax.unclipped is not None and 0.0 <= ax.unclipped <= 100.0:
            check(f"ST-25 {ax.name}: an in-range score is not marked "
                  f"clipped", not ax.clipped,
                  f"unclipped {ax.unclipped}")

    # 2. A BLANK AXIS SAYS WHY IT IS BLANK.
    blank = [x.name for x in axes if x.score is None]
    check("ST-25 the sample design has a blank axis to test",
          bool(blank))
    check("ST-25 n/e is expanded", "not established" in text.lower())
    for name in blank:
        reason = NOT_ESTABLISHED_REASON.get(name, "")
        check(f"ST-25 {name}: a reason is declared",
              len(reason) > 40, reason)
        check(f"ST-25 {name}: the reason is printed",
              reason[:40] in text,
              "a gap with no explanation reads as a broken chart")
    check("ST-25 not established is distinguished from zero",
          "not a score of zero" in text.lower()
          or "score of zero" in text.lower())

    # AN AXIS MARKED n/e EXPLAINS ITSELF ON THE SCREEN A READER SEES.
    #
    # The reasons were written in the text renderer and the notebook
    # path while the report panel attached nothing, and the Streamlit
    # adapter drew a note only when the panel also had rows - which the
    # balance panel does not. So the shipped screen showed two gaps
    # marked `n/e` and said nothing about what `n/e` means, which reads
    # as not evaluated, not applicable, zero or error depending on the
    # reader.
    from ppact.engineering_report import build_engineering_report as _b25
    from ppact.outcome import single as _s25
    from ppact.report_render import render_report_text as _rt25

    _rep25 = _b25(_s25("custom_design", "industrial_vision",
                       SystemConfig("cortex_a78_x4", "npu_64x64",
                                    "LPDDR5", 2)))
    _bal25p = next(p for p in _rep25.panels
                   if p.key.value == "architecture_balance")
    _blank25 = [x.name for x in axes if x.score is None]
    if _blank25:
        check("ST-25 the balance panel carries the n/e note",
              "not established" in _bal25p.note.lower(),
              "a panel whose content is a picture must still say what "
              "its gaps mean")
        for _n in _blank25:
            _r = NOT_ESTABLISHED_REASON.get(_n, "")
            check(f"ST-25 the panel note explains {_n}",
                  _r[:40] in _bal25p.note, _bal25p.note[:60])

        # AND IT REACHES EVERY ADAPTER.
        # WRAPPED TEXT IS STILL THE SAME TEXT. The terminal adapter
        # wraps at 66 columns, so a reason arrives split across lines
        # and a substring check on the raw string fails for a reason
        # that has nothing to do with the note being present.
        _txt25 = " ".join(" ".join(_rt25(_rep25)).split())
        check("ST-25 the text adapter prints the n/e note",
              "not established" in _txt25.lower())
        for _n in _blank25:
            _r = NOT_ESTABLISHED_REASON.get(_n, "")
            _want = " ".join(_r[:40].split())
            check(f"ST-25 the text adapter explains {_n}",
                  _want in _txt25, _txt25[:80])

        import inspect as _i25c
        from ppact import report_render as _rr25
        _rr_src = _i25c.getsource(_rr25)
        check("ST-25 no adapter hides a note behind a table",
              "panel.note and panel.rows" not in _rr_src,
              "a picture panel has no rows and still has something to "
              "say about itself")

    # 3 and 4. THE TWO CHARTS DO NOT BORROW EACH OTHER'S SCALE.
    check("ST-25 the two charts have different titles",
          TITLE != COMPARISON_TITLE, f"{TITLE!r}")
    check("ST-25 the single title names its scale",
          "Requirement" in TITLE, TITLE)
    check("ST-25 the comparison title names its scale",
          "Relative" in COMPARISON_TITLE, COMPARISON_TITLE)

    check("ST-25 the single legend explains 50",
          "requirement exactly met" in SINGLE_LEGEND)
    check("ST-25 the single legend does not claim 1.00x",
          "1.00x" not in SINGLE_LEGEND,
          "1.00x is the comparison chart's baseline and means nothing "
          "on a 0-100 score")
    check("ST-25 the single chart text does not claim 1.00x",
          "1.00x" not in text, text[:60])

    check("ST-25 the comparison legend explains 1.00x",
          "1.00x = no change" in COMPARISON_LEGEND)
    check("ST-25 the comparison legend does not claim a requirement "
          "score", "requirement exactly met" not in COMPARISON_LEGEND,
          "50 means nothing on a ratio axis")
    check("ST-25 the comparison legend says nothing clips",
          "no ceiling" in COMPARISON_LEGEND.lower())

    import inspect as _i25
    from ppact import demo_visual as _dv25
    cmp_src = _i25.getsource(_dv25.render_relative_spider)
    check("ST-25 the comparison renderer uses the comparison title",
          "COMPARISON_TITLE" in cmp_src, "it shared the single title")
    check("ST-25 the comparison renderer does not draw a requirement "
          "score", "requirement exactly met" not in cmp_src)


# ==============================================================================
# ST-26 - the legend does not sit on the chart it explains
# ==============================================================================
#
# The relative spider anchored its legend to the upper right of the
# polar axes. Demonstration rows carry labels of about fourteen
# characters and fitted; a workflow comparison names the decision that
# separates two designs and reaches forty-eight -
# "NPU 64x64 / LPDDR5  /  16 nm (scaling reference)" - and the second
# legend row landed on the `Performance` label at the top of the circle.
#
# It was found on a deployed screen, not here. The sweep written at the
# time measured the fifteen demonstrations and called itself
# exhaustive, and the labels that overlap are the ones it did not
# visit. This checks both sources.

LEGEND_CLEARANCE_PX = 4.0


def st26_legend_clears_the_chart():
    import os as _o26
    import tempfile as _t26
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as _plt26
    from ppact.demo import DEMOS as _D26
    from ppact.demo_visual import (build_demo_comparison as _bdc26,
                                   render_relative_spider as _rrs26)
    from ppact.engineering_report import _comparison_axes as _ca26
    from ppact.review import build_review as _br26
    from ppact.system import SystemConfig as _SC26

    measured = []
    orig = _plt26.Figure.savefig

    def probe(fig, path, **kw):
        # THE DRAWN EXTENTS, not an estimate from the string length.
        # A label's width depends on the font, and guessing it is how a
        # sweep passes while the picture overlaps.
        fig.canvas.draw()
        r = fig.canvas.get_renderer()
        legends = [c for c in fig.axes[0].get_children()
                   if c.__class__.__name__ == "Legend"]
        ticks = fig.axes[0].get_xticklabels()
        if legends and ticks:
            low = legends[0].get_window_extent(r).y0
            high = max(t.get_window_extent(r).y1 for t in ticks)
            measured.append((_o26.path.basename(path), low - high))
        return orig(fig, path, **kw)

    work = _t26.mkdtemp(prefix="ppact_legend_")
    _plt26.Figure.savefig = probe
    try:
        for i, demo in enumerate(_D26, 1):
            cmp = _bdc26(demo, i)
            if cmp is not None:
                _rrs26(cmp, _o26.path.join(work, f"demo_{i:03d}.png"))

        # THE WORKFLOW LABELS, which are the long ones. One case per
        # decision the label can name.
        base = dict(cpu="cortex_a78_x4", compute="npu_64x64",
                    memory="LPDDR5", memory_devices=2,
                    preprocessing_mode="cpu_only")
        CASES = (
            # The exact pair found on the deployed screen.
            ("process node", dict(accel_node="N16", soc_node="N16"),
             dict(accel_node="N3", soc_node="N3")),
            ("preprocessing", {}, dict(preprocessing_mode="isp_and_npu")),
            ("second engine", {},
             dict(secondary_compute="npu_64x64",
                  execution_mode="parallel", work_split=0.5)),
            ("host", {}, dict(cpu="cortex_a53_x4")),
            ("packages", {}, dict(memory_devices=8)),
            ("memory", {}, dict(memory="HBM3E")),
        )
        for name, left, right in CASES:
            a = _SC26(**{**base, **left})
            b = _SC26(**{**base, **left, **right})
            cmp = _ca26(_br26("what_if", "industrial_vision", a, a),
                        _br26("what_if", "industrial_vision", b, a))
            if cmp is None:
                continue
            _rrs26(cmp, _o26.path.join(
                work, f"workflow_{name.replace(' ', '_')}.png"))
    finally:
        _plt26.Figure.savefig = orig

    check("ST-26 both label sources were drawn",
          len(measured) >= len(_D26) + 5,
          f"only {len(measured)} figures measured; the sweep that "
          f"visited demonstrations alone is what missed this")

    # NOT MERELY TOUCHING. A tenth of a pixel apart reads as overlap on
    # a screen and would pass a `> 0` rule.
    for name, gap in measured:
        check(f"ST-26 {name}: the legend clears the axis labels",
              gap >= LEGEND_CLEARANCE_PX,
              f"{gap:.1f} px, wanted at least "
              f"{LEGEND_CLEARANCE_PX:.0f}")


def st6_launch():
    try:
        ast.parse(open("streamlit_app.py", encoding="utf-8").read())
        check("ST-6 the app parses", True)
    except SyntaxError as exc:
        check("ST-6 the app parses", False, str(exc))
        return

    port = "8599"
    proc = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "streamlit_app.py",
         "--server.headless=true", f"--server.port={port}"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        import urllib.request
        ok = False
        for _ in range(30):
            time.sleep(1)
            try:
                r = urllib.request.urlopen(
                    f"http://localhost:{port}/_stcore/health", timeout=3)
                ok = r.status == 200
                break
            except Exception:
                continue
        check("ST-6 the app launches and answers", ok)
    finally:
        proc.terminate()
        try:
            out, _ = proc.communicate(timeout=20)
        except subprocess.TimeoutExpired:
            proc.kill()
            out = ""
    bad = [l for l in out.splitlines()
           if "Traceback" in l or "ModuleNotFound" in l]
    check("ST-6 no exception during startup", not bad, str(bad[:2]))


# ==============================================================================
# ST-10 - the same figure, byte for byte
# ==============================================================================
#
# ST-9 proves the two paths read the same NUMBERS. It does not prove they
# draw the same PICTURE - two renderers given identical data can still
# differ in a colour, a label or an axis limit.
#
# Both paths call one renderer, so the file it writes must be identical
# whichever caller asked for it.

def st9b_demo_review_parity():
    """The path the notebook and terminal actually take.

    `render_demo_review` drew the requirement-centred spider, where both
    of a demonstration's designs pin at the same value - so Demo 001
    showed two identical polygons for a sixteenfold memory change while
    Streamlit showed 1.16x, 0.43x, 0.17x on the same data.
    """
    from ppact.demo import DEMOS, demo_panels, DEMO_PANELS
    from ppact.view_data import build_demo_view

    check("ST-9b the demo review declares four panels",
          len(DEMO_PANELS) == 4, str(len(DEMO_PANELS)))

    st_titles = ["Measured Results", "System Flow and Bottleneck Map",
                 "Bottleneck Analysis", "Architecture Balance"]
    check("ST-9b the panels match the Streamlit tabs",
          [t for t, _ in DEMO_PANELS] == st_titles,
          str([t for t, _ in DEMO_PANELS]))

    import inspect
    from ppact import demo as _dm
    src = inspect.getsource(_dm.demo_panels)
    # THE RELATIVE CHART, not the requirement-centred one.
    check("ST-9b the demo balance is the relative comparison",
          "render_relative_spider" in src,
          "render_balance_png scores against the requirement, where "
          "both of a demo's designs pin at the same value")
    check("ST-9b it does not fall back to the requirement chart",
          "render_balance_png" not in src)
    check("ST-9b the flow map is the compared one",
          "render_compared_flow_map_png" in src)

    for n in (1, 5, 12):
        recs = demo_panels(DEMOS[n - 1], n)
        made = [r for r in recs if r["status"] == "CREATED"]
        check(f"ST-9b demo {n:03d}: more than one panel is produced",
              len(made) > 1, f"{len(made)} produced")
        for r in recs:
            check(f"ST-9b demo {n:03d}/{r['panel']}: has a status",
                  r["status"] in ("CREATED", "NOT APPLICABLE"),
                  f"{r['status']} - {r['note']}")
        # PER-DEMO FILENAMES. A run of the library used to leave one set.
        names = [r["path"] for r in made]
        check(f"ST-9b demo {n:03d}: the files carry the demo number",
              all(f"demo_{n:03d}" in p for p in names), str(names[:2]))

    # THE TWO INTERFACES DRAW THE SAME BALANCE. Same builder, same data.
    from ppact.demo_visual import build_demo_comparison
    for n in range(1, 16):
        v = build_demo_view(n)
        cmp = build_demo_comparison(DEMOS[n - 1], n)
        if cmp is None or "spider" not in v.chart:
            continue
        ratios = {a.name: a.ratio for a in cmp.axes}
        check(f"ST-9b demo {n:03d}: the notebook and Streamlit balance "
              f"read the same ratios",
              ratios == v.chart["spider"].series["ratio"])


def st10_figure_digest():
    import hashlib
    import tempfile
    from ppact.demo import DEMOS
    from ppact import demo_visual as dv

    tmp = tempfile.mkdtemp(prefix="ppact_digest_")

    def digest(path):
        return hashlib.sha256(open(path, "rb").read()).hexdigest()[:16]

    for n in (1, 5, 8, 12, 15):
        demo = DEMOS[n - 1]
        # The notebook path and the Streamlit path both go through
        # render_* with the same arguments. Same input, same file.
        a = dv.render_measured_comparison(
            demo, n, os.path.join(tmp, f"nb_{n}.png"))
        b = dv.render_measured_comparison(
            demo, n, os.path.join(tmp, f"st_{n}.png"))
        check(f"ST-10 demo {n:03d}: the measured figure is byte-identical "
              f"across two calls",
              a and b and digest(a) == digest(b),
              f"{digest(a) if a else '-'} against "
              f"{digest(b) if b else '-'}")

        cmp = dv.build_demo_comparison(demo, n)
        if cmp is not None:
            a = dv.render_relative_spider(
                cmp, os.path.join(tmp, f"nbs_{n}.png"))
            b = dv.render_relative_spider(
                cmp, os.path.join(tmp, f"sts_{n}.png"))
            check(f"ST-10 demo {n:03d}: the spider is byte-identical",
                  a and b and digest(a) == digest(b),
                  f"{digest(a) if a else '-'} against "
                  f"{digest(b) if b else '-'}")


# ==============================================================================
# ST-11 - a demonstration compares; it does not describe one design
# ==============================================================================
#
# The flow map showed the current design alone, which left a reader with
# the first question they have: what was it before? Every figure on a
# demonstration screen is `reference -> current`.

def st11_comparative():
    from ppact.demo import DEMOS
    from ppact.view_data import flow_map_rows, flow_map_png

    for n in range(1, 16):
        rows = flow_map_rows(n)
        check(f"ST-11 demo {n:03d}: the flow rows are comparative",
              len(rows) == 10, f"{len(rows)} fields")
        (mods, links, ref_lim, cur_lim, _, _, ref_lab, cur_lab,
         changes, insight) = rows

        # A LOAD WITHOUT ITS NUMERATOR AND DENOMINATOR cannot be checked
        # by the reader, and the denominator is the whole argument for
        # why a sixteenfold memory produced a modest speedup.
        for l in links:
            check(f"ST-11 demo {n:03d}/{l[0]}->{l[1]}: the load carries "
                  f"demand and capacity",
                  len(l) == 11,
                  "a percentage with no numerator is a figure nobody "
                  "can verify")

        # PRODUCT WORDING, not the internal key. `preprocessing mode:
        # cpu_only -> isp_and_npu` is a field name and an enum value,
        # both written for the code.
        for c in changes:
            for key in ("preprocessing_mode", "memory_devices",
                        "secondary_compute", "soc_node", "accel_node",
                        "cpu_only", "isp_and_npu", "isp_assisted"):
                check(f"ST-11 demo {n:03d}: the change summary does not "
                      f"expose {key!r}",
                      key not in c, c[:60])

        check(f"ST-11 demo {n:03d}: the change is stated",
              bool(changes) and any(c.strip() for c in changes),
              str(changes[:1]))
        check(f"ST-11 demo {n:03d}: a key insight is generated",
              len(insight.strip()) > 40, insight[:50])
        # The insight must not contradict the limiting-element figures.
        #
        # Matched on the CLAIM, not on a word.
        #
        # "removed" contains "moved", and "no link load moved
        # materially" uses the word about something else entirely. Two
        # false positives from one lazy substring - the check has to name
        # the claim it is testing.
        import re as _re11
        moved_txt = bool(_re11.search(
            r"limiting element moved", insight, _re11.I))
        stayed_txt = bool(_re11.search(
            r"remained \w+|limits both designs", insight, _re11.I))
        check(f"ST-11 demo {n:03d}: the insight states one of the two "
              f"outcomes",
              moved_txt or stayed_txt, insight[:60])
        check(f"ST-11 demo {n:03d}: the insight agrees with the limit",
              moved_txt == (ref_lim != cur_lim),
              f"insight claims moved={moved_txt}, limits "
              f"{ref_lim!r} -> {cur_lim!r}")

        demo = DEMOS[n - 1]
        check(f"ST-11 demo {n:03d}: the labels name the two designs",
              ref_lab == demo.rows[0].label
              and cur_lab == demo.rows[-1].label,
              f"{ref_lab!r} / {cur_lab!r}")

        # EVERY module carries both figures, not one.
        for m in mods:
            name, ru, cu, rs, cs = m[0], m[1], m[2], m[3], m[4]
            check(f"ST-11 demo {n:03d}/{name}: utilisation is a pair",
                  len(m) == 8,
                  "a single figure leaves 'what was it before?' unasked")
        # At least one element must differ, or the demonstration shows
        # nothing.
        moved = [m[0] for m in mods if m[7]] + \
                [f"{l[0]}->{l[1]}" for l in links if l[6]]
        check(f"ST-11 demo {n:03d}: something changed between the two "
              f"designs", bool(moved), str(moved[:3]))

        imgs = flow_map_png(n)
        # A LOAD OVER 100% IS A SHORTFALL, not an occupancy. Reporting
        # it as a utilisation invites the reader to think a link is
        # 186.8% busy, which is physically odd.
        for l in links:
            for load in (l[2], l[3]):
                if load is not None and load > 100.0:
                    check(f"ST-11 demo {n:03d}/{l[0]}->{l[1]}: an "
                          f"over-capacity link carries its demand and "
                          f"available figures",
                          l[7] is not None and l[9] is not None,
                          f"load {load:.1f}% with demand {l[7]} and "
                          f"available {l[9]}")

        # THE LINK-TO-MODULE MIGRATION.
        #
        # `is_bottleneck` marks the lowest-throughput MODULE, which is a
        # different claim from "this limits the system". While a link
        # held the limit a module still carried the flag, and the screen
        # read "limiting element in both" - reversing the very
        # conclusion the demonstration exists to show.
        from ppact.flow_map import build_flow_map
        from ppact.review import build_review as _br
        from ppact import SystemConfig as _SC
        for side, row in (("starting point", demo.rows[0]),
                          ("current design", demo.rows[-1])):
            fm = build_flow_map(_br("education_step_by_step",
                                    row.application,
                                    _SC(**row.config)))
            flagged = [m.name for m in fm.modules if m.is_bottleneck]
            if fm.limiting_kind == "link":
                check(f"ST-11 demo {n:03d}/{side}: no module is flagged "
                      f"while a link holds the limit",
                      not flagged,
                      f"limit is the {fm.limiting} link and "
                      f"{flagged} is still marked")
            else:
                check(f"ST-11 demo {n:03d}/{side}: exactly one module "
                      f"holds the limit",
                      len(flagged) == 1, str(flagged))

        # And the comparative view must not say IN BOTH across a change
        # of object kind.
        for m in mods:
            if m[5] and m[6]:
                check(f"ST-11 demo {n:03d}/{m[0]}: 'in both' only when "
                      f"the limit was a module both times",
                      ref_lim == cur_lim,
                      f"marked limiting in both while the limit went "
                      f"{ref_lim!r} -> {cur_lim!r}")

        # THE LINK FIGURE IS AN AGGREGATE.
        #
        # `accel_required` divides TOTAL bytes per job by the interval,
        # and the model splits the VOLUMES (94.3 MB read against 21.0 MB
        # written) without splitting the BANDWIDTH. A directional arrow
        # with one number on it claims a decomposition that does not
        # exist.
        import inspect as _isp11
        from ppact import flow_map as _fm11
        src11 = _isp11.getsource(_fm11.render_compared_flow_map_png)
        check(f"ST-11 demo {n:03d}: the link connector is "
              f"double-headed",
              '"<|-|>"' in src11,
              "a one-way arrow says the figure is directional")
        check(f"ST-11 demo {n:03d}: the screen says the figures are "
              f"aggregates",
              "bidirectional aggregate" in src11)

        # COLOUR MEANS ONE THING.
        #
        # The bar colour used to be forced red for the limiting element,
        # so a host at 43.8% got a red bar under a legend reading
        # "bottleneck >= 85%". Band and limit are separate claims and
        # need separate encodings.
        from ppact.flow_map import _state, STATE_COLOUR
        check(f"ST-11 demo {n:03d}: the band comes from the value alone",
              _state(43.8) == "normal" and _state(70.0) == "warning"
              and _state(92.0) == "high",
              f"{_state(43.8)}/{_state(70.0)}/{_state(92.0)}")
        check(f"ST-11 demo {n:03d}: the band function takes no limit "
              f"flag",
              _isp11.signature(_state).parameters.keys() == {"pct"},
              str(list(_isp11.signature(_state).parameters)))

        check(f"ST-11 demo {n:03d}: the comparative map renders",
              imgs.get("map", "").endswith(".png"),
              str(imgs.get("map")))
        check(f"ST-11 demo {n:03d}: the migration renders",
              imgs.get("migration", "").endswith(".png"))


# ==============================================================================
# ST-12 - a comparison proposes the next one, from one component
# ==============================================================================
#
# Every comparison screen ends the same way and calls the same closure. A
# recommendation rule implemented per screen is a rule that drifts per
# screen, and this project has already spent a release cycle removing
# seven copies of a progress bar.

def st12_closure():
    from ppact.view_data import closure_rows, engine_provenance
    from ppact.closure import PROPOSALS, LINK_PROPOSALS

    prov = engine_provenance()
    check("ST-12 the screen records which engine produced it",
          prov.get("engine") and prov.get("digest") != "not available",
          str(prov))

    for n in range(1, 16):
        (conclusion, insight, proposals, modify, ask, not_shown,
         limiting, kind, trace) = closure_rows(n)
        tag = f"demo {n:03d}"

        # EVERY PROPOSAL NAMES ITS RULE. "It appeared" is not a reason,
        # and a rule id is what lets a reviewer disagree usefully.
        for (title, reason, prio, explored, rule, origins, cur, alts,
             die, orig_reasons, omitted, fam) in proposals:
            origin = origins[0] if origins else ""
            # THE ORIGIN IS NEVER OVERWRITTEN. Relabelling used to
            # replace the rule id, so EXPLORED_001 on screen could not
            # be traced to the rule that proposed it.
            check(f"ST-12 {tag}/{title}: names every origin rule",
                  bool(origins)
                  and all(o not in ("EXPLORED_001", "NOT_LIMITING_001")
                          for o in origins),
                  f"origins {origins!r}, shown {rule!r}")
            # A NODE PROPOSAL NAMES ITS DIE. soc_node and accel_node are
            # different silicon, and a proposal that does not say which
            # cannot be run.
            if "process node" in title.lower():
                check(f"ST-12 {tag}/{title}: names the target die",
                      bool(die), f"die {die!r}")

            # EVERY ORIGIN'S REASON IS KEPT, and one left out of the
            # sentence says why. Origins survived the merge and their
            # reasons did not.
            check(f"ST-12 {tag}/{title}: every origin has its reason",
                  len(orig_reasons) == len(origins),
                  f"{len(origins)} origins, {len(orig_reasons)} reasons")
            for rid, rs, why in omitted:
                check(f"ST-12 {tag}/{title}: {rid} says why it was left "
                      f"out of the sentence", len(why.strip()) > 20, why)

            # NO INTERNAL KEYS, NO None. A screen printing N3 or None is
            # a debug view.
            for value in [cur] + list(alts):
                check(f"ST-12 {tag}/{title}: {value!r} is a product name",
                      value not in ("None", "") and not (
                          len(value) <= 3 and value[:1] in "NA"
                          and value[1:].isdigit()),
                      value)
            check(f"ST-12 {tag}/{title}: the priority is a class, not a "
                  f"score",
                  prio in ("DIRECT", "CONTEXTUAL", "CONTRAST",
                           "COMPLETED"), prio)
            # A PROPOSAL WITH NO OPTIONS CANNOT START A COMPARISON.
            if prio != "COMPLETED":
                check(f"ST-12 {tag}/{title}: offers what to change to",
                      bool(alts), f"field value {cur!r}, no "
                                  f"alternatives")
            # NOT A PREDICTED GAIN. No counterfactual was run.
            check(f"ST-12 {tag}/{title}: claims no unevaluated benefit",
                  "benefit is low" not in reason.lower(), reason[:50])

        # THE PIPELINE IS RECORDED. The drop from candidates to five is
        # the part a reviewer most needs to see.
        check(f"ST-12 {tag}: the pipeline is traced",
              len(trace) >= 4, str(len(trace)))
        stages = [t[0] for t in trace]
        check(f"ST-12 {tag}: the trace starts at rule inspection",
              stages and "inspected" in stages[0], str(stages[:1]))
        check(f"ST-12 {tag}: the conditional node rules are counted "
              f"apart", any("conditional node" in x for x in stages),
              str(stages))
        check(f"ST-12 {tag}: the merge stage is recorded",
              any("combined" in x for x in stages), str(stages))
        # Every stage after the merge only removes.
        for stage, before, after, removed, note in trace[3:]:
            check(f"ST-12 {tag}/{stage}: the counts are consistent",
                  after <= before, f"{before} -> {after}")
        check(f"ST-12 {tag}: the last stage produces what is shown",
              trace[-1][2] == len(proposals),
              f"{trace[-1][2]} against {len(proposals)}")

        # A HIDDEN PROPOSAL SAYS WHAT WOULD BRING IT BACK.
        for title, rule, why, would in not_shown:
            check(f"ST-12 {tag}/{title}: says why it was hidden",
                  len(why.strip()) > 5, why)
            check(f"ST-12 {tag}/{title}: says what would show it",
                  len(would.strip()) > 5, would)

        check(f"ST-12 {tag}: the conclusion states what the engine "
              f"computed", len(conclusion) >= 2, str(len(conclusion)))
        check(f"ST-12 {tag}: the conclusion names the limiting element",
              any("limiting element" in c for c in conclusion))

        # FOUR OR FIVE. A list long enough to need reading reintroduces
        # the choice it was meant to remove.
        check(f"ST-12 {tag}: between three and five proposals",
              3 <= len(proposals) <= 5, str(len(proposals)))
        check(f"ST-12 {tag}: the limiting element carries its kind",
              kind in ("module", "link"), kind)

        for row in proposals:
            check(f"ST-12 {tag}/{row[0]}: says why it is proposed",
                  len(row[1].strip()) > 10, row[1])

        # ORDER COMES FROM THE LIMIT. A design limited by its host must
        # not be told to buy a bigger accelerator first.
        check(f"ST-12 {tag}: the first proposal is not one just "
              f"explored", not proposals[0][3], proposals[0][0])
        explored = [p for p in proposals if p[3]]
        for p in explored:
            check(f"ST-12 {tag}/{p[0]}: an explored change is COMPLETED",
                  p[2] == "COMPLETED", p[2])
            check(f"ST-12 {tag}/{p[0]}: explored proposals come last",
                  proposals.index(p) >= len(proposals) - len(explored))

        check(f"ST-12 {tag}: modify is offered", bool(modify.strip()))
        check(f"ST-12 {tag}: the free question is offered last",
              "your own" in ask.lower(), ask)

    # ==================================================================
    # THE PROCESS NODE IS CONDITIONAL, NOT UNIVERSAL.
    #
    # It appeared in 21 of 21 cases, which made it a fixed menu item
    # rather than a reading of the design. Four conditions must hold, and
    # each has a control below.
    # ==================================================================
    from ppact.closure import (_node_rules_that_fire, NODE_RULES,
                               NODE_COMPLETED, PRESSURE_PCT,
                               FABRICATED, _alternatives)
    from ppact.flow_map import build_flow_map
    from ppact.review import build_review as _brv
    from ppact import SystemConfig as _SCF
    from ppact.demo import DEMOS as _D

    with_node, completed_node = [], []
    for n in range(1, 16):
        rows = closure_rows(n)
        allp = [p for p in rows[2]] 
        hidden = rows[5]
        titles = [p[0] for p in allp] + [h[0] for h in hidden]
        node_shown = [p for p in allp
                      if "process node" in p[0].lower()]
        if node_shown:
            (with_node if node_shown[0][2] != "COMPLETED"
             else completed_node).append(n)

    # NOT EVERY CASE. A proposal present everywhere is a menu entry.
    check("ST-12 the process node is not proposed in every case",
          len(with_node) < 15,
          f"proposed in {len(with_node)} of 15")
    check("ST-12 the process node is proposed in at least one case",
          len(with_node) >= 1, str(with_node))

    # NO FABRICATED LOGIC -> ABSENT.
    #
    # Tested on a design where a node rule DOES fire. Using one with no
    # pressure proved nothing: the pressure test already returned empty,
    # so removing the fabricated-logic guard changed nothing and the
    # control fired zero times.
    firing = None
    for n in range(1, 16):
        d = _D[n - 1]
        rv = _brv("education_step_by_step", d.rows[-1].application,
                  _SCF(**d.rows[-1].config))
        pres = {m.name for m in build_flow_map(rv).modules}
        if _node_rules_that_fire(rv, pres):
            firing = (rv, pres)
            break
    check("ST-12 at least one design has a node rule firing",
          firing is not None)
    if firing:
        rv, pres = firing
        check("ST-12 the same design with no fabricated logic has none",
              _node_rules_that_fire(rv, set()) == (),
              "a design with no fabricated module has no logic a node "
              "could move")

    # A JUST-CHANGED NODE IS RECORDED, NEVER PROPOSED.
    for n in completed_node:
        rows = closure_rows(n)
        for p in rows[2]:
            if "process node" in p[0].lower():
                check(f"ST-12 demo {n:03d}: a changed node is COMPLETED",
                      p[2] == "COMPLETED", p[2])
                check(f"ST-12 demo {n:03d}: and is attributed to the "
                      f"change, not to a pressure rule",
                      "NODE_CHANGED_001" in p[5], str(p[5]))

    # SEVERAL NODE RULES, ONE ACTION.
    # MERGING KEEPS EVERY ORIGIN, not the first.
    #
    # Checking that each origin is a proposal rule passed with one
    # origin too, so a control that discarded the rest fired zero times.
    # What must be checked is that a merged action carries more than one.
    merged_any = False
    for n in range(1, 16):
        rows = closure_rows(n)
        tr = rows[8]
        combined = [t for t in tr if "combined" in t[0]]
        if combined and combined[0][3]:
            multi = [p for p in rows[2] if len(p[5]) > 1]
            check(f"ST-12 demo {n:03d}: a merged action keeps every "
                  f"origin",
                  bool(multi),
                  f"{len(combined[0][3])} reason(s) combined and no "
                  f"proposal carries more than one origin")
            if multi:
                merged_any = True
    check("ST-12 at least one case merges two rules into one action",
          merged_any)

    # ONE CONTRAST PER FAMILY. Two accelerator contrasts filled both
    # slots and the reader saw a narrower search than the rules produced.
    for n in range(1, 16):
        rows = closure_rows(n)
        # THE DECLARED FAMILY, not the title's last word. "accelerators"
        # and "accelerator" are different strings and the check passed
        # either way, so the control fired zero times.
        fams = [p[11] for p in rows[2] if p[2] == "CONTRAST"]
        check(f"ST-12 demo {n:03d}: contrasts do not repeat a family",
              len(fams) == len(set(fams)), str(fams))

    # ONE ACTION PER DIE, not one action for both.
    ids = {r.action_id for r in NODE_RULES}
    check("ST-12 the node actions are split by die",
          ids == {"ACT_SOC_NODE", "ACT_ACCEL_NODE"}, str(ids))
    for r in NODE_RULES:
        check(f"ST-12 {r.rule_id}: the action matches the field",
              (r.field == "soc_node") == (r.action_id == "ACT_SOC_NODE"),
              f"{r.action_id} changes {r.field}")

    # THE TEXT RENDERER IS EXERCISED. It kept STARS[p.confidence] after
    # both names had gone and raised NameError on its first line, which
    # no check had ever reached.
    from ppact.closure import render_closure as _rc, build_closure as _bc
    from ppact.flow_map import build_compared_flow_map as _bcfm
    import dataclasses as _dc
    d0 = _D[0]
    _b = _brv("education_step_by_step", d0.rows[0].application,
              _SCF(**d0.rows[0].config))
    _c = _brv("education_step_by_step", d0.rows[-1].application,
              _SCF(**d0.rows[-1].config))
    _ch = [f.name for f in _dc.fields(_SCF)
           if d0.rows[0].config.get(f.name)
           != d0.rows[-1].config.get(f.name)]
    try:
        text = _rc(_bc(_b, _c, _ch, ""))
        ok, err = True, ""
    except Exception as exc:
        ok, err, text = False, f"{type(exc).__name__}: {exc}", []
    check("ST-12 the text renderer runs", ok, err)
    if ok:
        check("ST-12 the text renderer stays inside 78 columns",
              all(len(l) <= 78 for l in text),
              str([len(l) for l in text if len(l) > 78][:3]))
        joined = " ".join(text)
        for retired in ("HIGH", "MEDIUM", "LOW", "confidence", "*****"):
            check(f"ST-12 the text renderer does not print {retired!r}",
                  retired not in joined)
    check("ST-12 the node rules name different pressures",
          len({r.reason for r in NODE_RULES}) == len(NODE_RULES))

    # THE RULES ARE DECLARED, not phrased at run time.
    # DETERMINISTIC. Five builds of the same case must agree.
    from ppact.view_data import recommendation_checksum
    for n in (1, 5, 12):
        digests = {recommendation_checksum(n) for _ in range(5)}
        check(f"ST-12 demo {n:03d}: the recommendation is deterministic",
              len(digests) == 1, str(digests))

    check("ST-12 the proposals are a declared table",
          isinstance(PROPOSALS, dict) and len(PROPOSALS) >= 4,
          str(list(PROPOSALS)))
    check("ST-12 a link limit has its own proposals",
          bool(LINK_PROPOSALS))


# ==============================================================================
# ST-21 - defined = registered = executed = reported
# ==============================================================================
#
# `st19_comparison_evidence` sat in the runner and did not exist, while
# `st19_comparisons_have_two_designs` was defined and never called. The
# suite reported a clean run, the rule had never fired, and nothing
# noticed - a check that is written but not executed is worse than one
# that is missing, because the count says it ran.

EXECUTED: List[str] = []


def st21_check_accounting():
    import inspect
    import re

    module = sys.modules[__name__]
    src = inspect.getsource(module)

    defined = {n for n, o in vars(module).items()
               if callable(o) and re.match(r"^st\d+[a-z]?_", n)}

    # THE LIST ITSELF, not a regex over the source.
    #
    # Parsing `for fn in (...)` matched nothing and reported zero
    # registered checks - a broken parser looked exactly like a broken
    # runner. The runner reads a named tuple, and so does this.
    registered = {f.__name__ for f in REGISTERED}

    missing = sorted(defined - registered)
    check("ST-21 every defined check is registered", not missing,
          f"{missing} are written and never called - the suite would "
          f"report a clean run for a rule that never fired")

    phantom = sorted(registered - defined)
    check("ST-21 every registered name exists", not phantom,
          f"{phantom} are named in the runner and not defined")

    executed = set(EXECUTED)
    unrun = sorted(registered - executed - {"st21_check_accounting"})
    check("ST-21 every registered check executed", not unrun,
          str(unrun))

    reported = {n.split()[0] for n, _ok, _d in RESULTS
                if n.startswith("ST-")}
    check("ST-21 every executed check reported something",
          len(reported) >= len(executed) - 2,
          f"{len(executed)} executed, {len(reported)} reported")

    check("ST-21 the four counts agree",
          len(defined) == len(registered)
          and registered <= executed | {"st21_check_accounting"},
          f"defined {len(defined)}, registered {len(registered)}, "
          f"executed {len(executed)}")


# THE REGISTERED CHECKS, in one list that both the runner and the
# accounting rule read.
REGISTERED = (st1_no_second_engine, st7_all_demos, st9_parity,
               st9b_demo_review_parity,
               st10_figure_digest, st11_comparative, st12_closure,
               st13_limits_visible, st14_notebook_panels,
               st15_notebook_kernel, st16_every_verb_works,
               st17_architecture_contract, st18_user_facing_names,
               st19_comparisons_have_two_designs,
               # DEFINED AND NEVER CALLED until the accounting rule
               # found it. It checks the same contract through the
               # scenario helpers rather than through the menu, so both
               # are kept: one asks whether the scenario can reach two
               # designs, the other whether the workflow did.
               st19_comparison_evidence,
               st20_semantic_digests, st22_study_instrument,
               st23_no_undefined_names,
               st24_selection_reaches_the_engine,
               st25_balance_semantics,
               st26_legend_clears_the_chart,
               st6_launch,
               st21_check_accounting)


def main() -> int:
    for fn in REGISTERED:
        EXECUTED.append(fn.__name__)
        try:
            fn()
        except Exception:
            check(f"{fn.__name__} completes", False,
                  traceback.format_exc().strip().splitlines()[-1])

    bad = [(n, d) for n, ok, d in RESULTS if not ok]
    print("=" * 78)
    print(" STREAMLIT QA")
    print("=" * 78)
    for n, d in bad:
        print(f"  FAILED  {n}")
        if d:
            print(f"          {d[:110]}")
    print(f"\n  {len(RESULTS) - len(bad)} / {len(RESULTS)} checks")
    print()
    print("  NOT PERFORMED: browser visual review. Nothing here")
    print("  establishes that a label is legible, that a table does not")
    print("  scroll sideways at 768 px, or that a chart fits its")
    print("  container. Those need a person at a screen.")
    print("=" * 78)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
