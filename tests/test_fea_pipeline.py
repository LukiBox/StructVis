"""
Physics validation: a thin-walled rectangular box cantilever solved by
CalculiX must match Euler-Bernoulli beam theory within 5%.

Reuses the REAL pipeline (mesher -> ccx_writer -> ccx_runner -> frd_parser ->
FeaResult) by feeding it a rectangular-section geometry, so a pass validates
the whole M2 chain end to end. Skipped when ccx is not installed.
"""
from __future__ import annotations

import numpy as np
import pytest

from structvis.core import mesher, materials
from structvis.core.wingbox import WingboxParams
from structvis.core.loads import StripLoads
from structvis.core.fea import binaries
from structvis.core.fea.ccx_runner import solve

pytestmark = pytest.mark.skipif(not binaries.is_available(),
                                reason="ccx solver not installed")


class RectGeometry:
    """Rectangular-section 'wing': flat top/bottom skins, constant chord."""
    def __init__(self, length, chord, height):
        self.half_span = length
        self._c = chord
        self._h = height

    def chord(self, y):
        return np.full_like(np.asarray(y, float), self._c) \
            if np.ndim(y) else self._c

    def x_le(self, y):
        return np.zeros_like(np.asarray(y, float)) if np.ndim(y) else 0.0

    def section_z(self, y, xc):
        xc = np.asarray(xc, float)
        return np.full_like(xc, self._h / 2), np.full_like(xc, -self._h / 2)


def test_cantilever_matches_beam_theory():
    L, C, h, t, P = 1.0, 0.125, 0.05, 0.002, 50.0
    front, rear = 0.1, 0.9
    b = (rear - front) * C                   # structural box width = 0.1 m

    geom = RectGeometry(L, C, h)
    params = WingboxParams(front_spar=front, rear_spar=rear, n_ribs=6,
                           skin_t=t, web_t=t, cap_t=t, rib_t=t, n_stringers=0,
                           material="al7075")
    mesh = mesher.build_mesh(geom, params, n_chord=6, n_vert=4)

    # tip point load: put all vertical force on the tip station
    n_st = len(mesh.station_nodes_front)
    Fz = np.zeros(n_st)
    Fz[-1] = P
    loads = StripLoads(y_stations=mesh.y_stations,
                       Fz_front=0.5 * Fz, Fz_rear=0.5 * Fz,
                       Fx=np.zeros(n_st),
                       x_cp_c=np.full(n_st, 0.5), lift_half=P)

    res = solve(mesh, params, loads, half_span=L)

    # thin-walled box second moment of area (bending about horizontal axis)
    I = b * t * h ** 2 / 2 + t * h ** 3 / 6
    E = materials.get("al7075").E
    delta_theory = P * L ** 3 / (3 * E * I)
    delta_fem = res.tip_deflection

    rel = abs(delta_fem - delta_theory) / delta_theory
    assert rel < 0.05, (f"tip deflection {delta_fem*1e3:.3f} mm vs theory "
                        f"{delta_theory*1e3:.3f} mm ({rel*100:.1f}% off)")


def test_root_is_most_stressed():
    """Sanity: peak stress must sit at/near the clamped root."""
    L, C, h, t, P = 1.0, 0.125, 0.05, 0.002, 50.0
    geom = RectGeometry(L, C, h)
    params = WingboxParams(front_spar=0.1, rear_spar=0.9, n_ribs=6,
                           skin_t=t, web_t=t, cap_t=t, rib_t=t, n_stringers=0)
    mesh = mesher.build_mesh(geom, params, n_chord=6, n_vert=4)
    n_st = len(mesh.station_nodes_front)
    Fz = np.zeros(n_st); Fz[-1] = P
    loads = StripLoads(mesh.y_stations, 0.5 * Fz, 0.5 * Fz,
                       np.zeros(n_st), np.full(n_st, 0.5), P)
    res = solve(mesh, params, loads, half_span=L)
    y_peak = res.nodes[res.max_vm_node, 1]
    assert y_peak < 0.35 * L, "peak stress not near the root"
