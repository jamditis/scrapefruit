# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for Scrapefruit

import os
import sys

block_cipher = None

# Get the project root
project_root = os.path.dirname(os.path.abspath(SPEC))

a = Analysis(
    ['main.py'],
    pathex=[project_root],
    binaries=[],
    datas=[
        # Include static files (HTML, CSS, JS)
        ('static', 'static'),
        # Include playwright_stealth JS files
        ('venv/Lib/site-packages/playwright_stealth/js', 'playwright_stealth/js'),
    ],
    hiddenimports=[
        'webview',
        'webview.platforms.winforms',
        'clr_loader',
        'pythonnet',
        'flask',
        'flask_cors',
        'flask_socketio',
        'sqlalchemy',
        'sqlalchemy.dialects.sqlite',
        'eventlet',
        'eventlet.hubs.epolls',
        'eventlet.hubs.kqueue',
        'eventlet.hubs.selects',
        'dns',
        'dns.resolver',
        'trafilatura',
        'lxml',
        'cssselect',
        'requests',
        'playwright',
        'playwright.sync_api',
        'playwright_stealth',
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Scrapefruit',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No console window (GUI app)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='static/favicon.ico' if os.path.exists('static/favicon.ico') else None,
)
