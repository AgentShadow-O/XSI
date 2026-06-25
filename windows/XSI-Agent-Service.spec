# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files
from PyInstaller.utils.hooks import collect_submodules

datas = [('C:\\CLI\\Cybersecurity\\XSI\\windows\\..\\config.yaml', '.')]
hiddenimports = ['win32timezone', 'backend.agents.common.api_client', 'backend.agents.common.temp_manager']
datas += collect_data_files('backend')
hiddenimports += collect_submodules('backend')


a = Analysis(
    ['service\\xsi_service.py'],
    pathex=['C:\\CLI\\Cybersecurity\\XSI\\windows\\..'],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
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
