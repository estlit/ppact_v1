"""
================================================================================
 Semiconductor School - AI 반도체 기술기획
 PPACT Simulator - Google Colab
================================================================================
 In a Colab cell:

     %run run_colab.py

 A menu appears. Pick a number. Run the cell again for another task.

 A Colab runtime starts empty, so the files have to arrive first. This looks
 for them in order:

   1. the working directory, extracting PPACT_Simulator.zip if present
   2. package files left loose by a flat extraction
   3. Google Drive at MyDrive/PPACT_Simulator.zip, if Drive is mounted
   4. an upload prompt

 To use Drive, mount it in the cell before this one:

     from google.colab import drive
     drive.mount("/content/drive")

 Author: Roger Kim
 Copyright (c) 2026 Roger Kim & EdgeChipLab
================================================================================
"""

from __future__ import annotations

import importlib
import os
import shutil
import sys
import zipfile

REQUIRED_VERSION = "4.19.0"

# Every module that belongs inside ppact/. Kept in sync with the package: a
# module missing here would be left behind when a flat extraction is repaired,
# producing a half-assembled package that fails much later and confusingly.
PACKAGE_MODULES = {
    "__init__.py", "__main__.py", "core.py", "process.py", "memory.py",
    "compute.py", "cpu.py", "application.py", "system.py", "report.py",
    "charts.py", "workflow.py", "menu.py", "game.py", "preprocess.py", "runtime.py", "innovation.py", "designs.py", "accuracy.py", "revisions.py", "coefficients.py", "validation.py", "memory_sweep.py", "evidence.py", "industry.py", "crossval.py", "interpret.py", "gold.py", "migration.py", "explain.py", "sensitivity.py", "reproducibility.py", "economics.py",
    "branding.py", "modes.py", "lessons.py", "progress.py", "challenge.py", "demo.py", "decide.py", "framework.py", "workspace.py", "industry_profiles.py", "arch_classes.py", "about.py", "guided.py", "questions.py", "text_capture.py", "closure.py", "flow_map.py", "view_data.py", "demo_library.py", "demo_visual.py", "reference_space.py", "traffic.py", "perf_bottleneck.py", "track.py", "evaluation_mode.py", "recommendation.py", "power_basis.py", "dashboard.py", "cost.py", "area.py", "power.py", "test_registry.py", "mutation_checkpoint.py", "memory_analysis.py", "performance_constraints.py", "bottleneck.py", "review.py", "terminology.py",
}

# Sub-packages have to be listed separately: os.listdir on the package
# directory returns "visual" as a directory, not its contents, so a
# half-extracted subpackage would have passed the file check above.
PACKAGE_SUBPACKAGES = {
    "visual": {"__init__.py", "text.py", "models.py", "balance.py"},
}


# ------------------------------------------------------------------------------
# Locating the package
#
# This file must work no matter how the archive was extracted or where the
# kernel happens to be. %run executes a script without putting its folder on
# sys.path, and a notebook's working directory is frequently somewhere else
# entirely, so nothing about the environment can be assumed. The only reliable
# starting point is this file's own location.
#
# Three broken layouts show up repeatedly and are all recoverable:
#   - the archive extracted flat, leaving the modules loose beside this file
#   - only this file and the .zip present
#   - an older copy left behind from a previous download
# The last one is the reason for the version check: silently importing a stale
# package produces confusing errors far from their cause.
# ------------------------------------------------------------------------------

try:
    HERE = os.path.dirname(os.path.abspath(__file__))
except NameError:                      # pasted into a cell instead of %run
    HERE = os.getcwd()


def _package_version(root):
    """Version of the ppact package under `root`, or None if unusable."""
    init = os.path.join(root, "ppact", "__init__.py")
    if not os.path.isfile(init):
        return None
    try:
        with open(init, encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("__version__"):
                    return line.split("=", 1)[1].strip().strip('"\'')
    except OSError:
        return None
    return "unknown"


def _candidate_roots():
    yield HERE
    yield os.path.join(HERE, "PPACT_Simulator")
    parent = os.path.dirname(HERE)
    if parent and parent != HERE:
        yield parent
    try:
        for entry in sorted(os.listdir(HERE)):
            full = os.path.join(HERE, entry)
            if os.path.isdir(full) and entry != "ppact":
                yield full
    except OSError:
        pass


def _find_root(require_version=True):
    fallback = None
    for root in _candidate_roots():
        version = _package_version(root)
        if version is None:
            continue
        if not require_version or version == REQUIRED_VERSION:
            return root
        fallback = fallback or root
    return None if require_version else fallback


def _extract_archives():
    """Unpack any PPACT archive sitting beside this file."""
    found = False
    try:
        entries = sorted(os.listdir(HERE))
    except OSError:
        return False
    for entry in entries:
        if entry.lower().endswith(".zip") and "ppact" in entry.lower():
            try:
                with zipfile.ZipFile(os.path.join(HERE, entry)) as archive:
                    archive.extractall(HERE)
                print(f"  extracted {entry}")
                found = True
            except Exception as exc:
                print(f"  could not extract {entry}: {exc}")
    return found


def _gather_loose_modules():
    """Rebuild ppact/ from module files extracted flat beside this script."""
    try:
        present = PACKAGE_MODULES & set(os.listdir(HERE))
    except OSError:
        return False
    if "__init__.py" not in present or len(present) < 6:
        return False

    target = os.path.join(HERE, "ppact")
    os.makedirs(target, exist_ok=True)
    print(f"  found {len(present)} package files loose - collecting into ppact/")
    for name in sorted(present):
        try:
            shutil.move(os.path.join(HERE, name), os.path.join(target, name))
        except Exception as exc:
            print(f"    could not move {name}: {exc}")
            return False
    return True


def _stale_warning(root):
    version = _package_version(root)
    print("\n" + "=" * 70)
    print(f" An older copy of ppact is present (version {version}).")
    print("=" * 70)
    print(f"  Location : {os.path.join(root, 'ppact')}")
    print(f"  Expected : {REQUIRED_VERSION}")
    print("\n  Delete that folder, or extract the current PPACT_Simulator.zip")
    print("  into a clean directory, and run this launcher again.")
    print("=" * 70)


def _fail(reason):
    print("\n" + "=" * 70)
    print(f" {reason}")
    print("=" * 70)
    print(f"  This launcher : {HERE}")
    try:
        contents = sorted(os.listdir(HERE))
    except OSError:
        contents = []
    print(f"  Alongside it  : {', '.join(contents[:14])}"
          + (" ..." if len(contents) > 14 else ""))
    print("\n  Expected layout:")
    print("      PPACT_Simulator/")
    print("         run_jupyter.py")
    print("         run_colab.py")
    print("         ppact/")
    print("            __init__.py")
    print("            ...")
    print("\n  Extract PPACT_Simulator.zip keeping its folder structure and run")
    print("  the launcher from inside the extracted folder.")
    print("=" * 70)
    raise SystemExit(1)


def _purge_stale_modules():
    """Drop anything already imported under these names.

    A notebook kernel keeps every module it has ever imported. If an earlier
    version of the launcher ran in this session, `import ppact` returns the
    cached module object rather than reading the files again - so a freshly
    updated package on disk is ignored, and the failure surfaces as a missing
    attribute rather than an obvious version problem. The file-based version
    check cannot catch this, because the file is fine; it is memory that is
    stale. Purging here is what makes "extract the new zip and re-run the cell"
    actually work without restarting the kernel.
    """
    doomed = [name for name in sys.modules
              if name == "ppact" or name.startswith("ppact.")
              or name in ("bootstrap", "menu")]
    for name in doomed:
        del sys.modules[name]
    if doomed:
        print(f"  cleared {len(doomed)} cached module(s) from a previous run")
    importlib.invalidate_caches()


def locate_package(fetch_remote=False):
    """Return a directory containing an importable, current ppact package."""
    root = _find_root()

    if root is None and _extract_archives():
        root = _find_root()

    if root is None and _gather_loose_modules():
        root = _find_root()

    if root is None and fetch_remote:
        if _fetch_remote_archive():
            root = _find_root()

    if root is None:
        stale = _find_root(require_version=False)
        if stale is not None:
            if _extract_archives():
                root = _find_root()
            if root is None:
                _stale_warning(stale)
                raise SystemExit(1)
        else:
            _fail("The ppact package was not found.")

    root = os.path.abspath(root)
    if root not in sys.path:
        sys.path.insert(0, root)
    os.chdir(root)
    _purge_stale_modules()
    return root


def _fetch_remote_archive():
    """Colab only: pull the archive from Drive, or ask for an upload."""
    for path in ("/content/drive/MyDrive/PPACT_Simulator.zip",
                 "/content/drive/My Drive/PPACT_Simulator.zip"):
        if os.path.isfile(path):
            print(f"  found {path}")
            with zipfile.ZipFile(path) as archive:
                archive.extractall(HERE)
            return True
    try:
        from google.colab import files          # type: ignore
    except ImportError:
        return False
    print("  Upload PPACT_Simulator.zip using the file picker below.")
    try:
        uploaded = files.upload()
    except Exception:
        return False
    for name in uploaded:
        if name.lower().endswith(".zip"):
            with zipfile.ZipFile(os.path.join(HERE, name)) as archive:
                archive.extractall(HERE)
            return True
    return False


ROOT = locate_package(fetch_remote=True)
print("=" * 70)
print(f" PPACT Simulator - working in {ROOT}")
print("=" * 70)

import ppact                                                          # noqa: E402

if getattr(ppact, "__version__", None) != REQUIRED_VERSION:
    print("\n" + "=" * 70)
    print(" A different version of ppact is loaded than the one on disk.")
    print("=" * 70)
    print(f"  Imported from : {getattr(ppact, '__file__', '?')}")
    print(f"  Version       : {getattr(ppact, '__version__', 'unknown')}")
    print(f"  Expected      : {REQUIRED_VERSION}")
    print("\n  Restart the kernel and run this cell again.")
    print("=" * 70)
    raise SystemExit(1)

from ppact import (                                                  # noqa: E402
    run_application, sweep, compare_memories, evaluate_system,
    list_applications, list_libraries, set_figure_scale,
    play, show_result, compare_designs, evaluate_with_precision,
    SystemConfig, Application, ComputeSpec, CPUSpec, MemorySpec,
    APPLICATION_LIBRARY, COMPUTE_LIBRARY, CPU_LIBRARY, MEMORY_LIBRARY,
)
from ppact.modes import main as mode_menu                                     # noqa: E402

mode_menu()
