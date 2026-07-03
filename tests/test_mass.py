import numpy as np

from structvis.core import mesher, materials
from structvis.core.mass import mass_breakdown, total_mass
from structvis.core.wingbox import WingboxParams


def test_mass_scales_with_thickness(project):
    p1 = WingboxParams(n_ribs=5)
    m1 = mesher.build_mesh(project.geometry, p1)
    mass1 = total_mass(m1, p1)
    p2 = p1.scaled(2.0)
    m2 = mesher.build_mesh(project.geometry, p2)
    mass2 = total_mass(m2, p2)
    # doubling every gauge doubles the mass
    assert abs(mass2 - 2 * mass1) / mass1 < 1e-6


def test_mass_positive_and_material_dependent(project):
    p = WingboxParams(n_ribs=5, material="al7075")
    mesh = mesher.build_mesh(project.geometry, p)
    m_al = total_mass(mesh, p)
    p_ti = WingboxParams(n_ribs=5, material="ti64")
    m_ti = total_mass(mesh, p_ti)
    assert m_al > 0
    # titanium is denser than aluminium -> heavier for identical geometry
    ratio = materials.get("ti64").rho / materials.get("al7075").rho
    assert abs(m_ti / m_al - ratio) < 1e-6


def test_half_vs_full(project):
    p = WingboxParams(n_ribs=5)
    mesh = mesher.build_mesh(project.geometry, p)
    assert abs(total_mass(mesh, p, half_wing=False)
               - 2 * total_mass(mesh, p, half_wing=True)) < 1e-9


def test_breakdown_keys(project):
    p = WingboxParams(n_ribs=5, n_stringers=2)
    mesh = mesher.build_mesh(project.geometry, p)
    bd = mass_breakdown(mesh, p)
    assert any("skin" in k.lower() for k in bd)
    assert any("spar" in k.lower() for k in bd)
    assert all(v >= 0 for v in bd.values())
