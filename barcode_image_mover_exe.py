#!/usr/bin/env python3
"""
电商图片批处理工具 - PySide6 独立 EXE 版
双击运行，无需额外文件。
依赖：pip install PySide6 Pillow openpyxl
打包：pyinstaller --onefile --windowed --collect-all PIL --collect-all openpyxl --collect-all PySide6 barcode_image_mover_exe.py
"""

import os
import sys
import re
import shutil
import zipfile
import datetime
import threading
import base64
import tempfile
import csv
import atexit
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from typing import NamedTuple, Optional
import winsound
from PIL import Image, ImageOps
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QComboBox, QCheckBox, QTextEdit,
                               QFileDialog, QMessageBox, QGridLayout,
                               QProgressBar, QFrame, QGraphicsDropShadowEffect,
                               QSizePolicy, QListView, QTabWidget)
from PySide6.QtCore import Qt, QThread, Signal, QObject, QTimer, QSize, QRectF
from PySide6.QtGui import (QTextCursor, QTextCharFormat, QColor, QFont, QIcon, QPixmap,
                            QPalette, QPainter, QLinearGradient, QPainterPath)


# ============================================================
# 核心常量与工具函数（从 app 包导入）
# ============================================================

from app.constants import (
    IMAGE_EXTS, TARGET_SIZE, ZIP_SPLIT_BYTES, COPY_WORKERS, IMAGE_WORKERS,
    MAIN_IMAGE_MAX_BYTES, DETAIL_IMAGE_MAX_BYTES,
    MAIN_JPEG_QUALITY, MAIN_JPEG_COMPRESS_START_QUALITY, MAIN_JPEG_MIN_QUALITY,
    DETAIL_JPEG_OPTIMIZE_QUALITY, DETAIL_JPEG_QUALITIES, DETAIL_SCALE_FACTORS,
    EXCEL_EMPTY_ROW_BREAK_THRESHOLD, MANUAL_REVIEW_DIR_NAME,
    LOG_FLUSH_INTERVAL, PROGRESS_REPORT_FRACTION, EXECUTOR_POLL_SECONDS,
    LOG_MAX_BLOCK_COUNT, DEBOUNCE_MS, SHIMMER_INTERVAL_MS,
    SHIMMER_STEP, SHIMMER_BAND_WIDTH, RESAMPLE_LANCZOS,
    MODE_NAMES, RESIZE_MODE_MAP, MODE_HELP_TEXT, UI_HELP_TEXT,
)
from app.services.logger import LogWriter
from app.services.icons import _darken, _write_temp_svg, _TEMP_ICON_PATHS, _cleanup_temp_icons
from app.core.classifier import (
    clean_detail_suffix, is_image_file, iter_files, iter_image_files,
    split_source_images, dir_has_files,
)
from app.core.file_ops import (
    get_unique_path, release_reserved_path, validate_output_dir, suggest_output_dir,
    copy_to_manual_review, remove_output_file_quiet, send_to_manual_and_remove_output,
    add_manual_source_aliases, build_manual_source_lookup, resolve_manual_source,
    make_temp_image_path, write_image_buffer, flatten_to_white_rgb,
    copy_files_parallel, clean_detail_names_in_dir, image_to_buffer,
    sanitize_csv_cell, unique_preserve_order,
)
from app.core.pipeline import run_all, step1_detail, step2_main
from app.core.excel_reader import step3_read_excel, excel_col_to_index, read_excel_preview
from app.core.matcher import step4_match_preview, step4_match
from app.core.image_processor import (
    MainImageResult, DetailImageResult,
    _resize_stretch, _resize_crop, _resize_fit,
    _process_main_image, step6_process_main,
    _process_detail_image_impl, _process_detail_image, step7_process_detail,
)
from app.core.packager import step8_zip



from app.ui.widgets import EmittingStream, DragLineEdit, RoundComboBox, AnimatedProgressBar
from app.ui.workers import WorkerThread, ExcelHeaderWorker
from app.ui.main_window import MainWindow

APP_ICON_B64 = "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"

def _remove_temp_icon(icon_path):
    try:
        if os.path.exists(icon_path):
            os.remove(icon_path)
    except OSError:
        pass


def main():
    if sys.platform == 'win32':
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    # Qt6 默认启用高 DPI 缩放，不再需要 QT_ENABLE_HIGHDPI_SCALING 环境变量
    font = QFont(["Microsoft YaHei", "Segoe UI", "Noto Sans CJK SC"])
    font.setPointSize(10)
    font.setStyleStrategy(
        QFont.StyleStrategy.PreferAntialias | QFont.StyleStrategy.PreferQuality
    )
    # 高 DPI 下 PreferNoHinting 渲染最清晰，PreferDefaultHinting 会使用位图 hint 导致锯齿
    font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    app.setFont(font)

    # 从嵌入的多尺寸 ICO 设置窗口图标，避免任务栏只拿到低分辨率图层。
    icon_bytes = base64.b64decode(APP_ICON_B64)
    icon_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".ico") as f:
            icon_path = f.name
            f.write(icon_bytes)
        app.setWindowIcon(QIcon(icon_path))
        app.aboutToQuit.connect(lambda p=icon_path: _remove_temp_icon(p))
    except Exception:
        if icon_path:
            _remove_temp_icon(icon_path)
        pm = QPixmap()
        pm.loadFromData(icon_bytes)
        app.setWindowIcon(QIcon(pm))

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

