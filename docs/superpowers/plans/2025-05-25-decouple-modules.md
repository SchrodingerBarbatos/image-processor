# 模块化解耦 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 3077 行单文件 `barcode_image_mover_exe.py` 拆分为分层包结构，使每个模块职责单一、可独立测试和修改。

**Architecture:** 三层分离 — `app/core/` 纯业务逻辑零 PySide6 依赖，`app/ui/` 纯界面 PySide6 依赖只在此层，`app/services/` 横切服务（日志/图标）。入口文件 `barcode_image_mover_exe.py` 缩减为仅 `main()` 函数。

**Tech Stack:** Python 3, PySide6, Pillow, openpyxl, PyInstaller

**约束：**
- 测试文件 `tests/test_core_regressions.py` 使用 `import barcode_image_mover_exe as app`，迁移期间需保持兼容
- PyInstaller 打包入口保持为 `barcode_image_mover_exe.py`
- core 层函数签名只使用 Python 标准库类型

---

## 文件结构

```
图片处理/
├── app/
│   ├── __init__.py
│   ├── constants.py          # 全局常量（唯一来源）
│   │
│   ├── core/                 # 纯业务逻辑 — 零 UI 依赖
│   │   ├── __init__.py
│   │   ├── pipeline.py       # run_all 流程编排
│   │   ├── classifier.py     # step1/step2: 图片分类（主图/详情图）
│   │   ├── excel_reader.py   # step3: Excel 读取 & 条码解析
│   │   ├── matcher.py        # step4: 条码匹配 & 文件提取
│   │   ├── image_processor.py# step6/step7: 图片缩放/压缩/格式转换
│   │   ├── packager.py       # step8: ZIP 分卷打包
│   │   └── file_ops.py       # 文件复制/移动/清理等通用操作
│   │
│   ├── ui/                   # 纯界面 — PySide6 依赖只在此层
│   │   ├── __init__.py
│   │   ├── main_window.py    # 主窗口布局 & 信号连接
│   │   ├── widgets.py        # 自定义控件
│   │   ├── workers.py        # QThread 子类
│   │   ├── styles.py         # QSS 样式 & 颜色常量
│   │   └── dialogs.py        # 对话框 / 帮助面板
│   │
│   └── services/              # 横切服务
│       ├── __init__.py
│       ├── logger.py          # LogWriter + 日志缓冲/刷新
│       └── icons.py           # SVG 图标生成 & 临时文件管理
│
├── tests/
├── barcode_image_mover_exe.py # 入口文件（仅 main()）
└── constants.py               # 顶层重导出（兼容旧引用）
```

---

## Phase 1: 创建 app/ 包结构 + 提取 constants.py

### Task 1.1: 创建目录结构和空 __init__.py

**Files:**
- Create: `app/__init__.py`
- Create: `app/core/__init__.py`
- Create: `app/ui/__init__.py`
- Create: `app/services/__init__.py`

- [ ] **Step 1: 创建所有目录和 __init__.py 文件**

```powershell
New-Item -ItemType Directory -Force -Path "app/core", "app/ui", "app/services"
```

每个 `__init__.py` 内容为空文件。

- [ ] **Step 2: 验证目录结构**

```powershell
Get-ChildItem -Recurse app/
```

Expected: 显示 `app/`, `app/core/`, `app/ui/`, `app/services/` 及各目录下的 `__init__.py`

- [ ] **Step 3: Commit**

```bash
git add app/
git commit -m "chore: create app/ package skeleton"
```

### Task 1.2: 创建 app/constants.py（统一常量来源）

**Files:**
- Create: `app/constants.py`
- Modify: `barcode_image_mover_exe.py:37-100` — 删除重复常量，改为从 app.constants 导入
- Modify: `constants.py` — 改为重导出

- [ ] **Step 1: 创建 `app/constants.py`**

将 `constants.py` 的完整内容复制到 `app/constants.py`（从已有文件直接复制）：

```powershell
Copy-Item constants.py app/constants.py
```

- [ ] **Step 2: 修改 `barcode_image_mover_exe.py` 第 37-100 行**

删除第 37-86 行（从 `IMAGE_EXTS` 到 `atexit.register(_cleanup_temp_icons)` 之间的常量定义和模块变量），替换为从 `app.constants` 导入。

将 lines 37-100 替换为：

```python
# ============================================================
# 核心模块（内嵌，无外部依赖）
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

_TEMP_ICON_PATHS = []
_UNIQUE_PATH_LOCK = threading.Lock()
_RESERVED_OUTPUT_PATHS = set()

def _cleanup_temp_icons():
    for p in _TEMP_ICON_PATHS:
        try:
            os.remove(p)
        except OSError:
            pass
    _TEMP_ICON_PATHS.clear()

atexit.register(_cleanup_temp_icons)
```

- [ ] **Step 3: 修改顶层 `constants.py` 为重导出**

将 `constants.py` 的内容替换为：

```python
# -*- coding: utf-8 -*-
"""图片处理工具 - 全局常量（兼容旧引用，从 app.constants 重导出）"""

from app.constants import *  # noqa: F401, F403
```

- [ ] **Step 4: 运行测试验证**

```powershell
python -m pytest tests/test_core_regressions.py -v
```

Expected: 所有 22 个测试通过。

- [ ] **Step 5: Commit**

```bash
git add app/constants.py constants.py barcode_image_mover_exe.py
git commit -m "refactor: extract constants to app/constants.py"
```

---

## Phase 2: 提取 services 层（logger + icons）

### Task 2.1: 提取 LogWriter 到 app/services/logger.py

**Files:**
- Create: `app/services/logger.py`
- Modify: `barcode_image_mover_exe.py:451-493` — 删除 LogWriter 类，改为导入

- [ ] **Step 1: 创建 `app/services/logger.py`**

从 `barcode_image_mover_exe.py` lines 451-493 提取 `LogWriter` 类：

```python
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
```

- [ ] **Step 2: 修改 `barcode_image_mover_exe.py`**

在文件顶部从 `app.constants` 导入区之后添加：
```python
from app.services.logger import LogWriter
```

删除 lines 451-493（LogWriter 类定义）。

- [ ] **Step 3: 运行测试**

```powershell
python -m pytest tests/test_core_regressions.py -v
```

Expected: 所有 22 个测试通过。

- [ ] **Step 4: Commit**

```bash
git add app/services/logger.py barcode_image_mover_exe.py
git commit -m "refactor: extract LogWriter to app/services/logger.py"
```

### Task 2.2: 提取图标/SVG 函数到 app/services/icons.py

**Files:**
- Create: `app/services/icons.py`
- Modify: `barcode_image_mover_exe.py` — 删除 `_darken`, `_write_temp_svg`, 及 `_TEMP_ICON_PATHS`, `_cleanup_temp_icons` 的本地定义，改为导入

- [ ] **Step 1: 创建 `app/services/icons.py`**

从 lines 91-99 和 143-162 提取：

```python
# -*- coding: utf-8 -*-
"""SVG 图标生成和临时文件管理"""

import os
import tempfile
import atexit

_TEMP_ICON_PATHS = []


def _darken(hex_color, factor=0.85):
    """将十六进制颜色按给定因子暗化。"""
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 3:
        hex_color = ''.join(ch * 2 for ch in hex_color)
    r, g, b = int(hex_color[:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    r, g, b = max(0, int(r * factor)), max(0, int(g * factor)), max(0, int(b * factor))
    return f'#{r:02x}{g:02x}{b:02x}'


def _write_temp_svg(svg_content, prefix):
    """将 SVG 内容写入临时文件，返回 QSS 可用的文件路径（空字符串表示失败）。"""
    try:
        f = tempfile.NamedTemporaryFile(delete=False, suffix=".svg", prefix=prefix)
        f.write(svg_content.encode("utf-8"))
        f.close()
        _TEMP_ICON_PATHS.append(f.name)
        return f.name.replace("\\", "/")
    except Exception:
        return ""


def _cleanup_temp_icons():
    for p in _TEMP_ICON_PATHS:
        try:
            os.remove(p)
        except OSError:
            pass
    _TEMP_ICON_PATHS.clear()


atexit.register(_cleanup_temp_icons)
```

- [ ] **Step 2: 修改 `barcode_image_mover_exe.py`**

在文件顶部导入区添加：
```python
from app.services.icons import _darken, _write_temp_svg, _TEMP_ICON_PATHS, _cleanup_temp_icons
```

删除 lines 87-99（`_TEMP_ICON_PATHS = []`, `_UNIQUE_PATH_LOCK`, `_RESERVED_OUTPUT_PATHS`, `_cleanup_temp_icons`, `atexit.register`）中与 icons 相关的部分。**保留** `_UNIQUE_PATH_LOCK` 和 `_RESERVED_OUTPUT_PATHS`（file_ops 依赖）。

具体变更：
- 删除 line 87: `_TEMP_ICON_PATHS = []  # 临时图标文件路径，窗口关闭时清理`
- 删除 lines 91-99: `_cleanup_temp_icons` 函数和 `atexit.register(_cleanup_temp_icons)`
- 删除 lines 143-162: `_darken` 和 `_write_temp_svg` 函数

- [ ] **Step 3: 运行测试**

```powershell
python -m pytest tests/test_core_regressions.py -v
```

Expected: 所有 22 个测试通过。

- [ ] **Step 4: Commit**

```bash
git add app/services/icons.py barcode_image_mover_exe.py
git commit -m "refactor: extract icon/SVG helpers to app/services/icons.py"
```

---

## Phase 3: 提取 core/file_ops.py 和 core/classifier.py

### Task 3.1: 提取文件操作到 app/core/file_ops.py

**Files:**
- Create: `app/core/file_ops.py`
- Modify: `barcode_image_mover_exe.py:205-349` — 删除文件操作函数，改为导入

**提取的函数**（lines 205-349）：`get_unique_path`, `release_reserved_path`, `sanitize_csv_cell`, `validate_output_dir`, `suggest_output_dir`, `unique_preserve_order`, `image_to_buffer`, `write_image_buffer`, `copy_to_manual_review`, `remove_output_file_quiet`, `send_to_manual_and_remove_output`, `add_manual_source_aliases`, `build_manual_source_lookup`, `resolve_manual_source`, `make_temp_image_path`, `flatten_to_white_rgb`, `copy_files_parallel`, `clean_detail_names_in_dir`

- [ ] **Step 1: 创建 `app/core/file_ops.py`**

将 lines 205-449 的所有函数移动到 `app/core/file_ops.py`，并添加所需 imports：

```python
# -*- coding: utf-8 -*-
"""文件系统通用操作"""

import os
import io
import shutil
import uuid
import threading
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED

from app.constants import (
    IMAGE_EXTS, COPY_WORKERS, PROGRESS_REPORT_FRACTION,
    EXECUTOR_POLL_SECONDS, MANUAL_REVIEW_DIR_NAME,
)
from app.core.classifier import clean_detail_suffix, iter_image_files

_UNIQUE_PATH_LOCK = threading.Lock()
_RESERVED_OUTPUT_PATHS = set()


def get_unique_path(path, reserve=False):
    # ... (从主文件 lines 205-220 完整复制)


def release_reserved_path(path):
    # ... (从主文件 lines 223-225 完整复制)


def sanitize_csv_cell(value):
    # ... (从主文件 lines 228-237 完整复制)


def validate_output_dir(source_dir, output_root):
    # ... (从主文件 lines 240-252 完整复制)


def suggest_output_dir(source_dir):
    # ... (从主文件 lines 255-259 完整复制)


def unique_preserve_order(items):
    # ... (从主文件 lines 262-272 完整复制)


def image_to_buffer(img, image_format, **save_kwargs):
    # ... (从主文件 lines 275-278 完整复制)


def write_image_buffer(buffer, path):
    # ... (从主文件 lines 281-283 完整复制)


def copy_to_manual_review(src_path, manual_dir):
    # ... (从主文件 lines 286-294 完整复制)


def remove_output_file_quiet(path):
    # ... (从主文件 lines 297-305 完整复制)


def send_to_manual_and_remove_output(output_path, manual_dir, manual_source_lookup=None):
    # ... (从主文件 lines 308-315 完整复制)


def add_manual_source_aliases(lookup, current_name, src_path):
    # ... (从主文件 lines 318-320 完整复制)


def build_manual_source_lookup(source_dir, files, clean_detail_name=False):
    # ... (从主文件 lines 323-330 完整复制)


def resolve_manual_source(current_path, source_lookup=None):
    # ... (从主文件 lines 333-345 完整复制)


def make_temp_image_path(folder, basename):
    # ... (从主文件 lines 348-349 完整复制)


def flatten_to_white_rgb(img):
    # ... (从主文件 lines 352-356 完整复制)


def copy_files_parallel(source_dir, out_dir, files, log, label, stop_event=None):
    # ... (从主文件 lines 359-421 完整复制)


def clean_detail_names_in_dir(detail_dir, log, stop_event=None, manual_source_lookup=None):
    # ... (从主文件 lines 424-448 完整复制)
```

**关键**：`file_ops.py` import `clean_detail_suffix` 和 `iter_image_files` from `app.core.classifier`，这需要在 Task 3.2 中创建 `classifier.py` 后才能正常工作。但由于 Classifier 会在同 Phase 内完成，此循环依赖在 Phase 结束时自动解决。

- [ ] **Step 2: 修改 `barcode_image_mover_exe.py`**

在文件顶部添加：
```python
from app.core.file_ops import (
    get_unique_path, release_reserved_path, validate_output_dir, suggest_output_dir,
    copy_to_manual_review, remove_output_file_quiet, send_to_manual_and_remove_output,
    add_manual_source_aliases, build_manual_source_lookup, resolve_manual_source,
    make_temp_image_path, write_image_buffer, flatten_to_white_rgb,
    copy_files_parallel, clean_detail_names_in_dir, image_to_buffer,
    sanitize_csv_cell, unique_preserve_order,
)
```

删除 lines 88-89（`_UNIQUE_PATH_LOCK` 和 `_RESERVED_OUTPUT_PATHS`）以及 lines 205-448 的所有函数定义。

- [ ] **Step 3: 保持向后兼容**

在 `file_ops.py` 顶部添加对 `_UNIQUE_PATH_LOCK` 和 `_RESERVED_OUTPUT_PATHS` 的模块级引用，供 `run_all` 通过 `app.core.file_ops._RESERVED_OUTPUT_PATHS` 访问。

### Task 3.2: 提取分类函数到 app/core/classifier.py

**Files:**
- Create: `app/core/classifier.py`
- Modify: `barcode_image_mover_exe.py:165-203` — 删除分类函数，改为导入

- [ ] **Step 1: 创建 `app/core/classifier.py`**

从 lines 165-203 提取：

```python
# -*- coding: utf-8 -*-
"""图片分类：按文件名将图片分为详情图和主图"""

import os

from app.constants import IMAGE_EXTS


def clean_detail_suffix(filename):
    name, ext = os.path.splitext(filename)
    new = name.replace('_详情图', '')
    return new + ext if new != filename else filename


def is_image_file(filename):
    return os.path.splitext(filename)[1].lower() in IMAGE_EXTS


def iter_files(folder):
    with os.scandir(folder) as entries:
        for entry in entries:
            if entry.is_file():
                yield entry.name


def iter_image_files(folder):
    return (name for name in iter_files(folder) if is_image_file(name))


def split_source_images(source_dir):
    """一次扫描源目录，分离详情图/主图列表，减少大目录重复扫描。"""
    detail_files = []
    main_files = []
    for fn in iter_image_files(source_dir):
        if '_详情图' in fn:
            detail_files.append(fn)
        else:
            main_files.append(fn)
    return detail_files, main_files


def dir_has_files(folder):
    if not os.path.isdir(folder):
        return False
    with os.scandir(folder) as entries:
        return any(entry.is_file() for entry in entries)
```

- [ ] **Step 2: 修改 `barcode_image_mover_exe.py`**

在文件顶部添加：
```python
from app.core.classifier import (
    clean_detail_suffix, is_image_file, iter_files, iter_image_files,
    split_source_images, dir_has_files,
)
```

删除 lines 165-203 的函数定义。

- [ ] **Step 3: 运行测试验证 Phase 3**

```powershell
python -m pytest tests/test_core_regressions.py -v
```

Expected: 所有 22 个测试通过。

- [ ] **Step 4: Commit**

```bash
git add app/core/file_ops.py app/core/classifier.py barcode_image_mover_exe.py
git commit -m "refactor: extract file_ops and classifier to app/core/"
```

---


## Phase 4: 提取 excel_reader、matcher、image_processor、packager 到 core

### Task 4.1: 提取 Excel 读取到 app/core/excel_reader.py

**Files:**
- Create: `app/core/excel_reader.py`
- Modify: `barcode_image_mover_exe.py:519-631` — 删除 Excel 函数，改为导入

**提取的函数**：`step3_read_excel`, `excel_col_to_index`, `read_excel_preview`

- [ ] **Step 1: 创建 `app/core/excel_reader.py`**

从主文件 lines 519-631 提取：

```python
# -*- coding: utf-8 -*-
"""Excel 读取 & 条码解析"""

import os
import re

from app.constants import EXCEL_EMPTY_ROW_BREAK_THRESHOLD
from app.core.file_ops import unique_preserve_order


def excel_col_to_index(col):
    """Excel 列字母转索引"""
    col = (col or "").strip().upper()
    if not re.match(r'^[A-Z]+$', col):
        raise ValueError(f"非法列名: {col}")
    col_idx = 0
    for ch in col:
        col_idx = col_idx * 26 + (ord(ch) - ord('A') + 1)
    return col_idx


def step3_read_excel(excel_path, col, log, start_row=None, end_row=None, sheet_name=None, stop_event=None):
    """读取 Excel 提取条码列表"""
    # [从主文件 lines 519-589 完整复制函数体]
    ...


def read_excel_preview(excel_path, sheet_name=None, col_text='A'):
    """读取 Excel 表头列表和当前列表头"""
    # [从主文件 lines 602-631 完整复制函数体]
    ...
```

- [ ] **Step 2: 修改 `barcode_image_mover_exe.py`**

添加导入：
```python
from app.core.excel_reader import step3_read_excel, excel_col_to_index, read_excel_preview
```

删除 lines 519-631。

- [ ] **Step 3: Commit**

```bash
git add app/core/excel_reader.py barcode_image_mover_exe.py
git commit -m "refactor: extract excel_reader to app/core/excel_reader.py"
```

### Task 4.2: 提取匹配逻辑到 app/core/matcher.py

**Files:**
- Create: `app/core/matcher.py`
- Modify: `barcode_image_mover_exe.py:634-764` — 删除匹配函数，改为导入

**提取的函数**：`_build_barcode_to_files`, `step4_match_preview`, `step4_match`

- [ ] **Step 1: 创建 `app/core/matcher.py`**

从主文件 lines 634-764 提取。依赖 `classifier` 和 `file_ops`：

```python
# -*- coding: utf-8 -*-
"""条码匹配 & 文件提取"""

import os
import csv
import shutil

from app.core.classifier import clean_detail_suffix, iter_image_files
from app.core.file_ops import get_unique_path, sanitize_csv_cell, add_manual_source_aliases, resolve_manual_source


def _build_barcode_to_files(files, barcode_set, clean_detail_name=False):
    # [从主文件 lines 634-646 完整复制]
    ...


def step4_match_preview(files, barcodes, log, clean_detail_name=False, stop_event=None):
    # [从主文件 lines 649-679 完整复制]
    ...


def step4_match(source_dir, output_dir, barcodes, log, clean_detail_name=False,
                dry_run=False, stop_event=None, copy_mode=False, manual_source_lookup=None):
    # [从主文件 lines 682-764 完整复制]
    ...
```

- [ ] **Step 2: 修改 `barcode_image_mover_exe.py`**

添加导入：
```python
from app.core.matcher import step4_match_preview, step4_match
```

删除 lines 634-764。

- [ ] **Step 3: Commit**

```bash
git add app/core/matcher.py barcode_image_mover_exe.py
git commit -m "refactor: extract matcher to app/core/matcher.py"
```

### Task 4.3: 提取图片处理到 app/core/image_processor.py

**Files:**
- Create: `app/core/image_processor.py`
- Modify: `barcode_image_mover_exe.py:102-116, 767-1166` — 删除 NamedTuples + 图片处理函数，改为导入

**提取的内容**：
- `MainImageResult(NamedTuple)`, `DetailImageResult(NamedTuple)` — lines 102-116
- `_resize_stretch`, `_resize_crop`, `_resize_fit` — lines 767-792
- `_process_main_image` — lines 795-892
- `step6_process_main` — lines 895-947
- `_process_detail_image_impl` — lines 950-1080
- `_process_detail_image` — lines 1083-1106
- `step7_process_detail` — lines 1109-1166

- [ ] **Step 1: 创建 `app/core/image_processor.py`**

```python
# -*- coding: utf-8 -*-
"""图片缩放、压缩、格式转换"""

import os
import io
from typing import NamedTuple, Optional
from PIL import Image, ImageOps

from app.constants import (
    TARGET_SIZE, RESAMPLE_LANCZOS, IMAGE_EXTS,
    MAIN_IMAGE_MAX_BYTES, MAIN_JPEG_QUALITY, MAIN_JPEG_COMPRESS_START_QUALITY, MAIN_JPEG_MIN_QUALITY,
    DETAIL_IMAGE_MAX_BYTES, DETAIL_JPEG_OPTIMIZE_QUALITY, DETAIL_JPEG_QUALITIES, DETAIL_SCALE_FACTORS,
    IMAGE_WORKERS, PROGRESS_REPORT_FRACTION, EXECUTOR_POLL_SECONDS,
)
from app.core.classifier import iter_image_files
from app.core.file_ops import (
    image_to_buffer, write_image_buffer, get_unique_path, release_reserved_path,
    make_temp_image_path, flatten_to_white_rgb, send_to_manual_and_remove_output,
)

# [其余函数体从主文件完整复制]
```

- [ ] **Step 2: 修改 `barcode_image_mover_exe.py`**

添加导入：
```python
from app.core.image_processor import (
    MainImageResult, DetailImageResult,
    step6_process_main, step7_process_detail, _process_main_image, _process_detail_image,
)
```

删除 lines 102-116 和 lines 767-1166。

- [ ] **Step 3: Commit**

```bash
git add app/core/image_processor.py barcode_image_mover_exe.py
git commit -m "refactor: extract image_processor to app/core/image_processor.py"
```

### Task 4.4: 提取打包逻辑到 app/core/packager.py

**Files:**
- Create: `app/core/packager.py`
- Modify: `barcode_image_mover_exe.py:1169-1240` — 删除打包函数，改为导入

- [ ] **Step 1: 创建 `app/core/packager.py`**

从主文件 lines 1169-1240 提取 `step8_zip`：

```python
# -*- coding: utf-8 -*-
"""ZIP 分卷打包"""

import os
import zipfile

from app.constants import ZIP_SPLIT_BYTES, IMAGE_EXTS


def step8_zip(source_dir, target_dir, max_bytes, log, stop_event=None):
    # [从主文件 lines 1169-1240 完整复制]
    ...
```

- [ ] **Step 2: 修改 `barcode_image_mover_exe.py`**

添加导入：
```python
from app.core.packager import step8_zip
```

删除 lines 1169-1240。

- [ ] **Step 3: 运行测试验证 Phase 4**

```powershell
python -m pytest tests/test_core_regressions.py -v
```

Expected: 所有 22 个测试通过。

- [ ] **Step 4: Commit**

```bash
git add app/core/packager.py barcode_image_mover_exe.py
git commit -m "refactor: extract packager to app/core/packager.py"
```

---

## Phase 5: 提取 core/pipeline.py（run_all 流程编排）

### Task 5.1: 提取 run_all 到 app/core/pipeline.py

**Files:**
- Create: `app/core/pipeline.py`
- Modify: `barcode_image_mover_exe.py:1243-1472, 495-516` — 删除 `run_all`, `step1_detail`, `step2_main`

- [ ] **Step 1: 创建 `app/core/pipeline.py`**

提取 `step1_detail` (lines 495-504), `step2_main` (lines 507-516), `run_all` (lines 1243-1472)：

```python
# -*- coding: utf-8 -*-
"""流程编排：run_all 总协调"""

import os
import datetime

from app.constants import MODE_NAMES, RESIZE_MODE_MAP, MANUAL_REVIEW_DIR_NAME, ZIP_SPLIT_BYTES
from app.services.logger import LogWriter
from app.core.classifier import split_source_images, dir_has_files
from app.core.file_ops import (
    validate_output_dir, get_unique_path, build_manual_source_lookup,
    copy_files_parallel, clean_detail_names_in_dir,
)
from app.core.excel_reader import step3_read_excel
from app.core.matcher import step4_match_preview, step4_match
from app.core.image_processor import step6_process_main, step7_process_detail
from app.core.packager import step8_zip


def step1_detail(source_dir, out_dir, log, stop_event=None, files=None):
    # [从主文件 lines 495-504 完整复制]


def step2_main(source_dir, out_dir, log, stop_event=None, files=None):
    # [从主文件 lines 507-516 完整复制]


def run_all(source_dir, output_root, mode=1, excel_path=None, col='A',
            sheet_name=None, start_row=None, end_row=None, force_format=None,
            resize_mode='crop', stop_event=None, copy_mode=False):
    # [从主文件 lines 1243-1472 完整复制，但对 _RESERVED_OUTPUT_PATHS 的引用改为]
    # from app.core.file_ops import _RESERVED_OUTPUT_PATHS
    ...
```

**注意**：`run_all` 函数中直接使用了 `_RESERVED_OUTPUT_PATHS`。需要在 `pipeline.py` 中从 `file_ops` 导入。

- [ ] **Step 2: 修改 `barcode_image_mover_exe.py`**

添加导入：
```python
from app.core.pipeline import run_all, step1_detail, step2_main
```

删除 lines 495-516 和 lines 1243-1472。

- [ ] **Step 3: 运行测试验证 Phase 5**

```powershell
python -m pytest tests/test_core_regressions.py -v
```

Expected: 所有 22 个测试通过。

- [ ] **Step 4: Commit**

```bash
git add app/core/pipeline.py barcode_image_mover_exe.py
git commit -m "refactor: extract pipeline (run_all) to app/core/pipeline.py"
```

---

## Phase 6: 提取 UI 模块

### Task 6.1: 提取 widgets 到 app/ui/widgets.py

**Files:**
- Create: `app/ui/widgets.py`
- Modify: `barcode_image_mover_exe.py:1479-1609` — 删除控件类

**提取的类**：`EmittingStream`, `DragLineEdit`, `RoundComboBox`, `AnimatedProgressBar`

- [ ] **Step 1: 创建 `app/ui/widgets.py`**

```python
# -*- coding: utf-8 -*-
"""自定义 Qt 控件"""

import os
from PySide6.QtWidgets import QLineEdit, QComboBox, QProgressBar, QListView, QSizePolicy
from PySide6.QtCore import Qt, QObject, Signal, QTimer, QSize, QRectF
from PySide6.QtGui import QPainter, QColor, QLinearGradient, QPainterPath

from app.constants import SHIMMER_INTERVAL_MS, SHIMMER_STEP, SHIMMER_BAND_WIDTH


class EmittingStream(QObject):
    # [从主文件 lines 1479-1490 完整复制]


class DragLineEdit(QLineEdit):
    # [从主文件 lines 1493-1524 完整复制]


class RoundComboBox(QComboBox):
    # [从主文件 lines 1527-1555 完整复制]


class AnimatedProgressBar(QProgressBar):
    # [从主文件 lines 1558-1609 完整复制]
```

- [ ] **Step 2: 修改 `barcode_image_mover_exe.py`**

添加导入：
```python
from app.ui.widgets import EmittingStream, DragLineEdit, RoundComboBox, AnimatedProgressBar
```

删除 lines 1479-1609。

- [ ] **Step 3: Commit**

```bash
git add app/ui/widgets.py barcode_image_mover_exe.py
git commit -m "refactor: extract custom widgets to app/ui/widgets.py"
```

### Task 6.2: 提取 workers 到 app/ui/workers.py

**Files:**
- Create: `app/ui/workers.py`
- Modify: `barcode_image_mover_exe.py:1612-1648` — 删除 Worker 类

- [ ] **Step 1: 创建 `app/ui/workers.py`**

```python
# -*- coding: utf-8 -*-
"""QThread 工作线程"""

from PySide6.QtCore import QThread, Signal
from app.core.pipeline import run_all
from app.core.excel_reader import read_excel_preview


class WorkerThread(QThread):
    # [从主文件 lines 1612-1628 完整复制]


class ExcelHeaderWorker(QThread):
    # [从主文件 lines 1631-1648 完整复制]
```

- [ ] **Step 2: 修改 `barcode_image_mover_exe.py`**

添加导入：
```python
from app.ui.workers import WorkerThread, ExcelHeaderWorker
```

删除 lines 1612-1648。

- [ ] **Step 3: Commit**

```bash
git add app/ui/workers.py barcode_image_mover_exe.py
git commit -m "refactor: extract workers to app/ui/workers.py"
```

### Task 6.3: 提取 MainWindow 到 app/ui/main_window.py

**Files:**
- Create: `app/ui/main_window.py`
- Modify: `barcode_image_mover_exe.py:1650-3014` — 删除 MainWindow 类

- [ ] **Step 1: 创建 `app/ui/main_window.py`**

提取 `MainWindow` 类（lines 1650-3014）全部。所需的 imports：

```python
# -*- coding: utf-8 -*-
"""主窗口布局 & 信号连接"""

import os
import sys
import re
import threading

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QCheckBox, QTextEdit, QFileDialog, QMessageBox,
    QProgressBar, QFrame, QGraphicsDropShadowEffect, QSizePolicy, QGridLayout,
    QTabWidget, QListView,
)
from PySide6.QtCore import Qt, QTimer, QSize, QRectF
from PySide6.QtGui import (
    QTextCursor, QTextCharFormat, QColor, QFont, QIcon, QPixmap,
    QPalette, QPainter, QLinearGradient, QPainterPath,
)
import winsound

from app.constants import (
    DEBOUNCE_MS, LOG_MAX_BLOCK_COUNT, MODE_HELP_TEXT, RESIZE_MODE_MAP, UI_HELP_TEXT,
)
from app.services.icons import _darken, _write_temp_svg, _TEMP_ICON_PATHS, _cleanup_temp_icons
from app.core.file_ops import validate_output_dir, suggest_output_dir
from app.core.pipeline import run_all
from app.core.excel_reader import read_excel_preview
from app.ui.widgets import EmittingStream, DragLineEdit, RoundComboBox, AnimatedProgressBar
from app.ui.workers import WorkerThread, ExcelHeaderWorker


class MainWindow(QMainWindow):
    # [从主文件 lines 1650-3014 完整复制]
```

- [ ] **Step 2: 修改 `barcode_image_mover_exe.py`**

添加导入：
```python
from app.ui.main_window import MainWindow
```

删除 lines 1650-3014（MainWindow 类全部）。

- [ ] **Step 3: Commit**

```bash
git add app/ui/main_window.py barcode_image_mover_exe.py
git commit -m "refactor: extract MainWindow to app/ui/main_window.py"
```

---

## Phase 7: 清理 + 最终验证

### Task 7.1: 清理 barcode_image_mover_exe.py 为纯入口文件

**Files:**
- Modify: `barcode_image_mover_exe.py` — 缩减为仅 `main()` 和入口

- [ ] **Step 1: 最终 barcode_image_mover_exe.py 结构**

文件应仅包含（保留在文件中）：
1. `#!/usr/bin/env python3` 文档字符串
2. 必要的 stdlib imports (`os, sys, base64, tempfile, atexit`)
3. 从 `app.*` 模块的 imports
4. `_TEMP_ICON_PATHS = []` / `_UNIQUE_PATH_LOCK` / `_RESERVED_OUTPUT_PATHS`
5. `_cleanup_temp_icons()` + `atexit.register`
6. `APP_ICON_B64` (base64 数据)
7. `_remove_temp_icon()`
8. `main()` 函数
9. `if __name__ == "__main__": main()`

完整内容：

```python
#!/usr/bin/env python3
"""
电商图片批处理工具 - PySide6 独立 EXE 版
双击运行，无需额外文件。
依赖：pip install PySide6 Pillow openpyxl
打包：pyinstaller --onefile --windowed --collect-all PIL --collect-all openpyxl --collect-all PySide6 barcode_image_mover_exe.py
"""

import os
import sys
import base64
import tempfile
import atexit
import threading

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont, QIcon, QPixmap

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
from app.services.icons import _darken, _write_temp_svg, _TEMP_ICON_PATHS, _cleanup_temp_icons
from app.services.logger import LogWriter
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
    sanitize_csv_cell, unique_preserve_order, _UNIQUE_PATH_LOCK, _RESERVED_OUTPUT_PATHS,
)
from app.core.excel_reader import step3_read_excel, excel_col_to_index, read_excel_preview
from app.core.matcher import step4_match_preview, step4_match
from app.core.image_processor import (
    MainImageResult, DetailImageResult,
    _resize_stretch, _resize_crop, _resize_fit,
    _process_main_image, step6_process_main,
    _process_detail_image_impl, _process_detail_image, step7_process_detail,
)
from app.core.packager import step8_zip
from app.core.pipeline import run_all, step1_detail, step2_main
from app.ui.widgets import EmittingStream, DragLineEdit, RoundComboBox, AnimatedProgressBar
from app.ui.workers import WorkerThread, ExcelHeaderWorker
from app.ui.main_window import MainWindow

# ---- 模块级变量（仅入口使用） ----
_TEMP_ICON_PATHS.clear()  # icons 模块已初始化，共享引用
atexit.register(_cleanup_temp_icons)

# ---- 嵌入的 ICO 图标 ----
APP_ICON_B64 = "..."  # (保留原 base64 数据)

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
    font = QFont(["Microsoft YaHei", "Segoe UI", "Noto Sans CJK SC"])
    font.setPointSize(10)
    font.setStyleStrategy(
        QFont.StyleStrategy.PreferAntialias | QFont.StyleStrategy.PreferQuality
    )
    font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    app.setFont(font)

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
```

- [ ] **Step 2: 运行完整测试套件**

```powershell
python -m pytest tests/test_core_regressions.py -v
```

Expected: 所有 22 个测试通过。

- [ ] **Step 3: 启动 GUI 冒烟测试**

```powershell
python barcode_image_mover_exe.py
```

Expected: 窗口正常启动，所有控件功能正常。

- [ ] **Step 4: Commit**

```bash
git add barcode_image_mover_exe.py
git commit -m "refactor: slim barcode_image_mover_exe.py to entry-point only"
```

### Task 7.2: 更新测试文件兼容性

**Files:**
- Modify: `tests/test_core_regressions.py` — 更新 import 路径

- [ ] **Step 1: 测试文件当前状态**

测试文件使用 `import barcode_image_mover_exe as app` 并通过 `app.validate_output_dir` 等方式访问。由于入口文件仍保留所有重导出，测试可以继续工作。验证通过即可。

- [ ] **Step 2: 可选：添加直接模块导入测试**

如果测试需要直接测试新模块，可添加：
```python
from app.core.file_ops import validate_output_dir
from app.services.logger import LogWriter
```

但为保持向后兼容，保留 `import barcode_image_mover_exe as app` 路径。

- [ ] **Step 3: 确认所有 22 个测试通过**

```powershell
python -m pytest tests/test_core_regressions.py -v
```

- [ ] **Step 4: Final commit**

```bash
git add tests/
git commit -m "test: verify tests pass with refactored module structure"
```

---

## Phase 8: PyInstaller 打包验证

### Task 8.1: 验证打包

- [ ] **Step 1: 检查 hidden imports**

PyInstaller 无法自动检测从 `app.*` 包的动态导入。需要更新 spec 文件或在命令行添加 `--hidden-import`：

```powershell
pyinstaller --onefile --windowed `
  --hidden-import app `
  --hidden-import app.constants `
  --hidden-import app.core `
  --hidden-import app.core.classifier `
  --hidden-import app.core.excel_reader `
  --hidden-import app.core.file_ops `
  --hidden-import app.core.image_processor `
  --hidden-import app.core.matcher `
  --hidden-import app.core.packager `
  --hidden-import app.core.pipeline `
  --hidden-import app.services `
  --hidden-import app.services.logger `
  --hidden-import app.services.icons `
  --hidden-import app.ui `
  --hidden-import app.ui.main_window `
  --hidden-import app.ui.widgets `
  --hidden-import app.ui.workers `
  --collect-all PIL --collect-all openpyxl --collect-all PySide6 `
  barcode_image_mover_exe.py
```

- [ ] **Step 2: 验证打包的 EXE 可运行**

```powershell
Start-Process "./dist/barcode_image_mover_exe.exe"
```

Expected: 无终端窗口，GUI 正常启动。

- [ ] **Step 3: Commit 打包配置**

```bash
git add barcode_image_mover_exe.spec
git commit -m "build: add PyInstaller hidden imports for app/ package"
```

---

## 自检清单

- [x] 所有 7 个 Phase 覆盖 spec 中全部模块
- [ ] 执行时验证：Phase 1-7 每阶段结束均运行 pytest
- [ ] 入口文件保持 PyInstaller 兼容
- [ ] `constants.py` 顶层文件重导出于 Phase 7 后可删除（或保留兼容）
- [ ] core 层零 PySide6 依赖
- [ ] `tests/test_core_regressions.py` 全 22 测试通过
