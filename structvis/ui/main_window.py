"""StructVis main window - tabbed layout, shared AppState, language switch."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import (QMainWindow, QTabWidget, QWidget, QVBoxLayout,
                               QLabel, QHBoxLayout, QComboBox, QFileDialog,
                               QMessageBox)

from ..core.i18n import t, set_language, get_language
from ..core.wingbox import WingboxParams
from ..core.loads import LoadCase
from ..core import project as proj
from .effects import apply_panel_shadows
from . import theme


class AppState(QObject):
    """State shared between tabs, with change signals."""
    project_changed = Signal()      # a new .flovis was imported
    params_changed = Signal()       # wingbox params or load case changed
    result_changed = Signal()       # a new FEA result is available

    def __init__(self, window):
        super().__init__()
        self.window = window
        self.project = None          # ImportedProject
        self.params = WingboxParams()
        self.load_case = LoadCase()
        self.point_masses = []       # list[PointMass] on the half-wing
        self.mesh = None             # last built WingboxMesh
        self.design = None           # DesignPoint
        self.result = None           # FeaResult
        self.buckling = None         # BucklingResult
        self.ai_review_text = None   # last AI review (optional, for the report)
        self.project_path = None     # .structvis path

    def status(self, text: str):
        self.window.statusBar().showMessage(text, 6000)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("StructVis")
        self.resize(1240, 820)
        self.state = AppState(self)
        self._build_ui()
        self.statusBar().showMessage(t("Ready. Open a .flovis file to begin."))

    def _build_ui(self):
        from .tabs.import_tab import ImportTab
        from .tabs.structure_tab import StructureTab
        from .tabs.analysis_tab import AnalysisTab
        from .tabs.results_tab import ResultsTab
        from .tabs.report_tab import ReportTab
        from .tabs.review_tab import ReviewTab
        from .dialogs import author_html

        header = QWidget()
        hl = QHBoxLayout(header)
        hl.setContentsMargins(16, 10, 16, 4)
        title = QLabel("StructVis"); title.setObjectName("h1")
        sub = QLabel(t("parametric wingbox generator · FEA stress viewer"))
        sub.setObjectName("hint")
        hl.addWidget(title); hl.addSpacing(12); hl.addWidget(sub); hl.addStretch()
        hl.addWidget(QLabel(t("Theme:")))
        self.theme_cb = QComboBox()
        self.theme_cb.addItem(t("Light"), "light")
        self.theme_cb.addItem(t("Dark"), "dark")
        self.theme_cb.setCurrentIndex(1 if theme.is_dark() else 0)
        self.theme_cb.setFixedWidth(90)
        self.theme_cb.currentIndexChanged.connect(self._on_theme_change)
        hl.addWidget(self.theme_cb)
        hl.addSpacing(10)
        hl.addWidget(QLabel(t("Language:")))
        self.lang_cb = QComboBox()
        self.lang_cb.addItem("English", "en")
        self.lang_cb.addItem("Polski", "pl")
        self.lang_cb.setCurrentIndex(0 if get_language() == "en" else 1)
        self.lang_cb.setFixedWidth(110)
        self.lang_cb.currentIndexChanged.connect(self._on_language_change)
        hl.addWidget(self.lang_cb)
        credit = QLabel(author_html()); credit.setOpenExternalLinks(True)
        hl.addSpacing(10); hl.addWidget(credit)

        self.tabs = QTabWidget()
        self.import_tab = ImportTab(self.state)
        self.structure_tab = StructureTab(self.state)
        self.analysis_tab = AnalysisTab(self.state)
        self.results_tab = ResultsTab(self.state)
        self.report_tab = ReportTab(self.state)
        self.review_tab = ReviewTab(self.state)
        self.tabs.addTab(self.import_tab, t("  1. Import and Loads  "))
        self.tabs.addTab(self.structure_tab, t("  2. Structure  "))
        self.tabs.addTab(self.analysis_tab, t("  3. Analysis  "))
        self.tabs.addTab(self.results_tab, t("  4. Results  "))
        self.tabs.addTab(self.report_tab, t("  5. Report  "))
        self.tabs.addTab(self.review_tab, t("  6. AI Review  "))

        central = QWidget(); central.setObjectName("central")
        v = QVBoxLayout(central)
        v.setContentsMargins(14, 8, 14, 12); v.setSpacing(10)
        v.addWidget(header); v.addWidget(self.tabs, 1)
        self.setCentralWidget(central)

        self._build_menu()
        apply_panel_shadows(self)

        # jump to Structure once a project is imported
        self.state.project_changed.connect(
            lambda: self.tabs.setCurrentWidget(self.structure_tab))
        self.state.result_changed.connect(
            lambda: self.tabs.setCurrentWidget(self.results_tab))

    def _build_menu(self):
        m = self.menuBar().addMenu(t("&File"))
        m.addAction(t("Import .flovis..."), self._import_flovis)
        m.addSeparator()
        m.addAction(t("Open project (.structvis)..."), self._open_project)
        m.addAction(t("Save project"), self._save_project)
        m.addAction(t("Save project as..."), self._save_project_as)
        m.addSeparator()
        m.addAction(t("Export PDF report..."), self._export_report)
        m.addSeparator()
        m.addAction(t("Quit"), self.close)

        h = self.menuBar().addMenu(t("&Help"))
        h.addAction(t("Solver status"), self._solver_status)
        h.addAction(t("About"), self._about)

    # ------------------------------------------------------------- actions
    def _import_flovis(self):
        self.import_tab.open_dialog()

    def _open_project(self):
        fn, _ = QFileDialog.getOpenFileName(
            self, t("Open StructVis project"), "",
            t("StructVis project (*.structvis)"))
        if not fn:
            return
        try:
            data = proj.load_project(fn)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, t("Read error"), str(e)); return
        self.state.project = data["project"]
        self.state.params = data["params"]
        self.state.load_case = data["load_case"]
        self.state.point_masses = data.get("point_masses", [])
        self.state.result = data["result"]
        self.state.buckling = data.get("buckling")
        self.state.project_path = fn
        # loaded params and results are consistent - don't flag them stale
        self.analysis_tab._suppress_stale = True
        try:
            self.import_tab.refresh_from_state()
            self.structure_tab.refresh_from_state()
            self.state.project_changed.emit()
        finally:
            self.analysis_tab._suppress_stale = False
        if self.state.result is not None:
            self.results_tab.refresh_from_state()
            self.state.result_changed.emit()
        self.state.status(t("Loaded project: {}").format(Path(fn).name))

    def _save_project(self):
        if self.state.project_path:
            self._write_project(self.state.project_path)
        else:
            self._save_project_as()

    def _save_project_as(self):
        fn, _ = QFileDialog.getSaveFileName(
            self, t("Save StructVis project"), "wingbox.structvis",
            t("StructVis project (*.structvis)"))
        if fn:
            self._write_project(fn)

    def _write_project(self, fn):
        if self.state.project is None:
            QMessageBox.information(self, t("Nothing to save"),
                                    t("Import a .flovis file first.")); return
        try:
            p = proj.save_project(fn, self.state.project, self.state.params,
                                  self.state.load_case, self.state.result,
                                  point_masses=self.state.point_masses,
                                  buckling=self.state.buckling)
            self.state.project_path = str(p)
            self.state.status(t("Saved: {}").format(Path(p).name))
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, t("Save error"), str(e))

    def _export_report(self):
        self.tabs.setCurrentWidget(self.report_tab)
        self.report_tab._export()

    def _solver_status(self):
        from ..core.fea import binaries
        if binaries.is_available():
            QMessageBox.information(
                self, t("Solver status"),
                t("CalculiX found:\n{}").format(binaries.ccx_path()))
        else:
            QMessageBox.warning(self, t("Solver status"), binaries.missing_hint())

    def _about(self):
        from .dialogs import AboutDialog
        from ..core.fea import binaries
        info = (t("CalculiX found: {}").format(binaries.ccx_path())
                if binaries.is_available()
                else t("CalculiX not found - the stress solve is disabled "
                       "until you install it (Help > Solver status)."))
        AboutDialog(self, solver_info=info).exec()

    # ------------------------------------------------------------- welcome
    def show_welcome(self):
        from .dialogs import WelcomeDialog
        from ..core import settings
        if settings.get("hide_welcome"):
            return
        dlg = WelcomeDialog(self)
        dlg.exec()
        if dlg.dont_show:
            settings.set_value("hide_welcome", True)
        if dlg.start_import:
            self.import_tab.open_dialog()

    # --------------------------------------------------------------- close
    def closeEvent(self, event):
        """Shut down any running solver/AI worker threads before exit."""
        for w in (getattr(self.analysis_tab, "_worker", None),
                  getattr(self.review_tab, "_stream", None)):
            try:
                if w is not None and w.isRunning():
                    if not w.wait(1500):
                        w.terminate()
                        w.wait(500)
            except Exception:  # noqa: BLE001
                pass
        super().closeEvent(event)

    def _on_language_change(self):
        lang = self.lang_cb.currentData()
        if lang and lang != get_language():
            set_language(lang)
            QMessageBox.information(
                self, "Language",
                "Language changed. Restart StructVis to fully apply.")

    def _on_theme_change(self):
        name = self.theme_cb.currentData()
        if not name or name == theme.get_theme():
            return
        from PySide6.QtWidgets import QApplication
        theme.set_theme(name)
        theme.apply(QApplication.instance())
        # refresh the custom-drawn plots and 3D views (not covered by QSS)
        for tab in (self.import_tab, self.structure_tab, self.analysis_tab,
                    self.results_tab, self.review_tab, self.report_tab):
            if hasattr(tab, "refresh_theme"):
                try:
                    tab.refresh_theme()
                except Exception:  # noqa: BLE001
                    pass
        self.state.status(t("Theme changed."))

