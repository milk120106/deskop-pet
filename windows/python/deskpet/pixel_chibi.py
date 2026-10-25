"""Brand-new standalone Q-Chibi pixel patrol system.
Features 4 heroine styles (DeepSeek whale, Claude spark, GPT tech, Gemini cat)
with full bodies, two cute legs/feet, pure-code 2D pixel matrices, nearest-neighbor
crisp rendering, window climbing with panic fall, main pet duang-bounce & climbing,
and bamboo copter / pixel fireworks props. Strictly zero emojis.
"""
from __future__ import annotations

import math
import random
import time
from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter, QPixmap
from PySide6.QtWidgets import QWidget

from .config import log


# =====================================================================
# 16x24 Pixel Art Matrix Data & Color Palettes
# =====================================================================
# Palette Symbols:
# . = Transparent
# H = Primary Hair
# h = Secondary Hair / Shadow
# S = Skin
# s = Skin shadow
# B = Blush (pink)
# E = Eyes
# e = Eye highlight / white
# A = Accessory (fin / spark / ear / headset)
# a = Accessory detail / glow
# T = Collar / Tie / Neck detail
# D = Dress / Top primary
# d = Dress / Top shadow / trim
# K = Skirt / Bottom primary
# k = Skirt / Bottom shadow
# L = Legs (bare skin or tights)
# W = Socks (white)
# F = Feet / Boots / Shoes
# f = Soles / Shoe detail
# P = Prop (copter stem / balloon string)
# R = Rotor blade / Balloon body

CHAR_PALETTES = {
    "deepseek": {
        "H": "#1e3a8a", "h": "#172554",
        "S": "#ffe4d0", "s": "#fbcfe8", "B": "#f472b6",
        "E": "#0284c7", "e": "#e0f2fe",
        "A": "#38bdf8", "a": "#bae6fd",  # Whale fin hairpin & tail
        "T": "#ffffff", "D": "#1d4ed8", "d": "#1e40af",
        "K": "#1e3a8a", "k": "#172554",  # Sailor pleated skirt
        "L": "#ffe4d0", "W": "#ffe4d0",  # Cute bare legs
        "F": "#1e3a8a", "f": "#0f172a",  # Sailor short boots
        "P": "#ca8a04", "R": "#facc15",
    },
    "claude": {
        "H": "#ea580c", "h": "#c2410c",  # Warm orange short hair
        "S": "#ffedd5", "s": "#fed7aa", "B": "#fb7185",
        "E": "#b45309", "e": "#fef3c7",
        "A": "#fbbf24", "a": "#fef08a",  # Golden spark hairpin
        "T": "#fed7aa", "D": "#fb923c", "d": "#f97316",  # Warm dress
        "K": "#ea580c", "k": "#c2410c",
        "L": "#ffedd5", "W": "#ffedd5",  # Light bare legs
        "F": "#9a3412", "f": "#7c2d12",  # Cute warm boots
        "P": "#ca8a04", "R": "#facc15",
    },
    "gpt": {
        "H": "#10b981", "h": "#047857",  # Mint green bob hair
        "S": "#ffe4d0", "s": "#fbcfe8", "B": "#f472b6",
        "E": "#059669", "e": "#d1fae5",
        "A": "#374151", "a": "#34d399",  # Tech headphones with LED
        "T": "#10b981", "D": "#374151", "d": "#1f2937",  # Tech workwear jacket
        "K": "#4b5563", "k": "#1f2937",  # Pleated skirt
        "L": "#ffe4d0", "W": "#ffffff",  # Cute legs with white trim
        "F": "#f3f4f6", "f": "#10b981",  # Sporty athletic sneakers
        "P": "#ca8a04", "R": "#facc15",
    },
    "gemini": {
        "H": "#312e81", "h": "#1e1b4b",  # Dark indigo hair
        "S": "#ffe4e6", "s": "#fecdd3", "B": "#fb7185",
        "E": "#7c3aed", "e": "#ede9fe",
        "A": "#4f46e5", "a": "#f472b6",  # Cat ears & starburst
        "T": "#c084fc", "D": "#6366f1", "d": "#4338ca",  # Blue-violet dress
        "K": "#7c3aed", "k": "#5b21b6",
        "L": "#ffe4e6", "W": "#ffffff",  # Slender legs with white socks
        "F": "#4338ca", "f": "#312e81",  # Mary Jane shoes
        "P": "#ca8a04", "R": "#facc15",
    },
}

# 16 columns x 24 rows character matrices
FRAMES = {
    # ------------------ Idle: 站立呼吸 ------------------
    "idle": [
        "....AAAA....AAAA",
        "...AAHHAAAAHHAA.",
        "..HHHHHHHHHHHH..",
        ".HHHHHHHHHHHHHH.",
        ".HHHhSSSSSSShHH.",
        "HHHhSSSSSSSSShHH",
        "HHHhSEeSSSSEShHH",
        "HHHhSEESSSSEESHH",
        ".HHhSBSSSSSBShH.",
        "..HhSSSSSSSSshH.",
        "...hTDDDDDDTh...",
        "...DDDDDDDDDD...",
        "..SDDDDDDDDDDDS.",
        "..SDDKKKKKKKDDS.",
        "...SDKKKKKKKDS..",
        "....KKKKKKKK....",
        "....KKKKKKKK....",
        "....LL....LL....",
        "....LL....LL....",
        "....LL....LL....",
        "....WW....WW....",
        "....WW....WW....",
        "...FFF....FFF...",
        "...fff....fff...",
    ],
    # ------------------ Walk 1: 邁出左腳，雙腿分明 ------------------
    "walk1": [
        "....AAAA....AAAA",
        "...AAHHAAAAHHAA.",
        "..HHHHHHHHHHHH..",
        ".HHHHHHHHHHHHHH.",
        ".HHHhSSSSSSShHH.",
        "HHHhSSSSSSSSShHH",
        "HHHhSEeSSSSEShHH",
        "HHHhSEESSSSEESHH",
        ".HHhSBSSSSSBShH.",
        "..HhSSSSSSSSshH.",
        "...hTDDDDDDTh...",
        "..SDDDDDDDDDD...",
        "..SDDDDDDDDDDDS.",
        "...DDKKKKKKKDD..",
        "...SDKKKKKKKD...",
        "....KKKKKKKK....",
        "....KKKKKKKK....",
        "...LL......LL...",
        "...LL......LL...",
        "...LL......LL...",
        "..WW........WW..",
        "..WW........WW..",
        ".FFF........FFF.",
        ".fff........fff.",
    ],
    # ------------------ Walk 2: 邁出右腳，雙腿分明 ------------------
    "walk2": [
        "....AAAA....AAAA",
        "...AAHHAAAAHHAA.",
        "..HHHHHHHHHHHH..",
        ".HHHHHHHHHHHHHH.",
        ".HHHhSSSSSSShHH.",
        "HHHhSSSSSSSSShHH",
        "HHHhSEeSSSSEShHH",
        "HHHhSEESSSSEESHH",
        ".HHhSBSSSSSBShH.",
        "..HhSSSSSSSSshH.",
        "...hTDDDDDDTh...",
        "...DDDDDDDDDDS..",
        "..SDDDDDDDDDDDS.",
        "..DDKKKKKKKDD...",
        "...DKKKKKKKDS...",
        "....KKKKKKKK....",
        "....KKKKKKKK....",
        "....LL....LL....",
        "....LL....LL....",
        "...LL......LL...",
        "...WW......WW...",
        "...WW......WW...",
        "..FFF......FFF..",
        "..fff......fff..",
    ],
    # ------------------ Sit: 坐下晃動小短腿 ------------------
    "sit": [
        "....AAAA....AAAA",
        "...AAHHAAAAHHAA.",
        "..HHHHHHHHHHHH..",
        ".HHHHHHHHHHHHHH.",
        ".HHHhSSSSSSShHH.",
        "HHHhSSSSSSSSShHH",
        "HHHhSEeSSSSEShHH",
        "HHHhSEESSSSEESHH",
        ".HHhSBSSSSSBShH.",
        "..HhSSSSSSSSshH.",
        "...hTDDDDDDTh...",
        "...DDDDDDDDDD...",
        "..SDDDDDDDDDDDS.",
        "...DDKKKKKKKDD..",
        "...KKKKKKKKKK...",
        "...KKKKKKKKKK...",
        "...LLLL..LLLL...",
        "...WWWW..WWWW...",
        "...FFFF..FFFF...",
        "...ffff..ffff...",
        "................",
        "................",
        "................",
        "................",
    ],
    # ------------------ Panic: 失足驚慌亂蹬小腿 ------------------
    "panic": [
        "..AA........AA..",
        ".AAAHHHHHHHHAAA.",
        ".HHHHHHHHHHHHHH.",
        "HHhSSSSSSSSSSshH",
        "HhSSEESSSEEESshH",
        "HhSEEEEEEEEEshH.",
        "HhSSEESSSEEESshH",
        ".HhSBBSSSSBBshH.",
        "..HhSSSSSSSSshH.",
        "...hTDDDDDDTh...",
        "..SDDDDDDDDDDDS.",
        ".SDDDDDDDDDDDDDS",
        "S..DDKKKKKKKD..S",
        "...SDKKKKKKKDS..",
        "....KKKKKKKK....",
        "....KKKKKKKK....",
        "...LL......LL...",
        "..LL........LL..",
        "..LL........LL..",
        ".WW..........WW.",
        ".WW..........WW.",
        "FFF..........FFF",
        "fff..........fff",
        "................",
    ],
    # ------------------ Climb: 向上攀爬 ------------------
    "climb": [
        "....AAAA....AAAA",
        "...AAHHAAAAHHAA.",
        "..HHHHHHHHHHHH..",
        ".HHHHHHHHHHHHHH.",
        ".HHHHHHHHHHHHHH.",
        "HHhHHHHHHHHHHshH",
        "HHhHHHHHHHHHHshH",
        "HHhHHHHHHHHHHshH",
        ".HhHHHHHHHHHHshH",
        "..HhSSSSSSSSshH.",
        "...hTDDDDDDTh...",
        "..SDDDDDDDDDDDS.",
        "..SDDDDDDDDDDDS.",
        "...DDKKKKKKKDD..",
        "...SDKKKKKKKDS..",
        "....KKKKKKKK....",
        "....KKKKKKKK....",
        "....LL....LL....",
        "...LL......LL...",
        "...LL......LL...",
        "...WW......WW...",
        "..FFF......WW...",
        "..fff.....FFF...",
        "..........fff...",
    ],
}

# Bamboo copter propeller overlays (Row 0-2)
COPTER_FRAMES = [
    [
        "....RRRRRRRR....",
        ".......PP.......",
        ".......PP.......",
    ],
    [
        "......RRRR......",
        ".......PP.......",
        ".......PP.......",
    ],
]


class PixelChibiRenderer:
    """純代碼 2D 像素陣列與色盤精確繪製器，最近鄰無失真放大。"""
    _cache: dict[tuple, QPixmap] = {}

    @classmethod
    def get_pixmap(cls, character: str, frame_name: str, facing_right: bool = False, scale: int = 3, has_copter: bool = False, copter_idx: int = 0) -> QPixmap:
        char_key = character.lower()
        if char_key not in CHAR_PALETTES:
            char_key = "deepseek"
        cache_key = (char_key, frame_name, facing_right, scale, has_copter, copter_idx)
        if cache_key in cls._cache:
            return cls._cache[cache_key]

        palette = CHAR_PALETTES[char_key]
        raw_rows = FRAMES.get(frame_name, FRAMES["idle"])
        w, h = 16, 24
        img = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
        img.fill(Qt.transparent)

        for y, row_str in enumerate(raw_rows):
            for x, ch in enumerate(row_str):
                if ch == "." or ch not in palette:
                    continue
                color_hex = palette[ch]
                img.setPixelColor(x, y, QColor(color_hex))

        # 疊加飛行小旋翼道具
        if has_copter:
            c_rows = COPTER_FRAMES[copter_idx % len(COPTER_FRAMES)]
            for cy, crow in enumerate(c_rows):
                for cx, cch in enumerate(crow):
                    if cch in palette:
                        img.setPixelColor(cx, cy, QColor(palette[cch]))

        if facing_right:
            img = img.mirrored(True, False)

        # 最近鄰取樣放大 (Qt.FastTransformation) 確保 100% 俐落像素邊緣
        target_w = w * scale
        target_h = h * scale
        scaled_img = img.scaled(target_w, target_h, Qt.IgnoreAspectRatio, Qt.FastTransformation)
        pm = QPixmap.fromImage(scaled_img)
        cls._cache[cache_key] = pm
        return pm


class PixelParticle:
    """像素煙火粒子。"""
    def __init__(self, x: float, y: float, vx: float, vy: float, color: QColor, life: float = 1.0):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.color = color
        self.life = life
        self.age = 0.0

    def update(self, dt: float) -> bool:
        self.age += dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.vy += 80.0 * dt  # 重力
        return self.age < self.life


class PixelChibiWindow(QWidget):
    """Q 版小人獨立桌面巡邏與互動視窗。"""
    panic_fall_started = Signal()
    panic_landed = Signal()
    duang_bounce = Signal()

    def __init__(self, cfg, sounds, pet=None, app=None):
        super().__init__(
            None,
            Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint | Qt.NoDropShadowWindowHint
        )
        self.cfg = cfg
        self.sounds = sounds
        self.pet = pet
        self.app = app

        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setMouseTracking(True)
        self.setWindowTitle("Pixel Chibi Patrol")

        self.scale_factor = 3  # 16x24 -> 48x72 px
        self.char_w = 16 * self.scale_factor
        self.char_h = 24 * self.scale_factor
        self.setFixedSize(self.char_w, self.char_h)

        # 狀態機
        self.character = cfg.get("character", "deepseek")
        self.state = "idle"  # idle, walk, sit, panic, climb, flight
        self.facing_right = True
        self.pos_x = 200.0
        self.pos_y = 600.0
        self.vel_x = 0.0
        self.vel_y = 0.0
        self.on_ground = True
        self.state_time = 0.0
        self.walk_phase = 0.0
        self.copter_idx = 0
        self.copter_timer = 0.0

        # 主寵互動
        self.climbing_pet = False
        self.pet_mount_slot = "floor"  # floor, head, iron, tablet

        # 道具
        self.particles: list[PixelParticle] = []

        # 定時器
        self.timer = QTimer(self)
        self.timer.setInterval(25)  # 40 fps
        self.timer.timeout.connect(self._tick)
        self.timer.start()

        self._init_position()

    def set_pet(self, pet):
        self.pet = pet

    def set_character(self, ch: str):
        self.character = ch
        self.update()

    def _screen_rect(self) -> QRect:
        s = QGuiApplication.screenAt(self.geometry().center()) or QGuiApplication.primaryScreen()
        return s.availableGeometry()

    def _init_position(self):
        ag = self._screen_rect()
        floor_y = ag.bottom() + 1 - self.char_h
        self.pos_x = float(ag.left() + 160)
        self.pos_y = float(floor_y)
        self.move(int(self.pos_x), int(self.pos_y))
        self.show()
        self.raise_()

    def _tick(self):
        dt = 0.025
        self.state_time += dt
        ag = self._screen_rect()
        floor_y = float(ag.bottom() + 1 - self.char_h)

        # 1. 確保圖層永遠高於主寵物 (Z-Order Topmost)
        self.raise_()

        # 2. 更新煙火粒子
        if self.particles:
            self.particles = [p for p in self.particles if p.update(dt)]
            self.update()

        # 3. 飛行道具模式 (飛行小旋翼)
        flight_on = bool(self.cfg.get("q_flight_prop", False))
        if flight_on:
            self.state = "flight"
            self.copter_timer += dt
            if self.copter_timer > 0.08:
                self.copter_timer = 0.0
                self.copter_idx = 1 - self.copter_idx

            # 自由飄蕩飛行
            self.pos_x += (28.0 if self.facing_right else -28.0) * dt
            target_air_y = floor_y - 180.0 + 40.0 * math.sin(self.state_time * 2.5)
            self.pos_y += (target_air_y - self.pos_y) * 0.1

            if self.pos_x > ag.right() - self.char_w - 40:
                self.facing_right = False
            elif self.pos_x < ag.left() + 40:
                self.facing_right = True

            self.move(int(self.pos_x), int(self.pos_y))
            self.update()
            return

        # 4. 視窗與按鈕攀爬辨識 (q_climb_windows)
        climb_enabled = bool(self.cfg.get("q_climb_windows", False))
        if climb_enabled and self.state not in ("panic", "bounce"):
            win_rect = self._get_active_window_rect()
            if win_rect and win_rect.isValid() and not win_rect.isEmpty():
                # 若小人在視窗邊界附近，切換至攀爬或站在標題列
                if abs(self.pos_x - win_rect.left()) < 24 and win_rect.top() <= self.pos_y <= win_rect.bottom():
                    self.state = "climb"
                    self.pos_y -= 30.0 * dt
                    if self.pos_y <= win_rect.top() - self.char_h:
                        self.pos_y = win_rect.top() - self.char_h
                        self.state = "walk"
                    self.move(int(self.pos_x), int(self.pos_y))
                    self.update()
                    return
            else:
                # 視窗消失、最小化或關閉：立足點消失，觸發失足慌張掉落！
                if self.pos_y < floor_y - 20:
                    self.start_panic_fall()

        # 5. 慌張失足掉落物理 (Panic Fall)
        if self.state == "panic":
            self.vel_y += 500.0 * dt  # 重力下墜
            self.pos_y += self.vel_y * dt
            if self.pos_y >= floor_y:
                self.pos_y = floor_y
                self.vel_y = 0.0
                self.state = "sit"
                self.state_time = 0.0
                self.panic_landed.emit()
                if self.sounds:
                    self.sounds.play("land")
            self.move(int(self.pos_x), int(self.pos_y))
            self.update()
            return

        # 6. Duang 軟彈後退坐倒狀態
        if self.state == "bounce":
            self.pos_x += self.vel_x * dt
            self.vel_x *= 0.85
            if self.state_time > 1.2:
                self.state = "idle"
                self.state_time = 0.0
            self.move(int(self.pos_x), int(self.pos_y))
            self.update()
            return

        # 7. 主寵物碰撞偵測與「Duang～」軟彈物理
        if self.pet and self.pet.isVisible() and not self.climbing_pet:
            pet_geom = self.pet.geometry()
            my_rect = QRect(int(self.pos_x), int(self.pos_y), self.char_w, self.char_h)
            if pet_geom.intersects(my_rect):
                self.trigger_duang_bounce()
                return

        # 8. 攀爬主寵物狀態 (頭頂、鐵盆、平板)
        if self.climbing_pet and self.pet and self.pet.isVisible():
            pet_pos = self.pet.pos()
            if self.pet_mount_slot == "head":
                head_rect = self.pet.head_zone_global()
                self.pos_x = head_rect.center().x() - self.char_w / 2
                self.pos_y = head_rect.top() - self.char_h * 0.7
                self.state = "sit"
            elif self.pet_mount_slot == "iron":
                head_rect = self.pet.head_zone_global()
                self.pos_x = head_rect.center().x() + 18
                self.pos_y = head_rect.top() - self.char_h * 0.4
                self.state = "sit"
            elif self.pet_mount_slot == "tablet":
                tab_rect = self.pet.tablet_zone_global()
                self.pos_x = tab_rect.center().x() - self.char_w / 2
                self.pos_y = tab_rect.top() - self.char_h * 0.5
                self.state = "sit"
            self.move(int(self.pos_x), int(self.pos_y))
            self.update()
            return

        # 9. 地面巡邏與行為狀態輪替
        self.pos_y = floor_y
        if self.state == "walk":
            speed = 40.0
            dx = (speed if self.facing_right else -speed) * dt
            self.pos_x += dx
            self.walk_phase = (self.walk_phase + dt * 4.5) % 2.0

            # 撞牆轉向
            if self.pos_x > ag.right() - self.char_w - 10:
                self.facing_right = False
            elif self.pos_x < ag.left() + 10:
                self.facing_right = True

            # 隨機停留或坐下晃雙腿
            if self.state_time > 6.0 and random.random() < 0.03:
                self.state = "sit" if random.random() < 0.5 else "idle"
                self.state_time = 0.0
        elif self.state == "idle":
            if self.state_time > 3.0:
                self.state = "walk"
                self.facing_right = (random.random() > 0.5)
                self.state_time = 0.0
        elif self.state == "sit":
            if self.state_time > 4.5:
                self.state = "walk"
                self.state_time = 0.0

        self.move(int(self.pos_x), int(self.pos_y))
        self.update()

    def start_panic_fall(self):
        """觸發失足驚慌掉落：四肢揮舞亂蹬掉回工作列。"""
        self.state = "panic"
        self.vel_y = 60.0
        self.state_time = 0.0
        self.panic_fall_started.emit()
        log("PixelChibi", "小人失足慌張掉落！小腿空中亂蹬中！")

    def trigger_duang_bounce(self):
        """撞擊主寵物觸發軟彈物理，後退兩步坐倒。"""
        self.state = "bounce"
        self.state_time = 0.0
        self.vel_x = -90.0 if self.facing_right else 90.0
        self.facing_right = not self.facing_right
        self.duang_bounce.emit()
        if self.sounds:
            self.sounds.play("hit")
        log("PixelChibi", "Duang～撞到主寵物軟彈後退坐倒！")

    def mount_pet(self, slot: str = "head"):
        """爬上主寵物身體（頭頂、鐵盆、平板）。"""
        self.climbing_pet = True
        self.pet_mount_slot = slot
        self.state = "sit"
        log("PixelChibi", f"小人已爬上主寵物位置：{slot}")

    def dismount_pet(self):
        """離開主寵物回到地面巡邏。"""
        self.climbing_pet = False
        self.start_panic_fall()

    def launch_fireworks(self):
        """像素煙火發射小道具：綻放繽紛像素火花！"""
        cx = self.char_w / 2.0
        cy = self.char_h * 0.2
        colors = [
            QColor(255, 90, 120), QColor(255, 215, 0), QColor(80, 220, 255),
            QColor(160, 100, 255), QColor(100, 255, 140), QColor(255, 150, 50)
        ]
        for _ in range(24):
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(40.0, 140.0)
            vx = math.cos(angle) * speed
            vy = math.sin(angle) * speed - 60.0  # 向上爆開
            col = random.choice(colors)
            self.particles.append(PixelParticle(cx, cy, vx, vy, col, life=random.uniform(0.7, 1.4)))
        self.update()
        log("PixelChibi", "發射慶祝像素煙火！")

    def _get_active_window_rect(self) -> QRect | None:
        """透過 Windows API 獲取當前前景活動視窗邊界。"""
        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            if not hwnd or hwnd == int(self.winId()):
                return None
            rect = wintypes.RECT()
            if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                w = rect.right - rect.left
                h = rect.bottom - rect.top
                if w > 80 and h > 80:
                    return QRect(rect.left, rect.top, w, h)
        except Exception:
            pass
        return None

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHints(QPainter.SmoothPixmapTransform | QPainter.Antialiasing)

        # 1. 決定當前動畫幀名稱
        if self.state == "walk":
            frame_name = "walk1" if self.walk_phase < 1.0 else "walk2"
        elif self.state == "sit" or self.state == "bounce":
            frame_name = "sit"
        elif self.state == "panic":
            frame_name = "panic"
        elif self.state == "climb":
            frame_name = "climb"
        elif self.state == "flight":
            frame_name = "sit"
        else:
            frame_name = "idle"

        # 2. 獲取像素幀並繪製
        has_copter = (self.state == "flight") or bool(self.cfg.get("q_flight_prop", False))
        pm = PixelChibiRenderer.get_pixmap(
            self.character,
            frame_name,
            facing_right=self.facing_right,
            scale=self.scale_factor,
            has_copter=has_copter,
            copter_idx=self.copter_idx,
        )
        p.drawPixmap(0, 0, pm)

        # 3. 繪製煙火像素粒子
        if self.particles:
            for pt in self.particles:
                alpha = max(0, int(255 * (1.0 - pt.age / pt.life)))
                c = QColor(pt.color)
                c.setAlpha(alpha)
                p.fillRect(int(pt.x), int(pt.y), 4, 4, c)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            # 點擊小人：如果在主寵上則跳下，如果在地上則坐下或發射煙火
            if self.climbing_pet:
                self.dismount_pet()
            elif self.cfg.get("q_fireworks_prop", False):
                self.launch_fireworks()
            else:
                self.state = "sit" if self.state != "sit" else "walk"
                self.state_time = 0.0
                self.update()
