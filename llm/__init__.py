"""Model provider selection for Strands Agents."""

from .errors import describe_model_error, find_api_error, is_retryable
from .factory import (
    SUPPORTED_PROVIDERS,
    build_model,
    describe_provider,
    meterless_model,
    model_label,
    openai_compatible_model,
)

__all__ = [
    "SUPPORTED_PROVIDERS",
    "build_model",
    "describe_model_error",
    "describe_provider",
    "find_api_error",
    "is_retryable",
    "meterless_model",
    "model_label",
    "openai_compatible_model",
]
