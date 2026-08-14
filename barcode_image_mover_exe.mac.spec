# -*- mode: python ; coding: utf-8 -*-
# PyInstaller macOS 打包配置 — 图片处理工具
# 产出 dist/图片处理工具.app（onedir + windowed）

import os

a = Analysis(
    ['barcode_image_mover_exe.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'app',
        'app.constants',
        'app.core',
        'app.core.classifier',
        'app.core.excel_reader',
        'app.core.file_ops',
        'app.core.image_processor',
        'app.core.matcher',
        'app.core.packager',
        'app.core.pipeline',
        'app.services',
        'app.services.logger',
        'app.services.icons',
        'app.ui',
        'app.ui.main_window',
        'app.ui.widgets',
        'app.ui.workers',
        'app.ui.dialogs',
        'app.ui.styles',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'PySide6.Qt3DAnimation', 'PySide6.Qt3DCore', 'PySide6.Qt3DExtras', 'PySide6.Qt3DInput',
        'PySide6.Qt3DLogic', 'PySide6.Qt3DRender', 'PySide6.QtBluetooth', 'PySide6.QtCharts',
        'PySide6.QtDataVisualization', 'PySide6.QtDesigner', 'PySide6.QtGraphs',
        'PySide6.QtGraphsWidgets', 'PySide6.QtHelp', 'PySide6.QtHttpServer', 'PySide6.QtLocation',
        'PySide6.QtMultimedia', 'PySide6.QtMultimediaWidgets', 'PySide6.QtNetworkAuth',
        'PySide6.QtNfc', 'PySide6.QtOpenGL', 'PySide6.QtOpenGLWidgets', 'PySide6.QtPdf',
        'PySide6.QtPdfWidgets', 'PySide6.QtPositioning', 'PySide6.QtPrintSupport',
        'PySide6.QtQml', 'PySide6.QtQuick', 'PySide6.QtQuick3D', 'PySide6.QtQuickControls2',
        'PySide6.QtQuickTest', 'PySide6.QtQuickWidgets', 'PySide6.QtRemoteObjects',
        'PySide6.QtScxml', 'PySide6.QtSensors', 'PySide6.QtSerialBus', 'PySide6.QtSerialPort',
        'PySide6.QtSpatialAudio', 'PySide6.QtSql', 'PySide6.QtStateMachine', 'PySide6.QtSvg',
        'PySide6.QtSvgWidgets', 'PySide6.QtTest', 'PySide6.QtTextToSpeech', 'PySide6.QtUiTools',
        'PySide6.QtWebChannel', 'PySide6.QtWebEngineCore', 'PySide6.QtWebEngineQuick',
        'PySide6.QtWebEngineWidgets', 'PySide6.QtWebSockets', 'PySide6.QtWebView', 'PySide6.QtXml',
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='图片处理工具',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    name='图片处理工具',
)

_icon = 'app.icns' if os.path.exists('app.icns') else None
app = BUNDLE(
    coll,
    name='图片处理工具.app',
    icon=_icon,
    bundle_identifier='com.image.processor',
)
