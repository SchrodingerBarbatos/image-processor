# -*- coding: utf-8 -*-
"""自定义 Qt 控件"""

import os
from PySide6.QtWidgets import QLineEdit, QComboBox, QProgressBar, QListView, QSizePolicy
from PySide6.QtCore import Qt, QObject, Signal, QTimer, QSize, QRectF
from PySide6.QtGui import QPainter, QColor, QLinearGradient, QPainterPath

from app.constants import SHIMMER_INTERVAL_MS, SHIMMER_STEP, SHIMMER_BAND_WIDTH

class EmittingStream(QObject):
    """将 print 输出重定向为 Qt 信号"""
    textWritten = Signal(str)

    def write(self, text):
        self.textWritten.emit(str(text))

    def flush(self):
        pass

    def isatty(self):
        return False


class DragLineEdit(QLineEdit):
    """支持把文件或文件夹拖到输入框里自动填路径。拖入时高亮边框提示。"""
    _accent_color = '#60A5FA'  # 默认值，由 _apply_app_style 覆盖

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet(
                f"background: palette(base); border: 2px solid {DragLineEdit._accent_color}; "
                "border-radius: 6px; padding: 0px 9px;"
            )
        else:
            super().dragEnterEvent(event)

    def dragLeaveEvent(self, event):
        self.setStyleSheet("")
        event.accept()

    def dropEvent(self, event):
        self.setStyleSheet("")
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if path:
                self.setText(os.path.normpath(path))
                event.acceptProposedAction()
                return
        super().dropEvent(event)


class RoundComboBox(QComboBox):
    """支持圆角透明弹窗背景的下拉框。"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._popup_chrome_applied = False

    def showPopup(self):
        # 1. 必须在系统绘制弹窗前设置透明属性，否则会导致全黑Bug
        if not self._popup_chrome_applied:
            view = self.view()
            if view:
                container = view.parentWidget()
                if container:
                    container.setObjectName("comboPopupContainer")
                    container.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
                    container.setWindowFlags(
                        Qt.WindowType.Popup
                        | Qt.WindowType.FramelessWindowHint
                        | Qt.WindowType.NoDropShadowWindowHint
                    )
                    # 用 ID 选择器只让容器自身透明，不能无选择器写样式
                    # 否则会级联覆盖子控件 QListView 的背景和边框
                    container.setStyleSheet(
                        "#comboPopupContainer { background: transparent; border: none; }"
                    )
            self._popup_chrome_applied = True
            
        # 2. 属性设置好之后，再调用系统的显示弹窗方法
        super().showPopup()


class AnimatedProgressBar(QProgressBar):
    """进度条，带微妙的流光效果。"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._shimmer_x = -1.0
        self._timer = QTimer(self)
        self._timer.setInterval(SHIMMER_INTERVAL_MS)
        self._timer.timeout.connect(self._tick)

    def _tick(self):
        self._shimmer_x += SHIMMER_STEP
        if self._shimmer_x > 2.0:
            self._shimmer_x = -0.5
        self.update()

    def start_animation(self):
        self._shimmer_x = -0.5
        self._timer.start()

    def stop_animation(self):
        self._timer.stop()
        self._shimmer_x = -1.0
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.maximum() == self.minimum() or self._shimmer_x < -0.5:
            return
        val = (self.value() - self.minimum()) / max(1, self.maximum() - self.minimum())
        if val <= 0:
            return
        fill_w = int(self.width() * val)
        if fill_w <= 0:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # 裁剪到填充区域（圆角与进度条外部一致）
        clip_path = QPainterPath()
        clip_path.addRoundedRect(QRectF(self.rect()), 8, 8)
        painter.setClipPath(clip_path)
        painter.setClipRect(0, 0, fill_w, self.height(), Qt.ClipOperation.IntersectClip)

        # 绘制流光条纹
        band_w = SHIMMER_BAND_WIDTH
        sx = fill_w * self._shimmer_x - band_w / 2
        grad = QLinearGradient(sx, 0, sx + band_w, 0)
        grad.setColorAt(0, QColor(255, 255, 255, 0))
        grad.setColorAt(0.5, QColor(255, 255, 255, 40))
        grad.setColorAt(1, QColor(255, 255, 255, 0))
        painter.fillRect(QRectF(sx, 0, band_w, self.height()), grad)
        painter.end()


