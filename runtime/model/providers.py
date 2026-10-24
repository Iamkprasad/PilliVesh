"""Chat provider registry + wire adapters (stdlib only).

Configured providers and their API keys live in results/providers.json,
created with mode 0600. Public API responses only expose a masked hint;
the key never leaves the server. Chat requests are proxied by the local
server, so keys are not sent to the browser and CORS is not needed.

Supported protocols: openai (also OpenRouter/Groq/DeepSeek/custom),
anthropic, google (Gemini), plus the built-in local llama.cpp provider.
"""
import json
import os
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "results"
CONFIG_FILE = RESULTS / "providers.json"

LOCAL_ID = "local"
LOCAL_HOST = "127.0.0.1"
LOCAL_PORT = 8081
LOCAL_PROVIDER = {
    "id": LOCAL_ID,
    "name": "Local llama.cpp",
    "type": "local",
    "base_url": f"http://{LOCAL_HOST}:{LOCAL_PORT}/v1",
    "model": "local",
    "builtin": True,
}

PROVIDER_TYPES = ("openai", "anthropic", "google")
TYPE_LABELS = {
    "openai": "OpenAI-compatible",
    "anthropic": "Anthropic",
    "google": "Google Gemini",
    "local": "On-device",
}

PRESETS = [
    {
        "preset": "openai", "name": "OpenAI", "type": "openai",
        "base_url": "https://api.openai.com/v1", "model": "gpt-4o-mini",
    },
    {
        "preset": "openrouter", "name": "OpenRouter", "type": "openai",
        "base_url": "https://openrouter.ai/api/v1",
        "model": "openai/gpt-4o-mini",
    },
    {
        "preset": "deepseek", "name": "DeepSeek", "type": "openai",
        "base_url": "https://api.deepseek.com/v1", "model": "deepseek-chat",
    },
    {
        "preset": "groq", "name": "Groq", "type": "openai",
        "base_url": "https://api.groq.com/openai/v1",
        "model": "llama-3.3-70b-versatile",
    },
    {
        "preset": "mistral", "name": "Mistral", "type": "openai",
        "base_url": "https://api.mistral.ai/v1", "model": "mistral-small-latest",
    },
    {
        "preset": "anthropic", "name": "Anthropic", "type": "anthropic",
        "base_url": "https://api.anthropic.com/v1", "model": "claude-sonnet-4-5",
    },
    {
        "preset": "gemini", "name": "Google Gemini", "type": "google",
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "model": "gemini-2.5-flash",
    },
    {
        "preset": "custom", "name": "Custom", "type": "openai",
        "base_url": "http://127.0.0.1:11434/v1", "model": "local-model",
    },
]


def _now():
    return datetime.now(timezone.utc).isoformat()


def _read_config():
    try:
        if CONFIG_FILE.exists():
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("providers"), list):
                data["providers"] = [
                    p for p in data["providers"]
                    if isinstance(p, dict) and p.get("id")
                ]
                return data
    except Exception:
        pass
    return {"active": LOCAL_ID, "providers": []}


def _write_config(config):
    RESULTS.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".providers.", dir=str(RESULTS))
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
            f.write("\n")
        os.replace(tmp, CONFIG_FILE)
        os.chmod(CONFIG_FILE, 0o600)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _clean_url(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Base URL is required")
    value = value.strip().rstrip("/")
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("Base URL must start with http:// or https://")
    if parsed.username or parsed.password:
        raise ValueError("Put credentials in the API key field, not the URL")
    if parsed.query or parsed.fragment:
        raise ValueError("Base URL must not contain a query or fragment")
    return value


def _mask(key):
    if not key:
        return ""
    tail = key[-4:] if len(key) > 4 else key
    return "••••" + tail


def _public(provider, active_id):
    out = {
        "id": provider.get("id"),
        "name": provider.get("name"),
        "type": provider.get("type"),
        "type_label": TYPE_LABELS.get(provider.get("type"), provider.get("type")),
        "base_url": provider.get("base_url"),
        "model": provider.get("model"),
        "builtin": bool(provider.get("builtin")),
        "has_key": bool(provider.get("api_key")),
        "key_hint": _mask(provider.get("api_key")),
        "active": provider.get("id") == active_id,
    }
    return out


def state():
    config = _read_config()
    active_id = config.get("active") or LOCAL_ID
    known = {p.get("id") for p in config["providers"]}
    if active_id != LOCAL_ID and active_id not in known:
        active_id = LOCAL_ID
    local_status = {"running": False, "loaded_id": None}
    try:
        from runtime.model import router
        local_status = {
            "running": bool(router.router_running()),
            "loaded_id": router.current_model_id(),
        }
    except Exception:
        pass
    providers = [_public(LOCAL_PROVIDER, active_id)]
    providers += [_public(p, active_id) for p in config["providers"]]
    return {
        "active": active_id,
        "providers": providers,
        "presets": PRESETS,
        "local": local_status,
    }


def resolve(provider_id=None):
    """Full provider config (including key) for server-side use only."""
    config = _read_config()
    pid = provider_id or config.get("active") or LOCAL_ID
    if pid == LOCAL_ID:
        return dict(LOCAL_PROVIDER)
    for provider in config["providers"]:
        if provider.get("id") == pid:
            return dict(provider)
    raise ValueError(f"Unknown provider: {pid}")


def save_provider(data):
    if not isinstance(data, dict):
        raise ValueError("Invalid provider data")
    name = str(data.get("name") or "").strip()
    if not name or len(name) > 60:
        raise ValueError("Name is required (max 60 chars)")
    ptype = str(data.get("type") or "").strip()
    if ptype not in PROVIDER_TYPES:
        raise ValueError("Type must be openai, anthropic or google")
    base_url = _clean_url(data.get("base_url"))
    model = str(data.get("model") or "").strip()
    if not model or len(model) > 160:
        raise ValueError("Model id is required (max 160 chars)")
    api_key = data.get("api_key")
    if api_key is not None and not isinstance(api_key, str):
        raise ValueError("API key must be text")
    api_key = (api_key or "").strip()
    if "\n" in api_key or "\r" in api_key or len(api_key) > 4096:
        raise ValueError("Invalid API key")

    config = _read_config()
    pid = str(data.get("id") or "").strip()
    existing = None
    if pid:
        if pid == LOCAL_ID:
            raise ValueError("The local provider is built-in")
        for provider in config["providers"]:
            if provider.get("id") == pid:
                existing = provider
                break
        if existing is None:
            raise ValueError("Provider not found")
    else:
        pid = "p-" + uuid.uuid4().hex[:8]

    if not api_key and existing:
        api_key = existing.get("api_key") or ""
    entry = {
        "id": pid,
        "name": name,
        "type": ptype,
        "base_url": base_url,
        "model": model,
        "api_key": api_key,
        "updated": _now(),
    }
    if existing:
        entry["created"] = existing.get("created") or _now()
        existing.update(entry)
    else:
        entry["created"] = _now()
        config["providers"].append(entry)
    _write_config(config)
    return _public(entry, config.get("active") or LOCAL_ID)


def delete_provider(provider_id):
    pid = str(provider_id or "").strip()
    if not pid:
        raise ValueError("Missing provider id")
    if pid == LOCAL_ID:
        raise ValueError("The local provider is built-in")
    config = _read_config()
    before = len(config["providers"])
    config["providers"] = [
        p for p in config["providers"] if p.get("id") != pid
    ]
    if len(config["providers"]) == before:
        raise ValueError("Provider not found")
    if config.get("active") == pid:
        config["active"] = LOCAL_ID
    _write_config(config)
    return {"deleted": pid, "active": config.get("active") or LOCAL_ID}


def set_active(provider_id):
    pid = str(provider_id or "").strip()
    if not pid:
        raise ValueError("Missing provider id")
    if pid != LOCAL_ID:
        config = _read_config()
        if not any(p.get("id") == pid for p in config["providers"]):
            raise ValueError("Provider not found")
        config["active"] = pid
        _write_config(config)
    else:
        config = _read_config()
        config["active"] = LOCAL_ID
        _write_config(config)
    return state()


def _headers(provider, method="POST"):
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "PilliVesh/1.0",
    }
    key = provider.get("api_key") or ""
    if provider.get("type") == "anthropic":
        if key:
            headers["x-api-key"] = key
        headers["anthropic-version"] = "2023-06-01"
    elif key:
        headers["Authorization"] = f"Bearer {key}"
    return headers


def _scrub(provider, text):
    """Remove the raw or URL-encoded key from any error text."""
    text = str(text)
    key = provider.get("api_key") or ""
    if key:
        text = text.replace(key, "***")
        text = text.replace(urllib.parse.quote(key, safe=""), "***")
    return text


def _http_error(provider, code, detail, key):
    if key:
        detail = detail.replace(key, "***")
        detail = detail.replace(urllib.parse.quote(key, safe=""), "***")
    if code in (401, 403):
        return ValueError(
            f"{provider.get('name')}: authentication failed (HTTP {code}) "
            f"— check the API key in Settings."
        )
    if code == 429:
        return ValueError(f"{provider.get('name')}: rate limited (HTTP 429)")
    detail = " ".join((detail or "").split())[:300]
    return ValueError(
        f"{provider.get('name')} error (HTTP {code})"
        + (f": {detail}" if detail else "")
    )


def _post(provider, url, payload):
    key = provider.get("api_key") or ""
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=_headers(provider),
        method="POST",
    )
    try:
        return urllib.request.urlopen(req, timeout=180)
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        raise _http_error(provider, e.code, detail, key)
    except Exception as e:
        raise ValueError(
            f"{provider.get('name')} request failed: {_scrub(provider, e)}"
        )


def _get(provider, url, timeout=12):
    key = provider.get("api_key") or ""
    req = urllib.request.Request(
        url, headers=_headers(provider), method="GET"
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        raise _http_error(provider, e.code, detail, key)
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(
            f"{provider.get('name')} request failed: {_scrub(provider, e)}"
        )


def _clean_messages(messages):
    if not isinstance(messages, list) or not messages:
        raise ValueError("Missing messages")
    cleaned = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        role = message.get("role")
        content = message.get("content")
        if not isinstance(content, str) or not content:
            continue
        if role not in ("system", "user", "assistant"):
            role = "user"
        cleaned.append({"role": role, "content": content})
    if not cleaned:
        raise ValueError("Missing messages")
    return cleaned


def _system_and_turns(messages):
    cleaned = _clean_messages(messages)
    system = "\n\n".join(m["content"] for m in cleaned if m["role"] == "system")
    turns = [m for m in cleaned if m["role"] != "system"]
    if not turns:
        turns = [{"role": "user", "content": system or "Hello"}]
    return system, turns


def _openai_text(value):
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        out = []
        for part in value:
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                out.append(part["text"])
            elif isinstance(part, str):
                out.append(part)
        return "".join(out)
    return ""


def _normalized(text, provider):
    return {
        "choices": [{"message": {"role": "assistant", "content": text}}],
        "model": provider.get("model") or provider.get("id"),
    }


def _json_response(resp):
    try:
        with resp:
            return json.loads(resp.read().decode("utf-8"))
    except ValueError:
        raise ValueError("Upstream returned malformed JSON")


def complete(provider, messages, max_tokens=512, temperature=0.7):
    """Non-streaming completion normalized to the OpenAI shape."""
    ptype = provider.get("type")
    if ptype == "openai":
        base = provider["base_url"].rstrip("/")
        payload = {
            "model": provider["model"],
            "messages": _clean_messages(messages),
            "max_tokens": int(max_tokens),
            "temperature": float(temperature),
            "stream": False,
        }
        data = _json_response(_post(provider, base + "/chat/completions", payload))
        choices = data.get("choices") or []
        if not choices:
            raise _http_error(provider, 502, "empty completion", "")
        message = choices[0].get("message") or {}
        result = _normalized(_openai_text(message.get("content")), provider)
        if data.get("usage"):
            result["usage"] = data["usage"]
        return result

    if ptype == "anthropic":
        base = provider["base_url"].rstrip("/")
        system, turns = _system_and_turns(messages)
        payload = {
            "model": provider["model"],
            "messages": turns,
            "max_tokens": int(max_tokens),
            "temperature": float(temperature),
        }
        if system:
            payload["system"] = system
        data = _json_response(_post(provider, base + "/messages", payload))
        text = ""
        for block in data.get("content") or []:
            if isinstance(block, dict) and block.get("type") == "text":
                text += block.get("text") or ""
        result = _normalized(text, provider)
        if data.get("usage"):
            usage = data["usage"]
            result["usage"] = {
                "prompt_tokens": usage.get("input_tokens"),
                "completion_tokens": usage.get("output_tokens"),
            }
        return result

    if ptype == "google":
        base = provider["base_url"].rstrip("/")
        model = provider["model"]
        if model.startswith("models/"):
            model = model[len("models/"):]
        key = provider.get("api_key") or ""
        if not key:
            raise ValueError(f"{provider.get('name')}: no API key saved.")
        system, turns = _system_and_turns(messages)
        contents = []
        for turn in turns:
            contents.append({
                "role": "model" if turn["role"] == "assistant" else "user",
                "parts": [{"text": turn["content"]}],
            })
        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": float(temperature),
                "maxOutputTokens": int(max_tokens),
            },
        }
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}
        url = (
            f"{base}/models/{urllib.parse.quote(model)}:generateContent"
            f"?key={urllib.parse.quote(key)}"
        )
        data = _json_response(_post(provider, url, payload))
        text = ""
        for candidate in data.get("candidates") or []:
            for part in (candidate.get("content") or {}).get("parts") or []:
                if isinstance(part, dict) and not part.get("thought"):
                    text += part.get("text") or ""
        result = _normalized(text, provider)
        usage = data.get("usageMetadata") or {}
        if usage:
            result["usage"] = {
                "prompt_tokens": usage.get("promptTokenCount"),
                "completion_tokens": usage.get("candidatesTokenCount"),
            }
        return result

    raise ValueError("This provider does not support remote completions")


def _iter_data_lines(resp):
    try:
        for raw in resp:
            line = raw.decode("utf-8", errors="replace").strip()
            if line.startswith("data:"):
                yield line[5:].strip()
    finally:
        try:
            resp.close()
        except Exception:
            pass


def _parse_openai_sse(data):
    if not data:
        return None
    if data == "[DONE]":
        return {"done": True}
    try:
        obj = json.loads(data)
    except ValueError:
        return None
    if isinstance(obj, dict) and obj.get("error"):
        error = obj["error"]
        message = error.get("message") if isinstance(error, dict) else str(error)
        raise ValueError(message or "Upstream stream error")
    choices = obj.get("choices") or []
    if not choices:
        return None
    delta = choices[0].get("delta") or {}
    text = _openai_text(delta.get("content"))
    return {"text": text} if text else None


def _parse_anthropic_sse(data):
    if not data:
        return None
    try:
        obj = json.loads(data)
    except ValueError:
        return None
    kind = obj.get("type")
    if kind == "content_block_delta":
        delta = obj.get("delta") or {}
        text = delta.get("text") or ""
        return {"text": text} if text else None
    if kind == "message_stop":
        return {"done": True}
    if kind == "error":
        error = obj.get("error") or {}
        raise ValueError(error.get("message") or "Upstream stream error")
    return None


def _parse_google_sse(data):
    if not data:
        return None
    try:
        obj = json.loads(data)
    except ValueError:
        return None
    text = ""
    for candidate in obj.get("candidates") or []:
        for part in (candidate.get("content") or {}).get("parts") or []:
            if isinstance(part, dict) and not part.get("thought"):
                text += part.get("text") or ""
    return {"text": text} if text else None


def _stream_openai(provider, messages, max_tokens, temperature):
    base = provider["base_url"].rstrip("/")
    payload = {
        "model": provider["model"],
        "messages": _clean_messages(messages),
        "max_tokens": int(max_tokens),
        "temperature": float(temperature),
        "stream": True,
    }
    resp = _post(provider, base + "/chat/completions", payload)
    for data in _iter_data_lines(resp):
        event = _parse_openai_sse(data)
        if not event:
            continue
        if event.get("done"):
            return
        yield event["text"]


def _stream_anthropic(provider, messages, max_tokens, temperature):
    base = provider["base_url"].rstrip("/")
    system, turns = _system_and_turns(messages)
    payload = {
        "model": provider["model"],
        "messages": turns,
        "max_tokens": int(max_tokens),
        "temperature": float(temperature),
        "stream": True,
    }
    if system:
        payload["system"] = system
    resp = _post(provider, base + "/messages", payload)
    for data in _iter_data_lines(resp):
        event = _parse_anthropic_sse(data)
        if not event:
            continue
        if event.get("done"):
            return
        yield event["text"]


def _stream_google(provider, messages, max_tokens, temperature):
    base = provider["base_url"].rstrip("/")
    model = provider["model"]
    if model.startswith("models/"):
        model = model[len("models/"):]
    key = provider.get("api_key") or ""
    if not key:
        raise ValueError(f"{provider.get('name')}: no API key saved.")
    system, turns = _system_and_turns(messages)
    contents = []
    for turn in turns:
        contents.append({
            "role": "model" if turn["role"] == "assistant" else "user",
            "parts": [{"text": turn["content"]}],
        })
    payload = {
        "contents": contents,
        "generationConfig": {
            "temperature": float(temperature),
            "maxOutputTokens": int(max_tokens),
        },
    }
    if system:
        payload["systemInstruction"] = {"parts": [{"text": system}]}
    url = (
        f"{base}/models/{urllib.parse.quote(model)}:streamGenerateContent"
        f"?alt=sse&key={urllib.parse.quote(key)}"
    )
    resp = _post(provider, url, payload)
    for data in _iter_data_lines(resp):
        event = _parse_google_sse(data)
        if event and event.get("text"):
            yield event["text"]


def stream(provider, messages, max_tokens=512, temperature=0.7):
    """Yield text deltas for a remote provider."""
    ptype = provider.get("type")
    if ptype == "openai":
        return _stream_openai(provider, messages, max_tokens, temperature)
    if ptype == "anthropic":
        return _stream_anthropic(provider, messages, max_tokens, temperature)
    if ptype == "google":
        return _stream_google(provider, messages, max_tokens, temperature)
    raise ValueError("This provider does not support streaming")


def test_provider(provider_id):
    provider = resolve(provider_id)
    if provider.get("type") == "local":
        url = f"http://{LOCAL_HOST}:{LOCAL_PORT}/health"
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "PilliVesh/1.0"}
            )
            with urllib.request.urlopen(req, timeout=4) as resp:
                if 200 <= resp.status < 300:
                    return {"ok": True, "detail": "llama-server is reachable."}
        except Exception:
            pass
        raise ValueError("llama-server is not running. Load a model first.")

    base = provider["base_url"].rstrip("/")
    key = provider.get("api_key") or ""
    if provider.get("type") == "google":
        if not key:
            raise ValueError(f"{provider.get('name')}: no API key saved.")
        url = f"{base}/models?key={urllib.parse.quote(key)}"
    else:
        url = base + "/models"
    data = _get(provider, url)
    items = data.get("data") if isinstance(data, dict) else None
    if items is None and isinstance(data, dict):
        items = data.get("models")
    count = len(items) if isinstance(items, list) else None
    detail = "Key accepted."
    if count is not None:
        detail = f"Key accepted — {count} model(s) visible."
    return {"ok": True, "detail": detail}
