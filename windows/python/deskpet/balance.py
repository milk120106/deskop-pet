"""Multi-provider & simulation balance bookkeeping with today's usage and event logging."""
from __future__ import annotations

import json
import random
import re
import threading
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from PySide6.QtCore import QObject, QTimer, Signal

from .config import find_api_key, log

STEP = 0.01
MAX_CUES_PER_POLL = 40


def _is_auth_or_quota_err(exc: Exception) -> bool:
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code in (401, 403, 429)
    msg = str(exc).lower()
    return any(p in msg for p in ("401", "403", "429", "unauthorized", "quota", "rate limit", "authentication"))


class Ledger(QObject):
    changed = Signal()                 # shown value or connection state changed
    cues = Signal(int)                 # N x 0.01 deductions to animate
    topup = Signal(float)              # recharge of X yuan/dollars -> drop rice bowl
    _fetched = Signal(object, str)     # (balance|None, error) from worker thread

    def __init__(self, cfg, provider_override: str | None = None):
        super().__init__()
        self.cfg = cfg
        self._provider_override = provider_override
        self.real: float | None = None
        self.shown: float | None = None
        self.online = False
        self.error = ""
        self._busy = False
        self.events: list[tuple[str, float, float]] = []  # [(HH:mm:ss, delta, balance)]

        self._fetched.connect(self._on_fetched)

        self.poll = QTimer(self)
        self.poll.timeout.connect(self.refresh)

        self.sim = QTimer(self)
        self.sim.timeout.connect(self._sim_event)

        self.apply_mode()

    @property
    def mode(self) -> str:
        return self.cfg.get("mode", "sim")

    @property
    def provider(self) -> str:
        if self._provider_override:
            return self._provider_override
        return self.cfg.get("provider", "deepseek")

    @property
    def currency(self) -> str:
        if self.mode == "sim":
            return "CNY"
        return "CNY" if self.provider == "deepseek" else "USD"

    @property
    def text(self) -> str:
        if self.shown is None:
            return "--"
        prefix = "" if self.currency == "CNY" else "$"
        return f"{prefix}{self.shown:.2f}"

    def note_event(self, delta: float, new_bal: float):
        ts = datetime.now().strftime("%m-%d %H:%M:%S")
        self.events.append((ts, round(delta, 2), round(new_bal, 2)))
        if len(self.events) > 300:
            self.events.pop(0)

    # ---------------------------------------------------------------- mode
    def apply_mode(self):
        self.poll.stop()
        self.sim.stop()
        self.real = self.shown = None
        self.online = False
        self.error = ""

        if self.mode == "sim":
            bal = float(self.cfg.get("sim_balance", 50.0))
            self.real = self.shown = round(bal, 2)
            self.online = True
            if self.cfg.get("sim_auto", True):
                self.sim.start(max(3, int(self.cfg.get("sim_interval", 30))) * 1000)
        else:
            # API mode
            interval = max(1000, int(self.cfg.get("poll_ms", 2000)))
            if self.provider in ("openai", "anthropic"):
                interval = max(30000, interval)  # cost report polling every 30-60s
            self.poll.start(interval)
            self.refresh()

        self.changed.emit()

    # ---------------------------------------------------------------- sim
    def _sim_event(self):
        if self.mode != "sim":
            return
        if random.random() < 0.75:
            self.sim_charge(random.choice([1, 2, 5, 10]))
        else:
            self.sim_topup(random.choice([1.0, 2.0, 3.0, 5.0]))

    def sim_charge(self, n: int):
        """Simulate deduction of n cents."""
        n = max(1, min(MAX_CUES_PER_POLL, int(n)))
        delta = round(n * STEP, 2)
        if self.real is not None:
            self.real = round(self.real - delta, 2)
            if self.mode == "sim":
                self.cfg.set("sim_balance", self.real, save=True)
        self.cues.emit(n)

    def sim_topup(self, amount: float):
        """Simulate recharge: drops rice bowl."""
        amount = round(float(amount), 2)
        self.topup.emit(amount)

    # ---------------------------------------------------------------- api
    def refresh(self):
        if self.mode != "api" or self._busy:
            return
        prov = self.provider
        key = find_api_key(self.cfg, prov)
        if not key:
            self.online, self.error = False, f"未設定 {prov} API Key"
            self.changed.emit()
            return

        self._busy = True
        threading.Thread(target=self._worker, args=(prov, key), daemon=True).start()

    def _worker(self, prov: str, key: str):
        keys = self.cfg.get_api_keys(prov) if hasattr(self.cfg, "get_api_keys") else []
        if not keys:
            keys = [key] if key else []
        if not keys:
            self._fetched.emit(None, f"未設定 {prov} API Key")
            return

        cur_key = self.cfg.get_current_api_key(prov) if hasattr(self.cfg, "get_current_api_key") else keys[0]
        if cur_key and cur_key in keys:
            start_idx = keys.index(cur_key)
            ordered_keys = keys[start_idx:] + keys[:start_idx]
        else:
            ordered_keys = list(keys)

        last_err = ""
        for i, k in enumerate(ordered_keys):
            try:
                if prov == "deepseek":
                    bal = self._query_deepseek(k)
                elif prov == "openai":
                    bal = self._query_openai(k)
                elif prov == "anthropic":
                    bal = self._query_anthropic(k)
                elif prov == "gemini":
                    bal = self._query_gemini(k)
                else:
                    raise ValueError(f"Unknown provider {prov}")
                self._fetched.emit(bal, "")
                return
            except Exception as e:
                last_err = f"{type(e).__name__}: {e}"
                if _is_auth_or_quota_err(e) and i < len(ordered_keys) - 1:
                    if hasattr(self.cfg, "rotate_api_key"):
                        self.cfg.rotate_api_key(prov)
                    log(f"[{prov}] 餘額查詢遭遇授權或額度錯誤，自動輪替至下一組金鑰重試")
                    continue
                break

        self._fetched.emit(None, last_err)

    def _query_gemini(self, key: str) -> float:
        # Validate Gemini key with models endpoint and calculate remaining budget
        budgets = self.cfg.get("budgets") or {}
        budget = float(budgets.get("gemini", 100.0))
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}&pageSize=1"
        req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "DesktopPet/2.0"})
        with urllib.request.urlopen(req, timeout=12) as r:
            json.loads(r.read().decode("utf-8"))
        today_used = float(self.cfg.get("today_used", 0.0))
        return max(0.0, budget - today_used)

    def _query_deepseek(self, key: str) -> float:
        req = urllib.request.Request(
            "https://api.deepseek.com/user/balance",
            headers={"Authorization": f"Bearer {key}", "Accept": "application/json",
                     "User-Agent": "DesktopPet/1.0"}
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode("utf-8"))
        infos = data.get("balance_infos") or []
        pick = next((i for i in infos if i.get("currency") == "CNY"), infos[0] if infos else None)
        if not pick:
            raise ValueError("無餘額資料 (balance_infos)")
        return float(pick["total_balance"])

    def _query_openai(self, key: str) -> float:
        # Starting budget minus cost report since date
        budgets = self.cfg.get("budgets") or {}
        sinces = self.cfg.get("sinces") or {}
        budget = float(budgets.get("openai", 100.0))
        since_str = sinces.get("openai") or datetime.now().strftime("%Y-%m-01")

        since_dt = datetime.strptime(since_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        st = int(since_dt.timestamp())

        sum_spend = 0.0
        page = None
        for _ in range(30):
            url = f"https://api.openai.com/v1/organization/costs?start_time={st}&bucket_width=1d&limit=180"
            if page:
                url += f"&page={urllib.parse.quote(page)}"
            req = urllib.request.Request(url, headers={"Authorization": f"Bearer {key}", "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=12) as r:
                body = r.read().decode("utf-8")
            for m in re.finditer(r'"amount"\s*:\s*\{\s*"value"\s*:\s*(-?[0-9.eE+-]+)', body):
                sum_spend += float(m.group(1))
            m_page = re.search(r'"next_page"\s*:\s*"([^"]+)"', body)
            page = m_page.group(1) if m_page else None
            if not page:
                break
        return max(0.0, budget - sum_spend)

    def _query_anthropic(self, key: str) -> float:
        budgets = self.cfg.get("budgets") or {}
        sinces = self.cfg.get("sinces") or {}
        budget = float(budgets.get("anthropic", 100.0))
        since_str = sinces.get("anthropic") or datetime.now().strftime("%Y-%m-01")

        from_iso = f"{since_str}T00:00:00Z"
        sum_spend = 0.0
        page = None
        for _ in range(30):
            url = f"https://api.anthropic.com/v1/organizations/cost_report?starting_at={urllib.parse.quote(from_iso)}&bucket_width=1d&limit=31"
            if page:
                url += f"&page={urllib.parse.quote(page)}"
            req = urllib.request.Request(
                url,
                headers={"x-api-key": key, "anthropic-version": "2023-06-01", "Accept": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=12) as r:
                body = r.read().decode("utf-8")
            for m in re.finditer(r'"amount"\s*:\s*"?(-?[0-9.eE+-]+)"?', body):
                sum_spend += float(m.group(1)) * 0.01  # cents to dollars
            m_page = re.search(r'"next_page"\s*:\s*"([^"]+)"', body)
            page = m_page.group(1) if m_page else None
            if not page:
                break
        return max(0.0, budget - sum_spend)

    def _on_fetched(self, value: float | None, err: str):
        self._busy = False
        if self.mode != "api":
            return
        if value is None:
            self.online, self.error = False, err
            log(f"balance fetch failed ({self.provider}): {err}")
            self.changed.emit()
            return

        self.online, self.error = True, ""
        val = round(value, 2)
        if self.real is None:
            self.real = self.shown = val
        else:
            delta = round(val - self.real, 2)
            self.real = val
            if delta <= -STEP / 2:
                cues_count = min(MAX_CUES_PER_POLL, int(round(-delta / STEP)))
                self.cues.emit(cues_count)
            elif delta >= STEP / 2:
                self.topup.emit(delta)

        self.changed.emit()

    # ---------------------------------------------------------------- shown bookkeeping
    def apply_cue(self, count: int = 1):
        """Called by the pet each time a deduction animation fires."""
        delta = round(max(1, int(count)) * STEP, 2)
        if self.shown is not None:
            self.shown = round(self.shown - delta, 2)
            used = self.cfg.get("today_used", 0.0) + delta
            self.cfg.set("today_used", round(used, 2), save=False)
            self.note_event(-delta, self.shown)
            self.changed.emit()

    def apply_credit(self, amount: float):
        """Called when a rice bowl is fed to the pet."""
        if self.shown is not None:
            self.shown = round(self.shown + amount, 2)
            topup = self.cfg.get("today_topup", 0.0) + amount
            self.cfg.set("today_topup", round(topup, 2), save=False)
            if self.mode == "sim":
                self.real = self.shown
                self.cfg.set("sim_balance", self.real, save=True)
            self.note_event(amount, self.shown)
            self.changed.emit()
