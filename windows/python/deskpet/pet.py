"""The main pet: sprite rendering (1024 square / 1536 tail), mirroring on snap-right,
tablet balance / peak-valley page, hurt flash / shake, feeding, iron bowl, and petting.
"""
from __future__ import annotations

import math
import time
from datetime import datetime, timezone, timedelta

from PySide6.QtCore import (QEasingCurve, QPoint, QPointF, QPropertyAnimation, QRectF, Qt, QTimer,
                            Signal)
from PySide6.QtGui import (QColor, QFont, QFontMetrics, QGuiApplication, QImage, QPainter,
                           QPainterPath, QPen, QPixmap, QPolygonF, QTransform)
from PySide6.QtWidgets import QWidget

from . import winapi
from .config import APP_DIR, ASSETS, CUSTOM_CHARS_DIR, PROV_NAMES, PROV_IDS, asset, log
from .props import Art, PropManager
from .input_manager import InputDispatcher
from .mood_engine import MoodEngine
from .floating_hud import FloatingMoodHUD
from .anchor_editor import load_character_anchors

M_L, M_R, M_T, M_B = 48, 48, 130, 28

QUAD_1024 = [(549.6 + 5.1, 706.2), (949.7 - 13.3, 642.0), (984.7 - 13.3, 860.2), (584.6 + 5.1, 924.3)]
QUAD_1536 = [(1060.0, 699.0), (1413.0, 644.0), (1443.0, 834.0), (1090.0, 889.0)]
QUAD_GEMINI_1024 = [(554.7, 708.2), (936.4, 644.0), (971.4, 862.2), (589.7, 926.3)]
QUAD_GEMINI_1536 = [(1065.0, 699.0), (1400.0, 646.0), (1430.0, 836.0), (1095.0, 889.0)]

SCREEN_W, SCREEN_H = 480, 264

HEART = [
    "0110110",
    "1111111",
    "1111111",
    "0111110",
    "0011100",
    "0001000",
]

STEP_GAP = 0.2
FLASH_DECAY = 0.28
SHAKE_DUR = 0.55
HOLD_NERVOUS = 1.0
HAPPY_AFTER_FEED = 2.0
IRON_TILT = -6.23
WAIT_TSUN = 10.0

PAT_PALM_X = (0.712, 0.749, 0.711, 0.818, 0.691)
PAT_PALM_Y = (0.305, 0.514, 0.629, 0.538, 0.402)
PETPET_W = (0.80, 0.82, 0.84, 0.86, 0.88)
PETPET_H = (0.80, 0.75, 0.70, 0.65, 0.60)
PETPET_OFFSET_Y = (0.12, 0.17, 0.22, 0.27, 0.32)
PETPET_BASE_OFFSET_Y = 0.12


def _quad_transform(w, h, dst_pts) -> QTransform:
    src = QPolygonF([QPointF(0, 0), QPointF(w, 0), QPointF(w, h), QPointF(0, h)])
    dst = QPolygonF([QPointF(x, y) for x, y in dst_pts])
    res = QTransform.quadToQuad(src, dst)
    if isinstance(res, tuple):
        res = res[-1] if isinstance(res[-1], QTransform) else res[0]
    return res


def is_peak_at(bj: datetime) -> bool:
    """DeepSeek peak hours: weekdays 09:00-12:00 and 14:00-18:00 (Beijing time)."""
    if bj.weekday() in (5, 6):  # Saturday, Sunday
        return False
    h = bj.hour + bj.minute / 60.0
    return (9.0 <= h < 12.0) or (14.0 <= h < 18.0)


def until_tariff_switch(bj: datetime) -> tuple[timedelta, bool]:
    now_peak = is_peak_at(bj)
    d = bj.replace(hour=0, minute=0, second=0, microsecond=0)
    for day in range(9):
        for q in range(1, 96):
            c = d + timedelta(days=day, minutes=q * 15)
            if c <= bj:
                continue
            if is_peak_at(c) != now_peak:
                return (c - bj), not now_peak
    return timedelta(0), not now_peak


class PetWindow(QWidget):
    context_requested = Signal(QPoint)
    hurt = Signal()
    moved_by_user = Signal()
    double_clicked_head = Signal()

    def __init__(self, cfg, ledger, sounds, character_override: str | None = None, is_extra: bool = False, pet_id: str | None = None):
        super().__init__(None, Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint
                         | Qt.NoDropShadowWindowHint)
        self.cfg = cfg
        self.ledger = ledger
        self.sounds = sounds
        self.is_extra = is_extra
        self.pet_id = pet_id or (character_override if character_override else "main")
        self._bubble = None

        if self.cfg.get("disable_transparency", False):
            self.setAttribute(Qt.WA_TranslucentBackground, False)
            self.setWindowOpacity(1.0)
        else:
            self.setAttribute(Qt.WA_TranslucentBackground, True)
            self.sync_opacity()

        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setMouseTracking(True)
        self.setWindowTitle("Desktop Pet")

        self.size_px = int(cfg.get("size", 454))
        self.character = character_override if character_override else cfg.get("character", "deepseek")
        self.variant = cfg.get("variant", "square")
        self.snap_right = (cfg.get("snap_corner") == "right")

        self.props = PropManager(self, sounds, cfg)
        self._src: dict[str, QImage] = {}
        self._scaled: dict[tuple, tuple] = {}
        self._bbox = None
        self._screen_img: QImage | None = None
        self._screen_tf: QTransform | None = None
        self._iron_pix: QPixmap | None = None
        self._hands: dict[int, QPixmap] = {}
        self._heart_pix: QPixmap | None = None

        # Animation state
        self.expr = "happy"
        self.flashes: list[float] = []
        self.floaters: list[list] = []
        self.hearts: list[list] = []
        self.cue_queue = 0
        self.nervous_until = 0.0
        self.happy_until = 0.0
        self.iron_count = 0
        self.iron_alpha = 1.0
        self.iron_fading = False
        self.bounce_t = 0.0
        self.pat_active = False
        self.pat_phase = 0.0
        self.pat_cooldown = 0.0
        self._wig_start = 0.0
        self._wig_dist = 0.0
        self._wig_last = 0.0
        self._wig_pos: QPointF | None = None
        self.page = 0  # 0: balance, 1: peak/valley or vendor spend
        self._press_pos: QPoint | None = None
        self._drag_off: QPoint | None = None
        self._anim: QPropertyAnimation | None = None
        self._last_tick = time.monotonic()

        # 2D 剪紙風格動態物理狀態
        self.paper_flip_t = 0.0
        self.paper_flip_active = False
        self.paper_scale_x = 1.0
        self.target_snap_right = self.snap_right
        self.flutter_angle = 0.0
        self.paper_land_t = 0.0
        self.is_dragging = False
        self.drag_prev_x = 0

        # 平板亮屏呼吸閃爍狀態 (鬧鐘)
        self.alarm_glowing = False
        self.alarm_glow_t = 0.0
        self.alarm_glow_name = ""

        self.timer = QTimer(self)
        self.timer.setInterval(16)
        self.timer.setTimerType(Qt.PreciseTimer)
        self.timer.timeout.connect(self._tick)

        self.cue_timer = QTimer(self)
        self.cue_timer.setInterval(int(STEP_GAP * 1000))
        self.cue_timer.timeout.connect(self._cue_tick)

        self.clock_timer = QTimer(self)
        self.clock_timer.setInterval(1000)
        self.clock_timer.timeout.connect(self._build_screen)

        ledger.cues.connect(self.enqueue_cues)
        ledger.topup.connect(self.on_topup)
        ledger.changed.connect(self._build_screen)

        # 視覺部位錨點載入
        self.anchors = load_character_anchors(self.character)

        # 模組一：用戶自訂操作與按鍵綁定系統 (InputDispatcher)
        self.input_dispatcher = InputDispatcher(self.cfg, self)
        self._init_input_actions()

        # 模組四：全維度行為因子心情值系統與自訂統計 HUD
        self.mood_engine = MoodEngine(self.cfg, self, sounds)
        self.floating_hud = FloatingMoodHUD(self.cfg, self.mood_engine)
        if bool(self.cfg.get("floating_hud_enabled", False)):
            self.floating_hud.show()

        self._last_pot_pulse = time.monotonic()

        # 模組五：鐵鍋動態滑落與天降空鍋週期定時器 (每 45 秒檢查一次)
        self.sky_pot_timer = QTimer(self)
        self.sky_pot_timer.setInterval(45000)
        self.sky_pot_timer.timeout.connect(self._on_sky_pot_timer)
        self.sky_pot_timer.start()

        self._resize_window()
        self._build_screen()
        self.update_fps_timer()

    def _init_input_actions(self):
        disp = self.input_dispatcher
        disp.register_action("switch_tablet_page", self.next_tablet_page)
        disp.register_action("pet_head", self.start_pat)
        disp.register_action("remove_iron_pot", lambda: self.remove_iron(all_pots=False))
        disp.register_action("remove_all_iron_pots", lambda: self.remove_iron(all_pots=True))
        disp.register_action("feed_pet", self.quick_feed)
        disp.register_action("summon_chibi", self.summon_chibi_patrol)
        disp.register_action("quick_hide", self.toggle_quick_hide)
        disp.register_action("open_panel", self.request_open_panel)
        disp.update_hotkeys()

    def quick_feed(self):
        """快捷餵食：直接生成飯盆並飄落。"""
        self.props.spawn_rice(1.0)

    def summon_chibi_patrol(self):
        """召喚 Q 版小人巡邏隊。"""
        mgr = getattr(self, "chibi_mgr", None) or (getattr(self, "app", None) and getattr(self.app, "chibi_mgr", None))
        if mgr:
            mgr.summon()

    def toggle_quick_hide(self):
        """老闆鍵：快速隱藏/顯示主寵與小人。"""
        mgr = getattr(self, "chibi_mgr", None) or (getattr(self, "app", None) and getattr(self.app, "chibi_mgr", None))
        if self.isVisible():
            self.hide()
            if mgr:
                for c in mgr.chibis:
                    c.hide()
        else:
            self.show()
            if mgr:
                for c in mgr.chibis:
                    c.show()

    def request_open_panel(self):
        """請求開啟設定面板。"""
        if getattr(self, "app", None) and hasattr(self.app, "open_panel"):
            self.app.open_panel()
        else:
            self.context_requested.emit(self.mapToGlobal(QPoint(self.width() // 2, self.height() // 2)))

    def _on_sky_pot_timer(self):
        """天降空鍋與自然滑落週期檢查。"""
        import random
        # 1. 戴鍋自然微幅滑落
        if bool(self.cfg.get("natural_pot_slip_enabled", True)) and self.iron_count > 1:
            if random.random() < 0.25:
                self.props.trigger_natural_slip()

        # 2. 天降空鐵鍋隨機掉落
        if bool(self.cfg.get("sky_pot_drop_enabled", True)) and random.random() < 0.15:
            self.props.spawn_sky_pot()

    def update_fps_timer(self):
        """根據 target_fps 與 performance_mode 動態調度定時器幀率。"""
        perf = bool(self.cfg.get("performance_mode", False))
        fps = int(self.cfg.get("target_fps", 60))
        if perf:
            effective_fps = min(30, fps) if fps > 0 else 30
        else:
            effective_fps = fps
        if effective_fps <= 0:
            interval = 1
        else:
            interval = max(1, int(1000 / effective_fps))
        self.timer.setInterval(interval)

    def sync_opacity(self, val: int | float | None = None):
        """同步大寵物透明度 (20..100)。"""
        if self.cfg.get("disable_transparency", False):
            self.setWindowOpacity(1.0)
            return
        if val is None:
            val = self.cfg.get("pet_opacity", self.cfg.get("opacity", 100))
        op = max(0.2, min(1.0, float(val) / 100.0))
        self.setWindowOpacity(op)

    def set_opacity(self, val: int | float, save: bool = True):
        """設定大寵物透明度並即時更新視窗。"""
        v = max(20, min(100, int(val)))
        self.cfg.set("pet_opacity", v, save=False)
        self.cfg.set("opacity", v, save=save)
        self.sync_opacity(v)

    def set_disable_transparency(self, on: bool):
        """動態切換停用半透明背景：使用純色背景緩衝，透明度鎖定 1.0。"""
        self.setAttribute(Qt.WA_TranslucentBackground, not on)
        self.sync_opacity()
        self.update()

    # ====================================================== Character & Art loading
    @property
    def iron_worn(self) -> bool:
        return self.iron_count > 0

    @iron_worn.setter
    def iron_worn(self, val: bool):
        if val:
            if self.iron_count == 0:
                self.iron_count = 1
        else:
            self.iron_count = 0

    @property
    def is_tail(self) -> bool:
        return self.variant == "tail"

    @property
    def aspect_ratio(self) -> float:
        mode = self.cfg.get("custom_pet_crop_mode", "fit")
        strict = self.cfg.get("strict_custom_image_ratio", True)
        if self.character.startswith("custom_") and (mode == "free" or not strict):
            src = self._load("happy")
            if not src.isNull() and src.height() > 0:
                return src.width() / float(src.height())
        return 1.5 if self.is_tail else 1.0

    @property
    def art_w(self) -> int:
        return max(10, int(self.size_px * self.aspect_ratio))

    @property
    def art_h(self) -> int:
        return max(10, self.size_px)

    def set_strict_custom_image_ratio(self, val: bool):
        self.cfg.set("strict_custom_image_ratio", bool(val))
        if bool(val) and self.cfg.get("custom_pet_crop_mode") == "free":
            self.cfg.set("custom_pet_crop_mode", "fit")
        elif not bool(val):
            self.cfg.set("custom_pet_crop_mode", "free")
        self._clear_cache()
        self._resize_window()
        self.keep_on_screen()
        self.update()

    def set_custom_pet_crop_mode(self, mode: str):
        """切換自訂立繪裁切模式：crop(裁切填滿)、fit(等比縮放)、free(自由比例)。"""
        if mode in ("crop", "fit", "free"):
            self.cfg.set("custom_pet_crop_mode", mode)
            self.cfg.set("strict_custom_image_ratio", (mode != "free"))
            self._clear_cache()
            self._resize_window()
            self.keep_on_screen()
            self.update()

    def set_character(self, char_id: str):
        if self.character == char_id:
            return
        self.character = char_id
        self.cfg.set("character", char_id)
        self._clear_cache()
        self._resize_window()
        self.update()

    def set_variant(self, variant: str):
        if variant not in ("square", "tail"):
            return
        if self.variant == variant:
            return
        self.variant = variant
        self.cfg.set("variant", variant)
        self._clear_cache()
        self._resize_window()
        self.keep_on_screen()
        self.update()

    def _clear_cache(self):
        self._src.clear()
        self._scaled.clear()
        self._bbox = None
        self._iron_pix = None
        self._hands.clear()
        self._heart_pix = None

    def _char_image_path(self, expr: str) -> str:
        # Check custom character first
        if self.character.startswith("custom_"):
            d = CUSTOM_CHARS_DIR / self.character
            if not d.exists():
                d = APP_DIR / "chars" / self.character
            # Check expression in sprites/
            exp_file = d / "sprites" / f"{expr}.png"
            if exp_file.exists():
                return str(exp_file)
            main_file = d / "sprite.png"
            if main_file.exists():
                return str(main_file)

        # Built-in characters: deepseek, claude, gemini, gpt
        cid = self.character if self.character in ("deepseek", "claude", "gemini", "gpt") else "deepseek"
        chars_dir = ASSETS / "chars" / cid

        if self.is_tail:
            # 1536x1024 wide art
            if cid == "deepseek":
                if expr == "nervous" and (chars_dir / "tail_nervous.png").exists():
                    return str(chars_dir / "tail_nervous.png")
                if expr == "cold" and (chars_dir / "tail_cold.png").exists():
                    return str(chars_dir / "tail_cold.png")
                if expr == "tsun" and (chars_dir / "tail_tsun.png").exists():
                    return str(chars_dir / "tail_tsun.png")
            tail_file = chars_dir / "tail.png"
            if tail_file.exists():
                return str(tail_file)

        # 1024x1024 square art
        expr_map = {"happy": "expression_11", "tsun": "expression_12", "cold": "expression_21", "nervous": "expression_22"}
        e_name = expr_map.get(expr, "expression_11")
        if cid == "deepseek":
            return str(ASSETS / "expr" / f"{e_name}.png")
        else:
            e_path = chars_dir / "sprites" / f"{e_name}.png"
            if e_path.exists():
                return str(e_path)
            s_path = chars_dir / "sprite.png"
            if s_path.exists():
                return str(s_path)
        return str(ASSETS / "expr" / "expression_11.png")

    def _load(self, expr: str) -> QImage:
        key = f"{self.character}_{self.variant}_{expr}"
        if key not in self._src:
            path = self._char_image_path(expr)
            self._src[key] = QImage(path)
        return self._src[key]

    def _sprite(self, expr: str):
        crop_mode = self.cfg.get("custom_pet_crop_mode", "fit")
        key = (self.character, self.variant, expr, self.size_px, self.snap_right, crop_mode)
        if key not in self._scaled:
            src = self._load(expr)
            if src.isNull() or src.width() <= 0 or src.height() <= 0:
                src = self._load("happy")

            target_w = self.art_w
            target_h = self.art_h

            if self.character.startswith("custom_") and not src.isNull() and src.width() > 0 and src.height() > 0:
                strict = self.cfg.get("strict_custom_image_ratio", True)
                mode = "free" if not strict else crop_mode

                if mode == "free":
                    img = src.scaled(target_w, target_h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation).convertToFormat(
                        QImage.Format_ARGB32_Premultiplied
                    )
                elif mode == "crop":
                    # 裁切填滿：維持長寬比填滿方框，超出部分置中裁切
                    canvas = QImage(target_w, target_h, QImage.Format_ARGB32_Premultiplied)
                    canvas.fill(Qt.transparent)
                    sc = max(target_w / float(src.width()), target_h / float(src.height()))
                    sw = max(1, int(round(src.width() * sc)))
                    sh = max(1, int(round(src.height() * sc)))
                    sc_img = src.scaled(sw, sh, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
                    qp = QPainter(canvas)
                    qp.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
                    qp.drawImage((target_w - sw) // 2, (target_h - sh) // 2, sc_img)
                    qp.end()
                    img = canvas
                else:  # "fit" (預設)
                    # 等比縮放：維持長寬比容納於方框內，水平居中、垂直靠下貼地
                    canvas = QImage(target_w, target_h, QImage.Format_ARGB32_Premultiplied)
                    canvas.fill(Qt.transparent)
                    sc = min(target_w / float(src.width()), target_h / float(src.height()))
                    sw = max(1, int(round(src.width() * sc)))
                    sh = max(1, int(round(src.height() * sc)))
                    sc_img = src.scaled(sw, sh, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
                    qp = QPainter(canvas)
                    qp.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
                    qp.drawImage((target_w - sw) // 2, target_h - sh, sc_img)
                    qp.end()
                    img = canvas
            else:
                img = src.scaled(target_w, target_h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation).convertToFormat(
                    QImage.Format_ARGB32_Premultiplied
                )

            if self.snap_right:
                img = img.mirrored(True, False)
            red = QImage(img)
            qp = QPainter(red)
            qp.setCompositionMode(QPainter.CompositionMode_SourceIn)
            qp.fillRect(red.rect(), QColor(255, 20, 20))
            qp.end()
            if len(self._scaled) > 20:
                self._scaled.clear()
            self._scaled[key] = (QPixmap.fromImage(img), img, QPixmap.fromImage(red))
        return self._scaled[key]

    def _tablet_corners_source(self) -> list[tuple[float, float]]:
        # Read custom tablet quad if available
        if self.character.startswith("custom_"):
            d = CUSTOM_CHARS_DIR / self.character
            t_file = d / "tablet.txt"
            if t_file.exists():
                try:
                    nums = [float(x.strip()) for x in t_file.read_text().split(",") if x.strip()]
                    if len(nums) == 8:
                        return [(nums[0], nums[1]), (nums[2], nums[3]), (nums[4], nums[5]), (nums[6], nums[7])]
                except Exception:
                    pass

        cid = self.character if self.character in ("deepseek", "claude", "gemini", "gpt") else "deepseek"
        if self.is_tail:
            return QUAD_GEMINI_1536 if cid == "gemini" else QUAD_1536
        return QUAD_GEMINI_1024 if cid == "gemini" else QUAD_1024

    def _update_tablet_transform(self):
        corners = self._tablet_corners_source()
        src_w = 1536.0 if self.is_tail else 1024.0
        src_h = 1024.0
        if self.character.startswith("custom_") and not self.cfg.get("strict_custom_image_ratio", True):
            src = self._load("happy")
            if not src.isNull() and src.height() > 0 and src.width() > 0:
                src_w = float(src.width())
                src_h = float(src.height())
        scale_x = self.art_w / src_w
        scale_y = self.art_h / src_h

        # 4 corners in unmirrored local coordinates
        pts = [(x * scale_x, y * scale_y) for x, y in corners]
        if self.snap_right:
            # When mirrored across X:
            # Original TL (0) moves to art_w - x, which is the RIGHT side of the mirrored tablet.
            # Original TR (1) moves to art_w - x, which is the LEFT side of the mirrored tablet.
            # To keep text readable and upright:
            # Text TL -> Mirrored TR (1)
            # Text TR -> Mirrored TL (0)
            # Text BR -> Mirrored BL (3)
            # Text BL -> Mirrored BR (2)
            tl = (self.art_w - pts[1][0], pts[1][1])
            tr = (self.art_w - pts[0][0], pts[0][1])
            br = (self.art_w - pts[3][0], pts[3][1])
            bl = (self.art_w - pts[2][0], pts[2][1])
            dst_pts = [tl, tr, br, bl]
        else:
            dst_pts = pts

        # 天花板倒掛模式逆向旋轉 180 度補償（維持文字水平正立便於閱讀）
        if bool(self.cfg.get("ceiling_hang_enabled", False)) and bool(self.cfg.get("tablet_auto_upright", True)):
            dst_pts = [dst_pts[2], dst_pts[3], dst_pts[0], dst_pts[1]]

        self._screen_tf = _quad_transform(SCREEN_W, SCREEN_H, dst_pts)

    def _resize_window(self):
        w = self.art_w
        h = self.art_h
        self.setFixedSize(w + M_L + M_R, h + M_T + M_B)
        self._update_tablet_transform()
        self._iron_pix = None
        self._hands.clear()
        self._heart_pix = None

    def set_size(self, px: int):
        px = max(180, min(1024, int(px)))
        if px == self.size_px:
            return
        old_bc = QPoint(self.x() + M_L + self.art_w // 2, self.y() + M_T + self.art_h)
        self.size_px = px
        self.cfg.set("size", px)
        self._clear_cache()
        self._resize_window()
        self.move(old_bc.x() - M_L - self.art_w // 2, old_bc.y() - M_T - self.art_h)
        self.keep_on_screen()
        self.update()

    # ====================================================== Geometry & Mirroring
    def set_snap_right(self, right: bool):
        if self.snap_right == right and self.cfg.get("snap_corner") == ("right" if right else "left"):
            return
        # Paper Flip 2D 動態：120ms 內平滑執行 1.0 -> 0.05 -> -1.0 翻轉
        if self.snap_right != right:
            self.paper_flip_active = True
            self.paper_flip_t = 0.0
            self.paper_scale_x = 1.0
            self.target_snap_right = right
            self.wake()
        self.snap_right = right
        self.cfg.set("snap_corner", "right" if right else "left", save=True)
        self._update_tablet_transform()
        self.update()

    def sprite_origin(self) -> QPointF:
        return QPointF(self.x() + M_L, self.y() + M_T)

    def body_center_global(self) -> QPointF:
        o = self.sprite_origin()
        # In tail mode character body sits on right side (0.66) unless mirrored
        bx = (0.34 if self.snap_right else 0.66) if self.is_tail else 0.50
        return QPointF(o.x() + self.art_w * bx, o.y() + self.art_h * 0.58)

    def head_zone_global(self) -> QRectF:
        o = self.sprite_origin()
        W = self.art_w
        H = self.art_h
        if self.character.startswith("custom_"):
            hz = getattr(self, "anchors", {}).get("head_zone", {})
            base_cx = hz.get("center_ratio_x", 0.672 if self.is_tail else 0.60)
            top_ry = hz.get("top_ratio_y", -0.14)
            w_ry = hz.get("width_ratio", 0.56)
            h_ry = hz.get("height_ratio", 0.54)
        else:
            base_cx = 0.672 if self.is_tail else 0.60
            top_ry = -0.14
            w_ry = 0.56
            h_ry = 0.54

        cx = o.x() + (W * (1.0 - base_cx) if self.snap_right else W * base_cx)
        w = H * w_ry
        x = cx - w / 2.0
        y = o.y() + H * top_ry
        h = H * h_ry
        if self.iron_count > 0:
            stack_extra = (self.iron_count - 1) * (H * 0.12)
            y -= (H * 0.10 + stack_extra)
            h += (H * 0.12 + stack_extra)
            w += H * 0.08
            x = cx - w / 2.0

        # 天花板倒掛模式：180 度反轉幾何對齊（倒懸時頭部位於寵物下方）
        if bool(self.cfg.get("ceiling_hang_enabled", False)):
            cy = y + h / 2.0
            new_cx = 2.0 * (o.x() + W / 2.0) - cx
            new_cy = 2.0 * (o.y() + H / 2.0) - cy
            return QRectF(new_cx - w / 2.0, new_cy - h / 2.0, w, h)

        return QRectF(x, y, w, h)

    def tablet_zone_global(self) -> QRectF:
        o = self.sprite_origin()
        W = self.art_w
        H = self.art_h
        tx = (W * 0.15) if self.snap_right else (W * 0.50 if self.is_tail else W * 0.45)
        ty = H * 0.60
        tw = W * 0.40
        th = H * 0.35

        # 天花板倒掛模式幾何適配
        if bool(self.cfg.get("ceiling_hang_enabled", False)):
            cx = o.x() + tx + tw / 2.0
            cy = o.y() + ty + th / 2.0
            new_cx = 2.0 * (o.x() + W / 2.0) - cx
            new_cy = 2.0 * (o.y() + H / 2.0) - cy
            return QRectF(new_cx - tw / 2.0, new_cy - th / 2.0, tw, th)

        return QRectF(o.x() + tx, o.y() + ty, tw, th)

    def contains_global(self, g: QPointF) -> bool:
        o = self.sprite_origin()
        lx, ly = g.x() - o.x(), g.y() - o.y()
        if not (-16 <= lx < self.art_w + 16 and -16 <= ly < self.art_h + 16):
            return False
        img = self._sprite(self.expr)[1]
        for dx, dy in ((0, 0), (14, 0), (-14, 0), (0, 14), (0, -14)):
            x, y = int(lx + dx), int(ly + dy)
            if 0 <= x < self.art_w and 0 <= y < self.art_h and (img.pixel(x, y) >> 24) > 20:
                return True
        return False

    def _hit_local(self, pos: QPoint) -> bool:
        x, y = pos.x() - M_L, pos.y() - M_T
        if not (0 <= x < self.art_w and 0 <= y < self.art_h):
            return False
        return (self._sprite(self.expr)[1].pixel(x, y) >> 24) > 20

    def bbox_frac(self):
        if self._bbox is None:
            img = self._load("happy").scaled(128, 128, Qt.IgnoreAspectRatio, Qt.FastTransformation)
            x0 = y0 = 128
            x1 = y1 = -1
            for y in range(128):
                for x in range(128):
                    if img.pixelColor(x, y).alpha() > 20:
                        x0, x1 = min(x0, x), max(x1, x)
                        y0, y1 = min(y0, y), max(y1, y)
            self._bbox = (x0 / 128.0, y0 / 128.0, (x1 + 1) / 128.0, (y1 + 1) / 128.0)
        return self._bbox

    # ====================================================== Window placement
    def showEvent(self, e):
        super().showEvent(e)
        hwnd = int(self.winId())
        winapi.hide_from_taskbar(hwnd)
        self.apply_window_prefs()
        if hasattr(self, "props") and self.props:
            self.props.show_all()

    def hideEvent(self, e):
        super().hideEvent(e)
        if hasattr(self, "props") and self.props:
            self.props.hide_all()

    def apply_window_prefs(self):
        hwnd = int(self.winId())
        self.sync_opacity()
        winapi.set_topmost(hwnd, bool(self.cfg.get("always_on_top", True)))
        self.apply_click_through(bool(self.cfg.get("click_through", False)))

    def apply_click_through(self, on: bool):
        winapi.set_click_through(int(self.winId()), on)
        self.props.set_click_through(on)

    def screen_ag(self):
        s = QGuiApplication.screenAt(self.frameGeometry().center()) or QGuiApplication.primaryScreen()
        return s.availableGeometry()

    def keep_on_screen(self):
        ag = self.screen_ag()
        L = self.x() + M_L
        R = self.x() + M_L + self.art_w
        T = self.y() + M_T
        B = self.y() + M_T + self.art_h
        dx = dy = 0
        if L < ag.left():
            dx = ag.left() - L
        elif R > ag.right() + 1:
            dx = ag.right() + 1 - R
        if B > ag.bottom() + 1:
            dy = ag.bottom() + 1 - B
        elif T < ag.top():
            dy = ag.top() - T
        if dx or dy:
            self.move(int(self.x() + dx), int(self.y() + dy))

    def _animate_to(self, target: QPoint, ms=160):
        if self._anim:
            self._anim.stop()
        self._anim = QPropertyAnimation(self, b"pos", self)
        self._anim.setDuration(ms)
        self._anim.setStartValue(self.pos())
        self._anim.setEndValue(target)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.finished.connect(self._save_pos)
        self._anim.start()

    def show_speech_bubble(self, text: str, thought: bool = False, timeout_ms: int = 6500, persistent: bool = False, on_click=None):
        if self._bubble is None:
            from .chat import SpeechBubble
            self._bubble = SpeechBubble(self)
        if on_click is not None:
            self._bubble.set_click_callback(on_click)
        else:
            self._bubble.set_click_callback(None)
        self._bubble.show_message(text, thought=thought, timeout_ms=timeout_ms, persistent=persistent)

    def hide_speech_bubble(self):
        if self._bubble is not None:
            self._bubble.hide()
            self._bubble.set_click_callback(None)

    def _save_pos(self):
        if self.is_extra and self.pet_id:
            extra_pos = self.cfg.get("extra_pet_positions") or {}
            extra_pos[self.pet_id] = [self.x(), self.y()]
            self.cfg.set("extra_pet_positions", extra_pos, save=True)
        else:
            self.cfg.set("pos", [self.x(), self.y()], save=False)
            self.cfg.set("snap_corner", "right" if self.snap_right else "left", save=True)

    def snap_target(self, force_corner: bool = False) -> QPoint | None:
        ag = self.screen_ag()
        L = self.x() + M_L
        R = self.x() + M_L + self.art_w
        T = self.y() + M_T
        B = self.y() + M_T + self.art_h
        nx, ny = self.x(), self.y()

        # 天花板倒掛模式：停靠螢幕上方邊界 (左上或右上角)
        if bool(self.cfg.get("ceiling_hang_enabled", False)):
            corner = self.cfg.get("ceiling_hang_corner", "top_right")
            if corner == "top_left":
                nx += (ag.left() - L)
                self.set_snap_right(False)
            else:
                nx += (ag.right() + 1 - R)
                self.set_snap_right(True)
            ny += (ag.top() - T)
            return QPoint(int(nx), int(ny))

        if force_corner:
            corner = self.cfg.get("snap_corner", "right")
            nx += (ag.left() - L) if corner == "left" else (ag.right() + 1 - R)
            ny += ag.bottom() + 1 - B
            self.set_snap_right(corner == "right")
            return QPoint(int(nx), int(ny))

        th = int(self.cfg.get("snap_distance", 120))
        cand_x = [(abs(L - ag.left()), ag.left() - L, False), (abs(ag.right() + 1 - R), ag.right() + 1 - R, True)]
        cand_y = [(abs(T - ag.top()), ag.top() - T), (abs(ag.bottom() + 1 - B), ag.bottom() + 1 - B)]

        dx = min(cand_x)
        dy = min(cand_y)
        moved = False
        if dx[0] <= th:
            nx += dx[1]
            moved = True
            self.set_snap_right(dx[2])
        if dy[0] <= th:
            ny += dy[1]
            moved = True
        return QPoint(int(nx), int(ny)) if moved else None

    def snap_now(self, force_corner=False):
        t = self.snap_target(force_corner)
        if t is not None and t != self.pos():
            self._animate_to(t)
        else:
            self._save_pos()

    def place_initial(self, default_offset_x: int = 0):
        if self.is_extra and self.pet_id:
            extra_pos = (self.cfg.get("extra_pet_positions") or {}).get(self.pet_id)
            if extra_pos and isinstance(extra_pos, list) and len(extra_pos) == 2:
                self.move(int(extra_pos[0]), int(extra_pos[1]))
                self.keep_on_screen()
                ag = self.screen_ag()
                center_x = self.x() + M_L + self.art_w / 2.0
                is_right = center_x > (ag.left() + ag.width() / 2.0)
                self.set_snap_right(is_right)
                return
        pos = self.cfg.get("pos") if not self.is_extra else None
        ag = self.screen_ag()
        if pos and isinstance(pos, list) and len(pos) == 2:
            self.move(int(pos[0]), int(pos[1]))
            self.keep_on_screen()
            # Auto-align direction based on which side of the screen the pet sits
            center_x = self.x() + M_L + self.art_w / 2.0
            is_right = center_x > (ag.left() + ag.width() / 2.0)
            self.set_snap_right(is_right)
        else:
            # Default to bottom-right corner
            corner = self.cfg.get("snap_corner", "right")
            self.set_snap_right(corner == "right")
            L = M_L
            R = M_L + self.art_w
            B = M_T + self.art_h
            nx = (ag.right() + 1 - R) if corner == "right" else (ag.left() - L)
            if self.is_extra and default_offset_x != 0:
                nx = max(ag.left(), min(ag.right() - R, nx + default_offset_x))
            ny = ag.bottom() + 1 - B
            self.move(int(nx), int(ny))
            self.keep_on_screen()
            self._save_pos()

    # ====================================================== Tablet Screen Rendering
    def is_deepseek_active(self) -> bool:
        ch = (self.character or "").lower()
        if ch in ("claude", "gpt", "gemini") or "claude" in ch or "gpt" in ch or "gemini" in ch:
            return False
        if "deepseek" in ch:
            return True
        prov = (self.ledger.provider or "").lower()
        active_prof_prov = ""
        try:
            profs = self.cfg.get("api_profiles", [])
            act = int(self.cfg.get("active_profile", 0))
            if 0 <= act < len(profs):
                active_prof_prov = str(profs[act].get("provider", "")).lower()
        except Exception:
            pass
        return ("deepseek" in prov) or ("deepseek" in active_prof_prov)

    def next_tablet_page(self):
        """分頁輪替：第 1 頁（峰谷頁）僅限 DeepSeek，第 4 頁（心情頁）僅限啟用心情系統。"""
        deepseek_ok = self.is_deepseek_active()
        mood_ok = bool(self.cfg.get("mood_system_enabled", False))
        valid_pages = [0]
        if deepseek_ok:
            valid_pages.append(1)
        valid_pages.extend([2, 3])
        if mood_ok:
            valid_pages.append(4)
        try:
            cur_idx = valid_pages.index(self.page)
            self.page = valid_pages[(cur_idx + 1) % len(valid_pages)]
        except ValueError:
            self.page = 0
        self._build_screen()

    def trigger_alarm_glow(self, alarm_name: str = ""):
        self.alarm_glowing = True
        self.alarm_glow_name = alarm_name
        self.alarm_glow_t = 0.0
        if not self.clock_timer.isActive():
            self.clock_timer.start()
        self._build_screen()
        self.wake()

    def stop_alarm_glow(self):
        self.alarm_glowing = False
        self.alarm_glow_name = ""
        self._build_screen()
        self.update()

    def _build_screen(self):
        img = QImage(SCREEN_W, SCREEN_H, QImage.Format_ARGB32_Premultiplied)
        img.fill(Qt.transparent)
        p = QPainter(img)
        p.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)

        # 若當前為第 1 頁但非 DeepSeek，自動跳至第 2 頁
        if self.page == 1 and not self.is_deepseek_active():
            self.page = 2

        if self.page == 0:
            # 第 0 頁：寵物餘額（通用）
            prov = (self.ledger.provider or "").lower()
            ch = (self.character or "").lower()
            if "deepseek" in prov or "deepseek" in ch:
                title = "DeepSeek 餘額"
            elif "claude" in prov or "anthropic" in prov or "claude" in ch:
                title = "Claude 餘額"
            elif "gemini" in prov or "gemini" in ch:
                title = "Gemini 餘額"
            elif "openai" in prov or "gpt" in prov or "gpt" in ch:
                title = "OpenAI 餘額"
            elif "openrouter" in prov:
                title = "OpenRouter 餘額"
            elif "siliconflow" in prov or "矽基" in prov:
                title = "矽基流動 餘額"
            elif "moonshot" in prov or "kimi" in prov:
                title = "Moonshot 餘額"
            elif "groq" in prov:
                title = "Groq 額度"
            elif "mistral" in prov:
                title = "Mistral 額度"
            elif "grok" in prov or "xai" in prov:
                title = "xAI/Grok 額度"
            elif "together" in prov:
                title = "Together 額度"
            elif "cerebras" in prov:
                title = "Cerebras 額度"
            elif "deepinfra" in prov:
                title = "DeepInfra 額度"
            elif "fireworks" in prov:
                title = "Fireworks 額度"
            elif "glm" in prov or "zhipu" in prov:
                title = "智譜 GLM 額度"
            elif "ollama" in prov:
                title = "Ollama 狀態"
            elif "lmstudio" in prov or "lm studio" in prov:
                title = "LM Studio 狀態"
            elif "vllm" in prov:
                title = "vLLM 狀態"
            elif "custom" in prov or "oneapi" in prov or "relay" in prov:
                title = "自訂 API 餘額"
            else:
                pname = getattr(self.ledger, "provider_display_name", self.character.capitalize())
                title = f"{pname} 餘額"
            body = self.ledger.text
            self._outlined(p, title, QRectF(0, 12, SCREEN_W, 70), 34, bold=False)

            if " (約 " in body:
                line1, line2 = body.split(" (約 ", 1)
                line2 = "(約 " + line2
                self._outlined(p, line1, QRectF(0, 72, SCREEN_W, 85), 62, bold=True)
                self._outlined(p, line2, QRectF(0, 162, SCREEN_W, 64), 30, bold=False, fill_color=QColor(230, 240, 255))
            else:
                size = 110
                f = QFont("Segoe UI", 1, QFont.Bold)
                while size > 26:
                    f.setPixelSize(size)
                    if QFontMetrics(f).horizontalAdvance(body) <= SCREEN_W * 0.86:
                        break
                    size -= 4
                self._outlined(p, body, QRectF(0, 78, SCREEN_W, 160), size, bold=True)

            if not self.ledger.online:
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(255, 60, 60))
                p.drawEllipse(QPointF(SCREEN_W - 26, 26), 9, 9)

        elif self.page == 1:
            # 第 1 頁：梁 / 峰谷時段（僅限 DeepSeek 顯示）
            bj = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))
            time_str = bj.strftime("%H:%M:%S")
            is_off = not is_peak_at(bj)
            tariff_name = "梁文谷" if is_off else "梁文峰"
            left, to_peak = until_tariff_switch(bj)
            cd_label = "距峰時" if to_peak else "距谷時"
            cd_str = f"{cd_label} {int(left.total_seconds()//3600)}:{int((left.total_seconds()%3600)//60):02d}:{int(left.total_seconds()%60):02d}"

            self._outlined(p, time_str, QRectF(0, 10, SCREEN_W, 60), 36, bold=False)
            ink_color = QColor(150, 226, 170) if is_off else QColor(240, 190, 120)
            self._outlined(p, tariff_name, QRectF(0, 80, SCREEN_W, 90), 54, bold=True, fill_color=ink_color)
            self._outlined(p, cd_str, QRectF(0, 180, SCREEN_W, 60), 32, bold=False)

        elif self.page == 2:
            # 第 2 頁：鬧鐘與倒數（即將響鈴時間、倒數計時器或暫無鬧鐘）
            alarms = [a for a in self.cfg.get("alarms", []) if a.get("enabled", True)]
            self._outlined(p, "鬧鐘與倒數", QRectF(0, 12, SCREEN_W, 60), 34, bold=False)
            if alarms:
                first = alarms[0]
                a_name = first.get("name", "提醒")
                if first.get("type") == "timer":
                    target_ts = float(first.get("target_ts", 0.0))
                    rem = max(0, int(target_ts - time.time()))
                    body_str = f"{rem // 60:02d}:{rem % 60:02d}"
                    sub_str = f"倒數：{a_name}"
                else:
                    body_str = first.get("time", "08:00")
                    sub_str = f"定時：{a_name}"
                self._outlined(p, body_str, QRectF(0, 76, SCREEN_W, 90), 52, bold=True, fill_color=QColor(255, 215, 120))
                self._outlined(p, sub_str, QRectF(0, 178, SCREEN_W, 60), 30, bold=False)
            else:
                self._outlined(p, "暫無即將響鈴", QRectF(0, 84, SCREEN_W, 80), 40, bold=True, fill_color=QColor(180, 200, 230))
                self._outlined(p, "於設定面板新增鬧鐘", QRectF(0, 178, SCREEN_W, 60), 28, bold=False)

        elif self.page == 3:
            # 第 3 頁：最新事件通知與狀態（通知紀錄、Webhook 狀態）
            notes = self.cfg.get("notifications", [])
            self._outlined(p, "最新事件與狀態", QRectF(0, 12, SCREEN_W, 60), 32, bold=False)
            if notes:
                last_note = notes[0]
                n_msg = last_note.get("title", "事件通知")
                n_time = last_note.get("timestamp", "")[-8:]
                self._outlined(p, n_msg, QRectF(0, 76, SCREEN_W, 80), 36, bold=True, fill_color=QColor(140, 230, 255))
                hook_status = "Webhook 已連動" if (self.cfg.get("discord_webhook_url") or self.cfg.get("telegram_bot_token")) else "本機通知已就緒"
                self._outlined(p, f"[{n_time}] {hook_status}", QRectF(0, 178, SCREEN_W, 60), 26, bold=False)
            else:
                self._outlined(p, "系統運行正常", QRectF(0, 80, SCREEN_W, 80), 42, bold=True, fill_color=QColor(150, 240, 180))
                hook_status = "Webhook 待命" if (self.cfg.get("discord_webhook_url") or self.cfg.get("telegram_bot_token")) else "通知分發器待命"
                self._outlined(p, hook_status, QRectF(0, 178, SCREEN_W, 60), 28, bold=False)

        elif self.page == 4:
            # 第 4 頁：心情指數與寵物互動統計（僅在 mood_system_enabled 時啟用）
            if not bool(self.cfg.get("mood_system_enabled", False)):
                self.page = 0
                return self._build_screen()

            m_val = float(self.cfg.get("mood_value", 50.0))
            m_max = float(self.cfg.get("mood_max_limit", 100.0))
            stats = self.cfg.get("pet_stats", {})
            total_pats = stats.get("total_pats", 0)
            total_feeds = stats.get("total_feeds", 0)
            combo = stats.get("feed_combo_count", 0)

            if m_val >= 80.0:
                mood_txt = "心情：雀躍興奮"
                m_color = QColor(100, 230, 160)
            elif m_val >= 50.0:
                mood_txt = "心情：愉快放鬆"
                m_color = QColor(120, 210, 255)
            elif m_val >= 30.0:
                mood_txt = "心情：平靜發呆"
                m_color = QColor(240, 210, 120)
            else:
                mood_txt = "心情：有些低落"
                m_color = QColor(255, 120, 120)

            self._outlined(p, "心情與統計", QRectF(0, 12, SCREEN_W, 60), 32, bold=False)
            self._outlined(p, f"{m_val:.1f} / {m_max:.0f}", QRectF(0, 68, SCREEN_W, 75), 52, bold=True, fill_color=m_color)
            sub_info = f"{mood_txt} (連擊 {combo})"
            self._outlined(p, sub_info, QRectF(0, 142, SCREEN_W, 50), 26, bold=False)
            stat_info = f"撫摸 {total_pats} 次 | 餵食 {total_feeds} 次"
            self._outlined(p, stat_info, QRectF(0, 186, SCREEN_W, 50), 24, bold=False, fill_color=QColor(200, 220, 255))

        # 鬧鐘響鈴動態：平板亮屏呼吸閃爍外框
        if self.alarm_glowing:
            alpha = int(180 + 75 * math.sin(time.monotonic() * 9.0))
            p.setPen(QPen(QColor(255, 60, 90, alpha), 8))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(QRectF(4, 4, SCREEN_W - 8, SCREEN_H - 8), 16, 16)

        p.end()
        self._screen_img = img
        self.update()

        if (self.page in (1, 2, 3, 4) or self.alarm_glowing) and not self.clock_timer.isActive():
            self.clock_timer.start()
        elif self.page == 0 and not self.alarm_glowing:
            self.clock_timer.stop()

    @staticmethod
    def _outlined(p: QPainter, text: str, rect: QRectF, px: int, bold: bool, fill_color: QColor | None = None):
        f = QFont("Segoe UI", 1)
        f.setPixelSize(px)
        f.setBold(bold)
        path = QPainterPath()
        fm = QFontMetrics(f)
        w = fm.horizontalAdvance(text)
        path.addText(rect.center().x() - w / 2, rect.center().y() + fm.ascent() / 2 - fm.descent() / 2, f, text)
        p.setPen(QPen(QColor(10, 14, 28), max(3, px // 12), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)
        p.setPen(Qt.NoPen)
        p.setBrush(fill_color or QColor(226, 238, 255))
        p.drawPath(path)

    # ====================================================== Expressions
    def rice_waiting(self) -> bool:
        now = time.monotonic()
        return any(b.locked_at is not None or (b.landed_at is not None and now - b.landed_at >= WAIT_TSUN)
                   for b in self.props.rice())

    def _want_expr(self) -> str:
        now = time.monotonic()
        rice_alive = bool(self.props.rice())
        if self.iron_worn and not rice_alive and now >= self.happy_until:
            return "cold"
        if now < self.nervous_until or self.pat_active:
            return "nervous"
        if self.rice_waiting():
            return "tsun"
        return "happy"

    def refresh_expr(self):
        if not bool(self.cfg.get("pet_expression_enabled", True)):
            if self.expr != "happy":
                self.expr = "happy"
                self.update()
            return
        e = self._want_expr()
        if e != self.expr:
            self.expr = e
            self.update()

    def on_bowl_state_changed(self):
        self.refresh_expr()

    # ====================================================== Painting
    def paintEvent(self, _):
        now = time.monotonic()
        W = self.art_w
        H = self.art_h
        pix, _img, red = self._sprite(self.expr)
        p = QPainter(self)
        p.setRenderHints(QPainter.SmoothPixmapTransform | QPainter.Antialiasing | QPainter.TextAntialiasing)

        # 低配效能優化：停用半透明時使用純色背景緩衝
        if self.cfg.get("disable_transparency", False):
            p.fillRect(self.rect(), QColor("#1e1e24"))

        anims_on = self.cfg.get("animations_enabled", True)

        # Shake: damped sine
        dx = dy = 0.0
        flash = 0.0
        if anims_on:
            for t0 in self.flashes[-3:]:
                a = now - t0
                if a < SHAKE_DUR:
                    env = (1 - a / SHAKE_DUR) ** 2
                    dx += 8.0 * math.sin(a * 2 * math.pi * 13) * env
                    dy += 3.0 * math.sin(a * 2 * math.pi * 17 + 1) * env
                flash += math.exp(-a / FLASH_DECAY)
            dx = max(-14.0, min(14.0, dx))
            dy = max(-6.0, min(6.0, dy))

        # 無重力懸浮飄動模式（zero_gravity_mode）：在未拖曳時產生微幅垂直漂移
        if bool(self.cfg.get("zero_gravity_mode", False)) and not self.is_dragging:
            dy += 5.0 * math.sin(now * 2.0)

        max_tint = max(0.30, 0.64 - (H / 1024.0) * 0.75)
        flash = min(1.0, flash) * max_tint

        # Body squash and downward shift
        sq_x = 1.0
        sq_y = 1.0
        shift_y = 0.0
        if anims_on:
            if self.pat_active:
                frame = int(self.pat_phase * 5) % 5
                w_rel = PETPET_W[frame] / PETPET_W[0]
                h_rel = PETPET_H[frame] / PETPET_H[0]
                sq_x = float(1.0 - (1.0 - w_rel))
                sq_y = float(1.0 - (1.0 - h_rel))
                shift_y = float((PETPET_OFFSET_Y[frame] - PETPET_BASE_OFFSET_Y) * H)
            if self.bounce_t > 0:
                sq_y -= 0.07 * math.sin(math.pi * (1 - self.bounce_t / 0.35))

        # 2D 剪紙風格動態物理：著陸回彈 (scaleY 0.88 -> 1.0)
        paper_squish_y = 1.0
        if self.paper_land_t > 0:
            progress = 1.0 - (self.paper_land_t / 0.20)
            paper_squish_y = 0.88 + 0.12 * math.sin(progress * math.pi / 2)

        is_ceiling = bool(self.cfg.get("ceiling_hang_enabled", False))
        ox, oy = M_L + dx, M_T + dy
        p.save()
        if is_ceiling:
            # 天花板倒掛模式：純粹幾何 180 度反轉渲染 (絕無任何動物腳爪繪製)
            p.translate(ox + W / 2, oy + H / 2)
            p.rotate(180)
            p.translate(-(ox + W / 2), -(oy + H / 2))

        p.translate(ox + W / 2, oy + H + shift_y)
        # 紙片懸空飄蕩微幅傾角 (±5 度)
        if self.flutter_angle != 0.0:
            p.rotate(self.flutter_angle)
        # 繪圖矩陣 transform 應用紙片翻轉與壓扁回彈
        p.scale(self.paper_scale_x * sq_x, paper_squish_y * sq_y)
        p.translate(-(ox + W / 2), -(oy + H))
        p.drawPixmap(int(ox), int(oy), pix)

        # Tablet quad transform mapping
        if self._screen_img is not None and self._screen_tf is not None:
            p.save()
            p.translate(ox, oy)
            p.setTransform(self._screen_tf, True)
            p.drawImage(0, 0, self._screen_img)
            p.restore()

        if flash > 0.01:
            p.setOpacity(flash)
            p.drawPixmap(int(ox), int(oy), red)
            p.setOpacity(1.0)

        if self.iron_worn:
            self._paint_iron(p, ox, oy)
        p.restore()

        if self.pat_active:
            self._paint_hand(p, ox, oy, now)
        self._paint_fx(p, ox, oy, now)

    def _iron(self) -> QPixmap:
        if self._iron_pix is None:
            src = Art.get("iron_bowl.png")
            w = int(self.size_px * 0.50)
            self._iron_pix = QPixmap.fromImage(src.scaledToWidth(w, Qt.SmoothTransformation))
        return self._iron_pix

    def _paint_iron(self, p: QPainter, ox, oy):
        if self.iron_count <= 0:
            return
        pm = self._iron()
        W = self.art_w
        H = self.art_h

        if self.character.startswith("custom_"):
            ib = getattr(self, "anchors", {}).get("iron_bowl", {})
            base_cx_ratio = ib.get("center_ratio_x", 0.672 if self.is_tail else 0.60)
            base_cy_ratio = ib.get("center_ratio_y", 0.19)
            anchor_tilt = ib.get("tilt_deg", IRON_TILT)
            base_tilt = -anchor_tilt if self.snap_right else anchor_tilt
        else:
            base_cx_ratio = 0.672 if self.is_tail else 0.60
            base_cy_ratio = 0.19
            base_tilt = -IRON_TILT if self.snap_right else IRON_TILT

        cx = ox + (W * (1.0 - base_cx_ratio) if self.snap_right else W * base_cx_ratio)
        base_cy = oy + H * base_cy_ratio

        # 疊鍋阻尼擺動物理 (Damped oscillation wobble)
        now = time.monotonic()
        wobble_dt = now - getattr(self, "_pot_wobble_time", 0.0)
        wobble_amp = 0.0
        if wobble_dt < 2.0:
            decay = math.exp(-wobble_dt * 2.5)
            wobble_amp = 7.5 * decay * math.sin(wobble_dt * 14.0)

        for idx in range(self.iron_count):
            p.save()
            p.setOpacity(max(0.0, self.iron_alpha))
            cy = base_cy + idx * (-H * 0.12)
            pot_tilt = base_tilt + ((idx + 1) / max(1, self.iron_count)) * wobble_amp
            p.translate(cx, cy)
            p.rotate(pot_tilt)
            p.drawPixmap(int(-pm.width() / 2), int(-pm.height() * 0.5), pm)
            p.restore()

    def _hand(self, i: int) -> QPixmap:
        if i not in self._hands:
            img = QImage(asset("hands", f"pat_hand_{i}.png"))
            k = self.art_h / 454.0
            dw = max(1, int(round(img.width() * k)))
            dh = max(1, int(round(img.height() * k)))
            scaled = img.scaled(dw, dh, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            self._hands[i] = QPixmap.fromImage(scaled)
        return self._hands[i]

    def _paint_hand(self, p: QPainter, ox, oy, now):
        W = self.art_w
        H = self.art_h
        k = H / 454.0
        frame = int(self.pat_phase * 5) % 5
        pm = self._hand(frame)
        dw = pm.width()
        dh = pm.height()

        head_x = int(W * 0.672) if self.is_tail else int(W * 0.50 + H * 0.17)
        crown_y = int(round(40.0 * (446.0 / 107.0) * k))

        palm_fx = PAT_PALM_X[frame]
        palm_fy = PAT_PALM_Y[frame]

        hand_x = int(round(head_x - palm_fx * dw))
        if self.snap_right:
            hand_x = (W - 1) - (hand_x + dw)
        hand_y = int(round(crown_y - palm_fy * dh))

        if self.snap_right:
            p.save()
            cx = ox + hand_x + dw / 2.0
            p.translate(cx, 0.0)
            p.scale(-1.0, 1.0)
            p.translate(-cx, 0.0)
            p.drawPixmap(int(ox + hand_x), int(oy + hand_y), pm)
            p.restore()
        else:
            p.drawPixmap(int(ox + hand_x), int(oy + hand_y), pm)

    def _heart(self) -> QPixmap:
        if self._heart_pix is None:
            u = max(2, int(self.size_px / 90))
            img = QImage(7 * u, 6 * u, QImage.Format_ARGB32_Premultiplied)
            img.fill(Qt.transparent)
            q = QPainter(img)
            for r, row in enumerate(HEART):
                for c, ch in enumerate(row):
                    if ch == "1":
                        q.fillRect(c * u, r * u, u, u, QColor(255, 80, 120))
            q.end()
            self._heart_pix = QPixmap.fromImage(img)
        return self._heart_pix

    def _paint_fx(self, p: QPainter, ox, oy, now):
        if not bool(self.cfg.get("pet_particles_enabled", True)):
            return
        if self.cfg.get("performance_mode", False) or not self.cfg.get("animations_enabled", True):
            # 在效能模式或停用動效時，關閉愛心粒子與飄字上升動效
            return

        W = self.art_w
        H = self.art_h
        k = H / 454.0
        f = QFont("Segoe UI", 1, QFont.Bold)
        f.setPixelSize(max(14, int(24 * k)))
        p.setFont(f)

        base_x = (0.35 if self.is_tail else 0.40)
        floater_x = W * (1.0 - base_x - 0.5) if self.snap_right else W * base_x

        for item in self.floaters:
            text, color, xo, t0 = item[0], item[1], item[2], item[3]
            a = now - t0
            life = 1.2
            if a < 0 or a > life:
                continue
            progress = min(1.0, a / life)
            y_rise = (1.0 - (1.0 - progress) ** 2) * 85.0 * max(0.7, k)
            y = oy + H * 0.12 - y_rise
            alpha = max(0.0, 1.0 - progress ** 1.8)
            p.setOpacity(alpha)
            r = QRectF(ox + floater_x + xo, y, W * 0.6, 36)
            p.setPen(QColor(10, 12, 18, int(220 * alpha)))
            for ddx, ddy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                p.drawText(r.translated(ddx, ddy), Qt.AlignHCenter, text)
            p.setPen(color)
            p.drawText(r, Qt.AlignHCenter, text)
        p.setOpacity(1.0)

        hp = self._heart()
        for x, y, vx, vy, t0 in self.hearts:
            a = now - t0
            if a < 0 or a > 1.3:
                continue
            p.setOpacity(max(0.0, 1.0 - (a / 1.3) ** 2))
            p.drawPixmap(int(ox + x + vx * a), int(oy + y + vy * a), hp)
        p.setOpacity(1.0)

    # ====================================================== Animation Loop
    def wake(self):
        if not self.timer.isActive():
            self._last_tick = time.monotonic()
            self.timer.start()

    def _tick(self):
        now = time.monotonic()
        dt = min(0.05, now - self._last_tick)
        self._last_tick = now
        busy = False

        self.flashes = [t for t in self.flashes if now - t < max(SHAKE_DUR, 1.0)]
        busy |= bool(self.flashes)
        self.floaters = [f for f in self.floaters if now - f[3] < 1.1]
        busy |= bool(self.floaters)
        self.hearts = [h for h in self.hearts if now - h[4] < 1.3]
        busy |= bool(self.hearts)

        if self.bounce_t > 0:
            self.bounce_t = max(0.0, self.bounce_t - dt)
            busy = True

        # Paper Flip 2D 動態更新 (120ms)
        if self.paper_flip_active:
            self.paper_flip_t += dt / 0.120
            busy = True
            if self.paper_flip_t < 0.5:
                k = self.paper_flip_t / 0.5
                self.paper_scale_x = max(0.05, 1.0 - 0.95 * k)
            elif self.paper_flip_t < 1.0:
                k = (self.paper_flip_t - 0.5) / 0.5
                self.paper_scale_x = min(1.0, 0.05 + 0.95 * k)
            else:
                self.paper_flip_active = False
                self.paper_flip_t = 0.0
                self.paper_scale_x = 1.0

        # Paper Landing 著陸壓扁回彈更新
        if self.paper_land_t > 0:
            self.paper_land_t = max(0.0, self.paper_land_t - dt)
            busy = True

        # 平板亮屏呼吸動態更新
        if self.alarm_glowing:
            self.alarm_glow_t += dt
            busy = True

        if self.iron_fading:
            self.iron_alpha -= dt / 0.35
            busy = True
            if self.iron_alpha <= 0:
                self.iron_fading = False
                self.iron_count = 0
                self.iron_alpha = 1.0
                self.sounds.play("off")
                self.refresh_expr()

        if self.pat_active:
            self.pat_phase = (self.pat_phase + dt * 2.6) % 1.0
            busy = True
            if now - self._wig_last > 0.25:
                self.end_pat()

        if now < self.nervous_until:
            busy = True
        elif self.expr == "nervous" and not self.pat_active:
            self.refresh_expr()

        # 無重力懸浮飄動與鐵鍋 wobble 擺動持續動畫刷新
        if bool(self.cfg.get("zero_gravity_mode", False)) and not self.is_dragging:
            busy = True
        if self.iron_worn and (now - getattr(self, "_pot_wobble_time", 0.0) < 2.0):
            busy = True

        self.update()
        if not busy:
            self.timer.stop()
            self.refresh_expr()

    # ====================================================== Hurt / Topup / Feed
    def enqueue_cues(self, n: int):
        self.cue_queue += int(n)
        if not self.cue_timer.isActive():
            self._cue_tick()
            self.cue_timer.start()

    def _cue_tick(self):
        if self.cue_queue <= 0:
            self.cue_timer.stop()
            return
        batch = 1
        if self.cue_queue >= 10:
            batch = 10
        elif self.cue_queue >= 5:
            batch = 5
        self.cue_queue -= batch
        self.fire_hurt(count=batch)
        if self.cue_queue <= 0:
            self.cue_timer.stop()

    def fire_hurt(self, count: int = 1):
        now = time.monotonic()
        count = max(1, int(count))
        self.ledger.apply_cue(count=count)
        self.flashes.append(now)
        amount = round(count * 0.01, 2)
        if hasattr(self, "mood_engine") and self.mood_engine.is_enabled():
            self.mood_engine.on_api_cost(amount)
        cur_sym = "" if self.ledger.currency == "CNY" else "$"
        import random
        xo = random.uniform(-20.0, 20.0)
        self.floaters.append([f"-{cur_sym}{amount:.2f}", QColor(255, 60, 60), xo, now])
        self.nervous_until = now + HOLD_NERVOUS
        self.sounds.play("hit")
        self.hurt.emit()
        self.refresh_expr()
        self.wake()

    def on_topup(self, amount: float):
        if hasattr(self, "mood_engine") and self.mood_engine.is_enabled():
            self.mood_engine.on_topup(amount)
        self.props.spawn_rice(amount)
        self.refresh_expr()

    def feed(self, amount: float, at: QPointF):
        now = time.monotonic()
        self.ledger.apply_credit(amount)
        cur_sym = "" if self.ledger.currency == "CNY" else "$"
        self.floaters.append([f"+{cur_sym}{amount:.2f}", QColor(60, 220, 110), 0, now])
        W = self.art_w
        import random
        for _ in range(9):
            self.hearts.append([W * (0.35 + random.random() * 0.4), self.art_h * (0.02 + random.random() * 0.18),
                                (random.random() - 0.5) * 40, -40 - random.random() * 50,
                                now + random.random() * 0.25])
        self.sounds.play("feed")
        self.happy_until = now + HAPPY_AFTER_FEED
        self.bounce_t = 0.35
        self.props.spawn_iron(at.x(), at.y())
        if hasattr(self, "mood_engine") and self.mood_engine.is_enabled():
            self.mood_engine.on_feed(amount)
            self.mood_engine.record_stat("total_feeds", 1)
        QTimer.singleShot(int(HAPPY_AFTER_FEED * 1000) + 50, self.refresh_expr)
        self.refresh_expr()
        self.wake()

    def get_max_iron_pots(self) -> int:
        """動態計算頭頂空間可容納的最大鐵鍋層數 (1..10)。"""
        ag = self.screen_ag()
        hz = self.head_zone_global()
        if bool(self.cfg.get("ceiling_hang_enabled", False)):
            headroom = ag.bottom() - hz.bottom()
        else:
            headroom = hz.top() - ag.top()
        pot_step = max(10.0, self.art_h * 0.12)
        max_allowed = int(headroom / pot_step)
        return max(1, min(10, max_allowed if max_allowed >= 1 else 5))

    def wear_iron(self):
        chibi = getattr(self, "pixel_chibi", None) or (getattr(self, "app", None) and getattr(self.app, "pixel_chibi", None))
        if chibi and getattr(chibi, "climbing_pet", False) and getattr(chibi, "pet_mount_slot", None) == "head":
            direction = -1 if getattr(self, "snap_right", False) else 1
            chibi.trigger_bowl_smash(direction=direction)

        max_pots = self.get_max_iron_pots()
        if self.iron_count < max_pots:
            self.iron_count += 1
        self.iron_alpha = 1.0
        self.iron_fading = False
        self.bounce_t = 0.35
        self._pot_wobble_time = time.monotonic()
        self.sounds.play("land")
        now = time.monotonic()
        msg = f"鐵盆已戴在頭上 (層數: {self.iron_count}/{max_pots})" if self.iron_count > 1 else "點擊頭頂取下鐵盆"
        self.floaters.append([msg, QColor(255, 230, 110), 0, now])
        self.setToolTip("點擊頭頂取下鐵盆")

        if hasattr(self, "mood_engine") and self.mood_engine.is_enabled():
            self.mood_engine.record_stat("total_pots_worn", 1)
            cur_rec = int(self.cfg.get("pet_stats", {}).get("max_pots_record", 0))
            if self.iron_count > cur_rec:
                self.mood_engine.set_stat("max_pots_record", self.iron_count)

        self.refresh_expr()
        self.wake()

    def remove_iron(self, all_pots: bool = False):
        if self.iron_count <= 0:
            return
        self.bounce_t = 0.35
        self.sounds.play("off")
        now = time.monotonic()
        if all_pots or self.iron_count == 1:
            self.iron_count = 0
            self.floaters.append(["鐵盆已取下", QColor(140, 220, 255), 0, now])
            self.setToolTip("")
        else:
            self.iron_count -= 1
            self.floaters.append([f"取下頂層鐵盆（剩餘 {self.iron_count} 個）", QColor(140, 220, 255), 0, now])
            self.setToolTip("點擊頭頂取下鐵盆")
        self.refresh_expr()
        self.wake()

    # ====================================================== Petting Interaction
    def start_pat(self):
        if self.pat_active:
            return
        self.pat_active = True
        self.pat_phase = 0.0
        self.refresh_expr()
        self.wake()

    def end_pat(self):
        if not self.pat_active:
            return
        self.pat_active = False
        self.refresh_expr()
        self.update()

    def _track_pat(self, pos: QPointF):
        if not self.cfg.get("pat", True) or self._drag_off is not None:
            return
        now = time.monotonic()
        if self._wig_pos is None or now - self._wig_last > 0.35:
            self._wig_start, self._wig_dist = now, 0.0
        else:
            self._wig_dist += math.hypot(pos.x() - self._wig_pos.x(), pos.y() - self._wig_pos.y())
        self._wig_pos, self._wig_last = pos, now

        if self.pat_active:
            return

        # If user strokes over 24 px within 0.35s:
        if self._wig_dist > 24 and now - self._wig_start >= 0.35 and now >= self.pat_cooldown:
            # 鐵盆扣在頭上時，摸頭直接不觸發（依使用者明確要求，不可取下鐵盆再摸）
            if self.iron_worn:
                return
            duration = now - self._wig_start
            velocity = self._wig_dist / max(0.01, duration)
            if hasattr(self, "mood_engine") and self.mood_engine.is_enabled():
                self.mood_engine.on_pat(velocity, duration)
                self.mood_engine.record_stat("total_pats", 1)
            self.start_pat()

    # ====================================================== Mouse events
    def contextMenuEvent(self, e):
        g = QPointF(self.mapToGlobal(e.pos()))
        hit = self._hit_local(e.pos()) or self.head_zone_global().contains(g)
        if not hit:
            return
        self.end_pat()
        if hasattr(self, "input_dispatcher"):
            self.input_dispatcher.handle_body_right_click()
        else:
            self.context_requested.emit(self.mapToGlobal(e.pos()))
        e.accept()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            g = QPointF(self.mapToGlobal(e.position().toPoint()))
            hit = self._hit_local(e.position().toPoint()) or (self.iron_worn and self.head_zone_global().contains(g))
            if not hit:
                return
            self.end_pat()
            self.pat_cooldown = time.monotonic() + 1.0
            if self._anim:
                self._anim.stop()
            self._drag_off = e.globalPosition().toPoint() - self.pos()
            self._press_pos = e.globalPosition().toPoint()
            self.is_dragging = True
            self.drag_prev_x = self.x()

    def mouseMoveEvent(self, e):
        if self._drag_off is not None and e.buttons() & Qt.LeftButton:
            new_pos = e.globalPosition().toPoint() - self._drag_off
            vx = new_pos.x() - self.drag_prev_x
            self.drag_prev_x = new_pos.x()
            self.move(new_pos)
            # 紙片懸空飄蕩：滑鼠提起拖曳時帶有微幅慣性傾角（±5 度紙片飄動）
            target_tilt = max(-5.0, min(5.0, -vx * 0.8))
            self.flutter_angle = target_tilt
            self.wake()
            # Mid-drag turning: check if dragged near left vs right edge
            ag = self.screen_ag()
            mid_x = (new_pos.x() + M_L + self.art_w / 2)
            self.set_snap_right(mid_x > ag.center().x())
            return

        g = QPointF(self.mapToGlobal(e.position().toPoint()))
        if self.head_zone_global().contains(g):
            self._track_pat(e.position())
        else:
            if not self.pat_active:
                self._wig_pos = None
                self._wig_dist = 0.0

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and self._drag_off is not None:
            self._drag_off = None
            self.is_dragging = False
            self.flutter_angle = 0.0
            # 落地著陸瞬間產生輕微紙板壓扁回彈（scaleY 0.88 -> 1.0）
            self.paper_land_t = 0.20
            self.wake()
            moved = self._press_pos is not None and \
                (e.globalPosition().toPoint() - self._press_pos).manhattanLength() > 3
            self._press_pos = None
            if moved:
                self.moved_by_user.emit()
                if self.cfg.get("auto_snap", True):
                    self.snap_now()
                else:
                    self._save_pos()
            else:
                g = QPointF(self.mapToGlobal(e.position().toPoint()))
                if self.head_zone_global().contains(g):
                    if self.iron_worn:
                        self.remove_iron(all_pots=False)
                        return
                    if hasattr(self, "input_dispatcher"):
                        has_double = bool(self.input_dispatcher.find_action_by_trigger("head_double_click"))
                        self.input_dispatcher.handle_head_single_click(needs_debounce=has_double)
                    return

    def mouseDoubleClickEvent(self, e):
        if e.button() != Qt.LeftButton:
            return
        g = QPointF(self.mapToGlobal(e.position().toPoint()))
        if self.head_zone_global().contains(g):
            if self.iron_worn:
                self.remove_iron(all_pots=True)
                return
            if hasattr(self, "input_dispatcher"):
                self.input_dispatcher.handle_head_double_click()
            else:
                self.bounce_t = 0.35
                self.wake()
                self.double_clicked_head.emit()
            return

        if self.tablet_zone_global().contains(g):
            if hasattr(self, "input_dispatcher"):
                self.input_dispatcher.handle_tablet_double_click()
            else:
                self.next_tablet_page()

    def nativeEvent(self, eventType, message):
        """處理 Windows 全域廣播熱鍵 WM_HOTKEY 訊息。"""
        if eventType in (b"windows_generic_MSG", "windows_generic_MSG"):
            try:
                import ctypes.wintypes
                msg = ctypes.wintypes.MSG.from_address(int(message))
                if msg.message == 0x0312:  # WM_HOTKEY
                    if hasattr(self, "input_dispatcher") and self.input_dispatcher.process_hotkey_message(msg.wParam):
                        return True, 0
            except Exception:
                pass
        return super().nativeEvent(eventType, message)

    def leaveEvent(self, e):
        super().leaveEvent(e)
        self._wig_pos = None
        self._wig_dist = 0.0
