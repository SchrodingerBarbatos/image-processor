# -*- coding: utf-8 -*-
"""图片分类：按文件名将图片分为详情图和主图"""

import os

from app.constants import IMAGE_EXTS


def clean_detail_suffix(filename):
    name, ext = os.path.splitext(filename)
    new = name.replace('_详情图', '')
    return new + ext if new != name else filename


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