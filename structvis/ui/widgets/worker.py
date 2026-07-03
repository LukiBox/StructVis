"""Generic QThread worker: run a callable off the UI thread with signals."""
from __future__ import annotations

from PySide6.QtCore import QThread, Signal


class Worker(QThread):
    """Runs fn(*args, progress=..., log=...) and emits done/failed."""
    done = Signal(object)
    failed = Signal(str)
    log = Signal(str)
    progress = Signal(object)

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs

    def run(self):
        try:
            # inject optional callbacks the target may accept
            import inspect
            params = inspect.signature(self._fn).parameters
            if "log_cb" in params:
                self._kwargs.setdefault("log_cb", self.log.emit)
            if "progress" in params:
                self._kwargs.setdefault("progress", self.progress.emit)
            result = self._fn(*self._args, **self._kwargs)
            self.done.emit(result)
        except Exception as e:  # noqa: BLE001
            import traceback
            self.failed.emit(f"{e}\n\n{traceback.format_exc()}")
