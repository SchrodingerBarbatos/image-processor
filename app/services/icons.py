# -*- coding: utf-8 -*-
"""SVG 图标生成和临时文件管理"""

import os
import tempfile
import atexit

_TEMP_ICON_PATHS = []


def _darken(hex_color, factor=0.85):
    """将十六进制颜色按给定因子暗化。"""
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 3:
        hex_color = ''.join(ch * 2 for ch in hex_color)
    r, g, b = int(hex_color[:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    r, g, b = max(0, int(r * factor)), max(0, int(g * factor)), max(0, int(b * factor))
    return f'#{r:02x}{g:02x}{b:02x}'


def _write_temp_svg(svg_content, prefix):
    """将 SVG 内容写入临时文件，返回 QSS 可用的文件路径（空字符串表示失败）。"""
    try:
        f = tempfile.NamedTemporaryFile(delete=False, suffix=".svg", prefix=prefix)
        f.write(svg_content.encode("utf-8"))
        f.close()
        _TEMP_ICON_PATHS.append(f.name)
        return f.name.replace("\\", "/")
    except Exception:
        return ""


def _cleanup_temp_icons():
    for p in _TEMP_ICON_PATHS:
        try:
            os.remove(p)
        except OSError:
            pass
    _TEMP_ICON_PATHS.clear()


atexit.register(_cleanup_temp_icons)
