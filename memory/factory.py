"""Pick the decision memory backend (MEMORY_BACKEND, default none)."""

from __future__ import annotations

from config import get_memory_backend, get_memory_local_dir

from .base import DecisionMemory
from .local_memory import LocalMemory
from .null_memory import NullMemory

SUPPORTED_BACKENDS = ("none", "local", "hmem")


def build_memory() -> DecisionMemory:
    backend = get_memory_backend()
    if backend == "none":
        return NullMemory()
    if backend == "local":
        return LocalMemory(get_memory_local_dir())
    if backend == "hmem":
        from integrations.hmem import HmemMemory

        return HmemMemory()
    raise ValueError(
        f"Unsupported MEMORY_BACKEND {backend!r}; expected one of: {', '.join(SUPPORTED_BACKENDS)}"
    )
