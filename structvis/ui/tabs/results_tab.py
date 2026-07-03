"""Tab 4: 3D stress / deflection results viewer - the money shot."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QGroupBox,
                               QLabel, QComboBox, QSlider, QCheckBox,
                               QMessageBox, QGridLayout)

from ...core.i18n import t
from .. import theme


class ResultsTab(QWidget):
    def __init__(self, app_state):
        super().__init__()
        self.state = app_state
        self.view = None
        self._build()
        self.state.result_changed.connect(self.refresh_from_state)

    def _build(self):
        root = QHBoxLayout(self)
        left = QVBoxLayout()

        disp = QGroupBox(t("Display"))
        dv = QVBoxLayout(disp)
        dv.addWidget(QLabel(t("Field:")))
        self.field_cb = QComboBox()
        self.field_cb.addItem(t("Von Mises stress"), "von_mises")
        self.field_cb.addItem(t("Factor of Safety"), "fos")
        self.field_cb.addItem(t("Displacement"), "disp")
        self.field_cb.addItem(t("Buckling mode 1"), "buckling")
        self.field_cb.currentIndexChanged.connect(self._on_field)
        dv.addWidget(self.field_cb)

        dv.addWidget(QLabel(t("Deflection exaggeration: ") + "×1"))
        self.warp_lbl = dv.itemAt(dv.count() - 1).widget()
        self.warp = QSlider(Qt.Horizontal)
        self.warp.setRange(1, 100); self.warp.setValue(1)
        self.warp.valueChanged.connect(self._on_warp)
        dv.addWidget(self.warp)

        self.cb_ghost = QCheckBox(t("Show undeformed ghost"))
        self.cb_ghost.setChecked(True)
        self.cb_ghost.toggled.connect(self._on_ghost)
        dv.addWidget(self.cb_ghost)
        self.cb_clip = QCheckBox(t("Interactive clip plane (slice inside)"))
        self.cb_clip.setToolTip(t(
            "Drag the plane widget to slice through the wing and see stress on "
            "the internal spar webs and ribs."))
        self.cb_clip.toggled.connect(self._on_clip)
        dv.addWidget(self.cb_clip)
        self.cb_mos = QCheckBox(t("Report Margin of Safety (MoS)"))
        self.cb_mos.setToolTip(t(
            "MoS = FoS_actual / FoS_target - 1. Negative MoS = failing part."))
        self.cb_mos.toggled.connect(lambda _=None: self.refresh_from_state())
        dv.addWidget(self.cb_mos)
        left.addWidget(disp)

        vis = QGroupBox(t("Show components"))
        vv = QGridLayout(vis)
        self._vis = {}
        comps = [("SKIN_UP", t("Upper skin")), ("SKIN_LO", t("Lower skin")),
                 ("SPAR_F", t("Front spar")), ("SPAR_R", t("Rear spar")),
                 ("RIBS", t("Ribs"))]
        for i, (k, lbl) in enumerate(comps):
            cb = QCheckBox(lbl); cb.setChecked(True)
            cb.toggled.connect(self._on_vis)
            self._vis[k] = cb
            vv.addWidget(cb, i // 2, i % 2)
        left.addWidget(vis)

        self.hud = QLabel(t("Run an analysis to see stress results here."))
        self.hud.setObjectName("h2"); self.hud.setWordWrap(True)
        left.addWidget(self.hud)
        left.addStretch()

        self.holder = QVBoxLayout()
        self.placeholder = QLabel(t("The 3D stress map appears here."))
        self.placeholder.setObjectName("hint")
        self.holder.addWidget(self.placeholder)

        lw = QWidget(); lw.setLayout(left); lw.setFixedWidth(300)
        root.addWidget(lw, 0)
        rw = QWidget(); rw.setLayout(self.holder)
        root.addWidget(rw, 1)

    def _hidden(self):
        hidden = {k for k, cb in self._vis.items() if not cb.isChecked()}
        if "SKIN_UP" in hidden:
            hidden |= {"CAP_UP", "STR_UP"}
        if "SKIN_LO" in hidden:
            hidden |= {"CAP_LO", "STR_LO"}
        return hidden

    def _ensure_view(self) -> bool:
        if self.view is not None:
            return True
        try:
            from ..widgets.wingbox_view import WingboxView
            self.view = WingboxView(self)
            if self.placeholder is not None:
                self.placeholder.setParent(None); self.placeholder = None
            self.holder.addWidget(self.view.widget)
            return True
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, t("3D view unavailable"), str(e))
            return False

    def refresh_from_state(self):
        if not self._ensure_view():
            return
        field = self.field_cb.currentData()
        if field == "buckling":
            if self.state.buckling is not None:
                self.view.show_buckling(self.state.buckling,
                                        warp=float(self.warp.value()),
                                        hidden=self._hidden())
            else:
                self.state.status(t("No buckling result yet - run the "
                                    "buckling analysis in the Analysis tab."))
        elif self.state.result is not None:
            self.view.show_result(self.state.result, field=field,
                                  warp=float(self.warp.value()),
                                  show_undeformed=self.cb_ghost.isChecked(),
                                  hidden=self._hidden())
        self._update_hud()

    def _update_hud(self):
        r = self.state.result
        target = self.state.load_case.target_fos
        parts = []
        if r is not None:
            s = r.summary()
            if self.cb_mos.isChecked():
                mos = s["min_FoS"] / max(target, 1e-6) - 1.0
                mcol = theme.c("success") if mos >= 0 else theme.c("danger")
                margin = (t("<b style='color:{}'>Margin of Safety: {:+.2f}</b> "
                            "(FoS {:.2f} / target {:.1f} - 1)").format(
                    mcol, mos, s["min_FoS"], target))
            else:
                fcol = theme.c("success") if s["min_FoS"] >= target else theme.c("danger")
                margin = (t("<b style='color:{}'>Min Factor of Safety: {:.2f}</b> "
                            "(target {:.1f})").format(fcol, s["min_FoS"], target))
            parts.append(
                t("<b>Max Von Mises:</b> {:.1f} MPa (yield {:.0f} MPa) at {}<br>"
                  "{}<br><b>Tip deflection:</b> {:.1f} mm ({:.1f}% of span)"
                  "<br><b>Tip twist:</b> {:.2f}°").format(
                    s["max_von_mises_MPa"], s["yield_MPa"], s["critical_component"],
                    margin, s["tip_deflection_mm"], s["tip_deflection_pct_span"],
                    s["tip_twist_deg"]))
        b = self.state.buckling
        if b is not None:
            cf = b.critical_factor
            bcol = theme.c("success") if cf >= target else theme.c("danger")
            parts.append(t("<b style='color:{}'>Critical buckling factor: {:.2f}</b>"
                           " (load multiplier to buckle)").format(bcol, cf))
        self.hud.setText("<hr>".join(parts) if parts else
                         t("Run an analysis to see results here."))

    def _on_field(self):
        self.refresh_from_state()

    def _on_warp(self, v):
        self.warp_lbl.setText(t("Deflection exaggeration: ") + f"×{v}")
        if self.view is not None:
            self.view.set_warp(v)

    def _on_ghost(self, on):
        if self.view is not None:
            self.view.set_show_undeformed(on)

    def _on_clip(self, on):
        if self.view is not None:
            self.view.set_clip(on)

    def refresh_theme(self):
        if self.view is not None:
            self.view.apply_theme()

    def _on_vis(self, _=None):
        if self.view is not None and self.state.result is not None:
            self.view.set_hidden(self._hidden())
