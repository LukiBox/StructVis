"""Report layer (summary + charts + PDF) - no ccx needed, uses a synthetic result."""
from __future__ import annotations

import numpy as np
import pytest

from structvis.core import mesher
from structvis.core.wingbox import WingboxParams
from structvis.core.loads import LoadCase, resolve_design_point, strip_loads
from structvis.core.fea.result import FeaResult
from structvis.core.report import summary, pdf_report


def _fake_result(mesh, yield_strength, peak_pa):
    """A plausible FeaResult: stress high at root, deflection at tip."""
    y = mesh.nodes[:, 1]
    yn = y / max(y.max(), 1e-9)
    disp = np.zeros_like(mesh.nodes)
    disp[:, 2] = 0.03 * yn ** 2
    vm = peak_pa * (1 - 0.85 * yn)
    return FeaResult(nodes=mesh.nodes, elems=mesh.elems, disp=disp,
                     von_mises=vm, yield_strength=yield_strength,
                     half_span=float(y.max()),
                     elset_of_elem=mesh.elset_of_element())


@pytest.fixture
def solved(project):
    params = WingboxParams(n_ribs=5)
    mesh = mesher.build_mesh(project.geometry, params)
    case = LoadCase(load_factor=6, velocity=16, target_fos=1.5)
    dp = resolve_design_point(project, case)
    sl = strip_loads(project, case, mesh.y_stations,
                     params.front_spar, params.rear_spar, design=dp)
    return project, params, case, dp, mesh, sl


def test_verdicts_levels(solved):
    project, params, case, dp, mesh, sl = solved
    # over-built: low stress -> high FoS -> yellow (over-built)
    res = _fake_result(mesh, 503e6, peak_pa=5e6)
    v = summary.verdicts(res, case)
    assert v[0].name.startswith("Minimum")
    assert v[0].level in ("green", "yellow")

    # failing: peak above yield -> red
    res_fail = _fake_result(mesh, 503e6, peak_pa=600e6)
    assert summary.verdicts(res_fail, case)[0].level == "red"


def test_plain_language_mentions_key_facts(solved):
    project, params, case, dp, mesh, sl = solved
    res = _fake_result(mesh, 503e6, peak_pa=350e6)  # FoS ~1.4 -> under target
    text = summary.plain_language(res, params, case, dp, total_mass_kg=0.5)
    assert "Factor of Safety" in text
    assert "%" in text                       # deflection as % span
    assert len(text) > 100


def test_pdf_builds(solved, tmp_path):
    project, params, case, dp, mesh, sl = solved
    res = _fake_result(mesh, 503e6, peak_pa=300e6)
    out = pdf_report.build_report(
        res, tmp_path / "r.pdf", project=project, params=params,
        load_case=case, design=dp, strip_loads=sl, total_mass_kg=0.6)
    assert out.exists()
    data = out.read_bytes()
    assert data[:4] == b"%PDF" and len(data) > 5000


def test_pdf_with_ai_text(solved, tmp_path):
    project, params, case, dp, mesh, sl = solved
    res = _fake_result(mesh, 503e6, peak_pa=200e6)
    out = pdf_report.build_report(
        res, tmp_path / "r2.pdf", project=project, params=params,
        load_case=case, design=dp, strip_loads=sl, total_mass_kg=0.6,
        ai_text="The rear spar is lightly loaded.\nConsider thinning it.")
    assert out.exists() and out.read_bytes()[:4] == b"%PDF"
