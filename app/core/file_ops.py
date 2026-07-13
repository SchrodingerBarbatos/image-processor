# -*- coding: utf-8 -*-
"""文件操作：路径生成、CSV清洗、图片缓冲、并行复制等工具函数"""

import os
import io
import shutil
import uuid
import threading
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from PIL import Image

from app.constants import (
    IMAGE_EXTS, COPY_WORKERS, PROGRESS_REPORT_FRACTION,
    EXECUTOR_POLL_SECONDS, MANUAL_REVIEW_DIR_NAME,
)
from app.core.classifier import clean_detail_suffix, iter_image_files

_UNIQUE_PATH_LOCK = threading.Lock()
_RESERVED_OUTPUT_PATHS = set()


def get_unique_path(path, reserve=False):
    with _UNIQUE_PATH_LOCK:
        if not os.path.exists(path) and path not in _RESERVED_OUTPUT_PATHS:
            if reserve:
                _RESERVED_OUTPUT_PATHS.add(path)
            return path
        folder, filename = os.path.split(path)
        name, ext = os.path.splitext(filename)
        idx = 1
        while True:
            candidate = os.path.join(folder, f"{name}_dup{idx}{ext}")
            if not os.path.exists(candidate) and candidate not in _RESERVED_OUTPUT_PATHS:
                if reserve:
                    _RESERVED_OUTPUT_PATHS.add(candidate)
                return candidate
            idx += 1


def release_reserved_path(path):
    with _UNIQUE_PATH_LOCK:
        _RESERVED_OUTPUT_PATHS.discard(path)


def clear_reserved_paths():
    """清空保留路径集合。供流程编排在开始/结束时复位共享状态。"""
    with _UNIQUE_PATH_LOCK:
        _RESERVED_OUTPUT_PATHS.clear()


def sanitize_csv_cell(value):
    text = "" if value is None else str(value)
    if not text:
        return text
    dangerous_prefixes = ("=", "+", "-", "@", "\t", "\r", "\n")
    if text.startswith(dangerous_prefixes):
        return "'" + text
    if text[:1].isspace() and text.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + text
    return text


def validate_output_dir(source_dir, output_root):
    source_abs = os.path.realpath(source_dir)
    output_abs = os.path.realpath(output_root)
    if source_abs == output_abs:
        raise ValueError("输出目录不能与源目录相同。")
    try:
        common = os.path.commonpath([source_abs, output_abs])
    except ValueError:
        return
    if common == source_abs:
        raise ValueError("输出目录不能位于源目录内，请选择源目录外部路径。")
    if common == output_abs:
        raise ValueError("输出目录不能包含源目录，请选择源目录外部路径。")


def suggest_output_dir(source_dir):
    source_abs = os.path.realpath(source_dir)
    parent = os.path.dirname(source_abs.rstrip("\\/")) or source_abs
    name = os.path.basename(source_abs.rstrip("\\/")) or "输出"
    return os.path.join(parent, f"{name}_输出")


def unique_preserve_order(items):
    seen = set()
    unique = []
    duplicates = 0
    for item in items:
        if item in seen:
            duplicates += 1
            continue
        seen.add(item)
        unique.append(item)
    return unique, duplicates


def image_to_buffer(img, image_format, **save_kwargs):
    buffer = io.BytesIO()
    img.save(buffer, format=image_format, **save_kwargs)
    return buffer


def write_image_buffer(buffer, path):
    with open(path, 'wb') as f:
        f.write(buffer.getvalue())


def copy_to_manual_review(src_path, manual_dir):
    if not manual_dir or not src_path or not os.path.isfile(src_path):
        return None
    os.makedirs(manual_dir, exist_ok=True)
    dst_path = os.path.join(manual_dir, os.path.basename(src_path))
    if os.path.exists(dst_path):
        dst_path = get_unique_path(dst_path)
    shutil.copy2(src_path, dst_path)
    return dst_path


def remove_output_file_quiet(path):
    """从提取/处理输出目录移除不合格图片，避免后续被打包。"""
    if not path or not os.path.isfile(path):
        return False
    try:
        os.remove(path)
        return True
    except OSError:
        return False


def send_to_manual_and_remove_output(output_path, manual_dir, manual_source_lookup=None):
    """复制原始文件到手动处理目录，并从提取目录删除处理失败/不合格输出。"""
    manual_copy = None
    if manual_dir:
        manual_src = resolve_manual_source(output_path, manual_source_lookup)
        manual_copy = copy_to_manual_review(manual_src, manual_dir)
    removed = remove_output_file_quiet(output_path)
    return manual_copy, removed


def add_manual_source_aliases(lookup, current_name, src_path):
    """登记当前输出名到源路径的映射。

    完整文件名始终写入；stem 仅在尚未占用时写入，避免同 stem 不同扩展互相覆盖。
    """
    if not current_name:
        return
    name_key = os.path.normcase(current_name)
    lookup[name_key] = src_path
    stem_key = os.path.normcase(os.path.splitext(current_name)[0])
    if stem_key not in lookup:
        lookup[stem_key] = src_path


def build_manual_source_lookup(source_dir, files, clean_detail_name=False):
    lookup = {}
    for fn in files:
        src_path = os.path.join(source_dir, fn)
        add_manual_source_aliases(lookup, fn, src_path)
        if clean_detail_name:
            cleaned = clean_detail_suffix(fn)
            if cleaned != fn:
                add_manual_source_aliases(lookup, cleaned, src_path)
    return lookup


def resolve_manual_source(current_path, source_lookup=None):
    if source_lookup:
        current_name = os.path.basename(current_path)
        for key in (
            current_name,
            clean_detail_suffix(current_name),
            os.path.splitext(current_name)[0],
            os.path.splitext(clean_detail_suffix(current_name))[0],
        ):
            src_path = source_lookup.get(os.path.normcase(key))
            if src_path and os.path.isfile(src_path):
                return src_path
    return current_path


def make_temp_image_path(folder, basename):
    return os.path.join(folder, f".tmp_{threading.get_ident()}_{uuid.uuid4().hex}_{basename}")


def flatten_to_white_rgb(img):
    rgba = img.convert('RGBA')
    bg = Image.new('RGB', rgba.size, (255, 255, 255))
    bg.paste(rgba, mask=rgba.getchannel('A'))
    return bg


def copy_files_parallel(source_dir, out_dir, files, log, label, stop_event=None):
    os.makedirs(out_dir, exist_ok=True)
    total = len(files)
    if total == 0:
        return 0
    copied = 0
    failed = 0
    progress_step = max(1, total // PROGRESS_REPORT_FRACTION)

    def copy_one(fn):
        if stop_event and stop_event.is_set():
            return None
        src = os.path.join(source_dir, fn)
        dst = get_unique_path(os.path.join(out_dir, fn), reserve=True)
        try:
            shutil.copy2(src, dst)
        except Exception:
            release_reserved_path(dst)
            raise
        return fn

    workers = min(COPY_WORKERS, total)
    executor = ThreadPoolExecutor(max_workers=workers)
    futures = {}
    try:
        file_iter = iter(files)
        for _ in range(workers):
            try:
                fn = next(file_iter)
            except StopIteration:
                break
            futures[executor.submit(copy_one, fn)] = fn

        stopping = False
        while futures:
            if stop_event and stop_event.is_set() and not stopping:
                log.write(f"  [停止] 用户中止{label}复制")
                stopping = True
            done, _ = wait(list(futures), return_when=FIRST_COMPLETED, timeout=EXECUTOR_POLL_SECONDS)
            for future in done:
                fn = futures.pop(future, None)
                if fn is None:
                    continue
                try:
                    if future.result() is not None:
                        copied += 1
                except Exception as e:
                    failed += 1
                    log.write(f"  [失败] 复制 {fn or '(未知文件)'}: {e}")
                if copied and copied % progress_step == 0:
                    log.write(f"  {label}复制进度: {copied}/{total}")
                if not stopping and not (stop_event and stop_event.is_set()):
                    try:
                        next_fn = next(file_iter)
                        futures[executor.submit(copy_one, next_fn)] = next_fn
                    except StopIteration:
                        pass
    finally:
        executor.shutdown(wait=True, cancel_futures=True)

    if failed:
        log.write(f"  [警告] {label}复制失败 {failed} 张")
    return copied


def clean_detail_names_in_dir(detail_dir, log, stop_event=None, manual_source_lookup=None):
    if not os.path.isdir(detail_dir):
        return 0, {}
    renamed = 0
    output_lookup = {}
    for fn in list(iter_image_files(detail_dir)):
        if stop_event and stop_event.is_set():
            log.write("  [停止] 用户中止详情图改名")
            break
        new_name = clean_detail_suffix(fn)
        src_original = resolve_manual_source(os.path.join(detail_dir, fn), manual_source_lookup)
        if new_name == fn:
            add_manual_source_aliases(output_lookup, fn, src_original)
            continue
        src = os.path.join(detail_dir, fn)
        dst = get_unique_path(os.path.join(detail_dir, new_name))
        try:
            os.replace(src, dst)
            renamed += 1
            add_manual_source_aliases(output_lookup, os.path.basename(dst), src_original)
        except Exception as e:
            log.write(f"  [失败] 详情图改名 {fn}: {e}")
    if renamed:
        log.write(f"  [完成] 已去掉 {renamed} 张详情图文件名中的'_详情图'")
    return renamed, output_lookup