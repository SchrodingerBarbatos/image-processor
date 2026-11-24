# -*- coding: utf-8 -*-
"""ZIP 分卷打包：所有分卷构建完成后才发布。"""

import os
import tempfile
import zipfile

from app.constants import IMAGE_EXTS


def _raise_walk_error(error):
    raise error


def step8_zip(source_dir, target_dir, max_bytes, log, stop_event=None):
    files_info = []
    for root, dirs, files in os.walk(source_dir, onerror=_raise_walk_error):
        dirs.sort()
        for f in sorted(files):
            if os.path.splitext(f)[1].lower() not in IMAGE_EXTS:
                continue
            fp = os.path.join(root, f)
            fsize = os.path.getsize(fp)
            if fsize == 0:
                raise OSError(f"图片文件为空，取消打包: {fp}")
            files_info.append((fp, fsize))
    if not files_info:
        log.write(f"  [信息] {source_dir} 无图片，跳过打包")
        return 0

    folder_name = os.path.basename(os.path.normpath(source_dir))
    os.makedirs(target_dir, exist_ok=True)
    volumes = []
    current = []
    current_size = 0
    for fp, fsize in files_info:
        if current and current_size + fsize > max_bytes:
            volumes.append(current)
            current = []
            current_size = 0
        if fsize > max_bytes:
            log.write(
                f"  [警告] {os.path.basename(fp)} 大小 {fsize / 1024 / 1024:.2f}MB "
                f"超过分卷上限 {max_bytes}字节，将单独生成超限zip"
            )
        current.append((fp, fsize))
        current_size += fsize
    if current:
        volumes.append(current)

    total_size = sum(size for _, size in files_info)
    processed = 0
    last_pct = -1
    with tempfile.TemporaryDirectory(prefix='.zip-stage-', dir=target_dir) as staging:
        names = []
        for index, files in enumerate(volumes, start=1):
            if stop_event is not None and stop_event.is_set():
                log.write("  [停止] 用户中止打包；未发布压缩包")
                return 0
            name = f'{folder_name}_{index:03d}.zip'
            with zipfile.ZipFile(os.path.join(staging, name), 'w', zipfile.ZIP_DEFLATED) as archive:
                for fp, fsize in files:
                    if stop_event is not None and stop_event.is_set():
                        log.write("  [停止] 用户中止打包；未发布压缩包")
                        return 0
                    arcname = os.path.relpath(fp, source_dir).replace('\\', '/')
                    try:
                        archive.write(fp, arcname)
                    except OSError as error:
                        raise OSError(f"打包文件失败 {fp}: {error}") from error
                    processed += fsize
                    pct = int(processed / total_size * 100)
                    if pct >= last_pct + 20:
                        last_pct = pct
                        log.write(f"  打包进度: {pct}%")
            names.append(name)

        if stop_event is not None and stop_event.is_set():
            log.write("  [停止] 用户中止打包；未发布压缩包")
            return 0
        for name in names:
            os.replace(os.path.join(staging, name), os.path.join(target_dir, name))
    log.write(f"  [打包] 已写完 {len(names)} 个zip包")
    return len(names)
