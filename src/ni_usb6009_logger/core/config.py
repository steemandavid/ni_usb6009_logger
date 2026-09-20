"""Configuration dataclasses shared by the CLI and GUI front-ends.

The CLI maps its argparse Namespace onto LoggerConfig; the GUI builds it
directly (and persists it as JSON via QSettings). Validation lives in
validate() so both front-ends reject the same things with the same messages.
"""
import re
from dataclasses import dataclass, field
from pathlib import Path

# --- USB-6009 hardware limits -----------------------------------------------
# Static because this tool targets one device. Each value was read back from
# the driver (nidaqmx device properties / ai_term_cfgs) rather than copied from
# the datasheet, and each is enforced here only so the user gets a usable
# message instead of a -200077 traceback from deep inside a task; the driver
# remains the authority, and cli.main() still reports any DaqError it raises.
AI_MAX_AGGREGATE_RATE = 48_000.0    # ai_max_multi_chan_rate, shared by all AI
AI_DIFF_CHANNELS = ("ai0", "ai1", "ai2", "ai3")  # ai4-ai7 are RSE-only
AI_SUPPORTED_TERMS = ("RSE", "DIFF")  # NRSE is accepted by argparse but not
#                                       by this device: ai_term_cfgs lists
#                                       only RSE and DIFF on every channel.


class ConfigError(Exception):
    """Invalid configuration. ``exit_code`` mirrors the CLI's historic codes."""

    def __init__(self, message: str, exit_code: int = 1):
        super().__init__(message)
        self.exit_code = exit_code


@dataclass
class CalibrationConfig:
    rate_out: float = 1.0            # screen output rate (Hz)
    window_seconds: float = 5.0      # moving-average window (0 disables)
    show_raw: bool = False
    sample_rate: float = 100.0       # internal hardware rate (Hz)


@dataclass
class IgnitionConfig:
    buzzer_line: str = ""            # DO line, e.g. 'port1/line0'
    igniter_line: str = ""           # DO line, e.g. 'port1/line1'
    arm_seconds: float = 15.0
    stabilize_seconds: float = 1.0
    pulse_seconds: float = 1.0
    sense_ai: str | None = None      # AI channel measuring the shunt, e.g. 'ai2'
    shunt_ohms: float = 1.0
    continuity_min_ma: float = 0.2
    leak_max_ma: float = 5.0
    fire_confirm_ma: float = 300.0
    sense_rate: float = 100.0
    sense_term: str = "DIFF"


@dataclass
class LoggerConfig:
    device: str = "Dev1"
    channels: list[str] = field(default_factory=lambda: ["ai0"])  # e.g. ['ai0', 'ai1']
    digital_lines: list[str] = field(default_factory=list)         # expanded DI lines
    rate: float = 1000.0
    chunk: int = 1000
    vmin: float = -10.0
    vmax: float = 10.0
    term: str = "RSE"               # RSE | NRSE | DIFF
    logs_dir: Path = Path("logs")   # CLI default; GUI overrides
    outfile: Path | None = None     # None -> auto-named under logs_dir
    fmt: str | None = None          # 'csv' | 'xlsx' | None (infer)
    duration: float | None = None
    update_interval: float = 0.5
    print_first_rows: int = 0
    progress: str = "auto"          # CLI-only display concern
    debug: bool = False
    read_timeout: float = 10.0      # per-chunk AI read timeout (s)
    require_explicit_output: bool = False  # GUI: refuse to start without outfile
    recovery: bool = False          # GUI: dual-write a recovery CSV
    calibration: CalibrationConfig | None = None
    ignition: IgnitionConfig | None = None

    @property
    def channels_full(self) -> list[str]:
        return [f"{self.device}/{c}" for c in self.channels]

    def read_timeout_for(self, samples: int) -> float:
        """Read timeout for a block of ``samples``, never shorter than it takes.

        read_timeout is a floor, not a ceiling: a block of N samples at R Hz
        cannot arrive in less than N/R seconds, so a fixed 10 s timeout fails
        every read as soon as a chunk takes longer than that to acquire --
        e.g. the default chunk of 1000 at 50 Hz needs 20 s and always raised
        DaqError -200284. Scale with the acquisition time and keep headroom
        for USB latency.
        """
        if self.rate <= 0:
            return self.read_timeout
        return max(self.read_timeout, (samples / self.rate) * 1.5 + 1.0)


def _check_terminal_config(term: str, channels: list[str], what: str) -> None:
    """Reject terminal-config/channel combinations the USB-6009 refuses."""
    if term not in AI_SUPPORTED_TERMS:
        raise ConfigError(
            f"Error: terminal configuration {term} is not supported by the "
            f"USB-6009 ({what}). Use "
            f"{' or '.join(AI_SUPPORTED_TERMS)}.",
            exit_code=2,
        )
    if term != "DIFF":
        return
    bad = [c for c in channels
           if re.fullmatch(r"ai\d+", c) and c not in AI_DIFF_CHANNELS]
    if bad:
        raise ConfigError(
            f"Error: {', '.join(bad)} cannot be used with --term DIFF "
            f"({what}). Differential wiring pairs the inputs, so only "
            f"{', '.join(AI_DIFF_CHANNELS)} are available; "
            f"ai4-ai7 are single-ended (RSE) only.",
            exit_code=2,
        )


def validate(cfg: LoggerConfig) -> None:
    """Raise ConfigError for invalid combinations (order matches the old CLI)."""
    if not cfg.channels:
        raise ConfigError("At least one analog input channel is required.")
    if cfg.rate <= 0:
        raise ConfigError("Error: the sample rate must be greater than 0 Hz.", exit_code=2)
    if cfg.chunk <= 0:
        raise ConfigError("Error: the chunk size must be at least 1 sample.", exit_code=2)
    if cfg.vmin >= cfg.vmax:
        raise ConfigError(
            "Error: the AI range minimum must be below the maximum.", exit_code=2)
    aggregate = cfg.rate * len(cfg.channels)
    if aggregate > AI_MAX_AGGREGATE_RATE:
        raise ConfigError(
            f"Error: {cfg.rate:g} Hz on {len(cfg.channels)} AI channels needs "
            f"{aggregate:g} S/s, but the USB-6009 samples at most "
            f"{AI_MAX_AGGREGATE_RATE:g} S/s in total across all channels. "
            f"Lower --rate to {AI_MAX_AGGREGATE_RATE / len(cfg.channels):g} Hz "
            f"or log fewer channels.",
            exit_code=2,
        )
    _check_terminal_config(cfg.term, cfg.channels, "--term")
    if cfg.calibration and cfg.calibration.sample_rate <= 0:
        raise ConfigError(
            "Error: the calibration sample rate must be greater than 0 Hz.", exit_code=2)
    if cfg.calibration and cfg.ignition:
        raise ConfigError(
            "Error: --ignite cannot be used together with --calibrate.",
            exit_code=2,
        )
    if cfg.ignition and (not cfg.ignition.buzzer_line
                         or not cfg.ignition.igniter_line):
        raise ConfigError(
            "Error: --ignite requires both --buzzer-line and --igniter-line.",
            exit_code=2,
        )
    if cfg.ignition and cfg.ignition.sense_ai:
        # Only reached when the sense channel is read on its own task; harmless
        # to check either way, and it catches the DIFF default landing on a
        # single-ended-only channel.
        _check_terminal_config(cfg.ignition.sense_term,
                               [cfg.ignition.sense_ai], "--sense-term")
