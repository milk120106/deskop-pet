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
    ASSETS,
    CUSTOM_CHARS_DIR,
    GITHUB_RELEASES_API,
    GITHUB_RELEASES_URL,
    GITHUB_REPO_URL,
    PROV_IDS,
    PROV_NAMES,
    SOUND_LIB_DIR,
)
from .dialogs import CharPickerDialog, ModernMessageBox, SoundLibraryDialog
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

ARROW_DOWN_DARK = (ASSETS / "arrow_down_dark.svg").as_posix()
ARROW_DOWN_LIGHT = (ASSETS / "arrow_down_light.svg").as_posix()

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
QScrollArea, QScrollArea > QWidget, #CardContainer, #CardViewport {
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
QLineEdit, QSpinBox, QDoubleSpinBox {
    background-color: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    padding: 6px 10px;
    color: #0f172a;
}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 2px solid #2563eb;
}
QComboBox {
    background-color: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    padding: 6px 30px 6px 12px;
    color: #0f172a;
}
QComboBox:hover {
    border-color: #94a3b8;
}
QComboBox:focus {
    border: 2px solid #2563eb;
    padding: 5px 29px 5px 11px;
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
QScrollBar:horizontal {
    border: none;
    background-color: #f8f9fa;
    height: 8px;
    margin: 0;
}
QScrollBar::handle:horizontal {
    background-color: #cbd5e1;
    min-width: 28px;
    border-radius: 4px;
    margin: 2px;
}
QScrollBar::add-line, QScrollBar::sub-line {
    width: 0;
    height: 0;
    background: none;
}
QScrollBar::add-page, QScrollBar::sub-page {
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
QScrollArea, QScrollArea > QWidget, #CardContainer, #CardViewport {
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
QLineEdit, QSpinBox, QDoubleSpinBox {
    background-color: #1f232b;
    border: 1px solid #3b404d;
    border-radius: 8px;
    padding: 6px 10px;
    color: #ffffff;
}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 2px solid #3b82f6;
}
QComboBox {
    background-color: #1f232b;
    border: 1px solid #3b404d;
    border-radius: 8px;
    padding: 6px 30px 6px 12px;
    color: #ffffff;
}
QComboBox:hover {
    border-color: #555b6d;
}
QComboBox:focus {
    border: 2px solid #3b82f6;
    padding: 5px 29px 5px 11px;
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
QComboBox QAbstractItemView {
    background-color: #1f232b;
    border: 1px solid #3b404d;
    border-radius: 8px;
    selection-background-color: #2c3954;
    selection-color: #93c5fd;
    padding: 4px;
    outline: none;
    color: #ffffff;
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
QScrollBar:horizontal {
    border: none;
    background-color: #16181d;
    height: 8px;
    margin: 0;
}
QScrollBar::handle:horizontal {
    background-color: #3b404d;
    min-width: 28px;
    border-radius: 4px;
    margin: 2px;
}
QScrollBar::add-line, QScrollBar::sub-line {
    width: 0;
    height: 0;
    background: none;
}
QScrollBar::add-page, QScrollBar::sub-page {
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

LIGHT_MD3_QSS = LIGHT_MD3_QSS.replace("__ARROW_DOWN_LIGHT__", ARROW_DOWN_LIGHT)
DARK_MD3_QSS = DARK_MD3_QSS.replace("__ARROW_DOWN_DARK__", ARROW_DOWN_DARK)


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
    if scroll.viewport():
        scroll.viewport().setObjectName("CardViewport")
        scroll.viewport().setAttribute(Qt.WA_StyledBackground, True)
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
        self.setWindowTitle("桌面寵物 設定中心")
        self.setFixedSize(960, 650)
        self._lock = False
        self._disc_worker = None
        self._update_worker = None

        is_dark = (self.cfg.get("theme", "light") == "dark")

        # Root layout: TitleBar (Top) + Body (Bottom)
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.title_bar = CustomTitleBar(self, "桌面寵物 設定中心", has_min=True, has_close=True, theme="dark" if is_dark else "light")
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

        sub_lbl = QLabel("設定中心")
        sub_lbl.setObjectName("AppSubtitle")
        sb_lay.addWidget(sub_lbl)

        self.nav_list = QListWidget()
        self.nav_list.setObjectName("NavList")
        nav_items = [
            "視窗設定",
            "角色與形態",
            "效能與渲染",
            "隱私與 Agent",
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
        btn_qml = QPushButton("QML 現代動效版")
        btn_qml.setIcon(get_icon("settings", "#3b82f6", 16))
        btn_qml.clicked.connect(self._open_qml_panel)
        sb_lay.addWidget(btn_qml)

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

        # Add 11 Pages
        self.stack.addWidget(_page_wrapper(self._tab_window()))
        self.stack.addWidget(_page_wrapper(self._tab_character()))
        self.stack.addWidget(_page_wrapper(self._tab_performance()))
        self.stack.addWidget(_page_wrapper(self._tab_privacy_agent()))
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

    def _open_qml_panel(self):
        self.app.show_qml_panel()

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

        t_lbl = QLabel("視窗行為、大小與字體")
        t_lbl.setObjectName("PageTitle")
        d_lbl = QLabel("設定桌面寵物之視窗行為、大小與字體。")
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
        for name, px in (("迷你 100", 100), ("精巧 180", 180), ("標準 340", 340), ("大杯 454", 454), ("特大 640", 640)):
            b = QPushButton(name)
            b.clicked.connect(lambda _=False, v=px: self.app.set_size(v))
            r_cup.addWidget(b)
        f2.addLayout(r_cup)

        r2 = QHBoxLayout()
        self.sp_size = QSpinBox()
        self.sp_size.setRange(80, 1024)
        self.sp_size.setSuffix(" px")
        b = QPushButton("套用自訂尺寸")
        b.clicked.connect(lambda: self.app.set_size(self.sp_size.value()))
        r2.addWidget(self.sp_size, 1)
        r2.addWidget(b)
        f2.addLayout(r2)
        lay.addWidget(g2)

        # 3. 自訂字體
        g_font = QGroupBox("自訂字體 (Typography)")
        f_font = QVBoxLayout(g_font)
        f_font.setContentsMargins(16, 18, 16, 16)
        f_font.setSpacing(12)

        f_font.addWidget(_hint("支援系統安裝字型選取或自訂 .ttf / .otf 檔案匯入，套用後即時生效。"))

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
        b_reset_font = QPushButton("重設為預設字體")
        b_reset_font.clicked.connect(self._reset_default_font)
        r_fbtns.addWidget(b_apply_font)
        r_fbtns.addWidget(b_reset_font)
        r_fbtns.addStretch(1)
        f_font.addLayout(r_fbtns)

        self.lb_font_status = QLabel("目前狀態：使用預設字體")
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
                ModernMessageBox.warning(self, "提示", "請先選取有效的 .ttf 或 .otf 字體檔案。")
                return
            ok, fam, err = load_font_file(path)
            if not ok:
                ModernMessageBox.warning(self, "字體載入失敗", err)
                return
            apply_global_font(fam)
            self.cfg.set("font_mode", "custom_file", save=False)
            self.cfg.set("custom_font_path", path, save=False)
            self.cfg.set("font_family", fam, save=True)
            self.lb_font_status.setText(f"目前狀態：已套用自訂字體 [{fam}]")
            ModernMessageBox.information(self, "字體設定", f"已成功全域套用自訂字體：{fam}")
        else:
            fam = self.cmb_sys_fonts.currentText().strip()
            if not fam:
                return
            apply_global_font(fam)
            self.cfg.set("font_mode", "system", save=False)
            self.cfg.set("font_family", fam, save=True)
            self.lb_font_status.setText(f"目前狀態：已套用系統字體 [{fam}]")
            ModernMessageBox.information(self, "字體設定", f"已成功全域套用系統字體：{fam}")

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
        self.lb_font_status.setText(f"目前狀態：已還原為預設字體 [{best}]")
        self._update_font_preview()
        ModernMessageBox.information(self, "字體設定", f"已還原為預設字體：{best}")

    # ------------------------------------------------------------- 2. 角色與形態
    def _tab_character(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)

        t_lbl = QLabel("角色設定與比例形態")
        t_lbl.setObjectName("PageTitle")
        d_lbl = QLabel("切換桌面寵物立繪與顯示比例。")
        d_lbl.setObjectName("PageDesc")
        lay.addWidget(t_lbl)
        lay.addWidget(d_lbl)

        g = QGroupBox("目前角色")
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

        g2 = QGroupBox("寵物形態比例")
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
        f2.addWidget(_hint("提供標準正方形 (1:1) 與完整立繪寬屏 (1.5:1) 兩種比例形態，手持平板與視窗邊界將自動適配。"))
        lay.addWidget(g2)

        lay.addStretch(1)
        return w

    def _open_char_picker(self):
        parent = self if self.isVisible() else None
        dlg = CharPickerDialog(self.app, parent)
        dlg.exec()
        self.sync()

    # ------------------------------------------------------------- 3. 效能與渲染設定
    def _tab_performance(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)

        t_lbl = QLabel("效能與渲染優化")
        t_lbl.setObjectName("PageTitle")
        d_lbl = QLabel("針對低配電腦、省電模式與不同顯示晶片調整更新率、垂直同步與動效。")
        d_lbl.setObjectName("PageDesc")
        lay.addWidget(t_lbl)
        lay.addWidget(d_lbl)

        g1 = QGroupBox("效能模式與畫面調度")
        f1 = QVBoxLayout(g1)
        f1.setContentsMargins(16, 18, 16, 16)
        f1.setSpacing(10)

        self.cb_perf_mode = QCheckBox("啟用極致效能模式 (幀率降至 30 FPS、關閉愛心粒子與飄字上升動效)")
        self.cb_perf_mode.toggled.connect(lambda v: self._do(self.app.set_performance_mode, v))
        f1.addWidget(self.cb_perf_mode)

        self.cb_disable_trans = QCheckBox("停用半透明背景 (改用純色背景緩衝，透明度鎖定 1.0，大幅減輕 GPU 負擔)")
        self.cb_disable_trans.toggled.connect(lambda v: self._do(self.app.set_disable_transparency, v))
        f1.addWidget(self.cb_disable_trans)

        self.cb_anims_enabled = QCheckBox("啟用角色撫摸形變與物理彈跳動效")
        self.cb_anims_enabled.toggled.connect(lambda v: self._do(self.app.set_animations_enabled, v))
        f1.addWidget(self.cb_anims_enabled)

        self.cb_disable_blur = QCheckBox("停用背景模糊特效 (減少視窗合成負擔)")
        self.cb_disable_blur.toggled.connect(lambda v: self._do(self.app.set_disable_blur, v))
        f1.addWidget(self.cb_disable_blur)
        lay.addWidget(g1)

        g2 = QGroupBox("更新率與底層渲染 API")
        f2 = QVBoxLayout(g2)
        f2.setContentsMargins(16, 18, 16, 16)
        f2.setSpacing(12)

        r_fps = QHBoxLayout()
        r_fps.addWidget(QLabel("目標幀率 (Target FPS)："))
        self.cmb_fps = QComboBox()
        self.fps_options = [10, 15, 20, 24, 30, 45, 60, 90, 120, 144, 240, 0]
        for fps in self.fps_options:
            self.cmb_fps.addItem(f"{fps} FPS" if fps > 0 else "無限制 (0)")
        self.cmb_fps.currentIndexChanged.connect(
            lambda idx: self._do(self.app.set_target_fps, self.fps_options[idx])
        )
        r_fps.addWidget(self.cmb_fps, 1)
        f2.addLayout(r_fps)

        r_vsync = QHBoxLayout()
        r_vsync.addWidget(QLabel("垂直同步模式 (V-Sync)："))
        self.cmb_vsync = QComboBox()
        self.vsync_options = [
            (1, "標準垂直同步 (1) - 推薦預設"),
            (0, "關閉垂直同步 (0) - 最低延遲"),
            (-1, "自適應 / 三重緩衝 (-1)"),
        ]
        for mode, label in self.vsync_options:
            self.cmb_vsync.addItem(label, mode)
        self.cmb_vsync.currentIndexChanged.connect(
            lambda idx: self._do(self.app.set_vsync_mode, self.vsync_options[idx][0])
        )
        r_vsync.addWidget(self.cmb_vsync, 1)
        f2.addLayout(r_vsync)

        r_rhi = QHBoxLayout()
        r_rhi.addWidget(QLabel("Qt 渲染後端 (QSG_RHI_BACKEND)："))
        self.cmb_backend = QComboBox()
        self.backend_options = [
            ("opengl", "OpenGL (預設，相容性最佳)"),
            ("d3d11", "Direct3D 11 (Windows 原生流暢)"),
            ("d3d12", "Direct3D 12 (現代低延遲)"),
            ("vulkan", "Vulkan (高效能跨平台)"),
            ("software", "Software (純軟體光柵化，無顯卡加速)"),
        ]
        for b_id, b_label in self.backend_options:
            self.cmb_backend.addItem(b_label, b_id)
        self.cmb_backend.currentIndexChanged.connect(
            lambda idx: self._do(self.app.set_rendering_backend, self.backend_options[idx][0])
        )
        r_rhi.addWidget(self.cmb_backend, 1)
        f2.addLayout(r_rhi)
        f2.addWidget(_hint("變更 Qt 渲染後端需重新啟動軟體方可完整生效。"))
        lay.addWidget(g2)

        lay.addStretch(1)
        return w

    # ------------------------------------------------------------- 4. 隱私與 Agent 規則
    def _tab_privacy_agent(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)

        t_lbl = QLabel("推論隱私與 Agent 規則")
        t_lbl.setObjectName("PageTitle")
        d_lbl = QLabel("管理個資脫敏過濾器、第三方零儲存參數與系統助手安全防護。")
        d_lbl.setObjectName("PageDesc")
        lay.addWidget(t_lbl)
        lay.addWidget(d_lbl)

        g_priv = QGroupBox("第三方推論隱私優先保護")
        f_priv = QVBoxLayout(g_priv)
        f_priv.setContentsMargins(16, 18, 16, 16)
        f_priv.setSpacing(10)

        self.cb_privacy_mode = QCheckBox("啟用本機資料脫敏過濾器 (自動遮蔽本機路徑、API Key、私有 IP 及使用者名稱)")
        self.cb_privacy_mode.toggled.connect(lambda v: self._do(self.app.set_privacy_mode, v))
        f_priv.addWidget(self.cb_privacy_mode)

        f_priv.addWidget(_hint("送出前將自動將路徑轉為 [本機檔案路徑]、IP 轉為 [私有IP位址]、憑證轉為 [金鑰憑證]。"))

        btn_openrouter_byok = QPushButton("開啟 OpenRouter 儀表板 Guardrails 與 BYOK 設定")
        btn_openrouter_byok.setIcon(get_icon("security", "#3b82f6", 16))
        btn_openrouter_byok.clicked.connect(lambda: webbrowser.open("https://openrouter.ai/settings/privacy"))
        f_priv.addWidget(btn_openrouter_byok)

        info_box = QLabel(
            "OpenRouter 具備強大雲端隱私與安全機制：\n"
            "1. 多 Key 聚合 (BYOK)：可自帶各家廠商原始 API Key，由 OpenRouter 統一代理調度。\n"
            "2. 雲端 PII 自動遮蔽：在推論前自動對個資與敏感資訊進行遮蔽與脫敏防護。\n"
            "3. 強制零資料保留 (Zero Data Retention, ZDR)：保證第三方模型供應商絕不保留或訓練使用者之對話數據。"
        )
        info_box.setWordWrap(True)
        info_box.setStyleSheet(
            "background-color: rgba(59, 130, 246, 0.08); border: 1px solid rgba(59, 130, 246, 0.25); "
            "border-radius: 8px; padding: 10px 12px; font-size: 12px; color: #64748b; line-height: 1.45;"
        )
        f_priv.addWidget(info_box)
        lay.addWidget(g_priv)

        g_agent = QGroupBox("系統助手 (Agent) 安全規則引擎")
        f_agent = QVBoxLayout(g_agent)
        f_agent.setContentsMargins(16, 18, 16, 16)
        f_agent.setSpacing(10)

        self.cb_agent_auto = QCheckBox("自動允許白名單指令執行 (若未勾選則每次執行指令皆需使用者確認)")
        self.cb_agent_auto.toggled.connect(lambda v: self._do(lambda x: self.cfg.set("agent_auto_approve_whitelist", x), v))
        f_agent.addWidget(self.cb_agent_auto)

        rules_lbl = QLabel(
            "安全防護規格：\n"
            "• 白名單指令 (15項)：dir, echo, date, time, whoami, hostname, ver, systeminfo, tasklist, ipconfig, ping, netstat 等\n"
            "• 黑名單指令 (嚴格禁止)：format, del /f /s /q, rmdir /s /q, rm -rf, reg delete, diskpart, shutdown 等\n"
            "• 敏感目錄防護：C:\\Windows, C:\\Program Files 等受寫入與刪除嚴格保護\n"
            "• 遇非白名單命令時，一律彈出精緻小彈窗 (380x220) 授權確認，絕不彈出全螢幕警報！"
        )
        rules_lbl.setWordWrap(True)
        rules_lbl.setStyleSheet(
            "background-color: rgba(16, 185, 129, 0.08); border: 1px solid rgba(16, 185, 129, 0.25); "
            "border-radius: 8px; padding: 10px 12px; font-size: 12px; color: #64748b; line-height: 1.45;"
        )
        f_agent.addWidget(rules_lbl)
        lay.addWidget(g_agent)

        lay.addStretch(1)
        return w

    # ------------------------------------------------------------- 4. 互動演示
    def _tab_demo(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)

        t_lbl = QLabel("互動與動作測試")
        t_lbl.setObjectName("PageTitle")
        d_lbl = QLabel("測試扣費動畫、充值掉落飯盆、物理碰撞與吸附效果。")
        d_lbl.setObjectName("PageDesc")
        lay.addWidget(t_lbl)
        lay.addWidget(d_lbl)

        g = QGroupBox("模擬扣費互動")
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

        g2 = QGroupBox("模擬充值餵食")
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
        f2.addWidget(_hint("飯盆掉落後具備重力與地面回彈效果；拖曳到角色身上即可餵食；閒置 10 秒將自動吸入。"))
        lay.addWidget(g2)

        g3 = QGroupBox("道具控制")
        f3 = QVBoxLayout(g3)
        f3.setContentsMargins(16, 18, 16, 16)
        f3.setSpacing(12)

        b_radar = QPushButton("觸發道具吸附")
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

        t_lbl = QLabel("聲音與音效設定")
        t_lbl.setObjectName("PageTitle")
        d_lbl = QLabel("調整提示音量或透過音效庫更換個別音訊檔案。")
        d_lbl.setObjectName("PageDesc")
        lay.addWidget(t_lbl)
        lay.addWidget(d_lbl)

        g = QGroupBox("音量與音效")
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
        b_lib = QPushButton("自訂音效庫設定...")
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
        d_lbl = QLabel("設定陪伴對話、語音辨識、Gemini Live 與模型選項。")
        d_lbl.setObjectName("PageDesc")
        lay.addWidget(t_lbl)
        lay.addWidget(d_lbl)

        # 1. AI 對話與設定檔
        g_core = QGroupBox("AI 對話與設定檔")
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
        g_live = QGroupBox("Gemini Live 語音模式")
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
        g_disc = QGroupBox("線上模型探索 (Remote Model Discovery)")
        f_disc = QVBoxLayout(g_disc)
        f_disc.setContentsMargins(16, 18, 16, 16)
        f_disc.setSpacing(12)

        f_disc.addWidget(_hint("向廠商 API 端點發送請求，取得該帳號可用的模型清單並支援套用。"))

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
            ModernMessageBox.warning(self, "提示", "尚未選擇有效的模型 ID。")
            return
        self.ed_live_model.setText(mid)
        self.cfg.set("gemini_live_model", mid, save=True)
        ModernMessageBox.information(self, "已套用", f"已將 Gemini Live 模型設定為: {mid}")

    def _apply_disc_to_active_profile(self):
        mid = self.cmb_disc_models.currentData() or self.cmb_disc_models.currentText()
        if not mid or mid.startswith("（"):
            ModernMessageBox.warning(self, "提示", "尚未選擇有效的模型 ID。")
            return
        profiles = [dict(x) for x in self.cfg.get("api_profiles", [])]
        act_idx = max(0, min(self.cmb_active_profile.currentIndex(), len(profiles) - 1))
        if profiles:
            profiles[act_idx]["model"] = mid
            self.cfg.set("api_profiles", profiles, save=True)
            ModernMessageBox.information(self, "已套用", f"已更新目前設定檔的模型 ID 為: {mid}")

    def _save_live_settings(self):
        self.cfg.set("gemini_live_model", self.ed_live_model.text().strip(), save=False)
        self.cfg.set("gemini_live_voice", self.cmb_live_voice.currentText().strip(), save=True)
        ModernMessageBox.information(self, "儲存成功", "Gemini Live 設定已更新。")

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

        t_lbl = QLabel("API 與餘額監控")
        t_lbl.setObjectName("PageTitle")
        d_lbl = QLabel("連接 API 即時監控餘額，或使用模擬模式進行測試。")
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
        ModernMessageBox.information(self, "已儲存", f"{PROV_NAMES[idx]} 設定已儲存並套用。")

    # ------------------------------------------------------------- 8. 網頁儀表板
    def _tab_web(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)

        t_lbl = QLabel("網頁儀表板 (Web Dashboard)")
        t_lbl.setObjectName("PageTitle")
        d_lbl = QLabel("在瀏覽器中檢視餘額趨勢、消費紀錄與匯出報表。")
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
                "網頁伺服器僅綁定本機 127.0.0.1，安全唯讀。支援檢視多模型即時餘額、花費統計、趨勢圖表與匯出 CSV。"
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

        t_lbl = QLabel("系統日誌 (Logs)")
        t_lbl.setObjectName("PageTitle")
        d_lbl = QLabel("檢視系統運作日誌，支援等級過濾與關鍵字搜尋。")
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
        d_lbl = QLabel("專案版本、官方開源倉庫、更新檢查與系統資訊。")
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
            "桌面餘額監控與互動寵物。支援 DeepSeek、Claude、OpenAI、Gemini 餘額顯示與互動。\n"
            "本專案為 VK-1 (DSH Balance Pet) 原型倉庫之開源分支（Fork）。"
        )
        intro.setWordWrap(True)
        c1_lay.addWidget(intro)

        repo_info = QLabel(f"官方開源倉庫：{GITHUB_REPO_URL}")
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

        # Card 2: 本機自訂資源目錄 (Local Custom Assets)
        card_art = QFrame()
        card_art.setObjectName("AboutCard")
        c_art_lay = QVBoxLayout(card_art)
        c_art_lay.setContentsMargins(18, 16, 18, 16)
        c_art_lay.setSpacing(10)

        h_art = QLabel("本機自訂資源目錄")
        h_art.setStyleSheet("font-size: 15px; font-weight: bold; color: #10b981;")
        c_art_lay.addWidget(h_art)

        art_desc = QLabel(
            "使用者可自由將自訂的角色立繪（支援 1:1 標準正方形與 1.5:1 帶尾巴形態）與音訊素材放入本機對應目錄中載入使用。"
        )
        art_desc.setWordWrap(True)
        c_art_lay.addWidget(art_desc)

        r_art_btns = QHBoxLayout()
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

        h3 = QLabel("開源協議與系統狀態")
        h3.setStyleSheet("font-size: 14px; font-weight: bold;")
        c3_lay.addWidget(h3)

        lic_lbl = QLabel(
            "本專案程式碼採用 MIT License 開源許可協議發布。\n"
            "圖示採用 Google Material Symbols（Apache License 2.0）。\n"
            "角色立繪與音訊素材著作權歸原創作者所有。"
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

        # Card 4: 開源專案與依賴清單
        card_thanks = QFrame()
        card_thanks.setObjectName("AboutCard")
        cthanks_lay = QVBoxLayout(card_thanks)
        cthanks_lay.setContentsMargins(18, 16, 18, 16)
        cthanks_lay.setSpacing(10)

        h_thanks = QLabel("開源專案與依賴清單")
        h_thanks.setStyleSheet("font-size: 14px; font-weight: bold;")
        cthanks_lay.addWidget(h_thanks)

        thanks_desc = QLabel(
            "• VK-1 (DSH Balance Pet)：原型倉庫（本專案為其衍生分支）\n"
            "• YuYue_Encryption：備份資料加密模組\n"
            "• PySide6 / Qt 6：介面與 QML 渲染框架 (LGPLv3)\n"
            "• Google Material Symbols：向量圖示庫 (Apache 2.0)\n"
            "• Python 標準庫 & Windows MCI：系統核心與本機音訊"
        )
        thanks_desc.setWordWrap(True)
        cthanks_lay.addWidget(thanks_desc)

        r_thanks_btns = QHBoxLayout()
        b_vk1 = QPushButton("造訪 VK-1 倉庫")
        b_vk1.clicked.connect(lambda: webbrowser.open("https://github.com/VKmich16/VK-1"))
        r_thanks_btns.addWidget(b_vk1)

        b_yuyue = QPushButton("造訪 YuYue_Encryption 倉庫")
        b_yuyue.clicked.connect(lambda: webbrowser.open("https://github.com/YuYue71/YuYue_Encryption"))
        r_thanks_btns.addWidget(b_yuyue)

        r_thanks_btns.addStretch(1)
        cthanks_lay.addLayout(r_thanks_btns)
        lay.addWidget(card_thanks)

        # Card 5: 全設定與資料安全備份
        card_bak = QFrame()
        card_bak.setObjectName("AboutCard")
        cbak_lay = QVBoxLayout(card_bak)
        cbak_lay.setContentsMargins(18, 16, 18, 16)
        cbak_lay.setSpacing(10)

        h_bak = QLabel("全設定與資料安全備份")
        h_bak.setStyleSheet("font-size: 14px; font-weight: bold;")
        cbak_lay.addWidget(h_bak)

        bak_desc = QLabel("支援完整匯出寵物配置、鬧鐘與自訂立繪；整合 YuYue 8 層複合高強度加密及 API 金鑰 5 秒倒數安全防護。")
        bak_desc.setWordWrap(True)
        cbak_lay.addWidget(bak_desc)

        r_bak_btns = QHBoxLayout()
        b_export = QPushButton("匯出所有設定與資料...")
        b_export.setObjectName("primary")
        b_export.clicked.connect(self._open_export_dialog)
        r_bak_btns.addWidget(b_export)

        b_import = QPushButton("匯入設定...")
        b_import.clicked.connect(self._open_import_dialog)
        r_bak_btns.addWidget(b_import)

        r_bak_btns.addStretch(1)
        cbak_lay.addLayout(r_bak_btns)
        lay.addWidget(card_bak)

        lay.addStretch(1)
        return w

    def _open_export_dialog(self):
        from .dialogs import ExportSettingsDialog
        dlg = ExportSettingsDialog(self.app, self)
        dlg.exec()

    def _open_import_dialog(self):
        from .dialogs import ImportPasswordDialog, ModernMessageBox
        from .export_data import import_backup_data

        path, _ = QFileDialog.getOpenFileName(
            self, "選擇設定備份檔案", "", "備份檔案 (*.json *.dpbak);;所有檔案 (*.*)"
        )
        if not path:
            return

        try:
            try:
                import_backup_data(self.app, path, password="")
            except ValueError as ve:
                if "NEED_PASSWORD" in str(ve):
                    pwd_dlg = ImportPasswordDialog(self, theme=self.app.cfg.get("theme", "light"))
                    if pwd_dlg.exec() != QDialog.Accepted:
                        return
                    import_backup_data(self.app, path, password=pwd_dlg.password)
                else:
                    raise

            ModernMessageBox.information(self, "匯入成功", "設定與資料已成功還原！已套用最新配置。")
        except Exception as e:
            ModernMessageBox.warning(self, "匯入失敗", f"無法匯入備份設定：{e}")

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
            ("deepseek", "藍色大肥魚 (DeepSeek 鯨魚娘)"),
            ("gpt", "GPT龍娘 (OpenAI)"),
            ("claude", "大小姐Claude (Anthropic)"),
            ("gemini", "北美貓娘Gemini (Google)"),
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

            # Performance & Rendering
            self.cb_perf_mode.setChecked(bool(c.get("performance_mode", False)))
            self.cb_disable_trans.setChecked(bool(c.get("disable_transparency", False)))
            self.cb_anims_enabled.setChecked(bool(c.get("animations_enabled", True)))
            self.cb_disable_blur.setChecked(bool(c.get("disable_blur", False)))

            fps_val = int(c.get("target_fps", 60))
            if fps_val in self.fps_options:
                self.cmb_fps.setCurrentIndex(self.fps_options.index(fps_val))

            vsync_val = int(c.get("vsync_mode", 1))
            vsync_idx = next((i for i, opt in enumerate(self.vsync_options) if opt[0] == vsync_val), 0)
            self.cmb_vsync.setCurrentIndex(vsync_idx)

            backend_val = str(c.get("rendering_backend", "opengl")).strip().lower()
            backend_idx = next((i for i, opt in enumerate(self.backend_options) if opt[0] == backend_val), 0)
            self.cmb_backend.setCurrentIndex(backend_idx)

            # Privacy & Agent
            self.cb_privacy_mode.setChecked(bool(c.get("privacy_mode", True)))
            self.cb_agent_auto.setChecked(bool(c.get("agent_auto_approve_whitelist", False)))

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
