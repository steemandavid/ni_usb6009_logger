"""Worker thread: runs a core session and bridges Reporter calls to Qt signals.

The worker never touches widgets. Signals cross into the GUI thread via
queued connections; ``sample_block`` carries a SampleBlock whose ``ai`` array
was already copied at emit time in the core.
"""
import threading

from PySide6.QtCore import QThread, Signal

from ni_usb6009_logger.core.events import (
    CalibRow,
    Reporter,
    SampleBlock,
    SessionState,
)


class _QtReporter(Reporter):
    """Forwards core callbacks to the worker's signals (queued to GUI thread)."""

    def __init__(self, sig):
        self._sig = sig

    def on_state(self, state: SessionState, detail=None):
        self._sig.state_changed.emit(state, detail or {})

    def on_status(self, text: str):
        self._sig.status_text.emit(text)

    def on_sample_block(self, block: SampleBlock):
        self._sig.sample_block.emit(block)

    def on_row_preview(self, row: list):
        self._sig.row_preview.emit(row)

    def on_calib_header(self, columns):
        self._sig.calib_header.emit(list(columns))

    def on_calib_row(self, row: CalibRow):
        self._sig.calib_row.emit(row)

    def on_progress(self, samples_total, ch_count, elapsed, inst_rate):
        self._sig.progress_info.emit(samples_total, ch_count, elapsed, inst_rate)

    def on_arming(self, remaining, current_ma):
        self._sig.arming.emit(remaining, current_ma)

    def on_error(self, exc):
        self._sig.error_text.emit(f"{type(exc).__name__}: {exc}")


class SessionWorker(QThread):
    state_changed = Signal(object, dict)   # SessionState, detail
    status_text = Signal(str)
    sample_block = Signal(object)          # SampleBlock
    row_preview = Signal(list)
    calib_header = Signal(list)
    calib_row = Signal(object)             # CalibRow
    progress_info = Signal(int, int, float, float)
    arming = Signal(float, object)         # remaining s, current mA | None
    error_text = Signal(str)
    finished_result = Signal(object)       # SessionResult

    def __init__(self, session_factory, parent=None):
        super().__init__(parent)
        self._factory = session_factory
        self._stop = threading.Event()
        self._fire = threading.Event()

    def run(self):
        reporter = _QtReporter(self)
        session = self._factory(reporter)
        try:
            result = session.run(stop=self._stop, fire_permission=self._fire)
            self.finished_result.emit(result)
        except Exception as e:  # surfaced as a friendly dialog by the window
            self.error_text.emit(f"{type(e).__name__}: {e}")

    # -- controls (thread-safe) --
    def request_stop(self):
        self._stop.set()

    def request_fire(self):
        self._fire.set()
