# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['illustrator_toolbox.py'],
    pathex=[],
    binaries=[],
    datas=[('MergeText_AI.jsx', '.'), ('MergeText_AI_Quick.jsx', '.'), ('ReleaseClippingMask.jsx', '.')],
    hiddenimports=['pythoncom', 'pywintypes', 'win32com', 'win32com.client', 'win32com.client.dynamic'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='IllustratorToolbox',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
