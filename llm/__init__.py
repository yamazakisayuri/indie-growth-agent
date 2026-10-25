"""Model provider selection for Strands Agents."""

from .errors import (
    ModelErrorSummary,
    describe_model_error,
    find_api_error,
    is_retryable,
    summarize_model_error,
)
from .factory import (
    SUPPORTED_PROVIDERS,
    build_model,
    describe_provider,
    meterless_model,
    model_label,
    openai_compatible_model,
)

__all__ = [
    "ModelErrorSummary",
    "SUPPORTED_PROVIDERS",
    "build_model",
    "describe_model_error",
    "describe_provider",
    "find_api_error",
    "is_retryable",
    "meterless_model",
    "model_label",
    "openai_compatible_model",
    "summarize_model_error",
]
