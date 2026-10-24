"""Persistent settings (JSON + provider.ini / usage.ini compatibility)."""
from __future__ import annotations

import json
import os
import re
import sys
import threading
from datetime import datetime
from pathlib import Path

from .winapi import dpapi_decrypt, dpapi_encrypt

def _get_base_dirs() -> tuple[Path, Path]:
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        bundle_dir = Path(getattr(sys, "_MEIPASS", exe_dir))

        is_writable = False
        test_file = exe_dir / ".perm_check"
        try:
            test_file.touch(exist_ok=True)
            test_file.unlink(missing_ok=True)
            is_writable = True
        except Exception:
            is_writable = False

        if is_writable:
            app_dir = exe_dir
        else:
            appdata = os.environ.get("LOCALAPPDATA")
            if appdata:
                app_dir = Path(appdata) / "DesktopPet"
                app_dir.mkdir(parents=True, exist_ok=True)
            else:
                app_dir = exe_dir

        if (bundle_dir / "assets").exists():
            assets_dir = bundle_dir / "assets"
        elif (exe_dir / "assets").exists():
            assets_dir = exe_dir / "assets"
        elif (exe_dir / "_internal" / "assets").exists():
            assets_dir = exe_dir / "_internal" / "assets"
        else:
            assets_dir = bundle_dir / "assets"

        return app_dir, assets_dir
    else:
        root_dir = Path(__file__).resolve().parent.parent
        return root_dir, root_dir / "assets"


APP_DIR, ASSETS = _get_base_dirs()
CUSTOM_CHARS_DIR = APP_DIR / "custom_characters"
SOUND_LIB_DIR = APP_DIR / "custom_sounds"
CONFIG_PATH = APP_DIR / "pet_config.json"
PROVIDER_INI_PATH = APP_DIR / "provider.ini"
USAGE_INI_PATH = APP_DIR / "usage.ini"
CHARACTER_TXT_PATH = APP_DIR / "character.txt"

APP_VERSION = "v2.1.0"
GITHUB_REPO_URL = "https://github.com/milk120106/deskop-pet"
GITHUB_RELEASES_URL = "https://github.com/milk120106/deskop-pet/releases"
GITHUB_RELEASES_API = "https://api.github.com/repos/milk120106/deskop-pet/releases/latest"

PROV_IDS = ["deepseek", "openai", "anthropic", "gemini"]
PROV_NAMES = ["DeepSeek", "OpenAI", "Anthropic (Claude)", "Google Gemini"]

PROV_ID_MAP = {
    "deepseek": "deepseek",
    "deepseek-chat": "deepseek",
    "openai": "openai",
    "anthropic": "anthropic",
    "claude": "anthropic",
    "gemini": "gemini",
    "google gemini": "gemini",
}


def provider_to_id(p: str) -> str:
    if not p:
        return "deepseek"
    return PROV_ID_MAP.get(str(p).strip().lower(), str(p).strip().lower())


def id_to_provider_name(p: str) -> str:
    pid = provider_to_id(p)
    return {
        "deepseek": "DeepSeek",
        "openai": "OpenAI",
        "anthropic": "Anthropic (Claude)",
        "gemini": "Google Gemini",
    }.get(pid, str(p))


def parse_api_keys(raw: str | list | None) -> list[str]:
    """將清單、換行或逗號/分號分隔之字串解析為獨立 API Key 清單。"""
    if not raw:
        return []
    if isinstance(raw, list):
        res: list[str] = []
        for item in raw:
            res.extend(parse_api_keys(item))
        return res
    if not isinstance(raw, str):
        raw = str(raw)
    tokens = re.split(r"[\r\n,;]+", raw)
    return [t.strip() for t in tokens if t.strip()]


def mask_key_preview(k: str) -> str:
    """產生安全遮蔽字串以供日誌紀錄，不洩漏完整金鑰（無表情符號）。"""
    if not k:
        return ""
    if len(k) <= 8:
        return "***"
    return k[:4] + "***" + k[-4:]

DEFAULTS = {
    # window
    "size": 454,              # pet height in px
    "opacity": 100,           # 20..100
    "always_on_top": True,
    "click_through": False,
    "auto_snap": True,
    "snap_distance": 120,
    "snap_corner": "right",   # left / right (default right)
    "pos": None,              # [x, y]
    "tutorial_shown": False,  # whether novice tutorial has been shown
    # character & look
    "character": "deepseek",  # deepseek / claude / gemini / gpt / custom_<name>
    "variant": "square",      # square (1024x1024) / tail (1536x1024)
    "theme": "light",         # control-panel theme: light / dark
    # performance & rendering
    "disable_transparency": False,
    "disable_blur": False,
    "animations_enabled": True,
    "performance_mode": False,
    "target_fps": 60,         # 10, 15, 20, 24, 30, 45, 60, 90, 120, 144, 240, 0=unlimited
    "vsync_mode": 1,          # 0=off, 1=standard vsync, -1=adaptive/triple buffering
    "rendering_backend": "opengl",  # opengl, d3d11, d3d12, vulkan, software
    # privacy & guardrails
    "privacy_mode": True,
    "zero_data_retention": True,
    # agent mode & security rules
    "chat_dialog_mode": "standard",  # standard / reasoner / voice / agent
    "agent_enabled": True,
    "agent_auto_approve_whitelist": False,
    "security_whitelist_commands": [
        "dir", "echo", "date", "time", "whoami", "hostname", "ver",
        "systeminfo", "tasklist", "ipconfig", "ping", "netstat",
        "get-process", "get-service", "get-date", "get-command"
    ],
    "security_blacklist_commands": [
        "format", "del /f /s /q", "rmdir /s /q", "rm -rf", "reg delete",
        "diskpart", "shutdown", "reboot", "stop-computer", "drop database",
        "vssadmin", "bcdedit", "cipher /w"
    ],
    "security_sensitive_paths": [
        "C:\\Windows\\System32",
        "C:\\Windows",
        "C:\\Program Files",
        "C:\\Program Files (x86)",
    ],
    # custom prompt
    "custom_system_prompt": "",
    # sound
    "sound": True,
    "volume": 80,
    "cue_volumes": {"hit": 80, "feed": 80, "land": 80, "off": 80},
    "cue_custom": {"hit": "", "feed": "", "land": "", "off": ""},
    # balance & providers
    "mode": "sim",            # sim / api
    "provider": "deepseek",   # deepseek / openai / anthropic / gemini
    "sim_balance": 50.0,
    "sim_auto": True,
    "sim_interval": 30,
    "api_keys": {"deepseek": "", "openai": "", "anthropic": "", "gemini": ""},
    "mask_api_keys": False,   # 遮蔽 API Key (預設關閉，開啟後顯示 Password 模式)
    "require_windows_auth": False,  # 要求 Windows 身分驗證 (檢視或修改 API Key 時需驗證 PIN/密碼)
    "budgets": {"openai": 100.0, "anthropic": 100.0},
    "sinces": {"openai": "", "anthropic": ""},
    "poll_ms": 2000,
    "pat": True,              # mouse stroking
    # usage tracking
    "usage_date": "",
    "today_used": 0.0,
    "today_topup": 0.0,
    "web_port": 8765,
    "web_enabled": True,
    # AI chat & profiles
    "ai_chat_enabled": True,
    "api_profiles": [
        {"name": "DeepSeek 預設", "provider": "DeepSeek", "key": "", "endpoint": "https://api.deepseek.com", "model": "deepseek-chat"},
        {"name": "OpenAI 預設", "provider": "OpenAI", "key": "", "endpoint": "https://api.openai.com/v1", "model": "gpt-4o-mini"},
        {"name": "Claude 預設", "provider": "Anthropic", "key": "", "endpoint": "https://api.anthropic.com", "model": "claude-3-5-haiku-latest"},
        {"name": "Gemini 預設", "provider": "Google Gemini", "key": "", "endpoint": "https://generativelanguage.googleapis.com/v1beta", "model": "gemini-3.5-flash-lite"},
    ],
    "active_profile": 0,
    # memory
    "short_memory_limit": 20,
    "short_memory": [],
    "long_memory": [],
    # voice & TTS
    "voice_input_mode": "traditional",
    "voice_auto_send": True,
    "stt_model": "whisper-1",
    "tts_mode": "off",
    "tts_model": "openai/tts-1",
    "tts_voice": "alloy",
    "gemini_live_model": "gemini-3.8-live",
    "gemini_live_voice": "Kore",
    "dynamic_effects": True,
    # Multi-pet balance summons (up to 4 pets)
    "extra_pets": [],
    "extra_pet_positions": {},
    # font settings
    "font_mode": "default",          # default / system / custom_file
    "font_family": "",               # selected system font family
    "custom_font_path": "",          # path to custom .ttf or .otf
    # mini pixel mode & alarms & notifications
    "mini_pixel_mode": False,        # 極小尺寸自動切換像素 Q 版
    "alarms": [],                    # 鬧鐘與倒數計時清單
    "notifications": [],             # 事件通知紀錄歷史
    "discord_webhook_url": "",       # Discord Webhook 轉發網址
    "telegram_bot_token": "",        # Telegram Bot Token
    "telegram_chat_id": "",          # Telegram Chat ID
    # Q-Chibi standalone pixel system
    "q_chibi_enabled": True,         # 啟用全新 Q 版獨立像素小人巡邏
    "q_climb_windows": False,        # 視窗與按鈕攀爬辨識（預設關閉）
    "q_flight_prop": False,          # 飛行小道具（竹蜻蜓 / 氣球飛行模式，預設關閉）
    "q_fireworks_prop": False,       # 像素煙火發射小道具（預設關閉）
}

_lock = threading.Lock()


class Config:
    def __init__(self, path: Path = CONFIG_PATH):
        self.path = path
        self.data = dict(DEFAULTS)
        self._key_indices: dict[str, int] = {}
        self.load()
        self._check_usage_day()

    def _check_usage_day(self):
        today = datetime.now().strftime("%Y-%m-%d")
        if self.data.get("usage_date") != today:
            self.data["usage_date"] = today
            self.data["today_used"] = 0.0
            self.data["today_topup"] = 0.0
            self.save()

    def load(self):
        # 1. Load JSON if present
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                for k, v in raw.items():
                    if k in DEFAULTS:
                        self.data[k] = v

                # 使用 Windows DPAPI 解密還原 api_keys
                if "api_keys" in self.data and isinstance(self.data["api_keys"], dict):
                    decrypted_keys = {}
                    for prov, k_val in self.data["api_keys"].items():
                        if isinstance(k_val, str):
                            decrypted_keys[prov] = dpapi_decrypt(k_val)
                        elif isinstance(k_val, list):
                            decrypted_keys[prov] = [dpapi_decrypt(x) for x in k_val]
                        else:
                            decrypted_keys[prov] = k_val
                    self.data["api_keys"] = decrypted_keys

                # 使用 Windows DPAPI 解密還原 api_profiles 中的 key
                if "api_profiles" in self.data and isinstance(self.data["api_profiles"], list):
                    for prof in self.data["api_profiles"]:
                        if isinstance(prof, dict) and "key" in prof:
                            k = prof.get("key")
                            if isinstance(k, str):
                                prof["key"] = dpapi_decrypt(k)
        except (OSError, ValueError):
            pass

        # 2. Check character.txt
        if CHARACTER_TXT_PATH.exists():
            try:
                ch = CHARACTER_TXT_PATH.read_text(encoding="utf-8").strip()
                if ch:
                    self.data["character"] = ch
            except OSError:
                pass

        # 3. Check provider.ini
        if PROVIDER_INI_PATH.exists():
            try:
                for line in PROVIDER_INI_PATH.read_text(encoding="utf-8").splitlines():
                    if "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k, v = k.strip(), v.strip()
                    if k == "mode" and v in ("sim", "api"):
                        self.data["mode"] = v
                    elif k == "provider" and v in PROV_IDS:
                        self.data["provider"] = v
                    elif k.startswith("budget_"):
                        p = k[7:]
                        try:
                            self.data["budgets"][p] = float(v)
                        except (ValueError, KeyError):
                            pass
                    elif k.startswith("since_"):
                        p = k[6:]
                        if p in self.data["sinces"]:
                            self.data["sinces"][p] = v
            except OSError:
                pass

        # 4. Check legacy API key files (相容舊版單次載入)
        for p in PROV_IDS:
            fname = "apikey.txt" if p == "deepseek" else f"apikey_{p}.txt"
            p_file = APP_DIR / fname
            if p_file.exists():
                try:
                    k = p_file.read_text(encoding="utf-8").strip()
                    if k and not self.data["api_keys"].get(p):
                        self.data["api_keys"][p] = k
                except OSError:
                    pass

        # Set default since date to beginning of current month if empty
        month_start = datetime.now().strftime("%Y-%m-01")
        for p in ("openai", "anthropic"):
            if not self.data["sinces"].get(p):
                self.data["sinces"][p] = month_start

    def save(self):
        with _lock:
            try:
                # 建立寫入磁碟複本，確保 pet_config.json 中的金鑰皆以 Windows DPAPI 加密存儲，絕不以明文外洩！
                save_data = json.loads(json.dumps(self.data, ensure_ascii=False))

                # 加密 api_keys
                if "api_keys" in save_data and isinstance(save_data["api_keys"], dict):
                    for prov, k_val in save_data["api_keys"].items():
                        if isinstance(k_val, str) and k_val.strip():
                            save_data["api_keys"][prov] = dpapi_encrypt(k_val.strip())
                        elif isinstance(k_val, list):
                            save_data["api_keys"][prov] = [
                                dpapi_encrypt(str(x).strip()) for x in k_val if str(x).strip()
                            ]

                # 加密 api_profiles 中的 key
                if "api_profiles" in save_data and isinstance(save_data["api_profiles"], list):
                    for prof in save_data["api_profiles"]:
                        if isinstance(prof, dict) and prof.get("key"):
                            prof["key"] = dpapi_encrypt(str(prof["key"]).strip())

                tmp = self.path.with_suffix(".tmp")
                tmp.write_text(json.dumps(save_data, ensure_ascii=False, indent=2), encoding="utf-8")
                os.replace(tmp, self.path)
            except OSError as exc:
                log(f"儲存設定檔失敗: {exc}")

            # Sync to character.txt
            try:
                CHARACTER_TXT_PATH.write_text(self.data.get("character", "deepseek"), encoding="utf-8")
            except OSError:
                pass

            # Sync to provider.ini
            try:
                lines = [
                    f"mode={self.data.get('mode', 'sim')}",
                    f"provider={self.data.get('provider', 'deepseek')}",
                ]
                for p in ("openai", "anthropic"):
                    b = self.data["budgets"].get(p, 100.0)
                    s = self.data["sinces"].get(p, "")
                    lines.append(f"budget_{p}={b}")
                    lines.append(f"since_{p}={s}")
                PROVIDER_INI_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
            except OSError:
                pass

    def get_api_keys(self, provider: str) -> list[str]:
        """取得指定供應商配置的所有可用 API Key 清單（支援清單、換行或逗號/分號分隔）。"""
        prov_id = provider_to_id(provider)
        keys_dict = self.data.get("api_keys") or {}
        raw = keys_dict.get(prov_id) or keys_dict.get(provider)
        keys = parse_api_keys(raw)
        if keys:
            return keys

        # 若 api_keys 未設定，檢查 api_profiles 中匹配的設定檔 key
        prov_name = id_to_provider_name(provider)
        for p in self.data.get("api_profiles", []):
            if p.get("provider") in (provider, prov_name, prov_id, "Anthropic" if prov_id == "anthropic" else ""):
                p_keys = parse_api_keys(p.get("key"))
                if p_keys:
                    return p_keys

        # 檢查環境變數
        if prov_id == "deepseek":
            k = os.environ.get("DESKPET_KEY", "").strip() or os.environ.get("DSHPET_KEY", "").strip() or os.environ.get("DEEPSEEK_API_KEY", "").strip()
            if k:
                return parse_api_keys(k)
            try:
                p = Path(os.path.expanduser("~")) / ".dsh" / ".credentials.yaml"
                m = re.search(r"DEEPSEEK_API_KEY\s*:\s*['\"]?([^\s'\"#]+)", p.read_text(encoding="utf-8"))
                if m:
                    return [m.group(1)]
            except OSError:
                pass
        elif prov_id == "openai":
            k = os.environ.get("OPENAI_API_KEY", "").strip()
            if k:
                return parse_api_keys(k)
        elif prov_id == "anthropic":
            k = os.environ.get("ANTHROPIC_API_KEY", "").strip()
            if k:
                return parse_api_keys(k)
        elif prov_id == "gemini":
            k = os.environ.get("GEMINI_API_KEY", "").strip()
            if k:
                return parse_api_keys(k)

        return []

    def get_current_api_key(self, provider: str) -> str:
        """取得指定供應商目前生效的 API Key。"""
        keys = self.get_api_keys(provider)
        if not keys:
            return ""
        prov_id = provider_to_id(provider)
        idx = self._key_indices.get(prov_id, 0)
        if idx >= len(keys) or idx < 0:
            idx = 0
            self._key_indices[prov_id] = 0
        return keys[idx]

    def rotate_api_key(self, provider: str) -> str:
        """將指定供應商之 API Key 輪替至下一組備用 Key，並記錄日誌。"""
        keys = self.get_api_keys(provider)
        if not keys:
            return ""
        prov_id = provider_to_id(provider)
        if len(keys) <= 1:
            log(f"[{provider}] 目前僅配置 1 組金鑰，維持目前金鑰")
            return keys[0]
        cur_idx = self._key_indices.get(prov_id, 0)
        new_idx = (cur_idx + 1) % len(keys)
        self._key_indices[prov_id] = new_idx
        old_preview = mask_key_preview(keys[cur_idx])
        new_preview = mask_key_preview(keys[new_idx])
        log(f"[{provider}] API Key 自動輪替：從第 {cur_idx + 1} 組 ({old_preview}) 切換至第 {new_idx + 1} 組 ({new_preview}) / 共 {len(keys)} 組")
        return keys[new_idx]

    def set_api_keys(self, provider: str, keys: str | list[str], save: bool = True):
        prov_id = provider_to_id(provider)
        if "api_keys" not in self.data:
            self.data["api_keys"] = {}
        if isinstance(keys, list):
            self.data["api_keys"][prov_id] = ", ".join(keys)
        else:
            self.data["api_keys"][prov_id] = str(keys).strip()
        self._key_indices[prov_id] = 0
        if save:
            self.save()

    def __getitem__(self, k):
        return self.data[k]

    def get(self, k, default=None):
        return self.data.get(k, default)

    def set(self, k, v, save=True):
        self.data[k] = v
        if save:
            self.save()


def find_api_key(cfg: Config, provider: str = "deepseek") -> str:
    """相容性介面：回傳目前生效的 API Key。"""
    return cfg.get_current_api_key(provider)


def asset(*parts: str) -> str:
    return str(ASSETS.joinpath(*parts))


def log(*args):
    try:
        from .logger import get_logger
        if len(args) == 1:
            get_logger().info(str(args[0]), source="Pet")
        elif len(args) >= 2:
            get_logger().info(str(args[1]), source=str(args[0]))
    except Exception:
        if sys.stdout:
            try:
                print(" ".join(str(a) for a in args))
            except Exception:
                pass
