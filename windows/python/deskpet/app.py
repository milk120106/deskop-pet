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
from .config import Config, asset, log
from .dialogs import CharPickerDialog, SoundLibraryDialog
from .panel import ControlPanel
from .pet import PetWindow
from .web import WebServer

MAX_CHARS = 8


class _DummyQCharManager:
    """Q版角色功能重構過渡期解耦佔位器。"""

    def __init__(self, *args, **kwargs):
        self.menu_cb = None
        self.chars: list = []

    def restore(self):
        pass

    def hide_all(self):
        pass

    def show_all(self):
        pass

    def set_click_through(self, on: bool):
        pass

    def apply_topmost(self):
        pass

    def set_dark_mode(self, on: bool):
        pass

    def remove_all(self):
        pass

    def remove(self, ch):
        pass

    def toggle_one(self, ch):
        pass

    def list_custom_q(self) -> list[str]:
        return []

    def import_custom_q(self, name: str, source_path: str):
        return False, "Q 版角色功能目前暫時停用並進行重構升級中，敬請期待後續版本開放！"

    def delete_custom_q(self, name: str):
        pass

BALANCE_PET_SPECS = {
    "deepseek": {"name": "DeepSeek", "title": "DeepSeek 餘額", "prov": "deepseek"},
    "claude": {"name": "Claude", "title": "Claude 餘額", "prov": "anthropic"},
    "gpt": {"name": "OpenAI", "title": "OpenAI 餘額", "prov": "openai"},
    "gemini": {"name": "Gemini", "title": "Gemini 餘額", "prov": "gemini"},
}


class App(QObject):
    state_changed = Signal()

    def __init__(self, qapp: QApplication):
        super().__init__()
        self.qapp = qapp
        self.cfg = Config()
        from .font_manager import init_app_font
        init_app_font(self.cfg)
        self.sounds = Sounds(self.cfg)
        self.ledger = Ledger(self.cfg)
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

        self.qchars = _DummyQCharManager()
        self.qchars.menu_cb = self.q_menu
        self.pet.props._menu_cb = self.prop_menu
        self.pet.context_requested.connect(lambda gpos: self.pet_menu(gpos, pet=self.pet))
        self.panel: ControlPanel | None = None

        # Start background WebServer (default port 8765..8775)
        self.web = WebServer(self)

        self.tray = QSystemTrayIcon(QIcon(asset("tray.ico")), self)
        self.tray.setToolTip("Desktop Pet")
        self.tray_menu = QMenu()
        self.tray_menu.aboutToShow.connect(lambda: self._fill_menu(self.tray_menu, tray=True))
        self.tray.setContextMenu(self.tray_menu)
        self.tray.activated.connect(self._tray_activated)
        self.tray.show()

        self.pet.place_initial()
        self.pet.show()
        self.qchars.restore()
        self._restore_extra_pets()
        self._tutorial_dlg = None
        if not self.cfg.get("tutorial_shown", False) and "--selftest" not in sys.argv:
            QTimer.singleShot(600, self.open_tutorial)
        qapp.aboutToQuit.connect(self._cleanup)

    def _cleanup(self):
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

    # ------------------------------------------------------------- Multi-pet Balance Management
    def _restore_extra_pets(self):
        saved = self.cfg.get("extra_pets") or []
        for cid in saved:
            if cid in BALANCE_PET_SPECS and cid != self.pet.character:
                self.summon_balance_pet(cid, save=False)

    def summon_balance_pet(self, cid: str, save: bool = True) -> PetWindow | None:
        if cid in self.extra_pets:
            win = self.extra_pets[cid]
            win.show()
            win.raise_()
            win.activateWindow()
            return win

        if cid not in BALANCE_PET_SPECS:
            return None

        spec = BALANCE_PET_SPECS[cid]
        ledger = Ledger(self.cfg, provider_override=spec["prov"])
        pet = PetWindow(self.cfg, ledger, self.sounds, character_override=cid, is_extra=True, pet_id=cid)
        pet.props._menu_cb = self.prop_menu
        pet.context_requested.connect(lambda gpos, p=pet: self.pet_menu(gpos, pet=p))

        idx = len(self.extra_pets) + 1
        offset_x = -idx * 260
        pet.place_initial(default_offset_x=offset_x)

        # Apply current global options
        pet.setWindowOpacity(max(0.2, min(1.0, int(self.cfg.get("opacity", 100)) / 100.0)))
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
        self._center_and_raise(self.chat_dialog)

    def start_pure_voice(self, target_pet: PetWindow | None = None):
        """啟動 Gemini Live 純語音即時連線（絕不彈出文字對話框）。"""
        cur_pet = target_pet or self.pet
        self.pure_voice_pet = cur_pet

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
            return

        # 2. 檢查音訊輸入裝置
        try:
            import sounddevice as sd
            devs = sd.query_devices()
            has_input = any(d.get("max_input_channels", 0) > 0 for d in devs)
            if not has_input:
                cur_pet.show_speech_bubble("未檢測到可用的麥克風輸入裝置。")
                return
        except Exception as e:
            cur_pet.show_speech_bubble(f"音訊模組載入失敗：{e}")
            return

        self.pure_voice_active = True
        self._start_pure_voice_listening()

    def _start_pure_voice_listening(self):
        """進入語音聆聽狀態"""
        if not self.pure_voice_active or not self.pure_voice_pet:
            return
        from .chat import VoiceRecorder

        self.pure_voice_pet.show_speech_bubble(
            "純語音模式：正在聆聽...（點擊氣泡可結束）",
            thought=False,
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
            "純語音模式：思考中...（點擊氣泡可結束）",
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
        if data.get("audio"):
            self.pure_voice_pet.sounds.play_file(data["audio"])

        # 顯示頭頂語音氣泡
        self.pure_voice_pet.show_speech_bubble(
            reply,
            thought=False,
            timeout_ms=8000,
            on_click=self.stop_pure_voice,
        )

        # 8.5 秒後若仍處於純語音模式，自動回到聆聽狀態
        QTimer.singleShot(8500, self._check_resume_pure_voice_listening)

    def _check_resume_pure_voice_listening(self):
        if self.pure_voice_active and self.pure_voice_pet:
            self._start_pure_voice_listening()

    def stop_pure_voice(self):
        """關閉純語音模式"""
        self.pure_voice_active = False
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

        act("AI 對話視窗...", lambda: self.open_chat_dialog(target_pet=cur_pet))
        if self.pure_voice_active:
            act("關閉純語音模式 (Gemini Live)", self.stop_pure_voice)
        else:
            act("純語音模式 (Gemini Live)...", lambda: self.start_pure_voice(target_pet=cur_pet))
        m.addSeparator()

        act("控制台", self.show_panel)
        act("角色選擇視窗...", self.open_char_picker)
        act("音效庫設定...", self.open_sound_library)
        act("開啟網頁儀表板", self.open_web_ui)
        m.addSeparator()

        # Multi-pet balance summons
        total_balance_pets = len(self.extra_pets) + (1 if self.pet.character in BALANCE_PET_SPECS else 0)
        sub_balance = m.addMenu(f"餘額寵物管理（在場 {total_balance_pets}/4）")
        for cid, spec in BALANCE_PET_SPECS.items():
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
        sub_balance.addAction("召喚全部 4 隻餘額寵物").triggered.connect(self.summon_all_balance_pets)
        sub_balance.addAction("移除全部額外餘額寵物").triggered.connect(self.dismiss_all_balance_pets)

        if cur_pet.is_extra:
            m.addAction(f"移除此額外寵物 ({cur_pet.character})").triggered.connect(
                lambda: self.dismiss_balance_pet(cur_pet.pet_id)
            )
            m.addSeparator()

        act("滑鼠穿透", self.set_click_through, c["click_through"])
        act("自動貼邊", self.set_auto_snap, c["auto_snap"])
        m.addSeparator()

        sub = m.addMenu("Q 版角色（維護中）")
        a_info = sub.addAction("Q 版角色功能重構升級中（暫時停用）")
        a_info.triggered.connect(self._show_qchars_maintenance_dialog)
        sub.addSeparator()
        a_ds = sub.addAction("新增 Q 版角色")
        a_ds.setEnabled(False)
        a_ds.triggered.connect(self._show_qchars_maintenance_dialog)
        a_custom = sub.addAction("自訂 Q 版角色管理...")
        a_custom.setEnabled(False)
        a_custom.triggered.connect(self._show_qchars_maintenance_dialog)

        sub = m.addMenu("演示 / 道具")
        sub.addAction("扣費 -0.01").triggered.connect(lambda: cur_pet.ledger.sim_charge(1))
        sub.addAction("扣費 -0.10").triggered.connect(lambda: cur_pet.ledger.sim_charge(10))
        sub.addAction("充值 +3.00（掉飯盆）").triggered.connect(lambda: cur_pet.ledger.sim_topup(3.0))
        sub.addAction("打開火控雷達").triggered.connect(cur_pet.props.lock_now)
        sub.addSeparator()
        sub.addAction("清除場上所有飯盆（金額入帳）").triggered.connect(self.clear_all_rice_bowls)
        sub.addAction("清除場上所有鐵盆").triggered.connect(self.clear_all_iron_bowls)
        if cur_pet.iron_worn:
            sub.addAction(f"取下頭頂鐵盆（剩餘 {cur_pet.iron_count} 個）").triggered.connect(
                lambda: cur_pet.remove_iron(all_pots=True)
            )

        sub = m.addMenu("尺寸")
        for name, px in (("中杯 340", 340), ("大杯 454", 454), ("超大杯 624", 624)):
            a = sub.addAction(name)
            a.setCheckable(True)
            a.setChecked(cur_pet.size_px == px)
            a.triggered.connect(lambda _=False, v=px: self.set_size(v))

        m.addSeparator()
        act("回到角落", lambda: self.go_corner(c["snap_corner"]))
        act("聲音開關", self.set_sound, c["sound"])
        act(
            "模式：" + ("模擬" if c["mode"] == "sim" else "API") + "（點此切換）",
            lambda: self.set_mode("api" if c["mode"] == "sim" else "sim"),
        )
        if not tray:
            act("隱藏寵物", self.hide_pet)
        else:
            act("顯示寵物" if not self.pet.isVisible() else "隱藏寵物", self.toggle_pet_visible)
            act("新手教學...", self.open_tutorial)
        m.addSeparator()
        act("退出程式", self.quit)

    def hide_pet(self):
        self.pet.hide()
        self.pet.props.hide_all()
        self.qchars.hide_all()
        self.sounds.set_muted(True)
        for ep in self.extra_pets.values():
            ep.hide()
            ep.props.hide_all()
        self._changed()

    def show_pet(self):
        self.pet.show()
        self.pet.props.show_all()
        self.qchars.show_all()
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

    def _center_and_raise(self, win: QWidget):
        scr = QGuiApplication.screenAt(self.pet.frameGeometry().center()) or QGuiApplication.primaryScreen()
        if scr:
            geo = scr.availableGeometry()
            x = geo.x() + (geo.width() - win.width()) // 2
            y = geo.y() + (geo.height() - win.height()) // 2
            win.move(x, y)
        win.show()
        win.raise_()
        win.activateWindow()
        try:
            winapi.set_topmost(int(win.winId()), True)
        except Exception:
            pass

    def pet_menu(self, gpos: QPoint, pet: PetWindow | None = None):
        target = pet or self.pet
        m = QMenu()
        self._fill_menu(m, pet=target)
        self._active_menu = m
        if "--selftest" in sys.argv:
            QTimer.singleShot(10, m.close)
        QTimer.singleShot(0, lambda: m.exec(gpos))

    def q_menu(self, ch, gpos: QPoint):
        pass

    def prop_menu(self, prop, gpos: QPoint):
        m = QMenu()
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
        if "--selftest" in sys.argv:
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
            self.show_panel()

    def show_panel(self):
        if self.panel is None:
            self.panel = ControlPanel(self)
        self._center_and_raise(self.panel)

    # ------------------------------------------------------------- Dialog openers
    def open_char_picker(self):
        parent = self.panel if (self.panel and self.panel.isVisible()) else None
        dlg = CharPickerDialog(self, parent)
        self._center_and_raise(dlg)
        dlg.exec()

    def open_sound_library(self):
        parent = self.panel if (self.panel and self.panel.isVisible()) else None
        dlg = SoundLibraryDialog(self, parent)
        self._center_and_raise(dlg)
        dlg.exec()

    def _show_qchars_maintenance_dialog(self):
        from .dialogs import ModernMessageBox
        ModernMessageBox.information(
            self.panel or self.pet,
            "提示",
            "Q 版角色功能目前暫時停用並進行重構升級中，敬請期待後續版本開放！",
        )

    def open_custom_q_dialog(self):
        self._show_qchars_maintenance_dialog()

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
        # If this character was in extra pets, remove it from extra pets
        if cid in self.extra_pets:
            self.dismiss_balance_pet(cid)
        self._changed()

    def set_variant(self, var: str):
        self.cfg.set("variant", var)
        self.pet.set_variant(var)
        self._changed()

    def set_click_through(self, on: bool):
        self.cfg.set("click_through", bool(on))
        self.pet.apply_click_through(bool(on))
        for ep in self.extra_pets.values():
            ep.apply_click_through(bool(on))
        self.qchars.set_click_through(bool(on))
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
        self.qchars.apply_topmost()
        self._changed()

    def set_pat(self, on: bool):
        self.cfg.set("pat", bool(on))
        if not on:
            self.pet.end_pat()
            for ep in self.extra_pets.values():
                ep.end_pat()
        self._changed()

    def set_opacity(self, v: int):
        self.cfg.set("opacity", int(v))
        op = max(0.2, min(1.0, int(v) / 100.0))
        self.pet.setWindowOpacity(op)
        for ep in self.extra_pets.values():
            ep.setWindowOpacity(op)
        self._changed()

    def set_size(self, px: int):
        self.pet.set_size(px)
        for ep in self.extra_pets.values():
            ep.set_size(px)
        self._changed()

    def set_theme(self, t: str):
        self.cfg.set("theme", t)
        if self.panel:
            self.panel.apply_theme()
        if self.chat_dialog:
            from .chat import _get_qss
            self.chat_dialog.setStyleSheet(_get_qss(t))
        self._changed()

    def set_q_dark(self, on: bool):
        self.qchars.set_dark_mode(bool(on))
        self._changed()

    def add_q(self, dark: bool | None = None, kind: str = "ds", custom_id: str = ""):
        self._show_qchars_maintenance_dialog()

    def remove_all_q(self):
        self.qchars.remove_all()
        self._changed()

    def set_q_height(self, h: int):
        self.cfg.set("q_height", int(h))
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
