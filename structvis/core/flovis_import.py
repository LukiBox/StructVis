"""
Reader for Flovis project files (.flovis).

A .flovis is a zip of JSON/dat files: manifest.json, model.json
(AircraftModel), airfoil.dat, result.json (AnalysisResult). Only geometry and
the *global* coefficient sweeps are persisted - Flovis drops array-valued
extras on save - so spanwise load distributions must be reconstructed here
(see loads.py / Schrenk).
"""
from __future__ import annotations

import json
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .geometry import AircraftModel, WingGeometry


@dataclass
class AeroData:
    """Global aero data recovered from result.json (all optional)."""
    method: str = ""
    velocity: float = 15.0
    alpha_deg: np.ndarray | None = None
    CL: np.ndarray | None = None
    CD: np.ndarray | None = None
    Cm: np.ndarray | None = None
    CL_max: float = 0.0
    reference_area: float = 0.0
    mac: float = 0.0

    @classmethod
    def from_dict(cls, d: dict) -> "AeroData":
        def arr(k):
            v = d.get(k)
            return np.asarray(v, float) if v is not None else None
        return cls(
            method=d.get("method", ""),
            velocity=float(d.get("velocity", 15.0)),
            alpha_deg=arr("alpha_deg"), CL=arr("CL"), CD=arr("CD"), Cm=arr("Cm"),
            CL_max=float(d.get("CL_max", 0.0) or 0.0),
            reference_area=float(d.get("reference_area", 0.0) or 0.0),
            mac=float(d.get("mac", 0.0) or 0.0),
        )

    def to_dict(self) -> dict:
        out = {"method": self.method, "velocity": self.velocity,
               "CL_max": self.CL_max, "reference_area": self.reference_area,
               "mac": self.mac}
        for k in ("alpha_deg", "CL", "CD", "Cm"):
            v = getattr(self, k)
            out[k] = None if v is None else np.asarray(v).tolist()
        return out

    # ---- design-point helpers ----------------------------------------
    def has_polar(self) -> bool:
        return (self.alpha_deg is not None and self.CL is not None
                and len(self.alpha_deg) >= 2)

    def alpha_at_cl(self, cl: float) -> float | None:
        """Angle of attack where CL(alpha) = cl (linear region interp)."""
        if not self.has_polar():
            return None
        a, CL = self.alpha_deg, self.CL
        order = np.argsort(CL)
        return float(np.interp(cl, CL[order], a[order]))

    def cm_at_cl(self, cl: float) -> float | None:
        if not self.has_polar() or self.Cm is None:
            return None
        alpha = self.alpha_at_cl(cl)
        return float(np.interp(alpha, self.alpha_deg, self.Cm))

    def cd_at_cl(self, cl: float) -> float | None:
        if not self.has_polar() or self.CD is None:
            return None
        alpha = self.alpha_at_cl(cl)
        return float(np.interp(alpha, self.alpha_deg, self.CD))


@dataclass
class ImportedProject:
    """Everything StructVis needs from a .flovis file."""
    model: AircraftModel
    geometry: WingGeometry
    aero: AeroData | None = None
    source_path: str = ""
    warnings: list[str] = field(default_factory=list)

    @property
    def mass_kg(self) -> float:
        return self.model.mass_kg


def load_flovis(path: str | Path) -> ImportedProject:
    """Parse a .flovis file. Raises ValueError when no usable wing exists."""
    path = Path(path)
    warnings: list[str] = []
    with zipfile.ZipFile(path, "r") as z:
        names = set(z.namelist())
        if "model.json" not in names:
            raise ValueError(
                "This .flovis file contains no geometry (model.json missing). "
                "Save the project in Flovis with a model loaded.")
        model = AircraftModel.from_dict(json.loads(z.read("model.json")))
        aero = None
        if "result.json" in names:
            aero = AeroData.from_dict(json.loads(z.read("result.json")))
        else:
            warnings.append(
                "No analysis result in the file - using default velocity and "
                "a generic pitching moment. Run an analysis in Flovis for "
                "better load estimates.")

    wing = model.wing
    if wing is None:
        raise ValueError("The model has no lifting surface.")
    if wing.span <= 0 or wing.root_chord <= 0:
        raise ValueError(f"Wing '{wing.name}' has degenerate dimensions.")

    geometry = WingGeometry(wing)
    if wing.dihedral_deg:
        warnings.append(
            f"Dihedral ({wing.dihedral_deg:g} deg) is ignored by the "
            "structural model (flat half-wing).")
    return ImportedProject(model=model, geometry=geometry, aero=aero,
                           source_path=str(path), warnings=warnings)
