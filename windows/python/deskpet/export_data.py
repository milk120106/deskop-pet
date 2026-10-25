"""設定與資料安全匯出與匯入系統（含 YuYue 8 層高強度複合加解密與 API Key 安全脫敏）。"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import zlib
from datetime import datetime
from pathlib import Path

from .config import APP_DIR, APP_VERSION, CUSTOM_CHARS_DIR, Config, log


TOTAL_CODEPOINTS = 0x110000 - 2048
HEX_CHARS = "0123456789abcdef"


def _cp_to_idx(cp: int) -> int:
    return cp if cp < 0xD800 else cp - 2048


def _idx_to_cp(idx: int) -> int:
    return idx if idx < 0xD800 else idx + 2048


class YuYueCipher:
    """YuYue 高強度 8 層複合對稱式加密引擎。
    純 Python 內建庫實作（hashlib, base64, zlib），無任何第三方套件依賴。
    8 層複合管道：
      1. 動態凱薩位移 caesar_shift1 (Unicode Codepoint 空間)
      2. 動態柵欄加密 Rail Fence Cipher (3~7 軌)
      3. Base64 編碼
      4. 轉 ASCII 8 位元二進位字串串接
      5. 二進位轉 16 進位字串
      6. 動態凱薩位移 caesar_shift2 (十六進位字元空間)
      7. Base32 編碼
      8. zlib 緊緻壓縮 + 最終 Base64 包裝
    """

    @staticmethod
    def _caesar_unicode(text: str, shift: int, decrypt: bool = False) -> str:
        s = (-shift) if decrypt else shift
        res = []
        for ch in text:
            idx = _cp_to_idx(ord(ch))
            new_idx = (idx + s) % TOTAL_CODEPOINTS
            res.append(chr(_idx_to_cp(new_idx)))
        return "".join(res)

    @staticmethod
    def _rail_fence_encrypt(text: str, rails: int) -> str:
        if rails <= 1 or len(text) <= rails:
            return text
        fence = [[] for _ in range(rails)]
        r, d = 0, 1
        for c in text:
            fence[r].append(c)
            r += d
            if r == rails - 1:
                d = -1
            elif r == 0:
                d = 1
        return "".join("".join(row) for row in fence)

    @staticmethod
    def _rail_fence_decrypt(cipher: str, rails: int) -> str:
        if rails <= 1 or len(cipher) <= rails:
            return cipher
        r, d = 0, 1
        rail_indices = [[] for _ in range(rails)]
        for i in range(len(cipher)):
            rail_indices[r].append(i)
            r += d
            if r == rails - 1:
                d = -1
            elif r == 0:
                d = 1
        res = [None] * len(cipher)
        pos = 0
        for row in range(rails):
            for idx in rail_indices[row]:
                res[idx] = cipher[pos]
                pos += 1
        return "".join(res)

    @staticmethod
    def _caesar_hex(hex_str: str, shift: int, decrypt: bool = False) -> str:
        s = (-shift) if decrypt else shift
        shifted = []
        for c in hex_str:
            idx = HEX_CHARS.find(c)
            if idx != -1:
                shifted.append(HEX_CHARS[(idx + s) % 16])
            else:
                shifted.append(c)
        return "".join(shifted)

    @classmethod
    def derive_params(cls, password: str, salt: bytes) -> tuple[bytes, int, int, int, str]:
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
        verify_hash = hashlib.sha256(dk + b"YuYueVerifyAnchor").hexdigest()
        shift1 = (dk[0] % 25) + 1
        rails = 3 + (dk[1] % 5)
        shift2 = (dk[2] % 15) + 1
        return dk, shift1, rails, shift2, verify_hash

    @classmethod
    def encrypt(cls, plaintext: str, password: str, salt: bytes | None = None) -> tuple[str, str, str]:
        """執行 8 層複合加密，回傳 (ciphertext, salt_hex, verify_hash)。"""
        if salt is None:
            salt = os.urandom(16)
        _, shift1, rails, shift2, verify_hash = cls.derive_params(password, salt)

        # 步驟 1: 凱薩加密 1
        s1 = cls._caesar_unicode(plaintext, shift1, decrypt=False)
        # 步驟 2: 柵欄加密 (3~7軌)
        s2 = cls._rail_fence_encrypt(s1, rails)
        # 步驟 3: Base64 編碼
        s3 = base64.b64encode(s2.encode("utf-8")).decode("ascii")
        # 步驟 4: 轉 8 位元二進位字串串接
        s4 = "".join(f"{ord(c):08b}" for c in s3)
        # 步驟 5: 二進位轉 16 進位字串
        s5 = "".join(f"{int(s4[i:i+4], 2):x}" for i in range(0, len(s4), 4))
        # 步驟 6: 十六進位空間二次凱薩加密
        s6 = cls._caesar_hex(s5, shift2, decrypt=False)
        # 步驟 7: Base32 編碼
        s7 = base64.b32encode(s6.encode("ascii"))
        # 步驟 8: zlib 緊緻壓縮 + 最終 Base64 包裝
        compressed = zlib.compress(s7, level=9)
        final_b64 = base64.b64encode(compressed).decode("ascii")

        return final_b64, salt.hex(), verify_hash

    @classmethod
    def decrypt(cls, ciphertext: str, password: str, salt_hex: str, verify_hash: str) -> str:
        """執行逆向 8 層解密管線，驗證密碼後回傳原始字串。若密碼不符拋出 ValueError。"""
        salt = bytes.fromhex(salt_hex)
        _, shift1, rails, shift2, computed_verify = cls.derive_params(password, salt)
        if computed_verify != verify_hash:
            raise ValueError("解密密碼錯誤，無法解鎖備份檔案。")

        try:
            # 逆向 8: Base64 解碼 + zlib 解壓縮
            compressed = base64.b64decode(ciphertext.encode("ascii"))
            s7 = zlib.decompress(compressed)
            # 逆向 7: Base32 解碼
            s6 = base64.b32decode(s7).decode("ascii")
            # 逆向 6: 十六進位凱薩解密
            s5 = cls._caesar_hex(s6, shift2, decrypt=True)
            # 逆向 5 & 4: 十六進位轉二進位，再轉 ASCII 字元
            s4 = "".join(f"{int(c, 16):04b}" for c in s5)
            s3 = "".join(chr(int(s4[i:i+8], 2)) for i in range(0, len(s4), 8))
            # 逆向 3: Base64 解碼
            s2 = base64.b64decode(s3.encode("ascii")).decode("utf-8")
            # 逆向 2: 柵欄解密
            s1 = cls._rail_fence_decrypt(s2, rails)
            # 逆向 1: 凱薩解密 1
            plaintext = cls._caesar_unicode(s1, shift1, decrypt=True)
            return plaintext
        except Exception as e:
            if isinstance(e, ValueError) and "解密密碼錯誤" in str(e):
                raise
            raise ValueError(f"備份檔案損壞或格式無效: {e}")


def export_backup_data(
    cfg: Config,
    dest_path: str | Path | None = None,
    include_keys: bool = False,
    password: str = "",
) -> dict:
    """匯出所有寵物配置與資料。
    若 include_keys 為 False，自動剔除或脫敏所有金鑰。
    若指定 password，則採用 YuYue 8 層複合高強度加密。
    回傳匯出之 dict 結構。
    """
    data_copy = json.loads(json.dumps(cfg.data, ensure_ascii=False))

    if not include_keys:
        # 安全脫敏：徹底剔除所有 API Key 與憑證
        data_copy["api_keys"] = {"deepseek": "", "openai": "", "anthropic": "", "gemini": ""}
        if "api_profiles" in data_copy and isinstance(data_copy["api_profiles"], list):
            for prof in data_copy["api_profiles"]:
                if isinstance(prof, dict):
                    prof["key"] = ""
        data_copy["telegram_bot_token"] = ""
    else:
        # 匯出真實可用金鑰
        decrypted_keys = {}
        for prov in ("deepseek", "openai", "anthropic", "gemini"):
            decrypted_keys[prov] = cfg.get_current_api_key(prov)
        data_copy["api_keys"] = decrypted_keys

    # 封裝自訂角色資源（包含 sprite.png 與 tablet.txt）
    custom_chars_payload = {}
    if CUSTOM_CHARS_DIR.exists():
        for d in CUSTOM_CHARS_DIR.iterdir():
            if d.is_dir():
                cid = d.name
                char_info = {}
                t_file = d / "tablet.txt"
                if t_file.exists():
                    try:
                        char_info["tablet"] = t_file.read_text(encoding="utf-8").strip()
                    except Exception:
                        pass
                s_file = d / "sprite.png"
                if s_file.exists():
                    try:
                        char_info["sprite_b64"] = base64.b64encode(s_file.read_bytes()).decode("ascii")
                    except Exception:
                        pass
                if char_info:
                    custom_chars_payload[cid] = char_info

    now_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    backup_payload = {
        "format": "deskpet_backup",
        "app_version": APP_VERSION,
        "exported_at": now_iso,
        "has_api_keys": bool(include_keys),
        "config": data_copy,
        "custom_characters": custom_chars_payload,
    }

    payload_json = json.dumps(backup_payload, ensure_ascii=False, indent=2)

    if password and password.strip():
        # 進行 YuYue 8 層複合加密
        ciphertext, salt_hex, verify_hash = YuYueCipher.encrypt(payload_json, password.strip())
        final_envelope = {
            "format": "deskpet_backup_yuyue",
            "version": "1.0",
            "encrypted": True,
            "exported_at": now_iso,
            "has_api_keys": bool(include_keys),
            "salt": salt_hex,
            "verify_hash": verify_hash,
            "payload": ciphertext,
        }
        if dest_path:
            Path(dest_path).write_text(json.dumps(final_envelope, ensure_ascii=False, indent=2), encoding="utf-8")
        log(f"全設定與資料已採用 YuYue 高強度加密匯出至：{dest_path}")
        return final_envelope
    else:
        if dest_path:
            Path(dest_path).write_text(payload_json, encoding="utf-8")
        log(f"全設定與資料已安全匯出至：{dest_path}")
        return backup_payload


def import_backup_data(app, source_path: str | Path, password: str = "") -> dict:
    """匯入並套用設定與資料備份檔案。
    若檔案為 YuYue 加密檔且未提供密碼，則拋出 ValueError('NEED_PASSWORD')。
    還原成功後同步至 app 與設定。
    """
    p = Path(source_path)
    if not p.exists():
        raise FileNotFoundError(f"找不到備份檔案：{source_path}")

    raw_text = p.read_text(encoding="utf-8")
    parsed = json.loads(raw_text)

    is_encrypted = parsed.get("encrypted") is True or parsed.get("format") == "deskpet_backup_yuyue"
    if is_encrypted:
        if not password:
            raise ValueError("NEED_PASSWORD")
        salt_hex = parsed.get("salt", "")
        verify_hash = parsed.get("verify_hash", "")
        ciphertext = parsed.get("payload", "")
        decrypted_json = YuYueCipher.decrypt(ciphertext, password, salt_hex, verify_hash)
        backup_dict = json.loads(decrypted_json)
    else:
        backup_dict = parsed

    cfg_data = backup_dict.get("config", {})
    if not isinstance(cfg_data, dict):
        raise ValueError("無效的備份資料格式：缺少 config 設定物件。")

    # 還原 config 項目
    for k, v in cfg_data.items():
        if k in app.cfg.data:
            app.cfg.data[k] = v

    # 若備份中包含自訂角色資料，還原至 custom_characters/
    custom_chars = backup_dict.get("custom_characters", {})
    if isinstance(custom_chars, dict):
        CUSTOM_CHARS_DIR.mkdir(parents=True, exist_ok=True)
        for cid, char_info in custom_chars.items():
            if not isinstance(char_info, dict):
                continue
            char_dir = CUSTOM_CHARS_DIR / cid
            char_dir.mkdir(parents=True, exist_ok=True)
            if "tablet" in char_info:
                (char_dir / "tablet.txt").write_text(char_info["tablet"], encoding="utf-8")
            if "sprite_b64" in char_info:
                try:
                    (char_dir / "sprite.png").write_bytes(base64.b64decode(char_info["sprite_b64"].encode("ascii")))
                except Exception:
                    pass

    # 儲存設定至磁碟
    app.cfg.save()

    # 套用關鍵變更至運作中的寵物與介面
    try:
        if hasattr(app, "set_character"):
            app.set_character(app.cfg.get("character", "deepseek"))
        if hasattr(app, "set_variant"):
            app.set_variant(app.cfg.get("variant", "square"))
        if hasattr(app, "set_size"):
            app.set_size(app.cfg.get("size", 454))
        if hasattr(app, "set_strict_custom_image_ratio"):
            app.set_strict_custom_image_ratio(app.cfg.get("strict_custom_image_ratio", True))
        if hasattr(app, "set_sound_enabled"):
            app.set_sound_enabled(app.cfg.get("sound", True))
        if hasattr(app, "set_volume"):
            app.set_volume(app.cfg.get("volume", 80))
        if hasattr(app, "set_opacity"):
            app.set_opacity(app.cfg.get("opacity", 100))
        if hasattr(app, "set_always_on_top"):
            app.set_always_on_top(app.cfg.get("always_on_top", True))
        if hasattr(app, "set_click_through"):
            app.set_click_through(app.cfg.get("click_through", False))
        if hasattr(app, "alarm_dispatcher") and hasattr(app.alarm_dispatcher, "load_alarms"):
            app.alarm_dispatcher.load_alarms()
        if hasattr(app, "pet") and app.pet:
            app.pet._clear_cache()
            app.pet._resize_window()
            app.pet.keep_on_screen()
            app.pet.update()
    except Exception as exc:
        log(f"套用匯入設定至寵物實例時發生例外: {exc}")

    log("設定與資料備份已成功還原並套用。")
    return backup_dict
