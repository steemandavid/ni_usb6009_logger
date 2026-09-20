"""End-to-end CLI runs against the fake DAQ: data content, DO sequences,
and safety inhibits. Values come from fake_nidaqmx.waveform() and are exact,
so logged AI columns can be compared value-for-value (timestamps excluded).
"""
import csv
import math
import re

TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}$")


def _read_rows(path):
    with open(path, newline="") as f:
        return list(csv.reader(f))


def _expected_v(ch_index, sample_index, rate):
    return (1.0 + ch_index) * math.sin(2.0 * math.pi * sample_index / rate)


def test_logging_csv_content(run_cli, fake_daq, tmp_path):
    rc = run_cli(
        "--device", "Dev1", "--channels", "ai0,ai1",
        "--digital", "port0/line0:1",
        "--rate", "100", "--chunk", "10", "--term", "RSE",
        "--outfile", "run.csv", "--duration", "0.4", "--progress", "none",
    )
    assert rc == 0
    rows = _read_rows(tmp_path / "run.csv")
    header, data = rows[0], rows[1:]
    assert header == ["timestamp_iso", "sample_index", "ai0", "ai1",
                      "di_port0_line0", "di_port0_line1"]
    n = len(data)
    assert 30 <= n <= 60, f"unexpected chunk count: {n}"
    for i, row in enumerate(data):
        assert TS_RE.match(row[0])
        assert int(row[1]) == i, "sample_index must be contiguous"
        assert float(row[2]) == _expected_v(0, i, 100.0)
        assert float(row[3]) == _expected_v(1, i, 100.0)
        assert row[4:] == ["0", "0"], "DI defaults to LOW"


def test_logging_auto_named_no_overwrite(run_cli, tmp_path):
    for _ in range(2):
        rc = run_cli("--device", "Dev1", "--channels", "ai0",
                     "--rate", "100", "--chunk", "10",
                     "--duration", "0.15", "--progress", "none")
        assert rc == 0
    logs = sorted((tmp_path / "logs").glob("ni_Dev1_*.csv"))
    assert len(logs) == 2, "second run must not overwrite the first"


def test_calibration_screen_only(run_cli, capsys, tmp_path):
    import _thread
    import threading
    # Calibration runs until Ctrl+C; simulate one after 1 s. interrupt_main()
    # trips SIGINT in the main thread and runs the handler cli.main() installed,
    # exactly like a real Ctrl+C -- and unlike os.kill(os.getpid(), SIGINT),
    # which on Windows falls through to TerminateProcess and kills the runner.
    stopper = threading.Timer(1.0, _thread.interrupt_main)
    stopper.start()
    try:
        rc = run_cli("--device", "Dev1", "--channels", "ai0",
                     "--calibrate", "--calib-sample-rate", "50",
                     "--rate", "5")
    finally:
        stopper.cancel()
    assert rc == 0
    out = capsys.readouterr().out
    assert "Calibration mode: screen-only live readout (no file)." in out
    assert not list(tmp_path.glob("logs/**")), "calibration writes no files"


def test_calibrate_plus_ignite_rejected(run_cli, capsys):
    rc = run_cli("--channels", "ai0", "--calibrate", "--ignite",
                 "--buzzer-line", "port1/line0", "--igniter-line", "port1/line1")
    assert rc == 2
    assert "--ignite cannot be used together with --calibrate" in capsys.readouterr().out


def test_ignite_requires_do_lines(run_cli, capsys):
    rc = run_cli("--channels", "ai0", "--ignite")
    assert rc == 2
    assert "requires both --buzzer-line and --igniter-line" in capsys.readouterr().out


def _ignite_argv(**overrides):
    argv = [
        "--device", "Dev1", "--channels", "ai0",
        "--rate", "100", "--chunk", "10", "--term", "RSE",
        "--outfile", "fire.csv", "--duration", "1.0", "--progress", "none",
        "--ignite", "--buzzer-line", "port1/line0", "--igniter-line", "port1/line1",
        "--arm-seconds", "0.3", "--stabilize-seconds", "0.2", "--pulse-seconds", "0.2",
        "--igniter-sense-ai", "ai2", "--sense-term", "RSE",
        "--shunt-ohms", "1.0",
        "--continuity-min-ma", "0.2", "--leak-max-ma", "5", "--fire-confirm-ma", "300",
        "--sense-rate", "200",
    ]
    for k, v in overrides.items():
        argv += [f"--{k.replace('_', '-')}", str(v)]
    return argv


def test_ignition_do_sequence(run_cli, fake_daq, tmp_path):
    # Continuity current 0.3 mA: above continuity-min, below leak-max.
    fake_daq.STATE.ai_voltage_overrides["Dev1/ai2"] = 0.0003
    rc = run_cli(*_ignite_argv())
    assert rc == 0
    writes = fake_daq.do_write_sequences()
    assert writes[0] == [False, False], "safety: DO forced LOW first"
    assert [True, False] in writes, "buzzer must sound during arming"
    assert writes.index([True, False]) < writes.index([False, True]), \
        "buzzer before relay"
    assert [False, True] in writes, "relay must fire after stabilization"
    assert writes.index([False, True]) < writes.index([False, False], writes.index([False, True])), \
        "relay must turn off after pulse"
    assert writes[-1] == [False, False], "final state: everything LOW"
    assert (tmp_path / "fire.csv").exists()


def test_ignition_leak_inhibits_fire(run_cli, fake_daq, capsys):
    # 10 mA through 1 Ω shunt: above leak-max → inhibit during arming.
    fake_daq.STATE.ai_voltage_overrides["Dev1/ai2"] = 0.01
    rc = run_cli(*_ignite_argv())
    assert rc == 0  # inhibit is a clean stop, not an error exit
    writes = fake_daq.do_write_sequences()
    assert all(w != [False, True] for w in writes), "relay must never fire"
    assert writes[-1] == [False, False]
    out = capsys.readouterr().out
    assert "leak current detected above limit" in out
    assert "Ignition inhibited" in out


def test_ignition_no_continuity_inhibits_fire(run_cli, fake_daq, capsys):
    # 0 mA: continuity never confirmed → inhibit after arming.
    fake_daq.STATE.ai_voltage_overrides["Dev1/ai2"] = 0.0
    rc = run_cli(*_ignite_argv())
    assert rc == 0
    writes = fake_daq.do_write_sequences()
    assert all(w != [False, True] for w in writes), "relay must never fire"
    assert "continuity not detected" in capsys.readouterr().out


def test_missing_device_reports_driver_error(run_cli, fake_daq, capsys):
    fake_daq.reset(devices=[])  # DAQ unplugged
    # AI task verification fails. The DaqError used to propagate as a raw
    # traceback; cli.main() now reports it in the driver's own words.
    rc = run_cli("--device", "Dev1", "--channels", "ai0",
                 "--rate", "100", "--chunk", "10", "--duration", "0.2",
                 "--progress", "none")
    assert rc == 1
    out = capsys.readouterr().out
    assert "DAQ driver error:" in out
    assert "not present in NI-DAQmx" in out
    assert "Traceback" not in out
