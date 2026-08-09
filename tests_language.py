"""
tests_language.py - the Language QA suite

WHY A PROGRAM NEEDS A LANGUAGE SUITE
====================================
The arithmetic is checked by nine other suites. Nothing checked the WORDS,
and the words are what a student takes away. A model that computes a 14.4%
latency change and prints "HBM is faster" has taught nothing: the reader
cannot say faster at what, by how much, or why, and those are the three
things they came for.

Worse, the vocabulary drifts. One screen says "single-job latency", another
says "execution latency", a third says "job latency". They are the same
number. A reader who does not already know that will assume they are three
numbers, and nothing in a passing test suite would tell them otherwise.

    L01  forbidden terminology       no adjective standing as a verdict
    L02  canonical terminology       one name per idea
    L03  unit consistency            no bare number
    L04  every conclusion has a why
    L05  every why carries numbers
    L06  no unsupported adjective
    L07  canonical metric names      one official name per metric
    L08  deployment terminology      no "ships", no "deployable"
    L09  recommendation wording      what, why, evidence, bottleneck
    L10  tutorial wording
    L11  demo wording
    L12  challenge wording
    L13  validation wording
    L14  help wording
    L15  error wording

WHAT THIS SUITE REFUSES TO DO
-----------------------------
It does not ban a word outright. "Performance" is in the product's own
subtitle; "small engine" is the name of a part in a lesson, not a judgement
of it. A blanket ban would force worse writing and would be obeyed by
replacing a clear word with a clumsy one.

So a word is forbidden AS A VERDICT - standing alone, or attached to a
subject with no number beside it - and the exceptions are listed here rather
than argued case by case, so the list cannot quietly grow.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

import contextlib
import dataclasses
import io
import os
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
# The vocabulary
# ==============================================================================

# Words that must never stand as a verdict. Each names a direction without
# naming what moved, by how much, or why - and the word is the part a reader
# remembers.
FORBIDDEN_AS_VERDICT = (
    "better", "worse", "good", "bad", "fast", "slow", "faster", "slower",
    "efficient", "inefficient", "excellent", "poor", "optimal",
    "significant", "huge", "tiny", "ships",
)

# Where these words are legitimate, and why. Listed so the list cannot grow
# without somebody reading it.
ALLOWED_USES = {
    "performance": "the product's own subtitle, and the name of a PPACT axis",
    "small engine": "the NAME of a row in a lesson table - a part, not a "
                    "judgement of one",
    "large engine": "the NAME of a row in a lesson table, as above",
    "medium engine": "the NAME of a row in a lesson table, as above",
    "small workload": "a named case in the memory pack",
    "slower half": "a technical term - a parallel pair cannot finish before "
                   "its slower half",
    "faster memory": "a comparative used with figures beside it, in a "
                     "question the reader is about to see answered",
    "slow engine": "a named case in the LLM pack",
    "fast engine": "a named case in the LLM pack, as above",
}

# One idea, one name. A reader meeting two names for one number will assume
# two numbers.
CANONICAL = {
    "single-job latency": ("execution latency", "job latency",
                           "inference latency", "per-job latency"),
    "pipeline capacity": ("service capacity", "max throughput",
                          "peak throughput"),
    "delivered throughput": ("actual throughput", "achieved throughput"),
    "sensor-to-control": ("end-to-end latency", "total latency"),
    "deployment status": ("shipping status", "deployable status",
                          "ship status"),
}

# Every number on a screen must carry one of these, or be inside a table
# whose header carries it.
UNITS = ("ms", "s", "W", "mJ", "USD", "GB/s", "GB", "MB", "mm2", "%",
         "inf/s", "tok/s", "/s", "pp", "us", "nm", "x")


def screens():
    """Every screen a user can reach, rendered."""
    from ppact import demo, lessons, framework, challenge, modes, branding
    from ppact.decide import explain, design_review, print_handover
    from ppact.system import print_metric_boundaries, print_infeasible
    from ppact.sensitivity import coefficient_liveness
    from ppact.progress import (print_score, print_certificate, Progress)
    from ppact.workspace import print_search

    out = {}
    out["banner"] = branding.banner()
    for d in demo.DEMOS:
        out[f"demo:{d.key}"] = quiet(demo.print_demo, d)
    for les in lessons.LESSONS:
        out[f"lesson:{les.number}"] = quiet(lessons.print_lesson, les)
        out[f"lesson:{les.number}:question"] = quiet(lessons.print_question,
                                                    les)
    for ch in challenge.CHALLENGES:
        out[f"challenge:{ch.key}"] = quiet(challenge.print_challenge, ch)
    out["framework"] = quiet(framework.print_framework)
    out["boundaries"] = quiet(print_metric_boundaries)
    out["menu"] = quiet(modes.print_main_menu)
    out["handover"] = quiet(print_handover)
    out["liveness"] = quiet(coefficient_liveness)
    out["search"] = quiet(print_search, "bottleneck")

    base = SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5", 2,
                        preprocessing_mode="cpu_only")
    after = dataclasses.replace(base, preprocessing_mode="isp_and_npu")
    out["explain"] = quiet(explain, "industrial_vision", base, after)
    out["review"] = quiet(design_review, "industrial_vision", base,
                          "offload", {"preprocessing_mode": "isp_and_npu"})
    bad = evaluate_system(APPLICATION_LIBRARY["llm_service"],
                          SystemConfig("server_x86_x32", "datacenter_gpu",
                                       "LPDDR5", 8))
    out["infeasible"] = quiet(print_infeasible, bad)

    p = Progress()
    for n in range(1, 9):
        p.record(n, 0, n > 4)
    out["score"] = quiet(print_score, p, 10)
    out["certificate"] = quiet(print_certificate, p, 10)
    return out


# Sections whose contents are PROSE, not results. A word inside a sentence
# that a reader is reading as a sentence is not a verdict on a table row, and
# banning it there would force the explanation to be written badly. The rule
# is about a word used AS a result.
PROSE_SECTIONS = ("ANSWER", "BECAUSE", "WHY", "IN ONE SENTENCE", "DECISION",
                  "REASON", "reading it", "what this", "VERDICT", "hint",
                  "Your prediction", "Before you see")


def _prose_ranges(text: str):
    """Line numbers inside a prose block, which end at a blank line pair."""
    out = set()
    lines = text.splitlines()
    inside = False
    for i, line in enumerate(lines):
        if any(marker in line for marker in PROSE_SECTIONS):
            inside = True
        elif inside and line.strip() == "" and i + 1 < len(lines) \
                and lines[i + 1].strip() == "":
            inside = False
        if inside:
            out.add(i)
    return out


def _is_verdict_line(line: str) -> bool:
    """A short line with no number, and not a question.

    A question is the opposite of a verdict - "Are two engines twice as
    fast?" is the thing the screen is about to answer with figures, and
    banning the word there would ban asking.
    """
    s = line.strip()
    if not s or len(s.split()) > 6:
        return False
    if s.endswith("?"):
        return False
    return not re.search(r"\d", s)


# ==============================================================================
# L01 / L06  forbidden terminology
# ==============================================================================

def l01_forbidden(all_screens):
    P = "L01"
    hits = []
    for name, text in all_screens.items():
        prose = _prose_ranges(text)
        for i, line in enumerate(text.splitlines(), 1):
            if (i - 1) in prose or not _is_verdict_line(line):
                continue
            low = line.strip().lower()
            for word in FORBIDDEN_AS_VERDICT:
                if not re.search(rf"\b{word}\b", low):
                    continue
                if any(a in low for a in ALLOWED_USES):
                    continue
                hits.append((name, i, line.strip(), word))
    check(P, "no forbidden word stands as a verdict", not hits,
          "; ".join(f"{n} line {i}: {t!r} ({w})"
                    for n, i, t, w in hits[:3]))
    check(P, "the forbidden list is not empty",
          len(FORBIDDEN_AS_VERDICT) >= 15)
    check(P, "and every allowed use gives its reason",
          all(len(v) > 20 for v in ALLOWED_USES.values()),
          "an exception without a reason is a hole")
    return hits


def l06_unsupported(all_screens):
    P = "L06"
    # a comparative must have a number on the same line or the one after it
    hits = []
    for name, text in all_screens.items():
        lines = text.splitlines()
        prose = _prose_ranges(text)
        for i, line in enumerate(lines):
            if i in prose or line.strip().endswith("?"):
                continue
            low = line.lower()
            for word in ("faster", "slower", "cheaper", "dearer", "higher",
                         "lower"):
                if not re.search(rf"\b{word}\b", low):
                    continue
                window = " ".join(lines[i:i + 3])
                if re.search(r"\d", window):
                    continue
                if any(a in low for a in ALLOWED_USES):
                    continue
                hits.append((name, i + 1, line.strip(), word))
    check(P, "every comparative has a number near it", not hits,
          "; ".join(f"{n} line {i}: {t!r}" for n, i, t, _ in hits[:3]))


# ==============================================================================
# L02 / L07  canonical names
# ==============================================================================

def l02_canonical(all_screens):
    P = "L02"
    joined = "\n".join(all_screens.values()).lower()
    for good, bad_names in CANONICAL.items():
        for bad in bad_names:
            # A word boundary, not a substring: "job latency" occurs inside
            # "single-job latency", and the first version of this check
            # reported the canonical name as a violation of itself.
            found = re.search(rf"(?<![-\w]){re.escape(bad)}\b", joined)
            check(P, f"{bad!r} is never used for {good!r}",
                  found is None,
                  f"one idea with two names reads as two numbers"
                  + (f" - found at {found.start()}" if found else ""))


def l07_metric_names(all_screens):
    P = "L07"
    from ppact.system import METRIC_BOUNDARIES
    # every contracted metric must appear under exactly its contracted name
    joined = "\n".join(all_screens.values())
    names = [b.metric for b in METRIC_BOUNDARIES]
    check(P, "the metric contracts name distinct metrics",
          len(names) == len(set(names)), str(len(names) - len(set(names))))
    # the engine must not report two keys that differ only in wording
    m = evaluate_system(APPLICATION_LIBRARY["industrial_vision"],
                        SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5",
                                     2)).metrics
    stripped = {}
    for k in m:
        base = re.sub(r"\s*\(.*\)", "", k).strip().lower()
        stripped.setdefault(base, []).append(k)
    dupes = {b: ks for b, ks in stripped.items() if len(ks) > 1}
    check(P, "no metric is reported under two names", not dupes,
          "; ".join(f"{b}: {ks}" for b, ks in list(dupes.items())[:2]))


# ==============================================================================
# L03  units
# ==============================================================================

def l03_units(all_screens):
    P = "L03"
    for name, text in all_screens.items():
        if name in ("banner", "menu", "handover", "search"):
            continue
        if not re.search(r"\d", text):
            continue
        has_unit = any(u in text for u in UNITS)
        check(P, f"{name}: numbers carry units", has_unit,
              "a column of numbers with no unit is a column of numbers")


# ==============================================================================
# L04 / L05  every conclusion has a why, and the why has numbers
# ==============================================================================

def l04_why(all_screens):
    P = "L04"
    for name in ("explain", "review"):
        text = all_screens[name]
        check(P, f"{name}: there is a WHY section",
              "WHY" in text or "2. WHY" in text)
    for d_key in [k for k in all_screens if k.startswith("demo:")]:
        text = all_screens[d_key]
        check(P, f"{d_key}: the answer is followed by a mechanism",
              "BECAUSE" in text,
              "an answer with no mechanism is a claim, and a reader cannot "
              "check a claim")
    for l_key in [k for k in all_screens
                  if k.startswith("lesson:") and ":question" not in k]:
        check(P, f"{l_key}: the result is followed by reasoning",
              "WHY" in all_screens[l_key])


def l05_numbers_in_why(all_screens):
    P = "L05"
    text = all_screens["explain"]
    if "2. WHY" in text and "3. HOW SURE" in text:
        why = text[text.index("2. WHY"):text.index("3. HOW SURE")]
        check(P, "the WHY section carries figures",
              len(re.findall(r"-?\d+\.\d+", why)) >= 3,
              f"{len(re.findall(r'-?\\d+\\.\\d+', why))} figures")
        check(P, "and units", any(u in why for u in ("ms", "%")))
    review = all_screens["review"]
    reasons = [ln for ln in review.splitlines() if "REASON" in ln]
    check(P, "the review's reasons are numbered", len(reasons) >= 3,
          str(len(reasons)))
    with_numbers = [ln for ln in reasons if re.search(r"\d", ln)]
    check(P, "and most of them carry a figure",
          len(with_numbers) >= len(reasons) // 2,
          f"{len(with_numbers)} of {len(reasons)}")


# ==============================================================================
# L08  deployment terminology
# ==============================================================================

def l08_deployment(all_screens):
    P = "L08"
    joined = "\n".join(all_screens.values()).lower()
    for word in ("ships", "shipping status", "deployable status"):
        check(P, f"{word!r} is not used", word not in joined,
              "students read 'ships' as a boat leaving")
    check(P, "the explanation states a deployment status",
          "DEPLOYMENT STATUS" in all_screens["explain"])
    check(P, "and gives its reason",
          "Reason:" in all_screens["explain"],
          "'ready' on its own is as vague as the adjectives removed")


# ==============================================================================
# L09  recommendation wording
# ==============================================================================

def l09_recommendation(all_screens):
    P = "L09"
    text = all_screens["explain"]
    check(P, "there is a WHAT TO DO section", "4. WHAT TO DO" in text)
    if "4. WHAT TO DO" in text:
        advice = text[text.index("4. WHAT TO DO"):]
        check(P, "the advice names the bottleneck or the time share",
              re.search(r"\d+(\.\d+)?%", advice) is not None,
              "advice with no evidence beside it is an opinion")
    review = all_screens["review"]
    check(P, "the review's verdict comes after its reasons",
          review.index("VERDICT") > review.rindex("REASON"))
    check(P, "and the decision is handed back",
          "decision is the designer" in review,
          "a tool that decided would be deciding without knowing the price, "
          "the schedule or the customer")


# ==============================================================================
# L10-L15  the rest of the program speaks the same way
# ==============================================================================

def l10_tutorial(all_screens):
    P = "L10"
    for key in [k for k in all_screens if k.startswith("lesson:")
                and ":question" in k]:
        text = all_screens[key]
        check(P, f"{key}: the question is asked before any figure",
              "?" in text)
        check(P, f"{key}: and the options are offered",
              text.count("\n") >= 3)
    for key in [k for k in all_screens if k.startswith("lesson:")
                and ":question" not in k]:
        check(P, f"{key}: ends in one sentence",
              "IN ONE SENTENCE" in all_screens[key])


def l11_demo(all_screens):
    P = "L11"
    for key in [k for k in all_screens if k.startswith("demo:")]:
        text = all_screens[key]
        check(P, f"{key}: states an answer", "ANSWER" in text)
        check(P, f"{key}: names the deployment column, not 'ships'",
              "ships" not in text.lower())


def l12_challenge(all_screens):
    P = "L12"
    for key in [k for k in all_screens if k.startswith("challenge:")]:
        text = all_screens[key]
        check(P, f"{key}: states what has to be true",
              "What has to be true" in text)
        check(P, f"{key}: and what may be changed",
              "What you may change" in text)


def l13_validation(all_screens):
    P = "L13"
    text = all_screens["framework"]
    check(P, "the capability map names what is NOT implemented",
          "not implemented" in text)
    check(P, "and says why a gap is not an apology",
          "quietly guesses" in text)
    live = all_screens["liveness"]
    check(P, "the coefficient audit says what it checked",
          "declare" in live.lower())


def l14_help(all_screens):
    P = "L14"
    banner_text = all_screens["banner"]
    from ppact.branding import PRODUCT_VERSION, PRODUCT_NAME
    check(P, "the banner names the product", PRODUCT_NAME in banner_text)
    check(P, "and its version", f"v{PRODUCT_VERSION}" in banner_text)
    from ppact.branding import CLAIM
    check(P, "and says the values are estimates",
          "engineering estimates" in CLAIM
          and all(w in banner_text for w in ("engineering", "estimates")),
          "the banner wraps, so the claim is checked at its source and the "
          "words are checked on screen")
    check(P, "and that the decision is the designer's",
          "responsibility of the designer" in CLAIM
          and "designer" in banner_text)
    check(P, "and carries the copyright",
          "Copyright" in banner_text and "EdgeChipLab" in banner_text)
    # the version must come from one place
    import ppact.branding as B
    src = open(B.__file__, encoding="utf-8").read()
    check(P, "the version is a constant, not a literal in a print",
          src.count('PRODUCT_VERSION = "') == 1
          and 'print("AI System' not in src,
          "a version typed into a print statement is a version that gets "
          "forgotten")


def l15_error(all_screens):
    P = "L15"
    app = APPLICATION_LIBRARY["robot"]
    base = SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5", 4,
                        preprocessing_mode="isp_and_npu",
                        secondary_compute="npu_32x32",
                        execution_mode="parallel")
    for field, bad in (("work_split", 2.0), ("alternative_share", -1.0)):
        try:
            evaluate_system(app, dataclasses.replace(base, **{field: bad}))
            check(P, f"{field}={bad} is refused", False)
        except ValueError as exc:
            msg = str(exc)
            check(P, f"{field}: the message names the field", field in msg,
                  msg[:60])
            check(P, f"{field}: says what is allowed",
                  any(t in msg for t in ("0", "1", "between")), msg[:60])
            check(P, f"{field}: and is a sentence", len(msg.split()) >= 6,
                  msg[:60])
            check(P, f"{field}: with no forbidden adjective",
                  not any(re.search(rf"\b{w}\b", msg.lower())
                          for w in FORBIDDEN_AS_VERDICT),
                  msg[:60])
    text = all_screens["infeasible"]
    check(P, "an infeasible design says why", "does not fit" in text)
    check(P, "and does not report a speed",
          "Not Evaluated" in text,
          "reporting a token rate for a machine that cannot hold its weights "
          "invites a comparison with one that can")


# ==============================================================================
# Report
# ==============================================================================

PACK_NAMES = {
    "L01": "forbidden terminology", "L02": "canonical terminology",
    "L03": "unit consistency", "L04": "every conclusion has a why",
    "L05": "numerical justification", "L06": "no unsupported adjective",
    "L07": "metric naming", "L08": "deployment terminology",
    "L09": "recommendation wording", "L10": "tutorial wording",
    "L11": "demo wording", "L12": "challenge wording",
    "L13": "validation wording", "L14": "help wording",
    "L15": "error wording",
}


# ==============================================================================
# L16 - the philosophy audit
# ==============================================================================
#
# Not a string search any more. It reads ppact.terminology and checks four
# things, because terminology drifts back: a term is removed, six months
# pass, somebody writes the natural phrase, and the philosophy is gone with
# no defect to point at.
#
#     forbidden      a banned name appears
#     deprecated     a term with no canonical replacement
#     contradictory  a document defines a term differently from the registry
#     duplicate      two names in use for one concept

def l16_philosophy(all_screens):
    import os
    P = "L16"
    from ppact import terminology as T

    check(P, "the terminology registry is coherent", not T.violations(),
          "; ".join(T.violations()[:3]))
    check(P, "every term explains why its aliases are wrong",
          all(len(t.reason) >= 40 for t in T.TERMS),
          "a ban without a reason is a rule somebody relaxes under pressure")

    # FORBIDDEN
    for fname in sorted(os.listdir("ppact")):
        if not fname.endswith(".py") or fname == "terminology.py":
            continue
        if fname in T.HISTORICAL_FILES:
            continue
        hits = T.scan(open(os.path.join("ppact", fname),
                           encoding="utf-8").read())
        check(P, f"ppact/{fname}: uses no retired terminology", not hits,
              "; ".join(f"{p!r} in {ln[:40]}" for p, ln, _ in hits[:2]))

    for doc in ("README.md", "ABOUT.md", "HELP.md", "METHODOLOGY.md",
                "STUDENT_GUIDE.md", "EXERCISES.md", "DEFERRED.md"):
        if not os.path.isfile(doc):
            continue
        hits = T.scan(open(doc, encoding="utf-8").read())
        check(P, f"{doc}: uses no retired terminology", not hits,
              "; ".join(f"{p!r}" for p, _, _ in hits[:3]))

    # CONTRADICTORY - one definition, referenced rather than reinvented
    for doc in ("ABOUT.md", "HELP.md", "METHODOLOGY.md"):
        if not os.path.isfile(doc):
            continue
        norm = " ".join(open(doc, encoding="utf-8").read().split())
        want = " ".join(T.definition("starting_point").split())
        check(P, f"{doc}: quotes the starting-point definition verbatim",
              want in norm,
              "a definition written twice becomes two definitions")

    about = open("ABOUT.md", encoding="utf-8").read() if os.path.isfile(
        "ABOUT.md") else ""
    check(P, "About states that the Studio recommends nothing",
          "does not recommend architectures" in about)
    check(P, "and says what published examples are",
          " ".join(T.definition("published_configuration").split())
          in " ".join(about.split()),
          "an illustrative example derived from public information is not a "
          "survey of the industry")

    # AMBIGUOUS - vague wording is reported, not failed. "Typical" claims a
    # survey nobody ran; each is occasionally right, and a rule that cannot
    # say "occasionally" gets ignored the first time it is wrong.
    vague = {}
    for fname in sorted(os.listdir("ppact")):
        if not fname.endswith(".py") or fname in T.HISTORICAL_RECORD:
            continue
        for word, line, why in T.scan_discouraged(
                open(os.path.join("ppact", fname), encoding="utf-8").read()):
            vague.setdefault(word, 0)
            vague[word] += 1
    check(P, "discouraged wording is tracked", isinstance(vague, dict),
          f"counts: {dict(sorted(vague.items())[:4])}")
    check(P, "every discouraged word says why it is discouraged",
          all(len(why) >= 20 for why in T.DISCOURAGED.values()))

    # VERSIONS - a term changing meaning is a change the audits must see
    from ppact.questions import REGISTRY_VERSION as _qv
    check(P, "the terminology registry is versioned",
          bool(T.REGISTRY_VERSION))
    check(P, "the question registry is versioned", bool(_qv))

    # FIRST APPEARANCE - one wording, taken from the registry
    from ppact.questions import glossary_from_registry, first_use
    g = glossary_from_registry()
    check(P, "the question glossary comes from the terminology registry",
          len(g) == len(T.TERMS),
          "a second glossary becomes a second definition the moment one is "
          "edited")
    for t in T.TERMS:
        check(P, f"{t.key}: has first-appearance wording",
              bool(first_use(t.key)))

    # the balance caveat must travel with the shape
    from ppact.visual.balance import PURPOSE_CAVEAT
    check(P, "the balance chart carries its caveat",
          "measured results" in PURPOSE_CAVEAT
          and "alongside" in PURPOSE_CAVEAT,
          "a spider chart gets screenshot into a slide and the measured "
          "bars do not travel with it")
    check(P, "and the caveat says how to read it, not that it is unusable",
          "should be based on" in PURPOSE_CAVEAT
          and "Not intended" not in PURPOSE_CAVEAT,
          "a reader told not to use a chart uses it anyway, without the "
          "thing that would have made it safe")
    check(P, "both registries state what they are compatible with",
          T.REGISTRY_COMPATIBILITY
          and __import__("ppact.questions", fromlist=["x"]
                         ).REGISTRY_COMPATIBILITY)

    # SEPARABILITY - checked, not claimed. The framework is meant to move
    # to a second product one day, and a registry that imports the engine at
    # module level cannot move without bringing the engine with it.
    import ast as _ast
    ENGINE = {"system", "compute", "memory", "cpu", "application",
              "process", "decide", "game", "runtime", "economics"}
    for mod in ("terminology.py", "questions.py"):
        tree = _ast.parse(open(os.path.join("ppact", mod),
                               encoding="utf-8").read())
        top = [n.module for n in tree.body
               if isinstance(n, _ast.ImportFrom) and n.module in ENGINE]
        check(P, f"ppact/{mod} does not import the engine at module level",
              not top, str(top))
    tree = _ast.parse(open(os.path.join("ppact", "terminology.py"),
                           encoding="utf-8").read())
    anywhere = [n.module for n in _ast.walk(tree)
                if isinstance(n, _ast.ImportFrom) and n.module in ENGINE]
    check(P, "the terminology registry touches no engine module at all",
          not anywhere, str(anywhere)
          + " - it governs words, and words do not depend on accelerators")

    # DUPLICATE - a canonical name must not also be somebody's forbidden one
    canon = {t.canonical.lower() for t in T.TERMS}
    banned = {p.lower() for p, _ in T.all_forbidden()}
    check(P, "no canonical name is banned elsewhere", not (canon & banned),
          str(sorted(canon & banned)))

    # the starting point must still say what it is not
    # Read where the statement is SHOWN, not where it used to be written.
    # It belongs beside the starting point on the user's screen, which is
    # the standard review, and checking game.py meant the sentence could be
    # deleted from the product while the check went on passing.
    src = open("ppact/review.py", encoding="utf-8").read()
    # RENDERED SCREENS, not source strings.
    #
    # L16 read source files, so a term absent from source but produced at
    # run time went unseen: What-if printed "N28" and "N7" for a process
    # node by formatting the raw option list, and this audit reported the
    # vendor names as gone.
    #
    # A term is retired when a USER cannot meet it. Source is where it is
    # written; a screen is where it appears.
    import re as _rev
    from ppact.questions import (render_question as _rq, field_question
                                 as _fq, REGISTRY as _REG)
    from ppact.decide import WHATIF_KNOBS as _KN

    rendered = ["\n".join(_rq(raw.resolved())) for raw in _REG.values()]
    for field, opts in _KN.values():
        rendered.append("\n".join(_rq(_fq(field, opts, opts[0]))))
    screen_text = "\n".join(rendered)

    for phrase, term in T.all_forbidden():
        hits = [ln for ln in screen_text.splitlines()
                if phrase in ln.lower() and not T.permitted(ln)]
        check(P, f"no rendered screen shows {phrase!r}", not hits,
              str(hits[:1]))

    VENDOR_NODE = _rev.compile(r"\b(N28|N16|N12|N7|N5|N4|N3|N2|A16)\b")
    node_hits = sorted(set(VENDOR_NODE.findall(screen_text)))
    check(P, "no rendered question names a node by vendor key",
          not node_hits, str(node_hits))

    RAW = _rev.compile(r"^\s*\d+\.\s+[\d.]+\s*$")
    bare = [ln for ln in screen_text.splitlines() if RAW.match(ln)]
    check(P, "no rendered option is a bare number", not bare,
          str(bare[:2]) + " - a user cannot tell what four of something is")


    check(P, "the starting configuration is said not to be a recommendation",
          "NOT a recommended architecture" in src)
    check(P, "and why it exists at all",
          "easier to read" in src or "easier to interpret" in src)


def main():
    print(LINE)
    print(" LANGUAGE QA")
    print(LINE)
    print("  The arithmetic is checked by nine other suites. Nothing checked")
    print("  the WORDS, and the words are what a reader takes away.\n")

    all_screens = screens()
    print(f"  {len(all_screens)} screens rendered.\n")

    hits = l01_forbidden(all_screens)
    for fn in (l16_philosophy, l02_canonical, l03_units, l04_why, l05_numbers_in_why,
               l06_unsupported, l07_metric_names, l08_deployment,
               l09_recommendation, l10_tutorial, l11_demo, l12_challenge,
               l13_validation, l14_help, l15_error):
        try:
            fn(all_screens)
        except Exception as exc:
            check(fn.__name__[:3].upper(), f"{fn.__name__} completes", False,
                  f"{type(exc).__name__}: {exc}")

    if hits:
        print("  FORBIDDEN WORD AUDIT")
        for name, line_no, text, word in hits[:12]:
            print(f"    {name} line {line_no}")
            print(f"      {text!r}")
            print(f"      {word!r} names a direction and nothing else -")
            print(f"      say what moved, by how much, and why.")

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

    print(f"\n{LINE}")
    print(" LANGUAGE QA REPORT")
    print(LINE)
    for pack in sorted(by_pack):
        good, total = by_pack[pack]
        label = PACK_NAMES.get(pack, pack)
        dots = "." * max(1, 34 - len(label))
        print(f"  {pack}  {label} {dots} "
              f"{'PASS' if good == total else 'FAIL'}  ({good}/{total})")

    passed = sum(1 for _, _, ok, _ in RESULTS if ok)
    print(f"\n  {passed} / {len(RESULTS)} checks")
    print(f"\n  ALLOWED USES OF OTHERWISE FORBIDDEN WORDS")
    for phrase, why in ALLOWED_USES.items():
        print(f"    {phrase:<18s}{why}")
    print(f"\n  These are listed rather than argued case by case, so the list")
    print(f"  cannot grow without somebody reading it. A blanket ban would")
    print(f"  force worse writing and would be obeyed by replacing a clear")
    print(f"  word with a clumsy one.")
    print(LINE)
    print(f"  {'PASS' if passed == len(RESULTS) else 'FAIL'}")
    print(LINE)
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
