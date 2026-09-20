"""CLI parity tests: argparse surface and --help must stay byte-identical.

Captured BEFORE the core refactor (Phase 1) so the Phase-2 rewrite of cli.py
into a thin adapter is provably behavior-preserving.
"""
import sys
from pathlib import Path

GOLDEN_HELP = Path(__file__).parent / "golden" / "cli_help.txt"


def _namespace(cli, argv):
    old = sys.argv
    sys.argv = ["ni_usb6009_logger"] + argv
    try:
        return cli.parse_args()
    finally:
        sys.argv = old


def test_help_golden(cli, capsys):
    sys.argv = ["ni_usb6009_logger", "--help"]
    try:
        cli.parse_args()
        raise AssertionError("--help should exit")
    except SystemExit as e:
        assert e.code == 0
    out = capsys.readouterr().out
    golden = GOLDEN_HELP.read_text(encoding="utf-8")
    assert out == golden, "--help output changed vs golden"


def test_parse_args_defaults(cli):
    a = _namespace(cli, ["--channels", "ai0"])
    assert a.device == "Dev1"
    assert a.channels == "ai0"
    assert a.digital == ""
    assert a.rate is None            # mode default applied later in main()
    assert a.chunk == 1000
    assert (a.vmin, a.vmax) == (-10.0, 10.0)
    assert a.term == "RSE"
    assert a.outfile == ""
    assert a.format is None
    assert a.duration is None
    assert a.progress == "auto"
    assert a.update_interval == 0.5
    assert a.print_first == 0
    assert a.debug is False
    assert a.calibrate is False
    assert a.calib_window == 5.0
    assert a.calib_show_raw is False
    assert a.calib_sample_rate == 100.0
    assert a.ignite is False
    assert a.buzzer_line is None
    assert a.igniter_line is None
    assert a.arm_seconds == 15.0
    assert a.stabilize_seconds == 1.0
    assert a.pulse_seconds == 1.0
    assert a.igniter_sense_ai is None
    assert a.shunt_ohms == 1.0
    assert a.continuity_min_ma == 0.2
    assert a.leak_max_ma == 5.0
    assert a.fire_confirm_ma == 300.0
    assert a.sense_rate == 100.0
    assert a.sense_term == "DIFF"


def test_parse_args_full_ignition(cli):
    a = _namespace(cli, [
        "--device", "Dev2", "--channels", "ai0,ai1", "--digital", "port0/line0:3",
        "--rate", "500", "--chunk", "100", "--term", "DIFF",
        "--outfile", "out.xlsx", "--format", "xlsx", "--duration", "30",
        "--progress", "bar", "--print-first", "5",
        "--ignite", "--buzzer-line", "port1/line0", "--igniter-line", "port1/line1",
        "--arm-seconds", "10", "--stabilize-seconds", "2", "--pulse-seconds", "0.5",
        "--igniter-sense-ai", "ai2", "--shunt-ohms", "0.5",
        "--continuity-min-ma", "1", "--leak-max-ma", "8", "--fire-confirm-ma", "250",
        "--sense-rate", "200", "--sense-term", "RSE",
    ])
    assert a.device == "Dev2"
    assert a.channels == "ai0,ai1"
    assert a.digital == "port0/line0:3"
    assert a.rate == 500.0
    assert a.chunk == 100
    assert a.term == "DIFF"
    assert a.outfile == "out.xlsx"
    assert a.format == "xlsx"
    assert a.duration == 30.0
    assert a.progress == "bar"
    assert a.print_first == 5
    assert a.ignite is True
    assert a.buzzer_line == "port1/line0"
    assert a.igniter_line == "port1/line1"
    assert a.arm_seconds == 10.0
    assert a.stabilize_seconds == 2.0
    assert a.pulse_seconds == 0.5
    assert a.igniter_sense_ai == "ai2"
    assert a.shunt_ohms == 0.5
    assert a.continuity_min_ma == 1.0
    assert a.leak_max_ma == 8.0
    assert a.fire_confirm_ma == 250.0
    assert a.sense_rate == 200.0
    assert a.sense_term == "RSE"


def test_channels_required(cli, capsys):
    import pytest
    with pytest.raises(SystemExit) as e:
        _namespace(cli, [])
    assert e.value.code == 2
    assert "required" in capsys.readouterr().err
