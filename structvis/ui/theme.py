"""
Theming: light / dark with semantic color tokens.

One token set per theme drives the Qt palette, the QSS stylesheet, the
pyqtgraph plots and the PyVista 3D views, so nothing is hardcoded per widget.
Dark mode uses desaturated slate tones (not a hard invert) for comfortable
contrast. The choice is persisted in the StructVis settings file.
"""
from __future__ import annotations

from string import Template

from ..core import settings as _settings

# ---- semantic tokens -------------------------------------------------------
LIGHT = {
    "window": "#f8f9fa", "surface": "#ffffff", "surface_alt": "#f3f4f6",
    "fg": "#1f2937", "fg_strong": "#111827", "fg_muted": "#6b7280",
    "accent": "#2563eb", "accent_hover": "#1d4ed8",
    "grad_top": "#3b82f6", "grad_bot": "#2563eb",
    "grad_top_h": "#60a5fa", "grad_bot_h": "#3b82f6",
    "border": "#d1d5db", "border_soft": "#eceff3", "divider": "#f1f5f9",
    "flat_hover_bg": "#f0f6ff", "flat_press_bg": "#e0ecff",
    "menu_hover_bg": "#eff6ff", "menu_hover_fg": "#2563eb",
    "slider_groove": "#e5e7eb", "scrollbar": "#cbd5e1", "scrollbar_h": "#94a3b8",
    "disabled_bg": "#cbd5e1", "disabled_fg": "#f1f5f9",
    "disabled_fg2": "#9ca3af", "disabled_border": "#e5e7eb",
    "status_bg": "#ffffff", "status_border": "#eef2f7",
    "tooltip_bg": "#1f2937", "tooltip_fg": "#ffffff",
    "selection_bg": "#2563eb", "selection_fg": "#ffffff",
    "plot_bg": "#ffffff", "plot_fg": "#1f2937",
    "view_bg": "#f8f9fa", "view_edge": "#94a3b8",
    "danger": "#dc2626", "success": "#059669",
}

DARK = {
    "window": "#0f172a", "surface": "#1e293b", "surface_alt": "#334155",
    "fg": "#e2e8f0", "fg_strong": "#f8fafc", "fg_muted": "#94a3b8",
    "accent": "#60a5fa", "accent_hover": "#93c5fd",
    "grad_top": "#3b82f6", "grad_bot": "#2563eb",
    "grad_top_h": "#60a5fa", "grad_bot_h": "#3b82f6",
    "border": "#475569", "border_soft": "#334155", "divider": "#334155",
    "flat_hover_bg": "#1e3a5f", "flat_press_bg": "#1e40af",
    "menu_hover_bg": "#1e3a5f", "menu_hover_fg": "#93c5fd",
    "slider_groove": "#334155", "scrollbar": "#475569", "scrollbar_h": "#64748b",
    "disabled_bg": "#334155", "disabled_fg": "#64748b",
    "disabled_fg2": "#64748b", "disabled_border": "#334155",
    "status_bg": "#1e293b", "status_border": "#334155",
    "tooltip_bg": "#0f172a", "tooltip_fg": "#f1f5f9",
    "selection_bg": "#3b82f6", "selection_fg": "#ffffff",
    "plot_bg": "#1e293b", "plot_fg": "#cbd5e1",
    "view_bg": "#0f172a", "view_edge": "#64748b",
    "danger": "#f87171", "success": "#34d399",
}

THEMES = {"light": LIGHT, "dark": DARK}
_current = "dark"                    # dark is the default theme


# ---- persistence -----------------------------------------------------------
def _load():
    global _current
    _current = ("light" if str(_settings.get("theme", "dark")).lower() == "light"
                else "dark")


def set_theme(name: str):
    global _current
    _current = "dark" if str(name).lower() == "dark" else "light"
    _settings.set_value("theme", _current)


def get_theme() -> str:
    return _current


def is_dark() -> bool:
    return _current == "dark"


def tokens() -> dict:
    return THEMES[_current]


def c(name: str) -> str:
    return THEMES[_current][name]


# ---- Qt palette ------------------------------------------------------------
def palette():
    from PySide6.QtGui import QPalette, QColor
    t = tokens()
    pal = QPalette()
    pal.setColor(QPalette.Window, QColor(t["window"]))
    pal.setColor(QPalette.WindowText, QColor(t["fg"]))
    pal.setColor(QPalette.Base, QColor(t["surface"]))
    pal.setColor(QPalette.AlternateBase, QColor(t["surface_alt"]))
    pal.setColor(QPalette.Text, QColor(t["fg"]))
    pal.setColor(QPalette.Button, QColor(t["surface"]))
    pal.setColor(QPalette.ButtonText, QColor(t["fg"]))
    pal.setColor(QPalette.BrightText, QColor("#f87171" if is_dark() else "#dc2626"))
    pal.setColor(QPalette.ToolTipBase, QColor(t["tooltip_bg"]))
    pal.setColor(QPalette.ToolTipText, QColor(t["tooltip_fg"]))
    pal.setColor(QPalette.Highlight, QColor(t["selection_bg"]))
    pal.setColor(QPalette.HighlightedText, QColor(t["selection_fg"]))
    pal.setColor(QPalette.PlaceholderText, QColor(t["fg_muted"]))
    pal.setColor(QPalette.Link, QColor(t["accent"]))
    for grp in (QPalette.Disabled,):
        pal.setColor(grp, QPalette.Text, QColor(t["disabled_fg2"]))
        pal.setColor(grp, QPalette.ButtonText, QColor(t["disabled_fg2"]))
        pal.setColor(grp, QPalette.WindowText, QColor(t["disabled_fg2"]))
    return pal


# ---- QSS -------------------------------------------------------------------
_QSS = Template("""
* {
    font-family: "Segoe UI Variable", "Segoe UI", "San Francisco", "Roboto", sans-serif;
    font-size: 13px;
    color: $fg;
}
QMainWindow, QDialog { background: $window; }
QWidget#central { background: $window; }

QLabel#h1 { font-size: 22px; font-weight: 800; color: $fg_strong; }
QLabel#h2 { font-size: 15px; font-weight: 700; color: $fg_strong; }
QLabel#hint { color: $fg_muted; font-size: 12px; }
QLabel#metric { font-size: 22px; font-weight: 800; color: $accent; }

QPushButton {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 $grad_top, stop:1 $grad_bot);
    color: #ffffff; border: none; border-radius: 8px; padding: 9px 18px; font-weight: 600;
}
QPushButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 $grad_top_h, stop:1 $grad_bot_h);
}
QPushButton:pressed {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 $grad_bot, stop:1 $accent_hover);
}
QPushButton:disabled { background: $disabled_bg; color: $disabled_fg; }

QPushButton[flat="true"] {
    background: $surface; color: $accent; border: 1px solid $border;
    border-radius: 8px; padding: 8px 16px; font-weight: 600;
}
QPushButton[flat="true"]:hover { border: 1px solid $accent; background: $flat_hover_bg; }
QPushButton[flat="true"]:pressed { background: $flat_press_bg; }
QPushButton[flat="true"]:disabled { color: $disabled_fg2; border: 1px solid $disabled_border; background: $window; }

QLineEdit, QDoubleSpinBox, QSpinBox, QComboBox {
    background: $surface; border: 1px solid $border; border-radius: 6px;
    padding: 7px 10px; selection-background-color: $selection_bg; selection-color: $selection_fg;
}
QLineEdit:hover, QDoubleSpinBox:hover, QSpinBox:hover, QComboBox:hover { border: 1px solid $scrollbar_h; }
QLineEdit:focus, QDoubleSpinBox:focus, QSpinBox:focus, QComboBox:focus {
    border: 2px solid $accent; padding: 6px 9px;
}
QComboBox::drop-down { border: none; width: 22px; }
QComboBox QAbstractItemView {
    background: $surface; border: 1px solid $border; border-radius: 8px;
    selection-background-color: $menu_hover_bg; selection-color: $fg; outline: none;
    padding: 4px;
}
QDoubleSpinBox::up-button, QSpinBox::up-button,
QDoubleSpinBox::down-button, QSpinBox::down-button { width: 16px; border: none; background: transparent; }

QTabWidget::pane { border: none; background: transparent; top: -1px; }
QTabBar::tab {
    background: transparent; padding: 10px 20px; margin-right: 4px;
    color: $fg_muted; border: none; border-bottom: 2px solid transparent; font-weight: 600;
}
QTabBar::tab:selected { color: $accent; border-bottom: 2px solid $accent; font-weight: 700; }
QTabBar::tab:hover:!selected { color: $fg; }

QGroupBox {
    border: 1px solid $border_soft; border-radius: 10px;
    margin-top: 20px; padding: 18px 14px 16px 14px; background: $surface; font-weight: 700;
}
QGroupBox::title {
    subcontrol-origin: margin; left: 14px; top: 3px; padding: 0 6px;
    color: $fg_strong; font-weight: 700;
}

QTextEdit, QPlainTextEdit {
    background: $surface; border: 1px solid $border_soft; border-radius: 8px; padding: 8px;
}
QTableWidget, QTableView {
    background: $surface; border: 1px solid $border_soft; border-radius: 8px; gridline-color: $divider;
}
QHeaderView::section { background: $surface_alt; border: none; padding: 8px; font-weight: 700; color: $fg_strong; }

QSlider::groove:horizontal { height: 4px; background: $slider_groove; border-radius: 2px; }
QSlider::sub-page:horizontal { background: $accent; border-radius: 2px; }
QSlider::handle:horizontal { background: $accent; width: 16px; height: 16px; margin: -6px 0; border-radius: 8px; }
QSlider::handle:horizontal:hover { background: $accent_hover; }

QMenuBar { background: transparent; padding: 2px 4px; }
QMenuBar::item { padding: 6px 12px; background: transparent; border-radius: 6px; }
QMenuBar::item:selected { background: $menu_hover_bg; color: $menu_hover_fg; }
QMenu { background: $surface; border: 1px solid $border_soft; border-radius: 10px; padding: 6px; }
QMenu::item { padding: 7px 22px; border-radius: 6px; }
QMenu::item:selected { background: $menu_hover_bg; color: $menu_hover_fg; }
QMenu::separator { height: 1px; background: $divider; margin: 5px 8px; }

QStatusBar { background: $status_bg; color: $fg_muted; border-top: 1px solid $status_border; }
QScrollArea { background: transparent; border: none; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: $scrollbar; border-radius: 5px; min-height: 28px; }
QScrollBar::handle:vertical:hover { background: $scrollbar_h; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:horizontal { background: $scrollbar; border-radius: 5px; min-width: 28px; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }

QCheckBox { spacing: 8px; }
QCheckBox::indicator { width: 16px; height: 16px; border: 1px solid $border; border-radius: 5px; background: $surface; }
QCheckBox::indicator:hover { border: 1px solid $accent; }
QCheckBox::indicator:checked { background: $accent; border: 1px solid $accent; }

QToolTip { background: $tooltip_bg; color: $tooltip_fg; border: none; border-radius: 6px; padding: 6px 8px; }
""")


def stylesheet() -> str:
    return _QSS.substitute(tokens())


# ---- pyqtgraph / pyvista accessors ----------------------------------------
def plot_bg() -> str:
    return c("plot_bg")


def plot_fg() -> str:
    return c("plot_fg")


def view_bg() -> str:
    return c("view_bg")


def style_plot(pw):
    """Re-theme a pyqtgraph PlotWidget (background, axes, title) in place."""
    try:
        import pyqtgraph as pg
        fg = plot_fg()
        pw.setBackground(plot_bg())
        pi = pw.getPlotItem()
        for name in ("left", "bottom"):
            ax = pi.getAxis(name)
            ax.setPen(pg.mkPen(fg))
            ax.setTextPen(pg.mkPen(fg))
        lbl = getattr(pi, "titleLabel", None)
        if lbl is not None and getattr(lbl, "text", ""):
            pi.setTitle(lbl.text, color=fg)
    except Exception:  # noqa: BLE001
        pass


def apply(app):
    """Apply the current theme to a QApplication (style + palette + QSS)."""
    app.setStyle("Fusion")
    app.setPalette(palette())
    app.setStyleSheet(stylesheet())
    try:
        import pyqtgraph as pg
        pg.setConfigOption("background", plot_bg())
        pg.setConfigOption("foreground", plot_fg())
        pg.setConfigOption("antialias", True)
    except Exception:  # noqa: BLE001
        pass


_load()
