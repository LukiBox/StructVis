"""Live mass estimation: shell areas x thickness x density, per component."""
from __future__ import annotations

import numpy as np

from . import materials
from .mesher import WingboxMesh
from .wingbox import WingboxParams

_LABELS = {
    "SKIN_UP": "Upper skin", "SKIN_LO": "Lower skin",
    "CAP_UP": "Upper spar caps", "CAP_LO": "Lower spar caps",
    "STR_UP": "Upper stringers", "STR_LO": "Lower stringers",
    "SPAR_F": "Front spar web", "SPAR_R": "Rear spar web",
    "RIBS": "Ribs",
}


def mass_breakdown(mesh: WingboxMesh, params: WingboxParams,
                   half_wing: bool = True) -> dict[str, float]:
    """Component -> mass [kg]. Doubled for the whole wing unless half_wing."""
    areas = mesh.element_areas()
    tmap = params.thickness_map()
    mmap = params.material_map()
    factor = 1.0 if half_wing else 2.0
    out: dict[str, float] = {}
    for name, idx in mesh.elsets.items():
        t = tmap.get(name, params.skin_t)
        rho = materials.get(mmap.get(name, params.material)).rho
        out[_LABELS.get(name, name)] = float(areas[idx].sum() * t * rho) * factor
    return out


def total_mass(mesh: WingboxMesh, params: WingboxParams,
               half_wing: bool = True) -> float:
    return sum(mass_breakdown(mesh, params, half_wing).values())


def element_mass(mesh: WingboxMesh, params: WingboxParams) -> np.ndarray:
    """Mass [kg] of every element (half-wing), for inertial relief."""
    areas = mesh.element_areas()
    tmap = params.thickness_map()
    mmap = params.material_map()
    m = np.zeros(mesh.n_elems)
    for name, idx in mesh.elsets.items():
        t = tmap.get(name, params.skin_t)
        rho = materials.get(mmap.get(name, params.material)).rho
        m[idx] = areas[idx] * t * rho
    return m


def mass_per_station(mesh: WingboxMesh, params: WingboxParams,
                     y_stations: np.ndarray) -> np.ndarray:
    """
    Half-wing structural mass [kg] lumped to the nearest spanwise station.
    Sums to the half-wing structural mass; used for inertial relief.
    """
    em = element_mass(mesh, params)
    ey = mesh.nodes[mesh.elems].mean(axis=1)[:, 1]     # element mean y
    y = np.asarray(y_stations, float)
    idx = np.abs(ey[:, None] - y[None, :]).argmin(axis=1)
    out = np.zeros(len(y))
    np.add.at(out, idx, em)
    return out
