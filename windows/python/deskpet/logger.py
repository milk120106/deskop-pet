"""Global logging and crash detection system for Desktop Pet.
Supports DEBUG, INFO, WARNING, ERROR levels.
Logs are stored in logs/session_YYYYMMDD_HHMMSS.log.
Retains logs within 14 days and at most 7 session log files.
Maintains a 500-entry in-memory ring buffer for the control panel log viewer.
Captures uncaught exceptions via sys.excepthook and threading.excepthook into crash.log.
"""
from __future__ import annotations

import atexit
import json
import os
import sys
import threading
import traceback
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
LOGS_DIR = APP_DIR / "logs"
CRASH_LOG_PATH = LOGS_DIR / "crash.log"
STATE_FILE_PATH = LOGS_DIR / ".session_state.json"
LEGACY_LOG_PATH = APP_DIR / "pet.log"

LEVEL_DEBUG = 10
LEVEL_INFO = 20
LEVEL_WARNING = 30
LEVEL_ERROR = 40
LEVEL_CRITICAL = 50

LEVEL_NAMES = {
    LEVEL_DEBUG: "DEBUG",
    LEVEL_INFO: "INFO",
    LEVEL_WARNING: "WARNING",
    LEVEL_ERROR: "ERROR",
    LEVEL_CRITICAL: "CRITICAL",
}

NAME_TO_LEVEL = {
    "DEBUG": LEVEL_DEBUG,
    "INFO": LEVEL_INFO,
    "WARNING": LEVEL_WARNING,
    "ERROR": LEVEL_ERROR,
    "CRITICAL": LEVEL_CRITICAL,
}


class GlobalLogger:
    """Thread-safe global logger with session files, memory ring buffer, and crash detection."""

    _instance: GlobalLogger | None = None
    _singleton_lock = threading.Lock()

    def __init__(self, retention_days: int = 14, max_session_files: int = 7, buffer_size: int = 500):
        self._lock = threading.RLock()
        self.retention_days = retention_days
        self.max_session_files = max_session_files
        self.buffer_size = buffer_size

        # In-memory ring buffer for console/GUI log viewer
        self._memory_buffer: deque[dict] = deque(maxlen=buffer_size)

        # Ensure logs directory exists
        LOGS_DIR.mkdir(parents=True, exist_ok=True)

        # Check crash status of previous run BEFORE writing new state file
        self.previous_crash_info = self._detect_previous_crash()

        # Session setup
        now = datetime.now()
        self.session_id = f"session_{now.strftime('%Y%m%d_%H%M%S')}"
        self.session_file = LOGS_DIR / f"{self.session_id}.log"
        self.min_level = LEVEL_DEBUG

        # Clean old session logs
        self._clean_old_logs()

        # Write initial session state (clean_exit = False until proper shutdown)
        self._write_state(clean_exit=False)

        # Register exit hook to mark clean exit
        atexit.register(self.mark_clean_exit)

        # Log session start
        self.info(f"=== 日誌工作階段啟動 [{self.session_id}] (PID: {os.getpid()}) ===", source="System")
        if self.previous_crash_info.get("crashed"):
            last_sess = self.previous_crash_info.get("last_session", "未知")
            self.warning(f"偵測到上次工作階段異常終止或崩潰: {last_sess}", source="CrashGuard")

    @classmethod
    def get_instance(cls) -> GlobalLogger:
        if cls._instance is None:
            with cls._singleton_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    # ------------------------------------------------------------- Crash Detection
    def _detect_previous_crash(self) -> dict:
        """Examine .session_state.json to determine if the prior run exited cleanly."""
        if not STATE_FILE_PATH.exists():
            return {"crashed": False, "reason": "無前次狀態檔案"}

        try:
            raw = STATE_FILE_PATH.read_text(encoding="utf-8")
            data = json.loads(raw)
            clean_exit = bool(data.get("clean_exit", False))
            last_pid = data.get("pid")
            last_session = data.get("session_id", "未知")
            start_time = data.get("start_time", "未知")

            if clean_exit:
                return {
                    "crashed": False,
                    "last_session": last_session,
                    "last_pid": last_pid,
                    "reason": "正常結束",
                }

            # If clean_exit is False, the previous process died abnormally
            crash_detail = self._read_recent_crash_log(start_time)
            return {
                "crashed": True,
                "last_session": last_session,
                "last_pid": last_pid,
                "start_time": start_time,
                "reason": "前次程式未正常呼叫清理程序即退出（可能異常崩潰或被強制終止）",
                "detail": crash_detail,
            }
        except Exception as e:
            return {
                "crashed": False,
                "reason": f"解析前次狀態失敗: {e}",
            }

    def _read_recent_crash_log(self, after_time: str) -> str:
        """Read the tail of crash.log if available."""
        if not CRASH_LOG_PATH.exists():
            return ""
        try:
            content = CRASH_LOG_PATH.read_text(encoding="utf-8", errors="replace")
            lines = content.strip().splitlines()
            return "\n".join(lines[-30:]) if lines else ""
        except Exception:
            return ""

    def _write_state(self, clean_exit: bool):
        """Persist session state for crash detection."""
        try:
            state = {
                "session_id": getattr(self, "session_id", "unknown"),
                "pid": os.getpid(),
                "start_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "clean_exit": clean_exit,
            }
            tmp = STATE_FILE_PATH.with_suffix(".tmp")
            tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(tmp, STATE_FILE_PATH)
        except Exception:
            pass

    def mark_clean_exit(self):
        """Mark current session as cleanly exited."""
        with self._lock:
            try:
                self.info(f"=== 日誌工作階段正常關閉 [{self.session_id}] ===", source="System")
                self._write_state(clean_exit=True)
            except Exception:
                pass

    def check_crash(self) -> dict:
        """Public method to inspect if previous launch crashed."""
        return dict(self.previous_crash_info)

    # ------------------------------------------------------------- Log Retention
    def _clean_old_logs(self):
        """Retain logs within retention_days and at most max_session_files."""
        try:
            now = datetime.now()
            cutoff = now - timedelta(days=self.retention_days)

            files = []
            for entry in LOGS_DIR.glob("session_*.log"):
                if entry.name == self.session_file.name:
                    continue
                try:
                    mtime = datetime.fromtimestamp(entry.stat().st_mtime)
                    # Also attempt to parse filename session_YYYYMMDD_HHMMSS.log
                    name_parts = entry.stem.split("_")
                    if len(name_parts) >= 3:
                        dt_str = f"{name_parts[1]}_{name_parts[2]}"
                        try:
                            file_dt = datetime.strptime(dt_str, "%Y%m%d_%H%M%S")
                        except ValueError:
                            file_dt = mtime
                    else:
                        file_dt = mtime

                    files.append((file_dt, entry))
                except OSError:
                    continue

            # 1. Delete files older than retention_days (14 days)
            surviving = []
            for f_dt, f_path in files:
                if f_dt < cutoff:
                    try:
                        f_path.unlink()
                    except OSError:
                        pass
                else:
                    surviving.append((f_dt, f_path))

            # 2. Sort remaining files oldest to newest; keep at most max_session_files - 1 (to leave room for current)
            surviving.sort(key=lambda x: x[0])
            max_allowed = max(1, self.max_session_files - 1)
            while len(surviving) > max_allowed:
                oldest_dt, oldest_path = surviving.pop(0)
                try:
                    oldest_path.unlink()
                except OSError:
                    pass

        except Exception as e:
            # Cleanup should never fail or crash
            sys.stderr.write(f"[Logger Cleanup Error] {e}\n")

    # ------------------------------------------------------------- Core Logging
    def log_record(self, level: int, message: str, source: str = "Pet", exc_info: bool | BaseException = False):
        if level < self.min_level:
            return

        now = datetime.now()
        ts_full = now.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        ts_short = now.strftime("%Y-%m-%d %H:%M:%S")
        lvl_name = LEVEL_NAMES.get(level, "INFO")

        extra_tb = ""
        if exc_info:
            if isinstance(exc_info, BaseException):
                extra_tb = "".join(traceback.format_exception(type(exc_info), exc_info, exc_info.__traceback__))
            else:
                extra_tb = traceback.format_exc()
            if extra_tb and not extra_tb.startswith("NoneType"):
                message = f"{message}\n{extra_tb}".strip()

        formatted = f"[{ts_full}] [{lvl_name:<5}] [{source}] {message}"
        legacy_formatted = f"[{ts_short}] [{lvl_name}] {message}"

        entry = {
            "timestamp": ts_full,
            "level": lvl_name,
            "level_no": level,
            "source": source,
            "message": message,
            "formatted": formatted,
        }

        with self._lock:
            # 1. Append to memory ring buffer
            self._memory_buffer.append(entry)

            # 2. Append to current session log file
            try:
                with open(self.session_file, "a", encoding="utf-8") as f:
                    f.write(formatted + "\n")
            except OSError:
                pass

            # 3. Synchronize with legacy pet.log for backward compatibility
            try:
                with open(LEGACY_LOG_PATH, "a", encoding="utf-8") as f:
                    f.write(legacy_formatted + "\n")
            except OSError:
                pass

            # 4. Stdout/Stderr output
            if sys.stdout:
                try:
                    stream = sys.stderr if level >= LEVEL_ERROR else sys.stdout
                    print(formatted, file=stream)
                except Exception:
                    pass

    def debug(self, msg: str, source: str = "Pet"):
        self.log_record(LEVEL_DEBUG, msg, source=source)

    def info(self, msg: str, source: str = "Pet"):
        self.log_record(LEVEL_INFO, msg, source=source)

    def warning(self, msg: str, source: str = "Pet"):
        self.log_record(LEVEL_WARNING, msg, source=source)

    def error(self, msg: str, source: str = "Pet", exc_info: bool | BaseException = False):
        self.log_record(LEVEL_ERROR, msg, source=source, exc_info=exc_info)

    def critical(self, msg: str, source: str = "Pet", exc_info: bool | BaseException = False):
        self.log_record(LEVEL_CRITICAL, msg, source=source, exc_info=exc_info)

    # ------------------------------------------------------------- Ring Buffer Query
    def get_recent_logs(self, count: int = 500, level: str | None = None, search: str | None = None) -> list[dict]:
        """Query memory log cache with level filter and text search.
        
        level: 'ALL', 'DEBUG', 'INFO', 'WARNING', 'ERROR'
        search: case-insensitive keyword
        """
        with self._lock:
            entries = list(self._memory_buffer)

        # Apply level filter
        target_min_no = None
        if level and level.upper() != "ALL":
            target_min_no = NAME_TO_LEVEL.get(level.upper(), None)

        results = []
        q = search.lower().strip() if search else None

        for item in entries:
            if target_min_no is not None and item["level_no"] < target_min_no:
                continue
            if q:
                if q not in item["message"].lower() and q not in item["source"].lower() and q not in item["level"].lower():
                    continue
            results.append(item)

        if count and count > 0:
            return results[-count:]
        return results

    def clear_memory_buffer(self):
        with self._lock:
            self._memory_buffer.clear()

    # ------------------------------------------------------------- Exception Hooks
    def handle_exception(self, exc_type, exc_value, exc_traceback, thread_name: str = "MainThread"):
        """Write unhandled exception to crash.log and session log."""
        tb_str = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        crash_entry = (
            f"\n{'='*70}\n"
            f"崩潰時間: {now_str}\n"
            f"工作階段: {self.session_id}\n"
            f"執行緒: {thread_name}\n"
            f"例外型別: {getattr(exc_type, '__name__', str(exc_type))}\n"
            f"例外訊息: {exc_value}\n"
            f"回溯記錄:\n{tb_str}"
            f"{'='*70}\n"
        )

        with self._lock:
            # 1. Write to crash.log
            try:
                with open(CRASH_LOG_PATH, "a", encoding="utf-8") as f:
                    f.write(crash_entry)
            except OSError:
                pass

            # 2. Record to session log and buffer
            self.critical(f"未捕獲之嚴重例外 [{thread_name}]: {exc_value}\n{tb_str}", source="CrashHandler")


# Module-level convenience functions
def get_logger() -> GlobalLogger:
    return GlobalLogger.get_instance()

def debug(msg: str, source: str = "Pet"):
    get_logger().debug(msg, source=source)

def info(msg: str, source: str = "Pet"):
    get_logger().info(msg, source=source)

def warning(msg: str, source: str = "Pet"):
    get_logger().warning(msg, source=source)

def error(msg: str, source: str = "Pet", exc_info: bool | BaseException = False):
    get_logger().error(msg, source=source, exc_info=exc_info)

def critical(msg: str, source: str = "Pet", exc_info: bool | BaseException = False):
    get_logger().critical(msg, source=source, exc_info=exc_info)

def log(msg: str):
    """Backward compatibility with legacy config.log()"""
    get_logger().info(msg, source="Pet")

def check_crash() -> dict:
    return get_logger().check_crash()

def clear_memory_buffer():
    get_logger().clear_memory_buffer()

def mark_clean_exit():
    get_logger().mark_clean_exit()

def get_recent_logs(
    count: int = 500,
    level: str | None = None,
    search: str | None = None,
    max_lines: int | None = None,
    level_filter: str | None = None,
    query_filter: str | None = None,
) -> list[dict]:
    c = max_lines if max_lines is not None else count
    lvl = level_filter if level_filter is not None else level
    q = query_filter if query_filter is not None else search
    return get_logger().get_recent_logs(count=c, level=lvl, search=q)

def install_exception_hooks():
    """Install sys.excepthook and threading.excepthook to intercept crashes."""
    orig_sys_hook = sys.excepthook

    def _sys_excepthook(exc_type, exc_value, exc_traceback):
        get_logger().handle_exception(exc_type, exc_value, exc_traceback, thread_name="MainThread")
        if orig_sys_hook and orig_sys_hook is not _sys_excepthook:
            try:
                orig_sys_hook(exc_type, exc_value, exc_traceback)
            except Exception:
                pass

    sys.excepthook = _sys_excepthook

    if hasattr(threading, "excepthook"):
        orig_threading_hook = threading.excepthook

        def _threading_excepthook(args):
            thread_name = args.thread.name if args.thread else "BackgroundThread"
            get_logger().handle_exception(args.exc_type, args.exc_value, args.exc_traceback, thread_name=thread_name)
            if orig_threading_hook and orig_threading_hook is not _threading_excepthook:
                try:
                    orig_threading_hook(args)
                except Exception:
                    pass

        threading.excepthook = _threading_excepthook
