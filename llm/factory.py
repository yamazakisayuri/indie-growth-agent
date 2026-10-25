"""Pick the model behind every Strands Agent in this app (Analyzer, Planner, Draft).

LLM_PROVIDER selects the provider. The default, bedrock, returns None so Strands
builds its own default BedrockModel — identical to Agent() without model=.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from strands.models import Model

from config import (
    OpenAICompatibleSettings,
    get_llm_provider,
    get_openai_compatible_settings,
)

if TYPE_CHECKING:
    from integrations.meterless import MeterlessSettings

SUPPORTED_PROVIDERS = ("bedrock", "openai_compatible", "meterless")


def _retry_args(sdk_retries: int | None) -> dict[str, int]:
    return {} if sdk_retries is None else {"max_retries": sdk_retries}


def openai_compatible_model(
    settings: OpenAICompatibleSettings, *, sdk_retries: int | None = None
) -> Model:
    # Imported lazily: the openai package is only needed off the Bedrock path.
    from strands.models.openai import OpenAIModel

    return OpenAIModel(
        client_args={
            "base_url": settings.base_url,
            "api_key": settings.api_key,
            "default_headers": dict(settings.headers),
            "timeout": settings.timeout_seconds,
            **_retry_args(sdk_retries),
        },
        model_id=settings.model_id,
    )


def meterless_model(settings: MeterlessSettings, *, sdk_retries: int | None = None) -> Model:
    from strands.models.openai import OpenAIModel

    return OpenAIModel(
        client_args={
            "base_url": settings.base_url,
            "api_key": settings.token,
            "default_headers": settings.headers(),
            "timeout": settings.timeout_seconds,
            **_retry_args(sdk_retries),
        },
        model_id=settings.model_id,
    )


def build_model(*, sdk_retries: int | None = None) -> Model | None:
    """sdk_retries: the openai client's max_retries; None keeps the SDK default (2).

    The SDK retries a request that timed out before its first byte, so with a long
    timeout each retry can add a full timeout of silent waiting. Bedrock ignores it.
    """
    provider = get_llm_provider()
    if provider == "bedrock":
        return None
    if provider == "openai_compatible":
        return openai_compatible_model(get_openai_compatible_settings(), sdk_retries=sdk_retries)
    if provider == "meterless":
        from integrations.meterless import get_meterless_settings

        return meterless_model(get_meterless_settings(), sdk_retries=sdk_retries)
    raise ValueError(
        f"Unsupported LLM_PROVIDER {provider!r}; "
        f"expected one of: {', '.join(SUPPORTED_PROVIDERS)}"
    )


def model_label() -> str:
    """provider:model for traces, e.g. meterless:nvidia/nemotron-3-ultra-550b-a55b."""
    provider = get_llm_provider()
    if provider == "openai_compatible":
        return f"openai_compatible:{get_openai_compatible_settings().model_id}"
    if provider == "meterless":
        from integrations.meterless import get_meterless_settings

        return f"meterless:{get_meterless_settings().model_id}"
    return provider


def describe_provider() -> str:
    """One log line naming the provider and where requests go. Never includes a key."""
    provider = get_llm_provider()
    if provider == "meterless":
        from integrations.meterless import get_meterless_settings

        s = get_meterless_settings()
        return (
            f"meterless (Meterless Nightshift runtime) base_url={s.base_url} "
            f"model={s.model_id} meterless-app={s.app} timeout={s.timeout_seconds:g}s"
        )
    if provider == "openai_compatible":
        s = get_openai_compatible_settings()
        return f"openai_compatible base_url={s.base_url} model={s.model_id}"
    return provider
