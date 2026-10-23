"""Pick the model behind every Strands Agent in this app (Analyzer, Planner, Draft).

LLM_PROVIDER selects the provider. The default, bedrock, returns None so Strands
builds its own default BedrockModel — identical to Agent() without model=.
"""

from __future__ import annotations

from strands.models import Model

from config import get_llm_provider

SUPPORTED_PROVIDERS = ("bedrock",)


def build_model() -> Model | None:
    provider = get_llm_provider()
    if provider == "bedrock":
        return None
    raise ValueError(
        f"Unsupported LLM_PROVIDER {provider!r}; "
        f"expected one of: {', '.join(SUPPORTED_PROVIDERS)}"
    )
