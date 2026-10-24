"""Entry point:  python main.py   (add --selftest for a headless check)."""
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


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

    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    qapp = QApplication(sys.argv)
    qapp.setQuitOnLastWindowClosed(False)
    qapp.setApplicationName("Desktop Pet")

    from deskpet.config import Config
    from deskpet.font_manager import init_app_font
    init_app_font(Config())

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
