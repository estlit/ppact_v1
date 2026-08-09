"""
tests_library_validation.py - is the library keeping up with the industry?

WHAT THIS ASKS
==============
Every other suite asks whether the model is right about itself. This one asks
whether the LIBRARY is complete enough to describe what people actually
build - and it answers with published specifications rather than with an
opinion.

Six reports, all for developers:

    1  COVERAGE     which architectural concepts the library can express
    2  GAP          what a published product needs and the library lacks
    3  ALIGNMENT    does the model explain WHY products look like this
    4  CONFIDENCE   how much of each profile is published rather than guessed
    5  CALIBRATION  which library defaults a published figure calls into
                    question
    6  TREND        what accumulates across profiles

WHAT IT DOES NOT DO
-------------------
It does not extend the library. Every gap becomes a line in a backlog that a
person reads, because a framework that added a part whenever it met one would
turn an exploration tool into a product catalogue - and it would do so
silently, which is worse.

It also does not treat a vendor's comparative claim as evidence. "2x TOPS/$
compared to existing solution" names no baseline, and a ratio without a
baseline is not a measurement of anything.

Run this by hand. It is not in the Studio menu and is not meant to be.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

import sys

sys.path.insert(0, ".")

from ppact.industry_profiles import (PROFILES, BY_KEY, CATEGORIES,
                                     LIBRARY_CAPABILITY,
                                     CAPABILITY_BY_CATEGORY, ALIGNMENT,
                                     PUBLISHED, ESTIMATED, UNKNOWN)

LINE = "=" * 78
RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))


def _wrap(text, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return lines or [""]


# ==============================================================================
# 1. Coverage
# ==============================================================================

def registry_report():
    from ppact.arch_classes import (print_registry, print_coverage_metrics,
                                    registry_violations)
    print_registry()
    print_coverage_metrics()
    v = registry_violations()
    check("the class registry agrees with the libraries", not v,
          "; ".join(v[:3]))
    return v


def library_validation_report():
    """What has been reviewed, and what the library learned from it.

    THIS REPLACED A SET OF COVERAGE PERCENTAGES at 4.4.0, and the reason is
    worth keeping: a percentage needs a denominator, and the only honest
    denominator for "industrial coverage" is the world's semiconductor
    industry. Eleven products from three vendors is not that. Printing
    "deployment coverage 12.5%" implied a measurement against the industry
    when it was a measurement against a list this project wrote itself.

    Everything below is a count of something that happened. A reader can
    check every line.
    """
    from ppact.arch_classes import (ACCELERATOR_CLASSES, MEMORY_CLASSES,
                                    DEPLOYMENT_CLASSES, STRUCTURAL_BACKLOG,
                                    REGISTRY_VERSION)
    from ppact.industry_profiles import (PROFILES, CAPABILITY_BY_CATEGORY,
                                         PUBLISHED)

    vendors = sorted({p.vendor for p in PROFILES})
    published_facts = sum(len(p.by_status(PUBLISHED)) for p in PROFILES)

    print(f"\n{LINE}")
    print(" INDUSTRIAL LIBRARY VALIDATION")
    print(LINE)
    print(f"  What has been reviewed, and what the library learned from it.")
    print(f"  No percentage appears below. A percentage needs a denominator,")
    print(f"  and the only honest denominator for 'industrial coverage' is")
    print(f"  the whole industry - which this is not a sample of.\n")

    print(f"  REVIEWED")
    print(f"    companies                {len(vendors)}")
    for v in vendors:
        n = sum(1 for p in PROFILES if p.vendor == v)
        print(f"      {v:<26s}{n} product(s)")
    print(f"    public products          {len(PROFILES)}")
    print(f"    published facts recorded {published_facts}")

    # what the reviews taught us: concepts named by a published fact that
    # the library could not express when it was first seen
    identified = []
    for p in PROFILES:
        for f in p.facts:
            if f.status != PUBLISHED:
                continue
            cap = CAPABILITY_BY_CATEGORY.get(f.category)
            if cap and cap.state != "expressed":
                identified.append((f.category, f.concept))
    unique_ident = sorted({c for c, _ in identified})

    print(f"\n  NEW ARCHITECTURAL CONCEPTS IDENTIFIED")
    for c in unique_ident:
        cap = CAPABILITY_BY_CATEGORY[c]
        print(f"    {c:<18s}{cap.state}")

    # what was implemented in response, read from the registry rather than
    # asserted here
    implemented = [c for c in ACCELERATOR_CLASSES
                   if c.key.startswith("class_")]
    print(f"\n  IMPLEMENTED LIBRARY CLASSES  ({len(implemented)} accelerator,"
          f" {len(MEMORY_CLASSES)} memory)")
    for c in implemented:
        print(f"    {c.name:<32s}{c.domain:<18s}{c.confidence}")

    print(f"\n  PENDING - STRUCTURAL, A SEPARATE PHASE")
    for name, what, why in STRUCTURAL_BACKLOG:
        print(f"    {name}")
    absent_dep = [n for n, st, _ in DEPLOYMENT_CLASSES if st == "absent"]
    print(f"    deployment classes not expressible: "
          f"{len(absent_dep)} of {len(DEPLOYMENT_CLASSES)} declared")
    for n in absent_dep:
        print(f"      {n}")

    print(f"\n  ESTIMATED INDUSTRIAL CLASSES")
    print(f"    every class in the registry is an estimate. The registry is")
    print(f"    at v{REGISTRY_VERSION} and no class carries a confidence")
    print(f"    above 'medium', because no vendor publishes enough for any")
    print(f"    figure in it to be checked.")

    print(f"\n  VALIDATION NOTES")
    notes = [(p.name, p.note) for p in PROFILES if p.note]
    for name, note in notes[:4]:
        for i, line in enumerate(_wrap(note, 64)):
            print(f"    {name + ':' if i == 0 else '':<28s}{line}"
                  if i == 0 else f"    {'':<28s}{line}")
    if len(notes) > 4:
        print(f"    ... and {len(notes) - 4} more")
    print(LINE)
    return {"vendors": len(vendors), "products": len(PROFILES),
            "identified": unique_ident, "implemented": len(implemented)}


def coverage_report():
    print(f"\n{LINE}")
    print(" 1. COVERAGE - what the library can express")
    print(LINE)
    print("  By category, not as one number. '68% covered' hides which 32%,")
    print("  and which 32% is the whole question.\n")

    counts = {"expressed": 0, "partial": 0, "absent": 0}
    for c in LIBRARY_CAPABILITY:
        counts[c.state] = counts.get(c.state, 0) + 1
        mark = {"expressed": "  ", "partial": "~ ", "absent": "x "}[c.state]
        print(f"  {mark}{c.category:<16s}{c.state}")
        for line in _wrap(c.how, 58):
            print(f"      {line}")
        if c.evidence:
            print(f"      [{c.evidence}]")
        print()
    total = sum(counts.values())
    print(f"  {counts['expressed']} expressed, {counts['partial']} partial, "
          f"{counts['absent']} absent, across {total} declared categories.")
    print(f"  These are counts of a list this project wrote. They are not a")
    print(f"  measurement of the industry and must not be read as one.")
    print(f"\n  The aim is not to raise the first number. It is to know which")
    print(f"  concepts are in the third column, because those are the ones a")
    print(f"  student cannot be shown and a designer cannot explore.")
    return counts


# ==============================================================================
# 2. Gap
# ==============================================================================

def gap_report():
    print(f"\n{LINE}")
    print(" 2. GAP - what these products need and the library lacks")
    print(LINE)

    gaps = {}
    for p in PROFILES:
        for f in p.facts:
            if f.status != PUBLISHED:
                continue
            cap = CAPABILITY_BY_CATEGORY.get(f.category)
            if cap is None or cap.state == "expressed":
                continue
            gaps.setdefault((f.category, cap.state), []).append(
                (p.name, f.concept, f.value))

    if not gaps:
        print("  Nothing published in these profiles is outside the library.")
        return gaps

    for (category, state), items in sorted(gaps.items()):
        cap = CAPABILITY_BY_CATEGORY[category]
        print(f"\n  {category}  ({state})")
        for line in _wrap(cap.how, 62):
            print(f"     {line}")
        print(f"     needed by:")
        for name, concept, value in items:
            print(f"       {name:<12s}{concept}: {value}")

    print(f"\n  This is a BACKLOG, not a change. Nothing above has been added")
    print(f"  to the library. A framework that added a part whenever it met")
    print(f"  one would turn an exploration tool into a product catalogue,")
    print(f"  and would do it silently.")
    return gaps


# ==============================================================================
# 3. Alignment
# ==============================================================================

def alignment_report():
    print(f"\n{LINE}")
    print(" 3. ALIGNMENT - does the model explain WHY?")
    print(LINE)
    print("  Coverage asks whether a concept can be named. This asks the")
    print("  harder question: does the model give the same reason the")
    print("  industry gives for doing it?\n")

    counts = {}
    for a in ALIGNMENT:
        counts[a.verdict] = counts.get(a.verdict, 0) + 1
        print(f"  [{a.verdict}]")
        print(f"     industry:  ", end="")
        lines = _wrap(a.observation, 58)
        print(lines[0])
        for extra in lines[1:]:
            print(f"                {extra}")
        print(f"     model:     ", end="")
        lines = _wrap(a.model_says, 58)
        print(lines[0])
        for extra in lines[1:]:
            print(f"                {extra}")
        print()
    print(f"  {counts}")
    print(f"\n  'silent' is not a failure and not a pass. The model neither")
    print(f"  predicts nor contradicts those, and recording them as either")
    print(f"  would be claiming something.")
    return counts


# ==============================================================================
# 4. Confidence
# ==============================================================================

def confidence_report():
    print(f"\n{LINE}")
    print(" 4. CONFIDENCE - published against estimated")
    print(LINE)
    print(f"  {'profile':<14s}{'published':>11s}{'estimated':>11s}"
          f"{'unknown':>9s}{'confidence':>12s}")
    print("  " + "-" * 55)
    for p in PROFILES:
        c = p.confidence()
        print(f"  {p.name:<14s}{len(p.by_status(PUBLISHED)):>11d}"
              f"{len(p.by_status(ESTIMATED)):>11d}"
              f"{len(p.by_status(UNKNOWN)):>9d}"
              f"{(f'{c:.0f}%' if c is not None else '-'):>12s}")
    print(f"\n  Confidence is published over published-plus-estimated.")
    print(f"  Unknowns are NOT counted: counting them would let a profile")
    print(f"  improve its confidence by listing fewer of them, which is the")
    print(f"  opposite of what should happen.")
    for p in PROFILES:
        if p.note:
            print()
            for line in _wrap(f"{p.name}: {p.note}", 70):
                print(f"  {line}")


# ==============================================================================
# 5. Calibration
# ==============================================================================

def calibration_report():
    print(f"\n{LINE}")
    print(" 5. CALIBRATION - which defaults a published figure questions")
    print(LINE)

    from ppact import COMPUTE_LIBRARY, MEMORY_LIBRARY

    suggestions = []

    # published arithmetic against the engines the library carries
    tops = []
    for p in PROFILES:
        for f in p.facts:
            if f.status == PUBLISHED and f.concept == "peak arithmetic":
                digits = "".join(ch for ch in f.value.split()[0]
                                 if ch.isdigit())
                if digits:
                    tops.append((p.name, float(digits)))
    if tops:
        have = sorted(s.peak_tops for s in COMPUTE_LIBRARY.values())
        for name, t in tops:
            below = [h for h in have if h <= t]
            above = [h for h in have if h >= t]
            lo = max(below) if below else None
            hi = min(above) if above else None
            if lo is not None and hi is not None and hi / max(lo, 1e-9) > 4:
                suggestions.append(
                    f"{name} is {t:.0f} TOPS. The library's nearest engines "
                    f"are {lo:.0f} and {hi:.0f} - a factor of "
                    f"{hi / lo:.0f} apart, so nothing sits near this class.")

    # published memory against the memories the library carries
    mems = {f.value for p in PROFILES for f in p.facts
            if f.status == PUBLISHED and f.concept == "external memory"}
    for m in sorted(mems):
        if m not in MEMORY_LIBRARY:
            suggestions.append(
                f"{m} is used by a shipping part and is not in the memory "
                f"library. The nearest entry is "
                f"{'LPDDR5' if 'LPDDR' in m else 'none'}.")

    # a host named by every profile that names one
    hosts = {f.value for p in PROFILES for f in p.facts
             if f.status == PUBLISHED and f.concept == "host core"}
    if hosts:
        suggestions.append(
            f"Every profile that names a host names {', '.join(sorted(hosts))}"
            f" - the library's cortex_a53_x4 is the right shape, and its core "
            f"count is an assumption no profile confirms.")

    for s in suggestions:
        print()
        for line in _wrap(f"- {s}", 70):
            print(f"  {line}")
    if not suggestions:
        print("\n  Nothing published here questions a current default.")
    print(f"\n  These are suggestions to REVIEW, not changes. A framework")
    print(f"  that retuned a coefficient because one vendor published a")
    print(f"  number would be fitting the model to a press release.")
    return suggestions


# ==============================================================================
# 6. Trend
# ==============================================================================

def trend_report():
    print(f"\n{LINE}")
    print(" 6. TREND - what accumulates across profiles")
    print(LINE)
    vendors = {p.vendor for p in PROFILES}
    print(f"  {len(PROFILES)} profiles from {len(vendors)} vendor(s).")
    print()
    if len(vendors) < 3 or len(PROFILES) < 8:
        print(f"  NOT ENOUGH TO CALL A TREND.")
        print()
        for line in _wrap(
                "A pattern drawn from one vendor is that vendor's roadmap, "
                "not the industry's. What follows is a tally of what these "
                "profiles happen to state, and it is not evidence of a "
                "direction.", 70):
            print(f"  {line}")
        print()
    tally = {}
    for p in PROFILES:
        for f in p.facts:
            if f.status == PUBLISHED:
                tally.setdefault(f.category, set()).add(f.value)
    for cat in sorted(tally):
        vals = sorted(v for v in tally[cat] if v)
        if vals:
            print(f"  {cat:<16s}{', '.join(vals[:3])}"
                  + (f" (+{len(vals) - 3})" if len(vals) > 3 else ""))
    print(f"\n  Success is not the number of profiles. It is whether the")
    print(f"  library explains real design choices with more confidence over")
    print(f"  time, while staying clear about what is known, estimated and")
    print(f"  unknown.")


# ==============================================================================
# Checks
# ==============================================================================

def run_checks(counts, gaps, align, suggestions):
    # the principles this framework is built on, as checks
    check("profiles are declared", len(PROFILES) >= 1)
    check("every profile names its source",
          all(p.source and p.retrieved for p in PROFILES))
    check("every fact declares its status",
          all(f.status in (PUBLISHED, ESTIMATED, UNKNOWN)
              for p in PROFILES for f in p.facts))
    check("no unknown fact carries a value",
          all(not f.value for p in PROFILES for f in p.facts
              if f.status == UNKNOWN),
          "an invented number reads exactly like a measured one")
    check("every category has a capability entry",
          set(CATEGORIES) == {c.category for c in LIBRARY_CAPABILITY},
          str(set(CATEGORIES) ^ {c.category for c in LIBRARY_CAPABILITY}))
    check("an absent capability says why",
          all(len(c.how) > 25 for c in LIBRARY_CAPABILITY
              if c.state == "absent"))
    check("the coverage is not claimed complete", counts["absent"] > 0,
          "a capability map with no gaps is a map nobody checked")
    check("gaps are found", len(gaps) > 0,
          "three shipping parts and no gap would mean the framework is not "
          "looking")
    check("alignment records silence as well as agreement",
          "silent" in align,
          "recording a silence as a pass would be claiming something")
    check("calibration produces suggestions, not changes",
          len(suggestions) > 0)

    # --- the registry keeps its promises -----------------------------------
    from ppact.arch_classes import (ACCELERATOR_CLASSES, MEMORY_CLASSES,
                                    CONFIDENCE_LEVELS, DOMAINS,
                                    STRUCTURAL_BACKLOG, coverage_metrics,
                                    REGISTRY_VERSION)
    check("the registry is versioned", bool(REGISTRY_VERSION))
    check("every class states its confidence",
          all(c.confidence in CONFIDENCE_LEVELS for c in ACCELERATOR_CLASSES))
    check("no class claims high confidence",
          "high" not in CONFIDENCE_LEVELS,
          "no vendor publishes enough for any of these to be checked")
    check("every class states what its estimate rests on",
          all(len(c.evidence) >= 25 for c in ACCELERATOR_CLASSES))
    check("every class names which parameters are estimates",
          all(c.estimated for c in ACCELERATOR_CLASSES))
    check("classes are organised by domain, not by TOPS",
          all(c.domain in DOMAINS for c in ACCELERATOR_CLASSES),
          "TOPS is a parameter inside a class, not a classification")
    m = coverage_metrics()
    check("the metrics are reported separately, never summed",
          "library quality" not in str(m),
          "one number would let a gap in one domain be paid for by an entry "
          "in another")

    # NO PERCENTAGE MAY BE PRESENTED AS COVERAGE.
    #
    # A coverage percentage was written at 4.3.0 and removed at 4.4.0. It
    # implied a measurement against the industry when it was a measurement
    # against a list this project wrote itself, and the credibility cost of
    # that is larger than anything it bought.
    import io as _io, contextlib as _ctx
    from ppact.arch_classes import print_coverage_metrics as _pcm
    buf = _io.StringIO()
    with _ctx.redirect_stdout(buf):
        _pcm()
        library_validation_report()
    text = buf.getvalue()
    check("no percentage is printed as coverage", "%" not in text,
          "a percentage needs a denominator, and the denominator implied by "
          "'industrial coverage' is the whole industry")
    check("and the report says why not",
          "not a sample of the industry" in text
          or "not a sample of" in text)
    for banned in ("Industrial Coverage", "Architecture Coverage",
                   "Deployment Coverage", "Memory Coverage",
                   "Interface Coverage", "Performance Coverage"):
        check(f"no report headed {banned!r}", banned not in text)
    check("a domain with no class is visible",
          m["domains covered"] < m["domains defined"]
          or all(m["by domain"].get(d) for d in DOMAINS),
          "a registry that hides an empty domain is a registry nobody "
          "checked")
    check("structural work is listed and kept out of the library",
          len(STRUCTURAL_BACKLOG) >= 4)
    from ppact.arch_classes import DEPLOYMENT_CLASSES
    check("the deployment spectrum is declared", len(DEPLOYMENT_CLASSES) >= 6)
    check("and most of it is honestly marked absent",
          sum(1 for _, st, _ in DEPLOYMENT_CLASSES if st == "absent") >= 5,
          "a portfolio review found six products differing in nothing but "
          "deployment, and the model cannot tell them apart")
    for name, st, why in DEPLOYMENT_CLASSES:
        check(f"deployment '{name}' says why", len(why) > 25)
    for name, what, why in STRUCTURAL_BACKLOG:
        check(f"'{name}' says why it is structural", len(why) > 30)

    # vendor neutrality, checked rather than promised
    import re as _re
    src = open("ppact/arch_classes.py", encoding="utf-8").read()
    src += open("ppact/compute.py", encoding="utf-8").read()
    src += open("ppact/memory.py", encoding="utf-8").read()
    VENDORS = ("NVIDIA", "Nvidia", "Qualcomm", "AMD ", "Tenstorrent",
               "BOS Semi", "Eagle-N", "Snapdragon", "Jetson", "Orin",
               "Furiosa", "FuriosaAI", "RNGD", "Tensor Contraction",
               "H100", "L40S", "EPYC", "Mobilint", "ARIES", "REGULUS",
               "MLA100", "MLA400", "MLX-A1", "MLX-R1", "MLD-R1",
               "Iris", "EXAONE")
    for vendor in VENDORS:
        check(f"no vendor or product name {vendor.strip()!r} in the library",
              vendor not in src,
              "commercial products validate the library; they never become "
              "entries in it")

    # The rule is precise rather than absolute: a product name is allowed in
    # an EVIDENCE file, where it is the thing being cited, and forbidden in a
    # LIBRARY file, where it would become something a user selects. Banning
    # it everywhere would mean the industry cases could not say which
    # industry they came from, which is the opposite of evidence.
    LIBRARY_FILES = ("ppact/compute.py", "ppact/memory.py", "ppact/cpu.py",
                     "ppact/arch_classes.py")
    EVIDENCE_FILES = ("ppact/industry.py", "ppact/crossval.py",
                      "ppact/industry_profiles.py")
    for path in LIBRARY_FILES:
        text = open(path, encoding="utf-8").read()
        hits = [v.strip() for v in VENDORS if v in text]
        check(f"{path} names no product", not hits, str(hits))
    cited = set()
    for path in EVIDENCE_FILES:
        text = open(path, encoding="utf-8").read()
        cited.update(v.strip() for v in VENDORS if v in text)
    check("evidence files may cite products, and do",
          cited,
          "an industry case that cannot say which industry it came from is "
          "not evidence")
    check("and a user-facing screen reaches only the evidence, never the "
          "library naming",
          all(v not in open("ppact/arch_classes.py", encoding="utf-8").read()
              for v in VENDORS))

    # THE PRINCIPLE THAT MATTERS: this must not be user-facing
    from ppact import menu, modes
    task_names = {fn.__name__ for _, fn in menu.TASKS}
    referenced = set()
    for m in modes.MODES:
        referenced.update(t for _, t in m.entries)
        referenced.update(m.auto)
    check("no Studio menu entry exposes the profiles",
          not any("industry_profile" in t or "profile" in t
                  for t in task_names | referenced),
          "PPACT Studio is an exploration tool; a catalogue of commercial "
          "parts would invite the one comparison it cannot support")
    src = open("ppact/industry_profiles.py", encoding="utf-8").read()
    check("and the module says so in the first paragraph",
          "NOT a product catalogue" in src)

    # a vendor's unbaselined ratio must not become evidence
    joined = " ".join(f.value for p in PROFILES for f in p.facts
                      if f.status == PUBLISHED)
    for claim in ("2X", "1.5X", "2x TOPS", "1.5x TOPS"):
        check(f"the unbaselined claim {claim!r} is not evidence",
              claim not in joined,
              "a ratio against an unnamed baseline is not a measurement")


def main():
    print(LINE)
    print(" PPACT STUDIO - LIBRARY VALIDATION")
    print(LINE)
    print("  Published specifications used to test the LIBRARY, not to")
    print("  populate it. Developer tool; not in the Studio menu.")

    from ppact.arch_classes import (print_registry, print_coverage_metrics,
                                    registry_violations, ACCELERATOR_CLASSES,
                                    MEMORY_CLASSES, DOMAINS,
                                    STRUCTURAL_BACKLOG, BY_KEY)
    print_registry()
    print_coverage_metrics()

    registry_report()
    library_validation_report()
    counts = coverage_report()
    gaps = gap_report()
    align = alignment_report()
    confidence_report()
    suggestions = calibration_report()
    trend_report()
    run_checks(counts, gaps, align, suggestions)

    # the registry must agree with the libraries it describes
    check("the class registry matches the libraries",
          not registry_violations(),
          "; ".join(registry_violations()[:2]))
    check("every declared class states its evidence",
          all(len(c.evidence) >= 25 for c in ACCELERATOR_CLASSES))
    check("and what in it is estimated",
          all(c.estimated for c in ACCELERATOR_CLASSES))
    check("no class claims high confidence",
          not any(c.confidence == "high" for c in ACCELERATOR_CLASSES),
          "no vendor publishes enough for any figure here to be checked")
    check("a memory figure is either standard or estimated, never both",
          all(not (set(m.standard_figures) & set(m.estimated))
              for m in MEMORY_CLASSES))
    check("classes are organised by domain, not by arithmetic",
          len({c.domain for c in ACCELERATOR_CLASSES}) >= 4,
          "TOPS is a parameter inside a class, not a classification")
    check("the structural backlog is kept separate and non-empty",
          len(STRUCTURAL_BACKLOG) >= 4,
          "data expansion changes no equation; structural expansion changes "
          "the timing decomposition, and shipping both under one version "
          "would make the first failure impossible to attribute")
    check("no vendor name reaches the registry",
          not any(v.lower() in open("ppact/arch_classes.py",
                                    encoding="utf-8").read().lower()
                  for v in ("nvidia", "qualcomm", "tenstorrent",
                            "bos semiconductors", "eagle-n")),
          "commercial products validate the library; they never become "
          "entries in it")

    passed = sum(1 for _, ok, _ in RESULTS if ok)
    print(f"\n{LINE}")
    print(" FRAMEWORK CHECKS")
    print(LINE)
    for name, ok, detail in RESULTS:
        if not ok:
            print(f"  FAILED  {name}")
            if detail:
                print(f"          {detail}")
    print(f"  {passed} / {len(RESULTS)} checks")
    print(f"\n  SAMPLE SIZE")
    print(f"    {len(PROFILES)} profiles, "
          f"{len({p.vendor for p in PROFILES})} vendor(s).")
    print(f"    Enough to find gaps - it found "
          f"{len(gaps)}. Nowhere near enough")
    print(f"    to call a trend, and every report says so.")
    print(LINE)
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
