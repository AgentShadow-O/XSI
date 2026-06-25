# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files, collect_submodules


a = Analysis(
    ['windows\\service\\xsi_service.py'],
    pathex=['.'],
    binaries=[],
    datas=[('config.yaml', '.')] + collect_data_files('backend'),
    hiddenimports=['win32serviceutil', 'win32service', 'win32event', 'servicemanager', 'win32timezone', 'backend.agents.common.api_client', 'backend.agents.common.temp_manager'] + collect_submodules('backend'),
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
    name='XSI-Agent-Service',
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
