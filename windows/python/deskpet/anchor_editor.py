"""視覺錨點編輯器（Visual Anchor Editor）。

提供獨立可視化介面 VisualAnchorEditorDialog：
1. 支援官方 4 大角色與所有 custom_* 自訂角色。
2. 可視化自由拖曳設定：
   - 頭部撫摸判定區 (Head Zone Handles)
   - 鐵盆戴頂中心與傾角 (Iron Bowl Anchor)
   - 平板透視四邊形 (Tablet Perspective Quad)
   - 飾品掛載點 (Accessory Mounts)
3. 支援四大生命週期操作：
   - 儲存 (Save)
   - 匯出 (Export)
   - 重置為預設 (Reset)
   - 刪除自訂角色 (Delete，官方角色禁止刪除，自訂角色強制二次警告確認彈窗)
"""
from __future__ import annotations

import json
import math
import os
import shutil
from pathlib import Path
from typing import Any

from PySide6.QtCore import QPointF, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygonF,
    QTransform,
)
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSlider,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from .config import APP_DIR, ASSETS, CUSTOM_CHARS_DIR, log

CUSTOM_ANCHORS_DIR = APP_DIR / "custom_anchors"
CUSTOM_ANCHORS_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_ANCHORS = {
    "version": "1.0",
    "base_resolution": [1024, 1024],
    "head_zone": {
        "center_ratio_x": 0.60,
        "top_ratio_y": -0.14,
        "width_ratio": 0.56,
        "height_ratio": 0.54
    },
    "iron_bowl": {
        "center_ratio_x": 0.60,
        "base_ratio_y": 0.19,
        "tilt_angle": 12.0,
        "scale_factor": 0.50
    },
    "iron_bowl_anchor": {
        "center_ratio_x": 0.60,
        "base_ratio_y": 0.19,
        "tilt_angle": 12.0,
        "scale_factor": 0.50
    },
    "tablet_quad": {
        "top_left": [638.0, 680.0],
        "top_right": [988.0, 696.0],
        "bottom_right": [956.0, 936.0],
        "bottom_left": [626.0, 920.0],
        "click_rect_ratio": [0.45, 0.60, 0.40, 0.35]
    },
    "accessory_anchor": {
        "head_mount": [0.60, 0.10],
        "chest_mount": [0.55, 0.50],
        "hand_mount": [0.40, 0.70]
    }
}


def get_character_anchor_path(character_id: str) -> Path:
    """取得指定角色的錨點檔案路徑。"""
    if character_id.startswith("custom_"):
        return CUSTOM_CHARS_DIR / character_id / "anchors.json"
    return CUSTOM_ANCHORS_DIR / f"{character_id}.json"


def load_character_anchors(character_id: str) -> dict[str, Any]:
    """載入角色錨點配置，若無則回傳預設結構。"""
    p = get_character_anchor_path(character_id)
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                merged = json.loads(json.dumps(DEFAULT_ANCHORS))
                for k, v in data.items():
                    if isinstance(v, dict) and k in merged:
                        merged[k].update(v)
                    else:
                        merged[k] = v
                if "iron_bowl" not in merged and "iron_bowl_anchor" in merged:
                    merged["iron_bowl"] = merged["iron_bowl_anchor"]
                return merged
        except Exception as exc:
            log("AnchorEditor", f"讀取角色「{character_id}」錨點失敗: {exc}")
    d = json.loads(json.dumps(DEFAULT_ANCHORS))
    d["character_id"] = character_id
    if "iron_bowl" not in d and "iron_bowl_anchor" in d:
        d["iron_bowl"] = d["iron_bowl_anchor"]
    if character_id == "claude":
        d["head_zone"]["center_ratio_x"] = 0.672
        d["iron_bowl_anchor"]["center_ratio_x"] = 0.672
        if "iron_bowl" in d:
            d["iron_bowl"]["center_ratio_x"] = 0.672
    return d


def save_character_anchors(character_id: str, data: dict[str, Any]):
    """保存角色錨點配置至磁碟。"""
    p = get_character_anchor_path(character_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    log("AnchorEditor", f"成功儲存角色「{character_id}」錨點配置至 {p}")


class AnchorCanvas(QWidget):
    """可視化畫布：繪製角色立繪、頭部感應框、鐵盆戴頂錨點與平板四邊形 Handles。"""
    anchors_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.character_id = "deepseek"
        self.anchors = json.loads(json.dumps(DEFAULT_ANCHORS))
        self.char_img: QImage | None = None
        self.iron_pix: QPixmap | None = None

        # 互動狀態
        self.active_handle: str | None = None
        self.drag_start_pos: QPointF | None = None
        self.drag_orig_val: Any = None
        self.hover_handle: str | None = None

        self._load_iron_pix()

    def _load_iron_pix(self):
        iron_path = ASSETS / "iron_bowl.png"
        if iron_path.exists():
            img = QImage(str(iron_path))
            self.iron_pix = QPixmap.fromImage(img)
        else:
            self.iron_pix = None

    def set_character(self, character_id: str):
        self.character_id = character_id
        self.anchors = load_character_anchors(character_id)
        self._load_character_image()
        self.update()

    def _load_character_image(self):
        # 尋找角色主立繪
        if self.character_id.startswith("custom_"):
            cdir = CUSTOM_CHARS_DIR / self.character_id
            for name in ("sprite.png", "default.png", "idle.png"):
                if (cdir / name).exists():
                    self.char_img = QImage(str(cdir / name))
                    return
            # 尋找第一張 png
            pngs = list(cdir.glob("*.png"))
            if pngs:
                self.char_img = QImage(str(pngs[0]))
                return
        else:
            # 官方角色
            if self.character_id == "deepseek":
                p = ASSETS / "expr" / "expression_11.png"
            else:
                p = ASSETS / "chars" / self.character_id / "sprites" / "expression_11.png"
            if p.exists():
                self.char_img = QImage(str(p))
                return
        self.char_img = None

    def get_canvas_rect(self) -> QRectF:
        """取得置中維持 1:1 或原圖比例之繪製區域。"""
        w = self.width() - 40
        h = self.height() - 40
        size = min(w, h)
        if size <= 10:
            size = 100
        x = (self.width() - size) / 2.0
        y = (self.height() - size) / 2.0
        return QRectF(x, y, size, size)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)

        # 背景格線 (棋盤格)
        p.fillRect(self.rect(), QColor("#1E222D"))
        crect = self.get_canvas_rect()

        # 角色主繪製區底框
        p.fillRect(crect, QColor("#12161F"))
        p.setPen(QPen(QColor("#384252"), 1, Qt.DashLine))
        p.drawRect(crect)

        # 繪製角色立繪
        if self.char_img and not self.char_img.isNull():
            p.drawImage(crect, self.char_img)
        else:
            p.setPen(QColor("#64748B"))
            p.drawText(crect, Qt.AlignCenter, f"未找到「{self.character_id}」之預覽立繪")

        # 1. 繪製頭部撫摸判定區 (綠色半透明框 + Handles)
        hz = self.anchors.get("head_zone", {})
        cx_r = hz.get("center_ratio_x", 0.60)
        top_r = hz.get("top_ratio_y", -0.14)
        w_r = hz.get("width_ratio", 0.56)
        h_r = hz.get("height_ratio", 0.54)

        head_w = crect.width() * w_r
        head_h = crect.height() * h_r
        head_x = crect.left() + crect.width() * cx_r - head_w / 2.0
        head_y = crect.top() + crect.height() * top_r

        head_rect = QRectF(head_x, head_y, head_w, head_h)
        p.fillRect(head_rect, QColor(34, 197, 94, 40))
        p.setPen(QPen(QColor("#22C55E"), 2))
        p.drawRect(head_rect)

        # 頭部標籤與拖曳手柄
        p.setPen(QColor("#22C55E"))
        p.setFont(QFont("Microsoft JhengHei UI", 9, QFont.Bold))
        p.drawText(QPointF(head_x + 4, head_y - 6), "撫摸感應區 (Head Zone)")
        self._draw_handle(p, QPointF(head_x + head_w / 2, head_y + head_h / 2), "head_center", QColor("#22C55E"))
        self._draw_handle(p, QPointF(head_x + head_w, head_y + head_h), "head_resize", QColor("#22C55E"))

        # 2. 繪製鐵盆錨點 (黃色標記與預覽)
        ib = self.anchors.get("iron_bowl_anchor", {})
        ib_cx_r = ib.get("center_ratio_x", 0.60)
        ib_cy_r = ib.get("base_ratio_y", 0.19)
        ib_tilt = ib.get("tilt_angle", 12.0)
        ib_scale = ib.get("scale_factor", 0.50)

        ib_cx = crect.left() + crect.width() * ib_cx_r
        ib_cy = crect.top() + crect.height() * ib_cy_r

        p.save()
        p.translate(ib_cx, ib_cy)
        p.rotate(ib_tilt)
        bowl_w = crect.width() * ib_scale
        bowl_h = bowl_w * 0.45
        bowl_rect = QRectF(-bowl_w / 2, -bowl_h * 0.5, bowl_w, bowl_h)
        if self.iron_pix and not self.iron_pix.isNull():
            p.drawPixmap(bowl_rect.toRect(), self.iron_pix)
        else:
            p.fillRect(bowl_rect, QColor(250, 204, 21, 80))
            p.setPen(QPen(QColor("#FACC15"), 2))
            p.drawRoundedRect(bowl_rect, 6, 6)
        p.restore()

        self._draw_handle(p, QPointF(ib_cx, ib_cy), "bowl_center", QColor("#FACC15"))
        p.setPen(QColor("#FACC15"))
        p.drawText(QPointF(ib_cx + 12, ib_cy - 8), f"鐵盆錨點 ({ib_tilt:.1f}°)")

        # 3. 繪製平板透視四邊形 (藍色 Handles + 測試網格)
        tq = self.anchors.get("tablet_quad", {})
        base_res = self.anchors.get("base_resolution", [1024, 1024])
        bx, by = base_res[0], base_res[1]

        def map_pt(pt_list):
            rx = pt_list[0] / bx
            ry = pt_list[1] / by
            return QPointF(crect.left() + crect.width() * rx, crect.top() + crect.height() * ry)

        tl = map_pt(tq.get("top_left", [638.0, 680.0]))
        tr = map_pt(tq.get("top_right", [988.0, 696.0]))
        br = map_pt(tq.get("bottom_right", [956.0, 936.0]))
        bl = map_pt(tq.get("bottom_left", [626.0, 920.0]))

        poly = QPolygonF([tl, tr, br, bl])
        p.setPen(QPen(QColor("#38BDF8"), 2))
        p.setBrush(QBrush(QColor(56, 189, 248, 45)))
        p.drawPolygon(poly)

        p.setPen(QColor("#38BDF8"))
        p.drawText(tl + QPointF(6, 16), "平板螢幕 (Tablet Quad)")

        self._draw_handle(p, tl, "tablet_tl", QColor("#38BDF8"))
        self._draw_handle(p, tr, "tablet_tr", QColor("#38BDF8"))
        self._draw_handle(p, br, "tablet_br", QColor("#38BDF8"))
        self._draw_handle(p, bl, "tablet_bl", QColor("#38BDF8"))

    def _draw_handle(self, p: QPainter, pt: QPointF, name: str, col: QColor):
        is_hover = (self.hover_handle == name or self.active_handle == name)
        rad = 7 if is_hover else 5
        p.setBrush(QBrush(col))
        p.setPen(QPen(QColor("#FFFFFF"), 2 if is_hover else 1))
        p.drawEllipse(pt, rad, rad)

    # ------------------------------------------------------------- 滑鼠拖曳互動
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            m_pos = e.position()
            handle = self._find_handle_at(m_pos)
            if handle:
                self.active_handle = handle
                self.drag_start_pos = m_pos
                self.drag_orig_val = json.loads(json.dumps(self.anchors))
                e.accept()
                self.update()

    def mouseMoveEvent(self, e):
        m_pos = e.position()
        if self.active_handle and self.drag_start_pos and self.drag_orig_val:
            crect = self.get_canvas_rect()
            dx_ratio = (m_pos.x() - self.drag_start_pos.x()) / crect.width()
            dy_ratio = (m_pos.y() - self.drag_start_pos.y()) / crect.height()

            orig = self.drag_orig_val
            base_res = self.anchors.get("base_resolution", [1024, 1024])

            if self.active_handle == "head_center":
                self.anchors["head_zone"]["center_ratio_x"] = orig["head_zone"]["center_ratio_x"] + dx_ratio
                self.anchors["head_zone"]["top_ratio_y"] = orig["head_zone"]["top_ratio_y"] + dy_ratio
            elif self.active_handle == "head_resize":
                self.anchors["head_zone"]["width_ratio"] = max(0.1, orig["head_zone"]["width_ratio"] + dx_ratio * 2)
                self.anchors["head_zone"]["height_ratio"] = max(0.1, orig["head_zone"]["height_ratio"] + dy_ratio * 2)
            elif self.active_handle == "bowl_center":
                self.anchors["iron_bowl_anchor"]["center_ratio_x"] = orig["iron_bowl_anchor"]["center_ratio_x"] + dx_ratio
                self.anchors["iron_bowl_anchor"]["base_ratio_y"] = orig["iron_bowl_anchor"]["base_ratio_y"] + dy_ratio
            elif self.active_handle.startswith("tablet_"):
                corner = self.active_handle.split("_")[1]
                key_map = {"tl": "top_left", "tr": "top_right", "br": "bottom_right", "bl": "bottom_left"}
                k = key_map.get(corner)
                if k:
                    orig_pt = orig["tablet_quad"][k]
                    new_x = orig_pt[0] + dx_ratio * base_res[0]
                    new_y = orig_pt[1] + dy_ratio * base_res[1]
                    self.anchors["tablet_quad"][k] = [round(new_x, 1), round(new_y, 1)]

            self.anchors_changed.emit()
            self.update()
            return

        # Hover 狀態檢查
        prev_hover = self.hover_handle
        self.hover_handle = self._find_handle_at(m_pos)
        if self.hover_handle != prev_hover:
            self.update()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.active_handle = None
            self.drag_start_pos = None
            self.drag_orig_val = None
            self.update()

    def _find_handle_at(self, m_pos: QPointF) -> str | None:
        crect = self.get_canvas_rect()
        base_res = self.anchors.get("base_resolution", [1024, 1024])
        bx, by = base_res[0], base_res[1]

        def dist(pt: QPointF) -> float:
            return math.hypot(m_pos.x() - pt.x(), m_pos.y() - pt.y())

        # 檢測頭部
        hz = self.anchors.get("head_zone", {})
        cx_r = hz.get("center_ratio_x", 0.60)
        top_r = hz.get("top_ratio_y", -0.14)
        w_r = hz.get("width_ratio", 0.56)
        h_r = hz.get("height_ratio", 0.54)
        head_w = crect.width() * w_r
        head_h = crect.height() * h_r
        head_x = crect.left() + crect.width() * cx_r - head_w / 2.0
        head_y = crect.top() + crect.height() * top_r

        if dist(QPointF(head_x + head_w / 2, head_y + head_h / 2)) <= 12:
            return "head_center"
        if dist(QPointF(head_x + head_w, head_y + head_h)) <= 12:
            return "head_resize"

        # 檢測鐵盆
        ib = self.anchors.get("iron_bowl_anchor", {})
        ib_cx = crect.left() + crect.width() * ib.get("center_ratio_x", 0.60)
        ib_cy = crect.top() + crect.height() * ib.get("base_ratio_y", 0.19)
        if dist(QPointF(ib_cx, ib_cy)) <= 12:
            return "bowl_center"

        # 檢測平板 Handles
        tq = self.anchors.get("tablet_quad", {})
        for corner, k in [("tl", "top_left"), ("tr", "top_right"), ("br", "bottom_right"), ("bl", "bottom_left")]:
            pt = tq.get(k, [0, 0])
            pt_mapped = QPointF(crect.left() + crect.width() * (pt[0] / bx), crect.top() + crect.height() * (pt[1] / by))
            if dist(pt_mapped) <= 12:
                return f"tablet_{corner}"

        return None


class VisualAnchorEditorDialog(QDialog):
    """獨立視覺錨點可視化編輯器對話框。"""

    def __init__(self, *args, **kwargs):
        parent = None
        initial_character = "deepseek"
        if len(args) == 1:
            if isinstance(args[0], str):
                initial_character = args[0]
            else:
                parent = args[0]
        elif len(args) >= 2:
            if isinstance(args[0], str):
                initial_character, parent = args[0], args[1]
            else:
                parent, initial_character = args[0], args[1]
        if "parent" in kwargs:
            parent = kwargs.pop("parent")
        if "initial_character" in kwargs:
            initial_character = kwargs.pop("initial_character")
        super().__init__(parent)
        self.setWindowTitle("桌面寵物部位視覺錨點編輯器")
        self.resize(960, 680)
        self.setStyleSheet("""
            QDialog { background-color: #10141D; color: #F8FAFC; }
            QLabel { color: #F8FAFC; font-family: "Microsoft JhengHei UI", sans-serif; font-size: 13px; }
            QComboBox { background-color: #1E293B; color: #F8FAFC; border: 1px solid #334155; border-radius: 6px; padding: 5px 10px; font-size: 13px; }
            QPushButton { background-color: #2563EB; color: #FFFFFF; border: none; border-radius: 6px; padding: 7px 16px; font-weight: bold; font-size: 13px; }
            QPushButton:hover { background-color: #3B82F6; }
            QPushButton#btnDelete { background-color: #DC2626; }
            QPushButton#btnDelete:hover { background-color: #EF4444; }
            QPushButton#btnReset { background-color: #475569; }
            QPushButton#btnReset:hover { background-color: #64748B; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # 頂部控制列：角色選擇與傾角調節
        top_bar = QHBoxLayout()
        top_bar.addWidget(QLabel("選擇目標角色："))

        self.cb_character = QComboBox()
        self._populate_characters()
        idx = self.cb_character.findData(initial_character)
        if idx >= 0:
            self.cb_character.setCurrentIndex(idx)
        self.cb_character.currentIndexChanged.connect(self._on_character_changed)
        top_bar.addWidget(self.cb_character)

        top_bar.addSpacing(20)
        top_bar.addWidget(QLabel("鐵盆傾角："))
        self.slider_tilt = QSlider(Qt.Horizontal)
        self.slider_tilt.setRange(-45, 45)
        self.slider_tilt.setValue(12)
        self.slider_tilt.valueChanged.connect(self._on_tilt_changed)
        top_bar.addWidget(self.slider_tilt)
        self.lbl_tilt = QLabel("12°")
        top_bar.addWidget(self.lbl_tilt)

        top_bar.addStretch()
        layout.addLayout(top_bar)

        # 中間主體：可視化編輯畫布
        self.canvas = AnchorCanvas(self)
        self.canvas.set_character(self.cb_character.currentData() or "deepseek")
        self.canvas.anchors_changed.connect(self._sync_ui_from_anchors)
        layout.addWidget(self.canvas, 1)

        # 底部操作工具列 (儲存、匯出、重置、刪除自訂角色)
        bottom_bar = QHBoxLayout()
        bottom_bar.setSpacing(10)

        self.btn_reset = QPushButton("重置為預設 (Reset)")
        self.btn_reset.setObjectName("btnReset")
        self.btn_reset.clicked.connect(self._on_reset)
        bottom_bar.addWidget(self.btn_reset)

        self.btn_export = QPushButton("匯出配置 (Export)")
        self.btn_export.clicked.connect(self._on_export)
        bottom_bar.addWidget(self.btn_export)

        self.btn_delete = QPushButton("刪除自訂角色 (Delete)")
        self.btn_delete.setObjectName("btnDelete")
        self.btn_delete.clicked.connect(self._on_delete)
        bottom_bar.addWidget(self.btn_delete)

        bottom_bar.addStretch()

        self.btn_save = QPushButton("儲存設定 (Save)")
        self.btn_save.clicked.connect(self._on_save)
        bottom_bar.addWidget(self.btn_save)

        layout.addLayout(bottom_bar)
        self._update_delete_button_state()

    def _populate_characters(self):
        self.cb_character.clear()
        # 官方 4 大角色
        official = [
            ("DeepSeek (小深)", "deepseek"),
            ("Claude (小克)", "claude"),
            ("Gemini (雙子)", "gemini"),
            ("ChatGPT (小智)", "gpt")
        ]
        for name, cid in official:
            self.cb_character.addItem(name, cid)

        # 掃描自訂角色
        if CUSTOM_CHARS_DIR.exists():
            for p in sorted(CUSTOM_CHARS_DIR.iterdir()):
                if p.is_dir() and p.name.startswith("custom_"):
                    self.cb_character.addItem(f"自訂角色: {p.name}", p.name)

    def _on_character_changed(self):
        cid = self.cb_character.currentData()
        if cid:
            self.canvas.set_character(cid)
            self._sync_ui_from_anchors()
            self._update_delete_button_state()

    def _sync_ui_from_anchors(self):
        tilt = int(self.canvas.anchors.get("iron_bowl_anchor", {}).get("tilt_angle", 12.0))
        self.slider_tilt.blockSignals(True)
        self.slider_tilt.setValue(tilt)
        self.slider_tilt.blockSignals(False)
        self.lbl_tilt.setText(f"{tilt}°")

    def _on_tilt_changed(self, val: int):
        self.lbl_tilt.setText(f"{val}°")
        self.canvas.anchors["iron_bowl_anchor"]["tilt_angle"] = float(val)
        self.canvas.update()

    def _update_delete_button_state(self):
        cid = self.cb_character.currentData() or ""
        # 官方 4 角色嚴格禁止刪除
        is_custom = cid.startswith("custom_")
        self.btn_delete.setEnabled(is_custom)
        if not is_custom:
            self.btn_delete.setToolTip("官方核心角色受系統保護，不可刪除")
        else:
            self.btn_delete.setToolTip("永久刪除此自訂角色配置與相關圖檔")

    def _on_save(self):
        cid = self.cb_character.currentData()
        if cid:
            save_character_anchors(cid, self.canvas.anchors)
            QMessageBox.information(self, "儲存成功", f"角色「{cid}」部位視覺錨點配置已順利保存！")

    def _on_export(self):
        cid = self.cb_character.currentData() or "anchors"
        path, _ = QFileDialog.getSaveFileName(
            self, "匯出錨點 JSON 配置", f"{cid}_anchors.json", "JSON 檔案 (*.json)"
        )
        if path:
            Path(path).write_text(json.dumps(self.canvas.anchors, ensure_ascii=False, indent=2), encoding="utf-8")
            QMessageBox.information(self, "匯出成功", f"錨點配置已順利匯出至：\n{path}")

    def _on_reset(self):
        cid = self.cb_character.currentData() or "deepseek"
        self.canvas.anchors = json.loads(json.dumps(DEFAULT_ANCHORS))
        self.canvas.anchors["character_id"] = cid
        if cid == "claude":
            self.canvas.anchors["head_zone"]["center_ratio_x"] = 0.672
            self.canvas.anchors["iron_bowl_anchor"]["center_ratio_x"] = 0.672
        self._sync_ui_from_anchors()
        self.canvas.update()

    def _on_delete(self):
        cid = self.cb_character.currentData() or ""
        if not cid.startswith("custom_"):
            QMessageBox.warning(self, "操作被拒絕", "官方 4 大核心角色為系統核心依賴，嚴格禁止刪除！")
            return

        target_dir = CUSTOM_CHARS_DIR / cid
        # 強制二次警告確認彈窗
        res = QMessageBox.warning(
            self,
            "永久刪除角色警告確認 (第 1 步 / 共 2 步)",
            f"【重大危險操作警告】\n\n您正準備刪除自訂角色「{cid}」！\n"
            f"目標資料夾路徑：\n{target_dir}\n\n"
            "此操作將永久銷毀該角色的所有立繪切片、透明度材質與部位錨點！\n是否確認要繼續進行？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if res != QMessageBox.Yes:
            return

        res2 = QMessageBox.critical(
            self,
            "最終強制確認 (第 2 步 / 共 2 步)",
            f"請再次確認：確定要立即且不可復接地永久刪除「{cid}」嗎？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if res2 == QMessageBox.Yes:
            try:
                if target_dir.exists():
                    shutil.rmtree(target_dir)
                anchor_file = get_character_anchor_path(cid)
                if anchor_file.exists():
                    anchor_file.unlink(missing_ok=True)
                QMessageBox.information(self, "刪除完成", f"自訂角色「{cid}」已安全徹底清理完畢。")
                self._populate_characters()
            except Exception as exc:
                QMessageBox.critical(self, "刪除失敗", f"執行清理自訂角色檔案時發生異常：{exc}")
