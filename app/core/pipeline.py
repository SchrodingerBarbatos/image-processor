# -*- coding: utf-8 -*-
"""流程编排：run_all 总协调"""

import os
import datetime

from app.constants import MODE_NAMES, RESIZE_MODE_MAP, MANUAL_REVIEW_DIR_NAME, ZIP_SPLIT_BYTES
from app.services.logger import LogWriter
from app.core.classifier import split_source_images, dir_has_files, iter_image_files
from app.core.file_ops import (
    validate_output_dir, get_unique_path, build_manual_source_lookup,
    copy_files_parallel, clean_detail_names_in_dir,
    _RESERVED_OUTPUT_PATHS,
)
from app.core.excel_reader import step3_read_excel
from app.core.matcher import step4_match_preview, step4_match
from app.core.image_processor import step6_process_main, step7_process_detail
from app.core.packager import step8_zip



def step1_detail(source_dir, out_dir, log, stop_event=None, files=None):
    if files is None:
        files = [f for f in iter_image_files(source_dir) if '_详情图' in f]
    if not files:
        log.write("  [信息] 无含'_详情图'的图片，跳过")
        os.makedirs(out_dir, exist_ok=True)
        return out_dir
    c = copy_files_parallel(source_dir, out_dir, files, log, "详情图", stop_event)
    log.write(f"  [完成] 已复制 {c} 张详情图至 {out_dir}（源文件未改动）")
    return out_dir


def step2_main(source_dir, out_dir, log, stop_event=None, files=None):
    if files is None:
        files = [f for f in iter_image_files(source_dir) if '_详情图' not in f]
    if not files:
        log.write("  [信息] 无主图图片，跳过")
        os.makedirs(out_dir, exist_ok=True)
        return out_dir
    c = copy_files_parallel(source_dir, out_dir, files, log, "主图", stop_event)
    log.write(f"  [完成] 已复制 {c} 张主图至 {out_dir}（源文件未改动）")
    return out_dir


def run_all(
    source_dir,
    output_root,
    mode=1,
    excel_path=None,
    col='A',
    sheet_name=None,
    start_row=None,
    end_row=None,
    force_format=None,
    resize_mode='crop',
    stop_event=None,
    copy_mode=False,
):
    """执行完整处理流程。"""
    if not os.path.isdir(source_dir):
        raise ValueError(f"源文件夹不存在: {source_dir}")

    validate_output_dir(source_dir, output_root)
    _RESERVED_OUTPUT_PATHS.clear()

    no_excel = mode == 4 or not excel_path
    dry_run = (mode == 2)
    do_compress = mode == 1
    do_zip = mode == 1

    if excel_path and not no_excel and not os.path.isfile(excel_path):
        raise ValueError(f"Excel文件不存在: {excel_path}")

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    if dry_run:
        task_root = output_root
        log_path = None
        manual_dir = None
    else:
        task_root = get_unique_path(os.path.join(output_root, f"任务_{ts}"), reserve=True)
        os.makedirs(task_root, exist_ok=True)
        log_path = os.path.join(task_root, f"处理日志_{ts}.txt")
        manual_dir = os.path.join(task_root, MANUAL_REVIEW_DIR_NAME)
    log = LogWriter(log_path)

    log.write("=" * 60)
    log.write("图片处理工具")
    log.write("=" * 60)
    log.write(f"[信息] 模式: {MODE_NAMES.get(mode, '未知')}")
    log.write(f"[信息] 源文件夹: {source_dir}")
    if dry_run:
        log.write("[信息] 输出目录: 预览模式不使用（不会写入任何文件）")
    else:
        log.write(f"[信息] 输出目录: {task_root}")
    if no_excel:
        log.write("[信息] Excel: 全量处理（不按条码匹配）")
    else:
        log.write(f"[信息] Excel: {excel_path}")
        log.write(f"[信息] 条码列: {col}")
    log.write("[信息] 分类步骤: 始终复制，源文件夹不改动")
    log.write(f"[信息] Excel匹配提取步骤: {'复制（保留分类结果）' if copy_mode else '剪切（移动到提取目录）'}")
    log.write(f"[信息] 输出格式: JPG/JPEG/PNG保持原格式；非标准格式转{force_format.upper() if force_format else 'JPG'}")
    log.write(f"[信息] 主图缩放: {RESIZE_MODE_MAP.get(resize_mode, resize_mode)}")
    source_detail_files, source_main_files = split_source_images(source_dir)
    main_manual_lookup = build_manual_source_lookup(source_dir, source_main_files)
    detail_manual_lookup = build_manual_source_lookup(source_dir, source_detail_files, clean_detail_name=True)
    if dry_run:
        preview_detail_files = source_detail_files
        preview_main_files = source_main_files

    try:
        # 步骤1
        detail_dir = os.path.join(task_root, "详情图")
        log.write(f"\n[步骤1] 复制含'_详情图'的图片至 {detail_dir}...（源文件未改动）")
        if dry_run:
            log.write("  [预览] 跳过文件移动")
            log.write(f"  [预览] 详情图候选: {len(preview_detail_files)} 张")
        else:
            detail_dir = step1_detail(
                source_dir, detail_dir, log, stop_event=stop_event, files=source_detail_files
            )

        if stop_event and stop_event.is_set():
            log.write("\n[停止] 用户中止")
            return

        # 步骤2
        main_dir = os.path.join(task_root, "主图")
        log.write(f"\n[步骤2] 复制主图至 {main_dir}...（源文件未改动）")
        if dry_run:
            log.write("  [预览] 跳过文件移动")
            log.write(f"  [预览] 主图候选: {len(preview_main_files)} 张")
        else:
            main_dir = step2_main(
                source_dir, main_dir, log, stop_event=stop_event, files=source_main_files
            )

        if stop_event and stop_event.is_set():
            log.write("\n[停止] 用户中止")
            return

        # 匹配
        if no_excel:
            detail_output = detail_dir
            main_output = main_dir
            log.write("\n[信息] 全量处理模式：已跳过条码读取和匹配")
            if not dry_run:
                log.write("\n[步骤3] 全量模式详情图改名...")
                _, detail_manual_lookup = clean_detail_names_in_dir(
                    detail_output, log, stop_event=stop_event,
                    manual_source_lookup=detail_manual_lookup
                )
        else:
            log.write("\n[步骤3] 读取Excel条码...")
            barcodes = step3_read_excel(excel_path, col, log, start_row, end_row, sheet_name, stop_event=stop_event)
            if not barcodes:
                log.write("[错误] 未读取到任何条码，程序退出")
                return

            if stop_event and stop_event.is_set():
                log.write("\n[停止] 用户中止")
                return

            detail_output = os.path.join(task_root, "详情图提取")
            log.write(f"\n[步骤4] 详情图条码匹配提取（{'复制' if copy_mode else '剪切'}） -> {detail_output}")
            if dry_run:
                step4_match_preview(preview_detail_files, barcodes, log,
                                    clean_detail_name=True, stop_event=stop_event)
            else:
                detail_manual_lookup = step4_match(
                    detail_dir, detail_output, barcodes, log,
                    clean_detail_name=True, dry_run=dry_run,
                    stop_event=stop_event, copy_mode=copy_mode,
                    manual_source_lookup=detail_manual_lookup
                )

            if stop_event and stop_event.is_set():
                log.write("\n[停止] 用户中止")
                return

            main_output = os.path.join(task_root, "主图提取")
            log.write(f"\n[步骤5] 主图条码匹配提取（{'复制' if copy_mode else '剪切'}） -> {main_output}")
            if dry_run:
                step4_match_preview(preview_main_files, barcodes, log,
                                    clean_detail_name=False, stop_event=stop_event)
            else:
                main_manual_lookup = step4_match(
                    main_dir, main_output, barcodes, log,
                    clean_detail_name=False, dry_run=dry_run,
                    stop_event=stop_event, copy_mode=copy_mode,
                    manual_source_lookup=main_manual_lookup
                )

            if stop_event and stop_event.is_set():
                log.write("\n[停止] 用户中止")
                return

        if dry_run:
            log.write("\n" + "=" * 60)
            log.write("  预览结束（未修改任何文件）")
            log.write("  确认无误后重新运行即可")
            log.write("=" * 60)
            return

        # 步骤6+7
        manual_count = 0
        if do_compress:
            log.write("\n[步骤6] 主图处理...")
            if dir_has_files(main_output):
                manual_count += step6_process_main(main_output, log, stop_event=stop_event,
                                                   resize_mode=resize_mode, force_format=force_format,
                                                   manual_dir=manual_dir,
                                                   manual_source_lookup=main_manual_lookup)
            else:
                log.write("  [信息] 主图输出文件夹为空，跳过")

            if stop_event and stop_event.is_set():
                log.write("\n[停止] 用户中止")
                return

            log.write("\n[步骤7] 详情图格式转换...")
            if dir_has_files(detail_output):
                manual_count += step7_process_detail(detail_output, log, stop_event=stop_event,
                                                     force_format=force_format, manual_dir=manual_dir,
                                                     manual_source_lookup=detail_manual_lookup)
            else:
                log.write("  [信息] 详情图输出文件夹为空，跳过")

            if stop_event and stop_event.is_set():
                log.write("\n[停止] 用户中止")
                return
        else:
            log.write("\n[步骤6/7] 跳过压缩处理")

        # 步骤8
        if manual_count:
            log.write(f"  [提醒] {manual_count} 张图片压缩后仍未达到大小要求，原图已复制到: {manual_dir}")

        if do_zip:
            log.write(f"\n[步骤8] 打包zip（每卷≤{ZIP_SPLIT_BYTES}字节）...")
            zip_dir = os.path.join(task_root, "压缩包")
            if dir_has_files(main_output):
                log.write("  --- 打包主图提取 ---")
                step8_zip(main_output, zip_dir, ZIP_SPLIT_BYTES, log, stop_event=stop_event)
            if dir_has_files(detail_output):
                log.write("  --- 打包详情图提取 ---")
                step8_zip(detail_output, zip_dir, ZIP_SPLIT_BYTES, log, stop_event=stop_event)

            if stop_event and stop_event.is_set():
                log.write("\n[停止] 用户中止")
                return
        else:
            log.write("\n[步骤8] 跳过打包")

        # 完成
        log.write("\n" + "=" * 60)
        log.write("  全部处理完成！")
        log.write(f"  主图输出: {main_output}")
        log.write(f"  详情图输出: {detail_output}")
        if do_zip:
            log.write(f"  zip包: {os.path.join(task_root, '压缩包')}")
        if log_path:
            log.write(f"  日志文件: {log_path}")
        if manual_count:
            log.write(f"  需要手动处理: {manual_dir}")
        log.write("=" * 60)

    except Exception as e:
        log.write(f"\n[错误] 处理异常: {e}")
        import traceback
        log.write(traceback.format_exc())
    finally:
        log.close()
        _RESERVED_OUTPUT_PATHS.clear()

