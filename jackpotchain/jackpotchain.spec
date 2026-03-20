# -*- mode: python ; coding: utf-8 -*-
"""
JackpotChain PyInstaller Spec File
"""
from PyInstaller.utils.hooks import collect_all, collect_submodules

block_cipher = None

# 모든 데이터/모듈 수집
textual_datas, textual_binaries, textual_hiddenimports = collect_all('textual')
rich_datas, rich_binaries, rich_hiddenimports = collect_all('rich')
aiohttp_datas, aiohttp_binaries, aiohttp_hiddenimports = collect_all('aiohttp')
ecdsa_datas, ecdsa_binaries, ecdsa_hiddenimports = collect_all('ecdsa')

a = Analysis(
    ['cli/main.py'],
    pathex=[],
    binaries=textual_binaries + rich_binaries + aiohttp_binaries + ecdsa_binaries,
    datas=[
        ('tui/styles.tcss', 'jackpotchain/tui'),
    ] + textual_datas + rich_datas + aiohttp_datas + ecdsa_datas,
    hiddenimports=[
        'jackpotchain',
        'jackpotchain.core',
        'jackpotchain.consensus',
        'jackpotchain.network',
        'jackpotchain.wallet',
        'jackpotchain.mempool',
        'jackpotchain.gacha',
        'jackpotchain.script',
        'jackpotchain.rpc',
        'jackpotchain.storage',
        'jackpotchain.sync',
        'jackpotchain.validation',
        'jackpotchain.crypto',
        'jackpotchain.tui',
        'jackpotchain.tui.app',
        'jackpotchain.tui.client',
        'jackpotchain.tui.widgets',
        'jackpotchain.tui.widgets.dashboard',
        'jackpotchain.tui.widgets.wallet',
        'jackpotchain.tui.widgets.mining',
        'jackpotchain.tui.widgets.lotto',
        'jackpotchain.tui.widgets.history',
        'jackpotchain.tui.widgets.network',
        'jackpotchain.tui.simple',
        'asyncio',
        'json',
        'hashlib',
        'ctypes',
        'ctypes.wintypes',
        'cryptography',
        'cryptography.hazmat',
        'cryptography.hazmat.primitives',
        'cryptography.hazmat.primitives.ciphers',
        'cryptography.hazmat.primitives.kdf',
    ] + textual_hiddenimports + rich_hiddenimports + aiohttp_hiddenimports + ecdsa_hiddenimports,
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
    name='jackpotchain',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
