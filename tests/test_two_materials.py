"""Skin vs support material: mapping, mass, deck, FoS, project round-trip."""
from __future__ import annotations

import numpy as np
import pytest

from structvis.core import mesher, materials
from structvis.core.wingbox import WingboxParams, SUPPORT_SETS, SKIN_SETS
from structvis.core.mass import total_mass
from structvis.core.fea.ccx_writer import build_inp
from structvis.core.fea.result import FeaResult
from structvis.core.loads import LoadCase, strip_loads


def test_new_materials_present():
    keys = {m.key for m in materials.MATERIALS}
    for k in ("balsa", "pla", "fiberglass", "paper", "cardstock", "eps_foam"):
        assert k in keys
    # existing ones kept
    for k in ("al7075", "al6061", "ti64", "steel4130", "cfrp_qi", "plywood"):
        assert k in keys


def test_material_map_splits_skin_and_support():
    p = WingboxParams(material="balsa", support_material="pla")
    mm = p.material_map()
    for s in SKIN_SETS:
        assert mm[s] == "balsa"
    for s in SUPPORT_SETS:
        assert mm[s] == "pla"
    assert p.materials_used() == ["balsa", "pla"]


def test_empty_support_falls_back_to_skin():
    p = WingboxParams(material="al6061", support_material="")
    assert p.effective_support_material == "al6061"
    assert p.materials_used() == ["al6061"]
    assert set(p.material_map().values()) == {"al6061"}


def test_mass_uses_per_component_material(project):
    light = WingboxParams(n_ribs=5, material="balsa", support_material="balsa")
    heavy_support = WingboxParams(n_ribs=5, material="balsa", support_material="steel4130")
    mesh = mesher.build_mesh(project.geometry, light)
    m_light = total_mass(mesh, light)
    m_heavy = total_mass(mesh, heavy_support)
    # steel spars/ribs must weigh more than balsa ones
    assert m_heavy > m_light


def test_inp_has_two_material_blocks(wingbox_mesh, project):
    mesh, _ = wingbox_mesh
    params = WingboxParams(n_ribs=5, material="al7075", support_material="cfrp_qi")
    sl = strip_loads(project, LoadCase(), mesh.y_stations,
                     params.front_spar, params.rear_spar)
    inp = build_inp(mesh, params, sl)
    assert inp.count("*MATERIAL, NAME=") == 2
    assert "MAT_AL7075" in inp and "MAT_CFRP_QI" in inp


def test_inp_single_material_when_same(wingbox_mesh, project):
    mesh, params = wingbox_mesh          # default: support empty -> same
    inp = build_inp(mesh, params, None)
    assert inp.count("*MATERIAL, NAME=") == 1


def test_node_yield_drives_fos_to_weaker_material():
    """A weak support must lower min FoS even if its stress is modest."""
    nodes = np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0],
                      [2, 0, 0], [2, 1, 0]], float)
    elems = np.array([[0, 1, 2, 3], [1, 4, 5, 2]])
    vm = np.array([100e6, 100e6, 100e6, 100e6, 50e6, 50e6])
    # node_yield: strong skin (503) on first quad nodes, weak foam (0.25e6)... use pla 45
    ny = np.array([503e6, 503e6, 503e6, 503e6, 45e6, 45e6])
    r = FeaResult(nodes=nodes, elems=elems, disp=np.zeros_like(nodes),
                  von_mises=vm, yield_strength=503e6, node_yield=ny,
                  elset_of_elem=np.array(["SKIN_UP", "SPAR_F"], dtype=object),
                  node_material=np.array(["al7075"]*4 + ["pla"]*2, dtype=object))
    # weakest point: pla nodes 50 MPa vs 45 MPa yield -> FoS 0.9
    assert abs(r.min_fos - 45e6 / 50e6) < 1e-6
    assert r.where_min_fos() == "SPAR_F"
    assert r.critical_material() == "pla"


def test_project_roundtrip_two_materials(project, tmp_path):
    from structvis.core import project as proj
    params = WingboxParams(n_ribs=5, material="balsa", support_material="pla")
    case = LoadCase()
    nodes = np.random.rand(8, 3)
    elems = np.array([[0, 1, 2, 3], [4, 5, 6, 7]])
    r = FeaResult(nodes=nodes, elems=elems, disp=np.zeros_like(nodes),
                  von_mises=np.random.rand(8) * 1e7, yield_strength=45e6,
                  node_yield=np.full(8, 15e6),
                  node_material=np.array(["balsa"] * 8, dtype=object),
                  elset_of_elem=np.array(["SKIN_UP", "SPAR_F"], dtype=object))
    path = proj.save_project(tmp_path / "tm.structvis", project, params, case, r)
    loaded = proj.load_project(path)
    assert loaded["params"].support_material == "pla"
    lr = loaded["result"]
    assert lr.node_yield is not None and np.allclose(lr.node_yield, 15e6)
    assert list(lr.node_material) == ["balsa"] * 8
