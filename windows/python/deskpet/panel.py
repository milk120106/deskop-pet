"""Material Design 3 style Control Panel for Desktop Pet.
Features responsive card layouts, sidebar navigation, full dark/light theming,
custom draggable titlebar with minimize/close buttons, typography font system,
global live logging viewer, AI & Gemini Live settings, remote model discovery,
and community art resource invitation.
Strictly zero emojis used anywhere.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QRectF, QThread, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGraphicsOpacityEffect,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .chat import ApiProfileDialog, MemoryDialog, ModelListWorker, VoiceSettingsDialog
from .config import (
    APP_DIR,
    APP_VERSION,
    CUSTOM_CHARS_DIR,
    GITHUB_RELEASES_API,
    GITHUB_RELEASES_URL,
    GITHUB_REPO_URL,
    PROV_IDS,
    PROV_NAMES,
    SOUND_LIB_DIR,
)
from .dialogs import CharPickerDialog, CustomQDialog, SoundLibraryDialog
from .font_manager import (
    apply_global_font,
    get_system_fonts,
    load_font_file,
    resolve_best_default_font,
)
from .icons import get_icon
from .logger import LOGS_DIR, check_crash, clear_memory_buffer, get_recent_logs
from .model_catalog import PROVIDERS, ModelCatalogError, discover_models
from .titlebar import CustomTitleBar

# ========================================================= Material Design 3 Stylesheets
LIGHT_MD3_QSS = """
QWidget {
    background-color: #f8f9fa;
    color: #1f2937;
    font-family: 'Segoe UI Variable Text', 'Microsoft JhengHei UI', 'PingFang TC', 'Noto Sans TC', sans-serif;
    font-size: 13px;
}
#Sidebar {
    background-color: #edf2f7;
    border-right: 1px solid #e2e8f0;
}
#AppTitle {
    font-size: 16px;
    font-weight: bold;
    color: #1e3a8a;
    padding: 6px 0 2px 0;
    background-color: transparent;
}
#AppSubtitle {
    font-size: 11px;
    color: #64748b;
    padding-bottom: 8px;
    background-color: transparent;
}
QListWidget#NavList {
    background-color: transparent;
    border: none;
    outline: none;
}
QListWidget#NavList::item {
    height: 38px;
    padding-left: 14px;
    margin: 2px 8px;
    border-radius: 19px;
    color: #334155;
    font-weight: 500;
}
QListWidget#NavList::item:hover {
    background-color: #e2e8f0;
    color: #0f172a;
}
QListWidget#NavList::item:selected {
    background-color: #dbeafe;
    color: #1d4ed8;
    font-weight: bold;
}
QScrollArea, #CardContainer, #CardViewport {
    background-color: #f8f9fa;
    border: none;
}
QGroupBox {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 14px;
    margin-top: 18px;
    padding: 18px 16px 16px 16px;
    font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 16px;
    padding: 0 6px;
    color: #1e40af;
    background-color: transparent;
}
QFrame#AboutCard {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 14px;
    padding: 16px;
}
QLabel {
    background-color: transparent;
    color: #1f2937;
}
QLabel#PageTitle {
    font-size: 18px;
    font-weight: bold;
    color: #0f172a;
    margin-bottom: 2px;
    background-color: transparent;
}
QLabel#PageDesc {
    font-size: 12px;
    color: #64748b;
    margin-bottom: 10px;
    background-color: transparent;
}
QLabel#hint {
    color: #64748b;
    font-size: 12px;
    line-height: 1.45;
    background-color: transparent;
}
QPushButton {
    background-color: #e2e8f0;
    color: #1e293b;
    border: 1px solid #cbd5e1;
    border-radius: 16px;
    padding: 6px 16px;
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
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    padding: 6px 10px;
    color: #0f172a;
}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
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
    width: 18px;
    height: 18px;
    margin: -6px 0;
    border-radius: 9px;
    background: #2563eb;
}
QSlider::handle:horizontal:hover {
    background: #1d4ed8;
}
QCheckBox, QRadioButton {
    spacing: 8px;
    background-color: transparent;
}
QCheckBox::indicator, QRadioButton::indicator {
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 2px solid #94a3b8;
    background: #ffffff;
}
QRadioButton::indicator {
    border-radius: 9px;
}
QCheckBox::indicator:checked, QRadioButton::indicator:checked {
    background-color: #2563eb;
    border-color: #2563eb;
}
QScrollBar:vertical {
    border: none;
    background-color: #f8f9fa;
    width: 8px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background-color: #cbd5e1;
    min-height: 28px;
    border-radius: 4px;
    margin: 2px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
    background: none;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none;
}
QAbstractScrollArea::corner {
    background-color: #f8f9fa;
}
QTextEdit#LogViewer {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 8px;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 12px;
    color: #1e293b;
}
"""

DARK_MD3_QSS = """
QWidget {
    background-color: #16181d;
    color: #e2e2e6;
    font-family: 'Segoe UI Variable Text', 'Microsoft JhengHei UI', 'PingFang TC', 'Noto Sans TC', sans-serif;
    font-size: 13px;
}
#Sidebar {
    background-color: #1b1e26;
    border-right: 1px solid #282c37;
}
#AppTitle {
    font-size: 16px;
    font-weight: bold;
    color: #93c5fd;
    padding: 6px 0 2px 0;
    background-color: transparent;
}
#AppSubtitle {
    font-size: 11px;
    color: #8c9199;
    padding-bottom: 8px;
    background-color: transparent;
}
QListWidget#NavList {
    background-color: transparent;
    border: none;
    outline: none;
}
QListWidget#NavList::item {
    height: 38px;
    padding-left: 14px;
    margin: 2px 8px;
    border-radius: 19px;
    color: #c4c7c5;
    font-weight: 500;
}
QListWidget#NavList::item:hover {
    background-color: #282c37;
    color: #ffffff;
}
QListWidget#NavList::item:selected {
    background-color: #2c3954;
    color: #93c5fd;
    font-weight: bold;
}
QScrollArea, #CardContainer, #CardViewport {
    background-color: #16181d;
    border: none;
}
QGroupBox {
    background-color: #20232a;
    border: 1px solid #2d313b;
    border-radius: 14px;
    margin-top: 18px;
    padding: 18px 16px 16px 16px;
    font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 16px;
    padding: 0 6px;
    color: #93c5fd;
    background-color: transparent;
}
QFrame#AboutCard {
    background-color: #20232a;
    border: 1px solid #2d313b;
    border-radius: 14px;
    padding: 16px;
}
QLabel {
    background-color: transparent;
    color: #e2e2e6;
}
QLabel#PageTitle {
    font-size: 18px;
    font-weight: bold;
    color: #ffffff;
    margin-bottom: 2px;
    background-color: transparent;
}
QLabel#PageDesc {
    font-size: 12px;
    color: #8c9199;
    margin-bottom: 10px;
    background-color: transparent;
}
QLabel#hint {
    color: #8c9199;
    font-size: 12px;
    line-height: 1.45;
    background-color: transparent;
}
QPushButton {
    background-color: #282c37;
    color: #e2e2e6;
    border: 1px solid #3b404d;
    border-radius: 16px;
    padding: 6px 16px;
    min-height: 24px;
    font-weight: 500;
}
QPushButton:hover {
    background-color: #3b404d;
    border-color: #555b6d;
}
QPushButton:pressed {
    background-color: #1f232b;
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
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: #1f232b;
    border: 1px solid #3b404d;
    border-radius: 8px;
    padding: 6px 10px;
    color: #ffffff;
}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border: 2px solid #3b82f6;
}
QComboBox QAbstractItemView {
    background-color: #1f232b;
    border: 1px solid #3b404d;
    border-radius: 8px;
    selection-background-color: #2c3954;
    selection-color: #93c5fd;
    padding: 4px;
    outline: none;
}
QSlider::groove:horizontal {
    height: 6px;
    background: #282c37;
    border-radius: 3px;
}
QSlider::sub-page:horizontal {
    background: #3b82f6;
    border-radius: 3px;
}
QSlider::handle:horizontal {
    width: 18px;
    height: 18px;
    margin: -6px 0;
    border-radius: 9px;
    background: #3b82f6;
}
QSlider::handle:horizontal:hover {
    background: #60a5fa;
}
QCheckBox, QRadioButton {
    spacing: 8px;
    background-color: transparent;
}
QCheckBox::indicator, QRadioButton::indicator {
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 2px solid #555b6d;
    background: #1f232b;
}
QRadioButton::indicator {
    border-radius: 9px;
}
QCheckBox::indicator:checked, QRadioButton::indicator:checked {
    background-color: #3b82f6;
    border-color: #3b82f6;
}
QScrollBar:vertical {
    border: none;
    background-color: #16181d;
    width: 8px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background-color: #3b404d;
    min-height: 28px;
    border-radius: 4px;
    margin: 2px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
    background: none;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none;
}
QAbstractScrollArea::corner {
    background-color: #16181d;
}
QTextEdit#LogViewer {
    background-color: #1a1c23;
    border: 1px solid #2d313b;
    border-radius: 10px;
    padding: 8px;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 12px;
    color: #e2e2e6;
}
"""


# ========================================================= Background Update Worker
class UpdateCheckWorker(QThread):
    finished = Signal(bool, str, str, str)  # (ok, tag, url, msg)

    def run(self):
        try:
            req = urllib.request.Request(
                GITHUB_RELEASES_API,
                headers={"User-Agent": "DesktopPet/2.1.0", "Accept": "application/vnd.github.v3+json"},
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            tag = data.get("tag_name", "").strip()
            url = data.get("html_url", GITHUB_RELEASES_URL)
            body = data.get("body", "")
            self.finished.emit(True, tag, url, body)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                self.finished.emit(
                    True, "", GITHUB_RELEASES_URL, "已連線至 GitHub 倉庫，目前尚未建立正式 Release 標籤（當前版本 v2.1.0 為最新版本）。"
                )
            else:
                self.finished.emit(False, "", GITHUB_RELEASES_URL, f"HTTP 回應狀態：{e.code} {e.reason}")
        except Exception as e:
            self.finished.emit(False, "", GITHUB_RELEASES_URL, f"連線至 GitHub 失敗：{e}")


# ========================================================= Helpers
def _hint(text: str) -> QLabel:
    lb = QLabel(text)
    lb.setObjectName("hint")
    lb.setWordWrap(True)
    return lb


def _slider(lo: int, hi: int, val: int, cb) -> QSlider:
    s = QSlider(Qt.Horizontal)
    s.setRange(lo, hi)
    s.setValue(val)
    s.valueChanged.connect(cb)
    return s


def _page_wrapper(page_widget: QWidget) -> QScrollArea:
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    scroll.setFrameShape(QFrame.NoFrame)
    container = QWidget()
    container.setObjectName("CardContainer")
    container.setAttribute(Qt.WA_StyledBackground, True)
    lay = QVBoxLayout(container)
    lay.setContentsMargins(26, 20, 26, 24)
    lay.setSpacing(16)
    lay.addWidget(page_widget)
    scroll.setWidget(container)
    return scroll


# ========================================================= Control Panel Main Window
class ControlPanel(QWidget):
    def __init__(self, app):
        super().__init__(None, Qt.FramelessWindowHint | Qt.Window | Qt.WindowStaysOnTopHint)
        self.app = app
        self.cfg = app.cfg
        self.setWindowTitle("桌面寵物 控制中心")
        self.setFixedSize(960, 650)
        self._lock = False
        self._disc_worker = None
        self._update_worker = None

        is_dark = (self.cfg.get("theme", "light") == "dark")

        # Root layout: TitleBar (Top) + Body (Bottom)
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.title_bar = CustomTitleBar(self, "桌面寵物 控制中心", has_min=True, has_close=True, theme="dark" if is_dark else "light")
        root_layout.addWidget(self.title_bar)

        body_widget = QWidget()
        main_layout = QHBoxLayout(body_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        root_layout.addWidget(body_widget, 1)

        # ---------------- Left Sidebar (Navigation Rail)
        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setAttribute(Qt.WA_StyledBackground, True)
        sidebar.setFixedWidth(210)
        sb_lay = QVBoxLayout(sidebar)
        sb_lay.setContentsMargins(14, 16, 14, 16)
        sb_lay.setSpacing(8)

        title_lbl = QLabel("桌面寵物")
        title_lbl.setObjectName("AppTitle")
        sb_lay.addWidget(title_lbl)

        sub_lbl = QLabel("控制台中心 · MD3")
        sub_lbl.setObjectName("AppSubtitle")
        sb_lay.addWidget(sub_lbl)

        self.nav_list = QListWidget()
        self.nav_list.setObjectName("NavList")
        nav_items = [
            "視窗設定",
            "角色與形態",
            "Q 版夥伴",
            "互動演示",
            "聲音設定",
            "AI 對話與語音",
            "API 與餘額",
            "網頁儀表板",
            "全域日誌",
            "關於本軟體",
        ]
        self._idx_logs = nav_items.index("全域日誌")
        for name in nav_items:
            it = QListWidgetItem(name)
            self.nav_list.addItem(it)
        self.nav_list.currentRowChanged.connect(self._on_nav_changed)
        sb_lay.addWidget(self.nav_list, 1)

        # Bottom actions in sidebar
        btn_theme = QPushButton("切換主題")
        btn_theme.setIcon(get_icon("palette", "#64748b", 16))
        btn_theme.clicked.connect(self._toggle_theme)
        sb_lay.addWidget(btn_theme)

        quit_btn = QPushButton("退出程式")
        quit_btn.setObjectName("danger")
        quit_btn.setIcon(get_icon("close", "#ffffff", 16))
        quit_btn.clicked.connect(app.quit)
        sb_lay.addWidget(quit_btn)

        main_layout.addWidget(sidebar)

        # ---------------- Right Content Area (StackedWidget)
        self.stack = QStackedWidget()
        self.stack.setObjectName("ContentStack")
        self.stack.setAttribute(Qt.WA_StyledBackground, True)
        self.opacity_effect = QGraphicsOpacityEffect(self.stack)
        self.stack.setGraphicsEffect(self.opacity_effect)

        self.fade_anim = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_anim.setDuration(180)
        self.fade_anim.setEasingCurve(QEasingCurve.OutCubic)

        # Add 10 Pages
        self.stack.addWidget(_page_wrapper(self._tab_window()))
        self.stack.addWidget(_page_wrapper(self._tab_character()))
        self.stack.addWidget(_page_wrapper(self._tab_q()))
        self.stack.addWidget(_page_wrapper(self._tab_demo()))
        self.stack.addWidget(_page_wrapper(self._tab_sound()))
        self.stack.addWidget(_page_wrapper(self._tab_ai_voice()))
        self.stack.addWidget(_page_wrapper(self._tab_balance()))
        self.stack.addWidget(_page_wrapper(self._tab_web()))
        self.stack.addWidget(_page_wrapper(self._tab_logs()))
        self.stack.addWidget(_page_wrapper(self._tab_about()))

        main_layout.addWidget(self.stack, 1)

        # Periodic status refresh
        self.status_timer = QTimer(self)
        self.status_timer.setInterval(1000)
        self.status_timer.timeout.connect(self._status)

        # Log refresh timer
        self.log_timer = QTimer(self)
        self.log_timer.setInterval(600)
        self.log_timer.timeout.connect(self._refresh_logs)

        self.nav_list.setCurrentRow(0)

        app.state_changed.connect(self.sync)
        self.apply_theme()
        self.sync()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(e)

    def _on_nav_changed(self, idx: int):
        if idx < 0 or idx >= self.stack.count():
            return
        self.stack.setCurrentIndex(idx)
        self.fade_anim.stop()
        self.fade_anim.setStartValue(0.3)
        self.fade_anim.setEndValue(1.0)
        self.fade_anim.start()

        if hasattr(self, "log_timer"):
            if idx == self._idx_logs:
                self._refresh_logs()
                if not self.log_timer.isActive():
                    self.log_timer.start()
            else:
                self.log_timer.stop()

    def _toggle_theme(self):
        cur = self.cfg.get("theme", "light")
        next_t = "dark" if cur == "light" else "light"
        self._do(self.app.set_theme, next_t)
        self.cmb_theme.setCurrentIndex(1 if next_t == "dark" else 0)
        self.apply_theme()

    # ------------------------------------------------------------- 1. 視窗設定 (包含自訂字體模組)
    def _tab_window(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)

        t_lbl = QLabel("視窗行為、外觀與字體系統")
        t_lbl.setObjectName("PageTitle")
        d_lbl = QLabel("設定桌面寵物的常駐、穿透、貼邊、透明度與自訂文字排版引擎")
        d_lbl.setObjectName("PageDesc")
        lay.addWidget(t_lbl)
        lay.addWidget(d_lbl)

        # 1. 互動行為
        g = QGroupBox("視窗互動行為")
        f = QVBoxLayout(g)
        f.setContentsMargins(16, 18, 16, 16)
        f.setSpacing(12)

        self.cb_through = QCheckBox("滑鼠穿透（游標穿透寵物與物件）")
        self.cb_through.toggled.connect(lambda v: self._do(self.app.set_click_through, v))
        f.addWidget(self.cb_through)
        f.addWidget(_hint("開啟後滑鼠點擊會穿透寵物與物件，若欲還原可在工作列右下角托盤選單關閉。"))

        self.cb_snap = QCheckBox("自動貼邊（放開滑鼠時自動吸附至最近螢幕邊緣並轉向面向內側）")
        self.cb_snap.toggled.connect(lambda v: self._do(self.app.set_auto_snap, v))
        f.addWidget(self.cb_snap)

        r = QHBoxLayout()
        r.addWidget(QLabel("貼邊距離"))
        self.sl_snap = _slider(20, 300, 120, lambda v: self._do(self.app.set_snap_distance, v))
        self.lb_snap = QLabel("120 px")
        self.lb_snap.setFixedWidth(55)
        r.addWidget(self.sl_snap, 1)
        r.addWidget(self.lb_snap)
        f.addLayout(r)

        r_corn = QHBoxLayout()
        b1 = QPushButton("吸附到左下角（面向右側）")
        b1.clicked.connect(lambda: self.app.go_corner("left"))
        b2 = QPushButton("吸附到右下角（面向左側）")
        b2.clicked.connect(lambda: self.app.go_corner("right"))
        r_corn.addWidget(b1)
        r_corn.addWidget(b2)
        f.addLayout(r_corn)

        self.cb_top = QCheckBox("永遠置頂（保持在一般視窗最上層）")
        self.cb_top.toggled.connect(lambda v: self._do(self.app.set_topmost, v))
        f.addWidget(self.cb_top)

        self.cb_pat = QCheckBox("滑鼠撫摸互動（在角色身上來回滑動可觸發摸頭；鐵盆扣在頭頂時單擊即可取下）")
        self.cb_pat.toggled.connect(lambda v: self._do(self.app.set_pat, v))
        f.addWidget(self.cb_pat)

        r_op = QHBoxLayout()
        r_op.addWidget(QLabel("透明度"))
        self.sl_op = _slider(20, 100, 100, lambda v: self._do(self.app.set_opacity, v))
        self.lb_op = QLabel("100 %")
        self.lb_op.setFixedWidth(55)
        r_op.addWidget(self.sl_op, 1)
        r_op.addWidget(self.lb_op)
        f.addLayout(r_op)
        lay.addWidget(g)

        # 2. 尺寸大小
        g2 = QGroupBox("尺寸大小 (Height)")
        f2 = QVBoxLayout(g2)
        f2.setContentsMargins(16, 18, 16, 16)
        f2.setSpacing(12)

        r_cup = QHBoxLayout()
        for name, px in (("中杯 340", 340), ("大杯 454", 454), ("超大杯 624", 624)):
            b = QPushButton(name)
            b.clicked.connect(lambda _=False, v=px: self.app.set_size(v))
            r_cup.addWidget(b)
        f2.addLayout(r_cup)

        r2 = QHBoxLayout()
        self.sp_size = QSpinBox()
        self.sp_size.setRange(200, 1400)
        self.sp_size.setSuffix(" px")
        b = QPushButton("套用自訂尺寸")
        b.clicked.connect(lambda: self.app.set_size(self.sp_size.value()))
        r2.addWidget(self.sp_size, 1)
        r2.addWidget(b)
        f2.addLayout(r2)
        lay.addWidget(g2)

        # 3. 自訂字體系統 (Typography System)
        g_font = QGroupBox("自訂字體系統 (Typography && Fonts)")
        f_font = QVBoxLayout(g_font)
        f_font.setContentsMargins(16, 18, 16, 16)
        f_font.setSpacing(12)

        f_font.addWidget(_hint("支援系統安裝字型選取或自訂 .ttf / .otf 檔案匯入，全域即時套用並儲存偏好設定。"))

        r_fmode = QHBoxLayout()
        self.rb_font_sys = QRadioButton("模式一：從系統讀取並選擇字體")
        self.rb_font_file = QRadioButton("模式二：匯入自訂字體檔案 (.ttf / .otf)")
        self.rb_font_sys.setChecked(True)
        r_fmode.addWidget(self.rb_font_sys)
        r_fmode.addWidget(self.rb_font_file)
        f_font.addLayout(r_fmode)

        # Mode 1 Container (System Fonts)
        self.w_font_sys = QWidget()
        lay_font_sys = QHBoxLayout(self.w_font_sys)
        lay_font_sys.setContentsMargins(0, 0, 0, 0)
        lay_font_sys.addWidget(QLabel("系統字型:"))
        self.cmb_sys_fonts = QComboBox()
        self.cmb_sys_fonts.setMaxVisibleItems(15)
        for fam in get_system_fonts():
            self.cmb_sys_fonts.addItem(fam)
        self.cmb_sys_fonts.currentTextChanged.connect(self._update_font_preview)
        lay_font_sys.addWidget(self.cmb_sys_fonts, 1)
        f_font.addWidget(self.w_font_sys)

        # Mode 2 Container (Custom File)
        self.w_font_file = QWidget()
        self.w_font_file.hide()
        lay_font_file = QHBoxLayout(self.w_font_file)
        lay_font_file.setContentsMargins(0, 0, 0, 0)
        lay_font_file.addWidget(QLabel("字體檔案:"))
        self.ed_font_path = QLineEdit()
        self.ed_font_path.setPlaceholderText("請選取 .ttf 或 .otf 字體檔案路徑")
        self.ed_font_path.textChanged.connect(self._update_font_preview)
        b_browse_font = QPushButton("瀏覽選取字體檔...")
        b_browse_font.clicked.connect(self._browse_custom_font)
        lay_font_file.addWidget(self.ed_font_path, 1)
        lay_font_file.addWidget(b_browse_font)
        f_font.addWidget(self.w_font_file)

        # Font Preview Box
        self.lb_font_preview = QLabel("繁體中文排版預覽：永遠熱愛生活，桌面寵物陪伴你的每一天。0123456789")
        self.lb_font_preview.setWordWrap(True)
        self.lb_font_preview.setStyleSheet("""
            QLabel {
                padding: 10px 14px;
                border: 1px dashed #64748b;
                border-radius: 8px;
                background-color: transparent;
                font-size: 14px;
            }
        """)
        f_font.addWidget(self.lb_font_preview)

        # Buttons row
        r_fbtns = QHBoxLayout()
        b_apply_font = QPushButton("套用選定字體")
        b_apply_font.setObjectName("primary")
        b_apply_font.clicked.connect(self._apply_selected_font)
        b_reset_font = QPushButton("重設為現代預設字體")
        b_reset_font.clicked.connect(self._reset_default_font)
        r_fbtns.addWidget(b_apply_font)
        r_fbtns.addWidget(b_reset_font)
        r_fbtns.addStretch(1)
        f_font.addLayout(r_fbtns)

        self.lb_font_status = QLabel("目前狀態：使用現代預設字體堆疊")
        self.lb_font_status.setStyleSheet("color: #64748b; font-size: 12px;")
        f_font.addWidget(self.lb_font_status)

        self.rb_font_sys.toggled.connect(self._on_font_mode_toggled)
        self.rb_font_file.toggled.connect(self._on_font_mode_toggled)
        lay.addWidget(g_font)

        # 4. 外觀佈景主題
        g3 = QGroupBox("外觀佈景主題")
        f3 = QHBoxLayout(g3)
        f3.setContentsMargins(16, 18, 16, 16)
        f3.addWidget(QLabel("控制台主題風格"))
        self.cmb_theme = QComboBox()
        self.cmb_theme.addItems(["淺色 (Light)", "深色 (Dark)"])
        self.cmb_theme.currentIndexChanged.connect(
            lambda i: self._do(self.app.set_theme, "dark" if i else "light"))
        f3.addWidget(self.cmb_theme, 1)
        lay.addWidget(g3)

        lay.addStretch(1)
        return w

    def _on_font_mode_toggled(self):
        if self.rb_font_sys.isChecked():
            self.w_font_sys.show()
            self.w_font_file.hide()
        else:
            self.w_font_sys.hide()
            self.w_font_file.show()
        self._update_font_preview()

    def _browse_custom_font(self):
        path, _ = QFileDialog.getOpenFileName(self, "選取字體檔案", "", "字體檔案 (*.ttf *.otf *.ttc)")
        if path:
            self.ed_font_path.setText(path)
            self._update_font_preview()

    def _update_font_preview(self):
        if self.rb_font_file.isChecked():
            path = self.ed_font_path.text().strip()
            if path and Path(path).exists():
                ok, fam, _ = load_font_file(path)
                if ok:
                    f = QFont(fam, 11)
                    self.lb_font_preview.setFont(f)
                    return
        fam = self.cmb_sys_fonts.currentText()
        if fam:
            f = QFont(fam, 11)
            self.lb_font_preview.setFont(f)

    def _apply_selected_font(self):
        if self.rb_font_file.isChecked():
            path = self.ed_font_path.text().strip()
            if not path or not Path(path).exists():
                QMessageBox.warning(self, "提示", "請先選取有效的 .ttf 或 .otf 字體檔案。")
                return
            ok, fam, err = load_font_file(path)
            if not ok:
                QMessageBox.warning(self, "字體載入失敗", err)
                return
            apply_global_font(fam)
            self.cfg.set("font_mode", "custom_file", save=False)
            self.cfg.set("custom_font_path", path, save=False)
            self.cfg.set("font_family", fam, save=True)
            self.lb_font_status.setText(f"目前狀態：已套用自訂字體 [{fam}]")
            QMessageBox.information(self, "字體設定", f"已成功全域套用自訂字體：{fam}")
        else:
            fam = self.cmb_sys_fonts.currentText().strip()
            if not fam:
                return
            apply_global_font(fam)
            self.cfg.set("font_mode", "system", save=False)
            self.cfg.set("font_family", fam, save=True)
            self.lb_font_status.setText(f"目前狀態：已套用系統字體 [{fam}]")
            QMessageBox.information(self, "字體設定", f"已成功全域套用系統字體：{fam}")

    def _reset_default_font(self):
        best = resolve_best_default_font()
        apply_global_font(best)
        self.cfg.set("font_mode", "default", save=False)
        self.cfg.set("font_family", "", save=False)
        self.cfg.set("custom_font_path", "", save=True)
        self.rb_font_sys.setChecked(True)
        idx = self.cmb_sys_fonts.findText(best)
        if idx >= 0:
            self.cmb_sys_fonts.setCurrentIndex(idx)
        self.lb_font_status.setText(f"目前狀態：已還原為現代預設字體 [{best}]")
        self._update_font_preview()
        QMessageBox.information(self, "字體設定", f"已還原為現代排版預設字體：{best}")

    # ------------------------------------------------------------- 2. 角色與形態
    def _tab_character(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)

        t_lbl = QLabel("角色設定與比例形態")
        t_lbl.setObjectName("PageTitle")
        d_lbl = QLabel("切換桌面寵物角色立繪或調整正方形與寬屏比例")
        d_lbl.setObjectName("PageDesc")
        lay.addWidget(t_lbl)
        lay.addWidget(d_lbl)

        g = QGroupBox("目前角色資訊")
        f = QVBoxLayout(g)
        f.setContentsMargins(16, 18, 16, 16)
        f.setSpacing(12)

        self.lb_cur_char = QLabel("目前角色: --")
        self.lb_cur_char.setStyleSheet("font-size: 15px; font-weight: bold;")
        self.lb_cur_char.setWordWrap(True)
        f.addWidget(self.lb_cur_char)

        b_picker = QPushButton("開啟角色選擇視窗（切換角色 / 匯入自訂圖片）...")
        b_picker.setObjectName("primary")
        b_picker.clicked.connect(self._open_char_picker)
        f.addWidget(b_picker)
        lay.addWidget(g)

        g2 = QGroupBox("寵物形態比例（正方形 1:1 vs 完整立繪 1.5:1）")
        f2 = QVBoxLayout(g2)
        f2.setContentsMargins(16, 18, 16, 16)
        f2.setSpacing(12)

        r = QHBoxLayout()
        self.rb_var_square = QRadioButton("標準正方形形態 (1024×1024, 1:1)")
        self.rb_var_tail = QRadioButton("完整立繪寬屏形態 (1536×1024, 1.5:1)")
        self.rb_var_square.toggled.connect(lambda v: v and self._do(self.app.set_variant, "square"))
        self.rb_var_tail.toggled.connect(lambda v: v and self._do(self.app.set_variant, "tail"))
        r.addWidget(self.rb_var_square)
        r.addWidget(self.rb_var_tail)
        f2.addLayout(r)
        f2.addWidget(_hint("提供標準正方形 (1:1) 與完整立繪寬屏 (1.5:1) 兩種比例形態，手持平板與視窗邊界將自動精準適配。"))
        lay.addWidget(g2)

        lay.addStretch(1)
        return w

    def _open_char_picker(self):
        parent = self if self.isVisible() else None
        dlg = CharPickerDialog(self.app, parent)
        dlg.exec()
        self.sync()

    # ------------------------------------------------------------- 3. Q版角色
    def _tab_q(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)

        t_lbl = QLabel("Q 版桌面夥伴")
        t_lbl.setObjectName("PageTitle")
        d_lbl = QLabel("管理在桌面漫步巡邏的 Q 版夥伴與暗黑模式風格")
        d_lbl.setObjectName("PageDesc")
        lay.addWidget(t_lbl)
        lay.addWidget(d_lbl)

        g = QGroupBox("黑化風格模式（限 DeepSeek Q 版角色）")
        f = QVBoxLayout(g)
        f.setContentsMargins(16, 18, 16, 16)
        f.setSpacing(12)

        self.cb_dark = QCheckBox("啟用黑化模式：DeepSeek Q 版夥伴切換為暗黑立繪")
        self.cb_dark.toggled.connect(lambda v: self._do(self.app.set_q_dark, v))
        f.addWidget(self.cb_dark)
        f.addWidget(_hint("功能說明：開啟後 DeepSeek 角色將啟用暗色調立繪風格與暗紅光暈特效；扣費互動時將呈現專屬跳躍反饋。"))
        lay.addWidget(g)

        g2 = QGroupBox("桌面巡邏夥伴管理")
        f2 = QVBoxLayout(g2)
        f2.setContentsMargins(16, 18, 16, 16)
        f2.setSpacing(12)

        self.lb_qcount = QLabel("在場角色: 0")
        f2.addWidget(self.lb_qcount)

        r = QHBoxLayout()
        b_ds_norm = QPushButton("召喚 DeepSeek Q版 (一般)")
        b_ds_norm.clicked.connect(lambda: self.app.add_q(kind="ds", dark=False))
        b_ds_dark = QPushButton("召喚 DeepSeek Q版 (黑化)")
        b_ds_dark.clicked.connect(lambda: self.app.add_q(kind="ds", dark=True))
        r.addWidget(b_ds_norm)
        r.addWidget(b_ds_dark)
        f2.addLayout(r)

        r2 = QHBoxLayout()
        b_custom = QPushButton("管理與匯入自訂 Q 版人物...")
        b_custom.clicked.connect(self._open_custom_q)
        b_clear = QPushButton("移除所有桌面 Q 版角色")
        b_clear.setObjectName("danger")
        b_clear.clicked.connect(self.app.remove_all_q)
        r2.addWidget(b_custom)
        r2.addWidget(b_clear)
        f2.addLayout(r2)

        r3 = QHBoxLayout()
        r3.addWidget(QLabel("Q版人物高度"))
        self.sl_qh = _slider(90, 320, 170, lambda v: self._do(self.app.set_q_height, v))
        self.lb_qh = QLabel("170 px")
        self.lb_qh.setFixedWidth(55)
        r3.addWidget(self.sl_qh, 1)
        r3.addWidget(self.lb_qh)
        f2.addLayout(r3)
        lay.addWidget(g2)

        lay.addStretch(1)
        return w

    def _open_custom_q(self):
        parent = self if self.isVisible() else None
        dlg = CustomQDialog(self.app, parent)
        dlg.exec()
        self.sync()

    # ------------------------------------------------------------- 4. 互動演示
    def _tab_demo(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)

        t_lbl = QLabel("互動與特效演示")
        t_lbl.setObjectName("PageTitle")
        d_lbl = QLabel("即時觸發扣費動畫、充值掉飯盆、物理碰撞與雷達吸附")
        d_lbl.setObjectName("PageDesc")
        lay.addWidget(t_lbl)
        lay.addWidget(d_lbl)

        g = QGroupBox("模擬扣費互動（動態飄字金額）")
        f = QVBoxLayout(g)
        f.setContentsMargins(16, 18, 16, 16)
        f.setSpacing(12)

        r_quick = QHBoxLayout()
        for n in (1, 5, 10, 30):
            b = QPushButton(f"-{n * 0.01:.2f}")
            b.clicked.connect(lambda _=False, v=n: self.app.ledger.sim_charge(v))
            r_quick.addWidget(b)
        f.addLayout(r_quick)

        r_custom = QHBoxLayout()
        self.sp_cents = QSpinBox()
        self.sp_cents.setRange(1, 40)
        self.sp_cents.setValue(3)
        self.sp_cents.setSuffix(" × 0.01")
        b_charge = QPushButton("執行自訂扣費")
        b_charge.clicked.connect(lambda: self.app.ledger.sim_charge(self.sp_cents.value()))
        r_custom.addWidget(self.sp_cents, 1)
        r_custom.addWidget(b_charge)
        f.addLayout(r_custom)
        lay.addWidget(g)

        g2 = QGroupBox("模擬充值餵食（物理重力碰撞飯盆）")
        f2 = QVBoxLayout(g2)
        f2.setContentsMargins(16, 18, 16, 16)
        f2.setSpacing(12)

        r_top = QHBoxLayout()
        self.sp_topup = QDoubleSpinBox()
        self.sp_topup.setRange(0.01, 9999)
        self.sp_topup.setValue(3.0)
        self.sp_topup.setPrefix("¥ ")
        b_drop = QPushButton("掉下一盆米飯")
        b_drop.setObjectName("primary")
        b_drop.clicked.connect(lambda: self.app.ledger.sim_topup(self.sp_topup.value()))
        r_top.addWidget(self.sp_topup, 1)
        r_top.addWidget(b_drop)
        f2.addLayout(r_top)
        f2.addWidget(_hint("飯盆掉落後具備重力、地面回彈與多盆互斥碰撞體積；拖曳到角色身上即可餵食；閒置 10 秒將被火控雷達鎖定自動吸入。"))
        lay.addWidget(g2)

        g3 = QGroupBox("道具與雷達控制")
        f3 = QVBoxLayout(g3)
        f3.setContentsMargins(16, 18, 16, 16)
        f3.setSpacing(12)

        b_radar = QPushButton("開啟火控雷達（提前顯示目標航向與距離名牌）")
        b_radar.clicked.connect(self.app.pet.props.lock_now)
        f3.addWidget(b_radar)

        b_clr_props = QPushButton("清除場上所有飯盆與鐵盆")
        b_clr_props.setObjectName("danger")
        b_clr_props.clicked.connect(lambda: self.app.pet.props.clear())
        f3.addWidget(b_clr_props)
        lay.addWidget(g3)

        lay.addStretch(1)
        return w

    # ------------------------------------------------------------- 5. 聲音設定
    def _tab_sound(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)

        t_lbl = QLabel("音效系統設定")
        t_lbl.setObjectName("PageTitle")
        d_lbl = QLabel("調整提示音量或透過音效庫更換個別音訊檔案")
        d_lbl.setObjectName("PageDesc")
        lay.addWidget(t_lbl)
        lay.addWidget(d_lbl)

        g = QGroupBox("聲音主要設定")
        f = QVBoxLayout(g)
        f.setContentsMargins(16, 18, 16, 16)
        f.setSpacing(12)

        self.cb_sound = QCheckBox("啟用音效反饋")
        self.cb_sound.toggled.connect(lambda v: self._do(self.app.set_sound, v))
        f.addWidget(self.cb_sound)

        r = QHBoxLayout()
        r.addWidget(QLabel("主音量"))
        self.sl_vol = _slider(0, 100, 80, lambda v: self._do(self.app.set_volume, v))
        self.lb_vol = QLabel("80 %")
        self.lb_vol.setFixedWidth(55)
        r.addWidget(self.sl_vol, 1)
        r.addWidget(self.lb_vol)
        f.addLayout(r)

        r_btn = QHBoxLayout()
        b_test = QPushButton("試聽扣費音效")
        b_test.clicked.connect(lambda: self.app.sounds.play("hit"))
        b_lib = QPushButton("開啟自訂音效庫（四個提示音獨立調音與更換）...")
        b_lib.clicked.connect(self._open_sound_lib)
        r_btn.addWidget(b_test)
        r_btn.addWidget(b_lib)
        f.addLayout(r_btn)
        lay.addWidget(g)

        lay.addStretch(1)
        return w

    def _open_sound_lib(self):
        parent = self if self.isVisible() else None
        dlg = SoundLibraryDialog(self.app, parent)
        dlg.exec()

    # ------------------------------------------------------------- 6. AI 對話與語音
    def _tab_ai_voice(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)

        t_lbl = QLabel("AI 對話與語音設定")
        t_lbl.setObjectName("PageTitle")
        d_lbl = QLabel("管理陪伴對話、語音辨識、Gemini Live 純語音與線上模型探索")
        d_lbl.setObjectName("PageDesc")
        lay.addWidget(t_lbl)
        lay.addWidget(d_lbl)

        # 1. AI 對話與設定檔
        g_core = QGroupBox("AI 核心與設定檔")
        f_core = QVBoxLayout(g_core)
        f_core.setContentsMargins(16, 18, 16, 16)
        f_core.setSpacing(12)

        self.cb_ai_chat = QCheckBox("啟用桌面 AI 陪伴對話視窗功能")
        self.cb_ai_chat.toggled.connect(lambda v: self._do(lambda x: self.cfg.set("ai_chat_enabled", x, save=True), v))
        f_core.addWidget(self.cb_ai_chat)

        r_prof = QHBoxLayout()
        r_prof.addWidget(QLabel("目前使用設定檔:"))
        self.cmb_active_profile = QComboBox()
        self.cmb_active_profile.currentIndexChanged.connect(self._on_active_profile_changed)
        r_prof.addWidget(self.cmb_active_profile, 1)
        f_core.addLayout(r_prof)

        r_btns = QHBoxLayout()
        b_prof = QPushButton("開啟 API 設定檔管理...")
        b_prof.clicked.connect(self._open_api_profile_dialog)
        b_mem = QPushButton("角色記憶管理...")
        b_mem.clicked.connect(self._open_memory_dialog)
        b_open_chat = QPushButton("開啟 AI 對話視窗")
        b_open_chat.setObjectName("primary")
        b_open_chat.clicked.connect(lambda: self.app.open_chat_dialog())
        r_btns.addWidget(b_prof)
        r_btns.addWidget(b_mem)
        r_btns.addWidget(b_open_chat)
        f_core.addLayout(r_btns)
        lay.addWidget(g_core)

        # 2. 語音辨識與朗讀
        g_voice = QGroupBox("語音輸入與文字朗讀 (STT / TTS)")
        f_voice = QVBoxLayout(g_voice)
        f_voice.setContentsMargins(16, 18, 16, 16)
        f_voice.setSpacing(12)

        r_stt = QHBoxLayout()
        r_stt.addWidget(QLabel("語音輸入模式 (STT):"))
        self.cmb_stt_mode = QComboBox()
        self.cmb_stt_mode.addItems(["traditional (本機 Vosk 語音)", "ai (雲端 Whisper 語音)"])
        self.cmb_stt_mode.currentIndexChanged.connect(
            lambda i: self._do(lambda _: self.cfg.set("voice_input_mode", "traditional" if i == 0 else "ai", save=True), None)
        )
        r_stt.addWidget(self.cmb_stt_mode, 1)
        f_voice.addLayout(r_stt)

        r_tts = QHBoxLayout()
        r_tts.addWidget(QLabel("文字朗讀模式 (TTS):"))
        self.cmb_tts_mode = QComboBox()
        self.cmb_tts_mode.addItems(["off (關閉朗讀)", "traditional (本機 pyttsx3)", "ai (雲端 TTS)"])
        self.cmb_tts_mode.currentIndexChanged.connect(
            lambda i: self._do(lambda _: self.cfg.set("tts_mode", ["off", "traditional", "ai"][i], save=True), None)
        )
        r_tts.addWidget(self.cmb_tts_mode, 1)
        f_voice.addLayout(r_tts)

        b_adv_voice = QPushButton("開啟進階語音模型與音色微調...")
        b_adv_voice.clicked.connect(self._open_voice_settings)
        f_voice.addWidget(b_adv_voice)
        lay.addWidget(g_voice)

        # 3. Gemini Live 設定
        g_live = QGroupBox("Gemini Live 純語音模式")
        f_live = QVBoxLayout(g_live)
        f_live.setContentsMargins(16, 18, 16, 16)
        f_live.setSpacing(12)

        r_live_m = QHBoxLayout()
        r_live_m.addWidget(QLabel("Gemini Live 模型:"))
        self.ed_live_model = QLineEdit()
        self.ed_live_model.setPlaceholderText("gemini-flash-latest")
        r_live_m.addWidget(self.ed_live_model, 1)
        f_live.addLayout(r_live_m)

        r_live_v = QHBoxLayout()
        r_live_v.addWidget(QLabel("Gemini Live 聲音:"))
        self.cmb_live_voice = QComboBox()
        self.cmb_live_voice.setEditable(True)
        self.cmb_live_voice.addItems(["Kore", "Puck", "Charon", "Fenrir", "Aoede"])
        r_live_v.addWidget(self.cmb_live_voice, 1)
        f_live.addLayout(r_live_v)

        r_live_act = QHBoxLayout()
        b_save_live = QPushButton("儲存 Gemini Live 設定")
        b_save_live.setObjectName("primary")
        b_save_live.clicked.connect(self._save_live_settings)
        b_start_live = QPushButton("立即啟動 Gemini Live")
        b_start_live.clicked.connect(lambda: self.app.open_gemini_live())
        r_live_act.addWidget(b_save_live)
        r_live_act.addWidget(b_start_live)
        f_live.addLayout(r_live_act)
        lay.addWidget(g_live)

        # 4. 線上模型探索
        g_disc = QGroupBox("線上模型清單探索 (Remote Model Discovery)")
        f_disc = QVBoxLayout(g_disc)
        f_disc.setContentsMargins(16, 18, 16, 16)
        f_disc.setSpacing(12)

        f_disc.addWidget(_hint("向廠商 API 端點發送探測請求，即時取得該帳號所有可用的遠端模型清單，支援一鍵套用。"))

        r_disc_top = QHBoxLayout()
        r_disc_top.addWidget(QLabel("廠商:"))
        self.cmb_disc_prov = QComboBox()
        self.cmb_disc_prov.addItems(PROVIDERS)
        self.cmb_disc_prov.currentIndexChanged.connect(self._on_disc_prov_changed)
        r_disc_top.addWidget(self.cmb_disc_prov, 1)

        r_disc_top.addWidget(QLabel("Key:"))
        self.ed_disc_key = QLineEdit()
        self.ed_disc_key.setEchoMode(QLineEdit.Password)
        self.ed_disc_key.setPlaceholderText("請輸入 API Key")
        r_disc_top.addWidget(self.ed_disc_key, 2)
        f_disc.addLayout(r_disc_top)

        r_disc_ep = QHBoxLayout()
        r_disc_ep.addWidget(QLabel("端點:"))
        self.ed_disc_endpoint = QLineEdit()
        self.ed_disc_endpoint.setPlaceholderText("預設端點（可留空使用官方標準路徑）")
        r_disc_ep.addWidget(self.ed_disc_endpoint, 1)
        self.btn_disc = QPushButton("獲取線上模型列表")
        self.btn_disc.setObjectName("primary")
        self.btn_disc.clicked.connect(self._discover_models)
        r_disc_ep.addWidget(self.btn_disc)
        f_disc.addLayout(r_disc_ep)

        self.lb_disc_status = QLabel("請選擇廠商並輸入 API Key 後點擊獲取。")
        self.lb_disc_status.setStyleSheet("color: #64748b; font-size: 12px;")
        self.lb_disc_status.setWordWrap(True)
        f_disc.addWidget(self.lb_disc_status)

        r_disc_res = QHBoxLayout()
        r_disc_res.addWidget(QLabel("遠端模型清單:"))
        self.cmb_disc_models = QComboBox()
        self.cmb_disc_models.addItem("（尚未獲取清單）", "")
        r_disc_res.addWidget(self.cmb_disc_models, 1)
        f_disc.addLayout(r_disc_res)

        r_disc_apply = QHBoxLayout()
        b_apply_live = QPushButton("套用為 Gemini Live 模型")
        b_apply_live.clicked.connect(self._apply_disc_to_live)
        b_apply_chat = QPushButton("套用至目前對話模型")
        b_apply_chat.clicked.connect(self._apply_disc_to_active_profile)
        r_disc_apply.addWidget(b_apply_live)
        r_disc_apply.addWidget(b_apply_chat)
        f_disc.addLayout(r_disc_apply)
        lay.addWidget(g_disc)

        lay.addStretch(1)
        return w

    def _on_disc_prov_changed(self, idx: int):
        prov = self.cmb_disc_prov.currentText()
        keys = self.cfg.get("api_keys", {})
        prov_map = {
            "DeepSeek": "deepseek",
            "OpenAI": "openai",
            "Google Gemini": "gemini",
            "Anthropic": "anthropic",
        }
        k = keys.get(prov_map.get(prov, ""), "")
        if k:
            self.ed_disc_key.setText(k)
        endpoints = {
            "Ollama": "http://localhost:11434",
            "Cloudflare AI": "https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run",
        }
        self.ed_disc_endpoint.setText(endpoints.get(prov, ""))

    def _discover_models(self):
        prov = self.cmb_disc_prov.currentText()
        key = self.ed_disc_key.text().strip()
        ep = self.ed_disc_endpoint.text().strip()

        if not key and prov not in ("Ollama",):
            self.lb_disc_status.setText(f"錯誤：{prov} 需要 API Key 才能查詢。")
            return

        profile = {"provider": prov, "key": key, "endpoint": ep}
        self.lb_disc_status.setText(f"正在查詢 {prov} 的遠端模型清單...")
        self.btn_disc.setEnabled(False)

        self._disc_worker = ModelListWorker(profile, self)
        self._disc_worker.models_ready.connect(self._on_models_discovered)
        self._disc_worker.start()

    def _on_models_discovered(self, ok: bool, models: list, note: str):
        self.btn_disc.setEnabled(True)
        if ok and models:
            self.cmb_disc_models.clear()
            for m in models:
                self.cmb_disc_models.addItem(f"{m.get('label', m.get('id'))} ({m.get('id')})", m.get("id"))
            self.lb_disc_status.setText(f"查詢成功：共找到 {len(models)} 個模型 ({note})")
        else:
            self.lb_disc_status.setText(f"查詢失敗：{note}")

    def _apply_disc_to_live(self):
        mid = self.cmb_disc_models.currentData() or self.cmb_disc_models.currentText()
        if not mid or mid.startswith("（"):
            QMessageBox.warning(self, "提示", "尚未選擇有效的模型 ID。")
            return
        self.ed_live_model.setText(mid)
        self.cfg.set("gemini_live_model", mid, save=True)
        QMessageBox.information(self, "已套用", f"已將 Gemini Live 模型設定為: {mid}")

    def _apply_disc_to_active_profile(self):
        mid = self.cmb_disc_models.currentData() or self.cmb_disc_models.currentText()
        if not mid or mid.startswith("（"):
            QMessageBox.warning(self, "提示", "尚未選擇有效的模型 ID。")
            return
        profiles = [dict(x) for x in self.cfg.get("api_profiles", [])]
        act_idx = max(0, min(self.cmb_active_profile.currentIndex(), len(profiles) - 1))
        if profiles:
            profiles[act_idx]["model"] = mid
            self.cfg.set("api_profiles", profiles, save=True)
            QMessageBox.information(self, "已套用", f"已更新目前設定檔的模型 ID 為: {mid}")

    def _save_live_settings(self):
        self.cfg.set("gemini_live_model", self.ed_live_model.text().strip(), save=False)
        self.cfg.set("gemini_live_voice", self.cmb_live_voice.currentText().strip(), save=True)
        QMessageBox.information(self, "儲存成功", "Gemini Live 設定已更新。")

    def _on_active_profile_changed(self, idx: int):
        if idx >= 0:
            self.cfg.set("active_profile", idx, save=True)

    def _open_api_profile_dialog(self):
        dlg = ApiProfileDialog(self.cfg, self)
        dlg.exec()
        self.sync()

    def _open_memory_dialog(self):
        dlg = MemoryDialog(self.cfg, self)
        dlg.exec()

    def _open_voice_settings(self):
        dlg = VoiceSettingsDialog(self.cfg, self)
        dlg.exec()
        self.sync()

    # ------------------------------------------------------------- 7. API 與餘額
    def _tab_balance(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)

        t_lbl = QLabel("API 廠商與餘額監控")
        t_lbl.setObjectName("PageTitle")
        d_lbl = QLabel("連接官方 API 即時監控模型額度，或啟用模擬模式進行測試")
        d_lbl.setObjectName("PageDesc")
        lay.addWidget(t_lbl)
        lay.addWidget(d_lbl)

        g = QGroupBox("運作模式選擇")
        f = QVBoxLayout(g)
        f.setContentsMargins(16, 18, 16, 16)
        f.setSpacing(12)

        self.rb_sim = QRadioButton("模擬模式（使用本機虛擬餘額，可自訂初始額度）")
        self.rb_api = QRadioButton("API 模式（連接官方 API 即時更新）")
        self.rb_sim.toggled.connect(lambda v: v and self._do(self.app.set_mode, "sim"))
        self.rb_api.toggled.connect(lambda v: v and self._do(self.app.set_mode, "api"))
        f.addWidget(self.rb_sim)
        f.addWidget(self.rb_api)

        r_sim = QHBoxLayout()
        r_sim.addWidget(QLabel("模擬模式帳面餘額:"))
        self.sp_simbal = QDoubleSpinBox()
        self.sp_simbal.setRange(0.0, 999999.0)
        self.sp_simbal.setValue(float(self.cfg.get("sim_balance", 50.0)))
        b_setbal = QPushButton("設定餘額")
        b_setbal.clicked.connect(self._set_sim_bal)
        r_sim.addWidget(self.sp_simbal, 1)
        r_sim.addWidget(b_setbal)
        f.addLayout(r_sim)

        self.cb_simauto = QCheckBox("模擬模式自動隨機發生扣費與充值")
        self.cb_simauto.toggled.connect(lambda v: self._do(self.app.set_sim_auto, v))
        f.addWidget(self.cb_simauto)
        lay.addWidget(g)

        g_prov = QGroupBox("API 廠商與金鑰設定")
        f_prov = QFormLayout(g_prov)
        f_prov.setContentsMargins(16, 18, 16, 16)
        f_prov.setSpacing(12)

        self.cmb_prov = QComboBox()
        self.cmb_prov.addItems(PROV_NAMES)
        self.cmb_prov.currentIndexChanged.connect(self._on_provider_changed)
        f_prov.addRow("選擇廠商", self.cmb_prov)

        self.ed_key = QLineEdit()
        self.ed_key.setEchoMode(QLineEdit.Password)
        self.ed_key.setPlaceholderText("請輸入 API 金鑰 (API Key)")
        f_prov.addRow("API Key", self.ed_key)

        self.sp_budget = QDoubleSpinBox()
        self.sp_budget.setRange(0, 999999)
        self.sp_budget.setValue(100.0)
        self.sp_budget.setPrefix("$ ")
        f_prov.addRow("起始額度 (Budget)", self.sp_budget)

        self.ed_since = QLineEdit()
        self.ed_since.setPlaceholderText("YYYY-MM-01")
        f_prov.addRow("起算日 (Since)", self.ed_since)

        r_act = QHBoxLayout()
        b_save_prov = QPushButton("儲存設定")
        b_save_prov.setObjectName("primary")
        b_save_prov.clicked.connect(self._save_provider_settings)
        b_refresh = QPushButton("立即刷新餘額")
        b_refresh.clicked.connect(self.app.ledger.refresh)
        r_act.addWidget(b_save_prov)
        r_act.addWidget(b_refresh)
        f_prov.addRow(r_act)

        self.lb_prov_status = QLabel()
        self.lb_prov_status.setStyleSheet("font-weight: bold; color: #2563eb;")
        self.lb_prov_status.setWordWrap(True)
        f_prov.addRow("目前連線狀態", self.lb_prov_status)
        lay.addWidget(g_prov)

        lay.addStretch(1)
        return w

    def _set_sim_bal(self):
        val = round(self.sp_simbal.value(), 2)
        self.cfg.set("sim_balance", val)
        if self.cfg.get("mode") == "sim":
            self.app.ledger.set_sim_balance(val)

    def _on_provider_changed(self, idx: int):
        if idx < 0 or idx >= len(PROV_IDS):
            return
        pid = PROV_IDS[idx]
        keys = self.cfg.get("api_keys", {})
        self.ed_key.setText(keys.get(pid, ""))
        budgets = self.cfg.get("budgets", {})
        self.sp_budget.setValue(float(budgets.get(pid, 100.0)))
        sinces = self.cfg.get("sinces", {})
        self.ed_since.setText(sinces.get(pid, ""))

    def _save_provider_settings(self):
        idx = self.cmb_prov.currentIndex()
        if idx < 0 or idx >= len(PROV_IDS):
            return
        pid = PROV_IDS[idx]
        keys = dict(self.cfg.get("api_keys", {}))
        keys[pid] = self.ed_key.text().strip()
        self.cfg.set("api_keys", keys, save=False)

        budgets = dict(self.cfg.get("budgets", {}))
        budgets[pid] = self.sp_budget.value()
        self.cfg.set("budgets", budgets, save=False)

        sinces = dict(self.cfg.get("sinces", {}))
        sinces[pid] = self.ed_since.text().strip()
        self.cfg.set("sinces", sinces, save=False)

        self.cfg.set("provider", pid, save=True)
        self.app.ledger.set_provider(pid)
        QMessageBox.information(self, "已儲存", f"{PROV_NAMES[idx]} 設定已儲存並套用。")

    # ------------------------------------------------------------- 8. 網頁儀表板
    def _tab_web(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)

        t_lbl = QLabel("本機網頁面板 (Web Dashboard)")
        t_lbl.setObjectName("PageTitle")
        d_lbl = QLabel("在網頁瀏覽器中即時檢視圖表趨勢、消費紀錄與匯出 CSV")
        d_lbl.setObjectName("PageDesc")
        lay.addWidget(t_lbl)
        lay.addWidget(d_lbl)

        g = QGroupBox("伺服器狀態與連線")
        f = QVBoxLayout(g)
        f.setContentsMargins(16, 18, 16, 16)
        f.setSpacing(12)

        self.lb_web_status = QLabel()
        self.lb_web_status.setWordWrap(True)
        f.addWidget(self.lb_web_status)

        b_open_web = QPushButton("在瀏覽器中開啟網頁面板")
        b_open_web.setObjectName("primary")
        b_open_web.setIcon(get_icon("open_in_new", "#ffffff", 16))
        b_open_web.clicked.connect(self._open_web_browser)
        f.addWidget(b_open_web)

        f.addWidget(
            _hint(
                "網頁伺服器僅綁定本機 127.0.0.1 迴圈地址，唯讀安全。支援在同一介面檢視多模型即時餘額、今日花費/充值統計、即時趨勢圖表，並支援一鍵匯出 CSV 報表。"
            )
        )
        lay.addWidget(g)

        lay.addStretch(1)
        return w

    def _open_web_browser(self):
        port = self.app.web.port if self.app.web else 8765
        webbrowser.open(f"http://127.0.0.1:{port}/")

    # ------------------------------------------------------------- 9. 全域日誌
    def _tab_logs(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)

        t_lbl = QLabel("全域日誌流 (Global Logs)")
        t_lbl.setObjectName("PageTitle")
        d_lbl = QLabel("整合 logger.py 核心，支援等級過濾、即時搜尋與記憶體日誌串流")
        d_lbl.setObjectName("PageDesc")
        lay.addWidget(t_lbl)
        lay.addWidget(d_lbl)

        g_ctrl = QGroupBox("日誌過濾與搜尋")
        f_ctrl = QVBoxLayout(g_ctrl)
        f_ctrl.setContentsMargins(16, 18, 16, 16)
        f_ctrl.setSpacing(10)

        r_bar = QHBoxLayout()
        r_bar.addWidget(QLabel("等級過濾:"))
        self.log_level_cmb = QComboBox()
        self.log_level_cmb.addItems(["全部 (ALL)", "DEBUG", "INFO", "WARNING", "ERROR"])
        self.log_level_cmb.currentIndexChanged.connect(lambda _: self._refresh_logs())
        r_bar.addWidget(self.log_level_cmb)

        r_bar.addWidget(QLabel("搜尋:"))
        self.log_search_ed = QLineEdit()
        self.log_search_ed.setPlaceholderText("輸入關鍵字進行過濾...")
        self.log_search_ed.textChanged.connect(lambda _: self._refresh_logs())
        r_bar.addWidget(self.log_search_ed, 1)
        f_ctrl.addLayout(r_bar)

        r_act = QHBoxLayout()
        self.log_autoscroll_cb = QCheckBox("自動滾動至最新")
        self.log_autoscroll_cb.setChecked(True)
        r_act.addWidget(self.log_autoscroll_cb)
        r_act.addStretch(1)

        b_clear = QPushButton("清空日誌緩衝")
        b_clear.clicked.connect(self._clear_logs)
        r_act.addWidget(b_clear)

        b_open_folder = QPushButton("開啟日誌目錄")
        b_open_folder.setIcon(get_icon("folder", "#334155", 16))
        b_open_folder.clicked.connect(self._open_logs_dir)
        r_act.addWidget(b_open_folder)

        f_ctrl.addLayout(r_act)
        lay.addWidget(g_ctrl)

        self.log_text_edit = QTextEdit()
        self.log_text_edit.setObjectName("LogViewer")
        self.log_text_edit.setReadOnly(True)
        self.log_text_edit.setMinimumHeight(280)
        lay.addWidget(self.log_text_edit, 1)

        lay.addStretch(1)
        return w

    def _refresh_logs(self):
        if not hasattr(self, "log_text_edit"):
            return
        level = self.log_level_cmb.currentText()
        if "ALL" in level or "全部" in level:
            level_filter = None
        else:
            level_filter = level

        query = self.log_search_ed.text().strip() or None
        entries = get_recent_logs(count=300, level=level_filter, search=query)

        is_dark = (self.cfg.get("theme", "light") == "dark")
        html_lines = []
        for item in entries:
            line = item if isinstance(item, str) else (item.get("formatted") or item.get("message", ""))
            col = "#94a3b8" if is_dark else "#475569"
            if "[ERROR ]" in line or "[CRITICAL]" in line:
                col = "#f87171" if is_dark else "#dc2626"
            elif "[WARN  ]" in line:
                col = "#fbbf24" if is_dark else "#d97706"
            elif "[INFO  ]" in line:
                col = "#e2e8f0" if is_dark else "#1e293b"
            elif "[DEBUG ]" in line:
                col = "#60a5fa" if is_dark else "#2563eb"

            escaped = (
                line.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
            )
            html_lines.append(f"<span style='color:{col}; white-space:pre-wrap;'>{escaped}</span>")

        self.log_text_edit.setHtml("<br>".join(html_lines))
        if self.log_autoscroll_cb.isChecked():
            sb = self.log_text_edit.verticalScrollBar()
            if sb:
                sb.setValue(sb.maximum())

    def _clear_logs(self):
        clear_memory_buffer()
        self._refresh_logs()

    def _open_logs_dir(self):
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(str(LOGS_DIR))
        else:
            webbrowser.open(LOGS_DIR.as_uri())

    # ------------------------------------------------------------- 10. 關於本軟體 (UPGRADED)
    def _tab_about(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)

        t_lbl = QLabel("關於 Desktop Pet 桌面寵物")
        t_lbl.setObjectName("PageTitle")
        d_lbl = QLabel("專案版本、官方開源倉庫、版本更新檢查與社群美術資源徵求")
        d_lbl.setObjectName("PageDesc")
        lay.addWidget(t_lbl)
        lay.addWidget(d_lbl)

        # Card 1: 專案資訊與官方倉庫
        card1 = QFrame()
        card1.setObjectName("AboutCard")
        c1_lay = QVBoxLayout(card1)
        c1_lay.setContentsMargins(18, 16, 18, 16)
        c1_lay.setSpacing(10)

        h1 = QLabel(f"Desktop Pet 桌面寵物 {APP_VERSION}")
        h1.setStyleSheet("font-size: 16px; font-weight: bold; color: #3b82f6;")
        c1_lay.addWidget(h1)

        intro = QLabel(
            "專為 Windows 桌面環境打造的高性能互動掛件與多模型 API 餘額即時監控助手。\n"
            "具備極簡深灰高質感膠囊對話視窗、自訂字體系統、動態頭頂氣泡、原生音訊引擎與本機安全儀表板。"
        )
        intro.setWordWrap(True)
        c1_lay.addWidget(intro)

        repo_info = QLabel(f"官方開源倉庫網址：{GITHUB_REPO_URL}")
        repo_info.setStyleSheet("color: #64748b; font-size: 12px;")
        repo_info.setWordWrap(True)
        c1_lay.addWidget(repo_info)

        r_repo_btns = QHBoxLayout()
        b_repo = QPushButton("開啟 GitHub 專案倉庫")
        b_repo.setObjectName("primary")
        b_repo.setIcon(get_icon("open_in_new", "#ffffff", 16))
        b_repo.clicked.connect(lambda: webbrowser.open(GITHUB_REPO_URL))
        r_repo_btns.addWidget(b_repo)

        b_check_update = QPushButton("檢查最新版本 (Check for Updates)")
        b_check_update.setIcon(get_icon("refresh", "#334155", 16))
        b_check_update.clicked.connect(self._check_for_updates)
        r_repo_btns.addWidget(b_check_update)

        r_repo_btns.addStretch(1)
        c1_lay.addLayout(r_repo_btns)

        self.lb_update_status = QLabel("點擊按鈕檢查是否有新版本發布")
        self.lb_update_status.setStyleSheet("color: #64748b; font-size: 12px;")
        self.lb_update_status.setWordWrap(True)
        c1_lay.addWidget(self.lb_update_status)

        lay.addWidget(card1)

        # Card 2: 徵求圖片與美術資源 (Community Art & Assets)
        card_art = QFrame()
        card_art.setObjectName("AboutCard")
        c_art_lay = QVBoxLayout(card_art)
        c_art_lay.setContentsMargins(18, 16, 18, 16)
        c_art_lay.setSpacing(10)

        h_art = QLabel("徵求圖片與美術資源 (Community Art & Asset Invitation)")
        h_art.setStyleSheet("font-size: 15px; font-weight: bold; color: #10b981;")
        c_art_lay.addWidget(h_art)

        art_desc = QLabel(
            "熱情邀請廣大社群創作者、插畫師與玩家共同參與桌面寵物的豐富生態！\n"
            "我們熱切徵求各類原創與衍生美術資源：\n"
            "· 角色全身原畫立繪（支援 1:1 標準正方形與 1.5:1 寬屏帶尾巴立繪）\n"
            "· 表情差分素材包（開心、警戒、傲嬌、冰冷、受傷等生動表情）\n"
            "· 摸頭互動回饋動畫與特殊動作幀\n"
            "· 特色桌寵道具（米飯盆、頭頂鐵盆、專屬配件與場景裝飾）\n"
            "歡迎透過 GitHub 提交 Pull Request 或 Issue 分享您的作品，作品將署名列入感謝清單！"
        )
        art_desc.setWordWrap(True)
        c_art_lay.addWidget(art_desc)

        r_art_btns = QHBoxLayout()
        b_art_repo = QPushButton("前往 GitHub 提交美術資源")
        b_art_repo.setObjectName("primary")
        b_art_repo.setIcon(get_icon("code", "#ffffff", 16))
        b_art_repo.clicked.connect(lambda: webbrowser.open(f"{GITHUB_REPO_URL}/issues"))
        r_art_btns.addWidget(b_art_repo)

        b_art_dir = QPushButton("開啟本機自訂立繪目錄")
        b_art_dir.setIcon(get_icon("folder", "#334155", 16))
        b_art_dir.clicked.connect(self._open_custom_chars_dir)
        r_art_btns.addWidget(b_art_dir)

        b_sound_dir = QPushButton("開啟本機自訂音效目錄")
        b_sound_dir.setIcon(get_icon("folder", "#334155", 16))
        b_sound_dir.clicked.connect(self._open_custom_sounds_dir)
        r_art_btns.addWidget(b_sound_dir)

        r_art_btns.addStretch(1)
        c_art_lay.addLayout(r_art_btns)
        lay.addWidget(card_art)

        # Card 3: 開源協議與快捷診斷
        card3 = QFrame()
        card3.setObjectName("AboutCard")
        c3_lay = QVBoxLayout(card3)
        c3_lay.setContentsMargins(18, 16, 18, 16)
        c3_lay.setSpacing(10)

        h3 = QLabel("開源許可協議與系統健康診斷")
        h3.setStyleSheet("font-size: 14px; font-weight: bold;")
        c3_lay.addWidget(h3)

        lic_lbl = QLabel(
            "本專案程式碼採用 MIT License 開源許可協議發布。\n"
            "按鈕圖示整合 Google Material Symbols，遵循 Apache License 2.0 協議。\n"
            "所有原創角色立繪、插畫與音訊素材著作權歸原創作者所有。"
        )
        lic_lbl.setWordWrap(True)
        c3_lay.addWidget(lic_lbl)

        crash_info = check_crash()
        if crash_info.get("crashed"):
            status_text = f"前次執行狀態: 異常終止 (工作階段: {crash_info.get('last_session', '未知')})"
            diag_color = "#ef4444"
        else:
            status_text = "前次執行狀態: 正常關閉"
            diag_color = "#10b981"

        self.diag_lbl = QLabel(status_text)
        self.diag_lbl.setStyleSheet(f"font-weight: bold; color: {diag_color};")
        c3_lay.addWidget(self.diag_lbl)

        r_btns = QHBoxLayout()
        b_tut = QPushButton("開啟新手教學指引")
        b_tut.clicked.connect(self.app.open_tutorial)
        r_btns.addWidget(b_tut)

        b_web = QPushButton("開啟 Web 儀表板")
        b_web.clicked.connect(self.app.open_web_ui)
        r_btns.addWidget(b_web)

        b_dir_logs = QPushButton("開啟日誌目錄")
        b_dir_logs.clicked.connect(self._open_logs_dir)
        r_btns.addWidget(b_dir_logs)

        b_dir_app = QPushButton("開啟專案安裝目錄")
        b_dir_app.clicked.connect(self._open_app_dir)
        r_btns.addWidget(b_dir_app)

        r_btns.addStretch(1)
        c3_lay.addLayout(r_btns)
        lay.addWidget(card3)

        lay.addStretch(1)
        return w

    def _check_for_updates(self):
        self.lb_update_status.setText("正在連線至 GitHub 檢查最新版本...")
        if self._update_worker and self._update_worker.isRunning():
            return
        self._update_worker = UpdateCheckWorker(self)
        self._update_worker.finished.connect(self._on_update_check_done)
        self._update_worker.start()

    def _on_update_check_done(self, ok: bool, tag: str, url: str, msg: str):
        self._update_worker = None
        if not ok:
            self.lb_update_status.setText(f"檢查更新失敗：{msg}")
            return

        if not tag:
            self.lb_update_status.setText(f"{msg}")
            return

        clean_tag = tag.strip().lstrip("v")
        clean_cur = APP_VERSION.strip().lstrip("v")
        if clean_tag > clean_cur:
            self.lb_update_status.setText(f"發現新版本發布：{tag}！（目前版本：{APP_VERSION}）請造訪 GitHub 進行下載。")
        else:
            self.lb_update_status.setText(f"目前已是最新版本 ({APP_VERSION})，無須更新。")

    def _open_custom_chars_dir(self):
        CUSTOM_CHARS_DIR.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(str(CUSTOM_CHARS_DIR))
        else:
            webbrowser.open(CUSTOM_CHARS_DIR.as_uri())

    def _open_custom_sounds_dir(self):
        SOUND_LIB_DIR.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(str(SOUND_LIB_DIR))
        else:
            webbrowser.open(SOUND_LIB_DIR.as_uri())

    def _open_app_dir(self):
        if sys.platform == "win32":
            os.startfile(str(APP_DIR))
        else:
            webbrowser.open(APP_DIR.as_uri())

    # ------------------------------------------------------------- Plumbing & Sync
    def _do(self, fn, v):
        if not self._lock:
            fn(v)

    def apply_theme(self):
        theme = self.cfg.get("theme", "light")
        self.setStyleSheet(DARK_MD3_QSS if theme == "dark" else LIGHT_MD3_QSS)
        if hasattr(self, "title_bar"):
            self.title_bar.apply_theme(theme)
        self._refresh_logs()

    def _status(self):
        led = self.app.ledger
        cid = self.app.pet.character
        cname = cid
        for k, v in [
            ("deepseek", "藍色大肥魚 (DeepSeek)"),
            ("claude", "大小姐 Claude"),
            ("gemini", "祈願神龍 Gemini"),
            ("gpt", "GPT 龍娘"),
        ]:
            if k == cid:
                cname = v
                break
        self.lb_cur_char.setText(
            f"目前角色: {cname} [{ '完整立繪形態 (1536×1024)' if self.app.pet.is_tail else '標準正方形形態 (1024×1024)' }]"
        )

        if self.cfg.get("mode") == "sim":
            self.lb_prov_status.setText(
                f"模擬模式：帳面餘額 {led.text} (今日已用 {self.cfg.get('today_used', 0.0):.2f})"
            )
        elif led.online:
            self.lb_prov_status.setText(f"已連線：{self.cfg.get('provider')} 餘額 {led.text}")
        else:
            self.lb_prov_status.setText(f"離線：{led.error or '未連線'}")

        self.lb_qcount.setText(f"目前在場 Q 版角色：{len(self.app.qchars.chars)} / 8")

        port = self.app.web.port if self.app.web else 0
        if port:
            self.lb_web_status.setText(
                f"網頁伺服器運作中: <a href='http://127.0.0.1:{port}/' style='color:#3b82f6;'>http://127.0.0.1:{port}/</a>"
            )
        else:
            self.lb_web_status.setText("網頁伺服器未啟動")

    def sync(self):
        c = self.cfg
        self._lock = True
        try:
            self.cb_through.setChecked(bool(c.get("click_through", False)))
            self.cb_snap.setChecked(bool(c.get("auto_snap", True)))
            self.sl_snap.setValue(int(c.get("snap_distance", 120)))
            self.lb_snap.setText(f"{int(c.get('snap_distance', 120))} px")
            self.cb_top.setChecked(bool(c.get("always_on_top", True)))
            self.cb_pat.setChecked(bool(c.get("pat", True)))
            self.sl_op.setValue(int(c.get("opacity", 100)))
            self.lb_op.setText(f"{int(c.get('opacity', 100))} %")
            self.sp_size.setValue(int(c.get("size", 454)))
            self.cmb_theme.setCurrentIndex(1 if c.get("theme") == "dark" else 0)

            # Character variant
            self.rb_var_square.setChecked(c.get("variant", "square") == "square")
            self.rb_var_tail.setChecked(c.get("variant", "square") == "tail")

            # Q dark
            self.cb_dark.setChecked(bool(c.get("q_dark", False)))
            self.sl_qh.setValue(int(c.get("q_height", 170)))
            self.lb_qh.setText(f"{int(c.get('q_height', 170))} px")

            # Sound
            self.cb_sound.setChecked(bool(c.get("sound", True)))
            self.sl_vol.setValue(int(c.get("volume", 80)))
            self.lb_vol.setText(f"{int(c.get('volume', 80))} %")

            # Font sync
            f_mode = self.cfg.get("font_mode", "default")
            f_fam = self.cfg.get("font_family", "")
            f_path = self.cfg.get("custom_font_path", "")
            if f_mode == "custom_file" and f_path:
                self.rb_font_file.setChecked(True)
                self.ed_font_path.setText(f_path)
                self.lb_font_status.setText(f"目前狀態：已套用自訂字體 [{f_fam or Path(f_path).name}]")
            elif f_mode == "system" and f_fam:
                self.rb_font_sys.setChecked(True)
                idx = self.cmb_sys_fonts.findText(f_fam)
                if idx >= 0:
                    self.cmb_sys_fonts.setCurrentIndex(idx)
                self.lb_font_status.setText(f"目前狀態：已套用系統字體 [{f_fam}]")
            else:
                self.rb_font_sys.setChecked(True)
                best = resolve_best_default_font()
                idx = self.cmb_sys_fonts.findText(best)
                if idx >= 0:
                    self.cmb_sys_fonts.setCurrentIndex(idx)
                self.lb_font_status.setText(f"目前狀態：使用現代預設字體 [{best}]")
            self._update_font_preview()

            # AI & Voice
            self.cb_ai_chat.setChecked(bool(c.get("ai_chat_enabled", True)))
            self.ed_live_model.setText(str(c.get("gemini_live_model", "gemini-flash-latest")))
            self.cmb_live_voice.setCurrentText(str(c.get("gemini_live_voice", "Kore")))

            stt_mode = c.get("voice_input_mode", "traditional")
            self.cmb_stt_mode.setCurrentIndex(1 if stt_mode == "ai" else 0)
            tts_mode = c.get("tts_mode", "off")
            tts_idx = 0
            if tts_mode == "traditional":
                tts_idx = 1
            elif tts_mode == "ai":
                tts_idx = 2
            self.cmb_tts_mode.setCurrentIndex(tts_idx)

            profiles = c.get("api_profiles", [])
            self.cmb_active_profile.blockSignals(True)
            self.cmb_active_profile.clear()
            for p in profiles:
                self.cmb_active_profile.addItem(f"{p.get('name', '未命名')} ({p.get('provider', '')})")
            act_idx = max(0, min(int(c.get("active_profile", 0)), max(0, len(profiles) - 1)))
            if profiles:
                self.cmb_active_profile.setCurrentIndex(act_idx)
            self.cmb_active_profile.blockSignals(False)

            # Balance
            self.rb_sim.setChecked(c.get("mode", "sim") == "sim")
            self.rb_api.setChecked(c.get("mode", "sim") == "api")
            self.cb_simauto.setChecked(bool(c.get("sim_auto", True)))
            self.sp_simbal.setValue(float(c.get("sim_balance", 50.0)))

            prov_id = c.get("provider", "deepseek")
            if prov_id in PROV_IDS:
                self.cmb_prov.setCurrentIndex(PROV_IDS.index(prov_id))
            self._on_provider_changed(self.cmb_prov.currentIndex())
        finally:
            self._lock = False
        self._status()

    def showEvent(self, e):
        super().showEvent(e)
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            x = geo.x() + max(0, (geo.width() - self.width()) // 2)
            y = geo.y() + max(0, (geo.height() - self.height()) // 2)
            self.move(x, y)
        self.raise_()
        self.activateWindow()

        self.apply_theme()
        self.sync()
        self.status_timer.start()
        if self.nav_list.currentRow() == self._idx_logs:
            self.log_timer.start()

    def hideEvent(self, e):
        super().hideEvent(e)
        self.status_timer.stop()
        if hasattr(self, "log_timer"):
            self.log_timer.stop()
