"""Pure helpers, moved verbatim from the original cli.py.

infer_output now takes the LoggerConfig (logs dir configurable for the GUI;
the CLI keeps the historic '.\\logs' default).
"""
import time
from pathlib import Path

from ni_usb6009_logger.core.config import LoggerConfig


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


def infer_output(cfg: LoggerConfig):
    if cfg.fmt:
        fmt = cfg.fmt
    elif cfg.outfile:
        ext = Path(cfg.outfile).suffix.lower()
        fmt = "xlsx" if ext == ".xlsx" else "csv"
    else:
        fmt = "csv"

    if cfg.outfile:
        out = Path(cfg.outfile)
        if fmt == "xlsx" and out.suffix.lower() != ".xlsx":
            out = out.with_suffix(".xlsx")
        if fmt == "csv" and out.suffix.lower() != ".csv":
            out = out.with_suffix(".csv")
    else:
        ts = time.strftime('%Y%m%d_%H%M%S')
        base = f"ni_{cfg.device}_{ts}"
        folder = Path(cfg.logs_dir)
        folder.mkdir(parents=True, exist_ok=True)
        out = folder / f"{base}.{fmt}"

    out = safe_path(out)
    return fmt, out


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


def compute_current_ma(v_shunt, r_ohms):
    return (v_shunt / max(r_ohms, 1e-9)) * 1000.0
