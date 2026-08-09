"""
ppact.branding - the name, the version, and what the program claims to be

WHY THE VERSION IS HERE AND NOT IN THE BANNER
=============================================
A version string typed into a print statement is a version string that gets
forgotten. This project has already shipped one release where certify.py
carried 3.84.0 and the package carried 3.82.0, and the symptom - a TypeError
about an argument count - looked like a defect in the model. One constant,
read everywhere.

The PRODUCT version and the ENGINE version are different numbers on purpose.
The engine is at 3.x because it has been revised three hundred times against
its own arithmetic; the product is at 1.0 because this is the first release
anybody outside is meant to use. Reporting the engine number to a student
would be reporting a fact about the developer's history rather than about
what they are holding.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

PRODUCT_NAME = "AI System PPACT Studio"
PRODUCT_VERSION = "1.0"

# The release LABEL, which is not the same as the version. A candidate and
# the release it becomes share a version and differ in label, and mixing the
# two across a zip name, a manifest and a screen is how somebody ends up
# testing one thing and shipping another. One constant, read everywhere.
# v1.0-RC3.1, not "RC3 Final" a second time.
#
# "Final" was applied at 4.17.1 and then a further change followed - the
# process-node display rework. A label that says Final twice, for two
# different archives, would be false about the first one. Keeping the
# correction visible in the name costs nothing; hiding it would mean the
# release history disagrees with what happened.
# v1.0-RC3.1, not "RC3 Final".
#
# "Final" was applied at 4.17.1 and then a further change followed - the
# process node display. Calling this one Final too would put the same name
# on two different archives, and renaming the earlier one is not possible
# because it no longer exists: it was deleted during this build, which is
# recorded in the revision log rather than tidied away.
#
# A label that admits the final release was not final is more accurate than
# one that hides it.
# v1.0-RC3.1, not "RC3 Final" again.
#
# "Final" was applied at 4.17.1 and a change arrived after it: the process
# node display moved off one foundry's naming. Reusing the earlier label
# would put two different archives under one name, and this project has
# refused that everywhere else - a name that identifies two things
# identifies neither.
#
# The ".1" records that the final was not final. That is more accurate than
# a name which hides it.
# v1.0-RC3.1, not "RC3 Final" again.
#
# "Final" was applied to 4.17.1 and then a change followed it. Reusing the
# name would say the earlier build had not existed; a new name says a
# release called final was not the last one, which is what happened.
# THE LABEL TRAVELS WITH THE FILES.
#
# A repository was updated file by file and ended up holding two
# releases at once: `ppact/` and `streamlit_app.py` from RC4 beside a
# `requirements.txt` and `run_jupyter.py` from two days earlier. Nothing
# in the tree said which release it was, so nothing could notice.
#
# The archive, the top-level directory inside it and this constant now
# all carry the label, and `check_release.py` requires them to agree. A
# new version therefore lands in a differently named directory and
# cannot silently merge with the old one.
# RC4 is preserved as the frozen artifact that went to the Cloud and
# failed there. RC4.1 carries one fix - the question capture - and
# nothing else, so a Cloud rerun compares two builds that differ in the
# one thing under test.
RELEASE_LABEL = "v1.0-RC4.3"
# THE FIVE PPACT AXES.
#
# Thermal was moved to the deployment gates - it is computed from
# power and area rather than chosen, so it is a check a product must
# clear and not a dimension a designer trades. Traffic took its
# place. The banner kept saying Thermal, so the first line a reader
# saw named a set of axes the tool no longer has.
AXES = "Performance - Power - Area - Cost - Traffic"
ORGANISATION = "EdgeChipLab"
CHANNEL = "https://www.youtube.com/@EdgeChipLab"

# What the program is, and what it is not. The last sentence is the one that
# matters: a tool that appeared to decide would be teaching students that
# tools decide, and the ones they use later will.
CLAIM = (
    "PPACT Studio evaluates AI system architectures using analytical "
    "models. Reported values are engineering estimates for design "
    "exploration. It explains what changed, why it changed, and what limits "
    "the design. Final engineering decisions remain the responsibility of "
    "the designer."
)

LINE = "=" * 61


def _wrap(text: str, width: int):
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


def banner(engine_version: str = "") -> str:
    """The startup screen. Identical on every run."""
    title = f"{PRODUCT_NAME} (v{PRODUCT_VERSION})"
    out = [LINE, f"{title:^61s}", f"{AXES:^61s}", LINE, ""]
    out += _wrap(CLAIM, 58)
    out += ["",
            f"Copyright (C) {ORGANISATION}. All rights reserved.",
            f"YouTube - {CHANNEL}"]
    if engine_version:
        out.append(f"Engine {engine_version}")
    out += ["", LINE]
    return "\n".join(out)


def print_banner(engine_version: str = "") -> None:
    print(banner(engine_version))
