"""Core-level tests beyond CLI parity: config mapping, recovery dual-write,
and the GUI fire-permission gate.
"""
import csv
import sys
import threading
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ni_usb6009_logger.core.config import (  # noqa: E402
    CalibrationConfig,
    ConfigError,
    IgnitionConfig,
    LoggerConfig,
    validate,
)
from ni_usb6009_logger.core.events import Reporter, SessionState  # noqa: E402
from ni_usb6009_logger.core.session import LoggingSession  # noqa: E402


# --------------------------------------------------------------- config map
def test_build_config_maps_flags(fake_daq, monkeypatch, tmp_path):
    import ni_usb6009_logger.cli as cli
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", [
        "ni_usb6009_logger", "--device", "Dev1", "--channels", "ai0, ai1",
        "--digital", "port0/line0:1", "--rate", "250",
        "--ignite", "--buzzer-line", "port1/line0", "--igniter-line", "port1/line1",
        "--arm-seconds", "5", "--igniter-sense-ai", "ai3",
    ])
    args = cli.parse_args()
    cfg = cli._build_config(args)
    assert cfg.device == "Dev1"
    assert cfg.channels == ["ai0", "ai1"]
    assert cfg.digital_lines == ["port0/line0", "port0/line1"]
    assert cfg.rate == 250.0
    assert cfg.ignition.buzzer_line == "port1/line0"
    assert cfg.ignition.igniter_line == "port1/line1"
    assert cfg.ignition.arm_seconds == 5.0
    assert cfg.ignition.sense_ai == "ai3"
    assert cfg.outfile is None and str(cfg.logs_dir) == r".\logs"


def test_build_config_calibrate_defaults(fake_daq, monkeypatch, tmp_path):
    import ni_usb6009_logger.cli as cli
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["ni_usb6009_logger", "--channels", "ai0", "--calibrate"])
    cfg = cli._build_config(cli.parse_args())
    assert cfg.rate == 1.0
    assert cfg.calibration.rate_out == 1.0
    assert cfg.calibration.sample_rate == 100.0
    assert cfg.ignition is None


def test_validate_rejects(fake_daq):
    with pytest.raises(ConfigError) as e:
        validate(LoggerConfig(channels=[]))
    assert "At least one analog input" in str(e.value)

    cfg = LoggerConfig(channels=["ai0"], calibration=CalibrationConfig(),
                       ignition=IgnitionConfig())
    with pytest.raises(ConfigError) as e:
        validate(cfg)
    assert e.value.exit_code == 2


# ------------------------------------------------------- recovery dual-write
def _logging_cfg(tmp_path, **kw):
    return LoggerConfig(
        device="Dev1", channels=["ai0", "ai1"],
        rate=100, chunk=10,
        outfile=Path(tmp_path) / "main.csv",
        duration=0.3, update_interval=0.05,
        **kw,
    )


def test_recovery_dual_write_and_ok_rename(fake_daq, tmp_path):
    cfg = _logging_cfg(tmp_path, recovery=True)
    result = LoggingSession(cfg, Reporter()).run()
    assert result.state == SessionState.DONE
    main_rows = list(csv.reader(open(tmp_path / "main.csv")))
    rec_path = tmp_path / "recovery" / "main_recovery_OK.csv"
    rec_rows = list(csv.reader(open(rec_path)))
    assert result.recovery_path == rec_path
    assert main_rows == rec_rows, "recovery CSV must mirror the main file"
    assert len(main_rows) > 10


def test_no_recovery_by_default(fake_daq, tmp_path):
    result = LoggingSession(_logging_cfg(tmp_path), Reporter()).run()
    assert result.recovery_path is None
    assert not (tmp_path / "recovery").exists()


def test_require_explicit_output(fake_daq, tmp_path):
    cfg = _logging_cfg(tmp_path)
    cfg.outfile = None
    cfg.require_explicit_output = True
    with pytest.raises(ConfigError):
        LoggingSession(cfg, Reporter()).run()


# ---------------------------------------------------- GUI fire permission gate
class _StateRecorder(Reporter):
    def __init__(self):
        self.states = []
        self.do_writes = []

    def on_state(self, state, detail=None):
        self.states.append(state)


def _ignite_cfg(tmp_path):
    return LoggerConfig(
        device="Dev1", channels=["ai0"], rate=100, chunk=10,
        outfile=Path(tmp_path) / "fire.csv",
        duration=1.0, update_interval=0.05,
        ignition=IgnitionConfig(
            buzzer_line="port1/line0", igniter_line="port1/line1",
            arm_seconds=0.2, stabilize_seconds=0.2, pulse_seconds=0.2,
            sense_ai="ai2", sense_term="RSE", sense_rate=200,
        ),
    )


def test_fire_permission_blocks_until_set(fake_daq, tmp_path):
    fake_daq.STATE.ai_voltage_overrides["Dev1/ai2"] = 0.0003  # continuity OK
    rec = _StateRecorder()
    fire = threading.Event()
    cfg = _ignite_cfg(tmp_path)
    t = threading.Thread(target=lambda: LoggingSession(cfg, rec).run(fire_permission=fire))
    t.start()
    # wait for FIRE_PENDING, keep permission withheld a moment
    deadline = time.time() + 5
    while not any(s == SessionState.FIRE_PENDING for s in rec.states):
        assert time.time() < deadline, f"no FIRE_PENDING; states={rec.states}"
        time.sleep(0.02)
    time.sleep(0.2)
    writes_before = list(fake_daq.do_write_sequences())
    assert all(w != [False, True] for w in writes_before), \
        "relay must stay OFF while fire permission withheld"
    fire.set()
    t.join(timeout=10)
    assert not t.is_alive()
    writes = fake_daq.do_write_sequences()
    assert [False, True] in writes, "relay must fire after permission granted"
    assert writes[-1] == [False, False]


def test_fire_withheld_until_stop_aborts_without_fire(fake_daq, tmp_path):
    fake_daq.STATE.ai_voltage_overrides["Dev1/ai2"] = 0.0003
    rec = _StateRecorder()
    fire = threading.Event()
    stop = threading.Event()
    cfg = _ignite_cfg(tmp_path)
    result_holder = {}

    def _run():
        result_holder["r"] = LoggingSession(cfg, rec).run(stop=stop, fire_permission=fire)

    t = threading.Thread(target=_run)
    t.start()
    deadline = time.time() + 5
    while not any(s == SessionState.FIRE_PENDING for s in rec.states):
        assert time.time() < deadline
        time.sleep(0.02)
    stop.set()  # ABORT instead of granting fire
    t.join(timeout=10)
    assert not t.is_alive()
    writes = fake_daq.do_write_sequences()
    assert all(w != [False, True] for w in writes), "abort must not fire the relay"
    assert writes[-1] == [False, False], "DO lines forced LOW on abort"
    assert result_holder["r"].state == SessionState.ABORTED
