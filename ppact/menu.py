"""
================================================================================
 Semiconductor School - AI 반도체 기술기획
 Shared interactive menu
================================================================================
 One menu, used by both launchers:

     run_jupyter.py   Jupyter Notebook
     run_colab.py     Google Colab

 It lives inside the package on purpose. A launcher that had to import a
 sibling file would break the moment the files were extracted flat, or the
 kernel's working directory differed from the script's. The only thing a
 launcher now needs beside it is the ppact folder itself.

 In a notebook the cell ends when the task ends, so the menu does not loop -
 running the cell again is the natural repeat. main_menu(loop=True) restores
 looping for a terminal session.

 Author: Roger Kim
 Copyright (c) 2026 Roger Kim & EdgeChipLab
================================================================================
"""

from __future__ import annotations

import os

from .core import in_notebook
from .application import APPLICATION_LIBRARY
from .compute import COMPUTE_LIBRARY
from .cpu import CPU_LIBRARY
from .memory import MEMORY_LIBRARY
from .system import SystemConfig
from .workflow import run_application, sweep, compare_memories

LINE = "=" * 70

# Set once input() proves unusable. Falling back to defaults is right for a
# single prompt, but a menu that loops would then re-run the same task forever,
# so the loop has to know that no further answers are coming.
_STDIN_DEAD = False


# ------------------------------------------------------------------------------
# Prompts
# ------------------------------------------------------------------------------

def ask(prompt: str, options: list, default: int = 1) -> int:
    """Numbered prompt that survives a stray Enter or a bad entry.

    The question comes FIRST. This printed the options and then the
    prompt, so a reader met a numbered list before learning what it was a
    list of, and had to scroll back on every screen with more than one
    question.
    """
    from .questions import NonInteractiveEnvironmentError

    while True:
        print(f"\n  {prompt}")
        for i, text in enumerate(options, 1):
            print(f"    {i}. {text}")
        try:
            raw = input(f"\n  Selection [{default}]: ").strip()
        except NonInteractiveEnvironmentError:
            # THE ONE EXCEPTION A CALLER USES DELIBERATELY.
            #
            # The broad handler below is right for a dead stdin and wrong
            # for a caller saying "stop asking". A Streamlit front end
            # supplying answers one at a time raised this to halt a task;
            # it was absorbed, a default was chosen, and `task_lessons`
            # looped forever with nothing able to interrupt it.
            raise
        except Exception:
            # Deliberately broad. A bare terminal raises EOFError, a piped stdin
            # runs out, and a kernel driven by nbconvert or papermill raises
            # ipykernel's StdinNotImplementedError, which shares no useful base
            # class. Catching only EOFError leaves "Run All Cells" broken.
            global _STDIN_DEAD
            _STDIN_DEAD = True
            print(f"  (no input available - using {default})")
            return default
        if not raw:
            return default
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return int(raw)
        print(f"\n  Enter a number from 1 to {len(options)}.\n")


def ask_nav(name: str, description: str, options: list,
            default: int = 1) -> int:
    """Every prompt in this file goes through the registry path.

    A navigation prompt does not set a model value, so it does not carry an
    engineering effect or an affected metric. It DOES carry a name, an
    explanation of what the choice leads to, working help, and the same
    refusal wording as any other question - because the standard is about
    whether a prompt is governed, not about whether it changes a number.
    """
    from .questions import navigate, ask_question
    return ask_question(navigate(name, description, options, default))


def pause() -> None:
    """Hold the window open after a task. Skipped in a notebook."""
    if in_notebook():
        return
    try:
        input("\n  Press Enter to continue. ")
    except Exception:
        pass


def _charts_note() -> None:
    if in_notebook():
        return
    print(f"\n  Charts written to: {os.getcwd()}")


# ------------------------------------------------------------------------------
# Tasks
# ------------------------------------------------------------------------------

def task_evaluate() -> None:
    keys = list(APPLICATION_LIBRARY)
    labels = [f"{APPLICATION_LIBRARY[k].name:<32s} {APPLICATION_LIBRARY[k].model}"
              for k in keys]
    print(f"\n{LINE}\n SELECT AN APPLICATION\n{LINE}")
    import dataclasses as _dcm
    from .questions import get as _qm, ask_question as _aqm, Option as _OptM
    app_q = _dcm.replace(_qm("application"),
                         options=tuple(_OptM(k, lbl)
                                       for k, lbl in zip(keys, labels)),
                         default=1, option_builder=None)
    print()
    run_application(_aqm(app_q))
    _charts_note()


def task_sweep() -> None:
    keys = list(APPLICATION_LIBRARY)
    print(f"\n{LINE}\n DESIGN SPACE SWEEP\n{LINE}")
    from .questions import get as _qs, ask_question as _aqs
    app = _aqs(_qs("application"))

    print()
    obj = _aqs(_qs("sweep_objective"))
    print()
    sweep(app, objective=obj, minimize=True, top=15)


def task_memory() -> None:
    print(f"\n{LINE}\n COMPONENT-LEVEL MEMORY COMPARISON\n{LINE}")
    from .questions import get as _qc, ask_question as _aqc
    names = list(MEMORY_LIBRARY)
    chosen = _aqc(_qc("memory_comparison_set"))
    print()
    picked = names if chosen == "all" else [n.strip()
                                            for n in chosen.split(",")]
    compare_memories(picked)
    _charts_note()


def task_custom():
    """Build one candidate.

    RETURNS ITS CONFIGURATION.

    This used to reach the engine through `run_application` and return
    nothing, so a report built by watching `build_review` never saw it -
    zero of seven panels. What every workflow has in common is the
    configuration it ends with, and saying so is better than inferring
    it from which function happened to be called.
    """
    from .outcome import single as _single, SelectedAnswer

    print(f"\n{LINE}\n BUILD YOUR OWN CANDIDATE\n{LINE}")
    keys = list(APPLICATION_LIBRARY)
    from .questions import get as _qs, ask_question as _aqs
    app = _aqs(_qs("application"))

    cpus, comps, mems = list(CPU_LIBRARY), list(COMPUTE_LIBRARY), list(MEMORY_LIBRARY)
    print()
    from .questions import get as _q, ask_question
    cpu = ask_question(_q("host_processor"))
    print()
    comp = ask_question(_q("accelerator_class"))
    print()
    mem = ask_question(_q("memory_type"))
    print()
    from .questions import (memory_context, memory_summary,
                            memory_unit_count_question)
    for line in memory_context(mem):
        print(f"  {line}")
    print()
    n = ask_question(memory_unit_count_question(mem))
    print()
    for line in memory_summary(mem, n):
        print(f"  {line}")
    print()
    cfg = SystemConfig(cpu, comp, mem, n)
    # Remember it, so a researcher on their fourth iteration can still find
    # the second. The configuration only - never the results.
    try:
        import os
        from .workspace import remember
        remember(app, cfg,
                 os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    except Exception:
        pass
    run_application(app, candidates=[cfg])
    _charts_note()
    from .present import present as _present
    _out = _single(
        "custom_design", app, cfg,
        (SelectedAnswer(1, "Application", str(app)),
         SelectedAnswer(2, "Host Processor", str(cpu)),
         SelectedAnswer(3, "Accelerator", str(comp)),
         SelectedAnswer(4, "Memory Technology", str(mem)),
         SelectedAnswer(5, "Memory Devices", str(n))))
    _present(_out)
    return _out


def ask_node(app):
    """Let the student pick a process node, with the trade visible."""
    from .process import NODE_LIBRARY
    keys = list(NODE_LIBRARY)
    default = keys.index(app.default_accel_node) + 1
    labels = [f"{k}  {NODE_LIBRARY[k].label}" for k in keys]
    import dataclasses as _dcn
    from .questions import get as _qnd, ask_question as _aqn, Option as _OptN
    node_q = _dcn.replace(_qnd("process_node"),
                          options=tuple(_OptN(k, lbl)
                                        for k, lbl in zip(keys, labels)),
                          default=default, option_builder=None)
    return _aqn(node_q)


def task_reproducibility() -> None:
    """What ran, on what, and whether a rerun agrees."""
    import os
    from .reproducibility import write_package, verify, coefficient_snapshot
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = os.path.join(root, "reproducibility")
    print(f"\n{LINE}\n REPRODUCIBILITY EVIDENCE\n{LINE}")
    if not os.path.isfile(os.path.join(out, "manifest.json")):
        print("  no package recorded yet - writing one")
        h = write_package(root, out)
        print(f"  evidence hash  {h}")
        print(f"  written to     {out}/")
    verify(root, out)


def task_sensitivity() -> None:
    """Which conclusions survive their assumptions."""
    from .sensitivity import build_sweeps, run_sweep, print_sweep, run_all
    sweeps = build_sweeps()
    labels = [f"{sw.sid}  {sw.description}" for sw in sweeps] + ["All of them"]
    print()
    from .questions import get as _qa, ask_question as _aqa
    chosen_sid = _aqa(_qa("model_assumption"))
    pick = (len(labels) if chosen_sid == "__all__"
            else [sw.sid for sw in sweeps].index(chosen_sid) + 1)
    if pick > len(sweeps):
        run_all()
        from .sensitivity import (handoff_break_even, handoff_ranking,
                                  print_ranking, coefficient_liveness)
        handoff_break_even()
        print_ranking(handoff_ranking(320 * 240, include_dual=False))
        from .sensitivity import (memory_energy_common_scale,
                                  memory_energy_relative)
        memory_energy_common_scale()
        memory_energy_relative()
        coefficient_liveness()
    else:
        print_sweep(run_sweep(sweeps[pick - 1]))


def task_explain() -> None:
    """Compare two designs and say why the numbers moved."""
    from .explain import decision_explanation, CHAINS, why
    keys = list(APPLICATION_LIBRARY)
    print(f"\n{LINE}\n WHY DID THE NUMBER CHANGE\n{LINE}")
    from .questions import get as _qs, ask_question as _aqs
    app = _aqs(_qs("application"))
    a = APPLICATION_LIBRARY[app]
    cpu = ("server_x86_x32" if a.domain == "Data Center" else "cortex_a78_x4")
    comps = list(COMPUTE_LIBRARY)
    print()
    from .questions import get as _qb, ask_question as _aqb
    c1 = _aqb(_qb("baseline_accelerator"))
    print()
    c2 = _aqb(_qb("comparison_accelerator"))
    print()
    mems = list(MEMORY_LIBRARY)
    m1 = _aqb(_qb("baseline_memory"))
    print()
    m2 = mems[ask_nav("Comparison Accelerator Compute Class", "Select the comparison accelerator compute class for this task.", mems) - 1]
    decision_explanation(
        app, SystemConfig(cpu, c1, m1, 2), SystemConfig(cpu, c2, m2, 2))
    print()
    labels = [CHAINS[k][0] for k in CHAINS] + ["Back"]
    pick = ask_nav("Continue Reading", "Choose whether to read another mechanism or return.", labels)
    if pick <= len(CHAINS):
        why(list(CHAINS)[pick - 1])


def task_runtime() -> None:
    from .runtime import simulate, print_dashboard
    from .game import PRECISION_OPTIONS
    from .preprocess import MODES as PMODES

    keys = list(APPLICATION_LIBRARY)
    print(f"\n{LINE}\n RUN A SYSTEM FOR A WHILE\n{LINE}")
    from .questions import get as _qs, ask_question as _aqs
    app = _aqs(_qs("application"))
    print()
    comps = list(COMPUTE_LIBRARY)
    from .questions import get as _q2, ask_question as _aq2
    comp = _aq2(_q2("accelerator_class"))
    print()
    mems = list(MEMORY_LIBRARY)
    mem = _aq2(_q2("memory_type"))
    print()
    counts = [1, 2, 4, 8]
    n = counts[ask_nav("Memory Unit Count", "Select the memory unit count for this task.", [str(c) for c in counts], 3) - 1]
    print()
    pmodes = list(PMODES)
    pmode = pmodes[ask_nav("Preprocessing Location", "Select the preprocessing location for this task.", [PMODES[k]["label"] for k in pmodes]) - 1]
    print()
    # The process node was previously only selectable in the design game, so a
    # student following the main path could not choose the axis where their
    # intuition is most likely to be wrong.
    node = ask_node(APPLICATION_LIBRARY[app])
    print()
    durations = [10, 30, 60, 120]
    d = durations[ask_nav("Observation Window", "Choose how long the runtime simulation observes the system.", [f"{x} s" for x in durations], 3) - 1]

    cpu = ("server_x86_x32" if APPLICATION_LIBRARY[app].domain == "Data Center"
           else "cortex_a78_x4")
    cfg = SystemConfig(cpu, comp, mem, n, preprocessing_mode=pmode,
                       accel_node=node, soc_node=node)
    r = simulate(app, cfg, duration_s=float(d))
    print_dashboard(r)
    from .runtime import explore_memory
    explore_memory(app, cfg, duration_s=float(d))
    from .migration import node_sweep, design_type_nodes
    node_sweep(app, cfg)
    design_type_nodes()
    from .economics import print_economics, node_decision
    print_economics(app, cfg)
    from .process import NODE_LIBRARY as _NL
    keys = list(_NL)
    here = keys.index(node)
    if here + 2 < len(keys):
        node_decision(app, cfg, node, keys[here + 2])
        # One step, not four. Quadrupling the packages was the most
        # expensive option on the list and it was the default, which framed
        # the memory question as "how much do you want to spend".
        from .economics import node_and_memory, memory_options
        node_and_memory(app, cfg, keys[here + 2], mem, min(n * 2, 8))
        memory_options(app, cfg)
        from .economics import (host_options, allocation_sweep,
                                stack_marginal_utility)
        if APPLICATION_LIBRARY[app].workload_class == "text":
            from .economics import context_sweep, quantisation_sweep
            context_sweep(app, cfg)
            from .economics import (batch_sweep, model_size_sweep,
                                    prompt_ratio_sweep, moe_comparison)
            batch_sweep(app, cfg)
            quantisation_sweep(app, cfg)
            model_size_sweep(app, cfg)
            prompt_ratio_sweep(app, cfg)
            moe_comparison(app, cfg)
        if mem.startswith("HBM"):
            stack_marginal_utility(app, cfg, mem)
        else:
            # Before showing what a faster memory did, ask why it was chosen.
            from .economics import memory_choice
            import dataclasses as _dcm
            memory_choice(app, cfg, _dcm.replace(cfg, memory="HBM3E",
                                                 memory_devices=1))
        host_options(app, cfg)
        if comp.startswith("npu_"):
            slower = {"npu_128x128": "npu_64x64", "npu_64x64": "npu_32x32",
                      "npu_32x32": "npu_24x24", "npu_24x24": "npu_16x16"}
            if comp in slower:
                allocation_sweep(app, cfg, slower[comp], "alternative")


def task_innovation() -> None:
    """Starting point -> student modification -> evidence -> report.

    The student never starts from nothing: choosing an application produces a
    working reference, and the exercise is to change it. Only the differences
    are asked for.
    """
    from .innovation import (evaluate_proposal, print_innovation_report,
                             REFERENCE_PLATFORMS)
    from .designs import print_designs, reference_of, compare_with_examples
    from .preprocess import MODES as PMODES
    from .application import make_custom_application

    # --- 1. application, including one the student invents ------------------
    keys = list(APPLICATION_LIBRARY)
    print(f"\n{LINE}\n 1. APPLICATION\n{LINE}")
    labels = [APPLICATION_LIBRARY[k].name for k in keys] + ["Define a new application"]
    choice = ask_nav("Target Application", "Select the target application for this task.", labels, 3)
    if choice == len(labels):
        app = _build_custom_application()
    else:
        app = keys[choice - 1]

    # --- 2. reference and examples, generated -------------------------------
    print_designs(app)
    ref = reference_of(app)
    print("  The reference is your starting point. Change what you think is")
    print("  wrong with it - the examples are there to argue with, not copy.")

    # --- 3. the student's changes ------------------------------------------
    print(f"\n{LINE}\n 3. YOUR CHANGES\n{LINE}")
    print("  Leave anything unchanged by pressing Enter.\n")
    comps = list(COMPUTE_LIBRARY)
    from .questions import get as _q3, ask_question as _aq3
    comp = _aq3(_q3("accelerator_class"))
    print()
    mems = list(MEMORY_LIBRARY)
    mem = _aq3(_q3("memory_type"))
    print()
    counts = [1, 2, 4, 8]
    n = counts[ask_nav("Memory Unit Count", "Select the memory unit count for this task.", [str(c) for c in counts],
                   counts.index(ref.memory_devices) + 1
                   if ref.memory_devices in counts else 1) - 1]
    print()
    pmodes = list(PMODES)
    pmode = pmodes[ask_nav("Preprocessing Location", "Select the preprocessing location for this task.", [PMODES[k]["label"] for k in pmodes],
                       pmodes.index(ref.preprocessing_mode) + 1) - 1]

    print()
    refs = ["(none)"] + [REFERENCE_PLATFORMS[k].name for k in REFERENCE_PLATFORMS]
    rc = ask_nav("Published Comparison", "Choose whether to compare this design against a published platform.", refs)
    platform = None if rc == 1 else list(REFERENCE_PLATFORMS)[rc - 2]

    proposed = SystemConfig(ref.cpu, comp, mem, n, preprocessing_mode=pmode)
    if (proposed.compute == ref.compute and proposed.memory == ref.memory
            and proposed.memory_devices == ref.memory_devices
            and proposed.preprocessing_mode == ref.preprocessing_mode):
        print("\n  Nothing was changed, so there is nothing to compare. The")
        print("  report below describes the starting point only.")

    # --- 4-6. simulate, compare, report ------------------------------------
    prop = evaluate_proposal(app, ref, proposed, 60.0, reference=platform)
    compare_with_examples(app, proposed)
    print_innovation_report(app, proposed, prop)
    print("\n  The instructor's rubric is a separate menu entry: this screen")
    print("  contains no judgement, only measurements and two blank questions.")


def _build_custom_application() -> str:
    """A new application, defined by the student."""
    from .application import make_custom_application
    print(f"\n{LINE}\n DEFINE A NEW APPLICATION\n{LINE}")
    print("  Wafer inspection, marine litter detection, wildfire watch, crop")
    print("  disease, underwater drones, orbital robotics, factory AGVs - the")
    print("  point is an application the library does not already have.\n")

    def num(prompt, default):
        try:
            raw = input(f"  {prompt} [{default:g}]: ").strip()
            return float(raw) if raw else default
        except Exception:
            return default

    try:
        name = input("  Application name [New Application]: ").strip() or "New Application"
    except Exception:
        name = "New Application"

    make_custom_application(
        name=name,
        mac_per_inference=num("Compute per inference, GMAC", 3.0) * 1e9,
        weight_bytes=num("Model size, MB", 12.0) * 1e6,
        activation_bytes=num("Model size, MB", 12.0) * 1e6 * 2.5,
        reference_accuracy_pct=num("Model accuracy, %", 97.0),
        required_accuracy_pct=num("Accuracy required, %", 94.0),
        target_inferences_per_s=num("Inferences per second", 30.0),
        power_budget_w=num("Power budget, W", 10.0),
        bom_budget_usd=num("BOM budget, USD", 150.0),
        board_budget_mm2=num("Board area budget, mm2", 600.0),
        production_volume=int(num("Lifetime volume, units", 200000)),
        register_as="innovation_custom")
    print(f"\n  {name} registered.")
    return "innovation_custom"


def task_designs() -> None:
    """Just look at the reference and the examples, without designing anything."""
    from .designs import print_designs
    keys = list(APPLICATION_LIBRARY)
    print(f"\n{LINE}\n STARTING POINT ARCHITECTURES\n{LINE}")
    app = keys[ask_nav("Target Application", "Select the target application for this task.", [APPLICATION_LIBRARY[k].name for k in keys], 3) - 1]
    print_designs(app)


def task_memory_generations() -> None:
    """HBM3E against HBM4, four ways."""
    from .memory_sweep import COMPARISONS, compare
    keys = [k for k, a in APPLICATION_LIBRARY.items() if a.domain == "Data Center"]
    print(f"\n{LINE}\n HBM GENERATION COMPARISON\n{LINE}")
    from .questions import get as _qs, ask_question as _aqs
    app = _aqs(_qs("application"))
    print()
    comps = ["datacenter_gpu", "npu_128x128", "npu_32x32", "npu_16x16"]
    comp = comps[ask_nav("AI Accelerator Class", "Select the ai accelerator class for this task.", [COMPUTE_LIBRARY[c].name for c in comps]) - 1]
    print()
    modes = list(COMPARISONS)
    labels = [COMPARISONS[k].title for k in modes] + ["All four"]
    choice = ask_nav("Comparison", "Choose which pair of designs to compare.", labels)
    for mode in (modes if choice == len(labels) else [modes[choice - 1]]):
        compare(app, mode, comp)


def task_migration() -> None:
    """What must hold when a design moves from one architecture to another."""
    from .migration import MIGRATIONS, check_migration, check_all
    check_all()
    labels = [f"{m.mid}  {m.title}" for m in MIGRATIONS] + ["Back"]
    print()
    pick = ask_nav("Migration Case", "Choose which process migration to examine.", labels)
    if pick <= len(MIGRATIONS):
        check_migration(MIGRATIONS[pick - 1].mid)


def task_gold() -> None:
    """Run a design against the fixed scenarios."""
    from .gold import (SCENARIOS, run_gold, run_all_gold,
                       print_promotion_queue)
    run_all_gold()
    print_promotion_queue()
    labels = [f"{s.gid}  {s.title}" for s in SCENARIOS] + ["Back"]
    print()
    pick = ask_nav("Scenario", "Choose which worked scenario to step through.", labels)
    if pick <= len(SCENARIOS):
        run_gold(SCENARIOS[pick - 1].gid)


def task_interpret() -> None:
    """Read a design's numbers against what is ordinary for its domain."""
    from .interpret import interpret, explain_metric, METRIC_GUIDE
    from .designs import designs_for
    keys = list(APPLICATION_LIBRARY)
    print(f"\n{LINE}\n RESULT INTERPRETATION\n{LINE}")
    from .questions import get as _qs, ask_question as _aqs
    app = _aqs(_qs("application"))
    options = designs_for(app)
    print()
    pick = ask_nav("Design", "Choose which design to work with.", [f"{d.tier} - {d.label}" for d in options])
    interpret(app, options[pick - 1].config)
    print()
    names = list(METRIC_GUIDE)
    which = ask_nav("Metric Detail", "Choose whether to show the full definition of a metric.", names + ["No thanks"])
    if which <= len(names):
        explain_metric(names[which - 1])


def task_industry() -> None:
    """Real company cases, and what the model cannot represent."""
    from .industry import (CASES, gap_report, print_case, run_case,
                           power_gap_report)
    gap_report()
    power_gap_report()
    labels = [f"{c.cid}  {c.company_role}" for c in CASES]
    print()
    choice = ask_nav("Industry Case", "Choose which published industry case to read.", labels)
    c = CASES[choice - 1]
    print_case(c.cid)
    from .industry import revalidate
    revalidate(c.cid)


def task_rubric() -> None:
    """Instructor-facing. Deliberately not part of the student flow."""
    from .innovation import print_rubric, print_calibration
    from .accuracy import print_table
    from .revisions import print_revisions
    from .coefficients import print_coefficients
    from .validation import print_validation
    from .crossval import print_crossval
    from .evidence import print_evidence
    print_rubric()
    print_calibration()
    print_table()
    print_coefficients()
    print_validation()
    print_crossval()
    print_evidence()
    print_revisions()


def task_lessons() -> None:
    """The education wizard: one change at a time, with the reason."""
    import os
    from .lessons import main as lessons_main
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    lessons_main(ask, folder=root)


def task_workspace() -> None:
    """Recent designs, saved designs, search and export.

    The retyping is what costs a researcher time, not the arithmetic. A
    design is seven fields, and comparing it with something tried twenty
    minutes ago used to mean entering all seven again from memory - which is
    where the errors come from, because the one field remembered wrongly is
    invisible in the result.
    """
    import os
    from .workspace import (print_workspace, recent, saved, export_csv,
                            export_markdown, forget_all, rebuild, describe,
                            print_search, remember)
    from .system import evaluate_system
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    while True:
        print_workspace(root)
        pick = ask_nav("Next Action", "Choose which part of the model to look at next.", [
            "Open a recent design",
            "Open a saved design",
            "Save the most recent design under a name",
            "Search for a tool, an application or a part",
            "Export one design as a document",
            "Export the recent ones to a spreadsheet",
            "Export the saved ones to a spreadsheet",
            "Clear the history",
            "Back"], 9)

        if pick == 9:
            return

        if pick == 8:
            forget_all(root)
            print("\n  Cleared. Only the list is gone - nothing was ever")
            print("  stored that could not be rebuilt from a configuration.")
            continue

        if pick == 4:
            try:
                term = input("\n  Search for: ").strip()
            except Exception:
                print("  (no input available)")
                continue
            if term:
                print_search(term)
            continue

        if pick == 3:
            entries = recent(root)
            if not entries:
                print("\n  Nothing has been built yet.")
                continue
            try:
                name = input("\n  Call it: ").strip()
            except Exception:
                print("  (no input available)")
                continue
            if not name:
                continue
            app_key, cfg = rebuild(entries[0])
            from .workspace import save_as
            save_as(name, app_key, cfg, root)
            print(f"\n  Saved as {name!r}: {describe(entries[0])}")
            continue

        if pick in (1, 2, 5):
            if pick == 2:
                store = saved(root)
                entries = list(store.values())
                names = list(store.keys())
            else:
                entries = recent(root)
                names = [describe(e) for e in entries]
                if pick == 5:
                    store = saved(root)
                    entries = list(store.values()) + entries
                    names = list(store.keys()) + [describe(e)
                                                  for e in recent(root)]
            if not entries:
                print("\n  Nothing there yet.")
                continue
            got = ask_nav("Design", "Choose which of the candidate designs to inspect.", names + ["Back"], 1)
            if got > len(entries):
                continue
            entry = entries[got - 1]

            if pick == 5:
                path = export_markdown(entry, "ppact_design.md", root,
                                       title=names[got - 1])
                if path:
                    print(f"\n  Wrote {path}")
                    print(f"  Recomputed as it was written, so it cannot")
                    print(f"  disagree with what you saw.")
                else:
                    print(f"\n  Could not write the file.")
                continue

            # OPENING a design puts it back at the top of the history, so the
            # next thing that asks for "the most recent" gets this one. That
            # is the whole point of opening it.
            app_key, cfg = rebuild(entry)
            remember(app_key, cfg, root)
            r = evaluate_system(APPLICATION_LIBRARY[app_key], cfg)
            print(f"\n{LINE}")
            print(f" {names[got - 1]}")
            print(LINE)
            for f, v in sorted(entry["config"].items()):
                print(f"  {f:<24s}{v}")
            print()
            for m in ("Latency (ms)", "Pipeline capacity (inf/s)",
                      "System power (W)", "System cost (USD)"):
                if m in r.metrics:
                    print(f"  {m:<24s}{r.metrics[m]:>12.2f}")
            failed = sorted(g for g, ok in r.gate.items() if not ok)
            print(f"  {'limited by':<24s}{r.bound_by:>12s}")
            print(f"  {'deployment':<24s}"
                  f"{('ready' if r.passes else 'NOT READY'):>12s}")
            if failed:
                print(f"  unmet: {', '.join(failed)}")
            print(f"\n  This design is now the most recent, so 'save under a")
            print(f"  name' and the other tools will pick it up.")
            print(LINE)
            continue

        entries = (recent(root) if pick == 6 else list(saved(root).values()))
        if not entries:
            print("\n  Nothing to export yet.")
            continue
        name = "ppact_recent.csv" if pick == 6 else "ppact_saved.csv"
        written = export_csv(entries, name, root)
        print(f"\n  Wrote {len(entries)} design(s) to {written}")
        print(f"  Every figure was recomputed, so it cannot disagree with")
        print(f"  what you saw on screen.")


def task_validation_summary() -> None:
    """One screen: what was checked, and what is still missing."""
    import os
    from .reproducibility import print_validation_summary
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    print_validation_summary(root, os.path.join(root, "reproducibility"))


def task_whatif() -> None:
    """Change one thing, see everything, change it back."""
    from .decide import whatif
    keys = list(APPLICATION_LIBRARY)
    print(f"\n{LINE}\n WHAT IF\n{LINE}")
    app = keys[ask_nav("Target Application", "Select the target application for this task.", [APPLICATION_LIBRARY[k].name for k in keys]) - 1]
    a = APPLICATION_LIBRARY[app]
    cpu = "server_x86_x32" if a.domain == "Data Center" else "cortex_a78_x4"
    base = SystemConfig(cpu, "npu_32x32", "LPDDR5", 2,
                        preprocessing_mode="cpu_only")
    result = whatif(app, base, ask)
    from .review import build_review, render_standard_engineering_review
    from .outcome import (comparison as _cmp, cancelled as _cancel,
                          SelectedAnswer)
    if isinstance(result, dict) and result.get("now") is not None:
        # THE WORKFLOW NAMES ITS REFERENCE. Which design is the starting
        # point is its decision, not something to read off the order two
        # configurations were evaluated in.
        from .present import present as _present
        _out = _cmp(
            "what_if", app, result["base"], result["now"],
            (SelectedAnswer(1, "Application", str(app)),
             SelectedAnswer(2, "Change",
                            ", ".join(result.get("changed", {})) or "-"),
             SelectedAnswer(3, "Finish", "Done")))
        _present(_out)
        return _out
    # DONE WITH NOTHING CHANGED IS A CANCELLATION.
    #
    # The user started a comparison and produced nothing to compare.
    # IN_PROGRESS would say the workflow is still running, which it is
    # not, and COMPLETED would promise a report there is no second
    # design for.
    return _cancel("what_if", app)


def task_review() -> None:
    """Propose a change; the Studio reviews it against the alternatives."""
    import dataclasses
    from .decide import design_review
    keys = list(APPLICATION_LIBRARY)
    print(f"\n{LINE}\n DESIGN REVIEW\n{LINE}")
    print("  Propose one change. The Studio answers with its reasons, the")
    print("  alternatives it tried, and a verdict - in that order.\n")
    app = keys[ask_nav("Target Application", "Select the target application for this task.", [APPLICATION_LIBRARY[k].name for k in keys]) - 1]
    a = APPLICATION_LIBRARY[app]
    cpu = "server_x86_x32" if a.domain == "Data Center" else "cortex_a78_x4"
    base = SystemConfig(cpu, "npu_32x32", "LPDDR5", 2,
                        preprocessing_mode="cpu_only")
    proposals = {
        "Add a faster memory": {"memory": "HBM3E", "memory_devices": 1},
        "Add a second engine": {"secondary_compute": "npu_32x32",
                                "execution_mode": "parallel",
                                "work_split": 0.5},
        "Use a bigger engine": {"compute": "npu_64x64"},
        "Move preprocessing off the host":
            {"preprocessing_mode": "isp_and_npu"},
        "Widen the memory": {"memory_devices": 8},
    }
    names = list(proposals)
    print()
    pick = names[ask_nav("Proposal", "Choose which proposal to evaluate.", names, 1) - 1]
    others = {k: v for k, v in proposals.items() if k != pick}
    design_review(app, base, pick, proposals[pick], alternatives=others)
    # The final result goes through the one entry point. design_review()
    # still prints its own reasoning above this, which R2 will continue to
    # report until that function is reduced to producing a ReviewAnalysis.
    # ONE RENDERING PATH.
    #
    # This printed the legacy review and `present(outcome)` printed the
    # common report, so one analysis appeared twice and a reader could
    # not tell which was authoritative.
    import dataclasses as _dcr
    # NO BROAD EXCEPT.
    #
    # `except Exception: pass` here returned None for a workflow that had
    # completed, and said nothing about why - a missing return, a wrong
    # status and a silent stop all look the same from outside. A user
    # cancelling and a workflow breaking are different facts and get
    # different statuses; anything else is raised.
    from .outcome import comparison as _rc, SelectedAnswer as _SA
    from .present import present as _present
    # `pick` is already the proposal's NAME - indexing a list with it
    # raised TypeError, and the broad except turned that into a silent
    # None. The exception was the information.
    _outcome = _rc(
        "design_review", app, base,
        _dcr.replace(base, **proposals[pick]),
        (_SA(1, "Application", str(app)),
         _SA(2, "Proposal", str(pick))))
    from .decide import (try_options, print_cost_effectiveness,
                         print_ceilings)
    print(f"\n  WHAT EACH GAIN COSTS")
    print_cost_effectiveness(try_options(app, base, proposals))
    print(f"\n  AND WHAT MONEY CANNOT BUY")
    print_ceilings(app, base)
    _present(_outcome)
    return _outcome


def task_guided():
    """Think first, then read: a guided design comparison.

    A REAL COMPARISON. The reader chooses a baseline accelerator and a
    comparison accelerator on screen, so both designs exist, both are
    visible, and neither is manufactured from an application default.
    """
    from .guided import guided_comparison
    keys = list(APPLICATION_LIBRARY)
    print(f"\n{LINE}\n THINK LIKE AN ARCHITECT\n{LINE}")
    app = keys[ask_nav("Target Application", "Select the target application for this task.", [APPLICATION_LIBRARY[k].name for k in keys]) - 1]
    a = APPLICATION_LIBRARY[app]
    cpu = "server_x86_x32" if a.domain == "Data Center" else "cortex_a78_x4"
    comps = list(COMPUTE_LIBRARY)
    print()
    c1 = comps[ask_nav("Baseline Accelerator Compute Class", "Select the baseline accelerator compute class for this task.", [COMPUTE_LIBRARY[c].name for c in comps], 5) - 1]
    print()
    c2 = comps[ask_nav("Comparison Accelerator Compute Class", "Select the comparison accelerator compute class for this task.", [COMPUTE_LIBRARY[c].name for c in comps], 6) - 1]
    base_cfg = SystemConfig(cpu, c1, "LPDDR5", 2)
    cur_cfg = SystemConfig(cpu, c2, "LPDDR5", 2)
    guided_comparison(app, base_cfg, cur_cfg, ask, mode="education")
    from .outcome import comparison as _gc, SelectedAnswer as _GA
    from .present import present as _present
    _out = _gc("education_guided_design", app, base_cfg, cur_cfg,
               (_GA(1, "Target Application", str(app)),
                _GA(2, "Baseline Accelerator", str(c1)),
                _GA(3, "Comparison Accelerator", str(c2))))
    _present(_out)
    return _out


def task_decide() -> None:
    """A comparison explained: what changed, why, how sure, what to do."""
    import dataclasses, os
    from .decide import explain, report_markdown
    keys = list(APPLICATION_LIBRARY)
    print(f"\n{LINE}\n EXPLAIN A CHANGE\n{LINE}")
    app = keys[ask_nav("Target Application", "Select the target application for this task.", [APPLICATION_LIBRARY[k].name for k in keys]) - 1]
    a = APPLICATION_LIBRARY[app]
    cpu = "server_x86_x32" if a.domain == "Data Center" else "cortex_a78_x4"
    comps = list(COMPUTE_LIBRARY)
    print()
    c1 = comps[ask_nav("Baseline Accelerator Compute Class", "Select the baseline accelerator compute class for this task.", [COMPUTE_LIBRARY[c].name for c in comps], 5) - 1]
    print()
    c2 = comps[ask_nav("Comparison Accelerator Compute Class", "Select the comparison accelerator compute class for this task.", [COMPUTE_LIBRARY[c].name for c in comps], 6) - 1]
    mems = list(MEMORY_LIBRARY)
    print()
    m1 = mems[ask_nav("Baseline Memory Technology", "Select the baseline memory technology for this task.", mems) - 1]
    print()
    m2 = mems[ask_nav("Comparison Memory Technology", "Select the comparison memory technology for this task.", mems) - 1]
    before = SystemConfig(cpu, c1, m1, 2)
    after = SystemConfig(cpu, c2, m2, 2)
    # One exit point. This task used to call explain() and stop there, so a
    # user comparing two designs never saw measured bars or the balance
    # chart - the two layers the product's own introduction promises.
    print()
    if ask_nav("Sensitivity Check", "Choose whether to move the assumptions and see whether the conclusion holds.", ["Yes - move the coefficients and watch", "No"], 1) == 1:
        from .decide import confidence_evidence, print_confidence_evidence
        print(f"\n  SENSITIVITY")
        print_confidence_evidence(confidence_evidence(app, before, after))
    print()
    if ask_nav("Report Export", "Choose whether to write this result to a markdown file.", ["Yes", "No"], 2) == 1:
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(root, "ppact_report.md")
        try:
            with open(path, "w") as fh:
                fh.write(report_markdown(app, before, after))
            print(f"\n  Written to {path}")
        except OSError as exc:
            print(f"\n  Could not write the report: {exc}")
    from .outcome import comparison as _dc2, SelectedAnswer as _SAd
    from .present import present as _present
    _out = _dc2("education_why_changed", app, before, after,
                (_SAd(1, "Application", str(app)),
                 _SAd(2, "Starting point", str(before)[:40]),
                 _SAd(3, "Current design", str(after)[:40])))
    _present(_out)
    return _out


def task_demo():
    """One question, one comparison, one answer.

    DEMO IS NOT AN EXCEPTION. It returns the same object every other
    workflow returns; what differs is that its two designs are given
    rather than chosen.
    """
    from .demo import main as demo_main
    return demo_main(ask)


def task_challenge():
    """A task with a bar, and a rank among designs that clear it."""
    from .challenge import main as challenge_main
    return challenge_main(ask)


def task_quickstart() -> None:
    """One worked design, reviewed. Nothing to fill in.

    Quick means fewer inputs, not a thinner conclusion - so this asks for
    an application and produces the same standard review every other
    analysis produces.
    """
    from .designs import designs_for
    from .review import build_review, render_standard_engineering_review
    keys = list(APPLICATION_LIBRARY)
    print("\n  One worked design for an application you choose, reviewed")
    print("  the same way every analysis in this program is reviewed.\n")
    # The registry question, not ask_nav. Target Application decides the
    # workload, every requirement and every budget - labelling it "does not
    # change any design or any estimate" was the opposite of true, and it
    # happened because the prompt was built with the navigation helper.
    import dataclasses as _dcq
    from .questions import (get as _qq, ask_question as _aqq,
                            Option as _OptQ)
    app_q = _dcq.replace(
        _qq("application"),
        options=tuple(_OptQ(k, APPLICATION_LIBRARY[k].name,
                            APPLICATION_LIBRARY[k].domain) for k in keys),
        option_builder=None)
    app = _aqq(app_q)
    cfg = designs_for(app)[0].config
    # THE COMMON REPORT, not the legacy renderer.
    from .outcome import single as _single, SelectedAnswer
    from .present import present as _present
    out = _single("quick_start", app, cfg,
                  (SelectedAnswer(1, "Application", str(app)),))
    _present(out)
    return out


def task_system_flow() -> None:
    """System Flow: the picture first, then what it does not settle.

    SYSTEM FLOW leads because it is the only view that shows the design as
    a whole. The three that follow each answer a question the picture
    raises and cannot answer by itself:

        the flow shows where time goes
        block throughput shows the rate each block could sustain - a
            different decomposition, and the block that sets the system
            rate may have no box in the picture
        memory says whether the bus suffices, and where the reasoning
            about it stops
        bottleneck names a candidate, and refuses to name a cause

    They are one task rather than four menu entries because a user who
    reaches the adequacy verdict without the capacity-floor sentence, or
    the candidate without the NOT ESTABLISHED tail, has the number and not
    the finding.
    """
    from .review import build_review
    from .visual import (build_flow, render_flow_text,
                         build_throughput_view, render_throughput_view)
    from .memory_analysis import analyse_memory, render_memory_analysis
    from .bottleneck import infer_bottleneck, render_bottleneck
    from .designs import designs_for
    from .questions import (get as _q, ask_question as _ask, Option as _Opt)
    import dataclasses as _dc

    keys = list(APPLICATION_LIBRARY)
    print(f"\n{LINE}\n ANALYZE CURRENT DESIGN\n{LINE}")
    print("  Understand how your design performs and what limits it.")
    print()
    print("  The design as a whole, and then the questions the picture")
    print("  raises and cannot answer by itself.\n")

    app_q = _dc.replace(
        _q("application"),
        options=tuple(_Opt(k, APPLICATION_LIBRARY[k].name,
                           APPLICATION_LIBRARY[k].domain) for k in keys),
        option_builder=None)
    app = _ask(app_q)
    cfg = designs_for(app)[0].config

    # A SINGLE-variant workflow. what_if is a comparison and refused to
    # be built without a starting configuration, which is the registry
    # doing its job: this screen analyses one design and has no second one
    # to compare against.
    analysis = build_review("education_step_by_step", app, cfg)
    flow = build_flow(analysis)
    memory = analyse_memory(analysis)

    # Titled. The text renderer emits the flow without a heading because
    # the standard review supplies its own numbered one; here there is no
    # numbered section, so the screen would begin with a bare "one job".
    print(f"\n{LINE}")
    print("  1. SYSTEM FLOW AND LATENCY COMPOSITION")
    print("")
    for line in render_flow_text(flow):
        print(f"  {line}" if line.strip() else "")

    from .performance_constraints import (build_performance_constraints,
                                          render_performance_constraints)
    print(f"\n{LINE}")
    print("  2. PERFORMANCE CONSTRAINTS - what is required, and the room "
          "left")
    print("")
    for line in render_performance_constraints(
            build_performance_constraints(analysis, flow),
            show_title=False):
        print(f"  {line}" if line.strip() else "")

    print(f"\n{LINE}")
    print("  3. BLOCK THROUGHPUT - the lowest one sets the system")
    print("")
    for line in render_throughput_view(
            build_throughput_view(analysis, flow, memory),
            show_title=False):
        print(f"  {line}" if line.strip() else "")

    print(f"\n{LINE}")
    print("  4. MEMORY ANALYSIS - whether the shared bus suffices")
    print("")
    for line in render_memory_analysis(memory, flow):
        print(f"  {line}" if line.strip() else "")

    from .perf_bottleneck import (find_bottleneck,
                                  render_performance_bottleneck,
                                  render_performance_recommendation)
    print(f"\n{LINE}")
    print("  5. PERFORMANCE BOTTLENECK - the lowest stage throughput")
    print("")
    pb = find_bottleneck(analysis)
    for line in render_performance_bottleneck(pb, show_title=False):
        print(f"  {line}" if line.strip() else "")
    print("")
    for line in render_performance_recommendation(pb):
        print(f"  {line}" if line.strip() else "")

    from .traffic import (build_traffic_balance, render_traffic_balance,
                          recommend_traffic)
    print(f"\n{LINE}")
    print("  6. TRAFFIC BALANCE - how evenly the stages are matched")
    print("")
    tb = build_traffic_balance(analysis)
    for line in render_traffic_balance(tb, show_title=False):
        print(f"  {line}" if line.strip() else "")
    _trec = recommend_traffic(tb)
    if _trec:
        print("")
        print("  Traffic recommendation")
        from .visual.text import wrap_text as _wt2
        for _l in _wt2(_trec, 62):
            print(f"      {_l}")

    from .performance_constraints import build_performance_constraints \
        as _bpc
    from .bottleneck import infer_bottleneck as _ib
    from .recommendation import recommend, render_recommendation

    print(f"\n{LINE}")
    print("  7. BOTTLENECK INFERENCE - a candidate, not a cause")
    print("")
    bottleneck = _ib(analysis, flow, memory)
    for line in render_bottleneck(bottleneck):
        print(f"  {line}" if line.strip() else "")

    from .area import (build_area_view, render_area_view,
                       recommend_area, render_area_recommendation)
    print(f"\n{LINE}")
    print("  8. AREA ANALYSIS - the same chain, on a different axis")
    print("")
    area = build_area_view(analysis)
    for line in render_area_view(area, show_title=False):
        print(f"  {line}" if line.strip() else "")
    print("")
    for line in render_area_recommendation(recommend_area(area), area):
        print(f"  {line}" if line.strip() else "")

    from .cost import (build_cost_view, render_cost_view,
                       recommend_cost, render_cost_recommendation)
    print(f"\n{LINE}")
    print("  9. COST ANALYSIS - what is known, and what is not")
    print("")
    costs = build_cost_view(analysis)
    for line in render_cost_view(costs, show_title=False):
        print(f"  {line}" if line.strip() else "")
    print("")
    for line in render_cost_recommendation(recommend_cost(costs), costs):
        print(f"  {line}" if line.strip() else "")

    from .power import (build_power_view, render_power_view,
                        analyse_power, render_power_analysis)
    from .power_basis import render_power_framework
    print(f"\n{LINE}")
    print("  10. POWER - the chain on an axis whose basis is open")
    print("")
    pv = build_power_view(analysis)
    for line in render_power_view(pv):
        print(f"  {line}" if line.strip() else "")
    print("")
    for line in render_power_framework(show_title=False):
        print(f"  {line}" if line.strip() else "")
    print("")
    for line in render_power_analysis(analyse_power(pv)):
        print(f"  {line}" if line.strip() else "")

    from .reference_space import build_reference_space, render_position
    print(f"\n{LINE}")
    print("  11. POSITION IN THE DESIGN SPACE - is this design unusual?")
    print("")
    for line in render_position(
            build_reference_space(app, limit=600), analysis):
        print(f"  {line}" if line.strip() else "")

    from .dashboard import (build_dashboard, render_dashboard,
                            recommended_order)
    print(f"\n{LINE}")
    print("  12. PPACT SUMMARY - five axes through one interface")
    print("")
    rows = build_dashboard(analysis)
    for line in render_dashboard(rows, show_title=False):
        print(f"  {line}" if line.strip() else "")
    print("")
    for line in recommended_order(rows):
        print(f"  {line}" if line.strip() else "")

    print(f"\n{LINE}")
    print("  13. RECOMMENDATION - what to change next")
    print("")
    cons = _bpc(analysis, flow)
    for line in render_recommendation(
            recommend(analysis, flow, cons, memory, bottleneck), cons):
        print(f"  {line}" if line.strip() else "")
    print(LINE)


def task_about() -> None:
    """What this is, how it works, how it evolves, and how to read it."""
    from .about import print_about
    print_about()


def task_framework() -> None:
    """What this analyses, and what it does not."""
    from .framework import print_framework
    print()
    pick = ask_nav("View", "Choose which view of this result to display.", ["Everything", "Only what is NOT implemented"], 1)
    print_framework(show_absent_only=(pick == 2))


def task_all_tools() -> None:
    """Every tool, named after what it does.

    Reachable from Research Mode, where the audience already has the
    vocabulary. It is not on the first screen, because a menu of seventeen
    technical names is a menu a beginner cannot choose from.
    """
    while True:
        print(f"\n{LINE}\n ALL TOOLS\n{LINE}")
        labels = [name for name, _ in TASKS] + ["Back"]
        pick = ask_nav("Next Action", "Choose which part of the model to look at next.", labels, len(labels))
        if pick > len(TASKS):
            return
        TASKS[pick - 1][1]()


def task_game():
    """Step-by-step design. Returns what was built."""
    from .game import play
    return play()


# Every tool the program has, named after what it does. Ten of these were
# reachable only from a mode and were therefore missing from BOTH the full
# tool list and the search - found when a search for "bottleneck" returned
# one result while three tools answer that question. A tool nobody can find
# is a tool that does not exist.
TASKS = [
    ("Quick Start: one worked design, reviewed", task_quickstart),
    ("Analyze Current Design: where the time goes and what limits it",
     task_system_flow),
    ("About: what this is and how to read it", task_about),
    ("Think like an architect: a guided comparison", task_guided),
    ("Take the lessons, in order", task_lessons),
    ("Take a set challenge", task_challenge),
    ("Pick a question and watch it answered", task_demo),
    ("Explain a change: what, why, how sure, what to do", task_decide),
    ("Propose a change and have it reviewed", task_review),
    ("Try a change and put it back", task_whatif),
    ("What is analysed, and what is not", task_framework),
    ("What was checked, and what is still missing",
     task_validation_summary),
    ("Recent designs, saved designs, search and export", task_workspace),
    ("Design a system step by step (start here)", task_game),
    ("Run a system for a while and see the dashboard", task_runtime),
    ("Starting point and design examples", task_designs),
    ("Compare HBM3E and HBM4 on an LLM workload", task_memory_generations),
    ("Why did the number change", task_explain),
    ("Reproducibility: what ran, and does a rerun agree", task_reproducibility),
    ("How much does this verdict depend on an assumption", task_sensitivity),
    ("Migration: what must hold when a design moves", task_migration),
    ("Gold reference scenarios", task_gold),
    ("Interpret a result against its application domain", task_interpret),
    ("Industry cases: what the model can and cannot express", task_industry),
    ("Innovation Challenge: starting point, your change, report", task_innovation),
    ("Grading rubric (instructor)", task_rubric),
    ("Evaluate an application against the default candidates", task_evaluate),
    ("Sweep the whole design space and rank the survivors", task_sweep),
    ("Compare memory technologies on their own", task_memory),
    ("Build one candidate by hand", task_custom),
]


# ------------------------------------------------------------------------------
# Menu
# ------------------------------------------------------------------------------

# ==============================================================================
# Welcome and workflow
# ==============================================================================
#
# The flat menu had thirty peers and no route through them. The most
# developed function in Studio - the thirteen-section analysis - was entry
# two of thirty, and reachable from no mode at all.
#
# Seven verbs, in the order a designer uses them. Nothing new is built
# here: every entry runs a task that already existed.

WORKFLOW = (
    ("Start",
     "Create or open a design.",
     (("Quick Start", "One design, analysed end to end.",
       "task_quickstart"),
      ("Start a New Design", "Build a system from scratch.",
       "task_game"),
      ("Build One Candidate", "Choose the parts yourself.",
       "task_custom"),
      ("Open an Existing Design", "Return to a design you built earlier.",
       "task_workspace"),
      ("Example Designs", "Start from a design that already works.",
       "task_designs"))),

    ("Analyze",
     "Understand how your design performs and what limits it.",
     (("Analyze Current Design",
       "Where the time goes, what limits it, and what to change.",
       "task_system_flow"),
      ("Watch a Design Run", "Watch a design execute, station by station.",
       "task_runtime"))),

    ("Improve",
     "Try changes and see whether they help.",
     (("Try a Change", "Change one thing; put it back at any point.",
       "task_whatif"),
      ("Review a Proposed Change",
       "Have a change assessed before you make it.", "task_review"),
      ("Explain This Result", "Find out why a figure is what it is.",
       "task_decide"),
      ("Why Did This Number Change?",
       "Attribute a difference to what caused it.", "task_explain"),
      ("How Solid Is This Result?",
       "See how far the verdict survives its assumptions.",
       "task_sensitivity"),
      ("Explore Design Space",
       "Search the space and rank what meets the requirements.",
       "task_sweep"))),

    ("Compare",
     "Put designs side by side and see what differs.",
     (("Compare Memory Technologies", "Memory technologies on their own.",
       "task_memory"),
      ("Compare Memory Generations", "HBM3E against HBM4 on a language "
       "model.", "task_memory_generations"),
      ("Evaluate Against Candidates",
       "Your application against the default candidates.",
       "task_evaluate"))),

    ("History",
     "See how your design changed, and what each change bought.",
     ()),

    ("Learn",
     "Work through the material, from first lesson to challenge.",
     (("Learning Path", "Work through the material in order.",
       "task_lessons"),
      ("Guided Tutorial", "Think through a comparison with the reasoning "
       "shown.", "task_guided"),
      ("Take a Challenge", "Solve a set problem and see how it is marked.",
       "task_challenge"),
      ("Innovation Challenge",
       "Start from a given design, make your change, produce a report.",
       "task_innovation"),
      ("Watch a Question Answered",
       "Pick a question and see it worked through.", "task_demo"),
      ("Interpret a Result",
       "Read a result against what its application needs.",
       "task_interpret"),
      ("What This Model Analyses", "What is inside the model, and what is "
       "not.", "task_framework"),
      ("About Studio", "What this is and how to read it.",
       "task_about"))),

    ("Verify",
     "Confirm the analysis is sound and reproducible.",
     (("Check What Was Verified", "What has been checked, and what has "
       "not.", "task_validation_summary"),
      ("Reproduce a Run", "Confirm a rerun agrees with the recorded one.",
       "task_reproducibility"),
      ("Check Gold Scenarios", "Reference cases and the results they must "
       "produce.", "task_gold"),
      ("Read Industry Cases", "What the model can and cannot express "
       "about real products.", "task_industry"),
      ("Check Migration Invariants",
       "What must still hold when a design moves platform.",
       "task_migration"),
      ("Instructor Tools", "Grading rubric and marking guidance.",
       "task_rubric"))),
)

PLANNED_NOTE = "Coming in a future release."


def featured_demo():
    """Today's demonstration, chosen by the date.

    Rotating by day-of-year means the screen changes without anyone
    maintaining a schedule, and the demo NUMBER is its position in the
    registered list - permanent, because a video citing Demo 007 must
    find the same question there.
    """
    import datetime
    from .demo import DEMOS

    if not DEMOS:
        return None, None
    n = datetime.date.today().timetuple().tm_yday % len(DEMOS)
    return n + 1, DEMOS[n]


def welcome_screen() -> str:
    """What Studio is, before any menu.

    Value, then feature, then philosophy - a launch screen that opens with
    a principle is answering a question nobody has asked yet.

    Enter runs Quick Start, NOT the demo. A user who has chosen nothing
    and is shown a memory analysis reasonably concludes Studio is a memory
    tool; Quick Start is the shortest complete path through what it
    actually does.
    """
    number, demo = featured_demo()
    print(f"\n{LINE}")
    print("                              PPACT STUDIO")
    print()
    print("                  Constraint-Based Design Assessment")
    print("                       for AI Hardware Systems")
    print()
    print("                       Analyze.  Compare.  Improve.")
    print(LINE)
    print()
    print("  Design better AI hardware through constraint-driven "
          "analysis.")
    print()
    print("  Every reported result is evaluated against explicit design "
          "constraints.")
    print()
    print("  Studio also tells you what it cannot establish.")
    print()

    labels = ["Quick Start", "Start a New Design",
              "Open an Existing Design", "Explore Demonstrations",
              "Learn PPACT", "All Tools"]
    notes = ["One design, analysed end to end.",
             "Build a system from scratch.",
             "Return to a design you built earlier.",
             f"{len(_demo_list())} questions, worked through.",
             "Work through the material in order.",
             "Everything Studio can do."]
    for i, (lab, note) in enumerate(zip(labels, notes), 1):
        print(f"    {i}. {lab:<28s}{note}")

    if demo is not None:
        print()
        print("  " + "-" * 74)
        print()
        # QUESTION FIRST, number second. People remember questions and
        # click on questions; the number is how a video refers back.
        print(f"  Today's Featured Demonstration")
        print()
        print(f"  {demo.question:<52s}Demo {number:03d}")
        print()
        print(f"  {'':<52s}Press D  ·  View all (V)")
    print("  " + "-" * 74)

    choice = ask_nav("Where would you like to start?",
                     "Choose one. Press D for today's demonstration, or "
                     "V to see them all.", labels, 1)
    return {1: "quickstart", 2: "new", 3: "open", 4: "demos",
            5: "learn", 6: "tools"}.get(choice, "quickstart")


def _demo_list():
    from .demo import DEMOS
    return DEMOS


def view_all_demonstrations() -> None:
    """The library. No filters, because there is nothing to filter on.

    Fourteen of the fifteen demos watch the same three metrics, so a topic
    or axis column derived from the data would show the same value on
    nearly every row - information-shaped and carrying none.
    """
    from .demo import DEMOS, print_demo, render_demo_review

    print(f"\n{LINE}")
    print(f" EXPLORE DEMONSTRATIONS{'':<28s}"
          f"{len(DEMOS)} worked questions")
    print(LINE)
    print("  Each one takes something a designer reasonably assumes and")
    print("  shows the conditions under which it fails.\n")
    labels = [f"Demo {i:03d}   {d.question}"
              for i, d in enumerate(DEMOS, 1)] + ["Back"]
    pick = ask_nav("Which demonstration?",
                   "Choose a question to see it worked through.", labels)
    if pick > len(DEMOS):
        return
    demo = DEMOS[pick - 1]
    print_demo(demo)
    # The number is passed so each demonstration's panels get their own
    # filenames. Without it a run of the library left one set on disk.
    render_demo_review(demo, pick)


def workflow_menu(loop: bool = True) -> int:
    """Seven verbs, in the order they are used.

    Not alphabetical and not by size: Learn and Verify sit last because a
    student reaches them late and a researcher starts there deliberately.
    """
    while True:
        print(f"\n{LINE}")
        print(f"  PPACT STUDIO")
        print(LINE)
        print()
        for i, (name, note, entries) in enumerate(WORKFLOW, 1):
            planned = "" if entries else f"   {PLANNED_NOTE}"
            print(f"    {i}. {name:<12s}{note}")
            if planned:
                print(f"       {'':<12s}{PLANNED_NOTE}")
        print()
        labels = [name for name, _, _ in WORKFLOW] + ["Back"]
        pick = ask_nav("What would you like to do?",
                       "Choose a stage of the design workflow.", labels)
        if pick > len(WORKFLOW):
            return 0
        name, note, entries = WORKFLOW[pick - 1]
        if not entries:
            print(f"\n  {name}: {PLANNED_NOTE}")
            print(f"  {note}")
            continue
        _run_group(name, note, entries)


def _run_group(name, note, entries) -> None:
    by_id = {fn.__name__: fn for _, fn in TASKS}
    print(f"\n{LINE}")
    print(f"  {name.upper()}")
    print(LINE)
    print(f"  {note}\n")
    for i, (title, line, _tid) in enumerate(entries, 1):
        print(f"    {i}. {title:<30s}{line}")
    print()
    labels = [t for t, _, _ in entries] + ["Back"]
    pick = ask_nav(f"{name}: which one?",
                   "Choose what to do next.", labels)
    if pick > len(entries):
        return
    task_id = entries[pick - 1][2]
    fn = by_id.get(task_id)
    if fn is None:
        print(f"\n  {task_id} is not available.")
        return
    try:
        fn()
    except KeyboardInterrupt:
        print("\n  Interrupted.")
    except Exception as exc:
        print(f"\n  Something went wrong: {type(exc).__name__}: {exc}")


def main_menu(loop: bool | None = None) -> int:
    """Show the menu and run the chosen task.

    `loop` defaults to True in a terminal and False in a notebook: a shell
    session stays open and expects to be returned to, while a notebook cell is
    finished when the task is, and re-running the cell is the natural repeat.

    Looping stops as soon as input becomes unavailable. Without that, a piped
    or exhausted stdin would make every prompt return its default and the menu
    would repeat the same task until killed.
    """
    global _STDIN_DEAD
    _STDIN_DEAD = False
    if loop is None:
        loop = not in_notebook()

    # THE WELCOME SCREEN COMES FIRST, once.
    #
    # Then the workflow. The flat list of thirty is still reachable - it
    # is what "All Tools" means - because a returning user who knows the
    # name of a task should not have to walk a hierarchy to reach it.
    by_id = {fn.__name__: fn for _, fn in TASKS}
    try:
        entry = welcome_screen()
    except Exception:
        entry = "tools"
    routes = {"quickstart": "task_quickstart", "new": "task_game",
              "open": "task_workspace", "learn": "task_lessons"}
    if entry == "demos":
        try:
            view_all_demonstrations()
        except Exception as exc:
            print(f"\n  Something went wrong: {type(exc).__name__}: {exc}")
    elif entry in routes:
        fn = by_id.get(routes[entry])
        if fn is not None:
            try:
                fn()
            except KeyboardInterrupt:
                print("\n  Interrupted.")
            except Exception as exc:
                print(f"\n  Something went wrong: "
                      f"{type(exc).__name__}: {exc}")
    if not loop:
        return 0

    while True:
        print(f"\n{LINE}")
        print(" AI 반도체 기술기획 - PPACT Simulator")
        print(f"{LINE}")
        print("  Pick an application, assemble CPU + Compute + Memory,")
        print("  and find out whether the product ships.\n")

        labels = ([t[0] for t in TASKS]
                  + ["Workflow menu: Start, Analyze, Improve, Compare, "
                     "Learn, Verify"]
                  + (["Quit"] if loop else ["Nothing, just exit"]))
        choice = ask_nav("Next Action", "Choose which task to run next.", labels)
        if choice == len(TASKS) + 1:
            try:
                workflow_menu(loop)
            except Exception as exc:
                print(f"\n  Something went wrong: "
                      f"{type(exc).__name__}: {exc}")
            continue
        if choice == len(TASKS) + 2:
            print("\n  Done.\n")
            return 0
        if _STDIN_DEAD:
            loop = False

        try:
            TASKS[choice - 1][1]()
        except KeyboardInterrupt:
            print("\n  Interrupted.")
        except Exception as exc:                       # keep the session alive
            print(f"\n  Something went wrong: {type(exc).__name__}: {exc}")

        if not loop:
            if in_notebook():
                print(f"\n{LINE}")
                print("  Run this cell again for another task.")
                print(f"{LINE}")
            else:
                print("\n  Done.\n")
            return 0
        pause()
