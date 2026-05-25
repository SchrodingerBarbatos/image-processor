# Image Processor / 图片处理工具

E-commerce product image batch processing tool with barcode-based matching and Excel integration. Built with Python 3 + PySide6.

基于条码匹配的电商产品图片批处理工具，支持 Excel 条码导入，Python 3 + PySide6 构建。

## Features / 功能

- **Image classification** — auto-split main/detail images by filename suffix
- **Barcode matching** — match images to Excel barcodes with preview mode
- **Image processing** — resize, crop, fit modes with JPEG/PNG optimization
- **Batch packaging** — ZIP split-volume export
- **Dark/Light theme** — auto-detects Windows system theme
- **Multithreaded** — parallel copy/process with progress reporting

- **图片分类** — 按文件名自动区分主图/详情图
- **条码匹配** — 根据 Excel 条码匹配图片，支持预览模式
- **图片处理** — 缩放/裁剪/适配，JPEG/PNG 质量优化
- **批量打包** — ZIP 分卷导出
- **暗色/亮色主题** — 自动跟随 Windows 系统主题
- **多线程处理** — 并行复制/处理，实时进度反馈

## Processing Modes / 处理模式

| Mode | Description |
|------|-------------|
| 完整流程 | Full pipeline: classify → match → process → zip |
| 预览模式 | Preview barcode matching results only |
| 仅分类 | Classify images only (no Excel needed) |

## Requirements / 环境依赖

- Python 3.10+
- PySide6 ≥ 6.5
- Pillow ≥ 10.0
- openpyxl ≥ 3.0

```bash
pip install PySide6 Pillow openpyxl
```

## Quick Start / 快速开始

```bash
python barcode_image_mover_exe.py
```

## Project Structure / 项目结构

```
├── app/
│   ├── constants.py          # global constants / 全局常量
│   ├── core/                 # pure business logic (zero UI) / 纯业务逻辑
│   │   ├── pipeline.py       # run_all workflow / 流程编排
│   │   ├── classifier.py     # image classification / 图片分类
│   │   ├── excel_reader.py   # Excel barcode parsing / Excel 条码解析
│   │   ├── matcher.py        # barcode matching / 条码匹配
│   │   ├── image_processor.py# resize/compress/convert / 图片处理
│   │   ├── packager.py       # ZIP split-volume / ZIP 分卷打包
│   │   └── file_ops.py       # file copy/move/clean / 文件通用操作
│   ├── ui/                   # Qt UI layer / 界面层
│   │   ├── main_window.py    # main window / 主窗口
│   │   ├── widgets.py        # custom widgets / 自定义控件
│   │   ├── workers.py        # QThread workers / 后台线程
│   │   ├── styles.py         # QSS styles & colors / 样式主题
│   │   └── dialogs.py        # dialog helpers / 对话框
│   └── services/             # cross-cutting / 横切服务
│       ├── logger.py         # log writer / 日志
│       └── icons.py          # SVG icon generation / SVG 图标
├── tests/                    # regression tests / 回归测试
├── barcode_image_mover_exe.py# entry point / 入口文件
└── constants.py              # re-export compat / 重导出兼容
```

## Build EXE / 打包为 EXE

```bash
pyinstaller --onefile --windowed ^
  --hidden-import app --hidden-import app.constants ^
  --hidden-import app.core --hidden-import app.core.classifier ^
  --hidden-import app.core.excel_reader --hidden-import app.core.file_ops ^
  --hidden-import app.core.image_processor --hidden-import app.core.matcher ^
  --hidden-import app.core.packager --hidden-import app.core.pipeline ^
  --hidden-import app.services --hidden-import app.services.logger ^
  --hidden-import app.services.icons ^
  --hidden-import app.ui --hidden-import app.ui.main_window ^
  --hidden-import app.ui.widgets --hidden-import app.ui.workers ^
  --collect-all PIL --collect-all openpyxl --collect-all PySide6 ^
  barcode_image_mover_exe.py
```

Or use the spec file:

```bash
pyinstaller barcode_image_mover_exe.spec
```

## Testing / 测试

```bash
python -m pytest tests/test_core_regressions.py -v
```

## License

MIT
