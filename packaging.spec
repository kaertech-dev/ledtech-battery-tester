# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['packaging.py'],
    pathex=[],
    binaries=[],
    datas=[('try.ui', '.'), ('messageform.ui', '.'), ('reprint.ui', '.'), ('duplicate_message.ui', '.'), ('packaging_log.csv', '.'), ('label_config.txt', '.'), ('inner_zpl.txt', '.'), ('outer_zpl.txt', '.')],
    hiddenimports=[],
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
    [],
    exclude_binaries=True,
    name='packaging',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='packaging',
)
