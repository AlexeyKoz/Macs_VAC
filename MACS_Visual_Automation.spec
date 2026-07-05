# -*- mode: python ; coding: utf-8 -*-
# Build:  venv\Scripts\pyinstaller.exe MACS_Visual_Automation.spec
# Output: dist\MACS_VAC\MACS_Visual_Automation.exe

from PyInstaller.utils.hooks import collect_all

block_cipher = None

datas = []
binaries = []
hiddenimports = [
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "cv2",
    "numpy",
    "PIL",
    "PIL.Image",
    "pyautogui",
    "pyscreeze",
    "pytweening",
    "mouseinfo",
    "mss",
    "pytesseract",
    "pygetwindow",
    "pyrect",
]

# OpenCV ships extra data/DLLs; PySide6 is handled by PyInstaller's built-in hook.
cv2_datas, cv2_binaries, cv2_hidden = collect_all("cv2")
datas += cv2_datas
binaries += cv2_binaries
hiddenimports += cv2_hidden

a = Analysis(
    ["MACS_Visual_Automation.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name="MACS_Visual_Automation",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="MACS_VAC",
)
