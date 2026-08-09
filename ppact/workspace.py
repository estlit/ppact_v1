"""
ppact.workspace - recent designs, saved designs, and getting them out

WHY THIS IS SMALL
=================
A researcher builds a candidate, looks at it, changes one field, looks again -
and by the fourth iteration cannot remember what the second one was. That is
the whole problem this solves, and solving more of it would be building a
project manager nobody asked for.

So: a short history that remembers itself, names a design can be saved under,
and a way to get the numbers into something else. Nothing is stored that
cannot be rebuilt from the configuration, because a file of cached results
goes stale the first time a coefficient moves and nothing notices.

Author: Roger Kim
Copyright (c) 2026 Roger Kim & EdgeChipLab
"""

from __future__ import annotations

import dataclasses
import json
import os
from typing import Dict, List, Optional, Tuple

LINE = "=" * 78
HISTORY_LIMIT = 12
STORE = "workspace.json"


def _path(root: str = ".") -> str:
    return os.path.join(root, STORE)


def _load(root: str = ".") -> Dict:
    try:
        with open(_path(root), encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {"recent": [], "saved": {}}
    data.setdefault("recent", [])
    data.setdefault("saved", {})
    return data


def _save(data: Dict, root: str = ".") -> bool:
    try:
        with open(_path(root), "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, sort_keys=True)
        return True
    except OSError:
        # A read-only folder must not turn an analysis into an error. The
        # history is a convenience; the result already happened.
        return False


def _as_dict(config) -> Dict:
    return {f.name: getattr(config, f.name)
            for f in dataclasses.fields(config)
            if getattr(config, f.name) is not None}


def remember(app_key: str, config, root: str = ".") -> None:
    """Add a design to the history, most recent first, without duplicates."""
    data = _load(root)
    entry = {"app": app_key, "config": _as_dict(config)}
    data["recent"] = ([entry]
                      + [e for e in data["recent"] if e != entry])[:HISTORY_LIMIT]
    _save(data, root)


def recent(root: str = ".") -> List[Dict]:
    return _load(root)["recent"]


def save_as(name: str, app_key: str, config, root: str = ".") -> bool:
    data = _load(root)
    data["saved"][name] = {"app": app_key, "config": _as_dict(config)}
    return _save(data, root)


def saved(root: str = ".") -> Dict:
    return _load(root)["saved"]


def forget_all(root: str = ".") -> bool:
    return _save({"recent": [], "saved": {}}, root)


def rebuild(entry: Dict):
    """A configuration from a stored entry. Nothing cached is trusted."""
    from .system import SystemConfig
    return entry["app"], SystemConfig(**entry["config"])


def describe(entry: Dict) -> str:
    c = entry["config"]
    bits = [c.get("compute", "?"), c.get("cpu", "?"),
            f"{c.get('memory', '?')} x{c.get('memory_devices', '?')}"]
    if c.get("secondary_compute"):
        bits.append(f"+ {c['secondary_compute']}")
    if c.get("preprocessing_mode"):
        bits.append(c["preprocessing_mode"])
    return f"{entry['app']}: " + ", ".join(bits)


# ==============================================================================
# Getting the numbers out
# ==============================================================================

EXPORT_METRICS = (
    "Latency (ms)", "Sensor-to-control (ms)", "Pipeline capacity (inf/s)",
    "Delivered throughput (inf/s)", "System power (W)",
    "Energy per inference (mJ)", "Logic silicon (mm2)",
    "System cost (USD)", "Deployment accuracy (%)",
)


def export_csv(entries: List[Dict], path: str, root: str = ".") -> str:
    """One row per design. Recomputed, never read from a cache.

    A file of stored results goes stale the first time a coefficient moves,
    and nothing notices. So an export runs the model again - which also means
    an exported figure and a figure on screen cannot disagree.
    """
    import csv
    from .application import APPLICATION_LIBRARY
    from .system import evaluate_system
    from . import __version__

    rows = []
    for entry in entries:
        app_key, cfg = rebuild(entry)
        r = evaluate_system(APPLICATION_LIBRARY[app_key], cfg)
        row = {"version": __version__, "application": app_key,
               "status": r.status, "passes": "yes" if r.passes else "no",
               "bound_by": r.bound_by,
               "failed_gates": ",".join(sorted(g for g, ok in r.gate.items()
                                               if not ok))}
        row.update({k: v for k, v in entry["config"].items()})
        for m in EXPORT_METRICS:
            row[m] = r.metrics.get(m, "")
        rows.append(row)

    if not rows:
        return ""
    fields = []
    for row in rows:
        for k in row:
            if k not in fields:
                fields.append(k)
    full = os.path.join(root, path)
    with open(full, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    return full


def print_workspace(root: str = ".") -> None:
    data = _load(root)
    print(f"\n{LINE}")
    print(" WORKSPACE")
    print(LINE)
    r = data["recent"]
    if r:
        print(f"  Recent, newest first:")
        for i, e in enumerate(r, 1):
            print(f"    {i:2d}. {describe(e)}")
    else:
        print(f"  Nothing recent. Build a candidate and it will appear here.")
    if data["saved"]:
        print(f"\n  Saved:")
        for name, e in sorted(data["saved"].items()):
            print(f"    {name:<20s}{describe(e)}")
    print(f"\n  Only the configuration is stored, never the results. A file "
          f"of")
    print(f"  cached numbers goes stale the first time a coefficient moves,")
    print(f"  and nothing notices - so an export runs the model again.")
    print(LINE)


# ==============================================================================
# Finding things
# ==============================================================================
#
# The menu is now seventeen tools across six modes. Somebody who wants to know
# what is limiting a design does not know the tool is called "explain", and a
# search that matched only names would send them back to reading the menu -
# which is the thing they were trying to avoid.
#
# So descriptions are searched too, and a docstring is treated as part of the
# name of a thing.

# Words a person would actually type, pointed at the tool that answers them.
# Built by hand because the alternative - hoping the word appears in a
# docstring - failed the first search tried: "bottleneck" matched nothing,
# while three separate tools answer exactly that question.
CONCEPTS = {
    "bottleneck": ("task_decide", "task_runtime", "task_lessons"),
    "limit": ("task_decide", "task_review"),
    "headroom": ("task_decide",),
    "upper bound": ("task_decide", "task_review"),
    "why": ("task_decide", "task_lessons"),
    "explain": ("task_decide", "task_review"),
    "recommend": ("task_review", "task_decide"),
    "trade": ("task_review",),
    "cost": ("task_review", "task_sweep", "task_workspace"),
    "roi": ("task_review",),
    "what if": ("task_whatif",),
    "slider": ("task_whatif",),
    "compare": ("task_whatif", "task_decide", "task_workspace"),
    "assumption": ("task_sensitivity", "task_decide"),
    "sensitivity": ("task_sensitivity",),
    "robust": ("task_sensitivity", "task_decide"),
    "confidence": ("task_sensitivity", "task_decide"),
    "memory": ("task_memory", "task_memory_generations", "task_decide"),
    "hbm": ("task_memory_generations", "task_demo"),
    "bandwidth": ("task_memory", "task_memory_generations"),
    "capacity": ("task_memory_generations", "task_framework"),
    "power": ("task_sweep", "task_decide"),
    "thermal": ("task_decide", "task_framework"),
    "cooling": ("task_decide", "task_framework"),
    "node": ("task_migration", "task_demo"),
    "process": ("task_migration",),
    "llm": ("task_memory_generations", "task_framework"),
    "language model": ("task_memory_generations",),
    "batch": ("task_memory_generations", "task_framework"),
    "learn": ("task_lessons", "task_game"),
    "lesson": ("task_lessons",),
    "quiz": ("task_lessons",),
    "exam": ("task_challenge", "task_lessons"),
    "challenge": ("task_challenge", "task_innovation"),
    "assignment": ("task_challenge", "task_rubric"),
    "grade": ("task_rubric", "task_challenge"),
    "demo": ("task_demo",),
    "surprising": ("task_demo",),
    "validate": ("task_validation_summary", "task_reproducibility"),
    "evidence": ("task_validation_summary", "task_framework"),
    "reproduce": ("task_reproducibility",),
    "export": ("task_workspace",),
    "save": ("task_workspace",),
    "recent": ("task_workspace",),
    "sweep": ("task_sweep",),
    "design space": ("task_sweep",),
}


def search(term: str) -> Dict[str, List[Tuple[str, str]]]:
    """Substring, case-insensitive, over names, descriptions and concepts."""
    from .application import APPLICATION_LIBRARY
    from .compute import COMPUTE_LIBRARY
    from .memory import MEMORY_LIBRARY
    from .cpu import CPU_LIBRARY
    from . import menu, modes

    t = term.strip().lower()
    if not t:
        return {}
    found: Dict[str, List[Tuple[str, str]]] = {}

    def add(group: str, key: str, label: str) -> None:
        found.setdefault(group, []).append((key, label))

    for key, spec in APPLICATION_LIBRARY.items():
        if key.startswith("__"):
            continue
        if t in f"{key} {spec.name} {getattr(spec, 'domain', '')}".lower():
            add("applications", key, spec.name)
    for lib, group in ((COMPUTE_LIBRARY, "engines"),
                       (MEMORY_LIBRARY, "memories"),
                       (CPU_LIBRARY, "hosts")):
        for key, spec in lib.items():
            if t in f"{key} {getattr(spec, 'name', '')}".lower():
                add(group, key, getattr(spec, "name", key))
    by_name = {fn.__name__: label for label, fn in menu.TASKS}
    hits: List[str] = []
    for label, fn in menu.TASKS:
        doc = " ".join((fn.__doc__ or "").split())
        if t in f"{label} {doc}".lower():
            hits.append(fn.__name__)
    # the mode entries describe the same tools in the words a reader chose
    for m in modes.MODES:
        for entry_label, task in m.entries:
            if t in entry_label.lower() and task not in hits:
                hits.append(task)
    for word, tasks in CONCEPTS.items():
        if t in word or word in t:
            for task in tasks:
                if task not in hits:
                    hits.append(task)
    for task in hits:
        if task in by_name:
            add("tools", task, by_name[task])

    for m in modes.MODES:
        if t in f"{m.title} {m.one_line} {m.purpose}".lower():
            add("modes", m.key, m.title)
    return found


def print_search(term: str) -> Dict:
    found = search(term)
    print(f"\n{LINE}")
    print(f" SEARCH  {term!r}")
    print(LINE)
    if not found:
        print(f"  Nothing matched.")
        print(f"\n  Names and descriptions are both searched, so a word for")
        print(f"  what you want it to DO usually finds more than a word for")
        print(f"  what it is called.")
        print(LINE)
        return found
    for group in sorted(found):
        print(f"\n  {group}")
        for key, label in found[group][:8]:
            print(f"     {key:<28s}{label}")
        if len(found[group]) > 8:
            print(f"     ... and {len(found[group]) - 8} more")
    print(LINE)
    return found


# ==============================================================================
# One design, as a document
# ==============================================================================

def _boundary_block() -> str:
    """The full statement, on every exported file, whatever the session.

    A file travels on its own. A boundary that depended on having read an
    earlier screen is a boundary that disappears the moment the file is
    forwarded, which is exactly when it matters most.
    """
    from .review import BOUNDARY_FULL
    from .visual import wrap_text
    lines = ["", "## Assumptions and Model Boundaries", ""]
    lines += wrap_text(BOUNDARY_FULL, 74)
    return "\n".join(lines) + "\n"


def export_markdown(entry: Dict, path: str, root: str = ".",
                    title: str = "") -> str:
    """A single design and its numbers. Recomputed, like the CSV."""
    import math
    from .application import APPLICATION_LIBRARY
    from .system import evaluate_system
    from . import __version__

    app_key, cfg = rebuild(entry)
    app = APPLICATION_LIBRARY[app_key]
    r = evaluate_system(app, cfg)

    out = [f"# {title or app.name}", "",
           f"PPACT Studio {__version__}", "", "## Design", "",
           "| field | value |", "|---|---|"]
    for k, v in sorted(entry["config"].items()):
        out.append(f"| {k} | {v} |")

    out += ["", "## Result", "", "| measure | value |", "|---|---|"]
    for m in EXPORT_METRICS:
        if m not in r.metrics:
            continue
        v = r.metrics[m]
        shown = ("not evaluated"
                 if isinstance(v, float) and math.isnan(v) else f"{v:.3f}")
        out.append(f"| {m} | {shown} |")

    failed = sorted(g for g, ok in r.gate.items() if not ok)
    out += ["", "## Deployment", "",
            f"**{'READY' if r.passes else 'NOT READY'}**", ""]
    out.append(f"Unmet requirements: {', '.join(failed)}." if failed
               else "Every deployment constraint is satisfied.")
    out += ["", f"Limited by {r.bound_by} ({r.bound_strength}).", "",
            "---", "",
            "Every figure above was recomputed when this file was written, "
            "so it cannot disagree with what was on screen. Nothing is read "
            "from a cache - a stored result goes stale the first time a "
            "coefficient moves, and nothing notices."]
    out.append(_boundary_block())
    full = os.path.join(root, path)
    try:
        with open(full, "w", encoding="utf-8") as fh:
            fh.write("\n".join(out))
    except OSError:
        return ""
    return full
