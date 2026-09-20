"""In-memory fake of the nidaqmx API surface used by ni_usb6009_logger.

Installed into ``sys.modules`` by tests/conftest.py (and by ``NI_USB6009_FAKE=1``
for GUI development) so the CLI, core and GUI can be
exercised on machines without the NI-DAQmx driver (development happens on
Linux; the DAQ hardware is Windows-only).

Knobs on ``STATE`` let tests simulate devices, sense voltages (continuity /
leak / fire-confirm), DI levels, and mid-run unplug (remove the device name
from ``STATE.devices`` so task verification raises, like the real driver).
"""
import math
import sys
import time
import types


class DaqError(Exception):
    """Mirrors nidaqmx.errors.DaqError."""


class DriverNotInstalledError(DaqError):
    """Mirrors nidaqmx.errors.DriverNotInstalledError."""


class State:
    """Test-controllable state, reset via reset()."""

    def __init__(self):
        self.devices = ["Dev1"]          # names of "connected" DAQs
        self.ai_voltage_overrides = {}   # "Dev1/ai2" -> volts (constant)
        self.di_values = []              # bools returned by DI reads (cycled)
        self.do_writes = []              # [(lines_tuple, bool_tuple)] per write
        self.do_write_times = []         # time.time() of each DO write
        self.read_time_scale = 1.0       # 0 = no simulated read blocking
        # The USB-6009 has ONE analog-input timing engine: a second AI task on
        # the same device is refused by the real driver (-50103). Modelling it
        # keeps that constraint visible in CI instead of only on hardware.
        self.single_ai_engine = True
        self.ai_reservations = set()     # device names with a running AI task


STATE = State()


def reset(devices=None):
    STATE.devices = list(devices) if devices is not None else ["Dev1"]
    STATE.ai_voltage_overrides = {}
    STATE.di_values = []
    STATE.do_writes = []
    STATE.do_write_times = []
    STATE.read_time_scale = 1.0
    STATE.single_ai_engine = True
    STATE.ai_reservations = set()


def waveform(channel_index, sample_index, rate):
    """Deterministic synthetic AI signal: per-channel amplitude, 1 Hz sine.

    Same inputs always give the same value, so golden comparisons of logged
    data columns are exact.
    """
    amp = 1.0 + channel_index
    return amp * math.sin(2.0 * math.pi * 1.0 * sample_index / rate)


def do_write_sequences():
    """DO writes only, as tuples of bools, in order."""
    return [list(vals) for _lines, vals in STATE.do_writes]


def do_write_times():
    """Wall-clock time of each DO write, index-aligned with the sequences."""
    return list(STATE.do_write_times)


# --- constants module -------------------------------------------------------
constants = types.ModuleType("nidaqmx.constants")


class _AcquisitionType:
    CONTINUOUS = "continuous"
    FINITE = "finite"
    ON_DEMAND = "on_demand"


class _TerminalConfiguration:
    RSE = "RSE"
    NRSE = "NRSE"
    DIFF = "DIFF"


class _LineGrouping:
    CHAN_PER_LINE = "chan_per_line"
    ONE_LINE_FOR_ALL = "one_line_for_all"


class _TaskMode:
    TASK_VERIFY = "task_verify"
constants.AcquisitionType = _AcquisitionType
constants.TerminalConfiguration = _TerminalConfiguration
constants.LineGrouping = _LineGrouping
constants.TaskMode = _TaskMode


# --- errors module ----------------------------------------------------------
errors = types.ModuleType("nidaqmx.errors")
errors.DaqError = DaqError
errors.DriverNotInstalledError = DriverNotInstalledError


# --- Task -------------------------------------------------------------------
class _AIChannels:
    def __init__(self, task):
        self._task = task

    def add_ai_voltage_chan(self, physical_channel, min_val=-10.0, max_val=10.0,
                            terminal_config=None):
        for phys in physical_channel.split(","):
            self._task._ai.append(phys.strip())


class _DIChannels:
    def __init__(self, task):
        self._task = task

    def add_di_chan(self, physical_channel, line_grouping=None):
        self._task._di.append(physical_channel)


class _DOChannels:
    def __init__(self, task):
        self._task = task

    def add_do_chan(self, physical_channel, line_grouping=None):
        self._task._do.append(physical_channel)


class _Timing:
    def __init__(self, task):
        self._task = task

    def cfg_samp_clk_timing(self, rate=None, sample_mode=None, samps_per_chan=None):
        self._task._rate = float(rate)


class Task:
    def __init__(self, new_task_name=""):
        self._ai, self._di, self._do = [], [], []
        self._rate = None
        self._sample_k = 0
        self.ai_channels = _AIChannels(self)
        self.di_channels = _DIChannels(self)
        self.do_channels = _DOChannels(self)
        self.timing = _Timing(self)
        self.in_stream = types.SimpleNamespace(task=self)
        self._closed = False
        self._started = False

    # context manager, like the real Task
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False

    def _check_devices(self):
        for phys in self._ai + self._di + self._do:
            dev = phys.split("/", 1)[0]
            if dev not in STATE.devices:
                raise DaqError(
                    f"Device requested by the task is not present in NI-DAQmx. ({dev})"
                )

    def _ai_device(self):
        return self._ai[0].split("/", 1)[0] if self._ai else None

    def _check_ai_engine(self):
        """Refuse a second AI task on a device that already has one running."""
        dev = self._ai_device()
        if STATE.single_ai_engine and dev is not None and dev in STATE.ai_reservations:
            raise DaqError(
                "Specified resource is reserved. The operation could not be "
                f"completed as specified. ({dev} analog input)")

    def control(self, mode):
        self._check_devices()

    def start(self):
        self._check_devices()
        if self._ai and not self._started:
            self._check_ai_engine()
            dev = self._ai_device()
            if dev is not None:
                STATE.ai_reservations.add(dev)
        self._started = True

    def stop(self):
        self._release_ai()
        self._started = False

    def _release_ai(self):
        dev = self._ai_device()
        if self._started and dev is not None:
            STATE.ai_reservations.discard(dev)

    def close(self):
        self.stop()
        self._closed = True

    def write(self, data, auto_start=False):
        if self._do:
            vals = tuple(bool(v) for v in data)
            STATE.do_writes.append((tuple(self._do), vals))
            STATE.do_write_times.append(time.time())
            return len(vals)
        raise DaqError("write() on a task without DO channels")

    def read(self, number_of_samples_per_channel=1, timeout=10.0):
        if self._ai and not self._started:
            self._check_ai_engine()  # on-demand read auto-starts the task
        if self._di:
            n = len(self._di)
            src = STATE.di_values or [False]
            return [bool(src[i % len(src)]) for i in range(n)]
        if self._ai:
            if number_of_samples_per_channel == 1:
                return self._read_ai_sample(0)
            return [[self._read_ai_sample(j)]
                    for j in range(number_of_samples_per_channel)]
        raise DaqError("read() on a task without channels")

    def _read_ai_sample(self, offset):
        phys = self._ai[0]
        if phys in STATE.ai_voltage_overrides:
            return float(STATE.ai_voltage_overrides[phys])
        rate = self._rate or 1000.0
        k = self._sample_k + offset
        self._sample_k += 1
        return waveform(0, k, rate)


# --- stream readers ---------------------------------------------------------
stream_readers = types.ModuleType("nidaqmx.stream_readers")


class AnalogMultiChannelReader:
    def __init__(self, in_stream):
        self._task = in_stream.task

    def read_many_sample(self, data, number_of_samples_per_channel=1,
                         timeout=10.0):
        task = self._task
        if not task._ai:
            raise DaqError("no AI channels on task")
        task._check_devices()  # simulate mid-run unplug
        if not task._started:
            task._check_ai_engine()
        rate = task._rate or 1000.0
        # Simulate hardware cadence so duration-based loops behave like reality.
        if STATE.read_time_scale > 0:
            time.sleep(number_of_samples_per_channel / rate * STATE.read_time_scale)
        for i, phys in enumerate(task._ai):
            override = STATE.ai_voltage_overrides.get(phys)
            for j in range(number_of_samples_per_channel):
                if override is not None:
                    data[i, j] = override
                else:
                    data[i, j] = waveform(i, task._sample_k + j, rate)
        task._sample_k += number_of_samples_per_channel
        return number_of_samples_per_channel


stream_readers.AnalogMultiChannelReader = AnalogMultiChannelReader


# --- System (device enumeration) --------------------------------------------
class _SystemLocal:
    @property
    def devices(self):
        return [types.SimpleNamespace(name=d, product_type="USB-6009")
                for d in STATE.devices]


class System:
    @staticmethod
    def local():
        return _SystemLocal()


# Mirror the real layout: System lives in the nidaqmx.system SUBMODULE, and
# nidaqmx has no top-level System attribute. Exposing it the wrong way here is
# what let core.daq call a non-existent nidaqmx.System and still pass CI.
# The attributes set on the fake module below mirror real nidaqmx AS
# daq.backend() leaves it -- i.e. after backend() has imported every submodule
# explicitly. Do not add an attribute here that backend() does not import.
system = types.ModuleType("nidaqmx.system")
system.System = System


# --- top-level fake module --------------------------------------------------
_nidaqmx = types.ModuleType("nidaqmx")
_nidaqmx.__fake__ = True
_nidaqmx.Task = Task
_nidaqmx.constants = constants
_nidaqmx.errors = errors
_nidaqmx.stream_readers = stream_readers
_nidaqmx.system = system

_SUBMODULES = ("nidaqmx.constants", "nidaqmx.errors",
               "nidaqmx.stream_readers", "nidaqmx.system")


def install():
    for name in ("nidaqmx",) + _SUBMODULES:
        sys.modules[name] = {"nidaqmx": _nidaqmx,
                             "nidaqmx.constants": constants,
                             "nidaqmx.errors": errors,
                             "nidaqmx.stream_readers": stream_readers,
                             "nidaqmx.system": system}[name]


def uninstall():
    for name in ("nidaqmx",) + _SUBMODULES:
        sys.modules.pop(name, None)
