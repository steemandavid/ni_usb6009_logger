# GUI Functional Specifications — NI USB-6009 Logger

**Version:** 1.0 · **Date:** 2026-09-20 · **Status:** Implemented (Phases 0–5); Windows
installer verification (Phase 6) pending — see §17.

---

## 1. Introduction

### 1.1 Purpose
This document specifies the functional behavior of the stand-alone Windows GUI
application for the NI USB-6009 data logger (`ni_usb6009_gui`). It is the reference
for verification, future changes, and user documentation.

### 1.2 Target user
A non-IT-savvy operator of a rocket-motor static test stand. Installation must be
Next-Next-Finish; every error must be explained in plain language; no data may be
lost through user error.

### 1.3 Scope
The GUI offers full parity with the command-line application (`ni_usb6009_logger`):
logging of analog inputs (AI) and digital inputs (DI) to CSV/XLSX, calibration mode
with moving-average readout, and the ignition sequence (buzzer + relay with
current-sense failsafes). Both applications share one core; the CLI's flags and
console output are unchanged.

### 1.4 Definitions
| Term | Meaning |
|---|---|
| DAQ | The NI USB-6009 measurement device (`Dev1` in NI MAX) |
| AI / DI / DO | Analog inputs / digital inputs / digital outputs of the DAQ |
| Shunt | 1 Ω resistor in the igniter ground path; voltage across it measures igniter current |
| Recovery file | Parallel CSV written with every logging/ignition run (crash/loss insurance) |
| ARM / FIRE / ABORT | The ignition three-step safety flow |
| Core | `src/ni_usb6009_logger/core/` — all DAQ logic, hardware failsafes, file writing |

---

## 2. System overview

```
┌─────────────┐   ┌─────────────────────────── core (Qt-free) ───────────────┐
│ CLI adapter │──▶│ LoggerConfig · Reporter callbacks · LoggingSession       │
└─────────────┘   │ CalibrationSession · writers (CSV/XLSX/Tee) · daq.py     │◀── NI-DAQmx driver
┌─────────────┐   │ (the ONLY nidaqmx import)                                │
│ GUI (PySide6)│──▶│                                                          │
└─────────────┘   └──────────────────────────────────────────────────────────┘
```

- The GUI runs sessions in a worker `QThread` (`gui/worker.py`) and receives data via
  queued Qt signals. Widgets never call the DAQ directly.
- All hardware safety logic lives in the core and is identical for CLI and GUI.
- The fake backend (`NI_USB6009_FAKE=1`, `_fake_nidaqmx.py`) allows full GUI operation
  on machines without driver or hardware (development/CI/demo).

---

## 3. Installation & startup

### 3.1 Installer (Windows)
1. Single setup exe built by Inno Setup (`packaging/installer.iss`), version taken
   from `ni_usb6009_logger.__version__`.
2. Components: **app** (fixed) and **NI-DAQmx driver runtime** (default-checked when
   the redistributable `nidaqmx_setup.exe` is shipped alongside). The driver installs
   silently (`/q /AcceptLicenses yes /suppressrestart`) — no user interaction.
   *(Flags must be confirmed against the exact redistributable — §17.)*
3. Optional desktop shortcut; Start-menu entries; clean uninstall.
4. Post-install **self-test** (checkbox, default on): the installer runs
   `NI6009Logger.exe --selftest` and shows the summary:
   | Result | Meaning shown to user |
   |---|---|
   | 0 | "Driver OK and USB-6009 detected — everything works." |
   | 1 | "Driver OK. No DAQ device found yet. Connect the USB-6009…" |
   | 2 | "The NI-DAQmx driver is not working yet. Reboot once…" |

### 3.2 First launch / driver check
- On start the GUI checks `driver_available()`. If the NI-DAQmx driver is missing, a
  modal dialog explains this and offers **"Open download page"** (ni.com NI-DAQmx).
  The app then exits. This path also covers an installer shipped without the driver
  component.

### 3.3 Development mode
`NI_USB6009_FAKE=1` substitutes the in-memory fake DAQ; the entire GUI operates
normally (offscreen rendering with `QT_QPA_PLATFORM=offscreen` for CI).

---

## 4. Main window layout

```
┌────────────────────────────────────────────────────────────────────────────┐
│ NI USB-6009 Logger — v<x.y.z>                                    [status bar]│
├───────────────────┬─ Output file: [path………………] [Browse…] ─────────────────┤
│ CONFIG PANEL      │ ┌ Tab: Log │ Calibrate │ Ignite │ Recovery ───────────┐│
│  DAQ device  [ ▼] │ │ (tab content; see §6–§9)                            ││
│  AI channels [   ]│ │                                                      ││
│  DI lines    [   ]│ │                                                      ││
│  Sample rate [   ]│ │                                                      ││
│  Chunk size  [   ]│ │                                                      ││
│  Term config [ ▼] │ │                                                      ││
│  AI range  [ ] to [ ]                                                      ││
│  Duration    [   ]│ └──────────────────────────────────────────────────────┘│
└───────────────────┴────────────────────────────────────────────────────────┘
```

- **Config panel** (applies to all modes): device combo (auto-detected, editable),
  AI channels (comma list, e.g. `ai0,ai1`), DI lines (spec syntax `port0/line0:7` or
  comma list), sample rate (1–48 000 Hz), chunk size, terminal config (RSE/NRSE/DIFF),
  AI voltage range, duration (0 = run until Stop).
- **Output file box** sits above the tabs and is shared by Log and Ignite.
- All settings persist across launches (§11) and are restored on start.

---

## 5. DAQ device detection & monitoring

| Behavior | Specification |
|---|---|
| Launch scan | Enumerate all devices via the driver; a unique device is auto-selected and shown in the status bar ("DAQ detected: Dev1 (USB-6009)") |
| Multiple devices | User picks from the combo (each entry shows name + product type) |
| No device | Status bar "No DAQ detected — waiting for device…"; Start/ARM disabled; a **Refresh** button and a 2-second automatic rescan keep watching |
| Hot-plug | Detected within ≤2 s; the combo and status bar update; Start/ARM enable when a device appears |
| Hot-unplug **mid-run** | The DAQ read raises; the session stops safely (DO forced LOW by the core), a friendly dialog explains what happened and names the output + recovery files; all data written so far is on disk (§10) |
| Typed name | The device field stays editable so a device not visible to enumeration can be entered manually; typing a name enables Start/ARM even when enumeration returns nothing |

---

## 6. Log tab

1. **Precondition:** an output file must be chosen (**Browse…**) before **Start** is
   possible — Start stays disabled otherwise. Browse suggests
   `Documents\NI6009 Logs\ni_<device>_<timestamp>.csv`, offers CSV/XLSX filters, and
   never overwrites (a `_1`, `_2`… suffix is appended to existing names). The
   suffixed name is applied immediately on selection, so the path shown in the
   output box is the path that will be written.
2. **Start** launches a logging session in the worker:
   - AI channels are hardware-timed at the sample rate; DI lines are snapshotted once
     per chunk (USB-6009 DI is static).
   - Rows are `timestamp_iso, sample_index, <ai…>, <di…>` in the chosen format.
   - A recovery CSV is written in parallel (§10).
3. **Live view:** the plot (§9) shows every AI channel in real time; the status bar
   shows samples/channel, elapsed time and aggregate rate.
4. **Stop** (or Duration elapsing) ends the run; tasks stop, files close, and a
   summary dialog offers **"Open folder"**.
5. The log pane echoes the same status lines the CLI prints.

---

## 7. Calibrate tab

- Settings: moving-average window (s), screen output rate (Hz), internal sample
  rate (Hz).
- **Start calibration** runs screen-only — **no file is written** and no output file
  is required.
- Display: one large numeric readout of the per-channel moving averages (plus raw
  values when the GUI is extended to show them), refreshed at the output rate, and a
  live plot of the raw signals.
- **Stop** ends the run.

---

## 8. Ignite tab (safety-critical)

### 8.1 Configuration fields
Buzzer DO line, igniter relay DO line, current-sense AI channel, sense terminal
config, shunt resistance (Ω), continuity minimum (mA), leak maximum (mA),
fire-confirm minimum (mA), buzzer warning time (s), stabilize time (s), relay pulse
time (s). An output file is required (shared box) — ignition always logs.

### 8.2 Safety panel
Four status LEDs — **DO lines LOW**, **Continuity**, **No leak current**,
**Igniter relay** — a status line (state + live current during arming), a hold
progress bar, and three buttons: **ARM**, **FIRE**, **ABORT**.

### 8.3 Flow (state machine)

| Step | Trigger | Behavior | Hardware |
|---|---|---|---|
| 1. ARM | User clicks ARM → confirmation dialog ("buzzer will sound… relay stays OFF") | Session starts; **DO lines forced LOW first**, before anything else | `[F,F]` |
| 2. Arming | After confirm | Buzzer sounds for the warning time while shunt current is monitored; LEDs + live mA shown; user may ABORT | `[T,F]` |
| 3a. Inhibit — leak | Current ≥ leak max | Buzzer off, **FIRE never offered**, status "INHIBITED by safety failsafe", reason in log | back to `[F,F]` |
| 3b. Inhibit — no continuity | Current never ≥ continuity min | Same as 3a | `[F,F]` |
| 4. Logging | Arming passed | Logging starts; after the stabilize time the state becomes FIRE_PENDING and **FIRE becomes enabled** | `[F,F]` |
| 5. FIRE | User **holds the FIRE button 2 s** (progress bar fills; releasing cancels) | Fire permission granted to the core, which energizes the relay for the pulse time and verifies current | `[F,T]` → `[F,F]` |
| 6. ABORT | Any moment | Stop requested; core re-forces DO LOW on every exit path | `[F,F]` |

Rules:
- FIRE is **never** enabled before FIRE_PENDING, and is disabled again after FIRED,
  INHIBITED, or session end.
- All current thresholds (continuity/leak/fire-confirm) are evaluated **in the core**,
  not the UI — identical protection as the CLI.
- If fire-confirm current stays below threshold during the pulse, a warning is shown
  (wiring/supply/igniter check) — the relay still completes its pulse and switches off.
- **Fire-confirm source:** the USB-6009 has a single AI timing engine, so a second AI
  task cannot run alongside the acquisition task. When the current-sense channel is
  included in the AI channel list, the confirm value is taken from the running task's
  own samples (peak of the chunk covering the pulse) — this is the recommended
  configuration. Otherwise the core attempts a separate task (range derived from
  `fire_confirm_ma × shunt_ohms`) and reports a log message if the driver refuses it;
  the pulse itself is unaffected either way.
- **Pulse timing:** while ignition is enabled the AI stream is read in ~20 ms
  sub-blocks rather than one chunk at a time, so the relay opens after
  `pulse_seconds` (not after the current chunk read completes) and ABORT reaches the
  hardware within a sub-block.
- Closing the window during a session equals ABORT: the worker is stopped and the
  window stays open, behind a modal "stopping safely" indicator, until the worker has
  actually finished and the core's exit path has forced the DO lines LOW.

---

## 9. Live plot

- One curve per AI channel, distinct colors, legend with channel names.
- Data appended chunk-by-chunk into fixed-capacity ring buffers (60 s window or
  ≥4× chunk, capped at 500 000 points per channel) — memory stays flat no matter the
  run length, and bounded at the panel's maximum rate × channel count.
- Repaint throttled to ~10 Hz; PyQtGraph peak downsampling + clip-to-view keep
  multi-channel 1 kHz streaming smooth.
- View toggle **follow live / pause view**; user may zoom/pan while paused.
- X axis: seconds relative to run start. Y axis: volts (configured AI range).

---

## 10. Output-file-first & recovery dual-write

| Aspect | Specification |
|---|---|
| File choice | Mandatory **before** Start/ARM (shared box above tabs); safe naming; format from extension (CSV default) |
| Recovery path | `<output dir>/recovery/<output stem>_recovery.csv`, created automatically for every logging/ignition run |
| Format | Recovery is **always CSV flushed every chunk** (XLSX only reaches disk at close, so it cannot serve as the crash copy) |
| Clean finish | Recovery file renamed `…_recovery_OK.csv` |
| Interrupted run (crash, unplug, abort) | Recovery file remains without the `_OK` marker — partial data preserved on both sinks (writers close in a `finally`) |
| Recovery tab | Lists all recovery files (newest first) with OK/INTERRUPTED status and size, from the current output file's `recovery/` folder **and** the default logs folder; **Copy to…** restores any file to a user-chosen location |

---

## 11. Settings persistence

- Whole configuration stored as one JSON blob under QSettings
  (`steeman.be` / `NI USB-6009 Logger`), versioned key `config_v1`.
- Saved on every run start and on close, covering **all** panel fields — including
  the calibration *and* ignition parameters regardless of which mode was started, so
  the continuity/leak/fire-confirm thresholds survive a plain logging run.
- Restored on launch (all panel fields, calibration and ignition parameters, output
  directory). Corrupt/missing settings fall back to defaults
  (`Documents\NI6009 Logs`).

---

## 12. Error handling matrix (graceful, never a traceback)

| Situation | User sees |
|---|---|
| NI-DAQmx driver missing at launch | Modal + link to ni.com download; app exits |
| DAQ disappears / unreachable during run | Dialog: check USB cable / replug; names output + recovery files |
| Driver services broken ("MIG"/DLL errors) | Dialog: restart NI services or reboot (README has the service names) |
| No output file chosen | Start/ARM simply disabled; hint text in the tab |
| Unwritable output path | Error dialog with the underlying message |
| Ignition setup failure (DO task) | Error dialog (historic CLI exit code 3 equivalent) |
| Any unexpected exception | Top-level handler: friendly dialog; details to stderr/log output |

---

## 13. `--selftest` mode (installer integration)

Console mode: `NI6009Logger.exe --selftest` prints one SELFTEST line and exits
0 (driver OK + device found) / 1 (driver OK, no device) / 2 (driver missing/broken).
Used by the installer's post-install verification (§3.1).

---

## 14. Non-functional requirements

| Requirement | Specification |
|---|---|
| OS | Windows 10/11 64-bit (+ NI-DAQmx runtime) |
| Runtime deps in bundle | PySide6, PyQtGraph, numpy, openpyxl — everything except the NI driver |
| Never bundled | `nicaiu.dll` / any NI driver DLL (licensing + version skew) |
| Start-up | Onedir build for fast launch and low antivirus false-positive risk |
| Memory | Bounded by ring buffers; flat over run length (tested) |
| Data integrity | No overwrite ever; recovery copy per run; writers flush/close on all paths |
| Safety | DO-safe ordering and all failsafes in the shared core, golden- and state-machine-tested |

## 15. Verification traceability

| Spec section | Automated tests (30 total) |
|---|---|
| CLI parity (unchanged behavior) | `test_cli_parity.py` (golden `--help`, flag mapping, exit codes) |
| Logging data / auto-naming | `test_sessions_fake_daq.py` |
| Ignition DO sequence & inhibits | `test_sessions_fake_daq.py`, `test_core_sessions.py` |
| Fire-permission gate | `test_core_sessions.py` |
| Recovery dual-write & `_OK` rename | `test_core_sessions.py`, `test_gui_smoke.py` |
| Device gating / unplug / error surfacing | `test_gui_smoke.py` |
| Ring-buffer bounds | `test_gui_smoke.py` |
| Ignition GUI state machine | `test_gui_smoke.py` (full flow, leak inhibit, abort) |

CI runs the suite on every push (ubuntu; GUI tests offscreen) and builds the Windows
installer on `v*` tags (`.github/workflows/`).

## 16. Relationship to the CLI

- One repository, one core; feature work lands in both simultaneously.
- CLI flags, defaults, console output and exit codes are locked by golden tests.
- GUI-only features (output-file gating, recovery dual-write, hold-to-fire) are
  opt-in core capabilities inactive for the CLI.

## 17. Open items (Phase 6 — Windows hardware required)

1. Verify the installer on a clean VM: silent NI-DAQmx install flags, self-test,
   uninstall cleanliness, SmartScreen messaging ("More info → Run anyway"; optional
   code-signing certificate later).
2. Real-DAQ manual runs: calibration, CSV + XLSX logging, recovery inspection,
   relay/buzzer ignition dry run **without an igniter** before first live use.
3. Set the repo variable `NIDAQMX_URL` to bundle the driver component in CI builds,
   then tag `v1.2.0` to produce the first release installer.
