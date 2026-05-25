# 电商图片批处理工具 — 模块化解耦设计

## 目标

将 3077 行单文件 `barcode_image_mover_exe.py` 拆分为分层包结构，使每个模块职责单一、可独立测试和修改。

## 架构总览

```
图片处理/
├── app/
│   ├── __init__.py
│   ├── constants.py          # 全局常量（去重，统一来源）
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

## 各模块职责与接口

### app/constants.py

合并当前 `constants.py` 和主文件前 100 行的重复常量，统一为唯一来源。

包含：IMAGE_EXTS, TARGET_SIZE, ZIP_SPLIT_BYTES, COPY_WORKERS, IMAGE_WORKERS, 所有 JPEG 质量参数, Excel 阈值, UI 时序常量, 动画参数, MODE_NAMES, MODE_HELP_TEXT, UI_HELP_TEXT 等。

### app/core/classifier.py

**职责**：按文件名将图片分为详情图和主图。

**函数**：
- `split_source_images(source_dir)` → `tuple[detail_files, main_files]`
- `clean_detail_suffix(filename)` → 去除详情图后缀
- `is_image_file(filename)` → 判断是否为图片文件
- `iter_image_files(folder)` → 遍历目录中的图片文件
- `dir_has_files(folder)` → 检查目录是否有文件

### app/core/excel_reader.py

**职责**：读取 Excel，提取条码列表。

**函数**：
- `read_excel_barcodes(excel_path, col, log, start_row, end_row, sheet_name, stop_event)` → `list[str]`
- `excel_col_to_index(col)` → Excel 列字母转索引
- `read_excel_preview(excel_path, sheet_name, col_text)` → 预览数据

### app/core/matcher.py

**职责**：条码与文件名匹配，执行提取/复制操作。

**函数**：
- `match_preview(files, barcodes, log, clean_detail_name, stop_event)` → 匹配预览
- `match_and_extract(source_dir, output_dir, barcodes, log, ...)` → 执行匹配提取
- `build_barcode_to_files(files, barcode_set, clean_detail_name)` → 构建映射

### app/core/image_processor.py

**职责**：图片缩放、压缩、格式转换。

**函数**：
- `process_main_image(main_dir, fn, resize_mode, force_format, stop_event, ...)` → `MainImageResult`
- `process_detail_image(detail_dir, fn, force_format, stop_event, ...)` → `DetailImageResult`
- `step6_process_main(main_dir, log, stop_event, resize_mode, force_format, ...)` → 批量处理主图
- `step7_process_detail(detail_dir, log, stop_event, force_format, ...)` → 批量处理详情图
- 内部辅助：`_resize_stretch`, `_resize_crop`, `_resize_fit`, `flatten_to_white_rgb`, `image_to_buffer`

数据类型：
- `MainImageResult(NamedTuple)` — 原始/处理后尺寸、字节数、路径、是否需手动审查
- `DetailImageResult(NamedTuple)` — 同上

### app/core/packager.py

**职责**：ZIP 分卷打包。

**函数**：
- `zip_in_volumes(source_dir, target_dir, max_bytes, log, stop_event)` → 分卷打包

### app/core/file_ops.py

**职责**：文件系统通用操作。

**函数**：
- `copy_files_parallel(source_dir, out_dir, files, log, label, stop_event)` → 并行复制
- `get_unique_path(path, reserve)` / `release_reserved_path(path)` → 路径唯一性管理
- `validate_output_dir(source_dir, output_root)` → 校验输出目录
- `suggest_output_dir(source_dir)` → 建议输出目录
- `copy_to_manual_review(src_path, manual_dir)` → 复制到手动审查目录
- `remove_output_file_quiet(path)` → 静默删除输出文件
- `send_to_manual_and_remove_output(output_path, manual_dir, ...)` → 移至手动审查并清理
- `write_image_buffer(buffer, path)` → 写入图片缓冲到文件
- `make_temp_image_path(folder, basename)` → 生成临时图片路径

### app/core/pipeline.py

**职责**：流程编排，调用各步骤函数，传递上下文，处理中断。

**函数**：
- `run_all(source_dir, output_dir, mode, ui_config, excel_config, log, stop_event)` → 总协调

参数通过简单的配置字典或 NamedTuple 传入，不依赖 UI 对象。

### app/services/logger.py

**职责**：日志写入与缓冲。

将当前 `LogWriter` 类提取至此，保持接口不变。

### app/services/icons.py

**职责**：SVG 图标生成和临时文件管理。

提取当前 `_write_temp_svg`, `_cleanup_temp_icons`, `_darken` 等函数，以及 `_TEMP_ICON_PATHS` 和相关清理逻辑。

### app/ui/widgets.py

提取自定义控件：`DragLineEdit`, `RoundComboBox`, `AnimatedProgressBar` 等。

### app/ui/workers.py

提取 `WorkerThread`, `ExcelHeaderWorker`。

### app/ui/main_window.py

提取 `MainWindow` 类，保留 UI 布局和信号连接逻辑。

### app/ui/styles.py

提取 QSS 样式字符串和颜色常量（`_darken` 等颜色辅助函数移入 `icons.py` 或此处）。

### app/ui/dialogs.py

提取帮助面板等对话框。

## 关键设计原则

1. **core 层零 PySide6 依赖**：core 中的函数签名只使用 Python 标准库类型。日志通过 `Callable` 或 `LogWriter` 传入，不依赖 `Signal`。
2. **pipeline 只做编排**：每个步骤是独立函数调用，pipeline 负责按序执行、传递上下文、处理 `stop_event` 中断。
3. **常量统一来源**：删除 `barcode_image_mover_exe.py` 中的重复常量，全部从 `app.constants` 导入。顶层 `constants.py` 仅做重导出以兼容旧测试。
4. **入口文件极简**：`barcode_image_mover_exe.py` 缩减为仅 `main()` 函数，负责 `QApplication` 创建和窗口启动。PyInstaller 打包入口不变。

## 迁移策略

分阶段执行，每阶段可独立验证：

1. **阶段 1**：创建 `app/` 包结构，提取 `constants.py`，确保导入正常。
2. **阶段 2**：提取 `services/logger.py` 和 `services/icons.py`。
3. **阶段 3**：提取 `core/file_ops.py`、`core/classifier.py`、`core/excel_reader.py`。
4. **阶段 4**：提取 `core/matcher.py`、`core/image_processor.py`、`core/packager.py`。
5. **阶段 5**：提取 `core/pipeline.py`，整合 `run_all`。
6. **阶段 6**：提取 UI 模块（widgets → workers → styles → dialogs → main_window）。
7. **阶段 7**：清理主文件，缩减为入口脚本，验证完整功能。

每个阶段完成后运行测试验证无回归。