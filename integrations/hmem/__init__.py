"""Meterless H-MEM as the decision memory (MEMORY_BACKEND=hmem).

vendor/ is the unmodified H-MEM reference and conformance suite from
github.com/Meterless/Meterless (engines/hmem @ 1742dec, Apache-2.0, see vendor/LICENSE).
Remove this package and set MEMORY_BACKEND back to none or local to take H-MEM out.
"""

from .memory import HmemMemory, HmemSettings, get_hmem_settings

__all__ = ["HmemMemory", "HmemSettings", "get_hmem_settings"]
