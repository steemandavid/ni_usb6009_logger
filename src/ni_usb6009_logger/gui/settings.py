"""Persist the GUI configuration (LoggerConfig) as one JSON blob in QSettings."""
import json
from dataclasses import asdict, fields, is_dataclass
from pathlib import Path

from PySide6.QtCore import QSettings

from ni_usb6009_logger.core.config import (
    CalibrationConfig,
    IgnitionConfig,
    LoggerConfig,
)

_ORG = "steeman.be"
_APP = "NI USB-6009 Logger"
_KEY = "config_v1"


def _default_logs_dir() -> Path:
    docs = Path.home() / "Documents"
    return docs / "NI6009 Logs"


def default_config() -> LoggerConfig:
    return LoggerConfig(logs_dir=_default_logs_dir())


def _to_json(cfg: LoggerConfig) -> dict:
    d = asdict(cfg)
    d["logs_dir"] = str(cfg.logs_dir)
    d["outfile"] = str(cfg.outfile) if cfg.outfile else None
    return d


def _from_dict(d: dict) -> LoggerConfig:
    known = {f.name for f in fields(LoggerConfig)}
    kwargs = {k: v for k, v in d.items() if k in known}
    if isinstance(kwargs.get("logs_dir"), str):
        kwargs["logs_dir"] = Path(kwargs["logs_dir"])
    if isinstance(kwargs.get("outfile"), str):
        kwargs["outfile"] = Path(kwargs["outfile"])
    elif kwargs.get("outfile") is None:
        kwargs["outfile"] = None
    if isinstance(kwargs.get("calibration"), dict):
        kwargs["calibration"] = CalibrationConfig(**kwargs["calibration"])
    if isinstance(kwargs.get("ignition"), dict):
        kwargs["ignition"] = IgnitionConfig(**kwargs["ignition"])
    cfg = LoggerConfig(**kwargs)
    if not is_dataclass(cfg):  # pragma: no cover
        raise TypeError("LoggerConfig construction failed")
    return cfg


def save_config(cfg: LoggerConfig) -> None:
    QSettings(_ORG, _APP).setValue(_KEY, json.dumps(_to_json(cfg)))


def load_config() -> LoggerConfig:
    raw = QSettings(_ORG, _APP).value(_KEY, "")
    if not raw:
        return default_config()
    try:
        return _from_dict(json.loads(raw))
    except Exception:
        return default_config()
