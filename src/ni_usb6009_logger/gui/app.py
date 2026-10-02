"""GUI entry point: driver check, friendly startup errors, main loop.

Also implements --selftest for the installer: checks the NI-DAQmx driver and
device presence, prints a summary, and exits 0 (all good), 1 (driver OK but
no DAQ connected) or 2 (driver missing/broken).
"""
import sys
import traceback

from ni_usb6009_logger.core import daq
from ni_usb6009_logger.core.helpers import configure_stdio

NI_DRIVER_URL = "https://www.ni.com/en/shop/model/ni-daqmx.html"


def _selftest() -> int:
    devices, problem = daq.enumerate_devices_ex()
    if problem == "driver":
        print("SELFTEST: NI-DAQmx driver NOT available.")
        return 2
    if problem == "service":
        print("SELFTEST: NI-DAQmx installed, but the NI configuration service "
              "is not running (start the NI services or reboot the PC).")
        return 2
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
    # --selftest prints to stdout, and _excepthook writes tracebacks there --
    # a DAQ error message carrying the ignition messages' U+03A9 would
    # otherwise raise UnicodeEncodeError while reporting the real error.
    configure_stdio()
    argv = list(sys.argv if argv is None else argv)
    if "--selftest" in argv:
        return _selftest()

    from PySide6.QtWidgets import QApplication, QMessageBox

    sys.excepthook = _excepthook
    app = QApplication(argv)
    app.setApplicationName("NI USB-6009 Logger")
    app.setOrganizationName("steeman.be")

    _devices, problem = daq.enumerate_devices_ex()
    if problem == "service":
        # Seen on the dev box: mxssvr stopped makes the driver look missing,
        # and "install NI-DAQmx" advice sends the user down the wrong path.
        QMessageBox.critical(
            None, "NI services not running",
            "The NI configuration service is not running, so the app cannot\n"
            "see any DAQ device.\n\n"
            "Start the NI services (as administrator) or reboot the PC, then\n"
            "start this app again. See the README's troubleshooting section.")
        return 1
    if problem == "driver":
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
