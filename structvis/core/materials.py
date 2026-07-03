"""Aerospace materials library (isotropic idealizations)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Material:
    key: str
    name: str
    E: float            # Young's modulus [Pa] (E1 for orthotropic)
    nu: float           # Poisson's ratio (nu12 for orthotropic)
    rho: float          # density [kg/m^3]
    yield_strength: float  # [Pa] (0.2% proof or equivalent allowable)
    note: str = ""
    # --- orthotropic extension (woven / UD laminate idealization) ---
    ortho: bool = False
    E2: float = 0.0
    E3: float = 0.0
    G12: float = 0.0
    G13: float = 0.0
    G23: float = 0.0
    nu13: float = 0.0
    nu23: float = 0.0

    def ortho_constants(self):
        """9 engineering constants: E1,E2,E3,nu12,nu13,nu23,G12,G13,G23."""
        return (self.E, self.E2, self.E3, self.nu, self.nu13, self.nu23,
                self.G12, self.G13, self.G23)


def make_orthotropic(key, name, E1, E2, G12, nu12, rho, yield_strength,
                     note="", E3=8.0e9, G13=None, G23=None, nu13=0.30,
                     nu23=0.35) -> Material:
    """
    Build an orthotropic material from the primary woven-fabric constants
    (E11, E22, G12, nu12). Transverse/through-thickness values default to
    matrix-dominated estimates - enough to capture the low interlaminar shear
    and transverse stiffness that make composites behave unlike isotropic metal.
    """
    G13 = G13 if G13 is not None else 0.8 * G12
    G23 = G23 if G23 is not None else 0.6 * G12
    return Material(key, name, E1, nu12, rho, yield_strength, note, ortho=True,
                    E2=E2, E3=E3, G12=G12, G13=G13, G23=G23,
                    nu13=nu13, nu23=nu23)


# Composite / wood / foam entries are isotropic idealizations - a common
# preliminary sizing simplification; real anisotropic materials (laminates,
# grained wood, printed parts) need direction-dependent analysis.
MATERIALS: list[Material] = [
    # --- engineering / structural ---
    Material("al7075", "Aluminum 7075-T6", 71.7e9, 0.33, 2810, 503e6),
    Material("al6061", "Aluminum 6061-T6", 68.9e9, 0.33, 2700, 276e6),
    Material("ti64", "Titanium Ti-6Al-4V", 113.8e9, 0.342, 4430, 880e6),
    Material("steel4130", "Steel 4130 (normalized)", 205e9, 0.29, 7850, 460e6),
    Material("cfrp_qi", "Carbon fiber (quasi-isotropic eq.)", 45e9, 0.30, 1600,
             350e6, "laminate equivalent; verify with ply analysis"),
    Material("fiberglass", "Fiberglass (E-glass laminate eq.)", 23e9, 0.28, 1900,
             250e6, "laminate equivalent; orthotropy ignored"),
    # --- model / hobby building ---
    Material("plywood", "Birch plywood (aircraft grade)", 12.5e9, 0.30, 680,
             40e6, "orthotropy ignored"),
    Material("balsa", "Balsa wood (light)", 3.2e9, 0.30, 160, 15e6,
             "grain orthotropy ignored (along-grain values)"),
    Material("pla", "PLA (3D printed)", 3.5e9, 0.36, 1240, 45e6,
             "printed parts are anisotropic/weaker than bulk"),
    Material("cardstock", "Card stock / cardboard", 2.0e9, 0.30, 700, 10e6,
             "in-plane isotropic idealization"),
    Material("paper", "Paper (copy sheet)", 3.0e9, 0.20, 800, 20e6,
             "in-plane isotropic idealization"),
    Material("eps_foam", "Foam (expanded polystyrene)", 8.0e6, 0.10, 30, 0.25e6,
             "closed-cell foam; buckling not modelled"),
    # --- orthotropic composites (ELASTIC, TYPE=ENGINEERING CONSTANTS) ---
    make_orthotropic("cfrp_woven", "Carbon fiber (woven fabric)",
                     E1=62e9, E2=59e9, G12=4.2e9, nu12=0.05, rho=1550,
                     yield_strength=550e6,
                     note="woven 0/90; single allowable - not ply failure"),
    make_orthotropic("cfrp_ud", "Carbon fiber (unidirectional)",
                     E1=135e9, E2=9e9, G12=5e9, nu12=0.28, rho=1600,
                     yield_strength=1200e6, E3=9e9, nu23=0.40,
                     note="strong along fibres, weak across; allowable is "
                          "fibre-direction only - transverse fails far sooner"),
    make_orthotropic("glass_woven", "Fiberglass (woven cloth)",
                     E1=25e9, E2=24e9, G12=4e9, nu12=0.12, rho=1900,
                     yield_strength=350e6, E3=8e9,
                     note="woven E-glass; single allowable"),
]

_BY_KEY = {m.key: m for m in MATERIALS}


def get(key: str) -> Material:
    return _BY_KEY.get(key, MATERIALS[0])
