"""Meterless Runtime (Nightshift) as the model provider (LLM_PROVIDER=meterless).

Remove this package and set LLM_PROVIDER back to bedrock to take Meterless out.
"""

from __future__ import annotations

from .runtime import RuntimeStatus, TextReply, detect, probe, text_request
from .settings import MeterlessSettings, get_meterless_settings, normalize_base_url

__all__ = [
    "MeterlessSettings",
    "RuntimeStatus",
    "TextReply",
    "detect",
    "get_meterless_settings",
    "normalize_base_url",
    "probe",
    "text_request",
]
