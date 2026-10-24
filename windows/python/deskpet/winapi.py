"""Thin Win32 helpers (click-through, topmost, DPAPI, CredUI) via ctypes."""
from __future__ import annotations

import base64
import ctypes
import sys
from ctypes import wintypes

IS_WIN = sys.platform == "win32"

GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020
WS_EX_LAYERED = 0x00080000
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
SWP_NOSIZE = 0x1
SWP_NOMOVE = 0x2
SWP_NOACTIVATE = 0x10
SWP_SHOWWINDOW = 0x40
WM_NCHITTEST = 0x0084
HTTRANSPARENT = -1

if IS_WIN:
    _u = ctypes.windll.user32
    _get = _u.GetWindowLongPtrW
    _get.restype = ctypes.c_ssize_t
    _get.argtypes = [ctypes.c_void_p, ctypes.c_int]
    _set = _u.SetWindowLongPtrW
    _set.restype = ctypes.c_ssize_t
    _set.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_ssize_t]
    _pos = _u.SetWindowPos
    _pos.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                     ctypes.c_int, ctypes.c_int, ctypes.c_uint]

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [
            ("cbData", wintypes.DWORD),
            ("pbData", ctypes.POINTER(ctypes.c_char)),
        ]

    class CREDUI_INFOW(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("hwndParent", wintypes.HWND),
            ("pszMessageText", wintypes.LPCWSTR),
            ("pszCaptionText", wintypes.LPCWSTR),
            ("hbmBanner", wintypes.HBITMAP),
        ]


def set_click_through(hwnd: int, on: bool):
    """Make the whole window ignore the mouse (clicks fall through to what is below)."""
    if not IS_WIN or not hwnd:
        return
    st = _get(hwnd, GWL_EXSTYLE)
    st |= WS_EX_LAYERED
    st = (st | WS_EX_TRANSPARENT) if on else (st & ~WS_EX_TRANSPARENT)
    _set(hwnd, GWL_EXSTYLE, st)


def set_topmost(hwnd: int, on: bool):
    if not IS_WIN or not hwnd:
        return
    _pos(hwnd, HWND_TOPMOST if on else HWND_NOTOPMOST, 0, 0, 0, 0,
         SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)


def hide_from_taskbar(hwnd: int):
    if not IS_WIN or not hwnd:
        return
    st = _get(hwnd, GWL_EXSTYLE)
    _set(hwnd, GWL_EXSTYLE, (st | WS_EX_TOOLWINDOW) & ~0x00040000)  # no APPWINDOW


# ==============================================================================
# Windows DPAPI 加密與解密（原生 crypt32.dll）
# ==============================================================================
DPAPI_PREFIX = "DPAPI:"


def dpapi_encrypt(data: str) -> str:
    """使用 Windows 原生 DPAPI 加密字串，回傳 Base64 編碼字串（帶 DPAPI: 前綴）。"""
    if not data:
        return ""
    if not IS_WIN:
        return data
    try:
        raw = data.encode("utf-8")
        in_blob = DATA_BLOB(len(raw), ctypes.cast(ctypes.create_string_buffer(raw), ctypes.POINTER(ctypes.c_char)))
        out_blob = DATA_BLOB()
        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32
        if not crypt32.CryptProtectData(
            ctypes.byref(in_blob),
            "deskpet_api_key",
            None,
            None,
            None,
            0,
            ctypes.byref(out_blob),
        ):
            return data
        try:
            buf = ctypes.string_at(out_blob.pbData, out_blob.cbData)
            return DPAPI_PREFIX + base64.b64encode(buf).decode("ascii")
        finally:
            kernel32.LocalFree(out_blob.pbData)
    except Exception as exc:
        try:
            from .logger import log
            log(f"DPAPI 加密發生例外: {exc}")
        except Exception:
            pass
        return data


def dpapi_decrypt(cipher: str) -> str:
    """使用 Windows 原生 DPAPI 解密字串。若未加密或解密失敗，安全回退不崩潰。"""
    if not cipher:
        return ""
    if not isinstance(cipher, str):
        return str(cipher)
    if not cipher.startswith(DPAPI_PREFIX):
        return cipher
    if not IS_WIN:
        return cipher
    try:
        b64_part = cipher[len(DPAPI_PREFIX):]
        raw_bytes = base64.b64decode(b64_part.encode("ascii"))
        in_blob = DATA_BLOB(len(raw_bytes), ctypes.cast(ctypes.create_string_buffer(raw_bytes), ctypes.POINTER(ctypes.c_char)))
        out_blob = DATA_BLOB()
        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32
        if not crypt32.CryptUnprotectData(
            ctypes.byref(in_blob),
            None,
            None,
            None,
            None,
            0,
            ctypes.byref(out_blob),
        ):
            return ""
        try:
            return ctypes.string_at(out_blob.pbData, out_blob.cbData).decode("utf-8")
        finally:
            kernel32.LocalFree(out_blob.pbData)
    except Exception as exc:
        try:
            from .logger import log
            log(f"DPAPI 解密失敗，安全回退: {exc}")
        except Exception:
            pass
        return ""


# ==============================================================================
# Windows 原生身分驗證對話框（CredUIPromptForWindowsCredentials）
# ==============================================================================
def prompt_windows_credentials(
    hwnd: int = 0,
    message: str = "請驗證您的 Windows 本機身分以存取或修改 API 金鑰",
    caption: str = "桌面寵物 - Windows 安全性驗證",
) -> bool:
    """呼叫 Windows 原生認證對話框驗證本機使用者身分（支援 PIN、密碼或 Windows Hello）。"""
    if not IS_WIN:
        return True
    try:
        ui_info = CREDUI_INFOW()
        ui_info.cbSize = ctypes.sizeof(CREDUI_INFOW)
        ui_info.hwndParent = hwnd or 0
        ui_info.pszMessageText = message
        ui_info.pszCaptionText = caption
        ui_info.hbmBanner = None

        auth_package = wintypes.ULONG(0)
        out_buf = ctypes.c_void_p()
        out_size = wintypes.ULONG(0)
        save = wintypes.BOOL(False)

        credui = ctypes.windll.credui
        ole32 = ctypes.windll.ole32

        # 嘗試使用 CREDUIWIN_ENUMERATE_CURRENT_USER (0x200) 驗證目前使用者
        flags = 0x200
        ret = credui.CredUIPromptForWindowsCredentialsW(
            ctypes.byref(ui_info),
            0,
            ctypes.byref(auth_package),
            None,
            0,
            ctypes.byref(out_buf),
            ctypes.byref(out_size),
            ctypes.byref(save),
            flags,
        )
        if ret == 0:
            if out_buf:
                ole32.CoTaskMemFree(out_buf)
            return True
        elif ret == 1223:  # ERROR_CANCELLED
            return False

        # 若 0x200 失敗，嘗試通用旗標 CREDUIWIN_GENERIC (0x1)
        flags_generic = 0x1
        ret_gen = credui.CredUIPromptForWindowsCredentialsW(
            ctypes.byref(ui_info),
            0,
            ctypes.byref(auth_package),
            None,
            0,
            ctypes.byref(out_buf),
            ctypes.byref(out_size),
            ctypes.byref(save),
            flags_generic,
        )
        if ret_gen == 0:
            if out_buf:
                ole32.CoTaskMemFree(out_buf)
            return True
        return False
    except Exception as exc:
        try:
            from .logger import log
            log(f"Windows 憑證驗證例外: {exc}")
        except Exception:
            pass
        return False

