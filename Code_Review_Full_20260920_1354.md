# Full Code Review — NI USB-6009 Logger (Phases 0–7)

**Document ID:** NIUSB6009-REVIEW-FULL-001
**Reviewer:** Code Review Agent
**Date:** 2026-09-20
**Scope:** Whole codebase — shared core, CLI adapter, PySide6 GUI, tests, packaging, CI
**FSD Reference:** `GUI-functional-specifications-document.md` v1.0 (2026-09-20)
**Commit Reviewed:** `5396d51` (clean tree, branch `main`)

---

## Verdict: MAYBE

The architecture is genuinely good: the Qt-free core is a clean seam, the CLI is a
faithful thin adapter, the DO-safe ordering (`[F,F]` first, `finally` on every exit
path) is correct and well tested, and the 30-test suite is real coverage rather than
decoration — it passes in 11 s against the fake backend. But three classes of defect
stop this from being a pass. First, the **Windows release pipeline cannot currently
build**: `packaging/installer.iss` has a Pascal operator-precedence error and a
runtime path check that can never succeed on a target machine, and `release.yml`
feeds ISCC paths that don't resolve. Second, there are **real safety-relevant defects
in the fire path** — the relay ON time is quantized to the AI chunk read and can
substantially exceed `pulse_seconds`, ABORT during the pulse is not immediate, and
`closeEvent` can abandon a running worker after 5 s with the relay potentially still
energized. Third, several **FSD §5/§10/§11 behaviors are implemented in a way that
doesn't work for the operator** (Recovery tab looks in the wrong directory, safety
thresholds aren't persisted, the typed-device escape hatch is unreachable, the panel
LEDs use hardcoded thresholds instead of the configured ones). None of these are
architectural; all are fixable without restructuring.

---

## Table of Contents

1. [Coverage Analysis](#1-coverage-analysis)
2. [Deviation Report](#2-deviation-report)
3. [Plan vs. Implementation](#3-plan-vs-implementation)
4. [Edge Cases & Safety](#4-edge-cases--safety)
5. [Concurrency & Platform Issues](#5-concurrency--platform-issues)
6. [Error Handling](#6-error-handling)
7. [Code Quality](#7-code-quality)
8. [Summary](#8-summary)
9. [Recommendation](#9-recommendation)

---

## Files Reviewed

| File | Purpose |
|------|---------|
| `src/ni_usb6009_logger/core/session.py` | Logging session + ignition sequence (safety-critical) |
| `src/ni_usb6009_logger/core/calibration.py` | Screen-only moving-average session |
| `src/ni_usb6009_logger/core/config.py` | Config dataclasses + `validate()` |
| `src/ni_usb6009_logger/core/writers.py` | CSV / XLSX / Tee writers |
| `src/ni_usb6009_logger/core/helpers.py` | Safe paths, DI spec expansion, current conversion |
| `src/ni_usb6009_logger/core/daq.py` | Sole `nidaqmx` import; driver/device discovery |
| `src/ni_usb6009_logger/core/events.py` | `Reporter` interface, state enum, data records |
| `src/ni_usb6009_logger/cli.py` | Argparse adapter + historic console output |
| `src/ni_usb6009_logger/gui/main_window.py` | Config panel, tabs, session orchestration |
| `src/ni_usb6009_logger/gui/worker.py` | `QThread` session runner, Reporter→signal bridge |
| `src/ni_usb6009_logger/gui/app.py` | Entry point, driver check, `--selftest` |
| `src/ni_usb6009_logger/gui/settings.py` | QSettings JSON persistence |
| `src/ni_usb6009_logger/gui/widgets/ignition_panel.py` | ARM / hold-to-FIRE / ABORT panel |
| `src/ni_usb6009_logger/gui/widgets/live_plot.py` | Ring buffers + PyQtGraph curves |
| `src/ni_usb6009_logger/gui/widgets/device_picker.py` | Device combo + rescan |
| `src/ni_usb6009_logger/_fake_nidaqmx.py` | In-memory fake backend |
| `tests/` (5 files, 30 tests) | CLI parity, core sessions, fake-DAQ runs, GUI smoke |
| `packaging/installer.iss`, `packaging/ni_usb6009_gui.spec` | Inno Setup + PyInstaller |
| `.github/workflows/ci.yml`, `release.yml` | CI and tag-triggered release |

**Verification run (this review, not taken from the changelog):**

```
$ .venv/bin/python -m pytest tests -q
..............................                                           [100%]
30 passed in 11.34s

$ .venv/bin/python -m flake8
./USB-6009 test scripts/daq_diag.py:1:11: E401 multiple imports on one line
./src/ni_usb6009_logger/gui/main_window.py:12:1: F401 'QSpinBox' imported but unused
./src/ni_usb6009_logger/gui/main_window.py:593:1: W391 blank line at end of file
./src/ni_usb6009_logger/gui/widgets/ignition_panel.py:10:1: F401 'Qt' imported but unused
./src/ni_usb6009_logger/gui/worker.py:11:1: F401 'SessionResult' imported but unused
```

Note that bare `pytest` from the repo root **fails at collection** — see §7.

---

## 1. Coverage Analysis

| FSD § | Requirement | Status | Implementation |
|---|---|---|---|
| 3.1 | Inno Setup installer, version from `__version__` | **PARTIAL** | `installer.iss`; version passed via `/DAppVersion` from `release.yml:24`, but the script does not compile as written (§2 D-1) |
| 3.1 | Optional silent NI-DAQmx component | **PARTIAL** | Component declared, but its `Check` can never be true on a target machine (§2 D-2) |
| 3.1 | Post-install self-test + result messages | **PARTIAL** | Messages match the spec table exactly; the guard expression is malformed (§2 D-1) |
| 3.2 | Driver check at launch, download link, exit | DONE | `gui/app.py:54-71` |
| 3.3 | `NI_USB6009_FAKE=1` dev mode | DONE | `core/daq.py:12-22`, `_fake_nidaqmx.py` |
| 4 | Config panel fields, ranges, persistence | **PARTIAL** | All fields present (`main_window.py:85-125`); persistence incomplete (§2 D-7) |
| 5 | Launch scan / auto-select / status bar | DONE | `main_window.py:339-345`, `device_picker.py:24-39` |
| 5 | 2 s rescan, hot-plug ≤2 s | DONE | `DEVICE_POLL_MS = 2000`, `main_window.py:64-68` |
| 5 | Hot-unplug mid-run → safe stop + friendly dialog | DONE | `worker.py:78-79` → `main_window.py:510-530`; tested |
| 5 | Typed device name usable | **MISSING** | Start/ARM gated on enumeration only (§2 D-8) |
| 6 | Output file required before Start | DONE | `main_window.py:356-366`, `core/session.py:51-52` |
| 6 | Browse suggestion / filters / no overwrite | **PARTIAL** | `main_window.py:369-379` + `helpers.safe_path`; the confirm-overwrite dialog and the `_1` suffix disagree (§7) |
| 6 | Hardware-timed AI, DI snapshot per chunk, row format | DONE | `session.py:129-245` |
| 6 | Stop / duration / summary + "Open folder" | DONE | `main_window.py:532-557` |
| 7 | Calibrate tab, screen-only, no file required | DONE | `calibration.py`, `main_window.py:443-453` |
| 7 | Large readout + live plot at output rate | DONE | `main_window.py:473-477` |
| 8.1 | All ignition configuration fields | DONE | `main_window.py:222-249` |
| 8.2 | Four LEDs, status line, hold bar, three buttons | **PARTIAL** | Present; LED thresholds hardcoded (§2 D-6) |
| 8.3 | DO LOW first, ARM confirm, inhibits, FIRE gating, ABORT | DONE | `session.py:68-84`, `_arm()`, `ignition_panel.py`; tested end-to-end |
| 8.3 | Relay energized "for the pulse time" | **PARTIAL** | ON time quantized to the chunk read (§4 S-1) |
| 8.3 | Fire-confirm current verified during pulse | **PARTIAL** | Implemented, but likely non-functional on real hardware (§4 S-3, S-4) |
| 8.3 | Window close == ABORT | **PARTIAL** | Best-effort with a 5 s budget, then abandons (§4 S-2) |
| 9 | Ring buffers, 10 Hz repaint, downsampling, follow/pause | DONE | `live_plot.py` |
| 9 | Y axis = configured AI range | **MISSING** | Autoranges instead (`live_plot.py:144-145`) |
| 10 | Output-first, recovery path, CSV-always, `_OK` rename | DONE | `session.py:112-119, 275-281`; tested |
| 10 | Recovery tab lists all recovery files | **PARTIAL** | Looks in the wrong directory (§2 D-5) |
| 11 | Whole config as JSON under `config_v1`, restored on launch | **PARTIAL** | Storage correct; round-trip lossy (§2 D-7) |
| 12 | Error matrix, never a traceback | DONE (one gap) | `main_window.py:517-530`, `app.py:29-39`; calibration setup errors escape as `UnboundLocalError` (§6 E-1) |
| 13 | `--selftest` exit codes 0/1/2 | DONE | `app.py:15-26` |
| 14 | Onedir, no NI DLLs bundled, bounded memory | DONE | `ni_usb6009_gui.spec` |
| 15 | 30 automated tests, CI on push, installer on tag | **PARTIAL** | 30 tests pass; CI enumerates test files by name (§7) |
| 16 | CLI flags/output/exit codes locked by golden tests | DONE | `cli.py`, `tests/test_cli_parity.py`, `tests/golden/cli_help.txt` |

---

## 2. Deviation Report

### D-1 — `installer.iss` self-test guard is a Pascal precedence error — **CRITICAL**
`packaging/installer.iss`, `CurStepChanged`:

```pascal
if CurStep = ssPostInstall and WizardIsTaskSelected('runselftest') then
```

In Pascal, `and` binds *tighter* than `=`, so this parses as
`CurStep = (ssPostInstall and WizardIsTaskSelected(...))` — a `TSetupStep` compared
against a Boolean expression. ISCC rejects this with a type mismatch at compile time,
which takes the whole installer build down with it. Needs
`if (CurStep = ssPostInstall) and WizardIsTaskSelected('runselftest') then`.
This is the single most impactful finding in the review because it blocks FSD §3.1
entirely and has never been exercised (Phase 6 pending, no Windows CI job).

### D-2 — The NI-DAQmx driver component can never install — **CRITICAL**
```pascal
function NiDaqFileExists(): Boolean;
begin
  Result := FileExists(ExpandConstant('{#NiDaqSetup}'));
end;
```
`{#NiDaqSetup}` is a *preprocessor* value substituted at compile time — in CI it is
`..\packaging\nidaqmx\nidaqmx_setup.exe`, a path on the **build** machine. The
`Check:` runs at **install** time on the operator's PC, where that relative path does
not exist, so the check returns False for both the `[Files]` entry and the `[Run]`
entry. Result: even when the driver redistributable is shipped, the component is
silently skipped and the driver is never installed — the exact opposite of FSD §3.1's
"Next-Next-Finish" promise for a non-IT-savvy user. The compile-time presence of the
file should be tested with `#if FileExists(...)`, and any runtime check should target
`{tmp}\nidaqmx\nidaqmx_setup.exe`.

### D-3 — `release.yml` passes ISCC paths that don't resolve — **CRITICAL**
Two problems in `.github/workflows/release.yml:44-49`:

1. `/DNiDaqSetup="..\packaging\nidaqmx\nidaqmx_setup.exe"` is passed **unconditionally**,
   including on the documented default path where `NIDAQMX_URL` is unset and the file
   was never downloaded. The `[Files]` entry has no `skipifsourcedoesntexist` flag, so
   ISCC fails at compile time with a missing-source error.
2. `/DSourceDir="dist\NI6009Logger"` — Inno resolves relative `Source:` paths against
   the directory containing the `.iss` file, i.e. `packaging\dist\NI6009Logger`.
   PyInstaller wrote to the repo-root `dist\`. It should be `..\dist\NI6009Logger`.
   The same mistake is in `packaging/README.md`'s manual build command.

### D-4 — Relay ON time is not `pulse_seconds` — **MAJOR** (see §4 S-1)

### D-5 — Recovery tab reads a different directory than the writer writes — **MAJOR**
`session.py:116` writes recovery files to `<output file's parent>/recovery/`, exactly
as FSD §10 specifies. `main_window.py:562` and `:575` read them from
`self.cfg.logs_dir / "recovery"`, and `logs_dir` is never updated when the operator
browses to a different folder — which is the normal case, since Browse merely
*suggests* the default directory. The Recovery tab therefore shows an empty list
after most real runs, and **Copy to…** would build a source path that doesn't exist.
Not caught by tests: `test_gui_logging_run_with_recovery` asserts the file on disk,
never the list widget.

### D-6 — Ignition LEDs use hardcoded thresholds — **MAJOR**
`ignition_panel.py:208-209`:
```python
self.led_continuity.set_state("ok" if current_ma >= 0.2 else "warn")
self.led_leak.set_state("warn" if current_ma >= 5.0 else "ok")
```
These are the *default* continuity/leak values, not `cfg.ignition.continuity_min_ma` /
`leak_max_ma`. An operator who raises the leak maximum to 50 mA sees a red-flagged
"No leak current" LED at 5 mA while the core happily continues, and an operator who
*lowers* it to 1 mA sees a green LED while the core is about to inhibit. The core
remains authoritative (FSD §8.3's rule that thresholds are evaluated in the core is
honored), so this is a display-integrity defect rather than a hazard — but on a safety
panel a misleading indicator is worth fixing before first live use.

### D-7 — Settings round-trip is lossy, including safety thresholds — **MAJOR**
FSD §11 requires "all panel fields, calibration and ignition parameters, output
directory" to be restored. Two independent gaps:

- `_panel_config()` (`main_window.py:319-336`) builds a **fresh** `LoggerConfig` with
  only the current mode's `**extra`, then saves it. Starting a log run therefore
  persists `ignition=None`, discarding every ignition parameter; starting a
  calibration run discards `outfile`.
- `_load_panel_from_config()` (`:294-317`) restores only a subset even when the data
  *is* present: `ign_sense_term`, `ign_cont_spin`, `ign_leak_spin` and
  `ign_confirm_spin` are never restored. The continuity, leak and fire-confirm
  thresholds silently revert to defaults on every launch.

### D-8 — The typed-device escape hatch is unreachable — **MAJOR**
FSD §5: "the device field stays editable so a device not visible to enumeration can be
entered manually." The combo is editable (`device_picker.py:14`), but nothing connects
its text changes to `_device_present`, which is set only from `devices_changed`
(`main_window.py:339-341`) and gates Start/ARM (`:359-364`). When enumeration returns
nothing — precisely the situation this feature exists for — Start and ARM stay
disabled no matter what the operator types.

### D-9 — Live plot Y axis autoranges — **MINOR**
FSD §9 specifies "Y axis: volts (configured AI range)". `live_plot.py:144-145` calls
`enableAutoRange(x=True, y=True)`.

### D-10 — Self-test task flag — **MINOR**
FSD §3.1 says the post-install self-test checkbox is "default on"; `installer.iss`
uses `Flags: checkedonce`, which is default-on for the *first* install only.

---

## 3. Plan vs. Implementation

No `Implementation_Plan_*.md` exists in the project root or `docs/` — **section
skipped**. As a substitute, the `CHANGELOG.md` claims were checked against the code:
the shared-core extraction, GUI tabs, recovery dual-write, ignition panel, packaging
scaffolding, CI, and "30 tests" are all present and the test count is exact. The
changelog's "Pending (needs Windows hardware)" note is accurate and, given §2 D-1
through D-3, understated — the packaging path is not merely unverified but currently
non-building.

No prior `*Code_Review*.md` exists, so there are no earlier findings to re-check.

---

## 4. Edge Cases & Safety

### S-1 — Relay ON time is quantized to the AI chunk read — **MAJOR**
`session.py:177-222`. The main loop fires the relay at the top of an iteration
(`:191`), then performs a **blocking** `read_many_sample` of `cfg.chunk` samples
(`:222`) before the next iteration can evaluate `now >= fire_until` and open it
(`:214-218`). Relay ON time is therefore
`max(pulse_seconds, ceil-to-next-chunk-boundary)`.

*Failure scenario (GUI defaults):* rate = 1000 Hz, chunk = 1000 → one chunk read takes
~1 s. With `pulse_seconds` left at its 1.0 s default the relay stays closed for ~1–2 s;
set `pulse_seconds` to 0.2 s (as the tests themselves do) and the relay stays closed
for a full second — **5× the configured time** — with the ignition supply's full
current flowing. The fix is to break the chunk into shorter reads, or to move the DO
open onto a separate timer, while ignition is active.

The existing tests miss this because `_ignite_cfg` uses rate = 100, chunk = 10 (0.1 s
reads) with `pulse_seconds = 0.2`, where the quantization is invisible.

### S-2 — `closeEvent` can abandon a running session with the relay energized — **CRITICAL**
`main_window.py:585-592`:
```python
if self.worker is not None:
    self.worker.request_stop()
    if not self.worker.wait(3000):
        self.statusBar().showMessage("Forcing outputs safe…")
        self.worker.wait(2000)
gsettings.save_config(self.cfg)
super().closeEvent(event)
```
After 5 s the window closes regardless of whether the worker actually stopped. The
status message claims the outputs were forced safe; nothing in this path forces
anything — only the core's `finally` (`session.py:287-295`) does, and it hasn't run.
`cfg.read_timeout` defaults to **10 s**, so a stalled or slow DAQ read reliably
outlives the 5 s budget. The window closes, the last window closing quits the
application, and the process tears down with the DO lines in whatever state they were
left in. If the close happens during the pulse, the igniter relay stays energized with
no application left to open it.

FSD §8.3 states plainly that "closing the window during a session equals ABORT: the
worker is stopped and the core's exit path forces the DO lines LOW." That guarantee
does not hold. The event should be `ignore()`d until the worker genuinely finishes
(with a modal "stopping safely…" indication), rather than proceeding on a timeout.

### S-3 — Fire-confirm opens a second AI task on a single-AI-engine device — **MAJOR**
`session.py:197-205` creates a new `nx.Task()` with an AI channel *while* the main
`ai_task` is running and acquiring. The USB-6009 has a single analog-input timing
engine; the real NI-DAQmx driver refuses a second AI task on the same device
("resource reserved", −50103). On hardware the confirm read will almost certainly
raise, be swallowed at `:209-210` as `IGNITION ERROR: …`, and the fire-confirm check —
a documented safety feature in both FSD §8.3 and README §9 — will silently never
execute. The relay still closes and reopens correctly (`fire_until`/`fired` are set
outside the `except`, `:211-212`), so this degrades rather than endangers, but the
operator loses the confirmation they were told they had.

This is invisible to the suite because `_fake_nidaqmx.py` models no device-level
resource reservation. Worth an explicit Phase 6 hardware check, and a fake-backend
enhancement to model the constraint.

### S-4 — Fire-confirm AI range is hardcoded to ±1 V — **MAJOR**
`session.py:198-201` adds the confirm channel with `min_val=-1.0, max_val=1.0`. README
("Ignition current-sense wiring") documents that with the relay closed, 3–6 A through
the 1 Ω shunt produces **3–6 V**. The reading is clipped at ~1 V, i.e. ~1000 mA, so the
confirm number shown to the operator (`IGNITION confirm sample: … mA`) is simply
wrong, and the `fire_confirm_ma` comparison is only meaningful for thresholds below
~1000 mA. The ±1 V range is correct for the *arming* path (`:313-315`, where 0.25 mA
continuity is the signal of interest) but not here; the confirm task needs a range
derived from `fire_confirm_ma × shunt_ohms`.

### S-5 — ABORT during the pulse is not immediate — **MAJOR**
Same loop structure as S-1: `stop.is_set()` is only evaluated at the top of the
iteration (`:177`), after the blocking chunk read. Pressing ABORT while the relay is
closed does not open it until the current read returns — up to one chunk period
normally, up to `read_timeout` (10 s) if the DAQ is stalled. FSD §8.3 offers ABORT "at
any moment."

### S-6 — Leak current is only monitored during arming — **INFO**
`_arm()` inhibits on `i_ma >= leak_max_ma`, but once arming passes there is no further
leak monitoring through the stabilize window or the (potentially long) FIRE_PENDING
hold. A leak developing after arming is undetected. FSD §8.3 doesn't require continuous
monitoring, so this is an observation rather than a deviation — but it is the kind of
thing worth deciding deliberately before live use.

### S-7 — `compute_current_ma` is unsigned-blind — **INFO**
`helpers.py:93-94` has no `abs()`. With reversed sense wiring a genuine leak reads as a
large *negative* mA, passes the leak test, and fails the continuity test — so the
outcome is still an inhibit. Fail-safe by luck rather than design; an explicit
"implausible negative current" inhibit would be clearer.

### S-8 — Row timestamps are shifted forward by one chunk — **MINOR**
`session.py:231-236` takes `chunk_start = time.time()` **after** `read_many_sample`
returns, then stamps row *i* as `chunk_start + i/rate`. The samples in that buffer were
acquired *before* that instant, so every timestamp in the file leads the true
acquisition time by roughly one chunk period (1 s at GUI defaults). For correlating
log data against video or a separate DAQ during a static fire, that's a meaningful
offset. This is inherited CLI behavior locked by parity tests, so changing it is a
deliberate decision — but it should be a decision, not an accident.

### S-9 — FIRE permission can be granted from the keyboard — **MINOR**
`ignition_panel.py:79-80` drives the hold from `pressed`/`released`. A `QPushButton`
with keyboard focus emits these for the space bar, so holding **Space** for two seconds
grants fire permission without any deliberate pointer action on the FIRE button.
`setFocusPolicy(Qt.NoFocus)` on `fire_btn` would close this.

### S-10 — `_arm` reports unrelated `RuntimeError`s as a leak inhibit — **MINOR**
`session.py:355-358` catches `RuntimeError` and returns `_ARM_LEAK`, telling the
operator "Buzzer OFF. Ignition inhibited." after what may have been a read timeout or
a buffer error. Inhibiting is the right *action*; attributing it to a leak is
misleading during troubleshooting.

---

## 5. Concurrency & Platform Issues

The threading model is sound and I found no data races. Specifically:

- `_QtReporter` (`worker.py:20-51`) touches only signals; `main_window` connects them
  to slots that run on the GUI thread via Qt's automatic queued connections. The
  "widgets never call the DAQ directly" invariant of FSD §2 holds throughout.
- `SampleBlock.ai` is copied in the core before emission (`session.py:232`,
  `calibration.py:103-104`), so the plot never reads a buffer the acquisition loop is
  overwriting. This is exactly right and easy to get wrong.
- `stop` and `fire_permission` are `threading.Event`s set from the GUI thread and
  polled in the worker — correct, lock-free, no torn state.
- The 2 s device poll short-circuits while a worker exists (`main_window.py:348-349`),
  avoiding concurrent driver enumeration during acquisition.

Platform issues:

- **C-1 (MAJOR)** — DI task leak on error paths. `di_task` is created bare
  (`session.py:140-145`), not as a context manager, and only stopped/closed on the
  normal path (`:269-271`). Any exception in the acquisition loop — including the
  unplug case the FSD explicitly calls out — leaves a DAQmx task handle open until
  garbage collection. On real hardware a leaked task keeps the DI lines reserved and
  can make the *next* run fail with a resource-reserved error, turning one unplug into
  a session the operator can't restart. `calibration.py:123-126` has the same shape.
- **C-2 (MINOR)** — `closeEvent` blocks the GUI thread for up to 5 s (see S-2); the
  window is frozen and unrepainted for that period, with no visual indication beyond a
  status-bar message that can't be painted.
- **C-3 (MINOR)** — `live_plot.py:101, 119` reach into PyQtGraph internals
  (`plot.getPlotItem().legend.items = []`) instead of `legend.clear()`. This is the
  kind of thing that breaks silently on a PyQtGraph upgrade inside a frozen bundle.
- **C-4 (MINOR)** — Ring capacity is `max(rate × 60, chunk × 4)` doubles **per
  channel, twice** (values + timestamps). At the panel's maximum 48 kHz across 8
  channels that is ~368 MB of buffers. FSD §14's "memory bounded, flat over run
  length" is technically satisfied, but the bound is high enough to be worth a cap.

---

## 6. Error Handling

- **E-1 (MAJOR)** — `calibration.py:120-126`: the `finally` block references `ai_task`
  and `di_task`, but `di_task` is not bound until `:77`. Any failure during AI task
  setup — a bad channel name, the device vanishing between enumeration and start, a
  terminal-config mismatch — raises before `:77`, and the `finally` then dies with
  `UnboundLocalError: cannot access local variable 'di_task'`, **replacing** the
  original DAQ error. The operator sees a Python-internals message instead of the
  friendly DAQ text FSD §12 promises, and the real cause is lost. Initialize
  `di_task = None` before the `try`.
- **E-2 (MAJOR)** — `writers.py:74-76`: `TeeWriter.close()` calls `self.main.close()`
  first with no guard. `XLSXWriter.close()` performs the entire workbook save there
  (`:43-48`), which is exactly the operation likely to fail on a full disk, a network
  path, or a file the operator has open in Excel. When it raises, `self.recovery.close()`
  never runs — so the crash-insurance CSV is left unflushed precisely in the scenario
  it exists for. Close the recovery sink in a `finally`.
- **E-3 (MINOR)** — `XLSXWriter.close()` sets `_saved = True` only *after* a successful
  save, and `session.py` calls `writer.close()` twice (`:274` and the `finally` at
  `:285`). A failing save is therefore retried and raises a second time from the
  `finally`, masking the first exception.
- **E-4 (MINOR)** — `app.py:29-39`: `_excepthook` tells the user "The app will now
  close" but neither closes nor exits; control returns and the app keeps running in
  whatever state the exception left it.
- **E-5 (MINOR)** — `config.validate()` checks only channels, calibrate/ignite
  exclusivity, and DO line presence. Nothing rejects `rate <= 0`, `chunk <= 0`, or
  `vmin >= vmax`. The GUI spinboxes constrain these, but the CLI does not:
  `ni_usb6009_logger --channels ai0 --rate 0` reaches `1.0 / cfg.rate`
  (`session.py:232`) and dies with a raw `ZeroDivisionError`. Since `validate()` is the
  documented shared gate and FSD §4 states the 1–48 000 Hz range, the bounds belong
  there.
- **E-6 (MINOR)** — `cli.py:318-324` ignores SIGINT after the first Ctrl+C. If the run
  is wedged in a 10 s blocking read, a second Ctrl+C cannot break out.

Error handling that is done well and worth keeping: the `IgnitionSetupError` →
exit-code-3 path (`session.py:79-84`, `cli.py:334-336`), the idempotent writer close
in a `finally`, the unconditional DO-LOW outer `finally`, and `_friendly_error`'s
mapping of driver/device failures to plain-language guidance.

---

## 7. Code Quality

Structure is good overall — the Reporter indirection is the right abstraction, the
core has no Qt or console dependency, and the ignition panel is a genuinely dumb view
with all failsafes in the core, exactly as its docstring claims. Substantive issues:

- **`pytest` from the repo root fails at collection.** The unrelated
  `USB-6009 test scripts/test_ai.py` matches `test_*.py`, imports the real `nidaqmx`,
  and aborts the entire run. `pytest tests` works (30 passed). CI sidesteps this by
  naming the four test files explicitly in `ci.yml:24` — which means **any test file
  added later will silently never run in CI**. A `testpaths = ["tests"]` entry in
  `pyproject.toml` fixes both at once.
- **`release.yml` has no dependency on the `test` job.** A tag push builds and
  publishes an installer without running a single test.
- **CI lints only `core/`, `cli.py` and `_fake_nidaqmx.py`** (`ci.yml:22`), so the GUI's
  flake8 findings listed above never fail a build.
- **Version is duplicated** — `pyproject.toml:7` and `__init__.py:3` both carry
  `1.1.0`, despite the changelog designating `__version__` as the single source for
  installer versioning. These will drift.
- **The "no overwrite" behavior is confusing end-to-end.** `QFileDialog.getSaveFileName`
  asks the operator to confirm overwriting an existing file; `safe_path` then writes to
  `…_1.csv` instead. The path shown in the output box is not the path written. The
  final summary dialog does show the real path, so no data is lost — but the flow
  should either not offer overwrite confirmation or should reflect the suffixed name
  immediately.
- **`reporter._digital_count` is injected from outside** (`cli.py:314`) and consumed in
  `on_row_preview` (`:221`) without being declared in `__init__`. It works, but it's an
  undeclared part of the class contract.
- **Duplicated chunk formula** — `max(1, int(rate_hw * 0.2))` appears in
  `calibration.py:64` and again in `main_window.py:460`. If one changes, the plot's ring
  sizing silently desynchronizes from the actual chunk.
- **`_poll_devices` contains a dead sub-condition** — `len(names) != len(devices)`
  (`main_window.py:353`) is always False, since `names` is derived from `devices` one
  line above. A device count change from 2 → 1 therefore triggers no rescan. The
  function also enumerates devices twice per tick (once directly, once inside
  `rescan()`).
- **`IgnitionPanel.reset()` wipes the inhibit message.** After an inhibit, the worker
  finishes and `_worker_gone` → `reset()` puts the panel back to "Idle" and re-enables
  ARM, erasing the "INHIBITED by safety failsafe" text FSD §8.3 step 3a asks for. The
  status bar and the modal dialog still inform the operator, so this is cosmetic, but
  the most safety-relevant message on the panel is the one that disappears fastest.
- **Dead code** — `LivePlot.clear()` is never called.
- **`arm_confirmed = Signal()`** is declared mid-class at `ignition_panel.py:128`,
  between methods. Valid, but easy to miss when reading the widget's interface.

Test-quality notes: the suite is better than most at this stage — it asserts on the
actual DO write *sequences* (`do_write_sequences()`), which is the right invariant for
this domain, and it covers abort, leak inhibit, and the fire-permission gate. Gaps
worth closing: nothing asserts FIRE is disabled *during* ARMING (only after an
inhibit); `test_gui_ignition_full_flow` drives `_hold_tick()` manually so the real 2 s
hold duration is never verified; no test covers the Recovery tab listing (which is why
D-5 survived); and the fake backend models neither AI range clipping nor device
resource reservation, hiding S-3 and S-4.

---

## 8. Summary

| Category | Critical | Major | Minor | Info |
|----------|----------|-------|-------|------|
| Spec conformance | 0 | 4 (D-5…D-8) | 2 (D-9, D-10) | 0 |
| Plan conformance | — | — | — | — (no plan document) |
| Correctness | 0 | 3 (S-1, E-1, E-2) | 3 (S-8, dead condition, chunk duplication) | 0 |
| Safety | 1 (S-2) | 3 (S-3, S-4, S-5) | 3 (S-9, S-10, inhibit message) | 2 (S-6, S-7) |
| Concurrency & platform | 0 | 1 (C-1) | 3 (C-2, C-3, C-4) | 0 |
| Error handling | 0 | 0 | 4 (E-3…E-6) | 0 |
| Code quality | 0 | 0 | 6 | 1 (dead code) |
| Packaging & CI | 3 (D-1, D-2, D-3) | 0 | 4 | 0 |
| **Total** | **4** | **11** | **25** | **3** |

---

## 9. Recommendation

**Do not tag `v1.2.0`, and do not run a live igniter, until the Critical items are
fixed.** Phase 7 (packaging/CI) cannot be considered complete: as written, the
installer does not compile, and if it did, the driver component would never install.

**Must fix before the Phase 6 hardware session:**

1. D-1 — parenthesize the `CurStepChanged` guard in `installer.iss`.
2. D-2 — replace the runtime `{#NiDaqSetup}` existence check with a compile-time
   `#if FileExists(...)` (and add `skipifsourcedoesntexist`).
3. D-3 — make `release.yml` pass `/DNiDaqSetup` only when the download happened, and
   correct `/DSourceDir` to `..\dist\NI6009Logger`; fix the same path in
   `packaging/README.md`.
4. S-2 — make `closeEvent` refuse to close until the worker has actually finished,
   rather than abandoning it after 5 s.
5. S-1 / S-5 — while ignition is active, bound the AI read so the relay-open check and
   `stop` are evaluated on a timescale much shorter than `pulse_seconds` (a
   sub-chunk read loop, or a dedicated DO timer thread).

**Should fix before first live use (safety-visible, low effort):**

6. S-4 — derive the fire-confirm AI range from `fire_confirm_ma × shunt_ohms`.
7. D-6 — feed the configured thresholds into the panel LEDs.
8. E-1 — initialize `di_task = None` in `calibration.py`.
9. E-2 — close the recovery sink in a `finally` inside `TeeWriter.close()`.
10. C-1 — wrap the DI task so it closes on every exit path.
11. S-9 — `fire_btn.setFocusPolicy(Qt.NoFocus)`.

**Verify on hardware during Phase 6 (cannot be settled here):**

12. S-3 — whether a second AI task for fire-confirm is accepted while the main
    acquisition task runs. If it is refused, fire-confirm needs to be restructured to
    read the sense channel from the main task instead. Consider extending
    `_fake_nidaqmx.py` to model the single-AI-engine constraint so this is caught in CI.

**Worth doing alongside:** D-7 (persistence round-trip, including the safety
thresholds), D-8 (typed-device gating), D-5 (Recovery tab directory), `testpaths` in
`pyproject.toml` plus a `needs: test` on the release job, and the remaining minors as
convenient.

The foundations here are solid — the core/front-end split, the DO-safe ordering, and
the DO-sequence assertions in the test suite are all the right decisions, and they are
what make the above a fixable list rather than a rewrite. Once items 1–5 are addressed,
this is a straightforward re-review.
