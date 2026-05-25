# -*- coding: utf-8 -*-
"""QSS 样式 & 颜色常量"""

import sys

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from app.services.icons import _darken


def get_theme_colors():
    """根据系统调色板生成浅色/暗色可读配色。"""
    app = QApplication.instance()
    is_dark = False
    if app:
        is_dark = app.palette().color(QPalette.ColorRole.Window).lightness() < 128
    if sys.platform == 'win32':
        try:
            import winreg
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
            ) as key:
                is_dark = winreg.QueryValueEx(key, "AppsUseLightTheme")[0] == 0
        except Exception:
            pass
    if is_dark:
        return {
            'window': '#111827',
            'card': '#1F2937',
            'card2': '#263244',
            'border': '#374151',
            'text': '#F3F4F6',
            'muted': '#AAB2BD',
            'input': '#111827',
            'input_border': '#6B7280',
            'accent': '#60A5FA',
            'accent_hover': '#3B82F6',
            'green': '#16A34A',
            'green_hover': '#15803D',
            'red': '#EF4444',
            'red_hover': '#DC2626',
            'log': '#0B1220',
            'help': '#152219',
            'tip': '#2A2112',
            'tip_text': '#FBBF24',
            'tip_border': '#D97706',
            'disabled_card': '#161E2A',
            'disabled_border': '#374151',
            'shadow': QColor(0, 0, 0, 45),
        }
    return {
        'window': '#F6F8FB',
        'card': '#FFFFFF',
        'card2': '#F8FAFD',
        'border': '#E4E8EF',
        'text': '#111827',
        'muted': '#6B7280',
        'input': '#FFFFFF',
        'input_border': '#D7DDE7',
        'accent': '#0078D4',
        'accent_hover': '#106EBE',
        'green': '#0EA348',
        'green_hover': '#098A37',
        'red': '#FF2D30',
        'red_hover': '#E52225',
        'log': '#FFFFFF',
        'help': '#F4FBF5',
        'tip': '#FFF8E8',
        'tip_text': '#B45309',
        'tip_border': '#F5C16C',
        'disabled_card': '#F0F3F8',
        'disabled_border': '#D6DCE7',
        'shadow': QColor(15, 23, 42, 18),
    }


def build_stylesheet(c, checkbox_checked_css, checkbox_unchecked_css, arrow_ico):
    """根据主题颜色和图标路径生成完整 QSS 样式表。"""
    return f"""
        QMainWindow, QWidget {{
            background: {c['window']};
            color: {c['text']};
        }}
        QFrame#CardFrame {{
            background: {c['card']};
            border: 1px solid {c['border']};
            border-radius: 8px;
        }}
        QLabel {{
            color: {c['text']};
            background: transparent;
        }}
        QLabel:disabled {{
            color: {c['muted']};
        }}
        QToolTip {{
            background: {c['card']};
            color: {c['text']};
            border: 1px solid {c['border']};
            border-radius: 4px;
            padding: 4px 8px;
        }}
        QLabel#sectionTitle {{
            color: {c['text']};
            background: transparent;
            font-size: 11pt;
            font-weight: 700;
            padding: 0 0 8px 0;
            border-bottom: 1px solid {c['border']};
        }}
        QLabel#hintLabel {{
            color: {c['muted']};
            font-size: 9pt;
        }}
        QLabel#fieldLabel {{
            font-size: 11pt;
            font-weight: 600;
        }}
        QLineEdit {{
            background: {c['input']};
            color: {c['text']};
            border: 2px solid {c['input_border']};
            border-radius: 6px;
            min-height: 34px;
            max-height: 34px;
            padding: 0px 9px;
        }}
        QComboBox {{
            background: {c['input']};
            color: {c['text']};
            border: 2px solid {c['input_border']};
            border-radius: 6px;
            min-height: 34px;
            max-height: 34px;
            padding: 0px 25px 0px 9px;
        }}
        QLineEdit:focus, QComboBox:focus {{
            border-color: {c['accent']};
        }}
        QLineEdit:hover, QComboBox:hover {{
            border-color: {c['accent']};
        }}
        QLineEdit:disabled, QComboBox:disabled {{
            color: {c['muted']};
            background: {c['card2']};
            border-color: {c['border']};
        }}
        QComboBox::drop-down {{
            subcontrol-origin: padding;
            subcontrol-position: top right;
            right: 10px;
            width: 14px;
            border: none;
            background: transparent;
        }}
        QComboBox::down-arrow {{
            image: url({arrow_ico});
            width: 10px;
            height: 7px;
        }}
        QListView#roundComboView {{
            background: {c['input']};
            color: {c['text']};
            border: 1px solid {c['input_border']};
            border-radius: 8px;
            outline: none;
            padding: 4px;
        }}
        QListView#roundComboView::item {{
            min-height: 26px;
            margin: 2px 4px;
            padding: 2px 8px;
            border-radius: 6px;
        }}
        QListView#roundComboView::item:selected {{
            background: {c['accent']};
            color: #FFFFFF;
        }}
        QPushButton {{
            background: {c['card2']};
            color: {c['text']};
            border: 2px solid {c['border']};
            border-radius: 7px;
            min-height: 34px;
            max-height: 34px;
            padding: 0px 11px;
        }}
        QPushButton:hover {{
            border-color: {c['accent']};
            background: {c['input']};
        }}
        QPushButton:pressed {{
            background: {c['border']};
            border-color: {c['muted']};
        }}
        QPushButton:disabled {{
            color: {c['muted']};
            background: {c['card2']};
            border-color: {c['border']};
        }}
        QPushButton#startButton {{
            background: {c['green']};
            border-color: {c['green_hover']};
            color: white;
            font-size: 13pt;
            font-weight: 800;
            min-height: 46px;
            max-height: 46px;
            border-radius: 8px;
            padding: 0px 16px;
        }}
        QPushButton#startButton:hover {{
            background: {c['green_hover']};
        }}
        QPushButton#startButton:pressed {{
            background: {_darken(c['green_hover'], 0.8)};
        }}
        QPushButton#startButton:disabled {{
            background: {c['card2']};
            border-color: {c['border']};
            color: {c['muted']};
        }}
        QPushButton#stopButton {{
            background: {c['red']};
            border-color: {c['red_hover']};
            color: white;
            font-size: 13pt;
            font-weight: 800;
            min-height: 46px;
            max-height: 46px;
            border-radius: 8px;
            padding: 0px 16px;
        }}
        QPushButton#stopButton:hover {{
            background: {c['red_hover']};
        }}
        QPushButton#stopButton:pressed {{
            background: {_darken(c['red_hover'], 0.8)};
        }}
        QPushButton#stopButton:disabled {{
            background: {c['card2']};
            border-color: {c['border']};
            color: {c['muted']};
        }}
        QPushButton#logToolButton {{
            min-height: 34px;
            max-height: 34px;
            padding: 0px 12px;
        }}
        QTextEdit {{
            background: {c['log']};
            color: {c['text']};
            border: 1px solid {c['border']};
            border-radius: 8px;
            padding: 10px;
            font-family: Consolas, "Courier New", monospace;
            font-size: 10pt;
        }}
        QTextEdit#helpText {{
            background: transparent;
            border: none;
        }}
        QFrame#helpContainer {{
            background: {c['card2']};
            border: 1px solid {c['border']};
            border-radius: 8px;
        }}
        QTabWidget#helpTabs::pane {{
            border: none;
            background: transparent;
            margin-top: 0px;
        }}
        QTabWidget#helpTabs QWidget {{
            background: transparent;
        }}
        QTabWidget#helpTabs QTabBar {{
            background: transparent;
        }}
        QTabWidget#helpTabs QTabBar::tab {{
            background: {c['card2']};
            border: 1px solid {c['border']};
            color: {c['muted']};
            padding: 7px 12px;
            min-width: 84px;
            font-weight: 600;
            border-top-left-radius: 8px;
            border-top-right-radius: 8px;
            border-bottom-left-radius: 0px;
            border-bottom-right-radius: 0px;
            margin-right: 0px;
            margin-bottom: 0px;
        }}
        QTabWidget#helpTabs QTabBar::tab:selected {{
            background: {c['card']};
            color: {c['text']};
            border-color: {c['input_border']};
            border-bottom-color: {c['card']};
            margin-bottom: -1px;
        }}
        QFrame#helpTabCard {{
            background: {c['card']};
            border: 1px solid {c['input_border']};
            border-top: none;
            border-top-left-radius: 0px;
            border-top-right-radius: 0px;
            border-bottom-left-radius: 8px;
            border-bottom-right-radius: 8px;
        }}
        QTextEdit#helpTabText {{
            background: {c['card']};
            border: none;
            padding: 10px;
        }}
        QFrame#modeHelpBox {{
            background: {c['help']};
            border: 1px solid {c['border']};
            border-radius: 8px;
        }}
        QLabel#modeHelpText {{
            color: {c['green']};
            background: transparent;
        }}
        QFrame#tipBox {{
            background: {c['tip']};
            border: 1px solid {c['tip_border']};
            border-radius: 8px;
        }}
        QLabel#tipText {{
            color: {c['tip_text']};
            background: transparent;
        }}
        QProgressBar {{
            background: {c['border']};
            color: {c['text']};
            border: none;
            border-radius: 8px;
            min-height: 20px;
            text-align: center;
            font-weight: 700;
        }}
        QProgressBar::chunk {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {c['green']}, stop:1 {_darken(c['green'], 0.78)});
            border-radius: 8px;
        }}
        QCheckBox {{
            color: {c['text']};
            background: transparent;
            spacing: 8px;
            min-height: 40px;
            max-height: 40px;
        }}
        QCheckBox::indicator {{
            width: 20px;
            height: 20px;
            border: none;
            background: transparent;
        }}
        QCheckBox::indicator:unchecked {{
            {checkbox_unchecked_css}
        }}
        QCheckBox::indicator:checked {{
            {checkbox_checked_css}
        }}
        QScrollBar:vertical {{
            background: transparent;
            width: 10px;
            margin: 4px 2px 4px 2px;
        }}
        QScrollBar::handle:vertical {{
            background: {c['input_border']};
            border-radius: 5px;
            min-height: 28px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {c['muted']};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
        QScrollBar:horizontal {{
            background: transparent;
            height: 10px;
            margin: 2px 4px 2px 4px;
        }}
        QScrollBar::handle:horizontal {{
            background: {c['input_border']};
            border-radius: 5px;
            min-width: 28px;
        }}
        QScrollBar::handle:horizontal:hover {{
            background: {c['muted']};
        }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            width: 0px;
        }}
    """
