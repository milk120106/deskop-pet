"""AI 對話視窗、語音錄音與語音合成、記憶系統與背景工作執行緒。
完全遵循純文字與繁體中文排版，嚴格禁止任何表情符號 (No Emojis)。
極簡深灰高質感膠囊容器設計，完美契合現代介面審美。
"""
from __future__ import annotations

import asyncio
import json
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

from PySide6.QtCore import QPoint, QRectF, QSize, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath
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
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .config import APP_DIR, Config, log
from .icons import get_icon
from .model_catalog import OPENAI_BASES, PROVIDERS, ModelCatalogError, discover_models
from .titlebar import CustomTitleBar

VOICE_DIR = APP_DIR / "voice_cache"
VOSK_MODEL = APP_DIR / "models" / "vosk-model-small-cn-0.22"

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
QLineEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background: #f1f4f9;
    color: #1a1c1e;
    border: 1px solid #74777f;
    border-radius: 8px;
    padding: 6px 10px;
    selection-background-color: #0b57d0;
    selection-color: #ffffff;
}
QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
    border: 2px solid #0b57d0;
    background: #ffffff;
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
QLineEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background: #211f26;
    color: #e6e0e9;
    border: 1px solid #79747e;
    border-radius: 8px;
    padding: 6px 10px;
    selection-background-color: #a8c7fa;
    selection-color: #041e49;
}
QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
    border: 2px solid #a8c7fa;
    background: #2b2930;
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
    "OpenAI 相容自訂端點": "openai/",
}

DEFAULT_MODELS = {
    "DeepSeek": "deepseek-chat",
    "OpenAI": "gpt-4o-mini",
    "Google Gemini": "gemini-flash-latest",
    "Anthropic": "claude-3-5-haiku-latest",
    "Mistral": "mistral-small-latest",
    "xAI / Grok": "grok-3-mini",
    "Ollama": "llama3.2",
    "Ollama Cloud": "llama3.2",
    "OpenRouter": "auto",
    "Groq": "llama-3.3-70b-versatile",
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

    def __init__(self, traditional: bool = False, parent=None):
        super().__init__(parent)
        self.traditional = traditional
        self.stop_event = threading.Event()
        self.frames = []

    def run(self):
        try:
            import numpy as np
            import sounddevice as sd
            import soundfile as sf
        except ImportError:
            self.failed.emit("尚未安裝 sounddevice/soundfile 音訊庫，請安裝 requirements.txt")
            return

        try:
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

    def __init__(self, path: str, mode: str, profile: dict, parent=None):
        super().__init__(parent)
        self.path = path
        self.mode = mode
        self.profile = profile

    def run(self):
        try:
            if self.mode == "traditional":
                if not VOSK_MODEL.exists():
                    raise RuntimeError("找不到本機 Vosk 模型，請下載 vosk-model-small-cn-0.22 至 models 目錄")
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
                text = json.loads(rec.FinalResult()).get("text", "")
            else:
                try:
                    from litellm import transcription

                    with open(self.path, "rb") as f:
                        result = transcription(
                            model=self.profile.get("stt_model") or "whisper-1",
                            file=f,
                            api_key=self.profile.get("key") or None,
                            api_base=self.profile.get("endpoint") or None,
                        )
                    text = getattr(result, "text", "") or (result.get("text", "") if isinstance(result, dict) else "")
                except Exception as e:
                    raise RuntimeError(f"AI 語音辨識錯誤：{e}") from e
            self.finished.emit(True, text.strip())
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
            if self.mode == "traditional":
                import pyttsx3

                engine = pyttsx3.init()
                engine.say(self.text)
                engine.runAndWait()
                self.finished.emit(True, "")
            else:
                from litellm import speech

                VOICE_DIR.mkdir(parents=True, exist_ok=True)
                path = VOICE_DIR / f"tts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3"
                result = speech(
                    model=self.profile.get("tts_model") or "openai/tts-1",
                    voice=self.profile.get("tts_voice") or "alloy",
                    input=self.text,
                    api_key=self.profile.get("key") or None,
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

            async with client.aio.live.connect(model=self.model, config=live_config) as session:
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
        self.setWordWrap(True)
        self.setAlignment(Qt.AlignCenter)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.hide()

    def show_message(self, text: str, thought: bool = False):
        self.setText(text)
        theme = self.pet.cfg.get("theme", "light")
        if theme == "dark":
            bg = "#1e1f24" if not thought else "#16171b"
            border = "#3e424e" if not thought else "#60a5fa"
            fg = "#f1f3f5"
        else:
            bg = "#ffffff" if not thought else "#f1f4f9"
            border = "#cbd5e1" if not thought else "#0b57d0"
            fg = "#0f172a"

        self.setStyleSheet(
            f"QLabel {{ color: {fg}; background-color: {bg}; border: 1.5px solid {border}; "
            f"border-radius: 16px; padding: 10px 14px; font-size: 13px; font-weight: {'bold' if thought else 'normal'}; }}"
        )
        max_w = max(200, min(380, self.pet.width() - 20))
        self.setMaximumWidth(max_w)
        self.adjustSize()
        w = min(max_w, max(200, self.sizeHint().width()))
        h = max(42, self.sizeHint().height())
        self.resize(w, h)
        self.move(max(6, (self.pet.width() - w) // 2), 10)
        self.raise_()
        self.show()
        QTimer.singleShot(6500, self.hide)


# ==============================================================================
# 4. 輔助設定對話框 (記憶管理、語音設定、API 設定檔)
# ==============================================================================
def center_dialog(dialog: QWidget):
    screen = QApplication.primaryScreen()
    if screen:
        geo = screen.availableGeometry()
        x = geo.x() + max(0, (geo.width() - dialog.width()) // 2)
        y = geo.y() + max(0, (geo.height() - dialog.height()) // 2)
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
        QMessageBox.information(self, "記憶管理", "短期記憶已清空。")

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
                    QMessageBox.warning(self, "身分驗證失敗", "Windows 身分驗證未通過，無法檢視金鑰。")
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
            QMessageBox.warning(self, "提示", "至少保留一個設定檔。")
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
                QMessageBox.warning(self, "身分驗證失敗", "Windows 身分驗證未通過，無法儲存變更。")
                return
        self.cfg.set("api_profiles", self.profiles, save=True)
        self.accept()


# ==============================================================================
# 5. 極簡深灰高質感膠囊對話視窗 (ChatDialog)
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
        self.current_mode = "Turbo"

        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMinimumSize(480, 420)
        self.resize(580, 520)

        self._setup_ui()
        self.sync_profiles()
        self.sync_memory_info()

    def _setup_ui(self):
        # Outer dialog root layout
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(10, 10, 10, 10)
        outer_layout.setSpacing(0)

        # Window Frame Container
        self.container = QFrame(self)
        self.container.setObjectName("ChatContainer")
        self.container.setStyleSheet("""
            QFrame#ChatContainer {
                background-color: #17181c;
                border: 1px solid #282a32;
                border-radius: 18px;
            }
        """)

        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(0, 0, 0, 12)
        container_layout.setSpacing(8)

        # Title Bar
        self.title_bar = CustomTitleBar(self, "AI 膠囊對話", has_min=True, has_close=True, theme="dark")
        container_layout.addWidget(self.title_bar)

        # Conversation History Stream
        body_widget = QWidget()
        body_layout = QVBoxLayout(body_widget)
        body_layout.setContentsMargins(14, 4, 14, 0)
        body_layout.setSpacing(8)

        self.history_view = QTextEdit()
        self.history_view.setReadOnly(True)
        self.history_view.setPlaceholderText("輸入任何問題開始對話，Enter 發送訊息...")
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
        body_layout.addWidget(self.history_view, 1)

        # Status Bar Indicator (Subtle text)
        status_box = QHBoxLayout()
        status_box.setContentsMargins(4, 0, 4, 0)
        self.lb_status = QLabel("就緒")
        self.lb_status.setStyleSheet("color: #64748b; font-size: 11px;")
        status_box.addWidget(self.lb_status, 1)

        self.lb_model_tag = QLabel("")
        self.lb_model_tag.setStyleSheet("color: #60a5fa; font-size: 11px; font-weight: bold;")
        status_box.addWidget(self.lb_model_tag)
        body_layout.addLayout(status_box)

        # Minimalist Capsule Input Container (Dark Charcoal Capsule #1e1f24, Border #2e3038, Radius 20px)
        self.capsule = QFrame()
        self.capsule.setObjectName("CapsuleFrame")
        self.capsule.setStyleSheet("""
            QFrame#CapsuleFrame {
                background-color: #1e1f24;
                border: 1px solid #2e3038;
                border-radius: 20px;
            }
        """)

        capsule_layout = QVBoxLayout(self.capsule)
        capsule_layout.setContentsMargins(14, 10, 14, 10)
        capsule_layout.setSpacing(6)

        # Top Area: Transparent Input LineEdit
        self.ed_input = QLineEdit()
        self.ed_input.setPlaceholderText("輸入任何問題，Enter 發送...")
        self.ed_input.returnPressed.connect(self.send_message)
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

        # Hidden QComboBox for backward compatibility and profile index management
        self.cmb_profile = QComboBox()
        self.cmb_profile.hide()
        self.cmb_profile.currentIndexChanged.connect(self._on_profile_switched)
        ctrl_row.addWidget(self.cmb_profile)

        ctrl_row.addStretch(1)

        # Right: Mode Capsule (e.g. "Turbo ▾")
        self.btn_mode = QPushButton("Turbo ▾")
        self.btn_mode.setIcon(get_icon("shield", "#94a3b8", 15))
        self.btn_mode.setToolTip("對話模式")
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
        self.btn_mic.setToolTip("語音輸入")
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

        container_layout.addWidget(body_widget, 1)
        outer_layout.addWidget(self.container)

    # ------------------------------------------------------------- Companion Placement
    def show_beside_pet(self):
        self.show()
        self.raise_()
        self.activateWindow()
        pet_rect = self.pet.geometry()
        screen = QApplication.primaryScreen().availableGeometry()

        x = pet_rect.left() - self.width() - 15
        if x < screen.left():
            x = pet_rect.right() + 15
        y = max(screen.top() + 20, min(screen.bottom() - self.height() - 20, pet_rect.top()))
        self.move(x, y)

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
            ("Turbo", "極速模式 (Turbo)"),
            ("Live", "Gemini Live 純語音"),
            ("Companion", "純文字陪伴模式"),
        ]
        for mode_key, mode_name in modes:
            act = m.addAction(mode_name)
            act.setCheckable(True)
            act.setChecked(self.current_mode == mode_key)
            act.triggered.connect(lambda _=False, mk=mode_key: self._set_mode(mk))
        pos = self.btn_mode.mapToGlobal(QPoint(0, self.btn_mode.height()))
        m.exec(pos)

    def _set_mode(self, mode_key: str):
        self.current_mode = mode_key
        if mode_key == "Live":
            self.btn_mode.setText("Live ▾")
            self.btn_mode.setIcon(get_icon("bolt", "#60a5fa", 15))
            self.toggle_gemini_live()
        elif mode_key == "Companion":
            self.btn_mode.setText("陪伴 ▾")
            self.btn_mode.setIcon(get_icon("shield", "#94a3b8", 15))
        else:
            self.btn_mode.setText("Turbo ▾")
            self.btn_mode.setIcon(get_icon("shield", "#94a3b8", 15))

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
                self.add_history_entry(who, item.get("content", ""))

    # ------------------------------------------------------------- Messaging
    def add_history_entry(self, who: str, text: str):
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

    def _build_prompt(self, user_text: str) -> str:
        long_mem = self.cfg.get("long_memory", [])
        short_mem = self.cfg.get("short_memory", [])
        char_name = self.pet.character

        parts = [
            f"你是桌面上的可愛角色（目前外觀：{char_name}）。請以繁體中文回答，簡短自然親切，字數在 150 字以內，不要輸出任何思考過程標籤或 markdown 表情符號。"
        ]
        if long_mem:
            parts.append("長期記憶（手動設定，請適時參考）：\n" + "\n".join(f"- {x}" for x in long_mem))
        if short_mem:
            recent_turns = short_mem[-10:]
            history_lines = []
            for item in recent_turns:
                prefix = "使用者：" if item.get("role") == "user" else "角色："
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
        self.add_history_entry("角色", reply)
        self._remember("assistant", reply)

        # Synchronously display speech bubble above pet's head
        self.pet.show_speech_bubble(reply, thought=False)

        if ok:
            self.lb_status.setText("回覆完成")
        else:
            self.lb_status.setText(f"AI 回覆失敗，已採用陪伴語句：{err}")

        # Trigger TTS if configured
        self._speak(reply)

    def _remember(self, role: str, content: str):
        items = list(self.cfg.get("short_memory", []))
        items.append({"role": role, "content": content, "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
        limit = max(1, int(self.cfg.get("short_memory_limit", 20))) * 2
        items = items[-limit:]
        self.cfg.set("short_memory", items, save=True)

    # ------------------------------------------------------------- Voice & TTS
    def _speak(self, text: str):
        mode = self.cfg.get("tts_mode", "off")
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
            self.lb_status.setText("語音錄製完成，正在辨識...")
            self.voice_recorder.stop()
            return

        mode = self.cfg.get("voice_input_mode", "traditional")
        self.voice_recorder = VoiceRecorder(traditional=(mode == "traditional"), parent=self)
        self.voice_recorder.partial.connect(lambda t: self.ed_input.setText(t))
        self.voice_recorder.level.connect(lambda v: self.lb_status.setText(f"錄音中... 音量: {v}%"))
        self.voice_recorder.finished.connect(self._on_recorded)
        self.voice_recorder.failed.connect(self._on_voice_failed)
        self.voice_recorder.start()

        self.btn_mic.setChecked(True)
        self.btn_mic.setIcon(get_icon("mic", "#ffffff", 18))
        self.lb_status.setText("錄音中...")

    def _on_voice_failed(self, err: str):
        self.voice_recorder = None
        self.btn_mic.setChecked(False)
        self.btn_mic.setIcon(get_icon("mic", "#94a3b8", 18))
        self.btn_live.setChecked(False)
        self.lb_status.setText(f"語音錯誤：{err}")

    def _on_recorded(self, path: str):
        self.voice_recorder = None
        self.btn_mic.setChecked(False)
        self.btn_mic.setIcon(get_icon("mic", "#94a3b8", 18))
        self.lb_status.setText("正在進行語音辨識...")

        mode = self.cfg.get("voice_input_mode", "traditional")
        profile = self.current_profile()
        profile["stt_model"] = self.cfg.get("stt_model", "whisper-1")

        self.voice_transcriber = VoiceTranscriber(path, mode, profile, self)
        self.voice_transcriber.finished.connect(self._on_transcribed)
        self.voice_transcriber.start()

    def _on_transcribed(self, ok: bool, text: str):
        self.voice_transcriber = None
        if not ok:
            self.lb_status.setText(f"語音辨識失敗：{text}")
            return
        self.ed_input.setText(text)
        self.lb_status.setText("語音辨識完成")
        if self.cfg.get("voice_auto_send", True) and text.strip():
            self.send_message()

    # ------------------------------------------------------------- Gemini Live Mode
    def toggle_gemini_live(self):
        if self.live_worker and self.live_worker.isRunning():
            self.live_worker.cancel()
            self.btn_live.setChecked(False)
            self.btn_mode.setText("Turbo ▾")
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

        model = self.cfg.get("gemini_live_model", "gemini-flash-latest")
        voice = self.cfg.get("gemini_live_voice", "Kore")

        self.live_worker = GeminiLiveWorker(path, gemini_prof, self._build_prompt(""), model, voice, self)
        self.live_worker.finished.connect(self._on_live_finished)
        self.live_worker.start()

    def _on_live_finished(self, ok: bool, data: dict):
        self.live_worker = None
        self.btn_live.setChecked(False)
        self.btn_mode.setText("Turbo ▾")

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
