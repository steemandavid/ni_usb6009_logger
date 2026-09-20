"""Main window: config panel, Log / Calibrate / Ignite / Recovery tabs.

Phase 3 skeleton: device auto-detection with continuous monitoring, graceful
error dialogs, output-file-first flow with recovery dual-write, and Start/Stop
via the worker thread. Live plotting (Phase 4) and the ignition ARM/FIRE
panel (Phase 5) plug into the same signals.
"""
import time

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

import ni_usb6009_logger
from ni_usb6009_logger.core import daq
from ni_usb6009_logger.core.config import (
    CalibrationConfig,
    ConfigError,
    IgnitionConfig,
    LoggerConfig,
)
from ni_usb6009_logger.core.events import SessionState
from ni_usb6009_logger.core.helpers import expand_digital_spec
from ni_usb6009_logger.gui import settings as gsettings
from ni_usb6009_logger.gui.widgets.device_picker import DevicePicker
from ni_usb6009_logger.gui.worker import SessionWorker

DEVICE_POLL_MS = 2000


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"NI USB-6009 Logger — v{ni_usb6009_logger.__version__}")
        self.cfg = gsettings.load_config()
        self.worker = None
        self._session_kind = "log"
        self._device_present = False
        self.interactive = True  # False (CI/offscreen): log instead of dialogs

        self._build_ui()
        self._load_panel_from_config()

        # Continuous device monitoring
        self._device_timer = QTimer(self)
        self._device_timer.setInterval(DEVICE_POLL_MS)
        self._device_timer.timeout.connect(self._poll_devices)
        self._device_timer.start()
        self.device_picker.rescan()

    # ------------------------------------------------------------------- UI
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._build_config_panel())
        splitter.addWidget(self._build_right_side())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter, 1)

        self.statusBar().showMessage("Ready")

    def _build_config_panel(self) -> QWidget:
        panel = QWidget()
        form = QFormLayout(panel)

        self.device_picker = DevicePicker()
        self.device_picker.devices_changed.connect(self._on_devices_changed)
        form.addRow("DAQ device", self.device_picker)

        self.channels_edit = QLineEdit("ai0")
        self.channels_edit.setToolTip("Comma-separated AI channels, e.g. ai0,ai1")
        form.addRow("AI channels", self.channels_edit)

        self.digital_edit = QLineEdit()
        self.digital_edit.setToolTip("Optional DI lines, e.g. port0/line0:7")
        form.addRow("DI lines", self.digital_edit)

        self.rate_spin = self._spin(1.0, 48000.0, 1000.0, 1.0, " Hz")
        form.addRow("Sample rate", self.rate_spin)

        self.chunk_spin = self._spin(1, 100000, 1000, 1, "")
        self.chunk_spin.setToolTip("Samples per read; lower = more frequent DI snapshots")
        form.addRow("Chunk size", self.chunk_spin)

        self.term_combo = QComboBox()
        self.term_combo.addItems(["RSE", "NRSE", "DIFF"])
        form.addRow("Term config", self.term_combo)

        range_box = QHBoxLayout()
        self.vmin_spin = self._spin(-10.0, 10.0, -10.0, 0.5, " V")
        self.vmax_spin = self._spin(-10.0, 10.0, 10.0, 0.5, " V")
        range_box.addWidget(self.vmin_spin)
        range_box.addWidget(QLabel("to"))
        range_box.addWidget(self.vmax_spin)
        form.addRow("AI range", range_box)

        self.duration_spin = self._spin(0.0, 100000.0, 0.0, 1.0, " s")
        self.duration_spin.setSpecialValueText("run until Stop")
        self.duration_spin.setToolTip("0 = run until you press Stop")
        form.addRow("Duration", self.duration_spin)

        return panel

    def _build_right_side(self) -> QWidget:
        tabs = QTabWidget()
        tabs.addTab(self._build_log_tab(), "Log")
        tabs.addTab(self._build_calibrate_tab(), "Calibrate")
        tabs.addTab(self._build_ignite_tab(), "Ignite")
        tabs.addTab(self._build_recovery_tab(), "Recovery")
        self.tabs = tabs

        holder = QWidget()
        lay = QVBoxLayout(holder)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(tabs)
        return holder

    def _build_log_tab(self) -> QWidget:
        tab = QWidget()
        lay = QVBoxLayout(tab)

        file_box = QGroupBox("Output file (required before starting)")
        fform = QFormLayout(file_box)
        row = QHBoxLayout()
        self.outfile_edit = QLineEdit()
        self.outfile_edit.setReadOnly(True)
        self.outfile_edit.setPlaceholderText("Click Browse to choose where the data is saved…")
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._choose_outfile)
        row.addWidget(self.outfile_edit, 1)
        row.addWidget(browse)
        fform.addRow(row)
        lay.addWidget(file_box)

        self.log_message = QLabel("Pick an output file, then press Start.")
        lay.addWidget(self.log_message)

        from ni_usb6009_logger.gui.widgets.live_plot import LivePlot
        self.log_plot = LivePlot()
        lay.addWidget(self.log_plot, 3)

        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMaximumBlockCount(2000)
        lay.addWidget(self.log_output, 1)

        btns = QHBoxLayout()
        self.log_start = QPushButton("Start")
        self.log_start.setEnabled(False)
        self.log_start.clicked.connect(self._start_logging)
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop_session)
        btns.addWidget(self.log_start)
        btns.addWidget(self.stop_btn)
        btns.addStretch(1)
        lay.addLayout(btns)
        return tab

    def _build_calibrate_tab(self) -> QWidget:
        tab = QWidget()
        lay = QVBoxLayout(tab)

        controls = QFormLayout()
        self.calib_window_spin = self._spin(0.0, 300.0, 5.0, 1.0, " s")
        controls.addRow("Moving-average window", self.calib_window_spin)
        self.calib_rate_spin = self._spin(0.1, 50.0, 1.0, 0.5, " Hz")
        controls.addRow("Screen output rate", self.calib_rate_spin)
        self.calib_hw_spin = self._spin(1.0, 1000.0, 100.0, 10.0, " Hz")
        controls.addRow("Internal sample rate", self.calib_hw_spin)
        lay.addLayout(controls)

        # Big numeric readouts, one per channel, refreshed at the output rate
        self.calib_readout = QLabel("—")
        self.calib_readout.setAlignment(Qt.AlignCenter)
        font = self.calib_readout.font()
        font.setPointSize(font.pointSize() + 6)
        self.calib_readout.setFont(font)
        lay.addWidget(self.calib_readout)

        from ni_usb6009_logger.gui.widgets.live_plot import LivePlot
        self.calib_plot = LivePlot()
        lay.addWidget(self.calib_plot, 1)

        btns = QHBoxLayout()
        self.calib_start = QPushButton("Start calibration")
        self.calib_start.clicked.connect(self._start_calibration)
        self.calib_stop = QPushButton("Stop")
        self.calib_stop.setEnabled(False)
        self.calib_stop.clicked.connect(self._stop_session)
        btns.addWidget(self.calib_start)
        btns.addWidget(self.calib_stop)
        btns.addStretch(1)
        lay.addLayout(btns)
        return tab

    def _build_ignite_tab(self) -> QWidget:
        tab = QWidget()
        lay = QVBoxLayout(tab)
        form = QFormLayout()
        self.ign_buzzer_edit = QLineEdit("port1/line1")
        form.addRow("Buzzer DO line", self.ign_buzzer_edit)
        self.ign_relay_edit = QLineEdit("port1/line0")
        form.addRow("Igniter relay DO line", self.ign_relay_edit)
        self.ign_sense_edit = QLineEdit("ai2")
        form.addRow("Current-sense AI", self.ign_sense_edit)
        self.ign_shunt_spin = self._spin(0.01, 10.0, 1.0, 0.1, " Ω")
        form.addRow("Shunt resistance", self.ign_shunt_spin)
        self.ign_arm_spin = self._spin(1.0, 120.0, 15.0, 1.0, " s")
        form.addRow("Buzzer warning time", self.ign_arm_spin)
        self.ign_stab_spin = self._spin(0.0, 60.0, 1.0, 0.5, " s")
        form.addRow("Stabilize time", self.ign_stab_spin)
        self.ign_pulse_spin = self._spin(0.1, 10.0, 1.0, 0.1, " s")
        form.addRow("Relay pulse time", self.ign_pulse_spin)
        lay.addLayout(form)
        note = QLabel("Full ARM / FIRE safety controls are being finalized.\n"
                      "Until then, run ignition tests with the command line.")
        note.setWordWrap(True)
        lay.addWidget(note)
        lay.addStretch(1)
        return tab

    def _build_recovery_tab(self) -> QWidget:
        tab = QWidget()
        lay = QVBoxLayout(tab)
        hint = QLabel("Recovery copies are written in parallel with every test.\n"
                      "Files ending in _OK completed cleanly; others were interrupted.")
        hint.setWordWrap(True)
        lay.addWidget(hint)
        self.recovery_list = QListWidget()
        lay.addWidget(self.recovery_list, 1)
        btns = QHBoxLayout()
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self._refresh_recovery)
        copy = QPushButton("Copy to…")
        copy.clicked.connect(self._copy_recovery)
        btns.addWidget(refresh)
        btns.addWidget(copy)
        btns.addStretch(1)
        lay.addLayout(btns)
        return tab

    @staticmethod
    def _spin(lo, hi, val, step, suffix):
        s = QDoubleSpinBox()
        s.setRange(lo, hi)
        s.setValue(val)
        s.setDecimals(2 if isinstance(step, float) and step < 1 else 1)
        s.setSingleStep(step)
        if suffix:
            s.setSuffix(suffix)
        return s

    # ------------------------------------------------------------ config IO
    def _load_panel_from_config(self):
        c = self.cfg
        self.channels_edit.setText(",".join(c.channels))
        self.digital_edit.setText(",".join(c.digital_lines))
        self.rate_spin.setValue(c.rate)
        self.chunk_spin.setValue(c.chunk)
        self.term_combo.setCurrentText(c.term)
        self.vmin_spin.setValue(c.vmin)
        self.vmax_spin.setValue(c.vmax)
        self.duration_spin.setValue(c.duration if c.duration else 0.0)
        if c.outfile:
            self.outfile_edit.setText(str(c.outfile))
        if c.calibration:
            self.calib_window_spin.setValue(c.calibration.window_seconds)
            self.calib_rate_spin.setValue(c.calibration.rate_out)
            self.calib_hw_spin.setValue(c.calibration.sample_rate)
        if c.ignition:
            self.ign_buzzer_edit.setText(c.ignition.buzzer_line)
            self.ign_relay_edit.setText(c.ignition.igniter_line)
            self.ign_sense_edit.setText(c.ignition.sense_ai or "")
            self.ign_shunt_spin.setValue(c.ignition.shunt_ohms)
            self.ign_arm_spin.setValue(c.ignition.arm_seconds)
            self.ign_stab_spin.setValue(c.ignition.stabilize_seconds)
            self.ign_pulse_spin.setValue(c.ignition.pulse_seconds)

    def _panel_config(self, **extra) -> LoggerConfig:
        channels = [c.strip() for c in self.channels_edit.text().split(",") if c.strip()]
        cfg = LoggerConfig(
            device=self.device_picker.current_device() or "Dev1",
            channels=channels,
            digital_lines=expand_digital_spec(self.digital_edit.text()),
            rate=self.rate_spin.value(),
            chunk=int(self.chunk_spin.value()),
            vmin=self.vmin_spin.value(),
            vmax=self.vmax_spin.value(),
            term=self.term_combo.currentText(),
            logs_dir=self.cfg.logs_dir,
            duration=self.duration_spin.value() or None,
            **extra,
        )
        self.cfg = cfg
        gsettings.save_config(cfg)
        return cfg

    # ------------------------------------------------------------- devices
    def _on_devices_changed(self, devices):
        self._device_present = bool(devices)
        self._update_start_enabled()
        if len(devices) == 1:
            self.statusBar().showMessage(f"DAQ detected: {devices[0][0]} ({devices[0][1]})")
        elif not devices:
            self.statusBar().showMessage("No DAQ detected — waiting for device…")

    def _poll_devices(self):
        if self.worker is not None:
            return  # don't rescan mid-run
        current = self.device_picker.current_device()
        devices = daq.enumerate_devices()
        names = [n for n, _ in devices]
        if (current in names) != self._device_present or len(names) != len(devices):
            self.device_picker.rescan()

    def _update_start_enabled(self):
        busy = self.worker is not None
        has_file = bool(self.outfile_edit.text())
        self.log_start.setEnabled(self._device_present and has_file and not busy)
        self.calib_start.setEnabled(self._device_present and not busy)
        self.stop_btn.setEnabled(busy)
        self.calib_stop.setEnabled(busy)
        if not has_file and not busy:
            self.log_message.setText("Pick an output file, then press Start.")

    # ----------------------------------------------------------- file pick
    def _choose_outfile(self):
        default = self.cfg.logs_dir
        default.mkdir(parents=True, exist_ok=True)
        suggested = default / f"ni_{self.device_picker.current_device() or 'Dev1'}_{time.strftime('%Y%m%d_%H%M%S')}.csv"
        path, flt = QFileDialog.getSaveFileName(
            self, "Choose output file", str(suggested),
            "CSV files (*.csv);;Excel files (*.xlsx)")
        if path:
            self.outfile_edit.setText(path)
            self._update_start_enabled()
            self.log_message.setText(f"Will log to {path} (a recovery copy is kept too)")

    # ------------------------------------------------------------ sessions
    def _make_worker(self, factory):
        w = SessionWorker(factory)
        w.state_changed.connect(self._on_state)
        w.status_text.connect(self.log_output.appendPlainText)
        w.sample_block.connect(self._on_sample_block)
        w.calib_header.connect(lambda cols: self.log_output.appendPlainText(" | ".join(cols)))
        w.calib_row.connect(self._on_calib_row)
        w.progress_info.connect(self._on_progress)
        w.error_text.connect(self._on_worker_error)
        w.finished_result.connect(self._on_finished)
        return w

    def _start_logging(self):
        from pathlib import Path
        try:
            cfg = self._panel_config(
                outfile=Path(self.outfile_edit.text()),
                require_explicit_output=True,
                recovery=True,
            )
        except ConfigError as e:
            QMessageBox.warning(self, "Cannot start", str(e))
            return
        from ni_usb6009_logger.core.session import LoggingSession
        self.calib_readout.setText("—")
        self._launch("log", lambda reporter: LoggingSession(cfg, reporter))

    def _start_calibration(self):
        cfg = self._panel_config(
            calibration=CalibrationConfig(
                rate_out=self.calib_rate_spin.value(),
                window_seconds=self.calib_window_spin.value(),
                sample_rate=self.calib_hw_spin.value(),
            ),
        )
        from ni_usb6009_logger.core.calibration import CalibrationSession
        self.calib_readout.setText("—")
        self._launch("calib", lambda reporter: CalibrationSession(cfg, reporter))

    def _launch(self, kind, factory):
        self._session_kind = kind
        self.worker = self._make_worker(factory)
        self.worker.finished.connect(self._worker_gone)
        self.log_output.clear()
        chunk = max(1, int(self.calib_hw_spin.value() * 0.2)) if kind == "calib" \
            else int(self.chunk_spin.value())
        rate = self.calib_hw_spin.value() if kind == "calib" else self.rate_spin.value()
        plot = self.calib_plot if kind == "calib" else self.log_plot
        plot.start([c.strip() for c in self.channels_edit.text().split(",") if c.strip()],
                   rate, chunk)
        self._update_start_enabled()
        self.worker.start()

    def _on_sample_block(self, block):
        plot = self.calib_plot if self._session_kind == "calib" else self.log_plot
        plot.append_block(block)

    def _on_calib_row(self, r):
        parts = [f"{v:.6f}" for v in r.averages]
        if r.raw is not None:
            parts += [f"{v:.6f}" for v in r.raw]
        self.calib_readout.setText("   |   ".join(parts))

    def _stop_session(self):
        if self.worker:
            self.statusBar().showMessage("Stopping…")
            self.worker.request_stop()

    def _worker_gone(self):
        self.worker = None
        self.log_plot.stop()
        self.calib_plot.stop()
        self._update_start_enabled()

    # ------------------------------------------------------------- events
    def _on_state(self, state, detail):
        if state == SessionState.DONE:
            self.statusBar().showMessage("Done")
        elif state == SessionState.ABORTED:
            self.statusBar().showMessage("Stopped")
        elif state == SessionState.INHIBITED:
            self.statusBar().showMessage("Ignition inhibited by safety failsafe")

    def _on_progress(self, samples, ch_count, elapsed, inst_rate):
        self.statusBar().showMessage(
            f"Logging… {samples:,} samples/ch | {elapsed:5.1f}s | ~{inst_rate*ch_count:,.0f} S/s")

    def _on_worker_error(self, text):
        friendly = self._friendly_error(text)
        if self.interactive:
            QMessageBox.critical(self, "Test stopped", friendly)
        self.log_output.appendPlainText(f"\nERROR: {text}")
        self.statusBar().showMessage("Error")

    @staticmethod
    def _friendly_error(text):
        lower = text.lower()
        if "not present" in lower or "device" in lower and "not" in lower:
            return ("The DAQ device could not be reached.\n\n"
                    "• Check that the USB cable is connected\n"
                    "• Unplug it and plug it back in\n\n"
                    "Any data recorded so far is safe in the output and recovery files.")
        if "driver" in lower or "nicaiu" in lower or "dll" in lower:
            return ("The NI-DAQmx driver reported a problem.\n\n"
                    "Try restarting the NI services (see the README) or reboot the PC,\n"
                    "then start the app again.")
        return ("Something went wrong during the test:\n\n" + text +
                "\n\nAny data recorded so far is safe in the output and recovery files.")

    def _on_finished(self, result):
        lines = []
        if result.output_path:
            lines.append(f"Saved: {result.output_path}")
        if result.recovery_path:
            lines.append(f"Recovery copy: {result.recovery_path}")
        if result.state == SessionState.INHIBITED:
            if self.interactive:
                QMessageBox.warning(self, "Ignition inhibited",
                                    "A safety failsafe blocked the ignition.\n"
                                    "See the log for the reason (continuity or leak current).")
        elif lines:
            summary = "\n".join(lines) + f"\n\nSamples per channel: ~{result.samples_total}"
            if self.interactive:
                box = QMessageBox(self)
                box.setWindowTitle("Test finished")
                box.setText(summary)
                open_btn = box.addButton("Open folder", QMessageBox.ActionRole)
                box.addButton(QMessageBox.Close)
                box.exec()
                if box.clickedButton() is open_btn and result.output_path:
                    QDesktopServices.openUrl(QUrl.fromLocalFile(str(result.output_path.parent)))
            else:
                self.log_output.appendPlainText(summary)
        self._refresh_recovery()

    # ------------------------------------------------------------ recovery
    def _refresh_recovery(self):
        self.recovery_list.clear()
        rec_dir = self.cfg.logs_dir / "recovery"
        if rec_dir.exists():
            import os
            for f in sorted(rec_dir.glob("*.csv"), key=os.path.getmtime, reverse=True):
                status = "OK" if f.stem.endswith("_OK") else "INTERRUPTED"
                size_kb = f.stat().st_size / 1024
                self.recovery_list.addItem(f"{f.name}   [{status}, {size_kb:.0f} KB]")

    def _copy_recovery(self):
        item = self.recovery_list.currentItem()
        if not item:
            return
        name = item.text().split("   [")[0]
        src = self.cfg.logs_dir / "recovery" / name
        dest, _ = QFileDialog.getSaveFileName(self, "Copy recovery file",
                                              str(self.cfg.logs_dir / name),
                                              "CSV files (*.csv)")
        if dest:
            import shutil
            shutil.copy2(src, dest)
            self.statusBar().showMessage(f"Copied to {dest}")

    # --------------------------------------------------------------- close
    def closeEvent(self, event):
        if self.worker is not None:
            self.worker.request_stop()
            if not self.worker.wait(3000):
                self.statusBar().showMessage("Forcing outputs safe…")
                self.worker.wait(2000)
        gsettings.save_config(self.cfg)
        super().closeEvent(event)

