"""Chat providers for the AI advisor.

Two wire formats, one interface:

* ``openai`` — any OpenAI-compatible ``/chat/completions`` endpoint (OpenAI,
  OpenRouter, Groq, Mistral, and local servers such as Ollama or
  ``llama-server`` which speak the same schema);
* ``gemini`` — Google's native ``generativelanguage`` streaming API.

Only ``urllib`` is used, so the feature adds no HTTP dependency. Calls are
blocking generators: the GUI runs them in a worker thread and forwards
chunks to the UI, exactly like the existing update checker.

Nothing here logs the API key; error bodies are redacted before they reach a
message, and the key is only placed in the request header.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, replace

from . import guard


class ProviderError(RuntimeError):
    """A provider call failed (bad key, quota, network, malformed reply)."""

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class Preset:
    """A selectable provider endpoint."""

    id: str
    label: str
    kind: str
    base_url: str
    model: str
    needs_key: bool = True
    note: str = ""


PRESETS: dict[str, Preset] = {
    "openai": Preset(
        "openai", "OpenAI", "openai",
        "https://api.openai.com/v1", "gpt-4o-mini",
        note="Platform key from platform.openai.com",
    ),
    "openrouter": Preset(
        "openrouter", "OpenRouter", "openai",
        "https://openrouter.ai/api/v1", "openai/gpt-4o-mini",
        note="One key for many models",
    ),
    "groq": Preset(
        "groq", "Groq", "openai",
        "https://api.groq.com/openai/v1", "llama-3.3-70b-versatile",
        note="Fast hosted inference",
    ),
    "gemini": Preset(
        "gemini", "Google Gemini", "gemini",
        "https://generativelanguage.googleapis.com/v1beta",
        "gemini-2.0-flash",
        note="Native Google API",
    ),
    "local": Preset(
        "local", "Local (Ollama / llama.cpp)", "openai",
        "http://localhost:11434/v1", "llama3.2",
        needs_key=False,
        note="Runs on this machine; no cloud key",
    ),
    "custom": Preset(
        "custom", "Custom OpenAI-compatible", "openai",
        "", "",
        note="Any /v1 endpoint that speaks chat/completions",
    ),
}


def preset(preset_id: str) -> Preset:
    """Look up a preset, falling back to ``custom``."""
    return PRESETS.get(preset_id or "", PRESETS["custom"])


@dataclass
class ProviderConfig:
    """Everything needed to talk to one endpoint."""

    preset_id: str = "openai"
    kind: str = "openai"
    base_url: str = ""
    model: str = ""
    api_key: str = ""
    temperature: float = 0.2
    max_tokens: int = 1200
    timeout: float = 60.0
    retry_delay: float = 1.0

    @classmethod
    def from_preset(
        cls, preset_id: str, api_key: str = "", model: str = ""
    ) -> "ProviderConfig":
        """Build a config from a preset, overriding model when given."""
        chosen = preset(preset_id)
        return cls(
            preset_id=chosen.id,
            kind=chosen.kind,
            base_url=chosen.base_url,
            model=model or chosen.model,
            api_key=api_key,
        )

    def with_key(self, api_key: str) -> "ProviderConfig":
        return replace(self, api_key=api_key or "")

    @property
    def needs_key(self) -> bool:
        return preset(self.preset_id).needs_key

    @property
    def is_local(self) -> bool:
        return self.preset_id == "local" or "localhost" in (self.base_url or "") \
            or "127.0.0.1" in (self.base_url or "")


def validate(config: ProviderConfig) -> list[str]:
    """Human-readable problems with *config* (empty list means usable)."""
    problems: list[str] = []
    if config.kind not in ("openai", "gemini"):
        problems.append(f"unknown provider kind: {config.kind!r}")
    if not (config.base_url or "").strip():
        problems.append("base URL is empty")
    elif not config.base_url.startswith(("http://", "https://")):
        problems.append("base URL must start with http:// or https://")
    if not (config.model or "").strip():
        problems.append("model name is empty")
    if config.needs_key and not (config.api_key or "").strip():
        problems.append("API key is missing (store it in the system keyring)")
    if config.max_tokens < 64:
        problems.append("max tokens is too small")
    return problems


def estimate_tokens(text: str) -> int:
    """Rough token estimate (~4 characters per token)."""
    return max(1, len(text or "") // 4)


# --------------------------------------------------------------------------
# Request building
# --------------------------------------------------------------------------

def _openai_body(config: ProviderConfig, messages: list[dict]) -> dict:
    body = {
        "model": config.model,
        "messages": messages,
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
        "stream": True,
    }
    if not config.is_local:
        body["stream_options"] = {"include_usage": True}
    return body


def _gemini_body(config: ProviderConfig, messages: list[dict]) -> dict:
    system_parts: list[str] = []
    contents: list[dict] = []
    for message in messages:
        role = message.get("role")
        text = message.get("content") or ""
        if role == "system":
            system_parts.append(text)
            continue
        contents.append(
            {
                "role": "model" if role == "assistant" else "user",
                "parts": [{"text": text}],
            }
        )
    body: dict = {
        "contents": contents,
        "generationConfig": {
            "temperature": config.temperature,
            "maxOutputTokens": config.max_tokens,
        },
    }
    if system_parts:
        body["systemInstruction"] = {"parts": [{"text": "\n\n".join(system_parts)}]}
    return body


def build_request(
    config: ProviderConfig, messages: list[dict]
) -> tuple[str, dict, dict]:
    """Return ``(url, headers, body)`` for *config*; raises on bad config."""
    problems = validate(config)
    if problems:
        raise ProviderError("; ".join(problems))

    if config.kind == "gemini":
        base = config.base_url.rstrip("/")
        model = config.model.strip()
        if model.startswith("models/"):
            model = model[len("models/"):]
        url = f"{base}/models/{model}:streamGenerateContent?alt=sse"
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": config.api_key,
        }
        return url, headers, _gemini_body(config, messages)

    url = config.base_url.rstrip("/") + "/chat/completions"
    headers = {"Content-Type": "application/json"}
    if config.api_key:
        headers["Authorization"] = f"Bearer {config.api_key}"
    return url, headers, _openai_body(config, messages)


# --------------------------------------------------------------------------
# Response parsing
# --------------------------------------------------------------------------

def _extract_text(kind: str, payload: dict) -> str:
    """Pull the incremental text out of one streamed JSON object."""
    if kind == "gemini":
        candidates = payload.get("candidates") or []
        if not candidates:
            return ""
        parts = (candidates[0].get("content") or {}).get("parts") or []
        return "".join(part.get("text") or "" for part in parts)
    choices = payload.get("choices") or []
    if not choices:
        return ""
    delta = choices[0].get("delta") or {}
    if "content" in delta:
        return delta.get("content") or ""
    message = choices[0].get("message") or {}
    return message.get("content") or ""


def _extract_usage(kind: str, payload: dict) -> dict:
    if kind == "gemini":
        usage = payload.get("usageMetadata") or {}
        return {
            "in": usage.get("promptTokenCount"),
            "out": usage.get("candidatesTokenCount"),
        }
    usage = payload.get("usage") or {}
    return {"in": usage.get("prompt_tokens"), "out": usage.get("completion_tokens")}


# --------------------------------------------------------------------------
# Calls
# --------------------------------------------------------------------------

def stream_chat(
    config: ProviderConfig,
    messages: list[dict],
    cancel=None,
    usage_out: dict | None = None,
):
    """Yield text chunks for *messages*.

    *cancel* is an optional zero-argument callable; returning ``True`` stops
    the stream cleanly (the GUI uses it for its Stop button). ``usage_out`` is
    filled with token counts when the provider reports them.
    """
    url, headers, body = build_request(config, messages)
    data = json.dumps(body).encode("utf-8")
    attempt = 0
    while True:
        attempt += 1
        request = urllib.request.Request(
            url, data=data, headers=headers, method="POST"
        )
        try:
            with urllib.request.urlopen(request, timeout=config.timeout) as resp:
                yield from _iter_response(config.kind, resp, cancel, usage_out)
            return
        except urllib.error.HTTPError as exc:
            status = exc.code
            snippet = ""
            try:
                snippet = exc.read().decode("utf-8", "replace")[:400]
            except Exception:  # noqa: BLE001
                pass
            snippet = guard.redact(snippet)
            retry_after = exc.headers.get("Retry-After") if exc.headers else None
            if status in (429, 500, 502, 503, 504) and attempt == 1:
                delay = config.retry_delay
                try:
                    delay = min(float(retry_after), 10.0)
                except (TypeError, ValueError):
                    pass
                time.sleep(max(0.0, delay))
                continue
            hint = ""
            if status in (401, 403):
                hint = " — the API key was rejected; check it in Settings → AI"
            elif status == 404:
                hint = " — the model name or base URL is wrong"
            elif status == 429:
                hint = " — rate limited or out of quota"
            raise ProviderError(
                f"{status} from {config.preset_id}{hint}: {snippet}", status=status
            ) from None
        except urllib.error.URLError as exc:
            raise ProviderError(
                f"cannot reach {config.base_url}: {guard.redact(str(exc.reason))}"
            ) from None
        except TimeoutError:
            raise ProviderError(
                f"the request timed out after {config.timeout:g}s"
            ) from None


def _iter_response(kind: str, resp, cancel, usage_out: dict | None):
    for raw in resp:
        if cancel is not None and cancel():
            return
        line = raw.decode("utf-8", "replace").strip()
        if not line or line.startswith(":"):
            continue
        if line.startswith("data:"):
            line = line[5:].strip()
        if line == "[DONE]":
            return
        if not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
        except ValueError:
            continue
        text = _extract_text(kind, payload)
        if text:
            yield text
        if usage_out is not None:
            usage = _extract_usage(kind, payload)
            if usage.get("in"):
                usage_out["in"] = usage["in"]
            if usage.get("out"):
                usage_out["out"] = usage["out"]


def complete(
    config: ProviderConfig,
    messages: list[dict],
    cancel=None,
    usage_out: dict | None = None,
) -> str:
    """Blocking convenience wrapper returning the whole reply."""
    return "".join(stream_chat(config, messages, cancel=cancel, usage_out=usage_out))
