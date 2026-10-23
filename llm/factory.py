"""Pick the model behind every Strands Agent in this app (Analyzer, Planner, Draft).

LLM_PROVIDER selects the provider. The default, bedrock, returns None so Strands
builds its own default BedrockModel — identical to Agent() without model=.
"""

from __future__ import annotations

from strands.models import Model

from config import (
    OpenAICompatibleSettings,
    get_llm_provider,
    get_openai_compatible_settings,
)

SUPPORTED_PROVIDERS = ("bedrock", "openai_compatible")


def openai_compatible_model(settings: OpenAICompatibleSettings) -> Model:
    # Imported lazily: the openai package is only needed off the Bedrock path.
    from strands.models.openai import OpenAIModel

    return OpenAIModel(
        client_args={
            "base_url": settings.base_url,
            "api_key": settings.api_key,
            "default_headers": dict(settings.headers),
            "timeout": settings.timeout_seconds,
        },
        model_id=settings.model_id,
    )


def build_model() -> Model | None:
    provider = get_llm_provider()
    if provider == "bedrock":
        return None
    if provider == "openai_compatible":
        return openai_compatible_model(get_openai_compatible_settings())
    raise ValueError(
        f"Unsupported LLM_PROVIDER {provider!r}; "
        f"expected one of: {', '.join(SUPPORTED_PROVIDERS)}"
    )
