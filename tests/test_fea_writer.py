"""Writer/parser tests that don't need the ccx binary."""
from __future__ import annotations

import numpy as np

from structvis.core.fea.ccx_writer import build_inp
from structvis.core.fea.frd_parser import parse_frd, von_mises
from structvis.core.loads import LoadCase, strip_loads
from structvis.core.wingbox import WingboxParams


def test_inp_has_required_cards(wingbox_mesh, project):
    mesh, params = wingbox_mesh
    y = mesh.y_stations
    sl = strip_loads(project, LoadCase(), y, params.front_spar, params.rear_spar)
    inp = build_inp(mesh, params, sl)
    for card in ("*NODE", "*ELEMENT, TYPE=S4", "*SHELL SECTION",
                 "*MATERIAL", "*ELASTIC", "*BOUNDARY", "*CLOAD",
                 "*STATIC", "OUTPUT=2D"):
        assert card in inp, f"missing {card}"
    # every element set gets a shell section
    for name in mesh.elsets:
        assert f"ELSET={name}" in inp


def test_inp_node_count(wingbox_mesh, project):
    mesh, params = wingbox_mesh
    inp = build_inp(mesh, params, None)
    node_lines = [ln for ln in inp.splitlines()
                  if ln and ln[0].isdigit() and ", " in ln]
    # at least as many data lines as nodes
    assert len(node_lines) >= mesh.n_nodes


def test_von_mises_uniaxial():
    # pure uniaxial stress sigma -> von Mises = sigma
    assert abs(von_mises(100e6, 0, 0, 0, 0, 0) - 100e6) < 1.0


def test_von_mises_pure_shear():
    # pure shear tau -> von Mises = sqrt(3)*tau
    assert abs(von_mises(0, 0, 0, 50e6, 0, 0) - np.sqrt(3) * 50e6) < 1.0


def test_frd_roundtrip(tmp_path):
    """Hand-write a tiny FRD and confirm the parser recovers it."""
    frd = tmp_path / "job.frd"
    lines = [
        "    1C",
        " -4  DISP        4    1",
        " -5  D1          1    2    1    0",
        " -5  D2          1    2    2    0",
        " -5  D3          1    2    3    0",
        f" -1{1:10d}{0.0:12.5E}{0.0:12.5E}{1.0e-3:12.5E}",
        f" -1{2:10d}{0.0:12.5E}{0.0:12.5E}{2.0e-3:12.5E}",
        " -3",
        " -4  STRESS      6    1",
        " -5  SXX         1    4    1    1",
        " -5  SYY         1    4    2    2",
        " -5  SZZ         1    4    3    3",
        " -5  SXY         1    4    1    2",
        " -5  SYZ         1    4    2    3",
        " -5  SZX         1    4    3    1",
        f" -1{1:10d}{100e6:12.5E}{0.0:12.5E}{0.0:12.5E}{0.0:12.5E}{0.0:12.5E}{0.0:12.5E}",
        f" -1{2:10d}{0.0:12.5E}{0.0:12.5E}{0.0:12.5E}{50e6:12.5E}{0.0:12.5E}{0.0:12.5E}",
        " -3",
    ]
    frd.write_text("\n".join(lines))
    out = parse_frd(frd, n_nodes=2)
    assert abs(out["disp"][1, 2] - 2.0e-3) < 1e-9
    assert abs(out["von_mises"][0] - 100e6) < 1e3
    assert abs(out["von_mises"][1] - np.sqrt(3) * 50e6) < 1e3
