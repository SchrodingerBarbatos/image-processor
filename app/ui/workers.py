# -*- coding: utf-8 -*-
"""QThread 工作线程"""

from PySide6.QtCore import QThread, Signal
from app.core.pipeline import run_all
from app.core.excel_reader import read_excel_preview


class WorkerThread(QThread):
    """后台工作线程"""
    finished_signal = Signal()

    def __init__(self, kwargs):
        super().__init__()
        self.kwargs = kwargs

    def run(self):
        try:
            run_all(**self.kwargs)
        except Exception as e:
            print(f"\n[错误] {e}")
            import traceback
            print(traceback.format_exc())
        finally:
            self.finished_signal.emit()


class ExcelHeaderWorker(QThread):
    """后台读取 Excel 表头，避免大文件卡住 UI。"""
    loaded = Signal(str, str, str, list, object)
    failed = Signal(str, str, str, str)

    def __init__(self, excel_path, sheet_name, col_text):
        super().__init__()
        self.excel_path = excel_path
        self.sheet_name = sheet_name
        self.col_text = col_text

    def run(self):
        try:
            headers, cell_val = read_excel_preview(self.excel_path, self.sheet_name, self.col_text)
            self.loaded.emit(self.excel_path, self.sheet_name or "", self.col_text, headers, cell_val)
        except Exception as e:
            self.failed.emit(self.excel_path, self.sheet_name or "", self.col_text, str(e))


