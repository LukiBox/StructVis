"""
Aerodynamic load reconstruction.

.flovis files carry no spanwise distributions, so lift is rebuilt with
Schrenk's approximation: the local lift per unit span is the average of the
planform-proportional and the elliptic distribution, scaled so the whole wing
carries exactly L = n * m * g at the chosen load case.

Chordwise, each spanwise strip's lift acts at the local center of pressure
(quarter chord shifted by the pitching moment) and is split between the front
and rear spar by lever-arm balance - this puts realistic bending AND torsion
into the FE model.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .flovis_import import ImportedProject

G = 9.80665
RHO_DEFAULT = 1.225
CM_DEFAULT = -0.05          # generic cambered-airfoil pitching moment
CD_DEFAULT = 0.02


@dataclass
class LoadCase:
    load_factor: float = 6.0        # n [g] - typical RC aerobatic limit load
    velocity: float = 15.0          # [m/s]
    rho: float = RHO_DEFAULT
    target_fos: float = 1.5
    inertial_relief: bool = True    # subtract n*g*(wing mass) from the lift
    aileron_factor: float = 0.0     # 0..1: spikes outer-panel torsion
    aileron_start: float = 0.6      # span fraction where the aileron begins

    @property
    def q(self) -> float:
        return 0.5 * self.rho * self.velocity**2


@dataclass
class PointMass:
    """A concentrated mass (engine, fuel, payload) placed on the half-wing."""
    name: str = "mass"
    mass_kg: float = 0.5
    span_frac: float = 0.3          # 0..1 of the half-span
    chord_frac: float = 0.4         # 0..1 of the local chord

    def to_dict(self) -> dict:
        return {"name": self.name, "mass_kg": self.mass_kg,
                "span_frac": self.span_frac, "chord_frac": self.chord_frac}

    @classmethod
    def from_dict(cls, d: dict) -> "PointMass":
        return cls(**{k: d[k] for k in d if k in cls.__dataclass_fields__})


@dataclass
class DesignPoint:
    """Load case resolved against the imported aero data."""
    lift_total: float               # n*m*g [N], whole aircraft
    CL_design: float
    cm: float
    cd: float
    alpha_deg: float | None
    warnings: list[str] = field(default_factory=list)


def resolve_design_point(project: ImportedProject, case: LoadCase) -> DesignPoint:
    L = case.load_factor * project.mass_kg * G
    S = project.geometry.area_full
    CL = L / max(case.q * S, 1e-9)

    warnings: list[str] = []
    cm, cd, alpha = CM_DEFAULT, CD_DEFAULT, None
    aero = project.aero
    if aero is not None and aero.has_polar():
        alpha = aero.alpha_at_cl(CL)
        cm_val = aero.cm_at_cl(CL)
        cd_val = aero.cd_at_cl(CL)
        cm = cm_val if cm_val is not None else CM_DEFAULT
        cd = cd_val if cd_val is not None else CD_DEFAULT
        cl_max = aero.CL_max or float(np.max(aero.CL))
        if CL > cl_max:
            warnings.append(
                f"Required CL = {CL:.2f} exceeds the wing's CL_max = "
                f"{cl_max:.2f}: this load case is beyond what the wing can "
                "aerodynamically produce at this speed. Increase velocity or "
                "reduce the load factor.")
    else:
        warnings.append("No polar data - using generic cm/cd for torsion/drag.")
    return DesignPoint(lift_total=L, CL_design=CL, cm=cm, cd=cd,
                       alpha_deg=alpha, warnings=warnings)


def schrenk_lift_per_span(geometry, y) -> np.ndarray:
    """
    Unnormalized Schrenk shape at spanwise stations y (half wing).
    Average of planform chord and elliptic equivalent chord.
    """
    y = np.asarray(y, float)
    b = 2 * geometry.half_span
    S = geometry.area_full
    c_plan = geometry.chord(y)
    arg = np.clip(1.0 - (2 * y / b) ** 2, 0.0, 1.0)
    c_ell = (4 * S / (np.pi * b)) * np.sqrt(arg)
    return 0.5 * (c_plan + c_ell)


@dataclass
class StripLoads:
    """Nodal force amounts per spanwise station row (root station excluded)."""
    y_stations: np.ndarray          # all mesh stations, y_stations[0] = root
    Fz_front: np.ndarray            # [N] vertical force -> front spar column
    Fz_rear: np.ndarray             # [N] vertical force -> rear spar column
    Fx: np.ndarray                  # [N] drag (chordwise, +x aft) per station
    x_cp_c: np.ndarray              # center-of-pressure fraction per station
    lift_half: float                # gross aerodynamic lift applied [N] (half)
    net_Fz: np.ndarray = None       # [N] net vertical per station (lift - inertia)
    inertial_half: float = 0.0      # total inertial relief applied [N] (half)

    def shear(self) -> np.ndarray:
        """Spanwise shear V(y) = integral of net load from the tip inward."""
        nz = self.net_Fz if self.net_Fz is not None else (self.Fz_front + self.Fz_rear)
        return np.cumsum(nz[::-1])[::-1]

    def bending_moment(self) -> np.ndarray:
        """Root-referenced bending moment M(y) from the net shear."""
        y = self.y_stations
        V = self.shear()
        M = np.zeros_like(V)
        for i in range(len(y) - 2, -1, -1):
            M[i] = M[i + 1] + V[i + 1] * (y[i + 1] - y[i])
        return M


def strip_loads(project: ImportedProject, case: LoadCase,
                y_stations: np.ndarray, front_spar: float, rear_spar: float,
                design: DesignPoint | None = None,
                struct_mass_station: np.ndarray | None = None,
                point_masses: "list[PointMass] | None" = None,
                fold_root: bool = True) -> StripLoads:
    """
    Integrate the Schrenk distribution into per-station forces, with inertial
    relief and point masses.

    Net vertical load per station = aerodynamic lift
        - n*g*(structural mass at the station)         [inertial relief]
        - n*g*(point masses mapped to the station).    [engines/fuel]

    Chordwise, every contribution acts at its own fraction (lift at the CP,
    structure near mid-box, each point mass at its chord fraction), so bending
    AND torsion stay correct. The clamped root station's share is folded into
    the first free station.
    """
    geom = project.geometry
    dp = design or resolve_design_point(project, case)
    y = np.asarray(y_stations, float)
    n = len(y)
    ng = case.load_factor * G

    # tributary lengths
    edges = np.empty(n + 1)
    edges[0] = y[0]
    edges[-1] = y[-1]
    edges[1:-1] = 0.5 * (y[:-1] + y[1:])
    trib = np.diff(edges)

    shape = schrenk_lift_per_span(geom, y)
    w = shape * trib
    total = w.sum()
    L_half = 0.5 * dp.lift_total
    dL = w * (L_half / max(total, 1e-12))       # [N] lift per station

    # chordwise placement of lift: x_cp/c = 0.25 - cm/CL
    cl_loc = max(abs(dp.CL_design), 0.05)
    x_cp_c = np.full(n, 0.25 - dp.cm / cl_loc)
    chord_mid = 0.5 * (front_spar + rear_spar)
    span_f = max(rear_spar - front_spar, 1e-6)

    def rear_share(chord_frac):
        return (np.asarray(chord_frac) - front_spar) / span_f

    # accumulate vertical force and its rear/front split from each contribution
    Fz_rear = dL * rear_share(x_cp_c)
    Fz_front = dL - Fz_rear
    net = dL.copy()

    # --- inertial relief: the wing's own weight pulls down at n*g ---
    inertial_half = 0.0
    if case.inertial_relief and struct_mass_station is not None:
        sm = np.asarray(struct_mass_station, float)
        inert = ng * sm                         # [N] down per station
        net -= inert
        Fz_rear -= inert * rear_share(chord_mid)
        Fz_front -= inert - inert * rear_share(chord_mid)
        inertial_half += float(inert.sum())

    # --- point masses (engines / fuel), placed on the half-wing ---
    for pm in (point_masses or []):
        if pm.mass_kg <= 0:
            continue
        yj = np.clip(pm.span_frac, 0.0, 1.0) * geom.half_span
        i = int(np.argmin(np.abs(y - yj)))
        f = ng * pm.mass_kg                     # [N] down
        rs = float(rear_share(pm.chord_frac))
        net[i] -= f
        Fz_rear[i] -= f * rs
        Fz_front[i] -= f * (1.0 - rs)
        inertial_half += f

    # --- aileron deflection: extra torsion couple on the outer panels ---
    if case.aileron_factor > 0:
        q = case.q
        outer = y >= case.aileron_start * geom.half_span
        d_cm = -0.20 * case.aileron_factor      # nose-down increment
        c = geom.chord(y)
        M = np.where(outer, q * c**2 * d_cm * trib, 0.0)     # [N.m] per station
        couple = M / (span_f * np.maximum(c, 1e-6))          # spar-couple force
        Fz_rear += couple
        Fz_front -= couple

    # fold the clamped-root station into the first free station (solver decks
    # only; fold_root=False gives the smooth distribution for display plots)
    if fold_root and n > 1:
        for arr in (Fz_front, Fz_rear, net):
            arr[1] += arr[0]
            arr[0] = 0.0

    # drag strip loads (small, in-plane)
    q = case.q
    Fx = q * geom.chord(y) * dp.cd * trib
    if fold_root and n > 1:
        Fx[1] += Fx[0]
        Fx[0] = 0.0

    return StripLoads(y_stations=y, Fz_front=Fz_front, Fz_rear=Fz_rear,
                      Fx=Fx, x_cp_c=x_cp_c, lift_half=float(dL.sum()),
                      net_Fz=net, inertial_half=inertial_half)
