"""
tests_questions.py - can a user answer the question they are shown?

WHY THIS SUITE WAS WRITTEN BEFORE THE QUESTIONS WERE FIXED
==========================================================
A user was shown `Memory packages [1]:` followed by `1. 1  2. 2  3. 4  4. 8`
and could not tell what they were choosing. Eleven prompts in the design flow
had the same shape.

Fixing eleven prompts by hand produces eleven prompts that are clear today.
The twelfth will be written the way the eleven used to be, because nothing
holds it to a standard. So the standard is a suite, and it is written first.

WHAT IT CHECKS
--------------
    Q1  registry      every question is defined once, completely
    Q2  clarity       a name, an explanation, and what the choice affects
    Q3  options       every option carries an engineering label, not a bare
                      number
    Q4  effect        score-only and model-changing are distinguished, in
                      words, in the prompt
    Q5  terminology   professional terms, used consistently, defined once
    Q6  invalid input actionable guidance naming the default
    Q7  coverage      no user-facing prompt bypasses the registry

WHAT IT CANNOT CHECK
--------------------
Whether the explanation is any good. A sentence can satisfy every rule here
and still leave a reader none the wiser. This suite makes an unclear question
impossible to ship silently; it does not make a clear one.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

import re
import sys

sys.path.insert(0, ".")

LINE = "=" * 84
RESULTS = []


def check(pack, name, cond, detail=""):
    RESULTS.append((pack, name, bool(cond), detail))


# The prompts a user meets in the design flow. Every one of these must come
# from the registry - the list is the coverage requirement, not a snapshot of
# what happens to exist.
REQUIRED_QUESTIONS = (
    "application",
    "host_processor",
    "accelerator_class",
    "memory_type",
    "memory_unit_count",
    "bandwidth_utilisation",
    "process_node",
    "preprocessing_location",
    "offload_handoff",
    "precision",
    "design_priority",
)

# Words that must not appear as a user-facing parameter name. Each is an
# internal field, and a user meeting it is being shown the source code.
INTERNAL_NAMES = ("memory_devices", "work_split", "alternative_share",
                  "preprocessing_mode", "accel_node", "soc_node",
                  "compute", "cpu", "n_mem", "pmode", "prec")

# Simplified wording this platform does not use. Professional terminology is
# the policy; the objection is not to short words but to imprecise ones.
BANNED_WORDING = ("fast cpu", "big memory", "better accelerator",
                  "how many memories", "which cpu", "speed",
                  "faster chip", "good design")


def q1_registry():
    P = "Q1"
    from ppact import questions as Q

    check(P, "the registry is populated", len(Q.REGISTRY) > 0,
          "no question is defined; every prompt is still written where it "
          "is used")
    missing = [k for k in REQUIRED_QUESTIONS if k not in Q.REGISTRY]
    check(P, "every question in the design flow is registered", not missing,
          f"missing: {', '.join(missing)}")
    check(P, "and the registry is internally consistent",
          not Q.question_violations(),
          "; ".join(Q.question_violations()[:3]))


def q2_clarity():
    P = "Q2"
    from ppact import questions as Q

    for key, raw in sorted(Q.REGISTRY.items()):
        # Resolved, as a screen would see it. Judging the unresolved
        # definition reports "the default is not a real option" for every
        # question whose options come from a library - which is a fault in
        # the check, not in the question.
        q = raw.resolved()
        check(P, f"{key}: has a user-facing parameter name",
              q.parameter_name and q.parameter_name[0].isupper(),
              q.parameter_name)
        check(P, f"{key}: the name is not an internal field",
              q.parameter_name.lower().replace(" ", "_")
              not in INTERNAL_NAMES,
              q.parameter_name)
        check(P, f"{key}: explains what the parameter represents",
              len(q.short_description) >= 40, q.short_description)
        check(P, f"{key}: states what the selection can affect",
              len(q.effect) >= 25 or q.score_only, q.effect)
        check(P, f"{key}: the default is a real option",
              1 <= q.default <= len(q.options))


def q3_options():
    P = "Q3"
    from ppact import questions as Q

    for key, raw in sorted(Q.REGISTRY.items()):
        q = raw.resolved()
        for opt in q.options:
            label = opt.label.strip()
            check(P, f"{key}: option {opt.value!r} is not a bare number",
                  not re.fullmatch(r"[\d.]+", label),
                  f"{label!r} - a user cannot tell what four of something is")
            check(P, f"{key}: option {opt.value!r} carries a unit or a name",
                  len(label) >= 3, label)


def q4_effect():
    P = "Q4"
    from ppact import questions as Q

    for key, raw in sorted(Q.REGISTRY.items()):
        q = raw.resolved()
        rendered = "\n".join(Q.render_question(q))
        norm = " ".join(rendered.split())
        if q.score_only:
            check(P, f"{key}: says it changes the score only",
                  " ".join(Q.SCORE_ONLY_NOTE.split()) in norm,
                  "a user must never have to guess whether a choice changed "
                  "the design or only the marking")
            check(P, f"{key}: and claims no physical effect",
                  not q.affected_metrics)
        else:
            check(P, f"{key}: says it changes the modeled configuration",
                  " ".join(Q.MODEL_CHANGING_NOTE.split()) in norm)
            check(P, f"{key}: and names what it affects",
                  bool(q.affected_metrics), str(q.affected_metrics))

    # at least one of each must exist, or the distinction is untested
    score_only = [q for q in Q.REGISTRY.values() if q.score_only]
    model = [q for q in Q.REGISTRY.values() if not q.score_only]
    check(P, "both kinds of question exist",
          score_only and model,
          f"{len(score_only)} score-only, {len(model)} model-changing")


def q5_terminology():
    P = "Q5"
    from ppact import questions as Q

    all_text = " ".join(
        " ".join(Q.render_question(q.resolved())).lower()
        for q in Q.REGISTRY.values())
    for banned in BANNED_WORDING:
        check(P, f"no simplified wording {banned!r}", banned not in all_text,
              "professional terminology is the policy; the objection is to "
              "imprecise words, not to short ones")

    # a term used in a question must be defined somewhere
    for key, q in sorted(Q.REGISTRY.items()):
        for term, meaning in q.terms:
            check(P, f"{key}: the term {term!r} is defined",
                  len(meaning) >= 30, meaning)

    check(P, "the glossary defines the recurring terms",
          len(Q.GLOSSARY) >= 5)
    for term, meaning in Q.GLOSSARY.items():
        check(P, f"glossary: {term!r} is a definition, not a gloss",
              len(meaning) >= 40, meaning)

    # ONE name per concept. The project already chose these.
    canonical = {"execution latency": ("response time", "job time"),
                 "host-active time": ("cpu time", "host time")}
    for good, bad_names in canonical.items():
        for bad in bad_names:
            check(P, f"{bad!r} is not used for {good!r}",
                  bad not in all_text)


def q6_invalid():
    P = "Q6"
    from ppact import questions as Q

    for key, raw in sorted(Q.REGISTRY.items()):
        q = raw.resolved()
        lines = Q.invalid_message(q, "6")
        text = " ".join(lines)
        check(P, f"{key}: the rejection names what was entered",
              "'6'" in text or '"6"' in text, text[:60])
        check(P, f"{key}: lists the accepted numbers",
              "option numbers" in text, text[:60])
        # The rule changed with the policy. An engineering question has no
        # default, so there is nothing for Enter to do and promising
        # otherwise would be false. What must be said is that a choice is
        # required, and where the help is.
        if q.requires_explicit_choice:
            check(P, f"{key}: says an explicit choice is required",
                  "H for additional details" in text,
                  "no default exists, so the refusal must not offer one")
            check(P, f"{key}: does not offer a default that is not there",
                  "Press Enter to keep" not in text,
                  "promising a default a question does not have is worse "
                  "than having one")
        else:
            check(P, f"{key}: and says what Enter does",
                  "Press Enter" in text and q.default_option().label in text)
        check(P, f"{key}: and is not just 'Invalid input'",
              len(text.split()) >= 12)


def q9_no_direct_prompts():
    """A prompt written inline is a prompt nothing holds to the standard.

    Q7 checks that no prompt uses an internal field name. This checks
    something stronger and more durable: that the design flow does not build
    prompts at all. Without it, the twelfth question gets written the way
    the first eleven were, passes Q7 because somebody chose a decent noun,
    and is back to a bare list under a name.
    """
    P = "Q9"
    import os
    import re as _re

    # Files that ask a user for an engineering value.
    #
    # This listed only game.py and menu.py, so challenge.py and lessons.py
    # went on printing "memory_devices" over a list of 1, 2, 4 and 8 while
    # Q9 reported zero direct prompts. A check that does not look at a file
    # says nothing about it - the fifth time that has come up here.
    # EVERY module, not a list somebody maintains.
    #
    # The list was game.py, menu.py, challenge.py, lessons.py. What-if
    # lives in decide.py and was never watched, so it went on printing
    # "1  2  4  8" for a memory question and "N28  N16  N7" for a process
    # node through four rounds of prompt migration while this check
    # reported zero direct prompts.
    #
    # A hand-kept list of governed files is the same failure one level up:
    # the sixth time a check has been shown to say nothing about a file it
    # does not read.
    GOVERNED = tuple(sorted(
        f for f in os.listdir("ppact")
        if f.endswith(".py") and f not in ("questions.py",)))
    offenders = []
    for fname in GOVERNED:
        path = os.path.join("ppact", fname)
        if not os.path.isfile(path):
            continue
        text = open(path, encoding="utf-8").read()
        for m in _re.finditer(r'(?<!def )\b_?ask\(\s*"([^"]{2,60})"', text):
            line_no = text[:m.start()].count("\n") + 1
            offenders.append(f"{fname}:{line_no} ask({m.group(1)!r})")
    # A raw configuration field name must not be shown as a question. The
    # registry has an entry for each of them.
    from ppact.questions import FIELD_QUESTION
    raw_named = []
    for fname in GOVERNED:
        path = os.path.join("ppact", fname)
        if not os.path.isfile(path):
            continue
        text = open(path, encoding="utf-8").read()
        if 'ask_fn(f"{field_name}"' in text or "ask_fn(field_name" in text:
            raw_named.append(f"{fname}: asks by internal field name")
    check(P, "no screen asks by a raw configuration field name",
          not raw_named, "; ".join(raw_named)
          + f" - {len(FIELD_QUESTION)} fields have registry entries with "
            f"professional names and labelled options")

    check(P, "the design flow builds no prompt of its own", not offenders,
          "; ".join(offenders[:4])
          + " - every question must come from ppact.questions")

    # and the registry path must actually be the one used
    # Only modules that ASK anything are required to ask through the
    # registry. Most modules ask nothing, and demanding a call from them
    # would report every library file as a defect.
    for fname in GOVERNED:
        text = open(os.path.join("ppact", fname), encoding="utf-8").read()
        prompts = bool(re.search(r"\bask_fn\(|\bask\(|\binput\(", text))
        # SUPPLYING AN ANSWER IS NOT ASKING A QUESTION.
        #
        # `text_capture` replaces `builtins.input` so a caller can hand
        # a task the answers it needs. The rule saw the name and read it
        # as a module prompting outside the registry, which is the
        # opposite of what it does - it exists so the questions the
        # registry asks can be answered from a browser.
        supplies_answers = ("builtins.input = " in text
                            and "def run_task(" in text)
        if not prompts or supplies_answers:
            continue
        check(P, f"{fname} asks through the registry",
              "ask_question(" in text or "ask_nav(" in text,
              "a module that prompts and never reaches the registry is "
              "asking some other way")


def q10_behaviour_unchanged():
    """Moving a prompt must not move a result.

    The whole claim of this migration is that it changed how a question
    READS. If the same answers produce a different design, it changed
    something else as well, and the claim is false.
    """
    P = "Q10"
    import dataclasses
    from ppact import questions as Q
    from ppact import APPLICATION_LIBRARY, SystemConfig, evaluate_system

    # every registered option must resolve to a value the engine accepts
    from ppact.compute import COMPUTE_LIBRARY
    from ppact.memory import MEMORY_LIBRARY
    from ppact.cpu import CPU_LIBRARY
    from ppact.process import NODE_LIBRARY

    pairs = (("accelerator_class", COMPUTE_LIBRARY),
             ("memory_type", MEMORY_LIBRARY),
             ("host_processor", CPU_LIBRARY),
             ("process_node", NODE_LIBRARY))
    for key, library in pairs:
        q = Q.get(key).resolved()
        bad = [o.value for o in q.options if o.value not in library]
        check(P, f"{key}: every option is a real library key", not bad,
              str(bad[:3]) + " - a selectable option the engine cannot use")
        check(P, f"{key}: and every library entry is selectable",
              len(q.options) == len(library),
              f"{len(q.options)} options against {len(library)} entries")

    # the count question must return the integers the engine expects
    count_q = Q.memory_unit_count_question("LPDDR5")
    values = [o.value for o in count_q.options]
    check(P, "the unit count returns integers", all(isinstance(v, int)
                                                    for v in values),
          str(values))

    # a design built from registry defaults must evaluate
    app = APPLICATION_LIBRARY["industrial_vision"]
    # An engineering question has no default now, so a design cannot be
    # assembled from defaults. The FIRST option is used instead, and the
    # difference is not pedantry: the first option is a choice this test
    # makes, where a default would have been a choice the program made.
    def _first(key):
        return Q.get(key).resolved().options[0].value

    cfg = SystemConfig(_first("host_processor"),
                       _first("accelerator_class"),
                       _first("memory_type"),
                       count_q.options[0].value)
    try:
        r = evaluate_system(app, cfg)
        check(P, "a design built from the first options evaluates",
              r.metrics.get("Latency (ms)") is not None)
    except Exception as exc:
        check(P, "a design built from the first options evaluates", False,
              f"{type(exc).__name__}: {exc}")

    # preprocessing and hand-off must return what the engine reads
    from ppact.preprocess import MODES as PMODES
    pq = Q.get("preprocessing_location").resolved()
    bad = [o.value for o in pq.options if o.value not in PMODES]
    check(P, "preprocessing options are real modes", not bad, str(bad))
    hq = Q.get("offload_handoff").resolved()
    check(P, "the hand-off question returns a boolean",
          all(isinstance(o.value, bool) for o in hq.options),
          str([o.value for o in hq.options]))


def q8_help_works():
    """The help handler, driven. Every accepted spelling, and the promise.

    "Type H for additional details" was printed on screen before any H
    handler existed. A reader who typed H and got "Enter a number from 1 to
    4" would learn the program does not mean what it says, which costs more
    than having offered no help at all.
    """
    P = "Q8"
    from ppact import questions as Q

    for key, raw in sorted(Q.REGISTRY.items()):
        q = raw.resolved()
        for spelling in Q.HELP_INPUTS:
            it = iter([spelling, "1"])
            out = []
            value = Q.ask_question(q, input_fn=lambda p, it=it: next(it),
                                   print_fn=out.append)
            text = "\n".join(out)
            check(P, f"{key}: {spelling!r} opens the help",
                  "additional details" in text,
                  "the prompt offers help; typing it must produce help")
            check(P, f"{key}: {spelling!r} returns to the same question",
                  text.count(q.parameter_name) >= 2,
                  "seeing the help must not skip the question")
            check(P, f"{key}: {spelling!r} does not change the answer",
                  value == q.options[0].value,
                  "the selection after help is the one the user then typed")

        # help then Enter: an engineering question must NOT resolve, and
        # must say why. A navigation question keeps its default.
        it = iter(["h", "", "1"])
        out = []
        value = Q.ask_question(q, input_fn=lambda p, it=it: next(it),
                               print_fn=out.append)
        if q.requires_explicit_choice:
            check(P, f"{key}: Enter after the help still selects nothing",
                  value == q.options[0].value
                  and "No selection was entered" in "\n".join(out))
        else:
            check(P, f"{key}: the default survives a visit to the help",
                  value == q.default_option().value)

        # help then a bad entry must give guidance, not a crash
        it = iter(["h", "999", "1"])
        out = []
        value = Q.ask_question(q, input_fn=lambda p, it=it: next(it),
                               print_fn=out.append)
        text = "\n".join(out)
        # The guidance is "here are the numbers, here is the help". It is
        # NOT "press Enter" - an engineering question has nothing for Enter
        # to do, and a refusal that offered one would be describing a
        # program that no longer exists.
        check(P, f"{key}: a bad entry after help is refused with guidance",
              "Invalid selection" in text
              and "option numbers" in text
              and "H for additional details" in text)
        check(P, f"{key}: and the question can still be answered",
              value == q.options[0].value)

    # WHAT THE HELP MUST CONTAIN
    for key, raw in sorted(Q.REGISTRY.items()):
        q = raw.resolved()
        text = "\n".join(Q.help_lines(q))
        norm = " ".join(text.split())
        if q.requires_explicit_choice:
            check(P, f"{key}: the help states that a choice is required",
                  "requires an explicit engineering choice" in text
                  or "no default" in text.lower(),
                  "the help must not describe a default the question does "
                  "not have")
        else:
            check(P, f"{key}: the help states the default",
                  q.default_option().label in text)
        check(P, f"{key}: and whether it changes the design or the score",
              " ".join((Q.SCORE_ONLY_NOTE if q.score_only
                        else Q.MODEL_CHANGING_NOTE).split()) in norm)
        check(P, f"{key}: and lists every option",
              all(o.label in text for o in q.options))
        if q.affected_metrics:
            check(P, f"{key}: and names the metrics it can move",
                  all(m in text for m in q.affected_metrics))
        for term, meaning in q.terms:
            check(P, f"{key}: and defines {term!r}", meaning[:40] in text)
        check(P, f"{key}: and says it is returning to the question",
              "Returning to the question" in text)

    # "ADDITIONAL DETAILS" MUST BE ADDITIONAL.
    #
    # The help used to repeat the question and add four metric names. A
    # reader who pressed H saw the same screen twice, which is why the
    # heading was questioned: it promised more than it delivered.
    for key, raw in sorted(Q.REGISTRY.items()):
        q = raw.resolved()
        help_text = "\n".join(Q.help_lines(q))
        question_text = "\n".join(Q.render_question(q))
        h_lines = {l.strip() for l in help_text.splitlines() if l.strip()}
        q_lines = {l.strip() for l in question_text.splitlines()
                   if l.strip()}
        new_lines = h_lines - q_lines
        check(P, f"{key}: the help adds material the question lacks",
              len(new_lines) >= 8,
              f"only {len(new_lines)} lines are new - a heading saying "
              f"'additional details' has to be additional")

        has_table = key in Q.DETAIL_TABLES
        says_none = "no further figures" in help_text
        check(P, f"{key}: figures are shown or their absence is stated",
              has_table != says_none,
              "a question with no figures says so rather than being "
              "padded; one with figures shows them")
        check(P, f"{key}: no detail table failed to build",
              "detail table unavailable" not in help_text)

    # the invalid message must mention help, since help exists
    for key, raw in sorted(Q.REGISTRY.items()):
        text = " ".join(Q.invalid_message(raw, "6"))
        check(P, f"{key}: the rejection points at the help",
              "H for additional details" in text)

    # THE COUNT IS A RELATION, NOT A NUMBER.
    #
    # A suite asserting "236 help checks ran" is a suite that fails the day a
    # question is added and passes the day one is silently dropped. What has
    # to hold is that every registered question was exercised on every
    # accepted spelling, whatever those counts happen to be.
    # The relation, restated after the default policy changed. Each
    # question is driven once per spelling with three behaviour checks, and
    # then twice more: Enter-after-help (which now selects nothing for an
    # engineering question) and bad-entry-after-help, the second of which
    # contributes two checks.
    per_spelling = 3        # help shown, question redisplayed, answer kept
    per_question = (len(Q.HELP_INPUTS) * per_spelling) + 2
    driven = [r for r in RESULTS
              if r[0] == P and ("opens the help" in r[1]
                                or "returns to the same question" in r[1]
                                or "does not change the answer" in r[1]
                                or "default survives" in r[1]
                                or "bad entry after help" in r[1]
                                or "can still be answered" in r[1])]
    check(P, "every question was driven through every help spelling",
          len(driven) == len(Q.REGISTRY) * per_question,
          f"{len(driven)} behaviour checks against "
          f"{len(Q.REGISTRY)} x {per_question} expected - the count is a "
          f"relation, not a number, so adding a question raises it and "
          f"dropping one lowers it")


def q7_coverage():
    P = "Q7"
    import os

    # A prompt built inline, with a bare string, is a prompt the registry
    # does not govern. This is the check that stops the twelfth question
    # being written the way the first eleven were.
    inline = []
    for fname in sorted(os.listdir("ppact")):
        if not fname.endswith(".py") or fname == "questions.py":
            continue
        text = open(os.path.join("ppact", fname), encoding="utf-8").read()
        for m in re.finditer(r'_?ask\w*\(\s*"([^"]{2,40})"', text):
            prompt = m.group(1)
            # a prompt that is a bare noun phrase with no explanation
            if prompt.lower().replace(" ", "_") in INTERNAL_NAMES:
                inline.append(f"{fname}: {prompt!r}")
    check(P, "no prompt uses an internal field name as its text", not inline,
          "; ".join(inline[:3]))


def main():
    print(LINE)
    print(" QUESTION CLARITY AUDIT")
    print(LINE)
    print("  A user must understand the question before being expected to")
    print("  answer it. Written before the questions were migrated, because")
    print("  eleven prompts fixed by hand are eleven prompts clear today.\n")

    for fn in (q1_registry, q2_clarity, q3_options, q4_effect,
               q5_terminology, q6_invalid, q7_coverage, q8_help_works,
               q9_no_direct_prompts, q10_behaviour_unchanged):
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
    labels = {"Q1": "registry", "Q2": "clarity", "Q3": "options",
              "Q4": "effect declared", "Q5": "terminology",
              "Q6": "invalid input", "Q7": "coverage",
              "Q8": "help works", "Q9": "no direct prompts",
              "Q10": "behaviour unchanged"}
    print(f"\n{LINE}")
    for pack in sorted(by_pack):
        good, total = by_pack[pack]
        print(f"  {pack}  {labels.get(pack, pack):<20s}{good:>5d} / "
              f"{total:<6d}{'pass' if good == total else 'FAIL'}")
    print(f"\n  {passed} / {len(RESULTS)} checks")
    print(f"\n  This suite makes an unclear question impossible to ship")
    print(f"  silently. It does not make a clear one - a sentence can satisfy")
    print(f"  every rule here and still leave a reader none the wiser.")
    print(LINE)
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
