"""The ONLY place that imports nidaqmx.

Keeping the import here (and lazy) lets the rest of the package be imported
on machines without the NI-DAQmx driver — the GUI checks availability via
enumerate_devices_ex() and shows a friendly dialog instead of crashing, and
dev on Linux uses NI_USB6009_FAKE=1 to swap in the in-memory fake backend.
"""
import os
import sys


def backend():
    """Return the nidaqmx module (real, or fake when NI_USB6009_FAKE=1)."""
    mod = sys.modules.get("nidaqmx")
    if mod is not None and getattr(mod, "__fake__", False):
        return mod
    if os.environ.get("NI_USB6009_FAKE"):
        from ni_usb6009_logger import _fake_nidaqmx
        if not getattr(sys.modules.get("nidaqmx"), "__fake__", False):
            _fake_nidaqmx.install()
    import nidaqmx
    # Which submodules nidaqmx/__init__.py binds is a version detail, and it
    # binds neither `system` nor `stream_readers` as of 1.6.0 -- `System` has
    # never been a top-level attribute at all. Import every submodule the
    # package reaches through backend() so nx.<sub> is guaranteed, whatever
    # __init__ does. Accessing one it did not happen to bind is how
    # driver_available() and the AnalogMultiChannelReader lookup both broke.
    import nidaqmx.constants    # noqa: F401
    import nidaqmx.errors       # noqa: F401
    import nidaqmx.stream_readers  # noqa: F401
    import nidaqmx.system       # noqa: F401
    return nidaqmx


def term_map() -> dict:
    from nidaqmx.constants import TerminalConfiguration
    return {
        "RSE": TerminalConfiguration.RSE,
        "NRSE": TerminalConfiguration.NRSE,
        "DIFF": TerminalConfiguration.DIFF,
    }


def safe_stop(task) -> None:
    """Best-effort Task.stop(); a failure here must not mask the real error."""
    try:
        task.stop()
    except Exception:
        pass


def normalize_di_read(vals) -> list:
    """A DI task read as a list, whatever shape the driver returned.

    DAQmx unwraps single-channel reads: one DI line yields a bare bool,
    multiple lines a list. Iterating the raw return crashed the per-chunk
    DI snapshot on real hardware (the fake always returned a list), so
    every DI read goes through here.
    """
    if isinstance(vals, (list, tuple)):
        return list(vals)
    return [vals]


def daq_error_type() -> type[BaseException]:
    """The backend's DaqError class, for front-ends that catch it.

    Resolved through backend() so a front-end never imports nidaqmx itself and
    so the fake's DaqError is matched under NI_USB6009_FAKE. Falls back to a
    class that catches nothing when the driver is unavailable.
    """
    try:
        return backend().errors.DaqError
    except Exception:
        class _NeverRaised(Exception):
            pass
        return _NeverRaised


def enumerate_devices_ex() -> tuple[list[tuple[str, str]], str | None]:
    """(devices, problem) — an empty list is not also an empty explanation.

    problem is None (driver healthy), "service" (driver installed but the NI
    configuration database is unreachable — mxssvr stopped, as seen on the
    dev box: "MAX: (Hex 0x8004032B) The configuration database is not
    running") or "driver" (no usable NI-DAQmx runtime).
    """
    global _last_import_error
    try:
        nx = backend()
        _last_import_error = None
    except Exception as e:
        _last_import_error = f"{type(e).__name__}: {e}"
        return [], "driver"
    try:
        devices = [(d.name, d.product_type)
                   for d in nx.system.System.local().devices]
        return devices, None
    except nx.errors.DriverNotInstalledError:
        return [], "driver"
    except nx.errors.DaqError:
        # Enumeration reaching the driver but failing means the driver's
        # backend services, not the desk, are the problem.
        return [], "service"
    except Exception:
        return [], "driver"


def enumerate_devices() -> list[tuple[str, str]]:
    """[(name, product_type)] for every DAQ visible to the driver."""
    return enumerate_devices_ex()[0]


_last_import_error = None


def last_import_error() -> str | None:
    """Why backend() last failed to import nidaqmx, for --selftest output."""
    return _last_import_error
