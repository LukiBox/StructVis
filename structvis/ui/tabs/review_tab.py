"""Tab 5: AI structural review via a local Ollama model (streaming)."""
from __future__ import annotations

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QGroupBox,
                               QPushButton, QLabel, QComboBox, QTextEdit,
                               QMessageBox, QCheckBox)

from ...core.i18n import t
from .. import theme
from ...core.ai import review
from ...core.mass import mass_breakdown


class _ReviewStream(QThread):
    chunk = Signal(str, str)        # (kind, text)
    done = Signal()
    failed = Signal(str)

    def __init__(self, payload, model, preset, think=False):
        super().__init__()
        self.payload, self.model, self.preset = payload, model, preset
        self.think = think

    def run(self):
        try:
            for kind, text in review.interpret_stream(
                    self.payload, model=self.model, preset=self.preset,
                    think=self.think):
                self.chunk.emit(kind, text)
            self.done.emit()
        except Exception as e:  # noqa: BLE001
            self.failed.emit(str(e))


class ReviewTab(QWidget):
    def __init__(self, app_state):
        super().__init__()
        self.state = app_state
        self._stream = None
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        bar = QHBoxLayout()
        self.preset_cb = QComboBox()
        for key, (label, _) in review.PRESETS.items():
            self.preset_cb.addItem(t(label), key)
        bar.addWidget(QLabel(t("Review type:")))
        bar.addWidget(self.preset_cb)
        self.model_cb = QComboBox(); self.model_cb.setEditable(True)
        self.model_cb.setMinimumWidth(220)
        bar.addWidget(QLabel(t("Model:")))
        bar.addWidget(self.model_cb)
        self.cb_think = QCheckBox(t("Show reasoning (slower)"))
        self.cb_think.setToolTip(t(
            "Reasoning models (e.g. qwen3) think before answering. Leave off "
            "for a fast, direct review; turn on to see the model's reasoning."))
        bar.addWidget(self.cb_think)
        self.b_run = QPushButton(t("Generate review"))
        self.b_run.clicked.connect(self._run)
        bar.addWidget(self.b_run)
        bar.addStretch()
        root.addLayout(bar)

        self.status = QLabel(""); self.status.setObjectName("hint")
        self.status.setWordWrap(True)
        root.addWidget(self.status)

        self.think = QTextEdit(); self.think.setReadOnly(True)
        self.think.setMaximumHeight(90)
        self._style_think()
        self.think.setPlaceholderText(t("(model reasoning appears here when enabled)"))
        self.think.setVisible(False)
        root.addWidget(self.think)

        self.out = QTextEdit(); self.out.setReadOnly(True)
        root.addWidget(self.out, 1)
        self._refresh_models()

    def _refresh_models(self):
        self.model_cb.clear()
        if not review.is_available():
            self.status.setText(t("Ollama not reachable at localhost:11434 - "
                                  "start it with 'ollama serve'."))
            self.model_cb.addItem(review.DEFAULT_MODEL)
            return
        models = review.list_models()
        if models:
            self.model_cb.addItems(models)
            idx = self.model_cb.findText(review.DEFAULT_MODEL)
            if idx >= 0:
                self.model_cb.setCurrentIndex(idx)
        else:
            self.model_cb.addItem(review.DEFAULT_MODEL)
        self.status.setText(t("Ollama ready."))

    def _run(self):
        if self.state.result is None:
            QMessageBox.information(self, t("No results"),
                                    t("Run an analysis first.")); return
        if not review.is_available():
            QMessageBox.warning(self, t("Ollama unavailable"),
                                review.missing_model_hint(self.model_cb.currentText()))
            return
        mb = None
        if self.state.mesh is not None:
            mb = mass_breakdown(self.state.mesh, self.state.params, half_wing=False)
        payload = review.build_context(
            self.state.result, self.state.params, self.state.load_case,
            design=self.state.design, mass_breakdown=mb,
            buckling=self.state.buckling)

        self.out.clear(); self.think.clear()
        think = self.cb_think.isChecked()
        self.think.setVisible(think)
        self._got_output = False
        self.status.setText(t(
            "Contacting the model... the first run loads it into memory and "
            "can take ~30 s for a large model. Please wait."))
        self.b_run.setEnabled(False)
        self._stream = _ReviewStream(payload, self.model_cb.currentText(),
                                     self.preset_cb.currentData(), think=think)
        self._stream.chunk.connect(self._on_chunk)
        self._stream.done.connect(self._on_done)
        self._stream.failed.connect(self._on_failed)
        self._stream.start()

    def _on_chunk(self, kind, text):
        from PySide6.QtGui import QTextCursor
        if not self._got_output:
            self._got_output = True
            self.status.setText(t("Generating review..."))
        target = self.think if kind == "thinking" else self.out
        target.moveCursor(QTextCursor.End)
        target.insertPlainText(text)
        target.moveCursor(QTextCursor.End)

    def _on_done(self):
        self.b_run.setEnabled(True)
        self.status.setText(t("Review complete."))
        # make the review available to the PDF report
        self.state.ai_review_text = self.out.toPlainText().strip() or None

    def _on_failed(self, msg):
        self.b_run.setEnabled(True)
        self.status.setText(t("Failed: ") + msg)

    def _style_think(self):
        self.think.setStyleSheet(
            f"color:{theme.c('fg_muted')}; font-style:italic;")

    def refresh_theme(self):
        self._style_think()
