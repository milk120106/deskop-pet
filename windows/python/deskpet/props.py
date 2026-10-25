"""Rice bowls (recharge) and iron bowl: draggable, throwable, bouncing props with bowl-vs-bowl collision."""
from __future__ import annotations

import math
import random
import time

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import (QColor, QFont, QGuiApplication, QImage, QPainter, QPen, QPixmap)
from PySide6.QtWidgets import QWidget

from . import winapi
from .config import asset

GRAVITY = 2100.0
RESTITUTION = 0.5
AIR_DRAG = 0.30
SLIDE_FRICTION = 1.40
SLIDE_STOP = 14.0
THROW_MAX = 4200.0
THROW_MAX_Y = 1700.0
WAIT_SEC = 10.0          # Unclaimed rice bowl gets locked after 10s
LOCK_DELAY = 1.0         # ...and is sucked toward pet 1s later
AUTO_CLEAR_SEC = 45.0    # 45s untouched bowl auto collected quietly
SUCK_ACCEL = 960.0
SUCK_MAX = 2400.0
PAD = 46                 # transparent margin around art for radar
GREEN = QColor(110, 255, 140)


def _crop_alpha(img: QImage) -> QImage:
    """Trim fully transparent borders."""
    img = img.convertToFormat(QImage.Format_ARGB32)
    small = img.scaled(180, 180, Qt.IgnoreAspectRatio, Qt.FastTransformation)
    x0, y0, x1, y1 = 180, 180, -1, -1
    for y in range(180):
        for x in range(180):
            if small.pixelColor(x, y).alpha() > 8:
                x0, x1 = min(x0, x), max(x1, x)
                y0, y1 = min(y0, y), max(y1, y)
    if x1 < 0:
        return img
    sx, sy = img.width() / 180.0, img.height() / 180.0
    return img.copy(int(max(0, x0 * sx - 2)), int(max(0, y0 * sy - 2)),
                    int(min(img.width(), (x1 + 1) * sx + 4)), int(min(img.height(), (y1 + 1) * sy + 4)))


class Art:
    _cache: dict[str, QImage] = {}

    @classmethod
    def get(cls, name: str) -> QImage:
        if name not in cls._cache:
            img = QImage(asset(name))
            img = _crop_alpha(img)
            if img.width() > 640:
                img = img.scaledToWidth(640, Qt.SmoothTransformation)
            cls._cache[name] = img
        return cls._cache[name]


class Prop(QWidget):
    def __init__(self, mgr: "PropManager", kind: str, width: int, amount: float = 0.0):
        super().__init__(None, Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint
                         | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.mgr = mgr
        self.kind = kind
        self.amount = amount
        src = Art.get("rice.png" if kind == "rice" else "iron_bowl.png")
        self.aw = int(width)
        self.ah = int(round(width * src.height() / src.width()))
        self.pix = QPixmap.fromImage(src.scaled(self.aw, self.ah, Qt.IgnoreAspectRatio,
                                                Qt.SmoothTransformation))
        self.setFixedSize(self.aw + 2 * PAD, self.ah + 2 * PAD)

        # Physics: x, y = centre of art in global screen coordinates
        self.x = 0.0
        self.y = 0.0
        self.vx = 0.0
        self.vy = 0.0
        self.bounces = 0
        self.max_bounces = 3
        self.held = False
        self.grab_off = QPointF()
        self.trail: list[tuple[float, float, float]] = []
        self.born = time.monotonic()
        self.landed_at: float | None = None
        self.locked_at: float | None = None
        self.sucking = False
        self.radar_demo = False
        self.dead = False
        self._closing = 0.0

    @property
    def radius(self) -> float:
        # Effective radius for collision
        return self.aw * 0.44

    def art_rect(self) -> QRectF:
        return QRectF(self.x - self.aw / 2, self.y - self.ah / 2, self.aw, self.ah)

    def place(self):
        self.move(int(self.x - self.width() / 2), int(self.y - self.height() / 2))

    def showEvent(self, e):
        super().showEvent(e)
        hwnd = int(self.winId())
        winapi.hide_from_taskbar(hwnd)
        winapi.set_topmost(hwnd, True)
        if self.mgr.click_through:
            winapi.set_click_through(hwnd, True)
        self.raise_()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.setRenderHint(QPainter.Antialiasing)
        p.drawPixmap(PAD, PAD, self.pix)
        if self.kind == "rice" and not self.sucking:
            f = QFont("Segoe UI", 10)
            f.setBold(True)
            p.setFont(f)
            p.setPen(QPen(QColor(20, 90, 40)))
            cur_sym = "" if self.mgr.pet.ledger.currency == "CNY" else "$"
            p.drawText(QRectF(0, 2, self.width(), PAD - 6), Qt.AlignHCenter | Qt.AlignBottom,
                       f"+{cur_sym}{self.amount:.2f}")
        if self.kind == "rice" and (self.locked_at is not None or self.radar_demo):
            self._paint_radar(p)

    def _paint_radar(self, p: QPainter):
        r = QRectF(PAD - 8, PAD - 8, self.aw + 16, self.ah + 16)
        p.setPen(QPen(GREEN, 2))
        L = min(r.width(), r.height()) * 0.22
        for (cx, cy, sx, sy) in ((r.left(), r.top(), 1, 1), (r.right(), r.top(), -1, 1),
                                 (r.left(), r.bottom(), 1, -1), (r.right(), r.bottom(), -1, -1)):
            p.drawLine(QPointF(cx, cy), QPointF(cx + sx * L, cy))
            p.drawLine(QPointF(cx, cy), QPointF(cx, cy + sy * L))
        pet = self.mgr.pet
        t = pet.body_center_global()
        dx, dy = t.x() - self.x, t.y() - self.y
        dist = math.hypot(dx, dy)
        f = QFont("Consolas", 8)
        f.setBold(True)
        p.setFont(f)
        p.setPen(QPen(GREEN))
        lines = [f"{dist / 1000:.2f}kpx", f"{self._closing:+.0f}px/s", f"{-dy:+.0f}px"]
        y = r.bottom() + 2
        for ln in lines:
            p.drawText(QRectF(0, y, self.width(), 12), Qt.AlignHCenter, ln)
            y += 11
        # Direction needle
        c = QPointF(r.right() + 2, r.top() - 2)
        p.drawEllipse(c, 6, 6)
        a = math.atan2(dy, dx)
        p.drawLine(c, QPointF(c.x() + 6 * math.cos(a), c.y() + 6 * math.sin(a)))

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.held = True
            self.sucking = False
            self.locked_at = None
            self.radar_demo = False
            self.landed_at = None
            g = e.globalPosition()
            self.grab_off = QPointF(g.x() - self.x, g.y() - self.y)
            self.trail = [(time.monotonic(), g.x(), g.y())]
            self.vx = self.vy = 0.0
            self.raise_()

    def contextMenuEvent(self, e):
        self.mgr.prop_menu(self, e.globalPos())
        e.accept()

    def mouseMoveEvent(self, e):
        if not self.held:
            return
        g = e.globalPosition()
        self.x, self.y = g.x() - self.grab_off.x(), g.y() - self.grab_off.y()
        self.place()
        self.raise_()
        now = time.monotonic()
        self.trail.append((now, g.x(), g.y()))
        self.trail = [s for s in self.trail if now - s[0] < 0.12]

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.LeftButton or not self.held:
            return
        self.held = False
        if len(self.trail) >= 2:
            t0, x0, y0 = self.trail[0]
            t1, x1, y1 = self.trail[-1]
            dt = max(1e-3, t1 - t0)
            self.vx = max(-THROW_MAX, min(THROW_MAX, (x1 - x0) / dt))
            self.vy = max(-THROW_MAX_Y, min(THROW_MAX_Y, (y1 - y0) / dt))
            if math.hypot(self.vx, self.vy) < 12:
                self.vx = self.vy = 0.0
        self.landed_at = None
        self.bounces = 0
        floor = self.mgr.floor_for(self.x, self.y)
        self.max_bounces = bounces_for_drop(max(0.0, floor - (self.y + self.ah / 2)))
        self.mgr.released(self)
        self.mgr.wake()


def bounces_for_drop(px: float) -> int:
    if px < 40:
        return 0
    if px < 160:
        return 1
    if px < 420:
        return 2
    return 3


class PropManager:
    def __init__(self, pet, sounds, cfg):
        self.pet = pet
        self.sounds = sounds
        self.cfg = cfg
        self.props: list[Prop] = []
        self.click_through = False
        self.timer = QTimer()
        self.timer.setInterval(16)
        self.timer.setTimerType(Qt.PreciseTimer)
        self.timer.timeout.connect(self.step)
        self._t = time.monotonic()
        self._menu_cb = None

    def bowl_width(self) -> int:
        return max(70, int(self.pet.size_px * 0.27))

    def screen_at(self, x, y):
        s = QGuiApplication.screenAt(QPointF(x, y).toPoint())
        return s or QGuiApplication.primaryScreen()

    def floor_for(self, x, y) -> float:
        return float(self.screen_at(x, y).availableGeometry().bottom() + 1)

    def rice(self):
        return [p for p in self.props if p.kind == "rice"]

    def irons(self):
        return [p for p in self.props if p.kind == "iron"]

    def wake(self):
        if not self.timer.isActive():
            self._t = time.monotonic()
            self.timer.start()

    def set_click_through(self, on: bool):
        self.click_through = on
        for p in self.props:
            if p.isVisible():
                winapi.set_click_through(int(p.winId()), on)

    def prop_menu(self, prop: Prop, gpos):
        if self._menu_cb:
            self._menu_cb(prop, gpos)

    # ------------------------------------------------------------ spawning
    def spawn_rice(self, amount: float):
        b = Prop(self, "rice", self.bowl_width(), amount)
        scr = QGuiApplication.screenAt(self.pet.frameGeometry().center()) or QGuiApplication.primaryScreen()
        ag = scr.availableGeometry()
        b.x = ag.right() - b.aw / 2 - 4
        b.y = ag.top() + ag.height() * 0.28
        b.vx = -260.0
        b.vy = 0.0
        b.max_bounces = 3
        self._add(b)
        self.pet.on_bowl_state_changed()
        return b

    def spawn_iron(self, x: float, y: float):
        max_pots = getattr(self.pet, "get_max_iron_pots", lambda: 5)()
        if self.pet.iron_count >= max_pots or (len(self.irons()) + self.pet.iron_count) >= max_pots:
            return None
        b = Prop(self, "iron", self.bowl_width(), 0.0)
        b.x, b.y = x, y
        b.vx, b.vy = 0.0, -260.0
        b.max_bounces = 2
        self._add(b)
        return b

    def spawn_sky_pot(self):
        """天降空鐵鍋：從螢幕頂部水平隨機坐標自由落體墜落。"""
        scr = QGuiApplication.screenAt(self.pet.frameGeometry().center()) or QGuiApplication.primaryScreen()
        ag = scr.availableGeometry()
        b = Prop(self, "iron", self.bowl_width(), 0.0)
        b.is_sky_drop = True
        b.x = random.uniform(ag.left() + 60, ag.right() - 60)
        b.y = ag.top() + 10
        b.vx = random.uniform(-20.0, 20.0)
        b.vy = 40.0
        b.max_bounces = 2
        self._add(b)
        return b

    def trigger_pot_collapse(self):
        """大崩塌：所有鐵鍋歸零並全域四散炸開！"""
        cnt = self.pet.iron_count
        if cnt <= 0:
            return
        self.pet.iron_count = 0
        self.pet.refresh_expr()
        head = self.pet.head_zone_global()
        for _ in range(cnt):
            b = Prop(self, "iron", self.bowl_width(), 0.0)
            b.x = head.center().x() + random.uniform(-25, 25)
            b.y = head.top() + random.uniform(-15, 15)
            b.vx = random.uniform(-450.0, 450.0)
            b.vy = random.uniform(-380.0, -120.0)
            b.max_bounces = 3
            self._add(b)
        if self.sounds:
            self.sounds.play("hit")

    def trigger_natural_slip(self, count: int = 1):
        """自然滑落：隨機微幅滑落鐵鍋至地面。"""
        if self.pet.iron_count <= 0:
            return
        slip_cnt = min(self.pet.iron_count, count)
        self.pet.iron_count -= slip_cnt
        self.pet.refresh_expr()
        head = self.pet.head_zone_global()
        is_right = getattr(self.pet, "snap_right", False)
        for _ in range(slip_cnt):
            b = Prop(self, "iron", self.bowl_width(), 0.0)
            b.x = head.center().x() + (30 if is_right else -30)
            b.y = head.top()
            b.vx = random.uniform(80.0, 160.0) if is_right else random.uniform(-160.0, -80.0)
            b.vy = -60.0
            b.max_bounces = 2
            self._add(b)
        if self.sounds:
            self.sounds.play("land")

    def _add(self, b: Prop):
        self.props.append(b)
        b.place()
        b.show()
        b.raise_()
        self.wake()

    def remove(self, b: Prop):
        b.dead = True
        if b in self.props:
            self.props.remove(b)
        b.hide()
        b.deleteLater()
        self.pet.on_bowl_state_changed()

    def clear_all_rice(self) -> float:
        total = 0.0
        for b in list(self.props):
            if b.kind == "rice" and not b.dead:
                total += b.amount
                self.remove(b)
        return total

    def clear_all_iron(self) -> int:
        count = 0
        for b in list(self.props):
            if b.kind == "iron" and not b.dead:
                count += 1
                self.remove(b)
        return count

    def clear(self, kind: str | None = None):
        for b in list(self.props):
            if kind is None or b.kind == kind:
                self.remove(b)

    def hide_all(self):
        for b in self.props:
            if not b.dead:
                b.hide()

    def show_all(self):
        for b in self.props:
            if not b.dead:
                b.show()

    def lock_now(self):
        for b in self.rice():
            b.radar_demo = True
            b.update()

    # ------------------------------------------------------------ release
    def released(self, b: Prop):
        c = QPointF(b.x, b.y)
        if b.kind == "rice":
            if self.pet.contains_global(c):
                self.pet.feed(b.amount, c)
                self.remove(b)
        else:
            head = self.pet.head_zone_global()
            max_pots = getattr(self.pet, "get_max_iron_pots", lambda: 5)()
            if (head.contains(c) or head.intersects(b.art_rect())) and self.pet.iron_count < max_pots:
                self.pet.wear_iron()
                self.remove(b)

    # ------------------------------------------------------------ physics & collision
    def step(self):
        now = time.monotonic()
        dt = min(0.05, max(1e-3, now - self._t))
        self._t = now
        moving = False

        # 1. Check radar lock condition for rice bowls
        waiting = [b for b in self.rice() if not b.held and b.landed_at is not None]
        if any(now - b.landed_at >= WAIT_SEC for b in waiting):
            for b in self.rice():
                if b.locked_at is None and not b.held:
                    b.locked_at = now

        # 2. Check 45s auto-clear
        for b in list(self.rice()):
            if not b.held and now - b.born >= AUTO_CLEAR_SEC:
                # auto-collected quietly (credits money without fanfare)
                self.pet.ledger.apply_credit(b.amount)
                self.remove(b)

        # 3. Step individual physics
        for b in list(self.props):
            if b.dead or b.held:
                moving = moving or b.held
                continue
            if b.kind == "rice" and b.locked_at is not None and now - b.locked_at >= LOCK_DELAY:
                b.sucking = True
            if b.sucking:
                moving = True
                self._suck(b, dt)
                continue
            moving = self._integrate(b, dt, now) or moving
            if b.locked_at is not None or b.radar_demo:
                moving = True
                b.update()

        # 4. BOWL-VERSUS-BOWL COLLISION
        if self._collide_bowls(dt):
            moving = True

        self.pet.on_bowl_state_changed()

        if moving:
            self.timer.setInterval(16)
        elif self.rice():
            self.timer.setInterval(100)      # rice waiting on floor
        else:
            self.timer.stop()

    def _collide_bowls(self, dt: float) -> bool:
        """Bowl-vs-bowl collision: separation push and elastic impulse exchange."""
        changed = False
        n = len(self.props)
        for i in range(n):
            ra = self.props[i]
            if ra.dead:
                continue
            for j in range(i + 1, n):
                rb = self.props[j]
                if rb.dead:
                    continue

                dx = rb.x - ra.x
                dy = rb.y - ra.y
                d2 = dx * dx + dy * dy
                minD = ra.radius + rb.radius
                if d2 >= minD * minD:
                    continue

                d = math.sqrt(d2)
                if d < 1e-4:
                    dx, dy, d = 1.0, 0.0, 1.0
                nx, ny = dx / d, dy / d

                push = (minD - d) * 0.5
                a_fixed = ra.held or ra.sucking
                b_fixed = rb.held or rb.sucking

                aw = 0.0 if a_fixed else (1.0 if b_fixed else 0.5)
                bw = 0.0 if b_fixed else (1.0 if a_fixed else 0.5)

                ra.x -= nx * push * 2 * aw
                ra.y -= ny * push * 2 * aw
                rb.x += nx * push * 2 * bw
                rb.y += ny * push * 2 * bw

                # Relative closing velocity along normal
                va = ra.vx * nx + ra.vy * ny
                vb = rb.vx * nx + rb.vy * ny
                if va - vb > 0 and not a_fixed and not b_fixed:
                    imp = (va - vb) * 0.45
                    ra.vx -= imp * nx
                    ra.vy -= imp * ny
                    rb.vx += imp * nx
                    rb.vy += imp * ny
                    changed = True

                ra.place()
                rb.place()
                changed = True
        return changed

    def _suck(self, b: Prop, dt: float):
        t = self.pet.body_center_global()
        dx, dy = t.x() - b.x, t.y() - b.y
        d = math.hypot(dx, dy)
        if d < max(24.0, self.pet.size_px * 0.12) or self.pet.contains_global(QPointF(b.x, b.y)):
            self.pet.feed(b.amount, QPointF(b.x, b.y))
            self.remove(b)
            return
        sp = min(SUCK_MAX, math.hypot(b.vx, b.vy) + SUCK_ACCEL * dt)
        b.vx, b.vy = dx / d * sp, dy / d * sp
        b._closing = sp
        b.x += b.vx * dt
        b.y += b.vy * dt
        b.place()
        b.raise_()
        b.update()

    def _integrate(self, b: Prop, dt: float, now: float) -> bool:
        scr = self.screen_at(b.x, b.y).availableGeometry()
        floor = float(scr.bottom() + 1)
        left, right = float(scr.left()), float(scr.right() + 1)
        bottom = b.y + b.ah / 2
        on_floor = bottom >= floor - 0.5 and abs(b.vy) < 1.0

        if on_floor and abs(b.vx) < SLIDE_STOP:
            if b.landed_at is None:
                b.landed_at = now
            b.vx = 0.0
            b.y = floor - b.ah / 2
            b.place()
            return False

        b.vy += GRAVITY * dt
        b.vx *= max(0.0, 1.0 - AIR_DRAG * dt)
        b.x += b.vx * dt
        b.y += b.vy * dt

        # Screen boundaries
        if b.x - b.aw / 2 < left:
            b.x = left + b.aw / 2
            b.vx = abs(b.vx) * RESTITUTION
        elif b.x + b.aw / 2 > right:
            b.x = right - b.aw / 2
            b.vx = -abs(b.vx) * RESTITUTION

        bottom = b.y + b.ah / 2
        if bottom >= floor:
            b.y = floor - b.ah / 2
            if abs(b.vy) > 60 and b.bounces < b.max_bounces:
                b.vy = -b.vy * RESTITUTION
                b.bounces += 1
                self.sounds.play("land")
            else:
                if abs(b.vy) > 200:
                    self.sounds.play("land")
                b.vy = 0.0
                if b.landed_at is None:
                    b.landed_at = now
            if b.vy == 0.0:
                b.vx *= max(0.0, 1.0 - SLIDE_FRICTION * dt * 4)
        else:
            b.landed_at = None if b.vy != 0 else b.landed_at

        b.place()

        # Iron bowl dropped onto head from above
        max_pots = getattr(self.pet, "get_max_iron_pots", lambda: 5)()
        if b.kind == "iron" and b.vy > 30 and self.pet.iron_count < max_pots:
            head = self.pet.head_zone_global()
            test_pt = QPointF(b.x, b.y + b.ah * 0.25)
            swept_catch = (head.left() <= b.x <= head.right() and (b.y - b.vy * dt) <= head.top() <= (b.y + b.ah * 0.5))
            if head.contains(test_pt) or head.intersects(b.art_rect()) or swept_catch:
                self.pet.wear_iron()
                self.remove(b)
                return False

        # 天降空鐵鍋砸中 Q 版小人 -> 觸發舉鍋巡邏 (lift_walk)
        if b.kind == "iron" and b.vy > 30:
            chibi_mgr = getattr(self.pet, "chibi_mgr", None) or (getattr(self.pet, "app", None) and getattr(self.pet.app, "chibi_mgr", None))
            chibis = chibi_mgr.chibis if chibi_mgr else ([getattr(self.pet, "pixel_chibi", None)] if getattr(self.pet, "pixel_chibi", None) else [])
            for ch in chibis:
                if ch and ch.isVisible() and not getattr(ch, "climbing_pet", False) and getattr(ch, "state", "") not in ("lift_walk", "bowl_smash"):
                    ch_rect = QRectF(ch.geometry())
                    if ch_rect.intersects(b.art_rect()) or ch_rect.contains(QPointF(b.x, b.y)):
                        if hasattr(ch, "trigger_lift_pot"):
                            ch.trigger_lift_pot()
                            self.remove(b)
                            return False
        return True
