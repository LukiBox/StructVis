"""Export to SimVis: build and write ``simvis_mass.json`` (schema simvis-mass/1).

StructVis knows the *wing structure* mass exactly (skin/spar/rib/stringer
areas x thickness x density, straight off the FEA mesh). The rest of the
aircraft - fuselage, tail, motor, battery, payload - is entered by the user
as point masses (or left to a single "everything else" lump placed to hit a
target all-up mass). From the wing element cloud plus those point masses we
integrate the full mass, CG and inertia tensor in the Flovis geometry frame
(x aft from the nose, y right, z up) and write the file SimVis validates
strictly.

The limit load factor - the number that powers SimVis's in-flight structural
failure - comes straight from the design load case and the achieved factor
of safety, so "StructVis said 6.2 g" and "SimVis folds the wing at 6.2 g"
are the same number.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .flovis_import import ImportedProject
from .mass import element_mass
from .mesher import WingboxMesh
from .wingbox import WingboxParams

SCHEMA_ID = "simvis-mass/1"


@dataclass
class PointMass:
    """A discrete mass item at a geometry-frame position [m] (y=0 = centerline)."""
    name: str
    mass_kg: float
    x: float = 0.0
    z: float = 0.0
    y: float = 0.0

    def to_dict(self) -> dict:
        return {"name": self.name, "mass_kg": self.mass_kg,
                "x": self.x, "y": self.y, "z": self.z}

    @classmethod
    def from_dict(cls, d: dict) -> "PointMass":
        return cls(name=d.get("name", "mass"), mass_kg=float(d["mass_kg"]),
                   x=float(d.get("x", 0.0)), y=float(d.get("y", 0.0)),
                   z=float(d.get("z", 0.0)))


@dataclass
class MassModel:
    """Assembled mass model + the numbers SimVis needs."""
    mass_kg: float
    cg_m: np.ndarray                     # [x, y, z] geometry frame
    inertia: dict[str, float]            # Ixx, Iyy, Izz, Ixz, Ixy, Iyz
    wing_structural_kg: float
    point_mass_kg: float
    limit_load_pos: float
    limit_load_neg: float
    min_factor_of_safety: float | None
    notes: str = ""
    warnings: list[str] = field(default_factory=list)

    def to_schema_dict(self) -> dict:
        d = {
            "schema": SCHEMA_ID,
            "mass_kg": round(float(self.mass_kg), 6),
            "cg_m": [round(float(v), 6) for v in self.cg_m],
            "inertia_kgm2": {k: round(float(v), 8)
                             for k, v in self.inertia.items()},
            "limit_load_factor": {
                "positive": round(float(self.limit_load_pos), 3),
                "negative": round(float(self.limit_load_neg), 3)},
        }
        if self.min_factor_of_safety is not None:
            d["min_factor_of_safety"] = round(float(self.min_factor_of_safety), 3)
        if self.notes:
            d["notes"] = self.notes
        return d


# --------------------------------------------------------------- inertia math
def _point_cloud_inertia(rel: np.ndarray, m: np.ndarray) -> np.ndarray:
    """Inertia matrix of point masses about the origin of ``rel`` (standard
    sign convention: off-diagonals are ``-Ixy`` etc.)."""
    x, y, z = rel[:, 0], rel[:, 1], rel[:, 2]
    ixx = float((m * (y * y + z * z)).sum())
    iyy = float((m * (x * x + z * z)).sum())
    izz = float((m * (x * x + y * y)).sum())
    ixy = float((m * x * y).sum())
    ixz = float((m * x * z).sum())
    iyz = float((m * y * z).sum())
    return np.array([[ixx, -ixy, -ixz],
                     [-ixy, iyy, -iyz],
                     [-ixz, -iyz, izz]])


def wing_mass_cloud(project: ImportedProject, mesh: WingboxMesh,
                    params: WingboxParams) -> tuple[np.ndarray, np.ndarray]:
    """Full-wing structural point cloud in the geometry frame.

    Returns (positions (2M,3), masses (2M,)). The FEA mesh is a half-wing in
    local coordinates (x chordwise from the root LE, y spanwise, z airfoil
    height); it is translated by the parent surface's ``x_le``/``z_pos`` and
    mirrored to the other half.
    """
    em = element_mass(mesh, params)                  # per-element, half-wing
    centroids = mesh.nodes[mesh.elems].mean(axis=1)  # (M,3) local
    surf = project.model.wing
    x0 = float(getattr(surf, "x_le", 0.0))
    z0 = float(getattr(surf, "z_pos", 0.0))

    half = np.column_stack([centroids[:, 0] + x0,
                            centroids[:, 1],
                            centroids[:, 2] + z0])
    mirror = half.copy()
    mirror[:, 1] *= -1.0
    pos = np.vstack([half, mirror])
    mass = np.concatenate([em, em])
    return pos, mass


# --------------------------------------------------------------- assembly
def assemble_mass_model(project: ImportedProject, mesh: WingboxMesh,
                        params: WingboxParams,
                        point_masses: list[PointMass],
                        limit_load_pos: float,
                        limit_load_neg: float | None = None,
                        min_fos: float | None = None,
                        notes: str = "") -> MassModel:
    """Integrate the wing cloud + point masses into mass / CG / inertia."""
    warnings: list[str] = []
    pos, mass = wing_mass_cloud(project, mesh, params)
    wing_kg = float(mass.sum())

    pm_pos = np.array([[p.x, p.y, p.z] for p in point_masses], float) \
        if point_masses else np.zeros((0, 3))
    pm_mass = np.array([p.mass_kg for p in point_masses], float) \
        if point_masses else np.zeros(0)
    pm_kg = float(pm_mass.sum())

    all_pos = np.vstack([pos, pm_pos]) if len(pm_pos) else pos
    all_mass = np.concatenate([mass, pm_mass]) if len(pm_mass) else mass
    total = float(all_mass.sum())
    if total <= 0:
        raise ValueError("Total mass is zero - add the aircraft's masses.")

    cg = (all_mass[:, None] * all_pos).sum(axis=0) / total
    inertia = _point_cloud_inertia(all_pos - cg, all_mass)

    if abs(cg[1]) > 1e-4:
        warnings.append(
            f"CG is {cg[1]*1000:.0f} mm off the centerline - a point mass "
            f"has a non-zero Y. SimVis assumes lateral symmetry.")

    if limit_load_neg is None:
        limit_load_neg = -0.5 * limit_load_pos
    if pm_kg <= 0:
        warnings.append(
            "Only the wing structure is included - add the fuselage, tail, "
            "motor and battery masses, or the CG and inertia will be wrong.")

    # positive-definiteness guard (the same check SimVis runs)
    tensor = np.array([[inertia[0, 0], inertia[0, 1], inertia[0, 2]],
                       [inertia[1, 0], inertia[1, 1], inertia[1, 2]],
                       [inertia[2, 0], inertia[2, 1], inertia[2, 2]]])
    if np.any(np.linalg.eigvalsh(tensor) <= 0):
        warnings.append(
            "Inertia tensor is not positive-definite - masses may be nearly "
            "colinear. Spread them out in x/y/z.")

    return MassModel(
        mass_kg=total, cg_m=cg,
        inertia={"Ixx": inertia[0, 0], "Iyy": inertia[1, 1],
                 "Izz": inertia[2, 2],
                 "Ixz": float(-inertia[0, 2]),     # JSON stores +Sum(m x z)
                 "Ixy": float(-inertia[0, 1]),
                 "Iyz": float(-inertia[1, 2])},
        wing_structural_kg=wing_kg, point_mass_kg=pm_kg,
        limit_load_pos=limit_load_pos, limit_load_neg=limit_load_neg,
        min_factor_of_safety=min_fos, notes=notes, warnings=warnings)


def default_point_masses(project: ImportedProject,
                         target_total_kg: float,
                         wing_structural_kg: float) -> list[PointMass]:
    """Seed a plausible non-wing mass set to hit a target all-up mass.

    Splits the non-wing remainder into motor (nose), battery (ahead of the
    wing), fuselage+tail (behind the wing) and RX/servos - a starting point
    the user then edits.
    """
    surf = project.model.wing
    x_wing = float(getattr(surf, "x_le", 0.3))
    mac = float(project.geometry.mac)
    remainder = max(target_total_kg - wing_structural_kg, 0.0)
    if remainder <= 1e-6:
        return []
    fus_len = float(getattr(project.model, "fuselage_length", 1.0))
    return [
        PointMass("Motor", 0.22 * remainder, x=0.02),
        PointMass("Battery", 0.30 * remainder, x=max(x_wing - 0.06, 0.03)),
        PointMass("Fuselage + tail", 0.36 * remainder,
                  x=x_wing + 0.5 * (fus_len - x_wing)),
        PointMass("RX + servos", 0.12 * remainder, x=x_wing + 0.10),
    ]


def write_simvis_mass(model: MassModel, path: str | Path) -> Path:
    """Write the validated simvis_mass.json (name enforced for the pipeline)."""
    path = Path(path)
    if path.suffix != ".json":
        path = path.with_suffix(".json")
    path.write_text(json.dumps(model.to_schema_dict(), ensure_ascii=False,
                              indent=2), encoding="utf-8")
    return path
