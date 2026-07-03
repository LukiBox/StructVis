"""
Parametric wingbox definition - the sliders live here.

All dimensions in SI (meters); the UI converts to mm. Thicknesses map to
CalculiX *SHELL SECTION cards per element set, so changing a thickness never
requires remeshing (key to the fast auto-sizing loop).
"""
from __future__ import annotations

from dataclasses import dataclass, replace, asdict

# Element sets that make up the internal "supports" (the load-bearing skeleton:
# spar webs, spar caps and ribs). Everything else - the skins and their
# stringers - is the "wing" surface. Used to assign a separate support material.
SUPPORT_SETS = ("SPAR_F", "SPAR_R", "CAP_UP", "CAP_LO", "RIBS")
SKIN_SETS = ("SKIN_UP", "SKIN_LO", "STR_UP", "STR_LO")


@dataclass
class WingboxParams:
    front_spar: float = 0.20        # chord fraction
    rear_spar: float = 0.70
    n_ribs: int = 6                 # including root and tip ribs
    skin_t: float = 0.0015          # [m]
    web_t: float = 0.0020           # spar web thickness
    cap_t: float = 0.0030           # spar cap (skin strip over spar) thickness
    rib_t: float = 0.0015
    n_stringers: int = 2            # per skin panel (upper & lower)
    stringer_t: float = 0.0025      # thickened-strip idealization
    material: str = "al7075"        # skin / "wing" material
    support_material: str = ""      # spars/caps/ribs; "" = same as `material`

    # element-set -> thickness [m]
    def thickness_map(self) -> dict[str, float]:
        return {
            "SKIN_UP": self.skin_t, "SKIN_LO": self.skin_t,
            "CAP_UP": self.cap_t, "CAP_LO": self.cap_t,
            "STR_UP": self.stringer_t, "STR_LO": self.stringer_t,
            "SPAR_F": self.web_t, "SPAR_R": self.web_t,
            "RIBS": self.rib_t,
        }

    @property
    def effective_support_material(self) -> str:
        return self.support_material or self.material

    # element-set -> material key
    def material_map(self) -> dict[str, str]:
        supp = self.effective_support_material
        m = {name: self.material for name in SKIN_SETS}
        m.update({name: supp for name in SUPPORT_SETS})
        return m

    def materials_used(self) -> list[str]:
        """Distinct material keys, skin first."""
        out = [self.material]
        if self.effective_support_material != self.material:
            out.append(self.effective_support_material)
        return out

    _SCALABLE = ("skin_t", "web_t", "cap_t", "rib_t", "stringer_t")

    def scaled(self, factor: float) -> "WingboxParams":
        """All gauge thicknesses scaled - used by the auto-sizing loop."""
        return replace(self, **{k: getattr(self, k) * factor
                                for k in self._SCALABLE})

    def validated(self) -> list[str]:
        """Return a list of problems (empty = OK)."""
        issues = []
        if not 0.05 <= self.front_spar < self.rear_spar <= 0.95:
            issues.append("Spar positions must satisfy 5% <= front < rear <= 95%.")
        if self.n_ribs < 2:
            issues.append("At least 2 ribs (root and tip) are required.")
        for k in self._SCALABLE:
            if getattr(self, k) <= 0:
                issues.append(f"{k} must be positive.")
        return issues

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "WingboxParams":
        return cls(**{k: d[k] for k in d if k in cls.__dataclass_fields__})
