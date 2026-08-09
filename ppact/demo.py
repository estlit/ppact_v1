"""
ppact.demo - one question, one comparison, one answer

WHAT A DEMO IS FOR
==================
A lecture, a recording, a stand at a conference. The person watching did not
choose the parameters and cannot be asked to. So a demo takes NO input: pick
a question, and the answer arrives.

That constraint is the whole design. A demo that asks "which application?"
has already lost the room, and a demo that shows a table without saying what
it means has shown a table.

EVERY QUESTION HERE HAS THE ANSWER "NO"
---------------------------------------
Not out of contrarianism. A demonstration that things work teaches that
things work, which the audience already assumed. What they do not know is
where the intuition breaks, and that is the only part worth taking their time
for.

    does a faster memory always help          no - depends what was waiting
    does a bigger engine always help          no - it stops, and then reverses
    are two engines twice as fast             no - here they are slower
    does a finer process node make it faster  no - not if memory is the limit
    does more memory capacity mean speed      no - capacity is not bandwidth
    is the fastest design the one you ship    no - it fails three gates

THE CLAIMS ARE CHECKED
----------------------
Each demo states an answer in words. If the model stops producing the result
that answer rests on, the answer becomes a lie told to an audience. So every
claim is a check in the suite, exactly as the lessons are.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

LINE = "=" * 78

WATCH = ("Latency (ms)", "System power (W)", "System cost (USD)")


@dataclass(frozen=True)
class Row:
    label: str
    application: str
    config: Dict


@dataclass(frozen=True)
class Demo:
    key: str
    question: str
    setup: str              # one or two lines: what is being held constant
    rows: Tuple[Row, ...]
    watch: Tuple[str, ...]
    answer: str             # the sentence the audience leaves with
    because: str            # the mechanism, in one more sentence
    # WHICH TWO ROWS THE CHART COMPARES.
    #
    # The chart took the first row and the last. In a 2x2 study that
    # crosses both axes at once: Demo 007 asks when a second engine is
    # worth having and its first-to-last pair changed the memory as
    # well, so the picture answered a question the demo was not asking.
    # The rows stay as they are - the grid is the demonstration - and
    # only the pair the chart draws is named.
    spider_pair: Optional[Tuple[int, int]] = None


VISION = dict(cpu="cortex_a78_x4", compute="npu_32x32", memory="LPDDR5",
              memory_devices=2, preprocessing_mode="isp_and_npu")
# The dual demo uses a HOST-PREPROCESSED variant, where the pair is genuinely
# slower. On the ISP-assisted configuration above the second engine helps,
# and a demo whose stated answer contradicts its own table is worse than no
# demo - the audience is watching the numbers.
VISION_HOST = dict(VISION, preprocessing_mode="cpu_only")
ROBOT = dict(cpu="cortex_a78_x4", compute="npu_128x128", memory="LPDDR5",
             memory_devices=1, preprocessing_mode="isp_and_npu")
MOBILE = dict(cpu="cortex_a78_x4", compute="npu_64x64", memory="LPDDR5",
              memory_devices=2, preprocessing_mode="isp_and_npu")


DEMOS: Tuple[Demo, ...] = (

    Demo(
        "memory",
        "Does much faster memory produce a proportional system speedup?",
        setup="The same engine, the same workload. Only the memory changes.",
        rows=(
            # ONE VARIABLE. The setup says "only the memory changes"
            # and the comparison changed the package count as well, 2
            # to 1, so the result mixed a technology change with a
            # capacity change and Recommended Next Comparisons marked
            # both as COMPLETED. A demonstration that names one change
            # and makes two teaches the wrong lesson first.
            Row("ordinary", "industrial_vision", VISION_HOST),
            # Thirteen characters. The row labels head a table column
            # and `demo_violations` holds them to fourteen; "much
            # faster memory" was eighteen and the check that guards the
            # table caught it.
            Row("faster memory", "industrial_vision",
                {**VISION_HOST, "memory": "HBM3E"}),
        ),
        watch=WATCH,
        answer="No. Nineteen times the bandwidth buys a seventh off the "
               "latency, at twelve times the price.",
        because="This design was computing, not waiting. A faster memory "
                "shortens a wait, and there was very little wait to shorten.",
    ),

    Demo(
        "engine",
        "Does a bigger engine always help?",
        setup="The same memory, the same workload. Only the engine changes.",
        rows=(
            Row("small", "industrial_vision",
                {**VISION_HOST, "compute": "npu_16x16"}),
            Row("medium", "industrial_vision",
                {**VISION_HOST, "compute": "npu_32x32"}),
            Row("large", "industrial_vision",
                {**VISION_HOST, "compute": "npu_64x64"}),
        ),
        watch=WATCH,
        answer="No. It helps, then it stops, then it reverses - the large "
               "engine is SLOWER than the medium one.",
        because="The large engine multiplies faster than the memory can feed "
                "it, so the extra multipliers wait. The limit moved, and "
                "buying more arithmetic cannot move a limit that is no longer "
                "there.",
    ),

    Demo(
        "dual", "Are two engines twice as fast?",
        setup="One accelerator, then two, sharing one memory system.",
        rows=(
            Row("one engine", "industrial_vision", VISION_HOST),
            Row("two engines", "industrial_vision",
                {**VISION_HOST, "secondary_compute": "npu_32x32",
                 "execution_mode": "parallel", "work_split": 0.5}),
        ),
        watch=WATCH,
        answer="No. Here they are SLOWER than one.",
        because="Each engine does half the arithmetic, but both read the same "
                "memory - so the transfers did not halve, they queued. And "
                "the pair pays to split the work and to put it back together.",
    ),

    Demo(
        "node", "Does a finer process node make it faster?",
        setup="The identical design, fabricated at three different nodes.",
        rows=(
            Row("16 nm", "mobile_ai",
                {**MOBILE, "soc_node": "N16", "accel_node": "N16"}),
            Row("7 nm", "mobile_ai",
                {**MOBILE, "soc_node": "N7", "accel_node": "N7"}),
            Row("3 nm", "mobile_ai",
                {**MOBILE, "soc_node": "N3", "accel_node": "N3"}),
        ),
        watch=WATCH,
        answer="Barely. Two node generations move the time by under one per "
               "cent.",
        because="A node makes arithmetic faster and does nothing to a memory "
                "bought off a shelf. This design was waiting for the memory, "
                "and it still is. The power does fall - which is usually the "
                "real reason parts move.",
    ),


    Demo(
        "order", "Three ways to spend money. Which one works?",
        setup="Three ways to spend money on the same design. Only one of "
              "them is worth doing.",
        rows=(
            Row("as it stands", "industrial_vision", VISION_HOST),
            Row("bigger engine", "industrial_vision",
                {**VISION_HOST, "compute": "npu_64x64"}),
            Row("more memory", "industrial_vision",
                {**VISION_HOST, "memory_devices": 8}),
            Row("host relieved", "industrial_vision",
                {**VISION_HOST, "preprocessing_mode": "isp_and_npu"}),
        ),
        watch=WATCH,
        answer="The cheapest change is the best one, and the obvious "
               "hardware upgrade makes it worse.",
        because="The host was the slowest station. Moving its work elsewhere "
                "costs almost nothing and removes the actual constraint; "
                "buying arithmetic or bandwidth spends money on stations "
                "that were not in the way.",
    ),





    Demo(
        "finest", "Is the finest process node the fastest?",
        setup="A compute-bound design fabricated at three nodes.",
        rows=(
            Row("16 nm", "industrial_vision",
                {**VISION_HOST, "soc_node": "N16", "accel_node": "N16"}),
            Row("7 nm", "industrial_vision",
                {**VISION_HOST, "soc_node": "N7", "accel_node": "N7"}),
            Row("3 nm", "industrial_vision",
                {**VISION_HOST, "soc_node": "N3", "accel_node": "N3"}),
        ),
        watch=WATCH,
        answer="No. The 3 nm part is slower than the 7 nm one, and dearer.",
        because="Below a certain point the memory arrays stop shrinking with "
                "the logic, so the die does not get proportionally smaller "
                "and the wafer costs far more. The power keeps falling, which "
                "is usually the real reason parts move - not the speed.",
    ),

    Demo(
        "together", "When is a second engine worth having?",
        setup="The same pair of engines, on a narrow memory and a wide one.",
        rows=(
            Row("narrow, one", "robot", ROBOT),
            Row("narrow, two", "robot",
                {**ROBOT, "secondary_compute": "npu_128x128",
                 "execution_mode": "parallel", "work_split": 0.5}),
            Row("wide, one", "robot",
                {**ROBOT, "memory": "HBM3E", "memory_devices": 1}),
            Row("wide, two", "robot",
                {**ROBOT, "memory": "HBM3E", "memory_devices": 1,
                 "secondary_compute": "npu_128x128",
                 "execution_mode": "parallel", "work_split": 0.5}),
        ),
        # THE GRID SHOWS BOTH MEMORIES; THE CHART ISOLATES THE ENGINE.
        #
        # First-to-last crossed both axes of this 2x2, so the picture
        # answered a question the demo was not asking.
        # `narrow, one -> narrow, two` is the counter-example and stays
        # in the table, where it belongs.
        spider_pair=(2, 3),
        watch=WATCH,
        answer="Only once the memory can feed it. On the narrow bus the pair "
               "is slower; on the wide one it is faster.",
        because="The second engine was never short of work - it was short of "
                "data. Adding it before the memory can supply both makes "
                "things worse, so the order the two upgrades are tried in "
                "decides what a designer concludes about either.",
    ),

    Demo(
        "shipping",
        "Does better traffic balance mean the design passes every check?",
        setup="The quickest configuration available, against its "
              "requirements.",
        rows=(
            Row("a sensible one", "mobile_ai", MOBILE),
            Row("the quickest", "mobile_ai",
                {**MOBILE, "memory": "HBM3E", "memory_devices": 1}),
        ),
        watch=("Latency (ms)", "System power (W)", "System cost (USD)"),
        answer="No. The quick one is eight times faster and fails four "
               "requirements.",
        because="Speed is one axis. Power, cost and the cooling class the "
                "part demands are three others, and a product has to clear "
                "all of them. One of those failures is not even a number - a "
                "part needing airflow cannot go in a sealed case at any "
                "wattage.",
    ),

    Demo(
        "host", "Which should you upgrade first?",
        setup="Identical accelerator and memory. Only the host changes.",
        rows=(
            Row("modest host", "industrial_vision",
                {**VISION_HOST, "cpu": "cortex_a53_x4"}),
            Row("capable host", "industrial_vision", VISION_HOST),
        ),
        watch=WATCH,
        answer="The host, here. Three times faster, and the accelerator was "
               "never touched.",
        because="The host prepares every frame before the accelerator sees "
                "it. On the modest one that preparation takes longer than the "
                "inference, so the accelerator sat waiting.",
    ),

    Demo(
        "offload", "Where should the preprocessing run?",
        setup="Same parts throughout. Only WHERE the frame is prepared "
              "changes.",
        rows=(
            Row("on the host", "industrial_vision", VISION_HOST),
            Row("on fixed logic", "industrial_vision",
                {**VISION_HOST, "preprocessing_mode": "isp_and_npu"}),
        ),
        watch=WATCH,
        answer="Not on the host. Moving it cuts the time by nearly two "
               "thirds and the power with it.",
        because="A general-purpose core doing per-pixel work is the most "
                "expensive way to do per-pixel work. Fixed logic does it for "
                "a fraction of the energy, and the host stops being the "
                "slowest station.",
    ),

    Demo(
        "capacity", "Does more memory make it faster?",
        setup="The same memory type. Only how much of it changes.",
        rows=(
            Row("one package", "industrial_vision",
                {**VISION_HOST, "memory_devices": 1}),
            Row("eight", "industrial_vision",
                {**VISION_HOST, "memory_devices": 8}),
        ),
        watch=WATCH,
        answer="Here yes - but not because of the capacity. Eight packages "
               "cost seven times as much.",
        because="More packages buy BANDWIDTH as well as capacity, and this "
                "design was memory-limited. The same purchase on a "
                "compute-limited design buys almost nothing, which is a "
                "different demo.",
    ),

    Demo(
        "fit", "What happens when the model does not fit?",
        setup="A large language model on two memory configurations.",
        rows=(
            Row("too small", "llm_service",
                dict(cpu="server_x86_x32", compute="datacenter_gpu",
                     memory="HBM3E", memory_devices=2)),
            Row("large enough", "llm_service",
                dict(cpu="server_x86_x32", compute="datacenter_gpu",
                     memory="HBM3E", memory_devices=6)),
        ),
        watch=("Latency (ms)", "System power (W)", "System cost (USD)"),
        answer="Nothing. Not slow - absent. The row reports no timing at all.",
        because="A model that does not fit cannot run at any speed. Reporting "
                "a latency for it would invite a comparison between a machine "
                "that works and one that cannot exist.",
    ),

    Demo(
        "cheaper", "Can a cheaper memory be the right answer?",
        setup="A drone, with two memory types at the same package count.",
        rows=(
            Row("low-power", "drone",
                dict(cpu="cortex_a78_x4", compute="npu_24x24",
                     memory="LPDDR5", memory_devices=2,
                     preprocessing_mode="isp_and_npu")),
            Row("graphics", "drone",
                dict(cpu="cortex_a78_x4", compute="npu_24x24",
                     memory="GDDR6", memory_devices=2,
                     preprocessing_mode="isp_and_npu")),
        ),
        watch=WATCH,
        answer="The graphics memory is 41% cheaper and the same speed - and "
               "it doubles the power.",
        because="This design is compute-limited, so neither memory is what is "
                "holding it up. The choice comes down to price against power, "
                "and on a battery that is not a close call.",
    ),

    Demo(
        "split", "Does splitting a job between two engines help?",
        setup="Two engines of different sizes, one job divided between them.",
        rows=(
            Row("one engine", "smart_camera",
                dict(cpu="cortex_a78_x4", compute="npu_32x32",
                     memory="LPDDR5", memory_devices=2,
                     preprocessing_mode="isp_and_npu")),
            Row("split evenly", "smart_camera",
                dict(cpu="cortex_a78_x4", compute="npu_32x32",
                     memory="LPDDR5", memory_devices=2,
                     preprocessing_mode="isp_and_npu",
                     secondary_compute="npu_16x16",
                     execution_mode="parallel", work_split=0.5)),
        ),
        watch=WATCH,
        answer="Not evenly. Half the work on a quarter of the engine takes "
               "longer than all of it on the whole one.",
        because="A parallel pair cannot finish before its slower half. "
                "Splitting work evenly between unequal engines gives the "
                "small one more than it can carry.",
    ),

    Demo(
        "nodecost", "Is the newest process node the cheapest to make?",
        setup="The same design, fabricated at four nodes. Watch the LOGIC "
              "die cost - the part a node actually moves.",
        rows=(
            Row("28 nm", "industrial_vision",
                {**VISION_HOST, "soc_node": "N28", "accel_node": "N28"}),
            Row("16 nm", "industrial_vision",
                {**VISION_HOST, "soc_node": "N16", "accel_node": "N16"}),
            Row("7 nm", "industrial_vision",
                {**VISION_HOST, "soc_node": "N7", "accel_node": "N7"}),
            Row("3 nm", "industrial_vision",
                {**VISION_HOST, "soc_node": "N3", "accel_node": "N3"}),
        ),
        watch=("Latency (ms)", "Logic die cost (USD)", "System cost (USD)"),
        answer="No. The cost falls to 7 nm and then RISES again - 3 nm is "
               "dearer than 7 nm here, and slower.",
        because="A finer node shrinks the die, which lowers cost, and raises "
                "the wafer price and lowers the yield, which raises it. The "
                "two cross. Where they cross depends on how much of the die "
                "is memory, because memory shrinks at about half the rate "
                "logic does.",
    ),
)


BY_KEY = {d.key: d for d in DEMOS}


def run_demo(d: Demo) -> List[Tuple[str, Dict, str, bool, List[str]]]:
    """Compute the rows. Every figure comes from the engine."""
    from .application import APPLICATION_LIBRARY
    from .system import SystemConfig, evaluate_system

    out = []
    for row in d.rows:
        r = evaluate_system(APPLICATION_LIBRARY[row.application],
                            SystemConfig(**row.config))
        failed = sorted(g for g, ok in r.gate.items() if not ok)
        out.append((row.label, {k: r.metrics[k] for k in d.watch},
                    r.bound_by, r.passes, failed))
    return out


# THE FOUR PANELS A DEMONSTRATION SHOWS.
#
# Ordered evidence first, then mechanism, then the summary - the same
# order the Streamlit tabs use, because a reader moving between the two
# should not have to relearn where to look.

DEMO_PANELS = (
    ("Measured Results", "measured"),
    ("System Flow and Bottleneck Map", "flow_map"),
    ("Bottleneck Analysis", "bottleneck"),
    ("Architecture Balance", "balance"),
)


def demo_panels(d, number: int, out_dir: str = "") -> List[Dict]:
    """Build every panel for a demonstration and report each one.

    A DEMONSTRATION IS A COMPARISON, on every interface.

    The notebook and terminal paths called the requirement-centred
    review, where both of a demo's designs sit far above the application
    budget and pin at the same value - so Demo 001 drew two identical
    polygons for a sixteenfold memory change. Streamlit had been moved to
    the relative chart and these had not, and the parity check did not
    notice because it compared `demo_visual` against itself and called
    one side "the notebook path".
    """
    import os
    import tempfile

    from .demo_visual import (render_measured_comparison,
                              render_bottleneck_chart,
                              build_demo_comparison,
                              render_relative_spider)
    from .flow_map import (build_compared_flow_map,
                           render_compared_flow_map_png)
    from .review import build_review
    from .system import SystemConfig

    root = out_dir or os.path.join(tempfile.gettempdir(),
                                   "ppact_demo_panels")
    os.makedirs(root, exist_ok=True)
    stem = os.path.join(root, f"demo_{number:03d}")

    first, last = d.rows[0], d.rows[-1]
    cmp = build_demo_comparison(d, number)

    def build(kind):
        if kind == "measured":
            return render_measured_comparison(
                d, number, f"{stem}_measured.png")
        if kind == "bottleneck":
            return render_bottleneck_chart(
                d, number, f"{stem}_bottleneck.png")
        if kind == "balance":
            if cmp is None:
                return None
            return render_relative_spider(cmp, f"{stem}_balance.png")
        if kind == "flow_map":
            if cmp is None:
                return None
            b = build_review("education_step_by_step",
                             first.application,
                             SystemConfig(**first.config))
            c = build_review("education_step_by_step",
                             last.application,
                             SystemConfig(**last.config))
            return render_compared_flow_map_png(
                build_compared_flow_map(b, c, first.label, last.label),
                f"{stem}_flow_map.png")
        return None

    out: List[Dict] = []
    for title, kind in DEMO_PANELS:
        rec = {"panel": title, "kind": kind, "status": "MISSING",
               "path": "", "note": ""}
        try:
            path = build(kind)
            if path is None:
                rec["status"] = "NOT APPLICABLE"
                rec["note"] = "this demonstration has nothing to compare"
            elif os.path.isfile(path):
                rec["status"] = "CREATED"
                rec["path"] = path
            else:
                rec["note"] = "the renderer returned a path not on disk"
        except Exception as exc:
            rec["status"] = "FAILED"
            rec["note"] = f"{type(exc).__name__}: {exc}"
        out.append(rec)
    return out


def render_demo_review(d, number: int = 0) -> None:
    """A demonstration ends with its four panels and its closure.

    Same panels, same order and same figures as the Streamlit tabs.
    """
    import os

    from .system import SystemConfig
    from .closure import build_closure, render_closure
    from .flow_map import build_compared_flow_map
    from .review import build_review

    if len(d.rows) < 2:
        return
    first, last = d.rows[0], d.rows[-1]
    if first.application != last.application:
        return
    if not number:
        number = next((i for i, x in enumerate(DEMOS, 1)
                       if x.key == d.key), 0)

    print(f"\n{LINE}")
    print(" ENGINEERING REVIEW FOR THIS QUESTION")
    print(LINE)
    print(f"  {d.question}")
    print(f"  {first.label}  ->  {last.label}\n")

    try:
        from .core import in_notebook
        notebook = bool(in_notebook())
    except Exception:
        notebook = False

    recs = demo_panels(d, number)
    if notebook:
        try:
            from IPython.display import Image, display, Markdown
            for rec in recs:
                if rec["status"] == "CREATED":
                    display(Markdown(f"**{rec['panel']}**"))
                    display(Image(filename=rec["path"]))
                else:
                    # A PANEL THAT DID NOT APPEAR SAYS SO. Silence reads
                    # as "this interface cannot draw it".
                    display(Markdown(f"*{rec['panel']}: not shown - "
                                     f"{rec['note'] or rec['status']}.*"))
        except Exception:
            notebook = False
    if not notebook:
        for rec in recs:
            state = (os.path.basename(rec["path"])
                     if rec["status"] == "CREATED"
                     else f"{rec['status']} - {rec['note']}")
            print(f"  {rec['panel']:<34s}{state}")
        print()

    # THE DEMO WORKFLOW IS STILL THE DEMO WORKFLOW.
    #
    # Routing every call through `education_step_by_step` took the demo
    # workflow out of the registry's reach, and R2 - which exists so no
    # screen quietly stops using the standard review - caught it. The
    # comparison analysis is built under "demo"; the two single-design
    # analyses beside it are what a flow map needs, one per side.
    comparison = build_review("demo", last.application,
                              SystemConfig(**last.config),
                              SystemConfig(**first.config))
    b = build_review("education_step_by_step", first.application,
                     SystemConfig(**first.config))
    c = build_review("education_step_by_step", last.application,
                     SystemConfig(**last.config))
    cm = build_compared_flow_map(b, c, first.label, last.label)
    changed = [f for f in first.config
               if first.config.get(f) != last.config.get(f)]
    for line in render_closure(
            build_closure(b, c, changed, cm.key_insight)):
        print(line)



def print_demo(d: Demo, show_gates: bool = True) -> None:
    rows = run_demo(d)

    print(f"\n{LINE}")
    print(f" {d.question}")
    print(LINE)
    for line in _wrap(d.setup, 72):
        print(f"  {line}")
    print()

    # 78 columns total: two of indent, the label, three metric columns, the
    # bottleneck, and the gate verdict. The label is capped so the table
    # cannot push the last column off the screen.
    width = min(max(len(r[0]) for r in rows) + 2, 16)
    # A metric name longer than its column runs into the one before it.
    # Truncating is better than a header that reads "LatencyLogic die cost".
    head = f"  {'':<{width}s}" + "".join(
        f"{m.split(' (')[0][:12]:>13s}" for m in d.watch)
    head += f"{'limited by':>12s}"
    if show_gates:
        head += f"{'deploy':>8s}"
    print(head)
    print("  " + "-" * (len(head) - 2))
    for label, metrics, bound, passes, failed in rows:
        line = f"  {label:<{width}s}"
        for m in d.watch:
            line += f"{metrics[m]:>13.2f}"
        line += f"{bound:>12s}"
        if show_gates:
            line += f"{('yes' if passes else 'no'):>8s}"
        print(line)
        if show_gates and failed:
            print(f"  {'':<{width}s}fails: {', '.join(failed)}")

    if show_gates:
        print(f"\n  'deploy' is whether the design meets EVERY requirement -")
        print(f"  latency, power, cost, cooling class - not whether it is "
              f"quick.")
    print(f"\n  ANSWER")
    for line in _wrap(d.answer, 70):
        print(f"     {line}")
    print(f"\n  BECAUSE")
    for line in _wrap(d.because, 70):
        print(f"     {line}")
    print(LINE)


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


def demo_violations() -> List[str]:
    """A demo must take no input, compare something, and answer in words."""
    problems = []
    # A duplicate key does not raise; it silently overwrites in BY_KEY, so
    # one demo becomes unreachable and nothing says so. Found when four new
    # demos were added and three collided with ones already present.
    seen = set()
    for d in DEMOS:
        if d.key in seen:
            problems.append(
                f"{d.key}: two demos share this key - the second silently "
                f"replaces the first in the lookup and one becomes "
                f"unreachable")
        seen.add(d.key)
    for d in DEMOS:
        width = min(max(len(r.label) for r in d.rows) + 2, 16)
        rendered = 2 + width + 13 * len(d.watch) + 12 + 8
        if rendered > 78:
            problems.append(
                f"{d.key}: the table renders {rendered} wide and wraps")
        for r in d.rows:
            if len(r.label) > 14:
                problems.append(f"{d.key}/{r.label}: label too long")
        if len(d.rows) < 2:
            problems.append(f"{d.key}: a demo with one row compares nothing")
        if not d.question.endswith("?"):
            problems.append(f"{d.key}: the title is not a question")
        if not d.answer or len(d.answer) < 25:
            problems.append(f"{d.key}: no answer in words")
        if not d.because or len(d.because) < 40:
            problems.append(
                f"{d.key}: an answer with no mechanism behind it is a claim, "
                f"and an audience cannot check a claim")
        # every row must differ from the first in something
        first = d.rows[0].config
        for row in d.rows[1:]:
            if row.config == first and row.application == d.rows[0].application:
                problems.append(f"{d.key}/{row.label}: identical to the first "
                                f"row")
    return problems


def main(ask_fn):
    """The library. Returns the demonstration that was read.

    A DEMONSTRATION IS A COMPARISON like any other, so it returns the
    same object every workflow returns - two named designs and the
    answers that reached them.
    """
    while True:
        print(f"\n{LINE}")
        print(f" QUESTIONS")
        print(LINE)
        print(f"  Pick one. Nothing to fill in - the comparison runs and the")
        print(f"  answer follows.\n")
        labels = [d.question for d in DEMOS] + ["All of them", "Back"]
        # Navigation, through the registry path: same help handling and
        # same refusal wording as every other prompt.
        from .menu import ask_nav
        pick = ask_nav("Demonstration",
                       "Choose which question to see answered.", labels, 1)
        if pick > len(DEMOS) + 1:
            return
        if pick == len(DEMOS) + 1:
            for i, d in enumerate(DEMOS, 1):
                print_demo(d)
                render_demo_review(d, i)
        else:
            d = DEMOS[pick - 1]
            print_demo(d)
            render_demo_review(d, pick)
            from .outcome import comparison as _dc, SelectedAnswer as _SA
            from .present import present as _present
            from .system import SystemConfig as _SC
            first, last = d.rows[0], d.rows[-1]
            _out = _dc("demo", last.application,
                       _SC(**first.config), _SC(**last.config),
                       (_SA(1, "Demonstration", d.question),
                        _SA(2, "Starting point", first.label),
                        _SA(3, "Current design", last.label)))
            _present(_out)
            return _out
