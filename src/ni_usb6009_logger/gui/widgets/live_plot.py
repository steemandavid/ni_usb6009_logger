"""Live plot: preallocated ring buffers per channel, ~10 Hz throttled repaint.

One curve per AI channel; PyQtGraph's peak downsampling + clip-to-view keeps
1 kHz multi-channel streaming smooth. Memory is bounded by the buffer
capacity regardless of run length.
"""
import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QVBoxLayout, QWidget

pg.setConfigOptions(antialias=False, background="w", foreground="k")

_WINDOW_SECONDS = 60.0
_COLORS = ["#1f77b4", "#d62728", "#2ca02c", "#9467bd",
           "#ff7f0e", "#8c564b", "#e377c2", "#7f7f7f"]


class _Ring:
    """Fixed-capacity float64 ring buffer with an ordered snapshot view."""

    def __init__(self, capacity: int):
        self.buf = np.zeros(capacity, dtype=np.float64)
        self.t = np.zeros(capacity, dtype=np.float64)
        self.capacity = capacity
        self.start = 0
        self.size = 0

    def append(self, t_arr: np.ndarray, v_arr: np.ndarray):
        n = len(v_arr)
        if n >= self.capacity:
            v_arr, t_arr = v_arr[-self.capacity:], t_arr[-self.capacity:]
            n = self.capacity
        w = (self.start + self.size) % self.capacity
        first = min(n, self.capacity - w)
        self.buf[w:w + first] = v_arr[:first]
        self.t[w:w + first] = t_arr[:first]
        rest = n - first
        if rest:
            self.buf[:rest] = v_arr[first:]
            self.t[:rest] = t_arr[first:]
        if self.size + n > self.capacity:
            self.start = (self.start + self.size + n - self.capacity) % self.capacity
        self.size = min(self.size + n, self.capacity)

    def snapshot(self):
        if self.size == 0:
            return self.t[:0], self.buf[:0]
        end = self.start + self.size
        if end <= self.capacity:
            return self.t[self.start:end], self.buf[self.start:end]
        t = np.concatenate((self.t[self.start:], self.t[:end - self.capacity]))
        v = np.concatenate((self.buf[self.start:], self.buf[:end - self.capacity]))
        return t, v


class LivePlot(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._channels = []
        self._rings = []
        self._curves = []
        self._t0 = None
        self._dirty = False

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)

        self.plot = pg.PlotWidget()
        self.plot.addLegend(offset=(10, 10))
        self.plot.setLabel("left", "Voltage", units="V")
        self.plot.setLabel("bottom", "Time", units="s")
        self.plot.setDownsampling(auto=True, mode="peak")
        self.plot.setClipToView(True)
        self.plot.showGrid(x=True, y=True, alpha=0.25)
        lay.addWidget(self.plot, 1)

        self._legend_toggle = QComboBox()
        self._legend_toggle.addItems(["pause view", "follow live"])
        self._legend_toggle.currentIndexChanged.connect(self._on_follow)
        top = QHBoxLayout()
        top.addStretch(1)
        view_label = QLabel("view:")
        view_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        top.addWidget(view_label)
        top.addWidget(self._legend_toggle)
        lay.addLayout(top)

        self._follow = True
        self._timer = QTimer(self)
        self._timer.setInterval(100)  # ~10 Hz repaint
        self._timer.timeout.connect(self._repaint)

    def start(self, channels: list[str], rate: float, chunk: int):
        """Configure for a new run and begin repainting."""
        self.stop()
        self._channels = list(channels)
        capacity = max(int(rate * _WINDOW_SECONDS), chunk * 4)
        self._rings = [_Ring(capacity) for _ in self._channels]
        self.plot.clear()
        self.plot.getPlotItem().legend.items = []
        self._curves = []
        for i, name in enumerate(self._channels):
            c = self.plot.plot(pen=pg.mkPen(_COLORS[i % len(_COLORS)], width=1), name=name)
            self._curves.append(c)
        self._t0 = None
        self._dirty = False
        self._legend_toggle.setCurrentIndex(1)
        self._follow = True
        self._timer.start()

    def stop(self):
        self._timer.stop()
        self._repaint()

    def clear(self):
        self._channels, self._rings, self._curves = [], [], []
        self.plot.clear()
        self.plot.getPlotItem().legend.items = []
        self._t0 = None

    def append_block(self, block):
        """Queue one SampleBlock; drain on the next repaint tick."""
        if not self._rings:
            return
        if self._t0 is None:
            self._t0 = block.t0
        n = block.ai.shape[1]
        t_rel = (block.t0 - self._t0) + np.arange(n) * block.period
        for i, ring in enumerate(self._rings):
            ring.append(t_rel, block.ai[i])
        self._dirty = True

    def _on_follow(self, index):
        self._follow = index == 1

    def _repaint(self):
        if not self._dirty or not self._curves:
            return
        self._dirty = False
        for curve, ring in zip(self._curves, self._rings):
            t, v = ring.snapshot()
            curve.setData(t, v)
        if self._follow:
            self.plot.enableAutoRange(x=True, y=True)
