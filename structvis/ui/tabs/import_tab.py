"""Tab 1: import a .flovis file, set the load case, preview the load distribution."""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QGroupBox,
                               QPushButton, QLabel, QFileDialog, QMessageBox,
                               QCheckBox, QScrollArea, QTableWidget,
                               QTableWidgetItem, QHeaderView, QAbstractItemView)
import pyqtgraph as pg

from ...core.i18n import t
from ...core.flovis_import import load_flovis
from ...core.loads import (LoadCase, PointMass, resolve_design_point,
                           schrenk_lift_per_span, strip_loads, G)
from .. import theme
from ..widgets.param_slider import FloatSlider


class ImportTab(QWidget):
    def __init__(self, app_state):
        super().__init__()
        self.state = app_state
        self._loading = False
        self._emitting = False
        self._build()
        # refresh net-load / bending-moment once a structure (mesh) exists
        self.state.params_changed.connect(self._on_external_change)

    def _build(self):
        root = QHBoxLayout(self)

        panel = QWidget()
        left = QVBoxLayout(panel)

        box = QGroupBox(t("Aerodynamic source"))
        bv = QVBoxLayout(box)
        b_open = QPushButton(t("Import .flovis file..."))
        b_open.clicked.connect(self.open_dialog)
        bv.addWidget(b_open)
        self.info = QLabel(t("No file loaded."))
        self.info.setObjectName("hint"); self.info.setWordWrap(True)
        bv.addWidget(self.info)
        left.addWidget(box)

        lc = QGroupBox(t("Load case"))
        lcf = QVBoxLayout(lc)
        self.s_n = FloatSlider(t("Load factor n"), 1.0, 12.0,
                               self.state.load_case.load_factor, step=0.5,
                               decimals=1, suffix=" g")
        self.s_v = FloatSlider(t("Velocity"), 5.0, 80.0,
                               self.state.load_case.velocity, step=1.0,
                               decimals=0, suffix=" m/s")
        self.s_fos = FloatSlider(t("Target Factor of Safety"), 1.0, 3.0,
                                 self.state.load_case.target_fos, step=0.1,
                                 decimals=1)
        for s in (self.s_n, self.s_v, self.s_fos):
            s.changed.connect(self._on_case_change)
            lcf.addWidget(s)
        left.addWidget(lc)

        ic = QGroupBox(t("Inertial and control loads"))
        icf = QVBoxLayout(ic)
        self.cb_inertial = QCheckBox(t("Inertial relief (subtract wing weight)"))
        self.cb_inertial.setChecked(self.state.load_case.inertial_relief)
        self.cb_inertial.setToolTip(t(
            "At n g the wing's own mass pulls down and relieves the root "
            "bending moment. Needs a built structure for the mass distribution."))
        self.cb_inertial.toggled.connect(self._on_case_change)
        icf.addWidget(self.cb_inertial)
        self.s_ail = FloatSlider(t("Aileron deflection"), 0.0, 1.0,
                                 self.state.load_case.aileron_factor, step=0.05,
                                 decimals=2)
        self.s_ail.setToolTip(t("Spikes trailing-edge torsion on the outer wing."))
        self.s_ail_start = FloatSlider(t("Aileron starts at"), 0.3, 0.9,
                                       self.state.load_case.aileron_start,
                                       step=0.05, decimals=2, suffix=" span")
        for s in (self.s_ail, self.s_ail_start):
            s.changed.connect(self._on_case_change)
            icf.addWidget(s)
        left.addWidget(ic)

        pm = QGroupBox(t("Point masses (engines, fuel, payload)"))
        pmv = QVBoxLayout(pm)
        self.pm_table = QTableWidget(0, 4)
        self.pm_table.setHorizontalHeaderLabels(
            [t("Name"), t("kg"), t("span %"), t("chord %")])
        self.pm_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.Stretch)
        self.pm_table.setEditTriggers(QAbstractItemView.AllEditTriggers)
        self.pm_table.setMaximumHeight(140)
        self.pm_table.itemChanged.connect(self._on_pm_edit)
        pmv.addWidget(self.pm_table)
        row = QHBoxLayout()
        b_add = QPushButton(t("+ Add mass")); b_add.clicked.connect(self._add_pm)
        b_del = QPushButton(t("- Remove")); b_del.setProperty("flat", True)
        b_del.clicked.connect(self._del_pm)
        row.addWidget(b_add); row.addWidget(b_del); row.addStretch()
        pmv.addLayout(row)
        left.addWidget(pm)

        self.dp_info = QLabel(""); self.dp_info.setObjectName("hint")
        self.dp_info.setWordWrap(True)
        left.addWidget(self.dp_info)
        left.addStretch()

        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setWidget(panel); scroll.setFixedWidth(360)

        right = QVBoxLayout()
        self.plan_plot = pg.PlotWidget(title=t("Wing planform (half span)"))
        self.plan_plot.setAspectLocked(True)
        self.plan_plot.setLabel("bottom", "x [m]"); self.plan_plot.setLabel("left", "y [m]")
        self.load_plot = pg.PlotWidget(title=t("Spanwise load"))
        self.load_plot.setLabel("bottom", "y [m]")
        self.load_plot.setLabel("left", "load / span [N/m]")
        self.load_plot.addLegend(); self.load_plot.showGrid(x=True, y=True, alpha=0.3)
        self.bm_plot = pg.PlotWidget(title=t("Bending moment"))
        self.bm_plot.setLabel("bottom", "y [m]"); self.bm_plot.setLabel("left", "M [N·m]")
        self.bm_plot.showGrid(x=True, y=True, alpha=0.3)
        right.addWidget(self.plan_plot, 2)
        right.addWidget(self.load_plot, 2)
        right.addWidget(self.bm_plot, 2)

        root.addWidget(scroll, 0)
        rw = QWidget(); rw.setLayout(right)
        root.addWidget(rw, 1)

    # ---------------------------------------------------------------- actions
    def open_dialog(self):
        fn, _ = QFileDialog.getOpenFileName(
            self, t("Import Flovis file"), "",
            t("Flovis file (*.flovis);;All files (*.*)"))
        if not fn:
            return
        if not str(fn).lower().endswith(".flovis"):
            self._wrong_file(); return
        try:
            project = load_flovis(fn)
        except Exception as e:  # noqa: BLE001
            from ..dialogs import wrong_file_message
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Warning)
            box.setWindowTitle(t("Could not read this file"))
            box.setTextFormat(Qt.RichText)
            box.setText(t("StructVis could not read this as a Flovis project."
                          "<br><br><span style='color:#6b7280'>{}</span>"
                          "<br><br>{}").format(str(e), wrong_file_message()))
            box.exec()
            return
        self.state.project = project
        # a new wing invalidates everything derived from the previous one
        self.state.mesh = None
        self.state.result = None
        self.state.buckling = None
        self.state.design = None
        self.state.ai_review_text = None
        self.state.load_case.velocity = (
            project.aero.velocity if project.aero else self.state.load_case.velocity)
        self.s_v.set_value(self.state.load_case.velocity)
        self._refresh_info()
        self._update_plots()
        self.state.project_changed.emit()
        if project.warnings:
            QMessageBox.information(self, t("Import notes"),
                                    "\n\n".join(project.warnings))
        self.state.status(t("Imported: {}").format(project.model.name))

    def _wrong_file(self):
        from ..dialogs import wrong_file_message
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle(t("Not a Flovis file"))
        box.setTextFormat(Qt.RichText)
        box.setText(wrong_file_message())
        box.exec()

    def refresh_from_state(self):
        self._loading = True
        c = self.state.load_case
        self.s_n.set_value(c.load_factor)
        self.s_v.set_value(c.velocity)
        self.s_fos.set_value(c.target_fos)
        self.cb_inertial.setChecked(c.inertial_relief)
        self.s_ail.set_value(c.aileron_factor)
        self.s_ail_start.set_value(c.aileron_start)
        self._reload_pm_table()
        self._loading = False
        self._refresh_info()
        self._update_plots()

    def _on_external_change(self):
        # a mesh/param change elsewhere - just redraw (do not re-emit);
        # skip when we emitted the signal ourselves (avoids a double redraw)
        if self._emitting or self.state.project is None:
            return
        self._update_plots()

    def refresh_theme(self):
        from .. import theme
        for pw in (self.plan_plot, self.load_plot, self.bm_plot):
            theme.style_plot(pw)
        if self.state.project is not None:
            self._update_plots()

    def _on_case_change(self, _=None):
        if self._loading:
            return
        c = self.state.load_case
        c.load_factor = self.s_n.value()
        c.velocity = self.s_v.value()
        c.target_fos = self.s_fos.value()
        c.inertial_relief = self.cb_inertial.isChecked()
        c.aileron_factor = self.s_ail.value()
        c.aileron_start = self.s_ail_start.value()
        self._update_plots()
        self._emitting = True
        try:
            self.state.params_changed.emit()
        finally:
            self._emitting = False

    # ----------------------------------------------------------- point masses
    def _reload_pm_table(self):
        self._loading = True
        self.pm_table.setRowCount(0)
        for pmass in self.state.point_masses:
            self._append_pm_row(pmass)
        self._loading = False

    def _append_pm_row(self, pmass: PointMass):
        r = self.pm_table.rowCount()
        self.pm_table.insertRow(r)
        vals = [pmass.name, f"{pmass.mass_kg:g}",
                f"{pmass.span_frac*100:g}", f"{pmass.chord_frac*100:g}"]
        for c, v in enumerate(vals):
            self.pm_table.setItem(r, c, QTableWidgetItem(v))

    def _add_pm(self):
        self.state.point_masses.append(PointMass("motor", 0.5, 0.3, 0.4))
        self._reload_pm_table()
        self._on_pm_edit()

    def _del_pm(self):
        r = self.pm_table.currentRow()
        if 0 <= r < len(self.state.point_masses):
            self.state.point_masses.pop(r)
            self._reload_pm_table()
            self._on_pm_edit()

    def _on_pm_edit(self, _=None):
        if self._loading:
            return
        masses = []
        for r in range(self.pm_table.rowCount()):
            def cell(c, default=""):
                it = self.pm_table.item(r, c)
                return it.text() if it else default
            try:
                masses.append(PointMass(
                    name=cell(0, "mass") or "mass",
                    mass_kg=float(cell(1, "0") or 0),
                    span_frac=float(cell(2, "0") or 0) / 100.0,
                    chord_frac=float(cell(3, "40") or 40) / 100.0))
            except ValueError:
                continue
        self.state.point_masses = masses
        self._update_plots()
        self._emitting = True
        try:
            self.state.params_changed.emit()
        finally:
            self._emitting = False

    def _refresh_info(self):
        p = self.state.project
        if p is None:
            self.info.setText(t("No file loaded.")); return
        w = p.geometry
        self.info.setText(
            f"<b>{p.model.name}</b><br>"
            + t("Mass: {:.2f} kg &nbsp; Half-span: {:.2f} m").format(
                p.mass_kg, w.half_span) + "<br>"
            + t("Root chord: {:.3f} m &nbsp; Tip chord: {:.3f} m").format(
                w.root_chord, w.tip_chord) + "<br>"
            + t("Airfoil root: {}").format(w.spec_root.name))

    # ------------------------------------------------------------------ plots
    def _update_plots(self):
        p = self.state.project
        if p is None:
            return
        g = p.geometry
        yy = np.linspace(0, g.half_span, 60)
        chord = g.chord(yy); xle = g.x_le(yy); xte = xle + chord

        self.plan_plot.clear()
        xs = np.concatenate([xle, xte[::-1], [xle[0]]])
        ys = np.concatenate([yy, yy[::-1], [yy[0]]])
        self.plan_plot.plot(xs, ys, pen=pg.mkPen("#2563eb", width=2))
        for frac, col in ((self.state.params.front_spar, "#1d4ed8"),
                          (self.state.params.rear_spar, "#dc2626")):
            self.plan_plot.plot(xle + frac * chord, yy,
                                pen=pg.mkPen(col, width=1, style=Qt.DashLine))
        # mark point masses on the planform
        for pmass in self.state.point_masses:
            ypm = pmass.span_frac * g.half_span
            xpm = g.x_le(ypm) + pmass.chord_frac * g.chord(ypm)
            self.plan_plot.plot([xpm], [ypm], pen=None, symbol="o",
                                symbolBrush="#f59e0b", symbolSize=10)
        self.plan_plot.invertY(True)

        case = self.state.load_case
        dp = resolve_design_point(p, case)
        self.state.design = dp

        self.load_plot.clear()
        self.bm_plot.clear()
        sl = self._strip_loads(dp)
        if sl is not None:
            y = sl.y_stations
            trib = np.gradient(y)
            trib[trib == 0] = 1e-6
            # gross lift per span vs net per span
            gross = np.interp(y, yy, schrenk_lift_per_span(g, yy))
            gross *= (0.5 * dp.lift_total) / max(np.trapezoid(gross, y), 1e-9)
            self.load_plot.plot(y, gross, pen=pg.mkPen("#059669", width=2),
                                name=t("lift"))
            self.load_plot.plot(y, sl.net_Fz / trib, pen=pg.mkPen("#dc2626", width=2),
                                name=t("net (lift - inertia)"))
            self.bm_plot.plot(y, sl.bending_moment(),
                              pen=pg.mkPen("#7c3aed", width=2))
            root_bm = float(sl.bending_moment()[0] if len(y) else 0.0)
            relief = (f" &nbsp;|&nbsp; " + t("inertial relief: {:.0f} N").format(
                sl.inertial_half)) if sl.inertial_half else ""
            extra = f"<br>" + t("Root bending moment: {:.1f} N·m").format(root_bm) + relief
        else:
            shape = schrenk_lift_per_span(g, yy)
            scale = (0.5 * dp.lift_total) / max(np.trapezoid(shape, yy), 1e-9)
            self.load_plot.plot(yy, shape * scale,
                                pen=pg.mkPen("#059669", width=2), name=t("lift"))
            extra = ("<br><span style='color:" + theme.c("fg_muted") + "'>" + t(
                "Build the wingbox (tab 2) to see net load, inertial relief and "
                "the bending moment.") + "</span>")

        self.dp_info.setText(
            t("Design point: CL = {:.2f}, total lift = {:.0f} N "
              "(n·m·g = {:.1f}×{:.2f}×9.81)").format(
                dp.CL_design, dp.lift_total, case.load_factor, p.mass_kg)
            + extra
            + ("<br><span style='color:" + theme.c("danger") + "'>"
               + "<br>".join(dp.warnings) + "</span>" if dp.warnings else ""))

    def _strip_loads(self, dp):
        """Full strip loads when a mesh exists (enables inertial relief)."""
        if self.state.mesh is None:
            return None
        from ...core.mass import mass_per_station
        sm = mass_per_station(self.state.mesh, self.state.params,
                              self.state.mesh.y_stations)
        # fold_root=False: keep the smooth distribution for the display plots
        # (the solver decks fold the clamped root; here it would show a spike)
        return strip_loads(self.state.project, self.state.load_case,
                           self.state.mesh.y_stations,
                           self.state.params.front_spar,
                           self.state.params.rear_spar, design=dp,
                           struct_mass_station=sm,
                           point_masses=self.state.point_masses,
                           fold_root=False)
