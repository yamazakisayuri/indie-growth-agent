"""Zetaris as the evidence store (EVIDENCE_STORE=zetaris).

Remove this package and set EVIDENCE_STORE back to sqlite to take Zetaris out.
"""

from __future__ import annotations

from .settings import ZetarisSettings, get_zetaris_settings
from .staging import DockerVolumeStager, FileStager
from .store import ZetarisEvidenceStore
from .transport import ZetarisTransport


def build_transport(settings: ZetarisSettings) -> ZetarisTransport:
    if settings.transport == "jdbc":
        from .jdbc import JdbcTransport

        return JdbcTransport(settings)
    raise ValueError(f"Unsupported ZETARIS_TRANSPORT {settings.transport!r}")


def build_stager(settings: ZetarisSettings) -> FileStager:
    if settings.staging == "docker":
        return DockerVolumeStager(settings.docker_container, settings.staging_dir)
    raise ValueError(f"Unsupported ZETARIS_STAGING {settings.staging!r}")


def build_zetaris_store(settings: ZetarisSettings | None = None) -> ZetarisEvidenceStore:
    settings = settings or get_zetaris_settings()
    return ZetarisEvidenceStore(
        build_transport(settings), build_stager(settings), database=settings.database
    )


__all__ = [
    "DockerVolumeStager",
    "FileStager",
    "ZetarisEvidenceStore",
    "ZetarisSettings",
    "ZetarisTransport",
    "build_zetaris_store",
    "get_zetaris_settings",
]
