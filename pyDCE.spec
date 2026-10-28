# -*- mode: python ; coding: utf-8 -*-

import os
import sys

block_cipher = None

extra_datas = [
    ('gui/iconos', 'gui/iconos'),
    ('locales', 'locales'),
    ('version.txt', '.'),
]
for icon_name in ['pyDCE.png', 'pydce.png', 'pyDCE.ico', 'pydce.ico', 'icono.png', 'paintdotnet.ico']:
    icon_path = os.path.join('gui', icon_name)
    if os.path.exists(icon_path):
        extra_datas.append((icon_path, 'gui'))

app_icon = None
if sys.platform == 'win32':
    for candidate in ['gui/pyDCE.ico', 'gui/pydce.ico', 'gui/paintdotnet.ico']:
        if os.path.exists(candidate):
            app_icon = candidate
            break
else:
    for candidate in ['gui/pyDCE.png', 'gui/pydce.png', 'gui/icono.png']:
        if os.path.exists(candidate):
            app_icon = candidate
            break

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=extra_datas,
    hiddenimports=[
        'PyQt6',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'cv2',
        'numpy',
        'json',
        'requests',
        'PIL',
        'Pillow',
    ],
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
    name='pyDCE',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=app_icon,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='pyDCE',
)
