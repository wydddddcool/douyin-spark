# -*- mode: python ; coding: utf-8 -*-
import sys
from PyInstaller.utils.hooks import collect_all, collect_submodules

# 收集 playwright 全部依赖（含动态 import 的子模块）
pw_datas, pw_binaries, pw_hiddenimports = collect_all('playwright')

# 收集 flask / jinja2 模板相关隐式依赖
flask_hidden = collect_submodules('flask')
jinja2_hidden = collect_submodules('jinja2')
apscheduler_hidden = collect_submodules('apscheduler')

block_cipher = None

a = Analysis(
    ['launcher.py'],
    pathex=['.'],
    binaries=pw_binaries,
    datas=pw_datas + [
        ('web/templates', 'web/templates'),
        ('web/static',    'web/static'),
        ('config/settings.yaml', 'config'),  # 默认配置（首次运行复制到用户目录）
    ],
    hiddenimports=pw_hiddenimports + flask_hidden + jinja2_hidden + apscheduler_hidden + [
        'yaml',
        'core',
        'core.auth',
        'core.browser',
        'core.message',
        'core.tasks',
        'utils',
        'utils.logger',
        'utils.paths',
        'engineio',
        'engineio.async_drivers.threading',
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
    name='抖音续火花',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,      # 不显示黑色控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='抖音续火花',
)

# macOS 专属：打包成 .app bundle（Windows 上此步骤自动忽略）
if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='抖音续火花.app',
        icon=None,
        bundle_identifier='com.douyinspark.app',
        info_plist={
            'NSHighResolutionCapable': True,
            'CFBundleShortVersionString': '1.0.0',
            'CFBundleVersion': '1.0.0',
            'NSHumanReadableCopyright': '',
        },
    )
