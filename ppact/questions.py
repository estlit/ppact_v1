"""
ppact.questions - every question the program asks, defined once

WHY A REGISTRY
==============
A user was shown this:

    Memory packages [1]:
      1. 1
      2. 2
      3. 4
      4. 8

and could not tell what they were selecting. Four bare integers, a parameter
name that is nearly the internal variable, and no indication that the choice
moves capacity, bandwidth, cost and power at once.

That was not one bad prompt. Eleven questions in the design flow had the same
shape, because each was written where it was needed and nothing held them to
a common standard.

So the questions live here. A screen asks for one BY KEY and cannot invent a
wording, an option label, or a default of its own. The same definition then
feeds a terminal prompt and any later interface, which is the only mechanical
way two interfaces stay consistent.

THE RULE
--------
A user must understand the question before being expected to answer it.

That does not mean simplifying. PPACT Studio is a professional engineering
platform and should teach the vocabulary somebody will meet in commercial
tools - host processor, execution latency, thermal design power - rather than
replacing it with classroom words. Professional does not mean unexplained: a
term is used, and defined once where it first appears.

SCORE-ONLY VERSUS MODEL-CHANGING
--------------------------------
The distinction a user must never have to guess. Choosing a memory changes
what the model computes. Choosing a design priority changes only how the
educational score weights what was already computed. A question declares
which it is, and the prompt says so in words.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class Option:
    """One choice, with what it means in engineering terms."""
    value: Any
    label: str                  # what the user reads: "4 packages", "8 cores"
    note: str = ""              # the engineering consequence, one clause


@dataclass(frozen=True)
class QuestionDefinition:
    key: str
    parameter_name: str         # the professional term, title case
    short_description: str      # one or two sentences: what this IS
    effect: str                 # what selecting it can change
    options: Tuple[Option, ...]
    default: int = 1            # 1-based
    score_only: bool = False    # changes the score, not the model
    affected_metrics: Tuple[str, ...] = ()
    help_text: str = ""         # shown on H, never required to understand
    # The wording used when a selection is refused. A field rather than a
    # function so an interface cannot invent its own, and so the same
    # sentence appears in a terminal and in any later interface.
    validation_message: str = ""
    terms: Tuple[Tuple[str, str], ...] = ()   # term, definition
    # Some option lists come from a library rather than being written here -
    # the accelerator classes, for instance, must not be listed twice. The
    # builder is called when the question is asked, and its absence is what
    # makes an empty option list legitimate.
    option_builder: Optional[Callable[[], Tuple[Option, ...]]] = None

    def resolved(self) -> "QuestionDefinition":
        """The question with its options filled in."""
        if self.options or self.option_builder is None:
            return self
        import dataclasses as _dc
        built = tuple(self.option_builder())
        default = self.default if 1 <= self.default <= len(built) else 1
        return _dc.replace(self, options=built, default=default)

    # An engineering question has NO default. A preselected answer is read
    # as a recommendation - the standard configuration, the safe choice,
    # what the author would pick - and PPACT Studio does not recommend
    # architectures. Navigation questions may keep a default; deciding
    # something is not the same as going somewhere.
    requires_explicit_choice: bool = True

    def default_option(self) -> Optional[Option]:
        if self.requires_explicit_choice:
            return None
        return self.options[self.default - 1]


# Terms defined once and reused. A professional term is not removed; it is
# explained where it first appears and then used plainly.
def glossary_from_registry() -> Dict[str, str]:
    """Terms, taken from the terminology registry rather than retyped.

    The first version of this file kept its own glossary. Two glossaries
    become two definitions the moment one is edited, which is exactly the
    failure the terminology registry exists to prevent - and keeping a
    private copy here would have been that failure, committed by the file
    that argues against it.
    """
    from .terminology import TERMS
    return {t.canonical.lower(): t.definition for t in TERMS}


def _significance_of(term_name: str) -> str:
    """The first-appearance line for a term, from the terminology registry.

    Looked up by canonical name so a question does not restate it. A term
    explained in two places is explained differently in one of them.
    """
    from .terminology import TERMS
    wanted = term_name.strip().lower()
    for t in TERMS:
        if t.canonical.lower() == wanted:
            return t.first_use
    return ""


def first_use(key: str) -> str:
    """What to say the first time a reader meets a term."""
    from .terminology import BY_KEY
    term = BY_KEY.get(key)
    return term.first_use if term else ""


GLOSSARY = {
    "host-active time":
        "Time the host processor spends on preprocessing, dispatch and "
        "postprocessing for a single job.",
    "execution latency":
        "The time one job takes, from the first byte in to the last byte "
        "out.",
    "pipeline throughput":
        "How many jobs the system can complete per second when they overlap "
        "in the pipeline.",
    "thermal design power":
        "The sustained power the cooling solution is designed to remove.",
    "process node":
        "The manufacturing generation a die is built on. A finer node "
        "usually reduces area and power and raises wafer cost.",
    "memory unit":
        "One physical memory device on the board or in the package. What "
        "counts as a unit differs by memory type - see the unit name shown "
        "beside the count.",
    "architecture class":
        "A generalized performance and power band, not a commercial "
        "product.",
}

# What a memory generation's countable unit is actually called. Calling an
# HBM stack a "package" is wrong in a way an engineer notices immediately,
# and calling a DIMM one is wrong in a different way.
MEMORY_UNIT_NAME = {
    "DDR4": ("module", "modules"),
    "DDR5": ("module", "modules"),
    "LPDDR4": ("package", "packages"),
    "LPDDR4X": ("package", "packages"),
    "LPDDR5": ("package", "packages"),
    "LPDDR5X": ("package", "packages"),
    "GDDR6": ("device", "devices"),
    "HBM2E": ("stack", "stacks"),
    "HBM3": ("stack", "stacks"),
    "HBM3E": ("stack", "stacks"),
    "HBM4_36": ("stack", "stacks"),
    "HBM4_48": ("stack", "stacks"),
}

DEFAULT_UNIT_NAME = ("unit", "units")


def unit_name(memory_key: str, plural: bool = False) -> str:
    pair = MEMORY_UNIT_NAME.get(memory_key, DEFAULT_UNIT_NAME)
    return pair[1] if plural else pair[0]


# The sentence a score-only question must carry, and the one a
# model-changing question must carry. Fixed strings so they cannot drift.
SCORE_ONLY_NOTE = (
    "This selection changes the priority-weighted education score only. It "
    "does not change latency, throughput, power, area, cost or thermal "
    "estimates.")

MODEL_CHANGING_NOTE = (
    "This selection changes the modeled system configuration and therefore "
    "can affect the physical estimates.")


EMPTY_ENTRY_MESSAGE = (
    "This question requires an explicit engineering choice.")


class NonInteractiveEnvironmentError(RuntimeError):
    """No input is available and the question requires a decision.

    The earlier behaviour was to take the first option and say so. That was
    a default wearing a different name: it produced an analysis nobody
    chose, and printed it under the same heading as one somebody did. A
    result whose configuration was selected by the absence of a person is
    worse than no result, because it is indistinguishable from a real one
    once it is on screen or in a file.
    """


NON_INTERACTIVE_MESSAGE = (
    "This analysis requires explicit engineering decisions and cannot run "
    "without user input. Run it in an interactive session, or supply the "
    "configuration directly through the API.")


def empty_message(q) -> List[str]:
    """An empty entry is not a typo. It is a decision not yet made.

    Reporting it as `Invalid selection: ''` would tell a user they typed
    something wrong when they typed nothing, and would hide that the
    program is waiting for a decision rather than a correction.
    """
    q = q.resolved()
    numbers = ", ".join(str(i) for i in range(1, len(q.options)))
    numbers = f"{numbers}, or {len(q.options)}" if len(q.options) > 1 else "1"
    return ["No selection was entered.", "",
            EMPTY_ENTRY_MESSAGE,
            f"Enter one of the listed option numbers: {numbers}.",
            "Enter H for additional details."]


def invalid_message(q, entered: str) -> List[str]:
    """Actionable, not 'Invalid input'.

    Names what was rejected, lists what is accepted, and says what Enter
    does - because a user who does not know the default cannot use it.

    A question may carry its own validation_message for a case the generic
    wording handles badly; the generic form is used otherwise, so no
    question has to write one to be correct.
    """
    q = q.resolved()
    numbers = ", ".join(str(i) for i in range(1, len(q.options)))
    numbers = f"{numbers}, or {len(q.options)}" if len(q.options) > 1 else "1"
    out = [f"Invalid selection: {entered!r}", ""]
    if q.validation_message:
        out += wrap_lines(q.validation_message, 68)
        out.append("")
    out.append(f"Enter one of the listed option numbers: {numbers}.")
    if not q.requires_explicit_choice:
        out.append(f"Press Enter to keep the default selection: "
                   f"{q.default_option().label}.")
    out.append("Enter H for additional details.")
    return out


def wrap_lines(text: str, width: int) -> List[str]:
    from .visual import wrap_text
    return wrap_text(text, width)


HELP_INPUTS = ("h", "help", "?")


def help_lines(q) -> List[str]:
    """Everything a reader could want about one question, on request.

    Not a longer version of the description. The description says what the
    parameter IS; this says what the choice touches, what the terms mean,
    what happens if nothing is entered, and - the thing a user most often
    needs - whether this changes the design or only the marking.
    """
    q = q.resolved()
    out = [f"{q.parameter_name} - additional details", ""]
    out += [f"  {line}" for line in wrap_lines(q.short_description, 66)]
    out.append("")

    out.append("  What this selection changes")
    note = _effect_note(q)
    out += [f"    {line}" for line in wrap_lines(note, 64)]
    if q.affected_metrics:
        out.append("")
        out.append("  Metrics it can move")
        for m in q.affected_metrics:
            out.append(f"    {m}")
    if q.effect:
        out.append("")
        out += [f"    {line}" for line in wrap_lines(q.effect, 64)]

    out.append("")
    out.append("  Options")
    for i, opt in enumerate(q.options, 1):
        out.append(f"    {i}. {opt.label}"
                   + (f"   {opt.note}" if opt.note else ""))

    out.append("")
    if q.requires_explicit_choice:
        out.append("  This question requires an explicit engineering "
                   "choice.")
        out.append("  Pressing Enter selects nothing.")
    else:
        out.append(f"  Default if nothing is entered")
        out.append(f"    {q.default_option().label}")

    if q.terms:
        out.append("")
        out.append("  Terms")
        for term, meaning in q.terms:
            out.append(f"    {term}")
            out += [f"      {line}" for line in wrap_lines(meaning, 60)]

    if q.help_text:
        out.append("")
        out += [f"  {line}" for line in wrap_lines(q.help_text, 66)]

    # THE FIGURES. This is what "additional details" has to mean.
    #
    # Before this, H repeated the question and added four metric names. A
    # reader saw the same screen twice and reasonably asked what had
    # happened. What the program actually holds - the numbers that decide
    # whether a design passes - was never shown, and prose about them is
    # weaker than the numbers.
    out.append("")
    builder = DETAIL_TABLES.get(q.key)
    if builder is not None:
        try:
            out += [f"  {line}" if line else "" for line in builder()]
        except Exception as exc:
            out.append(f"  (detail table unavailable: "
                       f"{type(exc).__name__})")
    else:
        # Said plainly. Padding a question that has no figures would put
        # the reader back where they started: a heading promising more
        # than the screen delivers.
        out += [f"  {line}" for line in wrap_lines(NO_DETAIL_TABLE, 66)]

    out.append("")
    out.append("  Returning to the question.")
    return out


def ask_question(q, input_fn=None,
                 print_fn=print, context: Sequence[str] = ()) -> Any:
    """Show a question and take an answer. The one place a prompt is run.

    input_fn is injectable so the help path can be driven by a test. A help
    handler nobody can exercise is a help handler nobody knows works, and
    this one was promised on screen before it existed.

    Seeing the help must not change the selection or skip the question: the
    loop returns to the same prompt with the same default.
    """
    q = q.resolved()
    reader = input_fn if input_fn is not None else input
    while True:
        for line in render_question(q, context):
            print_fn(f"  {line}" if line else "")
        try:
            prompt_text = ("\n  Selection: " if q.requires_explicit_choice
                           else f"\n  Selection "
                                f"[{q.default_option().label}]: ")
            raw = reader(prompt_text)
            raw = (raw or "").strip()
        except NonInteractiveEnvironmentError:
            raise
        except Exception:
            # No stdin.
            #
            # A question requiring an explicit choice CANNOT be answered by
            # silence. Taking the first option and announcing it would be a
            # default under another name - and the announcement scrolls
            # past while the analysis it produced stays on screen.
            if q.requires_explicit_choice:
                print_fn("")
                print_fn(f"  {q.parameter_name}")
                for line in wrap_lines(NON_INTERACTIVE_MESSAGE, 68):
                    print_fn(f"  {line}")
                print_fn("")
                raise NonInteractiveEnvironmentError(
                    f"{q.parameter_name}: {NON_INTERACTIVE_MESSAGE}")
            print_fn(f"  (no input available - using "
                     f"{q.default_option().label})")
            return q.default_option().value

        if not raw:
            if q.requires_explicit_choice:
                print_fn("")
                for line in empty_message(q):
                    print_fn(f"  {line}")
                print_fn("")
                continue
            return q.default_option().value

        if raw.lower() in HELP_INPUTS:
            print_fn("")
            for line in help_lines(q):
                print_fn(f"  {line}" if line else "")
            print_fn("")
            continue

        if raw.isdigit() and 1 <= int(raw) <= len(q.options):
            return q.options[int(raw) - 1].value

        print_fn("")
        for line in invalid_message(q, raw):
            print_fn(f"  {line}")
        print_fn("")


def _effect_note(q) -> str:
    """Which fixed sentence a question carries about its own consequences."""
    if isinstance(q, NavigationQuestion):
        return NAVIGATION_NOTE
    return SCORE_ONLY_NOTE if q.score_only else MODEL_CHANGING_NOTE


def render_question(q, context: Sequence[str] = (),
                    show_help: bool = False) -> List[str]:
    """The prompt, as lines. One shape for every question in the program."""
    from .visual import wrap_text

    out: List[str] = []
    if context:
        out += list(context)
        out.append("")

    out.append(q.parameter_name)
    out.append("")
    for line in wrap_text(q.short_description, 68):
        out.append(f"  {line}")
    out.append("")
    note = _effect_note(q)
    for line in wrap_text(note, 68):
        out.append(f"  {line}")
    if q.effect:
        out.append("")
        for line in wrap_text(q.effect, 68):
            out.append(f"  {line}")

    out.append("")
    for i, opt in enumerate(q.options, 1):
        line = f"  {i}. {opt.label}"
        if opt.note:
            line += f"   {opt.note}"
        out.append(line)

    if q.terms:
        out.append("")
        # A FIXED ORDER on first appearance: the term, what it means, why it
        # matters here. A reader who meets "execution latency" halfway down
        # a list of options has to hold an unknown word while reading about
        # it; met first, defined second, the word is available by the time
        # the options arrive.
        for term, meaning in q.terms:
            out.append(f"  {term}")
            for line in wrap_text(meaning, 64):
                out.append(f"    {line}")
            significance = _significance_of(term)
            if significance:
                out.append(f"    Why it matters here: {significance}")

    if show_help and q.help_text:
        out.append("")
        for line in wrap_text(q.help_text, 68):
            out.append(f"  {line}")
    elif q.help_text:
        out.append("")
        out.append(f"  Type H for additional details.")
    return out


# One version per registry. A question changing meaning is a change the
# documentation audit must see, and a version is how it sees it.
REGISTRY_VERSION = "1.0"
REGISTRY_COMPATIBILITY = "PPACT Studio 1.x"

REGISTRY: Dict[str, QuestionDefinition] = {}


def register(q: QuestionDefinition) -> QuestionDefinition:
    if q.key in REGISTRY:
        raise ValueError(f"question {q.key!r} is registered twice")
    REGISTRY[q.key] = q
    return q


def get(key: str) -> QuestionDefinition:
    return REGISTRY[key]


def question_violations() -> List[str]:
    """Every rule the audit enforces, checkable from here too."""
    problems = []
    for key, q in REGISTRY.items():
        if q.key != key:
            problems.append(f"{key}: key disagrees with the definition")
        if not q.parameter_name or q.parameter_name.islower():
            problems.append(f"{key}: no user-facing parameter name")
        if len(q.short_description) < 30:
            problems.append(f"{key}: not explained")
        if not q.options and q.option_builder is None:
            problems.append(f"{key}: no options and no way to build them")
        q = q.resolved()
        if not q.options:
            problems.append(f"{key}: the option builder produced nothing")
            continue
        for opt in q.options:
            if not opt.label or opt.label.strip().isdigit():
                problems.append(
                    f"{key}: option {opt.value!r} has a bare number for a "
                    f"label - a user cannot tell what four of something is")
        if not 1 <= q.default <= len(q.options):
            problems.append(f"{key}: default out of range")
        if not q.score_only and not q.affected_metrics:
            problems.append(
                f"{key}: model-changing and names no affected metric")
        if q.score_only and q.affected_metrics:
            problems.append(
                f"{key}: score-only and claims to affect a metric")
        # an internal variable name must not be the visible parameter name
        for internal in ("memory_devices", "work_split", "compute",
                         "alternative_share", "preprocessing_mode",
                         "accel_node", "soc_node", "cpu"):
            if q.parameter_name.lower() == internal.replace("_", " "):
                problems.append(
                    f"{key}: the parameter name is the internal field name")
    return problems


# ==============================================================================
# The questions
# ==============================================================================
#
# Written in the vocabulary somebody will meet in a commercial engineering
# tool. A student who learns "host processor" and "execution latency" here
# recognises them elsewhere; a student who learns "the CPU bit" does not.

def memory_unit_count_question(memory_key: str,
                               counts: Sequence[int] = (1, 2, 4, 8)
                               ) -> QuestionDefinition:
    """Built per memory type, because the unit is not the same thing.

    An HBM stack, an LPDDR package and a DDR module are three different
    physical objects. The model counts an abstract unit; the prompt must say
    which object that unit corresponds to for the memory actually chosen,
    because calling a stack a package is wrong in a way an engineer notices
    at once.
    """
    singular = unit_name(memory_key)
    plural = unit_name(memory_key, plural=True)
    options = tuple(
        Option(c, f"{c} {singular if c == 1 else plural}")
        for c in counts)
    return QuestionDefinition(
        key="memory_unit_count",
        parameter_name="Memory Unit Count",
        short_description=(
            f"Select how many identical {memory_key} {plural} are included "
            f"in the modeled system configuration."),
        effect=(
            "Total capacity and the modeled aggregate bandwidth scale with "
            "this count according to the memory model. Memory cost, memory "
            "power and board area scale with it as well."),
        options=options,
        default=2 if len(options) > 1 else 1,
        affected_metrics=("Memory capacity (GB)",
                          "Effective bandwidth (GB/s)",
                          "System cost (USD)", "System power (W)",
                          "Board area (mm2)"),
        terms=(("Memory unit", GLOSSARY["memory unit"]),),
        help_text=(
            "The engine holds one abstract unit count and derives capacity "
            "and bandwidth from the selected memory's per-unit figures. The "
            "word shown beside the number is the physical object that unit "
            "corresponds to for this memory generation: a stack for HBM, a "
            "package for LPDDR, a module for DDR."),
    )


def memory_context(memory_key: str) -> List[str]:
    """What the user is configuring, shown BEFORE the count is asked.

    A count is meaningless without the thing being counted. Showing the
    per-unit figures first is what turns "4" into a decision.
    """
    from .memory import MEMORY_LIBRARY, evaluate

    spec = MEMORY_LIBRARY[memory_key]
    result = evaluate(spec)
    per_unit_gb = result.metrics.get("Package capacity (GB)")
    per_unit_bw = result.metrics.get("Package peak bandwidth (GB/s)")
    singular = unit_name(memory_key)

    out = ["Selected Memory", f"  {spec.name}"]
    if per_unit_gb is not None:
        out.append(f"  {per_unit_gb:.0f} GB per {singular}")
    if per_unit_bw is not None:
        out.append(f"  {per_unit_bw:.0f} GB/s per {singular} (peak)")
    return out


def memory_summary(memory_key: str, count: int) -> List[str]:
    """What was actually configured, shown AFTER the count is chosen.

    Anything the model does not compute is named as such rather than
    estimated into the table. A figure a reader cannot distinguish from a
    computed one is worse than a gap.
    """
    from .memory import MEMORY_LIBRARY, evaluate

    spec = MEMORY_LIBRARY[memory_key]
    result = evaluate(spec)
    per_gb = result.metrics.get("Package capacity (GB)")
    per_bw = result.metrics.get("Package peak bandwidth (GB/s)")
    plural = unit_name(memory_key, plural=True)

    out = ["Memory Configuration", ""]
    out.append(f"  {'Memory type':<28s}{spec.name}")
    out.append(f"  {'Unit type':<28s}{unit_name(memory_key)}")
    out.append(f"  {'Unit count':<28s}{count}")
    if per_gb is not None:
        out.append(f"  {'Total capacity':<28s}{per_gb * count:.0f} GB")
    if per_bw is not None:
        out.append(f"  {'Peak bandwidth':<28s}{per_bw * count:.0f} GB/s")
        out.append(f"  {'Modeled effective bandwidth':<28s}"
                   f"{per_bw * count * spec.bandwidth_efficiency:.0f} GB/s")
    out.append("")
    out.append(f"  Peak bandwidth scales with the unit count. The modeled")
    out.append(f"  effective figure applies this memory's controller and")
    out.append(f"  access-pattern efficiency of "
               f"{spec.bandwidth_efficiency:.2f}.")
    out.append("")
    out.append(f"  {'Memory cost':<28s}computed in the system result")
    out.append(f"  {'Memory power':<28s}computed in the system result")
    out.append(f"  Both depend on the workload and are reported with the")
    out.append(f"  design rather than here.")
    return out


# --- the remaining design-flow questions --------------------------------

# memory_unit_count is built per memory type by
# memory_unit_count_question(), because the unit name depends on the memory
# chosen. A representative instance is registered so the audit can see it.
register(memory_unit_count_question("LPDDR5"))

register(QuestionDefinition(
    key="application",
    parameter_name="Target Application",
    short_description=(
        "Select the product the architecture is being designed for. The "
        "application supplies the workload, the arrival rate and every "
        "requirement the design is judged against."),
    effect=("Every requirement, budget and workload figure comes from this "
            "choice. It is the first decision and it constrains all the "
            "others."),
    options=(),         # filled at call time from the library
    affected_metrics=("Latency (ms)", "Delivered throughput (inf/s)",
                      "System power (W)", "System cost (USD)"),
    help_text=(
        "The application is not a setting to tune. It carries the model "
        "size, the frame rate, the accuracy the product needs, and every "
        "budget the design is measured against - so the same accelerator "
        "passes in one application and fails in another without changing "
        "at all."),
))

register(QuestionDefinition(
    key="host_processor",
    parameter_name="Host Processor",
    short_description=(
        "Select the processor responsible for preprocessing, dispatch, "
        "scheduling and postprocessing. The accelerator does the "
        "arithmetic; the host does everything around it."),
    effect=("A more capable host usually reduces host-active time and "
            "raises power, silicon area and system cost."),
    options=(),
    affected_metrics=("Latency (ms)", "CPU active (ms)", "System power (W)",
                      "System cost (USD)", "Total silicon (mm2)"),
    terms=(("Host-active time", GLOSSARY["host-active time"]),),
))

register(QuestionDefinition(
    key="accelerator_class",
    parameter_name="AI Accelerator Class",
    short_description=(
        "Select the accelerator class for the primary AI workload. A class "
        "is a generalized performance and power band, not a commercial "
        "product."),
    effect=("Determines modeled compute throughput, accelerator power, "
            "silicon area and cost. A larger class does not always reduce "
            "execution latency - it does so only while the arithmetic is "
            "the limit."),
    options=(),
    affected_metrics=("Latency (ms)", "Compute time (ms)",
                      "System power (W)", "Total silicon (mm2)",
                      "System cost (USD)"),
    terms=(("Architecture class", GLOSSARY["architecture class"]),),
))

register(QuestionDefinition(
    key="memory_type",
    parameter_name="Memory Technology",
    short_description=(
        "Select the external memory generation. This sets the per-unit "
        "capacity, the per-unit bandwidth, the energy per bit and the "
        "cooling class the memory requires."),
    effect=("Bandwidth, capacity, memory power and memory cost all follow "
            "from this choice, as does whether the design can be cooled "
            "passively."),
    options=(),
    affected_metrics=("Effective bandwidth (GB/s)", "Memory capacity (GB)",
                      "System power (W)", "System cost (USD)"),
))

register(QuestionDefinition(
    key="bandwidth_utilisation",
    parameter_name="Memory Controller Efficiency",
    short_description=(
        "Select the fraction of peak memory bandwidth the controller and "
        "access pattern are assumed to deliver. Peak bandwidth is a pin "
        "rate; no real access pattern reaches it."),
    effect=("Scales the delivered bandwidth, and therefore any part of "
            "execution latency spent waiting for data."),
    options=(
        Option(0.60, "60% of peak", "conservative: scattered access"),
        Option(0.72, "72% of peak", "typical for this memory class"),
        Option(0.85, "85% of peak", "well-tiled, largely sequential"),
        Option(0.95, "95% of peak", "optimistic bound"),
    ),
    default=2,
    affected_metrics=("Effective bandwidth (GB/s)", "Memory time (ms)",
                      "Latency (ms)"),
    help_text=(
        "This is an assumption, not a measurement. Sensitivity analysis "
        "moves it across this range and reports whether a conclusion "
        "survives."),
))

register(QuestionDefinition(
    key="process_node",
    parameter_name="Process Node",
    short_description=(
        "Select the manufacturing generation the logic is built on. A finer "
        "node reduces area and switching power and raises wafer cost per "
        "square millimetre."),
    effect=("Changes silicon area, static and dynamic power, and die cost. "
            "It does not change memory bandwidth, so a memory-limited "
            "design may gain very little execution latency from it."),
    options=(),
    affected_metrics=("Total silicon (mm2)", "System power (W)",
                      "Logic die cost (USD)", "System cost (USD)"),
    terms=(("Process node", GLOSSARY["process node"]),),
))

register(QuestionDefinition(
    key="preprocessing_location",
    parameter_name="Preprocessing Location",
    short_description=(
        "Select where per-frame preprocessing runs before inference: on the "
        "host processor, on a dedicated image signal processor, or split "
        "between the ISP and the accelerator."),
    effect=("Moves work off the host, which usually reduces host-active "
            "time and adds an offload hand-off cost. On a host-limited "
            "design this is often the largest single change available."),
    options=(
        Option("cpu_only", "Host processor only",
               "no dedicated preprocessing block"),
        Option("isp_assisted", "ISP assisted",
               "image pipeline on a dedicated block"),
        Option("isp_and_npu", "ISP and accelerator",
               "preprocessing split off the host entirely"),
    ),
    default=1,
    affected_metrics=("CPU active (ms)", "Offload overhead (ms)",
                      "Latency (ms)", "ISP area (mm2)"),
    terms=(("Host-active time", GLOSSARY["host-active time"]),),
))

register(QuestionDefinition(
    key="offload_handoff",
    parameter_name="Offload Hand-off Mode",
    short_description=(
        "Select whether preprocessing results are handed to the accelerator "
        "one frame at a time or in batches. Batching amortises the "
        "per-hand-off cost and adds latency to the first frame in a batch."),
    effect=("Changes offload overhead and therefore execution latency and "
            "pipeline throughput, in opposite directions."),
    options=(
        Option(True, "Batched hand-off",
               "lower overhead per frame, higher first-frame latency"),
        Option(False, "Per-frame hand-off",
               "lowest first-frame latency, highest overhead"),
    ),
    default=1,
    affected_metrics=("Offload overhead (ms)", "Latency (ms)",
                      "Pipeline capacity (inf/s)"),
))

register(QuestionDefinition(
    key="precision",
    parameter_name="Numeric Precision",
    short_description=(
        "Select the numeric format the accelerator uses for inference. A "
        "narrower format moves fewer bytes and does more arithmetic per "
        "second, and costs accuracy."),
    effect=("Changes memory traffic, compute throughput and deployment "
            "accuracy together. An accuracy requirement can reject a format "
            "that is quicker on every other axis."),
    options=(),
    affected_metrics=("Deployment accuracy (%)", "DRAM traffic (MB)",
                      "Compute time (ms)", "Latency (ms)"),
))

register(QuestionDefinition(
    key="design_priority",
    parameter_name="Design Priority",
    short_description=(
        "Select the engineering objective that receives the highest weight "
        "in the educational score. This orders the axes; it does not change "
        "the design."),
    effect="",
    options=(
        Option("Accuracy", "Accuracy first"),
        Option("Performance", "Execution latency first"),
        Option("Power", "Power efficiency first"),
        Option("Cost", "Lowest system cost"),
        Option("Area", "Smallest silicon area"),
        Option("Thermal", "Largest thermal margin"),
    ),
    default=1,
    score_only=True,
    help_text=(
        "Two designs can score the same with opposite choices. What a "
        "student defends is the priority order, not the number."),
))


# --- option builders ----------------------------------------------------
#
# These read the libraries rather than repeating them. A class listed in two
# places is a class that disagrees with itself after the first edit.

def _application_options():
    from .application import APPLICATION_LIBRARY
    return tuple(
        Option(k, spec.name, spec.domain)
        for k, spec in APPLICATION_LIBRARY.items() if not k.startswith("__"))


def _host_options():
    from .cpu import CPU_LIBRARY
    return tuple(Option(k, spec.name) for k, spec in CPU_LIBRARY.items())


def _accelerator_options():
    from .compute import COMPUTE_LIBRARY
    return tuple(
        # A class of 0.4 TOPS printed as "0 TOPS" reads as broken. Small
        # engines keep a decimal; large ones do not need one.
        Option(k, f"{spec.peak_tops:.1f} TOPS  {spec.name}"
                  if spec.peak_tops < 10
                  else f"{spec.peak_tops:.0f} TOPS  {spec.name}",
               spec.category)
        for k, spec in COMPUTE_LIBRARY.items())


def _memory_options():
    from .memory import MEMORY_LIBRARY
    return tuple(
        Option(k, spec.name,
               f"{unit_name(k)}s, {spec.cooling_requirement} cooling")
        for k, spec in MEMORY_LIBRARY.items())


def _node_options():
    """A node key alone is a code. "N7" tells a first-time reader nothing
    about what it costs or what it buys, and the label is the only place
    they will look."""
    from .process import NODE_LIBRARY, nodes_in_order
    out = []
    for k in nodes_in_order():
        spec = NODE_LIBRARY[k]
        # The dimension is the name. The remark about why the node is in
        # the table goes in the note, where a reader can tell it apart
        # from the name itself.
        note = spec.description or ""
        if note:
            note += "   "
        note += (f"logic area x{spec.logic_area:.2f}, "
                 f"wafer x{spec.wafer_cost_factor:.2f}")
        out.append(Option(k, spec.user_name, note))
    return tuple(out)


def _precision_options():
    from .game import PRECISION_OPTIONS
    return tuple(
        Option(k, v.get("label", k) if isinstance(v, dict) else str(k),
               v.get("note", "") if isinstance(v, dict) else "")
        for k, v in PRECISION_OPTIONS.items())


for _key, _builder in (("application", _application_options),
                       ("host_processor", _host_options),
                       ("accelerator_class", _accelerator_options),
                       ("memory_type", _memory_options),
                       ("process_node", _node_options),
                       ("precision", _precision_options)):
    import dataclasses as _dcq
    REGISTRY[_key] = _dcq.replace(REGISTRY[_key], option_builder=_builder)


register(QuestionDefinition(
    key="sweep_objective",
    parameter_name="Sweep Ranking Metric",
    short_description=(
        "Select the metric the design-space sweep ranks candidates by. "
        "Every candidate is evaluated on all metrics; this chooses which "
        "one orders the table."),
    effect=("Changes the order of the results and therefore which designs "
            "appear at the top. It does not change any candidate's figures, "
            "and a design that ranks first on one metric can rank last on "
            "another."),
    options=(
        Option("Energy per inference (mJ)", "Energy per inference",
               "lower is favourable, in mJ"),
        Option("Latency (ms)", "Execution latency",
               "lower is favourable, in ms"),
        Option("System cost (USD)", "System cost",
               "lower is favourable, in USD"),
        Option("System power (W)", "System power",
               "lower is favourable, in W"),
        Option("Total silicon (mm2)", "Total silicon area",
               "lower is favourable, in mm2"),
    ),
    default=1,
    score_only=True,
    help_text=(
        "Ranking is a view, not a verdict. The sweep reports every metric "
        "for every candidate; sorting by one of them is how a reader "
        "navigates the table, and the design at the top is the best on that "
        "metric alone."),
))

register(QuestionDefinition(
    key="memory_comparison_set",
    parameter_name="Memory Technologies to Compare",
    short_description=(
        "Select which memory generations to place side by side. The "
        "comparison is at component level: bandwidth, capacity, energy per "
        "bit, die area and cost per package, with no workload attached."),
    effect=("Changes which technologies appear in the comparison. No figure "
            "changes: each memory's characteristics are the same whatever "
            "it is compared against."),
    options=(
        Option("all", "All memory technologies",
               "every generation in the library"),
        Option("LPDDR5, GDDR6", "LPDDR5 against GDDR6",
               "low power against graphics-class"),
        Option("LPDDR5, HBM3E", "LPDDR5 against HBM3E",
               "low power against stacked"),
    ),
    default=1,
    score_only=True,
    help_text=(
        "A component comparison answers what a memory IS, not what it does "
        "for a design. A stacked memory has the highest bandwidth here and "
        "can still be the wrong choice, because this view has no workload "
        "and no budget in it."),
))


register(QuestionDefinition(
    key="model_assumption",
    parameter_name="Model Assumption",
    short_description=(
        "Select which modelling assumption to move across its plausible "
        "range. The sweep reports whether the conclusion survives being "
        "moved, and names the assumption when it does not."),
    effect=("Changes which assumption is varied. Every design's figures at "
            "the nominal value are unchanged; what the sweep reports is how "
            "far a conclusion holds when the assumption does not."),
    options=(),
    default=1,
    score_only=True,
    option_builder=lambda: _sweep_options(),
    help_text=(
        "A conclusion that reverses inside an assumption's range is a "
        "property of the assumption as much as of the design. That is worth "
        "knowing before the design is defended, not after."),
))

register(QuestionDefinition(
    key="baseline_accelerator",
    parameter_name="Baseline Accelerator Compute Class",
    short_description=(
        "Select the accelerator class the comparison starts from. This is "
        "the design the second one is measured against, and every reported "
        "change is relative to it."),
    effect=("Sets the reference point. A change reported as an improvement "
            "is an improvement over THIS design and no other."),
    options=(),
    option_builder=lambda: _accelerator_options(),
    default=5,
    affected_metrics=("Latency (ms)", "System power (W)",
                      "System cost (USD)", "Total silicon (mm2)"),
))

register(QuestionDefinition(
    key="comparison_accelerator",
    parameter_name="Comparison Accelerator Compute Class",
    short_description=(
        "Select the accelerator class to compare against the baseline. The "
        "report describes what changed relative to the baseline and why."),
    effect=("Determines what is compared. The pair is what the reason "
            "breakdown decomposes; neither design's own figures depend on "
            "the other."),
    options=(),
    option_builder=lambda: _accelerator_options(),
    default=6,
    affected_metrics=("Latency (ms)", "System power (W)",
                      "System cost (USD)", "Total silicon (mm2)"),
))

register(QuestionDefinition(
    key="baseline_memory",
    parameter_name="Baseline Memory Technology",
    short_description=(
        "Select the memory generation the comparison starts from. Capacity, "
        "bandwidth and cooling class all follow from this choice."),
    effect=("Sets the memory the comparison is measured against."),
    options=(),
    option_builder=lambda: _memory_options(),
    default=1,
    affected_metrics=("Effective bandwidth (GB/s)", "Memory capacity (GB)",
                      "System cost (USD)"),
))

register(QuestionDefinition(
    key="comparison_memory",
    parameter_name="Comparison Memory Technology",
    short_description=(
        "Select the memory generation to compare against the baseline. A "
        "higher-bandwidth memory helps only while bandwidth is the limit."),
    effect=("Determines what is compared. A memory that is quicker in "
            "isolation can leave execution latency unchanged when the "
            "design is limited elsewhere."),
    options=(),
    option_builder=lambda: _memory_options(),
    default=2,
    affected_metrics=("Effective bandwidth (GB/s)", "Memory capacity (GB)",
                      "System cost (USD)"),
))


def _sweep_options():
    from .sensitivity import build_sweeps
    out = [Option(sw.sid, f"{sw.sid}  {sw.description[:52]}")
           for sw in build_sweeps()]
    out.append(Option("__all__", "All assumptions",
                      "every sweep, one after another"))
    return tuple(out)


# ==============================================================================
# Navigation
# ==============================================================================
#
# Not every prompt sets a model value. "What would you like to do" picks a
# screen; it has no engineering effect, no affected metric, and no default
# worth defending.
#
# Forcing the parameter shape onto those produces noise - a paragraph about
# engineering consequences above a list of menu items - and noise is how a
# standard stops being read. So navigation is a SECOND kind, with its own
# smaller contract:
#
#     a name, an explanation of what the choice leads to, and options
#     whose labels say where they go
#
# What it does NOT get is an exemption from the registry path. A navigation
# prompt still goes through ask_question, still handles H, and still refuses
# a bad entry with the same wording. The distinction is what a question must
# DECLARE, not whether it is governed.

@dataclass(frozen=True)
class NavigationQuestion:
    """Navigation may carry a default. Deciding is not the same as going.

    What it may NEVER default to is Back, Exit, Cancel or Return. If Enter
    means "leave", users leave by accident - and the education menu did
    exactly that, defaulting to the trailing Back entry.
    """
    parameter_name: str
    short_description: str
    options: Tuple[Option, ...]
    default: int = 1
    help_text: str = ""

    # the parameter-question interface, so one renderer serves both
    effect: str = ""
    score_only: bool = True
    affected_metrics: Tuple[str, ...] = ()
    terms: Tuple[Tuple[str, str], ...] = ()
    validation_message: str = ""
    key: str = "navigation"
    option_builder: Optional[Callable[[], Tuple[Option, ...]]] = None
    requires_explicit_choice: bool = False

    def resolved(self) -> "NavigationQuestion":
        return self

    # An engineering question has NO default. A preselected answer is read
    # as a recommendation - the standard configuration, the safe choice,
    # what the author would pick - and PPACT Studio does not recommend
    # architectures. Navigation questions may keep a default; deciding
    # something is not the same as going somewhere.
    requires_explicit_choice: bool = True

    def default_option(self) -> Optional[Option]:
        if self.requires_explicit_choice:
            return None
        return self.options[self.default - 1]


NAVIGATION_NOTE = (
    "This selection chooses what to look at next. It does not change any "
    "design or any estimate.")


def navigate(name: str, description: str, labels: Sequence[str],
             default: int = 1, values: Optional[Sequence[Any]] = None,
             help_text: str = "") -> NavigationQuestion:
    """Build a navigation prompt. Still governed, still helped, still checked."""
    vals = list(values) if values is not None else list(range(1, len(labels) + 1))
    return NavigationQuestion(
        parameter_name=name,
        short_description=description,
        options=tuple(Option(v, str(lbl)) for v, lbl in zip(vals, labels)),
        default=default,
        help_text=help_text,
        requires_explicit_choice=False,
    )


# ==============================================================================
# One definition, used everywhere
# ==============================================================================
#
# A term defined one way in the help and another in the methodology is two
# ideas wearing one name. This is the sentence, and a check requires it to
# appear verbatim in ABOUT, HELP and METHODOLOGY.

# Imported, not copied. A definition written in two files is two
# definitions, and the second one drifts.
from .terminology import STARTING_POINT_DEFINITION  # noqa: E402,F401


# ==============================================================================
# Detail tables for the help screen
# ==============================================================================
#
# "Type H for additional details" promised more than it delivered: the help
# repeated the question and added four metric names. A reader who pressed H
# saw the same screen twice and reasonably wondered what had happened.
#
# The details worth showing are not more prose. They are the FIGURES the
# library already holds - the ones that decide whether a design passes - and
# a question whose options carry no figures says so rather than padding.

def _fmt(value, unit: str = "", nd: int = 0) -> str:
    if value is None:
        return "-"
    if isinstance(value, float) and value != int(value):
        return f"{value:,.{max(nd,1)}f}{unit}"
    return f"{int(value):,}{unit}"


def application_details() -> List[str]:
    """What each application demands. The reason one design passes here and
    fails there, as numbers rather than as a sentence about it."""
    from .application import APPLICATION_LIBRARY

    out = ["What each application requires", ""]
    out.append(f"  {'':<20s}{'rate':>8s}{'latency':>10s}"
               f"{'power':>9s}{'cost':>10s}{'silicon':>10s}")
    out.append(f"  {'':<20s}{'inf/s':>8s}{'ms':>10s}"
               f"{'W':>9s}{'USD':>10s}{'mm2':>10s}")
    out.append("  " + "-" * 67)
    for k, a in APPLICATION_LIBRARY.items():
        out.append(
            f"  {a.name[:19]:<20s}"
            f"{_fmt(a.target_inferences_per_s):>8s}"
            f"{_fmt(a.latency_budget_ms):>10s}"
            f"{_fmt(a.power_budget_w):>9s}"
            f"{_fmt(a.bom_budget_usd):>10s}"
            f"{_fmt(a.soc_silicon_budget_mm2):>10s}")
    out.append("")
    out.append("  The same accelerator meets one row and misses another. "
               "Nothing")
    out.append("  about the accelerator changes between those two "
               "sentences.")
    return out


def application_workload_details() -> List[str]:
    """The work itself, which is what the budgets have to be met against."""
    from .application import APPLICATION_LIBRARY

    out = ["", "The work each one asks for", ""]
    out.append(f"  {'':<20s}{'model':>12s}{'weights':>10s}"
               f"{'streams':>9s}{'accuracy':>10s}")
    out.append(f"  {'':<20s}{'MMAC/job':>12s}{'MB':>10s}"
               f"{'':>9s}{'needed %':>10s}")
    out.append("  " + "-" * 63)
    for k, a in APPLICATION_LIBRARY.items():
        out.append(
            f"  {a.name[:19]:<20s}"
            f"{a.mac_per_inference / 1e6:>12,.1f}"
            f"{a.weight_bytes / 1e6:>10,.1f}"
            f"{a.streams:>9d}"
            f"{a.required_accuracy_pct:>10.1f}")
    return out


def memory_details() -> List[str]:
    """Capacity, bandwidth and what each generation needs to stay cool."""
    from .memory import MEMORY_LIBRARY, evaluate

    out = ["What each memory technology provides, per unit", ""]
    out.append(f"  {'':<12s}{'capacity':>10s}{'peak BW':>11s}"
               f"{'efficiency':>12s}{'cooling':>12s}")
    out.append(f"  {'':<12s}{'GB':>10s}{'GB/s':>11s}"
               f"{'':>12s}{'':>12s}")
    out.append("  " + "-" * 57)
    for k, spec in MEMORY_LIBRARY.items():
        m = evaluate(spec).metrics
        out.append(
            f"  {k:<12s}"
            f"{m.get('Package capacity (GB)', 0):>10,.0f}"
            f"{m.get('Package peak bandwidth (GB/s)', 0):>11,.0f}"
            f"{spec.bandwidth_efficiency:>12.2f}"
            f"{spec.cooling_requirement:>12s}")
    out.append("")
    out.append("  Peak bandwidth is a pin rate. The efficiency column is "
               "the share")
    out.append("  a real access pattern is modelled to reach.")
    return out


def accelerator_details() -> List[str]:
    """Arithmetic, area and power per class - the three that trade."""
    from .compute import COMPUTE_LIBRARY

    out = ["What each accelerator class costs and delivers", ""]
    # Field names read from the dataclass, not guessed. The first version
    # asked for area_mm2 and power_w, which do not exist, and getattr's
    # default printed a column of 0.00 that looked like a measurement.
    # "array 32" under a heading of MACs reads as thirty-two multipliers.
    # It is the side of a 32x32 array, which is 1,024 of them - a factor of
    # a thousand, in the column a reader uses to compare classes.
    out.append(f"  {'':<18s}{'peak':>10s}{'array':>10s}{'clock':>9s}"
               f"{'SRAM':>9s}{'cost':>9s}")
    out.append(f"  {'':<18s}{'TOPS':>10s}{'side':>10s}{'GHz':>9s}"
               f"{'kB':>9s}{'USD':>9s}")
    out.append("  " + "-" * 66)
    for k, spec in COMPUTE_LIBRARY.items():
        out.append(
            f"  {spec.name[:17]:<18s}"
            f"{spec.peak_tops:>10.2f}"
            f"{spec.mac_array:>7,d}x{spec.mac_array:<2,d}"
            f"{spec.clock_ghz:>9.2f}"
            f"{spec.sram_kb:>9,.0f}"
            f"{spec.cost_usd:>9,.0f}")
    out.append("")
    out.append("  A larger class shortens the arithmetic only. It does "
               "nothing")
    out.append("  for the time spent on the host or waiting for memory.")
    return out


def host_details() -> List[str]:
    """What the host brings, since it often holds most of a job."""
    from .cpu import CPU_LIBRARY

    out = ["What each host processor provides", ""]
    out.append(f"  {'':<20s}{'cores':>7s}{'clock':>8s}{'active':>9s}"
               f"{'die':>9s}{'cost':>9s}")
    out.append(f"  {'':<20s}{'':>7s}{'GHz':>8s}{'W':>9s}"
               f"{'mm2':>9s}{'USD':>9s}")
    out.append("  " + "-" * 63)
    for k, spec in CPU_LIBRARY.items():
        out.append(
            f"  {spec.name[:19]:<20s}"
            f"{spec.cores:>7d}"
            f"{spec.clock_ghz:>8.2f}"
            f"{spec.active_power_w:>9.2f}"
            f"{spec.die_area_mm2:>9.2f}"
            f"{spec.cost_usd:>9,.0f}")
    out.append("")
    out.append("  The host runs preprocessing, dispatch and "
               "postprocessing. In")
    out.append("  many designs it holds more of a job than the "
               "accelerator does.")
    return out


def node_details() -> List[str]:
    """Scaling factors, which is all a node is in this model."""
    from .process import NODE_LIBRARY, nodes_in_order

    out = ["What each process node changes", ""]
    out.append(f"  {'':<10s}{'logic':>10s}{'SRAM':>9s}"
               f"{'energy':>9s}{'wafer':>9s}   note")
    out.append(f"  {'':<10s}{'area x':>10s}{'area x':>9s}"
               f"{'x':>9s}{'cost x':>9s}")
    out.append("  " + "-" * 68)
    for k in nodes_in_order():
        s = NODE_LIBRARY[k]
        out.append(
            f"  {s.user_name:<10s}{s.logic_area:>10.2f}{s.sram_area:>9.2f}"
            f"{s.energy:>9.2f}{s.wafer_cost_factor:>9.2f}   "
            f"{s.description}")
    out.append("")
    out.append("  Factors relative to the 16nm scaling reference. A finer "
               "node")
    out.append("  reduces area and switching energy and raises wafer cost.")
    return out


# Which question gets which table. A question with no entry gets no table,
# and says so rather than being padded.
DETAIL_TABLES: Dict[str, Callable[[], List[str]]] = {
    "application": lambda: application_details()
                           + application_workload_details(),
    "memory_type": memory_details,
    "baseline_memory": memory_details,
    "comparison_memory": memory_details,
    "accelerator_class": accelerator_details,
    "baseline_accelerator": accelerator_details,
    "comparison_accelerator": accelerator_details,
    "host_processor": host_details,
    "process_node": node_details,
}

NO_DETAIL_TABLE = (
    "There are no further figures for this question. Its options are "
    "assumptions or orderings rather than components with measured "
    "properties, so everything the model uses is on the screen already.")


# ==============================================================================
# Editing an existing design
# ==============================================================================
#
# Challenge and the final exam let a student change fields of a design that
# already exists. Both printed the INTERNAL FIELD NAME and the RAW VALUE:
#
#     preprocessing_mode [1]:        memory_devices [2]:
#       1. cpu_only                    1. 1
#       2. isp_assisted                2. 2
#       3. isp_and_npu                 3. 4
#       4. leave as it is              4. 8
#                                      5. leave as it is
#
# Nothing on the second screen says what 1, 2, 4 and 8 are, and both names
# are variables rather than anything a person would say. Every one of these
# fields already has a registry entry with a professional name, an
# explanation and labelled options - the screens simply were not using it.

# Which registry question governs which configuration field.
FIELD_QUESTION = {
    "compute": "accelerator_class",
    "cpu": "host_processor",
    "memory": "memory_type",
    "memory_devices": "memory_unit_count",
    "preprocessing_mode": "preprocessing_location",
    "soc_node": "process_node",
    "accel_node": "process_node",
    "bandwidth_efficiency": "bandwidth_utilisation",
    "offload_batching": "offload_handoff",
    # A second accelerator has no registry question of its own; the
    # accelerator question's labels describe the same components, and
    # "none" is added by the caller as a real option.
    "secondary_compute": "accelerator_class",
}

KEEP_CURRENT = "Keep the current value"


def field_question(field_name: str, allowed: Sequence[Any],
                   current: Any) -> QuestionDefinition:
    """A registry question narrowed to the values this exercise allows.

    The option labels come from the registry, so "4" becomes "4 packages"
    and "isp_assisted" becomes the labelled choice with its note. Values
    the exercise does not offer are dropped rather than shown and refused.

    "Keep the current value" stays IN the list and names what it would
    keep. It is a real choice here - the design already exists - but it is
    not a value, so leaving it unlabelled put a non-value in a list of
    values with nothing to tell them apart.
    """
    key = FIELD_QUESTION.get(field_name)
    base = REGISTRY.get(key).resolved() if key in REGISTRY else None

    if base is not None:
        by_value = {o.value: o for o in base.options}
        options = []
        for v in allowed:
            o = by_value.get(v)
            if o is not None:
                options.append(o)
            elif v is None:
                # "None" is what a Python value prints as, not what a
                # designer calls the absence of a second accelerator.
                options.append(Option(None, "No second accelerator",
                                      "one engine does all the work"))
            else:
                options.append(Option(v, str(v)))
        name = base.parameter_name
        description = base.short_description
        effect = base.effect
        help_text = base.help_text
        terms = base.terms
        metrics = base.affected_metrics
    else:
        # No registry entry. Say the field name rather than inventing a
        # nice one, so a missing mapping is visible instead of disguised.
        options = [Option(v, str(v)) for v in allowed]
        name = field_name
        description = (f"Select a value for {field_name}. This field has no "
                       f"registry entry, so no explanation is available.")
        effect = ""
        help_text = ""
        terms = ()
        metrics = ("Latency (ms)",)

    current_label = next((o.label for o in options if o.value == current),
                         "not set" if current is None else str(current))
    options.append(Option("__keep__",
                          f"{KEEP_CURRENT} ({current_label})",
                          "changes nothing"))

    import dataclasses as _dcf
    if base is not None:
        return _dcf.replace(base, options=tuple(options),
                            option_builder=None, key=f"edit_{field_name}")
    return QuestionDefinition(
        key=f"edit_{field_name}", parameter_name=name,
        short_description=description, effect=effect,
        options=tuple(options), affected_metrics=metrics,
        terms=terms, help_text=help_text)


def field_option_labels(field_name: str, allowed: Sequence[Any]) -> str:
    """The allowed values of a field, as a person would read them.

    Used by the 'what you may change' summary, which printed raw values
    beside a raw field name.
    """
    key = FIELD_QUESTION.get(field_name)
    base = REGISTRY.get(key)
    if base is None:
        return ", ".join(str(v) for v in allowed)
    by_value = {o.value: o.label for o in base.resolved().options}
    return ", ".join(str(by_value.get(v, v)) for v in allowed)


def field_display_name(field_name: str) -> str:
    key = FIELD_QUESTION.get(field_name)
    base = REGISTRY.get(key)
    return base.parameter_name if base is not None else field_name
