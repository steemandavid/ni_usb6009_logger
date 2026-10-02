"""Ad hoc offscreen tab walk against the REAL NI-DAQmx backend.

Yesterday's walk (CHANGELOG 2026-10-01) used the fake backend; this one drives
the same GUI flows against the NI-DAQmx simulated device created in NI MAX.
Not part of the test suite -- run with:

    .venv/Scripts/python.exe walk_real_daq.py [--unplug]

--unplug additionally starts an endless run and waits while the operator
deletes the simulated device in NI MAX (the closest thing to a real unplug).

Every step prints PASS / FAIL; unhandled exceptions in Qt slots (which would
close the real app) fail the step. Exit code = number of failed steps.
"""
import os
import sys
import tempfile
import time
import traceback

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

# QSettings(QSettings.defaultFormat(), ...) -> temp INI, never the registry
# (the GUI builds QSettings from defaultFormat since 2026-10-01).
SETTINGS_DIR = tempfile.mkdtemp(prefix="walk_qsettings_")
QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, SETTINGS_DIR)
QSettings.setDefaultFormat(QSettings.IniFormat)

APP = QApplication([])

# A slot exception never reaches the caller: it lands in sys.excepthook, which
# would close the real app. Record instead.
UNHANDLED = []
sys.excepthook = lambda et, e, tb: UNHANDLED.append(
    "".join(traceback.format_exception(et, e, tb)))

# Any dialog that still opens offscreen would hang the walk; record it instead.
DIALOGS = []
for _name in ("exec", "warning", "critical", "information", "about"):
    setattr(QMessageBox, _name,
            staticmethod(lambda *a, _n=_name, **k: (DIALOGS.append(_n), 0)[1]))

DEVICE = "Simulated-usb-6009"
WORK = tempfile.mkdtemp(prefix="walk_real_")

FAILURES = []


def step(name, fn):
    print(f"\n=== {name} ", end="", flush=True)
    UNHANDLED.clear()
    DIALOGS.clear()
    try:
        fn()
        if UNHANDLED:
            raise AssertionError(
                f"unhandled slot exception:\n{UNHANDLED[0]}")
        print("PASS", flush=True)
        if DIALOGS:
            print(f"    (dialogs: {DIALOGS})", flush=True)
    except Exception:
        print("FAIL", flush=True)
        traceback.print_exc()
        if UNHANDLED:
            print(UNHANDLED[0], file=sys.stderr)
        FAILURES.append(name)


def pump(deadline_s, cond, what):
    deadline = time.time() + deadline_s
    while not cond():
        assert time.time() < deadline, f"timed out waiting for {what}"
        APP.processEvents()
        time.sleep(0.02)


def make_window():
    from ni_usb6009_logger.gui.main_window import MainWindow
    win = MainWindow()
    win.interactive = False
    win.ign_panel.interactive = False
    win.cfg.logs_dir = os.path.join(WORK, "logs")
    win._update_start_enabled()
    return win


def wait_worker_done(win, timeout=30.0):
    pump(timeout, lambda: win.worker is None, "worker to finish")
    for _ in range(10):
        APP.processEvents()
        time.sleep(0.02)


def main():
    unplug = "--unplug" in sys.argv
    from ni_usb6009_logger.core import daq
    from ni_usb6009_logger.core.events import SessionState

    def in_state(win, name):
        return win.ign_panel._last_state is SessionState[name]

    def s_detect():
        devices = daq.enumerate_devices()
        print(f"    driver_available={daq.driver_available()} devices={devices}")
        assert devices, "no devices enumerated"
        win = make_window()
        pump(5, lambda: DEVICE in win._device_names, f"{DEVICE} in the picker")
        win.outfile_edit.setText(os.path.join(WORK, "run.csv"))
        win.rate_spin.setValue(100)
        win.chunk_spin.setValue(10)
        win.duration_spin.setValue(3)
        win._update_start_enabled()
        assert win.log_start.isEnabled()
        return win

    # window reused by the first steps; keep a reference outside `step`
    # closures so a failure in step N still leaves a closable window.
    win = None

    def s_csv_run():
        nonlocal win
        win = s_detect()
        win._start_logging()
        wait_worker_done(win)
        out = os.path.join(WORK, "run.csv")
        rec = os.path.join(WORK, "recovery", "run_recovery_OK.csv")
        assert os.path.exists(out), "output CSV missing"
        assert os.path.exists(rec), "recovery copy missing"
        lines = open(out).read().splitlines()
        assert len(lines) > 2, f"too few lines: {lines}"
        print(f"    csv lines={len(lines)} head={lines[0]!r} data={lines[1]!r}")

    def s_recovery_tab():
        win.tabs.setCurrentIndex(win.tabs.indexOf(win._recovery_tab))
        names = [win.recovery_list.item(i).text()
                 for i in range(win.recovery_list.count())]
        assert any("run_recovery_OK.csv" in n for n in names), names
        print(f"    listed: {names}")

    def s_xlsx_run():
        win.outfile_edit.setText(os.path.join(WORK, "run.xlsx"))
        win.duration_spin.setValue(2)
        win._update_start_enabled()
        win._start_logging()
        wait_worker_done(win)
        assert os.path.exists(os.path.join(WORK, "run.xlsx")), "XLSX missing"

    def s_calibration():
        win.calib_hw_spin.setValue(50)
        win.calib_rate_spin.setValue(10)
        win._start_calibration()
        pump(15, lambda: win.calib_readout.text() not in ("—", ""),
             "first calibration readout")
        print(f"    readout: {win.calib_readout.text()!r}")
        assert win.calib_plot._curves
        for ring in win.calib_plot._rings:
            t, v = ring.snapshot()
            assert len(t) > 0, "calibration plot received no samples"
            print(f"    simulated AI values: min={min(v):.4f} max={max(v):.4f}")
        win._stop_session()
        wait_worker_done(win)

    def s_bogus_device():
        # the previous step closed the window mid-run; the queued finished
        # signal needs a pumped event loop to clear MainWindow.worker.
        pump(10, lambda: win.worker is None, "worker gone after close")
        win.device_picker.combo.setEditText("DevX")  # typed: escape hatch
        win.duration_spin.setValue(1)
        win._update_start_enabled()
        assert win.log_start.isEnabled(), "typed name must enable Start"
        win._start_logging()
        wait_worker_done(win)
        assert "ERROR:" in win.log_output.toPlainText(), "no error surfaced"
        win.device_picker.rescan()
        pump(5, lambda: DEVICE in win._device_names, "real device back")

    def arm_window():
        # A typed name survives rescan by design (escape hatch); make sure the
        # real device is selected before arming.
        win.device_picker.combo.setCurrentText(f"{DEVICE} — USB-6009")
        # thresholds informed by s_calibration's observed simulated values;
        # leak wide open so FIRE_PENDING is reachable whatever the sim returns.
        win.ign_cont_spin.setValue(0.0)
        win.ign_leak_spin.setValue(1000.0)
        win.ign_sense_edit.setText("ai2")
        win.ign_sense_term.setCurrentText("RSE")
        win.ign_shunt_spin.setValue(10.0)
        win.ign_arm_spin.setValue(2.0)
        win.ign_stab_spin.setValue(1.0)
        win.ign_pulse_spin.setValue(0.5)
        win.duration_spin.setValue(0.0)
        win.outfile_edit.setText(os.path.join(WORK, "ignite.csv"))
        win._update_start_enabled()

    def s_ignite_inhibit():
        # defaults: continuity_min 0.2 mA. Which way the simulated signal
        # falls is informational: FIRE_PENDING or INHIBIT are both correct,
        # as long as the app survives and the run can be ended.
        arm_window()
        win.ign_cont_spin.setValue(0.2)
        win.ign_arm_spin.setValue(0.5)
        win.ign_stab_spin.setValue(0.2)
        win._update_start_enabled()
        assert win.ign_panel.arm_btn.isEnabled()
        win.ign_panel._confirm_arm()
        deadline = time.time() + 20
        while (win.worker is not None
               and not in_state(win, "FIRE_PENDING")):
            assert time.time() < deadline, "neither FIRE_PENDING nor run end"
            APP.processEvents()
            time.sleep(0.02)
        print(f"    state={win.ign_panel._last_state}")
        if win.worker is not None:
            print("    continuity passed on the simulated signal; aborting")
            win.ign_panel.abort_btn.click()
        wait_worker_done(win, timeout=20)
        text = win.log_output.toPlainText()
        print(f"    log tail: {text.splitlines()[-1] if text.splitlines() else ''!r}")

    def s_ignite_fire_abort():
        arm_window()
        win.ign_panel._confirm_arm()
        assert win.worker is not None, "ARM did not start a session"
        pump(20, lambda: in_state(win, "FIRE_PENDING"), "FIRE_PENDING")
        assert win.ign_panel.fire_btn.isEnabled(), "FIRE not offered"
        win.ign_panel.abort_btn.click()
        wait_worker_done(win, timeout=20)
        text = win.log_output.toPlainText()
        assert os.path.exists(os.path.join(WORK, "ignite.csv"))
        print(f"    state={win.ign_panel._last_state}")
        print("    abort log:",
              [ln for ln in text.splitlines()
               if "relay" in ln.lower() or "low" in ln.lower()][-3:])

    def s_ignite_fire_full():
        arm_window()
        win.ign_panel._confirm_arm()
        pump(20, lambda: in_state(win, "FIRE_PENDING"), "FIRE_PENDING")
        # A synthetic click() is an instant press+release, which the hold
        # logic rightly cancels. Drive the real 50 ms hold timer instead:
        # press (held, no release) and let it tick for the full 2 seconds.
        win.ign_panel.fire_btn.setDown(True)
        win.ign_panel._hold_start()
        pump(20, lambda: in_state(win, "FIRED"), "FIRED")
        win._stop_session()
        wait_worker_done(win, timeout=20)
        text = win.log_output.toPlainText()
        relay_lines = [ln for ln in text.splitlines()
                       if "relay" in ln.lower() or "confirm" in ln.lower()]
        print(f"    state={win.ign_panel._last_state}")
        print(f"    relay/confirm log: {relay_lines[-4:]}")

    def s_close_mid_run():
        win.duration_spin.setValue(0.0)
        win.outfile_edit.setText(os.path.join(WORK, "closemid.csv"))
        win._update_start_enabled()
        win._start_logging()
        pump(10, lambda: win.worker is not None, "run underway")
        time.sleep(0.5)
        APP.processEvents()
        win.close()  # equals ABORT; must not hang or crash
        print("    closed during run")

    def s_unplug():
        # Operator deletes the simulated device in NI MAX while this runs.
        win2 = make_window()
        pump(5, lambda: DEVICE in win2._device_names, "device present")
        win2.outfile_edit.setText(os.path.join(WORK, "unplug.csv"))
        win2.duration_spin.setValue(0.0)
        win2._update_start_enabled()
        win2._start_logging()
        pump(10, lambda: win2.worker is not None, "run underway")
        time.sleep(1.0)
        APP.processEvents()
        print("\n    >>> DELETE the simulated device in NI MAX now "
              "(Devices and Interfaces -> right-click -> Delete) <<<", flush=True)
        deadline = time.time() + 120
        while time.time() < deadline:
            APP.processEvents()
            time.sleep(0.2)
            if win2.worker is None:
                break
        assert win2.worker is None, "run did not end after device deletion"
        text = win2.log_output.toPlainText()
        assert "ERROR:" in text, f"no error surfaced; log tail: {text[-400:]!r}"
        assert os.path.exists(os.path.join(WORK, "unplug.csv")), "no partial data"
        names = [win2.recovery_list.item(i).text()
                 for i in range(win2.recovery_list.count())]
        print(f"    recovery tab after unplug: {names}")
        win2.close()

    step("device detection + CSV logging run", s_csv_run)
    step("recovery tab lists the finished run", s_recovery_tab)
    step("XLSX logging run", s_xlsx_run)
    step("calibration start/stop", s_calibration)
    step("ignition, defaults (expect inhibit or armed)", s_ignite_inhibit)
    step("ignition ARM -> FIRE_PENDING -> ABORT", s_ignite_fire_abort)
    step("ignition ARM -> FIRE -> stop", s_ignite_fire_full)
    step("window close mid-run", s_close_mid_run)
    # last: leaves a bogus typed device name in the picker
    step("bogus typed device name", s_bogus_device)
    if win is not None:
        win.close()
    if unplug:
        step("mid-run device deletion (NI MAX)", s_unplug)

    print(f"\nwork dir: {WORK}")
    print(f"qsettings: {SETTINGS_DIR}")
    if FAILURES:
        print(f"\n{len(FAILURES)} step(s) FAILED: {FAILURES}")
        return 1
    print("\nall steps passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
