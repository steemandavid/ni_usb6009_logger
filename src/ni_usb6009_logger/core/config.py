"""Configuration dataclasses shared by the CLI and GUI front-ends.

The CLI maps its argparse Namespace onto LoggerConfig; the GUI builds it
directly (and persists it as JSON via QSettings). Validation lives in
validate() so both front-ends reject the same things with the same messages.
"""
from dataclasses import dataclass, field
from pathlib import Path


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
