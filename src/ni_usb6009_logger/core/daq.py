"""The ONLY place that imports nidaqmx.

Keeping the import here (and lazy) lets the rest of the package be imported
on machines without the NI-DAQmx driver — the GUI checks availability via
driver_available() and shows a friendly dialog instead of crashing, and dev
on Linux uses NI_USB6009_FAKE=1 to swap in the in-memory fake backend.
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
    return nidaqmx


def term_map() -> dict:
    from nidaqmx.constants import TerminalConfiguration
    return {
        "RSE": TerminalConfiguration.RSE,
        "NRSE": TerminalConfiguration.NRSE,
        "DIFF": TerminalConfiguration.DIFF,
    }


def driver_available() -> bool:
    """True when the NI-DAQmx driver/runtime is installed and loadable."""
    try:
        nx = backend()
        nx.System.local().devices  # touches the driver DLL/services
        return True
    except Exception:
        return False


def enumerate_devices() -> list[tuple[str, str]]:
    """[(name, product_type)] for every DAQ visible to the driver."""
    try:
        nx = backend()
        return [(d.name, d.product_type) for d in nx.System.local().devices]
    except Exception:
        return []
