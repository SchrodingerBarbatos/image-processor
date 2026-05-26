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

class MainImageResult(NamedTuple):
    filename: str
    ok: bool
    error: Optional[str]
    manual_copy: Optional[str] = None


class DetailImageResult(NamedTuple):
    filename: str
    ok: bool
    error: Optional[str]
    converted: int
    compressed: int
    info: Optional[str]
    manual_copy: Optional[str] = None


def _resize_stretch(img, target):
    return img.resize(target, RESAMPLE_LANCZOS)


def _resize_crop(img, target):
    tw, th = target
    w, h = img.size
    ratio = max(tw / w, th / h)
    new_w, new_h = int(w * ratio), int(h * ratio)
    img = img.resize((new_w, new_h), RESAMPLE_LANCZOS)
    left = (new_w - tw) // 2
    top = (new_h - th) // 2
    return img.crop((left, top, left + tw, top + th))


def _resize_fit(img, target, bg_color=(255, 255, 255)):
    tw, th = target
    w, h = img.size
    ratio = min(tw / w, th / h)
    new_w, new_h = int(w * ratio), int(h * ratio)
    img = img.resize((new_w, new_h), RESAMPLE_LANCZOS)
    canvas = Image.new('RGB', target, bg_color)
    x = (tw - new_w) // 2
    y = (th - new_h) // 2
    canvas.paste(img, (x, y))
    return canvas


def _standard_output_for_actual_format(ext_lower, actual_format):
    actual_format = (actual_format or '').upper()
    if actual_format == 'JPEG':
        out_ext = ext_lower if ext_lower in {'.jpg', '.jpeg'} else '.jpg'
        return out_ext, 'JPEG'
    if actual_format == 'PNG':
        return '.png', 'PNG'
    return None, None


def _target_output_for_actual_format(ext_lower, actual_format, force_format):
    out_ext, out_format = _standard_output_for_actual_format(ext_lower, actual_format)
    if out_format:
        return out_ext, out_format, False
    if force_format == 'png':
        return '.png', 'PNG', True
    return '.jpg', 'JPEG', True


def _process_main_image(main_dir, fn, resize_mode='crop', force_format=None, stop_event=None,
                        manual_dir=None, manual_source_lookup=None):
    resize_fns = {'stretch': _resize_stretch, 'crop': _resize_crop, 'fit': _resize_fit}
    resize_fn = resize_fns.get(resize_mode, _resize_crop)
    fp = os.path.join(main_dir, fn)
    name, ext = os.path.splitext(fn)
    ext_lower = ext.lower()
    tmp_path = None
    out_path = None
    unresolved_copy = None
    try:
        if stop_event and stop_event.is_set():
            return MainImageResult(fn, True, None, unresolved_copy)
        with Image.open(fp) as img:
            if stop_event and stop_event.is_set():
                return MainImageResult(fn, True, None, unresolved_copy)
            actual_format = img.format
            img = ImageOps.exif_transpose(img)
            w, h = img.size
            needs_resize = (w != TARGET_SIZE[0] or h != TARGET_SIZE[1])
            out_ext, out_format, needs_convert = _target_output_for_actual_format(
                ext_lower, actual_format, force_format
            )
            fsize = os.path.getsize(fp)
            needs_compress = fsize > MAIN_IMAGE_MAX_BYTES
            if out_ext != ext_lower:
                needs_convert = True
            if not (needs_resize or needs_convert or needs_compress):
                return MainImageResult(fn, True, None, unresolved_copy)
            if needs_resize:
                img = resize_fn(img, TARGET_SIZE)
            out_name = name + out_ext
            out_path = os.path.join(main_dir, out_name)
            if out_name != fn and os.path.exists(out_path):
                out_path = get_unique_path(out_path, reserve=True)
                out_name = os.path.basename(out_path)
            tmp_path = make_temp_image_path(main_dir, out_name)
            if out_format == 'JPEG' and img.mode in ('RGBA', 'P', 'LA'):
                img = flatten_to_white_rgb(img)
            if img.mode not in ('RGB', 'RGBA'):
                if out_format == 'JPEG':
                    img = img.convert('RGB')
                else:
                    img = img.convert('RGBA')
            if out_format == 'JPEG':
                best_buffer = image_to_buffer(img, 'JPEG', quality=MAIN_JPEG_QUALITY)
            else:
                best_buffer = image_to_buffer(img, 'PNG', optimize=True)
            if best_buffer.tell() > MAIN_IMAGE_MAX_BYTES:
                if out_format == 'JPEG':
                    quality = MAIN_JPEG_COMPRESS_START_QUALITY
                    while quality >= MAIN_JPEG_MIN_QUALITY:
                        if stop_event and stop_event.is_set():
                            return MainImageResult(fn, True, None, unresolved_copy)
                        if best_buffer.tell() <= MAIN_IMAGE_MAX_BYTES:
                            break
                        best_buffer = image_to_buffer(img, 'JPEG', quality=quality)
                        quality -= 10
                else:
                    if img.mode in ('RGBA', 'LA'):
                        p_img = img.quantize(colors=256, method=Image.Quantize.FASTOCTREE).convert('RGBA')
                    else:
                        p_img = img.convert('P', palette=Image.Palette.ADAPTIVE, colors=256)
                    best_buffer = image_to_buffer(p_img, 'PNG', optimize=True)
            write_image_buffer(best_buffer, tmp_path)
            os.replace(tmp_path, out_path)
            if os.path.normcase(out_path) != os.path.normcase(fp) and os.path.exists(fp):
                try:
                    os.remove(fp)
                except OSError as e:
                    print(f"  [警告] {fn}: 主图转换成功，但旧文件删除失败: {e}")
        if best_buffer.tell() > MAIN_IMAGE_MAX_BYTES:
            unresolved_copy, _ = send_to_manual_and_remove_output(
                out_path, manual_dir, manual_source_lookup
            )
        return MainImageResult(out_name, True, None, unresolved_copy)
    except Exception as e:
        if out_path:
            release_reserved_path(out_path)
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        if manual_dir:
            unresolved_copy, _ = send_to_manual_and_remove_output(
                fp, manual_dir, manual_source_lookup
            )
        return MainImageResult(fn, False, str(e), unresolved_copy)


def step6_process_main(main_dir, log, stop_event=None, resize_mode='crop', force_format=None,
                       manual_dir=None, manual_source_lookup=None):
    from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
    files = sorted(iter_image_files(main_dir))
    total = len(files)
    if total == 0:
        log.write("  [信息] 主图输出文件夹无图片，跳过")
        return 0
    progress_step = max(1, total // PROGRESS_REPORT_FRACTION)
    workers = min(IMAGE_WORKERS, total)
    processed = 0
    unresolved_count = 0
    executor = ThreadPoolExecutor(max_workers=workers)
    futures = {}
    try:
        file_iter = iter(files)
        for _ in range(workers):
            try:
                fn = next(file_iter)
            except StopIteration:
                break
            futures[executor.submit(_process_main_image, main_dir, fn, resize_mode, force_format,
                                    stop_event, manual_dir, manual_source_lookup)] = fn
        stopping = False
        while futures:
            if stop_event and stop_event.is_set() and not stopping:
                log.write("  [停止] 用户中止主图处理")
                stopping = True
            done, _ = wait(list(futures), return_when=FIRST_COMPLETED, timeout=EXECUTOR_POLL_SECONDS)
            for future in done:
                futures.pop(future, None)
                processed += 1
                result = future.result()
                if result.manual_copy:
                    unresolved_count += 1
                    log.write(
                        f"  [提醒] {result.filename} 已复制到手动处理，并已从提取文件夹移除，不参与打包"
                    )
                if not result.ok:
                    log.write(f"  [失败] {result.filename}: {result.error}")
                if processed % progress_step == 0 or processed == total:
                    log.write(f"  主图处理进度: {processed}/{total}")
                if not stopping and not (stop_event and stop_event.is_set()):
                    try:
                        next_fn = next(file_iter)
                        futures[executor.submit(_process_main_image, main_dir, next_fn, resize_mode,
                                                force_format, stop_event, manual_dir,
                                                manual_source_lookup)] = next_fn
                    except StopIteration:
                        pass
    finally:
        executor.shutdown(wait=True, cancel_futures=True)
    log.write("  [完成] 主图处理完毕")
    return unresolved_count


def _process_detail_image_impl(detail_dir, fn, force_format=None, stop_event=None):
    fp = os.path.join(detail_dir, fn)
    name, ext = os.path.splitext(fn)
    ext_lower = ext.lower()
    converted = 0
    compressed = 0
    info = None

    if stop_event and stop_event.is_set():
        return DetailImageResult(fn, True, None, converted, compressed, info)
    try:
        with Image.open(fp) as img:
            actual_format = img.format
    except Exception as e:
        return DetailImageResult(fn, False, f"读取格式 {fn}: {e}", converted, compressed, info)

    target_ext, target_fmt, needs_convert = _target_output_for_actual_format(
        ext_lower, actual_format, force_format
    )
    if target_ext != ext_lower:
        needs_convert = True
    if needs_convert:
        out_path = None
        tmp_path = None
        replace_done = False
        old_fn = fn
        try:
            with Image.open(fp) as img:
                if stop_event and stop_event.is_set():
                    return DetailImageResult(fn, True, None, converted, compressed, info)
                img = ImageOps.exif_transpose(img)
                desired_out_path = os.path.join(detail_dir, name + target_ext)
                if os.path.normcase(desired_out_path) == os.path.normcase(fp):
                    out_path = desired_out_path
                else:
                    out_path = get_unique_path(desired_out_path, reserve=True)
                tmp_path = make_temp_image_path(detail_dir, os.path.basename(out_path))
                if img.mode in ('RGBA', 'P', 'LA') and target_fmt == 'JPEG':
                    img = flatten_to_white_rgb(img)
                elif target_fmt == 'JPEG' and img.mode != 'RGB':
                    img = img.convert('RGB')
                elif target_fmt == 'PNG' and img.mode not in ('RGB', 'RGBA'):
                    img = img.convert('RGBA')
                img.save(tmp_path, format=target_fmt)
            os.replace(tmp_path, out_path)
            replace_done = True
            tmp_path = None
            converted = 1
            fp = out_path
            fn = os.path.basename(out_path)
            ext_lower = os.path.splitext(fn)[1].lower()
            if os.path.normcase(out_path) != os.path.normcase(os.path.join(detail_dir, old_fn)):
                old_path = os.path.join(detail_dir, old_fn)
                if os.path.exists(old_path):
                    try:
                        os.remove(old_path)
                    except OSError as e:
                        info = f"{old_fn}: 转换成功，但旧文件删除失败: {e}"
        except Exception as e:
            if out_path and not replace_done:
                release_reserved_path(out_path)
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
            return DetailImageResult(fn, False, f"格式转换 {fn}: {e}", converted, compressed, info)

    tmp = None
    try:
        if os.path.getsize(fp) <= DETAIL_IMAGE_MAX_BYTES:
            return DetailImageResult(fn, True, None, converted, compressed, info)
        out_fmt = 'JPEG' if ext_lower in {'.jpg', '.jpeg'} else 'PNG'
        tmp = make_temp_image_path(detail_dir, fn)
        with Image.open(fp) as img:
            if stop_event and stop_event.is_set():
                return DetailImageResult(fn, True, None, converted, compressed, info)
            img = ImageOps.exif_transpose(img)
            if out_fmt == 'JPEG':
                best_buffer = image_to_buffer(
                    img, 'JPEG', quality=DETAIL_JPEG_OPTIMIZE_QUALITY, optimize=True
                )
            else:
                best_buffer = image_to_buffer(img, 'PNG', optimize=True)
            if best_buffer.tell() <= DETAIL_IMAGE_MAX_BYTES:
                write_image_buffer(best_buffer, tmp)
                os.replace(tmp, fp)
                return DetailImageResult(fn, True, None, converted, 1, info)

            if out_fmt == 'PNG' and img.mode != 'P':
                quantize_method = Image.Quantize.FASTOCTREE if img.mode in ('RGBA', 'LA') else Image.Quantize.MEDIANCUT
                p_img = img.quantize(colors=256, method=quantize_method)
                if img.mode in ('RGBA', 'LA'):
                    p_img = p_img.convert('RGBA')
                best_buffer = image_to_buffer(p_img, 'PNG', optimize=True)
                if best_buffer.tell() <= DETAIL_IMAGE_MAX_BYTES:
                    write_image_buffer(best_buffer, tmp)
                    os.replace(tmp, fp)
                    return DetailImageResult(fn, True, None, converted, 1, info)

            if out_fmt == 'JPEG':
                for q in DETAIL_JPEG_QUALITIES:
                    if stop_event and stop_event.is_set():
                        return DetailImageResult(fn, True, None, converted, compressed, info)
                    best_buffer = image_to_buffer(img, 'JPEG', quality=q, optimize=True)
                    if best_buffer.tell() <= DETAIL_IMAGE_MAX_BYTES:
                        break
                if best_buffer.tell() <= DETAIL_IMAGE_MAX_BYTES:
                    write_image_buffer(best_buffer, tmp)
                    os.replace(tmp, fp)
                    return DetailImageResult(fn, True, None, converted, 1, info)

            base_w, base_h = img.size
            for factor in DETAIL_SCALE_FACTORS:
                if stop_event and stop_event.is_set():
                    return DetailImageResult(fn, True, None, converted, compressed, info)
                r_img = img.resize((int(base_w * factor), int(base_h * factor)), RESAMPLE_LANCZOS)
                if out_fmt == 'JPEG':
                    best_buffer = image_to_buffer(r_img, 'JPEG', quality=MAIN_JPEG_QUALITY, optimize=True)
                else:
                    best_buffer = image_to_buffer(r_img, 'PNG', optimize=True)
                if best_buffer.tell() <= DETAIL_IMAGE_MAX_BYTES:
                    break
            if best_buffer.tell() <= DETAIL_IMAGE_MAX_BYTES:
                write_image_buffer(best_buffer, tmp)
                os.replace(tmp, fp)
                compressed = 1
            else:
                info = f"{fn}: 压缩后仍超5MB，保留原文件"
        return DetailImageResult(fn, True, None, converted, compressed, info)
    except Exception as e:
        if tmp and os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
        return DetailImageResult(fn, False, f"压缩 {fn}: {e}", converted, compressed, info)


def _process_detail_image(detail_dir, fn, force_format=None, stop_event=None,
                          manual_dir=None, manual_source_lookup=None):
    if not manual_dir:
        return _process_detail_image_impl(detail_dir, fn, force_format, stop_event)

    unresolved_copy = None
    result = _process_detail_image_impl(
        detail_dir, fn, force_format, stop_event
    )
    out_path = os.path.join(detail_dir, result.filename)
    still_too_large = (
        result.ok and result.compressed == 0 and os.path.isfile(out_path)
        and os.path.getsize(out_path) > DETAIL_IMAGE_MAX_BYTES
    )
    if still_too_large:
        unresolved_copy, _ = send_to_manual_and_remove_output(
            out_path, manual_dir, manual_source_lookup
        )
    elif not result.ok:
        failed_path = os.path.join(detail_dir, result.filename or fn)
        unresolved_copy, _ = send_to_manual_and_remove_output(
            failed_path, manual_dir, manual_source_lookup
        )
    return result._replace(manual_copy=unresolved_copy)


def step7_process_detail(detail_dir, log, stop_event=None, force_format=None,
                         manual_dir=None, manual_source_lookup=None):
    from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
    files = sorted(iter_image_files(detail_dir))
    total = len(files)
    if total == 0:
        log.write("  [信息] 详情图输出文件夹无图片，跳过")
        return 0
    converted = 0
    compressed = 0
    processed = 0
    unresolved_count = 0
    progress_step = max(1, total // PROGRESS_REPORT_FRACTION)
    workers = min(IMAGE_WORKERS, total)
    executor = ThreadPoolExecutor(max_workers=workers)
    futures = {}
    try:
        file_iter = iter(files)
        for _ in range(workers):
            try:
                fn = next(file_iter)
            except StopIteration:
                break
            futures[executor.submit(_process_detail_image, detail_dir, fn, force_format, stop_event,
                                    manual_dir, manual_source_lookup)] = fn
        stopping = False
        while futures:
            if stop_event and stop_event.is_set() and not stopping:
                log.write("  [停止] 用户中止详情图处理")
                stopping = True
            done, _ = wait(list(futures), return_when=FIRST_COMPLETED, timeout=EXECUTOR_POLL_SECONDS)
            for future in done:
                futures.pop(future, None)
                processed += 1
                result = future.result()
                if result.manual_copy:
                    unresolved_count += 1
                    log.write(
                        f"  [提醒] {result.filename} 已复制到手动处理，并已从提取文件夹移除，不参与打包"
                    )
                converted += result.converted
                compressed += result.compressed
                if not result.ok:
                    log.write(f"  [失败] {result.error}")
                if result.info:
                    log.write(f"  [信息] {result.info}")
                if processed % progress_step == 0 or processed == total:
                    log.write(f"  详情图处理进度: {processed}/{total}")
                if not stopping and not (stop_event and stop_event.is_set()):
                    try:
                        next_fn = next(file_iter)
                        futures[executor.submit(_process_detail_image, detail_dir, next_fn, force_format,
                                                stop_event, manual_dir, manual_source_lookup)] = next_fn
                    except StopIteration:
                        pass
    finally:
        executor.shutdown(wait=True, cancel_futures=True)
    log.write(f"  [完成] 详情图处理: 格式转换 {converted} 张, 压缩 {compressed} 张")
    return unresolved_count
