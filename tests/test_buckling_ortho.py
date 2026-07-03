"""Buckling deck/parser and orthotropic material cards (no ccx needed)."""
from __future__ import annotations

import numpy as np

from structvis.core import mesher, materials
from structvis.core.wingbox import WingboxParams
from structvis.core.loads import LoadCase, strip_loads
from structvis.core.fea.ccx_writer import build_inp
from structvis.core.fea.frd_parser import parse_buckling_factors
from structvis.core.fea.result import BucklingResult


def test_buckle_deck_has_buckle_step(wingbox_mesh, project):
    mesh, params = wingbox_mesh
    sl = strip_loads(project, LoadCase(), mesh.y_stations,
                     params.front_spar, params.rear_spar)
    inp = build_inp(mesh, params, sl, buckle_modes=5)
    assert "*BUCKLE" in inp
    assert "\n5" in inp                       # number of modes
    assert "*STATIC" not in inp
    assert "*CLOAD" in inp


def test_static_deck_has_no_buckle(wingbox_mesh, project):
    mesh, params = wingbox_mesh
    inp = build_inp(mesh, params, None)
    assert "*BUCKLE" not in inp and "*STATIC" in inp


def test_orthotropic_cards(project):
    params = WingboxParams(n_ribs=5, material="cfrp_woven")
    mesh = mesher.build_mesh(project.geometry, params)
    inp = build_inp(mesh, params, None)
    assert "TYPE=ENGINEERING CONSTANTS" in inp
    assert "*ORIENTATION" in inp and "ORI_WING" in inp
    # 9 engineering constants -> 8 on first line, 1 on the next
    assert "ORIENTATION=ORI_WING" in inp


def test_new_ortho_materials_exist():
    keys = {m.key for m in materials.MATERIALS}
    for k in ("cfrp_woven", "cfrp_ud", "glass_woven"):
        assert k in keys and materials.get(k).ortho


def test_ortho_constants_shape():
    m = materials.get("cfrp_ud")
    c = m.ortho_constants()
    assert len(c) == 9 and all(v > 0 for v in c[:3])   # E1,E2,E3 positive


def test_parse_buckling_factors(tmp_path):
    # CalculiX letter-spaces the header
    dat = tmp_path / "b.dat"
    dat.write_text(
        "                        S T E P       1\n\n"
        "     B U C K L I N G   F A C T O R   O U T P U T\n\n"
        " MODE NO       BUCKLING\n                FACTOR\n\n"
        "      1   0.2162677E+02\n"
        "      2   0.2468534E+02\n"
        "      3   0.3122548E+02\n")
    f = parse_buckling_factors(dat)
    assert len(f) == 3
    assert abs(f[0] - 21.62677) < 1e-3


def test_buckling_result_critical_factor():
    b = BucklingResult(factors=np.array([-0.5, 3.2, 4.1]),
                       nodes=np.zeros((4, 3)), elems=np.array([[0, 1, 2, 3]]))
    # ignores the negative eigenvalue, takes the lowest positive
    assert abs(b.critical_factor - 3.2) < 1e-9
    assert b.summary()["buckles_below_limit"] is False
