"""Export to SimVis dialog: assemble mass/CG/inertia and write simvis_mass.json.

The wing structural mass is computed (from the FEA mesh) and shown read-only;
the user enters the rest of the aircraft as point masses (seeded to hit a
target all-up mass) and picks the limit load factor. A live readout shows the
resulting total mass, CG and static-margin-relevant inertia before saving.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
                               QGroupBox, QLabel, QDoubleSpinBox, QPushButton,
                               QTableWidget, QTableWidgetItem, QHeaderView,
                               QFileDialog, QMessageBox, QWidget)

from ..core.i18n import t
from ..core.simvis_export import (PointMass, assemble_mass_model,
                                  default_point_masses, write_simvis_mass)
from ..core.mass import total_mass
from . import theme


class SimVisExportDialog(QDialog):
    def __init__(self, state, parent=None):
        super().__init__(parent)
        self.state = state
        self.setWindowTitle(t("Export to SimVis"))
        self.setMinimumWidth(620)
        self._model = None

        # wing structural mass from the current mesh (full wing = 2x half)
        self._wing_kg = total_mass(state.mesh, state.params, half_wing=False)
        target = max(getattr(state.project, "mass_kg", 0.0) or 0.0,
                     self._wing_kg * 1.6)

        v = QVBoxLayout(self)
        head = QLabel(t("Export to SimVis")); head.setObjectName("h1")
        v.addWidget(head)
        sub = QLabel(t("Writes simvis_mass.json - mass, CG, inertia and the "
                       "structural limit load - for the flight simulator."))
        sub.setObjectName("hint"); sub.setWordWrap(True)
        v.addWidget(sub)

        # ---- masses -----------------------------------------------------------
        mbox = QGroupBox(t("Masses"))
        ml = QVBoxLayout(mbox)
        wrow = QHBoxLayout()
        wrow.addWidget(QLabel(t("Wing structure (computed):")))
        self.wing_lbl = QLabel(f"<b>{self._wing_kg*1000:.0f} g</b>")
        wrow.addWidget(self.wing_lbl); wrow.addStretch(1)
        wrow.addWidget(QLabel(t("Target all-up mass:")))
        self.target = QDoubleSpinBox(); self.target.setRange(
            self._wing_kg, 60.0)
        self.target.setDecimals(3); self.target.setSuffix(" kg")
        self.target.setValue(target)
        wrow.addWidget(self.target)
        ml.addLayout(wrow)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(
            [t("Item"), t("Mass [g]"), t("x [m]"), t("z [m]")])
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        ml.addWidget(self.table)
        row = QHBoxLayout()
        add = QPushButton(t("Add item")); add.setProperty("flat", True)
        add.clicked.connect(self._add_row)
        rem = QPushButton(t("Remove selected")); rem.setProperty("flat", True)
        rem.clicked.connect(self._remove_row)
        seed = QPushButton(t("Seed to target mass")); seed.setProperty("flat", True)
        seed.clicked.connect(self._seed)
        row.addWidget(add); row.addWidget(rem); row.addWidget(seed)
        row.addStretch(1)
        ml.addLayout(row)
        hint = QLabel(t("x is measured aft from the nose (same origin as "
                        "Flovis); items sit on the centerline."))
        hint.setObjectName("hint"); hint.setWordWrap(True)
        ml.addWidget(hint)
        v.addWidget(mbox)

        # ---- structural limits ------------------------------------------------
        sbox = QGroupBox(t("Structural limits"))
        sf = QFormLayout(sbox)
        self.n_pos = QDoubleSpinBox(); self.n_pos.setRange(1.0, 20.0)
        self.n_pos.setDecimals(1); self.n_pos.setSuffix(" g")
        self.n_pos.setValue(float(getattr(state.load_case, "load_factor", 6.0)))
        sf.addRow(t("Positive limit load"), self.n_pos)
        self.n_neg = QDoubleSpinBox(); self.n_neg.setRange(-20.0, -0.5)
        self.n_neg.setDecimals(1); self.n_neg.setSuffix(" g")
        self.n_neg.setValue(-0.5 * self.n_pos.value())
        sf.addRow(t("Negative limit load"), self.n_neg)
        fos = self._current_fos()
        self.fos_lbl = QLabel(f"{fos:.2f}" if fos is not None
                              else t("(run the analysis for FoS)"))
        sf.addRow(t("Min. factor of safety"), self.fos_lbl)
        v.addWidget(sbox)

        # ---- live readout -----------------------------------------------------
        self.readout = QLabel(""); self.readout.setObjectName("hint")
        self.readout.setWordWrap(True)
        v.addWidget(self.readout)

        # ---- buttons ----------------------------------------------------------
        btns = QHBoxLayout(); btns.addStretch(1)
        cancel = QPushButton(t("Cancel")); cancel.setProperty("flat", True)
        cancel.clicked.connect(self.reject)
        self.save_btn = QPushButton(t("Export simvis_mass.json"))
        self.save_btn.clicked.connect(self._export)
        btns.addWidget(cancel); btns.addWidget(self.save_btn)
        v.addLayout(btns)

        for w in (self.target, self.n_pos, self.n_neg):
            w.valueChanged.connect(self._recompute)
        self.n_pos.valueChanged.connect(
            lambda _v: self.n_neg.setValue(-0.5 * self.n_pos.value()))
        self.table.itemChanged.connect(self._recompute)
        self._seed()

    # ---- helpers --------------------------------------------------------------
    def _current_fos(self):
        res = getattr(self.state, "result", None)
        if res is not None and hasattr(res, "min_fos"):
            try:
                return float(res.min_fos)
            except Exception:  # noqa: BLE001
                return None
        return None

    def _add_row(self, name="Item", mass_g=50.0, x=0.1, z=0.0):
        self.table.blockSignals(True)
        r = self.table.rowCount(); self.table.insertRow(r)
        self.table.setItem(r, 0, QTableWidgetItem(str(name)))
        for col, val in ((1, mass_g), (2, x), (3, z)):
            it = QTableWidgetItem(f"{val:.3f}" if col > 1 else f"{val:.0f}")
            self.table.setItem(r, col, it)
        self.table.blockSignals(False)
        self._recompute()

    def _remove_row(self):
        r = self.table.currentRow()
        if r >= 0:
            self.table.removeRow(r)
            self._recompute()

    def _seed(self):
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        self.table.blockSignals(False)
        pms = default_point_masses(self.state.project, self.target.value(),
                                   self._wing_kg)
        for pm in pms:
            self._add_row(pm.name, pm.mass_kg * 1000.0, pm.x, pm.z)
        self._recompute()

    def _point_masses(self) -> list[PointMass]:
        out = []
        for r in range(self.table.rowCount()):
            try:
                name = self.table.item(r, 0).text() or f"Item {r+1}"
                m = float(self.table.item(r, 1).text()) / 1000.0
                x = float(self.table.item(r, 2).text())
                z = float(self.table.item(r, 3).text())
                if m > 0:
                    out.append(PointMass(name, m, x=x, z=z))
            except (ValueError, AttributeError):
                continue
        return out

    def _recompute(self, *_a):
        try:
            self._model = assemble_mass_model(
                self.state.project, self.state.mesh, self.state.params,
                self._point_masses(), self.n_pos.value(), self.n_neg.value(),
                min_fos=self._current_fos(),
                notes=f"StructVis export: wing structure "
                      f"{self._wing_kg*1000:.0f} g measured, remainder as "
                      f"point masses.")
        except ValueError as e:
            self.readout.setText(str(e))
            self.save_btn.setEnabled(False)
            return
        m = self._model
        pm_total = m.point_mass_kg + m.wing_structural_kg
        delta = (self.target.value() - pm_total) * 1000.0
        sm = m.cg_m
        txt = (t("Total {:.3f} kg (wing {:.0f} g + items {:.0f} g).  "
                 "CG at x = {:.3f} m, z = {:.3f} m.").format(
                     m.mass_kg, m.wing_structural_kg * 1000.0,
                     m.point_mass_kg * 1000.0, sm[0], sm[2])
               + "  " + t("Ixx {:.3f}, Iyy {:.3f}, Izz {:.3f} kg·m².").format(
                   m.inertia["Ixx"], m.inertia["Iyy"], m.inertia["Izz"]))
        if abs(delta) > 20.0:
            txt += "  " + t("(items are {:+.0f} g off the target mass)").format(
                delta)
        for w in m.warnings:
            txt += "\n⚠ " + w
        self.readout.setText(txt)
        self.save_btn.setEnabled(True)

    def _export(self):
        if self._model is None:
            return
        start = "simvis_mass.json"
        if getattr(self.state, "project_path", None):
            start = str(Path(self.state.project_path).with_name(
                "simvis_mass.json"))
        fn, _ = QFileDialog.getSaveFileName(
            self, t("Export simvis_mass.json"), start, "JSON (*.json)")
        if not fn:
            return
        try:
            out = write_simvis_mass(self._model, fn)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, t("Export error"), str(e))
            return
        msg = t("Saved {}.\n\nOpen it in SimVis together with the .flovis "
                "project (Aircraft tab -> Import mass file).").format(out.name)
        if self._model.warnings:
            msg += "\n\n" + t("Note:") + "\n- " + "\n- ".join(
                self._model.warnings)
        QMessageBox.information(self, t("Exported to SimVis"), msg)
        self.accept()
