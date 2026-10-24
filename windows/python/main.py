"""Entry point:  python main.py   (add --selftest for a headless check)."""
import os
import sys
import traceback

# 1. 先讓 Python 模組路徑正確載入
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 2. 終極路徑切換邏輯
if getattr(sys, 'frozen', False):
    # onefile 模式：切換到解壓暫存區以讀取包在內部的 assets/deskpet 等
    if hasattr(sys, '_MEIPASS'):
        os.chdir(sys._MEIPASS)
    else:
        # onedir/MSI/ZIP 模式：保持在執行檔所在目錄
        os.chdir(os.path.dirname(sys.executable))


def main() -> int:
    from deskpet.logger import (
        check_crash,
        error as log_error,
        info as log_info,
        install_exception_hooks,
        mark_clean_exit,
    )
    # Install crash detection and global exception catcher
    install_exception_hooks()

    from PySide6.QtCore import QLockFile, Qt
    from PySide6.QtWidgets import QApplication, QMessageBox
    from deskpet.config import APP_DIR, log

    # Check crash status of prior launch
    crash_info = check_crash()
    if crash_info.get("crashed"):
        log_info(
            f"偵測到上次工作階段異常終止或崩潰: {crash_info.get('last_session')} (PID: {crash_info.get('last_pid')})",
            source="CrashGuard",
        )

    # 讀取渲染後端設定並在 QApplication 實例化前配置 QSG_RHI_BACKEND
    from deskpet.config import Config
    try:
        cfg_init = Config()
        rendering_backend = str(cfg_init.get("rendering_backend", "opengl")).strip().lower()
        if rendering_backend in ("opengl", "d3d11", "d3d12", "vulkan", "software"):
            os.environ["QSG_RHI_BACKEND"] = rendering_backend
            log_info(f"配置 Qt Quick 渲染後端 (QSG_RHI_BACKEND): {rendering_backend}", source="Main")
    except Exception as exc:
        log_info(f"讀取渲染後端設定失敗，採用預設值: {exc}", source="Main")

    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    qapp = QApplication(sys.argv)
    qapp.setQuitOnLastWindowClosed(False)
    qapp.setApplicationName("Desktop Pet")

    from deskpet.font_manager import init_app_font
    init_app_font(cfg_init)

    if "--selftest" in sys.argv:
        from deskpet.selftest import run
        return run(qapp)

    is_dev = "--dev" in sys.argv
    port_override = None
    if "--port" in sys.argv:
        try:
            p_idx = sys.argv.index("--port")
            if p_idx + 1 < len(sys.argv):
                port_override = int(sys.argv[p_idx + 1])
        except Exception:
            pass

    lock = None
    if not is_dev:
        lock = QLockFile(os.path.join(os.environ.get("TEMP", str(APP_DIR)), "desktop_pet_py.lock"))
        lock.setStaleLockTime(0)
        if not lock.tryLock(100):
            QMessageBox.information(None, "桌面寵物", "寵物已經在執行中。")
            return 0

    try:
        from deskpet.app import App
        app = App(qapp)          # keep a reference
        if port_override:
            app.cfg.set("web_port", port_override)
            if app.web:
                app.web.stop()
                app.web.start()
        log("started" + (" (dev mode)" if is_dev else ""))
        return qapp.exec()
    except Exception as e:
        log_error(f"應用程式發生嚴重例外: {e}", source="Main", exc_info=True)
        raise
    finally:
        mark_clean_exit()
        if lock:
            lock.unlock()


if __name__ == "__main__":
    sys.exit(main())
