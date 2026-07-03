"""
Structured quad shell mesher for the parametric wingbox.

One global node array; skins, spar webs and ribs share nodes along their
junction lines by construction, so the mesh is watertight without any
merging step. Element sets per component map 1:1 to CalculiX *SHELL SECTION
cards.

Grid parameterization:
  i - spanwise station (rib locations + subdivisions), i=0 at the root
  j - chordwise station between front (j=0) and rear (j=n_c) spar
  k - vertical station between lower (k=0) and upper (k=n_v) surface
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .geometry import WingGeometry
from .wingbox import WingboxParams


@dataclass
class WingboxMesh:
    nodes: np.ndarray                       # (N, 3) float
    elems: np.ndarray                       # (M, 4) int, 0-based node ids
    elsets: dict[str, np.ndarray]           # set name -> element indices
    y_stations: np.ndarray                  # (n_s+1,) spanwise stations
    rib_station_idx: np.ndarray             # indices into y_stations
    station_nodes_front: list[np.ndarray]   # per-station front spar node column
    station_nodes_rear: list[np.ndarray]
    root_nodes: np.ndarray                  # clamped node ids
    n_chord: int = 8
    n_vert: int = 4
    warnings: list[str] = field(default_factory=list)

    @property
    def n_nodes(self) -> int:
        return len(self.nodes)

    @property
    def n_elems(self) -> int:
        return len(self.elems)

    def element_areas(self) -> np.ndarray:
        """Quad areas (sum of two triangles), vectorized."""
        p = self.nodes[self.elems]          # (M, 4, 3)
        a1 = 0.5 * np.linalg.norm(
            np.cross(p[:, 1] - p[:, 0], p[:, 3] - p[:, 0]), axis=1)
        a2 = 0.5 * np.linalg.norm(
            np.cross(p[:, 1] - p[:, 2], p[:, 3] - p[:, 2]), axis=1)
        return a1 + a2

    def elset_of_element(self) -> np.ndarray:
        """Element index -> set name (object array)."""
        out = np.empty(self.n_elems, dtype=object)
        for name, idx in self.elsets.items():
            out[idx] = name
        return out

    def elset_nodes(self, name: str) -> np.ndarray:
        """Unique node ids used by an element set."""
        return np.unique(self.elems[self.elsets[name]])

    def tip_nodes(self) -> np.ndarray:
        y_tip = self.y_stations[-1]
        return np.nonzero(np.abs(self.nodes[:, 1] - y_tip) < 1e-9)[0]


def _stringer_columns(n_c: int, n_str: int) -> list[int]:
    """Interior chordwise columns for stringer strips (avoid cap columns)."""
    if n_str <= 0 or n_c < 4:
        return []
    cols = sorted({int(round((s + 1) * n_c / (n_str + 1)))
                   for s in range(n_str)})
    return [j for j in cols if 1 <= j <= n_c - 2]


def build_mesh(geometry: WingGeometry, params: WingboxParams,
               n_chord: int = 8, n_vert: int = 4,
               max_bay_elems: int = 6) -> WingboxMesh:
    issues = params.validated()
    if issues:
        raise ValueError("; ".join(issues))

    hs = geometry.half_span
    xf, xr = params.front_spar, params.rear_spar
    n_c, n_v = int(n_chord), int(n_vert)

    # ---- spanwise stations: ribs + subdivisions -------------------------
    rib_y = np.linspace(0.0, hs, params.n_ribs)
    mean_box_w = float(np.mean(geometry.chord(rib_y))) * (xr - xf)
    dx_target = max(mean_box_w / n_c, 1e-6)
    stations = [0.0]
    rib_idx = [0]
    for a, b in zip(rib_y[:-1], rib_y[1:]):
        n_e = int(np.clip(np.ceil((b - a) / dx_target), 1, max_bay_elems))
        stations.extend(np.linspace(a, b, n_e + 1)[1:].tolist())
        rib_idx.append(len(stations) - 1)
    y_st = np.asarray(stations)
    n_s = len(y_st) - 1                     # spanwise element rows

    xc = xf + (xr - xf) * np.arange(n_c + 1) / n_c

    # ---- nodes -----------------------------------------------------------
    nodes: list[tuple[float, float, float]] = []

    def add(x, y, z) -> int:
        nodes.append((float(x), float(y), float(z)))
        return len(nodes) - 1

    n_st = n_s + 1
    uid = np.empty((n_st, n_c + 1), int)
    lid = np.empty((n_st, n_c + 1), int)
    zu_all = np.empty((n_st, n_c + 1))
    zl_all = np.empty((n_st, n_c + 1))
    for i, y in enumerate(y_st):
        c = float(geometry.chord(y))
        xle = float(geometry.x_le(y))
        zu, zl = geometry.section_z(y, xc)
        zu_all[i], zl_all[i] = zu, zl
        for j in range(n_c + 1):
            x = xle + xc[j] * c
            uid[i, j] = add(x, y, zu[j])
            lid[i, j] = add(x, y, zl[j])

    # spar web columns (share skin nodes at k=0 and k=n_v)
    def web_column(i: int, j: int) -> np.ndarray:
        col = np.empty(n_v + 1, int)
        col[0] = lid[i, j]
        col[n_v] = uid[i, j]
        x, y = nodes[lid[i, j]][0], y_st[i]
        zl, zu = zl_all[i, j], zu_all[i, j]
        for k in range(1, n_v):
            col[k] = add(x, y, zl + (zu - zl) * k / n_v)
        return col

    fweb = np.stack([web_column(i, 0) for i in range(n_st)])
    rweb = np.stack([web_column(i, n_c) for i in range(n_st)])

    # rib node grids (share skin rows and web columns on the boundary)
    rib_grids: dict[int, np.ndarray] = {}
    for ir in rib_idx:
        g = np.empty((n_c + 1, n_v + 1), int)
        g[:, 0] = lid[ir]
        g[:, n_v] = uid[ir]
        g[0, :] = fweb[ir]
        g[n_c, :] = rweb[ir]
        y = y_st[ir]
        for j in range(1, n_c):
            x = nodes[lid[ir, j]][0]
            zl, zu = zl_all[ir, j], zu_all[ir, j]
            for k in range(1, n_v):
                g[j, k] = add(x, y, zl + (zu - zl) * k / n_v)
        rib_grids[ir] = g

    # ---- elements ---------------------------------------------------------
    elems: list[tuple[int, int, int, int]] = []
    sets: dict[str, list[int]] = {
        k: [] for k in ("SKIN_UP", "SKIN_LO", "CAP_UP", "CAP_LO",
                        "STR_UP", "STR_LO", "SPAR_F", "SPAR_R", "RIBS")}

    def quad(setname: str, a: int, b: int, c: int, d: int):
        sets[setname].append(len(elems))
        elems.append((a, b, c, d))

    str_cols = set(_stringer_columns(n_c, params.n_stringers))
    cap_cols = {0, n_c - 1}

    def skin_set(j: int, upper: bool) -> str:
        if j in cap_cols:
            return "CAP_UP" if upper else "CAP_LO"
        if j in str_cols:
            return "STR_UP" if upper else "STR_LO"
        return "SKIN_UP" if upper else "SKIN_LO"

    for i in range(n_s):
        for j in range(n_c):
            quad(skin_set(j, True),
                 uid[i, j], uid[i, j + 1], uid[i + 1, j + 1], uid[i + 1, j])
            quad(skin_set(j, False),
                 lid[i, j], lid[i + 1, j], lid[i + 1, j + 1], lid[i, j + 1])
        for k in range(n_v):
            quad("SPAR_F", fweb[i, k], fweb[i, k + 1],
                 fweb[i + 1, k + 1], fweb[i + 1, k])
            quad("SPAR_R", rweb[i, k], rweb[i, k + 1],
                 rweb[i + 1, k + 1], rweb[i + 1, k])
    for ir, g in rib_grids.items():
        for j in range(n_c):
            for k in range(n_v):
                quad("RIBS", g[j, k], g[j + 1, k], g[j + 1, k + 1], g[j, k + 1])

    nodes_arr = np.asarray(nodes)
    elems_arr = np.asarray(elems, int)
    elsets = {k: np.asarray(v, int) for k, v in sets.items() if v}

    # ---- special node groups ----------------------------------------------
    station_front = [fweb[i].copy() for i in range(n_st)]
    station_rear = [rweb[i].copy() for i in range(n_st)]
    root = np.nonzero(np.abs(nodes_arr[:, 1]) < 1e-12)[0]

    warnings = []
    areas_hint = geometry.chord(0.0) * (xr - xf) / n_c
    dy_max = float(np.max(np.diff(y_st)))
    if dy_max / max(areas_hint, 1e-9) > 12:
        warnings.append("Coarse spanwise mesh (element aspect ratio > 12); "
                        "consider adding ribs.")

    return WingboxMesh(nodes=nodes_arr, elems=elems_arr, elsets=elsets,
                       y_stations=y_st, rib_station_idx=np.asarray(rib_idx),
                       station_nodes_front=station_front,
                       station_nodes_rear=station_rear,
                       root_nodes=root, n_chord=n_c, n_vert=n_v,
                       warnings=warnings)
