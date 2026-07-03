import numpy as np

from structvis.core import mesher
from structvis.core.wingbox import WingboxParams


def test_mesh_builds(wingbox_mesh):
    mesh, params = wingbox_mesh
    assert mesh.n_nodes > 0 and mesh.n_elems > 0
    # all element node ids are valid
    assert mesh.elems.min() >= 0
    assert mesh.elems.max() < mesh.n_nodes


def test_no_duplicate_nodes(wingbox_mesh):
    """Watertight-by-construction: no two nodes share a location."""
    mesh, _ = wingbox_mesh
    rounded = np.round(mesh.nodes, 9)
    uniq = np.unique(rounded, axis=0)
    assert len(uniq) == len(mesh.nodes), "duplicate coincident nodes found"


def test_junction_nodes_shared(wingbox_mesh):
    """Skin, spar and rib element sets must share boundary nodes."""
    mesh, _ = wingbox_mesh
    skin_up = set(mesh.elset_nodes("SKIN_UP").tolist()) \
        if "SKIN_UP" in mesh.elsets else set(mesh.elset_nodes("CAP_UP").tolist())
    spar_f = set(mesh.elset_nodes("SPAR_F").tolist())
    ribs = set(mesh.elset_nodes("RIBS").tolist())
    # front spar shares its top edge with the upper skin/caps
    cap_up = set(mesh.elset_nodes("CAP_UP").tolist())
    assert spar_f & (skin_up | cap_up), "spar web not fused to skin"
    assert ribs & spar_f, "ribs not fused to spar"


def test_root_nodes_present(wingbox_mesh):
    mesh, _ = wingbox_mesh
    assert len(mesh.root_nodes) > 0
    assert np.allclose(mesh.nodes[mesh.root_nodes, 1], 0.0)


def test_thickness_change_preserves_mesh(project):
    """Scaling thicknesses must NOT change mesh topology (fast optimizer)."""
    p1 = WingboxParams(n_ribs=5)
    p2 = p1.scaled(2.0)
    m1 = mesher.build_mesh(project.geometry, p1)
    m2 = mesher.build_mesh(project.geometry, p2)
    assert m1.n_nodes == m2.n_nodes
    assert np.array_equal(m1.elems, m2.elems)


def test_more_ribs_more_elements(project):
    m_few = mesher.build_mesh(project.geometry, WingboxParams(n_ribs=3))
    m_many = mesher.build_mesh(project.geometry, WingboxParams(n_ribs=10))
    assert m_many.n_elems > m_few.n_elems
