"""Custom Font Management System.
Supports:
1. Mode 1: Select from system fonts (QFontDatabase.families()).
2. Mode 2: Import custom font file (.ttf / .otf via QFontDatabase.addApplicationFont).
3. Modern typography font stack replacing old default fonts.
4. Global application via QApplication.setFont.
Strictly zero emojis used anywhere.
"""
from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

MODERN_FONT_STACK = [
    "Segoe UI Variable Text",
    "Microsoft JhengHei UI",
    "PingFang TC",
    "Noto Sans TC",
    "Segoe UI",
    "Microsoft JhengHei",
    "sans-serif",
]

_REGISTERED_CUSTOM_FONTS: dict[str, str] = {}  # path -> family


def get_system_fonts() -> list[str]:
    """Retrieve all clean system font families, excluding vertical '@' variants."""
    raw = QFontDatabase.families()
    cleaned = sorted({f for f in raw if not f.startswith("@")}, key=lambda s: s.lower())
    return cleaned


def resolve_best_default_font() -> str:
    """Find the highest-priority modern font present in the operating system."""
    available = set(QFontDatabase.families())
    for candidate in MODERN_FONT_STACK:
        if candidate in available:
            return candidate
    return "Microsoft JhengHei UI"


def load_font_file(file_path: str) -> tuple[bool, str, str]:
    """Register and load a .ttf or .otf font file. Returns (ok, family_name, error_msg)."""
    p = Path(file_path).resolve()
    if not p.is_file():
        return False, "", f"找不到指定的字體檔案：{file_path}"

    ext = p.suffix.lower()
    if ext not in (".ttf", ".otf", ".ttc"):
        return False, "", "不支援的檔案副檔名，僅支援 .ttf 與 .otf 格式字體檔案"

    norm_path = str(p)
    if norm_path in _REGISTERED_CUSTOM_FONTS:
        return True, _REGISTERED_CUSTOM_FONTS[norm_path], ""

    font_id = QFontDatabase.addApplicationFont(norm_path)
    if font_id == -1:
        return False, "", "字體檔案註冊失敗，檔案可能損毀或非標準字體格式"

    families = QFontDatabase.applicationFontFamilies(font_id)
    if not families:
        return False, "", "字體載入成功但未能讀取到有效的字族名稱"

    fam = families[0]
    _REGISTERED_CUSTOM_FONTS[norm_path] = fam
    return True, fam, ""


def apply_global_font(family: str, point_size: int = 10):
    """Set the application-wide font on QApplication."""
    qapp = QApplication.instance()
    font = QFont(family, point_size)
    font.setStyleHint(QFont.StyleHint.SansSerif)
    if qapp:
        qapp.setFont(font)


def init_app_font(cfg) -> str:
    """Initialize and apply application font on startup based on persisted config."""
    mode = cfg.get("font_mode", "default")
    if mode == "custom_file":
        path = cfg.get("custom_font_path", "")
        if path:
            ok, fam, _ = load_font_file(path)
            if ok:
                apply_global_font(fam)
                return fam
    elif mode == "system":
        fam = cfg.get("font_family", "")
        if fam:
            apply_global_font(fam)
            return fam

    # Default modern font stack
    best = resolve_best_default_font()
    apply_global_font(best)
    return best
