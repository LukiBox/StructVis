"""Fully Stressed Design optimizer - convergence with a fake linear evaluator."""
from __future__ import annotations

from structvis.core.optimize import fully_stressed_design, GAUGE_SETS
from structvis.core.wingbox import WingboxParams

YIELD = 300e6


class _FakeRes:
    """Membrane stress ~ 1/t per gauge, with different load intensities."""
    # load intensity [Pa*m] per gauge: rear-ish members lightly loaded
    K = {"skin_t": 4e5, "web_t": 6e5, "cap_t": 9e5, "rib_t": 1e5, "stringer_t": 2e5}

    def __init__(self, params):
        self.comp = {}
        for g, sets in GAUGE_SETS.items():
            s = self.K[g] / getattr(params, g)
            for st in sets:
                self.comp[st] = s
        self.min_fos = min(YIELD / v for v in self.comp.values())

    def component_max_vm(self):
        return self.comp


def test_fsd_drives_all_gauges_to_target():
    params = WingboxParams(skin_t=0.003, web_t=0.003, cap_t=0.003,
                           rib_t=0.003, stringer_t=0.003)
    gy = {g: YIELD for g in GAUGE_SETS}
    res = fully_stressed_design(params, _FakeRes, target_fos=1.5, gauge_yield=gy,
                                max_iter=25, tol=0.005)
    assert res.converged
    # every gauge should end fully stressed at ~ target FoS
    assert abs(res.min_fos - 1.5) < 0.1
    # the lightly loaded rib gauge must end thinner than the hot cap gauge
    assert res.params.rib_t < res.params.cap_t


def test_fsd_thins_unloaded_member():
    """A gauge carrying almost no stress should be driven toward the minimum."""
    class Res(_FakeRes):
        K = {"skin_t": 5e5, "web_t": 5e5, "cap_t": 5e5, "rib_t": 1e2,
             "stringer_t": 5e5}
    params = WingboxParams(skin_t=0.003, web_t=0.003, cap_t=0.003,
                           rib_t=0.003, stringer_t=0.003)
    gy = {g: YIELD for g in GAUGE_SETS}
    res = fully_stressed_design(params, Res, target_fos=1.5, gauge_yield=gy,
                                t_min=1e-4, max_iter=30)
    assert res.params.rib_t < 0.0005          # driven to near-minimum
    assert res.history[0].step == 0
