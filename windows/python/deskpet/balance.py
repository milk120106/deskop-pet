"""Multi-provider & simulation balance bookkeeping with today's usage and event logging."""
from __future__ import annotations

import json
import random
import re
import threading
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from PySide6.QtCore import QObject, QTimer, Signal

from .config import find_api_key, id_to_provider_name, log, provider_to_id

STEP = 0.01
MAX_CUES_PER_POLL = 40

SUPPORTED_BALANCE_PROVIDERS = [
    "deepseek",
    "openai",
    "anthropic",
    "gemini",
    "openrouter",
    "siliconflow",
    "moonshot",
    "custom_openai",
    "groq",
    "mistral",
    "grok",
    "together",
    "cerebras",
    "deepinfra",
    "fireworks",
    "glm",
    "ollama",
    "lmstudio",
    "vllm",
]


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
    def provider_id(self) -> str:
        return provider_to_id(self.provider)

    @property
    def provider_display_name(self) -> str:
        return id_to_provider_name(self.provider)

    def set_provider(self, prov: str):
        """切換餘額監視的供應商。"""
        pid = provider_to_id(prov)
        self._provider_override = pid
        self.cfg.set("provider", pid, save=True)
        self.apply_mode()

    @property
    def currency(self) -> str:
        pid = self.provider_id
        if pid in ("deepseek", "siliconflow", "moonshot", "glm"):
            return "CNY"
        if pid in ("ollama", "lmstudio", "vllm"):
            return "FREE"
        return "USD"

    @property
    def currency_symbol(self) -> str:
        c = self.currency
        if c == "CNY":
            return "¥"
        elif c == "USD":
            return "$"
        return ""

    @property
    def text(self) -> str:
        if self.shown is None:
            return "--"
        if self.currency == "FREE":
            return "FREE"
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
            pid = self.provider_id
            if pid in ("openai", "anthropic", "gemini", "groq", "mistral", "grok", "together"):
                interval = max(30000, interval)  # cost report / budget polling every 30-60s
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
        pid = self.provider_id
        if pid in ("ollama", "lmstudio", "vllm"):
            self._busy = True
            threading.Thread(target=self._worker, args=(prov, ""), daemon=True).start()
            return

        key = find_api_key(self.cfg, prov)
        if not key:
            self.online, self.error = False, f"未設定 {self.provider_display_name} API Key"
            self.changed.emit()
            return

        self._busy = True
        threading.Thread(target=self._worker, args=(prov, key), daemon=True).start()

    def _get_budget(self, prov_id: str, default: float = 100.0) -> float:
        budgets = self.cfg.get("budgets") or {}
        if prov_id in budgets:
            return float(budgets[prov_id])
        pname = id_to_provider_name(prov_id)
        if pname in budgets:
            return float(budgets[pname])
        return default

    def _get_provider_endpoint(self, prov_id: str) -> str:
        eps = self.cfg.get("api_endpoints") or {}
        if prov_id in eps and eps[prov_id]:
            return str(eps[prov_id])
        pname = id_to_provider_name(prov_id)
        if pname in eps and eps[pname]:
            return str(eps[pname])
        for p in self.cfg.get("api_profiles", []):
            if p.get("provider", "").lower() in (prov_id.lower(), pname.lower()):
                ep = str(p.get("endpoint", "")).strip()
                if ep:
                    return ep
        from .model_catalog import OPENAI_BASES
        return str(OPENAI_BASES.get(pname, OPENAI_BASES.get(prov_id, "")))

    def _worker(self, prov: str, key: str):
        pid = provider_to_id(prov)
        if pid in ("ollama", "lmstudio", "vllm"):
            try:
                bal = self._query_local_offline(pid)
                self._fetched.emit(bal, "")
                return
            except Exception as e:
                self._fetched.emit(None, f"本地服務連線失敗: {e}")
                return

        keys = self.cfg.get_api_keys(prov) if hasattr(self.cfg, "get_api_keys") else []
        if not keys:
            keys = [key] if key else []
        if not keys:
            self._fetched.emit(None, f"未設定 {self.provider_display_name} API Key")
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
                if pid == "deepseek":
                    bal = self._query_deepseek(k)
                elif pid == "openai":
                    bal = self._query_openai(k)
                elif pid == "anthropic":
                    bal = self._query_anthropic(k)
                elif pid == "gemini":
                    bal = self._query_gemini(k)
                elif pid == "openrouter":
                    bal = self._query_openrouter(k)
                elif pid == "siliconflow":
                    bal = self._query_siliconflow(k)
                elif pid == "moonshot":
                    bal = self._query_moonshot(k)
                elif pid in ("custom_openai", "oneapi", "newapi"):
                    bal = self._query_custom_openai(k)
                elif pid == "groq":
                    bal = self._query_groq(k)
                elif pid == "mistral":
                    bal = self._query_mistral(k)
                elif pid == "grok":
                    bal = self._query_grok(k)
                elif pid == "together":
                    bal = self._query_together(k)
                elif pid == "cerebras":
                    bal = self._query_cerebras(k)
                elif pid == "deepinfra":
                    bal = self._query_deepinfra(k)
                elif pid == "fireworks":
                    bal = self._query_fireworks(k)
                elif pid == "glm":
                    bal = self._query_glm(k)
                else:
                    bal = self._query_custom_openai(k)
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
        budget = self._get_budget("gemini", default=100.0)
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
        budget = self._get_budget("openai", default=100.0)
        sinces = self.cfg.get("sinces") or {}
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
        budget = self._get_budget("anthropic", default=100.0)
        sinces = self.cfg.get("sinces") or {}
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

    def _query_openrouter(self, key: str) -> float:
        headers = {"Authorization": f"Bearer {key}", "Accept": "application/json", "User-Agent": "DesktopPet/2.0"}
        # 1. 優先查詢官方 credits 端點
        try:
            req = urllib.request.Request("https://openrouter.ai/api/v1/credits", headers=headers)
            with urllib.request.urlopen(req, timeout=12) as r:
                data = json.loads(r.read().decode("utf-8"))
            c_data = data.get("data") or {}
            if "total_credits" in c_data and "total_usage" in c_data:
                total_c = float(c_data["total_credits"])
                total_u = float(c_data["total_usage"])
                return max(0.0, round(total_c - total_u, 2))
        except Exception:
            pass

        # 2. 查詢金鑰額度限制 (auth/key)
        req2 = urllib.request.Request("https://openrouter.ai/api/v1/auth/key", headers=headers)
        with urllib.request.urlopen(req2, timeout=12) as r2:
            data2 = json.loads(r2.read().decode("utf-8"))
        k_data = data2.get("data") or {}
        limit = k_data.get("limit")
        usage = float(k_data.get("usage", 0.0))
        if limit is not None:
            return max(0.0, round(float(limit) - usage, 2))
        budget = self._get_budget("openrouter", default=100.0)
        return max(0.0, round(budget - usage, 2))

    def _query_siliconflow(self, key: str) -> float:
        headers = {"Authorization": f"Bearer {key}", "Accept": "application/json", "User-Agent": "DesktopPet/2.0"}
        req = urllib.request.Request("https://api.siliconflow.cn/v1/user/info", headers=headers)
        with urllib.request.urlopen(req, timeout=12) as r:
            data = json.loads(r.read().decode("utf-8"))
        u_data = data.get("data") or {}
        raw_bal = u_data.get("totalBalance")
        if raw_bal is None:
            raw_bal = u_data.get("balance", 0.0)
        return round(float(raw_bal), 2)

    def _query_moonshot(self, key: str) -> float:
        headers = {"Authorization": f"Bearer {key}", "Accept": "application/json", "User-Agent": "DesktopPet/2.0"}
        req = urllib.request.Request("https://api.moonshot.cn/v1/users/me/balance", headers=headers)
        with urllib.request.urlopen(req, timeout=12) as r:
            data = json.loads(r.read().decode("utf-8"))
        b_data = data.get("data") or {}
        avail = b_data.get("available_balance")
        if avail is None:
            avail = float(b_data.get("cash_balance", 0.0)) + float(b_data.get("voucher_balance", 0.0))
        return round(float(avail), 2)

    def _query_custom_openai(self, key: str) -> float:
        ep = self._get_provider_endpoint("custom_openai") or "https://api.openai.com/v1"
        ep = ep.rstrip("/")
        base_url = ep[:-3] if ep.endswith("/v1") else ep
        v1_url = f"{base_url}/v1"
        headers = {"Authorization": f"Bearer {key}", "Accept": "application/json", "User-Agent": "DesktopPet/2.0"}

        # 1. 嘗試 OneAPI / NewAPI /api/user/self
        try:
            req = urllib.request.Request(f"{base_url}/api/user/self", headers=headers)
            with urllib.request.urlopen(req, timeout=6) as r:
                data = json.loads(r.read().decode("utf-8"))
                if data.get("success") and "data" in data:
                    quota = float(data["data"].get("quota", 0.0))
                    return round(quota / 500000.0, 2)
        except Exception:
            pass

        # 2. 嘗試 /v1/dashboard/billing/subscription
        try:
            req = urllib.request.Request(f"{v1_url}/dashboard/billing/subscription", headers=headers)
            with urllib.request.urlopen(req, timeout=6) as r:
                sub = json.loads(r.read().decode("utf-8"))
                hard_limit = float(sub.get("hard_limit_usd", 0.0))
                if hard_limit > 0:
                    if "total_usage" in sub:
                        return max(0.0, round(hard_limit - float(sub["total_usage"]), 2))
                    return round(hard_limit, 2)
        except Exception:
            pass

        # 3. 嘗試 /v1/dashboard/billing/credit_grants
        try:
            req = urllib.request.Request(f"{v1_url}/dashboard/billing/credit_grants", headers=headers)
            with urllib.request.urlopen(req, timeout=6) as r:
                cg = json.loads(r.read().decode("utf-8"))
                if "total_available" in cg:
                    return round(float(cg["total_available"]), 2)
        except Exception:
            pass

        # 4. 驗證連線與模型可用性
        req = urllib.request.Request(f"{v1_url}/models", headers=headers)
        with urllib.request.urlopen(req, timeout=10) as r:
            json.loads(r.read().decode("utf-8"))
        budget = self._get_budget("custom_openai", default=100.0)
        today_used = float(self.cfg.get("today_used", 0.0))
        return max(0.0, round(budget - today_used, 2))

    def _query_models_validation_with_budget(self, key: str, base_url: str, prov_id: str) -> float:
        url = f"{base_url.rstrip('/')}/models"
        headers = {"Authorization": f"Bearer {key}", "Accept": "application/json", "User-Agent": "DesktopPet/2.0"}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=12) as r:
            json.loads(r.read().decode("utf-8"))
        budget = self._get_budget(prov_id, default=100.0)
        today_used = float(self.cfg.get("today_used", 0.0))
        return max(0.0, round(budget - today_used, 2))

    def _query_groq(self, key: str) -> float:
        return self._query_models_validation_with_budget(key, "https://api.groq.com/openai/v1", "groq")

    def _query_mistral(self, key: str) -> float:
        return self._query_models_validation_with_budget(key, "https://api.mistral.ai/v1", "mistral")

    def _query_grok(self, key: str) -> float:
        return self._query_models_validation_with_budget(key, "https://api.x.ai/v1", "grok")

    def _query_together(self, key: str) -> float:
        return self._query_models_validation_with_budget(key, "https://api.together.xyz/v1", "together")

    def _query_cerebras(self, key: str) -> float:
        return self._query_models_validation_with_budget(key, "https://api.cerebras.ai/v1", "cerebras")

    def _query_deepinfra(self, key: str) -> float:
        return self._query_models_validation_with_budget(key, "https://api.deepinfra.com/v1/openai", "deepinfra")

    def _query_fireworks(self, key: str) -> float:
        return self._query_models_validation_with_budget(key, "https://api.fireworks.ai/inference/v1", "fireworks")

    def _query_glm(self, key: str) -> float:
        return self._query_models_validation_with_budget(key, "https://open.bigmodel.cn/api/paas/v4", "glm")

    def _query_local_offline(self, prov_id: str) -> float:
        port_map = {"ollama": 11434, "lmstudio": 1234, "vllm": 8000}
        port = port_map.get(prov_id, 11434)
        url = f"http://localhost:{port}/v1/models" if prov_id != "ollama" else "http://localhost:11434/api/tags"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=4) as r:
            json.loads(r.read().decode("utf-8"))
        return 999.00

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
