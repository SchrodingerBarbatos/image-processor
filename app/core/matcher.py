# -*- coding: utf-8 -*-
"""条码匹配 & 文件提取"""

import os
import csv
import shutil

from app.core.classifier import clean_detail_suffix, iter_image_files
from app.core.file_ops import get_unique_path, sanitize_csv_cell, add_manual_source_aliases, resolve_manual_source


def _build_barcode_to_files(files, barcode_set, clean_detail_name=False):
    barcode_to_files = {}
    for fn in files:
        cn = os.path.splitext(clean_detail_suffix(fn) if clean_detail_name else fn)[0]
        cn_key = cn.upper()
        if cn_key in barcode_set:
            barcode_to_files.setdefault(cn_key, []).append(fn)
        parts = cn_key.split('_')
        for i in range(len(parts) - 1):
            candidate = '_'.join(parts[:i + 1])
            if candidate in barcode_set:
                barcode_to_files.setdefault(candidate, []).append(fn)
    return barcode_to_files


def step4_match_preview(files, barcodes, log, clean_detail_name=False, stop_event=None):
    all_files = list(files)
    if not all_files:
        log.write("  [信息] 预览源无图片，跳过")
        return
    barcode_set = {str(b).upper() for b in barcodes}
    barcode_to_files = _build_barcode_to_files(all_files, barcode_set, clean_detail_name=clean_detail_name)

    matched_total = 0
    preview_total = 0
    unmatched = []
    total = len(barcodes)
    last_pct = -1
    for idx, barcode in enumerate(barcodes):
        if stop_event and stop_event.is_set():
            log.write("  [停止] 用户中止匹配预览")
            break
        matched = barcode_to_files.get(str(barcode).upper(), [])
        if not matched:
            unmatched.append(barcode)
            continue
        matched_total += len(matched)
        for fn in matched:
            out_name = clean_detail_suffix(fn) if clean_detail_name else fn
            log.write(f"  [预览] {fn} → {out_name}")
            preview_total += 1
        pct = int((idx + 1) / total * 100)
        if pct >= last_pct + 20:
            last_pct = pct
            log.write(f"  匹配进度: {pct}% ({idx + 1}/{total})")
    log.write(f"  [结果] 匹配{matched_total}张, 预览{preview_total}张, 失败0张, 未匹配{len(unmatched)}个条码")


def step4_match(source_dir, output_dir, barcodes, log, clean_detail_name=False,
                dry_run=False, stop_event=None, copy_mode=False, manual_source_lookup=None):
    if not os.path.isdir(source_dir):
        log.write(f"  源文件夹不存在: {source_dir}，跳过")
        return {}
    if not dry_run:
        os.makedirs(output_dir, exist_ok=True)
    all_files = sorted(iter_image_files(source_dir))
    if not all_files:
        log.write("  [信息] 源文件夹无图片，跳过")
        return {}
    barcode_set = {str(b).upper() for b in barcodes}
    barcode_to_files = _build_barcode_to_files(all_files, barcode_set, clean_detail_name=clean_detail_name)

    matched_total = 0
    moved_total = 0
    failed_total = 0
    unmatched = []
    file_log = []
    output_lookup = {}
    total = len(barcodes)
    last_pct = -1
    processed_files = set()

    op_name = "复制" if copy_mode else "剪切"
    for idx, barcode in enumerate(barcodes):
        if stop_event and stop_event.is_set():
            log.write("  [停止] 用户中止匹配")
            break
        matched = barcode_to_files.get(str(barcode).upper(), [])
        if not matched:
            unmatched.append(barcode)
            continue
        matched_total += len(matched)
        for fn in matched:
            src = os.path.join(source_dir, fn)
            if not copy_mode and src in processed_files:
                continue
            out_name = clean_detail_suffix(fn) if clean_detail_name else fn
            dst = get_unique_path(os.path.join(output_dir, out_name))
            if dry_run:
                log.write(f"  [预览] {fn} → {out_name}")
                moved_total += 1
            else:
                try:
                    fsize = os.path.getsize(src)
                    if copy_mode:
                        shutil.copy2(src, dst)
                    else:
                        shutil.move(src, dst)
                    moved_total += 1
                    processed_files.add(src)
                    src_original = resolve_manual_source(src, manual_source_lookup)
                    add_manual_source_aliases(output_lookup, os.path.basename(dst), src_original)
                    file_log.append({'src': src, 'dst': dst, 'size': fsize,
                                     'barcode': barcode, 'status': 'ok'})
                except Exception as e:
                    failed_total += 1
                    log.write(f"  [失败] {fn}: {e}")
        pct = int((idx + 1) / total * 100)
        if pct >= last_pct + 20:
            last_pct = pct
            log.write(f"  匹配进度: {pct}% ({idx + 1}/{total})")
    log.write(f"  [结果] 匹配{matched_total}张, {op_name}{moved_total}张, "
              f"失败{failed_total}张, 未匹配{len(unmatched)}个条码")
    if file_log:
        log_path = os.path.join(output_dir, '匹配日志.csv')
        try:
            with open(log_path, 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['原路径', '目标路径', '文件大小', '条码', '状态'])
                for item in file_log:
                    writer.writerow([
                        sanitize_csv_cell(item['src']),
                        sanitize_csv_cell(item['dst']),
                        item['size'],
                        sanitize_csv_cell(item['barcode']),
                        sanitize_csv_cell(item['status']),
                    ])
            log.write(f"  [日志] 详情已写入 {log_path}")
        except Exception as e:
            log.write(f"  [警告] 写入日志失败: {e}")
    return output_lookup