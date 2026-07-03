"""Inertial relief, point masses, aileron torsion, and mass-per-station."""
from __future__ import annotations

import numpy as np

from structvis.core import mesher
from structvis.core.mass import mass_per_station, total_mass
from structvis.core.wingbox import WingboxParams
from structvis.core.loads import (LoadCase, PointMass, resolve_design_point,
                                  strip_loads)


def test_mass_per_station_sums_to_total(project):
    p = WingboxParams(n_ribs=6)
    mesh = mesher.build_mesh(project.geometry, p)
    sm = mass_per_station(mesh, p, mesh.y_stations)
    assert abs(sm.sum() - total_mass(mesh, p, half_wing=True)) < 1e-9


def test_inertial_relief_reduces_root_bending(project):
    p = WingboxParams(n_ribs=6)
    mesh = mesher.build_mesh(project.geometry, p)
    sm = mass_per_station(mesh, p, mesh.y_stations)
    case = LoadCase(load_factor=6, inertial_relief=True)
    dp = resolve_design_point(project, case)

    no_relief = strip_loads(project, LoadCase(load_factor=6, inertial_relief=False),
                            mesh.y_stations, p.front_spar, p.rear_spar, design=dp,
                            struct_mass_station=sm)
    with_relief = strip_loads(project, case, mesh.y_stations,
                              p.front_spar, p.rear_spar, design=dp,
                              struct_mass_station=sm)
    # relief removes lift -> lower net load and lower root bending moment
    assert with_relief.inertial_half > 0
    assert abs(with_relief.bending_moment()[0]) < abs(no_relief.bending_moment()[0])


def test_point_mass_adds_downforce_and_shear_step(project):
    p = WingboxParams(n_ribs=8)
    mesh = mesher.build_mesh(project.geometry, p)
    sm = mass_per_station(mesh, p, mesh.y_stations)
    case = LoadCase(load_factor=6, inertial_relief=False)
    dp = resolve_design_point(project, case)

    base = strip_loads(project, case, mesh.y_stations, p.front_spar, p.rear_spar,
                       design=dp, struct_mass_station=sm)
    heavy = strip_loads(project, case, mesh.y_stations, p.front_spar, p.rear_spar,
                        design=dp, struct_mass_station=sm,
                        point_masses=[PointMass("motor", 3.0, 0.3, 0.4)])
    # a 3 kg mass at 6 g pulls down ~176 N -> net load drops
    assert heavy.net_Fz.sum() < base.net_Fz.sum() - 100
    assert heavy.inertial_half > 150


def test_aileron_spikes_outer_torsion(project):
    p = WingboxParams(n_ribs=8)
    mesh = mesher.build_mesh(project.geometry, p)
    case0 = LoadCase(aileron_factor=0.0)
    case1 = LoadCase(aileron_factor=1.0, aileron_start=0.6)
    dp = resolve_design_point(project, case0)
    sl0 = strip_loads(project, case0, mesh.y_stations, p.front_spar, p.rear_spar, design=dp)
    sl1 = strip_loads(project, case1, mesh.y_stations, p.front_spar, p.rear_spar, design=dp)
    # aileron adds a front/rear couple on the outer panel: front & rear differ more
    y = mesh.y_stations
    outer = y >= 0.6 * project.geometry.half_span
    couple0 = np.abs(sl0.Fz_front - sl0.Fz_rear)[outer].sum()
    couple1 = np.abs(sl1.Fz_front - sl1.Fz_rear)[outer].sum()
    assert couple1 > couple0


def test_pointmass_roundtrip():
    pm = PointMass("engine", 2.5, 0.4, 0.35)
    d = pm.to_dict()
    pm2 = PointMass.from_dict(d)
    assert pm2.mass_kg == 2.5 and pm2.span_frac == 0.4 and pm2.name == "engine"
