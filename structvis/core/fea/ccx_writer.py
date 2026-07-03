"""
Writer for the CalculiX input deck (.inp).

Emits an S4 shell model: nodes, elements grouped into element sets, one
*SHELL SECTION per set (thickness from WingboxParams), an isotropic material,
a fully-clamped root, mapped nodal loads (*CLOAD), and a linear static step
requesting nodal displacement (U) and element stress (S).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from .. import materials
from ..mesher import WingboxMesh
from ..wingbox import WingboxParams
from ..loads import StripLoads


def _fmt(v: float) -> str:
    return f"{v:.9g}"


def _mat_name(key: str) -> str:
    """A valid CalculiX material name from a material key."""
    return "MAT_" + key.upper().replace("-", "_").replace(" ", "_")


def build_inp(mesh: WingboxMesh, params: WingboxParams,
              loads: StripLoads | None = None,
              material_key: str | None = None,
              buckle_modes: int | None = None) -> str:
    """
    Return the full .inp text.

    buckle_modes=None  -> linear static analysis (U + Von Mises).
    buckle_modes=N     -> linear buckling: extract N eigenvalues (load factors)
                          under the applied load, plus the mode shapes.
    """
    tmap = params.thickness_map()
    mmap = params.material_map()
    if material_key is not None:      # optimizer override: force one material
        mmap = {k: material_key for k in mmap}
    lines: list[str] = ["*HEADING", "StructVis wingbox - linear static shell model"]

    # ---- nodes (1-based ids) ---------------------------------------------
    lines.append("*NODE, NSET=NALL")
    for i, (x, y, z) in enumerate(mesh.nodes, start=1):
        lines.append(f"{i}, {_fmt(x)}, {_fmt(y)}, {_fmt(z)}")

    # ---- elements per set -------------------------------------------------
    for name, idx in mesh.elsets.items():
        if len(idx) == 0:
            continue
        lines.append(f"*ELEMENT, TYPE=S4, ELSET={name}")
        for e in idx:
            a, b, c, d = mesh.elems[e] + 1
            lines.append(f"{e + 1}, {a}, {b}, {c}, {d}")

    # ---- materials (one block per distinct material actually used) --------
    used = {mmap.get(name, params.material) for name in mesh.elsets
            if len(mesh.elsets[name])}
    any_ortho = any(materials.get(k).ortho for k in used)
    if any_ortho:
        # material 1-axis along span (Y), 2-axis chordwise - projected onto
        # each shell. A single orientation is a stated simplification.
        lines += ["*ORIENTATION, NAME=ORI_WING, SYSTEM=RECTANGULAR",
                  "0., 1., 0., 1., 0., 0."]
    for key in sorted(used):
        mat = materials.get(key)
        lines.append(f"*MATERIAL, NAME={_mat_name(key)}")
        if mat.ortho:
            E1, E2, E3, nu12, nu13, nu23, G12, G13, G23 = mat.ortho_constants()
            lines += ["*ELASTIC, TYPE=ENGINEERING CONSTANTS",
                      f"{_fmt(E1)}, {_fmt(E2)}, {_fmt(E3)}, {_fmt(nu12)}, "
                      f"{_fmt(nu13)}, {_fmt(nu23)}, {_fmt(G12)}, {_fmt(G13)}",
                      _fmt(G23)]
        else:
            lines += ["*ELASTIC", f"{_fmt(mat.E)}, {_fmt(mat.nu)}"]
        lines += ["*DENSITY", _fmt(mat.rho)]

    # ---- shell sections (thickness + material per set) -------------------
    for name, idx in mesh.elsets.items():
        if len(idx) == 0:
            continue
        t = tmap.get(name, params.skin_t)
        key = mmap.get(name, params.material)
        ori = ", ORIENTATION=ORI_WING" if materials.get(key).ortho else ""
        lines += [f"*SHELL SECTION, ELSET={name}, MATERIAL={_mat_name(key)}{ori}",
                  _fmt(t)]

    # ---- boundary: clamp the root ----------------------------------------
    lines.append("*NSET, NSET=ROOT")
    lines += _int_rows(mesh.root_nodes + 1)
    lines += ["*BOUNDARY", "ROOT, 1, 6"]      # all 6 DOF of shell nodes

    # ---- step -------------------------------------------------------------
    if buckle_modes:
        # linear buckling: eigenvalues = factors on the applied load
        lines += ["*STEP", "*BUCKLE", f"{int(buckle_modes)}"]
        if loads is not None:
            lines.append("*CLOAD")
            lines += _cload_rows(mesh, loads)
        lines += ["*NODE FILE, OUTPUT=2D", "U", "*END STEP"]
    else:
        lines += ["*STEP", "*STATIC"]
        if loads is not None:
            lines.append("*CLOAD")
            lines += _cload_rows(mesh, loads)
        # OUTPUT=2D keeps results on the ORIGINAL shell nodes; without it
        # CalculiX expands shells to 3D and renumbers, breaking node mapping.
        lines += ["*NODE FILE, OUTPUT=2D", "U",
                  "*EL FILE, OUTPUT=2D", "S",
                  "*END STEP"]
    return "\n".join(lines) + "\n"


def _int_rows(ids, per_row: int = 8) -> list[str]:
    ids = np.asarray(ids, int)
    return [", ".join(str(v) for v in ids[i:i + per_row])
            for i in range(0, len(ids), per_row)]


def _cload_rows(mesh: WingboxMesh, loads: StripLoads) -> list[str]:
    """
    Distribute each station's spar forces across that station's web nodes.

    Vertical force (DOF 3) is shared equally among the web column nodes;
    drag (DOF 1) likewise. The root station carries no load (clamped).
    """
    rows: list[str] = []
    n_st = len(mesh.station_nodes_front)
    for i in range(n_st):
        fz_f = loads.Fz_front[i] if i < len(loads.Fz_front) else 0.0
        fz_r = loads.Fz_rear[i] if i < len(loads.Fz_rear) else 0.0
        fx = loads.Fx[i] if i < len(loads.Fx) else 0.0

        fcol = mesh.station_nodes_front[i]
        rcol = mesh.station_nodes_rear[i]
        for col, fz in ((fcol, fz_f), (rcol, fz_r)):
            if not len(col):
                continue
            per = fz / len(col)
            fx_per = 0.5 * fx / len(col)
            for nid in col + 1:
                if abs(per) > 1e-12:            # skip zero rows (deck size)
                    rows.append(f"{nid}, 3, {_fmt(per)}")
                if abs(fx_per) > 1e-12:
                    rows.append(f"{nid}, 1, {_fmt(fx_per)}")
    return rows


def write_inp(path: str | Path, mesh: WingboxMesh, params: WingboxParams,
              loads: StripLoads | None = None,
              material_key: str | None = None,
              buckle_modes: int | None = None) -> Path:
    path = Path(path)
    if path.suffix != ".inp":
        path = path.with_suffix(".inp")
    path.write_text(build_inp(mesh, params, loads, material_key,
                              buckle_modes=buckle_modes), encoding="ascii")
    return path
