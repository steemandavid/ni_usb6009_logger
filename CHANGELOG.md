# Changelog

## 2026-10-02 — Simulated-device tab walk all-pass; enumeration names a dead config service

Closes FSD §17 items 4 and 5 (both 2026-10-01 follow-ups). Test suite 60 → 62;
`flake8` clean. Both new tests were confirmed to **fail against the previous
code**.

### NI services were down again after the reboot

`mxssvr` (NI Configuration Manager) was *Stopped* despite *Automatic*, and
`nidevldu` (NI Device Loader) terminated unexpectedly once at boot (event
7034, 08:08). NI MAX's "database" complaint is just `mxssvr` being down
(the linked knowledgebase article is about the service, not a corrupt
database). Both started from an elevated shell; second occurrence in two
days — see follow-ups.

### Tab walk against the real NI-DAQmx driver (follow-up 1)

`walk_real_daq.py` (repo root) drives the GUI offscreen against the
NI-DAQmx simulated device: same pattern as the 2026-10-01 fake-backend walk,
but through the real driver stack. **All ten flows pass; no app defects
found.**

| Flow | Result |
|---|---|
| Detection → CSV run (301 lines) | PASS |
| Recovery tab lists `_OK` copy | PASS |
| XLSX run | PASS |
| Calibration start/stop (simulated AI −0.30…+0.70 V) | PASS |
| Ignition defaults → FIRE_PENDING → abort (simulated signal *passes* continuity) | PASS |
| ARM → FIRE_PENDING → ABORT (DO LOW first and last) | PASS |
| ARM → FIRE (relay ON 0.5 s → OFF) | PASS |
| Window close mid-run | PASS |
| Bogus typed device name (graceful `-200220` in the log pane) | PASS |
| Mid-run device deletion in NI MAX → interrupted 140 KB recovery copy listed first | PASS |

Harness lessons (the walk's own three failures, all harness bugs):

- A **typed device name survives `rescan()`** by design (the escape hatch);
  after the bogus-device step the real device must be re-selected or every
  later run arms against `DevX` → `-200220` "Device Identifier is Invalid".
- `fire_btn.click()` cannot hold-to-fire: `pressed`/`released` bracket it
  instantly and the hold rightly cancels. Drive the 50 ms hold timer
  (`_hold_start()`) with the button `setDown(True)` instead.
- After `win.close()` mid-run, the queued `finished` signal needs a pumped
  event loop before `MainWindow.worker` clears — a step that reads it must
  `processEvents()` first.

### Changed — an empty device list is not also an empty explanation (follow-up 2)

- `core/daq.py`: `enumerate_devices_ex() -> (devices, problem)` with problem
  `None` / `"service"` / `"driver"`. `DriverNotInstalledError` → `"driver"`;
  any other `DaqError` → `"service"` (what a stopped `mxssvr` actually
  raises: `MAX: (Hex 0x8004032B) The configuration database is not running`).
  `enumerate_devices()` wraps it; `driver_available()` removed (no callers
  left).
- GUI status bar now distinguishes: *"NI configuration service not running —
  start the NI services or reboot the PC (see the README)"* instead of
  *"No DAQ detected — waiting for device…"* (`DevicePicker.last_problem`).
- `gui/app.py`: launch shows a service-specific dialog instead of the
  misleading driver-missing one; `--selftest` names the cause (exit 2 for
  both, wording differs).
- Fake: `STATE.devices_error` knob raised by `_SystemLocal.devices`, so CI
  can reproduce the service-down shape.
- Test gotcha: exception classes must come from the `fake_daq` **fixture
  handle** — re-importing `_fake_nidaqmx` inside a test builds a *second*
  module whose classes `enumerate_devices_ex()` cannot recognize (classified
  `"driver"`), which is exactly what the first run of the test did.
- Docs: FSD §5 "NI service down" row, §13 selftest wording, §17 items 4/5
  struck through; README Errors section leads with the new status-bar text.

### Commits

| SHA | Subject |
|---|---|
| `a06d276` | Name a stopped NI config service instead of showing an empty desk |

### Verification

- `--selftest` live (services up, simulated device deleted by the unplug
  test): *"driver OK, no DAQ device found"*, exit 1.
- The live service-down branch was **not** re-verified (the UAC prompt to
  stop `mxssvr` was declined); it is covered by the fake test plus
  yesterday's real error text.

### Follow-ups

1. Set recovery options (auto-restart) on `mxssvr`/`nidevldu` — the services
   have now failed to come up after two consecutive reboots.
2. Recreate `Simulated-usb-6009` in NI MAX when the simulated device is
   needed again (the unplug test deletes it).
3. Hardware-only items unchanged (FSD §17 items 1–3).

## 2026-10-01 — NRSE removed from the GUI; tab walk fixes

Closes FSD §17 items 4 (NRSE) and, on the fake backend, 5 (walk the remaining tabs).
Test suite 54 → 60; `flake8` clean. Every new test was confirmed to **fail against
the previous code**.

### Changed — NRSE no longer offered

- Both terminal-config combos (Term config, Sense term config) are filled from
  `core.config.AI_SUPPORTED_TERMS` (RSE, DIFF), so GUI and validation cannot drift.
- A settings blob saved by an older version with `NRSE` falls back to RSE, with a note
  in the Log tab's output pane. (A status-bar message was tried first: device
  detection overwrites it milliseconds after launch, so nobody would ever see it.)
- The CLI keeps `--term NRSE` in its argparse choices deliberately (explains instead
  of "invalid choice"); golden `--help` unchanged.

### Fixed — GUI tests were writing the real Windows registry (critical for the dev box)

`QSettings(org, app)` **always uses NativeFormat** — the registry on Windows — and
ignores `QSettings.setDefaultFormat()`, which only applies to the other constructors.
The `qapp` fixture's redirect to a temp INI therefore did nothing on Windows:

- every GUI test overwrote the operator's real saved settings
  (`HKCU\Software\steeman.be\NI USB-6009 Logger`), leaving pytest temp paths and
  **empty buzzer/relay DO lines** behind;
- state leaked between tests — the cause of `test_fire_stays_blocked_during_arming`
  failing on unmodified code (it inherited empty DO lines, so the ignition run was
  rejected by validation and ARMING was never reached).

Linux CI cannot notice: there NativeFormat *is* an INI file. `gui/settings.py` now
builds `QSettings(QSettings.defaultFormat(), UserScope, org, app)` — registry in
production, temp INI under the fixture. `test_settings_stay_out_of_the_real_profile`
guards it. The polluted registry key was deleted, so the GUI starts from defaults.

### Fixed — defects found walking the tabs (fake backend)

A scripted offscreen walk (unhandled slot exceptions recorded) covered: invalid
configs, XLSX logging, mid-run unplug and replug, Recovery listing and Copy to…,
ignition with no sense channel (ARM → FIRE → ABORT), DIFF on a single-ended sense
channel, and closing the window during FIRE_PENDING.

| Defect | Fix |
|---|---|
| Invalid settings (vmin ≥ vmax, DIFF on ai4–ai7, …) were validated only inside the worker and surfaced as *"Something went wrong during the test … data recorded so far is safe"*, with `ConfigError:` and CLI flag names (`--term`, `--sense-term`) | `_panel_config()` calls `validate()` up front → "Cannot start" / "Cannot arm" dialog; `_gui_message()` strips `Error: ` and maps flags to GUI field names |
| Recovery tab empty at launch even with files on disk, and **not refreshed after an unplug/error** — the interrupted copy, the one that matters, was not listed | Refresh at launch, when the tab is opened, and in `_worker_gone` (every ending) |
| **Copy to…** raised `FileNotFoundError` in a slot → `_excepthook` → app closed | `OSError` caught, "Copy failed" dialog |

Verified OK during the walk: XLSX output, Start/ARM gating on unplug/replug (within
one 2 s poll), ignition DO sequence (LOW first and last), window close mid-ignition
(worker stopped, DO LOW, ~0.02 s on the fake).

### Docs

- FSD §4 (RSE/DIFF only), §10 (Recovery refresh + copy failure), §12 (pre-start
  config errors, copy failure), §17 open items rewritten.
- `packaging/README.md`: uninstall check pointed at `%LOCALAPPDATA%`; settings
  actually live in the registry key above.

### Commits

| SHA | Subject |
|---|---|
| `ab5337f` | Drop NRSE from the GUI and fix defects found walking the tabs |

### Notes / gotchas

- **NI services stopped on this machine.** `mxssvr` (NI Configuration Manager) and
  `nidevldu` (NI Device Loader) were *Stopped* despite *Automatic* start; nidaqmx
  then raises `MAX: (Hex 0x8004032B) The configuration database is not running`,
  and the simulated USB-6009 is invisible. Starting them needs admin:
  `Start-Service mxssvr, nidevldu` (elevated) or reboot.
- In that state `daq.enumerate_devices()` swallows the error and the GUI shows
  *"No DAQ detected — waiting for device…"* — misleading; see follow-up 2.
- The walk scripts must patch `QMessageBox.exec` too: `_update_start_enabled()`
  copies `MainWindow.interactive` onto the ignition panel, and a real modal hangs an
  offscreen run indefinitely.
- `_make_window` sets the output file *after* construction, so anything the window
  does at launch from the saved output path must be tested by seeding settings first.

### Follow-ups

1. Walk the tabs against the **NI simulated device** once the NI services run
   (FSD §17 item 4).
2. Distinguish "NI configuration service not running" from "no device" in
   enumeration and say so in the GUI (FSD §17 item 5).
3. Hardware-only items unchanged (ignition dry run, accuracy/noise, sustained
   high rate, PyInstaller DLL hooks).

## 2026-09-20 — First run on Windows: driver, console and GUI fixes

First time the project ran on the Windows machine that hosts the DAQ. Development
and CI had only ever been Linux, which hid one whole class of defect: anything that
touches the real NI-DAQmx module surface, the Windows console encoding, or a Qt
slot. Test suite grew 45 → 54; `flake8` clean across the tree.

No USB-6009 hardware was present. An **NI-DAQmx simulated device** (`Simulated-usb-6009`,
created in NI MAX) stood in and found three of the bugs below on its own.

### Environment set up on this machine

| Item | Value |
|---|---|
| Project | `C:\Users\David\claudecode\projects\ni_usb6009_logger` |
| Venv | `.venv` on Python **3.11.9** (3.13 is the system default; 3.11 matches the existing bytecode and has proven wheels) |
| Install | `pip install -e .[gui,excel]` + `requirements-dev.txt` |
| NI-DAQmx | **25.5.0**, NI MAX present at `C:\Program Files (x86)\National Instruments\MAX\NIMax.exe` |
| nidaqmx-python | 1.6.0 |
| Test device | `Simulated-usb-6009` (NI MAX → Devices and Interfaces → Create New → NI-DAQmx Simulated Device → USB-6009) |

### Fixed — driver detection and API surface (critical)

- **The GUI could never see the driver.** `core/daq.py` called `nx.System.local()`,
  but `nidaqmx` has no top-level `System` — it lives in the `nidaqmx.system`
  submodule, which `nidaqmx/__init__.py` does not bind. `driver_available()` always
  returned `False` and `enumerate_devices()` always returned `[]` (the
  `AttributeError` was swallowed by its `except`). With NI-DAQmx installed the app
  still showed the "driver missing" dialog and exited 1; the device picker was
  permanently empty; `--selftest` always exited 2.
- **Every logging run died the same way**, one commit later: `nx.stream_readers`
  is also unbound, so the `AnalogMultiChannelReader` lookup in `session.py` and
  `calibration.py` raised `AttributeError` before a byte was written.
  (`stream_readers` *is* listed in `nidaqmx.__all__` but not imported — which is
  what made it easy to miss.)
- `daq.backend()` now imports `constants`, `errors`, `stream_readers` and `system`
  **explicitly**, so `nx.<sub>` holds regardless of what `__init__` binds in a given
  nidaqmx version.
- **Root cause of the blind spot:** `_fake_nidaqmx` exposed `System` at the top
  level, i.e. the fake was *more permissive* than the API it stands in for. It now
  mirrors the real layout (`nidaqmx.system` submodule, no top-level attribute), with
  a comment stating the invariant: do not add an attribute here that `backend()`
  does not import.

### Fixed — Windows console encoding (critical)

The CLI crashed with `UnicodeEncodeError` on **any** redirected or piped output —
`ni_usb6009_logger --help > out.txt` died before printing anything. Python only uses
the Unicode console API when stdout *is* a console; once redirected it falls back to
the locale encoding (cp1252 on a Western Windows install). Four printed characters
have no cp1252 mapping:

| Char | Where | Broke |
|---|---|---|
| `≈` U+2248 | `cli.py` help text | `--help` |
| `→` U+2192 | `session.py` status line | every run |
| `█` U+2588 | `helpers.py` progress bar | `--progress bar` |
| `Ω` U+03A9 | `session.py` ignition messages | ignition runs |

`helpers.configure_stdio()` (UTF-8, `errors="replace"`) is called from both entry
points — from `cli.main()` *before* `parse_args()`, since argparse prints `--help`
itself. Invisible to CI twice over: Linux is UTF-8, and pytest's `capsys` captures to
memory without ever encoding.

### Fixed — GUI crash on stopping a calibration run

Reported from a live GUI session. Stop anything on the Calibrate tab and the app died:

```
AttributeError: 'NoneType' object has no attribute 'output_path'
```

`CalibrationSession.run()` was annotated `-> None` and returned nothing, while
`LoggingSession.run()` returns a `SessionResult`. `gui/worker.py` emits whatever
`run()` hands back straight into `MainWindow._on_finished`, which opens with
`if result.output_path:`. Reproducible every time, since calibration runs until
stopped. Nothing was at risk — the crash lands after the session finishes, and
calibration writes no file.

- Calibration now returns `SessionResult(state=DONE)`; paths stay `None`, so no
  "Test finished" dialog appears for a screen-only mode.
- `_on_finished` returns early on `None` — a session returning nothing is a bug in
  that session, but it must not close the app on the user.

**The harness gap mattered more than the bug.** A test already covered this exact
flow (`test_gui_calibration_feeds_readout_and_plot`: start, wait for readout, Stop,
wait for worker) and passed while the app died. Qt does not propagate an exception
raised inside a slot — it routes it to `sys.excepthook`. In the app that hook shows
the dialog and quits; under pytest it is the default hook, printing to stderr that
nothing asserts on. **Any** GUI crash of this shape would have passed CI. The `qapp`
fixture now records hook calls and fails the test; verified by reverting both fixes
and confirming the test errors.

### Added — USB-6009 pre-flight validation

`config.validate()` rejects what can be predicted, before any task is created, so
both front-ends behave the same (it runs inside `session.run()` and
`calibration.run()`). Values were **read back from the driver**
(`ai_max_multi_chan_rate`, per-channel `ai_term_cfgs`), not taken from the datasheet:

| Rule | Value |
|---|---|
| Aggregate sample rate | 48 kS/s shared across all AI channels |
| Terminal config | RSE and DIFF only — **the device has no NRSE mode** |
| Differential channels | ai0–ai3 only; ai4–ai7 are single-ended |

The same terminal-config rules apply to the ignition sense channel, which catches
the `DIFF` default landing on a single-ended-only input. `--term NRSE` stays in the
argparse choices deliberately, so anyone carrying it over from an older script gets
an explanation rather than "invalid choice".

`cli.main()` also catches `DaqError` and prints NI's own text — which names the
offending property and its permitted range — instead of a traceback, exit 1. The
exception class is resolved via a new `daq.daq_error_type()` so the CLI still never
imports `nidaqmx` and the fake's `DaqError` is matched under `NI_USB6009_FAKE`.

### Fixed — read timeout was a fixed 10 s

N samples at R Hz cannot arrive in less than N/R seconds, so the *first* read failed
with `DaqError -200284` whenever a chunk took longer. The default chunk of 1000 broke
at any rate below ~100 Hz: `--rate 50` failed every time, `--rate 100` was a coin flip
(which is how it was spotted — one test run failed, the identical retry passed).
`config.read_timeout_for(samples)` keeps 10 s as a floor and grows to
`samples/rate × 1.5 + 1`. `read_timeout` is internal, with no CLI or GUI flag, so
nothing user-facing changed.

This matters for real use: README §7's calibration examples run at `--rate 1`.

### Fixed — test suite portability (Windows)

| Test | Problem |
|---|---|
| `test_calibration_screen_only` | Used `os.kill(os.getpid(), SIGINT)`. On Windows `os.kill` only maps `CTRL_C_EVENT`/`CTRL_BREAK_EVENT` to a console event; anything else falls through to `TerminateProcess`. It **killed the interpreter mid-run** — a bare `pytest` printed 38 dots then died with exit 2, no summary, no failure detail. Now `_thread.interrupt_main()`, which trips SIGINT in the main thread and runs the handler `cli.main()` installs. |
| `test_help_golden` | `read_text()` with no `encoding=` decoded the UTF-8 golden file as cp1252. The help output itself was byte-identical. |
| `test_build_config_maps_flags` | Asserted `str(cfg.logs_dir) == r".\logs"`. On Windows that normalises to `logs`; on Linux `.\logs` is a *single filename containing a backslash*, so a directory literally named `.\logs` was created and the assertion passed by accident. Default is now `Path("logs")`, which also removed the `rglob` workaround `test_logging_auto_named_no_overwrite` needed to find its own output. |
| `test_missing_device_raises` | Asserted a `DaqError` propagates, commented *"(today's behavior)"* — it pinned the traceback rather than requiring it. Now `test_missing_device_reports_driver_error`: exit 1, the driver's message, and **no** `Traceback` in the output. |

### Repo hygiene

`src/ni_usb6009_logger.egg-info/` and the committed `.pyc` files were untracked
(`git rm --cached`) — already matched by `.gitignore`, but ignore rules do not apply
to tracked paths. Added `*.egg-info/`, `build/`, `dist/`.

### Verified working (simulated device, real driver stack)

| Check | Result |
|---|---|
| `--selftest` | exit 0, `Simulated-usb-6009 (USB-6009)` |
| `--selftest` under `NI_USB6009_FAKE=1` | exit 0, `Dev1` |
| AI → CSV | 2000 samples/ch at 1000 Hz over 2 s, exact |
| AI + DI → XLSX | 500 samples/ch, 30 KB written |
| Aggregate boundary (4 ch × 12 kHz = 48 kS/s) | accepted |
| Rate ceiling / NRSE / DIFF on ai4+ | rejected with exit 2 and a usable message |
| Full suite + `flake8 src tests` | 54 passed, clean |

### Commits

| SHA | Subject |
|---|---|
| `85b25ec` | Fix driver detection on real hardware; make the test suite run on Windows |
| `c1779ce` | Fix two crashes and add USB-6009 pre-flight validation |
| `14d5ab7` | Fix GUI crash when a calibration run is stopped |

### Notes / gotchas

- **CI cannot catch any of this.** Both jobs run on ubuntu with no NI driver, and
  the fake backend is now a faithful stand-in rather than an authority — it cannot
  reject a bad terminal config, exceed a rate ceiling, or reproduce cp1252. The
  pre-build checks added to `packaging/README.md` are the only guard.
- **Fake backend vs simulated device.** The fake is better for *ignition logic*
  (`ai_voltage_overrides` injects sense voltages). The simulated device is better for
  *driver interaction*. Neither covers real relay timing or igniter continuity.
- **Ignition without hardware:** leave the sense channel **blank** to walk
  ARM → FIRE → ABORT end to end. With a sense channel configured, arming *should* be
  inhibited — the simulated ±9.4 V sine reads as ±9400 mA across a 1 Ω shunt, far past
  the 5 mA leak limit, and negative half-cycles trip the reversed-wiring check. Both
  inhibits firing is the pass condition, not a bug.
- `NI_USB6009_FAKE=1` gives **no visual indication** in the GUI that it is faking.
  Clear the variable before any real measurement.
- The `_on_finished` `None` guard means a session returning `None` now fails
  *quietly*. A tab finishing with no dialog where one is expected is worth
  investigating, not a silent pass.

### Follow-ups

1. Remove **NRSE** from the GUI terminal-config combos (`main_window.py:117` and
   `:242`) and from FSD §4. Choosing it now fails at Start with a clear message, but
   offering a choice that can never work is worse than not offering it.
2. Walk the remaining GUI tabs (Log, Ignite, Recovery, persistence) against the
   simulated device — the harness gap means other tabs may hide the same class of
   crash.
3. Hardware-only items unchanged: ignition dry run with relay board and shunt,
   analog accuracy and noise floor, sustained high-rate behaviour, and the
   PyInstaller bundle picking up the nidaqmx DLL hooks.

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

### Follow-ups
1. **`installer.iss` has still never been compiled.** The Pascal precedence and
   preprocessor fixes were made on Linux; ISCC has never successfully run this
   script, and the Windows session above exercised the driver stack but not the
   installer build. Verify with
   `iscc /DAppVersion=0.0.0 /DSourceDir=..\dist\NI6009Logger packaging\installer.iss`
   on Windows, or a throwaway tag, **before** the hardware session.
2. Hardware checks specific to this session's changes: fire-confirm with the sense
   channel included in `--channels`; relay ON time on a scope at GUI defaults
   (1 kHz / 1000-sample chunks, 0.2 s pulse); whether the driver really refuses the
   fallback second AI task (the assumption `_fake_nidaqmx.py` now models).
3. Bump `__version__` to 1.2.0 and tag — `pyproject.toml` derives the version from
   `__init__.py`, so that is the only edit.
4. README "10. My current test command" passes `--calibrate` *and* `--ignite`, which
   `validate()` rejects with exit code 2. Pre-existing; the command as written does
   not run.

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
