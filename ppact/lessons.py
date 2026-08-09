"""
ppact.lessons - the education wizard, as a ten-lesson course

THE SHAPE OF A LESSON
=====================
    a question the student answers BEFORE seeing anything
        ->  one change, and only one
        ->  the result
        ->  why the other answers were wrong

The order matters more than any of the parts. A student who reads a table and
then an explanation has been told something. A student who commits to an
answer first has made a prediction, and a prediction that turns out wrong is
the only thing that reliably changes a mind. Reading a correct explanation
feels like understanding and usually is not.

So the wrong answers get explained too - each one, individually. "Wrong" is
useless feedback. "Wrong, and here is the reasoning that leads there, and
here is where it breaks" is the lesson.

THE RULE THIS MODULE ENFORCES
-----------------------------
A step changes ONE THING. A student shown a faster host, a wider memory, a
second engine and a finer node all at once, coming out four times quicker,
has learnt that changing four things makes a system faster - which is not a
design principle and is not even true.

A DECISION, not a field: choosing HBM sets both the memory and the stack
count, and that is one choice a person makes.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

LINE = "=" * 78
RULE = "-" * 78

GROUPED_FIELDS = (
    frozenset({"memory", "memory_devices"}),
    frozenset({"secondary_compute", "execution_mode", "work_split"}),
    frozenset({"secondary_compute", "execution_mode", "alternative_share"}),
    frozenset({"soc_node", "accel_node"}),
)

MAX_CHANGES_PER_STEP = 1


def count_decisions(changes: Dict) -> int:
    """How many separate choices a step represents."""
    remaining = set(changes)
    decisions = 0
    for group in GROUPED_FIELDS:
        if remaining & group:
            decisions += 1
            remaining -= group
    return decisions + len(remaining)


@dataclass(frozen=True)
class Option:
    text: str
    correct: bool
    because: str


@dataclass(frozen=True)
class Step:
    label: str
    changes: Dict = field(default_factory=dict)
    app_changes: Dict = field(default_factory=dict)
    note: str = ""


@dataclass(frozen=True)
class Lesson:
    number: int
    title: str
    ask: str
    options: Tuple[Option, ...]
    application: str
    reference: Dict
    steps: Tuple[Step, ...]
    watch: Tuple[str, ...]
    why: Tuple[str, ...]
    answer: str
    # A HINT, not the answer. Given after a wrong guess, it points at the
    # question the student should be asking rather than at the option they
    # should be picking - showing the answer removes the reason to think,
    # and the thinking is the lesson.
    hint: str = ""
    # What this lesson leaves behind, for the summary page.
    takeaway: str = ""


REFERENCE = dict(cpu="cortex_a78_x4", compute="npu_32x32", memory="LPDDR5",
                 memory_devices=2, preprocessing_mode="cpu_only")
VISION = "industrial_vision"
WATCH = ("Latency (ms)", "System power (W)", "System cost (USD)")
LLM_REF = dict(cpu="server_x86_x32", compute="datacenter_gpu",
               memory="HBM3E", memory_devices=6)


LESSONS: Tuple[Lesson, ...] = (

    Lesson(
        1, "What is PPACT?",
        ask="A design is twice as fast as another. Is it the better design?",
        options=(
            Option("Yes - speed is what a processor is for", False,
                   "Speed is one axis of five. A part twice as quick that "
                   "needs a fan the product does not have is not a faster "
                   "product; it is not a product."),
            Option("It depends on power, cost, area and heat as well", True,
                   "Those five - performance, power, area, cost, thermal - "
                   "are what PPACT stands for, and a design has to clear all "
                   "of them at once."),
            Option("Only if it also costs less", False,
                   "Cost matters, and so do three other things. A design "
                   "that is cheaper and overheats does not meet its requirements either."),
        ),
        application=VISION, reference=REFERENCE,
        steps=(
            Step("modest engine", {"compute": "npu_16x16"}),
            Step("larger engine", {"compute": "npu_64x64"},
                 note="four times the multipliers"),
        ),
        watch=WATCH,
        why=("the larger engine has four times the arithmetic",
             "and draws more power, and costs more, and takes more silicon",
             "each of those is a separate requirement a product must meet",
             "a design is not better because one number improved - it is "
             "better when it still clears every requirement"),
        answer="PPACT is five axes at once: performance, power, area, cost "
               "and thermal. Improving one usually costs you another.",
        hint="Look along a row, not down a column. How many of the five numbers moved, and in which directions?",
        takeaway="a design is five numbers, not one",
    ),

    Lesson(
        2, "Why the host still matters",
        ask="You add a dedicated engine. What does the general-purpose "
            "processor do now?",
        options=(
            Option("Nothing much - the engine does the work", False,
                   "The engine multiplies. Something still has to fetch each "
                   "frame, put it in the format the engine expects, hand it "
                   "over and read the answer back. That is the host, every "
                   "frame."),
            Option("It prepares the data and collects the result", True,
                   "And on a modest host that preparation can take longer "
                   "than the inference does, at which point the engine "
                   "waits."),
            Option("It runs the same arithmetic in parallel", False,
                   "The work is not duplicated. Doing it twice would cost "
                   "twice and buy nothing at all."),
        ),
        application=VISION, reference=REFERENCE,
        steps=(
            Step("modest host", {"cpu": "cortex_a53_x4"},
                 note="the engine is identical in both rows"),
            Step("capable host", {"cpu": "cortex_a78_x4"}),
        ),
        watch=WATCH,
        why=("the accelerator is the same part in both rows",
             "the host prepares every frame before the accelerator sees it",
             "on the modest host that takes longer than the inference does",
             "so the accelerator waits, and the system runs at the host's "
             "speed",
             "and the faster host draws MORE power - a system can be quicker "
             "and hungrier at once"),
        answer="A system runs at the speed of its slowest station, and that "
               "station is often not the one you were thinking about.",
        hint="The accelerator is identical in both rows. So what is different, and what does it do before the accelerator gets the frame?",
        takeaway="the host can be the slowest station",
    ),

    Lesson(
        3, "What makes an engine fast",
        ask="If a 32x32 array beats a 16x16, will a 64x64 beat the 32x32?",
        options=(
            Option("Yes - four times the multipliers", False,
                   "Four times the multipliers helps only while the "
                   "multipliers are the limit. They can be fed no faster "
                   "than the memory feeds them."),
            Option("Only until something else becomes the limit", True,
                   "And on this workload it does. The large engine is "
                   "SLOWER than the medium one."),
            Option("Yes, but it will cost more power", False,
                   "It does cost more power - and it is also slower, which "
                   "is the part worth noticing."),
        ),
        application=VISION, reference=REFERENCE,
        steps=(
            Step("small", {"compute": "npu_16x16"}),
            Step("medium", {"compute": "npu_32x32"}),
            Step("large", {"compute": "npu_64x64"},
                 note="four times the multipliers of the medium one"),
        ),
        watch=WATCH,
        why=("small to medium roughly halved the time",
             "medium to large made it WORSE",
             "the large engine multiplies faster than the memory can feed it",
             "so it spends its extra multipliers waiting",
             "the limit moved from the arithmetic to the transfers, and "
             "buying more arithmetic cannot move a limit that is no longer "
             "there"),
        answer="An engine is fast when it is fed. Past that point more "
               "multipliers cost power and area and buy nothing.",
        hint="Look at the 'limited by' column for each engine. What changes between the medium one and the large one?",
        takeaway="an engine helps until something else becomes the limit",
    ),

    Lesson(
        4, "The memory bottleneck",
        ask="A design is limited by its memory. What tells you that?",
        options=(
            Option("The memory is the most expensive part", False,
                   "Price says nothing about what is waiting. The cheapest "
                   "part in a system can be the one holding it up."),
            Option("More bandwidth helps and more arithmetic does not", True,
                   "That is what 'limited by' means: the thing that helps is "
                   "the thing that was short."),
            Option("The engine is running at full utilisation", False,
                   "The opposite. An engine waiting for data is NOT at full "
                   "utilisation - that is the symptom you would see."),
        ),
        application=VISION, reference=dict(REFERENCE, compute="npu_64x64"),
        steps=(
            Step("2 packages", {"memory_devices": 2}),
            Step("8 packages", {"memory_devices": 8},
                 note="same engine, four times the bandwidth"),
        ),
        watch=WATCH,
        why=("the engine did not change between the rows",
             "only the number of memory packages did",
             "and the time fell substantially",
             "which is what memory bound means - the thing that helped was "
             "the thing that was short",
             "on the medium engine from lesson 3 the same change is worth far "
             "less, because that design was not waiting"),
        answer="A design is memory bound when more bandwidth helps and more "
               "arithmetic does not. Find out which before buying either.",
        hint="Nothing about the memory changed between the rows. So how can it be the limit in one and not the other?",
        takeaway="a bottleneck is a relationship, not a part",
    ),

    Lesson(
        5, "The HBM myth",
        ask="HBM has many times the bandwidth of ordinary memory. When is it "
            "worth buying?",
        options=(
            Option("Always - bandwidth is never wasted", False,
                   "Bandwidth IS wasted on a design that is not waiting for "
                   "data. Here it costs six times as much and buys a small "
                   "fraction of the time."),
            Option("When the design waits for data and can take the heat",
                   True,
                   "Both conditions. It is a cooling class as well as a "
                   "number, and a part needing airflow cannot go in a sealed "
                   "case at any wattage."),
            Option("When the model does not fit in ordinary memory", False,
                   "That is a real reason to want more CAPACITY, and HBM has "
                   "it - but capacity and bandwidth are different purchases, "
                   "and this names only one of the two cases."),
        ),
        application=VISION, reference=REFERENCE,
        steps=(
            Step("ordinary memory", {"compute": "npu_32x32"},
                 note="this design is busy computing, not waiting"),
            Step("fast memory", {"memory": "HBM3E", "memory_devices": 1}),
        ),
        watch=WATCH,
        why=("the fast memory cost roughly six times as much",
             "and bought a small fraction of the time",
             "because this design was not waiting for data",
             "a faster memory shortens a wait, and there was little wait to "
             "shorten",
             "on the memory-bound design from lesson 4 the same upgrade is "
             "worth far more"),
        answer="A faster memory helps a design that is waiting for data. "
               "Find out what is waiting before you buy anything.",
        hint="Before asking whether the memory is faster, ask whether this design was waiting for memory at all.",
        takeaway="a faster memory only helps a design that was waiting",
    ),

    Lesson(
        6, "Two engines",
        ask="You add a second identical accelerator and split the work. How "
            "much faster?",
        options=(
            Option("About twice - each does half the arithmetic", False,
                   "Each does half the ARITHMETIC. Both still read from the "
                   "same memory, so the transfers did not halve - they "
                   "queued."),
            Option("Somewhat less than twice, because of overheads", False,
                   "Closer, but still optimistic. On this design the pair is "
                   "not slightly short of twice - it is slower than ONE "
                   "engine."),
            Option("It can be slower than one engine", True,
                   "And here it is. Two engines share one memory, and the "
                   "pair also pays to split the work and put it back "
                   "together."),
        ),
        application=VISION, reference=REFERENCE,
        steps=(
            Step("one engine"),
            Step("two engines",
                 {"secondary_compute": "npu_32x32",
                  "execution_mode": "parallel", "work_split": 0.5},
                 note="half the arithmetic each"),
        ),
        watch=WATCH,
        why=("each engine now does half the arithmetic",
             "but both read from the SAME memory",
             "so the transfers did not halve - they queued",
             "and the pair pays to split the work and put it back together",
             "here the result is not twice as fast; it is SLOWER than one "
             "engine"),
        answer="Doubling the arithmetic does not double a system that was "
               "not limited by arithmetic.",
        hint="Two engines split the arithmetic. Did they split the memory?",
        takeaway="two engines share one memory",
    ),

    Lesson(
        7, "Serving a language model",
        ask="A server answers sixteen users at once instead of one. What "
            "happens to each user?",
        options=(
            Option("Each gets the same speed - they run in parallel", False,
                   "They share one machine. Sixteen users do not get sixteen "
                   "machines, and the arithmetic is done by one engine."),
            Option("Each gets slower, and the server does far more in total",
                   True,
                   "That is the trade a server makes and a phone does not. "
                   "The weights are read once for the whole batch, so the "
                   "cost per user falls sharply."),
            Option("Each gets sixteen times slower", False,
                   "Much less than that. The expensive part - reading the "
                   "weights - is shared, so sixteen users cost far less than "
                   "sixteen times one user."),
        ),
        application="llm_service", reference=LLM_REF,
        steps=(
            Step("one user", app_changes={"batch": 1}),
            Step("sixteen users", app_changes={"batch": 16},
                 note="the same model, the same board"),
        ),
        watch=("Latency (ms)", "DRAM traffic (MB)", "System power (W)"),
        why=("the weights are read once per step, however many users are "
             "served",
             "each user carries their own cache, which is NOT shared",
             "so the traffic per user falls sharply as the batch grows",
             "the machine does far more in total and each user waits longer",
             "a server is paid for total throughput and a phone for one "
             "user's latency - the same machine is the right answer to one "
             "and the wrong answer to the other"),
        answer="The weights are shared and the cache is not. That asymmetry "
               "is why servers batch and phones do not.",
        hint="There are two throughput numbers. What is the difference between what a machine could do and what it is asked to do?",
        takeaway="capacity is not delivered throughput",
    ),

    Lesson(
        8, "Cost against performance",
        ask="Two upgrades are available. How do you choose between them?",
        options=(
            Option("Take the quicker one", False,
                   "Quicker per pound is the question, not quicker. One of "
                   "these buys about a seventh of the time for six times the "
                   "price."),
            Option("Compare what each gains against what each costs", True,
                   "And check the cheaper gain does not break something else "
                   "- one of these upgrades makes the design fail a "
                   "requirement outright."),
            Option("Take the cheaper one", False,
                   "Cheaper is not free either. The cheaper change here "
                   "makes the design SLOWER and breaks a requirement."),
        ),
        application=VISION, reference=REFERENCE,
        steps=(
            Step("as it stands"),
            Step("faster memory", {"memory": "HBM3E", "memory_devices": 1},
                 note="quicker, and six times the price"),
            Step("bigger engine", {"compute": "npu_64x64"},
                 note="most silicon, most power"),
        ),
        watch=WATCH,
        why=("the faster memory buys about a seventh of the time",
             "and costs about six times as much",
             "the bigger engine costs almost nothing extra",
             "and makes the design SLOWER, because it moved the limit to the "
             "memory",
             "neither is 'the upgrade' - one is expensive and one is "
             "counterproductive, and only the numbers say which is which"),
        answer="A gain is only worth what it costs, and a cheap change can "
               "still be the wrong one.",
        hint="One of these three does not meet the requirement, and one is the slowest despite costing the most. Which is left?",
        takeaway="past the limit, more money buys less",
    ),

    Lesson(
        9, "Heat",
        ask="A design needs more cooling than the product has. What are the "
            "options?",
        options=(
            Option("Add a fan", False,
                   "Sometimes - and a sealed outdoor product cannot have "
                   "one, and a drone cannot carry one. A cooling class is a "
                   "product decision, not a component one."),
            Option("Reduce the power, change the cooling class, or pick a "
                   "part that needs less", True,
                   "All three are levers, and what matters is that some of "
                   "them are not available on a given product."),
            Option("Use a larger heatsink", False,
                   "That IS changing the cooling class, and it changes the "
                   "size, the weight and the price of the product with it."),
        ),
        application="drone",
        reference=dict(cpu="cortex_a78_x4", compute="npu_24x24",
                       memory="LPDDR5", memory_devices=2,
                       preprocessing_mode="isp_and_npu"),
        steps=(
            Step("passive memory"),
            Step("needs airflow", {"memory": "HBM3E", "memory_devices": 1},
                 note="a drone has no airflow to give it"),
        ),
        watch=WATCH,
        why=("the faster memory made the design slightly quicker",
             "and four times the power",
             "on a drone every watt is flight time",
             "and the part demands a cooling class the product does not have",
             "that last failure is not a magnitude - no amount of power "
             "reduction gives a sealed airframe forced airflow"),
        answer="Heat is a class as well as a number. Some parts cannot go in "
               "some products at any wattage.",
        hint="One of the failures is not a quantity. Which one, and what would you reduce to fix it?",
        takeaway="cooling class is a class, not a number",
    ),

    Lesson(
        10, "The design challenge",
        ask="Three requirements, and a design that meets one. What now?",
        options=(
            Option("Improve the weakest number first", False,
                   "A reasonable instinct that often makes another "
                   "requirement worse. The three pull against each other."),
            Option("Change one thing, see what it cost elsewhere, repeat",
                   True,
                   "Which is the whole method. Every lesson before this "
                   "changed exactly one thing for exactly this reason."),
            Option("Buy the fastest parts and reduce cost afterwards", False,
                   "The fastest parts here fail power, cost and cooling at "
                   "once - and cooling cannot be reduced afterwards. It is a "
                   "class the product either has or does not."),
        ),
        application=VISION, reference=REFERENCE,
        steps=(
            Step("as handed over"),
            Step("host relieved", {"preprocessing_mode": "isp_and_npu"},
                 note="lesson 2 said which station was in the way"),
        ),
        watch=WATCH,
        why=("one change, chosen because lesson 2 identified the host as the "
             "constraint",
             "the time fell by roughly two thirds",
             "the power fell too, because the host is doing less",
             "and the cost barely moved",
             "that is what changing the RIGHT one thing looks like - and "
             "finding which one is the job"),
        answer="Change one thing, measure what it cost elsewhere, repeat. "
               "Finding which one thing is the whole of the work.",
        hint="Every lever you might reach for helps one requirement and charges you on another. Which one fixes the station that is actually in the way?",
        takeaway="find what is waiting before choosing what to buy",
    ),
)


FINAL_CHALLENGE = {
    "title": "Meet three requirements at once",
    "question": "Latency, power and cost. Can one design satisfy all three?",
    "application": VISION,
    "reference": REFERENCE,
    "targets": (("Latency (ms)", "below", 6.0),
                ("System power (W)", "below", 3.0),
                ("System cost (USD)", "below", 20.0)),
    "closing": ("Every change you made helped one requirement and cost you "
                "another. That is the whole of product engineering, and it "
                "is why a specification is a set of numbers rather than one."),
}


def lesson_violations() -> List[str]:
    """A lesson that changes two things teaches nothing about either."""
    problems = []
    for les in LESSONS:
        for st in les.steps:
            n = count_decisions(st.changes)
            if n > MAX_CHANGES_PER_STEP:
                problems.append(
                    f"lesson {les.number} '{st.label}': changes {n} things "
                    f"({', '.join(sorted(st.changes))}) - a student cannot "
                    f"tell which one did it")
        if len(les.steps) < 2:
            problems.append(f"lesson {les.number}: needs a comparison")
        if not les.why:
            problems.append(f"lesson {les.number}: a result and no reason")

        if not les.ask.endswith("?"):
            problems.append(f"lesson {les.number}: the prompt is not a "
                            f"question")
        right = [o for o in les.options if o.correct]
        if len(right) != 1:
            problems.append(
                f"lesson {les.number}: {len(right)} correct options - a quiz "
                f"with none is broken and one with two is a trick")
        if len(les.options) < 3:
            problems.append(
                f"lesson {les.number}: fewer than three options; a coin flip "
                f"is not a prediction")
        for o in les.options:
            if len(o.because) < 40:
                problems.append(
                    f"lesson {les.number} '{o.text[:24]}': no reasoning given. "
                    f"'Wrong' is useless feedback")

        width = min(max(len(st.label) for st in les.steps) + 2, 22)
        rendered = 2 + width + 13 * len(les.watch) + 12
        if rendered > 78:
            problems.append(
                f"lesson {les.number}: the table renders {rendered} wide")
        for st in les.steps:
            if len(st.label) > 20:
                problems.append(
                    f"lesson {les.number} '{st.label}': label too long")
    return problems


def _apply(les: "Lesson", st: "Step"):
    """Build the workload and the config for one step."""
    from .application import APPLICATION_LIBRARY
    from .system import SystemConfig
    import dataclasses as _dc

    merged = dict(les.reference)
    merged.update(st.changes)
    app = APPLICATION_LIBRARY[les.application]

    batch = st.app_changes.get("batch") if st.app_changes else None
    if batch:
        # The weights are read once per step however many users are served;
        # the cache, the activations and the arithmetic all scale with the
        # batch. Derived from the per-token cost, NOT from the library's
        # kv_cache_bytes - that figure is already an aggregate for batched
        # serving, and using it per user would multiply an already-multiplied
        # quantity.
        per_user_kv = app.kv_bytes_per_token * app.context_tokens
        app = _dc.replace(
            app,
            kv_cache_bytes=per_user_kv * batch,
            kv_bytes_per_token=app.kv_bytes_per_token * batch,
            activation_bytes=app.activation_bytes * batch,
            mac_per_inference=app.mac_per_inference * batch,
            key="__lesson__")
    return app, SystemConfig(**merged)


def run_lesson(les: "Lesson") -> List[Tuple[str, Dict, str]]:
    """Compute the rows. Every number comes from the engine."""
    from .application import APPLICATION_LIBRARY
    from .system import evaluate_system

    rows = []
    for st in les.steps:
        app, cfg = _apply(les, st)
        temporary = app.key == "__lesson__"
        if temporary:
            APPLICATION_LIBRARY["__lesson__"] = app
        try:
            r = evaluate_system(app, cfg)
            rows.append((st.label, {k: r.metrics[k] for k in les.watch},
                         r.bound_by))
        finally:
            if temporary:
                APPLICATION_LIBRARY.pop("__lesson__", None)
    return rows


def _wrap(text: str, width: int) -> List[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return lines


def print_question(les: "Lesson") -> None:
    print(f"\n{LINE}")
    print(f" LESSON {les.number}  {les.title}")
    print(LINE)
    print(f"  Before you see anything - what do you think?\n")
    for line in _wrap(les.ask, 72):
        print(f"  {line}")


def print_lesson(les: "Lesson", difficulty: str = "medium") -> None:
    """The comparison.

    EASY shows directions rather than figures - a student who cannot yet read
    a latency in milliseconds can still see that one went up and one went
    down, and that is the whole of the lesson. ADVANCED adds what the result
    rests on. MEDIUM is the numbers as they are.
    """
    rows = run_lesson(les)
    print(f"\n{RULE}")
    print(f"  One thing changes between the rows. Everything else is held.\n")

    if difficulty == "easy":
        # Against the PREVIOUS row, not the first. Comparing everything to
        # the first row made the large engine read "better" than the small
        # one - true, and the opposite of what the lesson is about, which is
        # that it is worse than the medium one.
        width = min(max(len(r[0]) for r in rows) + 2, 22)
        head = f"  {'':<{width}s}" + "".join(f"{m.split(' (')[0]:>13s}"
                                             for m in les.watch)
        head += f"{'limited by':>12s}"
        print(head)
        print("  " + "-" * (len(head) - 2))
        for idx, (label, metrics, bound) in enumerate(rows):
            line = f"  {label:<{width}s}"
            prev = rows[idx - 1][1] if idx else None
            for m in les.watch:
                if prev is None:
                    line += f"{'-':>13s}"
                    continue
                a, b = prev[m], metrics[m]
                # A PERCENTAGE, not an adjective. "better" names a
                # direction without naming what moved or by how much, and
                # those are the two things a student needs to carry away.
                # Easy mode drops the absolute figures, not the meaning.
                if a == 0:
                    mark = "-"
                else:
                    chg = (b / a - 1) * 100
                    mark = "no change" if abs(chg) < 2 else f"{chg:+.0f}%"
                line += f"{mark:>13s}"
            line += f"{bound:>12s}"
            print(line)
        print(f"\n  (easy mode: the change against the row above, as a")
        print(f"  percentage. The absolute figures are in medium.)")
        _print_reasoning(les)
        return

    width = min(max(len(label) for label, _, _ in rows) + 2, 22)
    head = f"  {'':<{width}s}" + "".join(f"{m.split(' (')[0]:>13s}"
                                         for m in les.watch)
    head += f"{'limited by':>12s}"
    print(head)
    print("  " + "-" * (len(head) - 2))
    for (label, metrics, bound), st in zip(rows, les.steps):
        line = f"  {label:<{width}s}"
        for m in les.watch:
            line += f"{metrics[m]:>13.2f}"
        line += f"{bound:>12s}"
        print(line)
        if st.note:
            print(f"  {'':<{width}s}{st.note}")

    _print_reasoning(les)


def _print_reasoning(les: "Lesson") -> None:
    print(f"\n  WHY")
    for i, step in enumerate(les.why):
        prefix = "     " if i == 0 else "      -> "
        wrapped = _wrap(step, 78 - len(prefix))
        print(prefix + wrapped[0])
        for extra in wrapped[1:]:
            print(" " * len(prefix) + extra)

    print(f"\n  IN ONE SENTENCE")
    for line in _wrap(les.answer, 70):
        print(f"     {line}")


def print_verdict(les: "Lesson", chosen: Optional[int]) -> None:
    """Whether they were right, and then why EVERY option is what it is.

    'Wrong' is useless feedback. The reasoning that leads to each wrong
    answer is the part worth reading, and a student who picked it needs to
    see where their own reasoning broke rather than be told a different one.
    """
    right = next(i for i, o in enumerate(les.options) if o.correct)
    print(f"\n{RULE}")
    if chosen is None:
        print(f"  No answer recorded. The correct one is {right + 1}.")
    elif chosen == right:
        print(f"  Correct.")
    else:
        print(f"  Not quite - the answer is {right + 1}.")
    print()
    for i, o in enumerate(les.options):
        mark = "correct" if o.correct else "wrong"
        yours = "   <- you chose this" if chosen == i else ""
        for j, line in enumerate(_wrap(o.text, 66)):
            print(f"  {str(i + 1) + '.' if j == 0 else '  '} {line}")
        print(f"     [{mark}]{yours}")
        for line in _wrap(o.because, 68):
            print(f"     {line}")
        print()
    print(LINE)


def print_final_challenge() -> None:
    from .application import APPLICATION_LIBRARY
    from .system import SystemConfig, evaluate_system

    c = FINAL_CHALLENGE
    print(f"\n{LINE}")
    print(f" AFTER THE LESSONS  {c['title']}")
    print(LINE)
    print(f"  {c['question']}\n")
    print(f"  Your targets:")
    for metric, direction, value in c["targets"]:
        print(f"    {metric:<24s}{direction} {value:g}")

    r = evaluate_system(APPLICATION_LIBRARY[c["application"]],
                        SystemConfig(**c["reference"]))
    print(f"\n  The design you start from:")
    met = 0
    for metric, direction, value in c["targets"]:
        got = r.metrics[metric]
        ok = got < value if direction == "below" else got > value
        met += ok
        print(f"    {metric:<24s}{got:>10.2f}   "
              f"{'meets it' if ok else 'DOES NOT'}")
    print(f"\n  {met} of {len(c['targets'])} met.")
    print(f"\n  Challenge Mode has this as a marked task, with a rank against")
    print(f"  every design the allowed choices can reach.")
    print(f"\n  " + "\n  ".join(_wrap(c["closing"], 72)))
    print(LINE)


def print_lesson_summary(les: "Lesson", p) -> None:
    """One page at the end of a lesson: what it leaves behind."""
    print(f"\n{RULE}")
    print(f"  YOU LEARNED")
    print(f"     {les.takeaway}")
    done = [l for l in LESSONS if l.number in p.completed]
    if len(done) > 1:
        print(f"\n  SO FAR")
        for l in done:
            print(f"     {l.number:2d}. {l.takeaway}")


def _hint_or_answer(les: "Lesson", p, ask_fn) -> Optional[int]:
    """Ask until right, or until the student has earned the answer.

    Showing the answer on the first wrong guess removes the reason to think,
    and the thinking is the lesson. So a wrong guess gets a HINT - a question
    to ask, not an option to pick - and only after several attempts is the
    answer given.
    """
    from .progress import ATTEMPTS_BEFORE_ANSWER
    right = next(i for i, o in enumerate(les.options) if o.correct)
    hints = 0
    for attempt in range(1, ATTEMPTS_BEFORE_ANSWER + 1):
        got = ask_fn("Your answer", [o.text for o in les.options], 1)
        chosen = got - 1 if 1 <= got <= len(les.options) else None
        correct = (chosen == right)
        p.record(les.number, chosen if chosen is not None else -1, correct,
                 hints_used=hints)
        if correct:
            print(f"\n  Correct.")
            return chosen
        if attempt < ATTEMPTS_BEFORE_ANSWER:
            hints += 1
            print(f"\n  Not that one. Before guessing again:")
            for line in _wrap(les.hint, 68):
                print(f"     {line}")
            print(f"\n  ({ATTEMPTS_BEFORE_ANSWER - attempt} more "
                  f"attempt(s) before the answer is shown.)")
    print(f"\n  The answer is {right + 1}. It is explained below along with")
    print(f"  why each of the others is what it is.")
    return chosen


def main(ask_fn, folder: str = ".") -> None:
    """The course. Answer first, then see.

    State - progress, difficulty, hints, whether the instructor has unlocked
    anything - lives in ppact.progress and is saved after every lesson, so a
    student who stops in the middle resumes where they were.
    """
    from .progress import (Progress, print_progress, print_score,
                           print_certificate, print_distribution,
                           DIFFICULTIES, DIFFICULTY_NOTE, EASY, ADVANCED)
    from .challenge import FINAL_EXAM, population, print_challenge, \
        print_result, print_best

    p = Progress.load(folder)
    resumed = bool(p.completed)

    while True:
        print(f"\n{LINE}")
        print(f" THE COURSE")
        print(LINE)
        print_progress(p, len(LESSONS))
        if resumed:
            nxt = next((l.number for l in LESSONS
                        if l.number not in p.completed), None)
            if nxt:
                print(f"  Resuming - lesson {nxt} is next.")
            resumed = False
        print(f"\n  Each lesson asks you to commit to an answer before it")
        print(f"  shows you anything. A prediction that turns out wrong is")
        print(f"  the only thing that reliably changes a mind.\n")

        labels = []
        for les in LESSONS:
            mark = "done" if les.number in p.completed else "    "
            labels.append(f"[{mark}] {les.title}")
        extra = ["The final design challenge"
                 + (" - passed" if p.exam_passed else ""),
                 "How I am doing",
                 f"Difficulty: {p.difficulty}",
                 "Certificate",
                 "Instructor settings",
                 "Back"]
        pick = ask_fn("Which lesson", labels + extra, 1)

        n = len(LESSONS)
        if pick == n + 6:
            p.save(folder)
            return
        if pick == n + 1:
            _run_exam(p, ask_fn, folder)
            continue
        if pick == n + 2:
            print_score(p, len(LESSONS))
            continue
        if pick == n + 3:
            d = ask_fn("Difficulty",
                       [f"{x} - {DIFFICULTY_NOTE[x]}" for x in DIFFICULTIES],
                       DIFFICULTIES.index(p.difficulty) + 1)
            p.difficulty = DIFFICULTIES[d - 1]
            p.save(folder)
            print(f"\n  Set to {p.difficulty}.")
            continue
        if pick == n + 4:
            print_certificate(p, len(LESSONS))
            continue
        if pick == n + 5:
            _instructor(p, ask_fn, folder)
            continue

        les = LESSONS[pick - 1]
        print(f"\n{LINE}")
        print(f" LESSON {les.number} of {len(LESSONS)}  {les.title}")
        print(LINE)
        print_progress(p, len(LESSONS), les.number)
        print_question(les)
        print()

        if p.show_answers:
            right = next(i for i, o in enumerate(les.options) if o.correct)
            print(f"  [instructor] the answer is {right + 1}\n")

        chosen = _hint_or_answer(les, p, ask_fn)
        print_lesson(les, difficulty=p.difficulty)
        print_verdict(les, chosen)
        print_distribution(p, les.number, len(les.options),
                           next(i for i, o in enumerate(les.options)
                                if o.correct))
        print_lesson_summary(les, p)
        p.save(folder)


def _instructor(p, ask_fn, folder: str) -> None:
    from .progress import print_score
    while True:
        print(f"\n{LINE}")
        print(" INSTRUCTOR")
        print(LINE)
        print(f"  Show answers before the question   "
              f"{'on' if p.show_answers else 'off'}")
        print(f"  Mark every lesson complete         "
              f"{len(p.completed)} of {len(LESSONS)} done")
        print(f"\n  These change what a STUDENT sees. Leaving 'show answers'")
        print(f"  on removes the point of the prediction, so it is off by")
        print(f"  default and is announced on screen when it is not.\n")
        pick = ask_fn("Choose", ["Toggle show answers",
                                 "Mark all lessons complete",
                                 "Reset all progress", "Back"], 4)
        if pick == 1:
            p.show_answers = not p.show_answers
        elif pick == 2:
            p.completed = [l.number for l in LESSONS]
        elif pick == 3:
            p.attempts.clear()
            p.completed.clear()
            p.exam_passed = False
            p.exam_tries = 0
            print("  Progress cleared.")
        else:
            p.save(folder)
            return
        p.save(folder)


def _run_exam(p, ask_fn, folder: str) -> None:
    from .challenge import FINAL_EXAM, population, print_challenge, \
        print_result, print_best

    print_challenge(FINAL_EXAM)
    changes = {}
    # Through the registry, as the challenge loop now is. The exam showed
    # "memory_devices" over a list of 1, 2, 4 and 8 with nothing to say
    # what was being counted.
    from .questions import field_question, ask_question
    for field_name, options in FINAL_EXAM.allowed.items():
        print()
        current = FINAL_EXAM.start.get(field_name)
        chosen = ask_question(field_question(field_name, options, current))
        if chosen != "__keep__" and chosen != current:
            changes[field_name] = chosen

    print("\n  Working out how your design compares...")
    pop = population(FINAL_EXAM)
    sc = print_result(FINAL_EXAM, changes, pop)
    p.exam_tries += 1
    if sc["passes"]:
        p.exam_passed = True
        print(f"\n  You built the design. {p.exam_tries} attempt(s).")
    else:
        print(f"\n  Not yet. Something moved when you changed something")
        print(f"  else - which is the whole subject. Try again.")
    p.save(folder)
    if ask_fn("Show the best answers", ["Yes", "No"], 2) == 1:
        print_best(FINAL_EXAM, pop)

