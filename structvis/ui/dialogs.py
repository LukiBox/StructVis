"""Welcome / About dialogs and branding constants."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QCheckBox)

from ..core.i18n import t
from .. import __version__
from . import theme

AUTHOR = "LukiBox"
GITHUB = "https://github.com/LukiBox"
FLOVIS_URL = "https://github.com/LukiBox/Flovis"


def author_html(size: int = 8) -> str:
    return (f'<span style="color:{theme.c("fg_muted")}; font-size:{size}pt;">'
            f'Made by <b>{AUTHOR}</b> &nbsp;•&nbsp; '
            f'<a href="{GITHUB}" style="color:{theme.c("accent")};">'
            f'github.com/LukiBox</a></span>')


class WelcomeDialog(QDialog):
    """Startup screen: explains the Flovis dependency up front."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("Welcome to StructVis"))
        self.setMinimumWidth(560)
        self.dont_show = False
        self.start_import = False

        v = QVBoxLayout(self)
        title = QLabel("StructVis"); title.setObjectName("h1")
        v.addWidget(title)
        sub = QLabel(t("Parametric wingbox generator · FEA stress viewer"))
        sub.setObjectName("hint")
        v.addWidget(sub)
        v.addSpacing(6)

        warn = QLabel(
            t("<b>StructVis analyzes wings designed in Flovis.</b><br><br>"
              "To see and analyze a wing, it needs a <b>.flovis</b> project "
              "file that already contains a <b>detailed aerodynamic analysis</b> "
              "(geometry + a solved polar). StructVis reads the wing shape and "
              "the aerodynamic loads from that file and wraps your internal "
              "structure around them.<br><br>"
              "Without a proper Flovis analysis there is no wing for StructVis "
              "to work on. Design and analyze your wing in Flovis first, save "
              "the project, then import it here."))
        warn.setWordWrap(True)
        warn.setStyleSheet(
            f"background:{theme.c('menu_hover_bg')}; "
            f"border:1px solid {theme.c('border')}; border-radius:8px;"
            f"padding:12px; color:{theme.c('fg')};")
        v.addWidget(warn)

        link = QLabel(
            t('Need Flovis? Get it here: '
              '<a href="{u}" style="color:{c};">{u}</a>').format(
                u=FLOVIS_URL, c=theme.c("accent")))
        link.setOpenExternalLinks(True); link.setTextFormat(Qt.RichText)
        v.addWidget(link)
        v.addSpacing(8)

        row = QHBoxLayout()
        self.cb = QCheckBox(t("Don't show this again"))
        row.addWidget(self.cb); row.addStretch()
        b_import = QPushButton(t("Import a .flovis file..."))
        b_import.clicked.connect(self._do_import)
        b_close = QPushButton(t("Explore first")); b_close.setProperty("flat", True)
        b_close.clicked.connect(self.accept)
        row.addWidget(b_close); row.addWidget(b_import)
        v.addLayout(row)

        credit = QLabel(author_html()); credit.setOpenExternalLinks(True)
        credit.setTextFormat(Qt.RichText); credit.setAlignment(Qt.AlignRight)
        v.addWidget(credit)

    def _do_import(self):
        self.start_import = True
        self.accept()

    def accept(self):
        self.dont_show = self.cb.isChecked()
        super().accept()


class AboutDialog(QDialog):
    def __init__(self, parent=None, solver_info: str = ""):
        super().__init__(parent)
        self.setWindowTitle(t("About StructVis"))
        self.setMinimumWidth(480)
        v = QVBoxLayout(self)
        title = QLabel(f"StructVis {__version__}"); title.setObjectName("h1")
        v.addWidget(title)
        v.addWidget(QLabel(t("Parametric wingbox generator · FEA stress viewer.")))
        body = QLabel(
            t("A companion to <b>Flovis</b>: it imports your Flovis wing and "
              "aerodynamic loads, builds a parametric internal structure, and "
              "solves it with the open-source <b>CalculiX</b> shell FEA solver. "
              "Von Mises stress and deflection are shown as 3D heatmaps "
              "(blue = safe, red = at yield).<br><br>"
              "Built to be far simpler than a general-purpose FEM package: no "
              "meshing, no boundary-condition setup - just sliders."))
        body.setWordWrap(True); body.setTextFormat(Qt.RichText)
        v.addWidget(body)
        if solver_info:
            si = QLabel(solver_info); si.setObjectName("hint"); si.setWordWrap(True)
            v.addWidget(si)
        v.addSpacing(6)
        acc, mut = theme.c("accent"), theme.c("fg_muted")
        links = QLabel(
            f'<b>Made by {AUTHOR}</b><br>'
            f'GitHub: <a href="{GITHUB}" style="color:{acc};">{GITHUB}</a><br>'
            f'Flovis: <a href="{FLOVIS_URL}" style="color:{acc};">{FLOVIS_URL}</a><br><br>'
            f'<span style="color:{mut};">Solver: CalculiX (GPLv2) · '
            f'UI: PySide6 + PyVista · StructVis is MIT-licensed.</span>')
        links.setOpenExternalLinks(True); links.setTextFormat(Qt.RichText)
        links.setWordWrap(True)
        v.addWidget(links)
        b = QPushButton(t("Close")); b.clicked.connect(self.accept)
        v.addWidget(b, alignment=Qt.AlignRight)


def wrong_file_message() -> str:
    """Body text when a non-.flovis file is dropped/opened."""
    return t(
        "This is not a Flovis project.<br><br>"
        "StructVis can only analyze wings created and analyzed in <b>Flovis</b>, "
        "imported as a <b>.flovis</b> file. That file carries the wing geometry "
        "and the aerodynamic loads StructVis needs.<br><br>"
        "Create your wing in Flovis, run an analysis, and save it as .flovis "
        "first.<br><br>"
        'Get Flovis: <a href="{u}" style="color:{c};">{u}</a>').format(
            u=FLOVIS_URL, c=theme.c("accent"))
