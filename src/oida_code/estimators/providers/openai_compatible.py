"""Phase 4.4 (QA/A20.md, ADR-29) — OpenAI-compatible provider.

Speaks the OpenAI Chat Completions wire format
(``POST {base_url}/chat/completions`` with ``Bearer <key>``). DeepSeek,
Moonshot/Kimi, MiniMax, and several others document compatible
endpoints; the same adapter handles all three by changing
:class:`ProviderProfile`.

ADR-29 hard rules captured here:

* No external call unless the CLI passes ``--provider <name>``.
* API key is read **lazily** from the env var named in the profile
  (``api_key_env``); a missing var raises
  :class:`LLMProviderUnavailable` with a remediation message that
  NEVER echoes the key.
* Any exception bubbling up from the HTTP layer is **redacted** for
  the API key value before being wrapped in
  :class:`LLMProviderError`.
* ``timeout`` mandatory on every HTTP call.
* No streaming, no tools, no embeddings.
* Tests inject a fake HTTP transport via the ``http_post`` constructor
  argument so pytest never makes a real network call.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from oida_code.estimators.llm_provider import (
    LLMProviderError,
    LLMProviderInvalidResponse,
    LLMProviderTimeout,
    LLMProviderUnavailable,
)
from oida_code.estimators.provider_config import ProviderProfile


class ProviderRawResponse(BaseModel):
    """Output of one provider call.

    Frozen + ``extra="forbid"``. The full prompt is **not** stored
    here; only its SHA256 hash. Use the ``content`` field for the
    JSON payload the runner is going to validate against
    :class:`LLMEstimatorOutput` (or any other schema).
    """

    model_config = ConfigDict(
        extra="forbid", frozen=True, validate_assignment=True,
    )

    content: str
    prompt_sha256: str = Field(min_length=64, max_length=64)
    model: str
    response_id: str | None = None
    finish_reason: str | None = None
    usage_prompt_tokens: int | None = None
    usage_completion_tokens: int | None = None


class ProviderRedactedIO(BaseModel):
    """Phase 4.8-A (QA/A25.md, ADR-33) — opt-in redacted-only
    capture of one provider call for post-hoc label diagnosis.

    Frozen + ``extra="forbid"``. NEVER carries:

    * the raw prompt (only ``prompt_sha256``)
    * the API key value (``redact_secret`` is applied to
      ``redacted_response_body`` before it lands here)
    * any other secret-like content the operator passes in env

    The runner writes one of these per provider call to
    ``<out>/<provider>/redacted_io/<case_id>.json`` ONLY when the
    operator passed ``--store-redacted-provider-io`` to the CLI.
    """

    model_config = ConfigDict(
        extra="forbid", frozen=True, validate_assignment=True,
    )

    case_id: str | None = None
    prompt_sha256: str = Field(min_length=64, max_length=64)
    redacted_response_body: str
    model: str
    http_status: int
    wall_clock_ms: int
    response_id: str | None = None
    finish_reason: str | None = None
    usage_prompt_tokens: int | None = None
    usage_completion_tokens: int | None = None


@dataclass(frozen=True)
class HttpRequest:
    """Inputs the HTTP transport sees. ``json_body`` is the dict the
    transport will serialize. ``headers`` MUST include any auth header
    the provider needs."""

    url: str
    headers: Mapping[str, str]
    json_body: Mapping[str, Any]
    timeout_s: int


@dataclass(frozen=True)
class HttpResponse:
    """Output of one HTTP call. ``status_code=0`` means transport
    error (no response received)."""

    status_code: int
    body: str
    error: str | None = None


HttpPostFn = Callable[[HttpRequest], HttpResponse]
"""Single-shot HTTP POST signature. Tests inject a fake; production
uses :func:`default_urllib_post`."""


def default_urllib_post(req: HttpRequest) -> HttpResponse:
    """Default HTTP transport. Uses :mod:`urllib.request` so the
    provider has no extra dependency. Returns ``HttpResponse`` even
    on transport errors so the caller never sees a raw exception."""
    import urllib.error
    import urllib.request

    body_bytes = json.dumps(dict(req.json_body)).encode("utf-8")
    request = urllib.request.Request(
        req.url, data=body_bytes, method="POST",
    )
    for key, value in req.headers.items():
        request.add_header(key, value)
    try:
        with urllib.request.urlopen(
            request, timeout=req.timeout_s,
        ) as resp:
            payload = resp.read().decode("utf-8", errors="replace")
            return HttpResponse(status_code=resp.status, body=payload)
    except urllib.error.HTTPError as exc:
        try:
            err_body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            err_body = ""
        return HttpResponse(
            status_code=exc.code, body=err_body, error=str(exc),
        )
    except urllib.error.URLError as exc:
        return HttpResponse(status_code=0, body="", error=str(exc.reason))
    except TimeoutError as exc:
        return HttpResponse(status_code=0, body="", error=f"timeout: {exc}")
    except OSError as exc:
        return HttpResponse(status_code=0, body="", error=f"os error: {exc}")


def redact_secret(text: str, secret: str | None) -> str:
    """Replace ``secret`` (when non-empty) with ``[REDACTED]`` in
    ``text``. Used by the provider whenever it surfaces an exception
    or HTTP body that might contain the key."""
    if not text or not secret:
        return text
    return text.replace(secret, "[REDACTED]")


@dataclass
class OpenAICompatibleChatProvider:
    """One provider call over OpenAI Chat Completions wire format.

    Implements the :class:`~oida_code.estimators.llm_provider.LLMProvider`
    Protocol — its ``estimate(prompt, *, timeout_s)`` returns the
    JSON content string the existing runner expects, so
    :func:`run_llm_estimator` accepts it transparently.

    Phase 4.8-A: when ``capture_redacted_io=True`` the provider also
    stashes a frozen :class:`ProviderRedactedIO` after each call;
    the runner reads it via :meth:`pop_last_redacted_io` and writes
    it under ``<out>/<provider>/redacted_io/`` when
    ``--store-redacted-provider-io`` is set on the CLI. The
    redaction happens INSIDE this dataclass — the API key value
    never travels into the runner.
    """

    profile: ProviderProfile
    http_post: HttpPostFn = field(default=default_urllib_post)
    capture_redacted_io: bool = False
    _last_redacted_io: ProviderRedactedIO | None = field(
        default=None, init=False, repr=False, compare=False,
    )

    def estimate(self, prompt: str, *, timeout_s: int) -> str:
        """LLMProvider Protocol — returns the JSON content string."""
        return self.complete_json(prompt, timeout_s=timeout_s).content

    def pop_last_redacted_io(self) -> ProviderRedactedIO | None:
        """Return the redacted-IO captured by the most recent
        ``complete_json`` call (or ``None`` if capture is disabled
        or no call has happened). Clears the slot so the next call
        starts fresh."""
        out = self._last_redacted_io
        self._last_redacted_io = None
        return out

    def complete_json(
        self, prompt: str, *, timeout_s: int | None = None,
    ) -> ProviderRawResponse:
        """Run one chat-completions call and return a frozen
        :class:`ProviderRawResponse`.

        Failure modes (all wrapped — never raise raw vendor errors):

        * env var missing → :class:`LLMProviderUnavailable`
        * status 0 (transport error) → :class:`LLMProviderUnavailable`
          (or :class:`LLMProviderTimeout` if the error string
          contains ``timeout``)
        * status >= 400 → :class:`LLMProviderError` with the body
          truncated and the API key redacted
        * non-JSON or missing ``choices[0].message.content`` →
          :class:`LLMProviderInvalidResponse`
        """
        api_key = os.environ.get(self.profile.api_key_env)
        if not api_key:
            raise LLMProviderUnavailable(
                f"missing env var {self.profile.api_key_env}; "
                "Phase 4.4 requires an explicit API key in the "
                "environment AND --provider opt-in."
            )
        effective_timeout = timeout_s if timeout_s is not None else self.profile.timeout_s
        url = self.profile.base_url.rstrip("/") + "/chat/completions"
        body: dict[str, Any] = {
            "model": self.profile.default_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.profile.temperature,
            "max_tokens": self.profile.max_output_tokens,
        }
        if self.profile.supports_json_mode:
            body["response_format"] = {"type": "json_object"}

        req = HttpRequest(
            url=url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json_body=body,
            timeout_s=effective_timeout,
        )
        # Phase 4.8-A — measure wall-clock around the HTTP call so
        # the redacted-IO can record how long the provider took.
        import time
        t_start = time.perf_counter()
        try:
            resp = self.http_post(req)
        except Exception as exc:
            # Defensive: a faulty transport must NEVER leak the key.
            msg = redact_secret(f"{type(exc).__name__}: {exc}", api_key)
            raise LLMProviderError(f"http transport error: {msg}") from None
        wall_clock_ms = int((time.perf_counter() - t_start) * 1000)

        prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()

        if resp.status_code == 0:
            err = redact_secret(resp.error or "transport failure", api_key)
            if "timeout" in err.lower():
                raise LLMProviderTimeout(f"http timeout: {err}")
            raise LLMProviderUnavailable(f"http transport error: {err}")
        if resp.status_code >= 400:
            body_excerpt = redact_secret(resp.body[:400], api_key)
            raise LLMProviderError(
                f"http {resp.status_code}: {body_excerpt}"
            )

        try:
            decoded = json.loads(resp.body)
        except json.JSONDecodeError as exc:
            raise LLMProviderInvalidResponse(
                f"non-JSON body: {exc.msg} (offset {exc.pos})"
            ) from None
        if not isinstance(decoded, dict):
            raise LLMProviderInvalidResponse(
                f"top-level body is not a JSON object "
                f"(type={type(decoded).__name__})"
            )

        choices = decoded.get("choices")
        if not isinstance(choices, list) or not choices:
            raise LLMProviderInvalidResponse(
                "response has no 'choices' array"
            )
        first = choices[0]
        if not isinstance(first, dict):
            raise LLMProviderInvalidResponse("choices[0] is not an object")
        message = first.get("message")
        if not isinstance(message, dict):
            raise LLMProviderInvalidResponse(
                "choices[0].message is missing"
            )
        content = message.get("content")
        if not isinstance(content, str):
            raise LLMProviderInvalidResponse(
                "choices[0].message.content is not a string"
            )

        raw_usage = decoded.get("usage")
        usage: dict[str, Any] = raw_usage if isinstance(raw_usage, dict) else {}
        prompt_tokens_raw = usage.get("prompt_tokens")
        completion_tokens_raw = usage.get("completion_tokens")
        result_model = str(
            decoded.get("model") or self.profile.default_model,
        )
        result_response_id = (
            str(decoded.get("id")) if decoded.get("id") else None
        )
        result_finish_reason = (
            str(first.get("finish_reason"))
            if first.get("finish_reason") is not None else None
        )
        result_prompt_tokens = (
            int(prompt_tokens_raw)
            if isinstance(prompt_tokens_raw, (int, float))
            else None
        )
        result_completion_tokens = (
            int(completion_tokens_raw)
            if isinstance(completion_tokens_raw, (int, float))
            else None
        )
        # Phase 4.8-A — opt-in redacted IO capture. Redaction happens
        # HERE because the API key value is in scope only inside this
        # method; the runner must never see the key. The full
        # response body is captured AFTER `redact_secret(body, key)`
        # so a provider that echoes auth-related state in 401-style
        # bodies still has the key value scrubbed.
        if self.capture_redacted_io:
            self._last_redacted_io = ProviderRedactedIO(
                prompt_sha256=prompt_hash,
                redacted_response_body=redact_secret(resp.body, api_key),
                model=result_model,
                http_status=resp.status_code,
                wall_clock_ms=wall_clock_ms,
                response_id=result_response_id,
                finish_reason=result_finish_reason,
                usage_prompt_tokens=result_prompt_tokens,
                usage_completion_tokens=result_completion_tokens,
            )
        return ProviderRawResponse(
            content=content,
            prompt_sha256=prompt_hash,
            model=result_model,
            response_id=result_response_id,
            finish_reason=result_finish_reason,
            usage_prompt_tokens=result_prompt_tokens,
            usage_completion_tokens=result_completion_tokens,
        )


__all__ = [
    "HttpPostFn",
    "HttpRequest",
    "HttpResponse",
    "OpenAICompatibleChatProvider",
    "ProviderRawResponse",
    "ProviderRedactedIO",
    "default_urllib_post",
    "redact_secret",
]
