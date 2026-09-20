"""Reporter interface: how the core talks to any front-end.

The core never calls print()/sys.exit()/input() and never installs signal
handlers. Front-ends subclass Reporter:
- the CLI adapter reproduces the historic console output byte-for-byte;
- the GUI bridges the callbacks to Qt signals in a worker thread.
"""
from dataclasses import dataclass, field
from enum import Enum, auto

import numpy as np


class SessionState(Enum):
    IDLE = auto()
    STARTING = auto()
    ARMING = auto()
    CALIBRATING = auto()
    LOGGING = auto()
    FIRE_PENDING = auto()   # stabilized, waiting for the GUI's FIRE permission
    FIRED = auto()
    STOPPING = auto()
    DONE = auto()
    ABORTED = auto()
    INHIBITED = auto()      # safety failsafe blocked ignition
    ERROR = auto()


@dataclass
class SampleBlock:
    """One AI chunk — the unit the live plot consumes. ``ai`` is copied at emit."""
    t0: float                       # chunk start, epoch seconds
    period: float                   # 1 / rate
    ai: np.ndarray                  # (n_channels, n_samples) float64
    di: list[int] = field(default_factory=list)  # static snapshot per chunk


@dataclass
class CalibRow:
    """One calibration screen line (moving averages etc.)."""
    ts_iso: str
    averages: list[float]
    raw: list[float] | None = None  # set when show_raw
    di: list[int] = field(default_factory=list)


@dataclass
class SessionResult:
    samples_total: int = 0
    output_path: object = None      # Path | None
    recovery_path: object = None    # Path | None
    state: SessionState = SessionState.DONE


class Reporter:
    """No-op callback base class; override what the front-end cares about."""

    def on_state(self, state: SessionState, detail: dict | None = None) -> None:
        """Session lifecycle transitions (also carries e.g. arming current)."""

    def on_status(self, text: str) -> None:
        """Human-readable status line (exact historic CLI text)."""

    def on_sample_block(self, block: SampleBlock) -> None:
        """One chunk of AI (+ DI snapshot) data."""

    def on_row_preview(self, row: list) -> None:
        """One of the first N logged rows (--print-first)."""

    def on_calib_header(self, columns: list[str]) -> None:
        """Calibration screen header."""

    def on_calib_row(self, row: CalibRow) -> None:
        """One calibration output line."""

    def on_progress(self, samples_total: int, ch_count: int,
                    elapsed: float, inst_rate: float) -> None:
        """Periodic logging progress (every cfg.update_interval)."""

    def on_arming(self, remaining: float, current_ma: float | None) -> None:
        """Arming countdown tick (~sense_rate Hz); current None without sensing."""

    def on_error(self, exc: BaseException) -> None:
        """Non-fatal error report."""
