# Packaging — NI USB-6009 Logger GUI (Windows)

## One-time setup (Windows build machine)

1. Python 3.11+ and `pip install .[gui,excel] pyinstaller`
2. [Inno Setup 6](https://jrsoftware.org/isinfo.php)
3. *(optional)* NI-DAQmx runtime redistributable from ni.com as
   `packaging/nidaqmx/nidaqmx_setup.exe` so the installer can deploy the
   driver silently (royalty-free redistribution is permitted by NI's
   license; the file adds several hundred MB)

## Build

```powershell
pyinstaller packaging\ni_usb6009_gui.spec --noconfirm
# SourceDir is relative to packaging\installer.iss, so the repo-root dist\
# bundle is ..\dist\NI6009Logger (that is also the script's default).
iscc /DAppVersion=1.2.0 /DSourceDir=..\dist\NI6009Logger packaging\installer.iss
# result: packaging\Output\NI6009Logger_Setup_1.2.0.exe
```

CI does the same on tag push (`v*`); set the repository variable
`NIDAQMX_URL` to a direct download of the redistributable if you want the
driver component included in CI-built installers.

## Pre-build regression check (any Windows box, no hardware)

CI runs on ubuntu with no NI driver, so nothing in it exercises the driver.
Before tagging a release, run these against an NI-DAQmx **simulated** USB-6009
(NI MAX -> Devices and Interfaces -> Create New -> NI-DAQmx Simulated Device):

```powershell
.\.venv\Scripts\ni_usb6009_gui.exe --selftest        # expect exit 0 + device name
.\.venv\Scripts\ni_usb6009_logger.exe --help > nul   # redirected: catches encoding regressions
.\.venv\Scripts\ni_usb6009_logger.exe --device <sim> --channels ai0,ai1 --rate 1000 --duration 2 --progress bar
.\.venv\Scripts\ni_usb6009_logger.exe --device <sim> --channels ai0 --rate 50 --duration 0.3
```

The last one guards the read-timeout scaling (a fixed timeout failed every read
below ~100 Hz at the default chunk). Then open the GUI and stop a run on each
tab -- the Calibrate tab shipped a crash that the offscreen suite could not see.

## Phase-6 verification checklist (clean Windows VM)

- [ ] PyInstaller bundle starts; check PyInstaller picked up nidaqmx hooks
      (if `DriverNotInstalledError` appears *with the driver installed*,
      add `collect_dynamic_libs("nidaqmx")`-style binaries to the spec)
- [ ] Installer without the nidaqmx component → app shows the guided
      driver-download dialog
- [ ] Installer with the component → driver installs **silently**, no
      prompts (verify `/q /AcceptLicenses yes /suppressrestart` against the
      exact redistributable; NI Package Manager variants may differ)
- [ ] Post-install self-test reports "Driver OK and USB-6009 detected"
      with the device plugged in, "No DAQ device found yet" without
- [ ] Full run: log a test to CSV and XLSX, check `recovery\` copy
- [ ] Ignition dry run with relay board + buzzer, no igniter
- [ ] Uninstall is clean (no leftovers in %LOCALAPPDATA% settings)
- [ ] SmartScreen shows "Windows protected your PC" → document
      "More info → Run anyway" for users (real fix = code-signing cert)

## What is never bundled

`nicaiu.dll` and every NI driver DLL ship with NI-DAQmx itself — bundling
them would break licensing and version assumptions.
