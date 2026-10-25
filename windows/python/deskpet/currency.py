"""幣值選擇與多來源匯率換算系統 (Currency Converter & Multi-Source Exchange Rate Engine)。
支援免 Key 免費開源 API、需 Key 商用/進階 API、自訂端點、離線快取與雙幣顯示。
嚴格遵守：純文字繁體中文排版，嚴禁使用任何 Emoji。
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import log

# 支援目標顯示幣別定義
SUPPORTED_TARGET_CURRENCIES = {
    "TWD": {"name": "新台幣", "symbol": "NT$", "unit": "元"},
    "USD": {"name": "美元", "symbol": "$", "unit": "元"},
    "CNY": {"name": "人民幣", "symbol": "¥", "unit": "元"},
    "EUR": {"name": "歐元", "symbol": "€", "unit": "元"},
    "JPY": {"name": "日圓", "symbol": "¥", "unit": "円"},
    "HKD": {"name": "港幣", "symbol": "HK$", "unit": "元"},
    "GBP": {"name": "英鎊", "symbol": "£", "unit": "鎊"},
}

# 匯率資料來源定義
CURRENCY_SOURCES = {
    # A. 免 Key 免費開源匯率 API
    "exchangerate_api": {
        "name": "ExchangeRate-API (開放節點)",
        "requires_key": False,
        "url": "https://open.er-api.com/v6/latest/USD",
        "description": "免費開放存取，支援全球超過 160 種法定貨幣，包含新台幣 TWD。",
    },
    "frankfurter": {
        "name": "Frankfurter API (歐洲央行節點)",
        "requires_key": False,
        "url": "https://api.frankfurter.app/latest?from=USD",
        "description": "開源免費，即時追蹤歐洲央行官方參考匯率。",
    },
    "fawazahmed0": {
        "name": "Fawazahmed0 匯率開放節點",
        "requires_key": False,
        "url": "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/usd.json",
        "description": "開源 CDN 分散式即時匯率節點，無連線次數限制。",
    },
    # B. 需 Key 之進階開源/商用匯率 API
    "openexchangerates": {
        "name": "Open Exchange Rates",
        "requires_key": True,
        "key_param": "app_id",
        "url_template": "https://openexchangerates.org/api/latest.json?app_id={key}",
        "description": "商用級即時匯率 API，提供高頻率即時更新，需填寫有效 App ID。",
    },
    "currencyfreaks": {
        "name": "CurrencyFreaks",
        "requires_key": True,
        "key_param": "apikey",
        "url_template": "https://api.currencyfreaks.com/v2.0/rates/latest?apikey={key}&symbols=TWD,USD,CNY,EUR,JPY,HKD,GBP",
        "description": "專業外匯數據提供商，需填寫 API Key。",
    },
    "exchangeratesapi": {
        "name": "ExchangeRatesAPI.io",
        "requires_key": True,
        "key_param": "access_key",
        "url_template": "https://api.exchangeratesapi.io/v1/latest?access_key={key}&symbols=USD,TWD,CNY,EUR,JPY,HKD,GBP",
        "description": "國際標準匯率服務，需填寫 Access Key。",
    },
    "custom": {
        "name": "自訂匯率 API 端點",
        "requires_key": True,
        "key_param": "url",
        "url_template": "{endpoint}",
        "description": "自訂本機或第三方匯率服務端點 URL（支援 JSON rates 物件）。",
    },
}

KEY_REQUIRED_SOURCES = {"openexchangerates", "currencyfreaks", "exchangeratesapi", "custom"}

# 基準基準匯率（以 1 USD 為基準單位，用於離線預設防護，絕不崩潰）
BASELINE_RATES_USD: dict[str, float] = {
    "USD": 1.0,
    "TWD": 32.50,
    "CNY": 7.23,
    "EUR": 0.92,
    "JPY": 152.50,
    "HKD": 7.78,
    "GBP": 0.79,
}


class CurrencyConverter:
    """多來源匯率換算器與本機快取控制器。"""

    def __init__(self, cfg=None):
        self.cfg = cfg
        self._lock = threading.Lock()
        self._rates: dict[str, float] = dict(BASELINE_RATES_USD)
        self._last_updated: str = ""
        self._current_source: str = "exchangerate_api"
        self._display_mode: str = "dual"  # dual, converted, original
        self._target_currency: str = "TWD"

        self._load_from_config()

    def _load_from_config(self):
        """從設定中讀取快取匯率與使用者偏好。"""
        if not self.cfg:
            return

        self._target_currency = str(self.cfg.get("currency_target", "TWD")).upper()
        if self._target_currency not in SUPPORTED_TARGET_CURRENCIES:
            self._target_currency = "TWD"

        self._current_source = str(self.cfg.get("currency_source", "exchangerate_api"))
        if self._current_source not in CURRENCY_SOURCES:
            self._current_source = "exchangerate_api"

        self._display_mode = str(self.cfg.get("currency_display_mode", "dual"))
        if self._display_mode not in ("dual", "converted", "original"):
            self._display_mode = "dual"

        cache = self.cfg.get("currency_cache") or {}
        if isinstance(cache, dict) and "rates" in cache and isinstance(cache["rates"], dict):
            for k, v in cache["rates"].items():
                try:
                    self._rates[str(k).upper()] = float(v)
                except Exception:
                    pass
            self._last_updated = str(cache.get("last_updated", ""))

    @property
    def target_currency(self) -> str:
        return self._target_currency

    @property
    def current_source(self) -> str:
        return self._current_source

    @property
    def display_mode(self) -> str:
        return self._display_mode

    @property
    def last_updated(self) -> str:
        return self._last_updated or "尚未更新（使用內建基準匯率）"

    @property
    def rates(self) -> dict[str, float]:
        with self._lock:
            return dict(self._rates)

    def get_source_api_key(self, source: str) -> str:
        """取得指定需 Key 來源的 API Key 或自訂端點。"""
        if not self.cfg:
            return ""
        keys = self.cfg.get("currency_api_keys") or {}
        if source == "custom":
            return str(self.cfg.get("currency_custom_endpoint", "")).strip() or str(keys.get("custom", "")).strip()
        return str(keys.get(source, "")).strip()

    def set_source_api_key(self, source: str, key: str, save: bool = True):
        """設定指定需 Key 來源的 API Key。"""
        if not self.cfg:
            return
        keys = dict(self.cfg.get("currency_api_keys") or {})
        keys[source] = key.strip()
        self.cfg.set("currency_api_keys", keys, save=save)
        if source == "custom":
            self.cfg.set("currency_custom_endpoint", key.strip(), save=save)

    def set_target_currency(self, target: str, save: bool = True):
        """切換目標顯示幣別（TWD, USD, CNY, EUR, JPY, HKD, GBP）。"""
        t = (target or "TWD").upper().strip()
        if t not in SUPPORTED_TARGET_CURRENCIES:
            raise ValueError(f"不支援的幣別：{t}，支援清單：{list(SUPPORTED_TARGET_CURRENCIES.keys())}")
        self._target_currency = t
        if self.cfg and save:
            self.cfg.set("currency_target", t, save=True)
        log(f"[Currency] 目標顯示幣別已切換為：{t} ({SUPPORTED_TARGET_CURRENCIES[t]['name']})")

    def set_display_mode(self, mode: str, save: bool = True):
        """切換顯示模式：dual（原幣別 (約 換算幣別)）、converted（純換算後幣別）、original（純原幣別）。"""
        m = (mode or "dual").lower().strip()
        if m not in ("dual", "converted", "original"):
            raise ValueError(f"不支援的顯示模式：{m}")
        self._display_mode = m
        if self.cfg and save:
            self.cfg.set("currency_display_mode", m, save=True)
        log(f"[Currency] 貨幣顯示模式已切換為：{m}")

    def set_source(self, source: str, save: bool = True) -> tuple[bool, str]:
        """切換匯率資料來源。若為需 Key 之來源且未填寫 Key，禁止切換並回傳錯誤訊息。"""
        src = (source or "exchangerate_api").lower().strip()
        if src not in CURRENCY_SOURCES:
            return False, f"未知的匯率資料來源：{src}"

        if src in KEY_REQUIRED_SOURCES:
            key = self.get_source_api_key(src)
            if not key:
                err_msg = f"資料來源「{CURRENCY_SOURCES[src]['name']}」需填寫有效 Key 方可啟用！"
                log(f"[Currency] 切換失敗：{err_msg}")
                return False, err_msg

        self._current_source = src
        if self.cfg and save:
            self.cfg.set("currency_source", src, save=True)
        log(f"[Currency] 匯率資料來源已切換為：{CURRENCY_SOURCES[src]['name']}")
        return True, ""

    def convert(self, amount: float, from_curr: str, to_curr: str) -> float:
        """跨幣別精準匯率換算。以 USD 為內部基準。"""
        f = (from_curr or "USD").upper().strip()
        t = (to_curr or self._target_currency).upper().strip()

        if f == t:
            return float(amount)

        with self._lock:
            rates = dict(self._rates)

        rate_f = rates.get(f) or BASELINE_RATES_USD.get(f, 1.0)
        rate_t = rates.get(t) or BASELINE_RATES_USD.get(t, 1.0)

        # 先換算為基準 USD，再換算為目標貨幣
        usd_amount = float(amount) / rate_f
        converted = usd_amount * rate_t
        return converted

    def format_balance(
        self,
        amount: float | None,
        from_curr: str = "USD",
        to_curr: str | None = None,
        display_mode: str | None = None,
    ) -> str:
        """根據顯示模式格式化餘額字串。支援雙幣顯示、純換算後幣別與純原幣別。"""
        if amount is None:
            return "--"

        f = (from_curr or "USD").upper().strip()
        if f == "FREE":
            return "FREE"

        t = (to_curr or self._target_currency).upper().strip()
        mode = display_mode or self._display_mode

        sym_f = SUPPORTED_CURRENCIES_SYMBOL(f)
        sym_t = SUPPORTED_CURRENCIES_SYMBOL(t)

        orig_str = f"{sym_f}{amount:.2f}"
        if f == t:
            return orig_str

        conv_val = self.convert(amount, f, t)
        conv_str = f"{sym_t}{conv_val:.2f}"

        if mode == "converted":
            return conv_str
        elif mode == "original":
            return orig_str
        else:  # "dual"
            return f"{orig_str} (約 {conv_str})"

    def refresh_rates(self, source: str | None = None) -> bool:
        """向網路 API 請求最新即時匯率並寫入本機快取。若離線或失敗，自動使用最後已知快取。"""
        src = source or self._current_source
        if src not in CURRENCY_SOURCES:
            src = "exchangerate_api"

        spec = CURRENCY_SOURCES[src]
        url = ""

        try:
            if spec.get("requires_key"):
                key = self.get_source_api_key(src)
                if not key:
                    log(f"[Currency] 更新失敗：來源 {src} 未設定 API Key")
                    return False
                if src == "custom":
                    url = key
                else:
                    url = spec["url_template"].format(key=urllib.parse.quote(key))
            else:
                url = spec["url"]

            req = urllib.request.Request(
                url,
                headers={"User-Agent": "DeskPet/2.1 CurrencyClient"},
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            rates_map: dict[str, float] = {}

            # 解析不同來源的 JSON 結構
            if src == "exchangerate_api":
                raw_rates = data.get("rates") or {}
                for k, v in raw_rates.items():
                    try:
                        rates_map[str(k).upper()] = float(v)
                    except Exception:
                        pass

            elif src == "frankfurter":
                raw_rates = data.get("rates") or {}
                rates_map["USD"] = 1.0
                for k, v in raw_rates.items():
                    try:
                        rates_map[str(k).upper()] = float(v)
                    except Exception:
                        pass
                # Frankfurter 缺乏 TWD 時，自動融合既有/基準 TWD 匯率防護
                if "TWD" not in rates_map:
                    rates_map["TWD"] = self._rates.get("TWD", BASELINE_RATES_USD["TWD"])

            elif src == "fawazahmed0":
                usd_data = data.get("usd") or {}
                rates_map["USD"] = 1.0
                for k, v in usd_data.items():
                    try:
                        rates_map[str(k).upper()] = float(v)
                    except Exception:
                        pass

            elif src in ("openexchangerates", "currencyfreaks", "exchangeratesapi", "custom"):
                raw_rates = data.get("rates") or data
                base = str(data.get("base", "USD")).upper()
                for k, v in raw_rates.items():
                    try:
                        rates_map[str(k).upper()] = float(v)
                    except Exception:
                        pass
                # 若 base 非 USD，轉換為 USD 基準
                if base != "USD" and base in rates_map and rates_map[base] > 0:
                    base_usd_factor = 1.0 / rates_map[base]
                    rates_map = {k: v * base_usd_factor for k, v in rates_map.items()}
                rates_map["USD"] = 1.0

            if not rates_map:
                raise ValueError("未解析到任何匯率資料")

            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with self._lock:
                for k, v in rates_map.items():
                    if k in SUPPORTED_TARGET_CURRENCIES or k == "USD":
                        self._rates[k] = float(v)
                self._last_updated = now_str

            # 寫入本機快取
            if self.cfg:
                self.cfg.set(
                    "currency_cache",
                    {
                        "rates": self._rates,
                        "last_updated": now_str,
                        "source": src,
                    },
                    save=True,
                )

            log(f"[Currency] 匯率資料已從【{spec['name']}】成功更新！(時間: {now_str})")
            return True

        except Exception as e:
            log(f"[Currency] 匯率網路更新失敗 ({src})，自動使用本機快取匯率：{e}")
            # 離線保險：絕不崩潰
            return False

    def get_rates_snippet(self) -> str:
        """取得當前匯率摘要簡報（例如 1 USD = 32.50 TWD = 7.23 CNY）。"""
        with self._lock:
            twd = self._rates.get("TWD", BASELINE_RATES_USD["TWD"])
            cny = self._rates.get("CNY", BASELINE_RATES_USD["CNY"])
            eur = self._rates.get("EUR", BASELINE_RATES_USD["EUR"])
            jpy = self._rates.get("JPY", BASELINE_RATES_USD["JPY"])
        return f"1 USD = {twd:.2f} TWD = {cny:.2f} CNY = {eur:.2f} EUR = {jpy:.1f} JPY"


def SUPPORTED_CURRENCIES_SYMBOL(code: str) -> str:
    """取得幣別符號助手函式。"""
    c = (code or "").upper().strip()
    if c in SUPPORTED_TARGET_CURRENCIES:
        return SUPPORTED_TARGET_CURRENCIES[c]["symbol"]
    if c == "FREE":
        return ""
    return "$"


_global_converter: CurrencyConverter | None = None
_global_lock = threading.Lock()


def get_currency_converter(cfg=None) -> CurrencyConverter:
    """取得或初始化全域 CurrencyConverter 單例。"""
    global _global_converter
    with _global_lock:
        if _global_converter is None:
            _global_converter = CurrencyConverter(cfg)
        elif cfg and _global_converter.cfg is None:
            _global_converter.cfg = cfg
            _global_converter._load_from_config()
        return _global_converter
