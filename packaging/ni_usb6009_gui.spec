# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for the NI USB-6009 Logger GUI.
# Onedir (not onefile): faster startup, far fewer antivirus false positives.
# The NI-DAQmx driver DLLs (nicaiu.dll etc.) are NEVER bundled — they come
# with the NI-DAQmx driver installed by the installer (or separately).

import sys
from pathlib import Path

from PyInstaller.utils.hooks import copy_metadata

PROJECT_ROOT = Path(SPECPATH).parent
block_cipher = None

# nidaqmx's dependency nitypes reads its own package metadata at import
# (importlib.metadata); without the dist-info the frozen app dies with
# "PackageNotFoundError: nitypes" before ever touching the driver DLL.
datas = sum((copy_metadata(p) for p in ("nidaqmx", "nitypes", "python-decouple")), [])

a = Analysis(
    [str(PROJECT_ROOT / "src" / "ni_usb6009_logger" / "gui" / "app.py")],
    pathex=[str(PROJECT_ROOT / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "pyqtgraph",
        "pyqtgraph.graphicsItems.PlotItem.PlotItem",
        "pyqtgraph.graphicsItems.ViewBox.ViewBox",
        "openpyxl",
        "openpyxl.workbook",
        "openpyxl.write_only",
        "ni_usb6009_logger.gui.widgets.live_plot",
        "ni_usb6009_logger.gui.widgets.device_picker",
        "ni_usb6009_logger.gui.widgets.ignition_panel",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "pytest",
        "ni_usb6009_logger._fake_nidaqmx",  # dev-only fake backend
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="NI6009Logger",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,               # windowed app
    disable_windowed_traceback=False,
    icon=str(PROJECT_ROOT / "packaging" / "app.ico") if (PROJECT_ROOT / "packaging" / "app.ico").exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="NI6009Logger",
)
