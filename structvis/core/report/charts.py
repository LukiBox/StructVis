"""Matplotlib charts for the PDF report (no 3D / GL needed)."""
from __future__ import annotations

import io

import numpy as np

_ACCENT = "#2563eb"
_GREEN = "#059669"
_RED = "#dc2626"
_MUTED = "#6b7280"


def _fig_png(fig) -> bytes:
    import matplotlib.pyplot as plt
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight",
                facecolor="white")
    plt.close(fig)
    return buf.getvalue()


def _style(ax):
    ax.set_facecolor("white")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.grid(True, alpha=0.25)
    ax.tick_params(colors=_MUTED, labelsize=8)
    ax.xaxis.label.set_color("#1f2937")
    ax.yaxis.label.set_color("#1f2937")


def load_distribution_png(geometry, strip_loads) -> bytes:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    y = strip_loads.y_stations
    total = strip_loads.Fz_front + strip_loads.Fz_rear
    fig, ax = plt.subplots(figsize=(5.4, 3.0))
    ax.bar(y, total, width=(y[-1] / max(len(y), 1)) * 0.8,
           color=_ACCENT, alpha=0.85)
    ax.set_xlabel("spanwise station y [m]")
    ax.set_ylabel("applied vertical load [N]")
    ax.set_title("Spanwise load (Schrenk, mapped to stations)",
                 fontsize=9.5, color="#1f2937")
    _style(ax)
    return _fig_png(fig)


def component_stress_png(result, yield_strength: float) -> bytes:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    comp = result.component_max_vm()
    if not comp:
        comp = {"all": result.max_von_mises}
    names = list(comp.keys())
    vals = np.array([comp[n] / 1e6 for n in names])
    colors = [_RED if v > yield_strength / 1e6 else
              (_GREEN if v < 0.5 * yield_strength / 1e6 else _ACCENT)
              for v in vals]
    fig, ax = plt.subplots(figsize=(5.4, 3.0))
    ax.barh(names, vals, color=colors, alpha=0.9)
    ax.axvline(yield_strength / 1e6, color=_RED, ls="--", lw=1.2,
               label=f"yield {yield_strength/1e6:.0f} MPa")
    ax.set_xlabel("peak Von Mises stress [MPa]")
    ax.set_title("Stress by component", fontsize=9.5, color="#1f2937")
    ax.legend(fontsize=7.5, frameon=False)
    _style(ax)
    return _fig_png(fig)
