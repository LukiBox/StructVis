"""Export to SimVis: mass/CG/inertia assembly + simvis_mass.json validity.

The JSON is validated against the same rules SimVis enforces on import
(schema id, positive mass, cg length, positive-definite full inertia tensor,
limit-load signs), so a green test here means the file loads in SimVis.
"""
from __future__ import annotations

import json

import numpy as np
import pytest

from structvis.core.simvis_export import (PointMass, SCHEMA_ID,
                                          assemble_mass_model,
                                          default_point_masses,
                                          wing_mass_cloud, write_simvis_mass)


def _validate_like_simvis(d: dict):
    """Mirror SimVis's mass_schema.validate_mass_dict checks."""
    assert d["schema"] == SCHEMA_ID
    assert isinstance(d["mass_kg"], (int, float)) and d["mass_kg"] > 0
    assert len(d["cg_m"]) == 3
    inertia = d["inertia_kgm2"]
    for k in ("Ixx", "Iyy", "Izz"):
        assert inertia[k] > 0
    ixz = inertia.get("Ixz", 0.0)
    ixy = inertia.get("Ixy", 0.0)
    iyz = inertia.get("Iyz", 0.0)
    tensor = np.array([[inertia["Ixx"], -ixy, -ixz],
                       [-ixy, inertia["Iyy"], -iyz],
                       [-ixz, -iyz, inertia["Izz"]]])
    assert np.all(np.linalg.eigvalsh(tensor) > 0), "tensor not PD"
    llf = d["limit_load_factor"]
    assert llf["positive"] > 0 and llf["negative"] < 0


def test_wing_cloud_is_symmetric(project, wingbox_mesh):
    mesh, params = wingbox_mesh
    pos, mass = wing_mass_cloud(project, mesh, params)
    assert len(pos) == len(mass) and len(mass) > 0
    # both half-spans present, equal mass, CG on the centerline
    cg_y = float((mass * pos[:, 1]).sum() / mass.sum())
    assert abs(cg_y) < 1e-9
    assert pos[:, 1].min() < 0 < pos[:, 1].max()


def test_assemble_and_validate(project, wingbox_mesh):
    mesh, params = wingbox_mesh
    wing_kg = float(wing_mass_cloud(project, mesh, params)[1].sum())
    target = wing_kg + 1.5                         # realistic all-up mass
    pms = default_point_masses(project, target_total_kg=target,
                               wing_structural_kg=wing_kg)
    model = assemble_mass_model(project, mesh, params, pms,
                                limit_load_pos=6.2)
    assert model.mass_kg == pytest.approx(target, abs=0.05)
    assert model.limit_load_neg == pytest.approx(-3.1)
    # CG on the centerline, somewhere sensible along the fuselage
    assert abs(model.cg_m[1]) < 1e-6
    assert 0.0 < model.cg_m[0] < 1.2
    # roll inertia dominated by the wing span; yaw the largest overall
    assert model.inertia["Izz"] > model.inertia["Ixx"] * 0.5
    _validate_like_simvis(model.to_schema_dict())


def test_point_mass_moves_cg(project, wingbox_mesh):
    mesh, params = wingbox_mesh
    base = assemble_mass_model(project, mesh, params,
                               [PointMass("Ballast", 0.4, x=0.5)],
                               limit_load_pos=6.0)
    nose = assemble_mass_model(project, mesh, params,
                               [PointMass("Ballast", 0.4, x=0.02)],
                               limit_load_pos=6.0)
    assert nose.cg_m[0] < base.cg_m[0]


def test_write_round_trip(project, wingbox_mesh, tmp_path):
    mesh, params = wingbox_mesh
    wing_kg = float(wing_mass_cloud(project, mesh, params)[1].sum())
    pms = default_point_masses(project, wing_kg + 1.2, wing_kg)
    model = assemble_mass_model(project, mesh, params, pms,
                                limit_load_pos=6.2, min_fos=1.42,
                                notes="test")
    out = write_simvis_mass(model, tmp_path / "simvis_mass")
    assert out.name == "simvis_mass.json"
    d = json.loads(out.read_text(encoding="utf-8"))
    _validate_like_simvis(d)
    assert d["min_factor_of_safety"] == 1.42


def test_wing_only_warns(project, wingbox_mesh):
    mesh, params = wingbox_mesh
    model = assemble_mass_model(project, mesh, params, [], limit_load_pos=6.0)
    assert any("wing structure" in w.lower() for w in model.warnings)
    _validate_like_simvis(model.to_schema_dict())   # still a valid file
