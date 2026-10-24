"""Pick the evidence store backend (EVIDENCE_STORE, default sqlite)."""

from __future__ import annotations

from config import get_evidence_sqlite_path, get_evidence_store_kind

from .sqlite_store import SQLiteEvidenceStore
from .store import EvidenceStore

SUPPORTED_STORES = ("sqlite", "zetaris")


def build_store() -> EvidenceStore:
    kind = get_evidence_store_kind()
    if kind == "sqlite":
        return SQLiteEvidenceStore(get_evidence_sqlite_path())
    if kind == "zetaris":
        from integrations.zetaris import build_zetaris_store

        return build_zetaris_store()
    raise ValueError(
        f"Unsupported EVIDENCE_STORE {kind!r}; expected one of: {', '.join(SUPPORTED_STORES)}"
    )
