"""Calibration session: screen-only live readout with moving average.

Ported from the original run_calibration(); DAQ interaction is unchanged,
console output is reproduced by the CLI's Reporter instead of print().
"""
import time
from collections import deque

import numpy as np

from ni_usb6009_logger.core import daq
from ni_usb6009_logger.core.config import LoggerConfig, validate
from ni_usb6009_logger.core.events import CalibRow, Reporter, SessionState


class CalibrationSession:
    def __init__(self, cfg: LoggerConfig, reporter: Reporter):
        self.cfg = cfg
        self.rep = reporter

    def run(self, stop=None) -> None:
        import threading
        if stop is None:
            stop = threading.Event()
        cfg, rep = self.cfg, self.rep
        validate(cfg)
        if cfg.calibration is None:
            from ni_usb6009_logger.core.config import ConfigError
            raise ConfigError("CalibrationSession requires cfg.calibration.")
        cal = cfg.calibration
        nx = daq.backend()
        AcquisitionType = nx.constants.AcquisitionType
        TaskMode = nx.constants.TaskMode
        LineGrouping = nx.constants.LineGrouping
        AnalogMultiChannelReader = nx.stream_readers.AnalogMultiChannelReader
        TERM_MAP = daq.term_map()

        ch_full = cfg.channels_full
        ch_short = cfg.channels
        di_lines = cfg.digital_lines

        rep.on_state(SessionState.STARTING)
        rep.on_status("Starting logger… (calibration mode setup)")
        rep.on_status(f"AI channels: {', '.join(ch_full)} | term={cfg.term} | range=[{cfg.vmin},{cfg.vmax}] V")
        if di_lines:
            rep.on_status(f"DI lines: {', '.join(di_lines)}")

        rep.on_status("Calibration mode: screen-only live readout (no file).")
        rate_out = float(cal.rate_out)
        rate_hw = float(cal.sample_rate)
        window_seconds = cal.window_seconds
        window_samples = 1 if window_seconds <= 0 else max(1, int(round(window_seconds * rate_hw)))
        rep.on_status(
            f"Internal HW rate: {rate_hw:.3f} Hz | Output rate: {rate_out:.3f} Hz | "
            f"MA window: {window_samples} sample(s) (~{window_seconds:.2f}s)"
        )

        chunk = max(1, int(rate_hw * 0.2))
        try:
            with nx.Task() as ai_task:
                # Multi-channel add in ONE call to avoid MIG error
                phys = ",".join(ch_full)
                ai_task.ai_channels.add_ai_voltage_chan(
                    phys, min_val=cfg.vmin, max_val=cfg.vmax, terminal_config=TERM_MAP[cfg.term]
                )
                buf_samps = max(int(rate_hw * 3), chunk * 2)
                ai_task.timing.cfg_samp_clk_timing(
                    rate=rate_hw, sample_mode=AcquisitionType.CONTINUOUS, samps_per_chan=buf_samps)
                ai_task.control(TaskMode.TASK_VERIFY)

                di_task = None
                if di_lines:
                    di_task = nx.Task()
                    for ln in di_lines:
                        di_task.di_channels.add_di_chan(f"{cfg.device}/{ln}", line_grouping=LineGrouping.CHAN_PER_LINE)
                    di_task.control(TaskMode.TASK_VERIFY)

                ai_reader = AnalogMultiChannelReader(ai_task.in_stream)
                ch_count = len(ch_full)
                ai_buf = np.zeros((ch_count, chunk), dtype=np.float64)
                hist = [deque(maxlen=window_samples) for _ in range(ch_count)]

                hdr = ["time"] + [f"{name}_avg" for name in ch_short]
                if cal.show_raw: hdr += [f"{name}_raw" for name in ch_short]
                hdr += [("di_" + ln.replace("/", "_")).replace(":", "_") for ln in di_lines]
                rep.on_calib_header(hdr)

                ai_task.start()
                if di_task: di_task.start()
                rep.on_state(SessionState.CALIBRATING)

                next_print = time.time()
                while not stop.is_set():
                    ai_reader.read_many_sample(
                        ai_buf, number_of_samples_per_channel=chunk,
                        timeout=max(2.0, chunk / rate_hw * 2))
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
                        raw_vals = ai_buf[:, -1].tolist() if cal.show_raw else None
                        rep.on_calib_row(CalibRow(ts_iso, avgs, raw_vals, di_vals))
                        next_print = now + (1.0 / max(rate_out, 1e-6))
        finally:
            try: ai_task.stop()
            except Exception: pass
            if di_task:
                try: di_task.stop()
                except Exception: pass
                di_task.close()
        rep.on_state(SessionState.DONE)
