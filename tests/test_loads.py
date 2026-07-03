import numpy as np

from structvis.core.loads import (LoadCase, resolve_design_point,
                                  schrenk_lift_per_span, strip_loads, G)


def test_design_point_lift(project):
    case = LoadCase(load_factor=6.0, velocity=16.0)
    dp = resolve_design_point(project, case)
    assert abs(dp.lift_total - 6.0 * project.mass_kg * G) < 1e-6


def test_schrenk_integrates_to_lift(project):
    """Total mapped vertical load must equal n*m*g / 2 (half wing)."""
    case = LoadCase(load_factor=5.0, velocity=18.0)
    dp = resolve_design_point(project, case)
    y = np.linspace(0, project.geometry.half_span, 40)
    sl = strip_loads(project, case, y, 0.2, 0.7, design=dp)
    applied = float(sl.Fz_front.sum() + sl.Fz_rear.sum())
    assert abs(applied - 0.5 * dp.lift_total) / (0.5 * dp.lift_total) < 1e-6


def test_schrenk_shape_decreases_outboard(project):
    y = np.linspace(0, project.geometry.half_span, 20)
    shape = schrenk_lift_per_span(project.geometry, y)
    assert shape[0] > shape[-1]          # more lift at root than tip
    assert (shape >= 0).all()


def test_root_station_unloaded(project):
    """The clamped root station carries no direct nodal load."""
    case = LoadCase()
    y = np.linspace(0, project.geometry.half_span, 15)
    sl = strip_loads(project, case, y, 0.2, 0.7)
    assert sl.Fz_front[0] == 0.0 and sl.Fz_rear[0] == 0.0
