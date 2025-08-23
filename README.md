# NI USB-6009 Logger (`ni_usb6009_logger`)

A command-line data logger for the **NI USB-6009 DAQ** device.  
Logs **analog inputs (AI)** and optional **digital inputs (DI)** to **CSV** or **Excel (.xlsx)** files.  
Includes live progress display, safe file naming (no overwrite), and optional console preview of captured rows.

---

## ✨ Features
- **Analog inputs (AI)**, hardware-timed at up to 48 kS/s aggregate.
- **Digital inputs (DI)**, sampled once per AI chunk (static snapshot).
- Logs to **CSV** or **Excel (.xlsx)** with headers.
- **Safe filenames**: auto-generated timestamped names, never overwrite.
- **Progress feedback**: live counter or progress bar.
- **Preview option**: print the first N rows to the console.
- Cross-platform Python (tested on **Windows 10/11** with NI-DAQmx).

---

## 📦 Dependencies

### Required
- **NI-DAQmx driver/runtime** (download from NI’s website)  
- Python 3.10+  
- Python packages:
  - `nidaqmx`
  - `numpy`

### Optional
- `openpyxl` (only if you want Excel `.xlsx` output)

---

## 🔧 Installation

1. Clone this repository or download it:
   ```powershell
   git clone https://github.com/<your-user>/ni_usb6009_logger.git
   cd ni_usb6009_logger
   ```

2. Create a virtual environment (recommended):
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\activate
   ```

3. Install in editable/development mode:
   ```powershell
   pip install -U pip
   pip install -e .[excel]
   ```

4. Verify installation:
   ```powershell
   ni_usb6009_logger --help
   ```

---

## 🚀 Usage

### General syntax
```powershell
ni_usb6009_logger --device Dev1 --channels <channels> [options...]
```

### Options

| Option                | Description                                                                 | Default |
|-----------------------|-----------------------------------------------------------------------------|---------|
| `--device`            | NI-DAQmx device name/alias (from NI MAX)                                    | `Dev1`  |
| `--channels`          | Comma-separated analog input channels, e.g. `ai0,ai1`                       | *(req)* |
| `--digital`           | Optional DI lines, e.g. `port0/line0:7` or `port0/line0,port0/line3`        | none    |
| `--rate`              | Analog sample rate per channel (Hz)                                         | `1000`  |
| `--chunk`             | Samples per read (controls DI snapshot frequency)                          | `1000`  |
| `--vmin`, `--vmax`    | Expected AI voltage range (V)                                               | `-10, +10` |
| `--term`              | AI terminal config: `RSE`, `NRSE`, or `DIFF`                               | `RSE`   |
| `--outfile`           | Output file path. If omitted, auto-named in `.\logs\`                       | auto    |
| `--format`            | Force output format: `csv` or `xlsx`                                        | inferred|
| `--duration`          | Duration in seconds. Omit to run until Ctrl+C                              | none    |
| `--progress`          | Progress display: `auto`, `counter`, `bar`, `none`                         | auto    |
| `--update-interval`   | Seconds between progress updates                                            | `0.5`   |
| `--print-first N`     | Print the first N rows to console for preview                               | `0`     |
| `--debug`             | Print extra debug info                                                     | off     |

---

## 📝 Example commands

1. **Basic logging (AI only, CSV, auto-named file)**  
   ```powershell
   ni_usb6009_logger --device Dev1 --channels ai0 --rate 1000 --term RSE --print-first 10
   ```

2. **AI + DI logging (two AI, 4 DI lines on port0), custom CSV:**  
   ```powershell
   ni_usb6009_logger --device Dev1 --channels ai0,ai1 --digital port0/line0:3 --rate 100 --term RSE --outfile .\logs\run.csv --print-first 10
   ```

3. **Log to Excel (.xlsx):**  
   ```powershell
   ni_usb6009_logger --device Dev1 --channels ai0,ai1 --digital port0/line0:7 --rate 500 --term RSE --outfile .\logs\run.xlsx --print-first 10
   ```

4. **Timed run (auto-stop after 30s):**  
   ```powershell
   ni_usb6009_logger --device Dev1 --channels ai0 --rate 1000 --duration 30 --print-first 10
   ```

5. **Differential wiring example:**  
   ```powershell
   ni_usb6009_logger --device Dev1 --channels ai0,ai1 --rate 1000 --term DIFF --print-first 10
   ```

6. **Show live counter or progress bar:**  
   ```powershell
   # Counter (default when no --duration):
   ni_usb6009_logger --device Dev1 --channels ai0 --rate 1000 --term RSE --progress counter --print-first 10

   # Progress bar (useful with duration):
   ni_usb6009_logger --device Dev1 --channels ai0 --rate 1000 --term RSE --duration 30 --progress bar --print-first 10
   ```

---

## 📌 Notes on Digital Inputs
- On USB-6009, DI is **static** (not hardware-timed).  
- DI is snapshotted **once per AI chunk**, and that value is repeated for all rows in that chunk.  
- To increase DI sampling rate, reduce `--chunk`.  
  - Example: `--chunk 100` at 1 kHz ≈ 10 DI snapshots per second.

---

## 📂 File output
- Default folder: `.\logs\` (created automatically)  
- Default filename: `ni_<device>_<YYYYmmdd_HHMMSS>.<csv|xlsx>`  
- If a file exists, suffix `_1`, `_2`, … is added instead of overwriting.  

---

## 🔍 Development

Build & test locally:
```powershell
pip install -U build
python -m build
```

Run tests (minimal):
```powershell
pytest
```

---

## 📄 License
MIT © 2025 David Steeman
