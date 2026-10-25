"""獨立自由拖曳浮動條與自訂統計 HUD（FloatingMoodHUD）。

功能：
1. 自由拖曳移動並自動記憶座標 (floating_hud_pos)。
2. 透明度與尺寸縮放適應。
3. 支援雙擊快速收折為 Mini 膠囊條。
4. 全維度指標即時呈現：
   - 漸層心情值進度條與狀態文字
   - 親自餵食連擊數 (Feed Combo)
   - 撫摸摸頭累計次數、系統敲擊採樣次數、AI 對話互動數
   - 養寵陪伴時長自適應換算（年/月/天/時/分）
   - 頂鍋紀錄（目前/歷史最多）
   - 使用者自訂計數器與一鍵 (+) 快速累加
"""
from __future__ import annotations

import time
from typing import Any

from PySide6.QtCore import QPoint, QRect, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPen,
)
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .config import Config, log
from .mood_engine import MoodEngine, format_companion_time


class FloatingMoodHUD(QWidget):
    """獨立桌面置頂無邊框狀態 HUD。"""

    def __init__(self, cfg: Config, mood_engine: MoodEngine, parent=None):
        super().__init__(
            None,
            Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint | Qt.NoDropShadowWindowHint
        )
        self.cfg = cfg
        self.engine = mood_engine

        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setMouseTracking(True)
        self.setWindowTitle("Desktop Pet Stats HUD")

        self.is_mini = False
        self._drag_pos: QPoint | None = None

        self._init_ui()
        self.sync_appearance()
        self._restore_position()

        # 訊號監聽
        self.engine.mood_changed.connect(self._on_mood_changed)
        self.engine.feed_combo_updated.connect(self._on_combo_updated)

        # 定時刷新陪伴時長與統計數據 (每 10 秒)
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(10000)
        self.refresh_timer.timeout.connect(self.update_content)
        self.refresh_timer.start()

    def _init_ui(self):
        self.setFixedSize(360, 240)
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(14, 12, 14, 12)
        self.main_layout.setSpacing(8)

        # 1. 標題列
        title_box = QHBoxLayout()
        title_box.setSpacing(8)

        self.lbl_title = QLabel("::: 桌面寵物狀態 HUD")
        self.lbl_title.setStyleSheet("color: #94A3B8; font-weight: bold; font-size: 12px;")
        title_box.addWidget(self.lbl_title)

        title_box.addStretch()

        self.btn_toggle = QPushButton("—")
        self.btn_toggle.setFixedSize(22, 22)
        self.btn_toggle.setToolTip("切換精簡膠囊條")
        self.btn_toggle.setStyleSheet("""
            QPushButton { background-color: #334155; color: #FFFFFF; border-radius: 4px; font-weight: bold; }
            QPushButton:hover { background-color: #475569; }
        """)
        self.btn_toggle.clicked.connect(self.toggle_mini)
        title_box.addWidget(self.btn_toggle)

        self.btn_close = QPushButton("✕")
        self.btn_close.setFixedSize(22, 22)
        self.btn_close.setToolTip("隱藏 HUD (可在設定中重新開啟)")
        self.btn_close.setStyleSheet("""
            QPushButton { background-color: #7F1D1D; color: #FFFFFF; border-radius: 4px; font-weight: bold; }
            QPushButton:hover { background-color: #991B1B; }
        """)
        self.btn_close.clicked.connect(self.hide_hud)
        title_box.addWidget(self.btn_close)

        self.main_layout.addLayout(title_box)

        # 2. 心情進度文字與百分比
        self.lbl_mood = QLabel("心情值: 50.0 / 100.0 (平靜)")
        self.lbl_mood.setStyleSheet("color: #F8FAFC; font-weight: bold; font-size: 13px;")
        self.main_layout.addWidget(self.lbl_mood)

        # 3. 統計數據資訊標籤列
        self.lbl_combo_pat = QLabel("餵食連擊: [ 0 COMBO ]    撫摸摸頭: 0 次")
        self.lbl_combo_pat.setStyleSheet("color: #E2E8F0; font-size: 12px;")
        self.main_layout.addWidget(self.lbl_combo_pat)

        self.lbl_uptime = QLabel("陪伴時長: 剛剛開始陪伴")
        self.lbl_uptime.setStyleSheet("color: #38BDF8; font-size: 12px;")
        self.main_layout.addWidget(self.lbl_uptime)

        self.lbl_work = QLabel("工作擊鍵: 0 次    AI 對話: 0 次")
        self.lbl_work.setStyleSheet("color: #E2E8F0; font-size: 12px;")
        self.main_layout.addWidget(self.lbl_work)

        self.lbl_pots = QLabel("頂鍋紀錄: 0 頂 (歷史最高: 0 頂)")
        self.lbl_pots.setStyleSheet("color: #FACC15; font-size: 12px;")
        self.main_layout.addWidget(self.lbl_pots)

        # 4. 自訂計數器列
        self.custom_box = QHBoxLayout()
        self.custom_box.setSpacing(6)
        self.main_layout.addLayout(self.custom_box)
        self._refresh_custom_counters_ui()

        self.main_layout.addStretch()

    def sync_appearance(self):
        """同步 HUD 透明度與縮放尺寸。"""
        op = float(self.cfg.get("floating_hud_opacity", 90)) / 100.0
        self.setWindowOpacity(max(0.2, min(1.0, op)))
        self.update()

    def _restore_position(self):
        pos = self.cfg.get("floating_hud_pos")
        if pos and isinstance(pos, list) and len(pos) >= 2:
            self.move(int(pos[0]), int(pos[1]))
        else:
            self.move(120, 120)

    def _save_position(self):
        self.cfg.set("floating_hud_pos", [self.x(), self.y()], save=True)

    @property
    def is_collapsed(self) -> bool:
        return self.is_mini

    @is_collapsed.setter
    def is_collapsed(self, val: bool):
        self.is_mini = bool(val)

    def toggle_collapse(self):
        """切換迷你膠囊折疊狀態 (toggle_mini 別名)。"""
        self.toggle_mini()

    def toggle_mini(self):
        """切換迷你膠囊條與完整展開模式。"""
        self.is_mini = not self.is_mini
        if self.is_mini:
            self.setFixedSize(220, 48)
            self.lbl_combo_pat.hide()
            self.lbl_uptime.hide()
            self.lbl_work.hide()
            self.lbl_pots.hide()
            self.btn_toggle.setText("＋")
        else:
            self.setFixedSize(360, 240)
            self.lbl_combo_pat.show()
            self.lbl_uptime.show()
            self.lbl_work.show()
            self.lbl_pots.show()
            self.btn_toggle.setText("—")
        self.update_content()

    def hide_hud(self):
        self.cfg.set("floating_hud_enabled", False, save=True)
        self.hide()

    def update_content(self):
        """更新 HUD 內所有即時文字與計數。"""
        cur_mood = self.engine.get_mood()
        max_lim = self.engine.get_max_limit()
        pct = (cur_mood / max_lim) * 100.0

        if pct >= 80:
            desc = "非常開心"
        elif pct >= 60:
            desc = "愉快"
        elif pct >= 40:
            desc = "平靜"
        elif pct >= 20:
            desc = "無精打采"
        else:
            desc = "極度難過"

        self.lbl_mood.setText(f"心情值: {cur_mood:.1f} / {max_lim:.1f} ({desc})")

        stats = self.engine.get_stats()
        combo = stats.get("current_feed_combo", 0)
        pats = stats.get("pat_count", 0)
        self.lbl_combo_pat.setText(f"餵食連擊: [ x{combo} COMBO ]    撫摸摸頭: {pats:,} 次")

        self.lbl_uptime.setText(f"陪伴時長: {self.engine.get_companion_time_text()}")

        keys = stats.get("keystroke_count", 0)
        ai_cnt = stats.get("ai_dialogue_count", 0)
        self.lbl_work.setText(f"工作擊鍵: {keys:,} 次    AI 對話: {ai_cnt:,} 次")

        pots_worn = stats.get("total_pots_worn", 0)
        max_pots = stats.get("max_pots_record", 0)
        self.lbl_pots.setText(f"累積頂鍋: {pots_worn:,} 頂 (歷史最多: {max_pots:,} 頂)")

        self.update()

    def _refresh_custom_counters_ui(self):
        """重新生成自訂計數器按鈕列。"""
        # 清空舊有項目
        while self.custom_box.count() > 0:
            item = self.custom_box.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        stats = self.engine.get_stats()
        counters = stats.get("custom_counters", [])
        for c_item in counters:
            cid = c_item.get("id")
            cname = c_item.get("name", "自訂計數")
            count = c_item.get("count", 0)

            btn = QPushButton(f"{cname}: {count} (+)")
            btn.setStyleSheet("""
                QPushButton { background-color: #1E293B; color: #93C5FD; border: 1px solid #334155; border-radius: 4px; padding: 3px 8px; font-size: 11px; }
                QPushButton:hover { background-color: #2563EB; color: #FFFFFF; }
            """)
            btn.clicked.connect(lambda _, _cid=cid: self._increment_custom_counter(_cid))
            self.custom_box.addWidget(btn)

    def _increment_custom_counter(self, counter_id: str):
        stats = dict(self.engine.get_stats())
        counters = stats.get("custom_counters", [])
        for c in counters:
            if c.get("id") == counter_id:
                c["count"] = c.get("count", 0) + 1
                break
        self.cfg.set("pet_stats", stats, save=True)
        self._refresh_custom_counters_ui()
        self.engine.apply_delta(0.5, source="自訂打卡計數")

    def _on_mood_changed(self, cur, max_lim):
        self.update_content()

    def _on_combo_updated(self, combo):
        self.update_content()

    # ------------------------------------------------------------- 繪製自訂背景與心情漸層進度條
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)

        # 1. 現代半透明深色玻璃擬態卡片底框
        p.setBrush(QBrush(QColor(16, 20, 29, 235)))
        p.setPen(QPen(QColor(51, 65, 85, 180), 1))
        p.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 12, 12)

        # 2. 心情進度條槽 (Mini 模式或展開模式皆繪製於底部)
        bar_h = 6
        bar_y = self.height() - bar_h - 10
        bar_x = 14
        bar_w = self.width() - 28

        # 底槽
        p.setBrush(QBrush(QColor(30, 41, 59)))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(bar_x, bar_y, bar_w, bar_h, 3, 3)

        # 進度漸層 (綠-青-藍-紫)
        cur = self.engine.get_mood()
        lim = self.engine.get_max_limit()
        ratio = max(0.0, min(1.0, cur / lim))
        fill_w = int(bar_w * ratio)

        if fill_w > 0:
            grad = QLinearGradient(bar_x, bar_y, bar_x + fill_w, bar_y)
            grad.setColorAt(0.0, QColor("#10B981"))
            grad.setColorAt(0.5, QColor("#38BDF8"))
            grad.setColorAt(1.0, QColor("#818CF8"))
            p.setBrush(QBrush(grad))
            p.drawRoundedRect(bar_x, bar_y, fill_w, bar_h, 3, 3)

    # ------------------------------------------------------------- 滑鼠拖曳移動
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_pos = e.globalPosition().toPoint() - self.pos()
            e.accept()

    def mouseMoveEvent(self, e):
        if self._drag_pos and e.buttons() & Qt.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag_pos)
            e.accept()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_pos = None
            self._save_position()
            e.accept()

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.toggle_mini()
            e.accept()
