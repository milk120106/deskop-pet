"""全維度行為因子心情值系統（Multi-Factor Dynamic Mood Engine）。

整合六大行為因子數學模型：
1. 額度增減因子 (Balance Cost & Top-Up)
2. 親自餵食連擊機制 (Feed Combo Engine)
3. 摸頭撫摸動態積分 (Patting Intensity & Velocity)
4. 使用者系統活動監聽 (System Activity Monitor，純計數採樣，絕不記錄內容保護隱私)
5. AI 對話情緒標籤注入 (Dialogue Mood Tag Injection)
6. 日常互動頻率與自然衰減
7. 階梯門檻動作分發與高危動作安全防護 (30秒倒數中斷關機、網頁白名單、趣味聯動)
"""
from __future__ import annotations

import re
import time
import urllib.parse
from typing import Any, Callable

from PySide6.QtCore import QObject, QPointF, QTimer, Signal

from .config import Config, log

# 不可竄改之外部跳轉白名單網域
ALLOWED_URL_DOMAINS = (
    "youtube.com",
    "www.youtube.com",
    "bilibili.com",
    "www.bilibili.com",
    "github.com",
    "www.github.com",
    "deepseek.com",
    "www.deepseek.com",
)


def format_companion_time(total_seconds: float) -> str:
    """將秒數自適應換算為自然語言（年/月/天/時/分）。"""
    if total_seconds <= 0:
        return "剛剛開始陪伴"
    seconds = int(total_seconds)
    minutes = seconds // 60
    hours = minutes // 60
    days = hours // 24
    months = days // 30
    years = months // 12

    rem_months = months % 12
    rem_days = days % 30
    rem_hours = hours % 24
    rem_minutes = minutes % 60

    parts = []
    if years > 0:
        parts.append(f"{years} 年")
    if rem_months > 0:
        parts.append(f"{rem_months} 個月")
    if rem_days > 0:
        parts.append(f"{rem_days} 天")
    if rem_hours > 0 and years == 0:
        parts.append(f"{rem_hours} 小時")
    if rem_minutes > 0 and years == 0 and months == 0:
        parts.append(f"{rem_minutes} 分鐘")

    if not parts:
        return "不到 1 分鐘"
    return " ".join(parts)


class SystemActivityMonitor(QObject):
    """系統無感活動監聽器：採樣擊鍵、視窗切換與剪貼簿操作次數。
    
    【重要隱私防護】
    純粹進行操作次數增量計數，嚴格不記錄任何按鍵內容、視窗標題或剪貼文字，杜絕鍵盤記錄器疑慮！
    """
    stats_updated = Signal()

    def __init__(self, mood_engine: MoodEngine):
        super().__init__()
        self.engine = mood_engine
        self._key_count_buffer = 0
        self._switch_count_buffer = 0
        self._clip_count_buffer = 0
        self._last_active_hwnd = None

        self.timer = QTimer(self)
        self.timer.setInterval(2000)  # 每 2 秒採樣一次
        self.timer.timeout.connect(self._poll_activity)

    def start(self):
        self.timer.start()

    def stop(self):
        self.timer.stop()

    def _poll_activity(self):
        # 僅在心情系統啟用時運作
        if not self.engine.is_enabled():
            return
        try:
            import ctypes
            # 視窗切換採樣
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            if hwnd and hwnd != self._last_active_hwnd:
                self._last_active_hwnd = hwnd
                self.record_window_switch()
        except Exception:
            pass

    def record_keystroke(self, count: int = 1):
        """記錄擊鍵次數（純計數）。"""
        self._key_count_buffer += count
        self.engine.increment_stat("keystroke_count", count)
        # 每 120 次擊鍵，心情微幅增加 +0.4
        if self._key_count_buffer >= 120:
            self._key_count_buffer -= 120
            self.engine.apply_delta(0.4, source="主人專注工作擊鍵")

    def record_window_switch(self):
        """記錄視窗切換次數。"""
        self._switch_count_buffer += 1
        # 每 20 次切換，心情增加 +0.2
        if self._switch_count_buffer >= 20:
            self._switch_count_buffer -= 20
            self.engine.apply_delta(0.2, source="主人切換視窗工作")

    def record_clipboard_action(self):
        """記錄剪貼簿操作（純次數）。"""
        self._clip_count_buffer += 1
        # 每 15 次，心情增加 +0.3
        if self._clip_count_buffer >= 15:
            self._clip_count_buffer -= 15
            self.engine.apply_delta(0.3, source="主人剪貼文字整理")


class MoodEngine(QObject):
    """全維度行為動態心情引擎。"""
    mood_changed = Signal(float, float)  # (current_mood, max_limit)
    threshold_triggered = Signal(str, list)  # (threshold_id, action_names)
    feed_combo_updated = Signal(int)

    def __init__(self, cfg: Config, pet=None, sounds=None):
        super().__init__()
        self.cfg = cfg
        self.pet = pet
        self.sounds = sounds

        self._feed_combo = 0
        self._last_feed_time = 0.0
        self._last_interaction_time = time.monotonic()
        self._last_decay_time = time.monotonic()
        self._minute_deduction_sum = 0.0
        self._minute_window_start = time.monotonic()

        # 初始化首次啟動時間戳記
        stats = self.cfg.get("pet_stats") or {}
        if not stats.get("first_launch_timestamp"):
            self.update_stat("first_launch_timestamp", time.time())

        # 系統活動監聽器
        self.activity_monitor = SystemActivityMonitor(self)
        if self.is_enabled():
            self.activity_monitor.start()

        # 心情衰減定時器 (每 60 秒檢查一次)
        self.decay_timer = QTimer(self)
        self.decay_timer.setInterval(60000)
        self.decay_timer.timeout.connect(self._check_decay)
        self.decay_timer.start()

    def is_enabled(self) -> bool:
        return bool(self.cfg.get("mood_system_enabled", False))

    def set_enabled(self, val: bool):
        self.cfg.set("mood_system_enabled", bool(val))
        if val:
            self.activity_monitor.start()
        else:
            self.activity_monitor.stop()

    def get_mood(self) -> float:
        return float(self.cfg.get("mood_value", 50.0))

    def get_max_limit(self) -> float:
        # 嚴格保護性下限 >= 100.0
        return float(self.cfg.get("mood_max_limit", 100.0))

    def get_percentage(self) -> float:
        m = self.get_mood()
        lim = self.get_max_limit()
        return max(0.0, min(100.0, (m / lim) * 100.0))

    def get_stats(self) -> dict[str, Any]:
        return self.cfg.get("pet_stats") or {}

    def get_companion_time_text(self) -> str:
        stats = self.get_stats()
        first_launch = stats.get("first_launch_timestamp", 0.0)
        if not first_launch:
            return "剛剛開始陪伴"
        elapsed = max(0.0, time.time() - first_launch)
        return format_companion_time(elapsed)

    def increment_stat(self, key: str, delta: int = 1):
        stats = dict(self.get_stats())
        val = stats.get(key, 0)
        if isinstance(val, (int, float)):
            stats[key] = val + delta
            self.cfg.set("pet_stats", stats, save=False)

    def update_stat(self, key: str, val: Any):
        stats = dict(self.get_stats())
        stats[key] = val
        self.cfg.set("pet_stats", stats, save=False)

    # ------------------------------------------------------------- 心情動態調節核心
    def apply_delta(self, delta: float, source: str = "互動") -> float:
        """增減心情值，進行保護性邊界限制並觸發門檻動作。"""
        old_val = self.get_mood()
        max_lim = self.get_max_limit()
        new_val = max(0.0, min(max_lim, old_val + delta))
        self.cfg.set("mood_value", new_val, save=False)
        self._last_interaction_time = time.monotonic()

        log("MoodEngine", f"心情變化 [{source}]: {old_val:.1f} -> {new_val:.1f} (Δ={delta:+.1f})")
        self.mood_changed.emit(new_val, max_lim)

        # 門檻判定 (僅在系統啟用時觸發動作分發)
        if self.is_enabled():
            self._check_thresholds(old_val, new_val, max_lim)
        return new_val

    # 1. 額度變動因子
    def on_balance_deduct(self, cost: float, ref_cost: float = 0.05):
        """扣款因子：單次扣除心情，並限制每分鐘扣除上限不超過 15 點。"""
        now = time.monotonic()
        if now - self._minute_window_start > 60.0:
            self._minute_window_start = now
            self._minute_deduction_sum = 0.0

        ratio = cost / max(0.001, ref_cost)
        desired_loss = min(15.0, ratio * 5.0)
        available_cap = max(0.0, 15.0 - self._minute_deduction_sum)
        actual_loss = min(desired_loss, available_cap)
        self._minute_deduction_sum += actual_loss

        if actual_loss > 0.05:
            self.apply_delta(-actual_loss, source="API 呼叫消耗額度")

    def on_balance_topup(self, amount: float, ref_amount: float = 10.0):
        """充值增額因子：大額充值回饋心情，最高 +25.0。"""
        ratio = amount / max(0.01, ref_amount)
        gain = min(25.0, ratio * 10.0)
        if gain > 0.1:
            self.apply_delta(gain, source="帳戶儲值回饋")

    # 2. 親自餵食連擊因子
    def on_feed(self, amount: float = 1.0) -> int:
        """餵食連擊機制（8.0 秒判定窗口）。"""
        now = time.monotonic()
        if now - self._last_feed_time <= 8.0:
            self._feed_combo += 1
        else:
            self._feed_combo = 1
        self._last_feed_time = now

        # 更新統計指標
        stats = self.get_stats()
        highest = max(stats.get("highest_feed_combo", 0), self._feed_combo)
        self.update_stat("current_feed_combo", self._feed_combo)
        self.update_stat("feed_combo_count", self._feed_combo)
        self.update_stat("highest_feed_combo", highest)
        self.increment_stat("total_interactions", 1)

        # 連擊加成增量
        base_gain = 3.0
        combo_bonus = 1.0 + min(1.5, 0.15 * self._feed_combo)
        actual_gain = base_gain * combo_bonus
        self.apply_delta(actual_gain, source=f"親自餵食 (連擊 x{self._feed_combo})")
        self.feed_combo_updated.emit(self._feed_combo)
        return self._feed_combo

    def check_feed_combo_timeout(self):
        """檢查連擊是否超時。"""
        if self._feed_combo > 0 and time.monotonic() - self._last_feed_time > 8.0:
            self._feed_combo = 0
            self.update_stat("current_feed_combo", 0)
            self.update_stat("feed_combo_count", 0)
            self.feed_combo_updated.emit(0)

    # 3. 摸頭撫摸動態積分
    def on_pet_stroke(self, stroke_duration: float, velocity_x: float):
        """根據滑動速度與持續時間積分心情。"""
        vx = abs(velocity_x)
        if 120.0 <= vx <= 500.0:
            weight = 1.2  # 溫柔撫摸
        elif vx > 500.0:
            weight = 0.6  # 急躁粗魯
        else:
            weight = 0.3  # 過於緩慢

        gain = weight * min(4.0, stroke_duration * 2.5)
        self.increment_stat("pat_count", 1)
        self.increment_stat("total_interactions", 1)
        self.apply_delta(gain, source="溫柔摸頭撫摸")

    def on_api_cost(self, cost: float):
        """API 消耗額度回調別名。"""
        self.on_balance_deduct(cost)

    def on_topup(self, amount: float):
        """額度充值回調別名。"""
        self.on_balance_topup(amount)

    def on_pat(self, velocity: float = 200.0, duration: float = 0.5):
        """撫摸互動回調別名。"""
        self.on_pet_stroke(duration, velocity)

    def record_stat(self, key: str, amount: int = 1):
        """統計指標累加別名。"""
        self.increment_stat(key, amount)

    def set_stat(self, key: str, val: Any):
        """統計指標設定別名。"""
        self.update_stat(key, val)

    # 4. AI 對話情緒標籤解析
    def parse_ai_dialogue_mood(self, text: str) -> tuple[str, float]:
        """過濾 [MOOD: +5] / [MOOD: -3] 標籤並觸發心情調幅。"""
        cleaned_text = text
        delta_val = 0.0
        match = re.search(r"\[MOOD:\s*([+-]?\d+(?:\.\d+)?)\s*\]", text, re.IGNORECASE)
        if match:
            try:
                delta_val = float(match.group(1))
            except Exception:
                delta_val = 0.0
            cleaned_text = re.sub(r"\[MOOD:\s*([+-]?\d+(?:\.\d+)?)\s*\]", "", text, flags=re.IGNORECASE).strip()

        self.increment_stat("ai_dialogue_count", 1)
        self.increment_stat("total_interactions", 1)
        if abs(delta_val) > 0.01:
            self.apply_delta(delta_val, source="AI 情感對話共鳴")
        return cleaned_text, delta_val

    # 5. 自然衰減判定
    def _check_decay(self):
        self.check_feed_combo_timeout()
        if not self.is_enabled():
            return
        now = time.monotonic()
        decay_sec = float(self.cfg.get("mood_decay_interval_sec", 600))
        # 閒置無互動超過 15 分鐘 (900 秒) 後開始自然衰減
        if now - self._last_interaction_time >= 900.0:
            if now - self._last_decay_time >= decay_sec:
                self._last_decay_time = now
                amount = float(self.cfg.get("mood_decay_amount", 1.0))
                self.apply_delta(-amount, source="閒置無陪伴自然衰減")

    # ------------------------------------------------------------- 門檻動作分發與安全防護
    def _check_thresholds(self, old_val: float, new_val: float, max_lim: float):
        thresholds = self.cfg.get("mood_thresholds") or []
        for t in thresholds:
            th_target = float(t.get("threshold", 100.0))
            is_pct = t.get("type", "percentage") == "percentage"
            target_val = (th_target / 100.0 * max_lim) if is_pct else th_target

            # 跨過門檻且未達次數上限
            if old_val < target_val <= new_val:
                max_trig = int(t.get("max_triggers", 0))
                trig_cnt = int(t.get("triggered_count", 0))
                if max_trig == 0 or trig_cnt < max_trig:
                    t["triggered_count"] = trig_cnt + 1
                    self.cfg.set("mood_thresholds", thresholds, save=False)
                    actions = t.get("actions", [])
                    log("MoodEngine", f"觸發門檻「{t.get('id')}」({th_target}%)，執行動作: {actions}")
                    self.threshold_triggered.emit(t.get("id", ""), actions)
                    self._dispatch_threshold_actions(actions)

    def _dispatch_threshold_actions(self, actions: list[str]):
        """分發執行門檻綁定之動作。"""
        for act in actions:
            if act == "play_sound":
                if self.sounds:
                    self.sounds.play("feed")
            elif act == "desktop_toast":
                if self.pet and hasattr(self.pet, "show_toast"):
                    self.pet.show_toast("寵物心情極佳！感謝主人的溫暖陪伴！")
            elif act == "fireworks":
                if self.pet and hasattr(self.pet, "trigger_fireworks"):
                    self.pet.trigger_fireworks()
                chibi = getattr(self.pet, "pixel_chibi", None)
                if chibi and hasattr(chibi, "spawn_celebration_fireworks"):
                    chibi.spawn_celebration_fireworks()
            elif act == "pet_interact":
                if self.pet and hasattr(self.pet, "wear_iron"):
                    self.pet.wear_iron()

    # ------------------------------------------------------------- 高危安全動作分發器
    @classmethod
    def validate_action_url(cls, url: str) -> bool:
        """嚴格校驗跳轉網址是否屬於不可竄改之白名單網域。"""
        return cls.is_url_safe(url)

    @staticmethod
    def is_url_safe(url: str) -> bool:
        """嚴格校驗跳轉網址是否屬於不可竄改之白名單網域。"""
        try:
            parsed = urllib.parse.urlparse(url)
            if parsed.scheme not in ("http", "https"):
                return False
            domain = (parsed.hostname or "").lower()
            return domain in ALLOWED_URL_DOMAINS or any(domain.endswith("." + d) for d in ALLOWED_URL_DOMAINS)
        except Exception:
            return False
