"""Local-first model router for BAY-E.

Supported providers:
- OpenAI Responses API (server-side, optional)
- llama.cpp OpenAI-compatible server (/v1/chat/completions)
- Ollama (/api/chat)
- deterministic fallback

Secrets are read only from server-side environment variables.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
import urllib.error
import urllib.request
import time
from typing import Any, Protocol

from app.core.guardian import GUARDIAN
from app.core import db


@dataclass(slots=True)
class ModelReply:
    text: str
    provider: str
    model: str
    degraded: bool = False


class Provider(Protocol):
    name: str
    def generate(self, messages: list[dict[str, str]], *, temperature: float = 0.6) -> ModelReply: ...


def _post_json(url: str, payload: dict[str, Any], timeout: float = 12.0, headers: dict[str, str] | None = None) -> dict[str, Any]:
    req_headers = {"Content-Type": "application/json", **(headers or {})}
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=req_headers,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


class OpenAIProvider:
    name = "openai"

    def __init__(self, config: dict | None = None) -> None:
        config = config or {}
        self.base = str(config.get("openai_url") or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")).rstrip("/")
        self.model = str(config.get("openai_model") or os.getenv("BAYE_OPENAI_MODEL", "gpt-6-luna"))
        self.api_key = os.getenv("OPENAI_API_KEY", "").strip()

    def generate(self, messages: list[dict[str, str]], *, temperature: float = 0.6) -> ModelReply:
        if not self.api_key:
            raise OSError("OPENAI_API_KEY is not configured")

        instructions = "\n\n".join(
            m.get("content", "") for m in messages if m.get("role") == "system"
        ).strip()
        input_items = [
            {"role": m["role"], "content": m.get("content", "")}
            for m in messages if m.get("role") in ("user", "assistant")
        ]

        payload: dict[str, Any] = {
            "model": self.model,
            "input": input_items,
            "store": False,
        }
        if instructions:
            payload["instructions"] = instructions

        data = _post_json(
            f"{self.base}/responses",
            payload,
            timeout=float(os.getenv("BAYE_OPENAI_TIMEOUT", "30")),
            headers={"Authorization": f"Bearer {self.api_key}"},
        )

        text = str(data.get("output_text") or "").strip()
        if not text:
            chunks: list[str] = []
            for item in data.get("output", []) or []:
                for part in item.get("content", []) or []:
                    if part.get("type") in ("output_text", "text") and part.get("text"):
                        chunks.append(str(part["text"]))
            text = "\n".join(chunks).strip()
        if not text:
            raise ValueError("OpenAI response contained no text")
        return ModelReply(text=text, provider=self.name, model=self.model)


class LlamaCppProvider:
    name = "llama.cpp"

    def __init__(self, config: dict | None = None) -> None:
        config = config or {}
        self.base = str(config.get("llama_url") or os.getenv("BAYE_LLAMA_URL", "http://127.0.0.1:8080")).rstrip("/")
        self.model = str(config.get("llama_model") or os.getenv("BAYE_LLAMA_MODEL", "local"))

    def generate(self, messages: list[dict[str, str]], *, temperature: float = 0.6) -> ModelReply:
        data = _post_json(
            f"{self.base}/v1/chat/completions",
            {"model": self.model, "messages": messages, "temperature": temperature, "stream": False},
        )
        text = data["choices"][0]["message"]["content"].strip()
        return ModelReply(text=text, provider=self.name, model=self.model)


class OllamaProvider:
    name = "ollama"

    def __init__(self, config: dict | None = None) -> None:
        config = config or {}
        self.base = str(config.get("ollama_url") or os.getenv("BAYE_OLLAMA_URL", "http://127.0.0.1:11434")).rstrip("/")
        self.model = str(config.get("ollama_model") or os.getenv("BAYE_OLLAMA_MODEL", "qwen2.5:3b"))

    def generate(self, messages: list[dict[str, str]], *, temperature: float = 0.6) -> ModelReply:
        data = _post_json(
            f"{self.base}/api/chat",
            {"model": self.model, "messages": messages, "stream": False, "options": {"temperature": temperature}},
        )
        text = data["message"]["content"].strip()
        return ModelReply(text=text, provider=self.name, model=self.model)


class FallbackProvider:
    name = "fallback"
    model = "deterministic"

    def generate(self, messages: list[dict[str, str]], *, temperature: float = 0.0) -> ModelReply:
        user = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
        return ModelReply(
            text=(
                "Te escucho. Mi modelo local todavía no está disponible, así que no voy a inventar una respuesta. "
                f"Puedo guardar, buscar o relacionar lo que me digas mientras tanto."
                if user else
                "Estoy disponible."
            ),
            provider=self.name,
            model=self.model,
            degraded=True,
        )


class ModelRouter:
    def __init__(self) -> None:
        self.providers: list[Provider] = []
        self.fallback = FallbackProvider()
        self.last_provider = "fallback"
        self._fingerprint = ""
        self._failed_until: dict[str, float] = {}
        self.configure({})

    def configure(self, config: dict | None) -> None:
        config = dict(config or {})
        order_value = str(config.get("provider_order") or os.getenv("BAYE_MODEL_ORDER", "openai,llama.cpp,ollama"))
        known = {"openai": OpenAIProvider, "llama.cpp": LlamaCppProvider, "ollama": OllamaProvider}
        self.providers = [known[n.strip()](config) for n in order_value.split(",") if n.strip() in known]
        self._fingerprint = json.dumps(config, sort_keys=True, ensure_ascii=False)

    def _refresh_config(self) -> None:
        try:
            config = db.get_setting("settings:ai", {}) or {}
            fp = json.dumps(config, sort_keys=True, ensure_ascii=False)
            if fp != self._fingerprint:
                self.configure(config)
        except Exception:
            pass

    def status(self) -> dict:
        self._refresh_config()
        return {
            "last_provider": self.last_provider,
            "providers": [{
                "name": p.name,
                "model": getattr(p, "model", ""),
                "base": getattr(p, "base", ""),
                "configured": bool(getattr(p, "api_key", True)),
            } for p in self.providers],
            "fallback": self.fallback.name,
        }

    def generate(self, messages: list[dict[str, str]], *, temperature: float = 0.6) -> ModelReply:
        self._refresh_config()
        now = time.time()
        for provider in self.providers:
            if self._failed_until.get(provider.name, 0.0) > now:
                continue
            try:
                out = provider.generate(messages, temperature=temperature)
                self.last_provider = out.provider
                self._failed_until.pop(provider.name, None)
                GUARDIAN.report("model", "ok", f"{out.provider}:{out.model}")
                return out
            except (OSError, KeyError, ValueError, urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
                GUARDIAN.report("model", "degraded", f"{provider.name}: {exc!r}")
                self._failed_until[provider.name] = time.time() + 30.0
                continue
        out = self.fallback.generate(messages)
        self.last_provider = out.provider
        return out


MODELS = ModelRouter()