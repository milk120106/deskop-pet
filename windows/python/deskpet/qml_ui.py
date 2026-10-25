"""Qt Quick / QML 現代動效設定視窗模組。
提供具備 Material Design 3 / iOS 扁平化流暢動效之全新統一設定中心，
徹底整合傳統控制台、角色選擇視窗、音效庫管理、AI 模型金鑰與日誌檢視。
嚴格禁止使用任何 Emoji。
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
import webbrowser
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Property, QObject, QPoint, Qt, QThread, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QPainter, QPixmap
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtWidgets import QDialog, QFileDialog, QInputDialog, QVBoxLayout, QWidget

from . import winapi
from .config import (
    APP_DIR,
    APP_VERSION,
    ASSETS,
    CUSTOM_CHARS_DIR,
    GITHUB_RELEASES_API,
    GITHUB_RELEASES_URL,
    GITHUB_REPO_URL,
    SOUND_LIB_DIR,
    id_to_provider_name,
    provider_to_id,
)
from .font_manager import (
    apply_global_font,
    get_font_stack_string,
    get_system_fonts,
    load_font_file,
    resolve_best_default_font,
)
from .logger import LOGS_DIR, check_crash, clear_memory_buffer, get_recent_logs, log
from .model_catalog import DYNAMIC_MODEL_ALIASES, OPENAI_BASES, PROVIDERS, ModelCatalogError, discover_models


class QmlModelDiscoverWorker(QThread):
    """非同步線上遠端模型清單探索工作執行緒。"""
    models_ready = Signal(bool, list, str)

    def __init__(self, profile: dict, parent=None):
        super().__init__(parent)
        self.profile = dict(profile)

    def run(self):
        try:
            models, source, note = discover_models(self.profile)
            self.models_ready.emit(True, models, note or source)
        except Exception as e:
            self.models_ready.emit(False, [], str(e))


class QmlUpdateCheckWorker(QThread):
    """非同步 GitHub Releases 最新版本檢查執行緒。"""
    finished = Signal(bool, str, str, str)  # ok, tag, url, msg

    def run(self):
        try:
            req = urllib.request.Request(
                GITHUB_RELEASES_API,
                headers={"User-Agent": "DesktopPet/2.1.0", "Accept": "application/vnd.github.v3+json"},
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            tag = data.get("tag_name", "").strip()
            url = data.get("html_url", GITHUB_RELEASES_URL)
            body = data.get("body", "")
            self.finished.emit(True, tag, url, body)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                self.finished.emit(
                    True, "", GITHUB_RELEASES_URL, f"已連線至 GitHub 倉庫，目前尚未建立正式 Release 標籤（當前版本 {APP_VERSION} 為最新版本）。"
                )
            else:
                self.finished.emit(False, "", GITHUB_RELEASES_URL, f"HTTP 回應狀態：{e.code} {e.reason}")
        except Exception as e:
            self.finished.emit(False, "", GITHUB_RELEASES_URL, f"連線至 GitHub 失敗：{e}")


class QMLBackend(QObject):
    """QML 與應用程式控制器之間的雙向資料橋接器。"""

    themeChanged = Signal(str)
    characterChanged = Signal(str)
    variantChanged = Signal(str)
    sizeChanged = Signal(int)
    opacityChanged = Signal(int)
    clickThroughChanged = Signal(bool)
    autoSnapChanged = Signal(bool)
    alwaysOnTopChanged = Signal(bool)
    soundChanged = Signal(bool)
    volumeChanged = Signal(int)
    aiModeChanged = Signal(str)
    pureVoiceChanged = Signal(bool)
    geminiLiveVoiceChanged = Signal(str)
    statusSummaryChanged = Signal(str)
    logsChanged = Signal(str)
    currentFontChanged = Signal(str)
    customFontPathChanged = Signal(str)
    cueFilesChanged = Signal()
    apiProviderChanged = Signal(str)
    apiKeyChanged = Signal(str)
    apiEndpointChanged = Signal(str)
    chatModelChanged = Signal(str)
    systemPromptChanged = Signal(str)
    temperatureChanged = Signal(float)
    privacyModeChanged = Signal(bool)
    dpapiChanged = Signal(bool)
    pinAuthChanged = Signal(bool)
    remoteModelsChanged = Signal(list)
    remoteModelStatusChanged = Signal(str)
    updateStatusChanged = Signal(str)
    tabSwitched = Signal(int)
    noticeMessage = Signal(str, bool)  # text, is_error
    qChibiChanged = Signal(bool)
    qClimbWindowsChanged = Signal(bool)
    qFlightPropChanged = Signal(bool)
    qFireworksPropChanged = Signal(bool)
    alarmsChanged = Signal()
    notificationsChanged = Signal()
    strictCustomImageRatioChanged = Signal(bool)
    activeBalanceChanged = Signal()
    activeBalanceProviderChanged = Signal(str)

    def __init__(self, app, win: QWidget):
        super().__init__()
        self.app = app
        self.win = win
        self._drag_start_global: QPoint | None = None
        self._drag_win_pos: QPoint | None = None
        self._cached_logs = ""
        self._current_ai_mode = "standard"
        self._selected_api_prov = "DeepSeek"
        self._preview_font = self.get_current_font_family()
        self._custom_font_path = str(self.app.cfg.get("custom_font_path", ""))
        self._remote_models: list[str] = []
        self._remote_model_status = "請點擊按鈕獲取遠端可用模型清單"
        self._update_status = "點擊按鈕檢查線上是否有新版本"
        self._disc_worker: QmlModelDiscoverWorker | None = None
        self._update_worker: QmlUpdateCheckWorker | None = None

        # 監聽應用程式狀態變更以保持雙向同步
        if hasattr(self.app, "state_changed"):
            self.app.state_changed.connect(self.sync_from_app)

        if hasattr(self.app, "ledger") and self.app.ledger:
            self.app.ledger.changed.connect(self._on_ledger_changed)

    def _on_ledger_changed(self):
        self.activeBalanceChanged.emit()
        self.statusSummaryChanged.emit(self.get_status_summary())

    # --------------------------------------------------------- 屬性讀取器 (Getters)
    def get_theme(self) -> str:
        return str(self.app.cfg.get("theme", "light"))

    def get_character(self) -> str:
        return str(self.app.pet.character)

    def get_variant(self) -> str:
        return str(self.app.cfg.get("variant", "square"))

    def get_strict_custom_image_ratio(self) -> bool:
        return bool(self.app.cfg.get("strict_custom_image_ratio", True))

    def get_size_px(self) -> int:
        return int(self.app.pet.size_px)

    def get_opacity_val(self) -> int:
        return int(self.app.cfg.get("opacity", 100))

    def get_click_through(self) -> bool:
        return bool(self.app.cfg.get("click_through", False))

    def get_auto_snap(self) -> bool:
        return bool(self.app.cfg.get("auto_snap", True))

    def get_always_on_top(self) -> bool:
        return bool(self.app.cfg.get("always_on_top", True))

    def get_sound_enabled(self) -> bool:
        return bool(self.app.cfg.get("sound", True))

    def get_volume(self) -> int:
        return int(self.app.cfg.get("volume", 80))

    def get_ai_mode(self) -> str:
        if self.app.chat_dialog and hasattr(self.app.chat_dialog, "current_mode"):
            return str(self.app.chat_dialog.current_mode)
        return self._current_ai_mode

    def get_pure_voice_active(self) -> bool:
        return bool(getattr(self.app, "pure_voice_active", False))

    def get_gemini_live_voice(self) -> str:
        return str(self.app.cfg.get("gemini_live_voice", "Kore"))

    def get_app_version(self) -> str:
        return APP_VERSION

    def get_status_summary(self) -> str:
        cur_sym = "¥" if getattr(self.app.ledger, "currency", "CNY") == "CNY" else "$"
        balance = getattr(self.app.ledger, "shown", 0.0)
        mode_text = "模擬" if self.app.cfg.get("mode") == "sim" else "API"
        char_name = self.app.pet.character.capitalize()
        crash_info = check_crash()
        crash_txt = "正常" if not crash_info.get("crashed") else "異常終止"
        return f"主角色：{char_name} | 模式：{mode_text} | 餘額：{cur_sym}{balance:.2f} | 狀態：{crash_txt}"

    def get_logs_snippet(self) -> str:
        if not self._cached_logs:
            self._update_logs_cache()
        return self._cached_logs

    def get_system_fonts(self) -> list[str]:
        return get_system_fonts()

    def get_current_font_family(self) -> str:
        cfg_f = self.app.cfg.get("font_family")
        return str(cfg_f) if cfg_f else resolve_best_default_font()

    def get_custom_font_path(self) -> str:
        return self._custom_font_path

    def get_cue_hit_file(self) -> str:
        customs = self.app.cfg.get("cue_custom") or {}
        return customs.get("hit") or "預設音效 (hit.mp3)"

    def get_cue_feed_file(self) -> str:
        customs = self.app.cfg.get("cue_custom") or {}
        return customs.get("feed") or "預設音效 (feed.mp3)"

    def get_cue_land_file(self) -> str:
        customs = self.app.cfg.get("cue_custom") or {}
        return customs.get("land") or "預設音效 (pot_land.mp3)"

    def get_cue_off_file(self) -> str:
        customs = self.app.cfg.get("cue_custom") or {}
        return customs.get("off") or "預設音效 (pot_off.mp3)"

    def get_api_provider(self) -> str:
        return self._selected_api_prov

    def get_api_providers_list(self) -> list[str]:
        return list(PROVIDERS)

    def get_api_key(self) -> str:
        prov = self._selected_api_prov
        # 1. 優先自 api_profiles 查詢
        for p in self.app.cfg.get("api_profiles", []):
            if p.get("provider", "").lower() == prov.lower() or (prov == "Claude" and p.get("provider") == "Anthropic"):
                k = str(p.get("key", "")).strip()
                if k:
                    return k
        # 2. 自 api_keys 字典查詢
        prov_map = {
            "DeepSeek": "deepseek",
            "OpenAI": "openai",
            "Google Gemini": "gemini",
            "Claude": "anthropic",
            "Anthropic": "anthropic",
            "Groq": "groq",
            "Mistral": "mistral",
            "xAI / Grok": "grok",
            "Ollama": "ollama",
            "OpenRouter": "openrouter",
            "矽基流動 (SiliconFlow)": "siliconflow",
            "月之暗面 (Moonshot/Kimi)": "moonshot",
        }
        pid = prov_map.get(prov, prov.lower())
        keys = self.app.cfg.get("api_keys") or {}
        return str(keys.get(pid, keys.get(prov, "")))

    def get_api_endpoint(self) -> str:
        prov = self._selected_api_prov
        # 1. 優先自 api_profiles 查詢
        for p in self.app.cfg.get("api_profiles", []):
            if p.get("provider", "").lower() == prov.lower() or (prov == "Claude" and p.get("provider") == "Anthropic"):
                ep = str(p.get("endpoint", "")).strip()
                if ep:
                    return ep
        # 2. 自 api_endpoints 字典查詢
        eps = self.app.cfg.get("api_endpoints") or {}
        if prov in eps and eps[prov]:
            return str(eps[prov])
        return str(OPENAI_BASES.get(prov, ""))

    def get_chat_model(self) -> str:
        prov = self._selected_api_prov
        for p in self.app.cfg.get("api_profiles", []):
            if p.get("provider", "").lower() == prov.lower() or (prov == "Claude" and p.get("provider") == "Anthropic"):
                m = str(p.get("model", "")).strip()
                if m:
                    return m
        aliases = DYNAMIC_MODEL_ALIASES.get(prov, [])
        if aliases:
            return aliases[0]["id"]
        return str(self.app.cfg.get("active_model", ""))

    def get_system_prompt(self) -> str:
        return str(self.app.cfg.get("system_prompt", ""))

    def get_temperature(self) -> float:
        return float(self.app.cfg.get("temperature", 0.7))

    def get_privacy_mode(self) -> bool:
        return bool(self.app.cfg.get("privacy_sanitizer_enabled", True))

    def get_dpapi_enabled(self) -> bool:
        return bool(self.app.cfg.get("dpapi_enabled", True))

    def get_pin_auth_enabled(self) -> bool:
        return bool(self.app.cfg.get("pin_auth_enabled", False))

    def get_remote_models(self) -> list[str]:
        return self._remote_models

    def get_remote_model_status(self) -> str:
        return self._remote_model_status

    def get_update_status(self) -> str:
        return self._update_status

    def get_q_chibi_enabled(self) -> bool:
        return bool(self.app.cfg.get("q_chibi_enabled", True))

    def get_q_climb_windows(self) -> bool:
        return bool(self.app.cfg.get("q_climb_windows", False))

    def get_q_flight_prop(self) -> bool:
        return bool(self.app.cfg.get("q_flight_prop", False))

    def get_q_fireworks_prop(self) -> bool:
        return bool(self.app.cfg.get("q_fireworks_prop", False))

    def get_active_balance_provider(self) -> str:
        if hasattr(self.app, "ledger") and self.app.ledger:
            return self.app.ledger.provider_display_name
        return id_to_provider_name(self.app.cfg.get("provider", "deepseek"))

    def get_active_balance_text(self) -> str:
        if hasattr(self.app, "ledger") and self.app.ledger:
            return self.app.ledger.text
        return "--"

    def get_active_balance_status(self) -> str:
        if hasattr(self.app, "ledger") and self.app.ledger:
            if self.app.ledger.online:
                return "正常連線"
            return self.app.ledger.error or "未連線"
        return "未連線"

    def get_active_balance_currency(self) -> str:
        if hasattr(self.app, "ledger") and self.app.ledger:
            return self.app.ledger.currency
        return "CNY"

    def get_active_balance_is_online(self) -> bool:
        if hasattr(self.app, "ledger") and self.app.ledger:
            return bool(self.app.ledger.online)
        return False

    def _update_logs_cache(self, level: str | None = None, search: str | None = None):
        lvl_arg = None if (not level or "ALL" in level or "全部" in level) else level
        query_arg = search.strip() if search and search.strip() else None
        entries = get_recent_logs(count=150, level=lvl_arg, search=query_arg)
        lines = []
        for e in entries:
            ts = e.get("timestamp", "")[-8:]
            lvl = e.get("level", "INFO")
            src = e.get("source", "Pet")
            msg = e.get("message", "").replace("\n", " ")
            lines.append(f"[{ts}] [{lvl:5s}] [{src}] {msg}")
        self._cached_logs = "\n".join(lines) if lines else "目前尚無符合篩選條件的日誌紀錄。"

    # --------------------------------------------------------- 雙向屬性綁定宣告
    theme = Property(str, get_theme, notify=themeChanged)
    character = Property(str, get_character, notify=characterChanged)
    variant = Property(str, get_variant, notify=variantChanged)
    sizePx = Property(int, get_size_px, notify=sizeChanged)
    opacityVal = Property(int, get_opacity_val, notify=opacityChanged)
    clickThrough = Property(bool, get_click_through, notify=clickThroughChanged)
    autoSnap = Property(bool, get_auto_snap, notify=autoSnapChanged)
    alwaysOnTop = Property(bool, get_always_on_top, notify=alwaysOnTopChanged)
    soundEnabled = Property(bool, get_sound_enabled, notify=soundChanged)
    volume = Property(int, get_volume, notify=volumeChanged)
    aiMode = Property(str, get_ai_mode, notify=aiModeChanged)
    pureVoiceActive = Property(bool, get_pure_voice_active, notify=pureVoiceChanged)
    geminiLiveVoice = Property(str, get_gemini_live_voice, notify=geminiLiveVoiceChanged)
    appVersion = Property(str, get_app_version, constant=True)
    statusSummary = Property(str, get_status_summary, notify=statusSummaryChanged)
    logsSnippet = Property(str, get_logs_snippet, notify=logsChanged)
    systemFonts = Property(list, get_system_fonts, constant=True)
    currentFontFamily = Property(str, get_current_font_family, notify=currentFontChanged)
    customFontPath = Property(str, get_custom_font_path, notify=customFontPathChanged)
    cueHitFile = Property(str, get_cue_hit_file, notify=cueFilesChanged)
    cueFeedFile = Property(str, get_cue_feed_file, notify=cueFilesChanged)
    cueLandFile = Property(str, get_cue_land_file, notify=cueFilesChanged)
    cueOffFile = Property(str, get_cue_off_file, notify=cueFilesChanged)
    apiProvider = Property(str, get_api_provider, notify=apiProviderChanged)
    apiProvidersList = Property(list, get_api_providers_list, constant=True)
    apiKey = Property(str, get_api_key, notify=apiKeyChanged)
    apiEndpoint = Property(str, get_api_endpoint, notify=apiEndpointChanged)
    chatModel = Property(str, get_chat_model, notify=chatModelChanged)
    systemPrompt = Property(str, get_system_prompt, notify=systemPromptChanged)
    temperature = Property(float, get_temperature, notify=temperatureChanged)
    privacyMode = Property(bool, get_privacy_mode, notify=privacyModeChanged)
    dpapiEnabled = Property(bool, get_dpapi_enabled, notify=dpapiChanged)
    pinAuthEnabled = Property(bool, get_pin_auth_enabled, notify=pinAuthChanged)
    remoteModels = Property(list, get_remote_models, notify=remoteModelsChanged)
    remoteModelStatus = Property(str, get_remote_model_status, notify=remoteModelStatusChanged)
    updateStatus = Property(str, get_update_status, notify=updateStatusChanged)
    qChibiEnabled = Property(bool, get_q_chibi_enabled, notify=qChibiChanged)
    qClimbWindows = Property(bool, get_q_climb_windows, notify=qClimbWindowsChanged)
    qFlightProp = Property(bool, get_q_flight_prop, notify=qFlightPropChanged)
    qFireworksProp = Property(bool, get_q_fireworks_prop, notify=qFireworksPropChanged)
    strictCustomImageRatio = Property(bool, get_strict_custom_image_ratio, notify=strictCustomImageRatioChanged)
    activeBalanceProvider = Property(str, get_active_balance_provider, notify=activeBalanceProviderChanged)
    activeBalanceText = Property(str, get_active_balance_text, notify=activeBalanceChanged)
    activeBalanceStatus = Property(str, get_active_balance_status, notify=activeBalanceChanged)
    activeBalanceCurrency = Property(str, get_active_balance_currency, notify=activeBalanceChanged)
    activeBalanceIsOnline = Property(bool, get_active_balance_is_online, notify=activeBalanceChanged)

    # --------------------------------------------------------- 槽函式 (Slots)
    @Slot(str)
    def setTheme(self, t: str):
        self.app.set_theme(t)
        self.themeChanged.emit(t)

    @Slot()
    def toggleTheme(self):
        new_theme = "light" if self.get_theme() == "dark" else "dark"
        self.setTheme(new_theme)

    @Slot(str)
    def setCharacter(self, cid: str):
        self.app.set_character(cid)
        self.characterChanged.emit(cid)
        self.statusSummaryChanged.emit(self.get_status_summary())

    @Slot(str)
    def setVariant(self, var: str):
        if var in ("square", "tail"):
            self.app.set_variant(var)
            self.variantChanged.emit(var)

    @Slot(bool)
    def setStrictCustomImageRatio(self, val: bool):
        self.app.set_strict_custom_image_ratio(val)
        self.strictCustomImageRatioChanged.emit(val)

    @Slot()
    def exportSettingsData(self):
        """開啟全設定與資料安全匯出視窗。"""
        from .dialogs import ExportSettingsDialog
        dlg = ExportSettingsDialog(self.app, self.win)
        dlg.exec()

    @Slot()
    def importSettingsData(self):
        """開啟檔案選擇器匯入設定備份，支援 YuYue 加密密碼解鎖。"""
        from .dialogs import ImportPasswordDialog, ModernMessageBox
        from .export_data import import_backup_data

        path, _ = QFileDialog.getOpenFileName(
            self.win, "選擇設定備份檔案", "", "備份檔案 (*.json *.dpbak);;所有檔案 (*.*)"
        )
        if not path:
            return

        try:
            try:
                import_backup_data(self.app, path, password="")
            except ValueError as ve:
                if "NEED_PASSWORD" in str(ve):
                    pwd_dlg = ImportPasswordDialog(self.win, theme=self.app.cfg.get("theme", "light"))
                    if pwd_dlg.exec() != QDialog.Accepted:
                        return
                    import_backup_data(self.app, path, password=pwd_dlg.password)
                else:
                    raise

            # 重新整理 QML 介面所有狀態
            theme = self.app.cfg.get("theme", "light")
            self.themeChanged.emit(theme)
            self.characterChanged.emit(self.app.cfg.get("character", "deepseek"))
            self.variantChanged.emit(self.app.cfg.get("variant", "square"))
            self.strictCustomImageRatioChanged.emit(self.app.cfg.get("strict_custom_image_ratio", True))
            self.sizeChanged.emit(self.app.cfg.get("size", 454))
            self.opacityChanged.emit(self.app.cfg.get("opacity", 100))
            self.soundChanged.emit(self.app.cfg.get("sound", True))
            self.volumeChanged.emit(self.app.cfg.get("volume", 80))
            self.clickThroughChanged.emit(self.app.cfg.get("click_through", False))
            self.autoSnapChanged.emit(self.app.cfg.get("auto_snap", True))
            self.alwaysOnTopChanged.emit(self.app.cfg.get("always_on_top", True))
            self.qChibiChanged.emit(self.app.cfg.get("q_chibi_enabled", True))
            self.alarmsChanged.emit()
            self.notificationsChanged.emit()
            self.noticeMessage.emit("設定與資料已成功匯入並套用！", False)
            ModernMessageBox.information(self.win, "匯入成功", "設定與資料已成功還原！已套用最新配置。")
        except Exception as e:
            self.noticeMessage.emit(f"匯入失敗：{e}", True)
            ModernMessageBox.warning(self.win, "匯入失敗", f"無法匯入備份設定：{e}")

    @Slot()
    def importCustomCharacter(self):
        """呼叫檔案對話框選擇立繪，並新增自訂角色。"""
        path, _ = QFileDialog.getOpenFileName(
            self.win, "選擇角色圖片（建議透明背景 PNG）", "", "圖片檔案 (*.png *.jpg *.jpeg *.webp *.bmp)"
        )
        if not path:
            return
        name, ok = QInputDialog.getText(self.win, "自訂角色名稱", "請輸入自訂角色英文或數字名稱：")
        if not ok or not name.strip():
            return

        safe_name = "".join(c for c in name if c.isalnum() or c in ("_", "-")).strip()
        if not safe_name:
            self.noticeMessage.emit("請輸入有效的名稱（僅限英數與底線）", True)
            return

        cid = f"custom_{safe_name}"
        dest_dir = CUSTOM_CHARS_DIR / cid
        dest_dir.mkdir(parents=True, exist_ok=True)

        try:
            img = QImage(path)
            if img.isNull() or img.height() <= 0:
                raise ValueError("無法解析圖片檔案格式")

            strict = self.app.cfg.get("strict_custom_image_ratio", True)
            ratio = img.width() / float(img.height())
            if strict:
                if ratio < 0.7 or ratio > 1.8:
                    warn_msg = "圖片比例不符合官方立繪標準規格（1:1 或 1.5:1）。若欲強制使用特殊比例圖片，請至設定中關閉尺寸比例限制。"
                    self.noticeMessage.emit(warn_msg, True)
                    from .dialogs import ModernMessageBox
                    ModernMessageBox.warning(self.win, "圖片比例不符合", warn_msg)
                    return

            if not strict:
                # 關閉限制：保持原始寬高比
                img.save(str(dest_dir / "sprite.png"), "PNG")
            else:
                canvas = QImage(1024, 1024, QImage.Format_ARGB32_Premultiplied)
                canvas.fill(Qt.transparent)
                sc = min(1024.0 / img.width(), 1024.0 / img.height())
                w, h = int(img.width() * sc), int(img.height() * sc)
                p = QPainter(canvas)
                p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
                p.drawImage((1024 - w) // 2, 1024 - h, img.scaled(w, h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation))
                p.end()
                canvas.save(str(dest_dir / "sprite.png"), "PNG")

            (dest_dir / "tablet.txt").write_text("330,790,694,790,694,960,330,960", encoding="utf-8")
            self.setCharacter(cid)
            self.noticeMessage.emit(f"自訂角色「{safe_name}」匯入成功並已套用！", False)
        except Exception as e:
            self.noticeMessage.emit(f"匯入自訂角色失敗：{e}", True)

    @Slot(int)
    def setSizePx(self, size: int):
        self.app.set_size(size)
        self.sizeChanged.emit(size)

    @Slot(bool)
    def setQChibiEnabled(self, val: bool):
        self.app.set_q_chibi_enabled(val)
        self.qChibiChanged.emit(val)

    @Slot(bool)
    def setQClimbWindows(self, val: bool):
        self.app.set_q_climb_windows(val)
        self.qClimbWindowsChanged.emit(val)

    @Slot(bool)
    def setQFlightProp(self, val: bool):
        self.app.set_q_flight_prop(val)
        self.qFlightPropChanged.emit(val)

    @Slot(bool)
    def setQFireworksProp(self, val: bool):
        self.app.set_q_fireworks_prop(val)
        self.qFireworksPropChanged.emit(val)

    @Slot(str, str, str, int)
    def addAlarm(self, name: str, time_str: str, alarm_type: str, duration_sec: int):
        if hasattr(self.app, "alarm_dispatcher") and self.app.alarm_dispatcher:
            self.app.alarm_dispatcher.add_alarm(name, time_str, alarm_type, duration_sec)
            self.alarmsChanged.emit()

    @Slot(str)
    def removeAlarm(self, aid: str):
        if hasattr(self.app, "alarm_dispatcher") and self.app.alarm_dispatcher:
            self.app.alarm_dispatcher.remove_alarm(aid)
            self.alarmsChanged.emit()

    @Slot(str, bool)
    def toggleAlarm(self, aid: str, enabled: bool):
        if hasattr(self.app, "alarm_dispatcher") and self.app.alarm_dispatcher:
            self.app.alarm_dispatcher.toggle_alarm(aid, enabled)
            self.alarmsChanged.emit()

    @Slot(result=str)
    def getAlarmsJson(self) -> str:
        if hasattr(self.app, "alarm_dispatcher") and self.app.alarm_dispatcher:
            import json
            return json.dumps(self.app.alarm_dispatcher.get_alarms(), ensure_ascii=False)
        return "[]"

    @Slot(result=str)
    def getNotificationsJson(self) -> str:
        if hasattr(self.app, "alarm_dispatcher") and self.app.alarm_dispatcher:
            import json
            return json.dumps(self.app.alarm_dispatcher.get_notifications(), ensure_ascii=False)
        return "[]"

    @Slot(str, str, str)
    def setWebhookConfig(self, discord_url: str, tg_token: str, tg_chat: str):
        self.app.cfg.set("discord_webhook_url", discord_url.strip())
        self.app.cfg.set("telegram_bot_token", tg_token.strip())
        self.app.cfg.set("telegram_chat_id", tg_chat.strip(), save=True)
        self.noticeMessage.emit("通知管道 Webhook 設定已儲存", False)

    @Slot(int)
    def setOpacityVal(self, val: int):
        val = max(20, min(100, val))
        self.app.set_opacity(val)
        self.opacityChanged.emit(val)

    @Slot(bool)
    def setClickThrough(self, val: bool):
        self.app.set_click_through(val)
        self.clickThroughChanged.emit(val)

    @Slot(bool)
    def setAutoSnap(self, val: bool):
        self.app.set_auto_snap(val)
        self.autoSnapChanged.emit(val)

    @Slot(bool)
    def setAlwaysOnTop(self, val: bool):
        self.app.set_topmost(val)
        self.alwaysOnTopChanged.emit(val)

    @Slot(bool)
    def setSoundEnabled(self, val: bool):
        self.app.set_sound(val)
        self.soundChanged.emit(val)

    @Slot(int)
    def setVolume(self, val: int):
        val = max(0, min(100, val))
        self.app.set_volume(val)
        self.volumeChanged.emit(val)

    @Slot(str)
    def playCue(self, key: str):
        if hasattr(self.app, "sounds"):
            self.app.sounds.play(key)

    @Slot(str)
    def uploadCue(self, key: str):
        path, _ = QFileDialog.getOpenFileName(
            self.win, f"選取提示音效檔案 ({key})", "", "音效檔案 (*.mp3 *.wav *.ogg *.m4a)"
        )
        if not path:
            return
        ok, msg = self.app.sounds.set_custom_cue(key, path)
        if ok:
            self.cueFilesChanged.emit()
            self.noticeMessage.emit(f"成功更換提示音 [{key}]：{msg}", False)
        else:
            self.noticeMessage.emit(f"更換提示音失敗：{msg}", True)

    @Slot(str)
    def resetCue(self, key: str):
        self.app.sounds.restore_default_cue(key)
        self.cueFilesChanged.emit()
        self.noticeMessage.emit(f"已恢復 [{key}] 為預設音效", False)

    @Slot(str)
    def setAiMode(self, mode: str):
        self._current_ai_mode = mode
        if self.app.chat_dialog and hasattr(self.app.chat_dialog, "_set_mode"):
            self.app.chat_dialog._set_mode(mode)
        self.aiModeChanged.emit(mode)

    @Slot()
    def togglePureVoice(self):
        self.app.open_gemini_live()
        self.pureVoiceChanged.emit(self.get_pure_voice_active())

    @Slot(str)
    def setGeminiLiveVoice(self, voice: str):
        self.app.cfg.set("gemini_live_voice", voice, save=True)
        self.geminiLiveVoiceChanged.emit(voice)
        self.noticeMessage.emit(f"已設定 Gemini Live 音色為：{voice}", False)

    # --------------------------------------------------------- AI 與 API 金鑰設定
    @Slot(str)
    def setApiProvider(self, prov: str):
        self._selected_api_prov = prov
        self.apiProviderChanged.emit(prov)
        self.apiKeyChanged.emit(self.get_api_key())
        self.apiEndpointChanged.emit(self.get_api_endpoint())
        self.chatModelChanged.emit(self.get_chat_model())

        # 自動依動態別名填充可選模型列表
        aliases = DYNAMIC_MODEL_ALIASES.get(prov, [])
        if aliases:
            self._remote_models = [m["id"] for m in aliases]
            self.remoteModelsChanged.emit(self._remote_models)
            self._remote_model_status = f"已載入 {prov} 推薦動態模型（共 {len(self._remote_models)} 個）"
            self.remoteModelStatusChanged.emit(self._remote_model_status)

    @Slot(str, str)
    def saveApiKey(self, prov: str, key: str):
        prov_map = {
            "DeepSeek": "deepseek",
            "OpenAI": "openai",
            "Google Gemini": "gemini",
            "Claude": "anthropic",
            "Anthropic": "anthropic",
            "Groq": "groq",
            "Mistral": "mistral",
            "xAI / Grok": "grok",
            "Ollama": "ollama",
            "OpenRouter": "openrouter",
            "矽基流動 (SiliconFlow)": "siliconflow",
            "月之暗面 (Moonshot/Kimi)": "moonshot",
        }
        pid = prov_map.get(prov, prov.lower())
        keys = dict(self.app.cfg.get("api_keys") or {})
        keys[pid] = key.strip()
        keys[prov] = key.strip()
        self.app.cfg.set("api_keys", keys, save=True)

        # 同步至 api_profiles
        profiles = [dict(x) for x in self.app.cfg.get("api_profiles", [])]
        matched = False
        for p in profiles:
            if p.get("provider", "").lower() == prov.lower() or (prov == "Claude" and p.get("provider") == "Anthropic"):
                p["key"] = key.strip()
                matched = True
                break
        if not matched:
            target_prov = "Anthropic" if prov == "Claude" else prov
            profiles.append({"provider": target_prov, "key": key.strip(), "model": self.get_chat_model(), "endpoint": self.get_api_endpoint()})
        self.app.cfg.set("api_profiles", profiles, save=True)

        self.apiKeyChanged.emit(key.strip())
        self.noticeMessage.emit(f"{prov} API 金鑰已安全儲存！", False)

    @Slot(str, str)
    def saveApiEndpoint(self, prov: str, endpoint: str):
        eps = dict(self.app.cfg.get("api_endpoints") or {})
        eps[prov] = endpoint.strip()
        self.app.cfg.set("api_endpoints", eps, save=True)

        # 同步更新 api_profiles
        profiles = [dict(x) for x in self.app.cfg.get("api_profiles", [])]
        for p in profiles:
            if p.get("provider", "").lower() == prov.lower() or (prov == "Claude" and p.get("provider") == "Anthropic"):
                p["endpoint"] = endpoint.strip()
                break
        self.app.cfg.set("api_profiles", profiles, save=True)

        self.apiEndpointChanged.emit(endpoint.strip())
        self.noticeMessage.emit(f"{prov} API 端點已儲存！", False)

    @Slot(str)
    def setChatModel(self, model_name: str):
        m = model_name.strip()
        if not m:
            return
        prov = self._selected_api_prov
        self.app.cfg.set("active_model", m, save=True)
        profiles = [dict(x) for x in self.app.cfg.get("api_profiles", [])]
        matched = False
        for p in profiles:
            if p.get("provider", "").lower() == prov.lower() or (prov == "Claude" and p.get("provider") == "Anthropic"):
                p["model"] = m
                matched = True
                break
        if not matched:
            target_prov = "Anthropic" if prov == "Claude" else prov
            profiles.append({"provider": target_prov, "key": self.get_api_key(), "model": m, "endpoint": self.get_api_endpoint()})
        self.app.cfg.set("api_profiles", profiles, save=True)

        if prov == "Google Gemini":
            self.app.cfg.set("gemini_live_model", m, save=True)

        self.chatModelChanged.emit(m)
        self.noticeMessage.emit(f"已套用對話模型：{m}", False)

    @Slot(str)
    def setSystemPrompt(self, prompt: str):
        self.app.cfg.set("system_prompt", prompt.strip(), save=True)
        self.systemPromptChanged.emit(prompt.strip())
        self.noticeMessage.emit("系統提示詞已更新！", False)

    @Slot(float)
    def setTemperature(self, temp: float):
        self.app.cfg.set("temperature", float(temp), save=True)
        self.temperatureChanged.emit(float(temp))

    @Slot(str)
    def setActiveBalanceProvider(self, prov: str):
        if hasattr(self.app, "ledger") and self.app.ledger:
            self.app.ledger.set_provider(prov)
            self.activeBalanceProviderChanged.emit(self.get_active_balance_provider())
            self.activeBalanceChanged.emit()
            self.noticeMessage.emit(f"桌面主寵物餘額監視已切換為：{self.get_active_balance_provider()}！", False)

    @Slot()
    def refreshBalance(self):
        if hasattr(self.app, "ledger") and self.app.ledger:
            self.app.ledger.refresh()
            self.noticeMessage.emit("已發送餘額查詢請求...", False)

    @Slot(str)
    def summonBalancePet(self, prov: str):
        pid = provider_to_id(prov)
        from .app import BALANCE_PET_SPECS
        target_cid = None
        for cid, spec in BALANCE_PET_SPECS.items():
            if cid == pid or spec.get("prov") == pid:
                target_cid = cid
                break
        if not target_cid:
            target_cid = pid if pid in BALANCE_PET_SPECS else "deepseek"
        pet = self.app.summon_balance_pet(target_cid)
        if pet:
            self.noticeMessage.emit(f"已在桌面召喚【{BALANCE_PET_SPECS.get(target_cid, {}).get('name', target_cid)}】餘額寵物！", False)
        else:
            self.noticeMessage.emit("召喚餘額寵物失敗或該寵物已在場上", True)

    @Slot(str, result=float)
    def getProviderBudget(self, prov: str) -> float:
        pid = provider_to_id(prov)
        budgets = self.app.cfg.get("budgets") or {}
        if pid in budgets:
            return float(budgets[pid])
        pname = id_to_provider_name(pid)
        if pname in budgets:
            return float(budgets[pname])
        return 100.0

    @Slot(str, float, str)
    def saveProviderBudget(self, prov: str, budget: float, since_date: str):
        pid = provider_to_id(prov)
        pname = id_to_provider_name(pid)
        budgets = dict(self.app.cfg.get("budgets") or {})
        budgets[pid] = float(budget)
        budgets[pname] = float(budget)
        self.app.cfg.set("budgets", budgets, save=True)

        sinces = dict(self.app.cfg.get("sinces") or {})
        if since_date.strip():
            sinces[pid] = since_date.strip()
            sinces[pname] = since_date.strip()
            self.app.cfg.set("sinces", sinces, save=True)

        if hasattr(self.app, "ledger") and self.app.ledger:
            self.app.ledger.refresh()
        self.activeBalanceChanged.emit()
        self.noticeMessage.emit(f"{pname} 預算與起算日期已更新並重新整理！", False)

    @Slot(str, result=str)
    def getProviderSinceDate(self, prov: str) -> str:
        pid = provider_to_id(prov)
        sinces = self.app.cfg.get("sinces") or {}
        return str(sinces.get(pid, sinces.get(id_to_provider_name(pid), datetime.now().strftime("%Y-%m-01"))))

    @Slot()
    def openChatDialog(self):
        self.app.open_chat_dialog()

    @Slot()
    def openApiProfileDialog(self):
        from .chat import ApiProfileDialog
        d = ApiProfileDialog(self.app.cfg, parent=self.win)
        d.exec()

    @Slot(bool)
    def setDpapiEnabled(self, val: bool):
        self.app.cfg.set("dpapi_enabled", bool(val), save=True)
        self.dpapiChanged.emit(bool(val))
        self.noticeMessage.emit("Windows DPAPI 密文加密保護設定已更新！", False)

    @Slot(bool)
    def setPinAuthEnabled(self, val: bool):
        # 驗證身分後方可切換
        hwnd = int(self.win.winId()) if self.win else 0
        if not winapi.prompt_windows_credentials(hwnd, "請驗證 Windows 身分以切換身分驗證保護開關"):
            self.pinAuthChanged.emit(self.get_pin_auth_enabled())
            self.noticeMessage.emit("Windows 身分驗證已取消", True)
            return
        self.app.cfg.set("pin_auth_enabled", bool(val), save=True)
        self.pinAuthChanged.emit(bool(val))
        self.noticeMessage.emit(f"Windows PIN 身分驗證已{'啟用' if val else '停用'}", False)

    @Slot(bool)
    def setPerformanceMode(self, val: bool):
        self.app.set_performance_mode(bool(val))
        self.noticeMessage.emit(f"極致效能模式已{'開啟' if val else '關閉'}", False)

    @Slot(bool)
    def setDisableTransparency(self, val: bool):
        self.app.set_disable_transparency(bool(val))
        self.noticeMessage.emit(f"半透明背景已{'停用' if val else '啟用'}", False)

    @Slot(bool)
    def setAnimationsEnabled(self, val: bool):
        self.app.set_animations_enabled(bool(val))
        self.noticeMessage.emit(f"角色動效已{'啟用' if val else '停用'}", False)

    @Slot(int)
    def setTargetFps(self, val: int):
        self.app.set_target_fps(int(val))
        self.noticeMessage.emit(f"目標幀率已設為 {val} FPS", False)

    @Slot(int)
    def setVsyncMode(self, val: int):
        self.app.set_vsync_mode(int(val))
        self.noticeMessage.emit(f"垂直同步模式已設為 {val}", False)

    @Slot(str)
    def setRenderingBackend(self, val: str):
        self.app.set_rendering_backend(str(val))
        self.noticeMessage.emit(f"渲染後端已設為 {val}（需重啟生效）", False)

    @Slot(bool)
    def setPrivacyMode(self, val: bool):
        self.app.set_privacy_mode(bool(val))
        self.noticeMessage.emit(f"推論隱私脫敏模式已{'開啟' if val else '關閉'}", False)

    @Slot()
    def openOpenRouterPrivacy(self):
        import webbrowser
        webbrowser.open("https://openrouter.ai/settings/privacy")

    @Slot(str)
    def fetchRemoteModels(self, prov: str):
        key = self.get_api_key()
        endpoint = self.get_api_endpoint()
        is_local = prov in ("Ollama", "本地 LM Studio", "LM Studio", "本地 vLLM", "vLLM", "OpenAI 相容自訂端點")
        if not key and not is_local:
            self._remote_model_status = f"提示：請先輸入並儲存 {prov} 的 API 金鑰"
            self.remoteModelStatusChanged.emit(self._remote_model_status)
            return

        target_prov = "Anthropic" if prov == "Claude" else prov
        profile = {"provider": target_prov, "key": key, "endpoint": endpoint}
        self._remote_model_status = f"正在連線至 {prov} 查詢最新模型清單..."
        self.remoteModelStatusChanged.emit(self._remote_model_status)

        self._disc_worker = QmlModelDiscoverWorker(profile, self)
        self._disc_worker.models_ready.connect(self._on_models_discovered)
        self._disc_worker.start()

    def _on_models_discovered(self, ok: bool, models: list, note: str):
        if ok and models:
            self._remote_models = [m.get("id") for m in models if m.get("id")]
            self._remote_model_status = f"查詢成功：共找到 {len(self._remote_models)} 個可用模型"
        else:
            self._remote_models = []
            self._remote_model_status = f"查詢失敗：{note}"
        self.remoteModelsChanged.emit(self._remote_models)
        self.remoteModelStatusChanged.emit(self._remote_model_status)

    @Slot(str)
    def applyRemoteModel(self, model_id: str):
        if not model_id:
            return
        self.setChatModel(model_id)

    # --------------------------------------------------------- 字體排版設定
    @Slot(str)
    def selectSystemFont(self, fam: str):
        self._preview_font = fam
        self.currentFontChanged.emit(fam)

    @Slot()
    def browseCustomFont(self):
        path, _ = QFileDialog.getOpenFileName(
            self.win, "選取字體檔案", "", "字體檔案 (*.ttf *.otf *.ttc)"
        )
        if not path:
            return
        ok, fam, err = load_font_file(path)
        if ok:
            self._custom_font_path = path
            self._preview_font = fam
            self.customFontPathChanged.emit(path)
            self.currentFontChanged.emit(fam)
            self.noticeMessage.emit(f"成功載入字體：{fam}", False)
        else:
            self.noticeMessage.emit(f"字體載入失敗：{err}", True)

    @Slot(str)
    def applyFont(self, fam: str):
        if self._custom_font_path and Path(self._custom_font_path).exists():
            self.app.cfg.set("font_mode", "custom_file", save=False)
            self.app.cfg.set("custom_font_path", self._custom_font_path, save=False)
        else:
            self.app.cfg.set("font_mode", "system", save=False)
        self.app.cfg.set("font_family", fam, save=True)
        apply_global_font(fam)
        self.currentFontChanged.emit(fam)
        self.noticeMessage.emit(f"已成功套用字體：{fam}", False)

    @Slot()
    def resetDefaultFont(self):
        best = resolve_best_default_font()
        self._custom_font_path = ""
        self.app.cfg.set("font_mode", "default", save=False)
        self.app.cfg.set("custom_font_path", "", save=False)
        self.app.cfg.set("font_family", best, save=True)
        apply_global_font(best)
        self._preview_font = best
        self.currentFontChanged.emit(best)
        self.customFontPathChanged.emit("")
        self.noticeMessage.emit(f"已重設為系統現代無襯線字體：{best}", False)

    # --------------------------------------------------------- 系統日誌與版本更新
    @Slot(str, str)
    def refreshLogs(self, level: str = "", search: str = ""):
        self._update_logs_cache(level, search)
        self.logsChanged.emit(self._cached_logs)

    @Slot()
    def clearLogs(self):
        clear_memory_buffer()
        self._cached_logs = "記憶體日誌已清空。"
        self.logsChanged.emit(self._cached_logs)

    @Slot()
    def checkForUpdates(self):
        self._update_status = "正在向 GitHub Releases 檢查最新版本..."
        self.updateStatusChanged.emit(self._update_status)
        self._update_worker = QmlUpdateCheckWorker(self)
        self._update_worker.finished.connect(self._on_update_checked)
        self._update_worker.start()

    def _on_update_checked(self, ok: bool, tag: str, url: str, msg: str):
        if ok:
            if tag and tag != APP_VERSION:
                self._update_status = f"發現新版本：{tag}！請前往 GitHub 下載更新。"
            else:
                self._update_status = f"當前版本 {APP_VERSION} 為最新版本。"
        else:
            self._update_status = f"檢查失敗：{msg}"
        self.updateStatusChanged.emit(self._update_status)

    @Slot()
    def openRepoUrl(self):
        webbrowser.open(GITHUB_REPO_URL)

    @Slot()
    def openIssuesUrl(self):
        webbrowser.open(f"{GITHUB_REPO_URL}/issues")

    @Slot(str)
    def openExternalUrl(self, url: str):
        if url.startswith("https://") or url.startswith("http://"):
            webbrowser.open(url)

    @Slot()
    def openVk1Repo(self):
        webbrowser.open("https://github.com/VKmich16/VK-1")

    @Slot()
    def openYuYueRepo(self):
        webbrowser.open("https://github.com/YuYue71/YuYue_Encryption")

    @Slot()
    def openCustomCharsDir(self):
        CUSTOM_CHARS_DIR.mkdir(parents=True, exist_ok=True)
        os.startfile(CUSTOM_CHARS_DIR)

    @Slot()
    def openCustomSoundsDir(self):
        SOUND_LIB_DIR.mkdir(parents=True, exist_ok=True)
        os.startfile(SOUND_LIB_DIR)

    @Slot()
    def openLogsDir(self):
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        os.startfile(LOGS_DIR)

    @Slot()
    def openTutorial(self):
        self.app.open_tutorial()

    @Slot()
    def openChatDialog(self):
        self.app.open_chat_dialog()

    @Slot()
    def openWebUi(self):
        self.app.open_web_ui()

    @Slot(int, int)
    def startWindowDrag(self, gx: int, gy: int):
        self._drag_start_global = QPoint(gx, gy)
        self._drag_win_pos = self.win.pos()
        h = self.win.windowHandle()
        if h and hasattr(h, "startSystemMove"):
            h.startSystemMove()

    @Slot(int, int)
    def dragWindowMove(self, gx: int, gy: int):
        if self._drag_start_global is not None and self._drag_win_pos is not None:
            delta = QPoint(gx, gy) - self._drag_start_global
            self.win.move(self._drag_win_pos + delta)

    @Slot()
    def minimizeWindow(self):
        self.win.showMinimized()

    @Slot()
    def closeWindow(self):
        self.win.close()

    def sync_from_app(self):
        """當控制器狀態變更時，觸發通知讓 QML 保持同步。"""
        self.themeChanged.emit(self.get_theme())
        self.characterChanged.emit(self.get_character())
        self.variantChanged.emit(self.get_variant())
        self.sizeChanged.emit(self.get_size_px())
        self.opacityChanged.emit(self.get_opacity_val())
        self.clickThroughChanged.emit(self.get_click_through())
        self.autoSnapChanged.emit(self.get_auto_snap())
        self.alwaysOnTopChanged.emit(self.get_always_on_top())
        self.soundChanged.emit(self.get_sound_enabled())
        self.volumeChanged.emit(self.get_volume())
        self.pureVoiceChanged.emit(self.get_pure_voice_active())
        self.geminiLiveVoiceChanged.emit(self.get_gemini_live_voice())
        self.statusSummaryChanged.emit(self.get_status_summary())
        self.currentFontChanged.emit(self.get_current_font_family())
        self.cueFilesChanged.emit()


class QmlControlWindow(QWidget):
    """承載 Qt Quick / QML 現代動效介面之無邊框圓角視窗。"""

    def __init__(self, app, parent: QWidget | None = None):
        super().__init__(parent)
        self.app = app

        self.setObjectName("QmlControlWindow")
        self.setWindowTitle("設定")
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(840, 620)
        self.setMinimumSize(780, 540)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.quick_widget = QQuickWidget(self)
        self.quick_widget.setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)
        self.quick_widget.setClearColor(Qt.transparent)

        self.backend = QMLBackend(app, self)
        self.quick_widget.rootContext().setContextProperty("backend", self.backend)

        qml_path = self._resolve_qml_path()
        self.quick_widget.setSource(QUrl.fromLocalFile(str(qml_path)))

        layout.addWidget(self.quick_widget)

    @staticmethod
    def _resolve_qml_path() -> Path:
        local_p = Path(__file__).resolve().parent / "qml" / "ModernPanel.qml"
        if local_p.exists():
            return local_p
        if getattr(sys, "frozen", False):
            bundle_p = Path(getattr(sys, "_MEIPASS", "")) / "deskpet" / "qml" / "ModernPanel.qml"
            if bundle_p.exists():
                return bundle_p
        return local_p

    def apply_theme(self):
        """主題變更時通知後端同步。"""
        self.backend.sync_from_app()

    def switch_tab(self, tab: int):
        """切換至指定分頁索引。"""
        self.backend.tabSwitched.emit(tab)

    def showEvent(self, event):
        super().showEvent(event)
        self.backend.sync_from_app()
        self.backend.refreshLogs()
