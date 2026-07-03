# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for StructVis - single-file Windows executable.

Build:   pyinstaller structvis.spec
Result:  dist/StructVis.exe

Bundles the QSS theme and the heavy library data (PyVista/VTK, matplotlib,
reportlab). The CalculiX solver (ccx) is NOT bundled by default - StructVis
finds it via PATH / PrePoMax at runtime (Help > Solver status). To make a
fully portable build, copy ccx(.exe) *and its DLLs* into
structvis/resources/bin/ before building; the spec picks them up automatically.
"""
import glob
import os

from PyInstaller.utils.hooks import collect_all

datas = []
binaries = []
hiddenimports = []

# heavy packages with data files / dynamic imports
for pkg in ("pyvista", "pyvistaqt", "vtkmodules", "matplotlib", "reportlab"):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass

# Optional: bundle a solver dropped into resources/bin (ccx + its DLLs) for a
# portable build. Skipped silently when the folder is empty.
_bin = "structvis/resources/bin"
if os.path.isdir(_bin):
    for f in glob.glob(os.path.join(_bin, "*")):
        if os.path.isfile(f):
            binaries.append((f, "resources/bin"))

hiddenimports += [
    "ollama", "reportlab", "pyqtgraph",
    "scipy.interpolate", "scipy.special",
    "matplotlib.backends.backend_agg",
]

a = Analysis(
    ["structvis/app.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "PyQt5", "PyQt6", "pytest", "aerosandbox"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="StructVis",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,          # windowed app (no console)
    icon=None,
)
