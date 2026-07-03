"""
Wing geometry for StructVis.

`Surface`/`AircraftModel` mirror the Flovis dataclasses so `model.json` from a
`.flovis` file parses directly. `WingGeometry` is the derived half-wing
external mold line every other module works with: local chord, leading edge,
and airfoil surface heights at any (y, x/c).

Simplifications (stated in the UI): dihedral and incidence are ignored for
the structural model; the wingbox is built in the wing's local frame with the
root leading edge at x = x_le, y = 0 (right half-wing, root clamped).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from . import naca


@dataclass
class Surface:
    """A single lifting surface, as saved by Flovis."""
    name: str
    span: float                 # full span [m]
    root_chord: float
    tip_chord: float
    sweep_deg: float = 0.0      # leading-edge sweep
    dihedral_deg: float = 0.0
    incidence_deg: float = 0.0
    x_le: float = 0.0
    z_pos: float = 0.0
    airfoil_root: str = "NACA 2412"
    airfoil_tip: str = "NACA 2412"
    is_vertical: bool = False

    @property
    def area(self) -> float:
        return 0.5 * (self.root_chord + self.tip_chord) * self.span

    @property
    def mac(self) -> float:
        cr, ct = self.root_chord, self.tip_chord
        if cr + ct == 0:
            return 0.0
        taper = ct / cr
        return (2.0 / 3.0) * cr * (1 + taper + taper**2) / (1 + taper)

    @classmethod
    def from_dict(cls, d: dict) -> "Surface":
        fields = {k: d[k] for k in d if k in cls.__dataclass_fields__}
        return cls(**fields)


@dataclass
class AircraftModel:
    """Trimmed Flovis AircraftModel - enough to read model.json."""
    name: str = "model"
    layout: str = ""
    surfaces: list[Surface] = field(default_factory=list)
    fuselage_length: float = 1.0
    fuselage_diam: float = 0.12
    mass_kg: float = 2.0
    cg_x: float = 0.25

    @property
    def wing(self) -> Surface | None:
        for s in self.surfaces:
            if s.name.lower().startswith("wing") and not s.is_vertical:
                return s
        for s in self.surfaces:
            if not s.is_vertical:
                return s
        return self.surfaces[0] if self.surfaces else None

    @classmethod
    def from_dict(cls, d: dict) -> "AircraftModel":
        return cls(
            name=d.get("name", "model"),
            layout=str(d.get("layout", "")),
            surfaces=[Surface.from_dict(s) for s in d.get("surfaces", [])],
            fuselage_length=d.get("fuselage_length", 1.0),
            fuselage_diam=d.get("fuselage_diam", 0.12),
            mass_kg=d.get("mass_kg", 2.0),
            cg_x=d.get("cg_x", 0.25),
        )

    def to_dict(self) -> dict:
        from dataclasses import asdict
        return asdict(self)


def _safe_spec(text: str | None) -> naca.NacaSpec:
    try:
        return naca.parse_naca(text or "0012")
    except Exception:  # noqa: BLE001 - unknown airfoil name -> generic 12%
        return naca.NacaSpec(thickness=0.12)


class WingGeometry:
    """Half-wing mold line: chord/LE/surface heights as functions of y."""

    def __init__(self, surface: Surface):
        self.surface = surface
        self.name = surface.name
        self.half_span = surface.span / 2.0
        self.root_chord = surface.root_chord
        self.tip_chord = surface.tip_chord
        self.sweep_deg = surface.sweep_deg
        self.spec_root = _safe_spec(surface.airfoil_root)
        self.spec_tip = _safe_spec(surface.airfoil_tip or surface.airfoil_root)

    # ---- planform ---------------------------------------------------------
    def eta(self, y):
        return np.clip(np.asarray(y, float) / max(self.half_span, 1e-9), 0.0, 1.0)

    def chord(self, y):
        return self.root_chord + (self.tip_chord - self.root_chord) * self.eta(y)

    def x_le(self, y):
        return np.asarray(y, float) * np.tan(np.deg2rad(self.sweep_deg))

    @property
    def area_full(self) -> float:
        """Full-wing planform area (both halves)."""
        return 0.5 * (self.root_chord + self.tip_chord) * 2 * self.half_span

    @property
    def mac(self) -> float:
        return self.surface.mac

    # ---- section ----------------------------------------------------------
    def section_z(self, y: float, xc):
        """
        Absolute upper/lower surface heights [m] at span y, chord fractions xc.
        Airfoil thickness/camber blends linearly root -> tip.
        """
        zu_r, zl_r = naca.section_z(self.spec_root, xc)
        zu_t, zl_t = naca.section_z(self.spec_tip, xc)
        e = float(self.eta(y))
        c = float(self.chord(y))
        zu = ((1 - e) * zu_r + e * zu_t) * c
        zl = ((1 - e) * zl_r + e * zl_t) * c
        return zu, zl

    def box_height(self, y: float, xc: float) -> float:
        zu, zl = self.section_z(y, [xc])
        return float(zu[0] - zl[0])
