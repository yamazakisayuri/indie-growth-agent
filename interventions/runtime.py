"""Side effects shared by the CLI and the API: open the evidence store, sync memory.

Neither may stop a lifecycle change from being recorded; failures come back as warnings.
"""

from __future__ import annotations

from evidence import build_store
from evidence.store import EvidenceStore
from memory import build_memory
from product_config import load_product_by_id

from .ledger import InterventionLedger
from .memory_link import sync_memory
from .schema import Intervention


def open_store() -> tuple[EvidenceStore | None, str | None]:
    """The configured evidence store, or (None, warning) when it cannot be opened."""
    try:
        return build_store(), None
    except Exception as exc:  # noqa: BLE001 — the change is recorded without numbers
        return None, f"evidence store unavailable, nothing measured ({exc})"


def product_app_id(product_id: str) -> str | None:
    return load_product_by_id(product_id).app_store.app_id


def sync_memory_safely(
    ledger: InterventionLedger, item: Intervention
) -> tuple[Intervention, str | None]:
    """Copy into decision memory; the ledger already holds the change if this fails."""
    try:
        memory = build_memory()
    except Exception as exc:  # noqa: BLE001
        return item, f"decision memory unavailable ({type(exc).__name__}: {exc})"
    try:
        return sync_memory(ledger, memory, item), None
    except Exception as exc:  # noqa: BLE001
        return item, (
            f"decision memory not updated ({type(exc).__name__}: {exc}); run sync-memory later"
        )
    finally:
        memory.close()
