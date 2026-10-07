# NI USB-6009 Logger — User Manual

**Software version:** 1.1.0 · **Platform:** Windows 10/11 (64-bit) · **Language:** English
(Nederlandse versie: [USER-MANUAL.nl.md](USER-MANUAL.nl.md))

---

## Contents

1. [What this software does](#1-what-this-software-does)
2. [What you need](#2-what-you-need)
3. [Safety first](#3-safety-first)
4. [Connecting the hardware](#4-connecting-the-hardware)
5. [Installing the software](#5-installing-the-software)
6. [Starting the program for the first time](#6-starting-the-program-for-the-first-time)
7. [The main window](#7-the-main-window)
8. [Settings that apply to every mode](#8-settings-that-apply-to-every-mode)
9. [Logging data (Log tab)](#9-logging-data-log-tab)
10. [Calibrating (Calibrate tab)](#10-calibrating-calibrate-tab)
11. [Igniting (Ignite tab)](#11-igniting-ignite-tab)
12. [The live plot](#12-the-live-plot)
13. [Output files and the recovery copy](#13-output-files-and-the-recovery-copy)
14. [Using the command-line version](#14-using-the-command-line-version)
15. [Troubleshooting](#15-troubleshooting)
16. [Uninstalling](#16-uninstalling)
17. [Technical reference and limits](#17-technical-reference-and-limits)

---

## 1. What this software does

The NI USB-6009 Logger turns a National Instruments **USB-6009** data-acquisition
device (the "DAQ") into a data logger for a test stand. It can:

- **Log** analog voltages (AI) and, optionally, digital inputs (DI) to a **CSV** or
  **Excel (.xlsx)** file, with a live graph while it runs.
- **Calibrate**: show a steady, averaged number per channel on screen, without
  writing any file — for zeroing and checking sensors before a test.
- **Ignite**: run a safe, step-by-step ignition sequence (buzzer warning, igniter
  continuity and leak checks, hold-to-fire, current confirmation) while logging the
  whole event.
- **Protect your data**: every logging or ignition run is also written to a
  *recovery copy* on disk, so a crash, power loss or unplugged cable does not lose
  what was already measured.

There are two programs sharing the same engine:

| Program | For | Start from |
|---|---|---|
| **NI USB-6009 Logger** (GUI) | Normal operation by the operator | Start menu / desktop icon |
| `ni_usb6009_logger` (command line) | Scripting, advanced users | A terminal — see [chapter 14](#14-using-the-command-line-version) |

This manual concentrates on the graphical program.

## 2. What you need

| Item | Notes |
|---|---|
| NI **USB-6009** | With its USB cable. |
| A Windows PC | Windows 10 or 11, 64-bit, with a free USB port. |
| **NI-DAQmx driver** | Free from NI. The installer can include it (see chapter 5). |
| Installer | `NI6009Logger_Setup_1.1.0.exe` (or newer). |
| Sensors / signals | Wired to the USB-6009 as described in chapter 4. |
| *For ignition only:* relay board, buzzer, 1 Ω shunt resistor, 47 kΩ resistor, ignition power supply, fuse | See chapter 11 and the wiring diagram in 4.4. |

> **Disk space:** the NI-DAQmx driver alone is several hundred MB. The program itself is small.

## 3. Safety first

Read this before wiring anything, especially if you will use the ignition function.

- **The USB-6009 must never carry igniter current.** It only *measures* the small
  voltage across the shunt resistor and *switches a relay* through a driver.
- Always drive a relay coil through a **transistor or driver chip (e.g. ULN2803)**,
  never straight from a DAQ output pin. Put a **flyback diode** across the coil.
- **Fuse** the ignition power supply appropriately.
- Keep the ignition wiring physically **separate** from the DAQ wiring where possible,
  or use isolation (opto-coupler or an isolated current-sense amplifier).
- **Do a dry run first**, with a dummy load (e.g. a resistor or a lamp) instead of a
  real igniter, and with the igniter **disconnected from the motor**.
- Nobody may be near the test article while the buzzer sounds or while FIRE is
  possible.
- If anything looks wrong: press **ABORT**, or simply close the program — both force
  the output lines LOW (relay off, buzzer off).

## 4. Connecting the hardware

### 4.1 The USB-6009 terminals

The device has 32 screw terminals (two rows of 16, behind removable covers). Numbers
and names are printed on the device label.

| Terminal | Signal | Terminal | Signal |
|---|---|---|---|
| 1 | GND | 17 | P0.0 (digital) |
| 2 | AI 0 (+) | 18 | P0.1 |
| 3 | AI 4 (AI 0 − in differential) | 19 | P0.2 |
| 4 | GND | 20 | P0.3 |
| 5 | AI 1 (+) | 21 | P0.4 |
| 6 | AI 5 (AI 1 − in differential) | 22 | P0.5 |
| 7 | GND | 23 | P0.6 |
| 8 | AI 2 (+) | 24 | P0.7 |
| 9 | AI 6 (AI 2 − in differential) | 25 | P1.0 |
| 10 | GND | 26 | P1.1 |
| 11 | AI 3 (+) | 27 | P1.2 |
| 12 | AI 7 (AI 3 − in differential) | 28 | P1.3 |
| 13 | GND | 29 | PFI 0 |
| 14 | AO 0 | 30 | +2.5 V |
| 15 | AO 1 | 31 | +5 V |
| 16 | GND | 32 | GND |

(Always check against the label on your own device.) This software uses the **analog
inputs** (AI 0–7), the **digital lines** (port 0: lines 0–7, port 1: lines 0–3). The
analog outputs are not used.

Naming used in the program:

| On the device | In the program |
|---|---|
| AI 0 … AI 7 | `ai0` … `ai7` |
| P0.0 … P0.7 | `port0/line0` … `port0/line7` |
| P1.0 … P1.3 | `port1/line0` … `port1/line3` |

### 4.2 Connect the device to the PC

1. **Install the software first** (chapter 5) so the driver is ready, then plug in the
   USB-6009. (Plugging it in first also works; Windows just installs the driver
   afterwards.)
2. Connect the USB cable directly to a PC USB port — avoid unpowered hubs and long
   extension cables.
3. The device's LED comes on/blinks when it is recognised. Wait a few seconds.
4. The program recognises the device by itself, normally as **Dev1**. If you ever need
   to check or rename it, use *NI MAX* (Measurement & Automation Explorer, installed
   with the driver) → *Devices and Interfaces*.

### 4.3 Wiring the analog inputs

Choose one of two methods per measurement (the same setting applies to all logged
channels — it is the **Term config** field):

**RSE — single-ended (default).** Each signal needs two wires: signal → `AI n`, and
signal ground → any `GND` terminal. Works on all eight channels (ai0–ai7). Use for
sensors that share a ground with the DAQ; simplest wiring.

**DIFF — differential.** Each signal uses a *pair* of terminals: `+` to `AI n`, `−` to
the partner terminal (see the table: ai0 uses terminals 2 and 3, ai1 uses 5 and 6,
ai2 uses 8 and 9, ai3 uses 11 and 12). Better noise rejection for small or floating
signals. **Only ai0–ai3** are available in DIFF mode, because ai4–ai7 are the partner
pins. Don't use an ai4–ai7 channel at the same time as the DIFF channel that uses its
terminal.

Input range is ±10 V (maximum). **Never apply more than ±10 V** (relative to GND)
or the input may be damaged. For signals bigger than that, use a voltage divider.

> The USB-6009 has **no** "NRSE" mode, even though the command line accepts the word.
> Use RSE or DIFF.

### 4.4 Wiring digital inputs (optional)

Connect a digital signal (0 V = low, up to 5 V = high) between `P0.x` (or `P1.x`) and
`GND`. Digital inputs are **static**: the program reads them once per data block
(chunk) and repeats that value on all rows of the block. Lower the *Chunk size* to
sample them more often (see chapter 8).

### 4.5 Wiring the ignition circuit (only for the Ignite function)

This section is the reference wiring used by the software's default settings.

**Parts**

- **Relay** (via a driver/transistor such as a ULN2803 or MOSFET, with a flyback diode)
  to switch the igniter. The relay *contacts* carry the ignition current.
- **Buzzer** (driven from a DAQ digital output through a transistor if it needs more
  than the DAQ's few mA).
- **Shunt resistor**: 1.0 Ω, at least 2 W, low inductance, in the igniter's ground path.
- **Bias resistor**: 47 kΩ, from ignition +V to the igniter/shunt junction. It gives a
  tiny test current (~0.25 mA at 12 V) used to check that the igniter is connected.

**Connections**

```
 Ignition +V ──► Relay contact (NO) ──► Igniter (+)
                                         Igniter (−) ──┬──► 1 Ω shunt ──► Ignition GND
 Ignition +V ──► 47 kΩ ─────────────────────────────────┤ (junction)
                                                        └──► DAQ  AI+ (default ai2)
 DAQ GND (AI GND) ─────────────────────────────────────────► Ignition GND

 DAQ port1/line0 ──► relay driver (relay coil)     (default "igniter relay" line)
 DAQ port1/line1 ──► buzzer driver                 (default "buzzer" line)
```

**How the checks work**

| Relay | Current flowing | Voltage across 1 Ω | Used for |
|---|---|---|---|
| Open | only the bias current (~0.25 mA at 12 V) | ~0.25 mV | **Continuity** check — igniter is connected |
| Closed | full ignition current (3–6 A typical) | 3–6 V | **Fire confirmation** |

The software calculates current = measured voltage ÷ shunt resistance, and compares
it to three limits (set on the Ignite tab, see chapter 11).

**Mandatory:** include the current-sense channel (for example `ai2`) in the list of
*AI channels* on the left side of the window. See chapter 11.

> With the example wiring above, set **Term config** and **Sense term config** to
> **RSE**. If you wire the shunt differentially, use DIFF and a channel in ai0–ai3.

### 4.6 Checklist before powering up

- [ ] Every signal wire is on the intended terminal, and no wire touches another.
- [ ] No input exceeds ±10 V.
- [ ] DAQ GND and ignition GND are connected as in the diagram.
- [ ] The ignition supply is **off** (and fused) while you set things up.
- [ ] The igniter is a dummy load / not installed in a motor for the first test.

## 5. Installing the software

### 5.1 Run the installer

1. Double-click **`NI6009Logger_Setup_<version>.exe`**.
2. If Windows shows **"Windows protected your PC"** (SmartScreen), click **More info**
   and then **Run anyway**. This message appears because the installer is not yet
   code-signed; it is expected.
3. Allow the administrator prompt (the installer needs administrator rights).
4. Accept the licence (MIT) and click **Next**.
5. Choose the install folder (the default `C:\Program Files\NI USB-6009 Logger` is fine).
6. **Components** (if shown):
   - *NI USB-6009 Logger application* — always installed.
   - *NI-DAQmx driver runtime* — keep it **ticked** if you have not installed the NI
     driver on this PC. It installs by itself without questions and can take several
     minutes.
7. **Additional tasks:**
   - *Create a desktop shortcut* — optional.
   - *Test the installation now* — leave **ticked**.
8. Click **Install**, wait, then **Finish**.

### 5.2 Read the installation test

If you left the test ticked, a box will report one of three results:

| Message | Meaning / what to do |
|---|---|
| **Driver OK and USB-6009 detected — everything works.** | Done. |
| **Driver OK. No DAQ device found yet.** | Fine if the device isn't plugged in. Connect the USB-6009; the program finds it by itself. |
| **The NI-DAQmx driver is not working yet.** | Reboot the PC once, then start the program again. If it still fails, install NI-DAQmx from ni.com (see 5.3). |

### 5.3 If the NI-DAQmx driver is missing

If your installer didn't include the driver, the program tells you at start-up and
offers an **Open download page** button. Download and install **NI-DAQmx** from
ni.com (search "NI-DAQmx download"), restart the PC if asked, then start the program
again.

### 5.4 Installing the Python version (advanced users only)

Not needed if you use the installer. For the command-line tool or development, with
Python 3.10+ and the NI-DAQmx driver already installed:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -e .[excel]        # command-line tool + Excel output
pip install -e .[gui,excel]    # also the graphical program (ni_usb6009_gui)
```

## 6. Starting the program for the first time

1. Plug in the USB-6009.
2. Start **NI USB-6009 Logger** from the Start menu or the desktop icon.
3. The window title shows the version. In the status bar you should read
   **"DAQ detected: Dev1 (USB-6009)"**.

If instead you see:

| Status bar | Meaning |
|---|---|
| *No DAQ detected — waiting for device…* | The device isn't connected or isn't recognised yet. Check the cable; the program re-scans every 2 seconds, or press **Refresh**. |
| *NI configuration service not running…* | A Windows service of NI is stopped. See [troubleshooting](#15-troubleshooting). |

Your settings are remembered between sessions, so the second start looks like how you
left it.

## 7. The main window

```
┌───────────────────┬─ Output file: [path………………………] [Browse…] ───────────────┐
│ SETTINGS PANEL    │ ┌ Log │ Calibrate │ Ignite │ Recovery ───────────────────┐ │
│  DAQ device [ ▼ ] │ │ (content of the selected tab)                          │ │
│  AI channels      │ │                                                         │ │
│  DI lines         │ │            live plot / readouts / buttons               │ │
│  Sample rate      │ │                                                         │ │
│  Chunk size       │ └─────────────────────────────────────────────────────────┘ │
│  Term config      │                                                             │
│  AI range         │                                                             │
│  Duration         │                                                             │
└───────────────────┴──────────────────────────  status bar ─────────────────────┘
```

- **Left: settings panel** — settings that apply to every mode.
- **Top right: Output file** — where the data is saved; shared by *Log* and *Ignite*.
- **Tabs:** *Log*, *Calibrate*, *Ignite*, *Recovery*.
- **Status bar** (bottom): device status, then during a run the number of samples,
  elapsed time and data rate.
- A **log pane** repeats the program's messages.

## 8. Settings that apply to every mode

| Field | What to enter | Default |
|---|---|---|
| **DAQ device** | Choose from the list. It is filled in automatically. You can type a name if the device isn't listed. **Refresh** rescans. | `Dev1` |
| **AI channels** | Analog channels to measure, comma-separated: `ai0` or `ai0,ai1,ai2`. At least one is required. | `ai0` |
| **DI lines** | Optional digital inputs. `port0/line0:7` (a whole range) or `port0/line0,port0/line3`. Leave empty for none. Only `port0/line0-7` and `port1/line0-3` exist. A name like `D0` is refused. | empty |
| **Sample rate** | Samples per second **per channel**, 1–48 000 Hz. | 1000 Hz |
| **Chunk size** | Samples read from the device in one go. Also how often the digital inputs are read: once per chunk. | 1000 |
| **Term config** | `RSE` (single-ended) or `DIFF` (differential). See 4.3. | RSE |
| **AI range** | Expected minimum and maximum voltage, −10 V … +10 V. Also sets the plot's vertical axis. | −10 to +10 V |
| **Duration** | Run time in seconds. `0` shows "run until Stop". | run until Stop |

**Important limit — total speed.** The USB-6009 can sample at most **48 000 samples
per second *in total***, shared by all channels. So the maximum sample rate is
48 000 ÷ number of channels (4 channels → 12 000 Hz; 8 channels → 6 000 Hz). The
program checks this before starting and tells you the maximum.

**Digital sampling speed.** Digital inputs are read once per chunk. At 1000 Hz with a
chunk of 1000 you get a digital reading once per second; with a chunk of 100, ten
times per second. Smaller chunks make the program do more reads, but there is no
other cost.

All settings are saved when you start a run and when you close the program.

## 9. Logging data (Log tab)

### 9.1 Steps

1. Fill in the settings panel (chapter 8).
2. Click **Browse…** next to *Output file* and choose where to save. The suggested
   place is `Documents\NI6009 Logs\ni_<device>_<date>_<time>.csv`. Choose **CSV** or
   **Excel (.xlsx)** with the file type, or by the extension you type.
3. **Start** is enabled only once an output file is chosen and a device is available.
   Click **Start**.
4. Watch the live plot (chapter 12) and the status bar.
5. The run ends when the *Duration* has passed, or when you click **Stop**.
6. A summary box appears with an **Open folder** button that takes you to your files.

### 9.2 Existing files are never overwritten

If the name you chose already exists, `_1`, `_2`, … is added to the new file name. The
name shown in the *Output file* box after you choose is the exact name that will be
written.

### 9.3 What is in the file

One row per sample instant, with these columns:

| Column | Meaning |
|---|---|
| `timestamp_iso` | Date and time when the sample was **acquired** (not when it was read from the device). |
| `sample_index` | Counter of the sample, starting at 0. |
| One column per AI channel | Voltage in volts (`ai0`, `ai1`, …). |
| One column per DI line | 0 or 1 (`port0/line0`, …). Same value repeated within a chunk. |

**CSV** opens in Excel or any text editor. **XLSX** is a native Excel workbook; note
that an XLSX file only reaches the disk when the run *ends* (the always-flushed
[recovery copy](#13-output-files-and-the-recovery-copy) protects you meanwhile).

## 10. Calibrating (Calibrate tab)

Use this to look at stable, averaged values — for instance to zero a load cell or
check a sensor — **without** saving anything. No output file is needed.

Settings on the tab:

| Field | Meaning | Default |
|---|---|---|
| **Moving-average window** | Seconds of data averaged for each shown value. `0` disables averaging. | 5 s |
| **Screen output rate** | How many times per second the readout refreshes. | 1 Hz |
| **Internal sample rate** | How fast the hardware samples to feed the average. | 100 Hz |

1. Set channels and terminal config in the settings panel.
2. Click **Start calibration**.
3. The large readout shows the moving average for each channel; the plot shows the raw
   signals.
4. Click **Stop** when finished.

The average needs one full window to settle: with a 5 s window, wait about 5 s after
a change before reading the value.

## 11. Igniting (Ignite tab)

> ⚠ **Safety-critical function.** Read chapters 3 and 4.5 first. Do a complete dry run
> with a dummy load and **without** an igniter in the motor before real use.

### 11.1 Settings

| Field | Meaning | Default |
|---|---|---|
| **Buzzer DO line** | Digital output driving the buzzer. | `port1/line1` |
| **Igniter relay DO line** | Digital output driving the relay. | `port1/line0` |
| **Current-sense AI** | Analog input measuring the voltage across the shunt. | `ai2` |
| **Sense term config** | RSE or DIFF for that channel (must match your wiring). | RSE |
| **Shunt resistance** | Value of your shunt, in ohms. | 1.0 Ω |
| **Continuity minimum** | Minimum bias current that proves the igniter is connected. | 0.2 mA |
| **Leak maximum** | If more current than this flows *before* firing, the system is blocked. | 5 mA |
| **Fire-confirm minimum** | Current that must be seen *during* the pulse to confirm ignition. | 300 mA |
| **Buzzer warning time** | How long the warning buzzer sounds before logging starts. | 15 s |
| **Stabilize time** | Time between logging start and FIRE becoming available. | 1 s |
| **Relay pulse time** | How long the relay stays on. | 1 s |

Also needed:

- An **output file** (ignition always logs).
- The **current-sense channel in the "AI channels" list** (e.g. `ai0,ai2`). The
  USB-6009 can run only one analog acquisition at a time, so the confirmation current
  is read from the same running acquisition. If you leave it out the pulse still
  happens, but the confirmation reading may be reported as an error.
- Buzzer and relay lines must be real output lines (`port0/line0-7` or `port1/line0-3`)
  and different from each other.

### 11.2 The safety panel

Four LEDs: **DO lines LOW**, **Continuity**, **No leak current**, **Igniter relay**;
a status line (with the live current in mA while arming); a bar showing how long
you have held FIRE; and the buttons **ARM**, **FIRE**, **ABORT**.

### 11.3 The sequence, step by step

| Step | What you do | What the system does |
|---|---|---|
| **1. ARM** | Click **ARM** and confirm the dialog ("buzzer will sound… relay stays OFF"). | Starts the session. Forces both output lines LOW first. |
| **2. Arming** | Wait (you can ABORT any time). | The **buzzer sounds** for the warning time while the current is measured and shown live. |
| **3. Check** | — | **Pass:** continuity seen and no leak → continues. **Fail:** buzzer off and the message *"INHIBITED by safety failsafe"* with the reason (leak current too high, or no continuity). FIRE is **never offered** and the relay is never energised. |
| **4. Logging** | Wait. | Logging starts. After the stabilize time **FIRE is enabled**. |
| **5. FIRE** | **Press and hold FIRE for 2 seconds** (the bar fills; letting go early cancels). | The relay is switched on for the pulse time, the current is checked against *Fire-confirm minimum*, then the relay is switched off. |
| **6. ABORT** | Click **ABORT** at any moment. | Stops everything; output lines go LOW. |

Rules built into the system:

- FIRE is never available before the system is ready, and is disabled again after the
  pulse, after an inhibit, or when the session ends.
- The current limits are checked by the program core, not by the buttons — the same
  protection as the command-line version.
- If the current during the pulse stays below *Fire-confirm minimum*, a warning
  asks you to check wiring, supply and igniter. The relay still finishes its pulse
  and switches off.
- A strongly **negative** current (shunt wired backwards) blocks arming with an
  explicit message.
- **Closing the window = ABORT.** A "stopping safely" box stays until the output lines
  are confirmed LOW, then the program closes.
- Unplugging the USB cable during a run stops the session; the outputs go LOW and the
  data written so far is kept.

### 11.4 Suggested dry run

1. Wire everything with a dummy load (e.g. a suitable resistor or lamp) instead of an
   igniter, or no ignition supply at all, and the igniter not in the motor.
2. Set a short warning time (e.g. 5 s) for the test.
3. ARM → confirm → check the LEDs: continuity lights up, leak LED stays OK.
4. Disconnect the dummy load and ARM again → expect *INHIBITED (no continuity)*.
5. Reconnect, ARM, wait for FIRE, hold it → hear/see the relay click for 1 s, check
   the logged current.
6. Press ABORT during another arming → confirm everything goes quiet.

## 12. The live plot

- One coloured line per AI channel with a legend; X axis = seconds since the start of
  the run, Y axis = volts (your *AI range*).
- It shows roughly the last 60 seconds; memory use stays constant however long you
  run. The **file** contains *all* data.
- **view:** drop-down at the top right: **follow live** (moves with new data) or
  **pause view** (freezes the picture so you can zoom and pan; the recording
  continues).
- Zoom with the mouse wheel; drag to pan (while paused).

## 13. Output files and the recovery copy

### 13.1 Recovery copy

For every logging or ignition run the program writes a second, parallel file:

```
<your output folder>\recovery\<your file name>_recovery.csv
```

- It is always a CSV, saved to disk after every chunk (an XLSX only reaches the disk
  at the end).
- When the run finishes normally it is renamed to `…_recovery_OK.csv`.
- After a crash, an unplugged cable, an abort or any error, there is **no** `_OK`
  in the name — the partial data is safe and ready to be recovered.

### 13.2 The Recovery tab

Lists the recovery files (newest first) with their status (**OK** or
**INTERRUPTED**) and size, from the current output folder's `recovery` subfolder and
from the default logs folder. It refreshes at start-up, when you open the tab and
after every run.

- **Refresh** — rescan.
- **Copy to…** — copy the selected file to a place you choose. If copying fails you
  get a message with the reason.

### 13.3 Where is everything?

| What | Where |
|---|---|
| Default data folder | `Documents\NI6009 Logs` |
| Recovery copies | `recovery\` subfolder next to your output file |
| Your settings | Windows registry `HKCU\Software\steeman.be\NI USB-6009 Logger` (managed by the program) |

## 14. Using the command-line version

For scripting, open **PowerShell** (with the Python install active, chapter 5.4) and
run `ni_usb6009_logger`. A channel list is the only required option.

```powershell
ni_usb6009_logger --help
```

### 14.1 Examples

```powershell
# Log ai0 at 1000 Hz, auto-named file under .\logs, print first 10 rows
ni_usb6009_logger --device Dev1 --channels ai0 --rate 1000 --term RSE --print-first 10

# Two analog + four digital lines, custom CSV
ni_usb6009_logger --device Dev1 --channels ai0,ai1 --digital port0/line0:3 `
  --rate 100 --outfile .\logs\run.csv

# Excel output, 30 seconds, progress bar
ni_usb6009_logger --device Dev1 --channels ai0,ai1 --rate 500 `
  --outfile .\logs\run.xlsx --duration 30 --progress bar

# Differential
ni_usb6009_logger --device Dev1 --channels ai0,ai1 --rate 1000 --term DIFF

# Calibration (screen only, 5 s moving average)
ni_usb6009_logger --device Dev1 --channels ai0,ai1 --calibrate --calib-window 5 `
  --calib-sample-rate 100 --rate 1

# Ignition with buzzer, relay and current-sense failsafe
ni_usb6009_logger --device Dev1 --channels ai0,ai2 --rate 1000 --term RSE `
  --ignite --buzzer-line port1/line1 --igniter-line port1/line0 `
  --igniter-sense-ai ai2 --sense-term RSE --shunt-ohms 1.0 `
  --continuity-min-ma 0.2 --leak-max-ma 5 --fire-confirm-ma 300
```

(In `cmd.exe`, use `^` instead of the backtick for line continuation.)

### 14.2 Options

| Option | Meaning | Default |
|---|---|---|
| `--device` | Device name (as in NI MAX) | `Dev1` |
| `--channels` | AI channels, e.g. `ai0,ai1` (required) | — |
| `--digital` | DI lines, e.g. `port0/line0:7` | none |
| `--rate` | Sample rate (Hz) | 1000 (1 in calibration) |
| `--chunk` | Samples per read | 1000 |
| `--vmin`, `--vmax` | Expected voltage range | −10, 10 |
| `--term` | `RSE` or `DIFF` (`NRSE` is accepted but refused by this device) | RSE |
| `--outfile` | Output path; auto-named in `.\logs` if omitted | — |
| `--format` | `csv` or `xlsx` (otherwise from the extension) | csv |
| `--duration` | Seconds; omit to run until Ctrl+C | — |
| `--progress` | `auto`, `none`, `counter`, `bar` | auto |
| `--update-interval` | Seconds between progress updates | 0.5 |
| `--print-first` | Print the first N rows | 0 |
| `--debug` | Extra diagnostic output | off |
| `--calibrate` | Calibration mode | off |
| `--calib-window` | Moving-average window (s, 0 = off) | 5 |
| `--calib-show-raw` | Also print raw values | off |
| `--calib-sample-rate` | Internal rate in calibration (Hz) | 100 |
| `--ignite` | Enable ignition sequence | off |
| `--buzzer-line`, `--igniter-line` | Output lines (required with `--ignite`) | — |
| `--arm-seconds` | Buzzer warning time | 15 |
| `--stabilize-seconds` | Wait after logging starts | 1 |
| `--pulse-seconds` | Relay on-time | 1 |
| `--igniter-sense-ai` | Channel measuring the shunt, e.g. `ai2` | — |
| `--shunt-ohms` | Shunt value | 1.0 |
| `--continuity-min-ma` / `--leak-max-ma` / `--fire-confirm-ma` | Current limits | 0.2 / 5 / 300 |
| `--sense-rate` | Sense sample rate (Hz) | 100 |
| `--sense-term` | Terminal config for the sense channel | DIFF |

Note: the command-line default for `--sense-term` is **DIFF**, while the GUI shows RSE;
set it explicitly to match your wiring.

### 14.3 Stopping, exit codes

- **Ctrl+C** once = clean stop (current chunk finishes, files close, outputs LOW).
  A **second** Ctrl+C aborts immediately (exit code 130) if the device is stuck.
- Exit code **2** = a setting was refused before starting (with an explanation).

## 15. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Program says the **NI-DAQmx driver is missing** and exits | Click *Open download page*, install NI-DAQmx, restart the PC, start the program again. |
| **"No DAQ detected — waiting for device…"** | Check the USB cable and port; try another port. Press **Refresh**. Make sure the device appears in NI MAX. You can also type `Dev1` in the device field. |
| **"NI configuration service not running"** or an error mentioning *MIG* | NI background services are stopped. Reboot the PC. Otherwise, in an **administrator** PowerShell: `Get-Service *NI* \| Sort-Object Status, Name` then `Start-Service -Name "nidevldu","mxssvr","nimDNSResponder"`; or restart the *NI Configuration Manager* service in Windows *Services*. |
| **Start / ARM is greyed out** | No device available, or (for Log/Ignite) no output file chosen yet. |
| **"Cannot start" dialog** | A setting is invalid; the message names the field. Typical: rate × channels above 48 000; DIFF on ai4–ai7; wrong digital line name; AI minimum above maximum; empty channel list. |
| Digital line **`D0` refused** | Use the full name: `port0/line0`. |
| **Run stopped, "check USB cable"** dialog | The device disconnected. Data written so far is in the output *and* recovery files named in the dialog. Re-plug and start a new run. |
| **Arming says "INHIBITED — no continuity"** | Igniter not connected, bias resistor missing, sense wire off, or *Continuity minimum* set too high. |
| **"INHIBITED — leak current"** | Current flows before firing: short, wet/dirty connection, wrong wiring, relay stuck. Fix before retrying; do not raise the limit just to get past it. |
| Reversed-current message | The shunt or the AI wires are swapped. |
| **Fire-confirm warning** | Current during the pulse stayed below the limit: check supply voltage, fuse, igniter, shunt value and wiring. |
| Values look noisy or drift | Use DIFF wiring, shorter/shielded wires, a common ground; use Calibrate with a longer averaging window. |
| Excel file is missing after a crash | XLSX is only written at the end. Use the **Recovery** tab and copy the `…_recovery.csv`. |
| Windows SmartScreen warning at install | Click *More info* → *Run anyway*. |

## 16. Uninstalling

*Windows Settings → Apps → NI USB-6009 Logger → Uninstall*, or *Start menu → NI USB-6009
Logger → Uninstall NI USB-6009 Logger*. Your data files in `Documents\NI6009 Logs` are
**not** deleted. The NI-DAQmx driver is a separate product and stays installed (remove
it separately from *Apps* if you no longer need it).

## 17. Technical reference and limits

| Item | Value |
|---|---|
| Analog inputs | 8 single-ended (RSE) or 4 differential (DIFF, ai0–ai3), ±10 V max |
| Maximum sampling | 48 000 S/s total, shared by all channels |
| Digital lines | port0/line0–7, port1/line0–3; static (not clocked) |
| Terminal modes | RSE, DIFF only (no NRSE) |
| Digital snapshot | Once per chunk |
| Timestamps | Back-dated to when each sample was acquired |
| File formats | CSV, XLSX |
| Overwrite protection | Always; `_1`, `_2`… suffix |
| Recovery | CSV, flushed every chunk; `_OK` on clean finish |
| Live plot memory | Bounded; ~60 s window |
| Ignition timing | The AI stream is read in ~20 ms sub-blocks so the relay opens on time and ABORT acts within a sub-block |
| Operating system | Windows 10/11 64-bit |
| Not bundled | NI driver files (installed separately by NI-DAQmx) |

**Testing without hardware:** setting the environment variable `NI_USB6009_FAKE=1`
starts the program with a built-in fake device (no driver needed); useful for
training and demos. It is more forgiving than the real device. For a more realistic
test, create a *simulated USB-6009* in NI MAX (*Devices and Interfaces → Create New →
NI-DAQmx Simulated Device*).

**Self-test:** `NI6009Logger.exe --selftest` (from the install folder) prints one line
and returns 0 (driver and device OK), 1 (driver OK, no device) or 2 (driver missing or
NI service not running).

---

© 2025 David Steeman · MIT licence · [steeman.be](https://steeman.be)
