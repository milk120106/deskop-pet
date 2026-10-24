"""AI 對話視窗、語音錄音與語音合成、記憶系統與背景工作執行緒。
完全遵循純文字與繁體中文排版，嚴格禁止任何表情符號 (No Emojis)。
"""
from __future__ import annotations

import asyncio
import json
import math
import os
import random
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QEasingCurve, QPoint, QPointF, QPropertyAnimation, QRect, QRectF, QSize, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QGuiApplication, QIcon, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .config import APP_DIR, ASSETS, Config, log
from .dialogs import ModernMessageBox
from .icons import get_icon
from .model_catalog import OPENAI_BASES, PROVIDERS, ModelCatalogError, discover_models
from .titlebar import CustomTitleBar

ARROW_DOWN_DARK = (ASSETS / "arrow_down_dark.svg").as_posix()
ARROW_DOWN_LIGHT = (ASSETS / "arrow_down_light.svg").as_posix()

VOICE_DIR = APP_DIR / "voice_cache"
VOSK_MODEL = APP_DIR / "models" / "vosk-model-small-cn-0.22"


class PrivacySanitizer:
    """第三方推論隱私優先模式正則脫敏過濾器：
    對本機檔案路徑、API Key/Token、私有 IP、本機使用者名稱進行語義標籤替換。
    """
    _KEY_PATTERNS = [
        re.compile(r'\b(sk-[a-zA-Z0-9_\-]{20,})\b'),
        re.compile(r'\b(ghp_[a-zA-Z0-9]{36,})\b'),
        re.compile(r'\b(AIza[0-9A-Za-z\-_]{35})\b'),
        re.compile(r'(?i)bearer\s+([a-zA-Z0-9_\-\.]{20,})'),
        re.compile(r'(?i)(?:api[_-]?key|secret|token)\s*[:=]\s*["\']?([a-zA-Z0-9_\-]{16,})["\']?'),
    ]

    _PATH_WIN = re.compile(r'\b[a-zA-Z]:\\(?:[^\\/:*?"<>|\r\n]+\\)*[^\\/:*?"<>|\r\n]*')
    _PATH_UNIX = re.compile(r'\b/(?:home|Users|etc|var|usr|opt)/[^\s"\'<>]+')

    _PRIVATE_IPS = [
        re.compile(r'\b10\.\d{1,3}\.\d{1,3}\.\d{1,3}\b'),
        re.compile(r'\b192\.168\.\d{1,3}\.\d{1,3}\b'),
        re.compile(r'\b172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}\b'),
        re.compile(r'\b127\.0\.0\.1\b'),
    ]

    @classmethod
    def sanitize(cls, text: str) -> str:
        if not text or not isinstance(text, str):
            return text

        result = text

        # 1. 本機使用者名稱替換
        username = os.environ.get("USERNAME") or os.environ.get("USER") or ""
        if username and len(username) >= 2:
            result = re.sub(re.escape(username), "[本機使用者名稱]", result, flags=re.IGNORECASE)

        # 2. API Key / Token 脫敏
        for pat in cls._KEY_PATTERNS:
            def _key_repl(m):
                full = m.group(0)
                secret = m.group(1) if m.groups() else full
                return full.replace(secret, "[金鑰憑證]")
            result = pat.sub(_key_repl, result)

        # 3. 本機檔案路徑脫敏
        result = cls._PATH_WIN.sub("[本機檔案路徑]", result)
        result = cls._PATH_UNIX.sub("[本機檔案路徑]", result)

        # 4. 私有 IP 脫敏
        for pat in cls._PRIVATE_IPS:
            result = pat.sub("[私有IP位址]", result)

        return result


COMPANION_LINES = [
    "今天也要記得適度休息一下。",
    "我有看到你在認真努力喔。",
    "要不要餵我吃一點飯盆呢？",
    "目前沒有設定 AI 金鑰或連線失敗，我先用隨機文句陪你。",
    "桌面巡邏完成，目前一切平安。",
    "今天的狀態：可愛而且精神飽滿。",
    "記得多喝水，別讓自己太累了。",
    "我會一直在這裡陪著你。",
]

# Material Design 3 QSS for Auxiliary Dialogs
MD3_LIGHT = """
QDialog {
    background: #fdfbff;
    color: #1a1c1e;
    border: 1px solid #c4c7c5;
    border-radius: 14px;
}
QLabel {
    color: #1a1c1e;
    font-size: 13px;
}
QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox {
    background: #f1f4f9;
    color: #1a1c1e;
    border: 1px solid #74777f;
    border-radius: 8px;
    padding: 6px 10px;
    selection-background-color: #0b57d0;
    selection-color: #ffffff;
}
QLineEdit:focus, QTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 2px solid #0b57d0;
    background: #ffffff;
}
QComboBox {
    background: #f1f4f9;
    color: #1a1c1e;
    border: 1px solid #74777f;
    border-radius: 8px;
    padding: 6px 28px 6px 10px;
    selection-background-color: #0b57d0;
    selection-color: #ffffff;
}
QComboBox:hover {
    border-color: #0b57d0;
}
QComboBox:focus {
    border: 2px solid #0b57d0;
    background: #ffffff;
    padding: 5px 27px 5px 9px;
}
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 26px;
    border: none;
    background-color: transparent;
}
QComboBox::down-arrow {
    image: url("__ARROW_DOWN_LIGHT__");
    width: 10px;
    height: 7px;
}
QComboBox QAbstractItemView {
    background-color: #ffffff;
    border: 1px solid #74777f;
    border-radius: 8px;
    selection-background-color: #dbeafe;
    selection-color: #1d4ed8;
    padding: 4px;
    outline: none;
    color: #1a1c1e;
}
QPushButton {
    background: #0b57d0;
    color: #ffffff;
    font-weight: bold;
    border: none;
    border-radius: 16px;
    padding: 6px 16px;
    min-height: 24px;
}
QPushButton:hover {
    background: #0842a0;
}
QPushButton:pressed {
    background: #042e6f;
}
QPushButton:checked {
    background: #ba1a1a;
    color: #ffffff;
}
QPushButton#secondary {
    background: #e1e3e1;
    color: #1d1b20;
    border: 1px solid #74777f;
}
QPushButton#secondary:hover {
    background: #d3d6d3;
}
QPushButton#danger {
    background: #ba1a1a;
    color: #ffffff;
}
QListWidget {
    background: #f1f4f9;
    color: #1a1c1e;
    border: 1px solid #c4c7c5;
    border-radius: 8px;
    padding: 4px;
}
QListWidget::item:selected {
    background: #d3e3fd;
    color: #041e49;
    border-radius: 6px;
}
QScrollBar:vertical {
    background: transparent;
    width: 8px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #c4c7c5;
    border-radius: 4px;
    min-height: 24px;
}
"""

MD3_DARK = """
QDialog {
    background: #141218;
    color: #e6e0e9;
    border: 1px solid #49454f;
    border-radius: 14px;
}
QLabel {
    color: #e6e0e9;
    font-size: 13px;
}
QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox {
    background: #211f26;
    color: #e6e0e9;
    border: 1px solid #79747e;
    border-radius: 8px;
    padding: 6px 10px;
    selection-background-color: #a8c7fa;
    selection-color: #041e49;
}
QLineEdit:focus, QTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 2px solid #a8c7fa;
    background: #2b2930;
}
QComboBox {
    background: #211f26;
    color: #e6e0e9;
    border: 1px solid #79747e;
    border-radius: 8px;
    padding: 6px 28px 6px 10px;
    selection-background-color: #a8c7fa;
    selection-color: #041e49;
}
QComboBox:hover {
    border-color: #a8c7fa;
}
QComboBox:focus {
    border: 2px solid #a8c7fa;
    background: #2b2930;
    padding: 5px 27px 5px 9px;
}
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 26px;
    border: none;
    background-color: transparent;
}
QComboBox::down-arrow {
    image: url("__ARROW_DOWN_DARK__");
    width: 10px;
    height: 7px;
}
QComboBox QAbstractItemView {
    background-color: #211f26;
    border: 1px solid #79747e;
    border-radius: 8px;
    selection-background-color: #2c3954;
    selection-color: #93c5fd;
    padding: 4px;
    outline: none;
    color: #e6e0e9;
}
QPushButton {
    background: #a8c7fa;
    color: #041e49;
    font-weight: bold;
    border: none;
    border-radius: 16px;
    padding: 6px 16px;
    min-height: 24px;
}
QPushButton:hover {
    background: #8ab4f8;
}
QPushButton:pressed {
    background: #669df6;
}
QPushButton:checked {
    background: #ffb4ab;
    color: #690005;
}
QPushButton#secondary {
    background: #2b2930;
    color: #e6e0e9;
    border: 1px solid #79747e;
}
QPushButton#secondary:hover {
    background: #36343b;
}
QPushButton#danger {
    background: #93000a;
    color: #ffdad6;
}
QListWidget {
    background: #211f26;
    color: #e6e0e9;
    border: 1px solid #49454f;
    border-radius: 8px;
    padding: 4px;
}
QListWidget::item:selected {
    background: #004a77;
    color: #c2e7ff;
    border-radius: 6px;
}
QScrollBar:vertical {
    background: transparent;
    width: 8px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #49454f;
    border-radius: 4px;
    min-height: 24px;
}
"""

MD3_LIGHT = MD3_LIGHT.replace("__ARROW_DOWN_LIGHT__", ARROW_DOWN_LIGHT)
MD3_DARK = MD3_DARK.replace("__ARROW_DOWN_DARK__", ARROW_DOWN_DARK)


def _get_qss(theme: str) -> str:
    return MD3_DARK if theme == "dark" else MD3_LIGHT


# ==============================================================================
# 1. AI 呼叫封裝（支援 LiteLLM 與直接 HTTP Fallback）
# ==============================================================================
PREFIX_MAP = {
    "DeepSeek": "deepseek/",
    "Google Gemini": "gemini/",
    "Anthropic": "anthropic/",
    "Mistral": "mistral/",
    "xAI / Grok": "xai/",
    "Groq": "groq/",
    "OpenRouter": "openrouter/",
    "Ollama": "ollama/",
    "Ollama Cloud": "ollama_chat/",
    "Cloudflare AI": "cloudflare/",
    "Hugging Face": "huggingface/",
    "z.ai": "openai/",
    "GLM": "openai/",
    "Cerebras": "cerebras/",
    "Together AI": "together_ai/",
    "Fireworks AI": "fireworks_ai/",
    "DeepInfra": "deepinfra/",
    "矽基流動 (SiliconFlow)": "openai/",
    "SiliconFlow": "openai/",
    "月之暗面 (Moonshot/Kimi)": "moonshot/",
    "Moonshot": "moonshot/",
    "本地 LM Studio": "openai/",
    "LM Studio": "openai/",
    "本地 vLLM": "openai/",
    "vLLM": "openai/",
    "OpenAI 相容自訂端點": "openai/",
}

DEFAULT_MODELS = {
    "DeepSeek": "deepseek-chat",
    "OpenAI": "gpt-4o-mini",
    "Google Gemini": "gemini-3.8-flash-lite",
    "Anthropic": "claude-3-5-haiku-latest",
    "Mistral": "mistral-small-latest",
    "xAI / Grok": "grok-3-mini",
    "Ollama": "llama3.2",
    "Ollama Cloud": "llama3.2",
    "OpenRouter": "auto",
    "Groq": "llama-3.3-70b-versatile",
    "Cerebras": "llama-3.3-70b",
    "Together AI": "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
    "Fireworks AI": "accounts/fireworks/models/llama-v3p3-70b-instruct",
    "DeepInfra": "meta-llama/Llama-3.3-70B-Instruct",
    "矽基流動 (SiliconFlow)": "deepseek-ai/DeepSeek-V3",
    "SiliconFlow": "deepseek-ai/DeepSeek-V3",
    "月之暗面 (Moonshot/Kimi)": "moonshot-v1-8k",
    "Moonshot": "moonshot-v1-8k",
    "本地 LM Studio": "local-model",
    "LM Studio": "local-model",
    "本地 vLLM": "default",
    "vLLM": "default",
}


def _is_retryable_auth_or_quota_error(exc: Exception) -> tuple[bool, str]:
    """判斷異常是否為可自動輪替金鑰之錯誤 (401, 403, 429, Quota, Rate Limit, Auth failure)。"""
    if isinstance(exc, urllib.error.HTTPError):
        if exc.code in (401, 403, 429):
            return True, f"HTTP {exc.code}"
    msg = str(exc).lower()
    patterns = [
        "429", "401", "403", "quota", "rate limit", "rate_limit",
        "unauthorized", "authentication", "invalid_api_key",
        "invalid api key", "insufficient_quota", "resource_exhausted",
        "credit balance", "overloaded", "exceeded your current quota"
    ]
    for pat in patterns:
        if pat in msg:
            return True, pat
    return False, ""


def _call_via_urllib(profile: dict, prompt: str) -> str:
    """純 Python 標準庫 urllib 直接呼叫各廠商，完全無需任何額外第三方庫。"""
    provider = profile.get("provider", "DeepSeek")
    key = profile.get("key", "").strip()
    endpoint = profile.get("endpoint", "").strip().rstrip("/")
    model = profile.get("model", "").strip() or DEFAULT_MODELS.get(provider, "deepseek-chat")

    if provider == "Google Gemini":
        url = endpoint or "https://generativelanguage.googleapis.com/v1beta"
        url = f"{url}/models/{model}:generateContent?key={key}"
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "User-Agent": "DesktopPet/2.1.0"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        cands = data.get("candidates") or []
        if cands:
            parts = cands[0].get("content", {}).get("parts", [])
            if parts:
                return parts[0].get("text", "").strip()
        raise RuntimeError("Gemini 回傳內容為空")

    elif provider == "Anthropic":
        url = endpoint or "https://api.anthropic.com"
        url = url if url.endswith("/messages") else f"{url}/v1/messages"
        payload = {
            "model": model,
            "max_tokens": 300,
            "messages": [{"role": "user", "content": prompt}],
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
                "User-Agent": "DesktopPet/2.1.0",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        contents = data.get("content") or []
        if contents:
            return contents[0].get("text", "").strip()
        raise RuntimeError("Claude 回傳內容為空")

    else:
        # Standard OpenAI-compatible chat completions
        base = endpoint or OPENAI_BASES.get(provider, "https://api.openai.com/v1")
        if base.endswith("/chat/completions"):
            url = base
        elif base.endswith("/v1"):
            url = f"{base}/chat/completions"
        else:
            url = f"{base}/v1/chat/completions" if "/v1" not in base else f"{base}/chat/completions"

        headers = {"Content-Type": "application/json", "User-Agent": "DesktopPet/2.1.0"}
        if key:
            headers["Authorization"] = f"Bearer {key}"

        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 300,
        }
        # 第三方推論隱私優先：自動注入零儲存參數
        prov_lower = str(provider).lower()
        if "openrouter" in prov_lower or "openrouter.ai" in url:
            payload["provider"] = {"data_collection": "deny", "zdr": True}
        elif "mistral" in prov_lower:
            payload["safe_prompt"] = True
        else:
            payload["store"] = False
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        choices = data.get("choices") or []
        if choices:
            msg = choices[0].get("message", {}).get("content", "")
            return msg.strip()
        raise RuntimeError("AI 回傳內容為空")


def execute_chat(profile: dict, prompt: str, cfg: Config | None = None) -> str:
    """呼叫 AI 完成對話，支援多組 API Key 自動輪替（遭遇 429/401 或驗證錯誤自動切換備用 Key 重試）。"""
    if cfg and cfg.get("privacy_mode", True):
        prompt = PrivacySanitizer.sanitize(prompt)

    provider = profile.get("provider", "DeepSeek")
    raw_key = profile.get("key", "").strip()
    keys = parse_api_keys(raw_key)
    if not keys and cfg:
        keys = cfg.get_api_keys(provider)

    if not keys:
        keys = [""]

    cur_key = cfg.get_current_api_key(provider) if cfg else ""
    if cur_key and cur_key in keys:
        start_idx = keys.index(cur_key)
        ordered_keys = keys[start_idx:] + keys[:start_idx]
    else:
        ordered_keys = list(keys)

    endpoint = profile.get("endpoint", "").strip().rstrip("/")
    model = profile.get("model", "").strip() or DEFAULT_MODELS.get(provider, "")
    last_err = None

    for i, active_key in enumerate(ordered_keys):
        prof_attempt = dict(profile)
        prof_attempt["key"] = active_key

        # 1. 優先嘗試 LiteLLM
        try:
            from litellm import completion

            prefix = PREFIX_MAP.get(provider, "")
            full_model = model
            if prefix and not model.startswith(prefix) and not model.startswith(("ollama/", "openai/")):
                full_model = prefix + model

            kwargs = {
                "model": full_model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 300,
            }
            extra_body = {}
            prov_lower = str(provider).lower()
            if "openrouter" in prov_lower:
                extra_body["provider"] = {"data_collection": "deny", "zdr": True}
            elif "mistral" in prov_lower:
                extra_body["safe_prompt"] = True
            else:
                extra_body["store"] = False
            kwargs["extra_body"] = extra_body
            if active_key:
                kwargs["api_key"] = active_key
            if endpoint:
                kwargs["api_base"] = endpoint
            resp = completion(**kwargs)
            if resp and resp.choices:
                return resp.choices[0].message.content.strip()
        except Exception as e:
            is_auth_quota, reason = _is_retryable_auth_or_quota_error(e)
            if is_auth_quota and i < len(ordered_keys) - 1:
                if cfg:
                    cfg.rotate_api_key(provider)
                log(f"[{provider}] LiteLLM 對話遭遇 {reason}，自動輪替至下一組金鑰重試")
                continue
            log(f"LiteLLM 呼叫跳過或失敗，嘗試直接 HTTP 呼叫: {e}")

        # 2. 原生 HTTP Fallback
        try:
            return _call_via_urllib(prof_attempt, prompt)
        except Exception as e:
            last_err = e
            is_auth_quota, reason = _is_retryable_auth_or_quota_error(e)
            if is_auth_quota and i < len(ordered_keys) - 1:
                if cfg:
                    cfg.rotate_api_key(provider)
                log(f"[{provider}] 原生 HTTP 對話遭遇 {reason}，自動輪替至下一組金鑰重試")
                continue
            raise e

    if last_err:
        raise last_err
    raise RuntimeError("對話請求未執行或金鑰集為空")


# ==============================================================================
# 2. 背景工作執行緒 (Workers)
# ==============================================================================
class ChatWorker(QThread):
    done = Signal(bool, str, str)  # (ok, reply_text, error_info)

    def __init__(self, profile: dict, prompt: str, parent=None, cfg: Config | None = None):
        super().__init__(parent)
        self.profile = dict(profile)
        self.prompt = prompt
        self.cfg = cfg

    def run(self):
        try:
            prov = self.profile.get("provider", "")
            reply = execute_chat(self.profile, self.prompt, cfg=self.cfg)
            if not reply:
                reply = random.choice(COMPANION_LINES)
            self.done.emit(True, reply, "")
        except Exception as exc:
            log(f"ChatWorker 執行失敗: {exc}")
            fallback = random.choice(COMPANION_LINES)
            self.done.emit(False, fallback, str(exc))


class VoiceRecorder(QThread):
    finished = Signal(str)
    partial = Signal(str)
    level = Signal(int)
    failed = Signal(str)

    def __init__(self, traditional: bool = False, vad_enabled: bool = False, parent=None):
        super().__init__(parent)
        self.traditional = traditional
        self.vad_enabled = vad_enabled
        self.stop_event = threading.Event()
        self.frames = []
        self._has_spoken = False
        self._last_speech_time = 0.0

    def run(self):
        try:
            import numpy as np
            import sounddevice as sd
            import soundfile as sf
        except ImportError:
            self.failed.emit("尚未安裝 sounddevice/soundfile 音訊庫，請安裝 requirements.txt")
            return

        try:
            # 檢查可用輸入設備
            devs = sd.query_devices()
            has_input = any(d.get("max_input_channels", 0) > 0 for d in devs)
            if not has_input:
                self.failed.emit("未檢測到可用的麥克風輸入裝置")
                return

            recognizer = None
            _json = None
            if self.traditional and VOSK_MODEL.exists():
                try:
                    import json as _json
                    import vosk

                    recognizer = vosk.KaldiRecognizer(vosk.Model(str(VOSK_MODEL)), 16000)
                except Exception as e:
                    log(f"Vosk 初始化失敗: {e}")

            VOICE_DIR.mkdir(parents=True, exist_ok=True)
            path = VOICE_DIR / f"recording_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"

            def callback(indata, frames, time_info, status):
                self.frames.append(indata.copy())
                vol = min(100, int(float(np.abs(indata).mean()) * 900))
                self.level.emit(vol)

                if self.vad_enabled:
                    now = time.monotonic()
                    if vol >= 10:
                        self._has_spoken = True
                        self._last_speech_time = now
                    elif self._has_spoken and (now - self._last_speech_time > 1.8):
                        self.stop_event.set()

                if recognizer and _json:
                    recognizer.AcceptWaveform((indata[:, 0] * 32767).astype(np.int16).tobytes())
                    partial = _json.loads(recognizer.PartialResult()).get("partial", "")
                    if partial:
                        self.partial.emit(partial)

            started = time.monotonic()
            with sd.InputStream(samplerate=16000, channels=1, dtype="float32", callback=callback):
                while not self.stop_event.wait(0.05):
                    if time.monotonic() - started >= 120:
                        break

            audio_data = np.concatenate(self.frames, axis=0) if self.frames else np.zeros((1, 1), dtype="float32")
            sf.write(str(path), audio_data, 16000, subtype="PCM_16")
            self.finished.emit(str(path))
        except Exception as e:
            self.failed.emit(str(e))

    def stop(self):
        self.stop_event.set()


class VoiceTranscriber(QThread):
    finished = Signal(bool, str)

    def __init__(self, path: str, mode: str, profile: dict, all_profiles: list | None = None, parent=None):
        super().__init__(parent)
        self.path = path
        self.mode = mode
        self.profile = profile
        self.all_profiles = all_profiles or []

    def run(self):
        try:
            text = ""
            # 優先嘗試本機 Vosk（若設定為 traditional 且模型目錄存在）
            if self.mode == "traditional" and VOSK_MODEL.exists():
                import wave
                import vosk

                model = vosk.Model(str(VOSK_MODEL))
                wf = wave.open(self.path, "rb")
                rec = vosk.KaldiRecognizer(model, wf.getframerate())
                while True:
                    data = wf.readframes(4000)
                    if not data:
                        break
                    rec.AcceptWaveform(data)
                res = json.loads(rec.FinalResult())
                text = (res.get("text", "") or "").replace(" ", "")
            elif self.mode == "faster-whisper":
                try:
                    from faster_whisper import WhisperModel
                    fw_model = WhisperModel("base", device="cpu", compute_type="int8")
                    segments, _ = fw_model.transcribe(self.path, language="zh")
                    text = "".join(segment.text for segment in segments).strip()
                except ImportError:
                    pass
            if not text:
                # 雲端 AI 語音辨識（或 traditional 缺少模型時自動降級至可用金鑰）
                prof = self.profile
                if not prof.get("key", "").strip():
                    for p in self.all_profiles:
                        if p.get("key", "").strip() and p.get("provider") in ("Google Gemini", "OpenAI", "Groq"):
                            prof = p
                            break

                prov = prof.get("provider", "")
                raw_key = prof.get("key", "").strip()
                keys = parse_api_keys(raw_key) if raw_key else []

                if prov == "Google Gemini" and keys:
                    from google import genai
                    from google.genai import types

                    client = genai.Client(api_key=keys[0])
                    with open(self.path, "rb") as f:
                        audio_data = f.read()
                    resp = client.models.generate_content(
                        model="gemini-3.8-flash",
                        contents=[
                            types.Part.from_bytes(data=audio_data, mime_type="audio/wav"),
                            "請將這段語音轉錄為純文字繁體中文。請只輸出轉錄文字內容，不可包含任何說明、問候、標籤或 Markdown 符號。"
                        ]
                    )
                    text = (resp.text or "").strip()
                elif (prov == "Groq" or "groq" in (prof.get("endpoint") or "").lower()) and keys:
                    from litellm import transcription
                    with open(self.path, "rb") as f:
                        result = transcription(
                            model="groq/whisper-large-v3",
                            file=f,
                            api_key=keys[0] or None,
                        )
                    text = getattr(result, "text", "") or (result.get("text", "") if isinstance(result, dict) else "")
                    text = (text or "").strip()
                elif keys:
                    from litellm import transcription

                    with open(self.path, "rb") as f:
                        result = transcription(
                            model=prof.get("stt_model") or "whisper-1",
                            file=f,
                            api_key=keys[0] or None,
                            api_base=prof.get("endpoint") or None,
                        )
                    text = getattr(result, "text", "") or (result.get("text", "") if isinstance(result, dict) else "")
                    text = (text or "").strip()
                else:
                    if self.mode == "traditional":
                        raise RuntimeError("找不到本機 Vosk 模型（請執行 download_voice_model.bat），且未設定雲端 API 金鑰。")
                    else:
                        raise RuntimeError("雲端語音辨識需要 Google Gemini 或 OpenAI API Key，請先於設定中配置。")

            if text:
                self.finished.emit(True, text.strip())
            else:
                self.finished.emit(False, "語音內容過短或未能識別清晰文字")
        except Exception as e:
            self.finished.emit(False, str(e))


class TTSWorker(QThread):
    finished = Signal(bool, str)

    def __init__(self, text: str, mode: str, profile: dict, parent=None):
        super().__init__(parent)
        self.text = text
        self.mode = mode
        self.profile = profile

    def run(self):
        try:
            VOICE_DIR.mkdir(parents=True, exist_ok=True)
            tts_model = self.profile.get("tts_model") or ""
            prov = self.profile.get("provider", "")
            raw_key = self.profile.get("key", "").strip()
            keys = parse_api_keys(raw_key) if raw_key else []

            # 1. 傳統本機語音 (pyttsx3)
            if self.mode == "traditional" or self.mode == "pyttsx3":
                import pyttsx3

                engine = pyttsx3.init()
                engine.say(self.text)
                engine.runAndWait()
                self.finished.emit(True, "")
                return

            # 2. Edge-TTS 語音整合骨幹
            if self.mode == "edge" or "edge" in tts_model.lower():
                try:
                    import edge_tts
                    path = str(VOICE_DIR / f"edge_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3")
                    voice = self.profile.get("tts_voice") or "zh-TW-HsiaoChenNeural"
                    communicate = edge_tts.Communicate(self.text, voice)
                    asyncio.run(communicate.save(path))
                    self.finished.emit(True, path)
                    return
                except Exception:
                    pass

            # 3. Google Gemini 2.0 Audio Modality / Gemini TTS
            if prov == "Google Gemini" or "gemini" in tts_model.lower():
                if keys:
                    try:
                        from google import genai
                        from google.genai import types

                        client = genai.Client(api_key=keys[0])
                        path = str(VOICE_DIR / f"gemini_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav")
                        resp = client.models.generate_content(
                            model=self.profile.get("model") or "gemini-3.8-flash",
                            contents=f"請以繁體中文朗讀以下文字，不要有任何其他回應：{self.text}",
                            config=types.GenerateContentConfig(
                                response_modalities=["AUDIO"],
                                speech_config=types.SpeechConfig(
                                    voice_config=types.VoiceConfig(
                                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                            voice_name=self.profile.get("tts_voice") or "Kore"
                                        )
                                    )
                                )
                            )
                        )
                        if resp.candidates and resp.candidates[0].content and resp.candidates[0].content.parts:
                            for part in resp.candidates[0].content.parts:
                                if getattr(part, "inline_data", None) and part.inline_data.data:
                                    with open(path, "wb") as f:
                                        f.write(part.inline_data.data)
                                    self.finished.emit(True, path)
                                    return
                    except Exception:
                        pass

            # 4. LiteLLM / OpenAI 相容 TTS
            from litellm import speech

            path = VOICE_DIR / f"tts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3"
            result = speech(
                model=self.profile.get("tts_model") or "openai/tts-1",
                voice=self.profile.get("tts_voice") or "alloy",
                input=self.text,
                api_key=keys[0] if keys else None,
                api_base=self.profile.get("endpoint") or None,
            )
            result.stream_to_file(path)
            self.finished.emit(True, str(path))
        except Exception as e:
            self.finished.emit(False, str(e))


class GeminiLiveWorker(QThread):
    finished = Signal(bool, dict)

    def __init__(self, path: str, profile: dict, system_instruction: str = "", model: str = "gemini-flash-latest", voice: str = "Kore", parent=None):
        super().__init__(parent)
        self.path = path
        self.profile = profile
        self.system_instruction = system_instruction
        self.model = model
        self.voice = voice
        self.cancel_event = threading.Event()
        self.timeout_seconds = 180

    def run(self):
        try:
            raw_key = self.profile.get("key", "").strip()
            keys = parse_api_keys(raw_key)
            if not keys:
                raise RuntimeError("純語音需要 Google Gemini 設定檔的 API Key")
            last_err = None
            for i, k in enumerate(keys):
                try:
                    result = asyncio.run(self.session_with_timeout(k))
                    if self.cancel_event.is_set():
                        self.finished.emit(False, {"cancelled": True, "error": "使用者中斷 Gemini Live"})
                        return
                    self.finished.emit(True, result)
                    return
                except Exception as exc:
                    last_err = exc
                    is_auth_quota, reason = _is_retryable_auth_or_quota_error(exc)
                    if is_auth_quota and i < len(keys) - 1:
                        log(f"[Gemini Live] 遭遇 {reason}，自動切換至備用金鑰重試")
                        continue
                    raise exc
            if last_err:
                raise last_err
        except asyncio.TimeoutError:
            self.finished.emit(False, {"timeout": True, "error": "Gemini Live 等待逾時"})
        except asyncio.CancelledError:
            self.finished.emit(False, {"cancelled": True, "error": "Gemini Live 已取消"})
        except Exception as e:
            self.finished.emit(False, {"error": str(e)})

    def cancel(self):
        self.cancel_event.set()

    async def session_with_timeout(self, key: str):
        return await asyncio.wait_for(self.session(key), timeout=self.timeout_seconds)

    async def session(self, key: str):
        import wave
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=key)
        pcm = []
        transcript = []
        user_text = []
        model_text = []

        live_model = self.model
        if "3.8" in live_model or "latest" in live_model or not live_model.startswith("gemini-"):
            live_model = "gemini-2.0-flash-exp"

        live_failed = False
        try:
            with wave.open(self.path, "rb") as wf:
                rate = wf.getframerate()
                live_config = {
                    "response_modalities": ["AUDIO"],
                    "input_audio_transcription": {},
                    "output_audio_transcription": {},
                    "speech_config": {"voice_config": {"prebuilt_voice_config": {"voice_name": self.voice}}},
                }
                if self.system_instruction.strip():
                    live_config["system_instruction"] = self.system_instruction

                async with client.aio.live.connect(model=live_model, config=live_config) as session:
                    while True:
                        if self.cancel_event.is_set():
                            return {"audio": None, "text": "", "cancelled": True}
                        chunk = wf.readframes(2048)
                        if not chunk:
                            break
                        await session.send_realtime_input(audio=types.Blob(data=chunk, mime_type=f"audio/pcm;rate={rate}"))
                    await session.send_realtime_input(audio_stream_end=True)

                    receiver = session.receive()
                    deadline = time.monotonic() + self.timeout_seconds
                    pending = None
                    done_turn = False
                    try:
                        while time.monotonic() < deadline and not self.cancel_event.is_set() and not done_turn:
                            if pending is None:
                                pending = asyncio.ensure_future(receiver.__anext__())
                            finished, _ = await asyncio.wait({pending}, timeout=1.0)
                            if not finished:
                                continue
                            task = pending
                            pending = None
                            try:
                                response = task.result()
                            except StopAsyncIteration:
                                break
                            content = getattr(response, "server_content", None)
                            if content:
                                inp = getattr(content, "input_transcription", None)
                                out = getattr(content, "output_transcription", None)
                                if inp and getattr(inp, "text", None):
                                    user_text.append(inp.text)
                                if out and getattr(out, "text", None):
                                    model_text.append(out.text)
                                turn = getattr(content, "model_turn", None)
                                if turn:
                                    for part in getattr(turn, "parts", []) or []:
                                        inline = getattr(part, "inline_data", None)
                                        if inline and getattr(inline, "data", None):
                                            pcm.append(inline.data)
                                if getattr(content, "turn_complete", False):
                                    done_turn = True
                    finally:
                        if pending is not None:
                            pending.cancel()
        except Exception as live_err:
            log(f"[Gemini Live] 即時串流連線失敗 ({live_err})，自動切換至 Gemini 多模態語音降級")
            live_failed = True

        if live_failed or (not pcm and not model_text):
            with open(self.path, "rb") as af:
                audio_bytes = af.read()
            prompt = self.system_instruction or "你是桌面上可愛的寵物。請以繁體中文親切簡短地回答（100字以內，不要包含表情符號或Markdown標籤）。"
            resp = await client.aio.models.generate_content(
                model="gemini-2.5-flash",
                contents=[
                    types.Part.from_bytes(data=audio_bytes, mime_type="audio/wav"),
                    prompt,
                ]
            )
            fallback_reply = (resp.text or "").strip()
            if fallback_reply:
                model_text.append(fallback_reply)

        if user_text:
            transcript.append("使用者：" + "".join(user_text).strip())
        if model_text:
            transcript.append("Gemini：" + "".join(model_text).strip())
        if self.cancel_event.is_set():
            return {"audio": None, "text": "", "cancelled": True}

        out_path = None
        if pcm:
            VOICE_DIR.mkdir(parents=True, exist_ok=True)
            out_path = VOICE_DIR / f"gemini_live_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
            with wave.open(str(out_path), "wb") as out:
                out.setnchannels(1)
                out.setsampwidth(2)
                out.setframerate(24000)
                out.writeframes(b"".join(pcm))
        elif model_text:
            try:
                import pyttsx3
                tts_engine = pyttsx3.init()
                VOICE_DIR.mkdir(parents=True, exist_ok=True)
                out_path = VOICE_DIR / f"gemini_live_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
                tts_engine.save_to_file("".join(model_text).strip(), str(out_path))
                tts_engine.runAndWait()
            except Exception:
                out_path = None

        return {"audio": str(out_path) if out_path else None, "text": "\n".join(transcript)}


class ModelListWorker(QThread):
    models_ready = Signal(bool, list, str)

    def __init__(self, profile: dict, parent=None):
        super().__init__(parent)
        self.profile = dict(profile)

    def run(self):
        try:
            models, source, note = discover_models(self.profile)
            self.models_ready.emit(True, models, note or source)
        except ModelCatalogError as e:
            self.models_ready.emit(False, [], str(e))
        except Exception as e:
            self.models_ready.emit(False, [], str(e))


# ==============================================================================
# 3. 寵物頭頂對話氣泡 (SpeechBubble)
# ==============================================================================
class SpeechBubble(QLabel):
    def __init__(self, pet):
        super().__init__(pet)
        self.pet = pet
        self._click_cb = None
        self._thought = False
        self._persistent = False
        self._bubble_w = 200
        self._bubble_h = 42

        # 消失計時器
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

        # 溫和呼吸動效計時器（alpha 210..255）
        self._breath_timer = QTimer(self)
        self._breath_timer.setInterval(40)
        self._breath_timer.timeout.connect(self._on_breath_tick)
        self._breath_phase = 0.0
        self._breath_alpha = 255

        self.setWordWrap(True)
        self.setAlignment(Qt.AlignCenter)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setStyleSheet("background: transparent; border: none;")
        self.hide()

    def _on_breath_tick(self):
        self._breath_phase += 0.08
        self._breath_alpha = int(232.5 + 22.5 * math.sin(self._breath_phase))
        self.update()

    def hide(self):
        if hasattr(self, "_breath_timer") and self._breath_timer.isActive():
            self._breath_timer.stop()
        super().hide()

    def hideEvent(self, e):
        if hasattr(self, "_breath_timer") and self._breath_timer.isActive():
            self._breath_timer.stop()
        super().hideEvent(e)

    def set_click_callback(self, cb):
        self._click_cb = cb
        self.setAttribute(Qt.WA_TransparentForMouseEvents, cb is None)
        if cb is not None:
            self.setCursor(Qt.PointingHandCursor)
        else:
            self.unsetCursor()

    def mousePressEvent(self, e):
        if self._click_cb and e.button() == Qt.LeftButton:
            self._click_cb()
            e.accept()
        else:
            super().mousePressEvent(e)

    def _get_target_head_x(self, bubble_w: float) -> float:
        """計算精準指向寵物頭頂的水平座標（於氣泡自身座標系）。"""
        try:
            from .pet import M_L
            is_tail = getattr(self.pet, "is_tail", False)
            snap_right = getattr(self.pet, "snap_right", False)
            art_w = getattr(self.pet, "art_w", self.pet.width())
            base_cx = 0.672 if is_tail else 0.60
            head_cx_in_pet = M_L + (art_w * (1.0 - base_cx) if snap_right else art_w * base_cx)
            target_x = head_cx_in_pet - self.x()
            return max(28.0, min(float(bubble_w - 28.0), float(target_x)))
        except Exception:
            return bubble_w / 2.0

    def sizeHint(self) -> QSize:
        return QSize(self._bubble_w, self._bubble_h + (40 if self._thought else 0))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)

        theme = "light"
        if hasattr(self.pet, "cfg") and self.pet.cfg:
            theme = self.pet.cfg.get("theme", "light")

        alpha = self._breath_alpha if self._persistent else 255

        if theme == "dark":
            if self._thought:
                bg_col = QColor("#16171b")
                border_col = QColor(96, 165, 250, alpha)
                fg_col = QColor("#f1f3f5")
            else:
                bg_col = QColor("#1e1f24")
                border_col = QColor(62, 66, 78, alpha)
                fg_col = QColor("#f1f3f5")
        else:
            if self._thought:
                bg_col = QColor("#f1f4f9")
                border_col = QColor(11, 87, 208, alpha)
                fg_col = QColor("#0f172a")
            else:
                bg_col = QColor("#ffffff")
                border_col = QColor(203, 213, 225, alpha)
                fg_col = QColor("#0f172a")

        bw = float(self._bubble_w)
        bh = float(self._bubble_h)

        # 1. 繪製主體氣泡矩形（平滑圓角膠囊／矩形）
        pen = QPen(border_col, 1.5)
        painter.setPen(pen)
        painter.setBrush(QBrush(bg_col))

        radius = min(16.0, bh / 2.0)
        bubble_rect = QRectF(1.0, 1.0, bw - 2.0, bh - 2.0)
        painter.drawRoundedRect(bubble_rect, radius, radius)

        # 2. 當 thought=True 時，下方延伸繪製 3 顆由大至小依序遞減的小圓點指向角色頭頂
        if self._thought:
            target_x = self._get_target_head_x(bw)
            start_x = bw / 2.0 + (target_x - bw / 2.0) * 0.3

            # 3 顆小圓點直徑分別約為 12px, 8px, 5px（半徑 6.0, 4.0, 2.5）
            c1_x = start_x + (target_x - start_x) * 0.25
            c1_y = bh + 9.0
            r1 = 6.0

            c2_x = start_x + (target_x - start_x) * 0.65
            c2_y = bh + 22.0
            r2 = 4.0

            c3_x = target_x
            c3_y = bh + 33.0
            r3 = 2.5

            painter.drawEllipse(QPointF(c1_x, c1_y), r1, r1)
            painter.drawEllipse(QPointF(c2_x, c2_y), r2, r2)
            painter.drawEllipse(QPointF(c3_x, c3_y), r3, r3)

        # 3. 繪製文字
        painter.setPen(fg_col)
        font = self.font()
        font.setPointSize(13)
        font.setBold(self._thought)
        painter.setFont(font)

        text_rect = QRectF(14.0, 4.0, bw - 28.0, bh - 8.0)
        painter.drawText(text_rect, Qt.AlignCenter | Qt.TextWordWrap, self.text())
        painter.end()

    def show_message(self, text: str, thought: bool = False, timeout_ms: int = 6500, persistent: bool = False):
        self._thought = thought
        self._persistent = persistent
        self.setText(text)

        font = self.font()
        font.setPointSize(13)
        font.setBold(thought)
        self.setFont(font)

        fm = self.fontMetrics()
        max_w = max(200, min(380, self.pet.width() - 20))
        text_bound = fm.boundingRect(0, 0, max_w - 28, 1000, Qt.AlignCenter | Qt.TextWordWrap, text)

        bubble_w = min(max_w, max(180, text_bound.width() + 32))
        bubble_h = max(42, text_bound.height() + 20)
        dots_h = 40 if thought else 0

        self._bubble_w = bubble_w
        self._bubble_h = bubble_h
        self.resize(bubble_w, bubble_h + dots_h)

        # 水平置中於寵物視窗
        bx = max(6, min(self.pet.width() - bubble_w - 6, (self.pet.width() - bubble_w) // 2))
        by = 10
        self.move(bx, by)
        self.raise_()
        self.show()

        # 呼吸動畫控制
        if persistent:
            if not self._breath_timer.isActive():
                self._breath_phase = 0.0
                self._breath_alpha = 255
                self._breath_timer.start(40)
        else:
            self._breath_timer.stop()
            self._breath_alpha = 255

        self.update()

        self._timer.stop()
        if not persistent and timeout_ms > 0:
            self._timer.start(timeout_ms)


# ==============================================================================
# 4. 輔助設定對話框 (記憶管理、語音設定、API 設定檔)
# ==============================================================================
def clamp_to_screen(win: QWidget, target_x: int, target_y: int, scr=None) -> tuple[int, int]:
    screen = scr or QGuiApplication.primaryScreen()
    geo = screen.availableGeometry()
    w = win.width()
    h = win.height()
    x = max(geo.left() + 16, min(target_x, geo.right() - w - 16))
    y = max(geo.top() + 16, min(target_y, geo.bottom() - h - 16))
    return x, y


def center_dialog(dialog: QWidget):
    screen = QGuiApplication.primaryScreen()
    if screen:
        geo = screen.availableGeometry()
        w = dialog.width()
        h = dialog.height()
        cx = geo.x() + max(0, (geo.width() - w) // 2)
        cy = geo.y() + max(0, (geo.height() - h) // 2)
        x = max(geo.left() + 16, min(cx, geo.right() - w - 16))
        y = max(geo.top() + 16, min(cy, geo.bottom() - h - 16))
        dialog.move(x, y)


class MemoryDialog(QDialog):
    def __init__(self, cfg: Config, parent=None):
        super().__init__(parent, Qt.FramelessWindowHint | Qt.Window | Qt.WindowStaysOnTopHint)
        self.cfg = cfg
        theme = cfg.get("theme", "light")
        self.setStyleSheet(_get_qss(theme))
        self.setWindowTitle("角色記憶管理")
        self.resize(540, 440)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.title_bar = CustomTitleBar(self, "角色記憶管理", has_min=False, has_close=True, theme=theme)
        outer.addWidget(self.title_bar)

        content = QWidget()
        root = QVBoxLayout(content)
        root.setContentsMargins(18, 16, 18, 18)
        root.setSpacing(12)

        root.addWidget(QLabel("長期記憶（手動維護，每行一條，會持續注入 AI 提示詞）："))
        self.long_edit = QTextEdit()
        self.long_edit.setPlainText("\n".join(cfg.get("long_memory", [])))
        self.long_edit.setPlaceholderText("例如：\n主人喜歡喝熱茶。\n角色的名字是小藍。\n遇到不確定的事情先請示主人。")
        root.addWidget(self.long_edit)

        form = QFormLayout()
        self.limit_sp = QSpinBox()
        self.limit_sp.setRange(1, 100)
        self.limit_sp.setValue(int(cfg.get("short_memory_limit", 20)))
        form.addRow("短期記憶輪數（保留最近 N 次對話）", self.limit_sp)
        root.addLayout(form)

        row_btn = QHBoxLayout()
        clear_btn = QPushButton("清除所有短期記憶")
        clear_btn.setObjectName("secondary")
        clear_btn.clicked.connect(self._clear_short)
        row_btn.addWidget(clear_btn)
        row_btn.addStretch(1)
        root.addLayout(row_btn)

        note = QLabel("說明：短期記憶會在對話過程中自動滾動更新；長期記憶為手動設定且不會被覆蓋。")
        note.setStyleSheet("color: #74777f; font-size: 12px;")
        note.setWordWrap(True)
        root.addWidget(note)

        bbox = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        bbox.accepted.connect(self._save)
        bbox.rejected.connect(self.reject)
        root.addWidget(bbox)

        outer.addWidget(content, 1)

    def showEvent(self, e):
        super().showEvent(e)
        center_dialog(self)
        self.raise_()
        self.activateWindow()

    def _clear_short(self):
        self.cfg.set("short_memory", [])
        ModernMessageBox.information(self, "記憶管理", "短期記憶已清空。")

    def _save(self):
        lines = [x.strip() for x in self.long_edit.toPlainText().splitlines() if x.strip()]
        self.cfg.set("long_memory", lines, save=False)
        self.cfg.set("short_memory_limit", self.limit_sp.value(), save=True)
        self.accept()


class VoiceSettingsDialog(QDialog):
    def __init__(self, cfg: Config, parent=None):
        super().__init__(parent, Qt.FramelessWindowHint | Qt.Window | Qt.WindowStaysOnTopHint)
        self.cfg = cfg
        theme = cfg.get("theme", "light")
        self.setStyleSheet(_get_qss(theme))
        self.setWindowTitle("語音與 TTS 設定")
        self.resize(540, 460)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.title_bar = CustomTitleBar(self, "語音與 TTS 設定", has_min=False, has_close=True, theme=theme)
        outer.addWidget(self.title_bar)

        content = QWidget()
        f = QFormLayout(content)
        f.setContentsMargins(18, 16, 18, 18)
        f.setSpacing(12)

        self.input_mode = QComboBox()
        self.input_mode.addItems(["traditional", "ai"])
        self.input_mode.setCurrentText(cfg.get("voice_input_mode", "traditional"))
        f.addRow("語音輸入模式", self.input_mode)

        self.auto_send = QCheckBox("辨識完成後自動送出")
        self.auto_send.setChecked(cfg.get("voice_auto_send", True))
        f.addRow("", self.auto_send)

        self.stt_model = QLineEdit(cfg.get("stt_model", "whisper-1"))
        f.addRow("AI 語音模型 (STT)", self.stt_model)

        self.tts_mode = QComboBox()
        self.tts_mode.addItems(["off", "traditional", "ai"])
        self.tts_mode.setCurrentText(cfg.get("tts_mode", "off"))
        f.addRow("文字朗讀模式 (TTS)", self.tts_mode)

        self.tts_model = QLineEdit(cfg.get("tts_model", "openai/tts-1"))
        f.addRow("AI TTS 模型", self.tts_model)

        self.tts_voice = QLineEdit(cfg.get("tts_voice", "alloy"))
        f.addRow("AI TTS 聲音", self.tts_voice)

        self.live_model = QLineEdit(cfg.get("gemini_live_model", "gemini-flash-latest"))
        f.addRow("Gemini Live 模型", self.live_model)

        self.live_voice = QLineEdit(cfg.get("gemini_live_voice", "Kore"))
        f.addRow("Gemini Live 聲音", self.live_voice)

        note = QLabel("traditional 模式使用本機 Vosk / pyttsx3；ai 模式使用目前選定 API 設定檔的 Key 與端點。")
        note.setStyleSheet("color: #74777f; font-size: 12px;")
        note.setWordWrap(True)
        f.addRow(note)

        bbox = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        bbox.accepted.connect(self._save)
        bbox.rejected.connect(self.reject)
        f.addRow(bbox)

        outer.addWidget(content, 1)

    def _save(self):
        self.cfg.set("voice_input_mode", self.input_mode.currentText(), save=False)
        self.cfg.set("voice_auto_send", self.auto_send.isChecked(), save=False)
        self.cfg.set("stt_model", self.stt_model.text().strip(), save=False)
        self.cfg.set("tts_mode", self.tts_mode.currentText(), save=False)
        self.cfg.set("tts_model", self.tts_model.text().strip(), save=False)
        self.cfg.set("tts_voice", self.tts_voice.text().strip(), save=False)
        self.cfg.set("gemini_live_model", self.live_model.text().strip(), save=False)
        self.cfg.set("gemini_live_voice", self.live_voice.text().strip(), save=True)
        self.accept()

    def showEvent(self, e):
        super().showEvent(e)
        center_dialog(self)
        self.raise_()
        self.activateWindow()


class ApiProfileDialog(QDialog):
    def __init__(self, cfg: Config, parent=None):
        super().__init__(parent, Qt.FramelessWindowHint | Qt.Window | Qt.WindowStaysOnTopHint)
        self.cfg = cfg
        theme = cfg.get("theme", "light")
        self.setStyleSheet(_get_qss(theme))
        self.setWindowTitle("API 設定檔管理")
        self.resize(760, 520)

        self.profiles = [dict(x) for x in cfg.get("api_profiles", [])]
        self._cur_idx = -1
        self._worker = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.title_bar = CustomTitleBar(self, "API 設定檔管理", has_min=False, has_close=True, theme=theme)
        outer.addWidget(self.title_bar)

        content = QWidget()
        root = QVBoxLayout(content)
        root.setContentsMargins(18, 16, 18, 18)
        root.setSpacing(12)

        row = QHBoxLayout()
        self.list_w = QListWidget()
        self.list_w.currentRowChanged.connect(self._on_row_changed)
        row.addWidget(self.list_w, 1)

        form = QFormLayout()
        form.setSpacing(10)
        self.ed_name = QLineEdit()
        self.cmb_prov = QComboBox()
        self.cmb_prov.addItems(PROVIDERS)

        r_key = QHBoxLayout()
        r_key.setSpacing(6)
        self.ed_key = QLineEdit()
        self.ed_key.setPlaceholderText("支援多組 Key，以逗號、分號或換行分隔")
        is_masked = bool(self.cfg.get("mask_api_keys", False))
        self.ed_key.setEchoMode(QLineEdit.Password if is_masked else QLineEdit.Normal)
        r_key.addWidget(self.ed_key, 1)

        self.btn_toggle_key = QPushButton("顯示" if is_masked else "隱藏")
        self.btn_toggle_key.setObjectName("secondary")
        self.btn_toggle_key.setToolTip("切換金鑰顯示/隱藏")
        self.btn_toggle_key.clicked.connect(self._toggle_key_vis)
        r_key.addWidget(self.btn_toggle_key)

        self.ed_endpoint = QLineEdit()
        self.ed_model = QLineEdit()
        self.cmb_models = QComboBox()
        self.cmb_models.setEditable(True)
        self.cmb_models.activated.connect(
            lambda idx: self.ed_model.setText(self.cmb_models.itemData(idx) or self.cmb_models.currentText())
        )

        self.btn_refresh_models = QPushButton("刷新模型列表")
        self.btn_refresh_models.setObjectName("secondary")
        self.btn_refresh_models.clicked.connect(self._refresh_models)
        self.lb_model_status = QLabel("可手動輸入模型 ID；刷新失敗時仍可保存手動值。")
        self.lb_model_status.setStyleSheet("color: #74777f; font-size: 12px;")
        self.lb_model_status.setWordWrap(True)

        form.addRow("設定檔名稱", self.ed_name)
        form.addRow("供應商", self.cmb_prov)
        form.addRow("API Key", r_key)
        form.addRow("端點 URL (可留空使用預設)", self.ed_endpoint)
        form.addRow("模型 ID", self.ed_model)
        form.addRow("遠端模型清單", self.cmb_models)
        form.addRow("", self.btn_refresh_models)
        form.addRow("", self.lb_model_status)
        row.addLayout(form, 2)
        root.addLayout(row)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("新增設定檔")
        add_btn.setObjectName("secondary")
        add_btn.clicked.connect(self._add_profile)
        del_btn = QPushButton("刪除目前設定檔")
        del_btn.setObjectName("danger")
        del_btn.clicked.connect(self._del_profile)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(del_btn)
        btn_row.addStretch(1)
        root.addLayout(btn_row)

        bbox = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        bbox.accepted.connect(self._save)
        bbox.rejected.connect(self.reject)
        root.addWidget(bbox)

        outer.addWidget(content, 1)

        self._refresh_list()
        if self.profiles:
            self.list_w.setCurrentRow(0)

    def showEvent(self, e):
        super().showEvent(e)
        center_dialog(self)
        self.raise_()
        self.activateWindow()

    def _refresh_list(self):
        self._cur_idx = -1
        self.list_w.clear()
        for p in self.profiles:
            name = p.get("name", "") or p.get("provider", "未命名")
            self.list_w.addItem(name)

    def _save_current(self):
        if 0 <= self._cur_idx < len(self.profiles):
            self.profiles[self._cur_idx] = {
                "name": self.ed_name.text().strip() or "未命名",
                "provider": self.cmb_prov.currentText(),
                "key": self.ed_key.text().strip(),
                "endpoint": self.ed_endpoint.text().strip(),
                "model": self.ed_model.text().strip(),
            }

    def _toggle_key_vis(self):
        currently_hidden = (self.ed_key.echoMode() == QLineEdit.Password)
        if currently_hidden:
            if self.cfg.get("require_windows_auth", False):
                ok = prompt_windows_credentials(
                    int(self.winId()),
                    message="請驗證您的 Windows 本機身分以檢視 API 金鑰",
                    caption="API 設定檔 - 身分驗證",
                )
                if not ok:
                    ModernMessageBox.warning(self, "身分驗證失敗", "Windows 身分驗證未通過，無法檢視金鑰。")
                    return
            self.ed_key.setEchoMode(QLineEdit.Normal)
            self.btn_toggle_key.setText("隱藏")
        else:
            self.ed_key.setEchoMode(QLineEdit.Password)
            self.btn_toggle_key.setText("顯示")

    def _on_row_changed(self, row: int):
        self._save_current()
        self._cur_idx = row
        if 0 <= row < len(self.profiles):
            p = self.profiles[row]
            self.ed_name.setText(p.get("name", ""))
            self.cmb_prov.setCurrentText(p.get("provider", "DeepSeek"))
            self.ed_key.setText(p.get("key", ""))
            is_masked = bool(self.cfg.get("mask_api_keys", False))
            self.ed_key.setEchoMode(QLineEdit.Password if is_masked else QLineEdit.Normal)
            self.btn_toggle_key.setText("顯示" if is_masked else "隱藏")
            self.ed_endpoint.setText(p.get("endpoint", ""))
            self.ed_model.setText(p.get("model", ""))
            self.cmb_models.clear()
            self.cmb_models.addItem("（尚未刷新；可手動輸入）", p.get("model", ""))
            self.lb_model_status.setText("可手動輸入模型 ID；刷新失敗時仍可保存手動值。")

    def _add_profile(self):
        self._save_current()
        self.profiles.append({
            "name": f"新設定檔 {len(self.profiles) + 1}",
            "provider": "DeepSeek",
            "key": "",
            "endpoint": "",
            "model": "deepseek-chat",
        })
        self._refresh_list()
        self.list_w.setCurrentRow(len(self.profiles) - 1)

    def _del_profile(self):
        if len(self.profiles) <= 1:
            ModernMessageBox.warning(self, "提示", "至少保留一個設定檔。")
            return
        row = self.list_w.currentRow()
        if 0 <= row < len(self.profiles):
            self.profiles.pop(row)
            self._cur_idx = -1
            self._refresh_list()
            self.list_w.setCurrentRow(max(0, row - 1))

    def _refresh_models(self):
        self._save_current()
        if not (0 <= self._cur_idx < len(self.profiles)):
            return
        profile = self.profiles[self._cur_idx]
        self.lb_model_status.setText("正在查詢遠端模型清單...")
        self.btn_refresh_models.setEnabled(False)

        self._worker = ModelListWorker(profile, self)
        self._worker.models_ready.connect(self._on_models_ready)
        self._worker.start()

    def _on_models_ready(self, ok: bool, models: list, note: str):
        self.btn_refresh_models.setEnabled(True)
        if ok and models:
            self.cmb_models.clear()
            for m in models:
                self.cmb_models.addItem(f"{m.get('label', m.get('id'))} ({m.get('id')})", m.get("id"))
            self.lb_model_status.setText(f"查詢成功：共找到 {len(models)} 個模型 ({note})")
        else:
            self.lb_model_status.setText(f"查詢失敗：{note}")

    def _save(self):
        self._save_current()
        if self.cfg.get("require_windows_auth", False):
            ok = prompt_windows_credentials(
                int(self.winId()),
                message="請驗證您的 Windows 本機身分以儲存 API 金鑰變更",
                caption="API 設定檔 - 身分驗證",
            )
            if not ok:
                ModernMessageBox.warning(self, "身分驗證失敗", "Windows 身分驗證未通過，無法儲存變更。")
                return
        self.cfg.set("api_profiles", self.profiles, save=True)
        self.accept()


# ==============================================================================
# 5. AI 對話視窗 (ChatDialog)
# ==============================================================================
class ChatDialog(QDialog):
    def __init__(self, app, pet, parent=None):
        super().__init__(parent, Qt.FramelessWindowHint | Qt.Window | Qt.WindowStaysOnTopHint)
        self.app = app
        self.pet = pet
        self.cfg = app.cfg
        self.drag_pos = None

        self.chat_worker = None
        self.voice_recorder = None
        self.voice_transcriber = None
        self.tts_worker = None
        self.live_worker = None
        self.current_mode = self.cfg.get("chat_dialog_mode", "standard")
        if self.current_mode not in ("standard", "reasoner", "voice"):
            self.current_mode = "standard"
        self._toast_label = None
        self._toast_timer = None
        self.history_expanded = False
        self._anim = None

        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMinimumSize(500, 160)
        self.resize(560, 180)

        self._setup_ui()
        self._apply_mode_ui(self.current_mode)
        self.sync_profiles()
        self.sync_memory_info()

    def _setup_ui(self):
        theme = self.cfg.get("theme", "dark")

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(8, 8, 8, 8)
        outer_layout.setSpacing(0)

        # Window Frame Container
        self.container = QFrame(self)
        self.container.setObjectName("ChatContainer")

        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(0, 0, 0, 10)
        container_layout.setSpacing(6)

        # Title Bar
        self.title_bar = CustomTitleBar(self, "AI 對話", has_min=True, has_close=True, theme=theme)
        container_layout.addWidget(self.title_bar)

        # Body Widget
        body_widget = QWidget()
        body_layout = QVBoxLayout(body_widget)
        body_layout.setContentsMargins(14, 2, 14, 0)
        body_layout.setSpacing(6)

        # Collapsible Conversation History Stream
        self.history_widget = QWidget()
        h_layout = QVBoxLayout(self.history_widget)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(0)

        self.history_view = QTextEdit()
        self.history_view.setReadOnly(True)
        self.history_view.setPlaceholderText("輸入任何問題開始對話，Enter 發送訊息...")
        h_layout.addWidget(self.history_view)
        self.history_widget.setVisible(False)
        body_layout.addWidget(self.history_widget, 1)

        # Minimalist Capsule Input Container
        self.capsule = QFrame()
        self.capsule.setObjectName("CapsuleFrame")

        capsule_layout = QVBoxLayout(self.capsule)
        capsule_layout.setContentsMargins(12, 8, 12, 8)
        capsule_layout.setSpacing(4)

        # Top Area: Transparent Input LineEdit
        self.ed_input = QLineEdit()
        self.ed_input.setPlaceholderText("輸入任何問題，Enter 發送...")
        self.ed_input.returnPressed.connect(self.send_message)
        capsule_layout.addWidget(self.ed_input)

        # Bottom Integrated Control Row
        ctrl_row = QHBoxLayout()
        ctrl_row.setContentsMargins(0, 0, 0, 0)
        ctrl_row.setSpacing(6)

        # Left: Plus Button (+)
        self.btn_plus = QPushButton()
        self.btn_plus.setIcon(get_icon("add", "#94a3b8", 18))
        self.btn_plus.setFixedSize(28, 28)
        self.btn_plus.setToolTip("更多設定與選項")
        self.btn_plus.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                border-radius: 14px;
                padding: 0;
            }
            QPushButton:hover {
                background-color: #2b2d35;
            }
        """)
        self.btn_plus.clicked.connect(self._open_menu)
        ctrl_row.addWidget(self.btn_plus)

        # Left: Frameless Model Selection Capsule Button
        self.btn_model = QPushButton("Gemini Flash Latest ▾")
        self.btn_model.setToolTip("切換 AI 模型設定檔")
        self.btn_model.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #8ab4f8;
                border: none;
                border-radius: 12px;
                padding: 4px 8px;
                font-size: 13px;
                font-weight: 500;
                text-align: left;
            }
            QPushButton:hover {
                background-color: #282a32;
                color: #b3c5ff;
            }
        """)
        self.btn_model.clicked.connect(self._popup_model_menu)
        ctrl_row.addWidget(self.btn_model)

        # Hidden QComboBox for backward compatibility
        self.cmb_profile = QComboBox()
        self.cmb_profile.hide()
        self.cmb_profile.currentIndexChanged.connect(self._on_profile_switched)
        ctrl_row.addWidget(self.cmb_profile)

        ctrl_row.addStretch(1)

        # History Toggle Capsule Button
        self.btn_history_toggle = QPushButton("對話紀錄 ▾")
        self.btn_history_toggle.setToolTip("展開對話歷史紀錄")
        self.btn_history_toggle.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #94a3b8;
                border: none;
                border-radius: 10px;
                padding: 4px 8px;
                font-size: 11px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #282a32;
                color: #e2e8f0;
            }
        """)
        self.btn_history_toggle.clicked.connect(self.toggle_history)
        ctrl_row.addWidget(self.btn_history_toggle)

        # Right: Mode Capsule
        self.btn_mode = QPushButton("標準 ▾")
        self.btn_mode.setIcon(get_icon("forum", "#94a3b8", 15))
        self.btn_mode.setToolTip("切換對話模式")
        self.btn_mode.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #94a3b8;
                border: none;
                border-radius: 12px;
                padding: 4px 8px;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #282a32;
                color: #e2e8f0;
            }
        """)
        self.btn_mode.clicked.connect(self._popup_mode_menu)
        ctrl_row.addWidget(self.btn_mode)

        # Right: Microphone Button
        self.btn_mic = QPushButton()
        self.btn_mic.setIcon(get_icon("mic", "#94a3b8", 18))
        self.btn_mic.setFixedSize(30, 30)
        self.btn_mic.setCheckable(True)
        self.btn_mic.setToolTip("語音輸入（點擊開始錄音）")
        self.btn_mic.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                border-radius: 15px;
            }
            QPushButton:hover {
                background-color: #2b2d35;
            }
            QPushButton:checked {
                background-color: #ea4335;
            }
        """)
        self.btn_mic.clicked.connect(self.toggle_mic)
        ctrl_row.addWidget(self.btn_mic)

        # Proxy button for Gemini Live toggle (backward compatibility)
        self.btn_live = QPushButton()
        self.btn_live.hide()
        self.btn_live.setCheckable(True)
        self.btn_live.clicked.connect(self.toggle_gemini_live)
        ctrl_row.addWidget(self.btn_live)

        # Right: Circular Send Button with Right Arrow
        self.btn_send = QPushButton()
        self.btn_send.setIcon(get_icon("send", "#e2e8f0", 16))
        self.btn_send.setFixedSize(32, 32)
        self.btn_send.setToolTip("發送訊息 (Enter)")
        self.btn_send.setStyleSheet("""
            QPushButton {
                background-color: #2f313a;
                border: none;
                border-radius: 16px;
            }
            QPushButton:hover {
                background-color: #3d404c;
            }
            QPushButton:pressed {
                background-color: #22242b;
            }
        """)
        self.btn_send.clicked.connect(self.send_message)
        ctrl_row.addWidget(self.btn_send)

        capsule_layout.addLayout(ctrl_row)
        body_layout.addWidget(self.capsule)

        # Status Bar Indicator
        status_box = QHBoxLayout()
        status_box.setContentsMargins(4, 0, 4, 0)
        self.lb_status = QLabel("就緒")
        self.lb_status.setStyleSheet("color: #64748b; font-size: 11px;")
        status_box.addWidget(self.lb_status, 1)

        self.lb_model_tag = QLabel("")
        self.lb_model_tag.setStyleSheet("color: #60a5fa; font-size: 11px; font-weight: bold;")
        status_box.addWidget(self.lb_model_tag)
        body_layout.addLayout(status_box)

        container_layout.addWidget(body_widget, 1)
        outer_layout.addWidget(self.container)

        self.apply_theme(theme)

    def apply_theme(self, theme: str):
        is_dark = (theme == "dark")
        self.title_bar.apply_theme(theme)
        if is_dark:
            self.container.setStyleSheet("""
                QFrame#ChatContainer {
                    background-color: #17181c;
                    border: 1px solid #282a32;
                    border-radius: 18px;
                }
            """)
            self.capsule.setStyleSheet("""
                QFrame#CapsuleFrame {
                    background-color: #1e1f24;
                    border: 1px solid #2e3038;
                    border-radius: 18px;
                }
            """)
            self.ed_input.setStyleSheet("""
                QLineEdit {
                    background: transparent;
                    border: none;
                    color: #f1f3f5;
                    font-size: 14px;
                    padding: 2px 0 4px 0;
                    selection-background-color: #3b82f6;
                    selection-color: #ffffff;
                }
            """)
            self.history_view.setStyleSheet("""
                QTextEdit {
                    background: transparent;
                    border: none;
                    color: #e2e8f0;
                    font-size: 13px;
                    line-height: 1.5;
                    padding: 4px;
                }
                QScrollBar:vertical {
                    background: transparent;
                    width: 6px;
                    margin: 0;
                }
                QScrollBar::handle:vertical {
                    background: #333642;
                    border-radius: 3px;
                    min-height: 24px;
                }
            """)
        else:
            self.container.setStyleSheet("""
                QFrame#ChatContainer {
                    background-color: #ffffff;
                    border: 1px solid #e2e8f0;
                    border-radius: 18px;
                }
            """)
            self.capsule.setStyleSheet("""
                QFrame#CapsuleFrame {
                    background-color: #f8fafc;
                    border: 1px solid #e2e8f0;
                    border-radius: 18px;
                }
            """)
            self.ed_input.setStyleSheet("""
                QLineEdit {
                    background: transparent;
                    border: none;
                    color: #0f172a;
                    font-size: 14px;
                    padding: 2px 0 4px 0;
                    selection-background-color: #3b82f6;
                    selection-color: #ffffff;
                }
            """)
            self.history_view.setStyleSheet("""
                QTextEdit {
                    background: transparent;
                    border: none;
                    color: #0f172a;
                    font-size: 13px;
                    line-height: 1.5;
                    padding: 4px;
                }
                QScrollBar:vertical {
                    background: transparent;
                    width: 6px;
                    margin: 0;
                }
                QScrollBar::handle:vertical {
                    background: #cbd5e1;
                    border-radius: 3px;
                    min-height: 24px;
                }
            """)

    def toggle_history(self):
        self.set_history_expanded(not self.history_expanded, animate=True)

    def _update_history_toggle_label(self):
        if self.history_expanded:
            self.btn_history_toggle.setText("收起紀錄 ▴")
            self.btn_history_toggle.setToolTip("收起對話歷史紀錄，恢復極簡扁平膠囊")
        else:
            self.btn_history_toggle.setText("對話紀錄 ▾")
            self.btn_history_toggle.setToolTip("展開對話歷史紀錄")

    def set_history_expanded(self, expanded: bool, animate: bool = True):
        if self.history_expanded == expanded:
            return
        self.history_expanded = expanded
        target_w = 560
        target_h = 430 if expanded else 180

        screen = QGuiApplication.screenAt(self.geometry().center()) or QGuiApplication.primaryScreen()
        geo = screen.availableGeometry()

        cur_rect = self.geometry()
        new_w = target_w
        new_h = target_h
        new_x = max(geo.left() + 16, min(cur_rect.x(), geo.right() - new_w - 16))
        if expanded:
            new_y = min(cur_rect.y(), geo.bottom() - new_h - 16)
            new_y = max(geo.top() + 16, new_y)
        else:
            new_y = cur_rect.y()
            new_y = max(geo.top() + 16, min(new_y, geo.bottom() - new_h - 16))

        target_rect = QRect(new_x, new_y, new_w, new_h)

        if not animate:
            if expanded:
                self.history_widget.setVisible(True)
                self.setMinimumHeight(240)
                self.setMaximumHeight(800)
            else:
                self.history_widget.setVisible(False)
                self.setMinimumHeight(160)
                self.setMaximumHeight(220)
            self.setGeometry(target_rect)
            self._update_history_toggle_label()
            return

        if expanded:
            self.history_widget.setVisible(True)
            self.setMinimumHeight(160)
            self.setMaximumHeight(800)

        if self._anim and self._anim.state() == QPropertyAnimation.Running:
            self._anim.stop()

        self._anim = QPropertyAnimation(self, b"geometry")
        self._anim.setDuration(220)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.setStartValue(cur_rect)
        self._anim.setEndValue(target_rect)

        def on_finished():
            if not self.history_expanded:
                self.history_widget.setVisible(False)
                self.setMinimumHeight(160)
                self.setMaximumHeight(220)
            else:
                self.setMinimumHeight(240)
                self.setMaximumHeight(800)
            self._update_history_toggle_label()

        self._anim.finished.connect(on_finished)
        self._anim.start()

    # ------------------------------------------------------------- Companion Placement
    def show_beside_pet(self):
        self.show()
        self.raise_()
        self.activateWindow()

        pet_rect = self.pet.geometry()
        screen = QGuiApplication.screenAt(pet_rect.center()) or QGuiApplication.primaryScreen()
        geo = screen.availableGeometry()
        w = self.width()
        h = self.height()

        # 當寵物位於螢幕右側時，彈在寵物左側（內側）；位於左側時，彈在寵物右側（內側）
        if pet_rect.center().x() > geo.center().x():
            target_x = pet_rect.left() - w - 16
        else:
            target_x = pet_rect.right() + 16

        # 垂直對齊寵物中心
        target_y = pet_rect.center().y() - h // 2

        # 100% 邊界夾持演算法杜絕被螢幕邊緣遮擋
        x = max(geo.left() + 16, min(target_x, geo.right() - w - 16))
        y = max(geo.top() + 16, min(target_y, geo.bottom() - h - 16))
        self.move(x, y)
        try:
            from . import winapi
            winapi.set_topmost(int(self.winId()), True)
        except Exception:
            pass

    # ------------------------------------------------------------- Menu & Dialogs
    def _open_menu(self):
        m = QMenu(self)
        m.setStyleSheet("""
            QMenu {
                background-color: #1e1f24;
                color: #e2e8f0;
                border: 1px solid #333642;
                border-radius: 8px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 20px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #2b2d35;
                color: #ffffff;
            }
            QMenu::separator {
                height: 1px;
                background-color: #333642;
                margin: 4px 8px;
            }
        """)
        m.addAction("API 設定檔管理...").triggered.connect(self._open_api_profiles)
        m.addAction("語音與 TTS 設定...").triggered.connect(self._open_voice_settings)
        m.addAction("角色記憶管理 (長短期記憶)...").triggered.connect(self._open_memory_settings)
        m.addSeparator()
        m.addAction("清空目前對話記錄").triggered.connect(self._clear_history)
        m.addAction("開啟桌面控制中心...").triggered.connect(self.app.show_panel)
        pos = self.btn_plus.mapToGlobal(QPoint(0, self.btn_plus.height()))
        m.exec(pos)

    def _popup_model_menu(self):
        m = QMenu(self)
        m.setStyleSheet("""
            QMenu {
                background-color: #1e1f24;
                color: #e2e8f0;
                border: 1px solid #333642;
                border-radius: 8px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 20px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #2b2d35;
                color: #ffffff;
            }
            QMenu::separator {
                height: 1px;
                background-color: #333642;
                margin: 4px 8px;
            }
        """)
        profiles = self.cfg.get("api_profiles", [])
        cur_idx = self.cmb_profile.currentIndex()
        for idx, p in enumerate(profiles):
            name = p.get("name", "") or p.get("provider", "未命名")
            mod = p.get("model", "")
            label = f"{name} ({mod})"
            act = m.addAction(label)
            act.setCheckable(True)
            act.setChecked(idx == cur_idx)
            act.triggered.connect(lambda _=False, i=idx: self._select_profile(i))

        m.addSeparator()
        m.addAction("管理設定檔...").triggered.connect(self._open_api_profiles)
        pos = self.btn_model.mapToGlobal(QPoint(0, self.btn_model.height()))
        m.exec(pos)

    def _select_profile(self, idx: int):
        self.cmb_profile.setCurrentIndex(idx)
        self._update_model_tag()

    def _popup_mode_menu(self):
        m = QMenu(self)
        m.setStyleSheet("""
            QMenu {
                background-color: #1e1f24;
                color: #e2e8f0;
                border: 1px solid #333642;
                border-radius: 8px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 20px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #2b2d35;
                color: #ffffff;
            }
        """)
        modes = [
            ("standard", "標準對話模式"),
            ("reasoner", "深度思考模式 (Reasoner)"),
            ("voice", "語音陪伴模式 (自動朗讀)"),
            ("agent", "系統助手 Agent 模式 (Agent)"),
        ]
        for mode_key, mode_name in modes:
            act = m.addAction(mode_name)
            act.setCheckable(True)
            act.setChecked(self.current_mode == mode_key)
            act.triggered.connect(lambda _=False, mk=mode_key: self._set_mode(mk))
        pos = self.btn_mode.mapToGlobal(QPoint(0, self.btn_mode.height()))
        m.exec(pos)

    def _apply_mode_ui(self, mode_key: str):
        if mode_key == "reasoner":
            self.btn_mode.setText("思考 ▾")
            self.btn_mode.setIcon(get_icon("psychology", "#a78bfa", 15))
            self.btn_mode.setToolTip("深度思考模式：AI 將進行深入邏輯剖析")
        elif mode_key == "voice":
            self.btn_mode.setText("語音 ▾")
            self.btn_mode.setIcon(get_icon("volume_up", "#38bdf8", 15))
            self.btn_mode.setToolTip("語音陪伴模式：AI 回覆將自動以語音朗讀")
        elif mode_key == "agent":
            self.btn_mode.setText("助手 ▾")
            self.btn_mode.setIcon(get_icon("shield", "#10b981", 15))
            self.btn_mode.setToolTip("系統助手 Agent 模式：執行系統指令與任務")
        else:
            self.btn_mode.setText("標準 ▾")
            self.btn_mode.setIcon(get_icon("forum", "#94a3b8", 15))
            self.btn_mode.setToolTip("標準對話模式")

    def _set_mode(self, mode_key: str):
        self.current_mode = mode_key
        self.cfg.set("chat_dialog_mode", mode_key)
        self._apply_mode_ui(mode_key)
        if mode_key == "reasoner":
            self.show_floating_notice("已切換為【深度思考模式】：AI 將進行深入邏輯剖析")
        elif mode_key == "voice":
            self.show_floating_notice("已切換為【語音陪伴模式】：AI 回覆將自動以語音朗讀")
        elif mode_key == "agent":
            self.show_floating_notice("已切換為【系統助手 Agent 模式】：可執行系統任務與輔助指令")
        else:
            self.show_floating_notice("已切換為【標準對話模式】")

    def show_floating_notice(self, text: str, is_error: bool = False):
        """在膠囊對話視窗內顯示浮動提示氣泡，清晰醒目且平滑消失。"""
        if self._toast_label is None:
            self._toast_label = QLabel(self)
            self._toast_label.setAlignment(Qt.AlignCenter)
            self._toast_label.setWordWrap(True)
            self._toast_timer = QTimer(self)
            self._toast_timer.setSingleShot(True)
            self._toast_timer.timeout.connect(self._toast_label.hide)

        bg = "#2d1618" if is_error else "#162338"
        border = "#ef4444" if is_error else "#3b82f6"
        fg = "#fee2e2" if is_error else "#dbeafe"
        self._toast_label.setStyleSheet(
            f"QLabel {{ background-color: {bg}; color: {fg}; border: 1.5px solid {border}; "
            f"border-radius: 8px; padding: 8px 14px; font-size: 12px; font-weight: bold; }}"
        )
        self._toast_label.setText(text)
        self._toast_label.adjustSize()
        w = min(self.width() - 40, max(240, self._toast_label.sizeHint().width() + 20))
        h = max(36, self._toast_label.sizeHint().height() + 10)
        self._toast_label.resize(w, h)
        x = (self.width() - w) // 2
        y = self.height() - self.capsule.height() - h - 16
        self._toast_label.move(x, max(60, y))
        self._toast_label.raise_()
        self._toast_label.show()
        self._toast_timer.start(4500)

    def _open_api_profiles(self):
        dlg = ApiProfileDialog(self.cfg, self)
        if dlg.exec():
            self.sync_profiles()

    def _open_voice_settings(self):
        dlg = VoiceSettingsDialog(self.cfg, self)
        dlg.exec()

    def _open_memory_settings(self):
        dlg = MemoryDialog(self.cfg, self)
        dlg.exec()
        self.sync_memory_info()

    def _clear_history(self):
        self.history_view.clear()
        self.cfg.set("short_memory", [])
        self.lb_status.setText("對話記錄已清除")
        self.set_history_expanded(False, animate=True)

    # ------------------------------------------------------------- Profile & Memory Sync
    def sync_profiles(self):
        profiles = self.cfg.get("api_profiles", [])
        if not profiles:
            profiles = [
                {"name": "DeepSeek 預設", "provider": "DeepSeek", "key": "", "endpoint": "https://api.deepseek.com", "model": "deepseek-chat"},
                {"name": "OpenAI 預設", "provider": "OpenAI", "key": "", "endpoint": "https://api.openai.com/v1", "model": "gpt-4o-mini"},
                {"name": "Claude 預設", "provider": "Anthropic", "key": "", "endpoint": "https://api.anthropic.com", "model": "claude-3-5-haiku-latest"},
                {"name": "Gemini 預設", "provider": "Google Gemini", "key": "", "endpoint": "https://generativelanguage.googleapis.com/v1beta", "model": "gemini-flash-latest"},
            ]
            self.cfg.set("api_profiles", profiles, save=True)

        self.cmb_profile.blockSignals(True)
        self.cmb_profile.clear()
        for p in profiles:
            text = f"{p.get('name', '未命名')} ({p.get('provider', '')})"
            self.cmb_profile.addItem(text)

        active = max(0, min(int(self.cfg.get("active_profile", 0)), len(profiles) - 1))
        self.cmb_profile.setCurrentIndex(active)
        self.cmb_profile.blockSignals(False)
        self._update_model_tag()

    def _on_profile_switched(self, idx: int):
        if idx >= 0:
            self.cfg.set("active_profile", idx)
            self._update_model_tag()

    def _update_model_tag(self):
        profile = self.current_profile()
        mod = profile.get("model") or "預設模型"
        prov = profile.get("provider", "")
        btn_label = f"{mod} ▾" if len(mod) <= 24 else f"{mod[:21]}... ▾"
        self.btn_model.setText(btn_label)
        self.lb_model_tag.setText(f"[{prov}: {mod}]")

    def current_profile(self) -> dict:
        profiles = self.cfg.get("api_profiles", [])
        idx = max(0, min(self.cmb_profile.currentIndex(), len(profiles) - 1))
        return profiles[idx] if profiles else {}

    def sync_memory_info(self):
        short = self.cfg.get("short_memory", [])
        if not self.history_view.toPlainText().strip() and short:
            for item in short:
                role = item.get("role", "")
                who = "你" if role == "user" else "角色"
                self.add_history_entry(who, item.get("content", ""), auto_expand=False)

    # ------------------------------------------------------------- Messaging
    def add_history_entry(self, who: str, text: str, auto_expand: bool = True):
        is_user = (who == "你")
        align = "right" if is_user else "left"
        bg_col = "#202532" if is_user else "#1e2026"
        border_col = "#2e3b52" if is_user else "#2c2e36"
        name_col = "#60a5fa" if is_user else "#34d399"
        text_col = "#f1f5f9" if is_user else "#e2e8f0"

        escaped_text = (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\n", "<br>")
        )

        bubble_html = f"""
        <div style="margin: 6px 0; text-align: {align};">
            <div style="display: inline-block; max-width: 85%; text-align: left; background-color: {bg_col}; border: 1px solid {border_col}; border-radius: 14px; padding: 8px 14px;">
                <div style="font-size: 11px; font-weight: bold; color: {name_col}; margin-bottom: 3px;">{who}</div>
                <div style="color: {text_col}; font-size: 13px; line-height: 1.45;">{escaped_text}</div>
            </div>
        </div>
        """
        self.history_view.append(bubble_html)
        sb = self.history_view.verticalScrollBar()
        if sb:
            sb.setValue(sb.maximum())

        if auto_expand and not self.history_expanded:
            self.set_history_expanded(True, animate=True)

    def _build_prompt(self, user_text: str) -> str:
        long_mem = self.cfg.get("long_memory", [])
        short_mem = self.cfg.get("short_memory", [])
        char_name = self.pet.character

        custom_prompt = self.cfg.get("custom_system_prompt", "").strip()
        if custom_prompt:
            base_prompt = custom_prompt
        else:
            base_prompt = (
                f"你是一個客觀、簡潔且真實的桌面智慧助手（目前外觀：{char_name}）。"
                "請以繁體中文回答，保持簡潔真實、條理分明、無廢話，直接給予最精確有用的內容。"
                "嚴格禁止輸出任何思考標籤或表情符號 (No Emojis)。"
            )

        parts = [base_prompt]
        if self.current_mode == "reasoner":
            parts.append("【深度思考模式】請針對使用者的問題進行全方位、深度且邏輯嚴謹的剖析，列出關鍵步驟與深入見解。輸出條理分明、結構清晰。")
        elif self.current_mode == "voice":
            parts.append("【語音陪伴模式】請以生動、親切、自然且溫暖的口吻簡短回應（不超過 100 字），適合口語朗讀，避免使用複雜符號或表格。")
        elif self.current_mode == "agent":
            parts.append(
                "【系統助手 Agent 模式】\n"
                "你是一個具備系統指令與輔助任務執行能力的桌面智慧助手。若使用者的要求需要執行本機系統指令或查詢，請以標準格式輸出要執行的指令，格式如下：\n"
                "[EXECUTE: 指令內容]\n"
                "請嚴格遵從安全最小權限原則。若僅為一般諮詢，則直接以繁體中文客觀簡短回應。"
            )

        if long_mem:
            parts.append("長期記憶（手動設定，請適時參考）：\n" + "\n".join(f"- {x}" for x in long_mem))
        if short_mem:
            recent_turns = short_mem[-10:]
            history_lines = []
            for item in recent_turns:
                prefix = "使用者：" if item.get("role") == "user" else "助手："
                history_lines.append(prefix + item.get("content", ""))
            parts.append("最近對話歷史：\n" + "\n".join(history_lines))

        parts.append(f"使用者剛才說：{user_text}\n請回應：")
        return "\n\n".join(parts)

    def send_message(self):
        text = self.ed_input.text().strip()
        if not text:
            return
        self.ed_input.clear()
        self.add_history_entry("你", text)
        self._remember("user", text)

        # Show thinking on speech bubble above pet head
        self.pet.show_speech_bubble("思考中...", thought=True)
        self.lb_status.setText("正在等待 AI 回覆...")

        profile = self.current_profile()
        prompt = self._build_prompt(text)

        self.chat_worker = ChatWorker(profile, prompt, self, cfg=self.cfg)
        self.chat_worker.done.connect(self._on_chat_done)
        self.chat_worker.start()

    def _on_chat_done(self, ok: bool, reply: str, err: str):
        self.chat_worker = None
        self.add_history_entry("助手", reply)
        self._remember("assistant", reply)

        # Synchronously display speech bubble above pet's head
        self.pet.show_speech_bubble(reply, thought=False)

        if ok:
            self.lb_status.setText("回覆完成")
        else:
            self.lb_status.setText(f"AI 回覆失敗，已採用陪伴語句：{err}")

        # Trigger TTS if configured or in voice mode
        self._speak(reply)

        # Agent 模式指令執行與安全規則檢驗
        if ok and self.current_mode == "agent" and "[EXECUTE:" in reply:
            match = re.search(r'\[EXECUTE:\s*(.+?)\]', reply, re.DOTALL)
            if match:
                cmd = match.group(1).strip()
                self._handle_agent_command(cmd)

    def _handle_agent_command(self, cmd: str):
        if not cmd:
            return

        # 1. 檢查黑名單指令
        blacklist = self.cfg.get("security_blacklist_commands", [])
        cmd_lower = cmd.lower()
        for bl in blacklist:
            if bl.lower() in cmd_lower:
                self.show_floating_notice(f"【安全攔截】指令包含危險黑名單關鍵字「{bl}」，已自動拒絕執行！", is_error=True)
                self.add_history_entry("安全核心", f"已攔截危險指令：{cmd}\n原因：符合黑名單規則「{bl}」")
                return

        # 2. 檢查敏感目錄保護
        sensitive_paths = self.cfg.get("security_sensitive_paths", [])
        for sp in sensitive_paths:
            if sp.lower() in cmd_lower and any(op in cmd_lower for op in ("del", "rm", "format", "write", "new-item", "remove-item")):
                self.show_floating_notice(f"【安全攔截】指令試圖修改受保護敏感目錄「{sp}」，已自動拒絕執行！", is_error=True)
                self.add_history_entry("安全核心", f"已攔截指令：{cmd}\n原因：試圖修改敏感目錄「{sp}」")
                return

        # 3. 檢查白名單安全指令
        whitelist = self.cfg.get("security_whitelist_commands", [])
        tokens = cmd.strip().split()
        first_token = tokens[0].lower() if tokens else ""
        is_whitelisted = (first_token in [w.lower() for w in whitelist]) or (cmd.strip().lower() in [w.lower() for w in whitelist])

        auto_approve = self.cfg.get("agent_auto_approve_whitelist", False)
        if is_whitelisted and auto_approve:
            self._execute_agent_command_process(cmd)
            return

        # 4. 若不在白名單（或白名單需確認），彈出精緻小型確認彈窗 AgentConfirmDialog (380x220)
        from .dialogs import AgentConfirmDialog
        dlg = AgentConfirmDialog(self, command=cmd, theme=self.cfg.get("theme", "dark"))
        if dlg.exec() and dlg.confirmed:
            self._execute_agent_command_process(cmd)
        else:
            self.show_floating_notice("已取消執行 Agent 指令")
            self.add_history_entry("系統", f"使用者已取消或拒絕執行指令：{cmd}")

    def _execute_agent_command_process(self, cmd: str):
        import subprocess
        self.show_floating_notice(f"正在執行指令：{cmd[:30]}...")
        try:
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
            out = res.stdout.strip() or res.stderr.strip() or "指令執行完成，無輸出內容。"
            if len(out) > 800:
                out = out[:800] + "\n...(輸出過長已截斷)"
            self.add_history_entry("執行結果", out)
            self.pet.show_speech_bubble("指令執行完成", thought=False)
        except subprocess.TimeoutExpired:
            self.show_floating_notice("指令執行逾時 (15秒)", is_error=True)
            self.add_history_entry("執行結果", "錯誤：指令執行逾時")
        except Exception as e:
            self.show_floating_notice(f"執行失敗: {e}", is_error=True)
            self.add_history_entry("執行結果", f"執行錯誤: {e}")

    def _remember(self, role: str, content: str):
        items = list(self.cfg.get("short_memory", []))
        items.append({"role": role, "content": content, "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
        limit = max(1, int(self.cfg.get("short_memory_limit", 20))) * 2
        items = items[-limit:]
        self.cfg.set("short_memory", items, save=True)

    # ------------------------------------------------------------- Voice & TTS
    def _speak(self, text: str):
        mode = self.cfg.get("tts_mode", "off")
        if self.current_mode == "voice" and mode == "off":
            mode = "traditional"
        if mode == "off" or not text.strip():
            return
        profile = self.current_profile()
        self.tts_worker = TTSWorker(text, mode, profile, self)
        self.tts_worker.finished.connect(self._on_tts_finished)
        self.tts_worker.start()

    def _on_tts_finished(self, ok: bool, audio_path: str):
        self.tts_worker = None
        if ok and audio_path:
            self.pet.sounds.play_file(audio_path)

    def toggle_mic(self):
        if self.voice_recorder and self.voice_recorder.isRunning():
            self.btn_mic.setIcon(get_icon("mic", "#94a3b8", 18))
            self.btn_mic.setChecked(False)
            self.btn_mic.setToolTip("語音輸入（點擊開始錄音）")
            self.lb_status.setText("語音錄製完成，正在辨識...")
            self.show_floating_notice("語音錄製完成，正在進行辨識...", is_error=False)
            self.voice_recorder.stop()
            return

        # 預先檢測麥克風設備與依賴庫
        try:
            import sounddevice as sd
            devs = sd.query_devices()
            has_input = any(d.get("max_input_channels", 0) > 0 for d in devs)
            if not has_input:
                self.btn_mic.setChecked(False)
                self.show_floating_notice("未檢測到可用的麥克風輸入裝置", is_error=True)
                self.lb_status.setText("語音錯誤：未檢測到麥克風輸入裝置")
                return
        except Exception as exc:
            self.btn_mic.setChecked(False)
            self.show_floating_notice(f"音訊模組載入失敗: {exc}", is_error=True)
            self.lb_status.setText(f"語音錯誤：{exc}")
            return

        mode = self.cfg.get("voice_input_mode", "traditional")
        self.voice_recorder = VoiceRecorder(traditional=(mode == "traditional"), vad_enabled=False, parent=self)
        self.voice_recorder.partial.connect(lambda t: self.ed_input.setText(t))
        self.voice_recorder.level.connect(lambda v: self.lb_status.setText(f"正在錄音... 音量: {v}%（點擊送出）"))
        self.voice_recorder.finished.connect(self._on_recorded)
        self.voice_recorder.failed.connect(self._on_voice_failed)
        self.voice_recorder.start()

        self.btn_mic.setChecked(True)
        self.btn_mic.setIcon(get_icon("circle", "#ffffff", 14))
        self.btn_mic.setToolTip("正在錄音... / 點擊送出")
        self.lb_status.setText("正在錄音...（點擊麥克風完成送出）")
        self.show_floating_notice("正在錄音中... 請對麥克風說話，完成後點擊麥克風送出", is_error=False)

    def _on_voice_failed(self, err: str):
        self.voice_recorder = None
        self.btn_mic.setChecked(False)
        self.btn_mic.setIcon(get_icon("mic", "#94a3b8", 18))
        self.btn_mic.setToolTip("語音輸入（點擊開始錄音）")
        self.btn_live.setChecked(False)
        self.show_floating_notice(f"語音錯誤：{err}", is_error=True)
        self.lb_status.setText(f"語音錯誤：{err}")

    def _on_recorded(self, path: str):
        self.voice_recorder = None
        self.btn_mic.setChecked(False)
        self.btn_mic.setIcon(get_icon("mic", "#94a3b8", 18))
        self.btn_mic.setToolTip("正在進行語音辨識...")
        self.lb_status.setText("正在進行語音辨識...")

        mode = self.cfg.get("voice_input_mode", "traditional")
        profile = self.current_profile()
        profile["stt_model"] = self.cfg.get("stt_model", "whisper-1")
        all_profiles = self.cfg.get("api_profiles", [])

        self.voice_transcriber = VoiceTranscriber(path, mode, profile, all_profiles=all_profiles, parent=self)
        self.voice_transcriber.finished.connect(self._on_transcribed)
        self.voice_transcriber.start()

    def _on_transcribed(self, ok: bool, text: str):
        self.voice_transcriber = None
        self.btn_mic.setChecked(False)
        self.btn_mic.setIcon(get_icon("mic", "#94a3b8", 18))
        self.btn_mic.setToolTip("語音輸入（點擊開始錄音）")

        if not ok:
            self.show_floating_notice(f"語音辨識失敗：{text}", is_error=True)
            self.lb_status.setText(f"語音辨識失敗：{text}")
            return

        self.ed_input.setText(text)
        self.lb_status.setText("語音辨識完成")
        self.show_floating_notice(f"語音辨識完成：{text[:30]}", is_error=False)
        if self.cfg.get("voice_auto_send", True) and text.strip():
            self.send_message()

    # ------------------------------------------------------------- Gemini Live Mode
    def toggle_gemini_live(self):
        if self.live_worker and self.live_worker.isRunning():
            self.live_worker.cancel()
            self.btn_live.setChecked(False)
            self._apply_mode_ui(self.current_mode)
            self.lb_status.setText("已中斷 Gemini Live")
            return

        if self.voice_recorder and self.voice_recorder.isRunning():
            self.voice_recorder.stop()
            self.lb_status.setText("處理語音中...")
            return

        self.voice_recorder = VoiceRecorder(traditional=False, parent=self)
        self.voice_recorder.level.connect(lambda v: self.lb_status.setText(f"Gemini Live 錄音中... 音量: {v}%"))
        self.voice_recorder.finished.connect(self._on_live_recorded)
        self.voice_recorder.failed.connect(self._on_voice_failed)
        self.voice_recorder.start()
        self.btn_live.setChecked(True)
        self.btn_mode.setText("Live 錄音中 ▾")
        self.lb_status.setText("Gemini Live 錄音中...")

    def _on_live_recorded(self, path: str):
        self.voice_recorder = None
        self.lb_status.setText("正在連線至 Gemini Live 串流...")

        profiles = self.cfg.get("api_profiles", [])
        gemini_prof = next((p for p in profiles if p.get("provider") == "Google Gemini"), None)
        if not gemini_prof:
            gemini_prof = self.current_profile()

        model = self.cfg.get("gemini_live_model", "gemini-2.0-flash-exp")
        voice = self.cfg.get("gemini_live_voice", "Kore")

        self.live_worker = GeminiLiveWorker(path, gemini_prof, self._build_prompt(""), model, voice, self)
        self.live_worker.finished.connect(self._on_live_finished)
        self.live_worker.start()

    def _on_live_finished(self, ok: bool, data: dict):
        self.live_worker = None
        self.btn_live.setChecked(False)
        self._apply_mode_ui(self.current_mode)

        if not ok:
            err = data.get("error", "未知錯誤")
            self.lb_status.setText(f"Gemini Live 失敗：{err}")
            return

        text = data.get("text", "")
        self.lb_status.setText("Gemini Live 完成")
        for line in text.splitlines():
            if line.startswith("使用者："):
                msg = line[4:].strip()
                self.add_history_entry("你", msg)
                self._remember("user", msg)
            elif line.startswith("Gemini："):
                msg = line[7:].strip()
                self.add_history_entry("角色", msg)
                self._remember("assistant", msg)
                self.pet.show_speech_bubble(msg, thought=False)

        if data.get("audio"):
            self.pet.sounds.play_file(data["audio"])
