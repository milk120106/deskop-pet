"""Native Windows audio backend for Desktop Pet.
Replaces QtMultimedia/FFmpeg multi-player instances with Windows MCI (winmm.dll)
to achieve zero FFmpeg crashes, zero memory leaks, and native MP3/WAV playback.
"""
from __future__ import annotations

import atexit
import ctypes
import os
import shutil
import threading
from pathlib import Path

from .config import SOUND_LIB_DIR, asset
from .logger import error as log_error
from .logger import info as log_info
from .logger import warning as log_warning

CUE_KEYS = ["hit", "feed", "land", "off"]
CUE_DEFAULTS = {
    "hit": "hit.mp3",
    "feed": "feed.mp3",
    "land": "pot_land.mp3",
    "off": "pot_off.mp3",
}
CUE_NAMES = {
    "hit": "扣費音效 (hit)",
    "feed": "餵食音效 (feed)",
    "land": "盆落地音效 (land)",
    "off": "盆取下音效 (off)",
}
MAX_SOUND_BYTES = 50 * 1024 * 1024  # 50 MB limit


def _get_short_path(path: str) -> str:
    """Convert path to 8.3 short path on Windows to avoid issues with spaces or unicode in MCI commands."""
    if not path or not os.path.exists(path):
        return path
    if os.name == "nt":
        try:
            buf = ctypes.create_unicode_buffer(1024)
            length = ctypes.windll.kernel32.GetShortPathNameW(str(path), buf, 1024)
            if length > 0:
                return buf.value
        except Exception:
            pass
    return str(path)


def _mci_send(cmd: str) -> tuple[int, str]:
    """Execute mciSendStringW command safely."""
    if os.name != "nt":
        return 0, ""
    try:
        buf = ctypes.create_unicode_buffer(256)
        res = ctypes.windll.winmm.mciSendStringW(cmd, buf, 255, 0)
        if res != 0:
            err_buf = ctypes.create_unicode_buffer(256)
            ctypes.windll.winmm.mciGetErrorStringW(res, err_buf, 255)
            return res, err_buf.value
        return 0, buf.value
    except Exception as e:
        return -1, str(e)


class MciVoice:
    """Single MCI audio voice channel for polyphonic playback."""

    def __init__(self, alias: str):
        self.alias = alias
        self.is_open = False
        self.current_source = ""
        self.volume = 80  # 0..100
        self._lock = threading.RLock()

    def open(self, file_path: str, volume: int = 80) -> bool:
        with self._lock:
            if not file_path or not os.path.exists(file_path):
                return False
            self.close()
            short_p = _get_short_path(file_path)
            ext = os.path.splitext(file_path)[1].lower()
            mci_type = "type mpegvideo" if ext == ".mp3" else ("type waveaudio" if ext == ".wav" else "")
            cmd = f'open "{short_p}" {mci_type} alias {self.alias}'.strip()
            res, err_msg = _mci_send(cmd)
            if res != 0:
                # Fallback without explicit type parameter
                cmd_fallback = f'open "{short_p}" alias {self.alias}'
                res, err_msg = _mci_send(cmd_fallback)

            if res == 0:
                self.is_open = True
                self.current_source = file_path
                self.set_volume(volume)
                return True
            else:
                log_warning(f"MCI 開啟音效失敗 [{self.alias}]: {err_msg} (檔案: {file_path})", source="Audio")
                return False

    def set_volume(self, pct: int):
        with self._lock:
            self.volume = max(0, min(100, int(pct)))
            if not self.is_open:
                return
            mci_vol = self.volume * 10  # MCI scale 0..1000
            _mci_send(f"setaudio {self.alias} volume to {mci_vol}")

    def play(self):
        with self._lock:
            if not self.is_open or self.volume <= 0:
                return
            res, err_msg = _mci_send(f"play {self.alias} from 0")
            if res != 0:
                log_warning(f"MCI 播放失敗 [{self.alias}]: {err_msg}", source="Audio")

    def stop(self):
        with self._lock:
            if self.is_open:
                _mci_send(f"stop {self.alias}")

    def close(self):
        with self._lock:
            if self.is_open:
                _mci_send(f"close {self.alias}")
                self.is_open = False
                self.current_source = ""


class CuePool:
    """Pool of voice channels for a specific cue (e.g. hit, feed, land, off)."""

    def __init__(self, key: str, voices: int = 3):
        self.key = key
        self.voice_count = max(1, voices)
        self.voices: list[MciVoice] = [MciVoice(f"pet_cue_{key}_{i}") for i in range(self.voice_count)]
        self.voice_idx = 0
        self.enabled = True
        self.volume = 80
        self.current_source = ""
        self._lock = threading.RLock()

    def set_source(self, path: str):
        with self._lock:
            if not path or not os.path.exists(path):
                return
            if path == self.current_source and all(v.is_open for v in self.voices):
                return
            self.current_source = path
            for v in self.voices:
                v.open(path, self.volume)

    def set_volume(self, pct: int):
        with self._lock:
            self.volume = max(0, min(100, int(pct)))
            for v in self.voices:
                v.set_volume(self.volume)

    def play(self):
        if not self.enabled or not self.current_source or self.volume <= 0:
            return
        with self._lock:
            try:
                voice = self.voices[self.voice_idx]
                self.voice_idx = (self.voice_idx + 1) % len(self.voices)
                voice.play()
            except Exception as e:
                log_error(f"播放音效異常 ({self.key}): {e}", source="Audio")

    def close(self):
        with self._lock:
            for v in self.voices:
                v.close()


class Sounds:
    """Master sound manager: coordinates pools, settings, and custom cues."""

    def __init__(self, cfg):
        self.cfg = cfg
        SOUND_LIB_DIR.mkdir(parents=True, exist_ok=True)
        self.pools: dict[str, CuePool] = {}
        self._file_voice: MciVoice | None = None
        self._muted = False
        try:
            self.pools["hit"] = CuePool("hit", 3)
            self.pools["feed"] = CuePool("feed", 2)
            self.pools["land"] = CuePool("land", 2)
            self.pools["off"] = CuePool("off", 2)
            log_info("音訊引擎啟動完成 (Windows 原生 MCI 後端，零 FFmpeg 依賴)", source="Audio")
        except Exception as e:
            log_error(f"音訊引擎初始化失敗: {e}", source="Audio")
        self.apply()
        atexit.register(self.close_all)

    @property
    def hit(self):
        return self.pools.get("hit")

    @property
    def feed(self):
        return self.pools.get("feed")

    @property
    def land(self):
        return self.pools.get("land")

    @property
    def off(self):
        return self.pools.get("off")

    def apply(self):
        """Apply sound settings from config."""
        try:
            master_enabled = bool(self.cfg.get("sound", True))
            master_vol = int(self.cfg.get("volume", 80))
            cue_vols = self.cfg.get("cue_volumes") or {}
            cue_custom = self.cfg.get("cue_custom") or {}

            for key, pool in self.pools.items():
                pool.enabled = master_enabled
                # Cue volume scaled by master volume: (cue_vol * master_vol) / 100
                cue_vol = cue_vols.get(key, 80)
                combined_vol = int((cue_vol * master_vol) / 100.0)
                pool.set_volume(combined_vol)

                custom_file = cue_custom.get(key)
                if custom_file and (SOUND_LIB_DIR / custom_file).exists():
                    pool.set_source(str(SOUND_LIB_DIR / custom_file))
                else:
                    pool.set_source(asset(CUE_DEFAULTS[key]))
        except Exception as e:
            log_error(f"套用音訊設定失敗: {e}", source="Audio")

    def set_muted(self, muted: bool):
        """Mute or restore sound temporarily without overwriting config."""
        self._muted = bool(muted)
        master_enabled = bool(self.cfg.get("sound", True)) and (not self._muted)
        for pool in self.pools.values():
            pool.enabled = master_enabled

    def play(self, which: str):
        """Play sound cue safely without raising exceptions."""
        try:
            p = self.pools.get(which)
            if p:
                p.play()
        except Exception as e:
            log_error(f"觸發音效失敗 ({which}): {e}", source="Audio")

    def set_custom_cue(self, key: str, source_path: str) -> tuple[bool, str]:
        """Import a custom audio file for a cue slot."""
        if key not in CUE_DEFAULTS:
            return False, "無效的音效位置"
        p = Path(source_path)
        if not p.exists():
            return False, "檔案不存在"
        if p.stat().st_size > MAX_SOUND_BYTES:
            return False, f"檔案過大（超過 {MAX_SOUND_BYTES // (1024*1024)} MB）"

        ext = p.suffix.lower()
        if ext not in (".mp3", ".wav", ".ogg", ".m4a"):
            return False, "不支援的音效格式（建議 mp3 或 wav）"

        SOUND_LIB_DIR.mkdir(parents=True, exist_ok=True)
        dest_name = f"{key}_{p.name}"
        dest_path = SOUND_LIB_DIR / dest_name
        try:
            shutil.copy2(str(p), str(dest_path))
        except OSError as e:
            return False, f"複製失敗: {e}"

        c_custom = self.cfg.get("cue_custom") or {}
        c_custom[key] = dest_name
        self.cfg.set("cue_custom", c_custom)
        self.apply()
        log_info(f"成功更換提示音 [{key}]: {dest_name}", source="Audio")
        return True, dest_name

    def restore_default_cue(self, key: str):
        """Restore default cue sound file."""
        if key in CUE_DEFAULTS:
            c_custom = self.cfg.get("cue_custom") or {}
            c_custom[key] = ""
            self.cfg.set("cue_custom", c_custom)
            self.apply()
            log_info(f"已恢復預設提示音: {key}", source="Audio")

    def play_file(self, file_path: str, volume: int | None = None):
        """播放任意音訊檔案（MP3/WAV），用於語音辨識回應、TTS 或 Gemini Live 串流回覆。"""
        if not file_path or not os.path.exists(file_path):
            return
        master_vol = int(self.cfg.get("volume", 80))
        vol = master_vol if volume is None else int((volume * master_vol) / 100.0)
        if self._muted or vol <= 0:
            return
        try:
            if self._file_voice is None:
                self._file_voice = MciVoice("pet_playback_voice")
            self._file_voice.open(file_path, vol)
            self._file_voice.play()
        except Exception as e:
            log_error(f"播放語音檔案失敗 ({file_path}): {e}", source="Audio")

    def stop_file(self):
        """停止目前正在播放的語音檔案。"""
        try:
            if self._file_voice:
                self._file_voice.stop()
                self._file_voice.close()
        except Exception:
            pass

    def close_all(self):
        """Close all opened MCI voices."""
        try:
            for p in self.pools.values():
                p.close()
            if self._file_voice:
                self._file_voice.close()
        except Exception:
            pass
