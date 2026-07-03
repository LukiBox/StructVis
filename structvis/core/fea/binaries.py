"""
Locating the CalculiX solver binary (ccx).

Search order (mirrors Flovis's binaries.py):
  1. environment variable STRUCTVIS_CCX (full path),
  2. the bundled resources/bin directory (PyInstaller build),
  3. the system PATH (ccx, ccx_static, ccx_2.22, ...).

The app degrades gracefully when ccx is absent: everything except the actual
solve works, and the UI shows a clear hint (same UX as Flovis's missing-Ollama).
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

# common console names for CalculiX across distributions
_CCX_NAMES = ["ccx", "ccx_dynamic", "ccx_static",
              "ccx_2.22", "ccx_2.21", "ccx_2.20", "ccx_2.19"]


def _bin_dir() -> Path:
    if getattr(sys, "frozen", False):       # PyInstaller
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        return base / "resources" / "bin"
    # structvis/core/fea/binaries.py -> structvis/resources/bin
    return Path(__file__).resolve().parents[2] / "resources" / "bin"


# subfolders (relative to a PATH entry) where solvers are commonly bundled;
# e.g. PrePoMax ships ccx in "<install>\Solver\ccx_dynamic.exe"
_SOLVER_SUBDIRS = ["", "Solver", "bin", "ccx", "CalculiX"]


def _scan_path_entries() -> str | None:
    """Look for a ccx binary in PATH entries and their common subfolders."""
    exe_suffix = ".exe" if os.name == "nt" else ""
    for entry in os.environ.get("PATH", "").split(os.pathsep):
        entry = entry.strip().strip('"')
        if not entry:
            continue
        base = Path(entry)
        for sub in _SOLVER_SUBDIRS:
            d = base / sub if sub else base
            for name in _CCX_NAMES:
                cand = d / (name + exe_suffix)
                if cand.exists():
                    return str(cand)
    return None


def ccx_path() -> str | None:
    """Return a usable ccx path, or None when not found."""
    env = os.environ.get("STRUCTVIS_CCX")
    if env and Path(env).exists():
        return env

    exe_suffix = ".exe" if os.name == "nt" else ""
    for name in _CCX_NAMES:
        cand = _bin_dir() / (name + exe_suffix)
        if cand.exists():
            return str(cand)
    # direct hit on PATH (ccx itself is on PATH)
    for name in _CCX_NAMES:
        found = shutil.which(name)
        if found:
            return found
    # PrePoMax-style: a PATH entry whose Solver/ subfolder holds ccx
    return _scan_path_entries()


def is_available() -> bool:
    return ccx_path() is not None


def missing_hint() -> str:
    return (
        "CalculiX solver (ccx) was not found.\n\n"
        "StructVis can build the mesh, estimate mass and map loads without it, "
        "but running the stress analysis needs the ccx binary. Options:\n"
        "  - place ccx(.exe) in structvis/resources/bin, or\n"
        "  - set the STRUCTVIS_CCX environment variable to its full path, or\n"
        "  - install CalculiX / PrePoMax and add ccx to your PATH.")
