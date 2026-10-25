"""應用程式控制器：管理桌面主寵物、道具、多隻餘額寵物、Q版角色、系統匣圖示、選單、Web伺服器與控制台。"""
from __future__ import annotations

import sys
import time
import webbrowser
from PySide6.QtCore import QObject, QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QGuiApplication, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon, QWidget

from . import winapi
from .audio import Sounds
from .balance import Ledger
from .config import ASSETS, Config, asset, id_to_provider_name, log, provider_to_id
from .dialogs import CharPickerDialog, SoundLibraryDialog
from .panel import ControlPanel
from .pet import PetWindow
from .qml_ui import QmlControlWindow
from .web import WebServer

MAX_CHARS = 8

BALANCE_PET_SPECS = {
    # 嚴格限制只有最初的 4 個核心官方角色（藍色大肥魚 DeepSeek、GPT龍娘、大小姐Claude、北美貓娘Gemini）
    "deepseek": {"name": "藍色大肥魚", "sub": "DeepSeek 鯨魚娘", "title": "DeepSeek 餘額", "prov": "deepseek", "char": "deepseek"},
    "gpt": {"name": "GPT龍娘", "sub": "OpenAI 龍娘", "title": "OpenAI 餘額", "prov": "openai", "char": "gpt"},
    "claude": {"name": "大小姐Claude", "sub": "Anthropic 大小姐", "title": "Claude 餘額", "prov": "anthropic", "char": "claude"},
    "gemini": {"name": "北美貓娘Gemini", "sub": "Google 北美貓娘", "title": "Gemini 餘額", "prov": "gemini", "char": "gemini"},
}


def get_menu_qss(theme: str = "light") -> str:
    chk_dark = (ASSETS / "menu_check_dark.svg").as_posix()
    chk_light = (ASSETS / "menu_check_light.svg").as_posix()
    if theme == "dark":
        return f"""
        QMenu {{
            background-color: #16181d;
            color: #e2e8f0;
            border: 1px solid #2d313b;
            border-radius: 10px;
            padding: 6px 4px;
            font-family: "Microsoft JhengHei UI", sans-serif;
            font-size: 13px;
        }}
        QMenu::item {{
            background-color: transparent;
            padding: 7px 24px 7px 28px;
            border-radius: 6px;
            margin: 1px 4px;
            color: #e2e8f0;
        }}
        QMenu::item:selected {{
            background-color: #2b303c;
            color: #ffffff;
        }}
        QMenu::item:disabled {{
            color: #64748b;
        }}
        QMenu::separator {{
            height: 1px;
            background-color: #2d313b;
            margin: 5px 8px;
        }}
        QMenu::indicator {{
            width: 14px;
            height: 14px;
            left: 8px;
        }}
        QMenu::indicator:checked {{
            image: url("{chk_dark}");
        }}
        QMenu::indicator:unchecked {{
            image: none;
        }}
        """
    else:
        return f"""
        QMenu {{
            background-color: #ffffff;
            color: #0f172a;
            border: 1px solid #e2e8f0;
            border-radius: 10px;
            padding: 6px 4px;
            font-family: "Microsoft JhengHei UI", sans-serif;
            font-size: 13px;
        }}
        QMenu::item {{
            background-color: transparent;
            padding: 7px 24px 7px 28px;
            border-radius: 6px;
            margin: 1px 4px;
            color: #0f172a;
        }}
        QMenu::item:selected {{
            background-color: #f1f5f9;
            color: #0f172a;
        }}
        QMenu::item:disabled {{
            color: #94a3b8;
        }}
        QMenu::separator {{
            height: 1px;
            background-color: #e2e8f0;
            margin: 5px 8px;
        }}
        QMenu::indicator {{
            width: 14px;
            height: 14px;
            left: 8px;
        }}
        QMenu::indicator:checked {{
            image: url("{chk_light}");
        }}
        QMenu::indicator:unchecked {{
            image: none;
        }}
        """


class App(QObject):
    state_changed = Signal()

    def __init__(self, qapp: QApplication):
        super().__init__()
        self.qapp = qapp
        self.cfg = Config()
        from .font_manager import init_app_font
        init_app_font(self.cfg)
        self.sounds = Sounds(self.cfg)
        main_monitor = (self.cfg.get("pet_monitors") or {}).get("main", {})
        main_prov = main_monitor.get("provider") or None
        main_kidx = main_monitor.get("key_index", None)
        self.ledger = Ledger(self.cfg, provider_override=main_prov, key_index=main_kidx)
        self.pet = PetWindow(self.cfg, self.ledger, self.sounds)

        # Multi-pet balance summons (up to 4 balance pets)
        self.extra_pets: dict[str, PetWindow] = {}
        self.extra_ledgers: dict[str, Ledger] = {}
        self.chat_dialog = None

        # Gemini Live 純語音模式狀態管理（絕不彈出文字視窗）
        self.pure_voice_active = False
        self.pure_voice_recorder = None
        self.pure_voice_worker = None
        self.pure_voice_pet: PetWindow | None = None

        # 鬧鐘與通知排程調度器 (Alarm & Notification Dispatcher)
        from .alarm import AlarmDispatcher
        self.alarm_dispatcher = AlarmDispatcher(self.cfg, self.sounds, pet=self.pet, app=self)

        # 全新 Q 版人物獨立像素系統與巡邏隊管理器 (Pixel Chibi Patrol)
        from .pixel_chibi import PixelChibiManager, PixelChibiWindow
        self.chibi_manager = PixelChibiManager(self.cfg, self.sounds, pet=self.pet, app=self)
        self.pixel_chibi: PixelChibiWindow | None = self.chibi_manager.primary_chibi
        if self.pet:
            self.pet.pixel_chibi = self.pixel_chibi

        self.pet.props._menu_cb = self.prop_menu
        self.pet.context_requested.connect(lambda gpos: self.pet_menu(gpos, pet=self.pet))
        self.panel: ControlPanel | None = None
        self.qml_panel: QmlControlWindow | None = None

        # Start background WebServer (default port 8765..8775)
        self.web = WebServer(self)

        self.tray = QSystemTrayIcon(QIcon(asset("tray.ico")), self)
        self.tray.setToolTip("Desktop Pet")
        self.tray_menu = QMenu()
        theme = self.cfg.get("theme", "light")
        self.tray_menu.setStyleSheet(get_menu_qss(theme))
        self.tray_menu.setAttribute(Qt.WA_TranslucentBackground, True)
        self.tray_menu.setWindowFlags(self.tray_menu.windowFlags() | Qt.FramelessWindowHint)
        self.tray_menu.aboutToShow.connect(lambda: self._fill_menu(self.tray_menu, tray=True))
        self.tray.setContextMenu(self.tray_menu)
        self.tray.activated.connect(self._tray_activated)
        self.tray.show()

        self.pet.place_initial()
        self.pet.show()
        self._restore_extra_pets()
        self._restore_saved_layout()
        try:
            from .autostart import sync_auto_start
            sync_auto_start(self.cfg)
        except Exception:
            pass
        from .destruction_fx import DestructionOverlay
        self.destruction_overlay = DestructionOverlay(app_controller=self)
        self._tutorial_dlg = None
        if not self.cfg.get("tutorial_shown", False) and "--selftest" not in sys.argv:
            QTimer.singleShot(600, self.open_tutorial)
        qapp.aboutToQuit.connect(self._cleanup)

    def _cleanup(self):
        try:
            self.save_layout()
        except Exception:
            pass
        try:
            self.stop_pure_voice()
        except Exception:
            pass
        try:
            self.dismiss_all_balance_pets()
        except Exception:
            pass
        try:
            if self.web:
                self.web.stop()
        except Exception:
            pass
        self.cfg.save()

    def save_layout(self):
        """自動保存當前大寵物與所有場上活躍 Q 版小人位置與狀態。"""
        if not bool(self.cfg.get("auto_save_layout", True)):
            self.cfg.set("saved_chibi_layout", [], save=True)
            return

        self.cfg.set("pos", [self.pet.x(), self.pet.y()], save=False)
        chibi_data = []
        if hasattr(self, "chibi_manager") and self.chibi_manager:
            for c in self.chibi_manager.chibis:
                entry = {
                    "character": c.character,
                    "pos_x": float(c.pos_x),
                    "pos_y": float(c.pos_y),
                    "facing_right": bool(c.facing_right),
                    "state": str(c.state),
                    "climbing_pet": bool(c.climbing_pet),
                    "pet_mount_slot": str(getattr(c, "pet_mount_slot", "floor")),
                }
                chibi_data.append(entry)
        self.cfg.set("saved_chibi_layout", chibi_data, save=True)

    def _restore_saved_layout(self):
        """還原上次儲存的版面佈局（若視窗遺失則觸發小氣球安全緩降至地面）。"""
        if not bool(self.cfg.get("auto_save_layout", True)):
            return
        saved_chibis = self.cfg.get("saved_chibi_layout", [])
        if not saved_chibis or not hasattr(self, "chibi_manager") or not self.chibi_manager:
            return
        for entry in saved_chibis:
            cid = entry.get("character", "deepseek")
            w = self.chibi_manager.summon(cid, force=True)
            if w:
                w.pos_x = float(entry.get("pos_x", w.pos_x))
                w.pos_y = float(entry.get("pos_y", w.pos_y))
                w.set_facing_right(bool(entry.get("facing_right", True)))
                w.move(int(w.pos_x), int(w.pos_y))
                ag = w._screen_rect()
                floor_y = float(ag.bottom() + 1 - w.char_h)
                # 遺失視窗小氣球安全降落：若小人在半空中但沒有附著的視窗，觸發氣球緩降
                if w.pos_y < floor_y - 30:
                    win_rect = w._get_active_window_rect()
                    if not win_rect or not win_rect.isValid() or win_rect.isEmpty():
                        w.start_balloon_landing()

    # ------------------------------------------------------------- Multi-pet Balance Management
    def _restore_extra_pets(self):
        saved = self.cfg.get("extra_pets") or []
        for cid in saved:
            if cid in BALANCE_PET_SPECS and cid != self.pet.character:
                self.summon_balance_pet(cid, save=False)

    def summon_balance_pet(self, cid: str, save: bool = True, force: bool = False) -> PetWindow | None:
        if cid in self.extra_pets:
            win = self.extra_pets[cid]
            win.show()
            win.raise_()
            win.activateWindow()
            return win

        if cid not in BALANCE_PET_SPECS:
            return None

        # 檢查大寵物在場數量上限 (5, 10, 15, 20, 25, 30 隻)
        from .config import get_effective_pet_max_count
        cur_count = 1 + len(self.extra_pets)
        max_limit = get_effective_pet_max_count(self.cfg)
        if cur_count >= max_limit and not force:
            msg = f"目前在場大寵物已達數量上限 ({cur_count}/{max_limit} 隻)，建議收回部分寵物以維持最佳系統效能，或至設定中調高上限檔位！是否仍要繼續召喚？"
            log(f"[App] {msg}")
            if "--selftest" not in sys.argv:
                try:
                    from .dialogs import ModernMessageBox
                    ans = ModernMessageBox.question(self.pet, "大寵物數量上限提醒", msg)
                    if ans != ModernMessageBox.Yes:
                        return None
                except Exception:
                    pass

        spec = BALANCE_PET_SPECS[cid]
        char_id = spec.get("char", cid)

        # 外觀與監控目標解耦：讀取此寵物獨立配置之廠商與 Key
        monitors = self.cfg.get("pet_monitors") or {}
        p_cfg = monitors.get(cid, {})
        target_prov = p_cfg.get("provider") or spec["prov"]
        target_kidx = p_cfg.get("key_index", None)

        ledger = Ledger(self.cfg, provider_override=target_prov, key_index=target_kidx)
        pet = PetWindow(self.cfg, ledger, self.sounds, character_override=char_id, is_extra=True, pet_id=cid)
        pet.props._menu_cb = self.prop_menu
        pet.context_requested.connect(lambda gpos, p=pet: self.pet_menu(gpos, pet=p))

        idx = len(self.extra_pets) + 1
        offset_x = -idx * 260
        pet.place_initial(default_offset_x=offset_x)

        # Apply current global options
        pet.sync_opacity()
        pet.set_size(self.pet.size_px)
        if self.cfg.get("click_through", False):
            pet.apply_click_through(True)

        pet.show()
        self.extra_pets[cid] = pet
        self.extra_ledgers[cid] = ledger

        if save:
            active = list(self.cfg.get("extra_pets") or [])
            if cid not in active:
                active.append(cid)
                self.cfg.set("extra_pets", active, save=True)

        self._changed()
        return pet

    def set_pet_monitor(self, pet_id: str, provider: str, key_index: int | None = None):
        """將指定大寵物或主寵物之監視目標與 API Key 綁定解耦設定。"""
        monitors = dict(self.cfg.get("pet_monitors") or {})
        monitors[pet_id] = {"provider": provider, "key_index": key_index}
        self.cfg.set("pet_monitors", monitors, save=True)

        target_pet = None
        if pet_id == "main" or pet_id == getattr(self.pet, "character", ""):
            target_pet = self.pet
        elif pet_id in self.extra_pets:
            target_pet = self.extra_pets[pet_id]

        if target_pet and hasattr(target_pet, "ledger") and target_pet.ledger:
            target_pet.ledger.set_provider(provider)
            target_pet.ledger.set_key_index(key_index)
            log(f"[App] 寵物「{pet_id}」監視目標已更新為：{provider} (Key #{key_index + 1 if key_index is not None else '全部/輪替'})")
        self._changed()

    def set_pet_max_count(self, count: int):
        from .config import PET_MAX_COUNT_OPTIONS
        if count in PET_MAX_COUNT_OPTIONS:
            self.cfg.set("pet_max_count", int(count), save=True)
            log(f"[App] 大寵物在場數量上限已調整為：{count} 隻")
            self._changed()

    def set_aggregate_same_provider_keys(self, enabled: bool):
        self.cfg.set("aggregate_same_provider_keys", bool(enabled), save=True)
        log(f"[App] 同廠商多 API Key 額度整合計算已切換為：{'開啟' if enabled else '關閉'}")
        if hasattr(self, "ledger") and self.ledger:
            self.ledger.refresh()
        for ep_ledger in self.extra_ledgers.values():
            ep_ledger.refresh()
        self._changed()

    def summon_api_chibi(self, prov: str, key_index: int | None = None):
        """召喚指定 API 額度監控 Q 版小人（在桌面上巡邏、在想法框中顯示該 API 的額度/餘額）。"""
        if hasattr(self, "chibi_manager") and self.chibi_manager:
            cur = self.chibi_manager.active_count
            limit = self.chibi_manager.max_count
            force = False
            if cur >= limit:
                msg = f"目前在場 Q 版小人已達數量上限 ({cur}/{limit} 隻)，建議收回部分小人以維持最佳系統效能，或至設定中調高上限檔位！是否仍要繼續召喚？"
                log(f"[App] {msg}")
                if "--selftest" not in sys.argv:
                    from .dialogs import ModernMessageBox
                    ans = ModernMessageBox.question(None, "數量上限提醒", msg)
                    if ans != ModernMessageBox.Yes:
                        return None
                force = True
            return self.chibi_manager.summon_api_monitor(prov, key_index=key_index, force=force)
        return None

    def dismiss_balance_pet(self, cid: str):
        if cid in self.extra_pets:
            pet = self.extra_pets.pop(cid)
            if cid in self.extra_ledgers:
                ledger = self.extra_ledgers.pop(cid)
                ledger.poll.stop()
                ledger.sim.stop()
            pet.hide()
            pet.deleteLater()

            active = list(self.cfg.get("extra_pets") or [])
            if cid in active:
                active.remove(cid)
                self.cfg.set("extra_pets", active, save=True)

            self._changed()

    def summon_all_balance_pets(self):
        for cid in BALANCE_PET_SPECS:
            if cid != self.pet.character:
                self.summon_balance_pet(cid)

    def dismiss_all_balance_pets(self):
        for cid in list(self.extra_pets.keys()):
            self.dismiss_balance_pet(cid)

    # ------------------------------------------------------------- AI Chat & Gemini Live 純語音模式
    def open_chat_dialog(self, target_pet: PetWindow | None = None):
        from .chat import ChatDialog

        target = target_pet or self.pet
        if self.chat_dialog is None:
            self.chat_dialog = ChatDialog(self, target)
        else:
            self.chat_dialog.pet = target
        self.chat_dialog.show_beside_pet()

    def start_pure_voice(self, target_pet: PetWindow | None = None):
        """啟動 Gemini Live 純語音即時連線（絕不彈出文字對話框）。"""
        cur_pet = target_pet or self.pet
        self.pure_voice_pet = cur_pet

        cur_pet.show_speech_bubble(
            "現在是語音模式ㄛ",
            thought=True,
            persistent=True,
            on_click=self.stop_pure_voice,
        )

        # 1. 檢查 Google Gemini API Key
        profiles = self.cfg.get("api_profiles", [])
        gemini_prof = next((p for p in profiles if p.get("provider") == "Google Gemini" and p.get("key", "").strip()), None)
        if not gemini_prof:
            k = (self.cfg.get("api_keys") or {}).get("gemini", "").strip()
            if k:
                gemini_prof = {
                    "provider": "Google Gemini",
                    "key": k,
                    "model": self.cfg.get("gemini_live_model", "gemini-2.0-flash-exp"),
                }
        if not gemini_prof:
            cur_pet.show_speech_bubble("純語音模式需要 Google Gemini API Key，請先於設定中配置。")
            self.pure_voice_active = False
            return

        # 2. 檢查音訊輸入裝置
        try:
            import sounddevice as sd
            devs = sd.query_devices()
            has_input = any(d.get("max_input_channels", 0) > 0 for d in devs)
            if not has_input:
                cur_pet.show_speech_bubble("未檢測到可用的麥克風輸入裝置。")
                self.pure_voice_active = False
                return
        except Exception as e:
            cur_pet.show_speech_bubble(f"音訊模組載入失敗：{e}")
            self.pure_voice_active = False
            return

        self.pure_voice_active = True
        self._start_pure_voice_listening()

    def _start_pure_voice_listening(self):
        """進入語音聆聽狀態"""
        if not self.pure_voice_active or not self.pure_voice_pet:
            return
        from .chat import VoiceRecorder

        self.pure_voice_pet.show_speech_bubble(
            "現在是語音模式ㄛ",
            thought=True,
            persistent=True,
            on_click=self.stop_pure_voice,
        )

        self.pure_voice_recorder = VoiceRecorder(traditional=False, vad_enabled=True, parent=self)
        self.pure_voice_recorder.finished.connect(self._on_pure_voice_recorded)
        self.pure_voice_recorder.failed.connect(self._on_pure_voice_failed)
        self.pure_voice_recorder.start()

    def _on_pure_voice_failed(self, err: str):
        self.pure_voice_recorder = None
        if self.pure_voice_pet:
            self.pure_voice_pet.show_speech_bubble(f"純語音錯誤：{err}", timeout_ms=4000)
        self.pure_voice_active = False

    def _on_pure_voice_recorded(self, path: str):
        self.pure_voice_recorder = None
        if not self.pure_voice_active or not self.pure_voice_pet:
            return

        self.pure_voice_pet.show_speech_bubble(
            "思考中...",
            thought=True,
            persistent=True,
            on_click=self.stop_pure_voice,
        )

        from .chat import GeminiLiveWorker

        profiles = self.cfg.get("api_profiles", [])
        gemini_prof = next((p for p in profiles if p.get("provider") == "Google Gemini" and p.get("key", "").strip()), None)
        if not gemini_prof:
            k = (self.cfg.get("api_keys") or {}).get("gemini", "").strip()
            gemini_prof = {
                "provider": "Google Gemini",
                "key": k,
                "model": self.cfg.get("gemini_live_model", "gemini-2.0-flash-exp"),
            }

        model = self.cfg.get("gemini_live_model", "gemini-2.0-flash-exp")
        voice = self.cfg.get("gemini_live_voice", "Kore")
        char_name = self.pure_voice_pet.character
        sys_prompt = f"你是桌面上的可愛角色（目前外觀：{char_name}）。請以繁體中文親切回答，簡短自然，字數在 100 字以內，不要輸出任何思考過程標籤或 markdown 表情符號。"

        self.pure_voice_worker = GeminiLiveWorker(path, gemini_prof, sys_prompt, model, voice, self)
        self.pure_voice_worker.finished.connect(self._on_pure_voice_finished)
        self.pure_voice_worker.start()

    def _on_pure_voice_finished(self, ok: bool, data: dict):
        self.pure_voice_worker = None
        if not self.pure_voice_active or not self.pure_voice_pet:
            return

        if not ok:
            err = data.get("error", "未知錯誤")
            self.pure_voice_pet.show_speech_bubble(f"語音回應異常：{err}", timeout_ms=4000)
            self.stop_pure_voice()
            return

        text = data.get("text", "")
        reply = ""
        for line in text.splitlines():
            if line.startswith("Gemini："):
                reply = line[7:].strip()
                break
        if not reply and text:
            reply = text.strip()
        if not reply:
            reply = "我聽到了，但暫時無法生成回應。"

        # 播放語音回覆
        has_audio = False
        if data.get("audio"):
            try:
                self.pure_voice_pet.sounds.play_file(data["audio"])
                has_audio = True
            except Exception:
                has_audio = False

        # 顯示頭頂 AI 回覆文字（thought=False）
        self.pure_voice_pet.show_speech_bubble(
            reply,
            thought=False,
            timeout_ms=0,
            persistent=False,
            on_click=self.stop_pure_voice,
        )

        # 語音播放完畢後，若仍處於純語音模式，自動切回 _start_pure_voice_listening
        self._wait_audio_then_resume(has_audio=has_audio, text_len=len(reply))

    def _wait_audio_then_resume(self, has_audio: bool, text_len: int):
        if hasattr(self, "_pure_voice_resume_timer") and self._pure_voice_resume_timer:
            self._pure_voice_resume_timer.stop()
            self._pure_voice_resume_timer = None

        self._pure_voice_wait_count = 0
        self._pure_voice_resume_timer = QTimer(self)
        self._pure_voice_resume_timer.setInterval(250)

        # 最少閱讀停留時間（無音訊時以字數計算，有音訊時至少 1.5 秒）
        min_display_ticks = 6 if has_audio else max(10, min(32, text_len // 2))

        def _check_status():
            if not self.pure_voice_active or not self.pure_voice_pet:
                if self._pure_voice_resume_timer:
                    self._pure_voice_resume_timer.stop()
                    self._pure_voice_resume_timer = None
                return

            self._pure_voice_wait_count += 1
            is_playing = False
            if has_audio and hasattr(self.pure_voice_pet.sounds, "is_file_playing"):
                try:
                    is_playing = self.pure_voice_pet.sounds.is_file_playing()
                except Exception:
                    is_playing = False

            # 若仍在播放且未超過 40 秒（安全上限），繼續等待
            if is_playing and self._pure_voice_wait_count < 160:
                return

            # 若未達到最少顯示時間，繼續等待
            if self._pure_voice_wait_count < min_display_ticks:
                return

            # 播放完畢且顯示時間充足，停止計時並自動切回聆聽狀態
            if self._pure_voice_resume_timer:
                self._pure_voice_resume_timer.stop()
                self._pure_voice_resume_timer = None

            if self.pure_voice_active and self.pure_voice_pet:
                self._start_pure_voice_listening()

        self._pure_voice_resume_timer.timeout.connect(_check_status)
        self._pure_voice_resume_timer.start()

    def stop_pure_voice(self):
        """關閉純語音模式"""
        self.pure_voice_active = False
        if hasattr(self, "_pure_voice_resume_timer") and self._pure_voice_resume_timer:
            self._pure_voice_resume_timer.stop()
            self._pure_voice_resume_timer = None
        if self.pure_voice_recorder and self.pure_voice_recorder.isRunning():
            self.pure_voice_recorder.stop()
            self.pure_voice_recorder = None
        if self.pure_voice_worker and self.pure_voice_worker.isRunning():
            self.pure_voice_worker.cancel()
            self.pure_voice_worker = None
        if self.pure_voice_pet:
            self.pure_voice_pet.sounds.stop_file()
            self.pure_voice_pet.show_speech_bubble("已關閉純語音模式", timeout_ms=2500)
            self.pure_voice_pet = None

    def open_gemini_live(self, target_pet: PetWindow | None = None):
        """純語音模式切換（相容舊介面呼叫，絕不彈出文字視窗）"""
        if self.pure_voice_active:
            self.stop_pure_voice()
        else:
            self.start_pure_voice(target_pet=target_pet)

    # ------------------------------------------------------------- menus
    def _fill_menu(self, m: QMenu, tray: bool = False, pet: PetWindow | None = None):
        m.clear()
        c = self.cfg
        cur_pet = pet or self.pet
        theme = self.cfg.get("theme", "light")
        m.setStyleSheet(get_menu_qss(theme))
        m.setAttribute(Qt.WA_TranslucentBackground, True)
        m.setWindowFlags(m.windowFlags() | Qt.FramelessWindowHint)

        def act(text, fn, checked=None, enabled=True):
            a = QAction(text, m)
            if checked is not None:
                a.setCheckable(True)
                a.setChecked(bool(checked))
                a.toggled.connect(lambda v, f=fn: f(v))
            else:
                a.triggered.connect(lambda _=False, f=fn: f())
            a.setEnabled(enabled)
            m.addAction(a)
            return a

        act("AI 對話", lambda: self.open_chat_dialog(target_pet=cur_pet))
        if self.pure_voice_active:
            act("關閉純語音模式 (Gemini Live)", self.stop_pure_voice)
        else:
            act("純語音模式 (Gemini Live)", lambda: self.start_pure_voice(target_pet=cur_pet))
        m.addSeparator()

        act("設定", self.open_settings)
        act("開啟網頁儀表板", self.open_web_ui)
        m.addSeparator()

        # Multi-pet balance summons (嚴格限制只有 4 位核心官方角色)
        total_balance_pets = len(self.extra_pets) + (1 if self.pet.character in BALANCE_PET_SPECS else 0)
        sub_balance = m.addMenu(f"召喚餘額寵物（在場 {total_balance_pets}/{len(BALANCE_PET_SPECS)}）")
        sub_balance.setStyleSheet(m.styleSheet())
        sub_balance.setAttribute(Qt.WA_TranslucentBackground, True)
        sub_balance.setWindowFlags(sub_balance.windowFlags() | Qt.FramelessWindowHint)

        # 核心四大 AI 官方形象
        for cid in ["deepseek", "gpt", "claude", "gemini"]:
            spec = BALANCE_PET_SPECS[cid]
            is_main = (cid == self.pet.character)
            is_active = (is_main or cid in self.extra_pets)
            label = f"召喚 {spec['name']} 餘額寵物" + ("（目前為主寵物）" if is_main else "")
            a = sub_balance.addAction(label)
            a.setCheckable(True)
            a.setChecked(is_active)
            if is_main:
                a.setEnabled(False)
            else:
                a.triggered.connect(
                    lambda chk=False, c_id=cid: self.summon_balance_pet(c_id) if chk else self.dismiss_balance_pet(c_id)
                )

        sub_balance.addSeparator()
        sub_balance.addAction("召喚全部 4 隻核心餘額寵物").triggered.connect(self.summon_all_balance_pets)
        sub_balance.addAction("移除全部額外餘額寵物").triggered.connect(self.dismiss_all_balance_pets)

        # 大寵物在場數量上限檔位 (5, 10, 15, 20, 25, 30 隻)
        from .config import get_effective_pet_max_count, PET_MAX_COUNT_OPTIONS
        pet_limit = get_effective_pet_max_count(self.cfg)
        sub_pet_limit = m.addMenu(f"大寵物數量上限（目前：{pet_limit} 隻）")
        sub_pet_limit.setStyleSheet(m.styleSheet())
        sub_pet_limit.setAttribute(Qt.WA_TranslucentBackground, True)
        sub_pet_limit.setWindowFlags(sub_pet_limit.windowFlags() | Qt.FramelessWindowHint)
        perf_mode = bool(self.cfg.get("performance_mode", False))
        for opt in PET_MAX_COUNT_OPTIONS:
            is_active = (pet_limit == opt)
            label = f"{opt} 隻" + ("（目前生效）" if is_active else "")
            if perf_mode and opt > 10:
                label += "（效能模式開啟時最高限制 10 隻）"
            a = sub_pet_limit.addAction(label)
            a.setCheckable(True)
            a.setChecked(is_active)
            if perf_mode and opt > 10:
                a.setEnabled(False)
            else:
                a.triggered.connect(lambda _=False, count=opt: self.set_pet_max_count(count))

        # 當前寵物監視目標與 API Key 設定（外觀與監控完全解耦）
        from .balance import SUPPORTED_BALANCE_PROVIDERS
        pet_target_prov = cur_pet.ledger.provider_display_name if (cur_pet and cur_pet.ledger) else "DeepSeek"
        sub_target = m.addMenu(f"當前寵物監視目標與金鑰（{pet_target_prov}）")
        sub_target.setStyleSheet(m.styleSheet())
        sub_target.setAttribute(Qt.WA_TranslucentBackground, True)
        sub_target.setWindowFlags(sub_target.windowFlags() | Qt.FramelessWindowHint)

        cur_p_id = cur_pet.pet_id if (cur_pet and cur_pet.is_extra) else "main"
        m_prov_pick = sub_target.addMenu(f"切換監視廠商（目前：{pet_target_prov}）")
        m_prov_pick.setStyleSheet(m.styleSheet())
        m_prov_pick.setAttribute(Qt.WA_TranslucentBackground, True)
        m_prov_pick.setWindowFlags(m_prov_pick.windowFlags() | Qt.FramelessWindowHint)
        for prov in SUPPORTED_BALANCE_PROVIDERS:
            pname = id_to_provider_name(prov)
            a = m_prov_pick.addAction(pname)
            a.setCheckable(True)
            a.setChecked(provider_to_id(cur_pet.ledger.provider) == provider_to_id(prov))
            a.triggered.connect(lambda _=False, p=prov: self.set_pet_monitor(cur_p_id, p, cur_pet.ledger.key_index))

        cur_prov_keys = self.cfg.get_api_keys(cur_pet.ledger.provider) if hasattr(self.cfg, "get_api_keys") else []
        m_key_pick = sub_target.addMenu(f"切換監視 API Key（配置 {len(cur_prov_keys)} 組）")
        m_key_pick.setStyleSheet(m.styleSheet())
        m_key_pick.setAttribute(Qt.WA_TranslucentBackground, True)
        m_key_pick.setWindowFlags(m_key_pick.windowFlags() | Qt.FramelessWindowHint)
        a_kall = m_key_pick.addAction("預設 / 全部 Key 輪替")
        a_kall.setCheckable(True)
        a_kall.setChecked(cur_pet.ledger.key_index is None)
        a_kall.triggered.connect(lambda: self.set_pet_monitor(cur_p_id, cur_pet.ledger.provider, None))
        for kidx, k in enumerate(cur_prov_keys):
            masked = k[:6] + "..." + k[-4:] if len(k) > 12 else k
            label = f"Key #{kidx + 1} ({masked})"
            a_k = m_key_pick.addAction(label)
            a_k.setCheckable(True)
            a_k.setChecked(cur_pet.ledger.key_index == kidx)
            a_k.triggered.connect(lambda _=False, idx=kidx: self.set_pet_monitor(cur_p_id, cur_pet.ledger.provider, idx))

        act_agg = sub_target.addAction("同廠商多 Key 額度整合計算")
        act_agg.setCheckable(True)
        act_agg.setChecked(bool(self.cfg.get("aggregate_same_provider_keys", False)))
        act_agg.triggered.connect(lambda chk: self.set_aggregate_same_provider_keys(chk))

        if cur_pet.is_extra:
            m.addAction(f"移除此額外寵物 ({cur_pet.character})").triggered.connect(
                lambda: self.dismiss_balance_pet(cur_pet.pet_id)
            )
            m.addSeparator()

        # Q 版小人巡邏隊（在場 X/上限）
        if hasattr(self, "chibi_manager") and self.chibi_manager:
            cur_chibi_count = self.chibi_manager.active_count
            max_chibi_limit = self.chibi_manager.max_count
            sub_chibi = m.addMenu(f"Q 版小人巡邏隊（在場 {cur_chibi_count}/{max_chibi_limit}）")
            sub_chibi.setStyleSheet(m.styleSheet())
            sub_chibi.setAttribute(Qt.WA_TranslucentBackground, True)
            sub_chibi.setWindowFlags(sub_chibi.windowFlags() | Qt.FramelessWindowHint)

            # 1. 隨機召喚一隻 Q 版人物
            act_rand = sub_chibi.addAction("隨機召喚一隻 Q 版人物")
            act_rand.triggered.connect(self.summon_random_chibi)

            # 2. 指定召喚子選單
            sub_specific = sub_chibi.addMenu("指定召喚")
            sub_specific.setStyleSheet(m.styleSheet())
            sub_specific.setAttribute(Qt.WA_TranslucentBackground, True)
            sub_specific.setWindowFlags(sub_specific.windowFlags() | Qt.FramelessWindowHint)

            from .pixel_chibi import PixelChibiRegistry
            for cid, info in PixelChibiRegistry.list_official_characters().items():
                label = f"{info['name']}"
                if info.get("subtitle"):
                    label += f" ({info['subtitle']})"
                a = sub_specific.addAction(label)
                a.triggered.connect(lambda _=False, c=cid: self.summon_chibi(c))

            custom_chars = PixelChibiRegistry.list_custom_characters()
            if custom_chars:
                sub_specific.addSeparator()
                for cid, info in custom_chars.items():
                    w = info.get("width", 16)
                    h = info.get("height", 24)
                    size_tag = f" [{w}x{h}]" if (w != 16 or h != 24) else ""
                    label = f"{info.get('name', cid)}{size_tag}"
                    a = sub_specific.addAction(label)
                    a.triggered.connect(lambda _=False, c=cid: self.summon_chibi(c))

            # 3. 召喚特定 API 額度監控 Q 版小人
            sub_api_chibi = sub_chibi.addMenu("召喚特定 API 額度監控 Q 版小人")
            sub_api_chibi.setStyleSheet(m.styleSheet())
            sub_api_chibi.setAttribute(Qt.WA_TranslucentBackground, True)
            sub_api_chibi.setWindowFlags(sub_api_chibi.windowFlags() | Qt.FramelessWindowHint)
            for prov in SUPPORTED_BALANCE_PROVIDERS:
                pname = id_to_provider_name(prov)
                a_api = sub_api_chibi.addAction(f"召喚【{pname}】額度小人")
                a_api.triggered.connect(lambda _=False, p=prov: self.summon_api_chibi(p))

            sub_chibi.addSeparator()

            # 4. 開啟 Q 版人物像素編輯器...
            sub_chibi.addAction("開啟 Q 版人物像素編輯器...").triggered.connect(self.open_chibi_editor)

            # 5. 清除場上所有額外 Q 版小人（只保留 1 隻）
            act_clear_extra = sub_chibi.addAction("清除場上所有額外 Q 版小人（只保留 1 隻）")
            act_clear_extra.setEnabled(cur_chibi_count > 1)
            act_clear_extra.triggered.connect(self.clear_extra_chibis)

            # 5.5 允許地面走動（漫遊模式）開關
            act_walk = sub_chibi.addAction("允許地面自由走動")
            act_walk.setCheckable(True)
            act_walk.setChecked(bool(self.cfg.get("q_chibi_allow_walk", True)))
            act_walk.triggered.connect(lambda chk: self.set_q_chibi_allow_walk(chk))

            # 6. 上限檔位切換子選單 (5, 10, 15, 20, 25, 30)
            sub_limit = sub_chibi.addMenu(f"在場數量上限（目前：{max_chibi_limit} 隻）")
            sub_limit.setStyleSheet(m.styleSheet())
            sub_limit.setAttribute(Qt.WA_TranslucentBackground, True)
            sub_limit.setWindowFlags(sub_limit.windowFlags() | Qt.FramelessWindowHint)
            perf_mode = bool(self.cfg.get("performance_mode", False))
            for opt in (5, 10, 15, 20, 25, 30):
                is_active = (max_chibi_limit == opt)
                label = f"{opt} 隻" + ("（目前生效）" if is_active else "")
                if perf_mode and opt > 10:
                    label += "（效能模式開啟時最高限制 10 隻）"
                a = sub_limit.addAction(label)
                a.setCheckable(True)
                a.setChecked(is_active)
                if perf_mode and opt > 10:
                    a.setEnabled(False)
                else:
                    a.triggered.connect(lambda _=False, count=opt: self.set_q_chibi_max_count(count))

            m.addSeparator()

        act("滑鼠穿透", self.set_click_through, c["click_through"])
        act("自動貼邊", self.set_auto_snap, c["auto_snap"])
        act("回到角落", lambda: self.go_corner(c["snap_corner"]))

        # 寵物旋轉角度子選單
        cur_rot_val = int(round(getattr(cur_pet, "rotation_angle", 0.0))) % 360
        sub_rot = m.addMenu(f"旋轉角度 (當前: {cur_rot_val}°)")
        sub_rot.setStyleSheet(m.styleSheet())
        sub_rot.setAttribute(Qt.WA_TranslucentBackground, True)
        sub_rot.setWindowFlags(sub_rot.windowFlags() | Qt.FramelessWindowHint)

        sub_rot.addAction("向左旋轉 15°").triggered.connect(lambda: self.rotate_pet_by(-15.0, pet=cur_pet))
        sub_rot.addAction("向右旋轉 15°").triggered.connect(lambda: self.rotate_pet_by(15.0, pet=cur_pet))
        sub_rot.addAction("向左旋轉 90°").triggered.connect(lambda: self.rotate_pet_by(-90.0, pet=cur_pet))
        sub_rot.addAction("向右旋轉 90°").triggered.connect(lambda: self.rotate_pet_by(90.0, pet=cur_pet))
        sub_rot.addSeparator()
        sub_rot.addAction("重置為 0° (正立)").triggered.connect(lambda: self.reset_pet_rotation(pet=cur_pet))
        sub_rot.addAction("自由旋轉...").triggered.connect(lambda: self.open_rotation_slider_dialog(pet=cur_pet))

        # 水平鏡像翻轉
        act_mirror = m.addAction("水平鏡像翻轉")
        act_mirror.triggered.connect(lambda: self.toggle_pet_mirror(pet=cur_pet))

        # 【大破壞！？】玩家即時互動破壞模式（純視覺效果，絕無破壞）
        sub_destruct = m.addMenu("【大破壞！？】(純視覺互動)")
        sub_destruct.setStyleSheet(m.styleSheet())
        sub_destruct.setAttribute(Qt.WA_TranslucentBackground, True)
        sub_destruct.setWindowFlags(sub_destruct.windowFlags() | Qt.FramelessWindowHint)

        act_play_mode = sub_destruct.addAction("開啟大破壞互動模式 (玩具箱)...")
        act_play_mode.triggered.connect(self.start_interactive_destruction_mode)

        act_des_toggle = sub_destruct.addAction("允許大破壞視覺效果")
        act_des_toggle.setCheckable(True)
        act_des_toggle.setChecked(bool(self.cfg.get("destruction_fx_enabled", False)))
        act_des_toggle.triggered.connect(lambda chk: self.set_destruction_fx_enabled(chk))
        sub_destruct.addSeparator()

        sub_destruct.addAction("充氣大鐵錘 (咚～！)").triggered.connect(
            lambda: self.trigger_destruction_effect("hammer")
        )
        sub_destruct.addAction("放置定時炸彈 (砰～！)").triggered.connect(
            lambda: self.trigger_destruction_effect("bomb")
        )
        sub_destruct.addSeparator()
        sub_destruct.addAction("一鍵修復海綿 (Esc 清除)").triggered.connect(self.clear_destruction_effects)
        act("聲音開關", self.set_sound, c["sound"])
        act(
            "模式：" + ("模擬" if c["mode"] == "sim" else "API") + "（點此切換）",
            lambda: self.set_mode("api" if c["mode"] == "sim" else "sim"),
        )
        if not tray:
            act("隱藏寵物", self.hide_pet)
        else:
            act("顯示寵物" if not self.pet.isVisible() else "隱藏寵物", self.toggle_pet_visible)
        m.addSeparator()
        act("退出程式", self.quit)

    def hide_pet(self):
        self.pet.hide()
        self.pet.props.hide_all()
        self.sounds.set_muted(True)
        for ep in self.extra_pets.values():
            ep.hide()
            ep.props.hide_all()
        self._changed()

    def show_pet(self):
        self.pet.show()
        self.pet.props.show_all()
        self.sounds.set_muted(False)
        for ep in self.extra_pets.values():
            ep.show()
            ep.props.show_all()
        self._changed()

    def toggle_pet_visible(self):
        if self.pet.isVisible():
            self.hide_pet()
        else:
            self.show_pet()

    def clamp_to_screen(self, win: QWidget, target_x: int, target_y: int, scr=None) -> tuple[int, int]:
        target_scr = scr or QGuiApplication.screenAt(self.pet.frameGeometry().center()) or QGuiApplication.primaryScreen()
        geo = target_scr.availableGeometry() if target_scr else QGuiApplication.primaryScreen().availableGeometry()
        w = win.width()
        h = win.height()
        x = max(geo.left() + 16, min(target_x, geo.right() - w - 16))
        y = max(geo.top() + 16, min(target_y, geo.bottom() - h - 16))
        return x, y

    def _center_and_raise(self, win: QWidget):
        scr = QGuiApplication.screenAt(self.pet.frameGeometry().center()) or QGuiApplication.primaryScreen()
        geo = scr.availableGeometry() if scr else QGuiApplication.primaryScreen().availableGeometry()
        w = win.width()
        h = win.height()
        cx = geo.x() + (geo.width() - w) // 2
        cy = geo.y() + (geo.height() - h) // 2
        x, y = self.clamp_to_screen(win, cx, cy, scr=scr)
        win.move(x, y)
        win.show()
        win.raise_()
        win.activateWindow()
        try:
            winapi.set_topmost(int(win.winId()), True)
        except Exception:
            pass

    def set_pet_rotation_angle(self, angle: float, pet: PetWindow | None = None):
        target = pet or self.pet
        target.set_rotation_angle(angle)
        self._changed()

    def rotate_pet_by(self, delta: float, pet: PetWindow | None = None):
        target = pet or self.pet
        target.rotate_by(delta)
        self._changed()

    def reset_pet_rotation(self, pet: PetWindow | None = None):
        target = pet or self.pet
        target.reset_rotation()
        self._changed()

    def toggle_pet_mirror(self, pet: PetWindow | None = None):
        target = pet or self.pet
        target.toggle_mirror()
        self._changed()

    def open_rotation_slider_dialog(self, pet: PetWindow | None = None):
        from .pet_rotator import PetRotationDialog
        target = pet or self.pet
        dlg = PetRotationDialog(target)
        dlg.exec()

    def set_destruction_fx_enabled(self, enabled: bool):
        self.cfg.set("destruction_fx_enabled", bool(enabled), save=True)
        if not enabled and hasattr(self, "destruction_overlay"):
            self.destruction_overlay.stop_interactive_mode()
        self._changed()

    def start_interactive_destruction_mode(self):
        if hasattr(self, "destruction_overlay"):
            self.destruction_overlay.start_interactive_mode()

    def stop_interactive_destruction_mode(self):
        if hasattr(self, "destruction_overlay"):
            self.destruction_overlay.stop_interactive_mode()

    def trigger_destruction_effect(self, effect_type: str, pos=None):
        if not hasattr(self, "destruction_overlay"):
            return
        if effect_type == "bomb":
            self.destruction_overlay.trigger_cartoon_bomb(pos)
        elif effect_type in ("hammer", "chibi_hammer"):
            self.destruction_overlay.trigger_chibi_hammer(pos)
        elif effect_type == "giant_hammer":
            self.destruction_overlay.trigger_giant_hammer(pos)
        try:
            if hasattr(self, "sounds") and self.sounds:
                self.sounds.play("hit")
        except Exception:
            pass

    def clear_destruction_effects(self):
        if hasattr(self, "destruction_overlay"):
            self.destruction_overlay.clear_all_effects()


    def pet_menu(self, gpos: QPoint, pet: PetWindow | None = None):
        target = pet or self.pet
        m = QMenu()
        theme = self.cfg.get("theme", "light")
        m.setStyleSheet(get_menu_qss(theme))
        m.setAttribute(Qt.WA_TranslucentBackground, True)
        m.setWindowFlags(m.windowFlags() | Qt.FramelessWindowHint)
        self._fill_menu(m, pet=target)
        self._active_menu = m
        if "--selftest" in sys.argv or any("selftest" in arg for arg in sys.argv):
            QTimer.singleShot(10, m.close)
        QTimer.singleShot(0, lambda: m.exec(gpos))

    def prop_menu(self, prop, gpos: QPoint):
        m = QMenu()
        theme = self.cfg.get("theme", "light")
        m.setStyleSheet(get_menu_qss(theme))
        m.setAttribute(Qt.WA_TranslucentBackground, True)
        m.setWindowFlags(m.windowFlags() | Qt.FramelessWindowHint)
        cur_sym = "¥" if self.ledger.currency == "CNY" else "$"
        if prop.kind == "rice":
            m.addAction(f"清除此飯盆（{cur_sym}{prop.amount:.2f} 入帳）").triggered.connect(
                lambda: self._clear_prop(prop)
            )
            total_amount = sum(p.amount for p in self.pet.props.rice() if not p.dead)
            for ep in self.extra_pets.values():
                total_amount += sum(p.amount for p in ep.props.rice() if not p.dead)
            m.addAction(f"清除場上全部飯盆（全部金額 {cur_sym}{total_amount:.2f} 自動入帳）").triggered.connect(
                self.clear_all_rice_bowls
            )
        else:
            m.addAction("清除此鐵盆").triggered.connect(lambda: self._clear_prop(prop))
            m.addAction("清除場上全部鐵盆").triggered.connect(self.clear_all_iron_bowls)
        self._active_menu = m
        if "--selftest" in sys.argv or any("selftest" in arg for arg in sys.argv):
            QTimer.singleShot(10, m.close)
        QTimer.singleShot(0, lambda: m.exec(gpos))
        self._active_menu = m
        if "--selftest" in sys.argv or any("selftest" in arg for arg in sys.argv):
            QTimer.singleShot(10, m.close)
        QTimer.singleShot(0, lambda: m.exec(gpos))

    def _clear_prop(self, prop):
        if prop.kind == "rice":
            self.ledger.apply_credit(prop.amount)
        for pet in [self.pet] + list(self.extra_pets.values()):
            if prop in pet.props.props:
                pet.props.remove(prop)

    def clear_all_rice_bowls(self):
        total = 0.0
        for pet in [self.pet] + list(self.extra_pets.values()):
            total += pet.props.clear_all_rice()
        if total > 0:
            self.ledger.apply_credit(total)
            cur_sym = "¥" if self.ledger.currency == "CNY" else "$"
            now = time.monotonic()
            self.pet.floaters.append([f"已清除全部飯盆 (+{cur_sym}{total:.2f})", QColor(60, 220, 110), 0, now])
            self.pet.wake()

    def clear_all_iron_bowls(self):
        count = 0
        for pet in [self.pet] + list(self.extra_pets.values()):
            count += pet.props.clear_all_iron()
        if count > 0:
            now = time.monotonic()
            self.pet.floaters.append([f"已清除場上 {count} 個鐵盆", QColor(140, 220, 255), 0, now])
            self.pet.wake()

    def _tray_activated(self, reason):
        if reason in (QSystemTrayIcon.DoubleClick, QSystemTrayIcon.Trigger):
            self.open_settings()

    def open_settings(self):
        try:
            self.show_qml_panel()
        except Exception as e:
            log(f"開啟 QML 設定視窗失敗，改開啟控制台: {e}")
            self.show_panel()

    def show_panel(self):
        if self.panel is None:
            self.panel = ControlPanel(self)
        self._center_and_raise(self.panel)

    def show_qml_panel(self, tab: int | None = None):
        if self.qml_panel is None:
            self.qml_panel = QmlControlWindow(self)
        if tab is not None:
            self.qml_panel.switch_tab(tab)
        self._center_and_raise(self.qml_panel)

    # ------------------------------------------------------------- Dialog openers
    def open_char_picker(self):
        self.show_qml_panel(tab=0)

    def open_sound_library(self):
        self.show_qml_panel(tab=1)

    def open_tutorial(self):
        self.cfg.set("tutorial_shown", True)
        from .tutorial import TutorialDialog
        if self._tutorial_dlg is None or not self._tutorial_dlg.isVisible():
            parent = self.panel if (self.panel and self.panel.isVisible()) else None
            self._tutorial_dlg = TutorialDialog(parent, theme=self.cfg.get("theme", "dark"))
            self._center_and_raise(self._tutorial_dlg)
        else:
            self._center_and_raise(self._tutorial_dlg)

    def open_web_ui(self):
        if self.web and self.web.url:
            webbrowser.open(self.web.url)

    # ------------------------------------------------------------- setters
    def _changed(self):
        self.state_changed.emit()

    def set_character(self, cid: str):
        self.cfg.set("character", cid)
        self.pet.set_character(cid)
        if hasattr(self, "chibi_manager") and self.chibi_manager and self.chibi_manager.chibis:
            for c in self.chibi_manager.chibis:
                try:
                    c.set_character(cid)
                except Exception:
                    pass
        elif hasattr(self, "pixel_chibi") and self.pixel_chibi:
            try:
                self.pixel_chibi.set_character(cid)
            except Exception:
                pass
        # If this character was in extra pets, remove it from extra pets
        if cid in self.extra_pets:
            self.dismiss_balance_pet(cid)
        self._changed()

    def set_variant(self, var: str):
        self.cfg.set("variant", var)
        self.pet.set_variant(var)
        self._changed()

    def set_strict_custom_image_ratio(self, val: bool):
        self.cfg.set("strict_custom_image_ratio", bool(val))
        if hasattr(self.pet, "set_strict_custom_image_ratio"):
            self.pet.set_strict_custom_image_ratio(bool(val))
        for ep in self.extra_pets.values():
            if hasattr(ep, "set_strict_custom_image_ratio"):
                ep.set_strict_custom_image_ratio(bool(val))
        self._changed()

    def set_click_through(self, on: bool):
        self.cfg.set("click_through", bool(on))
        self.pet.apply_click_through(bool(on))
        for ep in self.extra_pets.values():
            ep.apply_click_through(bool(on))
        self._changed()

    def set_auto_snap(self, on: bool):
        self.cfg.set("auto_snap", bool(on))
        if on:
            self.pet.snap_now()
            for ep in self.extra_pets.values():
                ep.snap_now()
        self._changed()

    def set_snap_distance(self, v: int):
        self.cfg.set("snap_distance", int(v))
        self._changed()

    def go_corner(self, corner: str):
        self.cfg.set("snap_corner", corner)
        self.pet.snap_now(force_corner=True)
        self._changed()

    def set_topmost(self, on: bool):
        self.cfg.set("always_on_top", bool(on))
        winapi.set_topmost(int(self.pet.winId()), bool(on))
        for ep in self.extra_pets.values():
            winapi.set_topmost(int(ep.winId()), bool(on))
        self._changed()

    def set_pat(self, on: bool):
        self.cfg.set("pat", bool(on))
        if not on:
            self.pet.end_pat()
            for ep in self.extra_pets.values():
                ep.end_pat()
        self._changed()

    def set_pet_opacity(self, v: int):
        self.set_opacity(v)

    def set_opacity(self, v: int):
        v = max(20, min(100, int(v)))
        self.cfg.set("pet_opacity", v, save=False)
        self.cfg.set("opacity", v, save=True)
        op = max(0.2, min(1.0, float(v) / 100.0))
        self.pet.setWindowOpacity(op)
        for ep in self.extra_pets.values():
            ep.setWindowOpacity(op)
        self._changed()

    def set_q_chibi_opacity(self, v: int):
        v = max(20, min(100, int(v)))
        self.cfg.set("q_chibi_opacity", v, save=True)
        if hasattr(self, "chibi_manager") and self.chibi_manager:
            self.chibi_manager.sync_opacity(v)
        elif hasattr(self, "pixel_chibi") and self.pixel_chibi:
            self.pixel_chibi.setWindowOpacity(float(v) / 100.0)
        self._changed()

    def set_custom_pet_crop_mode(self, mode: str):
        if mode in ("crop", "fit", "free"):
            self.cfg.set("custom_pet_crop_mode", mode, save=True)
            self.cfg.set("strict_custom_image_ratio", (mode != "free"), save=True)
            if hasattr(self.pet, "set_custom_pet_crop_mode"):
                self.pet.set_custom_pet_crop_mode(mode)
            for ep in self.extra_pets.values():
                if hasattr(ep, "set_custom_pet_crop_mode"):
                    ep.set_custom_pet_crop_mode(mode)
            self._changed()

    def set_size(self, px: int):
        self.pet.set_size(px)
        for ep in self.extra_pets.values():
            ep.set_size(px)
        self._changed()

    def set_q_chibi_enabled(self, on: bool):
        self.cfg.set("q_chibi_enabled", bool(on), save=True)
        if hasattr(self, "chibi_manager") and self.chibi_manager:
            self.chibi_manager.set_enabled(on)
            self.pixel_chibi = self.chibi_manager.primary_chibi
        elif on:
            from .pixel_chibi import PixelChibiManager
            self.chibi_manager = PixelChibiManager(self.cfg, self.sounds, pet=self.pet, app=self)
            self.pixel_chibi = self.chibi_manager.primary_chibi
            if self.pet:
                self.pet.pixel_chibi = self.pixel_chibi
        self._changed()

    def summon_random_chibi(self):
        if hasattr(self, "chibi_manager") and self.chibi_manager:
            cur = self.chibi_manager.active_count
            limit = self.chibi_manager.max_count
            force = False
            if cur >= limit:
                msg = f"目前在場 Q 版小人已達數量上限 ({cur}/{limit} 隻)，建議收回部分小人以維持最佳系統效能，或至設定中調高上限檔位！是否仍要繼續召喚？"
                log(f"[App] {msg}")
                if "--selftest" not in sys.argv:
                    from .dialogs import ModernMessageBox
                    ans = ModernMessageBox.question(None, "數量上限提醒", msg)
                    if ans != ModernMessageBox.Yes:
                        return None
                force = True
            return self.chibi_manager.summon_random(force=force)

    def summon_chibi(self, cid: str):
        if hasattr(self, "chibi_manager") and self.chibi_manager:
            cur = self.chibi_manager.active_count
            limit = self.chibi_manager.max_count
            force = False
            if cur >= limit:
                msg = f"目前在場 Q 版小人已達數量上限 ({cur}/{limit} 隻)，建議收回部分小人以維持最佳系統效能，或至設定中調高上限檔位！是否仍要繼續召喚？"
                log(f"[App] {msg}")
                if "--selftest" not in sys.argv:
                    from .dialogs import ModernMessageBox
                    ans = ModernMessageBox.question(None, "數量上限提醒", msg)
                    if ans != ModernMessageBox.Yes:
                        return None
                force = True
            return self.chibi_manager.summon(cid, force=force)

    def clear_extra_chibis(self):
        if hasattr(self, "chibi_manager") and self.chibi_manager:
            self.chibi_manager.clear_extra_chibis()

    def set_q_chibi_allow_walk(self, on: bool):
        self.cfg.set("q_chibi_allow_walk", bool(on), save=True)
        if hasattr(self, "chibi_manager") and self.chibi_manager:
            for c in self.chibi_manager.chibis:
                if not on and not self.cfg.get("q_chibi_ceiling_mode", False) and not self.cfg.get("q_chibi_four_edges_floor_mode", False):
                    if c.state in ("walk", "run"):
                        c.state = "idle"
                        c.vel_x = 0.0
                        c.state_time = 0.0
                        c.update()
        self._changed()

    def set_q_chibi_max_count(self, count: int):
        self.cfg.set("q_chibi_max_count", int(count), save=True)
        if hasattr(self, "chibi_manager") and self.chibi_manager:
            self.chibi_manager.enforce_limit()
        self._changed()

    def open_chibi_editor(self):
        from .chibi_editor import ChibiPixelEditorDialog
        if not hasattr(self, "chibi_editor_dialog") or not self.chibi_editor_dialog or not self.chibi_editor_dialog.isVisible():
            self.chibi_editor_dialog = ChibiPixelEditorDialog(parent=None, cfg=self.cfg, app=self)
            self._center_and_raise(self.chibi_editor_dialog)
        else:
            self.chibi_editor_dialog.show()
            self.chibi_editor_dialog.raise_()
            self.chibi_editor_dialog.activateWindow()

    def set_q_climb_windows(self, on: bool):
        self.cfg.set("q_climb_windows", bool(on), save=True)
        self._changed()

    def set_q_flight_prop(self, on: bool):
        self.cfg.set("q_flight_prop", bool(on), save=True)
        self._changed()

    def set_q_fireworks_prop(self, on: bool):
        self.cfg.set("q_fireworks_prop", bool(on), save=True)
        self._changed()

    def set_theme(self, t: str):
        self.cfg.set("theme", t)
        if self.panel:
            self.panel.apply_theme()
        if self.qml_panel:
            self.qml_panel.apply_theme()
        if self.chat_dialog:
            self.chat_dialog.apply_theme(t)
        if hasattr(self, "tray_menu") and self.tray_menu:
            self.tray_menu.setStyleSheet(get_menu_qss(t))
        self._changed()

    # 效能、FPS、垂直同步與渲染後端配置
    def set_disable_transparency(self, on: bool):
        self.cfg.set("disable_transparency", bool(on))
        self.pet.set_disable_transparency(bool(on))
        for ep in self.extra_pets.values():
            ep.set_disable_transparency(bool(on))
        self._changed()

    def set_disable_blur(self, on: bool):
        self.cfg.set("disable_blur", bool(on))
        self._changed()

    def set_animations_enabled(self, on: bool):
        self.cfg.set("animations_enabled", bool(on))
        self.pet.update_fps_timer()
        for ep in self.extra_pets.values():
            ep.update_fps_timer()
        self._changed()

    def set_performance_mode(self, on: bool):
        self.cfg.set("performance_mode", bool(on))
        self.pet.update_fps_timer()
        for ep in self.extra_pets.values():
            ep.update_fps_timer()
        if hasattr(self, "chibi_manager") and self.chibi_manager:
            self.chibi_manager.sync_fps()
        elif hasattr(self, "pixel_chibi") and self.pixel_chibi:
            try:
                self.pixel_chibi.sync_fps()
            except Exception:
                pass
        if hasattr(self, "chibi_manager") and self.chibi_manager:
            self.chibi_manager.sync_fps()
            self.chibi_manager.enforce_limit()
        self._changed()

    def set_target_fps(self, fps: int):
        self.cfg.set("target_fps", int(fps))
        self.pet.update_fps_timer()
        for ep in self.extra_pets.values():
            ep.update_fps_timer()
        if hasattr(self, "chibi_manager") and self.chibi_manager:
            self.chibi_manager.sync_fps()
        elif hasattr(self, "pixel_chibi") and self.pixel_chibi:
            try:
                self.pixel_chibi.sync_fps()
            except Exception:
                pass
        self._changed()

    def set_vsync_mode(self, mode: int):
        self.cfg.set("vsync_mode", int(mode))
        self._changed()

    def set_rendering_backend(self, backend: str):
        self.cfg.set("rendering_backend", str(backend).strip().lower())
        self._changed()

    def set_privacy_mode(self, on: bool):
        self.cfg.set("privacy_mode", bool(on))
        self._changed()

    def set_custom_system_prompt(self, prompt: str):
        self.cfg.set("custom_system_prompt", str(prompt).strip())
        self._changed()

    def set_sound(self, on: bool):
        self.cfg.set("sound", bool(on))
        self.sounds.apply()
        self._changed()

    def set_volume(self, v: int):
        self.cfg.set("volume", int(v))
        self.sounds.apply()
        self._changed()

    def set_mode(self, mode: str):
        if self.cfg["mode"] == mode:
            return
        self.cfg.set("mode", mode)
        self.pet.props.clear("rice")
        self.ledger.apply_mode()
        for el in self.extra_ledgers.values():
            el.apply_mode()
        self.pet.page = self.pet.page
        for ep in self.extra_pets.values():
            ep.page = ep.page
        self._changed()

    def set_sim_auto(self, on: bool):
        self.cfg.set("sim_auto", bool(on))
        if self.cfg["mode"] == "sim":
            self.ledger.apply_mode()
            for el in self.extra_ledgers.values():
                el.apply_mode()
        self._changed()

    def quit(self):
        self._cleanup()
        self.tray.hide()
        self.qapp.quit()
