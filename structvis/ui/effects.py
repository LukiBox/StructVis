"""
Miekkie cienie (QGraphicsDropShadowEffect) dla paneli - efekt "unoszenia".

UWAGA: efekt graficzny wymusza rasteryzacje calego poddrzewa widgetu, co psuje
renderery sprzetowe (VTK/OpenGL) i bywa problematyczne dla pyqtgraph/matplotlib.
Dlatego cienie nakladamy tylko na panele sterowania (formularze, przyciski),
a pomijamy panele zawierajace ciezkie widoki (wykresy, edytor, widok 3D).
"""
from __future__ import annotations

from PySide6.QtWidgets import QGraphicsDropShadowEffect, QGroupBox, QWidget
from PySide6.QtGui import QColor

# nazwy klas widgetow, nad ktorymi NIE wolno zakladac efektu graficznego
_HEAVY = ("QtInteractor", "QVTKRenderWindowInteractor", "QOpenGLWidget",
          "GLViewWidget", "FigureCanvas", "PlotWidget", "GraphicsLayoutWidget",
          "GraphicsView")


def apply_shadow(widget: QWidget, blur: int = 22, dy: int = 3, alpha: int = 36):
    eff = QGraphicsDropShadowEffect(widget)
    eff.setBlurRadius(blur)
    eff.setXOffset(0)
    eff.setYOffset(dy)
    eff.setColor(QColor(15, 23, 42, alpha))
    widget.setGraphicsEffect(eff)


def _has_heavy_child(widget: QWidget) -> bool:
    for child in widget.findChildren(QWidget):
        if type(child).__name__ in _HEAVY:
            return True
    return False


def apply_panel_shadows(root: QWidget):
    """Apply a soft shadow to every card panel (QGroupBox) without heavy views."""
    for gb in root.findChildren(QGroupBox):
        if not _has_heavy_child(gb):
            apply_shadow(gb)
