"""
Parser for CalculiX .frd result files.

Fixed-format ("free" ASCII) FRD as written by ccx: each data record starts
with the key " -1" (columns 1-3), followed by a node id (10 chars) and value
fields (12 chars each). We read the DISP and STRESS result blocks and map them
back onto the original node ids (the deck uses OUTPUT=2D, so ids are preserved).

Von Mises is computed from the 6 nodal stress components.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np


def _parse_record(line: str) -> tuple[int, list[float]]:
    """Parse a ' -1' data record: node id + 12-char value fields."""
    node = int(line[3:13])
    rest = line[13:].rstrip("\n")
    vals = []
    for i in range(0, len(rest), 12):
        chunk = rest[i:i + 12].strip()
        if chunk:
            vals.append(float(chunk))
    return node, vals


def von_mises(sxx, syy, szz, sxy, syz, szx) -> float:
    return float(np.sqrt(
        0.5 * ((sxx - syy) ** 2 + (syy - szz) ** 2 + (szz - sxx) ** 2)
        + 3.0 * (sxy ** 2 + syz ** 2 + szx ** 2)))


def parse_frd(path: str | Path, n_nodes: int | None = None) -> dict:
    """
    Return {'disp': (N,3), 'von_mises': (N,), 'node_ids': (N,)}.

    Arrays are indexed 0..N-1 aligned to node id 1..N (id-1 = row). N is
    max(node id) unless n_nodes is given.
    """
    path = Path(path)
    text = path.read_text(encoding="latin-1", errors="ignore").splitlines()

    disp: dict[int, tuple[float, float, float]] = {}
    stress: dict[int, float] = {}       # node -> max von Mises seen

    block = None            # None | 'DISP' | 'STRESS'
    for line in text:
        if len(line) >= 3 and line[:3] == " -4":
            name = line[3:].split()[0] if line[3:].split() else ""
            if name.startswith("DISP"):
                block = "DISP"
            elif name.startswith("STRESS"):
                block = "STRESS"
            else:
                block = None
            continue
        if not line.startswith(" -1") and not line.startswith(" -2"):
            # any other key line ends the current data block
            if line[:3] in (" -3", " -5") or line.strip() == "":
                if line[:3] == " -3":
                    block = None
            continue
        if block is None:
            continue
        try:
            node, vals = _parse_record(line)
        except (ValueError, IndexError):
            continue
        if block == "DISP" and len(vals) >= 3:
            disp[node] = (vals[0], vals[1], vals[2])
        elif block == "STRESS" and len(vals) >= 6:
            vm = von_mises(*vals[:6])
            if vm > stress.get(node, -1.0):
                stress[node] = vm

    ids = sorted(set(disp) | set(stress))
    if not ids:
        raise ValueError(f"No DISP/STRESS results found in {path.name}. "
                         "The solver may have failed - check the .dat/.sta log.")
    return _assemble(disp, stress, n_nodes, ids)


def _assemble(disp, stress, n_nodes, ids):
    N = n_nodes if n_nodes is not None else max(ids)
    U = np.zeros((N, 3))
    VM = np.zeros(N)
    for nid, d in disp.items():
        if 1 <= nid <= N:
            U[nid - 1] = d
    for nid, v in stress.items():
        if 1 <= nid <= N:
            VM[nid - 1] = v
    return {"disp": U, "von_mises": VM, "node_ids": np.asarray(ids, int)}


def parse_buckling_factors(dat_path) -> np.ndarray:
    """
    Read the buckling eigenvalues (load factors) from a CalculiX .dat file.

    The block looks like:
        B U C K L I N G   F A C T O R   O U T P U T
        MODE NO       BUCKLING
                      FACTOR
           1   3.4567E+00
           2   ...
    """
    from pathlib import Path
    text = Path(dat_path).read_text(errors="ignore").splitlines()
    factors: list[float] = []
    in_block = False
    for line in text:
        # CalculiX letter-spaces the header: "B U C K L I N G   F A C T O R"
        if "BUCKLINGFACTOR" in "".join(line.upper().split()):
            in_block = True
            continue
        if not in_block:
            continue
        parts = line.split()
        if len(parts) >= 2:
            try:
                int(parts[0])
                factors.append(float(parts[1]))
                continue
            except ValueError:
                pass
        # header rows ("MODE NO", "FACTOR") and blanks are skipped until data
        # ends; once we have data, a non-parsing line closes the block
        if factors:
            break
    return np.asarray(factors, float)


def parse_frd_modes(path, n_nodes: int) -> list:
    """Return a list of (n_nodes, 3) mode-shape displacement arrays (per DISP block)."""
    from pathlib import Path
    text = Path(path).read_text(encoding="latin-1", errors="ignore").splitlines()
    modes: list = []
    cur: dict | None = None
    in_disp = False
    for line in text:
        if len(line) >= 3 and line[:3] == " -4":
            name = line[3:].split()[0] if line[3:].split() else ""
            if name.startswith("DISP"):
                in_disp = True
                cur = {}
            else:
                in_disp = False
                cur = None
            continue
        if line[:3] == " -3" and cur is not None:
            arr = np.zeros((n_nodes, 3))
            for nid, d in cur.items():
                if 1 <= nid <= n_nodes:
                    arr[nid - 1] = d
            modes.append(arr)
            cur = None
            in_disp = False
            continue
        if not in_disp or cur is None:
            continue
        if line.startswith(" -1") or line.startswith(" -2"):
            try:
                node, vals = _parse_record(line)
            except (ValueError, IndexError):
                continue
            if len(vals) >= 3:
                cur[node] = (vals[0], vals[1], vals[2])
    return modes
