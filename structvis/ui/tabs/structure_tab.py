"""Tab 2: parametric wingbox - sliders, material, live 3D preview, live mass."""
from __future__ import annotations

from PySide6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QGroupBox,
                               QLabel, QComboBox, QCheckBox, QMessageBox,
                               QScrollArea, QGridLayout)

from ...core.i18n import t
from .. import theme
from ...core import materials, mesher
from ...core.mass import mass_breakdown
from ...core.wingbox import WingboxParams
from ..widgets.param_slider import FloatSlider, IntSlider


class StructureTab(QWidget):
    def __init__(self, app_state):
        super().__init__()
        self.state = app_state
        self.view = None
        self._building = False
        self._build()
        self.state.project_changed.connect(self._rebuild)

    def _build(self):
        root = QHBoxLayout(self)

        # ---- left: controls (scrollable) ---------------------------------
        panel = QWidget()
        left = QVBoxLayout(panel)
        p = self.state.params

        geo = QGroupBox(t("Spars and ribs"))
        gv = QVBoxLayout(geo)
        self.s_front = FloatSlider(t("Front spar"), 5, 60, p.front_spar * 100,
                                   step=1, decimals=0, suffix=" %c")
        self.s_rear = FloatSlider(t("Rear spar"), 40, 95, p.rear_spar * 100,
                                  step=1, decimals=0, suffix=" %c")
        self.s_ribs = IntSlider(t("Number of ribs"), 2, 30, p.n_ribs)
        for s in (self.s_front, self.s_rear, self.s_ribs):
            gv.addWidget(s)
        left.addWidget(geo)

        gauge = QGroupBox(t("Gauges (thickness)"))
        ggv = QVBoxLayout(gauge)
        self.s_skin = FloatSlider(t("Skin"), 0.2, 8.0, p.skin_t * 1000,
                                  step=0.1, decimals=2, suffix=" mm")
        self.s_web = FloatSlider(t("Spar web"), 0.2, 10.0, p.web_t * 1000,
                                 step=0.1, decimals=2, suffix=" mm")
        self.s_cap = FloatSlider(t("Spar caps"), 0.2, 12.0, p.cap_t * 1000,
                                 step=0.1, decimals=2, suffix=" mm")
        self.s_rib = FloatSlider(t("Ribs"), 0.2, 8.0, p.rib_t * 1000,
                                 step=0.1, decimals=2, suffix=" mm")
        for s in (self.s_skin, self.s_web, self.s_cap, self.s_rib):
            ggv.addWidget(s)
        left.addWidget(gauge)

        strg = QGroupBox(t("Stringers and material"))
        sv = QVBoxLayout(strg)
        self.s_nstr = IntSlider(t("Stringers per skin"), 0, 8, p.n_stringers)
        self.s_strt = FloatSlider(t("Stringer gauge"), 0.5, 12.0,
                                  p.stringer_t * 1000, step=0.1, decimals=2,
                                  suffix=" mm")
        sv.addWidget(self.s_nstr); sv.addWidget(self.s_strt)
        self.mat_cb = QComboBox()
        for m in materials.MATERIALS:
            self.mat_cb.addItem(m.name, m.key)
        self._select_combo(self.mat_cb, p.material)
        self.mat_cb.currentIndexChanged.connect(self._on_change)
        sv.addWidget(QLabel(t("Skin / wing material:")))
        sv.addWidget(self.mat_cb)

        self.supp_mat_cb = QComboBox()
        self.supp_mat_cb.addItem(t("(same as skin)"), "")
        for m in materials.MATERIALS:
            self.supp_mat_cb.addItem(m.name, m.key)
        self._select_combo(self.supp_mat_cb, p.support_material)
        self.supp_mat_cb.currentIndexChanged.connect(self._on_change)
        sv.addWidget(QLabel(t("Support material (spars, caps, ribs):")))
        sv.addWidget(self.supp_mat_cb)
        left.addWidget(strg)

        for s in (self.s_front, self.s_rear, self.s_ribs, self.s_skin,
                  self.s_web, self.s_cap, self.s_rib, self.s_nstr, self.s_strt):
            s.changed.connect(self._on_change)

        vis = QGroupBox(t("Show components"))
        vv = QGridLayout(vis)
        self._vis_boxes = {}
        comps = [("SKIN_UP", t("Upper skin")), ("SKIN_LO", t("Lower skin")),
                 ("SPAR_F", t("Front spar")), ("SPAR_R", t("Rear spar")),
                 ("RIBS", t("Ribs")), ("STR_UP", t("Stringers"))]
        for i, (key, label) in enumerate(comps):
            cb = QCheckBox(label); cb.setChecked(True)
            cb.toggled.connect(self._on_visibility)
            self._vis_boxes[key] = cb
            vv.addWidget(cb, i // 2, i % 2)
        left.addWidget(vis)
        left.addStretch()

        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setWidget(panel); scroll.setFixedWidth(340)

        # ---- right: 3D preview + mass ------------------------------------
        right = QVBoxLayout()
        self.mass_lbl = QLabel(t("Import a .flovis file to build the wingbox."))
        self.mass_lbl.setObjectName("h2"); self.mass_lbl.setWordWrap(True)
        right.addWidget(self.mass_lbl)
        self.holder = QVBoxLayout()
        self.placeholder = QLabel(t("The 3D structure preview appears here."))
        self.placeholder.setObjectName("hint")
        self.holder.addWidget(self.placeholder)
        rw = QWidget(); rw.setLayout(self.holder)
        right.addWidget(rw, 1)

        root.addWidget(scroll, 0)
        rc = QWidget(); rc.setLayout(right)
        root.addWidget(rc, 1)

    # ------------------------------------------------------------- helpers
    def _select_combo(self, combo, key):
        i = combo.findData(key if key is not None else "")
        if i >= 0:
            combo.setCurrentIndex(i)

    def _hidden(self):
        hidden = {key for key, cb in self._vis_boxes.items() if not cb.isChecked()}
        # skin checkboxes also govern the caps on that face; the single
        # "stringers" box governs both upper and lower stringer strips
        if not self._vis_boxes["SKIN_UP"].isChecked():
            hidden |= {"CAP_UP"}
        if not self._vis_boxes["SKIN_LO"].isChecked():
            hidden |= {"CAP_LO"}
        if not self._vis_boxes["STR_UP"].isChecked():
            hidden |= {"STR_LO"}
        return hidden

    def _collect_params(self) -> WingboxParams:
        return WingboxParams(
            front_spar=self.s_front.value() / 100,
            rear_spar=self.s_rear.value() / 100,
            n_ribs=self.s_ribs.value(),
            skin_t=self.s_skin.value() / 1000,
            web_t=self.s_web.value() / 1000,
            cap_t=self.s_cap.value() / 1000,
            rib_t=self.s_rib.value() / 1000,
            n_stringers=self.s_nstr.value(),
            stringer_t=self.s_strt.value() / 1000,
            material=self.mat_cb.currentData(),
            support_material=self.supp_mat_cb.currentData() or "",
        )

    def refresh_from_state(self):
        self._building = True
        p = self.state.params
        self.s_front.set_value(p.front_spar * 100)
        self.s_rear.set_value(p.rear_spar * 100)
        self.s_ribs.set_value(p.n_ribs)
        self.s_skin.set_value(p.skin_t * 1000)
        self.s_web.set_value(p.web_t * 1000)
        self.s_cap.set_value(p.cap_t * 1000)
        self.s_rib.set_value(p.rib_t * 1000)
        self.s_nstr.set_value(p.n_stringers)
        self.s_strt.set_value(p.stringer_t * 1000)
        self._select_combo(self.mat_cb, p.material)
        self._select_combo(self.supp_mat_cb, p.support_material)
        self._building = False
        self._rebuild()

    # ------------------------------------------------------------- events
    def _on_change(self, _=None):
        if self._building:
            return
        self._rebuild()

    def _on_visibility(self, _=None):
        if self.view is not None and self.state.mesh is not None:
            self.view.set_hidden(self._hidden())

    def refresh_theme(self):
        if self.view is not None:
            self.view.apply_theme()

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

    def _rebuild(self):
        if self.state.project is None:
            return
        params = self._collect_params()
        issues = params.validated()
        if issues:
            self.mass_lbl.setText("<span style='color:" + theme.c("danger") + "'>"
                                  + "; ".join(issues) + "</span>")
            return
        self.state.params = params
        try:
            mesh = mesher.build_mesh(self.state.project.geometry, params)
        except Exception as e:  # noqa: BLE001
            self.mass_lbl.setText(
                f"<span style='color:{theme.c('danger')}'>{e}</span>")
            return
        self.state.mesh = mesh
        self._update_mass(mesh, params)
        if self._ensure_view():
            self.view.show_structure(mesh, params, hidden=self._hidden())
        self.state.params_changed.emit()

    def _update_mass(self, mesh, params):
        breakdown = mass_breakdown(mesh, params, half_wing=False)
        total = sum(breakdown.values())
        parts = "  ".join(f"{k}: {v*1000:.0f} g" for k, v in breakdown.items()
                          if v * 1000 >= 1)
        self.mass_lbl.setText(
            t("<b>Wing structural mass: {:.3f} kg</b> "
              "(both halves) &nbsp; | &nbsp; {} nodes, {} shells<br>"
              "<span style='color:{}'>{}</span>").format(
                total, mesh.n_nodes, mesh.n_elems, theme.c("fg_muted"), parts))
