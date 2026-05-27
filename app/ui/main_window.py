# -*- coding: utf-8 -*-
"""主窗口布局 & 信号连接"""

import os
import sys
import re
import threading

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QCheckBox, QTextEdit, QFileDialog, QMessageBox,
    QProgressBar, QFrame, QGraphicsDropShadowEffect, QSizePolicy, QGridLayout,
    QTabWidget, QListView,
)
from PySide6.QtCore import Qt, QTimer, QSize, QRectF
from PySide6.QtGui import (
    QTextCursor, QTextCharFormat, QColor, QFont, QIcon, QPixmap,
)
import winsound

from app.constants import (
    DEBOUNCE_MS, LOG_MAX_BLOCK_COUNT, MODE_HELP_TEXT, RESIZE_MODE_MAP, UI_HELP_TEXT,
)
from app.services.icons import _write_temp_svg, _TEMP_ICON_PATHS, _cleanup_temp_icons
from app.core.file_ops import validate_output_dir, suggest_output_dir
from app.core.pipeline import run_all
from app.core.excel_reader import read_excel_preview
from app.ui.widgets import EmittingStream, DragLineEdit, RoundComboBox, AnimatedProgressBar
from app.ui.workers import WorkerThread, ExcelHeaderWorker
from app.ui.styles import get_theme_colors, build_stylesheet
from app.ui.dialogs import question_box, info_box

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("图片处理工具")
        self.resize(1000, 680)
        self._colors = get_theme_colors()

        self.stop_event = threading.Event()
        self.worker = None
        self.header_worker = None
        self.header_workers = []
        self._last_output_dir = None
        self._old_stdout = sys.stdout
        self._stdout_stream = None
        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(DEBOUNCE_MS)
        self._debounce_timer.timeout.connect(self._do_update_header_preview)

        self._setup_ui()
        self._update_excel_params_enabled()  # 初始没有 Excel

        self._stdout_stream = EmittingStream()
        self._stdout_stream.textWritten.connect(
            self.append_log, Qt.ConnectionType.QueuedConnection
        )
        sys.stdout = self._stdout_stream

    def _populate_col_combo(self, headers):
        """根据当前 Excel 路径重新填充条码列下拉框"""
        # 保存当前选中值
        old_col = self.cb_col.currentData()
        self.cb_col.blockSignals(True)
        self.cb_col.clear()
        if headers:
            idx_to_set = 0
            for i, (col_letter, header_text) in enumerate(headers):
                header_brief = (str(header_text) if header_text is not None else "").strip()
                if len(header_brief) > 10:
                    header_brief = header_brief[:10] + "..."
                display_text = f"{col_letter}-{header_brief}" if header_brief else col_letter
                self.cb_col.addItem(display_text, col_letter)
                self.cb_col.setItemData(i, f"{col_letter} - {header_text}", Qt.ItemDataRole.ToolTipRole)
                if col_letter == old_col:
                    idx_to_set = i
            self.cb_col.setCurrentIndex(idx_to_set)
        else:
            fallback = old_col or "A"
            self.cb_col.addItem(fallback, fallback)
            self.cb_col.setItemData(0, "未检测到表头，使用当前/默认列", Qt.ItemDataRole.ToolTipRole)
        self.cb_col.blockSignals(False)

    def _update_excel_params_enabled(self):
        """Excel 路径为空时禁用所有 Excel 参数控件"""
        has_excel = bool(self.le_excel.text().strip())
        self.cb_col.setEnabled(has_excel)
        self.le_sheet.setEnabled(has_excel)
        self.le_start.setEnabled(has_excel)
        self.le_end.setEnabled(has_excel)
        self._sync_row_range_input_style(has_excel)
        self.lbl_header_preview.setEnabled(has_excel)
        if not has_excel:
            self.lbl_header_preview.setText("表头：(未选择 Excel)")
            self.lbl_header_preview.setStyleSheet(f"color: {self._colors['muted']};")

    def _sync_row_range_input_style(self, enabled):
        """行范围输入框在嵌套布局里禁用态偶尔不吃全局 QSS，单独同步颜色。"""
        c = self._colors
        bg = c['input'] if enabled else c['card2']
        fg = c['text'] if enabled else c['muted']
        border = c['input_border'] if enabled else c['border']
        style = (
            f"background: {bg}; color: {fg}; border: 1px solid {border}; "
            "border-radius: 6px; min-height: 34px; max-height: 34px; padding: 0px 10px;"
        )
        self.le_start.setStyleSheet(style)
        self.le_end.setStyleSheet(style)

    def _apply_app_style(self):
        c = self._colors
        # Qt QSS 不支持 data URI，需要把图标写到临时文件再引用
        # Checkbox 勾选图标
        checkbox_checked_svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="20" height="20">'
            f'<rect x="2" y="2" width="20" height="20" rx="6" ry="6" fill="{c["green"]}" />'
            f'<path d="M8 12 L11 15 L16 9" fill="none" stroke="#FFFFFF"'
            f' stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>'
            f'</svg>'
        )
        checkbox_unchecked_svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="20" height="20">'
            f'<rect x="2" y="2" width="20" height="20" rx="6" ry="6" '
            f'fill="{c["input"]}" stroke="{c["input_border"]}" stroke-width="2" />'
            f'</svg>'
        )
        cb_checked_ico = _write_temp_svg(checkbox_checked_svg, "cb_checked_ico_")
        cb_unchecked_ico = _write_temp_svg(checkbox_unchecked_svg, "cb_unchecked_ico_")
        checkbox_checked_css = f"image: url({cb_checked_ico});" if cb_checked_ico else f"background: {c['green']};"
        checkbox_unchecked_css = f"image: url({cb_unchecked_ico});" if cb_unchecked_ico else f"background: {c['input']};"

        # ComboBox 下拉箭头图标
        arrow_svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 12 8" width="12" height="8">'
            f'<path d="M1.5 1.5L6 6L10.5 1.5" fill="none" stroke="{c["muted"]}"'
            f' stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>'
            f'</svg>'
        )
        arrow_ico = _write_temp_svg(arrow_svg, "cb_arrow_")

        # 开始按钮（播放）图标 - 启用态白色、禁用态灰色
        play_ico = _write_temp_svg(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="20" height="20">'
            f'<polygon points="8,5 19,12 8,19" fill="white"/></svg>',
            "btn_play_"
        )
        play_ico_dis = _write_temp_svg(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="20" height="20">'
            f'<polygon points="8,5 19,12 8,19" fill="{c["muted"]}"/></svg>',
            "btn_play_dis_"
        )

        # 停止按钮（方块）图标 - 启用态白色、禁用态灰色
        stop_ico = _write_temp_svg(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="18" height="18">'
            '<rect x="6" y="6" width="12" height="12" rx="2" fill="white"/></svg>',
            "btn_stop_"
        )
        stop_ico_dis = _write_temp_svg(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="18" height="18">'
            f'<rect x="6" y="6" width="12" height="12" rx="2" fill="{c["muted"]}"/></svg>',
            "btn_stop_dis_"
        )

        # 保存图标路径，_setup_ui 和启用/禁用切换时使用
        self._play_ico_path = play_ico
        self._stop_ico_path = stop_ico
        self._play_ico_dis_path = play_ico_dis
        self._stop_ico_dis_path = stop_ico_dis

        # 更新 DragLineEdit 的拖拽高亮颜色，跟随主题
        DragLineEdit._accent_color = c['accent']

        self.setStyleSheet(build_stylesheet(self._colors, checkbox_checked_css, checkbox_unchecked_css, arrow_ico))

    def _add_shadow(self, widget, blur=14, y=3):
        effect = QGraphicsDropShadowEffect(widget)
        effect.setBlurRadius(blur)
        effect.setOffset(0, y)
        effect.setColor(self._colors['shadow'])
        widget.setGraphicsEffect(effect)

    def _section_title(self, icon, text, color=None):
        label = QLabel(text if not icon else f"{icon}  {text}")
        label.setObjectName("sectionTitle")
        if color:
            label.setStyleSheet(f"QLabel#sectionTitle {{ color: {color}; }}")
        return label

    def _hint_label(self, text):
        label = QLabel(text)
        label.setObjectName("hintLabel")
        label.setWordWrap(True)
        return label

    def _field_label(self, text):
        label = QLabel(text)
        label.setObjectName("fieldLabel")
        return label

    def _setup_combo_view(self, combo):
        view = QListView()
        view.setObjectName("roundComboView")
        combo.setView(view)
        combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        combo.setMinimumContentsLength(12)
        return combo

    def _setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        ui_gap = 14
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(ui_gap, ui_gap, ui_gap, ui_gap)
        main_layout.setSpacing(ui_gap)

        top_layout = QHBoxLayout()
        top_layout.setSpacing(ui_gap)

        path_group = QFrame()
        path_group.setObjectName("CardFrame")
        path_group.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        path_group.setMinimumWidth(480)
        path_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._add_shadow(path_group)
        path_layout = QGridLayout(path_group)
        path_layout.setHorizontalSpacing(10)
        path_layout.setVerticalSpacing(10)
        path_layout.setContentsMargins(14, 12, 14, 12)
        path_layout.setColumnMinimumWidth(0, 76)
        path_layout.setColumnMinimumWidth(1, 240)
        path_layout.setColumnMinimumWidth(2, 80)
        path_layout.setColumnStretch(1, 1)
        path_layout.addWidget(
            self._section_title("", "路径与文件设置"),
            0, 0, 1, 3,
            Qt.AlignmentFlag.AlignTop,
        )

        self.le_source = DragLineEdit()
        self.le_source.setMinimumWidth(240)
        self.le_source.setPlaceholderText(r"D:\ecommerce\images\source")
        self.le_source.setToolTip("原始图片所在文件夹。源文件不会在分类步骤中被改动。")
        btn_source = QPushButton("浏览...")
        btn_source.setFixedWidth(80)
        btn_source.setToolTip("选择原始图片所在文件夹。")
        btn_source.clicked.connect(lambda: self._browse_dir(self.le_source, is_source=True))
        path_layout.addWidget(self._field_label("源文件夹"), 1, 0, Qt.AlignmentFlag.AlignVCenter)
        path_layout.addWidget(self.le_source, 1, 1, Qt.AlignmentFlag.AlignVCenter)
        path_layout.addWidget(btn_source, 1, 2, Qt.AlignmentFlag.AlignVCenter)

        self.le_output = DragLineEdit()
        self.le_output.setMinimumWidth(240)
        self.le_output.setPlaceholderText(r"D:\ecommerce\images\output")
        self.le_output.setToolTip("处理结果保存目录。建议选择空文件夹或新文件夹，方便查看结果。")
        btn_output = QPushButton("浏览...")
        btn_output.setFixedWidth(80)
        btn_output.setToolTip("选择处理结果保存目录。")
        btn_output.clicked.connect(lambda: self._browse_dir(self.le_output, is_source=False))
        path_layout.addWidget(self._field_label("输出目录"), 2, 0, Qt.AlignmentFlag.AlignVCenter)
        path_layout.addWidget(self.le_output, 2, 1, Qt.AlignmentFlag.AlignVCenter)
        path_layout.addWidget(btn_output, 2, 2, Qt.AlignmentFlag.AlignVCenter)

        self.le_excel = DragLineEdit()
        self.le_excel.setMinimumWidth(240)
        self.le_excel.setPlaceholderText(r"D:\ecommerce\images\list\商品图清单.xlsx")
        self.le_excel.setToolTip("可选。选择 Excel 后会按条码列匹配图片；留空则不按条码匹配。")
        self.le_excel.textChanged.connect(self._update_excel_params_enabled)
        btn_excel = QPushButton("浏览...")
        btn_excel.setFixedWidth(80)
        btn_excel.setToolTip("选择包含条码清单的 Excel 文件（.xlsx 或 .xlsm）。")
        btn_excel.clicked.connect(self._browse_excel)
        path_layout.addWidget(self._field_label("Excel清单"), 3, 0, Qt.AlignmentFlag.AlignVCenter)
        path_layout.addWidget(self.le_excel, 3, 1, Qt.AlignmentFlag.AlignVCenter)
        path_layout.addWidget(btn_excel, 3, 2, Qt.AlignmentFlag.AlignVCenter)

        path_hint = self._hint_label("Excel 中需包含条码列，用于与图片文件名匹配；不选择 Excel 时会全量处理所有图片")
        path_hint.setContentsMargins(0, 2, 0, 0)
        path_layout.addWidget(path_hint, 4, 1, 1, 2, Qt.AlignmentFlag.AlignTop)
        top_layout.addWidget(path_group, 2)

        self.excel_group = QFrame()
        self.excel_group.setObjectName("CardFrame")
        self.excel_group.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.excel_group.setMinimumWidth(280)
        self.excel_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self._add_shadow(self.excel_group)
        excel_layout = QGridLayout(self.excel_group)
        excel_layout.setHorizontalSpacing(10)
        excel_layout.setVerticalSpacing(12)
        excel_layout.setContentsMargins(14, 14, 14, 14)
        excel_layout.setColumnMinimumWidth(0, 54)
        excel_layout.setColumnStretch(1, 1)
        excel_layout.addWidget(
            self._section_title("", "Excel 参数配置"),
            0, 0, 1, 4,
            Qt.AlignmentFlag.AlignTop,
        )

        excel_layout.addWidget(self._field_label("条码列"), 1, 0)
        barcode_row = QHBoxLayout()
        barcode_row.setSpacing(10)
        barcode_row.setContentsMargins(0, 0, 0, 0)
        self.cb_col = RoundComboBox()
        self.cb_col.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.cb_col.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.cb_col.setMinimumContentsLength(8)
        self._setup_combo_view(self.cb_col)
        self.cb_col.setToolTip("Excel 第一行会作为表头预览；请选择真正的条码列。")
        barcode_row.addWidget(self.cb_col, 1)
        self.lbl_header_preview = QLabel("表头：(未加载)")
        self.lbl_header_preview.setToolTip("显示当前条码列在 Excel 第一行对应的表头，便于检查是否选错列。")
        self.lbl_header_preview.setStyleSheet(f"color: {self._colors['muted']}; font-style: italic;")
        excel_layout.addLayout(barcode_row, 1, 1, 1, 3)
        excel_layout.addWidget(self.lbl_header_preview, 2, 1, 1, 3, Qt.AlignmentFlag.AlignLeft)

        excel_layout.addWidget(self._field_label("工作表"), 3, 0)
        self.le_sheet = QLineEdit()
        self.le_sheet.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.le_sheet.setPlaceholderText("Sheet1")
        self.le_sheet.setToolTip("可选。填写指定工作表名称；留空默认读取第一个工作表。")
        excel_layout.addWidget(self.le_sheet, 3, 1, 1, 3)

        excel_layout.addWidget(self._field_label("行范围"), 4, 0)
        self.row_range_wrap = QWidget()
        self.row_range_wrap.setStyleSheet("background: transparent;")
        self.row_range_wrap.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        row_range_layout = QHBoxLayout(self.row_range_wrap)
        row_range_layout.setSpacing(10)
        row_range_layout.setContentsMargins(0, 0, 0, 0)
        self.le_start = QLineEdit()
        self.le_start.setObjectName("rowRangeInput")
        self.le_start.setMinimumWidth(60)
        self.le_start.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.le_start.setPlaceholderText("2")
        self.le_start.setToolTip("可选。Excel 起始行号；留空默认从第 2 行开始，通常第 1 行是表头。")
        row_range_layout.addWidget(self.le_start, 1)
        self.lbl_to = self._field_label("至")
        self.lbl_to.setFixedWidth(30)
        self.lbl_to.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_to.setStyleSheet("background: transparent;")
        row_range_layout.addWidget(self.lbl_to)
        self.le_end = QLineEdit()
        self.le_end.setObjectName("rowRangeInput")
        self.le_end.setMinimumWidth(60)
        self.le_end.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.le_end.setPlaceholderText("999999")
        self.le_end.setToolTip("可选。Excel 结束行号；留空默认读取到最后一行。")
        row_range_layout.addWidget(self.le_end, 1)
        excel_layout.addWidget(self.row_range_wrap, 4, 1, 1, 3)

        excel_hint = self._hint_label("从第 2 行开始读取数据（通常第 1 行为表头）")
        excel_layout.addWidget(excel_hint, 5, 1, 1, 3)

        self.le_excel.textChanged.connect(self._debounce_header_preview)
        self.le_excel.textChanged.connect(self._update_excel_params_enabled)
        self.le_sheet.textChanged.connect(self._debounce_header_preview)
        self.cb_col.currentIndexChanged.connect(self._debounce_header_preview)
        top_layout.addWidget(self.excel_group, 1)

        opt_group = QFrame()
        opt_group.setObjectName("CardFrame")
        opt_group.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        opt_group.setMinimumWidth(320)
        opt_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self._add_shadow(opt_group)
        opt_layout = QGridLayout(opt_group)
        opt_layout.setHorizontalSpacing(10)
        opt_layout.setVerticalSpacing(12)
        opt_layout.setContentsMargins(14, 14, 14, 14)
        opt_layout.setColumnMinimumWidth(0, 104)
        opt_layout.setColumnMinimumWidth(1, 170)
        opt_layout.setColumnStretch(1, 1)
        opt_layout.addWidget(
            self._section_title("", "处理选项"),
            0, 0, 1, 2,
            Qt.AlignmentFlag.AlignTop,
        )

        opt_layout.addWidget(self._field_label("处理流程"), 1, 0)
        self.cb_mode = RoundComboBox()
        self._setup_combo_view(self.cb_mode)
        self.cb_mode.addItems(["完整流程", "预览模式", "仅分类(无Excel)"])
        self.cb_mode.setToolTip("完整流程适合正式处理；预览模式适合检查匹配；仅分类适合整理图片。")
        self.cb_mode.setItemData(0, MODE_HELP_TEXT["完整流程"], Qt.ItemDataRole.ToolTipRole)
        self.cb_mode.setItemData(1, MODE_HELP_TEXT["预览模式"], Qt.ItemDataRole.ToolTipRole)
        self.cb_mode.setItemData(2, MODE_HELP_TEXT["仅分类(无Excel)"], Qt.ItemDataRole.ToolTipRole)
        opt_layout.addWidget(self.cb_mode, 1, 1)

        opt_layout.addWidget(self._field_label("裁剪方式"), 2, 0)
        self.cb_resize = RoundComboBox()
        self._setup_combo_view(self.cb_resize)
        self.cb_resize.addItems(["crop - 铺满裁剪", "stretch - 拉伸", "fit - 留白缩放"])
        self.cb_resize.setToolTip("选择主图缩放到 800×800 的方式。")
        self.cb_resize.setItemData(0, "铺满目标尺寸并裁剪超出部分（默认，适合方形展示图）", Qt.ItemDataRole.ToolTipRole)
        self.cb_resize.setItemData(1, "直接拉伸/压缩到目标尺寸（图片可能变形）", Qt.ItemDataRole.ToolTipRole)
        self.cb_resize.setItemData(2, "保持原始比例缩放，空白处填充白色（适合带留白的商品图）", Qt.ItemDataRole.ToolTipRole)
        opt_layout.addWidget(self.cb_resize, 2, 1)

        opt_layout.addWidget(self._field_label("输出格式"), 3, 0)
        self.cb_force_format = RoundComboBox()
        self._setup_combo_view(self.cb_force_format)
        self.cb_force_format.addItems(["保持原格式", "JPG", "PNG"])
        self.cb_force_format.setCurrentIndex(1)
        self.cb_force_format.setToolTip("JPG/JPEG/PNG 始终保持原格式；此选项只决定 WEBP/AVIF/BMP 等非标准格式转成 JPG 还是 PNG。")
        self.cb_force_format.setItemData(0, "保持原格式：JPG/JPEG/PNG 不转换格式；WEBP/AVIF/BMP 等非标准格式转 JPG", Qt.ItemDataRole.ToolTipRole)
        self.cb_force_format.setItemData(1, "仅将 WEBP/AVIF/BMP 等非标准格式转换为 JPG；JPG/JPEG/PNG 不互转", Qt.ItemDataRole.ToolTipRole)
        self.cb_force_format.setItemData(2, "仅将 WEBP/AVIF/BMP 等非标准格式转换为 PNG；JPG/JPEG/PNG 不互转", Qt.ItemDataRole.ToolTipRole)
        opt_layout.addWidget(self.cb_force_format, 3, 1)

        opt_layout.addWidget(self._field_label("文件处理方式"), 4, 0)
        self.cb_move = RoundComboBox()
        self._setup_combo_view(self.cb_move)
        self.cb_move.addItems(["剪切（移动源文件）", "复制（保留源文件）"])
        self.cb_move.setCurrentIndex(1)
        self.cb_move.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.cb_move.setToolTip("复制更安全，会保留分类目录中的原文件；剪切更省空间。")
        self.cb_move.setItemData(0, "匹配到的文件从分类目录移到提取目录（节省空间）", Qt.ItemDataRole.ToolTipRole)
        self.cb_move.setItemData(1, "匹配到的文件复制到提取目录，分类目录保留原文件（安全）", Qt.ItemDataRole.ToolTipRole)
        opt_layout.addWidget(self.cb_move, 4, 1)

        self.chk_open_output = QCheckBox("处理完成后打开输出目录")
        self.chk_open_output.setChecked(True)
        self.chk_open_output.setToolTip("处理完成后自动打开输出目录，方便查看结果。")
        opt_layout.addWidget(self.chk_open_output, 5, 0, 1, 2)
        top_layout.addWidget(opt_group, 1)
        main_layout.addLayout(top_layout)

        middle_layout = QHBoxLayout()
        middle_layout.setSpacing(ui_gap)

        help_group = QFrame()
        help_group.setObjectName("CardFrame")
        help_group.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._add_shadow(help_group)
        help_layout = QVBoxLayout(help_group)
        help_layout.setSpacing(12)
        help_layout.setContentsMargins(16, 16, 16, 16)
        help_layout.addWidget(self._section_title("", "使用说明"))

        help_content_layout = QVBoxLayout()
        help_content_layout.setContentsMargins(0, 0, 0, 0)
        help_content_layout.setSpacing(12)

        self.help_tabs = QTabWidget()
        self.help_tabs.setObjectName("helpTabs")
        self.help_tabs.setDocumentMode(True)
        self.help_tabs.setUsesScrollButtons(False)
        self.help_tabs.tabBar().setDrawBase(False)
        self.help_tabs.tabBar().setExpanding(True)
        section_pattern = re.compile(r'【([^】]+)】\n(.*?)(?=\n【[^】]+】|$)', re.S)
        help_sections = section_pattern.findall(UI_HELP_TEXT)
        if not help_sections:
            help_sections = [("功能说明", UI_HELP_TEXT)]

        for title, body in help_sections:
            tab_page = QWidget()
            tab_layout = QVBoxLayout(tab_page)
            tab_layout.setContentsMargins(0, 0, 0, 0)
            tab_layout.setSpacing(0)

            tab_card = QFrame()
            tab_card.setObjectName("helpTabCard")
            tab_card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            tab_card_layout = QVBoxLayout(tab_card)
            tab_card_layout.setContentsMargins(10, 10, 10, 10)

            help_text = QTextEdit()
            help_text.setObjectName("helpTabText")
            help_text.setReadOnly(True)
            help_text.setPlainText(body.strip())
            help_text.setMinimumHeight(150)
            help_text.setToolTip("快速了解软件怎么用、各个选项的区别，以及输出目录里会生成什么。")
            tab_card_layout.addWidget(help_text)

            tab_layout.addWidget(tab_card)
            self.help_tabs.addTab(tab_page, title.strip())

        if self.help_tabs.count() > 0:
            first_help_text = self.help_tabs.widget(0).findChild(QTextEdit, "helpTabText")
            if first_help_text is not None:
                self.text_help = first_help_text
        help_content_layout.addWidget(self.help_tabs, 1)

        mode_help_box = QFrame()
        mode_help_box.setObjectName("modeHelpBox")
        mode_help_box.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        mode_help_layout = QVBoxLayout(mode_help_box)
        mode_help_layout.setContentsMargins(12, 10, 12, 10)
        mode_help_layout.setSpacing(0)
        self.lbl_mode_help = QLabel()
        self.lbl_mode_help.setObjectName("modeHelpText")
        self.lbl_mode_help.setWordWrap(True)
        self.lbl_mode_help.setToolTip("这里会随处理模式变化，说明当前模式实际会做什么。")
        mode_help_layout.addWidget(self.lbl_mode_help)
        self.cb_mode.currentTextChanged.connect(self._update_mode_help)
        self._update_mode_help(self.cb_mode.currentText())
        help_content_layout.addWidget(mode_help_box)

        tip_box = QFrame()
        tip_box.setObjectName("tipBox")
        tip_box.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        tip_layout = QVBoxLayout(tip_box)
        tip_layout.setContentsMargins(12, 10, 12, 10)
        tip_layout.setSpacing(0)
        tip_label = QLabel("提示：建议先小范围测试（如行范围 2-100），确认无误后再处理全部数据。")
        tip_label.setObjectName("tipText")
        tip_label.setWordWrap(True)
        tip_layout.addWidget(tip_label)
        help_content_layout.addWidget(tip_box)
        help_layout.addLayout(help_content_layout, 1)
        middle_layout.addWidget(help_group, 5)

        right_layout = QVBoxLayout()
        right_layout.setSpacing(12)
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        self.btn_start = QPushButton("开始处理")
        self.btn_start.setObjectName("startButton")
        self.btn_start.setToolTip("按当前设置开始处理。处理期间下方日志会显示进度和结果。")
        self.btn_start.clicked.connect(self.start_process)
        self.btn_stop = QPushButton("停止处理")
        self.btn_stop.setObjectName("stopButton")
        self.btn_stop.setToolTip("请求停止当前任务。正在处理中的少量文件可能会先完成。")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop_process)
        btn_layout.addWidget(self.btn_start)
        btn_layout.addWidget(self.btn_stop)
        right_layout.addLayout(btn_layout, 0)

        log_group = QFrame()
        log_group.setObjectName("CardFrame")
        log_group.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._add_shadow(log_group)
        log_layout = QVBoxLayout(log_group)
        log_layout.setSpacing(12)
        log_layout.setContentsMargins(16, 16, 16, 16)
        log_buttons = QHBoxLayout()
        log_buttons.setSpacing(10)
        log_buttons.setContentsMargins(0, 0, 0, 0)
        log_buttons.addWidget(self._section_title("", "处理日志"))
        log_buttons.addStretch()
        self.btn_clear_log = QPushButton("清空日志")
        self.btn_clear_log.setObjectName("logToolButton")
        self.btn_clear_log.setToolTip("清空当前界面日志，不删除已保存的日志文件。")
        self.btn_clear_log.clicked.connect(self._clear_log)
        self.btn_export_log = QPushButton("导出日志")
        self.btn_export_log.setObjectName("logToolButton")
        self.btn_export_log.setToolTip("把当前界面日志另存为文本文件。")
        self.btn_export_log.clicked.connect(self._export_log)
        log_buttons.addWidget(self.btn_clear_log)
        log_buttons.addWidget(self.btn_export_log)
        log_layout.addLayout(log_buttons)
        self.text_log = QTextEdit()
        self.text_log.setReadOnly(True)
        self.text_log.setMinimumHeight(180)
        self.text_log.setToolTip("运行日志。绿色表示完成，红色表示错误，橙色表示警告，紫色表示进度。")
        self.text_log.document().setMaximumBlockCount(LOG_MAX_BLOCK_COUNT)
        log_layout.addWidget(self.text_log, 1)
        right_layout.addWidget(log_group, 1)
        middle_layout.addLayout(right_layout, 7)
        main_layout.addLayout(middle_layout, 1)

        progress_group = QFrame()
        progress_group.setObjectName("CardFrame")
        progress_group.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._add_shadow(progress_group, blur=12, y=2)
        progress_layout = QVBoxLayout(progress_group)
        progress_layout.setContentsMargins(14, 14, 14, 12)
        progress_layout.addWidget(self._section_title("", "总体进度"))
        self.progress_bar = AnimatedProgressBar()
        self.progress_bar.setToolTip("显示当前任务的大致进度。")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        progress_layout.addWidget(self.progress_bar)
        progress_info_layout = QHBoxLayout()
        self.lbl_progress_detail = QLabel("准备就绪")
        self.lbl_progress_detail.setWordWrap(False)
        self.lbl_progress_detail.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        detail_h = self.lbl_progress_detail.sizeHint().height()
        self.lbl_progress_detail.setFixedHeight(detail_h)
        self.lbl_progress_detail.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.lbl_success_count = QLabel("成功: 0")
        self.lbl_failed_count = QLabel("失败: 0")
        self.lbl_skipped_count = QLabel("跳过: 0")
        for label in (self.lbl_progress_detail, self.lbl_success_count, self.lbl_failed_count, self.lbl_skipped_count):
            label.setStyleSheet(f"color: {self._colors['muted']};")
        progress_info_layout.addWidget(self.lbl_progress_detail, 3)
        progress_info_layout.addWidget(self.lbl_success_count)
        progress_info_layout.addWidget(self.lbl_failed_count)
        progress_info_layout.addWidget(self.lbl_skipped_count)
        progress_layout.addLayout(progress_info_layout)
        main_layout.addWidget(progress_group)

        self._apply_app_style()

        # 设置按钮图标（图标路径在 _apply_app_style 中创建）
        # 初始状态：开始按钮启用（白色图标），停止按钮禁用（灰色图标）
        if hasattr(self, '_play_ico_path') and self._play_ico_path:
            self.btn_start.setIcon(QIcon(self._play_ico_path))
            self.btn_start.setIconSize(QSize(20, 20))
        if hasattr(self, '_stop_ico_dis_path') and self._stop_ico_dis_path:
            self.btn_stop.setIcon(QIcon(self._stop_ico_dis_path))
            self.btn_stop.setIconSize(QSize(18, 18))
        elif hasattr(self, '_stop_ico_path') and self._stop_ico_path:
            self.btn_stop.setIcon(QIcon(self._stop_ico_path))
            self.btn_stop.setIconSize(QSize(18, 18))

    def _clear_log(self):
        self.text_log.clear()
        self.progress_bar.setValue(0)
        self.lbl_progress_detail.setText("日志已清空")
        self.lbl_success_count.setText("成功: 0")
        self.lbl_failed_count.setText("失败: 0")
        self.lbl_skipped_count.setText("跳过: 0")

    def _export_log(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "导出日志", "处理日志.txt", "Text Files (*.txt);;All Files (*)"
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.text_log.toPlainText())
            info_box(self, "导出完成", f"日志已导出到:\n{path}")
        except Exception as e:
            QMessageBox.warning(self, "导出失败", f"无法导出日志:\n{e}")

    def _open_output_dir(self):
        output = self._last_output_dir or self.le_output.text().strip()
        if not output:
            return
        try:
            if sys.platform == 'win32':
                os.startfile(output)
            else:
                import subprocess
                subprocess.Popen(['open' if sys.platform == 'darwin' else 'xdg-open', output])
        except Exception as e:
            print(f"[警告] 打开输出目录失败: {e}")

    def _browse_dir(self, line_edit, is_source=False):
        path = QFileDialog.getExistingDirectory(self, "选择文件夹")
        if path:
            path = os.path.normpath(path)
            line_edit.setText(path)
            if is_source and not self.le_output.text().strip():
                self.le_output.setText(suggest_output_dir(path))

    def _browse_excel(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择 Excel 文件", "", "Excel Files (*.xlsx *.xlsm)")
        if path:
            self.le_excel.setText(os.path.normpath(path))
            self._debounce_header_preview()

    def _debounce_header_preview(self):
        """防抖：用户停止输入 200ms 后再读取 Excel"""
        self._debounce_timer.start()

    def _do_update_header_preview(self):
        """启动后台线程读取 Excel 表头，并更新列下拉。"""
        excel_path = self.le_excel.text().strip()
        sheet_name = self.le_sheet.text().strip() or None
        col_text = self.cb_col.currentData() or "A"

        if not excel_path:
            self.lbl_header_preview.setText("表头：(未选择 Excel)")
            self.lbl_header_preview.setStyleSheet(f"color: {self._colors['muted']};")
            return

        if not col_text or not re.match(r'^[A-Z]+$', col_text):
            self.lbl_header_preview.setText("表头：(列输入有误)")
            self.lbl_header_preview.setStyleSheet(f"color: {self._colors['red']}; font-weight: bold;")
            return

        self.lbl_header_preview.setText("表头：(读取中...)")
        self.lbl_header_preview.setStyleSheet(f"color: {self._colors['muted']}; font-style: italic;")
        worker = ExcelHeaderWorker(excel_path, sheet_name, col_text)
        self.header_worker = worker
        self.header_workers.append(worker)
        worker.loaded.connect(self._on_excel_headers_loaded)
        worker.failed.connect(self._on_excel_headers_failed)
        worker.finished.connect(lambda w=worker: self._cleanup_excel_worker(w))
        worker.start()

    def _cleanup_excel_worker(self, worker):
        if worker in self.header_workers:
            self.header_workers.remove(worker)
        if self.header_worker is worker:
            self.header_worker = self.header_workers[-1] if self.header_workers else None

    def _is_current_excel_request(self, excel_path, sheet_name, col_text):
        return (
            excel_path == self.le_excel.text().strip()
            and sheet_name == (self.le_sheet.text().strip() or "")
            and col_text == (self.cb_col.currentData() or "A")
        )

    def _on_excel_headers_loaded(self, excel_path, sheet_name, col_text, headers, cell_val):
        if not self._is_current_excel_request(excel_path, sheet_name, col_text):
            return
        self._populate_col_combo(headers)
        current_col = self.cb_col.currentData() or "A"
        if current_col != col_text:
            self._debounce_header_preview()
            return
        if cell_val is not None:
            self.lbl_header_preview.setText(f"表头：{str(cell_val).strip()}")
            self.lbl_header_preview.setStyleSheet(f"color: {self._colors['green']}; font-weight: bold;")
        else:
            self.lbl_header_preview.setText("表头：(该列第一行为空)")
            self.lbl_header_preview.setStyleSheet(f"color: {self._colors.get('tip_text', '#F57C00')};")

    def _on_excel_headers_failed(self, excel_path, sheet_name, col_text, error):
        if not self._is_current_excel_request(excel_path, sheet_name, col_text):
            return
        self._populate_col_combo([])
        self.lbl_header_preview.setText(f"表头：(读取失败: {error})")
        self.lbl_header_preview.setStyleSheet(f"color: {self._colors['red']}; font-weight: bold;")

    def _advance_progress(self, text):
        """从日志文本中提取进度值并更新进度条"""
        m = re.search(r'进度.*?(\d+)%', text)
        if m:
            self.progress_bar.setValue(int(m.group(1)))
            return
        m = re.search(r'进度.*?(\d+)/(\d+)', text)
        if m:
            cur = int(m.group(1))
            total = int(m.group(2))
            if total > 0:
                self.progress_bar.setValue(int(cur / total * 100))
            return

    def _update_stats_from_log(self, text):
        """从日志消息中提取统计计数并更新界面标签。

        统计标签与日志格式的约定集中在此方法中，避免散落各处。
        支持显式 STAT 标签和遗留关键词两种格式。
        """
        if not hasattr(self, 'lbl_success_count'):
            return

        # 优先匹配显式 STAT 标签，格式固定不受日志措辞影响
        m = re.search(r'\[STAT success=(\d+) failed=(\d+) skipped=(\d+)\]', text)
        if m:
            self.lbl_success_count.setText(f"成功: {m.group(1)}")
            self.lbl_failed_count.setText(f"失败: {m.group(2)}")
            self.lbl_skipped_count.setText(f"跳过: {m.group(3)}")
            return

        # 遗留关键词匹配（保持与现有日志格式兼容）
        stat_patterns = [
            ('lbl_success_count', r'成功[:：]\s*(\d+)', '成功'),
            ('lbl_failed_count',  r'失败[:：]?\s*(\d+)', '失败'),
            ('lbl_skipped_count', r'跳过[:：]?\s*(\d+)', '跳过'),
        ]
        for attr, pattern, label in stat_patterns:
            m = re.search(pattern, text)
            if m:
                getattr(self, attr).setText(f"{label}: {m.group(1)}")

    def append_log(self, text):
        """追加彩色日志并更新进度条"""
        self._advance_progress(text)

        cursor = self.text_log.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        fmt = QTextCharFormat()
        is_dark = self._colors['window'] == '#111827'
        if "[错误]" in text or "[失败]" in text or "异常" in text:
            fmt.setForeground(QColor("#F87171" if is_dark else "#D32F2F"))
            fmt.setFontWeight(QFont.Weight.Bold)
        elif "[警告]" in text or "[提醒]" in text or "手动处理" in text:
            fmt.setForeground(QColor("#FBBF24" if is_dark else "#F57C00"))
        elif "[完成]" in text or "[结果]" in text or "全部处理完成" in text:
            fmt.setForeground(QColor("#4ADE80" if is_dark else "#388E3C"))
            fmt.setFontWeight(QFont.Weight.Bold)
        elif "[停止]" in text or "[预览]" in text:
            fmt.setForeground(QColor("#60A5FA" if is_dark else "#1976D2"))
        elif "进度" in text:
            fmt.setForeground(QColor("#C084FC" if is_dark else "#6A1B9A"))
        elif "[步骤" in text:
            fmt.setForeground(QColor("#93C5FD" if is_dark else "#5C6BC0"))
        else:
            fmt.setForeground(QColor(self._colors['text']))

        cursor.setCharFormat(fmt)
        cursor.insertText(text)

        self.text_log.setTextCursor(cursor)
        self.text_log.ensureCursorVisible()
        if hasattr(self, 'lbl_progress_detail') and text.strip():
            single_line = ' '.join(text.strip().split())
            self.lbl_progress_detail.setText(single_line)
        self._update_stats_from_log(text)

    def _update_mode_help(self, mode_name):
        """显示当前处理模式的说明，避免只靠下拉项猜含义。"""
        self.lbl_mode_help.setText(MODE_HELP_TEXT.get(mode_name, ""))

    def _set_processing_controls_enabled(self, enabled):
        widgets = [
            self.le_source,
            self.le_output,
            self.le_excel,
            self.cb_col,
            self.le_sheet,
            self.le_start,
            self.le_end,
            self.cb_mode,
            self.cb_resize,
            self.cb_force_format,
            self.cb_move,
            self.chk_open_output,
        ]
        for widget in widgets:
            widget.setEnabled(enabled)
        if enabled:
            self._update_excel_params_enabled()

    def start_process(self):
        source = self.le_source.text().strip()
        output = self.le_output.text().strip()

        if not source:
            QMessageBox.warning(self, "警告", "请选择源文件夹！")
            return
        if not output:
            QMessageBox.warning(self, "警告", "请选择输出目录！")
            return

        source_norm = os.path.normpath(source)
        output_norm = os.path.normpath(output)
        if source_norm == output_norm:
            output = suggest_output_dir(source_norm)
            self.le_output.setText(output)
            output_norm = os.path.normpath(output)
            print(f"[提示] 输出目录不能与源目录相同，已自动改为: {output}\n")
        try:
            validate_output_dir(source_norm, output_norm)
        except ValueError as e:
            QMessageBox.warning(self, "警告", str(e))
            return
        self._last_output_dir = output

        col_text = self.cb_col.currentData() or "A"

        mode_map = {"完整流程": 1, "预览模式": 2, "仅分类(无Excel)": 4}
        mode_val = mode_map.get(self.cb_mode.currentText(), 1)
        resize_map = {"crop - 铺满裁剪": "crop", "stretch - 拉伸": "stretch", "fit - 留白缩放": "fit"}
        resize_val = resize_map.get(self.cb_resize.currentText(), "crop")

        start_row = self.le_start.text().strip()
        start_row = int(start_row) if start_row.isdigit() else None

        end_row = self.le_end.text().strip()
        end_row = int(end_row) if end_row.isdigit() else None

        copy_mode = (self.cb_move.currentIndex() == 1)  # True=复制, False=剪切

        force_format_map = {"保持原格式": None, "JPG": "jpg", "PNG": "png"}
        force_format_val = force_format_map.get(self.cb_force_format.currentText(), None)

        kwargs = {
            'source_dir': source,
            'output_root': output,
            'mode': mode_val,
            'excel_path': self.le_excel.text().strip() or None,
            'col': col_text or 'A',
            'sheet_name': self.le_sheet.text().strip() or None,
            'start_row': start_row,
            'end_row': end_row,
            'force_format': force_format_val,
            'resize_mode': resize_val,
            'stop_event': self.stop_event,
            'copy_mode': copy_mode,
        }

        self.text_log.clear()
        self.progress_bar.setFormat("%p%")
        self.progress_bar.setValue(0)
        self.lbl_progress_detail.setText("正在准备处理...")
        self.lbl_success_count.setText("成功: 0")
        self.lbl_failed_count.setText("失败: 0")
        self.lbl_skipped_count.setText("跳过: 0")
        self.stop_event.clear()

        self._set_processing_controls_enabled(False)
        self.btn_start.setEnabled(False)
        self.btn_start.setIcon(QIcon(self._play_ico_dis_path) if hasattr(self, '_play_ico_dis_path') and self._play_ico_dis_path else QIcon())
        self.btn_start.setIconSize(QSize(20, 20))
        self.btn_stop.setEnabled(True)
        self.btn_stop.setIcon(QIcon(self._stop_ico_path) if hasattr(self, '_stop_ico_path') and self._stop_ico_path else QIcon())
        self.btn_stop.setIconSize(QSize(18, 18))

        self.worker = WorkerThread(kwargs)
        self.worker.finished_signal.connect(self._process_finished)
        self.worker.start()
        self.progress_bar.start_animation()

    def stop_process(self):
        if self.worker and self.worker.isRunning():
            reply = question_box(self, "确认停止", "当前任务正在处理图片。\n\n确定要停止当前任务吗？")
            if reply != QMessageBox.StandardButton.Yes:
                return
            print("\n>>> 正在发送停止信号，请稍等...")
            self.stop_event.set()

    def _process_finished(self):
        self.progress_bar.stop_animation()
        self._set_processing_controls_enabled(True)
        self.btn_start.setEnabled(True)
        self.btn_start.setIcon(QIcon(self._play_ico_path) if hasattr(self, '_play_ico_path') and self._play_ico_path else QIcon())
        self.btn_start.setIconSize(QSize(20, 20))
        self.btn_stop.setEnabled(False)
        self.btn_stop.setIcon(QIcon(self._stop_ico_dis_path) if hasattr(self, '_stop_ico_dis_path') and self._stop_ico_dis_path else QIcon())
        self.btn_stop.setIconSize(QSize(18, 18))

        completed = not self.stop_event.is_set()
        if completed:
            self.progress_bar.setValue(100)
            self.lbl_progress_detail.setText("处理完成")
        else:
            self.progress_bar.setFormat("已停止 %p%")
            self.lbl_progress_detail.setText("任务已停止")

        print("\n[系统] 后台任务已结束。")
        QApplication.alert(self, 0)
        if completed:
            try:
                if sys.platform == 'win32':
                    winsound.MessageBeep(winsound.MB_ICONASTERISK)
                else:
                    QApplication.beep()
            except Exception:
                QApplication.beep()
            if hasattr(self, 'chk_open_output') and self.chk_open_output.isChecked():
                self._open_output_dir()
            info_box(self, "处理完成", "全部处理完成！\n\n请在输出目录查看处理结果。")

    def _restore_stdout(self):
        if getattr(self, '_stdout_stream', None) is not None and sys.stdout is self._stdout_stream:
            sys.stdout = self._old_stdout
        self._stdout_stream = None

    def closeEvent(self, event):
        # 清理临时图标文件
        for p in _TEMP_ICON_PATHS:
            try:
                os.remove(p)
            except OSError:
                pass
        _TEMP_ICON_PATHS.clear()
        for header_worker in list(getattr(self, 'header_workers', [])):
            if header_worker.isRunning():
                header_worker.requestInterruption()
                header_worker.wait(1000)
        if self.worker and self.worker.isRunning():
            reply = QMessageBox.question(
                self, '确认退出',
                '当前有图片正在处理中，强制退出可能会导致部分文件处理中断。\n\n确定要中止并退出吗？',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.Yes:
                print("\n[系统] 正在中止任务并准备退出...")
                self.stop_event.set()
                self.worker.wait(5000)
                if self.worker.isRunning():
                    QMessageBox.warning(self, "仍在处理中", "后台任务仍未停止，请稍后再退出。")
                    event.ignore()
                    return
                self._restore_stdout()
                event.accept()
            else:
                event.ignore()
        else:
            self._restore_stdout()
            event.accept()

