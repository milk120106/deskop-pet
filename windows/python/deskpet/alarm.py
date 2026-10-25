"""Desktop Pet Alarm and Notification Dispatcher.
Supports scheduled alarms, countdown timers, snooze, and multi-channel forwarding
(Windows native toast, Discord Webhook, Telegram Bot Webhook).
"""
from __future__ import annotations

import json
import threading
import time
import urllib.request
import urllib.error
from datetime import datetime
from PySide6.QtCore import QObject, QTimer, Signal

from .config import log


class AlarmDispatcher(QObject):
    alarm_triggered = Signal(dict)
    notification_dispatched = Signal(dict)
    alarms_changed = Signal()

    def __init__(self, cfg, sounds, pet=None, app=None):
        super().__init__()
        self.cfg = cfg
        self.sounds = sounds
        self.pet = pet
        self.app = app
        self._ringing_alarms: dict[str, dict] = {}
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._check_alarms)
        self._timer.start()

    def set_pet(self, pet):
        self.pet = pet

    def set_app(self, app):
        self.app = app

    def get_alarms(self) -> list[dict]:
        return list(self.cfg.get("alarms", []))

    def get_notifications(self) -> list[dict]:
        return list(self.cfg.get("notifications", []))

    def add_alarm(
        self,
        name: str,
        time_str: str = "",
        alarm_type: str = "clock",
        duration_sec: int = 0,
        sound: str = "",
        repeat: bool = False,
    ) -> dict:
        """新增定時鬧鐘 (clock) 或倒數計時器 (timer)。"""
        alarms = self.get_alarms()
        alarm_id = f"alarm_{int(time.time() * 1000)}"
        target_ts = 0.0
        now_ts = time.time()

        if alarm_type == "timer":
            dur = max(1, int(duration_sec))
            target_ts = now_ts + dur
            time_display = f"{dur // 60:02d}:{dur % 60:02d}"
        else:
            time_display = time_str.strip() or "08:00"

        item = {
            "id": alarm_id,
            "name": name.strip() or "自訂提醒",
            "type": alarm_type,
            "time": time_display,
            "duration_sec": duration_sec,
            "target_ts": target_ts,
            "enabled": True,
            "repeat": repeat,
            "sound": sound.strip(),
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        alarms.append(item)
        self.cfg.set("alarms", alarms, save=True)
        self.alarms_changed.emit()
        log("Alarm", f"已新增鬧鐘：{item['name']} ({item['type']}, {item['time']})")
        return item

    def remove_alarm(self, alarm_id: str):
        alarms = [a for a in self.get_alarms() if a.get("id") != alarm_id]
        self.cfg.set("alarms", alarms, save=True)
        if alarm_id in self._ringing_alarms:
            del self._ringing_alarms[alarm_id]
        self.alarms_changed.emit()
        log("Alarm", f"已刪除鬧鐘：{alarm_id}")

    def toggle_alarm(self, alarm_id: str, enabled: bool):
        alarms = self.get_alarms()
        for a in alarms:
            if a.get("id") == alarm_id:
                a["enabled"] = bool(enabled)
                if not enabled and alarm_id in self._ringing_alarms:
                    del self._ringing_alarms[alarm_id]
                break
        self.cfg.set("alarms", alarms, save=True)
        self.alarms_changed.emit()

    def snooze_alarm(self, alarm_id: str, minutes: int = 5):
        """貪睡 5 分鐘：重新設定倒數目標時間並暫停當前響鈴。"""
        alarms = self.get_alarms()
        for a in alarms:
            if a.get("id") == alarm_id:
                a["type"] = "timer"
                a["target_ts"] = time.time() + minutes * 60
                a["enabled"] = True
                a["name"] = a["name"].replace(" (貪睡中)", "") + " (貪睡中)"
                break
        self.cfg.set("alarms", alarms, save=True)
        if alarm_id in self._ringing_alarms:
            del self._ringing_alarms[alarm_id]
        if self.pet:
            self.pet.hide_speech_bubble()
            self.pet.stop_alarm_glow()
        self.alarms_changed.emit()
        log("Alarm", f"鬧鐘 {alarm_id} 已設定貪睡 {minutes} 分鐘")

    def dismiss_alarm(self, alarm_id: str):
        """關閉或結束當前響鈴之鬧鐘。"""
        if alarm_id in self._ringing_alarms:
            del self._ringing_alarms[alarm_id]
        alarms = self.get_alarms()
        for a in alarms:
            if a.get("id") == alarm_id:
                if not a.get("repeat", False) and a.get("type") == "timer":
                    a["enabled"] = False
                elif not a.get("repeat", False) and a.get("type") == "clock":
                    a["enabled"] = False
                break
        self.cfg.set("alarms", alarms, save=True)
        if self.pet:
            self.pet.hide_speech_bubble()
            self.pet.stop_alarm_glow()
        self.alarms_changed.emit()
        log("Alarm", f"鬧鐘 {alarm_id} 已關閉響鈴")

    def trigger_alarm(self, alarm_dict: dict):
        """觸發鬧鐘：呼吸閃爍、冒出想法框、播放音效、多管道轉發。"""
        alarm_id = alarm_dict.get("id", "")
        alarm_name = alarm_dict.get("name", "提醒事件")
        self._ringing_alarms[alarm_id] = alarm_dict
        log("Alarm", f"觸發鬧鐘響鈴：【時間到囉：{alarm_name}】")

        # 1. 桌面寵物本體動態：平板亮屏呼吸閃爍與螢幕中上方彈窗通知
        try:
            from .dialogs import show_desktop_toast
            show_desktop_toast(f"【時間到囉：{alarm_name}】")
        except Exception:
            pass

        if self.pet:
            self.pet.trigger_alarm_glow(alarm_name)
            # 頭頂冒出想法框【時間到囉：事件名稱】，點擊可選擇關閉或貪睡
            bubble_text = f"【時間到囉：{alarm_name}】\n點擊關閉，長按貪睡 5 分鐘"
            self.pet.show_speech_bubble(
                bubble_text,
                thought=True,
                persistent=True,
                on_click=lambda: self.dismiss_alarm(alarm_id),
            )

        # 2. 播放自訂鬧鐘音效
        sound_file = alarm_dict.get("sound", "")
        if sound_file and hasattr(self.sounds, "play_file"):
            self.sounds.play_file(sound_file)
        elif hasattr(self.sounds, "play"):
            self.sounds.play("hit")

        # 3. 多管道同步轉發通知
        self.dispatch_notification(
            title="桌面寵物提醒",
            message=f"【時間到囉：{alarm_name}】",
            alarm_id=alarm_id,
        )

        # 4. 若像素煙火小道具開啟，觸發煙火慶祝
        if self.app and hasattr(self.app, "pixel_chibi") and self.app.pixel_chibi:
            if self.cfg.get("q_fireworks_prop", False):
                self.app.pixel_chibi.launch_fireworks()

        self.alarm_triggered.emit(alarm_dict)

    def dispatch_notification(self, title: str, message: str, alarm_id: str = ""):
        """多管道同步轉發：Windows 原生 Toast、Discord Webhook、Telegram Bot Webhook。"""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 1. Windows 原生 Toast / 系統匣通知
        if self.app and hasattr(self.app, "tray") and self.app.tray:
            try:
                from PySide6.QtWidgets import QSystemTrayIcon
                self.app.tray.showMessage(title, message, QSystemTrayIcon.Information, 7000)
            except Exception as e:
                log("Alarm", f"系統匣通知顯示失敗：{e}")

        # 2. 記錄至 notifications 清單
        history = self.get_notifications()
        note_entry = {
            "id": f"note_{int(time.time() * 1000)}",
            "timestamp": now_str,
            "title": title,
            "message": message,
            "alarm_id": alarm_id,
            "discord_status": "未設定",
            "telegram_status": "未設定",
        }

        # 3. Discord Webhook 非同步轉發
        discord_url = (self.cfg.get("discord_webhook_url") or "").strip()
        if discord_url:
            threading.Thread(
                target=self._send_discord_webhook,
                args=(discord_url, title, message, note_entry),
                daemon=True,
            ).start()

        # 4. Telegram Bot Webhook 非同步轉發
        tg_token = (self.cfg.get("telegram_bot_token") or "").strip()
        tg_chat_id = (self.cfg.get("telegram_chat_id") or "").strip()
        if tg_token and tg_chat_id:
            threading.Thread(
                target=self._send_telegram_webhook,
                args=(tg_token, tg_chat_id, title, message, note_entry),
                daemon=True,
            ).start()

        history.insert(0, note_entry)
        if len(history) > 50:
            history = history[:50]
        self.cfg.set("notifications", history, save=True)
        self.notification_dispatched.emit(note_entry)

    def _send_discord_webhook(self, url: str, title: str, message: str, note_entry: dict):
        try:
            payload = {
                "username": "桌面寵物提醒",
                "embeds": [
                    {
                        "title": title,
                        "description": message,
                        "color": 0x4F46E5,
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                        "footer": {"text": "Desktop Pet Notification Dispatcher"},
                    }
                ],
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json", "User-Agent": "DesktopPet/2.1"},
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                if resp.status in (200, 204):
                    note_entry["discord_status"] = "已發送"
                    log("Alarm", "Discord Webhook 通知發送成功")
                else:
                    note_entry["discord_status"] = f"HTTP {resp.status}"
        except Exception as err:
            note_entry["discord_status"] = f"失敗：{err}"
            log("Alarm", f"Discord Webhook 發送異常：{err}")

    def _send_telegram_webhook(self, token: str, chat_id: str, title: str, message: str, note_entry: dict):
        try:
            api_url = f"https://api.telegram.org/bot{token}/sendMessage"
            text_md = f"*{title}*\n\n{message}"
            payload = {
                "chat_id": chat_id,
                "text": text_md,
                "parse_mode": "Markdown",
            }
            req = urllib.request.Request(
                api_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json", "User-Agent": "DesktopPet/2.1"},
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                if resp.status == 200:
                    note_entry["telegram_status"] = "已發送"
                    log("Alarm", "Telegram Bot 通知發送成功")
                else:
                    note_entry["telegram_status"] = f"HTTP {resp.status}"
        except Exception as err:
            note_entry["telegram_status"] = f"失敗：{err}"
            log("Alarm", f"Telegram Bot 發送異常：{err}")

    def _check_alarms(self):
        now_ts = time.time()
        now_dt = datetime.now()
        cur_hhmm = now_dt.strftime("%H:%M")
        cur_sec = now_dt.second

        alarms = self.get_alarms()
        for a in alarms:
            if not a.get("enabled", True):
                continue
            aid = a.get("id", "")
            if aid in self._ringing_alarms:
                continue

            atype = a.get("type", "clock")
            if atype == "timer":
                target = float(a.get("target_ts", 0.0))
                if target > 0 and now_ts >= target:
                    self.trigger_alarm(a)
            elif atype == "clock":
                alarm_time = a.get("time", "").strip()
                # 僅在該分鐘的前 3 秒觸發一次，避免重複響鈴
                if alarm_time == cur_hhmm and cur_sec <= 2:
                    self.trigger_alarm(a)
