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
#    # Progress bar (useful with duration):
#    ni_usb6009_logger --device Dev1 --channels ai0 --rate 1000 --term RSE --duration 30 --progress bar --print-first 10
#
# 7) Calibration (screen-only; internal higher sample rate → moving average; output at --rate, default 1 Hz):
#    ni_usb6009_logger --device Dev1 --channels ai0,ai1 --calibrate --calib-window 5 --calib-sample-rate 100 --rate 1
#
# 8) IGNITION (buzzer pre-warn, then fire relay) — DO lines forced LOW immediately at script start:
#    ni_usb6009_logger --device Dev1 --channels ai0 --digital port0/line0:7 --rate 1000 --term RSE ^
#      --ignite --buzzer-line port1/line0 --igniter-line port1/line1 --arm-seconds 15 --stabilize-seconds 1 --pulse-seconds 1
#
# Notes on digital inputs (USB-6009):
# - DI is "static" (no hardware timing). This script snapshots DI once per analog chunk and repeats the snapshot
#   for each row in that chunk. To increase the effective DI sampling frequency, lower --chunk.
#
# File naming when --outfile is omitted:
#   .\logs\ni_<device>_<YYYYmmdd_HHMMSS>.<csv|xlsx>
# ---------------------------------------------------------------------------

import argparse, time, csv, signal, sys
from collections import deque
from pathlib import Path
import numpy as np

import nidaqmx
from nidaqmx.constants import (
    AcquisitionType, TerminalConfiguration, LineGrouping, TaskMode
)
from nidaqmx.stream_readers import AnalogMultiChannelReader

# ---------- Writers ----------
class BaseWriter:
    def write_header(self, header): ...
    def write_row(self, row): ...
    def flush(self): ...
    def close(self): ...

class CSVWriter(BaseWriter):
    def __init__(self, path: Path):
        self._f = path.open("w", newline="")
        self._writer = csv.writer(self._f)
    def write_header(self, header): self._writer.writerow(header); self._f.flush()
    def write_row(self, row): self._writer.writerow(row)
    def flush(self): self._f.flush()
    def close(self):
        try: self._f.flush()
        finally: self._f.close()

class XLSXWriter(BaseWriter):
    def __init__(self, path: Path, sheet_name="DAQ"):
        try:
            from openpyxl import Workbook
        except ImportError:
            print("Excel output requires 'openpyxl'. Install with: pip install openpyxl")
            raise
        self._path = path
        self._wb = Workbook(write_only=True)
        self._ws = self._wb.create_sheet(title=sheet_name)
        if len(self._wb._sheets) > 1 and self._wb._sheets[0].title != sheet_name:
            self._wb.remove(self._wb._sheets[0])
    def write_header(self, header): self._ws.append(header)
    def write_row(self, row): self._ws.append(row)
    def flush(self): pass
    def close(self):
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._wb.save(str(self._path))

# ---------- DAQ setup ----------
TERM_MAP = {
    "RSE":  TerminalConfiguration.RSE,
    "NRSE": TerminalConfiguration.NRSE,
    "DIFF": TerminalConfiguration.DIFF,
}

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
                   help="Digital OUTPUT line for buzzer (e.g. 'port1/line0'). Required with --ignite.")
    p.add_argument("--igniter-line", default=None,
                   help="Digital OUTPUT line for igniter relay (e.g. 'port1/line1'). Required with --ignite.")
    p.add_argument("--arm-seconds", type=float, default=15.0,
                   help="Seconds to sound buzzer before logging starts.")
    p.add_argument("--stabilize-seconds", type=float, default=1.0,
                   help="Seconds after logging starts before firing igniter.")
    p.add_argument("--pulse-seconds", type=float, default=1.0,
                   help="Duration of igniter relay ON time.")

    return p.parse_args()

# ---------- Filename helper ----------
def safe_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem, suffix, parent = path.stem, path.suffix, path.parent
    i = 1
    while True:
        candidate = parent / f"{stem}_{i}{suffix}"
        if not candidate.exists():
            return candidate
        i += 1

def infer_output(args):
    if args.format:
        fmt = args.format
    elif args.outfile:
        ext = Path(args.outfile).suffix.lower()
        fmt = "xlsx" if ext == ".xlsx" else "csv"
    else:
        fmt = "csv"

    if args.outfile:
        out = Path(args.outfile)
        if fmt == "xlsx" and out.suffix.lower() != ".xlsx":
            out = out.with_suffix(".xlsx")
        if fmt == "csv" and out.suffix.lower() != ".csv":
            out = out.with_suffix(".csv")
    else:
        ts = time.strftime('%Y%m%d_%H%M%S')
        base = f"ni_{args.device}_{ts}"
        folder = Path(r".\logs")
        folder.mkdir(parents=True, exist_ok=True)
        out = folder / f"{base}.{fmt}"

    out = safe_path(out)
    return fmt, out

# ---------- Digital line utilities ----------
def expand_digital_spec(spec: str):
    if not spec or not spec.strip():
        return []
    parts = []
    for token in [t.strip() for t in spec.split(",") if t.strip()]:
        if ":" in token:
            port, linerange = token.split("/line", 1)
            a, b = linerange.split(":")
            a, b = int(a), int(b)
            if b < a:
                a, b = b, a
            for i in range(a, b+1):
                parts.append(f"{port}/line{i}")
        else:
            parts.append(token)
    uniq, seen = [], set()
    for p in parts:
        if p not in seen:
            uniq.append(p); seen.add(p)
    return uniq

# ---------- Progress helpers ----------
def format_rate(samples_per_sec):
    if samples_per_sec >= 1e6: return f"{samples_per_sec/1e6:.2f} MS/s"
    if samples_per_sec >= 1e3: return f"{samples_per_sec/1e3:.2f} kS/s"
    return f"{samples_per_sec:.0f} S/s"

def progress_line_counter(samples_total, ch_count, elapsed, inst_rate):
    agg_samples = samples_total * ch_count
    rate_str = format_rate(inst_rate * ch_count)
    return f"[{elapsed:6.1f}s] samples/ch: {samples_total:,} | total: {agg_samples:,} | ~{rate_str}"

def progress_line_bar(elapsed, duration, width=30):
    frac = min(max(elapsed / duration, 0.0), 1.0) if duration else 0.0
    filled = int(frac * width)
    bar = "█" * filled + " " * (width - filled)
    percent = int(frac * 100)
    remaining = max(duration - elapsed, 0.0)
    return f"[{bar}] {percent:3d}% | elapsed {elapsed:5.1f}s | ETA {remaining:5.1f}s"

# ---------- Calibration ----------
def run_calibration(args, ch_full, di_lines, ch_short):
    print("Calibration mode: screen-only live readout (no file).")
    rate_out = 1.0 if args.rate is None else float(args.rate)
    rate_hw = float(args.calib_sample_rate)
    window_samples = 1 if args.calib_window <= 0 else max(1, int(round(args.calib_window * rate_hw)))
    print(f"Internal HW rate: {rate_hw:.3f} Hz | Output rate: {rate_out:.3f} Hz | MA window: {window_samples} sample(s) (~{args.calib_window:.2f}s)")

    stop = False
    def _sigint(_sig, _frame):
        nonlocal stop
        stop = True
        print("\nStopping calibration…")
        signal.signal(signal.SIGINT, signal.SIG_IGN)
    prev_handler = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, _sigint)

    chunk = max(1, int(rate_hw * 0.2))
    try:
        with nidaqmx.Task() as ai_task:
            for ch in ch_full:
                ai_task.ai_channels.add_ai_voltage_chan(ch, min_val=args.vmin, max_val=args.vmax, terminal_config=TERM_MAP[args.term])
            buf_samps = max(int(rate_hw * 3), chunk * 2)
            ai_task.timing.cfg_samp_clk_timing(rate=rate_hw, sample_mode=AcquisitionType.CONTINUOUS, samps_per_chan=buf_samps)
            ai_task.control(TaskMode.TASK_VERIFY)

            di_task = None
            if di_lines:
                di_task = nidaqmx.Task()
                for ln in di_lines:
                    di_task.di_channels.add_di_chan(f"{args.device}/{ln}", line_grouping=LineGrouping.CHAN_PER_LINE)
                di_task.control(TaskMode.TASK_VERIFY)

            ai_reader = AnalogMultiChannelReader(ai_task.in_stream)
            ch_count = len(ch_full)
            ai_buf = np.zeros((ch_count, chunk), dtype=np.float64)
            hist = [deque(maxlen=window_samples) for _ in range(ch_count)]

            hdr = ["time"] + [f"{name}_avg" for name in ch_short]
            if args.calib_show_raw: hdr += [f"{name}_raw" for name in ch_short]
            hdr += [("di_" + ln.replace("/", "_")).replace(":", "_") for ln in di_lines]
            print(" | ".join(hdr))

            ai_task.start()
            if di_task: di_task.start()

            next_print = time.time()
            try:
                while not stop:
                    ai_reader.read_many_sample(ai_buf, number_of_samples_per_channel=chunk, timeout=max(2.0, chunk / rate_hw * 2))
                    for j in range(chunk):
                        for i in range(ch_count): hist[i].append(ai_buf[i, j])

                    now = time.time()
                    if now >= next_print:
                        avgs = [sum(h) / len(h) if len(h) > 0 else 0.0 for h in hist]
                        ts_iso = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(now))
                        if di_task:
                            di_vals = di_task.read()
                            di_vals = [1 if bool(v) else 0 for v in di_vals]
                        else:
                            di_vals = []
                        parts = [ts_iso] + [f"{v:.6f}" for v in avgs]
                        if args.calib_show_raw:
                            raw_vals = ai_buf[:, -1].tolist()
                            parts += [f"{v:.6f}" for v in raw_vals]
                        parts += [str(d) for d in di_vals]
                        print(" | ".join(parts))
                        next_print = now + (1.0 / max(rate_out, 1e-6))
            except KeyboardInterrupt:
                print("\nStopping calibration…")
            finally:
                try: ai_task.stop()
                except: pass
                if di_task:
                    try: di_task.stop()
                    except: pass
                    di_task.close()
    finally:
        signal.signal(signal.SIGINT, prev_handler)

# ---------- Main (logging + ignition) ----------
def main():
    args = parse_args()

    # Defaults by mode
    if args.rate is None:
        args.rate = 1.0 if args.calibrate else 1000.0

    ch_short = [c.strip() for c in args.channels.split(",") if c.strip()]
    if not ch_short:
        print("At least one analog input channel is required.")
        sys.exit(1)
    ch_full = [f"{args.device}/{c}" for c in ch_short]
    ch_count = len(ch_full)

    di_lines = expand_digital_spec(args.digital)
    di_headers = [("di_" + ln.replace("/", "_")).replace(":", "_") for ln in di_lines]

    # Safety checks
    if args.calibrate and args.ignite:
        print("Error: --ignite cannot be used together with --calibrate.")
        sys.exit(2)
    if args.ignite and (not args.buzzer_line or not args.igniter_line):
        print("Error: --ignite requires both --buzzer-line and --igniter-line.")
        sys.exit(2)

    # Create DO task immediately (safe state FIRST) when ignition is requested
    do_task = None
    if args.ignite:
        try:
            do_task = nidaqmx.Task()
            # Fixed order [buzzer, igniter] for atomic writes
            do_task.do_channels.add_do_chan(f"{args.device}/{args.buzzer_line}", line_grouping=LineGrouping.CHAN_PER_LINE)
            do_task.do_channels.add_do_chan(f"{args.device}/{args.igniter_line}", line_grouping=LineGrouping.CHAN_PER_LINE)
            # SAFETY: force both LOW immediately at start
            do_task.write([False, False], auto_start=True)
            do_task.control(TaskMode.TASK_VERIFY)
            print("Safety: DO lines set LOW at start (buzzer=LOW, igniter=LOW).")
        except Exception as e:
            print(f"Error preparing ignition DO task: {e}")
            if do_task:
                try: do_task.close()
                except: pass
            sys.exit(3)

    # Calibration mode (no file I/O)
    if args.calibrate:
        print("Starting logger… (calibration mode setup)")
        print(f"AI channels: {', '.join(ch_full)} | term={args.term} | range=[{args.vmin},{args.vmax}] V")
        if di_lines:
            print(f"DI lines: {', '.join(di_lines)}")
        run_calibration(args, ch_full, di_lines, ch_short)
        # Ensure DO lines are LOW on exit (already LOW), then close task
        if do_task:
            try: do_task.write([False, False], auto_start=True)
            except: pass
            try: do_task.close()
            except: pass
        return

    # ---- Normal logging mode below ----
    fmt, out = infer_output(args)
    out.parent.mkdir(parents=True, exist_ok=True)

    mode = args.progress
    if mode == "auto":
        mode = "bar" if args.duration and args.duration > 0 else "counter"

    print("Starting logger… (initializing tasks)")
    print(f"Output → {out}   Format={fmt.upper()}")
    print(f"AI channels: {', '.join(ch_full)} | term={args.term} | range=[{args.vmin},{args.vmax}] V | rate={args.rate} Hz | chunk={args.chunk}")
    if di_lines:
        print(f"DI lines: {', '.join(di_lines)} (snapshotted per chunk)")
    if args.duration:
        print(f"Duration: ~{args.duration} s (Ctrl+C to stop early)")
    if args.print_first > 0:
        print(f"Will print the first {args.print_first} rows below as they are logged.")

    try:
        # Arming phase if ignition enabled
        if do_task:
            print(f"ARMING: Sounding buzzer for {args.arm_seconds:.1f} s. Press Ctrl+C to abort.")
            stop_arm = False
            def _arm_sigint(_s, _f):
                nonlocal stop_arm
                stop_arm = True
                print("\nAborting arming…")
            prev = signal.getsignal(signal.SIGINT)
            signal.signal(signal.SIGINT, _arm_sigint)

            try:
                do_task.write([True, False], auto_start=True)  # buzzer ON
                t_end = time.time() + args.arm_seconds
                while time.time() < t_end and not stop_arm:
                    remaining = max(0.0, t_end - time.time())
                    sys.stdout.write(f"\rArming… {remaining:5.1f}s remaining   ")
                    sys.stdout.flush()
                    time.sleep(0.1)
            finally:
                # Always silence buzzer
                do_task.write([False, False], auto_start=True)
                sys.stdout.write("\rArming… done.                      \n")
                sys.stdout.flush()
                signal.signal(signal.SIGINT, prev)

            if stop_arm:
                print("Arming aborted by user. Exiting.")
                if do_task:
                    try: do_task.write([False, False], auto_start=True)
                    except: pass
                    try: do_task.close()
                    except: pass
                return

        # Ctrl+C during logging
        stop = False
        def _sigint(_sig, _frame):
            nonlocal stop
            stop = True
            sys.stdout.write("\nStopping... (closing output)\n")
            sys.stdout.flush()
        signal.signal(signal.SIGINT, _sigint)

        # Create writer & tasks
        writer = CSVWriter(out) if fmt == "csv" else XLSXWriter(out, sheet_name="DAQ")
        samples_total = 0
        next_status_time = 0.0
        last_ts = time.time()
        last_samples = 0
        remaining_print = max(0, int(args.print_first))

        print("Creating AI task…")
        with nidaqmx.Task() as ai_task:
            for ch in ch_full:
                ai_task.ai_channels.add_ai_voltage_chan(ch, min_val=args.vmin, max_val=args.vmax, terminal_config=TERM_MAP[args.term])
            buf_samps = int(max(args.rate * 10, args.chunk * 2))
            ai_task.timing.cfg_samp_clk_timing(rate=args.rate, sample_mode=AcquisitionType.CONTINUOUS, samps_per_chan=buf_samps)
            print("Verifying AI task…")
            ai_task.control(TaskMode.TASK_VERIFY)

            di_task = None
            if di_lines:
                print("Creating DI task…")
                di_task = nidaqmx.Task()
                for ln in di_lines:
                    di_task.di_channels.add_di_chan(f"{args.device}/{ln}", line_grouping=LineGrouping.CHAN_PER_LINE)
                print("Verifying DI task…")
                di_task.control(TaskMode.TASK_VERIFY)

            ai_reader = AnalogMultiChannelReader(ai_task.in_stream)
            ai_buf = np.zeros((ch_count, args.chunk), dtype=np.float64)

            header = ["timestamp_iso", "sample_index"] + ch_short + di_headers
            writer.write_header(header)

            print("Starting tasks…")
            ai_task.start()
            if di_task: di_task.start()
            print("Running. Press Ctrl+C to stop.")

            # Preview header AFTER start messages
            if remaining_print > 0:
                print("(…start of preview…)")
                hdr = ["timestamp_iso", "idx"] + ch_short + di_headers
                print(" | ".join(hdr))
                sys.stdout.flush()

            t0 = time.time()
            last_ts = t0
            next_status_time = t0 + args.update_interval

            # Ignition timing flags (after logging started)
            fired = False
            fire_at = (t0 + args.stabilize_seconds) if do_task else None
            fire_until = None

            while not stop:
                now = time.time()
                if args.duration and (now - t0) >= args.duration:
                    break

                # Handle ignition timing
                if do_task and (not fired) and now >= fire_at:
                    try:
                        do_task.write([False, True], auto_start=True)  # igniter ON
                        print(f"\nIGNITION: Relay ON for {args.pulse_seconds:.3f}s")
                    except Exception as e:
                        print(f"\nIGNITION ERROR: {e}")
                    fire_until = now + args.pulse_seconds
                    fired = True

                if do_task and fired and fire_until and now >= fire_until:
                    try:
                        do_task.write([False, False], auto_start=True)
                        print("IGNITION: Relay OFF")
                    except: pass
                    fire_until = None

                # Read AI chunk
                ai_reader.read_many_sample(ai_buf, number_of_samples_per_channel=args.chunk, timeout=10.0)

                # DI snapshot once per chunk
                if di_task:
                    di_vals = di_task.read()
                    di_vals = [1 if bool(v) else 0 for v in di_vals]
                else:
                    di_vals = []

                chunk_start = time.time()
                for i in range(args.chunk):
                    ts = chunk_start + (i / args.rate)
                    ts_iso = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(ts)) + f".{int((ts%1)*1e6):06d}"
                    row_vals = ai_buf[:, i].tolist()
                    row = [ts_iso, samples_total + i] + row_vals + di_vals
                    writer.write_row(row)

                    if remaining_print > 0:
                        ai_str = [f"{v:.6f}" for v in row_vals]
                        di_str = [str(v) for v in di_vals]
                        print(" | ".join([ts_iso, str(samples_total + i)] + ai_str + di_str))
                        remaining_print -= 1
                        if remaining_print == 0:
                            print("(…end of preview…)")
                            sys.stdout.flush()

                samples_total += args.chunk

                # Periodic flush for CSV
                if isinstance(writer, CSVWriter) and (samples_total % max(int(args.rate*5), 1) < args.chunk):
                    writer.flush()

                if now >= next_status_time:
                    elapsed = now - t0
                    dt = now - last_ts if (now - last_ts) > 0 else 1e-9
                    inst_rate = (samples_total - last_samples) / dt
                    line = progress_line_bar(elapsed, args.duration) if (mode == "bar" and args.duration) else progress_line_counter(samples_total, ch_count, elapsed, inst_rate)
                    sys.stdout.write("\r" + line + " " * 10)
                    sys.stdout.flush()
                    last_ts = now
                    last_samples = samples_total
                    next_status_time = now + args.update_interval

            if mode != "none":
                sys.stdout.write("\n")
                sys.stdout.flush()

            print("Stopping tasks…")
            ai_task.stop()
            if di_task:
                di_task.stop()
                di_task.close()

        print("Closing output…")
        writer.close()
        print(f"Done. Wrote ~{samples_total} samples per AI channel to {out}")

    finally:
        # Always force DO lines LOW and close on exit
        if do_task:
            try:
                do_task.write([False, False], auto_start=True)
            except: pass
            try:
                do_task.close()
            except: pass

# ---------- CLI wrapper ----------
def run():
    """Entry-point wrapper so packaging can expose a `ni_usb6009_logger` command."""
    main()

if __name__ == "__main__":
    run()
