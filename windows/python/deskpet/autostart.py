# -*- coding: utf-8 -*-
"""Windows 開機自啟動 (Auto-Start on Boot) 管理模組。
使用 Windows 登錄檔 (HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run) 達成安全無權限要求的開機自動啟動。
"""
from __future__ import annotations

import sys
import os
from pathlib import Path
from .logger import log

RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "DesktopPet"


def _get_launch_command() -> str:
    """取得可攜式正確啟動命令列。相容 PyInstaller 打包單一執行檔與原始 Python 腳本。"""
    if getattr(sys, "frozen", False):
        exe_path = sys.executable
        return f'"{exe_path}"'
    else:
        python_exe = sys.executable
        main_script = Path(__file__).resolve().parent.parent / "main.py"
        return f'"{python_exe}" "{main_script}"'


def is_auto_start_registered() -> bool:
    """檢查登錄檔中是否已登記開機自啟動。"""
    if sys.platform != "win32":
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_READ) as key:
            val, _ = winreg.QueryValueEx(key, APP_NAME)
            return bool(val)
    except FileNotFoundError:
        return False
    except Exception as e:
        log("AutoStart", f"查詢開機自啟動登錄檔失敗：{e}")
        return False


def set_auto_start(enable: bool) -> bool:
    """設定或移除 Windows 使用者登錄檔開機自啟動項目。"""
    if sys.platform != "win32":
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_SET_VALUE) as key:
            if enable:
                cmd = _get_launch_command()
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, cmd)
                log("AutoStart", f"已成功設定開機自動啟動：{cmd}")
            else:
                try:
                    winreg.DeleteValue(key, APP_NAME)
                    log("AutoStart", "已成功移除開機自動啟動登錄檔項。")
                except FileNotFoundError:
                    pass
        return True
    except Exception as e:
        log("AutoStart", f"設定開機自啟動失敗：{e}")
        return False


def sync_auto_start(cfg) -> bool:
    """根據配置檔案同步登錄檔狀態。"""
    enabled = bool(cfg.get("auto_start_on_boot", False))
    return set_auto_start(enabled)
