# -*- coding: utf-8 -*-
"""图片处理工具 - 全局常量"""

import os
from PIL import Image

# ---- 文件/格式 ----
IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.tif', '.webp', '.avif'}
TARGET_SIZE = (800, 800)
ZIP_SPLIT_BYTES = 100_000_000

# ---- 并发 ----
COPY_WORKERS = min(8, (os.cpu_count() or 4) + 2)
IMAGE_WORKERS = min(8, os.cpu_count() or 4)

# ---- 图片处理阈值 ----
MAIN_IMAGE_MAX_BYTES = 1_000_000
DETAIL_IMAGE_MAX_BYTES = 5_000_000

# ---- JPEG 质量参数 ----
MAIN_JPEG_QUALITY = 85
MAIN_JPEG_COMPRESS_START_QUALITY = 75
MAIN_JPEG_MIN_QUALITY = 20
DETAIL_JPEG_OPTIMIZE_QUALITY = 95
DETAIL_JPEG_QUALITIES = (85, 75, 65, 55, 45, 35, 25, 20)
DETAIL_SCALE_FACTORS = (0.9, 0.8, 0.7, 0.6)

# ---- Excel ----
EXCEL_EMPTY_ROW_BREAK_THRESHOLD = 300

# ---- 目录/文件 ----
MANUAL_REVIEW_DIR_NAME = "需要手动处理"

# ---- 性能调优 ----
LOG_FLUSH_INTERVAL = 50
PROGRESS_REPORT_FRACTION = 5
EXECUTOR_POLL_SECONDS = 0.2
LOG_MAX_BLOCK_COUNT = 2000

# ---- UI 时序 (ms) ----
DEBOUNCE_MS = 200
SHIMMER_INTERVAL_MS = 40

# ---- 流光动画参数 ----
SHIMMER_STEP = 0.02
SHIMMER_BAND_WIDTH = 80

# ---- Pillow 重采样 ----
RESAMPLE_LANCZOS = getattr(Image, "Resampling", Image).LANCZOS

# ---- 模式名称 ----
MODE_NAMES = {1: "完整流程", 2: "预览模式", 4: "仅分类(无Excel)"}
RESIZE_MODE_MAP = {'crop': '铺满（裁剪）', 'stretch': '铺满（直接拉伸）', 'fit': '比例适应（留白）'}

MODE_HELP_TEXT = {
    "完整流程": (
        "完整流程：先分出详情图/主图；有 Excel 时按条码提取，没 Excel 时处理全部；"
        "随后处理图片并按 100MB 分卷打包。"
    ),
    "预览模式": (
        "预览模式：用于安全检查条码匹配结果，不移动、不压缩、不打包图片；"
        "会输出预览日志到界面，不会写入任何目录或文件。"
    ),
    "仅分类(无Excel)": (
        "仅分类(无Excel)：不读取 Excel，只按文件名是否包含"_详情图"分到详情图/主图目录；"
        "不压缩、不打包。"
    ),
}

UI_HELP_TEXT = """【基本用法】
1. 选择"源文件夹"：放原始商品图片的文件夹。
2. 选择"输出目录"：处理结果会写到这里；输出目录必须在源文件夹之外。
3. 如需按条码提取图片，选择 Excel 清单，并确认条码列、工作表和行范围；不选 Excel 时会处理全部图片。
4. 选择处理模式和图片选项，点击"开始处理"。
5. 文件处理方式只影响 Excel 匹配后的提取步骤：源文件夹 → 分类目录：始终复制，源文件夹不变；分类目录 → 提取目录：按此选项复制或剪切。

【文件名规则】
文件名包含"_详情图"的图片会归为详情图；其他图片归为主图。
按 Excel 匹配时，图片文件名去掉扩展名后，需要和条码一致；带下划线后缀的文件，也会尝试用前半段匹配条码。

【处理模式】
完整流程：分类 → 读取 Excel 条码（如有）→ 提取匹配图片 → 主图处理 → 详情图处理 → 100MB 分卷打包。
预览模式：只检查匹配结果，不移动、不压缩、不打包，适合正式处理前测试。
仅分类(无Excel)：不读取 Excel，只按文件名分成详情图/主图，不压缩、不打包。

【图片选项】
主图缩放只影响主图：crop 裁剪铺满 800×800；stretch 直接拉伸到 800×800；fit 等比例缩放并留白。
强制选择 JPG/PNG 只影响 WEBP/AVIF/BMP 等非标准格式；JPG/JPEG/PNG 始终保持原格式，不互相转换。
匹配后操作只影响 Excel 匹配后的提取步骤：复制更安全，剪切更省空间。

【输出结果】
常见目录包括：详情图、主图、详情图提取、主图提取、压缩包，以及处理日志。日志区会显示进度、错误和最终输出位置。
"""
