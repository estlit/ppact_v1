"""
tests_user_validation.py - can a reader answer, and is the answer sound

TWO QUESTIONS, NOT ONE
======================
Every other suite asks whether the model is right. This one asks two things
about the SCREEN:

    USER VALIDATION     given only this output, can the five questions a
                        designer actually asks be answered?
    ANSWER VALIDATION   and is the answer the program gives sound - specific,
                        numeric, in the canonical vocabulary, free of the
                        adjectives that say a direction and nothing else?

The first was measured by hand in an information-transfer experiment and gave
a result nobody predicted: the spider chart answered none of five. Doing it by
hand once is an experiment; doing it every release is a test.

WHAT THIS SUITE CANNOT DO
-------------------------
It cannot tell you whether a STUDENT understands. It checks that the answer
is present, specific and correct against the engine. Whether a person reads
it, believes it and acts on it is a question about people, and the only
instrument for that is people.

That distinction is not a hedge. A suite that reported "educational
effectiveness: PASS" would be claiming the one thing it has no way to
measure, and the claim would be believed because everything else here is
checked.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

import contextlib
import dataclasses
import io
import re
import sys

sys.path.insert(0, ".")

from ppact import APPLICATION_LIBRARY, SystemConfig, evaluate_system

LINE = "=" * 84
RESULTS = []


def check(pack, name, cond, detail=""):
    RESULTS.append((pack, name, bool(cond), detail))


def quiet(fn, *a, **kw):
    with contextlib.redirect_stdout(io.StringIO()) as buf:
        fn(*a, **kw)
    return buf.getvalue()


# ==============================================================================
# The scenarios
# ==============================================================================
#
# Ten comparisons a designer might actually run, chosen to span the shapes
# that behave differently: a change that helps, one that does not, one that
# helps and costs, one that breaks a requirement, one that cannot run at all.

SCENARIOS = (
    ("offload the preprocessing", "industrial_vision",
     dict(cpu="cortex_a78_x4", compute="npu_32x32", memory="LPDDR5",
          memory_devices=2, preprocessing_mode="cpu_only"),
     dict(preprocessing_mode="isp_and_npu")),

    ("a bigger engine, more memory", "industrial_vision",
     dict(cpu="cortex_a78_x4", compute="npu_32x32", memory="LPDDR5",
          memory_devices=2),
     dict(compute="npu_64x64", memory_devices=4)),

    ("a bigger engine alone", "industrial_vision",
     dict(cpu="cortex_a78_x4", compute="npu_32x32", memory="LPDDR5",
          memory_devices=2, preprocessing_mode="cpu_only"),
     dict(compute="npu_64x64")),

    ("stacked memory on a compute-bound design", "industrial_vision",
     dict(cpu="cortex_a78_x4", compute="npu_32x32", memory="LPDDR5",
          memory_devices=2),
     dict(memory="HBM3E", memory_devices=1)),

    ("a second accelerator", "industrial_vision",
     dict(cpu="cortex_a78_x4", compute="npu_32x32", memory="LPDDR5",
          memory_devices=2, preprocessing_mode="cpu_only"),
     dict(secondary_compute="npu_32x32", execution_mode="parallel",
          work_split=0.5)),

    ("a smaller host", "industrial_vision",
     dict(cpu="cortex_a78_x4", compute="npu_32x32", memory="LPDDR5",
          memory_devices=2, preprocessing_mode="cpu_only"),
     dict(cpu="cortex_a53_x4")),

    ("an automotive class part", "drone",
     dict(cpu="cortex_a78_x4", compute="npu_24x24", memory="LPDDR5",
          memory_devices=2, preprocessing_mode="isp_and_npu"),
     dict(compute="class_250_tops")),

    ("a finer process node", "mobile_ai",
     dict(cpu="cortex_a78_x4", compute="npu_64x64", memory="LPDDR5",
          memory_devices=2, preprocessing_mode="isp_and_npu",
          soc_node="N16", accel_node="N16"),
     dict(soc_node="N3", accel_node="N3")),

    ("more stacks on a language model", "llm_service",
     dict(cpu="server_x86_x32", compute="datacenter_gpu", memory="HBM3E",
          memory_devices=6),
     dict(memory_devices=12)),

    ("a memory that cannot hold the model", "llm_service",
     dict(cpu="server_x86_x32", compute="datacenter_gpu", memory="HBM3E",
          memory_devices=6),
     dict(memory="LPDDR5", memory_devices=8)),
)


def _pair(scen):
    _, app, base, change = scen
    before = SystemConfig(**base)
    after = dataclasses.replace(before, **change)
    return app, before, after


# ==============================================================================
# UV - can the five questions be answered from the screen?
# ==============================================================================

# What a designer asks. Each maps to a marker the output must contain AND a
# fact the engine must independently agree with - a screen that answers
# confidently and wrongly is worse than one that says nothing.
FIVE_QUESTIONS = (
    ("which is quicker", "Single-job latency"),
    # The screen says "The limit moved: X -> Y" or "The limit did not
    # move". The first version of this looked for "limited by", which is
    # what the dashboard says, and reported eight scenarios as unanswerable
    # when every one of them answered.
    ("what is the bottleneck", "The limit"),
    ("what to improve next", "Where to spend next"),
    ("is there a budget problem", "DEPLOYMENT STATUS"),
    ("why did it change", "WHY"),
)


def uv_screens():
    P = "UV"
    from ppact.decide import explain

    for scen in SCENARIOS:
        name = scen[0]
        app, before, after = _pair(scen)
        text = quiet(explain, app, before, after)
        rb = evaluate_system(APPLICATION_LIBRARY[app], after)
        infeasible = "INFEASIBLE" in rb.status

        for question, marker in FIVE_QUESTIONS:
            if infeasible and question != "is there a budget problem":
                # A design that cannot hold its model has no timing to
                # explain. Requiring a latency answer here would be
                # requiring the screen to invent one.
                continue
            check(P, f"{name}: '{question}' is answerable",
                  marker in text,
                  f"{marker!r} absent - a screen that cannot answer this "
                  f"leaves the reader to guess")

        if infeasible:
            check(P, f"{name}: the screen says why there is no timing",
                  "cannot hold its weights" in text or "no timing" in text,
                  "silence would read as a slow design")
            continue

        # THE ANSWER MUST MATCH THE ENGINE
        lat = rb.metrics["Latency (ms)"]
        check(P, f"{name}: the quoted latency is the computed one",
              f"{lat:.2f}" in text,
              f"{lat:.2f} not on screen - a confident wrong answer is worse "
              f"than none")
        check(P, f"{name}: the bottleneck on screen is the computed one",
              rb.bound_by in text, rb.bound_by)
        failed = sorted(g for g, ok in rb.gate.items() if not ok)
        check(P, f"{name}: the deployment verdict matches the gates",
              ("NOT READY" in text) == bool(failed),
              f"gates failing: {failed}")


def uv_guided():
    """The guided flow must ask only what it can answer."""
    P = "UV"
    from ppact.guided import build_questions, key_takeaway

    for scen in SCENARIOS:
        name = scen[0]
        app, before, after = _pair(scen)
        qs = build_questions(app, before, after)
        check(P, f"{name}: the guided flow asks something", len(qs) >= 2,
              str(len(qs)))
        keys = [q.key for q in qs]
        check(P, f"{name}: no question is asked twice",
              len(keys) == len(set(keys)), str(keys))
        for q in qs:
            check(P, f"{name}/{q.key}: the question ends in a question mark",
                  q.text.strip().endswith("?"), q.text[-40:])
            check(P, f"{name}/{q.key}: it has an answer",
                  len(q.answer) > 20, q.answer)
            check(P, f"{name}/{q.key}: and the evidence behind it",
                  len(q.evidence) > 3, q.evidence)

        take = key_takeaway(app, before, after)
        check(P, f"{name}: there is a takeaway", 40 < len(take) < 400,
              str(len(take)))


# ==============================================================================
# AV - is the answer sound?
# ==============================================================================

# The words banned as verdicts everywhere else. An answer is the last place
# they should appear: it is the sentence a student carries away.
BANNED = ("better", "worse", "good", "bad", "fast", "slow", "faster",
          "slower", "efficient", "optimal", "significant", "huge", "tiny",
          "great", "poor")

# The canonical names. An answer that says "execution latency" has invented a
# second name for a number the rest of the program calls something else.
NON_CANONICAL = ("execution latency", "job latency", "inference latency",
                 "max throughput", "actual throughput", "ships")


def av_answers():
    P = "AV"
    from ppact.guided import build_questions, key_takeaway

    for scen in SCENARIOS:
        name = scen[0]
        app, before, after = _pair(scen)
        rb = evaluate_system(APPLICATION_LIBRARY[app], after)
        for q in build_questions(app, before, after):
            low = q.answer.lower()

            # a bare adjective
            found = [w for w in BANNED
                     if re.search(rf"\b{w}\b", low)
                     and not re.search(rf"\b{w}\b[^.]*\d", low)]
            check(P, f"{name}/{q.key}: no adjective stands without a figure",
                  not found,
                  f"{found} in {q.answer[:60]!r} - the answer is the sentence "
                  f"a student carries away")

            # canonical vocabulary
            # A word boundary, not a substring: "job latency" sits inside
            # "single-job latency", and the canonical name would fail
            # itself. Third time this class of mistake has appeared in this
            # project, which is why it is written down here.
            wrong = [t for t in NON_CANONICAL
                     if re.search(rf"(?<![-\w]){re.escape(t)}\b", low)]
            check(P, f"{name}/{q.key}: canonical terms only", not wrong,
                  str(wrong))

            # specificity: an answer to a numeric question needs a number
            if q.key in ("quicker", "bottleneck", "next"):
                check(P, f"{name}/{q.key}: the answer carries a figure",
                      re.search(r"\d", q.answer) is not None,
                      q.answer[:60])

            # units where a figure is quoted
            if q.key == "quicker" and re.search(r"\d", q.answer):
                check(P, f"{name}/{q.key}: the figure carries its unit",
                      "ms" in q.answer or "unchanged" in q.answer,
                      q.answer[:60])

            # no hedging: a guess dressed as an answer
            for hedge in ("probably", "might be", "should be roughly",
                          "approximately around", "more or less"):
                check(P, f"{name}/{q.key}: no hedge {hedge!r}",
                      hedge not in low, q.answer[:60])

        # the takeaway is the most-read line, and gets the same treatment
        take = key_takeaway(app, before, after)
        low = take.lower()
        found = [w for w in BANNED
                 if re.search(rf"\b{w}\b", low)
                 and not re.search(rf"\b{w}\b[^.]*\d", low)]
        check(P, f"{name}: the takeaway carries no bare adjective",
              not found, f"{found} in {take[:70]!r}")
        check(P, f"{name}: the takeaway carries a figure",
              re.search(r"\d", take) is not None, take[:70])
        # and it must be about THIS comparison, not a slogan
        check(P, f"{name}: the takeaway names a measured quantity",
              any(t in low for t in ("latency", "memory", "cost", "time",
                                     "holds")),
              take[:70])


def av_distinct_takeaways():
    """A takeaway that fits every comparison is a slogan."""
    P = "AV"
    from ppact.guided import key_takeaway
    seen = {}
    for scen in SCENARIOS:
        app, before, after = _pair(scen)
        seen[scen[0]] = key_takeaway(app, before, after)
    unique = len(set(seen.values()))
    check(P, "the takeaways differ between scenarios",
          unique >= len(seen) - 1,
          f"{unique} distinct out of {len(seen)} - a line that fits every "
          f"comparison is a slogan, and a student who meets three stops "
          f"reading the last line")


# ==============================================================================
# What this suite does NOT establish
# ==============================================================================

NOT_ESTABLISHED = (
    ("a student understands it",
     "needs students; this checks that the answer is present, specific and "
     "correct against the engine"),
    ("the tool improves anybody's answers",
     "needs the same people with and without it, and a control"),
    ("the wording is clear to a beginner",
     "readability is a property of a reader, not of a string"),
)


def main():
    print(LINE)
    print(" USER AND ANSWER VALIDATION")
    print(LINE)
    print("  Two questions about the SCREEN: can the five questions a")
    print("  designer asks be answered from it, and is the answer sound?\n")

    for fn in (uv_screens, uv_guided, av_answers,
               av_distinct_takeaways, cv_consistency,
               cv_positive_control, os_stability):
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
                print(f"          {detail}")

    passed = sum(1 for _, _, ok, _ in RESULTS if ok)
    print(f"\n{LINE}")
    print(" REPORT")
    print(LINE)
    for pack in sorted(by_pack):
        good, total = by_pack[pack]
        label = {"UV": "user validation", "AV": "answer validation",
                 "CV": "consistency", "OS": "output stability"}.get(
            pack, pack)
        print(f"  {pack}  {label:<22s}{good:>5d} / {total:<6d}"
              f"{'pass' if good == total else 'FAIL'}")
    print(f"\n  {passed} / {len(RESULTS)} checks across "
          f"{len(SCENARIOS)} scenarios")

    print(f"\n  NOT ESTABLISHED BY THIS SUITE")
    for item, why in NOT_ESTABLISHED:
        print(f"    {item}")
        print(f"      {why}")
    print(f"\n  A suite reporting 'educational effectiveness: PASS' would be")
    print(f"  claiming the one thing it has no way to measure, and would be")
    print(f"  believed because everything else here is checked.")
    print(LINE)
    return 0 if passed == len(RESULTS) else 1



# ==============================================================================
# CV - do the four statements agree with each other?
# ==============================================================================
#
# The suite so far asked whether an answer exists and whether it is right.
# It never asked whether the answers agree.
#
# A student does not check the spider. They read the last line. So if the
# breakdown says the host holds 90% of the time and the takeaway says to
# upgrade the accelerator, the student leaves with the wrong lesson and
# every other check in this package passed while it happened.
#
# Four statements, one direction:
#
#     REASON       which station holds most of one job
#     CONCLUSION   what the engine reports as the limit
#     NEXT STEP    what the recommendation names first
#     TAKEAWAY     what the last line tells them to do

# Which words in a sentence refer to which station. Written out because
# "host active" in a breakdown and "Host processor" in a ranking are the
# same thing said twice, and a check that did not know that would pass a
# real contradiction.
STATION_WORDS = {
    "host": ("host", "cpu", "preprocess"),
    "accelerator": ("accelerator", "engine", "npu"),
    "memory": ("memory", "bandwidth", "dram"),
    "handoff": ("hand-off", "handoff", "split", "merge"),
}


def _station_of(text: str):
    """Which station a sentence is about, or None if it names several."""
    low = text.lower()
    hits = {name for name, words in STATION_WORDS.items()
            if any(w in low for w in words)}
    return hits


def cv_consistency():
    P = "CV"
    from ppact.decide import headroom, upgrade_ranking, recommendations
    from ppact.guided import build_questions, key_takeaway

    for scen in SCENARIOS:
        name = scen[0]
        app, before, after = _pair(scen)
        rb = evaluate_system(APPLICATION_LIBRARY[app], after)
        if "INFEASIBLE" in rb.status:
            continue
        m = rb.metrics
        hr = headroom(m)
        if not hr:
            continue

        # 1. REASON - the station holding most of one job
        reason_station = _station_of(hr[0].station)
        check(P, f"{name}: the breakdown names a station",
              reason_station, hr[0].station)

        # 2. CONCLUSION -> NEXT STEP
        ranking = upgrade_ranking(m, rb.bound_by)
        check(P, f"{name}: the ranking leads with the same station",
              ranking and _station_of(ranking[0][0]) & reason_station,
              f"breakdown says {hr[0].station}, ranking leads with "
              f"{ranking[0][0] if ranking else 'nothing'} - a recommendation "
              f"that names a different part from the one holding the time "
              f"contradicts its own evidence")

        # 3. NEXT STEP -> RECOMMENDATION
        failed = sorted(g for g, ok in rb.gate.items() if not ok)
        advice = " ".join(recommendations(m, m, rb.bound_by, rb.passes,
                                          failed))
        if hr[0].share_pct >= 50.0:
            adv_stations = _station_of(advice)
            check(P, f"{name}: the advice names the dominant station",
                  not adv_stations or (adv_stations & reason_station),
                  f"{hr[0].station} holds {hr[0].share_pct:.0f}% and the "
                  f"advice talks about {adv_stations} - {advice[:70]!r}")

        # 4. TAKEAWAY must not point elsewhere
        take = key_takeaway(app, before, after)
        take_stations = _station_of(take)
        if hr[0].share_pct >= 50.0 and take_stations:
            check(P, f"{name}: the takeaway points at the same station",
                  take_stations & reason_station,
                  f"breakdown {hr[0].station} {hr[0].share_pct:.0f}%, "
                  f"takeaway names {take_stations} - a student reads the "
                  f"last line and nothing else")

        # 5. and the guided answers must agree with all of it
        qs = {q.key: q for q in build_questions(app, before, after)}
        if "bottleneck" in qs:
            check(P, f"{name}: the guided bottleneck answer agrees",
                  _station_of(qs["bottleneck"].answer) & reason_station,
                  qs["bottleneck"].answer[:70])
        if "next" in qs:
            check(P, f"{name}: the guided next-step answer agrees",
                  _station_of(qs["next"].answer) & reason_station,
                  qs["next"].answer[:70])
        if "quicker" in qs:
            lat = m["Latency (ms)"]
            check(P, f"{name}: the guided latency agrees with the engine",
                  f"{lat:.2f}" in qs["quicker"].answer
                  or "unchanged" in qs["quicker"].answer,
                  qs["quicker"].answer[:70])


# ==============================================================================
# OS - the same input must produce the same output
# ==============================================================================

def cv_positive_control():
    """The consistency detector must actually fire.

    Every scenario passes, which is what it should do and also means the
    detector has never been seen to work. It is given the exact
    contradiction it exists to catch: a breakdown saying the host holds 90%
    of the time beside a takeaway saying to upgrade the accelerator.

    This is the ninth detector in this project found never to have fired,
    and the pattern is now the first thing checked when one is added.
    """
    P = "CV"
    import ppact.guided as _G
    real = _G.key_takeaway
    saved = list(RESULTS)
    try:
        _G.key_takeaway = (lambda a, b, c:
                           "Upgrade the accelerator. It is the obvious next "
                           "step at 90.0%.")
        RESULTS.clear()
        cv_consistency()
        caught = [r for r in RESULTS if not r[2]]
    finally:
        _G.key_takeaway = real
        RESULTS.clear()
        RESULTS.extend(saved)
    check(P, "a takeaway contradicting the breakdown is caught",
          len(caught) >= 3,
          f"{len(caught)} failures - a detector that has only seen correct "
          f"input is not known to work")
    check(P, "and the failure names both sides",
          any("breakdown" in r[3] and "takeaway names" in r[3]
              for r in caught),
          "a reader of the failure must be able to see the contradiction "
          "without rerunning anything")


def os_stability(runs: int = 10):
    """Byte-identical, ten times.

    Not a formality. A screen that differs between two identical runs has
    state it should not have - a cached figure, a set iterated in hash
    order, a timestamp - and the difference will surface as an unreproducible
    bug report months later.
    """
    P = "OS"
    from ppact.decide import explain
    from ppact.guided import build_questions, key_takeaway
    from ppact.visual import build_balance, render_balance_text

    for scen in SCENARIOS[:5]:
        name = scen[0]
        app, before, after = _pair(scen)

        outs = set()
        takes = set()
        balances = set()
        questions = set()
        for _ in range(runs):
            outs.add(quiet(explain, app, before, after))
            takes.add(key_takeaway(app, before, after))
            balances.add("\n".join(render_balance_text(
                build_balance(app, [("Starting point", before),
                                    ("Current design", after)]))))
            questions.add(tuple((q.key, q.text, q.answer)
                                for q in build_questions(app, before, after)))
        check(P, f"{name}: the explanation is identical over {runs} runs",
              len(outs) == 1, f"{len(outs)} distinct outputs")
        check(P, f"{name}: the takeaway is identical", len(takes) == 1,
              f"{len(takes)} distinct")
        check(P, f"{name}: the balance view is identical",
              len(balances) == 1, f"{len(balances)} distinct")
        check(P, f"{name}: the questions are identical",
              len(questions) == 1, f"{len(questions)} distinct")


if __name__ == "__main__":
    sys.exit(main())
