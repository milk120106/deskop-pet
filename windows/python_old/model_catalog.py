"""Model discovery with provider-specific handlers and OpenAI-compatible fallback."""
from __future__ import annotations

import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


class ModelCatalogError(RuntimeError):
    pass


OPENAI_BASES = {
    "OpenAI": "https://api.openai.com/v1",
    "DeepSeek": "https://api.deepseek.com",
    "xAI / Grok": "https://api.x.ai/v1",
    "Groq": "https://api.groq.com/openai/v1",
    "z.ai": "https://api.z.ai/api/paas/v4",
    "GLM": "https://open.bigmodel.cn/api/paas/v4",
}


def _get(url: str, key: str = "", headers: dict | None = None, params: dict | None = None) -> dict:
    if params:
        url += ("&" if "?" in url else "?") + urlencode({k: v for k, v in params.items() if v not in (None, "")})
    h = {"Accept": "application/json", "User-Agent": "PythonDesktopPet/4"}
    if key:
        h["Authorization"] = "Bearer " + key
    if headers:
        h.update(headers)
    try:
        with urlopen(Request(url, headers=h), timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        raise ModelCatalogError(f"HTTP {exc.code}: {detail}") from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise ModelCatalogError(str(exc)) from exc


def _endpoint(profile: dict) -> str:
    provider = profile.get("provider", "")
    return (profile.get("endpoint") or OPENAI_BASES.get(provider, "")).strip().rstrip("/")


def _normalise(items, provider: str, source: str) -> list[dict]:
    result = []
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
        result.append({
            "id": model_id,
            "label": item.get("display_name") or item.get("displayName") or item.get("name") or model_id,
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
            return _normalise(items, profile.get("provider", "Custom"), source)
        except ModelCatalogError as exc:
            errors.append(f"{url}: {exc}")
    raise ModelCatalogError("；".join(errors))


def _gemini(profile: dict) -> list[dict]:
    key = profile.get("key", "")
    if not key:
        raise ModelCatalogError("Gemini 模型列表需要 API Key")
    url = (profile.get("endpoint") or "https://generativelanguage.googleapis.com/v1beta/models").rstrip("/")
    token = None
    all_items = []
    while True:
        payload = _get(url, params={"key": key, "pageSize": 1000, "pageToken": token})
        all_items.extend(payload.get("models", []))
        token = payload.get("nextPageToken")
        if not token:
            break
    items = [x for x in all_items if "generateContent" in (x.get("supportedGenerationMethods") or []) or "generateContent" in (x.get("supported_actions") or [])]
    return _normalise(items, "Google Gemini", "provider")


def _anthropic(profile: dict) -> list[dict]:
    base = _endpoint(profile) or "https://api.anthropic.com"
    url = base if base.endswith("/models") else base.rstrip("/") + "/v1/models"
    payload = _get(url, headers={"x-api-key": profile.get("key", ""), "anthropic-version": "2023-06-01"}, params={"limit": 1000})
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


def discover_models(profile: dict) -> tuple[list[dict], str, str | None]:
    """Return (models, source, fallback_note). Never changes the profile."""
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
            models = direct(profile)
            return models, "provider", None
        except ModelCatalogError as exc:
            errors.append(f"{provider} 專用 API：{exc}")
    try:
        models = _openai_compatible(profile)
        if models:
            note = "；".join(errors) if errors else None
            return models, "openai-compatible", note
        errors.append("OpenAI 相容 API 沒有回傳模型")
    except ModelCatalogError as exc:
        errors.append(f"OpenAI 相容 fallback：{exc}")
    raise ModelCatalogError("模型列表查詢失敗：" + "；".join(errors))
