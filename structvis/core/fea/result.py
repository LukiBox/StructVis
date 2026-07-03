"""FEA result container + derived structural metrics."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class FeaResult:
    nodes: np.ndarray               # (N, 3) undeformed coordinates
    elems: np.ndarray               # (M, 4) node ids (0-based)
    disp: np.ndarray                # (N, 3) nodal displacement [m]
    von_mises: np.ndarray           # (N,) nodal Von Mises stress [Pa]
    yield_strength: float           # [Pa] representative (for the stress clim)
    half_span: float = 1.0
    root_y: float = 0.0
    elset_of_elem: np.ndarray | None = None   # (M,) object: component per elem
    node_yield: np.ndarray | None = None       # (N,) per-node yield [Pa]
    node_material: np.ndarray | None = None    # (N,) object: material key per node
    meta: dict = field(default_factory=dict)

    # ---- scalar metrics --------------------------------------------------
    @property
    def disp_mag(self) -> np.ndarray:
        return np.linalg.norm(self.disp, axis=1)

    @property
    def max_von_mises(self) -> float:
        return float(np.max(self.von_mises)) if len(self.von_mises) else 0.0

    @property
    def max_vm_node(self) -> int:
        return int(np.argmax(self.von_mises)) if len(self.von_mises) else -1

    def _node_yield(self) -> np.ndarray:
        if self.node_yield is not None:
            return self.node_yield
        return np.full(len(self.von_mises), self.yield_strength)

    @property
    def min_fos(self) -> float:
        ny = self._node_yield()
        vm = self.von_mises
        m = vm > 1e-3
        if not m.any():
            return float("inf")
        return float(np.min(ny[m] / vm[m]))

    @property
    def critical_node(self) -> int:
        """Node with the lowest local Factor of Safety."""
        ny = self._node_yield()
        with np.errstate(divide="ignore", invalid="ignore"):
            fos = np.where(self.von_mises > 1e-3, ny / self.von_mises, np.inf)
        return int(np.argmin(fos))

    @property
    def fos_field(self) -> np.ndarray:
        ny = self._node_yield()
        with np.errstate(divide="ignore", invalid="ignore"):
            f = np.where(self.von_mises > 1e-3, ny / self.von_mises, 10.0)
        return np.clip(f, 0.0, 10.0)

    @property
    def tip_deflection(self) -> float:
        """Max vertical displacement magnitude at the tip stations [m]."""
        tip_mask = np.abs(self.nodes[:, 1] - self.half_span - self.root_y) \
            < 0.02 * max(self.half_span, 1e-6)
        if not tip_mask.any():
            return float(np.max(np.abs(self.disp[:, 2])))
        return float(np.max(np.abs(self.disp[tip_mask, 2])))

    def tip_twist_deg(self) -> float:
        """
        Tip section twist from the LE/TE vertical displacement difference.
        Positive = leading edge up (nose-up washin).
        """
        y_tip = self.half_span + self.root_y
        tip_mask = np.abs(self.nodes[:, 1] - y_tip) < 0.02 * max(self.half_span, 1e-6)
        if tip_mask.sum() < 2:
            return 0.0
        xs = self.nodes[tip_mask, 0]
        uz = self.disp[tip_mask, 2]
        le, te = int(np.argmin(xs)), int(np.argmax(xs))
        chord = xs[te] - xs[le]
        if abs(chord) < 1e-9:
            return 0.0
        return float(np.degrees(np.arctan2(uz[le] - uz[te], chord)))

    def _component_at_node(self, node: int) -> str:
        if self.elset_of_elem is None:
            return "unknown"
        rows = np.nonzero(np.any(self.elems == node, axis=1))[0]
        names = [self.elset_of_elem[r] for r in rows if self.elset_of_elem[r]]
        return max(set(names), key=names.count) if names else "unknown"

    def where_max_stress(self) -> str:
        """Component name carrying the peak stress (best effort)."""
        return self._component_at_node(self.max_vm_node)

    def where_min_fos(self) -> str:
        """Component at the lowest Factor of Safety (the true weakest point)."""
        return self._component_at_node(self.critical_node)

    def critical_material(self) -> str:
        if self.node_material is not None:
            return str(self.node_material[self.critical_node])
        return str(self.meta.get("material", ""))

    def component_max_vm(self) -> dict[str, float]:
        """Peak Von Mises per element set (uses element corner-node values)."""
        if self.elset_of_elem is None:
            return {}
        out: dict[str, float] = {}
        for e_idx, name in enumerate(self.elset_of_elem):
            if not name:
                continue
            v = float(np.max(self.von_mises[self.elems[e_idx]]))
            if v > out.get(name, 0.0):
                out[name] = v
        return out

    def component_min_fos(self) -> dict[str, float]:
        """Minimum Factor of Safety per element set (uses local node yields)."""
        if self.elset_of_elem is None:
            return {}
        ny = self._node_yield()
        out: dict[str, float] = {}
        for e_idx, name in enumerate(self.elset_of_elem):
            if not name:
                continue
            nodes = self.elems[e_idx]
            vm = self.von_mises[nodes]
            m = vm > 1e-3
            if not m.any():
                continue
            f = float(np.min(ny[nodes][m] / vm[m]))
            if f < out.get(name, float("inf")):
                out[name] = f
        return out

    def summary(self) -> dict:
        cn = self.critical_node
        crit_yield = float(self._node_yield()[cn])
        return {
            "max_von_mises_MPa": round(self.max_von_mises / 1e6, 2),
            "yield_MPa": round(crit_yield / 1e6, 1),
            "min_FoS": round(self.min_fos, 3),
            "tip_deflection_mm": round(self.tip_deflection * 1000, 2),
            "tip_deflection_pct_span": round(
                100 * self.tip_deflection / max(self.half_span, 1e-9), 2),
            "tip_twist_deg": round(self.tip_twist_deg(), 3),
            "critical_component": self.where_min_fos(),
            "critical_stress_MPa": round(float(self.von_mises[cn]) / 1e6, 2),
        }


@dataclass
class BucklingResult:
    """Linear buckling eigenvalue extraction result."""
    factors: np.ndarray             # eigenvalues = load multipliers to buckle
    nodes: np.ndarray               # undeformed coordinates
    elems: np.ndarray               # (M,4) node ids
    mode1: np.ndarray | None = None  # (N,3) first mode shape (normalized)
    half_span: float = 1.0
    elset_of_elem: np.ndarray | None = None
    meta: dict = field(default_factory=dict)

    @property
    def critical_factor(self) -> float:
        """Lowest positive buckling factor (load multiplier at first buckling)."""
        pos = self.factors[self.factors > 1e-6] if len(self.factors) else []
        return float(np.min(pos)) if len(pos) else float("inf")

    def summary(self) -> dict:
        cf = self.critical_factor
        return {
            "critical_buckling_factor": round(cf, 3) if np.isfinite(cf) else None,
            "buckles_below_limit": bool(cf < 1.0),
            "n_modes": int(len(self.factors)),
            "factors": [round(float(f), 3) for f in self.factors[:6]],
        }
