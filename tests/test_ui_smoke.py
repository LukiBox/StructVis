"""
Headless UI smoke test: every UI module imports, the main window builds, and
the import tab processes a real project (pyqtgraph plots, load reconstruction).
The lazy PyVista/VTK 3D views are NOT instantiated here (need a GL context).
"""
from __future__ import annotations

import os
import importlib

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

UI_MODULES = [
    "structvis.app",
    "structvis.ui.main_window",
    "structvis.ui.dialogs",
    "structvis.ui.widgets.worker",
    "structvis.ui.widgets.param_slider",
    "structvis.ui.widgets.wingbox_view",
    "structvis.ui.tabs.import_tab",
    "structvis.ui.tabs.structure_tab",
    "structvis.ui.tabs.analysis_tab",
    "structvis.ui.tabs.results_tab",
    "structvis.ui.tabs.report_tab",
    "structvis.ui.tabs.review_tab",
]


@pytest.mark.parametrize("mod", UI_MODULES)
def test_ui_module_imports(mod):
    importlib.import_module(mod)


@pytest.fixture(scope="module")
def qapp():
    try:
        from PySide6.QtWidgets import QApplication
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"PySide6 unavailable: {e}")
    app = QApplication.instance() or QApplication([])
    yield app


def test_mainwindow_builds(qapp):
    from structvis.ui.main_window import MainWindow
    win = MainWindow()
    assert win.tabs.count() == 6
    win.close()


def test_import_tab_processes_project(qapp, flovis_file):
    from structvis.ui.main_window import MainWindow
    from structvis.core.flovis_import import load_flovis
    win = MainWindow()
    win.state.project = load_flovis(flovis_file)
    # drive the import tab's plotting/design-point path without a file dialog
    win.import_tab._refresh_info()
    win.import_tab._update_plots()
    assert win.state.design is not None
    assert win.state.design.lift_total > 0
    win.close()


def test_structure_params_collected(qapp, flovis_file):
    from structvis.ui.main_window import MainWindow
    from structvis.core.flovis_import import load_flovis
    win = MainWindow()
    win.state.project = load_flovis(flovis_file)
    params = win.structure_tab._collect_params()
    assert 0.05 <= params.front_spar < params.rear_spar <= 0.95
    assert params.n_ribs >= 2
    win.close()


def test_review_chunk_reaches_textbox(qapp):
    """Regression: streamed AI text must actually land in the output box.

    A Qt enum-via-instance access (textCursor().End) silently threw in the
    slot, so 'Review complete' fired but the box stayed empty.
    """
    from structvis.ui.main_window import MainWindow
    win = MainWindow()
    rt = win.review_tab
    rt._got_output = False
    rt._on_chunk("content", "Hello ")
    rt._on_chunk("content", "world.")
    assert rt.out.toPlainText() == "Hello world."
    win.close()


def test_solver_log_appends(qapp):
    from structvis.ui.main_window import MainWindow
    win = MainWindow()
    win.analysis_tab._append_log("line 1\n")
    win.analysis_tab._append_log("line 2\n")
    assert "line 1" in win.analysis_tab.log.toPlainText()
    assert "line 2" in win.analysis_tab.log.toPlainText()
    win.close()


def test_theme_tokens_and_qss():
    from structvis.ui import theme
    orig = theme.get_theme()
    try:
        for name in ("light", "dark"):
            theme.set_theme(name)
            qss = theme.stylesheet()
            assert "$" not in qss                 # all tokens substituted
            assert theme.plot_bg() and theme.view_bg()
        # dark and light must differ
        theme.set_theme("light"); light_bg = theme.plot_bg()
        theme.set_theme("dark"); dark_bg = theme.plot_bg()
        assert light_bg != dark_bg
    finally:
        theme.set_theme(orig)


def test_theme_switch_live(qapp):
    from structvis.ui.main_window import MainWindow
    from structvis.ui import theme
    orig = theme.get_theme()
    try:
        win = MainWindow()
        idx = win.theme_cb.findData("dark")
        win.theme_cb.setCurrentIndex(idx)      # triggers _on_theme_change
        assert theme.get_theme() == "dark"
        # switching back works without error
        win.theme_cb.setCurrentIndex(win.theme_cb.findData("light"))
        assert theme.get_theme() == "light"
        win.close()
    finally:
        theme.set_theme(orig)


def test_no_ampersand_mnemonic_in_titles(qapp):
    """Group/tab titles must not contain literal & (renders as underscore)."""
    from structvis.ui.main_window import MainWindow
    win = MainWindow()
    # tab labels
    for i in range(win.tabs.count()):
        assert "&" not in win.tabs.tabText(i)
    # group box titles
    from PySide6.QtWidgets import QGroupBox
    for gb in win.findChildren(QGroupBox):
        assert "&" not in gb.title(), gb.title()
    win.close()
