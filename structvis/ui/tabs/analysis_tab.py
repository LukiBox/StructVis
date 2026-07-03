"""Tab 3: run the FEA, watch the solver log, and auto-size to a target FoS."""
from __future__ import annotations

import numpy as np
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QGroupBox,
                               QPushButton, QLabel, QPlainTextEdit, QMessageBox,
                               QComboBox)
import pyqtgraph as pg

from ...core.i18n import t
from ...core import materials
from ...core.fea import binaries
from ...core.fea.ccx_runner import solve, solve_buckling
from ...core.loads import strip_loads, resolve_design_point
from ...core.optimize import autosize, fully_stressed_design
from ..widgets.worker import Worker


def _build_loads(state):
    from ...core.mass import mass_per_station
    dp = resolve_design_point(state.project, state.load_case)
    state.design = dp
    sm = mass_per_station(state.mesh, state.params, state.mesh.y_stations)
    return strip_loads(state.project, state.load_case, state.mesh.y_stations,
                       state.params.front_spar, state.params.rear_spar,
                       design=dp, struct_mass_station=sm,
                       point_masses=getattr(state, "point_masses", None))


def _run_autosize(mesh, params, loads, half_span, target_fos,
                  progress=None, log_cb=None):
    """Re-solve with scaled thicknesses until min FoS == target.

    Materials (skin + support) are taken from the scaled params, so a
    two-material design is optimized against the correct per-material yields.
    """
    def eval_fos(factor):
        scaled = params.scaled(factor)
        res = solve(mesh, scaled, loads, half_span=half_span)
        if log_cb:
            log_cb(f"  factor {factor:.3f} -> min FoS {res.min_fos:.3f}\n")
        return res.min_fos
    opt = autosize(eval_fos, target_fos=target_fos, progress=progress)
    # final solve at the converged factor to return a full result
    final = solve(mesh, params.scaled(opt.factor), loads, half_span=half_span)
    return opt, final, params.scaled(opt.factor)


def _gauge_yield(params) -> dict:
    skin_y = materials.get(params.material).yield_strength
    supp_y = materials.get(params.effective_support_material).yield_strength
    return {"skin_t": skin_y, "stringer_t": skin_y,
            "web_t": supp_y, "cap_t": supp_y, "rib_t": supp_y}


def _run_fsd(mesh, params, loads, half_span, target_fos,
             progress=None, log_cb=None):
    """Fully Stressed Design: size each gauge to the target FoS independently."""
    def evaluate(p):
        res = solve(mesh, p, loads, half_span=half_span)
        if log_cb:
            g = "  ".join(f"{k[:-2]}={getattr(p, k)*1000:.2f}"
                          for k in ("skin_t", "web_t", "cap_t", "rib_t"))
            log_cb(f"  {g}  -> min FoS {res.min_fos:.2f}\n")
        return res
    fsd = fully_stressed_design(params, evaluate, target_fos,
                                _gauge_yield(params), progress=progress)
    final = solve(mesh, fsd.params, loads, half_span=half_span)
    return fsd, final, fsd.params


class AnalysisTab(QWidget):
    def __init__(self, app_state):
        super().__init__()
        self.state = app_state
        self._worker = None
        self._suppress_stale = False
        self._build()
        self.state.params_changed.connect(self._on_params_changed)

    def _on_params_changed(self):
        """Flag displayed results as stale when the structure/loads change."""
        if self._suppress_stale or self.state.result is None:
            return
        self.stat.setText(t("Structure or loads changed since the last solve - "
                            "the displayed results are stale. Re-run the FEA."))

    def _build(self):
        root = QHBoxLayout(self)
        left = QVBoxLayout()

        run = QGroupBox(t("Stress analysis"))
        rv = QVBoxLayout(run)
        self.b_run = QPushButton(t("Run FEA (CalculiX)"))
        self.b_run.clicked.connect(self._run_fea)
        rv.addWidget(self.b_run)
        self.b_buck = QPushButton(t("Run buckling analysis"))
        self.b_buck.setProperty("flat", True)
        self.b_buck.setToolTip(t(
            "Linear eigenvalue buckling: finds the load multiplier at which the "
            "thin skins buckle. Thin aerospace skins usually buckle before they "
            "yield, so this is often the real failure mode."))
        self.b_buck.clicked.connect(self._run_buckling)
        rv.addWidget(self.b_buck)
        mrow = QHBoxLayout()
        mrow.addWidget(QLabel(t("Method:")))
        self.method_cb = QComboBox()
        self.method_cb.addItem(t("Uniform scaling"), "uniform")
        self.method_cb.addItem(t("Fully stressed (per-gauge)"), "fsd")
        self.method_cb.setCurrentIndex(1)
        self.method_cb.setToolTip(t(
            "Uniform scales all gauges together to hit the target FoS. "
            "Fully stressed sizes each gauge independently - it thins unloaded "
            "members (e.g. the rear spar) and beefs up the root: generative "
            "design."))
        mrow.addWidget(self.method_cb, 1)
        rv.addLayout(mrow)
        self.b_opt = QPushButton(t("Auto-size to target FoS"))
        self.b_opt.setProperty("flat", True)
        self.b_opt.clicked.connect(self._run_optimize)
        rv.addWidget(self.b_opt)
        self.stat = QLabel(t("Build a wingbox in the Structure tab, then run."))
        self.stat.setObjectName("hint"); self.stat.setWordWrap(True)
        rv.addWidget(self.stat)
        left.addWidget(run)

        conv = QGroupBox(t("Auto-size convergence"))
        cv = QVBoxLayout(conv)
        self.conv_plot = pg.PlotWidget()
        self.conv_plot.setLabel("bottom", t("iteration"))
        self.conv_plot.setLabel("left", t("min FoS"))
        self.conv_plot.showGrid(x=True, y=True, alpha=0.3)
        self.conv_plot.setMinimumHeight(200)
        cv.addWidget(self.conv_plot)
        left.addWidget(conv)
        left.addStretch()

        right = QVBoxLayout()
        right.addWidget(QLabel(t("Solver log")))
        self.log = QPlainTextEdit(); self.log.setReadOnly(True)
        self.log.setStyleSheet("font-family: Consolas, monospace; font-size: 11px;")
        right.addWidget(self.log, 1)

        lw = QWidget(); lw.setLayout(left); lw.setFixedWidth(360)
        root.addWidget(lw, 0)
        rw = QWidget(); rw.setLayout(right)
        root.addWidget(rw, 1)

    # --------------------------------------------------------------- guards
    def _ready(self) -> bool:
        if self.state.project is None or self.state.mesh is None:
            QMessageBox.information(self, t("Not ready"),
                                    t("Import a file and build the wingbox first."))
            return False
        if not binaries.is_available():
            QMessageBox.warning(self, t("Solver missing"), binaries.missing_hint())
            return False
        return True

    def _busy(self, on: bool):
        self.b_run.setEnabled(not on)
        self.b_opt.setEnabled(not on)
        self.b_buck.setEnabled(not on)

    # -------------------------------------------------------------- buckling
    def _run_buckling(self):
        if not self._ready():
            return
        self.log.clear()
        self.stat.setText(t("Running buckling eigenvalue analysis..."))
        self._busy(True)
        loads = _build_loads(self.state)
        s = self.state
        self._worker = Worker(solve_buckling, s.mesh, s.params, loads,
                              half_span=s.project.geometry.half_span, n_modes=5)
        self._worker.log.connect(self._append_log)
        self._worker.done.connect(self._buck_done)
        self._worker.failed.connect(self._fea_failed)
        self._worker.start()

    def _buck_done(self, buck):
        self._busy(False)
        self.state.buckling = buck
        cf = buck.critical_factor
        target = self.state.load_case.target_fos
        if cf < 1.0:
            verdict = t("BUCKLES below the applied load - unsafe.")
        elif cf < target:
            verdict = t("buckling margin below target FoS {:.1f}.").format(target)
        else:
            verdict = t("safe against buckling.")
        self.stat.setText(
            t("Critical buckling factor = {:.2f} ({}). See 'Buckling mode' in "
              "the Results tab.").format(cf, verdict))
        self.state.result_changed.emit()

    # ------------------------------------------------------------------ FEA
    def _run_fea(self):
        if not self._ready():
            return
        self.log.clear()
        self.stat.setText(t("Solving..."))
        self._busy(True)
        loads = _build_loads(self.state)
        s = self.state
        self._worker = Worker(solve, s.mesh, s.params, loads,
                              half_span=s.project.geometry.half_span)
        self._worker.log.connect(self._append_log)
        self._worker.done.connect(self._fea_done)
        self._worker.failed.connect(self._fea_failed)
        self._worker.start()

    def _fea_done(self, result):
        self._busy(False)
        self.state.result = result
        s = result.summary()
        self.stat.setText(
            t("Done. Max Von Mises {:.1f} MPa, min FoS {:.2f}, "
              "tip deflection {:.1f} mm.").format(
                s["max_von_mises_MPa"], s["min_FoS"], s["tip_deflection_mm"]))
        self.state.result_changed.emit()

    def _fea_failed(self, msg):
        self._busy(False)
        self.stat.setText(t("Solver failed."))
        self._append_log("\n[ERROR] " + msg)
        QMessageBox.critical(self, t("Solver error"), msg.splitlines()[0])

    # ------------------------------------------------------------- optimize
    def _run_optimize(self):
        if not self._ready():
            return
        self.log.clear(); self.conv_plot.clear()
        self._conv_x, self._conv_y = [], []
        method = self.method_cb.currentData()
        self.stat.setText(t("Auto-sizing ({})...").format(
            self.method_cb.currentText()))
        self._busy(True)
        loads = _build_loads(self.state)
        s = self.state
        fn = _run_fsd if method == "fsd" else _run_autosize
        self._worker = Worker(fn, s.mesh, s.params, loads,
                              s.project.geometry.half_span,
                              s.load_case.target_fos)
        self._worker.log.connect(self._append_log)
        self._worker.progress.connect(self._opt_progress)
        self._worker.done.connect(self._opt_done)
        self._worker.failed.connect(self._fea_failed)
        self._worker.start()

    def _opt_progress(self, it):
        self._conv_x.append(len(self._conv_x))
        self._conv_y.append(it.min_fos)
        self.conv_plot.clear()
        self.conv_plot.plot(self._conv_x, self._conv_y,
                            pen=pg.mkPen("#2563eb", width=2),
                            symbol="o", symbolBrush="#2563eb")
        tgt = self.state.load_case.target_fos
        self.conv_plot.addLine(y=tgt, pen=pg.mkPen("#dc2626", style=pg.QtCore.Qt.DashLine))

    def _opt_done(self, payload):
        opt, final, new_params = payload
        self._busy(False)
        self.state.params = new_params
        self.state.result = final
        conv = t("converged") if getattr(opt, "converged", False) else t("stopped")
        if hasattr(opt, "factor"):       # uniform scaler
            detail = t("factor {:.3f}").format(opt.factor)
        else:                            # FSD - report the final gauges
            p = new_params
            detail = t("gauges skin/web/cap/rib = {:.2f}/{:.2f}/{:.2f}/{:.2f} mm").format(
                p.skin_t * 1000, p.web_t * 1000, p.cap_t * 1000, p.rib_t * 1000)
        self.stat.setText(
            t("Auto-size {}: {}, min FoS {:.2f}. {}").format(
                conv, detail, final.min_fos, getattr(opt, "message", "")))
        self._append_log(f"\n{getattr(opt, 'message', '')}\n")
        # this params change carries fresh results - don't flag them stale
        self._suppress_stale = True
        try:
            self.state.params_changed.emit()
        finally:
            self._suppress_stale = False
        self.state.result_changed.emit()

    def _append_log(self, text):
        from PySide6.QtGui import QTextCursor
        self.log.moveCursor(QTextCursor.End)
        self.log.insertPlainText(text)
        self.log.moveCursor(QTextCursor.End)

    def refresh_theme(self):
        from .. import theme
        theme.style_plot(self.conv_plot)
