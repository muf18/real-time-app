# -*- mode: python ; coding: utf-8 -*-

import sys

block_cipher = None

# Platform-specific adjustments
if sys.platform == 'darwin':
    platform_name = 'macos'
    app_name = 'CryptoChart'
    icon_path = 'resources/icon.icns' # Assume this exists
    entitlements = 'resources/entitlements.plist' # Required for notarization
    extra_options = {
        'bundle_identifier': 'com.example.cryptochart',
        'codesign_identity': 'Apple Development: your.email@example.com',
        'entitlements_file': entitlements,
    }
elif sys.platform == 'win32':
    platform_name = 'windows'
    app_name = 'CryptoChart.exe'
    icon_path = 'resources/icon.ico' # Assume this exists
    extra_options = {}
else:
    raise RuntimeError("Unsupported platform")

a = Analysis(
    ['src/ui_desktop/main.py'],
    pathex=['src'],
    binaries=[],
    datas=[('src/ui_desktop/assets', 'assets')], # Bundle UI assets
    hiddenimports=['pyqtgraph.colors', 'keyring.backends.SecretService', 'keyring.backends.macOS', 'keyring.backends.Windows'],
    hookspath=[],
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
    name=app_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False, # GUI application
    icon=icon_path,
    **extra_options,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=f'dist/{platform_name}',
)

if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name=f'{app_name}.app',
        icon=icon_path,
        bundle_identifier=extra_options['bundle_identifier'],
    )