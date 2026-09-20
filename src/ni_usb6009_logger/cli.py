#!/usr/bin/env python3
# ---------------------------------------------------------------------------
# NI USB-6009 Data Logger (CSV/XLSX) with Live Progress and Safe Filenames. Works with analog and digital inputs.
#
# 2025 David Steeman
#
#
#
# Dependencies (install inside your virtual environment):
#
#   Download NI-DAQmx from NI's website and install.
#
#   pip install nidaqmx
#   pip install numpy
#
# Excel (.xlsx) output additionally requires:
#
#   pip install openpyxl
#
# Tested with Python 3.10/3.11 on Windows with NI-DAQmx runtime installed.
# ---------------------------------------------------------------------------
# Example usage:
#
# 1) Basic logging (AI only, CSV, auto-named file in the fixed logs folder):
#    ni_usb6009_logger --device Dev1 --channels ai0 --rate 1000 --term RSE --print-first 10
#
# 2) AI + DI logging (two AI, 4 DI lines on port0), custom CSV:
#    ni_usb6009_logger --device Dev1 --channels ai0,ai1 --digital port0/line0:3 --rate 100 --term RSE --outfile .\logs\run.csv --print-first 10
#
# 3) Log to Excel (.xlsx):
#    ni_usb6009_logger --device Dev1 --channels ai0,ai1 --digital port0/line0:7 --rate 500 --term RSE --outfile .\logs\run.xlsx --print-first 10
#
# 4) Timed run (auto-stop after 30s):
#    ni_usb6009_logger --device Dev1 --channels ai0 --rate 1000 --duration 30 --print-first 10
#
# 5) Differential wiring example:
#    ni_usb6009_logger --device Dev1 --channels ai0,ai1 --rate 1000 --term DIFF --print-first 10
#
# 6) Show live counter or progress bar:
#    # Counter (default when no --duration):
#    ni_usb6009_logger --device Dev1 --channels ai0 --rate 1000 --term RSE --progress counter --print-first 10
#
#    # Progress bar (useful with duration):
#    ni_usb6009_logger --device Dev1 --channels ai0 --rate 1000 --term RSE --duration 30 --progress bar --print-first 10
#
# 7) Calibration mode (screen only, moving average):
#    ni_usb6009_logger --device Dev1 --channels ai0,ai1 --calibrate --calib-window 5 --calib-sample-rate 100 --rate 1
#
# 8) Ignition with buzzer + relay:
#    ni_usb6009_logger --device Dev1 --channels ai0 --digital port0/line0:7 --rate 1000 --term RSE --ignite --buzzer-line port1/line0 --igniter-line port1/line1 --arm-seconds 15 --stabilize-seconds 1 --pulse-seconds 1
#
# 9) Ignition with current-sense failsafe (shunt in RSE mode):
#    ni_usb6009_logger --device Dev1 --channels ai0 --rate 1000 --term RSE --ignite --buzzer-line port1/line0 --igniter-line port1/line1 --igniter-sense-ai ai2 --sense-term RSE --shunt-ohms 1.0 --continuity-min-ma 0.2 --leak-max-ma 5 --fire-confirm-ma 300
#
# This module is a thin adapter: parse_args() maps onto core.LoggerConfig and
# CliReporter reproduces the historic console output from core callbacks.
# ---------------------------------------------------------------------------
import argparse
import signal
import sys
import threading
from pathlib import Path

from ni_usb6009_logger.core.calibration import CalibrationSession
from ni_usb6009_logger.core.config import (
    CalibrationConfig,
    ConfigError,
    IgnitionConfig,
    LoggerConfig,
)
from ni_usb6009_logger.core.events import (
    CalibRow,
    Reporter,
    SessionState,
)
from ni_usb6009_logger.core.helpers import (
    expand_digital_spec,
    progress_line_bar,
    progress_line_counter,
)
from ni_usb6009_logger.core.session import IgnitionSetupError, LoggingSession

# ---------- argparse / --help ----------
def parse_args():
    class _HelpFormatter(argparse.ArgumentDefaultsHelpFormatter, argparse.RawTextHelpFormatter):
        pass

    desc = (
        "Log NI USB-6009 analog inputs (AI) and optional digital inputs (DI) to CSV or XLSX.\n"
        "AI is hardware-timed; DI on USB-6009 is static (snapshotted once per AI chunk).\n"
        "Calibration mode prints live values to the screen (no file) with optional moving-average filtering.\n"
        "Ignition mode (logging only) actuates a buzzer pre-warning, then fires a relay after stabilization."
    )

    epilog = (
        "Digital lines syntax examples:\n"
        "  --digital port0/line0:7         # all 8 lines on port0\n"
        "  --digital port0/line0,port0/line3\n"
        "\n"
        "Tips:\n"
        "  • Lower --chunk to snapshot DI more often (e.g., --chunk 100 at 1 kHz ≈ 10 DI snaps/sec)\n"
        "  • Omit --outfile to auto-save under .\\logs with timestamped filename (no-overwrite).\n"
        "  • Use --calibrate for screen-only, filtered readout (internal --calib-sample-rate, prints at --rate).\n"
        "  • Use --ignite with explicit DO lines for buzzer and relay."
    )

    p = argparse.ArgumentParser(description=desc, epilog=epilog, formatter_class=_HelpFormatter)

    # Device & channels
    p.add_argument("--device", default="Dev1", help="NI-DAQmx device name/alias as shown in NI MAX (e.g., Dev1).")
    p.add_argument("--channels", required=True,
                   help="Comma-separated AI channels relative to device, e.g. 'ai0' or 'ai0,ai1'. "
                        "At least one AI is required (USB-6009 AI provides the hardware timing).")
    p.add_argument("--digital", default="",
                   help="Optional DI lines relative to device. Accepts comma list and ranges, e.g. "
                        "'port0/line0:7' or 'port0/line0,port0/line3'. DI is snapshotted once per chunk.")

    # Sampling / analog config
    p.add_argument("--rate", type=float, default=None,
                   help="Analog output/print rate in Hz. Default is 1000 for logging, or 1 for --calibrate if not specified.")
    p.add_argument("--chunk", type=int, default=1000,
                   help="Samples per read per AI channel (logging mode). Also sets DI snapshot cadence (once per chunk).")
    p.add_argument("--vmin", type=float, default=-10.0, help="Minimum expected AI voltage (V).")
    p.add_argument("--vmax", type=float, default=10.0, help="Maximum expected AI voltage (V).")
    p.add_argument("--term", choices=["RSE","NRSE","DIFF"], default="RSE", help="AI terminal configuration.")

    # Output / formatting (logging mode)
    p.add_argument("--outfile", default="",
                   help="Output file path. If omitted, auto-named under .\\logs as ni_<device>_<YYYYmmdd_HHMMSS>.<csv|xlsx>. "
                        "Existing files are never overwritten: a suffix _1, _2, ... is appended.")
    p.add_argument("--format", choices=["csv","xlsx"], default=None,
                   help="Output format. If omitted, inferred from --outfile extension, else CSV.")
    p.add_argument("--duration", type=float, default=None, help="Seconds to run. Omit to run until Ctrl+C.")
    p.add_argument("--progress", choices=["auto","none","counter","bar"], default="auto",
                   help="Progress display mode. 'auto' = bar if --duration set, else counter.")
    p.add_argument("--update-interval", type=float, default=0.5, help="Seconds between progress updates.")
    p.add_argument("--print-first", type=int, default=0, help="Print the first N logged rows to console.")
    p.add_argument("--debug", action="store_true", help="Print extra debug info during setup and runtime.")

    # Calibration mode
    p.add_argument("--calibrate", action="store_true",
                   help="Calibration mode: screen-only live readout (no file). Output prints at --rate (default 1 Hz).")
    p.add_argument("--calib-window", type=float, default=5.0,
                   help="Moving-average window in seconds for calibration display (set 0 to disable).")
    p.add_argument("--calib-show-raw", action="store_true",
                   help="Also print raw instantaneous values (in addition to the moving average).")
    p.add_argument("--calib-sample-rate", type=float, default=100.0,
                   help="Internal hardware sampling rate in calibration mode (Hz). Feeds moving average.")

    # Ignition (logging mode only)
    p.add_argument("--ignite", action="store_true",
                   help="Enable ignition sequence (logging mode only): buzzer pre-warning, then relay pulse after logging stabilizes.")
    p.add_argument("--buzzer-line", default=None,
                   help="Digital OUTPUT line for buzzer (e.g. 'port0/line1'). Required with --ignite.")
    p.add_argument("--igniter-line", default=None,
                   help="Digital OUTPUT line for igniter relay (e.g. 'port0/line0'). Required with --ignite.")
    p.add_argument("--arm-seconds", type=float, default=15.0,
                   help="Seconds to sound buzzer before logging starts.")
    p.add_argument("--stabilize-seconds", type=float, default=1.0,
                   help="Seconds after logging starts before firing igniter.")
    p.add_argument("--pulse-seconds", type=float, default=1.0,
                   help="Duration of igniter relay ON time.")

    # Current-sense & safety
    p.add_argument("--igniter-sense-ai", default=None,
                   help="AI channel used to measure shunt voltage for igniter current (e.g. 'ai2').")
    p.add_argument("--shunt-ohms", type=float, default=1.0,
                   help="Series shunt resistance in ohms.")
    p.add_argument("--continuity-min-ma", type=float, default=0.2,
                   help="Minimum current (mA) that indicates igniter continuity present (pre-arm check).")
    p.add_argument("--leak-max-ma", type=float, default=5.0,
                   help="Maximum allowed current (mA) BEFORE ignition; above this inhibits arming/firing.")
    p.add_argument("--fire-confirm-ma", type=float, default=300.0,
                   help="Minimum current (mA) that should be observed DURING pulse to confirm ignition.")
    p.add_argument("--sense-rate", type=float, default=100.0,
                   help="Sampling rate (Hz) for current-sense AI during arming/pulse confirm.")
    p.add_argument("--sense-term", choices=["RSE","NRSE","DIFF"], default="DIFF",
                   help="Terminal configuration for the igniter sense AI channel.")

    return p.parse_args()

# ---------- CLI adapter ----------
class CliReporter(Reporter):
    """Reproduces the historic console output from core callbacks."""

    def __init__(self, args):
        self.args = args
        self._phase = SessionState.IDLE
        self._progress_mode = args.progress
        if self._progress_mode == "auto":
            self._progress_mode = "bar" if (args.duration and args.duration > 0) else "counter"
        self._progress_active = False
        self._preview_left = max(0, int(args.print_first))

    # -- helpers
    def _write(self, text):
        sys.stdout.write(text)
        sys.stdout.flush()

    def interrupt_message(self):
        if self._phase == SessionState.CALIBRATING:
            return "\nStopping calibration…"
        if self._phase == SessionState.ARMING:
            return "\nAborting arming…"
        return "\nStopping... (closing output)\n"

    # -- callbacks
    def on_state(self, state, detail=None):
        self._phase = state
        if state in (SessionState.DONE, SessionState.ABORTED, SessionState.INHIBITED,
                     SessionState.ERROR, SessionState.STOPPING) and self._progress_active:
            self._write("\n")
            self._progress_active = False

    def on_status(self, text):
        print(text)
        sys.stdout.flush()

    def on_row_preview(self, row):
        ts_iso, idx = row[0], row[1]
        n_di = self._digital_count
        ai_vals = row[2:len(row) - n_di] if n_di else row[2:]
        di_vals = row[len(row) - n_di:] if n_di else []
        print(" | ".join([ts_iso, str(idx)]
                        + [f"{v:.6f}" for v in ai_vals] + [str(v) for v in di_vals]))
        self._preview_left -= 1
        if self._preview_left == 0:
            print("(…end of preview…)")
            sys.stdout.flush()

    def on_calib_header(self, columns):
        print(" | ".join(columns))

    def on_calib_row(self, r: CalibRow):
        parts = [r.ts_iso] + [f"{v:.6f}" for v in r.averages]
        if r.raw is not None:
            parts += [f"{v:.6f}" for v in r.raw]
        parts += [str(d) for d in r.di]
        print(" | ".join(parts))

    def on_progress(self, samples_total, ch_count, elapsed, inst_rate):
        if self._progress_mode == "none":
            return
        self._progress_active = True
        line = (progress_line_bar(elapsed, self.args.duration)
                if (self._progress_mode == "bar" and self.args.duration)
                else progress_line_counter(samples_total, ch_count, elapsed, inst_rate))
        self._write("\r" + line + " " * 10)

    def on_arming(self, remaining, current_ma):
        if current_ma is not None:
            self._write(f"\rArming… {remaining:5.1f}s | I={current_ma:7.2f} mA   ")
        else:
            self._write(f"\rArming… {remaining:5.1f}s   ")


def _build_config(args) -> LoggerConfig:
    rate = args.rate
    if rate is None:
        rate = 1.0 if args.calibrate else 1000.0

    calibration = None
    if args.calibrate:
        calibration = CalibrationConfig(
            rate_out=rate,
            window_seconds=args.calib_window,
            show_raw=args.calib_show_raw,
            sample_rate=args.calib_sample_rate,
        )

    ignition = None
    if args.ignite:
        ignition = IgnitionConfig(
            buzzer_line=args.buzzer_line or "",
            igniter_line=args.igniter_line or "",
            arm_seconds=args.arm_seconds,
            stabilize_seconds=args.stabilize_seconds,
            pulse_seconds=args.pulse_seconds,
            sense_ai=args.igniter_sense_ai,
            shunt_ohms=args.shunt_ohms,
            continuity_min_ma=args.continuity_min_ma,
            leak_max_ma=args.leak_max_ma,
            fire_confirm_ma=args.fire_confirm_ma,
            sense_rate=args.sense_rate,
            sense_term=args.sense_term,
        )

    return LoggerConfig(
        device=args.device,
        channels=[c.strip() for c in args.channels.split(",") if c.strip()],
        digital_lines=expand_digital_spec(args.digital),
        rate=rate,
        chunk=args.chunk,
        vmin=args.vmin,
        vmax=args.vmax,
        term=args.term,
        logs_dir=Path(r".\logs"),
        outfile=Path(args.outfile) if args.outfile else None,
        fmt=args.format,
        duration=args.duration,
        update_interval=args.update_interval,
        print_first_rows=args.print_first,
        progress=args.progress,
        debug=args.debug,
        calibration=calibration,
        ignition=ignition,
    )


def main():
    args = parse_args()
    cfg = _build_config(args)
    reporter = CliReporter(args)
    reporter._digital_count = len(cfg.digital_lines)

    stop = threading.Event()

    def _sigint(_sig, _frame):
        stop.set()
        sys.stdout.write(reporter.interrupt_message())
        sys.stdout.flush()
        signal.signal(signal.SIGINT, signal.SIG_IGN)
    prev_handler = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, _sigint)

    try:
        if args.calibrate:
            CalibrationSession(cfg, reporter).run(stop)
        else:
            LoggingSession(cfg, reporter).run(stop)
    except ConfigError as e:
        print(e)
        sys.exit(getattr(e, "exit_code", 1))
    except IgnitionSetupError:
        # message already reported via on_status by the session
        sys.exit(3)
    finally:
        signal.signal(signal.SIGINT, prev_handler)


# ---------- CLI wrapper ----------
def run():
    """Entry-point wrapper so packaging can expose a `ni_usb6009_logger` command."""
    main()

if __name__ == "__main__":
    run()
