"""A labelled slider + spinbox combo that emits a float value."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QWidget, QGridLayout, QLabel, QSlider,
                               QDoubleSpinBox, QSpinBox)


class FloatSlider(QWidget):
    """Slider bound to a QDoubleSpinBox; value in engineering units."""
    changed = Signal(float)

    def __init__(self, label: str, minimum: float, maximum: float,
                 value: float, step: float = 0.1, decimals: int = 2,
                 suffix: str = "", parent=None):
        super().__init__(parent)
        self._min, self._max, self._step = minimum, maximum, step
        self._n = max(int(round((maximum - minimum) / step)), 1)

        g = QGridLayout(self)
        g.setContentsMargins(2, 6, 2, 10)
        g.setHorizontalSpacing(12)
        g.setVerticalSpacing(7)
        self.lbl = QLabel(label)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, self._n)
        self.spin = QDoubleSpinBox()
        self.spin.setRange(minimum, maximum)
        self.spin.setDecimals(decimals)
        self.spin.setSingleStep(step)
        self.spin.setSuffix(suffix)
        self.spin.setFixedWidth(100)

        g.addWidget(self.lbl, 0, 0)
        g.addWidget(self.spin, 0, 1)
        g.addWidget(self.slider, 1, 0, 1, 2)

        self.set_value(value)
        self.slider.valueChanged.connect(self._from_slider)
        self.spin.valueChanged.connect(self._from_spin)

    def _to_slider(self, v: float) -> int:
        return int(round((v - self._min) / self._step))

    def set_value(self, v: float):
        v = min(max(v, self._min), self._max)
        self.spin.blockSignals(True); self.slider.blockSignals(True)
        self.spin.setValue(v)
        self.slider.setValue(self._to_slider(v))
        self.spin.blockSignals(False); self.slider.blockSignals(False)

    def value(self) -> float:
        return self.spin.value()

    def _from_slider(self, i: int):
        v = self._min + i * self._step
        self.spin.blockSignals(True)
        self.spin.setValue(v)
        self.spin.blockSignals(False)
        self.changed.emit(v)

    def _from_spin(self, v: float):
        self.slider.blockSignals(True)
        self.slider.setValue(self._to_slider(v))
        self.slider.blockSignals(False)
        self.changed.emit(v)


class IntSlider(QWidget):
    changed = Signal(int)

    def __init__(self, label: str, minimum: int, maximum: int, value: int,
                 suffix: str = "", parent=None):
        super().__init__(parent)
        g = QGridLayout(self)
        g.setContentsMargins(2, 6, 2, 10)
        g.setHorizontalSpacing(12)
        g.setVerticalSpacing(7)
        self.lbl = QLabel(label)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(minimum, maximum)
        self.spin = QSpinBox()
        self.spin.setRange(minimum, maximum)
        self.spin.setSuffix(suffix)
        self.spin.setFixedWidth(100)
        g.addWidget(self.lbl, 0, 0)
        g.addWidget(self.spin, 0, 1)
        g.addWidget(self.slider, 1, 0, 1, 2)
        self.set_value(value)
        self.slider.valueChanged.connect(self._sync_spin)
        self.spin.valueChanged.connect(self._sync_slider)

    def set_value(self, v: int):
        self.spin.blockSignals(True); self.slider.blockSignals(True)
        self.spin.setValue(v); self.slider.setValue(v)
        self.spin.blockSignals(False); self.slider.blockSignals(False)

    def value(self) -> int:
        return self.spin.value()

    def _sync_spin(self, i: int):
        self.spin.blockSignals(True); self.spin.setValue(i)
        self.spin.blockSignals(False); self.changed.emit(i)

    def _sync_slider(self, i: int):
        self.slider.blockSignals(True); self.slider.setValue(i)
        self.slider.blockSignals(False); self.changed.emit(i)
