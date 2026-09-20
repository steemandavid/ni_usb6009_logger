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
