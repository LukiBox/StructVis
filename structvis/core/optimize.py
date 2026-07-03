"""
Auto-sizing: scale gauge thicknesses until the minimum Factor of Safety hits a
target (default 1.5). Because a thickness change only rewrites *SHELL SECTION
cards, the mesh is fixed and every iteration is a fast re-solve.

The evaluator is injected (eval_fos: factor -> min_fos) so the loop is unit
testable without CalculiX. For thin shells under fixed load, stress ~ 1/t, so
FoS ~ t and a secant method converges in a handful of iterations.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Callable

# which gauge drives which element sets (for Fully Stressed Design)
GAUGE_SETS = {
    "skin_t": ("SKIN_UP", "SKIN_LO"),
    "web_t": ("SPAR_F", "SPAR_R"),
    "cap_t": ("CAP_UP", "CAP_LO"),
    "rib_t": ("RIBS",),
    "stringer_t": ("STR_UP", "STR_LO"),
}


@dataclass
class OptIteration:
    step: int
    factor: float
    min_fos: float


@dataclass
class OptResult:
    factor: float
    min_fos: float
    converged: bool
    history: list[OptIteration] = field(default_factory=list)
    message: str = ""


def autosize(eval_fos: Callable[[float], float], target_fos: float = 1.5,
             factor0: float = 1.0, tol: float = 0.02, max_iter: int = 12,
             f_lo: float = 0.05, f_hi: float = 20.0,
             progress: Callable[[OptIteration], None] | None = None
             ) -> OptResult:
    """
    Find a thickness scale factor so min_fos == target_fos (within tol).

    Uses the secant method on g(f) = fos(f) - target, with a robust fallback
    to bisection whenever a bracket [under-designed, over-designed] is known.
    """
    history: list[OptIteration] = []

    def evaluate(f: float, step: int) -> float:
        f = float(min(max(f, f_lo), f_hi))
        fos = float(eval_fos(f))
        it = OptIteration(step, f, fos)
        history.append(it)
        if progress:
            progress(it)
        return fos

    f0 = factor0
    fos0 = evaluate(f0, 0)
    if abs(fos0 - target_fos) <= tol * target_fos:
        return OptResult(f0, fos0, True, history, "Already at target FoS.")

    # second point: scale proportionally toward the target (FoS ~ factor)
    f1 = f0 * (target_fos / max(fos0, 1e-6))
    fos1 = evaluate(f1, 1)

    lo = hi = None            # bracket where fos-target changes sign
    for pair in ((f0, fos0), (f1, fos1)):
        if pair[1] < target_fos:
            lo = pair
        else:
            hi = pair

    for step in range(2, max_iter):
        if abs(fos1 - target_fos) <= tol * target_fos:
            return OptResult(f1, fos1, True, history,
                             f"Converged: min FoS = {fos1:.3f}.")
        denom = (fos1 - fos0)
        if abs(denom) > 1e-9:
            f2 = f1 - (fos1 - target_fos) * (f1 - f0) / denom
        else:
            f2 = 0.5 * (f0 + f1)
        # keep inside the bracket if we have one (guards against overshoot)
        if lo and hi and not (min(lo[0], hi[0]) < f2 < max(lo[0], hi[0])):
            f2 = 0.5 * (lo[0] + hi[0])

        fos2 = evaluate(f2, step)
        if fos2 < target_fos:
            lo = (f2, fos2)
        else:
            hi = (f2, fos2)
        f0, fos0, f1, fos1 = f1, fos1, f2, fos2

    converged = abs(fos1 - target_fos) <= tol * target_fos
    return OptResult(f1, fos1, converged, history,
                     "Converged." if converged else
                     "Stopped at iteration limit (result is usable).")


# ---------------------------------------------------------------------------
# Fully Stressed Design (per-gauge generative sizing)
# ---------------------------------------------------------------------------

@dataclass
class FsdIteration:
    step: int
    gauges_mm: dict          # gauge -> thickness [mm]
    min_fos: float
    max_stress_MPa: float


@dataclass
class FsdResult:
    params: object           # optimized WingboxParams
    min_fos: float
    converged: bool
    history: list[FsdIteration] = field(default_factory=list)
    message: str = ""


def fully_stressed_design(params, evaluate: Callable, target_fos: float,
                          gauge_yield: dict, t_min: float = 1e-4,
                          t_max: float = 0.02, max_iter: int = 10,
                          relax: float = 0.7, tol: float = 0.03,
                          progress: Callable | None = None) -> FsdResult:
    """
    Size each gauge so it is 'fully stressed' at the target Factor of Safety.

    For shell membrane stress ~ 1/t, the fixed-point update
        t_new = t_old * (sigma_actual / sigma_target) ** relax
    with sigma_target = yield / target_fos drives every gauge toward the same
    margin: heavily loaded members thicken, unloaded ones (e.g. the rear spar)
    thin out - the generative 'fully stressed' result. `relax` (<1) damps
    oscillation in the redundant structure. `evaluate(params)` must return an
    object exposing .component_max_vm() (set -> peak stress [Pa]) and .min_fos.
    """
    history: list[FsdIteration] = []
    cur = params
    message = "Stopped at iteration limit."
    for step in range(max_iter):
        res = evaluate(cur)
        comp = res.component_max_vm()
        it = FsdIteration(
            step, {g: getattr(cur, g) * 1000 for g in GAUGE_SETS},
            float(res.min_fos),
            round(max(comp.values(), default=0.0) / 1e6, 2))
        history.append(it)
        if progress:
            progress(it)

        updates = {}
        max_change = 0.0
        for g, sets in GAUGE_SETS.items():
            smax = max((comp.get(s, 0.0) for s in sets), default=0.0)
            t_old = getattr(cur, g)
            if smax <= 0:                     # unloaded -> drift toward minimum
                t_new = max(t_old * 0.7, t_min)
            else:
                sigma_target = gauge_yield.get(g, 1e9) / max(target_fos, 1e-6)
                ratio = smax / max(sigma_target, 1e-6)
                t_new = t_old * (ratio ** relax)
            t_new = float(min(max(t_new, t_min), t_max))
            updates[g] = t_new
            max_change = max(max_change, abs(t_new - t_old) / max(t_old, 1e-9))
        cur = replace(cur, **updates)

        if max_change < tol:
            message = f"Converged in {step + 1} iterations."
            break

    final = evaluate(cur)
    # final uniform correction: keep the generative distribution but scale all
    # gauges so the global minimum FoS lands on the target (FoS ~ thickness)
    if final.min_fos > 0 and abs(final.min_fos - target_fos) > tol * target_fos:
        corr = target_fos / final.min_fos
        cur = cur.scaled(corr)
        final = evaluate(cur)
        history.append(FsdIteration(
            len(history), {g: getattr(cur, g) * 1000 for g in GAUGE_SETS},
            float(final.min_fos),
            round(max(final.component_max_vm().values(), default=0.0) / 1e6, 2)))
        if progress:
            progress(history[-1])

    converged = abs(final.min_fos - target_fos) <= 0.06 * target_fos
    if converged and "Converged" not in message:
        message = "Converged (with final correction)."
    return FsdResult(params=cur, min_fos=float(final.min_fos),
                     converged=converged, history=history, message=message)
