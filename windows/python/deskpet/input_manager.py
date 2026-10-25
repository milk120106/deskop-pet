"""用戶自訂操作與按鍵綁定系統（Input & Action Binding System）。

提供：
1. ConflictDetector：區域手勢衝突、時序干涉（單雙擊防抖）與全域熱鍵衝突檢測。
2. InputDispatcher：統一事件分發，解耦 pet.py 中寫死之滑鼠事件。
3. 全域熱鍵管理與 Windows API 整合。
"""
from __future__ import annotations

import ctypes
import math
import time
from typing import Any, Callable
from PySide6.QtCore import QObject, QPoint, QPointF, QRectF, QTimer, Qt, Signal
from PySide6.QtGui import QKeySequence

# Windows API 全域熱鍵常數
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312

WINDOWS_RESERVED_HOTKEYS = {
    "CTRL+ALT+DEL",
    "WIN+L",
    "ALT+F4",
    "CTRL+SHIFT+ESC",
    "WIN+D",
    "WIN+M",
    "WIN+TAB",
    "ALT+TAB",
}

DEFAULT_BINDINGS_INFO = {
    "switch_tablet_page": {
        "trigger": "tablet_double_click",
        "hotkey": "",
        "enabled": True,
        "description": "切換平板分頁"
    },
    "pet_head": {
        "trigger": "head_stroke",
        "hotkey": "",
        "enabled": True,
        "description": "摸頭撫摸互動"
    },
    "drag_pet": {
        "trigger": "body_left_drag",
        "hotkey": "",
        "enabled": True,
        "description": "拖曳寵物移動"
    },
    "remove_iron_pot": {
        "trigger": "head_single_click",
        "hotkey": "",
        "enabled": True,
        "description": "取下單層鐵盆"
    },
    "remove_all_iron_pots": {
        "trigger": "head_double_click",
        "hotkey": "",
        "enabled": True,
        "description": "取下全部鐵盆"
    },
    "feed_pet": {
        "trigger": "drop_rice",
        "hotkey": "Ctrl+Alt+F",
        "enabled": True,
        "description": "快捷餵食"
    },
    "summon_chibi": {
        "trigger": "hotkey",
        "hotkey": "Ctrl+Alt+C",
        "enabled": True,
        "description": "召喚 Q 版小人"
    },
    "quick_hide": {
        "trigger": "hotkey",
        "hotkey": "Ctrl+Shift+H",
        "enabled": False,
        "description": "老闆鍵：快速隱藏/顯示寵物"
    },
    "open_panel": {
        "trigger": "body_right_click",
        "hotkey": "Ctrl+Alt+P",
        "enabled": True,
        "description": "開啟設定面板"
    }
}


def normalize_hotkey(hk: str) -> str:
    """正規化熱鍵字串，例如 'ctrl + alt + f' -> 'CTRL+ALT+F'。"""
    if not hk:
        return ""
    parts = [p.strip().upper() for p in hk.replace("-", "+").split("+") if p.strip()]
    order = {"CTRL": 1, "CONTROL": 1, "ALT": 2, "SHIFT": 3, "WIN": 4, "META": 4}
    mods = sorted([p for p in parts if p in order], key=lambda x: order.get(x, 99))
    keys = [p for p in parts if p not in order]
    return "+".join(mods + keys)


class ConflictDetector:
    """按鍵與手勢衝突檢測引擎。"""

    def __init__(self, bindings: dict[str, dict[str, Any]] | None = None):
        self.bindings = bindings or {}

    def detect_trigger_conflicts(self) -> list[dict[str, Any]]:
        """檢測區域手勢重複衝突。"""
        conflicts = []
        trigger_map: dict[str, list[str]] = {}
        for act_id, item in self.bindings.items():
            if not item.get("enabled", True):
                continue
            trig = item.get("trigger")
            if trig and trig not in ("hotkey", "none", ""):
                if trig in trigger_map:
                    for other in trigger_map[trig]:
                        conflicts.append({
                            "type": "AREA_DUPLICATE",
                            "actions": [act_id, other],
                            "description": f"手勢觸發「{trig}」在動作「{act_id}」與「{other}」間重複",
                        })
                    trigger_map[trig].append(act_id)
                else:
                    trigger_map[trig] = [act_id]
        return conflicts

    def detect_hotkey_conflicts(self) -> list[dict[str, Any]]:
        """檢測熱鍵碰撞與 Windows 保留熱鍵衝突。"""
        conflicts = []
        hotkey_map: dict[str, list[str]] = {}
        for act_id, item in self.bindings.items():
            if not item.get("enabled", True):
                continue
            raw_hk = item.get("hotkey") or ""
            hk = normalize_hotkey(raw_hk)
            if hk:
                if hk in WINDOWS_RESERVED_HOTKEYS:
                    conflicts.append({
                        "type": "WINDOWS_RESERVED",
                        "actions": [act_id],
                        "description": f"熱鍵「{hk}」與 Windows 系統保留熱鍵衝突",
                    })
                if hk in hotkey_map:
                    for other in hotkey_map[hk]:
                        conflicts.append({
                            "type": "HOTKEY_COLLISION",
                            "actions": [act_id, other],
                            "description": f"熱鍵「{hk}」在動作「{act_id}」與「{other}」間碰撞衝突",
                        })
                    hotkey_map[hk].append(act_id)
                else:
                    hotkey_map[hk] = [act_id]
        return conflicts

    def detect_timing_conflicts(self) -> list[dict[str, Any]]:
        """檢測單雙擊時序防抖干涉。"""
        conflicts = []
        head_single = [a for a, it in self.bindings.items() if it.get("enabled", True) and it.get("trigger") == "head_single_click"]
        head_double = [a for a, it in self.bindings.items() if it.get("enabled", True) and it.get("trigger") == "head_double_click"]
        if head_single and head_double:
            for s_act in head_single:
                for d_act in head_double:
                    conflicts.append({
                        "type": "TIMING_DELAY",
                        "actions": [s_act, d_act],
                        "description": f"頭部單擊「{s_act}」與雙擊「{d_act}」共存，單擊將啟用防抖延遲",
                    })
        return conflicts

    def detect_all_conflicts(self) -> list[dict[str, Any]]:
        """檢測全部衝突項目。"""
        return self.detect_trigger_conflicts() + self.detect_hotkey_conflicts() + self.detect_timing_conflicts()

    @staticmethod
    def evaluate_conflicts(bindings: dict[str, dict[str, Any]]) -> dict[str, list[str]]:
        """檢測所有啟用綁定之衝突，回傳 action_id -> [衝突原因/衝突動作ID清單]。"""
        conflicts: dict[str, list[str]] = {k: [] for k in bindings}

        # 1. 檢測滑鼠觸發手勢重複（區域與手勢衝突）
        trigger_map: dict[str, list[str]] = {}
        for act_id, item in bindings.items():
            if not item.get("enabled", True):
                continue
            trig = item.get("trigger")
            if trig and trig not in ("hotkey", "none", ""):
                if trig in trigger_map:
                    for other_act in trigger_map[trig]:
                        conflicts[act_id].append(other_act)
                        conflicts[other_act].append(act_id)
                    trigger_map[trig].append(act_id)
                else:
                    trigger_map[trig] = [act_id]

        # 2. 檢測快捷鍵重複與 Windows 系統保留熱鍵
        hotkey_map: dict[str, list[str]] = {}
        for act_id, item in bindings.items():
            if not item.get("enabled", True):
                continue
            raw_hk = item.get("hotkey") or ""
            hk = normalize_hotkey(raw_hk)
            if hk:
                if hk in WINDOWS_RESERVED_HOTKEYS:
                    conflicts[act_id].append(f"RESERVED:{hk}")
                if hk in hotkey_map:
                    for other_act in hotkey_map[hk]:
                        conflicts[act_id].append(other_act)
                        conflicts[other_act].append(act_id)
                    hotkey_map[hk].append(act_id)
                else:
                    hotkey_map[hk] = [act_id]

        # 3. 檢測時序干涉（同一感應區同時綁定單擊與雙擊）
        head_single = [a for a, it in bindings.items() if it.get("enabled", True) and it.get("trigger") == "head_single_click"]
        head_double = [a for a, it in bindings.items() if it.get("enabled", True) and it.get("trigger") == "head_double_click"]
        if head_single and head_double:
            for s_act in head_single:
                for d_act in head_double:
                    note = f"TIMING_DELAY:{d_act}"
                    if note not in conflicts[s_act]:
                        conflicts[s_act].append(note)

        # 移除重複項並排序
        return {k: sorted(list(set(v))) for k, v in conflicts.items()}

    @staticmethod
    def get_conflict_summary(bindings: dict[str, dict[str, Any]]) -> dict[str, str]:
        """產生各動作衝突之繁體中文描述，便於 UI 高亮與警告提示。"""
        conflicts = ConflictDetector.evaluate_conflicts(bindings)
        summaries: dict[str, str] = {}
        for act_id, conf_list in conflicts.items():
            if not conf_list:
                summaries[act_id] = ""
                continue
            messages = []
            for item in conf_list:
                if item.startswith("RESERVED:"):
                    hk = item.split(":", 1)[1]
                    messages.append(f"熱鍵 {hk} 與 Windows 系統保留快速鍵衝突")
                elif item.startswith("TIMING_DELAY:"):
                    other_id = item.split(":", 1)[1]
                    other_name = bindings.get(other_id, {}).get("description", other_id)
                    messages.append(f"與「{other_name}」手勢共存時，單擊將啟用防抖延遲")
                else:
                    other_name = bindings.get(item, {}).get("description", item)
                    messages.append(f"手勢或熱鍵已與「{other_name}」衝突")
            summaries[act_id] = "；".join(messages)
        return summaries


class InputDispatcher(QObject):
    """統一輸入事件調度器。
    
    支援：
    1. 註冊與調度自訂動作回呼。
    2. 滑鼠單擊防抖延遲（當單雙擊共存時）。
    3. 撫摸手勢積分與移動拖曳事件分發。
    4. 全域熱鍵管理。
    """
    action_triggered = Signal(str)

    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self._action_callbacks: dict[str, Callable[[], None]] = {}
        self._debounce_timers: dict[str, QTimer] = {}
        self._registered_hotkeys: dict[int, str] = {}
        self._next_hotkey_id = 1000

        # 防抖定時器
        self._pending_click_action: str | None = None
        self._click_timer = QTimer(self)
        self._click_timer.setSingleShot(True)
        self._click_timer.setInterval(220)
        self._click_timer.timeout.connect(self._on_click_timer_timeout)

    def get_bindings(self) -> dict[str, dict[str, Any]]:
        return self.cfg.get("input_bindings") or dict(DEFAULT_BINDINGS_INFO)

    def register_action(self, act_id: str, callback: Callable[[], None]):
        """註冊動作回呼。"""
        self._action_callbacks[act_id] = callback

    def unregister_action(self, act_id: str):
        self._action_callbacks.pop(act_id, None)

    def dispatch(self, act_id: str) -> bool:
        """分發執行指定動作。"""
        bindings = self.get_bindings()
        binding = bindings.get(act_id)
        if binding and not binding.get("enabled", True):
            return False

        self.action_triggered.emit(act_id)
        cb = self._action_callbacks.get(act_id)
        if cb:
            try:
                cb()
                return True
            except Exception as exc:
                from .config import log
                log("InputDispatcher", f"執行動作「{act_id}」失敗: {exc}")
        return False

    def find_action_by_trigger(self, trigger_name: str) -> str | None:
        """尋找綁定至指定手勢觸發源的啟用動作。"""
        bindings = self.get_bindings()
        for act_id, item in bindings.items():
            if item.get("enabled", True) and item.get("trigger") == trigger_name:
                return act_id
        return None

    def find_action_by_hotkey(self, hotkey_str: str) -> str | None:
        """尋找綁定至指定熱鍵的啟用動作。"""
        target = normalize_hotkey(hotkey_str)
        if not target:
            return None
        bindings = self.get_bindings()
        for act_id, item in bindings.items():
            if item.get("enabled", True):
                hk = normalize_hotkey(item.get("hotkey", ""))
                if hk == target:
                    return act_id
        return None

    # ------------------------------------------------------------- 滑鼠手勢分發
    def handle_head_single_click(self, needs_debounce: bool = False):
        """處理頭部單擊手勢。若存在雙擊綁定則啟動防抖定時器。"""
        act_id = self.find_action_by_trigger("head_single_click")
        if not act_id:
            return
        if needs_debounce:
            self._pending_click_action = act_id
            self._click_timer.start()
        else:
            self.dispatch(act_id)

    def handle_head_double_click(self):
        """處理頭部雙擊手勢，立即中斷單擊防抖。"""
        if self._click_timer.isActive():
            self._click_timer.stop()
            self._pending_click_action = None
        act_id = self.find_action_by_trigger("head_double_click")
        if act_id:
            self.dispatch(act_id)

    def handle_tablet_double_click(self):
        """處理平板雙擊手勢。"""
        act_id = self.find_action_by_trigger("tablet_double_click")
        if act_id:
            self.dispatch(act_id)

    def handle_body_right_click(self):
        """處理身體右鍵點擊手勢。"""
        act_id = self.find_action_by_trigger("body_right_click")
        if act_id:
            self.dispatch(act_id)

    def handle_feed_pet_trigger(self):
        """處理快捷餵食手勢。"""
        act_id = self.find_action_by_trigger("drop_rice")
        if act_id:
            self.dispatch(act_id)

    def _on_click_timer_timeout(self):
        """單擊防抖定時器超時確認執行單擊。"""
        if self._pending_click_action:
            act = self._pending_click_action
            self._pending_click_action = None
            self.dispatch(act)

    # ------------------------------------------------------------- 全域熱鍵管理
    def update_hotkeys(self):
        """重新註冊所有啟用的全域熱鍵。"""
        self.unregister_all_hotkeys()
        bindings = self.get_bindings()
        for act_id, item in bindings.items():
            if not item.get("enabled", True):
                continue
            hk = (item.get("hotkey") or "").strip()
            if hk:
                self.register_global_hotkey(act_id, hk)

    def register_global_hotkey(self, act_id: str, hotkey_str: str) -> bool:
        """透過 Windows API RegisterHotKey 註冊全域廣播熱鍵。"""
        normalized = normalize_hotkey(hotkey_str)
        if not normalized or normalized in WINDOWS_RESERVED_HOTKEYS:
            return False

        fs_modifiers = 0
        vk_code = 0
        parts = normalized.split("+")
        for p in parts:
            if p in ("CTRL", "CONTROL"):
                fs_modifiers |= MOD_CONTROL
            elif p == "ALT":
                fs_modifiers |= MOD_ALT
            elif p == "SHIFT":
                fs_modifiers |= MOD_SHIFT
            elif p in ("WIN", "META"):
                fs_modifiers |= MOD_WIN
            elif len(p) == 1:
                vk_code = ord(p.upper())
            elif p.startswith("F") and p[1:].isdigit():
                f_num = int(p[1:])
                if 1 <= f_num <= 24:
                    vk_code = 0x70 + (f_num - 1)  # VK_F1..VK_F24

        if not vk_code:
            return False

        try:
            hk_id = self._next_hotkey_id
            self._next_hotkey_id += 1
            # 支援 MOD_NOREPEAT 防止連按重複震盪
            res = ctypes.windll.user32.RegisterHotKey(
                None, hk_id, fs_modifiers | MOD_NOREPEAT, vk_code
            )
            if res:
                self._registered_hotkeys[hk_id] = act_id
                return True
        except Exception:
            pass
        return False

    def unregister_all_hotkeys(self):
        """註銷所有已註冊之全域熱鍵。"""
        for hk_id in list(self._registered_hotkeys.keys()):
            try:
                ctypes.windll.user32.UnregisterHotKey(None, hk_id)
            except Exception:
                pass
        self._registered_hotkeys.clear()

    def process_hotkey_message(self, hotkey_id: int) -> bool:
        """接收 WM_HOTKEY 訊息並調度相應動作。"""
        act_id = self._registered_hotkeys.get(hotkey_id)
        if act_id:
            return self.dispatch(act_id)
        return False
