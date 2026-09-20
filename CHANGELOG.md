# Changelog

## 2026-09-20 — Code-review fixes (Phases 0–7 review remediation)

All findings from `Code_Review_Full_20260920_1354.md` (4 critical, 11 major,
25 minor) are addressed. Test suite grew 30 → 45; `flake8` clean across the tree.

### Fixed — safety & ignition (core)
- **Relay ON time is now the configured pulse.** While ignition is enabled the AI
  stream is read in ~20 ms sub-blocks instead of one chunk per iteration, so the
  relay opens at `pulse_seconds` and **ABORT** reaches the hardware within a
  sub-block. Previously the ON time was quantized to the chunk read — up to 5× the
  configured pulse at GUI defaults (1000 Hz / 1000 samples).
- **Fire-confirm works on real hardware.** The USB-6009 has one AI timing engine, so
  the old second AI task would be refused (−50103). When the sense channel is in the
  AI channel list the confirm value now comes from the running task's samples (peak
  over the chunk covering the pulse); the fallback separate task derives its range
  from `fire_confirm_ma × shunt_ohms` instead of a hardcoded ±1 V (which clipped at
  ~1 A on a 1 Ω shunt) and reports a clear message if the driver refuses it.
- **Window close during a session no longer abandons the worker.** The window stays
  open behind a modal "stopping safely" indicator until the session thread has really
  finished and the core's exit path has forced the DO lines LOW (the old 5 s budget
  was shorter than the 10 s `read_timeout`).
- Reversed sense wiring (large negative current) inhibits arming explicitly instead of
  passing the leak test by luck.
- A `RuntimeError` during arming is reported as what it was (read timeout, buffer
  error) and inhibits via a distinct `_ARM_ERROR`, no longer mislabelled "leak".
- FIRE can no longer be granted from the keyboard (space bar): `fire_btn` is
  `Qt.NoFocus`.
- Row timestamps are dated back by the chunk's acquisition duration (they previously
  led the true acquisition time by ~1 chunk, 1 s at GUI defaults).

### Fixed — resource & error handling
- AI **and** DI tasks are owned by an `ExitStack` in `LoggingSession` and
  `CalibrationSession`: stopped and closed on every exit path, so an unplug no longer
  leaks a task that keeps the lines reserved for the next run.
- `CalibrationSession` setup failures surface the real DAQ error instead of
  `UnboundLocalError` masking it.
- `TeeWriter.close()` closes the recovery sink in a `finally` — the crash copy is
  flushed even when the XLSX save fails (full disk, file open in Excel).
- `XLSXWriter.close()` marks the attempt before saving, so the double close from
  `session.py` cannot raise a second time and mask the first exception.
- `config.validate()` rejects `rate <= 0`, `chunk <= 0`, `vmin >= vmax` and a
  non-positive calibration rate (exit code 2) instead of dying with
  `ZeroDivisionError` deep in the loop.
- A second `Ctrl+C` breaks out of a wedged read (exit code 130); the GUI's
  `_excepthook` now actually closes the app it says it will close.

### Fixed — GUI behavior (FSD conformance)
- Recovery tab lists the files that were really written (`<output file>/recovery/`
  plus the default logs folder); **Copy to…** uses the real path.
- Ignition LEDs use the configured continuity/leak thresholds instead of hardcoded
  0.2 / 5.0 mA.
- Settings round-trip is complete: starting any run persists *all* panel fields, so
  ignition thresholds are no longer discarded by a plain log run, and sense terminal
  config / continuity / leak / fire-confirm are restored on launch.
- A typed device name enables Start/ARM when enumeration sees nothing (the escape
  hatch FSD §5 promises); only genuine user edits count.
- Live plot Y axis is fixed to the configured AI range; ring capacity capped at
  500 000 points per channel (~368 MB → ~64 MB worst case); legend cleared via the
  public API rather than PyQtGraph internals.
- The inhibit message survives the panel reset; Browse shows the suffixed
  no-overwrite path it will actually write; device polling detects a device-count
  change and enumerates once per tick.

### Fixed — packaging & CI
- `installer.iss`: parenthesized `if (CurStep = ssPostInstall) and …` (Pascal
  precedence error that stopped ISCC compiling the script at all); driver presence is
  decided at **compile** time via `#if FileExists(...)` instead of a runtime check of
  a build-machine path (which meant the driver component could never install);
  self-test checkbox default-on on every install.
- `release.yml`: `/DSourceDir=..\dist\NI6009Logger` (Inno resolves relative paths
  against the `.iss` directory), `/DNiDaqSetup` passed only when the redistributable
  was downloaded, and a `needs: test` job so a tag cannot publish an untested
  installer. Same path corrected in `packaging/README.md`.
- `ci.yml` lints all of `src` and runs the whole suite; `testpaths = ["tests"]` in
  `pyproject.toml` makes bare `pytest` work (the unrelated `USB-6009 test scripts/`
  file no longer aborts collection). Version is now dynamic from `__version__` —
  one source of truth.

### Tests (30 → 45)
- Core: relay ON time vs. chunk size, ABORT during the pulse, fire-confirm from the
  running task, driver refusal of a second AI task, reversed-wiring inhibit,
  validation bounds, `TeeWriter` close ordering, calibration setup error.
- GUI: recovery listing next to the output file, settings round-trip of the ignition
  thresholds, FIRE blocked during ARMING, LEDs following configured thresholds,
  typed-device gating. QSettings redirected to a temp dir so tests stay out of the
  developer's profile.
- Fake backend models the single-AI-engine reservation and timestamps DO writes.

### Not changed (deliberate)
- Continuous leak monitoring after arming (review S-6) — the FSD does not require it;
  left as a decision for the operator before first live use.
- Phase 6 hardware verification per `packaging/README.md` is still pending.

---

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
