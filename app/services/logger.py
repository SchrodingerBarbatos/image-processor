# -*- coding: utf-8 -*-
"""日志写入与缓冲"""

import os
import sys
import datetime
import threading

from app.constants import LOG_FLUSH_INTERVAL


class LogWriter:
    def __init__(self, log_path=None, gui_callback=None):
        self.file = None
        self.gui_callback = gui_callback
        self._flush_counter = 0
        self._lock = threading.Lock()
        if log_path:
            d = os.path.dirname(log_path)
            if d:
                os.makedirs(d, exist_ok=True)
            try:
                self.file = open(log_path, 'w', encoding='utf-8')
            except OSError as e:
                print(f"[警告] 日志文件无法创建，将只输出到界面/控制台: {e}")

    def write(self, msg, end='\n'):
        with self._lock:
            ts = datetime.datetime.now().strftime('%H:%M:%S')
            line = f'[{ts}] {msg}'
            sys.stdout.write(line + end)
            if self.file:
                self.file.write(line + '\n')
                self._flush_counter += 1
                if self._flush_counter >= LOG_FLUSH_INTERVAL:
                    self.file.flush()
                    self._flush_counter = 0
        if self.gui_callback and threading.current_thread() is threading.main_thread():
            self.gui_callback(line)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False

    def close(self):
        with self._lock:
            if self.file:
                self.file.flush()
                self.file.close()
                self.file = None
