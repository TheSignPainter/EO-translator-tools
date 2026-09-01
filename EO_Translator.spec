# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['translator_gui.py'],
    pathex=[],
    binaries=[],
    datas=[('EO5/voice_hash_table.json', 'EO5')],
    hiddenimports=['EO5.single_parser', 'EO5.checker', 'EOU2.single_parser', 'checker'],
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
    name='EO_Translator',
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
