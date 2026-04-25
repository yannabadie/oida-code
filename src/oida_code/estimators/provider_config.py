"""Phase 4.4 (QA/A20.md, ADR-29) — provider profile schema.

Frozen Pydantic shape describing one external LLM provider behind an
OpenAI-Chat-Completions-compatible interface. **No API key field.**
Keys are read at runtime from the env var named in
:attr:`ProviderProfile.api_key_env` and **never** serialized into a
profile, log, error message, or report.

Predefined profiles:

* ``deepseek`` — DeepSeek (OpenAI-compatible Chat Completions)
* ``kimi`` — Moonshot/Kimi (OpenAI-compatible Chat Completions)
* ``minimax`` — MiniMax (OpenAI-compatible Chat Completions)
* ``custom_openai_compatible`` — any third party that speaks the
  same wire format; constructor sets ``base_url`` / ``api_key_env``
  / ``default_model`` explicitly.

ADR-29 hard rules:

* No provider by default — the integrator MUST pass an explicit
  ``--provider <name>`` flag at the CLI.
* No vendor SDK at module load — the provider implementation uses
  :mod:`urllib.request` so no extra dependency is required to import
  this module.
* No streaming, no tool/function-calling, no embeddings in 4.4.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ProviderName = Literal[
    "deepseek", "kimi", "minimax", "custom_openai_compatible",
]
ApiStyle = Literal["openai_chat_completions"]


class ProviderProfile(BaseModel):
    """Configuration for one external provider.

    Frozen + ``extra="forbid"``. ADR-29 §accepted: API key is **only**
    read at runtime from ``api_key_env`` — never stored on this
    profile, never serialized, never logged.
    """

    model_config = ConfigDict(
        extra="forbid", frozen=True, validate_assignment=True,
    )

    name: ProviderName
    api_style: ApiStyle = "openai_chat_completions"
    base_url: str = Field(min_length=1)
    api_key_env: str = Field(min_length=1)
    default_model: str = Field(min_length=1)

    supports_json_mode: bool = False
    supports_json_schema: bool = False
    supports_tools: bool = False

    timeout_s: int = Field(default=60, ge=1, le=600)
    max_output_tokens: int = Field(default=4096, ge=1)
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)


_PREDEFINED: dict[ProviderName, ProviderProfile] = {
    "deepseek": ProviderProfile(
        name="deepseek",
        base_url="https://api.deepseek.com/v1",
        api_key_env="DEEPSEEK_API_KEY",
        default_model="deepseek-chat",
        supports_json_mode=True,
    ),
    "kimi": ProviderProfile(
        name="kimi",
        base_url="https://api.moonshot.cn/v1",
        api_key_env="MOONSHOT_API_KEY",
        default_model="moonshot-v1-8k",
        supports_json_mode=False,
    ),
    "minimax": ProviderProfile(
        name="minimax",
        base_url="https://api.minimax.io/v1",
        api_key_env="MINIMAX_API_KEY",
        default_model="MiniMax-Text-01",
        supports_json_mode=False,
    ),
}


def get_predefined_profile(name: ProviderName) -> ProviderProfile:
    """Return the canonical profile for ``name``.

    ``custom_openai_compatible`` is NOT in the registry — callers must
    construct it explicitly with ``base_url`` / ``api_key_env`` /
    ``default_model``.
    """
    if name == "custom_openai_compatible":
        raise KeyError(
            "custom_openai_compatible has no predefined profile; "
            "construct ProviderProfile(...) explicitly."
        )
    profile = _PREDEFINED.get(name)
    if profile is None:
        raise KeyError(f"no predefined profile for {name!r}")
    return profile


__all__ = [
    "ApiStyle",
    "ProviderName",
    "ProviderProfile",
    "get_predefined_profile",
]
