# -*- coding: utf-8 -*-
"""ZIP 分卷打包"""

import os
import zipfile

from app.constants import IMAGE_EXTS


def step8_zip(source_dir, target_dir, max_bytes, log, stop_event=None):
    files_info = []
    for root, _, files in os.walk(source_dir):
        for f in sorted(files):
            # 只允许图片进入压缩包
            if os.path.splitext(f)[1].lower() not in IMAGE_EXTS:
                continue
            fp = os.path.join(root, f)
            try:
                files_info.append((fp, os.path.getsize(fp)))
            except OSError as e:
                log.write(f"  [警告] 跳过无法读取的文件 {fp}: {e}")
    if not files_info:
        log.write(f"  [信息] {source_dir} 为空，跳过打包")
        return
    folder_name = os.path.basename(source_dir)
    os.makedirs(target_dir, exist_ok=True)
    for fp, fsize in files_info:
        if fsize > max_bytes:
            log.write(
                f"  [警告] {os.path.basename(fp)} 大小 {fsize / 1024 / 1024:.2f}MB "
                f"超过分卷上限 {max_bytes}字节，将单独生成超限zip"
            )
    idx = 1
    cur_size = 0
    zf = None
    current_zip_path = None
    total_size = sum(sz for _, sz in files_info)
    processed = 0
    last_pct = -1
    try:
        for fp, fsize in files_info:
            if stop_event and stop_event.is_set():
                log.write("  [停止] 用户中止打包")
                return
            if zf is None or cur_size + fsize > max_bytes:
                if zf:
                    zf.close()
                    zf = None
                    current_zip_path = None
                current_zip_path = os.path.join(target_dir, f'{folder_name}_{idx:03d}.zip')
                zf = zipfile.ZipFile(current_zip_path, 'w', zipfile.ZIP_DEFLATED)
                cur_size = 0
                idx += 1
                log.write(f"  [打包] 创建: {os.path.basename(current_zip_path)}")
            try:
                arcname = os.path.relpath(fp, source_dir).replace('\\', '/')
                zf.write(fp, arcname)
            except OSError as e:
                log.write(f"  [失败] 打包 {fp}: {e}")
                continue
            cur_size += fsize
            processed += fsize
            pct = int(processed / total_size * 100)
            if pct >= last_pct + 20:
                last_pct = pct
                log.write(f"  打包进度: {pct}%")
        if zf:
            zf.close()
            zf = None
            current_zip_path = None
        total_zips = idx - 1
        log.write(f"  [完成] 打包完毕，共 {total_zips} 个zip包")
    finally:
        if zf:
            zf.close()
        if current_zip_path and os.path.exists(current_zip_path):
            try:
                os.remove(current_zip_path)
                log.write(f"  [清理] 已删除未完成压缩包: {os.path.basename(current_zip_path)}")
            except OSError as e:
                log.write(f"  [警告] 删除未完成压缩包失败: {e}")