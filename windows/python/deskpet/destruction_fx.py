# -*- coding: utf-8 -*-
"""【大破壞！？】玩家即時互動破壞玩具箱（純視覺渲染，絕無任何破壞或資料遺失）

本模組提供 100% 安全純 UI 視覺渲染的漫畫風搞笑互動破壞模式：
1. 吱吱充氣大鐵錘 (Hammer)：在螢幕任意處敲擊砸出漫畫碎裂貼圖與震屏；砸中主寵壓扁成麻糬、砸中小人翻滾咕嚕嚕！
2. 放置卡通定時炸彈 (TNT Bomb)：點擊放置引線炸彈，可拖曳移動，倒數「砰～！」大爆炸，把小人炸上半空張開小氣球緩降！
3. 彈弓彈射 Q 版小人 (Chibi Launcher)：按住小人向後拉出彈弓虛線軌跡，高速彈射發射，撞牆撞地「Duang～」彈性反彈！
4. 一鍵修復海綿 (Repair Sponge / Exit)：點擊海綿按鈕或按下 Esc 鍵，播放擦玻璃清潔動畫，抹除全部裂痕，螢幕恢復原狀！
"""
from __future__ import annotations

import math
import random
import time
from typing import Any

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QGuiApplication,
    QIcon,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
    QPixmap,
)
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class ScreenDecal:
    """透明層上的漫畫貼圖痕跡（裂紋、焦印等）。"""

    def __init__(self, kind: str, x: float, y: float, scale: float = 1.0):
        self.kind = kind  # "crack", "scorch", "sparkle"
        self.x = x
        self.y = y
        self.scale = scale
        self.created_at = time.monotonic()
        self.alpha = 240
        self.rays: list[tuple[float, float, float, float]] = []

        if kind == "crack":
            # 隨機產生放射狀蜘蛛網裂紋線段
            num_rays = random.randint(6, 10)
            for i in range(num_rays):
                ang = (i * (360.0 / num_rays) + random.uniform(-15, 15)) * math.pi / 180.0
                dist1 = random.uniform(25, 45) * scale
                dist2 = random.uniform(50, 85) * scale
                rx1 = math.cos(ang) * dist1
                ry1 = math.sin(ang) * dist1
                rx2 = math.cos(ang + random.uniform(-0.2, 0.2)) * dist2
                ry2 = math.sin(ang + random.uniform(-0.2, 0.2)) * dist2
                self.rays.append((0.0, 0.0, rx1, ry1))
                self.rays.append((rx1, ry1, rx2, ry2))




class GlassShard:
    """被擊碎位移的螢幕截圖碎片多邊形。"""

    def __init__(self, polygon: QPolygonF, dx: float, dy: float, path: QPainterPath):
        self.polygon = polygon
        self.dx = dx
        self.dy = dy
        self.path = path


class GlassShatterImpact:
    """玻璃碎裂放射狀裂紋與位移碎片集。"""

    def __init__(self, cx: float, cy: float, radius: float = 120.0):
        self.cx = cx
        self.cy = cy
        self.radius = radius
        self.shards: list[GlassShard] = []
        self.crack_lines: list[tuple[float, float, float, float]] = []
        self.shockwave_radii = [radius * 0.35, radius * 0.7, radius * 1.05]
        self._generate_shards()

    def _generate_shards(self):
        num_sectors = random.randint(8, 12)
        angles = sorted([random.uniform(0, 2 * math.pi) for _ in range(num_sectors)])
        angles.append(angles[0] + 2 * math.pi)

        for i in range(num_sectors):
            a1 = angles[i]
            a2 = angles[i + 1]
            r1 = self.radius * random.uniform(0.75, 1.15)
            r2 = self.radius * random.uniform(0.75, 1.15)
            mid_a = (a1 + a2) / 2.0
            mid_r = self.radius * random.uniform(0.85, 1.2)

            p1 = QPointF(self.cx, self.cy)
            p2 = QPointF(self.cx + math.cos(a1) * r1, self.cy + math.sin(a1) * r1)
            p_mid = QPointF(self.cx + math.cos(mid_a) * mid_r, self.cy + math.sin(mid_a) * mid_r)
            p3 = QPointF(self.cx + math.cos(a2) * r2, self.cy + math.sin(a2) * r2)

            poly = QPolygonF([p1, p2, p_mid, p3])
            path = QPainterPath()
            path.addPolygon(poly)

            shift_dist = random.uniform(3.0, 7.0)
            dx = math.cos(mid_a) * shift_dist
            dy = math.sin(mid_a) * shift_dist

            self.shards.append(GlassShard(poly, dx, dy, path))
            self.crack_lines.append((p1.x(), p1.y(), p2.x(), p2.y()))
            self.crack_lines.append((p2.x(), p2.y(), p_mid.x(), p_mid.y()))
            self.crack_lines.append((p_mid.x(), p_mid.y(), p3.x(), p3.y()))

            if random.random() < 0.6:
                ext_r = r1 * random.uniform(1.2, 1.6)
                ext_a = a1 + random.uniform(-0.25, 0.25)
                p_ext = QPointF(self.cx + math.cos(ext_a) * ext_r, self.cy + math.sin(ext_a) * ext_r)
                self.crack_lines.append((p2.x(), p2.y(), p_ext.x(), p_ext.y()))

class InteractiveBomb:
    """玩家放置的互動引線定時炸彈。"""

    def __init__(self, x: float, y: float, fuse_time: float = 3.0):
        self.x = x
        self.y = y
        self.fuse_time = fuse_time
        self.start_time = time.monotonic()
        self.is_dragging = False
        self.exploded = False
        self.explosion_start = 0.0

    @property
    def remaining(self) -> float:
        return max(0.0, self.fuse_time - (time.monotonic() - self.start_time))

    def contains(self, px: float, py: float) -> bool:
        return (px - self.x) ** 2 + (py - self.y) ** 2 <= 30 ** 2


class SlingshotState:
    """彈弓彈射瞄準狀態。"""

    def __init__(self):
        self.active = False
        self.target_chibi = None
        self.start_x = 0.0
        self.start_y = 0.0
        self.cur_x = 0.0
        self.cur_y = 0.0


class DestructionToolbar(QWidget):
    """大破壞模式頂部精緻快捷工具列。"""

    tool_selected = Signal(str)
    exit_requested = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.SubWindow
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedSize(680, 56)
        self.active_tool = "hammer"

        self._build_ui()

    def _build_ui(self):
        root_lay = QHBoxLayout(self)
        root_lay.setContentsMargins(6, 4, 6, 4)

        panel = QWidget(self)
        panel.setStyleSheet("""
            QWidget {
                background-color: rgba(30, 41, 59, 235);
                border: 2px solid #38bdf8;
                border-radius: 20px;
            }
            QPushButton {
                background-color: #334155;
                color: #f8fafc;
                font-family: 'Microsoft JhengHei UI', sans-serif;
                font-size: 12px;
                font-weight: bold;
                border: 1px solid #475569;
                border-radius: 14px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #0284c7;
                border-color: #38bdf8;
            }
            QPushButton[active="true"] {
                background-color: #0284c7;
                border: 2px solid #38bdf8;
                color: #ffffff;
            }
        """)

        lay = QHBoxLayout(panel)
        lay.setContentsMargins(12, 4, 12, 4)
        lay.setSpacing(8)

        lbl = QLabel("【大破壞！？】", panel)
        lbl.setStyleSheet("color: #38bdf8; font-weight: 900; font-size: 13px; border: none; background: transparent;")
        lay.addWidget(lbl)

        lbl_note = QLabel("（純視覺效果，不會造成任何系統破壞或資料遺失）", panel)
        lbl_note.setStyleSheet("color: #94a3b8; font-size: 11px; border: none; background: transparent;")
        lay.addWidget(lbl_note)

        self.btn_hammer = QPushButton("充氣大鐵錘", panel)
        self.btn_hammer.clicked.connect(lambda: self.select_tool("hammer"))
        lay.addWidget(self.btn_hammer)

        self.btn_bomb = QPushButton("定時炸彈", panel)
        self.btn_bomb.clicked.connect(lambda: self.select_tool("bomb"))
        lay.addWidget(self.btn_bomb)

        self.btn_launcher = QPushButton("小人彈弓", panel)
        self.btn_launcher.clicked.connect(lambda: self.select_tool("launcher"))
        lay.addWidget(self.btn_launcher)

        self.btn_sponge = QPushButton("修復還原 (Esc)", panel)
        self.btn_sponge.setStyleSheet("QPushButton { background-color: #10b981; border-color: #34d399; } QPushButton:hover { background-color: #059669; }")
        self.btn_sponge.clicked.connect(self.exit_requested.emit)
        lay.addWidget(self.btn_sponge)

        root_lay.addWidget(panel)
        self.select_tool("hammer")

    def select_tool(self, name: str):
        self.active_tool = name
        self.btn_hammer.setProperty("active", "true" if name == "hammer" else "false")
        self.btn_bomb.setProperty("active", "true" if name == "bomb" else "false")
        self.btn_launcher.setProperty("active", "true" if name == "launcher" else "false")
        for b in (self.btn_hammer, self.btn_bomb, self.btn_launcher):
            b.style().unpolish(b)
            b.style().polish(b)
        self.tool_selected.emit(name)


class DestructionOverlay(QWidget):
    """【大破壞！？】趣味互動透明特效置頂畫布。"""

    def __init__(self, app_controller: Any = None, parent: QWidget | None = None):
        super().__init__(parent)
        self.app = app_controller
        self.is_interactive_mode = False
        self.current_tool = "hammer"  # hammer, bomb, launcher

        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.WindowTransparentForInput
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setMouseTracking(True)

        self.decals: list[ScreenDecal] = []
        self.bombs: list[InteractiveBomb] = []
        self.shatter_impacts: list[GlassShatterImpact] = []
        self.screen_pixmap: QPixmap | None = None
        self.slingshot = SlingshotState()

        # 滑鼠浮動游標位置
        self.cursor_pos = QPointF(-100, -100)
        self.hammer_angle = 0.0
        self.hammer_hitting = False

        # 螢幕微幅震動偏移
        self.shake_x = 0.0
        self.shake_y = 0.0
        self.shake_decay = 0.0

        # 海綿清理動畫
        self.cleaning_active = False
        self.cleaning_progress = 0.0

        # 動態更新計時器 (~60 FPS)
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._on_tick)

        # 頂部工具列
        self.toolbar = DestructionToolbar(None)
        self.toolbar.tool_selected.connect(self.set_tool)
        self.toolbar.exit_requested.connect(self.stop_interactive_mode)

        self._sync_geometry()

    def _sync_geometry(self):
        screen = QGuiApplication.primaryScreen()
        if screen:
            self.setGeometry(screen.geometry())
            # 工具列置於螢幕頂部居中
            tb_x = screen.geometry().center().x() - self.toolbar.width() // 2
            tb_y = screen.geometry().top() + 24
            self.toolbar.move(tb_x, tb_y)

    def set_tool(self, name: str):
        self.current_tool = name
        self.update()

    def start_interactive_mode(self):
        """開啟玩家可親自點擊操作的大破壞模式。"""
        self._sync_geometry()
        self.is_interactive_mode = True

        # 使用 QGuiApplication.primaryScreen().grabWindow(0) 擷取當前全螢幕即時畫面，作為全螢幕覆蓋層背景
        screen = QGuiApplication.primaryScreen()
        if screen:
            try:
                self.screen_pixmap = screen.grabWindow(0)
            except Exception:
                self.screen_pixmap = None

        # 啟用滑鼠互動（移除 WindowTransparentForInput）
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.show()
        self.toolbar.show()
        self.toolbar.raise_()
        self.raise_()
        self.setFocus()

        if not self._timer.isActive():
            self._timer.start()
        self.update()

    def stop_interactive_mode(self):
        """關閉互動模式，啟動修復海綿平滑清潔螢幕。"""
        self.cleaning_active = True
        self.cleaning_progress = 0.0
        try:
            if self.app and hasattr(self.app, "sounds") and self.app.sounds:
                self.app.sounds.play("hit")
        except Exception:
            pass

    def _finish_exit(self):
        """清潔完成後完全關閉視窗穿透。"""
        self.is_interactive_mode = False
        self.cleaning_active = False
        self.decals.clear()
        self.bombs.clear()
        self.shatter_impacts.clear()
        self.screen_pixmap = None
        self.slingshot.active = False
        self.toolbar.hide()

        # 恢復完全滑鼠穿透
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.WindowTransparentForInput
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self._timer.stop()
        self.hide()

    def clear_all_effects(self):
        """清除全部貼圖痕跡。"""
        self.decals.clear()
        self.bombs.clear()
        self.shatter_impacts.clear()
        self.slingshot.active = False
        self.update()

    # ========================================================= 滑鼠與鍵盤互動
    def keyPressEvent(self, e: QKeyEvent):
        if e.key() in (Qt.Key_Escape, Qt.Key_Q):
            self.stop_interactive_mode()
        else:
            super().keyPressEvent(e)

    def mouseMoveEvent(self, e: QMouseEvent):
        pos = e.position()
        self.cursor_pos = pos

        # 定時炸彈拖曳
        for bomb in self.bombs:
            if bomb.is_dragging:
                bomb.x = pos.x()
                bomb.y = pos.y()
                self.update()
                return

        # 彈弓瞄準拖曳
        if self.slingshot.active:
            self.slingshot.cur_x = pos.x()
            self.slingshot.cur_y = pos.y()
            self.update()
            return

        self.update()

    def mousePressEvent(self, e: QMouseEvent):
        if e.button() != Qt.LeftButton:
            if e.button() == Qt.RightButton:
                self.stop_interactive_mode()
            return

        pos = e.position()
        px, py = pos.x(), pos.y()

        # 工具 1：充氣大鐵錘
        if self.current_tool == "hammer":
            self._trigger_hammer_hit(px, py)

        # 工具 2：放置定時炸彈
        elif self.current_tool == "bomb":
            # 檢查是否點擊已有炸彈以拖曳
            for bomb in self.bombs:
                if bomb.contains(px, py) and not bomb.exploded:
                    bomb.is_dragging = True
                    return
            # 放置新炸彈
            self.bombs.append(InteractiveBomb(px, py, fuse_time=2.5))
            try:
                if self.app and hasattr(self.app, "sounds") and self.app.sounds:
                    self.app.sounds.play("hit")
            except Exception:
                pass

        # 工具 3：彈弓彈射 Q 版小人
        elif self.current_tool == "launcher":
            target = self._find_chibi_at(px, py)
            if target:
                self.slingshot.active = True
                self.slingshot.target_chibi = target
                self.slingshot.start_x = px
                self.slingshot.start_y = py
                self.slingshot.cur_x = px
                self.slingshot.cur_y = py

        self.update()

    def mouseReleaseEvent(self, e: QMouseEvent):
        if e.button() == Qt.LeftButton:
            # 停止拖曳炸彈
            for bomb in self.bombs:
                bomb.is_dragging = False

            # 釋放彈弓發射小人
            if self.slingshot.active:
                self._launch_slingshot()

        self.update()

    def _trigger_hammer_hit(self, px: float, py: float):
        """充氣大鐵錘敲擊命中檢測。"""
        self.hammer_hitting = True
        QTimer.singleShot(120, lambda: setattr(self, "hammer_hitting", False))

        # 螢幕震動
        self.shake_decay = 0.25
        self.shake_x = random.choice([-8.0, 8.0])
        self.shake_y = random.choice([-6.0, 6.0])

        # 1. 檢測是否命中主寵物
        hit_pet = False
        if self.app and hasattr(self.app, "pet") and self.app.pet:
            pet = self.app.pet
            p_geo = pet.geometry()
            if p_geo.contains(int(px), int(py)):
                hit_pet = True
                # 壓扁成麻糬動態 (0.8s)
                pet.land_squash_t = 0.8
                pet.paper_land_t = 0.4
                pet.bounce_t = 0.4
                pet.wake()
                try:
                    pet.update()
                except Exception:
                    pass

        # 2. 檢測是否命中 Q 版小人
        hit_chibi = False
        chibi = self._find_chibi_at(px, py)
        if chibi:
            hit_chibi = True
            # 小人像保齡球瓶一樣咕嚕嚕翻滾
            chibi.vel_x = 750.0 if px < chibi.pos_x + chibi.char_w / 2 else -750.0
            chibi.vel_y = -180.0
            chibi.state = "panic"
            chibi.paper_lean = 720.0
            chibi.wake()

        # 3. 於打擊位置對截圖產生玻璃碎裂放射狀裂紋與位移碎片
        scale = 1.4 if not (hit_pet or hit_chibi) else 0.8
        self.shatter_impacts.append(GlassShatterImpact(px, py, radius=random.uniform(90.0, 130.0) * scale))
        self.decals.append(ScreenDecal("crack", px, py, scale=scale))

        try:
            if self.app and hasattr(self.app, "sounds") and self.app.sounds:
                self.app.sounds.play("hit")
        except Exception:
            pass

    def _find_chibi_at(self, px: float, py: float) -> Any | None:
        if not self.app:
            return None
        # 搜尋所有在場小人
        chibis = []
        if hasattr(self.app, "pixel_chibi") and self.app.pixel_chibi:
            chibis.append(self.app.pixel_chibi)
        if hasattr(self.app, "chibi_manager") and self.app.chibi_manager:
            for c in getattr(self.app.chibi_manager, "active_chibis", []):
                if c not in chibis:
                    chibis.append(c)

        for c in chibis:
            rect = QRectF(c.pos_x - 10, c.pos_y - 10, c.char_w + 20, c.char_h + 20)
            if rect.contains(px, py):
                return c
        return None

    def _launch_slingshot(self):
        chibi = self.slingshot.target_chibi
        if chibi:
            dx = self.slingshot.start_x - self.slingshot.cur_x
            dy = self.slingshot.start_y - self.slingshot.cur_y
            # 發射速度放大
            chibi.vel_x = max(-1200.0, min(1200.0, dx * 7.5))
            chibi.vel_y = max(-1000.0, min(1000.0, dy * 7.5))
            chibi.state = "panic"
            chibi.paper_lean = 1080.0
            chibi.wake()
            try:
                if self.app and hasattr(self.app, "sounds") and self.app.sounds:
                    self.app.sounds.play("hit")
            except Exception:
                pass

        self.slingshot.active = False
        self.slingshot.target_chibi = None

    # ========================================================= 每一影格更新邏輯
    def _on_tick(self):
        now = time.monotonic()

        # 螢幕震動衰減
        if self.shake_decay > 0.0:
            self.shake_decay = max(0.0, self.shake_decay - 0.016)
            self.shake_x *= 0.8
            self.shake_y *= 0.8
        else:
            self.shake_x = 0.0
            self.shake_y = 0.0

        # 海綿清理進度
        if self.cleaning_active:
            self.cleaning_progress += 0.016 / 0.5  # 0.5s 清潔擦拭完成
            if self.cleaning_progress >= 1.0:
                self._finish_exit()
                return

        # 炸彈倒數與引爆
        for bomb in self.bombs:
            if not bomb.exploded and bomb.remaining <= 0.0:
                bomb.exploded = True
                bomb.explosion_start = now
                self._detonate_bomb(bomb)

        # 移除已引爆完成的炸彈 (爆炸維持 1.0s)
        self.bombs = [b for b in self.bombs if not b.exploded or (now - b.explosion_start < 1.0)]

        # 如果非互動模式且無貼圖炸彈，停止計時
        if not self.is_interactive_mode and not self.bombs and not self.cleaning_active:
            self._timer.stop()
            self.hide()

        self.update()

    def _detonate_bomb(self, bomb: InteractiveBomb):
        """定時炸彈引爆：焦痕、衝擊波與將周邊小人炸得飛上天開小氣球。"""
        self.shatter_impacts.append(GlassShatterImpact(bomb.x, bomb.y, radius=random.uniform(170.0, 230.0)))
        self.decals.append(ScreenDecal("scorch", bomb.x, bomb.y, scale=1.3))
        self.shake_decay = 0.35
        self.shake_x = random.choice([-14.0, 14.0])
        self.shake_y = random.choice([-10.0, 10.0])

        # 炸飛周邊 Q 版小人
        if self.app:
            chibis = []
            if hasattr(self.app, "pixel_chibi") and self.app.pixel_chibi:
                chibis.append(self.app.pixel_chibi)
            if hasattr(self.app, "chibi_manager") and self.app.chibi_manager:
                for c in getattr(self.app.chibi_manager, "active_chibis", []):
                    if c not in chibis:
                        chibis.append(c)

            for c in chibis:
                dist = math.hypot(c.pos_x - bomb.x, c.pos_y - bomb.y)
                if dist < 280.0:
                    c.pos_y -= 140.0
                    c.vel_y = -420.0
                    c.vel_x = (c.pos_x - bomb.x) * 3.5
                    c.state = "flight"
                    c.start_balloon_landing()
                    c.wake()

        try:
            if self.app and hasattr(self.app, "sounds") and self.app.sounds:
                self.app.sounds.play("hit")
        except Exception:
            pass

    # ========================================================= 繪製邏輯
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)

        # 螢幕震動位移
        if self.shake_decay > 0.0:
            p.translate(self.shake_x, self.shake_y)

        # 0. 繪製截圖與真實擊碎碎裂視覺效果（多邊形碎片位移錯開、露出裂痕邊緣暗色背景與放射裂紋）
        if self.screen_pixmap and not self.screen_pixmap.isNull():
            p.drawPixmap(0, 0, self.screen_pixmap)

            for impact in self.shatter_impacts:
                # 繪製碎片位移後露出的暗色縫隙與邊緣背景
                p.save()
                p.setBrush(QBrush(QColor(15, 23, 42, 220)))
                p.setPen(Qt.NoPen)
                for shard in impact.shards:
                    p.drawPolygon(shard.polygon)
                p.restore()

                # 繪製放射狀輕微位移錯開的截圖碎片
                for shard in impact.shards:
                    p.save()
                    p.translate(shard.dx, shard.dy)
                    p.setClipPath(shard.path)
                    p.drawPixmap(0, 0, self.screen_pixmap)
                    p.setPen(QPen(QColor(255, 255, 255, 140), 1.2))
                    p.drawPolygon(shard.polygon)
                    p.restore()

                # 繪製同心震波環、放射狀銳利裂紋與撞擊中心
                p.save()
                p.setPen(QPen(QColor(224, 242, 254, 90), 1.0, Qt.DashLine))
                p.setBrush(Qt.NoBrush)
                for r in impact.shockwave_radii:
                    p.drawEllipse(QPointF(impact.cx, impact.cy), r, r)

                p.setPen(QPen(QColor(255, 255, 255, 230), 2.0))
                for x1, y1, x2, y2 in impact.crack_lines:
                    p.drawLine(QPointF(x1, y1), QPointF(x2, y2))

                p.setBrush(QBrush(QColor(255, 255, 255, 240)))
                p.setPen(QPen(QColor(186, 230, 253, 180), 2.5))
                p.drawEllipse(QPointF(impact.cx, impact.cy), 6, 6)
                p.restore()

        # 1. 繪製所有玻璃碎裂與焦黑貼圖
        for decal in self.decals:
            self._draw_decal(p, decal)

        # 2. 繪製定時炸彈與引爆雲霧
        for bomb in self.bombs:
            self._draw_bomb(p, bomb)

        # 3. 繪製彈弓瞄準軌跡
        if self.slingshot.active:
            self._draw_slingshot(p)

        # 4. 繪製大鐵錘游標（僅互動模式下跟隨滑鼠）
        if self.is_interactive_mode and self.current_tool == "hammer":
            self._draw_hammer_cursor(p)

        # 5. 繪製海綿清理擦拭特效
        if self.cleaning_active:
            self._draw_cleaning_wipe(p)

    def _draw_decal(self, p: QPainter, decal: ScreenDecal):
        p.save()
        if decal.kind == "crack":
            p.setPen(QPen(QColor(51, 65, 85, decal.alpha), 2))
            for x1, y1, x2, y2 in decal.rays:
                p.drawLine(QPointF(decal.x + x1, decal.y + y1), QPointF(decal.x + x2, decal.y + y2))
            # 中心白色小撞擊點
            p.setBrush(QBrush(QColor(255, 255, 255, 180)))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(decal.x, decal.y), 4, 4)
        elif decal.kind == "scorch":
            p.setBrush(QBrush(QColor(30, 41, 59, 160)))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(decal.x, decal.y), 45 * decal.scale, 20 * decal.scale)
        p.restore()

    def _draw_bomb(self, p: QPainter, bomb: InteractiveBomb):
        p.save()
        now = time.monotonic()
        if not bomb.exploded:
            # 炸彈本體
            p.setBrush(QBrush(QColor("#1e293b")))
            p.setPen(QPen(QColor("#0f172a"), 3))
            p.drawEllipse(QPointF(bomb.x, bomb.y), 22, 22)

            # 引線與閃爍火花
            spark_pulse = math.sin((bomb.fuse_time - bomb.remaining) * 24.0)
            spark_col = QColor("#ef4444") if spark_pulse > 0 else QColor("#f59e0b")
            p.setBrush(QBrush(spark_col))
            p.drawEllipse(QPointF(bomb.x + 8, bomb.y - 25), 6, 6)

            # 倒數計時數字浮標
            p.setFont(QFont("Arial Black", 14, QFont.Bold))
            p.setPen(QPen(QColor("#ffffff")))
            p.drawText(QRectF(bomb.x - 30, bomb.y - 12, 60, 24), Qt.AlignCenter, f"{bomb.remaining:.1f}")
        else:
            # 引爆漫畫「砰～！」煙霧
            prog = min(1.0, (now - bomb.explosion_start) / 0.8)
            alpha = int(255 * (1.0 - prog))

            p.setBrush(QBrush(QColor(254, 240, 138, alpha)))
            p.setPen(QPen(QColor(15, 23, 42, alpha), 3))
            p.drawEllipse(QPointF(bomb.x, bomb.y), 40 + prog * 60, 40 + prog * 60)

            p.setFont(QFont("Microsoft JhengHei UI", 24, QFont.Black))
            p.setPen(QPen(QColor(239, 68, 68, alpha)))
            p.drawText(QRectF(bomb.x - 60, bomb.y - 40, 120, 50), Qt.AlignCenter, "砰～！")
        p.restore()

    def _draw_slingshot(self, p: QPainter):
        p.save()
        sx, sy = self.slingshot.start_x, self.slingshot.start_y
        cx, cy = self.slingshot.cur_x, self.slingshot.cur_y

        # 彈力橡皮筋虛線
        pen = QPen(QColor("#38bdf8"), 3, Qt.DashLine)
        p.setPen(pen)
        p.drawLine(QPointF(sx, sy), QPointF(cx, cy))

        # 瞄準力量光圈
        dist = math.hypot(sx - cx, sy - cy)
        power_ratio = min(1.0, dist / 200.0)
        p.setBrush(QBrush(QColor(239, 68, 68, int(180 * power_ratio))))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(cx, cy), 12 + power_ratio * 10, 12 + power_ratio * 10)
        p.restore()

    def _draw_hammer_cursor(self, p: QPainter):
        p.save()
        hx, hy = self.cursor_pos.x(), self.cursor_pos.y()
        p.translate(hx, hy)

        # 揮錘時向下旋轉
        angle = 35.0 if self.hammer_hitting else -15.0
        p.rotate(angle)

        # 握柄
        p.setPen(QPen(QColor("#d97706"), 6))
        p.drawLine(QPointF(0, 0), QPointF(0, -50))

        # 充氣雙色錘頭
        p.setPen(QPen(QColor("#0f172a"), 3))
        p.setBrush(QBrush(QColor("#ef4444")))
        p.drawRoundedRect(QRectF(-35, -95, 70, 48), 12, 12)

        # 黃色條紋
        p.setBrush(QBrush(QColor("#facc15")))
        p.drawRoundedRect(QRectF(-25, -85, 50, 28), 8, 8)
        p.restore()

    def _draw_cleaning_wipe(self, p: QPainter):
        """海綿清潔水幕掃過動畫。"""
        p.save()
        w = self.width()
        h = self.height()
        wipe_x = w * self.cleaning_progress

        p.setBrush(QBrush(QColor(56, 189, 248, 80)))
        p.setPen(Qt.NoPen)
        p.drawRect(QRectF(0, 0, wipe_x, h))

        # 海綿擦拭光線邊界
        p.setPen(QPen(QColor("#38bdf8"), 6))
        p.drawLine(QPointF(wipe_x, 0), QPointF(wipe_x, h))
        p.restore()

    # 相容舊版 API
    def trigger_cartoon_bomb(self, pos=None):
        self._sync_geometry()
        x = pos.x() if hasattr(pos, "x") else self.rect().center().x()
        y = pos.y() if hasattr(pos, "y") else self.rect().bottom() - 140
        self.bombs.append(InteractiveBomb(float(x), float(y), fuse_time=1.5))
        if not self.isVisible():
            self.show()
        if not self._timer.isActive():
            self._timer.start()
        self.update()

    def trigger_chibi_hammer(self, pos=None):
        self._sync_geometry()
        x = pos.x() if hasattr(pos, "x") else self.rect().center().x()
        y = pos.y() if hasattr(pos, "y") else self.rect().bottom() - 90
        self._trigger_hammer_hit(float(x), float(y))
        if not self.isVisible():
            self.show()
        if not self._timer.isActive():
            self._timer.start()
        self.update()

    def trigger_giant_hammer(self, pos=None):
        self._sync_geometry()
        x = pos.x() if hasattr(pos, "x") else self.rect().center().x()
        y = pos.y() if hasattr(pos, "y") else self.rect().center().y()
        self._trigger_hammer_hit(float(x), float(y))
        if not self.isVisible():
            self.show()
        if not self._timer.isActive():
            self._timer.start()
        self.update()

    def has_active_effects(self) -> bool:
        return bool(self.decals or self.bombs or self.is_interactive_mode)
