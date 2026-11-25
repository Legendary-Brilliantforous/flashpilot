"""Provider wire format + streaming tests (OpenAI-compatible and Gemini).

A local ``http.server`` stands in for the provider so the real request body,
headers and SSE parsing are exercised — no network, no mocks of urllib.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from python.core.ai import provider
from python.core.ai.provider import ProviderConfig, ProviderError


class _State:
    def __init__(self):
        self.requests: list[dict] = []
        self.status = 200
        self.chunks: list[bytes] = []
        self.content_type = "text/event-stream"


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_POST(self):  # noqa: N802 - BaseHTTPRequestHandler API
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length)
        state: _State = self.server.state  # type: ignore[attr-defined]
        state.requests.append(
            {
                "path": self.path,
                "headers": {k.lower(): v for k, v in self.headers.items()},
                "body": json.loads(raw or b"{}"),
            }
        )
        if state.status != 200:
            body = json.dumps({"error": {"message": "nope"}}).encode()
            self.send_response(state.status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(200)
        self.send_header("Content-Type", state.content_type)
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()
        try:
            for chunk in state.chunks:
                self.wfile.write(f"{len(chunk):X}\r\n".encode() + chunk + b"\r\n")
            self.wfile.write(b"0\r\n\r\n")
        except (BrokenPipeError, ConnectionResetError):
            # The cancel test closes the stream early; that is the point.
            pass

    def log_message(self, *args):  # silence the test server
        return


@pytest.fixture()
def server():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    httpd.state = _State()  # type: ignore[attr-defined]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield httpd
    finally:
        httpd.shutdown()
        httpd.server_close()


def _openai_cfg(server, **kwargs) -> ProviderConfig:
    port = server.server_address[1]
    cfg = ProviderConfig(
        preset_id="openai",
        kind="openai",
        base_url=f"http://127.0.0.1:{port}/v1",
        model="test-model",
        api_key="sk-test-key",
        retry_delay=0.0,
        **kwargs,
    )
    return cfg


def _sse(*payloads) -> list[bytes]:
    return [
        f"data: {json.dumps(p)}\n\n".encode() for p in payloads
    ] + [b"data: [DONE]\n\n"]


# --------------------------------------------------------------------------
# Presets + validation
# --------------------------------------------------------------------------

def test_presets_cover_every_shipped_endpoint():
    ids = set(provider.PRESETS)
    assert {"openai", "openrouter", "groq", "gemini", "local", "custom"} <= ids
    assert provider.PRESETS["local"].needs_key is False
    assert provider.PRESETS["gemini"].kind == "gemini"


def test_validate_reports_missing_key_and_url():
    cfg = ProviderConfig(
        preset_id="openai", kind="openai", base_url="", model=""
    )
    problems = provider.validate(cfg)
    assert any("base URL" in p for p in problems)
    assert any("model" in p for p in problems)
    assert any("API key" in p for p in problems)


def test_local_preset_needs_no_key():
    cfg = ProviderConfig.from_preset("local")
    assert provider.validate(cfg) == []
    assert cfg.is_local is True


# --------------------------------------------------------------------------
# Request building
# --------------------------------------------------------------------------

def test_openai_request_shape():
    cfg = ProviderConfig(
        preset_id="openai",
        kind="openai",
        base_url="https://api.example.test/v1",
        model="test-model",
        api_key="sk-test-key",
    )
    url, headers, body = provider.build_request(
        cfg, [{"role": "user", "content": "hi"}]
    )
    assert url.endswith("/v1/chat/completions")
    assert headers["Authorization"] == "Bearer sk-test-key"
    assert body["model"] == "test-model"
    assert body["stream"] is True
    assert body["messages"][0]["content"] == "hi"
    assert body["stream_options"] == {"include_usage": True}


def test_local_request_omits_usage_option_and_auth(server):
    cfg = ProviderConfig.from_preset("local")
    cfg.base_url = f"http://127.0.0.1:{server.server_address[1]}/v1"
    _url, headers, body = provider.build_request(
        cfg, [{"role": "user", "content": "hi"}]
    )
    assert "Authorization" not in headers
    assert "stream_options" not in body


def test_gemini_request_shape(server):
    cfg = ProviderConfig(
        preset_id="gemini",
        kind="gemini",
        base_url="https://example.test/v1beta",
        model="models/gemini-test",
        api_key="gm-key",
    )
    url, headers, body = provider.build_request(
        cfg,
        [
            {"role": "system", "content": "be brief"},
            {"role": "user", "content": "why"},
            {"role": "assistant", "content": "because"},
        ],
    )
    assert url == (
        "https://example.test/v1beta/models/gemini-test:"
        "streamGenerateContent?alt=sse"
    )
    assert headers["x-goog-api-key"] == "gm-key"
    assert body["systemInstruction"]["parts"][0]["text"] == "be brief"
    assert [c["role"] for c in body["contents"]] == ["user", "model"]


# --------------------------------------------------------------------------
# Streaming
# --------------------------------------------------------------------------

def test_openai_stream_collects_text_and_usage(server):
    server.state.chunks = _sse(
        {"choices": [{"delta": {"content": "Hello"}}]},
        {"choices": [{"delta": {"content": " world"}}]},
        {"choices": [], "usage": {"prompt_tokens": 12, "completion_tokens": 3}},
    )
    usage: dict = {}
    text = provider.complete(
        _openai_cfg(server),
        [{"role": "user", "content": "say hi"}],
        usage_out=usage,
    )
    assert text == "Hello world"
    assert usage == {"in": 12, "out": 3}
    assert server.state.requests[0]["body"]["stream"] is True


def test_gemini_stream_collects_text(server):
    server.state.chunks = _sse(
        {"candidates": [{"content": {"parts": [{"text": "BROM"}]}}]},
        {"candidates": [{"content": {"parts": [{"text": " mode"}]}}]},
    )
    cfg = ProviderConfig(
        preset_id="gemini",
        kind="gemini",
        base_url=f"http://127.0.0.1:{server.server_address[1]}/v1beta",
        model="gemini-test",
        api_key="gm-key",
    )
    assert provider.complete(cfg, [{"role": "user", "content": "x"}]) == "BROM mode"


def test_non_streaming_json_reply_is_accepted(server):
    server.state.content_type = "application/json"
    server.state.chunks = [
        json.dumps(
            {"choices": [{"message": {"content": "plain reply"}}]}
        ).encode()
    ]
    assert (
        provider.complete(_openai_cfg(server), [{"role": "user", "content": "x"}])
        == "plain reply"
    )


def test_cancel_stops_the_stream(server):
    server.state.chunks = _sse(
        {"choices": [{"delta": {"content": "one"}}]},
        {"choices": [{"delta": {"content": "two"}}]},
    )
    seen = []

    def cancel():
        return len(seen) >= 1

    for piece in provider.stream_chat(
        _openai_cfg(server), [{"role": "user", "content": "x"}], cancel=cancel
    ):
        seen.append(piece)
    assert seen == ["one"]


def test_401_raises_with_key_hint_and_redacts(server):
    server.state.status = 401
    with pytest.raises(ProviderError) as exc:
        provider.complete(_openai_cfg(server), [{"role": "user", "content": "x"}])
    assert exc.value.status == 401
    assert "API key" in str(exc.value)


def test_429_is_retried_once(server):
    calls = {"n": 0}

    class _Flaky(_Handler):
        def do_POST(self):  # noqa: N802
            calls["n"] += 1
            if calls["n"] == 1:
                self.send_response(429)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            super().do_POST()

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Flaky)
    httpd.state = _State()
    httpd.state.chunks = _sse({"choices": [{"delta": {"content": "ok"}}]})
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        cfg = ProviderConfig(
            preset_id="openai",
            kind="openai",
            base_url=f"http://127.0.0.1:{httpd.server_address[1]}/v1",
            model="m",
            api_key="k",
            retry_delay=0.0,
        )
        assert provider.complete(cfg, [{"role": "user", "content": "x"}]) == "ok"
        assert calls["n"] == 2
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_unreachable_endpoint_raises_provider_error():
    cfg = ProviderConfig(
        preset_id="custom",
        kind="openai",
        base_url="http://127.0.0.1:1/v1",
        model="m",
        api_key="k",
        timeout=1.0,
    )
    with pytest.raises(ProviderError) as exc:
        provider.complete(cfg, [{"role": "user", "content": "x"}])
    assert "cannot reach" in str(exc.value)
