"""動態模型目錄查詢模組：支援多供應商專用 API、多金鑰自動重試與動態模型導向。
完全遵循繁體中文排版，嚴格禁止任何表情符號 (No Emojis)。
"""
from __future__ import annotations

import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class ModelCatalogError(RuntimeError):
    pass


OPENAI_BASES = {
    "OpenAI": "https://api.openai.com/v1",
    "DeepSeek": "https://api.deepseek.com",
    "Claude": "https://api.anthropic.com/v1",
    "Anthropic": "https://api.anthropic.com/v1",
    "Google Gemini": "https://generativelanguage.googleapis.com/v1beta",
    "xAI / Grok": "https://api.x.ai/v1",
    "Groq": "https://api.groq.com/openai/v1",
    "Mistral": "https://api.mistral.ai/v1",
    "Ollama": "http://localhost:11434/v1",
    "OpenRouter": "https://openrouter.ai/api/v1",
    "z.ai": "https://api.z.ai/api/paas/v4",
    "GLM": "https://open.bigmodel.cn/api/paas/v4",
    "Cerebras": "https://api.cerebras.ai/v1",
    "Together AI": "https://api.together.xyz/v1",
    "Fireworks AI": "https://api.fireworks.ai/inference/v1",
    "DeepInfra": "https://api.deepinfra.com/v1/openai",
    "矽基流動 (SiliconFlow)": "https://api.siliconflow.cn/v1",
    "SiliconFlow": "https://api.siliconflow.cn/v1",
    "月之暗面 (Moonshot/Kimi)": "https://api.moonshot.cn/v1",
    "Moonshot": "https://api.moonshot.cn/v1",
    "本地 LM Studio": "http://localhost:1234/v1",
    "LM Studio": "http://localhost:1234/v1",
    "本地 vLLM": "http://localhost:8000/v1",
    "vLLM": "http://localhost:8000/v1",
}

PROVIDERS = [
    "DeepSeek",
    "OpenAI",
    "Google Gemini",
    "Anthropic",
    "Mistral",
    "xAI / Grok",
    "z.ai",
    "GLM",
    "Cerebras",
    "Together AI",
    "Fireworks AI",
    "DeepInfra",
    "矽基流動 (SiliconFlow)",
    "月之暗面 (Moonshot/Kimi)",
    "本地 LM Studio",
    "本地 vLLM",
    "Ollama",
    "Ollama Cloud",
    "OpenRouter",
    "Cloudflare AI",
    "Groq",
    "Hugging Face",
    "OpenAI 相容自訂端點",
]

# 最新動態別名模型定義（不寫死版本快照，指向廠商最新動態別名）
DYNAMIC_MODEL_ALIASES: dict[str, list[dict]] = {
    "Google Gemini": [
        # Flash-Lite 模型（免費版可用，最新發布至 3.5，超低延遲、省 Token 首選）
        {"id": "gemini-flash-lite-latest", "label": "Gemini Flash-Lite (最新輕量動態導向，免費推薦)", "context_length": 1048576},
        {"id": "gemini-3.5-flash-lite", "label": "Gemini 3.5 Flash-Lite (最新發布輕量旗艦，免費可用)", "context_length": 1048576},
        {"id": "gemini-3.1-flash-lite", "label": "Gemini 3.1 Flash-Lite (輕量節能，免費可用)", "context_length": 1048576},
        {"id": "gemini-2.5-flash-lite", "label": "Gemini 2.5 Flash-Lite (穩定輕量，免費可用)", "context_length": 1048576},
        # Flash 模型（免費版可用，支援 2.5, 3.5, 3.6, 3.7, 3.8）
        {"id": "gemini-flash-latest", "label": "Gemini Flash (最新官方動態導向，免費推薦)", "context_length": 1048576},
        {"id": "gemini-3.8-flash", "label": "Gemini 3.8 Flash (最新日常高效旗艦，免費可用)", "context_length": 1048576},
        {"id": "gemini-3.7-flash", "label": "Gemini 3.7 Flash (高效多模態，免費可用)", "context_length": 1048576},
        {"id": "gemini-3.6-flash", "label": "Gemini 3.6 Flash (高效多模態，免費可用)", "context_length": 1048576},
        {"id": "gemini-3.5-flash", "label": "Gemini 3.5 Flash (穩定旗艦，免費可用)", "context_length": 1048576},
        {"id": "gemini-2.5-flash", "label": "Gemini 2.5 Flash (穩定旗艦，免費可用)", "context_length": 1048576},
        # Live 雙向與 TTS 語音模型
        {"id": "gemini-3.8-live", "label": "Gemini 3.8 Live (語音即時全雙工)", "context_length": 128000},
        {"id": "gemini-live", "label": "Gemini Live (語音即時動態導向)", "context_length": 128000},
        # Pro 模型（注意：僅限付費版方案！Google AI Studio 免費版無法調用任何 Pro 模型或生圖模型）
        {"id": "gemini-3.1-pro", "label": "Gemini 3.1 Pro (深度推理，僅限付費方案)", "context_length": 2097152},
        {"id": "gemini-2.5-pro", "label": "Gemini 2.5 Pro (深度推理，僅限付費方案)", "context_length": 2097152},
        {"id": "gemini-pro-latest", "label": "Gemini Pro (最新高階動態導向，僅限付費方案)", "context_length": 2097152},
    ],
    "OpenAI": [
        {"id": "gpt-4o", "label": "GPT-4o (最新旗艦快照)", "context_length": 128000},
        {"id": "gpt-4o-mini", "label": "GPT-4o mini (最新輕量快照)", "context_length": 128000},
        {"id": "o3-mini", "label": "o3-mini (最新推理模型快照)", "context_length": 200000},
        {"id": "o1", "label": "o1 (最新高階推理模型)", "context_length": 200000},
    ],
    "Anthropic": [
        {"id": "claude-3-5-sonnet-latest", "label": "Claude 3.5 Sonnet (最新動態導向)", "context_length": 200000},
        {"id": "claude-3-5-haiku-latest", "label": "Claude 3.5 Haiku (最新輕量動態導向)", "context_length": 200000},
        {"id": "claude-3-7-sonnet-latest", "label": "Claude 3.7 Sonnet (最新動態導向)", "context_length": 200000},
    ],
    "DeepSeek": [
        {"id": "deepseek-chat", "label": "DeepSeek-Chat (動態對齊 V3)", "context_length": 64000},
        {"id": "deepseek-reasoner", "label": "DeepSeek-Reasoner (動態對齊 R1)", "context_length": 64000},
    ],
    "Cerebras": [
        {"id": "llama-3.3-70b", "label": "Llama 3.3 70B (超高速推論)", "context_length": 128000},
        {"id": "llama3.1-8b", "label": "Llama 3.1 8B (極速輕量)", "context_length": 128000},
    ],
    "Together AI": [
        {"id": "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo", "label": "Llama 3.1 70B Turbo", "context_length": 131072},
        {"id": "deepseek-ai/DeepSeek-V3", "label": "DeepSeek-V3", "context_length": 64000},
    ],
    "Fireworks AI": [
        {"id": "accounts/fireworks/models/llama-v3p3-70b-instruct", "label": "Llama 3.3 70B Instruct", "context_length": 131072},
        {"id": "accounts/fireworks/models/deepseek-v3", "label": "DeepSeek-V3", "context_length": 64000},
    ],
    "DeepInfra": [
        {"id": "meta-llama/Llama-3.3-70B-Instruct", "label": "Llama 3.3 70B Instruct", "context_length": 131072},
        {"id": "deepseek-ai/DeepSeek-V3", "label": "DeepSeek-V3", "context_length": 64000},
    ],
    "矽基流動 (SiliconFlow)": [
        {"id": "deepseek-ai/DeepSeek-V3", "label": "DeepSeek-V3 (矽基全速版)", "context_length": 64000},
        {"id": "deepseek-ai/DeepSeek-R1", "label": "DeepSeek-R1 (深度推理版)", "context_length": 64000},
    ],
    "月之暗面 (Moonshot/Kimi)": [
        {"id": "moonshot-v1-8k", "label": "Moonshot v1 8K (Kimi)", "context_length": 8192},
        {"id": "moonshot-v1-32k", "label": "Moonshot v1 32K (Kimi)", "context_length": 32768},
        {"id": "moonshot-v1-128k", "label": "Moonshot v1 128K (Kimi)", "context_length": 131072},
    ],
    "Groq": [
        {"id": "llama-3.3-70b-versatile", "label": "Llama 3.3 70B (極速 Versatile)", "context_length": 131072},
        {"id": "llama-3.1-8b-instant", "label": "Llama 3.1 8B (極速 Instant)", "context_length": 131072},
        {"id": "mixtral-8x7b-32768", "label": "Mixtral 8x7B (多專家模型)", "context_length": 32768},
    ],
    "Mistral": [
        {"id": "mistral-large-latest", "label": "Mistral Large (最新旗艦)", "context_length": 128000},
        {"id": "mistral-small-latest", "label": "Mistral Small (高效輕量)", "context_length": 128000},
        {"id": "codestral-latest", "label": "Codestral (代碼旗艦)", "context_length": 256000},
    ],
    "xAI / Grok": [
        {"id": "grok-2-latest", "label": "Grok 2 (最新旗艦)", "context_length": 131072},
        {"id": "grok-beta", "label": "Grok Beta", "context_length": 131072},
    ],
    "Ollama": [
        {"id": "llama3.2", "label": "Llama 3.2 (本地模型)", "context_length": 131072},
        {"id": "deepseek-r1", "label": "DeepSeek R1 (本地推理)", "context_length": 64000},
        {"id": "qwen2.5", "label": "Qwen 2.5 (本地模型)", "context_length": 32768},
    ],
    "OpenRouter": [
        {"id": "deepseek/deepseek-chat", "label": "DeepSeek V3 (OpenRouter 聚合)", "context_length": 64000},
        {"id": "anthropic/claude-3.5-sonnet", "label": "Claude 3.5 Sonnet (OpenRouter 聚合)", "context_length": 200000},
        {"id": "openai/gpt-4o", "label": "GPT-4o (OpenRouter 聚合)", "context_length": 128000},
    ],
    "本地 LM Studio": [
        {"id": "local-model", "label": "LM Studio 本地加載模型", "context_length": 32768},
    ],
    "本地 vLLM": [
        {"id": "default", "label": "vLLM 本地高吞吐服務", "context_length": 32768},
    ],
    "OpenAI 相容自訂端點": [
        {"id": "custom-model", "label": "自訂端點模型", "context_length": 32768},
    ],
}


def _split_keys(key_str: str) -> list[str]:
    if not key_str:
        return []
    tokens = re.split(r"[\r\n,;]+", str(key_str))
    return [t.strip() for t in tokens if t.strip()]


def _get(url: str, key: str = "", headers: dict | None = None, params: dict | None = None) -> dict:
    """發送 HTTP GET 請求，若配置多金鑰且遭遇 401/429 則自動嘗試備用金鑰。"""
    keys = _split_keys(key) or [""]
    last_exc = None
    final_url = url
    if params:
        final_url += ("&" if "?" in final_url else "?") + urlencode({k: v for k, v in params.items() if v not in (None, "")})

    for k in keys:
        h = {"Accept": "application/json", "User-Agent": "DesktopPet/2.0"}
        if k:
            h["Authorization"] = "Bearer " + k
        if headers:
            h.update(headers)
            # 若自訂 headers 包含 x-api-key 且有多金鑰，動態替換
            if "x-api-key" in h and k:
                h["x-api-key"] = k

        # 針對 Gemini URL 參數中帶 key 的情況動態置換
        req_url = final_url
        if "key=" in req_url and k:
            req_url = re.sub(r"key=[^&]+", f"key={k}", req_url)

        try:
            with urlopen(Request(req_url, headers=h), timeout=20) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:300]
            last_exc = ModelCatalogError(f"HTTP {exc.code}: {detail}")
            # 若為 401 或 429 且還有備用金鑰，嘗試下一組
            if exc.code in (401, 403, 429) and len(keys) > 1:
                continue
            raise last_exc from exc
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_exc = ModelCatalogError(str(exc))
            if len(keys) > 1:
                continue
            raise last_exc from exc

    if last_exc:
        raise last_exc
    raise ModelCatalogError("請求未執行")


def _endpoint(profile: dict) -> str:
    provider = profile.get("provider", "")
    return (profile.get("endpoint") or OPENAI_BASES.get(provider, "")).strip().rstrip("/")


def _normalise(items, provider: str, source: str) -> list[dict]:
    result = []
    seen = set()
    for item in items or []:
        if isinstance(item, str):
            model_id = item
            item = {}
        else:
            model_id = item.get("id") or item.get("name") or item.get("model") or item.get("baseModelId")
        if not model_id:
            continue
        model_id = str(model_id)
        if model_id.startswith("models/"):
            model_id = model_id[7:]
        if model_id in seen:
            continue
        seen.add(model_id)

        display_name = item.get("display_name") or item.get("displayName") or item.get("name") or model_id
        # 若為知名動態模型，優化顯示名稱
        if model_id == "deepseek-chat" and "V3" not in display_name:
            display_name = "DeepSeek-Chat (動態對齊 V3)"
        elif model_id == "deepseek-reasoner" and "R1" not in display_name:
            display_name = "DeepSeek-Reasoner (動態對齊 R1)"

        result.append({
            "id": model_id,
            "label": display_name,
            "provider": provider,
            "source": source,
            "capabilities": item.get("capabilities") or item.get("supported_actions") or item.get("supportedGenerationMethods") or [],
            "context_length": item.get("context_length") or item.get("max_context_length") or item.get("inputTokenLimit"),
            "raw": item,
        })
    return result


def _openai_compatible(profile: dict, source: str = "openai-compatible") -> list[dict]:
    base = _endpoint(profile)
    if not base:
        raise ModelCatalogError("沒有可用的 API 端點")
    if base.endswith("/models"):
        candidates = [base]
    elif base.endswith("/v1"):
        candidates = [base + "/models"]
    else:
        candidates = [base + "/models", base + "/v1/models"]
    errors = []
    for url in candidates:
        try:
            payload = _get(url, profile.get("key", ""))
            items = payload.get("data", payload.get("models", [])) if isinstance(payload, dict) else payload
            return _normalise(items, profile.get("provider", "自訂端點"), source)
        except ModelCatalogError as exc:
            errors.append(f"{url}: {exc}")
    raise ModelCatalogError("；".join(errors))


def _gemini(profile: dict) -> list[dict]:
    raw_key = profile.get("key", "").strip()
    if not raw_key:
        raise ModelCatalogError("Gemini 模型列表需要 API Key")
    first_key = _split_keys(raw_key)[0] if _split_keys(raw_key) else raw_key

    endpoint = (profile.get("endpoint") or "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
    url = endpoint if endpoint.endswith("/models") else f"{endpoint}/models"
    token = None
    all_items = []
    while True:
        payload = _get(url, key=raw_key, params={"key": first_key, "pageSize": 1000, "pageToken": token})
        all_items.extend(payload.get("models", []))
        token = payload.get("nextPageToken")
        if not token:
            break
    items = [
        x for x in all_items
        if "generateContent" in (x.get("supportedGenerationMethods") or [])
        or "generateContent" in (x.get("supported_actions") or [])
    ]
    return _normalise(items, "Google Gemini", "provider")


def _anthropic(profile: dict) -> list[dict]:
    base = _endpoint(profile) or "https://api.anthropic.com"
    url = base if base.endswith("/models") else base.rstrip("/") + "/v1/models"
    raw_key = profile.get("key", "").strip()
    payload = _get(
        url,
        key=raw_key,
        headers={"x-api-key": raw_key, "anthropic-version": "2023-06-01"},
        params={"limit": 1000},
    )
    return _normalise(payload.get("data", []), "Anthropic", "provider")


def _mistral(profile: dict) -> list[dict]:
    base = _endpoint(profile) or "https://api.mistral.ai/v1"
    url = base if base.endswith("/models") else base.rstrip("/") + ("/models" if base.endswith("/v1") else "/v1/models")
    payload = _get(url, profile.get("key", ""))
    return _normalise(payload.get("data", []), "Mistral", "provider")


def _openrouter(profile: dict) -> list[dict]:
    base = (profile.get("endpoint") or "https://openrouter.ai/api/v1").rstrip("/")
    url = base if base.endswith("/models") else base + "/models"
    payload = _get(url, profile.get("key", ""))
    return _normalise(payload.get("data", []), "OpenRouter", "provider")


def _ollama(profile: dict) -> list[dict]:
    base = (profile.get("endpoint") or "http://localhost:11434").rstrip("/")
    base = base[:-3] if base.endswith("/v1") else base
    payload = _get(base + "/api/tags", profile.get("key", ""))
    return _normalise(payload.get("models", []), profile.get("provider", "Ollama"), "provider")


def merge_dynamic_aliases(provider: str, fetched_models: list[dict]) -> list[dict]:
    """將廠商最新的動態別名置頂呈現，確保使用者優先選用最新動態導向模型。"""
    aliases = DYNAMIC_MODEL_ALIASES.get(provider, [])
    if not aliases:
        return fetched_models

    existing_ids = {m["id"] for m in fetched_models}
    alias_items = []
    for a in aliases:
        aid = a["id"]
        alias_items.append({
            "id": aid,
            "label": a.get("label", aid),
            "provider": provider,
            "source": "dynamic-alias",
            "capabilities": ["chat", "generateContent"],
            "context_length": a.get("context_length", 128000),
            "raw": a,
        })

    # 保留遠端探測到的其餘模型，排除重複
    remaining = [m for m in fetched_models if m["id"] not in {a["id"] for a in aliases}]
    return alias_items + remaining


def discover_models(profile: dict) -> tuple[list[dict], str, str | None]:
    """回傳 (models, source, fallback_note)。絕不修改 profile 原始資料。
    若遠端探測成功，自動整合置頂最新的動態別名（Dynamic Aliases）。
    """
    provider = profile.get("provider", "")
    direct = {
        "Google Gemini": _gemini,
        "Anthropic": _anthropic,
        "Mistral": _mistral,
        "OpenRouter": _openrouter,
        "Ollama": _ollama,
    }.get(provider)
    errors = []
    if direct:
        try:
            raw_models = direct(profile)
            models = merge_dynamic_aliases(provider, raw_models)
            return models, "provider", None
        except ModelCatalogError as exc:
            errors.append(f"{provider} 專用 API：{exc}")
    try:
        raw_models = _openai_compatible(profile)
        if raw_models:
            models = merge_dynamic_aliases(provider, raw_models)
            note = "；".join(errors) if errors else None
            return models, "openai-compatible", note
        errors.append("OpenAI 相容端點未回傳模型清單")
    except ModelCatalogError as exc:
        errors.append(f"OpenAI 相容回退：{exc}")

    # 若遠端探測全數失敗但該廠商有定義動態別名，回退提供最新動態別名清單，避免阻斷操作
    if provider in DYNAMIC_MODEL_ALIASES:
        fallback_models = merge_dynamic_aliases(provider, [])
        note = "遠端探測失敗，已自動載入官方最新動態導向模型清單（" + "；".join(errors) + "）"
        return fallback_models, "dynamic-alias-fallback", note

    raise ModelCatalogError("模型列表查詢失敗：" + "；".join(errors))
