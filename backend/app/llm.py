"""LLM provider chain with failover.

Providers are declared in `.env` as numbered blocks and tried in order:

    LLM_PROVIDER_1_MODEL=nvidia/nemotron-3-super-120b-a12b
    LLM_PROVIDER_1_API_KEY=nvapi-…
    LLM_PROVIDER_1_BASE_URL=https://integrate.api.nvidia.com/v1
    LLM_PROVIDER_1_THINKING=false

    LLM_PROVIDER_2_MODEL=openai/gpt-oss-20b
    …

The point of the chain is that free-tier keys run out. When provider 1 is rate
limited, out of credit, or simply down, provider 2 takes the request — the
caller never sees the difference. Anything the next provider could plausibly
succeed at is a failover; a request *we* malformed is not, because retrying it
elsewhere would fail identically.

The endpoints are OpenAI-compatible, so pointing a provider at Anthropic,
OpenAI, or a local vLLM is a change to `.env`, not to this file.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from . import settings  # noqa: F401  - loads .env on import

log = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"
REQUEST_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "120"))
MAX_PROVIDERS = 8

# HTTP statuses where the *next* provider is likely to do better: quota and
# rate limits, auth problems with this particular key, and server-side faults.
FAILOVER_STATUSES = {401, 402, 403, 408, 409, 425, 429, 500, 502, 503, 504}


class LlmError(Exception):
    """Every provider in the chain failed."""


class NoProvidersConfigured(LlmError):
    pass


@dataclass
class Provider:
    name: str
    model: str
    api_key: str
    base_url: str
    thinking: bool = False
    guided_json: bool = False
    max_tokens: int = 4096
    temperature: float = 0.0

    @property
    def redacted_key(self) -> str:
        return f"{self.api_key[:8]}…{self.api_key[-4:]}" if self.api_key else "(none)"


def _flag(value: Optional[str], default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_providers(env: Optional[Dict[str, str]] = None) -> List[Provider]:
    """Read the numbered provider blocks out of the environment."""
    env = dict(os.environ if env is None else env)
    providers: List[Provider] = []
    for index in range(1, MAX_PROVIDERS + 1):
        prefix = f"LLM_PROVIDER_{index}_"
        model = env.get(f"{prefix}MODEL")
        api_key = env.get(f"{prefix}API_KEY")
        if not model or not api_key:
            continue
        providers.append(Provider(
            name=env.get(f"{prefix}NAME") or f"provider{index}:{model}",
            model=model,
            api_key=api_key,
            base_url=env.get(f"{prefix}BASE_URL") or DEFAULT_BASE_URL,
            thinking=_flag(env.get(f"{prefix}THINKING")),
            guided_json=_flag(env.get(f"{prefix}GUIDED_JSON")),
            max_tokens=int(env.get(f"{prefix}MAX_TOKENS") or 4096),
            temperature=float(env.get(f"{prefix}TEMPERATURE") or 0.0),
        ))
    return providers


def _status_of(exc: Exception) -> Optional[int]:
    status = getattr(exc, "status_code", None)
    if status is None:
        response = getattr(exc, "response", None)
        status = getattr(response, "status_code", None)
    return status


def should_failover(exc: Exception) -> bool:
    """Whether the next provider deserves a shot at this request.

    A 400 means we sent something the model rejected — the next provider would
    reject it too, so that surfaces immediately instead of burning the chain.
    """
    status = _status_of(exc)
    if status is not None:
        return status in FAILOVER_STATUSES
    # Connection resets, timeouts, DNS failures: no status, always worth
    # trying elsewhere.
    return True


class LlmClient:
    """Calls the first provider that works."""

    def __init__(self, providers: Optional[List[Provider]] = None):
        self.providers = providers if providers is not None else load_providers()
        self._clients: Dict[str, Any] = {}

    @property
    def configured(self) -> bool:
        return bool(self.providers)

    def describe(self) -> List[Dict[str, Any]]:
        """Non-secret provider summary, for /api/health."""
        return [
            {"name": p.name, "model": p.model, "base_url": p.base_url,
             "key": p.redacted_key}
            for p in self.providers
        ]

    def _client_for(self, provider: Provider):
        from openai import OpenAI  # imported lazily so the app starts without it

        if provider.name not in self._clients:
            self._clients[provider.name] = OpenAI(
                base_url=provider.base_url,
                api_key=provider.api_key,
                timeout=REQUEST_TIMEOUT,
                max_retries=0,  # the provider chain is the retry strategy
            )
        return self._clients[provider.name]

    def complete_json(self, system: str, user: str,
                      json_schema: Optional[dict] = None) -> tuple[str, Provider]:
        """Ask for a JSON object, returning (raw_text, provider_that_answered)."""
        if not self.providers:
            raise NoProvidersConfigured(
                "No LLM providers configured — set LLM_PROVIDER_1_MODEL and "
                "LLM_PROVIDER_1_API_KEY (see backend/.env.example)."
            )

        failures: List[str] = []
        for provider in self.providers:
            try:
                try:
                    text = self._call(provider, system, user, json_schema)
                except Exception as exc:  # noqa: BLE001
                    # A 400 usually means this model rejects one of the optional
                    # knobs (`response_format`, guided decoding). Retry once
                    # without them before writing the provider off — the prompt
                    # asks for JSON regardless.
                    if _status_of(exc) != 400:
                        raise
                    log.info("llm: %s rejected structured-output options, "
                             "retrying plain", provider.name)
                    text = self._call(provider, system, user, None, plain=True)
                if not text.strip():
                    raise LlmError("empty response")
                if failures:
                    log.info("llm: %s answered after %d failure(s)",
                             provider.name, len(failures))
                return text, provider
            except Exception as exc:  # noqa: BLE001 - classified just below
                status = _status_of(exc)
                failures.append(f"{provider.name}: {type(exc).__name__}"
                                f"{f' {status}' if status else ''}")
                # Never log the prompt or the response: both carry resume PII.
                log.warning("llm: %s failed (status=%s): %s",
                            provider.name, status, type(exc).__name__)
                if not should_failover(exc):
                    raise LlmError(f"{provider.name} rejected the request") from exc

        raise LlmError("all providers failed: " + "; ".join(failures))

    def _call(self, provider: Provider, system: str, user: str,
              json_schema: Optional[dict], plain: bool = False) -> str:
        if plain:
            response = self._client_for(provider).chat.completions.create(
                model=provider.model,
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": user}],
                temperature=provider.temperature,
                max_tokens=provider.max_tokens,
                stream=False,
            )
            return response.choices[0].message.content or ""

        extra_body: Dict[str, Any] = {}
        # Reasoning models expose a thinking toggle. Extraction is a
        # transcription task, not a reasoning one, so it stays off by default:
        # it only adds latency and tokens.
        if provider.thinking:
            extra_body["chat_template_kwargs"] = {"enable_thinking": True}
        else:
            extra_body["chat_template_kwargs"] = {"enable_thinking": False}
        # Guided decoding constrains output to the schema, which is far more
        # reliable than asking nicely — but support varies by model, so it is
        # opt-in per provider.
        if provider.guided_json and json_schema:
            extra_body["nvext"] = {"guided_json": json_schema}

        response = self._client_for(provider).chat.completions.create(
            model=provider.model,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
            temperature=provider.temperature,
            max_tokens=provider.max_tokens,
            response_format={"type": "json_object"},
            stream=False,
            extra_body=extra_body,
        )
        return response.choices[0].message.content or ""


_client: Optional[LlmClient] = None


def get_client() -> LlmClient:
    global _client
    if _client is None:
        _client = LlmClient()
    return _client


def reset_client() -> None:
    """Drop the cached client (used by tests after changing the environment)."""
    global _client
    _client = None
