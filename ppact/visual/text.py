"""
ppact.visual.text - one bar, one wrap, one set of characters

WHY THIS EXISTS
===============
An inventory of the visualisation layer found the same bar drawn six times,
in six modules, with four different fill characters and three different
rounding rules:

    decide.py      "#" and " "     round
    game.py        "#" and "-"     round
    game.py        "*" and "."     round        (a star rating)
    progress.py    "#" and "."     round
    runtime.py     "#", "~", "."   round
    report.py      "#" only        round, no track
    innovation.py  "#" only        round, no track

and the wrapping helper copied into seven modules with slightly different
widths. Nothing was wrong with any single one; the problem is that adding a
seventh screen means choosing between them, and the choice will be made by
whichever file was open at the time.

THE RULE THIS ENFORCES
----------------------
Every text bar in the program comes from here. A screen passes VALUES and
gets characters back; it does not decide what a bar looks like. That is the
only way two screens showing the same quantity look the same.

WHAT THIS IS NOT
----------------
It is not a chart library and it does not compute anything. Given a number
it draws a bar; given a percentage it draws a proportion. If a screen wants
a different number it must compute a different number, and a refactor of
this file can therefore never change an analytical result - which is checked.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

# One vocabulary. Chosen rather than inherited: '#' reads as filled in every
# font and terminal, '.' reads as a track rather than as a minus sign, and
# neither depends on colour. A blocked segment is '~' because it must be
# distinguishable from filled WITHOUT colour - on a monochrome printout, in a
# log file, and to a reader who cannot tell red from green.
FILL = "#"
TRACK = "."
BLOCKED = "~"
IDLE = " "

DEFAULT_WIDTH = 24


def render_bar(value: float, maximum: float = 100.0,
               width: int = DEFAULT_WIDTH, fill: str = FILL,
               track: str = TRACK, min_visible: bool = False) -> str:
    """A proportion, as characters.

    min_visible shows one cell for a non-zero value that would otherwise
    round to nothing - useful where a reader must see that a station exists
    at all, and wrong where the bar is being read as a quantity.
    """
    if maximum <= 0:
        return track * width
    frac = max(0.0, min(1.0, value / maximum))
    filled = int(round(width * frac))
    if min_visible and value > 0 and filled == 0:
        filled = 1
    return fill * filled + track * (width - filled)


def render_stacked_bar(segments: Sequence[Tuple[float, str]],
                       total: float = 100.0,
                       width: int = DEFAULT_WIDTH,
                       track: str = TRACK) -> str:
    """Several proportions end to end, each with its own character.

    The characters carry the meaning, not colour. A stacked bar that needs
    colour to be read is a stacked bar that cannot be printed, logged, or
    read by somebody who does not see colour the way the author does.
    """
    if total <= 0:
        return track * width
    out = ""
    for value, ch in segments:
        frac = max(0.0, min(1.0, value / total))
        out += ch * int(round(width * frac))
    return (out + track * width)[:width]


def render_progress(done: int, total: int,
                    width: int = DEFAULT_WIDTH) -> str:
    """How far through something a person is."""
    return render_bar(done, max(1, total), width)


def render_rating(score: float, out_of: float = 100.0,
                  steps: int = 5) -> str:
    """A coarse score.

    Deliberately NOT stars. A five-star rating reads like a review of a
    restaurant and invites comparison with things that have nothing to do
    with this - the same objection that removed a star rating from the
    confidence report. Where an exact figure exists, print the figure.
    """
    filled = int(round(max(0.0, min(1.0, score / out_of)) * steps))
    return FILL * filled + TRACK * (steps - filled)


def wrap_text(text: str, width: int) -> List[str]:
    """The one wrapper. Seven copies of this existed, with three widths."""
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


def render_labelled_bars(rows: Sequence[Tuple[str, float]],
                         total: Optional[float] = None,
                         label_width: int = 22,
                         width: int = DEFAULT_WIDTH,
                         unit: str = "%") -> List[str]:
    """A set of named proportions, aligned. The common case.

    The label is always printed beside the bar. A bar without its label is a
    shape, and a legend somewhere else is a second thing to read.
    """
    if total is None:
        total = sum(v for _, v in rows) or 1.0
    out = []
    for name, value in rows:
        share = value / total * 100 if total else 0.0
        out.append(f"{name[:label_width]:<{label_width}s}"
                   f"{render_bar(value, total, width, min_visible=True)}"
                   f"{share:6.1f}{unit}")
    return out


LEGEND = {
    FILL: "in use",
    BLOCKED: "blocked, waiting for something else",
    TRACK: "idle",
}


def legend_line(chars: Sequence[str] = (FILL, BLOCKED, TRACK)) -> str:
    """What the characters mean, printed beside them rather than elsewhere."""
    return "   ".join(f"{c} {LEGEND[c]}" for c in chars if c in LEGEND)


# ==============================================================================
# Semantic types
# ==============================================================================
#
# Standardising the CHARACTER was only half the job. A caller that picks its
# own characters can still give "blocked" a different look on two screens, and
# the point of a shared layer is that it cannot.
#
# So a state has a NAME here, and the name owns the character. Different
# states keep different patterns on purpose: work, blocked and idle are three
# things, and rendering them alike would be tidiness at the cost of meaning.
# The patterns are also the ONLY carrier - no colour - so the distinction
# survives a monochrome printout, a log file, and a reader who does not see
# colour the way the author does.

STATE_PATTERN = {
    "work": FILL,
    "blocked": BLOCKED,
    "idle": TRACK,
}

STATE_MEANING = {
    "work": "doing the job",
    "blocked": "waiting for something else",
    "idle": "nothing to do",
}

STATE_ORDER = ("work", "blocked", "idle")


def render_state_bar(states: Dict[str, float], total: float = 100.0,
                     width: int = DEFAULT_WIDTH) -> str:
    """A module's time, by state. The caller names states, not characters."""
    segments = [(states.get(name, 0.0), STATE_PATTERN[name])
                for name in STATE_ORDER if name != "idle"]
    return render_stacked_bar(segments, total, width)


def state_legend(names: Sequence[str] = STATE_ORDER) -> str:
    return "   ".join(f"{STATE_PATTERN[n]} {n}" for n in names
                      if n in STATE_PATTERN)


# ==============================================================================
# Measured results bars
# ==============================================================================
#
# A physical value against its requirement, in a terminal.
#
# Until now this existed only as a matplotlib PNG, so anybody running in a
# plain terminal received no visualization of physical values at all - the
# product's own introduction material promised a measured-bar layer that a
# terminal user never saw.
#
# The requirement sits at a FIXED COLUMN across every row. That is the whole
# design: it makes "how close am I to the limit" readable down the column
# rather than row by row, and it means a row with no requirement is visibly
# different rather than quietly rescaled.

REQUIREMENT_MARK = "|"
BAR_WIDTH = 30
REQUIREMENT_COLUMN = 22        # where the mark sits when a limit exists


def render_measured_bars(readings: Sequence, label_width: int = 22,
                         width: int = BAR_WIDTH) -> List[str]:
    """Rows of value-against-requirement, with units.

    `readings` are MetricReading objects from ppact.review. This function
    computes nothing: it is handed a value, a limit and a unit, and returns
    characters.
    """
    import math as _m

    out: List[str] = []
    for r in readings:
        name = r.label[:label_width]
        # A metric the model could not compute has no bar to draw. It is
        # printed as not computed rather than skipped: a row missing from
        # a list of measured results reads as a metric that has no
        # requirement, which is a different thing.
        if r.value is None or _m.isnan(r.value):
            out.append(f"{name:<{label_width}s}{'not computed':<{width}s}")
            out.append(f"{'':<4s}the model did not produce this figure for "
                       f"this design")
            out.append("")
            continue
        if r.limit is None or r.limit <= 0:
            # No requirement exists. The bar is scaled to the value itself
            # and carries no mark - a requirement line is never invented to
            # fill the column.
            bar = FILL * width
            note = "no requirement stated"
        else:
            frac = r.value / r.limit
            filled = int(round(REQUIREMENT_COLUMN * min(frac, 1.0)))
            # A non-zero value must never render as an empty bar. A system
            # cost of 18.8 USD against a 1500 USD budget rounds to zero
            # cells and vanishes, and a reader sees "nothing" where the
            # answer is "comfortably inside". One cell is the difference
            # between a small value and no value.
            if filled == 0 and r.value > 0:
                filled = 1
            if frac <= 1.0:
                bar = (FILL * filled
                       + TRACK * (REQUIREMENT_COLUMN - filled)
                       + REQUIREMENT_MARK
                       + TRACK * (width - REQUIREMENT_COLUMN - 1))
            else:
                over = min(width - REQUIREMENT_COLUMN - 1,
                           int(round((frac - 1.0) * REQUIREMENT_COLUMN)))
                bar = (FILL * REQUIREMENT_COLUMN + REQUIREMENT_MARK
                       + FILL * over
                       + TRACK * (width - REQUIREMENT_COLUMN - 1 - over))
            # "limit 60" beside a value of 60 read as a near-miss when the
            # requirement was a FLOOR and 60 met it exactly. The text bars
            # now say which kind of requirement it is, and give the same
            # verdict wording the image does - two views of one reading
            # must not describe it differently.
            # HOW MUCH room is left, not merely whether any is.
            #
            # 498 mm2 against a 500 mm2 ceiling and 18.8 USD against 1500
            # both printed "within requirement", and the first is a design
            # one memory package away from failing. A reader deciding what
            # to change next needs the distance, not the verdict alone.
            kind = "max" if r.lower_is_better else "min"
            if r.lower_is_better:
                margin = (r.limit - r.value) / r.limit * 100.0
            else:
                margin = (r.value - r.limit) / r.limit * 100.0
            # A margin is a number; whether it is safe is a judgement, and
            # a reader scanning seven rows should not have to make it seven
            # times. The bands are fixed and printed, so the judgement is
            # the tool's and the reader can disagree with the threshold
            # rather than having to compute the distance themselves.
            if r.over:
                verdict = f"EXCEEDS by {abs(margin):.1f}%"
            else:
                band = margin_band(margin)
                shown = (f"{margin:.1f}%" if margin < 10 else
                         f"{margin:.0f}%")
                verdict = f"{band}, {shown} margin"
            note = f"{kind} {r.limit:.2f} {r.unit}   {verdict}"

        out.append(f"{name:<{label_width}s}{bar}  "
                   f"{r.value:>10.3g} {r.unit}")
        # Indented under the LABEL, not past the bar.
        #
        # Aligning to label_width + bar width put the note at column 59, so
        # "max 1500.00 USD  COMFORTABLE, 98% margin" ran to 100 characters
        # and the 78-column rule caught it. The note belongs to the row, not
        # to the end of its bar.
        out.append(f"{'':<4s}{note}")
        if getattr(r, "starting_value", None) is not None:
            out.append(f"{'':<4s}starting point "
                       f"{r.starting_value:.3g} {r.unit}")
        out.append("")
    return out


# Fixed bands, printed with the bars. A design at 0.4% of its area budget
# and one at 98% of its cost budget both read "within requirement", and one
# of them fails if a single memory package is added.
MARGIN_BANDS = ((2.0, "CRITICAL"), (10.0, "TIGHT"), (float("inf"),
                                                     "COMFORTABLE"))


def margin_band(margin_pct: float) -> str:
    for limit, name in MARGIN_BANDS:
        if margin_pct < limit:
            return name
    return "COMFORTABLE"


def measured_bars_legend() -> str:
    return (f"{FILL} value    {REQUIREMENT_MARK} requirement    "
            f"{TRACK} headroom")


def margin_legend() -> str:
    # Two lines. On one it reached 83 characters once indented into a
    # review, and a legend that has to be scrolled to read is not a legend.
    return ("margin bands:  CRITICAL under 2%    TIGHT under 10%\n"
            "               COMFORTABLE 10% or more")
