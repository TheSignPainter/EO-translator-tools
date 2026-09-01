# -*- mode: python ; coding: utf-8 -*-
import os


# spec 所在目录即项目根目录（兼容 SPECPATH 为目录或文件路径两种语义）
_spec_path = os.path.abspath(SPECPATH)
project_root = _spec_path if os.path.isdir(_spec_path) else os.path.dirname(_spec_path)

a = Analysis(
    ['translator_gui.py'],
    pathex=[project_root],
    binaries=[],
    datas=[(
        os.path.join(project_root, 'EO5', 'voice_hash_table.json'),
        'EO5',
    )],
    # GUI 通过 importlib 动态导入解析器模块，字符串形式无法被静态分析发现，
    # 必须显式列出，否则冻结后的程序会报 ModuleNotFoundError。
    hiddenimports=[
        'EO5.single_parser',
        'EO5.checker',
        'EOU2.single_parser',
        'checker',
    ],
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
