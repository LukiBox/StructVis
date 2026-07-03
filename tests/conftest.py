"""Shared fixtures: a synthetic .flovis file and a built wingbox mesh."""
from __future__ import annotations

import json
import os
import tempfile
import zipfile

# isolate persisted settings (theme/language/welcome) from the real user
# config; must happen before structvis.ui.theme is imported anywhere
os.environ.setdefault("STRUCTVIS_CONFIG_DIR",
                      tempfile.mkdtemp(prefix="structvis_test_cfg_"))

import numpy as np
import pytest

from structvis.core.flovis_import import load_flovis
from structvis.core.wingbox import WingboxParams
from structvis.core import mesher


@pytest.fixture
def flovis_file(tmp_path):
    """Write a minimal but valid .flovis (rectangular-ish wing + polar)."""
    model = {
        "name": "TestWing", "layout": "Low wing (classic)",
        "surfaces": [{
            "name": "Wing", "span": 2.0, "root_chord": 0.30,
            "tip_chord": 0.20, "sweep_deg": 3.0, "dihedral_deg": 4.0,
            "airfoil_root": "NACA 2412", "airfoil_tip": "NACA 2410",
            "is_vertical": False,
        }],
        "fuselage_length": 1.15, "fuselage_diam": 0.12,
        "mass_kg": 2.5, "cg_x": 0.36,
    }
    alpha = np.linspace(-4, 12, 9)
    result = {
        "method": "VLM (AeroSandbox)", "model_name": "TestWing",
        "alpha_deg": alpha.tolist(),
        "CL": (0.1 * (alpha + 2)).tolist(),
        "CD": (0.02 + 0.01 * (0.1 * (alpha + 2)) ** 2).tolist(),
        "Cm": (-0.05 - 0.01 * alpha).tolist(),
        "velocity": 16.0, "reference_area": 0.5, "mac": 0.253,
        "CL_max": 1.3, "cg_x": 0.36,
    }
    path = tmp_path / "test.flovis"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("manifest.json", json.dumps({"format": "flovis", "version": 1}))
        z.writestr("model.json", json.dumps(model))
        z.writestr("result.json", json.dumps(result))
    return path


@pytest.fixture
def project(flovis_file):
    return load_flovis(flovis_file)


@pytest.fixture
def wingbox_mesh(project):
    params = WingboxParams(n_ribs=5)
    return mesher.build_mesh(project.geometry, params), params
