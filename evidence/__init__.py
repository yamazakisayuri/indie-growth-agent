"""Claims, sources, Critic findings, decision records, and the evidence store."""

from .factory import SUPPORTED_STORES, build_store
from .schema import (
    AnalystOutput,
    BaselineMetric,
    Claim,
    CriticFinding,
    CriticReport,
    DecisionRecord,
    Evidence,
    EvidenceRun,
    FindingResponse,
    ProposedAction,
    RevisionStep,
    TestPlan,
)
from .sql_guard import ReadOnlyQueryError, ensure_read_only
from .sqlite_store import SQLiteEvidenceStore
from .store import (
    DEFAULT_MAX_ROWS,
    Column,
    EvidenceStore,
    EvidenceStoreError,
    QueryResult,
    TableSpec,
    describe_tables,
)

__all__ = [
    "DEFAULT_MAX_ROWS",
    "SUPPORTED_STORES",
    "AnalystOutput",
    "BaselineMetric",
    "Claim",
    "Column",
    "CriticFinding",
    "CriticReport",
    "DecisionRecord",
    "Evidence",
    "EvidenceRun",
    "EvidenceStore",
    "EvidenceStoreError",
    "FindingResponse",
    "ProposedAction",
    "QueryResult",
    "ReadOnlyQueryError",
    "RevisionStep",
    "SQLiteEvidenceStore",
    "TableSpec",
    "TestPlan",
    "build_store",
    "describe_tables",
    "ensure_read_only",
]
