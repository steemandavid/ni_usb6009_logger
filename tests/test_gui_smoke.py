"""Offscreen GUI smoke tests on the fake DAQ.

Covers: start gating, a full logging run with recovery, and a mid-run device
unplug (friendly error + partial data still on disk).
"""
import sys
import time

import pytest


@pytest.fixture
def qapp(monkeypatch, tmp_path_factory):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("NI_USB6009_FAKE", "1")
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication
    # Keep persisted settings out of the developer's real profile.
    settings_dir = tmp_path_factory.mktemp("qsettings")
    QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, str(settings_dir))
    QSettings.setDefaultFormat(QSettings.IniFormat)
    app = QApplication.instance() or QApplication([])
    # Qt does not propagate an exception raised inside a slot into the caller:
    # it routes it to sys.excepthook. A crash that closes the real app (via
    # gui.app._excepthook) therefore left a PASSING test behind -- which is
    # exactly how CalibrationSession.run() returning None instead of a
    # SessionResult reached a user. Record them and fail the test.
    unhandled = []
    monkeypatch.setattr(sys, "excepthook",
                        lambda et, e, tb: unhandled.append((et, e)))
    yield app
    assert not unhandled, (
        "unhandled exception in a Qt slot (the real app would have closed): "
        f"{unhandled[0][0].__name__}: {unhandled[0][1]}")


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
    # Stopping calibration must complete like any other session: the worker
    # emits run()'s return value into _on_finished, so returning None here
    # crashed the app with AttributeError on result.output_path.
    assert win.calib_plot._curves, "calibration plot configured"
    for ring in win.calib_plot._rings:
        t, v = ring.snapshot()
        assert len(t) > 0
    win.close()


def _arm_window(qapp, fake_daq, tmp_path):
    win = _make_window(qapp, fake_daq, tmp_path)
    win.interactive = False
    win.ign_panel.interactive = False
    # thresholds may have been restored from persisted settings: pin them
    win.ign_cont_spin.setValue(0.2)
    win.ign_leak_spin.setValue(5.0)
    win.ign_confirm_spin.setValue(300.0)
    win.ign_sense_edit.setText("ai2")
    win.ign_sense_term.setCurrentText("RSE")
    # fast fake timings
    win.ign_arm_spin.setValue(0.3)
    win.ign_stab_spin.setValue(0.2)
    win.ign_pulse_spin.setValue(0.2)
    win.duration_spin.setValue(0.0)  # run until aborted
    win._update_start_enabled()
    return win


def _wait_state(qapp, win, name_or_state, timeout=8.0):
    from ni_usb6009_logger.core.events import SessionState as S
    target = name_or_state if isinstance(name_or_state, S) else S[name_or_state]
    deadline = time.time() + timeout
    while win.ign_panel._last_state != target:
        assert time.time() < deadline, f"state {target} not reached"
        qapp.processEvents()
        time.sleep(0.02)


def test_gui_ignition_full_flow(qapp, fake_daq, tmp_path):
    win = _arm_window(qapp, fake_daq, tmp_path)
    fake_daq.STATE.ai_voltage_overrides["Dev1/ai2"] = 0.0003  # continuity OK
    assert win.ign_panel.arm_btn.isEnabled(), "device + outfile -> ARM available"
    win.ign_panel._confirm_arm()   # non-interactive: auto-confirms
    assert win.worker is not None

    # LOGGING is transient (~stabilize time); wait for the gated state
    _wait_state(qapp, win, "FIRE_PENDING")
    assert win.ign_panel.fire_btn.isEnabled(), "FIRE available after stabilization"

    # simulate the 2-second hold via the panel's hold timer at full speed
    win.ign_panel._hold_start()
    while not win.ign_panel._held:
        qapp.processEvents()
        win.ign_panel._hold_tick()
    _wait_state(qapp, win, "FIRED")
    win._stop_session()
    _wait_worker_done(qapp, win)

    writes = fake_daq.do_write_sequences()
    assert writes[0] == [False, False]
    assert [True, False] in writes and [False, True] in writes
    assert writes[-1] == [False, False]
    assert (tmp_path / "run.csv").exists()
    win.close()


def test_gui_ignition_leak_inhibits_and_blocks_fire(qapp, fake_daq, tmp_path):
    win = _arm_window(qapp, fake_daq, tmp_path)
    fake_daq.STATE.ai_voltage_overrides["Dev1/ai2"] = 0.01  # 10 mA leak
    win.ign_panel._confirm_arm()
    _wait_worker_done(qapp, win, timeout=8)
    assert not win.ign_panel.fire_btn.isEnabled(), "FIRE must stay blocked"
    writes = fake_daq.do_write_sequences()
    assert all(w != [False, True] for w in writes), "relay must never fire"
    assert writes[-1] == [False, False]
    assert "INHIBIT" in win.log_output.toPlainText()
    win.close()


def test_gui_ignition_abort_leaves_do_low(qapp, fake_daq, tmp_path):
    win = _arm_window(qapp, fake_daq, tmp_path)
    fake_daq.STATE.ai_voltage_overrides["Dev1/ai2"] = 0.0003
    win.ign_panel._confirm_arm()
    _wait_state(qapp, win, "FIRE_PENDING")
    win.ign_panel.abort_btn.click()
    _wait_worker_done(qapp, win)
    writes = fake_daq.do_write_sequences()
    assert all(w != [False, True] for w in writes), "no fire after abort"
    assert writes[-1] == [False, False], "DO forced LOW on abort"
    win.close()


def test_recovery_tab_lists_files_next_to_the_output(qapp, fake_daq, tmp_path):
    # Browse only *suggests* logs_dir; the operator normally saves elsewhere,
    # and the recovery copy lands next to the chosen output file.
    out_dir = tmp_path / "elsewhere"
    out_dir.mkdir()
    win = _make_window(qapp, fake_daq, tmp_path)
    win.outfile_edit.setText(str(out_dir / "run.csv"))
    win._update_start_enabled()
    win._start_logging()
    _wait_worker_done(qapp, win)

    assert (out_dir / "recovery" / "run_recovery_OK.csv").exists()
    names = [win.recovery_list.item(i).text()
             for i in range(win.recovery_list.count())]
    assert any("run_recovery_OK.csv" in n for n in names), \
        f"Recovery tab must list the files actually written; got {names}"
    src = win.recovery_list.item(0).toolTip()
    assert src.startswith(str(out_dir)), "Copy to… must point at the real file"
    win.close()


def test_settings_round_trip_keeps_ignition_thresholds(qapp, fake_daq, tmp_path):
    from ni_usb6009_logger.gui import settings as gsettings
    win = _make_window(qapp, fake_daq, tmp_path)
    win.ign_cont_spin.setValue(0.5)
    win.ign_leak_spin.setValue(50.0)
    win.ign_confirm_spin.setValue(750.0)
    win.ign_sense_term.setCurrentText("DIFF")
    win.calib_window_spin.setValue(9.0)
    # A plain log run must not drop the ignition parameters when it saves.
    win._start_logging()
    _wait_worker_done(qapp, win)
    win.close()

    cfg = gsettings.load_config()
    assert cfg.ignition is not None and cfg.outfile is not None
    assert cfg.ignition.continuity_min_ma == 0.5
    assert cfg.ignition.leak_max_ma == 50.0
    assert cfg.ignition.fire_confirm_ma == 750.0
    assert cfg.ignition.sense_term == "DIFF"
    assert cfg.calibration.window_seconds == 9.0

    win2 = MainWindowFactory(qapp, fake_daq)
    assert win2.ign_cont_spin.value() == 0.5
    assert win2.ign_leak_spin.value() == 50.0
    assert win2.ign_confirm_spin.value() == 750.0
    assert win2.ign_sense_term.currentText() == "DIFF"
    win2.close()


def test_term_combos_offer_only_supported_modes(qapp, fake_daq, tmp_path):
    # The USB-6009 has no NRSE mode; offering it only fails at Start.
    win = _make_window(qapp, fake_daq, tmp_path)
    for combo in (win.term_combo, win.ign_sense_term):
        items = [combo.itemText(i) for i in range(combo.count())]
        assert items == ["RSE", "DIFF"]
    win.close()


def test_saved_nrse_falls_back_with_a_notice(qapp, fake_daq, tmp_path):
    from dataclasses import replace
    from ni_usb6009_logger.gui import settings as gsettings
    from ni_usb6009_logger.core.config import IgnitionConfig
    # Settings written by a version that still offered NRSE.
    gsettings.save_config(replace(gsettings.default_config(), term="NRSE",
                                  ignition=IgnitionConfig(sense_term="NRSE")))
    win = MainWindowFactory(qapp, fake_daq)
    assert win.term_combo.currentText() == "RSE"
    assert win.ign_sense_term.currentText() == "RSE"
    assert "NRSE is not supported" in win.log_output.toPlainText()
    win.close()


def MainWindowFactory(qapp, fake_daq):
    from ni_usb6009_logger.gui.main_window import MainWindow
    win = MainWindow()
    win.interactive = False
    return win


def test_fire_stays_blocked_during_arming(qapp, fake_daq, tmp_path):
    win = _arm_window(qapp, fake_daq, tmp_path)
    win.ign_arm_spin.setValue(1.5)
    fake_daq.STATE.ai_voltage_overrides["Dev1/ai2"] = 0.0003
    win.ign_panel._confirm_arm()
    _wait_state(qapp, win, "ARMING")
    assert not win.ign_panel.fire_btn.isEnabled(), "FIRE must be dead while arming"
    win._stop_session()
    _wait_worker_done(qapp, win)
    win.close()


def test_panel_leds_follow_the_configured_thresholds(qapp, fake_daq, tmp_path):
    win = _make_window(qapp, fake_daq, tmp_path)
    win.ign_cont_spin.setValue(1.0)
    win.ign_leak_spin.setValue(50.0)
    win.ign_panel.set_thresholds(win.ign_cont_spin.value(), win.ign_leak_spin.value())
    win.ign_panel.set_arming(1.0, 10.0)  # 10 mA: continuity OK, no leak
    assert "#2ca02c" in win.ign_panel.led_continuity.styleSheet()
    assert "#2ca02c" in win.ign_panel.led_leak.styleSheet()
    win.ign_panel.set_arming(1.0, 60.0)  # above the configured leak maximum
    assert "#ff7f0e" in win.ign_panel.led_leak.styleSheet()
    win.close()


def test_typed_device_name_enables_start(qapp, fake_daq, tmp_path):
    win = _make_window(qapp, fake_daq, tmp_path)
    fake_daq.reset(devices=[])
    win._poll_devices()
    assert not win.log_start.isEnabled()
    win.device_picker.combo.setEditText("Dev7")  # not visible to enumeration
    assert win.log_start.isEnabled(), "a typed device must be usable (FSD §5)"
    win.close()


def test_settings_stay_out_of_the_real_profile(qapp):
    # QSettings(org, app) ignores setDefaultFormat(): on Windows every test
    # wrote the registry, overwrote the operator's saved settings and leaked
    # state between tests. Linux CI could not notice (native format is INI).
    from ni_usb6009_logger.gui import settings as gsettings
    assert gsettings._settings().fileName().endswith(".ini")


def test_stopped_service_is_named_not_no_daq(qapp, fake_daq):
    """A dead mxssvr must not read as an empty desk (FSD §17 item 5)."""
    fake_daq.STATE.devices_error = fake_daq.DaqError(
        "MAX: (Hex 0x8004032B) The configuration database is not running.")
    win = MainWindowFactory(qapp, fake_daq)
    msg = win.statusBar().currentMessage()
    assert "configuration service" in msg.lower(), msg
    assert "No DAQ detected" not in msg
    win.close()


def test_config_error_is_refused_before_the_run(qapp, fake_daq, tmp_path, monkeypatch):
    # Validated in the worker, a bad setting read as "Something went wrong
    # during the test ... data recorded so far is safe", in CLI flag names.
    from PySide6.QtWidgets import QMessageBox
    shown = []
    monkeypatch.setattr(QMessageBox, "warning",
                        staticmethod(lambda _p, title, text: shown.append((title, text))))
    win = _make_window(qapp, fake_daq, tmp_path)
    win.channels_edit.setText("ai5")
    win.term_combo.setCurrentText("DIFF")
    win._start_logging()
    assert win.worker is None, "no session is started for an invalid config"
    title, text = shown[-1]
    assert title == "Cannot start"
    assert "Term config" in text and "--term" not in text
    assert not text.startswith("Error:")
    win.close()


def test_recovery_tab_shows_interrupted_runs(qapp, fake_daq, tmp_path):
    # Listed at launch, and refreshed after an unplug -- not only after a
    # clean finish, which was the one case that did not need it.
    (tmp_path / "recovery").mkdir()
    (tmp_path / "recovery" / "old_recovery.csv").write_text("t,ai0\n")
    from dataclasses import replace
    from ni_usb6009_logger.gui import settings as gsettings
    gsettings.save_config(replace(gsettings.default_config(),
                                  outfile=tmp_path / "run.csv"))
    win = _make_window(qapp, fake_daq, tmp_path)
    assert win.recovery_list.count() == 1, "existing recovery files listed at launch"

    win.duration_spin.setValue(0.0)
    win._start_logging()
    deadline = time.time() + 5
    while "Running" not in win.log_output.toPlainText() and time.time() < deadline:
        qapp.processEvents()
        time.sleep(0.02)
    fake_daq.reset(devices=[])
    _wait_worker_done(qapp, win)
    names = [win.recovery_list.item(i).text() for i in range(win.recovery_list.count())]
    assert any("run_recovery.csv" in n and "INTERRUPTED" in n for n in names), names
    win.close()


def test_copy_recovery_failure_does_not_crash(qapp, fake_daq, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog, QMessageBox
    (tmp_path / "recovery").mkdir()
    (tmp_path / "recovery" / "old_recovery.csv").write_text("t,ai0\n")
    shown = []
    monkeypatch.setattr(QMessageBox, "warning",
                        staticmethod(lambda _p, title, text: shown.append(title)))
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(
        lambda *a, **k: (str(tmp_path / "no_such_dir" / "c.csv"), "")))
    win = _make_window(qapp, fake_daq, tmp_path)
    win.tabs.setCurrentWidget(win._recovery_tab)  # opening the tab refreshes it
    win.recovery_list.setCurrentRow(0)
    win._copy_recovery()  # raised FileNotFoundError, which closes the real app
    assert shown == ["Copy failed"]
    win.close()
