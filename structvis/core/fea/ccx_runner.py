"""
Run CalculiX on a wingbox model and collect a FeaResult.

`solve()` is pure Python (no Qt) so it is unit-testable and reusable by the
optimizer. A ccx job is invoked as ``ccx <jobname>`` with the .inp in the
working directory; it writes <jobname>.frd which we parse.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np

from .. import materials
from ..mesher import WingboxMesh
from ..wingbox import WingboxParams
from ..loads import StripLoads
from . import binaries
from .ccx_writer import write_inp
from .frd_parser import parse_frd, parse_buckling_factors, parse_frd_modes
from .result import FeaResult, BucklingResult


class SolverError(RuntimeError):
    pass


class SolverUnavailable(SolverError):
    pass


def _scratch_dir() -> Path:
    base = os.environ.get("STRUCTVIS_SCRATCH")
    root = Path(base) if base else Path(tempfile.gettempdir()) / "structvis_fea"
    root.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix="job_", dir=root))


def run_ccx(inp_path: Path, ccx: str | None = None,
            log_cb=None, timeout: float = 600.0) -> Path:
    """Run ccx on <jobname>.inp; return the .frd path. Raise on failure."""
    ccx = ccx or binaries.ccx_path()
    if not ccx:
        raise SolverUnavailable(binaries.missing_hint())

    jobname = inp_path.with_suffix("").name
    workdir = inp_path.parent
    # ccx may pick up the number of threads from this env var
    env = dict(os.environ)
    env.setdefault("OMP_NUM_THREADS", str(max(os.cpu_count() or 1, 1)))

    try:
        proc = subprocess.run(
            [ccx, jobname], cwd=str(workdir), env=env,
            capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as e:
        raise SolverError(f"CalculiX timed out after {timeout:.0f}s") from e
    except OSError as e:
        raise SolverError(f"Could not launch ccx: {e}") from e

    if log_cb:
        log_cb(proc.stdout or "")
        if proc.stderr:
            log_cb(proc.stderr)

    frd = workdir / f"{jobname}.frd"
    if not frd.exists() or frd.stat().st_size == 0:
        tail = (proc.stdout or "")[-1500:]
        raise SolverError(
            "CalculiX produced no results (.frd missing/empty). "
            f"Return code {proc.returncode}.\n--- solver log tail ---\n{tail}")
    return frd


def _node_material_fields(mesh: WingboxMesh, eff_mmap: dict):
    """
    Per-node yield [Pa] and material key. Each node takes the MINIMUM yield
    among the elements touching it (conservative at material junctions), so a
    weak material anywhere is never masked by a strong neighbour.
    """
    n = mesh.n_nodes
    node_yield = np.full(n, np.inf)
    node_mat = np.empty(n, dtype=object)
    for name, idx in mesh.elsets.items():
        key = eff_mmap.get(name)
        y = materials.get(key).yield_strength
        for e in idx:
            for nd in mesh.elems[e]:
                if y < node_yield[nd]:
                    node_yield[nd] = y
                    node_mat[nd] = key
    # nodes not touched by any element (shouldn't happen) -> a sane default
    fallback = min((materials.get(k).yield_strength for k in eff_mmap.values()),
                   default=1e9)
    node_yield[~np.isfinite(node_yield)] = fallback
    return node_yield, node_mat


def solve(mesh: WingboxMesh, params: WingboxParams, loads: StripLoads,
          material_key: str | None = None, half_span: float = 1.0,
          keep_files: bool = False, log_cb=None,
          ccx: str | None = None) -> FeaResult:
    """Full pipeline: write .inp -> run ccx -> parse .frd -> FeaResult."""
    # effective element-set -> material (respecting an optimizer override)
    if material_key is not None:
        eff_mmap = {name: material_key for name in mesh.elsets}
    else:
        eff_mmap = params.material_map()
    used_yields = [materials.get(k).yield_strength for k in set(eff_mmap.values())]
    clim_yield = max(used_yields) if used_yields else 1e9
    node_yield, node_mat = _node_material_fields(mesh, eff_mmap)

    workdir = _scratch_dir()
    inp = write_inp(workdir / "wingbox.inp", mesh, params, loads,
                    material_key=material_key)
    try:
        frd = run_ccx(inp, ccx=ccx, log_cb=log_cb)
        parsed = parse_frd(frd, n_nodes=mesh.n_nodes)
    finally:
        if not keep_files:
            shutil.rmtree(workdir, ignore_errors=True)

    mat_names = ", ".join(sorted({materials.get(k).name
                                  for k in set(eff_mmap.values())}))
    return FeaResult(
        nodes=mesh.nodes, elems=mesh.elems,
        disp=parsed["disp"], von_mises=parsed["von_mises"],
        yield_strength=clim_yield,
        half_span=half_span, root_y=float(mesh.y_stations[0]),
        elset_of_elem=mesh.elset_of_element(),
        node_yield=node_yield, node_material=node_mat,
        meta={"material": mat_names, "n_nodes": mesh.n_nodes,
              "n_elems": mesh.n_elems, "solver": "CalculiX"},
    )


def solve_buckling(mesh: WingboxMesh, params: WingboxParams, loads: StripLoads,
                   material_key: str | None = None, half_span: float = 1.0,
                   n_modes: int = 5, keep_files: bool = False, log_cb=None,
                   ccx: str | None = None) -> BucklingResult:
    """
    Linear buckling: write a *BUCKLE deck, run ccx, and read the eigenvalues
    (load multipliers) plus the first mode shape. A critical factor < 1 means
    the skins buckle below the applied load.
    """
    workdir = _scratch_dir()
    inp = write_inp(workdir / "buckle.inp", mesh, params, loads,
                    material_key=material_key, buckle_modes=n_modes)
    try:
        frd = run_ccx(inp, ccx=ccx, log_cb=log_cb)
        factors = parse_buckling_factors(frd.with_suffix(".dat"))
        modes = parse_frd_modes(frd, n_nodes=mesh.n_nodes)
    finally:
        if not keep_files:
            shutil.rmtree(workdir, ignore_errors=True)

    if len(factors) == 0:
        raise SolverError("Buckling analysis produced no eigenvalues - the "
                          "model may be unconstrained or the load zero.")
    mode1 = modes[0] if modes else None
    return BucklingResult(
        factors=factors, nodes=mesh.nodes, elems=mesh.elems, mode1=mode1,
        half_span=half_span, elset_of_elem=mesh.elset_of_element(),
        meta={"n_modes": int(len(factors)), "solver": "CalculiX *BUCKLE"})
