"""Logging session (with optional ignition sequence), ported from the old main().

Behavior preservation:
- The DO task is created FIRST when ignition is configured and both lines are
  forced LOW immediately; every exit path re-forces LOW and closes the task.
- Hardware failsafes (leak inhibit, continuity check, fire-confirm current)
  stay here in the core, independent of any front-end.
- CLI parity: fire_permission=None fires automatically at stabilize time
  (historic behavior). The GUI passes an Event and the session waits in
  FIRE_PENDING (polling stop at 10 Hz) until the user holds FIRE.
"""
import threading
import time

import numpy as np

from ni_usb6009_logger.core import daq
from ni_usb6009_logger.core.config import ConfigError, LoggerConfig, validate
from ni_usb6009_logger.core.events import (
    Reporter,
    SampleBlock,
    SessionResult,
    SessionState,
)
from ni_usb6009_logger.core.helpers import compute_current_ma, infer_output, safe_path
from ni_usb6009_logger.core.writers import CSVWriter, TeeWriter, make_writer


class IgnitionSetupError(Exception):
    """The ignition DO task could not be prepared (historic CLI exit code 3)."""


_ARM_OK, _ARM_ABORTED, _ARM_LEAK, _ARM_NO_CONTINUITY = range(4)


class LoggingSession:
    def __init__(self, cfg: LoggerConfig, reporter: Reporter):
        self.cfg = cfg
        self.rep = reporter

    # ------------------------------------------------------------------ run
    def run(self, stop=None, fire_permission=None) -> SessionResult:
        if stop is None:
            stop = threading.Event()
        cfg, rep = self.cfg, self.rep
        validate(cfg)

        if cfg.calibration is not None:
            raise ConfigError("Use CalibrationSession for calibration mode.")

        if cfg.require_explicit_output and cfg.outfile is None:
            raise ConfigError("An output file must be selected before starting a test.")

        nx = daq.backend()
        AcquisitionType = nx.constants.AcquisitionType
        TaskMode = nx.constants.TaskMode
        LineGrouping = nx.constants.LineGrouping
        AnalogMultiChannelReader = nx.stream_readers.AnalogMultiChannelReader
        TERM_MAP = daq.term_map()

        ign = cfg.ignition
        ch_full = cfg.channels_full
        ch_short = cfg.channels
        ch_count = len(ch_full)
        di_lines = cfg.digital_lines
        di_headers = [("di_" + ln.replace("/", "_")).replace(":", "_") for ln in di_lines]

        # Create DO task immediately (safe state FIRST) when ignition is requested
        do_task = None
        if ign:
            try:
                do_task = nx.Task()
                do_task.do_channels.add_do_chan(f"{cfg.device}/{ign.buzzer_line}", line_grouping=LineGrouping.CHAN_PER_LINE)
                do_task.do_channels.add_do_chan(f"{cfg.device}/{ign.igniter_line}", line_grouping=LineGrouping.CHAN_PER_LINE)
                # SAFETY: force both LOW immediately at start
                do_task.write([False, False], auto_start=True)
                do_task.control(TaskMode.TASK_VERIFY)
                rep.on_status(f"Safety: DO lines set LOW at start (buzzer={ign.buzzer_line} LOW, igniter={ign.igniter_line} LOW).")
            except Exception as e:
                rep.on_status(f"Error preparing ignition DO task: {e}")
                if do_task:
                    try: do_task.close()
                    except Exception: pass
                raise IgnitionSetupError(str(e)) from e

        try:
            rep.on_state(SessionState.STARTING)
            fmt, out = infer_output(cfg)
            out.parent.mkdir(parents=True, exist_ok=True)

            rep.on_status("Starting logger… (initializing tasks)")
            rep.on_status(f"Output → {out}   Format={fmt.upper()}")
            rep.on_status(f"AI channels: {', '.join(ch_full)} | term={cfg.term} | range=[{cfg.vmin},{cfg.vmax}] V | rate={cfg.rate} Hz | chunk={cfg.chunk}")
            if di_lines:
                rep.on_status(f"DI lines: {', '.join(di_lines)} (snapshotted per chunk)")
            if cfg.duration:
                rep.on_status(f"Duration: ~{cfg.duration} s (Ctrl+C to stop early)")
            if cfg.print_first_rows > 0:
                rep.on_status(f"Will print the first {cfg.print_first_rows} rows below as they are logged.")

            # ---- Arming phase if ignition enabled (with current-sense) ----
            if do_task:
                arm = self._arm(nx, do_task, stop, TERM_MAP, AcquisitionType,
                                TaskMode, AnalogMultiChannelReader)
                if arm == _ARM_ABORTED:
                    rep.on_state(SessionState.ABORTED)
                    return SessionResult(state=SessionState.ABORTED)
                if arm in (_ARM_LEAK, _ARM_NO_CONTINUITY):
                    rep.on_state(SessionState.INHIBITED)
                    return SessionResult(state=SessionState.INHIBITED)

            # ---- Writer (optionally tee'd into a recovery CSV) ----
            recovery_path = None
            writer = make_writer(out, fmt, sheet_name="DAQ")
            if cfg.recovery:
                rec_dir = out.parent / "recovery"
                rec_dir.mkdir(parents=True, exist_ok=True)
                recovery_path = safe_path(rec_dir / f"{out.stem}_recovery.csv")
                writer = TeeWriter(writer, CSVWriter(recovery_path))

            samples_total = 0
            next_status_time = 0.0
            last_ts = time.time()
            last_samples = 0
            remaining_print = max(0, int(cfg.print_first_rows))

            try:
                rep.on_status("Creating AI task…")
                with nx.Task() as ai_task:
                    # Multi-channel add in ONE call to avoid MIG error
                    phys = ",".join(ch_full)
                    ai_task.ai_channels.add_ai_voltage_chan(
                        phys, min_val=cfg.vmin, max_val=cfg.vmax, terminal_config=TERM_MAP[cfg.term]
                    )
                    buf_samps = int(max(cfg.rate * 10, cfg.chunk * 2))
                    ai_task.timing.cfg_samp_clk_timing(rate=cfg.rate, sample_mode=AcquisitionType.CONTINUOUS, samps_per_chan=buf_samps)
                    rep.on_status("Verifying AI task…")
                    ai_task.control(TaskMode.TASK_VERIFY)

                    di_task = None
                    if di_lines:
                        rep.on_status("Creating DI task…")
                        di_task = nx.Task()
                        for ln in di_lines:
                            di_task.di_channels.add_di_chan(f"{cfg.device}/{ln}", line_grouping=LineGrouping.CHAN_PER_LINE)
                        rep.on_status("Verifying DI task…")
                        di_task.control(TaskMode.TASK_VERIFY)

                    ai_reader = AnalogMultiChannelReader(ai_task.in_stream)
                    ai_buf = np.zeros((ch_count, cfg.chunk), dtype=np.float64)

                    header = ["timestamp_iso", "sample_index"] + ch_short + di_headers
                    writer.write_header(header)

                    rep.on_status("Starting tasks…")
                    ai_task.start()
                    if di_task: di_task.start()
                    rep.on_status("Running. Press Ctrl+C to stop.")
                    rep.on_state(SessionState.LOGGING)

                    # Preview header AFTER start messages
                    if remaining_print > 0:
                        rep.on_status("(…start of preview…)")
                        hdr = ["timestamp_iso", "idx"] + ch_short + di_headers
                        rep.on_status(" | ".join(hdr))

                    t0 = time.time()
                    last_ts = t0
                    next_status_time = t0 + cfg.update_interval

                    # Ignition timing (after logging starts)
                    fired = False
                    fire_pending_announced = False
                    fire_at = (t0 + ign.stabilize_seconds) if do_task else None
                    fire_until = None

                    while not stop.is_set():
                        now = time.time()
                        if cfg.duration and (now - t0) >= cfg.duration:
                            break

                        # Handle ignition timing
                        if do_task and (not fired) and now >= fire_at:
                            if (fire_permission is not None
                                    and not fire_permission.is_set()):
                                if not fire_pending_announced:
                                    rep.on_state(SessionState.FIRE_PENDING)
                                    fire_pending_announced = True
                            else:
                                try:
                                    do_task.write([False, True], auto_start=True)  # igniter ON
                                    rep.on_status(f"\nIGNITION: Relay ON for {ign.pulse_seconds:.3f}s")
                                    rep.on_state(SessionState.FIRED)
                                    sense_chan_full = (f"{cfg.device}/{ign.sense_ai.strip()}"
                                                       if ign.sense_ai else None)
                                    if sense_chan_full:
                                        with nx.Task() as confirm_task:
                                            confirm_task.ai_channels.add_ai_voltage_chan(
                                                sense_chan_full, min_val=-1.0, max_val=1.0,
                                                terminal_config=TERM_MAP[ign.sense_term]
                                            )
                                            time.sleep(0.02)
                                            v_now = confirm_task.read(number_of_samples_per_channel=1, timeout=0.2)
                                            v_now = float(v_now)
                                            i_now_ma = compute_current_ma(v_now, ign.shunt_ohms)
                                            rep.on_status(f"IGNITION confirm sample: {i_now_ma:.1f} mA")
                                            if i_now_ma < ign.fire_confirm_ma:
                                                rep.on_status("WARNING: Ignition current below confirm threshold – check wiring/supply/igniter.")
                                except Exception as e:
                                    rep.on_status(f"\nIGNITION ERROR: {e}")
                                fire_until = now + ign.pulse_seconds
                                fired = True

                        if do_task and fired and fire_until and now >= fire_until:
                            try:
                                do_task.write([False, False], auto_start=True)
                                rep.on_status("IGNITION: Relay OFF")
                            except Exception: pass
                            fire_until = None

                        # Read AI chunk
                        ai_reader.read_many_sample(ai_buf, number_of_samples_per_channel=cfg.chunk, timeout=cfg.read_timeout)

                        # DI snapshot once per chunk
                        if di_task:
                            di_vals = di_task.read()
                            di_vals = [1 if bool(v) else 0 for v in di_vals]
                        else:
                            di_vals = []

                        chunk_start = time.time()
                        rep.on_sample_block(SampleBlock(chunk_start, 1.0 / cfg.rate, ai_buf.copy(), list(di_vals)))

                        for i in range(cfg.chunk):
                            ts = chunk_start + (i / cfg.rate)
                            ts_iso = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(ts)) + f".{int((ts%1)*1e6):06d}"
                            row_vals = ai_buf[:, i].tolist()
                            row = [ts_iso, samples_total + i] + row_vals + di_vals
                            writer.write_row(row)

                            if remaining_print > 0:
                                rep.on_row_preview(row)
                                remaining_print -= 1

                        samples_total += cfg.chunk

                        # Periodic flush for CSV (main + recovery every chunk)
                        if isinstance(writer, TeeWriter):
                            writer.recovery.flush()
                            if isinstance(writer.main, CSVWriter) and (samples_total % max(int(cfg.rate*5), 1) < cfg.chunk):
                                writer.main.flush()
                        elif isinstance(writer, CSVWriter) and (samples_total % max(int(cfg.rate*5), 1) < cfg.chunk):
                            writer.flush()

                        if now >= next_status_time:
                            elapsed = now - t0
                            dt = now - last_ts if (now - last_ts) > 0 else 1e-9
                            inst_rate = (samples_total - last_samples) / dt
                            rep.on_progress(samples_total, ch_count, elapsed, inst_rate)
                            last_ts = now
                            last_samples = samples_total
                            next_status_time = now + cfg.update_interval

                    state = SessionState.ABORTED if stop.is_set() else SessionState.DONE
                    rep.on_state(state)

                    rep.on_status("Stopping tasks…")
                    ai_task.stop()
                    if di_task:
                        di_task.stop()
                        di_task.close()

                rep.on_status("Closing output…")
                writer.close()
                if recovery_path is not None:
                    ok_path = recovery_path.with_name(recovery_path.stem + "_OK.csv")
                    try:
                        recovery_path.rename(ok_path)
                        recovery_path = ok_path
                    except OSError:
                        pass
                rep.on_status(f"Done. Wrote ~{samples_total} samples per AI channel to {out}")
                return SessionResult(samples_total, out, recovery_path, state)
            finally:
                writer.close()  # idempotent; flushes even on error paths

        finally:
            # Always force DO lines LOW and close on exit
            if do_task:
                try:
                    do_task.write([False, False], auto_start=True)
                except Exception: pass
                try:
                    do_task.close()
                except Exception: pass

    # --------------------------------------------------------------- arming
    def _arm(self, nx, do_task, stop, TERM_MAP, AcquisitionType, TaskMode,
             AnalogMultiChannelReader) -> int:
        cfg, rep, ign = self.cfg, self.rep, self.cfg.ignition

        rep.on_status(f"ARMING: Sounding buzzer for {ign.arm_seconds:.1f} s. Press Ctrl+C to abort.")
        rep.on_state(SessionState.ARMING)

        sense_task = None
        reader = None
        buf = np.zeros((1, 1), dtype=np.float64)
        try:
            sense_chan_full = f"{cfg.device}/{ign.sense_ai.strip()}" if ign.sense_ai else None
            if sense_chan_full:
                sense_task = nx.Task()
                sense_task.ai_channels.add_ai_voltage_chan(
                    sense_chan_full,
                    min_val=-1.0, max_val=1.0,
                    terminal_config=TERM_MAP[ign.sense_term]
                )
                sense_task.timing.cfg_samp_clk_timing(
                    rate=ign.sense_rate, sample_mode=AcquisitionType.CONTINUOUS, samps_per_chan=10
                )
                sense_task.control(TaskMode.TASK_VERIFY)
                reader = AnalogMultiChannelReader(sense_task.in_stream)
                sense_task.start()

            do_task.write([True, False], auto_start=True)  # buzzer ON
            t_end = time.time() + ign.arm_seconds
            rep.on_status(f"Continuity min = {ign.continuity_min_ma:.2f} mA | Leak max = {ign.leak_max_ma:.2f} mA")
            continuity_ok = False

            while time.time() < t_end and not stop.is_set():
                i_ma = None
                if reader:
                    reader.read_many_sample(buf, number_of_samples_per_channel=1, timeout=0.1)
                    v = float(buf[0, 0])
                    i_ma = compute_current_ma(v, ign.shunt_ohms)
                    rep.on_arming(max(0.0, t_end - time.time()), i_ma)
                    if i_ma >= ign.leak_max_ma:
                        rep.on_status("\nSafety INHIBIT: leak current detected above limit before firing.")
                        do_task.write([False, False], auto_start=True)
                        rep.on_status("Buzzer OFF. Ignition inhibited.")
                        return _ARM_LEAK
                    if i_ma >= ign.continuity_min_ma:
                        continuity_ok = True
                else:
                    rep.on_arming(max(0.0, t_end - time.time()), None)
                time.sleep(1.0 / max(ign.sense_rate, 10.0))

            if stop.is_set():
                rep.on_status("\nArming aborted by user. Exiting.")
                return _ARM_ABORTED

            if reader and not continuity_ok:
                rep.on_status("\nSafety INHIBIT: igniter continuity not detected (below threshold).")
                return _ARM_NO_CONTINUITY

        except RuntimeError:
            do_task.write([False, False], auto_start=True)
            rep.on_status("Buzzer OFF. Ignition inhibited.")
            return _ARM_LEAK
        finally:
            try: do_task.write([False, False], auto_start=True)
            except Exception: pass
            rep.on_status("\rArming… done.                      \n")
            if sense_task:
                try: sense_task.stop()
                except Exception: pass
                sense_task.close()
        return _ARM_OK
