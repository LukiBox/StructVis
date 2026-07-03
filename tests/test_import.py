from structvis.core.flovis_import import load_flovis


def test_load_geometry(flovis_file):
    proj = load_flovis(flovis_file)
    assert proj.model.mass_kg == 2.5
    g = proj.geometry
    assert g.half_span == 1.0
    assert abs(g.chord(0.0) - 0.30) < 1e-9
    assert abs(g.chord(1.0) - 0.20) < 1e-9
    # dihedral must be flagged as ignored
    assert any("dihedral" in w.lower() for w in proj.warnings)


def test_aero_design_point(project):
    aero = project.aero
    assert aero is not None and aero.has_polar()
    # CL(alpha) is 0.1*(alpha+2); at CL=0.5 -> alpha=3
    assert abs(aero.alpha_at_cl(0.5) - 3.0) < 1e-6


def test_section_heights_positive(project):
    zu, zl = project.geometry.section_z(0.0, [0.2, 0.5, 0.7])
    assert (zu > zl).all()
