"""
tests_docs.py - the documentation audit

WHY THIS SUITE WAS WRITTEN BEFORE THE DOCUMENTS
===============================================
An inspection of the existing README found defects that were not writing
problems. They were EXECUTABLE defects: two exercises told a student to work
on applications called `ondevice_llm` and `automotive`, neither of which
exists. A student following the document gets a KeyError.

Every one of those sentences was true when it was written. That is the point.
Fixing the prose without a check produces a document that is correct today and
wrong in three releases, and nobody will notice until a student does.

So the audit comes first, and the documents are then written to pass it.

WHAT IT CHECKS
--------------
    version         product, engine and release agree everywhere
    menu            documented modes exist, and every mode is documented
    entities        every application, metric and function named exists
    examples        every documented example RUNS
    terminology     no retired term, no unquantified adjective
    features        nothing claimed that is not implemented
    method          documented formulas match the implementation
    validation      categories in prose, counts generated

A REGISTRY, NOT A REGULAR EXPRESSION
------------------------------------
The audit compares docs_manifest.json against the code registries. Scanning
prose is kept as a secondary safeguard, because it is fragile in both
directions: it misses a claim phrased unusually, and it fails on a sentence
that merely mentions a word. Where prose IS scanned, the check says so.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, ".")

LINE = "=" * 84
RESULTS = []
MANIFEST = "docs_manifest.json"


def check(pack, name, cond, detail=""):
    RESULTS.append((pack, name, bool(cond), detail))


def load_manifest():
    with open(MANIFEST, encoding="utf-8") as fh:
        return json.load(fh)


def read(path):
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as fh:
        return fh.read()


# ==============================================================================
# D1 - the registry itself must be honest
# ==============================================================================

def d1_registry(man):
    P = "D1"
    import ppact
    from ppact import modes, APPLICATION_LIBRARY
    from ppact.arch_classes import HOST_CONNECTIONS

    check(P, "the manifest states the product version",
          man["product_version"] == ppact.PRODUCT_VERSION,
          f"{man['product_version']} against {ppact.PRODUCT_VERSION}")
    check(P, "and the engine version",
          man["engine_version"] == ppact.__version__,
          f"{man['engine_version']} against {ppact.__version__}")
    check(P, "the modes it lists are the modes that exist",
          man["public_modes"] == [m.title for m in modes.MODES],
          str(man["public_modes"]))
    for key in man["application_keys_used"]:
        check(P, f"application {key!r} exists", key in APPLICATION_LIBRARY,
              "a document naming an application that does not exist gives a "
              "student a KeyError")
    check(P, "the host connections it calls informational are the real ones",
          set(man["informational_only_features"]["Host connection"])
          == {k for k, _, _ in HOST_CONNECTIONS})
    check(P, "no validation COUNT appears in the registry",
          not any(re.search(r"\d{2,}", str(v))
                  for k, v in man.items()
                  if k == "validation_categories"),
          "counts go stale; categories do not")


def d1_metrics(man):
    P = "D1"
    from ppact import APPLICATION_LIBRARY, SystemConfig, evaluate_system
    m = evaluate_system(APPLICATION_LIBRARY["industrial_vision"],
                        SystemConfig("cortex_a78_x4", "npu_32x32", "LPDDR5",
                                     2)).metrics
    for name in man["metric_names_used"]:
        check(P, f"metric {name!r} is reported by the engine", name in m,
              "a document naming a metric the engine does not report is "
              "describing a different program")


# ==============================================================================
# D2 - the documents exist and carry their sections
# ==============================================================================

def d2_sections(man):
    P = "D2"
    for doc, sections in man["documents"].items():
        text = read(doc)
        check(P, f"{doc} exists", text is not None,
              "listed in the manifest and absent from the tree")
        if text is None:
            continue
        for section in sections:
            check(P, f"{doc}: has a section for {section!r}",
                  section.lower() in text.lower(),
                  "a document missing a required section is incomplete "
                  "rather than short")


# ==============================================================================
# D3 - terminology
# ==============================================================================

def d3_terminology(man):
    P = "D3"
    for doc in man["documents"]:
        text = read(doc)
        if text is None:
            continue
        low = text.lower()
        for term in man["retired_terms"]:
            # word boundary, not substring: "job latency" sits inside
            # "single-job latency" and the canonical name would fail itself
            hit = re.search(rf"(?<![-\w]){re.escape(term.lower())}\b", low)
            check(P, f"{doc}: retired term {term!r} is gone", hit is None,
                  f"at offset {hit.start() if hit else ''}")

        # An adjective is allowed WITH a figure and forbidden alone. Prose
        # scanning, and said to be: a sentence quantifying a comparison is
        # exactly what these documents should contain.
        for adj in man["unquantified_adjectives"]:
            for sentence in re.split(r"(?<=[.!?])\s+", text):
                if not re.search(rf"\b{adj}\b", sentence, re.I):
                    continue
                if re.search(r"\d", sentence):
                    continue
                if "`" in sentence or sentence.strip().startswith("|"):
                    continue    # a code span or a table row is not prose
                # A sentence DENYING a quality is the rule, not a breach of
                # it. "It is not a recommendation, not an optimal design"
                # is exactly the wording the project decided on, and a check
                # that cannot read a negation makes the correct sentence
                # impossible to write.
                if re.search(rf"\bnot\s+(?:an?\s+)?{adj}\b", sentence,
                             re.I):
                    continue
                check(P, f"{doc}: {adj!r} appears without a figure",
                      False, sentence.strip()[:80])


# ==============================================================================
# D4 - every documented example RUNS
# ==============================================================================

EXAMPLE_BLOCK = re.compile(r"```(?:python)?\n(.*?)```", re.S)


def d4_examples(man):
    P = "D4"
    from ppact import APPLICATION_LIBRARY

    for doc in man["documents"]:
        text = read(doc)
        if text is None:
            continue
        # any application key named in prose or code must exist
        for key in re.findall(r"`([a-z_]{4,})`", text):
            if key in APPLICATION_LIBRARY:
                continue
            looks_like_app = key in (
                "ondevice_llm", "automotive", "edge_vision", "server_llm",
                "smartphone", "datacentre")
            check(P, f"{doc}: `{key}` is not a retired application name",
                  not looks_like_app,
                  "two README exercises named applications that do not "
                  "exist; a student following them gets a KeyError")

        # executable blocks that are pure Python are executed
        for i, block in enumerate(EXAMPLE_BLOCK.findall(text)):
            body = block.strip()
            if not body.startswith(("from ppact", "import ppact")):
                continue
            try:
                exec(compile(body, f"{doc}#{i}", "exec"), {"__name__": "doc"})
                check(P, f"{doc}: example {i} runs", True)
            except Exception as exc:
                check(P, f"{doc}: example {i} runs", False,
                      f"{type(exc).__name__}: {exc}")


# ==============================================================================
# D5 - feature claims
# ==============================================================================

def d5_features(man):
    P = "D5"
    from ppact import menu, modes
    import ppact

    tasks = {fn.__name__ for _, fn in menu.TASKS}
    feature_backing = {
        "Reason Breakdown": "task_decide",
        "Measured Bar Charts": "task_designs",
        "Architecture Balance": "task_decide",
        "Design Review": "task_review",
        "What-if": "task_whatif",
        "Lessons": "task_lessons",
        "Challenges": "task_challenge",
        "Workspace": "task_workspace",
    }
    for feature in man["documented_features"]:
        backing = feature_backing.get(feature)
        check(P, f"the documented feature {feature!r} is implemented",
              backing in tasks,
              f"no task named {backing}; a documented feature that does not "
              f"exist is the worst kind of documentation defect")

    # anything called informational must be marked so wherever it is shown
    from ppact.arch_classes import HOST_CONNECTION_STATUS
    check(P, "the informational-only feature says so in the program",
          "does not use this" in HOST_CONNECTION_STATUS)
    for doc in man["documents"]:
        text = read(doc)
        if text is None or "Host connection" not in text:
            continue
        check(P, f"{doc}: host connection is marked informational",
              "informational" in text.lower(),
              "a parameter shown in a document reads as a parameter that "
              "was used")

    # no commercial product may be described as selectable
    VENDORS = ("NVIDIA", "Qualcomm", "Tenstorrent", "Furiosa", "RNGD",
               "Mobilint", "ARIES", "REGULUS", "Eagle-N", "Orin", "H100")
    for doc in man["documents"]:
        text = read(doc)
        if text is None:
            continue
        for v in VENDORS:
            check(P, f"{doc}: no product named {v!r} as a library item",
                  v not in text,
                  "commercial products validate the library; they never "
                  "become entries in it")


# ==============================================================================
# D6 - documented method matches the implementation
# ==============================================================================

def d6_method(man):
    P = "D6"
    text = read("METHODOLOGY.md")
    if text is None:
        check(P, "METHODOLOGY.md exists to check", False)
        return
    from ppact.system import SYSTEM_ANCHORS
    from ppact.visual import CLIP_HIGH, CLIP_LOW, BALANCE_NOTICE

    # the axis ranges must be the ones in the code
    for name, anchor in SYSTEM_ANCHORS.items():
        check(P, f"the documented range for {name} matches the code",
              f"{anchor.at_zero:g}" in text and f"{anchor.at_hundred:g}"
              in text,
              f"code says {anchor.at_zero:g} to {anchor.at_hundred:g}")
    check(P, "the clipping markers are documented as implemented",
          CLIP_HIGH in text and CLIP_LOW in text,
          f"{CLIP_HIGH} and {CLIP_LOW}")
    check(P, "the balance chart's stated limits are reproduced",
          "does not show physical values" in text,
          "the notice on screen and the notice in the methodology must be "
          "the same sentence")
    check(P, "the log normalisation is described",
          "log10" in text,
          "a formula that shapes every score belongs in the authoritative "
          "document even though it is hidden behind a keystroke on screen")

    # the latency decomposition terms
    from ppact.decide import LATENCY_TERMS
    for term, _, _ in LATENCY_TERMS:
        check(P, f"the decomposition term {term!r} is documented",
              term in text)


# ==============================================================================
# D7 - validation claims
# ==============================================================================

def d7_validation(man):
    P = "D7"
    readme = read("README.md")
    if readme is not None:
        # counts go stale; categories do not
        counts = re.findall(r"\b\d{3,}\s*(?:checks|tests|mutations)\b",
                            readme, re.I)
        check(P, "README carries no hard-coded validation count",
              not counts, str(counts[:3])
              + " - a count fixed in prose is wrong at the next release")
    for item in man["not_established"]:
        found = any(item.lower() in (read(d) or "").lower()
                    for d in man["documents"])
        check(P, f"{item!r} is stated somewhere as not established", found,
              "a document listing only what passed is an advertisement")

    report = read("VALIDATION_REPORT.txt")
    check(P, "a generated validation report ships", report is not None,
          "counts belong in a generated file, not in prose")
    if report:
        import ppact
        check(P, "the report names the release it belongs to",
              ppact.__version__ in report,
              "a stale report from an earlier build must not pass")
        check(P, "and when it was generated",
              re.search(r"\d{4}-\d{2}-\d{2}", report) is not None)
        for cat in man["validation_categories"][:5]:
            check(P, f"the report covers {cat!r}",
                  cat.lower() in report.lower())


# ==============================================================================
# D8 - the audit must catch a document it is shown
# ==============================================================================
#
# Every check above passes, which is what it should do and also exactly what
# an audit with a disabled check looks like. So each guard is shown input it
# must reject.
#
# WHY THIS IS A HARNESS AND NOT A SEQUENCE OF BLOCKS
# --------------------------------------------------
# The first version was nine blocks, each saving RESULTS, clearing it,
# running one control, restoring, and appending its own verdict. One block
# forgot to refresh the snapshot afterwards, so the NEXT block restored a
# stale copy and silently deleted the control's result.
#
# The consequence was worse than a missing check. That control was the one
# guarding NOT ESTABLISHED - the distinction this whole project is built on
# - and a mutation disabling it survived. The reported count of 186 was also
# wrong: 185 checks ran.
#
# So state capture, restoration, expected-failure identity and control
# accounting all happen HERE, once, and an individual control cannot omit
# any of them. It declares what to break and which rule must catch it.

RESTORE_NOTE = (
    "registered, executed and reported control counts must agree; a control "
    "whose result is discarded is a guard nobody is watching")



def _swap_file(paths, transform):
    """Rewrite one or more documents, run something, put them back.

    Takes a LIST because a claim can be made in several documents at once,
    and a control that edits one of them proves nothing: the rule is
    satisfied by the copies it did not touch. That is exactly what happened
    when EDUCATIONAL_VALIDATION.md was added and a control that had been
    reversing a claim in METHODOLOGY.md alone stopped catching anything.
    """
    if isinstance(paths, str):
        paths = [paths]
    originals = {p: (read(p) or "") for p in paths}

    def enter():
        for p, text in originals.items():
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(transform(text))

    def leave():
        for p, text in originals.items():
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(text)

    return enter, leave


def _temp_doc(man, sentence, tmpdir):
    """A manifest pointing at one deliberately broken document."""
    doc = os.path.join(tmpdir, "BROKEN.md")
    with open(doc, "w", encoding="utf-8") as fh:
        fh.write("# Broken\n\n" + sentence + "\n")
    bad = dict(man)
    bad["documents"] = {doc: []}
    return bad


# (label, rule to run, how to break the input, the substring that must
#  appear in the name of the check that catches it)
#
# The last field is the point. "The audit failed" is not enough: if a guard
# is disabled and a DIFFERENT rule happens to fail on the same input, the
# control would pass while the guard it was written for is dead.
def build_controls(man, tmpdir):
    return [
        ("dead application name", d4_examples,
         lambda: _temp_doc(man, "See the `ondevice_llm` example.", tmpdir),
         "retired application name", None),

        ("retired term", d3_terminology,
         lambda: _temp_doc(man, "The ships column shows status.", tmpdir),
         "retired term", None),

        ("unquantified adjective", d3_terminology,
         lambda: _temp_doc(man, "The larger engine is better here.", tmpdir),
         "without a figure", None),

        ("vendor product name", d5_features,
         lambda: _temp_doc(man, "Comparable to NVIDIA hardware.", tmpdir),
         "as a library item", None),

        ("version disagreement", d1_registry,
         lambda: {**man, "product_version": "99.9"},
         "states the product version", None),

        ("incomplete mode list", d1_registry,
         lambda: {**man, "public_modes": ["Quick Start"]},
         "modes it lists are the modes that exist", None),

        ("application key that does not exist", d1_registry,
         lambda: {**man, "application_keys_used": ["no_such_application"]},
         "exists", None),

        ("metric that the engine does not report", d1_metrics,
         lambda: {**man, "metric_names_used": ["Invented metric (ms)"]},
         "is reported by the engine", None),

        # A document that names Host connection without saying it is
        # informational. Added after a mutation disabling that guard
        # survived - the harness now reports a control-shaped hole instead
        # of hiding one.
        ("host connection described as if it were modelled", d5_features,
         lambda: _temp_doc(
             man, "Host connection selects PCIe Gen5 for this design.",
             tmpdir),
         "marked informational", None),

        ("hard-coded count in the README", d7_validation,
         lambda: man,
         "no hard-coded validation count",
         ("README.md", lambda t: t + "\n4905 checks pass.\n")),

        ("formula that contradicts the code", d6_method,
         lambda: man,
         "documented range",
         ("METHODOLOGY.md", lambda t: t.replace("20000", "12345"))),

        # --- the three NOT ESTABLISHED variants ------------------------
        #
        # This is the distinction the whole project rests on, and it is the
        # one whose guard was found dead. One variant is not enough: a
        # heading can be renamed, a section can be deleted, and a sentence
        # can be reversed, and all three would leave a reader believing
        # something had been established.
        ("NOT ESTABLISHED item absent from every document", d7_validation,
         lambda: {**man, "not_established": ["Something nobody wrote down"]},
         "not established", None),

        # A renamed HEADING is caught by the required-sections rule, not by
        # the item rule: the four items may still be named in README and
        # ABOUT, so the claim is still made - what is lost is the section a
        # reader is sent to. Attributing this to the wrong rule was my own
        # error, and it is exactly what expected-failure identity exists to
        # surface.
        ("NOT ESTABLISHED heading renamed", d2_sections,
         lambda: man, "section for 'Not established'",
         ("METHODOLOGY.md",
          lambda t: t.replace("Not established", "Not verified")
                     .replace("NOT ESTABLISHED", "NOT VERIFIED")
                     .replace("Measured hardware accuracy",
                              "Hardware accuracy notes"))),

        ("NOT ESTABLISHED section deleted", d7_validation,
         lambda: man, "not established",
         ("METHODOLOGY.md",
          lambda t: t.split("## Not established")[0])),

        ("a not-established claim reversed to established", d7_validation,
         lambda: man, "not established",
         (["METHODOLOGY.md", "DEFERRED.md"],
          lambda t: t.replace("Educational effectiveness",
                              "Educational value is established"))),
    ]


def d8_positive_controls(man):
    """Run every registered control through one path. Count them all."""
    P = "D8"
    import shutil
    import tempfile

    tmpdir = tempfile.mkdtemp(prefix="ppact_docs_")
    executed = 0
    reported = 0
    try:
        controls = build_controls(man, tmpdir)
        registered = len(controls)

        for label, rule, make_manifest, expect, swap in controls:
            outer = list(RESULTS)
            enter = leave = None
            if swap is not None:
                enter, leave = _swap_file(swap[0], swap[1])
            try:
                if enter:
                    enter()
                bad_man = make_manifest()
                RESULTS.clear()
                try:
                    rule(bad_man)
                except Exception as exc:
                    RESULTS.append((P, f"{label}: rule raised", False,
                                    f"{type(exc).__name__}: {exc}"))
                failures = [r for r in RESULTS if not r[2]]
                executed += 1
            finally:
                if leave:
                    leave()
                RESULTS.clear()
                RESULTS.extend(outer)

            matched = [r for r in failures if expect.lower() in r[1].lower()]
            check(P, f"the audit rejects a {label}", bool(matched),
                  f"caught by {[r[1][:40] for r in failures][:2]} - expected "
                  f"a check naming {expect!r}. A control satisfied by a "
                  f"different rule proves a different rule.")
            reported += 1

        # THE ACCOUNTING. This is what was missing: a control whose result
        # is discarded leaves no trace, and the count is the only thing that
        # notices.
        check(P, "every registered control executed",
              executed == registered, f"{executed} of {registered}")
        check(P, "and every executed control was reported",
              reported == executed, f"{reported} of {executed}")
        check(P, f"all {registered} controls are accounted for",
              registered == executed == reported, RESTORE_NOTE)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def main():
    print(LINE)
    print(" DOCUMENTATION AUDIT")
    print(LINE)
    print("  Fails when the documentation diverges from the program. Written")
    print("  BEFORE the documents, because every defect found in the old")
    print("  README was a sentence that had been true when it was written.\n")

    man = load_manifest()
    for fn in (d1_registry, d1_metrics, d2_sections, d3_terminology,
               d4_examples, d5_features, d6_method, d7_validation,
               d8_positive_controls):
        try:
            fn(man)
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
    labels = {"D1": "registry", "D2": "sections", "D3": "terminology",
              "D8": "positive controls",
              "D4": "examples run", "D5": "feature claims",
              "D6": "method", "D7": "validation claims"}
    for pack in sorted(by_pack):
        good, total = by_pack[pack]
        print(f"  {pack}  {labels.get(pack, pack):<22s}{good:>5d} / "
              f"{total:<6d}{'pass' if good == total else 'FAIL'}")
    print(f"\n  {passed} / {len(RESULTS)} checks")
    print(LINE)
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
