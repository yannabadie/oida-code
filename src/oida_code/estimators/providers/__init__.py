"""Phase 4.4 (QA/A20.md, ADR-29) — real provider bindings.

Sub-modules:

* :mod:`oida_code.estimators.providers.openai_compatible` —
  ``OpenAICompatibleChatProvider`` for DeepSeek / Kimi / MiniMax /
  any third party speaking OpenAI Chat Completions on the wire.

**No external call by default.** The CLI must pass an explicit
``--provider <name>`` flag AND the corresponding ``api_key_env`` MUST
be set in the environment. Tests inject a fake HTTP transport so no
real network call is ever made under pytest.
"""

from oida_code.estimators.providers.openai_compatible import (
    HttpPostFn,
    OpenAICompatibleChatProvider,
    ProviderRawResponse,
    redact_secret,
)

__all__ = [
    "HttpPostFn",
    "OpenAICompatibleChatProvider",
    "ProviderRawResponse",
    "redact_secret",
]
