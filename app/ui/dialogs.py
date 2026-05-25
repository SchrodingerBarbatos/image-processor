# -*- coding: utf-8 -*-
"""对话框 / 消息提示辅助函数"""

from PySide6.QtWidgets import QMessageBox


def center_message_box(box, parent):
    """将消息框居中于父窗口。"""
    box.adjustSize()
    center = parent.frameGeometry().center()
    box.move(center.x() - box.width() // 2, center.y() - box.height() // 2)


def question_box(parent, title, text):
    """显示是/否确认对话框，返回 QMessageBox.StandardButton。"""
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Question)
    box.setWindowTitle(title)
    box.setText(text)
    box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
    box.setDefaultButton(QMessageBox.StandardButton.No)
    center_message_box(box, parent)
    return box.exec()


def info_box(parent, title, text):
    """显示信息提示对话框。"""
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Information)
    box.setWindowTitle(title)
    box.setText(text)
    box.setStandardButtons(QMessageBox.StandardButton.Ok)
    box.setDefaultButton(QMessageBox.StandardButton.Ok)
    center_message_box(box, parent)
    return box.exec()
