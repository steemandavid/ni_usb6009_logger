"""Test configuration: inject the fake nidaqmx before the package is imported.

The real nidaqmx package (and the NI-DAQmx driver behind it) never exists on
the dev/CI machines; every test runs against tests/fake_nidaqmx.py.
"""
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).parent
SRC_DIR = TESTS_DIR.parent / "src"

sys.path.insert(0, str(TESTS_DIR))
sys.path.insert(0, str(SRC_DIR))

import fake_nidaqmx  # noqa: E402


@pytest.fixture
def fake_daq(monkeypatch):
    """Install the fake DAQ backend and return its state knobs."""
    fake_nidaqmx.install()
    fake_nidaqmx.reset(devices=["Dev1"])
    # Force a fresh import of the package so it binds to the fake modules.
    for mod in [m for m in sys.modules if m.startswith("ni_usb6009_logger")]:
        del sys.modules[mod]
    yield fake_nidaqmx
    fake_nidaqmx.uninstall()


@pytest.fixture
def cli(fake_daq, monkeypatch):
    """The CLI module bound to the fake DAQ."""
    import ni_usb6009_logger.cli as cli
    return cli


@pytest.fixture
def run_cli(cli, monkeypatch, tmp_path):
    """Run cli.main() with argv-style args inside tmp_path; returns (cap, rc)."""
    monkeypatch.chdir(tmp_path)

    def _run(*argv):
        monkeypatch.setattr(sys, "argv", ["ni_usb6009_logger", *argv])
        rc = 0
        try:
            cli.main()
        except SystemExit as e:
            rc = e.code if isinstance(e.code, int) else 1
        return rc

    return _run
