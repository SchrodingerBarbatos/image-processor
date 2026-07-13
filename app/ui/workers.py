# -*- coding: utf-8 -*-
"""QThread 工作线程"""

from PySide6.QtCore import QThread, Signal
from app.core.pipeline import run_all
from app.core.excel_reader import read_excel_preview


class WorkerThread(QThread):
    """后台工作线程。finished_signal 参数为状态: completed / failed / stopped。"""
    finished_signal = Signal(str)

    def __init__(self, kwargs):
        super().__init__()
        self.kwargs = kwargs

    def run(self):
        status = 'failed'
        try:
            result = run_all(**self.kwargs)
            if result in ('completed', 'failed', 'stopped'):
                status = result
            elif self.kwargs.get('stop_event') is not None and self.kwargs['stop_event'].is_set():
                status = 'stopped'
            else:
                status = 'completed' if result is None else 'failed'
        except Exception as e:
            print(f"\n[错误] {e}")
            import traceback
            print(traceback.format_exc())
            status = 'failed'
        finally:
            self.finished_signal.emit(status)


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
            if self.isInterruptionRequested():
                return
            headers, cell_val = read_excel_preview(self.excel_path, self.sheet_name, self.col_text)
            if self.isInterruptionRequested():
                return
            self.loaded.emit(self.excel_path, self.sheet_name or "", self.col_text, headers, cell_val)
        except Exception as e:
            if self.isInterruptionRequested():
                return
            self.failed.emit(self.excel_path, self.sheet_name or "", self.col_text, str(e))
