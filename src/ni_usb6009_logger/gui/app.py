"""GUI entry point: driver check, friendly startup errors, main loop.

Also implements --selftest for the installer: checks the NI-DAQmx driver and
device presence, prints a summary, and exits 0 (all good), 1 (driver OK but
no DAQ connected) or 2 (driver missing/broken).
"""
import sys
import traceback

from ni_usb6009_logger.core import daq

NI_DRIVER_URL = "https://www.ni.com/en/shop/model/ni-daqmx.html"


def _selftest() -> int:
    ok = daq.driver_available()
    if not ok:
        print("SELFTEST: NI-DAQmx driver NOT available.")
        return 2
    devices = daq.enumerate_devices()
    if devices:
        names = ", ".join(f"{n} ({p})" for n, p in devices)
        print(f"SELFTEST: driver OK, DAQ detected: {names}")
        return 0
    print("SELFTEST: driver OK, no DAQ device found (connect the USB-6009).")
    return 1


def _excepthook(exc_type, exc, tb):
    """Last-resort handler: never show a raw traceback to the user."""
    from PySide6.QtWidgets import QApplication, QMessageBox
    detail = "".join(traceback.format_exception(exc_type, exc, tb))
    print(detail, file=sys.stderr)
    app = QApplication.instance()
    if app is not None:
        QMessageBox.critical(
            None, "Unexpected error",
            "An unexpected error occurred:\n\n"
            f"{exc_type.__name__}: {exc}\n\n"
            "The app will now close. Details were written to the log output.")
        # Close for real: the windows' closeEvent still runs, so a session in
        # progress is stopped and the DO lines are forced LOW.
        app.closeAllWindows()
        app.quit()


def main(argv=None) -> int:
    argv = list(sys.argv if argv is None else argv)
    if "--selftest" in argv:
        return _selftest()

    from PySide6.QtWidgets import QApplication, QMessageBox

    sys.excepthook = _excepthook
    app = QApplication(argv)
    app.setApplicationName("NI USB-6009 Logger")
    app.setOrganizationName("steeman.be")

    if not daq.driver_available():
        box = QMessageBox()
        box.setIcon(QMessageBox.Critical)
        box.setWindowTitle("NI-DAQmx driver missing")
        box.setText(
            "This app needs the NI-DAQmx driver to talk to the USB-6009\n"
            "measurement device, and it is not installed on this PC.")
        box.setInformativeText(
            "Please install NI-DAQmx (free download from NI), then start\n"
            "this app again. Click 'Open download page' to go there now.")
        open_btn = box.addButton("Open download page", QMessageBox.ActionRole)
        box.addButton(QMessageBox.Close)
        box.exec()
        if box.clickedButton() is open_btn:
            from PySide6.QtGui import QDesktopServices
            from PySide6.QtCore import QUrl
            QDesktopServices.openUrl(QUrl(NI_DRIVER_URL))
        return 1

    from ni_usb6009_logger.gui.main_window import MainWindow
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
