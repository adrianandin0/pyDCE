# -*- mode: python ; coding: utf-8 -*-

import os
import sys

block_cipher = None

# Leer versión unificada
app_version = '1.1.2'
if os.path.exists('version.txt'):
    with open('version.txt', 'r', encoding='utf-8') as vf:
        v = vf.read().strip()
        if v:
            app_version = v

extra_datas = [
    ('gui/iconos', 'gui/iconos'),
    ('locales', 'locales'),
    ('version.txt', '.'),
]
for icon_name in [
    'pyDCE.png', 'pydce.png',
    'pyDCE.ico', 'pydce.ico',
    'pyDCE.icns', 'pydce.icns',
    'icono.png', 'paintdotnet.ico'
]:
    icon_path = os.path.join('gui', icon_name)
    if os.path.exists(icon_path):
        extra_datas.append((icon_path, 'gui'))

app_icon = None
if sys.platform == 'win32':
    for candidate in ['gui/pyDCE.ico', 'gui/pydce.ico', 'gui/paintdotnet.ico']:
        if os.path.exists(candidate):
            app_icon = candidate
            break
elif sys.platform == 'darwin':
    for candidate in ['gui/pyDCE.icns', 'gui/pydce.icns', 'gui/pyDCE.png']:
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

if sys.platform == 'darwin':
    bundle_icon = None
    for candidate in ['gui/pyDCE.icns', 'gui/pydce.icns']:
        if os.path.exists(candidate):
            bundle_icon = candidate
            break

    app = BUNDLE(
        coll,
        name='pyDCE.app',
        icon=bundle_icon,
        bundle_identifier='com.adrian.pydce',
        info_plist={
            'CFBundleName': 'pyDCE',
            'CFBundleDisplayName': 'pyDCE',
            'CFBundleIdentifier': 'com.adrian.pydce',
            'CFBundleVersion': app_version,
            'CFBundleShortVersionString': app_version,
            'CFBundlePackageType': 'APPL',
            'CFBundleSignature': '????',
            'CFBundleExecutable': 'pyDCE',
            'CFBundleIconFile': 'pyDCE.icns',
            'NSHighResolutionCapable': True,
            'LSMinimumSystemVersion': '11.0',
            'NSPrincipalClass': 'NSApplication',
            'NSAppleScriptEnabled': False,
        },
    )
