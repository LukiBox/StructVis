"""
Rule-based plain-language structural summary - the "no AI needed" explanation.

Turns a FeaResult + design inputs into: (a) Red/Yellow/Green verdicts for the
key metrics, and (b) a short, readable assessment a hobbyist can act on. If the
optional Ollama review is used it *adds* nuance, but this module always gives a
usable explanation on its own.
"""
from __future__ import annotations

from dataclasses import dataclass

from .. import materials

GREEN, YELLOW, RED = "green", "yellow", "red"
_LABEL = {GREEN: "OK", YELLOW: "CAUTION", RED: "ACTION"}

# friendly component names for the summary text
_FRIENDLY = {
    "SKIN_UP": "upper skin", "SKIN_LO": "lower skin",
    "CAP_UP": "upper spar caps", "CAP_LO": "lower spar caps",
    "STR_UP": "upper stringers", "STR_LO": "lower stringers",
    "SPAR_F": "front spar web", "SPAR_R": "rear spar web", "RIBS": "ribs",
}


@dataclass
class Verdict:
    name: str
    value: str
    level: str          # GREEN | YELLOW | RED
    comment: str

    @property
    def tag(self) -> str:
        return _LABEL[self.level]


def _fos_verdict(min_fos: float, target: float) -> Verdict:
    val = f"{min_fos:.2f}" if min_fos < 100 else ">100"
    if min_fos < 1.0:
        return Verdict("Minimum Factor of Safety", val, RED,
                       "The structure exceeds the material's yield strength - "
                       "it would permanently deform or break. Add material.")
    if min_fos < target:
        return Verdict("Minimum Factor of Safety", val, YELLOW,
                       f"Below the target of {target:.1f}. It survives this "
                       "load but with less margin than you asked for.")
    if min_fos > 2.5 * target:
        return Verdict("Minimum Factor of Safety", val, YELLOW,
                       "Far above target - the wing is over-built and carrying "
                       "weight it does not need.")
    return Verdict("Minimum Factor of Safety", val, GREEN,
                   f"Meets the target of {target:.1f} with sensible margin.")


def _deflection_verdict(pct_span: float) -> Verdict:
    val = f"{pct_span:.1f}% of span"
    if pct_span > 15:
        return Verdict("Tip deflection", val, RED,
                       "Very flexible - large bending may hurt handling and "
                       "risks aeroelastic problems.")
    if pct_span > 7:
        return Verdict("Tip deflection", val, YELLOW,
                       "Noticeably flexible; acceptable for many models but "
                       "stiffer is better for precision.")
    return Verdict("Tip deflection", val, GREEN,
                   "Stiff enough - small tip bending under the design load.")


def _twist_verdict(twist_deg: float) -> Verdict:
    val = f"{twist_deg:+.2f}°"
    a = abs(twist_deg)
    if a > 3:
        return Verdict("Tip twist", val, RED,
                       "Large aeroelastic twist - can change the lift "
                       "distribution and, if wash-in, risk divergence.")
    if a > 1.2:
        return Verdict("Tip twist", val, YELLOW,
                       "Some aeroelastic twist; keep an eye on it at higher "
                       "speeds.")
    return Verdict("Tip twist", val, GREEN, "Torsionally stiff - little twist.")


def verdicts(result, load_case) -> list[Verdict]:
    s = result.summary()
    return [
        _fos_verdict(result.min_fos, load_case.target_fos),
        _deflection_verdict(s["tip_deflection_pct_span"]),
        _twist_verdict(s["tip_twist_deg"]),
    ]


def _friendly(name: str) -> str:
    return _FRIENDLY.get(name, name)


def plain_language(result, params, load_case, design=None,
                   total_mass_kg: float | None = None) -> str:
    """Return a short multi-paragraph assessment (plain text, blank-line sep)."""
    s = result.summary()
    mat = materials.get(params.material)
    crit_mat = materials.get(result.critical_material() or params.material)
    two_mats = params.effective_support_material != params.material
    comp = result.component_max_vm()
    target = load_case.target_fos
    paras: list[str] = []

    # 1. overall verdict
    if result.min_fos < 1.0:
        paras.append(
            f"This design is not safe at the chosen load case. At the "
            f"{_friendly(s['critical_component'])} the stress of "
            f"{s['critical_stress_MPa']:.0f} MPa exceeds the {crit_mat.name} "
            f"yield strength of {s['yield_MPa']:.0f} MPa, so the minimum Factor "
            f"of Safety is {result.min_fos:.2f} - below 1.0. Increase thickness "
            f"there (or use a stronger material) before flying.")
    elif result.min_fos < target:
        paras.append(
            f"The wing holds together at {load_case.load_factor:.0f} g, but its "
            f"minimum Factor of Safety of {result.min_fos:.2f} is under your "
            f"target of {target:.1f}. The most stressed part is the "
            f"{_friendly(s['critical_component'])} at "
            f"{s['max_von_mises_MPa']:.0f} MPa. A modest thickness increase "
            f"there will restore the margin.")
    elif result.min_fos > 2.5 * target:
        paras.append(
            f"The wing is safe but clearly over-built: the minimum Factor of "
            f"Safety is {result.min_fos:.2f} against a target of {target:.1f}. "
            f"There is room to remove material and save weight while staying "
            f"above target. Use Auto-size to bring the FoS down to {target:.1f}.")
    else:
        paras.append(
            f"The wing is well sized for this load case. The minimum Factor of "
            f"Safety is {result.min_fos:.2f}, at or above your target of "
            f"{target:.1f}, with the peak stress of {s['max_von_mises_MPa']:.0f} "
            f"MPa at the {_friendly(s['critical_component'])} - the expected "
            f"place for a clamped wing root.")

    # 2. stiffness
    paras.append(
        f"Under the design load the tip deflects {s['tip_deflection_mm']:.0f} mm "
        f"({s['tip_deflection_pct_span']:.1f}% of the half-span) and twists "
        f"{s['tip_twist_deg']:+.2f}°. "
        + ("That is stiff and predictable."
           if s['tip_deflection_pct_span'] < 7 and abs(s['tip_twist_deg']) < 1.2
           else "Watch this if you fly fast or aerobatically - flexibility and "
                "twist change the real lift distribution."))

    # 3. load balance across components -> weight-saving hint (per-material FoS)
    fos_map = result.component_min_fos()
    if fos_map:
        hi = min(fos_map, key=fos_map.get)      # lowest FoS = works hardest
        lo = max(fos_map, key=fos_map.get)      # highest FoS = least loaded
        hi_fos, lo_fos = fos_map[hi], fos_map[lo]
        if hi != lo and lo_fos > 3 * max(hi_fos, 0.1):
            paras.append(
                f"The load is uneven: the {_friendly(hi)} works hardest "
                f"(FoS {hi_fos:.1f}) while the {_friendly(lo)} is barely loaded "
                f"(FoS {lo_fos:.1f}). You can thin the {_friendly(lo)} to save "
                f"weight and, if needed, reinforce the {_friendly(hi)}.")

    # 4. mass
    if total_mass_kg is not None:
        if two_mats:
            mat_desc = (f"{mat.name} skins with "
                        f"{materials.get(params.effective_support_material).name} "
                        f"spars/ribs")
        else:
            mat_desc = mat.name
        paras.append(
            f"The estimated wing structural mass is {total_mass_kg*1000:.0f} g "
            f"({mat_desc}). Lighter materials or thinner gauges reduce this, as "
            f"long as the Factor of Safety stays above {target:.1f}.")
    return "\n\n".join(paras)
