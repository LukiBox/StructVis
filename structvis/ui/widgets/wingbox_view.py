"""
PyVista viewer for the wingbox: structural preview and FEA result heatmaps.

Two modes on one QtInteractor:
  * show_structure(mesh, params) - component-colored solid preview; individual
    components can be hidden ("look inside" the box).
  * show_result(result, field, warp, show_undeformed) - Von Mises / FoS /
    displacement heatmap, blue = safe -> red = at yield, with deflection
    exaggeration via warp_by_vector.
"""
from __future__ import annotations

import numpy as np

from .. import theme

# component base colors for the structural preview
_COMPONENT_COLORS = {
    "SKIN_UP": "#bcd0ea", "SKIN_LO": "#a9c1e0",
    "CAP_UP": "#6b7280", "CAP_LO": "#6b7280",
    "STR_UP": "#f59e0b", "STR_LO": "#f59e0b",
    "SPAR_F": "#2563eb", "SPAR_R": "#1d4ed8",
    "RIBS": "#10b981",
}
_EDGE = "#94a3b8"


def _quad_faces(elems: np.ndarray) -> np.ndarray:
    """WingboxMesh quads -> VTK faces array [4,a,b,c,d, 4,...]."""
    n = len(elems)
    out = np.empty((n, 5), dtype=np.int64)
    out[:, 0] = 4
    out[:, 1:] = elems
    return out.ravel()


class WingboxView:
    def __init__(self, parent=None, off_screen=False):
        from pyvistaqt import QtInteractor
        self.plotter = QtInteractor(parent, off_screen=off_screen)
        self.plotter.set_background(theme.view_bg())
        self.widget = self.plotter
        self._mode = None
        self._mesh = None
        self._result = None
        self._hidden: set[str] = set()
        self._field = "von_mises"
        self._warp = 1.0
        self._show_undeformed = True
        self._clip = False
        self._buckling = None

    # ---------------------------------------------------------------- helpers
    def _full_poly(self, nodes, elems):
        import pyvista as pv
        return pv.PolyData(np.asarray(nodes, float), _quad_faces(np.asarray(elems)))

    def _component_poly(self, mesh, name):
        idx = mesh.elsets[name]
        return self._full_poly(mesh.nodes, mesh.elems[idx])

    # ------------------------------------------------------------- structure
    def show_structure(self, mesh, params, hidden=None):
        self._mode = "structure"
        self._mesh = mesh
        if hidden is not None:
            self._hidden = set(hidden)
        self._render_structure()

    def set_hidden(self, hidden):
        self._hidden = set(hidden)
        if self._mode == "structure":
            self._render_structure()
        elif self._mode == "result":
            self._render_result()

    def _render_structure(self):
        p = self.plotter
        p.clear(); p.set_background(theme.view_bg())
        mesh = self._mesh
        if mesh is None:
            p.add_text("No structure", position="upper_left", color=theme.plot_fg())
            return
        for name in mesh.elsets:
            if name in self._hidden:
                continue
            poly = self._component_poly(mesh, name)
            p.add_mesh(poly, color=_COMPONENT_COLORS.get(name, "#c9d4e3"),
                       show_edges=True, edge_color=_EDGE, line_width=0.5,
                       smooth_shading=False, name=name)
        p.add_axes(color=theme.plot_fg())
        self._reset_cam()

    # --------------------------------------------------------------- results
    def show_result(self, result, field="von_mises", warp=1.0,
                    show_undeformed=True, hidden=None):
        self._mode = "result"
        self._result = result
        self._field = field
        self._warp = warp
        self._show_undeformed = show_undeformed
        if hidden is not None:
            self._hidden = set(hidden)
        self._render_result()

    def set_field(self, field):
        self._field = field
        if field == "buckling" and self._buckling is not None:
            self._render_buckling()
        elif self._mode in ("result", "buckling"):
            self._render_result()

    def set_clip(self, on):
        self._clip = bool(on)
        if self._mode == "result":
            self._render_result()
        elif self._mode == "buckling":
            self._render_buckling()

    def _add_mesh(self, warped, **kw):
        """Add a mesh, using an interactive clip-plane widget when enabled."""
        if self._clip:
            try:
                self.plotter.add_mesh_clip_plane(warped, **kw)
                return
            except Exception:  # noqa: BLE001
                pass
        self.plotter.add_mesh(warped, **kw)

    # --------------------------------------------------------------- buckling
    def show_buckling(self, buckling, warp=30.0, hidden=None):
        self._mode = "buckling"
        self._buckling = buckling
        self._field = "buckling"
        self._warp = warp
        if hidden is not None:
            self._hidden = set(hidden)
        self._render_buckling()

    def _render_buckling(self):
        p = self.plotter
        p.clear(); p.set_background(theme.view_bg())
        b = self._buckling
        if b is None or b.mode1 is None:
            p.add_text("No buckling mode", position="upper_left", color=theme.plot_fg())
            return
        elems = b.elems
        if self._hidden and b.elset_of_elem is not None:
            keep = np.array([e not in self._hidden for e in b.elset_of_elem])
            elems = b.elems[keep]
        mode = b.mode1
        mag = np.linalg.norm(mode, axis=1)
        mmax = max(float(mag.max()), 1e-12)
        # normalize mode and scale to a visible fraction of the model size
        char = float(np.linalg.norm(b.nodes.max(0) - b.nodes.min(0)))
        # visible even at low slider values (mode shapes have arbitrary scale)
        amp = (0.05 + 0.15 * self._warp / 100.0) * char / mmax

        ghost = self._full_poly(b.nodes, elems)
        p.add_mesh(ghost, color="#d1d5db", opacity=0.2, name="undeformed")
        poly = self._full_poly(b.nodes, elems)
        poly.point_data["mode"] = mag
        poly.point_data["_warp"] = mode
        warped = poly.warp_by_vector("_warp", factor=amp)
        self._add_mesh(warped, scalars="mode", cmap="plasma",
                       smooth_shading=True, name="buckle",
                       scalar_bar_args={"title": f"Mode 1 (x{b.critical_factor:.1f})",
                                        "color": theme.plot_fg(), "n_labels": 4})
        p.add_axes(color=theme.plot_fg())
        self._reset_cam()

    def set_warp(self, warp):
        self._warp = float(warp)
        if self._mode == "result":
            self._render_result()
        elif self._mode == "buckling":
            self._render_buckling()

    def set_show_undeformed(self, on):
        self._show_undeformed = bool(on)
        if self._mode == "result":
            self._render_result()

    def _field_config(self, result):
        if self._field == "von_mises":
            return (result.von_mises / 1e6, "Von Mises [MPa]",
                    (0.0, result.yield_strength / 1e6), "coolwarm")
        if self._field == "fos":
            # clamp; reverse colormap so red = low FoS (danger)
            return (np.clip(result.fos_field, 0, 3), "Factor of Safety",
                    (result.min_fos if np.isfinite(result.min_fos) else 0.5, 3.0),
                    "coolwarm")
        return (result.disp_mag * 1000, "Displacement [mm]",
                None, "viridis")

    def _visible_elems(self, result):
        if not self._hidden or result.elset_of_elem is None:
            return result.elems
        keep = np.array([e not in self._hidden for e in result.elset_of_elem])
        return result.elems[keep]

    def _render_result(self):
        import pyvista as pv
        p = self.plotter
        p.clear(); p.set_background(theme.view_bg())
        result = self._result
        if result is None:
            p.add_text("No results", position="upper_left", color=theme.plot_fg())
            return

        scal, title, clim, cmap = self._field_config(result)
        elems = self._visible_elems(result)
        poly = self._full_poly(result.nodes, elems)
        poly.point_data[title] = scal
        poly.point_data["_warp"] = result.disp

        if self._show_undeformed:
            ghost = self._full_poly(result.nodes, elems)
            p.add_mesh(ghost, color="#d1d5db", opacity=0.15,
                       show_edges=False, name="undeformed")

        warped = poly.warp_by_vector("_warp", factor=self._warp)
        kw = dict(scalars=title, cmap=cmap, smooth_shading=True,
                  show_edges=False, name="result",
                  scalar_bar_args={"title": title, "color": theme.plot_fg(),
                                   "n_labels": 5})
        if clim is not None:
            kw["clim"] = clim
        self._add_mesh(warped, **kw)
        p.add_axes(color=theme.plot_fg())
        self._reset_cam()

    def apply_theme(self):
        """Re-render the current view with the active theme's colors."""
        self.plotter.set_background(theme.view_bg())
        if self._mode == "structure":
            self._render_structure()
        elif self._mode == "result":
            self._render_result()
        elif self._mode == "buckling":
            self._render_buckling()

    # ------------------------------------------------------------------ util
    def _reset_cam(self):
        try:
            self.plotter.reset_camera()
            self.plotter.view_isometric()
        except Exception:  # noqa: BLE001
            pass

    def screenshot(self, path):
        self.plotter.screenshot(path)

    def screenshot_bytes(self):
        """Return the current view as PNG bytes (for the PDF thumbnail)."""
        import tempfile
        import os
        fd, path = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        try:
            self.plotter.screenshot(path)
            with open(path, "rb") as f:
                return f.read()
        except Exception:  # noqa: BLE001
            return None
        finally:
            try:
                os.remove(path)
            except OSError:
                pass

    def close(self):
        try:
            self.plotter.close()
        except Exception:  # noqa: BLE001
            pass
