"""Offscreen GUI smoke tests on the fake DAQ.

Covers: start gating, a full logging run with recovery, and a mid-run device
unplug (friendly error + partial data still on disk).
"""
import time

import pytest


@pytest.fixture
def qapp(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("NI_USB6009_FAKE", "1")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def _make_window(qapp, fake_daq, tmp_path):
    from ni_usb6009_logger.gui.main_window import MainWindow
    fake_daq.reset(devices=["Dev1"])
    win = MainWindow()
    win.interactive = False  # offscreen: no modal dialogs
    win.cfg.logs_dir = tmp_path / "logs"
    win.outfile_edit.setText(str(tmp_path / "run.csv"))
    win.rate_spin.setValue(100)
    win.chunk_spin.setValue(10)
    win.duration_spin.setValue(0.5)
    win._update_start_enabled()
    return win


def _wait_worker_done(qapp, win, timeout=15.0):
    deadline = time.time() + timeout
    while win.worker is not None:
        assert time.time() < deadline, "worker did not finish in time"
        qapp.processEvents()
        time.sleep(0.02)
    # let queued signals (finished_result etc.) drain
    for _ in range(10):
        qapp.processEvents()


def test_start_requires_outfile_and_device(qapp, fake_daq, tmp_path):
    win = _make_window(qapp, fake_daq, tmp_path)
    assert win.log_start.isEnabled()  # device + outfile present
    win.outfile_edit.clear()
    win._update_start_enabled()
    assert not win.log_start.isEnabled(), "no outfile -> no Start"
    fake_daq.reset(devices=[])
    win._poll_devices()
    assert not win.calib_start.isEnabled(), "no device -> no Start"
    win.close()


def test_gui_logging_run_with_recovery(qapp, fake_daq, tmp_path):
    win = _make_window(qapp, fake_daq, tmp_path)
    win._start_logging()
    _wait_worker_done(qapp, win)
    assert (tmp_path / "run.csv").exists()
    rec = tmp_path / "recovery" / "run_recovery_OK.csv"
    assert rec.exists(), "recovery copy renamed _OK after clean run"
    main_lines = (tmp_path / "run.csv").read_text().splitlines()
    rec_lines = rec.read_text().splitlines()
    assert main_lines == rec_lines
    win.close()


def test_gui_unplug_mid_run_is_graceful(qapp, fake_daq, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    errors = []
    monkeypatch.setattr(QMessageBox, "critical",
                        staticmethod(lambda *a, **k: errors.append(a[2] if len(a) > 2 else a)))

    win = _make_window(qapp, fake_daq, tmp_path)
    win.duration_spin.setValue(0.0)  # run until stopped/unplugged
    win._start_logging()

    # wait until logging is underway, then yank the device
    deadline = time.time() + 5
    while "Running" not in win.log_output.toPlainText() and time.time() < deadline:
        qapp.processEvents()
        time.sleep(0.02)
    time.sleep(0.3)
    fake_daq.reset(devices=[])

    _wait_worker_done(qapp, win)
    # interactive=False logs the error instead of a dialog; the friendly text
    # goes to the user in real use. The raw error must be in the log pane.
    log_text = win.log_output.toPlainText()
    assert "ERROR:" in log_text, f"error surfaced to the user, log: {log_text!r}"
    # partial data survived in both sinks; recovery stays unmarked (interrupted)
    assert (tmp_path / "run.csv").exists()
    rec = tmp_path / "recovery" / "run_recovery.csv"
    assert rec.exists()
    assert not (tmp_path / "recovery" / "run_recovery_OK.csv").exists()
    assert len((tmp_path / "run.csv").read_text().splitlines()) > 1
    win.close()


def test_ring_buffer_bounds_memory(qapp):
    import numpy as np
    from ni_usb6009_logger.gui.widgets.live_plot import _Ring

    r = _Ring(100)
    big = np.arange(350, dtype=float)
    r.append(big, big)  # far larger than capacity
    t, v = r.snapshot()
    assert len(v) == 100
    assert list(v) == list(range(250, 350)), "keeps the newest capacity samples"

    # wrap-around appends in small pieces
    r2 = _Ring(10)
    for start in range(0, 35, 5):
        arr = np.arange(start, start + 5, dtype=float)
        r2.append(arr, arr)
    t2, v2 = r2.snapshot()
    assert len(v2) == 10
    assert list(v2) == [25.0, 26.0, 27.0, 28.0, 29.0, 30.0, 31.0, 32.0, 33.0, 34.0]
    assert list(t2) == list(v2)


def test_gui_logging_feeds_plot(qapp, fake_daq, tmp_path):
    win = _make_window(qapp, fake_daq, tmp_path)
    win._start_logging()
    _wait_worker_done(qapp, win)
    plot = win.log_plot
    assert plot._curves, "curves created for the configured channels"
    for ring in plot._rings:
        t, v = ring.snapshot()
        assert len(t) > 0, "plot received sample blocks"
        assert abs(t[-1]) < 60.0, "time axis is relative seconds"
    win.close()


def test_gui_calibration_feeds_readout_and_plot(qapp, fake_daq, tmp_path):
    win = _make_window(qapp, fake_daq, tmp_path)
    win.calib_hw_spin.setValue(50)
    win.calib_rate_spin.setValue(10)
    win._start_calibration()
    # wait for first calib row, then press Stop
    deadline = time.time() + 5
    while win.calib_readout.text() in ("—", "") and time.time() < deadline:
        qapp.processEvents()
        time.sleep(0.02)
    assert win.calib_readout.text() not in ("—", ""), "readout shows averages"
    win._stop_session()
    _wait_worker_done(qapp, win)
    assert win.calib_plot._curves, "calibration plot configured"
    for ring in win.calib_plot._rings:
        t, v = ring.snapshot()
        assert len(t) > 0
    win.close()
