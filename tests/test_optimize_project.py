import numpy as np

from structvis.core.optimize import autosize
from structvis.core.wingbox import WingboxParams
from structvis.core.loads import LoadCase
from structvis.core import project as proj
from structvis.core.fea.result import FeaResult


def test_autosize_hits_target():
    """FoS ~ factor (stress ~ 1/t): secant must converge to target."""
    base_fos_at_1 = 0.8            # under-designed at factor 1

    def eval_fos(factor):
        return base_fos_at_1 * factor      # linear model

    res = autosize(eval_fos, target_fos=1.5, tol=0.01)
    assert res.converged
    assert abs(res.min_fos - 1.5) < 0.015 * 1.5
    assert abs(res.factor - 1.5 / 0.8) < 0.05


def test_autosize_nonlinear_converges():
    def eval_fos(factor):
        return 0.5 * factor ** 1.2         # mildly nonlinear

    res = autosize(eval_fos, target_fos=1.5, tol=0.01, max_iter=15)
    assert res.converged
    assert abs(res.min_fos - 1.5) < 0.02 * 1.5


def test_autosize_already_ok():
    res = autosize(lambda f: 1.5, target_fos=1.5)
    assert res.converged and res.history[0].step == 0


def test_project_roundtrip(project, tmp_path):
    params = WingboxParams(n_ribs=7, skin_t=0.002, material="ti64")
    case = LoadCase(load_factor=4.5, velocity=20.0, target_fos=1.8)

    # fake a small result so the npz path is exercised
    nodes = np.random.rand(10, 3)
    elems = np.array([[0, 1, 2, 3], [4, 5, 6, 7]])
    result = FeaResult(nodes=nodes, elems=elems, disp=np.random.rand(10, 3),
                       von_mises=np.random.rand(10) * 1e8,
                       yield_strength=880e6, half_span=1.0,
                       elset_of_elem=np.array(["SKIN_UP", "SPAR_F"], dtype=object))

    path = proj.save_project(tmp_path / "p.structvis", project, params, case, result)
    assert path.exists()

    loaded = proj.load_project(path)
    assert loaded["params"].material == "ti64"
    assert loaded["params"].n_ribs == 7
    assert abs(loaded["load_case"].load_factor - 4.5) < 1e-9
    assert loaded["load_case"].target_fos == 1.8
    assert loaded["project"].model.name == project.model.name
    r = loaded["result"]
    assert r is not None
    assert np.allclose(r.nodes, nodes)
    assert r.yield_strength == 880e6
    assert list(r.elset_of_elem) == ["SKIN_UP", "SPAR_F"]


def test_project_roundtrip_no_result(project, tmp_path):
    params = WingboxParams()
    case = LoadCase()
    path = proj.save_project(tmp_path / "n.structvis", project, params, case, None)
    loaded = proj.load_project(path)
    assert loaded["result"] is None
    assert loaded["buckling"] is None
    assert loaded["project"].geometry.half_span == project.geometry.half_span


def test_project_roundtrip_buckling(project, tmp_path):
    from structvis.core.fea.result import BucklingResult
    params = WingboxParams()
    case = LoadCase()
    nodes = np.random.rand(6, 3)
    elems = np.array([[0, 1, 2, 3], [2, 3, 4, 5]])
    buck = BucklingResult(
        factors=np.array([3.2, 4.7, 8.1]), nodes=nodes, elems=elems,
        mode1=np.random.rand(6, 3), half_span=1.25,
        elset_of_elem=np.array(["SKIN_UP", "SPAR_F"], dtype=object))
    path = proj.save_project(tmp_path / "b.structvis", project, params, case,
                             None, buckling=buck)
    loaded = proj.load_project(path)
    lb = loaded["buckling"]
    assert lb is not None
    assert np.allclose(lb.factors, [3.2, 4.7, 8.1])
    assert abs(lb.critical_factor - 3.2) < 1e-9
    assert lb.mode1 is not None and lb.mode1.shape == (6, 3)
    assert lb.half_span == 1.25
    assert list(lb.elset_of_elem) == ["SKIN_UP", "SPAR_F"]
