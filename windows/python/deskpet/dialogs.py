"""Rich dialogs for Character Picker, Sound Library, Agent Confirm, and Privacy Prompt.
Material Design 3 style with dark/light theme switching and screen auto-centering.
"""
from __future__ import annotations

import json
import os
import shutil
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .config import APP_DIR, ASSETS, CUSTOM_CHARS_DIR, SOUND_LIB_DIR, asset, log
from .icons import get_icon
from .titlebar import CustomTitleBar

ARROW_DOWN_DARK = (ASSETS / "arrow_down_dark.svg").as_posix()
ARROW_DOWN_LIGHT = (ASSETS / "arrow_down_light.svg").as_posix()

BUILTIN_CHARS = [
    ("deepseek", "藍色大肥魚 (DeepSeek 鯨魚娘)"),
    ("gpt", "GPT龍娘 (OpenAI)"),
    ("claude", "大小姐Claude (Anthropic)"),
    ("gemini", "北美貓娘Gemini (Google)"),
]

# ========================================================= Dialog MD3 Stylesheets
DIALOG_LIGHT_QSS = """
QDialog {
    background-color: #f8f9fa;
    color: #1f2937;
    font-family: 'Segoe UI Variable Text', 'Microsoft JhengHei UI', 'PingFang TC', 'Noto Sans TC', sans-serif;
    font-size: 13px;
    border: 1px solid #cbd5e1;
    border-radius: 12px;
}
QLabel {
    color: #1f2937;
    background-color: transparent;
}
QGroupBox {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    margin-top: 14px;
    padding: 16px 12px 12px 12px;
    font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 4px;
    color: #1e40af;
    background-color: transparent;
}
QListWidget {
    background-color: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 10px;
    padding: 4px;
    color: #1f2937;
    outline: none;
}
QListWidget::item {
    height: 36px;
    padding-left: 10px;
    margin: 2px 4px;
    border-radius: 8px;
}
QListWidget::item:hover {
    background-color: #e2e8f0;
    color: #0f172a;
}
QListWidget::item:selected {
    background-color: #dbeafe;
    color: #1d4ed8;
    font-weight: bold;
}
QPushButton {
    background-color: #e2e8f0;
    color: #1e293b;
    border: 1px solid #cbd5e1;
    border-radius: 14px;
    padding: 4px 12px;
    min-height: 24px;
    font-weight: 500;
}
QPushButton:hover {
    background-color: #cbd5e1;
    border-color: #94a3b8;
}
QPushButton:pressed {
    background-color: #b0c0d0;
}
QPushButton#primary {
    background-color: #2563eb;
    color: #ffffff;
    border: none;
    font-weight: bold;
}
QPushButton#primary:hover {
    background-color: #1d4ed8;
}
QPushButton#primary:pressed {
    background-color: #1e40af;
}
QPushButton#danger {
    background-color: #ef4444;
    color: #ffffff;
    border: none;
    font-weight: bold;
}
QPushButton#danger:hover {
    background-color: #dc2626;
}
QPushButton#danger:pressed {
    background-color: #b91c1c;
}
QComboBox {
    background-color: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    padding: 6px 28px 6px 10px;
    color: #0f172a;
}
QComboBox:hover {
    border-color: #94a3b8;
}
QComboBox:focus {
    border: 2px solid #2563eb;
    padding: 5px 27px 5px 9px;
}
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 26px;
    border: none;
    background-color: transparent;
}
QComboBox::down-arrow {
    image: url("__ARROW_DOWN_LIGHT__");
    width: 10px;
    height: 7px;
}
QLineEdit, QSpinBox {
    background-color: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    padding: 6px 10px;
    color: #0f172a;
}
QLineEdit:focus, QSpinBox:focus {
    border: 2px solid #2563eb;
}
QComboBox QAbstractItemView {
    background-color: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    selection-background-color: #dbeafe;
    selection-color: #1d4ed8;
    padding: 4px;
    outline: none;
    color: #0f172a;
}
QSlider::groove:horizontal {
    height: 6px;
    background: #e2e8f0;
    border-radius: 3px;
}
QSlider::sub-page:horizontal {
    background: #2563eb;
    border-radius: 3px;
}
QSlider::handle:horizontal {
    width: 16px;
    height: 16px;
    margin: -5px 0;
    border-radius: 8px;
    background: #2563eb;
}
QSlider::handle:horizontal:hover {
    background: #1d4ed8;
}
QScrollBar:vertical {
    border: none;
    background: transparent;
    width: 8px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #cbd5e1;
    min-height: 24px;
    border-radius: 4px;
}
"""

DIALOG_DARK_QSS = """
QDialog {
    background-color: #16181d;
    color: #e2e2e6;
    font-family: 'Segoe UI Variable Text', 'Microsoft JhengHei UI', 'PingFang TC', 'Noto Sans TC', sans-serif;
    font-size: 13px;
    border: 1px solid #333642;
    border-radius: 12px;
}
QLabel {
    color: #e2e2e6;
    background-color: transparent;
}
QGroupBox {
    background-color: #20232a;
    border: 1px solid #2d313b;
    border-radius: 12px;
    margin-top: 14px;
    padding: 16px 12px 12px 12px;
    font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 4px;
    color: #93c5fd;
    background-color: transparent;
}
QListWidget {
    background-color: #1b1d24;
    border: 1px solid #2d313b;
    border-radius: 10px;
    padding: 4px;
    color: #e2e2e6;
    outline: none;
}
QListWidget::item {
    height: 36px;
    padding-left: 10px;
    margin: 2px 4px;
    border-radius: 8px;
}
QListWidget::item:hover {
    background-color: #282c37;
    color: #ffffff;
}
QListWidget::item:selected {
    background-color: #2c3954;
    color: #93c5fd;
    font-weight: bold;
}
QPushButton {
    background-color: #272a34;
    color: #e2e2e6;
    border: 1px solid #3c4252;
    border-radius: 14px;
    padding: 4px 12px;
    min-height: 24px;
    font-weight: 500;
}
QPushButton:hover {
    background-color: #333744;
    border-color: #4f576b;
}
QPushButton:pressed {
    background-color: #1c1e24;
}
QPushButton#primary {
    background-color: #3b82f6;
    color: #ffffff;
    border: none;
    font-weight: bold;
}
QPushButton#primary:hover {
    background-color: #2563eb;
}
QPushButton#primary:pressed {
    background-color: #1d4ed8;
}
QPushButton#danger {
    background-color: #dc2626;
    color: #ffffff;
    border: none;
    font-weight: bold;
}
QPushButton#danger:hover {
    background-color: #b91c1c;
}
QPushButton#danger:pressed {
    background-color: #991b1b;
}
QComboBox {
    background-color: #242731;
    border: 1px solid #3c4252;
    border-radius: 8px;
    padding: 6px 28px 6px 10px;
    color: #f1f5f9;
}
QComboBox:hover {
    border-color: #555b6d;
}
QComboBox:focus {
    border: 2px solid #60a5fa;
    padding: 5px 27px 5px 9px;
}
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 26px;
    border: none;
    background-color: transparent;
}
QComboBox::down-arrow {
    image: url("__ARROW_DOWN_DARK__");
    width: 10px;
    height: 7px;
}
QLineEdit, QSpinBox {
    background-color: #242731;
    border: 1px solid #3c4252;
    border-radius: 8px;
    padding: 6px 10px;
    color: #f1f5f9;
}
QLineEdit:focus, QSpinBox:focus {
    border: 2px solid #60a5fa;
}
QComboBox QAbstractItemView {
    background-color: #1b1d24;
    border: 1px solid #3c4252;
    border-radius: 8px;
    selection-background-color: #2c3954;
    selection-color: #93c5fd;
    padding: 4px;
    outline: none;
    color: #e2e2e6;
}
QSlider::groove:horizontal {
    height: 6px;
    background: #2d313b;
    border-radius: 3px;
}
QSlider::sub-page:horizontal {
    background: #3b82f6;
    border-radius: 3px;
}
QSlider::handle:horizontal {
    width: 16px;
    height: 16px;
    margin: -5px 0;
    border-radius: 8px;
    background: #60a5fa;
}
QSlider::handle:horizontal:hover {
    background: #93c5fd;
}
QScrollBar:vertical {
    border: none;
    background: transparent;
    width: 8px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #373c47;
    min-height: 24px;
    border-radius: 4px;
}
"""

DIALOG_LIGHT_QSS = DIALOG_LIGHT_QSS.replace("__ARROW_DOWN_LIGHT__", ARROW_DOWN_LIGHT)
DIALOG_DARK_QSS = DIALOG_DARK_QSS.replace("__ARROW_DOWN_DARK__", ARROW_DOWN_DARK)


def center_dialog(dialog: QDialog):
    screen = QApplication.primaryScreen()
    if screen:
        geo = screen.availableGeometry()
        x = geo.x() + max(0, (geo.width() - dialog.width()) // 2)
        y = geo.y() + max(0, (geo.height() - dialog.height()) // 2)
        dialog.move(x, y)


class ModernMessageBox(QDialog):
    """現代化全客製無邊框對話框，具備深淺主題切換、自訂標題列與向量圖示。
    提供與 QMessageBox 相同之 information、warning、question 靜態呼叫介面。
    """
    Ok = QMessageBox.StandardButton.Ok
    Cancel = QMessageBox.StandardButton.Cancel
    Yes = QMessageBox.StandardButton.Yes
    No = QMessageBox.StandardButton.No

    def __init__(
        self,
        parent: QWidget | None = None,
        title: str = "提示",
        text: str = "",
        buttons=QMessageBox.StandardButton.Ok,
        icon_type: str = "info",
        theme: str | None = None,
    ):
        super().__init__(parent, Qt.FramelessWindowHint | Qt.Window | Qt.WindowStaysOnTopHint)
        self.result_button = QMessageBox.StandardButton.Cancel if (buttons & QMessageBox.StandardButton.Cancel) else (
            QMessageBox.StandardButton.No if (buttons & QMessageBox.StandardButton.No) else QMessageBox.StandardButton.Ok
        )

        if not theme:
            if hasattr(parent, "cfg") and hasattr(parent.cfg, "get"):
                theme = parent.cfg.get("theme", "light")
            elif hasattr(parent, "app") and hasattr(parent.app, "cfg"):
                theme = parent.app.cfg.get("theme", "light")
            else:
                from .config import CONFIG_PATH
                try:
                    if CONFIG_PATH.exists():
                        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                            theme = json.load(f).get("theme", "light")
                    else:
                        theme = "light"
                except Exception:
                    theme = "light"

        is_dark = (theme == "dark")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(DIALOG_DARK_QSS if is_dark else DIALOG_LIGHT_QSS)
        self.setMinimumWidth(380)
        self.setMaximumWidth(540)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.title_bar = CustomTitleBar(self, title, has_min=False, has_close=True, theme="dark" if is_dark else "light")
        outer.addWidget(self.title_bar)

        content = QWidget()
        content.setObjectName("ModernDialogContent")
        content.setAttribute(Qt.WA_StyledBackground, True)
        bg_col = "#16181d" if is_dark else "#f8f9fa"
        content.setStyleSheet(
            f"QWidget#ModernDialogContent {{ background-color: {bg_col}; border-bottom-left-radius: 12px; border-bottom-right-radius: 12px; }}"
        )
        lay = QVBoxLayout(content)
        lay.setContentsMargins(22, 18, 22, 18)
        lay.setSpacing(16)

        msg_lay = QHBoxLayout()
        msg_lay.setSpacing(14)

        icon_map = {
            "info": ("info", "#3b82f6" if is_dark else "#2563eb"),
            "warning": ("warning", "#fbbf24" if is_dark else "#d97706"),
            "question": ("help", "#60a5fa" if is_dark else "#1d4ed8"),
            "success": ("check", "#10b981" if is_dark else "#059669"),
        }
        icon_name, icon_color = icon_map.get(icon_type, ("info", "#3b82f6"))
        lb_icon = QLabel()
        lb_icon.setPixmap(get_icon(icon_name, icon_color, 32).pixmap(32, 32))
        lb_icon.setFixedSize(36, 36)
        lb_icon.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        msg_lay.addWidget(lb_icon)

        lb_text = QLabel(text)
        lb_text.setWordWrap(True)
        lb_text.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lb_text.setStyleSheet(
            f"color: {'#e2e2e6' if is_dark else '#1f2937'}; font-size: 13px; line-height: 1.45;"
        )
        msg_lay.addWidget(lb_text, 1)
        lay.addLayout(msg_lay)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addStretch(1)

        if buttons & (QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No):
            b_yes = QPushButton("確定")
            b_yes.setObjectName("primary")
            b_yes.setMinimumWidth(80)
            b_yes.clicked.connect(lambda: self._choose(QMessageBox.StandardButton.Yes))
            btn_row.addWidget(b_yes)

            b_no = QPushButton("取消")
            b_no.setMinimumWidth(80)
            b_no.clicked.connect(lambda: self._choose(QMessageBox.StandardButton.No))
            btn_row.addWidget(b_no)
        else:
            if buttons & QMessageBox.StandardButton.Ok:
                b_ok = QPushButton("確定")
                b_ok.setObjectName("primary")
                b_ok.setMinimumWidth(80)
                b_ok.clicked.connect(lambda: self._choose(QMessageBox.StandardButton.Ok))
                btn_row.addWidget(b_ok)
            if buttons & QMessageBox.StandardButton.Cancel:
                b_cancel = QPushButton("取消")
                b_cancel.setMinimumWidth(80)
                b_cancel.clicked.connect(lambda: self._choose(QMessageBox.StandardButton.Cancel))
                btn_row.addWidget(b_cancel)

        lay.addLayout(btn_row)
        outer.addWidget(content, 1)

    def _choose(self, btn: QMessageBox.StandardButton):
        self.result_button = btn
        self.accept()

    def showEvent(self, e):
        super().showEvent(e)
        center_dialog(self)
        self.raise_()
        self.activateWindow()

    @classmethod
    def information(cls, parent: QWidget | None, title: str, text: str, buttons=QMessageBox.StandardButton.Ok) -> QMessageBox.StandardButton:
        dlg = cls(parent, title=title, text=text, buttons=buttons, icon_type="info")
        dlg.exec()
        return dlg.result_button

    @classmethod
    def warning(cls, parent: QWidget | None, title: str, text: str, buttons=QMessageBox.StandardButton.Ok) -> QMessageBox.StandardButton:
        dlg = cls(parent, title=title, text=text, buttons=buttons, icon_type="warning")
        dlg.exec()
        return dlg.result_button

    @classmethod
    def question(cls, parent: QWidget | None, title: str, text: str, buttons=QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) -> QMessageBox.StandardButton:
        dlg = cls(parent, title=title, text=text, buttons=buttons, icon_type="question")
        dlg.exec()
        return dlg.result_button


class CharPickerDialog(QDialog):
    def __init__(self, app, parent=None):
        super().__init__(parent, Qt.FramelessWindowHint | Qt.Window | Qt.WindowStaysOnTopHint)
        self.app = app
        self.setWindowTitle("選擇角色與尺寸形態")
        self.setFixedSize(600, 500)
        self.selected_id = app.pet.character
        self.selected_variant = app.pet.variant

        is_dark = (self.app.cfg.get("theme", "light") == "dark")
        self.setStyleSheet(DIALOG_DARK_QSS if is_dark else DIALOG_LIGHT_QSS)

        CUSTOM_CHARS_DIR.mkdir(parents=True, exist_ok=True)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.title_bar = CustomTitleBar(self, "選擇角色與尺寸形態", has_min=False, has_close=True, theme="dark" if is_dark else "light")
        outer.addWidget(self.title_bar)

        content = QWidget()
        lay = QHBoxLayout(content)
        lay.setContentsMargins(18, 16, 18, 18)
        lay.setSpacing(14)

        # Left: Character list
        left = QVBoxLayout()
        lbl_list = QLabel("可用角色清單")
        lbl_list.setStyleSheet("font-size: 14px; font-weight: bold; color: " + ("#93c5fd;" if is_dark else "#1e40af;"))
        left.addWidget(lbl_list)

        self.list_widget = QListWidget()
        self.list_widget.currentRowChanged.connect(self._on_char_selected)
        left.addWidget(self.list_widget, 1)

        r_btns = QHBoxLayout()
        b_add = QPushButton("新增自訂角色...")
        b_add.clicked.connect(self._add_custom)
        self.b_del = QPushButton("刪除角色")
        self.b_del.setObjectName("danger")
        self.b_del.clicked.connect(self._del_custom)
        r_btns.addWidget(b_add)
        r_btns.addWidget(self.b_del)
        left.addLayout(r_btns)
        lay.addLayout(left, 1)

        # Right: Preview & variant options
        right = QVBoxLayout()
        g_preview = QGroupBox("角色預覽")
        f_prev = QVBoxLayout(g_preview)
        self.lb_preview = QLabel()
        self.lb_preview.setAlignment(Qt.AlignCenter)
        self.lb_preview.setFixedSize(230, 220)
        bg_prev = "#1b1d24" if is_dark else "#f1f5f9"
        bd_prev = "#2d313b" if is_dark else "#cbd5e1"
        self.lb_preview.setStyleSheet(f"border: 1px dashed {bd_prev}; border-radius: 10px; background-color: {bg_prev};")
        f_prev.addWidget(self.lb_preview)
        right.addWidget(g_preview)

        g_opt = QGroupBox("寵物形態（寬高比）")
        f_opt = QVBoxLayout(g_opt)
        self.cmb_variant = QComboBox()
        self.cmb_variant.addItems(["正方形沒尾巴 (1024×1024, 1:1)", "有尾巴 (1536×1024, 1.5:1)"])
        self.cmb_variant.currentIndexChanged.connect(self._on_variant_changed)
        f_opt.addWidget(self.cmb_variant)
        right.addWidget(g_opt)

        r_act = QHBoxLayout()
        r_act.addStretch(1)
        b_ok = QPushButton("套用角色")
        b_ok.setObjectName("primary")
        b_ok.clicked.connect(self._apply)
        b_cancel = QPushButton("關閉")
        b_cancel.clicked.connect(self.reject)
        r_act.addWidget(b_ok)
        r_act.addWidget(b_cancel)
        right.addLayout(r_act)

        lay.addLayout(right, 1)
        outer.addWidget(content, 1)

        self._refresh_list()

    def showEvent(self, e):
        super().showEvent(e)
        center_dialog(self)
        self.raise_()
        self.activateWindow()

    def _refresh_list(self):
        self.list_widget.clear()
        entries = []
        for cid, name in BUILTIN_CHARS:
            entries.append((cid, name, False))

        # Scan custom_characters/
        for d in CUSTOM_CHARS_DIR.iterdir():
            if d.is_dir() and (d / "sprite.png").exists():
                cid = d.name
                disp = f"自訂：{cid.replace('custom_', '')}"
                entries.append((cid, disp, True))

        # Scan legacy chars/
        legacy_dir = APP_DIR / "chars"
        if legacy_dir.exists():
            for d in legacy_dir.iterdir():
                if d.is_dir() and (d / "sprite.png").exists() and d.name not in [e[0] for e in entries]:
                    cid = d.name
                    disp = f"自訂：{cid.replace('custom_', '')}"
                    entries.append((cid, disp, True))

        select_idx = 0
        for i, (cid, name, is_custom) in enumerate(entries):
            item = QListWidgetItem(name)
            item.setData(Qt.UserRole, (cid, is_custom))
            self.list_widget.addItem(item)
            if cid == self.selected_id:
                select_idx = i

        self.list_widget.setCurrentRow(select_idx)
        self.cmb_variant.setCurrentIndex(1 if self.selected_variant == "tail" else 0)

    def _on_char_selected(self, row: int):
        if row < 0:
            return
        item = self.list_widget.item(row)
        cid, is_custom = item.data(Qt.UserRole)
        self.selected_id = cid
        self.b_del.setEnabled(is_custom)
        self._update_preview()

    def _on_variant_changed(self, idx: int):
        self.selected_variant = "tail" if idx == 1 else "square"
        self._update_preview()

    def _update_preview(self):
        cid = self.selected_id
        is_tail = (self.selected_variant == "tail")
        p = None
        if cid.startswith("custom_"):
            d = CUSTOM_CHARS_DIR / cid
            if not d.exists():
                d = APP_DIR / "chars" / cid
            p = d / "sprite.png"
        else:
            chars_dir = APP_DIR / "assets" / "chars" / cid
            if is_tail:
                tail_f = chars_dir / "tail.png"
                if tail_f.exists():
                    p = tail_f
            if not p:
                square_f = chars_dir / "sprites" / "expression_11.png"
                if square_f.exists():
                    p = square_f
                else:
                    s_f = chars_dir / "sprite.png"
                    if s_f.exists():
                        p = s_f

        if not p or not p.exists():
            p = APP_DIR / "assets" / "expr" / "expression_11.png"

        img = QImage(str(p))
        if not img.isNull():
            pm = QPixmap.fromImage(img.scaled(200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self.lb_preview.setPixmap(pm)
        else:
            self.lb_preview.setText("無圖片預覽")

    def _add_custom(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "選擇角色圖片（建議透明背景 PNG）", "", "圖片檔案 (*.png *.jpg *.jpeg *.webp *.bmp)"
        )
        if not path:
            return
        name, ok = QInputDialog.getText(self, "自訂角色名稱", "給這個角色取個名字（英數底線）：")
        if not ok or not name.strip():
            return

        safe_name = "".join(c for c in name if c.isalnum() or c in ("_", "-")).strip()
        if not safe_name:
            ModernMessageBox.warning(self, "名稱錯誤", "請輸入有效的名稱。")
            return

        cid = f"custom_{safe_name}"
        dest_dir = CUSTOM_CHARS_DIR / cid
        dest_dir.mkdir(parents=True, exist_ok=True)

        try:
            img = QImage(path)
            if img.isNull() or img.height() <= 0:
                raise ValueError("無法解析圖片檔案格式")

            strict = self.app.cfg.get("strict_custom_image_ratio", True)
            ratio = img.width() / float(img.height())
            if strict:
                if ratio < 0.7 or ratio > 1.8:
                    ModernMessageBox.warning(
                        self,
                        "圖片比例不符合",
                        "圖片比例不符合官方立繪標準規格（1:1 或 1.5:1）。若欲強制使用特殊比例圖片，請至設定中關閉尺寸比例限制。",
                    )
                    return

            if not strict:
                # 關閉限制：保持原始寬高比直接儲存
                img.save(str(dest_dir / "sprite.png"), "PNG")
            else:
                # Fit into 1024x1024
                canvas = QImage(1024, 1024, QImage.Format_ARGB32_Premultiplied)
                canvas.fill(Qt.transparent)
                sc = min(1024.0 / img.width(), 1024.0 / img.height())
                w, h = int(img.width() * sc), int(img.height() * sc)
                from PySide6.QtGui import QPainter
                p = QPainter(canvas)
                p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
                p.drawImage((1024 - w) // 2, 1024 - h, img.scaled(w, h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation))
                p.end()
                canvas.save(str(dest_dir / "sprite.png"), "PNG")
            # Default tablet quad: centered at bottom
            (dest_dir / "tablet.txt").write_text("330,790,694,790,694,960,330,960", encoding="utf-8")
        except Exception as e:
            ModernMessageBox.warning(self, "建立失敗", f"無法建立自訂角色: {e}")
            return

        ModernMessageBox.information(self, "成功", f"自訂角色「{safe_name}」已新增！\n若角色手上有拿平板，可手動修改\n{dest_dir / 'tablet.txt'}\n的四角座標（1024×1024 座標系）。")
        self.selected_id = cid
        self._refresh_list()

    def _del_custom(self):
        cid = self.selected_id
        if not cid.startswith("custom_"):
            return
        if ModernMessageBox.question(self, "確認刪除", f"確定要刪除自訂角色「{cid}」嗎？") != ModernMessageBox.Yes:
            return
        d = CUSTOM_CHARS_DIR / cid
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)
        d_legacy = APP_DIR / "chars" / cid
        if d_legacy.exists():
            shutil.rmtree(d_legacy, ignore_errors=True)
        self.selected_id = "deepseek"
        self._refresh_list()

    def _apply(self):
        self.app.set_character(self.selected_id)
        self.app.set_variant(self.selected_variant)
        self.accept()


class SoundLibraryDialog(QDialog):
    def __init__(self, app, parent=None):
        super().__init__(parent, Qt.FramelessWindowHint | Qt.Window | Qt.WindowStaysOnTopHint)
        self.app = app
        self.sounds = app.sounds
        self.cfg = app.cfg
        self.setWindowTitle("音效庫與個別提示音設定")
        self.setFixedSize(640, 600)

        is_dark = (self.cfg.get("theme", "light") == "dark")
        self.setStyleSheet(DIALOG_DARK_QSS if is_dark else DIALOG_LIGHT_QSS)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.title_bar = CustomTitleBar(self, "音效庫與個別提示音設定", has_min=False, has_close=True, theme="dark" if is_dark else "light")
        outer.addWidget(self.title_bar)

        content = QWidget()
        lay = QVBoxLayout(content)
        lay.setContentsMargins(18, 16, 18, 18)
        lay.setSpacing(12)

        t_lbl = QLabel("自訂個別音效與音量")
        t_lbl.setStyleSheet("font-size: 15px; font-weight: bold; color: " + ("#93c5fd;" if is_dark else "#1e40af;"))
        lay.addWidget(t_lbl)

        d_lbl = QLabel("四個提示音各自獨立調整音量與更換檔案（支援 mp3, wav, ogg，上限 50MB）")
        d_lbl.setStyleSheet("font-size: 12px; color: " + ("#94a3b8;" if is_dark else "#64748b;"))
        lay.addWidget(d_lbl)

        from .audio import CUE_KEYS, CUE_NAMES
        self.sliders: dict[str, QSlider] = {}
        self.labels: dict[str, QLabel] = {}
        self.file_labels: dict[str, QLabel] = {}

        for k in CUE_KEYS:
            g = QGroupBox(CUE_NAMES[k])
            f = QVBoxLayout(g)
            f.setSpacing(6)

            r_vol = QHBoxLayout()
            r_vol.addWidget(QLabel("音量:"))
            sl = QSlider(Qt.Horizontal)
            sl.setRange(0, 100)
            cur_v = (self.cfg.get("cue_volumes") or {}).get(k, 80)
            sl.setValue(cur_v)
            lb_v = QLabel(f"{cur_v} %")
            lb_v.setFixedWidth(45)
            sl.valueChanged.connect(lambda v, key=k, label=lb_v: self._on_vol_changed(key, v, label))
            r_vol.addWidget(sl, 1)
            r_vol.addWidget(lb_v)
            f.addLayout(r_vol)

            r_act = QHBoxLayout()
            r_act.setSpacing(8)
            custom_fn = (self.cfg.get("cue_custom") or {}).get(k, "")
            lb_f = QLabel(f"檔案: {custom_fn or '預設音效'}")
            lb_f.setStyleSheet("color: " + ("#94a3b8;" if is_dark else "#64748b;"))
            b_play = QPushButton("試聽")
            b_play.setFixedWidth(68)
            b_play.clicked.connect(lambda _=False, key=k: self.sounds.play(key))
            b_upload = QPushButton("更換...")
            b_upload.setFixedWidth(78)
            b_upload.clicked.connect(lambda _=False, key=k: self._upload_cue(key))
            b_reset = QPushButton("恢復預設")
            b_reset.setFixedWidth(92)
            b_reset.clicked.connect(lambda _=False, key=k: self._reset_cue(key))

            r_act.addWidget(lb_f, 1)
            r_act.addWidget(b_play)
            r_act.addWidget(b_upload)
            r_act.addWidget(b_reset)
            f.addLayout(r_act)

            self.sliders[k] = sl
            self.labels[k] = lb_v
            self.file_labels[k] = lb_f
            lay.addWidget(g)

        b_close = QPushButton("完成")
        b_close.setObjectName("primary")
        b_close.clicked.connect(self.accept)
        lay.addWidget(b_close)
        outer.addWidget(content, 1)

    def showEvent(self, e):
        super().showEvent(e)
        center_dialog(self)
        self.raise_()
        self.activateWindow()

    def _on_vol_changed(self, key: str, v: int, label: QLabel):
        label.setText(f"{v} %")
        vols = self.cfg.get("cue_volumes") or {}
        vols[key] = v
        self.cfg.set("cue_volumes", vols)
        self.sounds.apply()

    def _upload_cue(self, key: str):
        path, _ = QFileDialog.getOpenFileName(self, "選擇音效檔案", "", "音效檔案 (*.mp3 *.wav *.ogg *.m4a)")
        if not path:
            return
        ok, msg = self.sounds.set_custom_cue(key, path)
        if not ok:
            ModernMessageBox.warning(self, "更換失敗", msg)
        else:
            self.file_labels[key].setText(f"檔案: {msg}")

    def _reset_cue(self, key: str):
        self.sounds.restore_default_cue(key)
        self.file_labels[key].setText("檔案: 預設音效")


class AgentConfirmDialog(QDialog):
    """精緻小型無邊框確認視窗（寬 380px，高 220px），用於 Agent 執行未在白名單之命令時的使用者確認。
    杜絕全螢幕紅色警示，提供高質感微光邊框與流暢操作。
    """
    def __init__(self, parent=None, command: str = "", reason: str = "", theme: str | None = None):
        super().__init__(parent, Qt.FramelessWindowHint | Qt.Window | Qt.WindowStaysOnTopHint)
        self.setFixedSize(380, 220)
        self.confirmed = False

        if not theme:
            if hasattr(parent, "cfg") and hasattr(parent.cfg, "get"):
                theme = parent.cfg.get("theme", "light")
            else:
                theme = "dark"
        is_dark = (theme == "dark")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(DIALOG_DARK_QSS if is_dark else DIALOG_LIGHT_QSS)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.title_bar = CustomTitleBar(self, "Agent 指令安全確認", has_min=False, has_close=True, theme="dark" if is_dark else "light")
        outer.addWidget(self.title_bar)

        content = QWidget()
        content.setObjectName("AgentConfirmContent")
        content.setAttribute(Qt.WA_StyledBackground, True)
        bg_col = "#16181d" if is_dark else "#f8f9fa"
        border_col = "#3b82f6" if is_dark else "#2563eb"
        content.setStyleSheet(
            f"QWidget#AgentConfirmContent {{ background-color: {bg_col}; border: 1.5px solid {border_col}; border-top: none; border-bottom-left-radius: 12px; border-bottom-right-radius: 12px; }}"
        )
        lay = QVBoxLayout(content)
        lay.setContentsMargins(18, 12, 18, 14)
        lay.setSpacing(10)

        header_lbl = QLabel("系統助手 Agent 欲執行非白名單命令：")
        header_lbl.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {'#93c5fd' if is_dark else '#1e40af'};")
        lay.addWidget(header_lbl)

        cmd_box = QLabel(command)
        cmd_box.setWordWrap(True)
        cmd_box.setTextInteractionFlags(Qt.TextSelectableByMouse)
        cmd_bg = "#0d1117" if is_dark else "#e2e8f0"
        cmd_fg = "#38bdf8" if is_dark else "#0369a1"
        cmd_box.setStyleSheet(
            f"background-color: {cmd_bg}; color: {cmd_fg}; font-family: 'Consolas', 'Courier New', monospace; "
            f"font-size: 12px; border: 1px solid {'#30363d' if is_dark else '#cbd5e1'}; border-radius: 6px; padding: 6px 10px;"
        )
        lay.addWidget(cmd_box, 1)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addStretch(1)

        btn_deny = QPushButton("拒絕")
        btn_deny.setObjectName("danger")
        btn_deny.setFixedWidth(85)
        btn_deny.clicked.connect(self._reject)
        btn_row.addWidget(btn_deny)

        btn_approve = QPushButton("確認執行")
        btn_approve.setObjectName("primary")
        btn_approve.setFixedWidth(95)
        btn_approve.clicked.connect(self._approve)
        btn_row.addWidget(btn_approve)

        lay.addLayout(btn_row)
        outer.addWidget(content, 1)

    def _approve(self):
        self.confirmed = True
        self.accept()

    def _reject(self):
        self.confirmed = False
        self.reject()

    def showEvent(self, e):
        super().showEvent(e)
        center_dialog(self)
        self.raise_()
        self.activateWindow()


class PrivacyPromptDialog(QDialog):
    """精緻小型無邊框隱私提示視窗（寬 380px，高 220px），提供清晰友善的隱私說明。"""
    def __init__(self, parent=None, message: str = "", theme: str | None = None):
        super().__init__(parent, Qt.FramelessWindowHint | Qt.Window | Qt.WindowStaysOnTopHint)
        self.setFixedSize(380, 220)

        if not theme:
            if hasattr(parent, "cfg") and hasattr(parent.cfg, "get"):
                theme = parent.cfg.get("theme", "light")
            else:
                theme = "dark"
        is_dark = (theme == "dark")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(DIALOG_DARK_QSS if is_dark else DIALOG_LIGHT_QSS)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.title_bar = CustomTitleBar(self, "隱私優先與脫敏保護", has_min=False, has_close=True, theme="dark" if is_dark else "light")
        outer.addWidget(self.title_bar)

        content = QWidget()
        content.setObjectName("PrivacyPromptContent")
        content.setAttribute(Qt.WA_StyledBackground, True)
        bg_col = "#16181d" if is_dark else "#f8f9fa"
        border_col = "#10b981" if is_dark else "#059669"
        content.setStyleSheet(
            f"QWidget#PrivacyPromptContent {{ background-color: {bg_col}; border: 1.5px solid {border_col}; border-top: none; border-bottom-left-radius: 12px; border-bottom-right-radius: 12px; }}"
        )
        lay = QVBoxLayout(content)
        lay.setContentsMargins(18, 12, 18, 14)
        lay.setSpacing(10)

        title_lbl = QLabel("本地脫敏過濾與零資料保留 (ZDR)")
        title_lbl.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {'#6ee7b7' if is_dark else '#065f46'};")
        lay.addWidget(title_lbl)

        desc_text = message or (
            "本模式已全面啟動：\n"
            "1. 自動過濾本機檔案路徑、API Key、私有 IP 及使用者名稱\n"
            "2. 請求時強制注入零儲存參數 (ZDR: True, store: False)"
        )
        msg_box = QLabel(desc_text)
        msg_box.setWordWrap(True)
        msg_box.setStyleSheet(f"color: {'#cbd5e1' if is_dark else '#334155'}; font-size: 12px; line-height: 1.4;")
        lay.addWidget(msg_box, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_ok = QPushButton("了解並確認")
        btn_ok.setObjectName("primary")
        btn_ok.setFixedWidth(110)
        btn_ok.clicked.connect(self.accept)
        btn_row.addWidget(btn_ok)
        lay.addLayout(btn_row)

        outer.addWidget(content, 1)

    def showEvent(self, e):
        super().showEvent(e)
        center_dialog(self)
        self.raise_()
        self.activateWindow()


class ApiKeyExportWarningDialog(QDialog):
    """API Key 敏感憑證匯出高風險安全警告對話框。
    強制執行 5 秒倒數鎖定，未倒數完畢前確認按鈕禁用。
    """
    def __init__(self, parent=None, theme: str | None = None):
        super().__init__(parent, Qt.FramelessWindowHint | Qt.Window | Qt.WindowStaysOnTopHint)
        self.setFixedSize(500, 240)
        self.countdown = 5

        if not theme:
            if hasattr(parent, "cfg") and hasattr(parent.cfg, "get"):
                theme = parent.cfg.get("theme", "light")
            elif hasattr(parent, "app") and hasattr(parent.app, "cfg"):
                theme = parent.app.cfg.get("theme", "light")
            else:
                theme = "light"
        is_dark = (theme == "dark")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(DIALOG_DARK_QSS if is_dark else DIALOG_LIGHT_QSS)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.title_bar = CustomTitleBar(self, "高風險安全警告", has_min=False, has_close=True, theme="dark" if is_dark else "light")
        outer.addWidget(self.title_bar)

        content = QWidget()
        content.setObjectName("ApiKeyWarningContent")
        content.setAttribute(Qt.WA_StyledBackground, True)
        bg_col = "#16181d" if is_dark else "#f8f9fa"
        border_col = "#ef4444" if is_dark else "#dc2626"
        content.setStyleSheet(
            f"QWidget#ApiKeyWarningContent {{ background-color: {bg_col}; border: 1.5px solid {border_col}; border-top: none; border-bottom-left-radius: 12px; border-bottom-right-radius: 12px; }}"
        )
        lay = QVBoxLayout(content)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(14)

        msg_lay = QHBoxLayout()
        msg_lay.setSpacing(14)

        lb_icon = QLabel()
        lb_icon.setPixmap(get_icon("warning", "#ef4444" if is_dark else "#dc2626", 36).pixmap(36, 36))
        lb_icon.setFixedSize(40, 40)
        lb_icon.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        msg_lay.addWidget(lb_icon)

        warn_text = (
            "警告：此匯出檔案將包含未加密的 API 金鑰與機密憑證，若外洩將造成額度被盜用或資產損失！"
            "請確認僅在安全且受信任的個人本機保存。"
        )
        lb_text = QLabel(warn_text)
        lb_text.setWordWrap(True)
        lb_text.setStyleSheet(
            f"color: {'#fca5a5' if is_dark else '#991b1b'}; font-size: 13px; font-weight: bold; line-height: 1.5;"
        )
        msg_lay.addWidget(lb_text, 1)
        lay.addLayout(msg_lay, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)

        b_cancel = QPushButton("取消")
        b_cancel.setFixedWidth(90)
        b_cancel.clicked.connect(self.reject)
        btn_row.addWidget(b_cancel)

        self.b_confirm = QPushButton("已知曉風險，確認匯出 (5s)...")
        self.b_confirm.setObjectName("danger")
        self.b_confirm.setMinimumWidth(210)
        self.b_confirm.setEnabled(False)
        self.b_confirm.clicked.connect(self.accept)
        btn_row.addWidget(self.b_confirm)
        lay.addLayout(btn_row)

        outer.addWidget(content, 1)

        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self._on_tick)
        self.timer.start()

    def _on_tick(self):
        self.countdown -= 1
        if self.countdown > 0:
            self.b_confirm.setText(f"已知曉風險，確認匯出 ({self.countdown}s)...")
        else:
            self.timer.stop()
            self.b_confirm.setEnabled(True)
            self.b_confirm.setText("確認包含金鑰匯出")

    def showEvent(self, e):
        super().showEvent(e)
        center_dialog(self)
        self.raise_()
        self.activateWindow()

    def closeEvent(self, e):
        self.timer.stop()
        super().closeEvent(e)


class ExportSettingsDialog(QDialog):
    """全設定與資料安全匯出對話框。
    支援 API Key 安全防護勾選、5秒倒數安全確認及 YuYue 8層複合高強度密碼加密。
    """
    def __init__(self, app, parent=None):
        super().__init__(parent, Qt.FramelessWindowHint | Qt.Window | Qt.WindowStaysOnTopHint)
        self.app = app
        self.setWindowTitle("匯出所有設定與資料")
        self.setFixedSize(520, 360)
        self._keys_confirmed = False

        theme = self.app.cfg.get("theme", "light")
        self.theme = theme
        is_dark = (theme == "dark")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(DIALOG_DARK_QSS if is_dark else DIALOG_LIGHT_QSS)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.title_bar = CustomTitleBar(self, "匯出所有設定與資料", has_min=False, has_close=True, theme="dark" if is_dark else "light")
        outer.addWidget(self.title_bar)

        content = QWidget()
        content.setObjectName("ExportDialogContent")
        content.setAttribute(Qt.WA_StyledBackground, True)
        bg_col = "#16181d" if is_dark else "#f8f9fa"
        content.setStyleSheet(
            f"QWidget#ExportDialogContent {{ background-color: {bg_col}; border-bottom-left-radius: 12px; border-bottom-right-radius: 12px; }}"
        )
        lay = QVBoxLayout(content)
        lay.setContentsMargins(22, 18, 22, 18)
        lay.setSpacing(14)

        desc = QLabel(
            "將完整的寵物配置（視窗位置、角色、音量、字體、鬧鐘、通知、自訂角色立繪與系統偏好）匯出為備份檔案。"
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {'#cbd5e1' if is_dark else '#334155'}; font-size: 12px; line-height: 1.4;")
        lay.addWidget(desc)

        # 敏感金鑰選項 (預設 False)
        self.chk_keys = QCheckBox("包含 API 金鑰與敏感憑證")
        self.chk_keys.setChecked(False)
        self.chk_keys.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {'#f87171' if is_dark else '#b91c1c'};")
        self.chk_keys.toggled.connect(self._on_keys_toggled)
        lay.addWidget(self.chk_keys)

        keys_hint = QLabel("未勾選時：自動剔除或脫敏所有金鑰，安全無虞。\n勾選時：將強制進行 5 秒倒數確認，請謹慎保存。")
        keys_hint.setStyleSheet(f"color: {'#94a3b8' if is_dark else '#64748b'}; font-size: 11px;")
        lay.addWidget(keys_hint)

        # YuYue 加密選項
        self.chk_encrypt = QCheckBox("設定自訂保護密碼（YuYue 複合高強度加密）")
        self.chk_encrypt.setChecked(False)
        self.chk_encrypt.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {'#93c5fd' if is_dark else '#1d4ed8'};")
        self.chk_encrypt.toggled.connect(self._on_encrypt_toggled)
        lay.addWidget(self.chk_encrypt)

        self.ed_password = QLineEdit()
        self.ed_password.setEchoMode(QLineEdit.Password)
        self.ed_password.setPlaceholderText("請輸入備份保護密碼...")
        self.ed_password.setEnabled(False)
        lay.addWidget(self.ed_password)

        lay.addStretch(1)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        b_cancel = QPushButton("取消")
        b_cancel.clicked.connect(self.reject)
        btn_row.addWidget(b_cancel)

        b_export = QPushButton("匯出設定")
        b_export.setObjectName("primary")
        b_export.clicked.connect(self._do_export)
        btn_row.addWidget(b_export)
        lay.addLayout(btn_row)

        outer.addWidget(content, 1)

    def _on_keys_toggled(self, checked: bool):
        if checked:
            dlg = ApiKeyExportWarningDialog(self, theme=self.theme)
            if dlg.exec() != QDialog.Accepted:
                self.chk_keys.blockSignals(True)
                self.chk_keys.setChecked(False)
                self.chk_keys.blockSignals(False)
                self._keys_confirmed = False
            else:
                self._keys_confirmed = True
        else:
            self._keys_confirmed = False

    def _on_encrypt_toggled(self, checked: bool):
        self.ed_password.setEnabled(checked)
        if checked:
            self.ed_password.setFocus()
        else:
            self.ed_password.clear()

    def _do_export(self):
        from .export_data import export_backup_data

        if self.chk_keys.isChecked() and not self._keys_confirmed:
            dlg = ApiKeyExportWarningDialog(self, theme=self.theme)
            if dlg.exec() != QDialog.Accepted:
                return
            self._keys_confirmed = True

        pwd = ""
        if self.chk_encrypt.isChecked():
            pwd = self.ed_password.text().strip()
            if not pwd:
                ModernMessageBox.warning(self, "密碼未填寫", "已勾選保護密碼選項，請輸入加密密碼。")
                return

        date_str = datetime.now().strftime("%Y%m%d")
        default_name = f"deskpet_backup_{date_str}.dpbak" if pwd else f"deskpet_backup_{date_str}.json"
        filter_str = "YuYue 加密備份檔 (*.dpbak);;JSON 備份檔案 (*.json)" if pwd else "JSON 備份檔案 (*.json);;所有檔案 (*.*)"
        dest, _ = QFileDialog.getSaveFileName(self, "儲存備份檔案", default_name, filter_str)
        if not dest:
            return

        try:
            export_backup_data(self.app.cfg, dest, include_keys=self.chk_keys.isChecked(), password=pwd)
            ModernMessageBox.information(self, "匯出成功", f"全設定與資料已安全匯出至：\n{dest}")
            self.accept()
        except Exception as e:
            ModernMessageBox.warning(self, "匯出失敗", f"匯出過程發生錯誤：{e}")

    def showEvent(self, e):
        super().showEvent(e)
        center_dialog(self)
        self.raise_()
        self.activateWindow()


class ImportPasswordDialog(QDialog):
    """YuYue 加密備份還原密碼輸入對話框。"""
    def __init__(self, parent=None, theme: str | None = None):
        super().__init__(parent, Qt.FramelessWindowHint | Qt.Window | Qt.WindowStaysOnTopHint)
        self.setFixedSize(400, 210)
        self.password = ""

        if not theme:
            if hasattr(parent, "cfg") and hasattr(parent.cfg, "get"):
                theme = parent.cfg.get("theme", "light")
            else:
                theme = "light"
        is_dark = (theme == "dark")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(DIALOG_DARK_QSS if is_dark else DIALOG_LIGHT_QSS)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.title_bar = CustomTitleBar(self, "輸入備份保護密碼", has_min=False, has_close=True, theme="dark" if is_dark else "light")
        outer.addWidget(self.title_bar)

        content = QWidget()
        content.setObjectName("ImportPasswordContent")
        content.setAttribute(Qt.WA_StyledBackground, True)
        bg_col = "#16181d" if is_dark else "#f8f9fa"
        content.setStyleSheet(
            f"QWidget#ImportPasswordContent {{ background-color: {bg_col}; border-bottom-left-radius: 12px; border-bottom-right-radius: 12px; }}"
        )
        lay = QVBoxLayout(content)
        lay.setContentsMargins(22, 16, 22, 16)
        lay.setSpacing(12)

        lbl = QLabel("此檔案已啟用 YuYue 複合高強度加密保護，請輸入解鎖密碼：")
        lbl.setWordWrap(True)
        lbl.setStyleSheet(f"font-size: 12px; color: {'#e2e8f0' if is_dark else '#1e293b'};")
        lay.addWidget(lbl)

        self.ed_pwd = QLineEdit()
        self.ed_pwd.setEchoMode(QLineEdit.Password)
        self.ed_pwd.setPlaceholderText("請輸入解密密碼...")
        lay.addWidget(self.ed_pwd)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        b_cancel = QPushButton("取消")
        b_cancel.clicked.connect(self.reject)
        btn_row.addWidget(b_cancel)

        b_ok = QPushButton("解密並匯入")
        b_ok.setObjectName("primary")
        b_ok.clicked.connect(self._on_confirm)
        btn_row.addWidget(b_ok)
        lay.addLayout(btn_row)

        outer.addWidget(content, 1)

    def _on_confirm(self):
        self.password = self.ed_pwd.text().strip()
        if not self.password:
            ModernMessageBox.warning(self, "密碼為空", "請輸入解密密碼。")
            return
        self.accept()

    def showEvent(self, e):
        super().showEvent(e)
        center_dialog(self)
        self.raise_()
        self.activateWindow()
