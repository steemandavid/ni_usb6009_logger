# Changelog

## 2026-09-20 — GUI application + shared core (v1.1.x development)

### Added
- **Shared Qt-free core** (`src/ni_usb6009_logger/core/`): config dataclasses with
  validation, `Reporter` callback interface, writers (incl. `TeeWriter` for recovery
  dual-write), helpers, `daq.py` (the only nidaqmx import; `driver_available()`,
  `enumerate_devices()`, `NI_USB6009_FAKE=1` fake backend), `CalibrationSession`,
  and `LoggingSession` with the ignition safety sequence (DO forced LOW first/last,
  leak/continuity/fire-confirm failsafes, GUI `fire_permission` gate).
- **Windows GUI** (`src/ni_usb6009_logger/gui/`, `pip install .[gui]`, `ni_usb6009_gui`):
  - automatic DAQ detection with continuous monitoring; hot-plug/unplug handled
    gracefully (friendly dialog, partial data preserved)
  - output file must be chosen **before** a test starts; a recovery CSV is written
    in parallel with every run and browsable/restorable in the Recovery tab
  - live plot of all AI channels (PyQtGraph ring buffers, follow/pause view) and
    large calibration readouts
  - ignition tab: ARM confirmation, arming with live current + continuity/leak LEDs,
    hold-to-fire (2 s), ABORT at any time
  - `--selftest` mode for installers: checks driver + device, returns status codes
- **Packaging** (`packaging/`): PyInstaller onedir spec; Inno Setup script with an
  optional silent NI-DAQmx driver component and post-install self-test; build
  instructions and clean-VM verification checklist.
- **CI** (`.github/workflows/`): ubuntu tests (3.10/3.12 + offscreen GUI) and a
  tag-triggered Windows release workflow that builds the setup exe.
- **Tests** (30): CLI golden `--help`/flag parity, fake-DAQ end-to-end runs, ignition
  DO-write sequencing and inhibits, fire-permission gate, recovery dual-write,
  offscreen GUI state-machine tests. Fake nidaqmx moved into the package.

### Changed
- `cli.py` rewritten as a thin adapter over the core; **all flags, defaults, console
  output, and exit codes unchanged** (verified by golden tests captured pre-refactor).
- Writers close idempotently and the session closes them on error paths (crash-safe).
- `pyproject.toml`: `[gui]` extra and `ni_usb6009_gui` entry point; `__version__`
  in `__init__.py` as the single source for installer versioning.

### Removed
- Stale snapshots inside the package (`cli - Copy 20250902.py`,
  `ni_csv_logger.py-old`) and the committed Windows `.venv`; `.gitignore` added.

### Pending (needs Windows hardware)
- Phase 6 verification per `packaging/README.md` (installer, silent NI-DAQmx flags,
  real-DAQ and relay dry runs), then tag `v1.2.0` for the CI-built installer.
