"""Zetaris connection settings (ZETARIS_* environment variables)."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from config import ROOT_DIR, load_env

DEFAULT_JDBC_URL = "jdbc:zetaris:lightning@localhost:10000"
DEFAULT_DATABASE = "INDIE_GROWTH"
DEFAULT_DOCKER_CONTAINER = "zetaris-driver-1"
# Inside the platform's customer-data volume; ZETARIS_LOCAL_FILE_SYTEM_ROOT_PATH points here.
DEFAULT_STAGING_DIR = "/home/zetaris/customer-data/shared/indie_growth"
DEFAULT_QUERY_TIMEOUT_SECONDS = 60
SUPPORTED_TRANSPORTS = ("jdbc",)
SUPPORTED_STAGING = ("docker",)
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class ZetarisSettings:
    user: str
    password: str
    transport: str = "jdbc"
    jdbc_url: str = DEFAULT_JDBC_URL
    jdbc_jar: Path | None = None
    java_home: Path | None = None
    database: str = DEFAULT_DATABASE
    staging: str = "docker"
    docker_container: str = DEFAULT_DOCKER_CONTAINER
    staging_dir: str = DEFAULT_STAGING_DIR
    query_timeout_seconds: int = DEFAULT_QUERY_TIMEOUT_SECONDS

    def __repr__(self) -> str:
        return (
            f"ZetarisSettings(user={self.user!r}, password='***', transport={self.transport!r}, "
            f"jdbc_url={self.jdbc_url!r}, database={self.database!r}, staging={self.staging!r})"
        )


def _optional_path(name: str) -> Path | None:
    raw = os.getenv(name, "").strip()
    if not raw:
        return None
    path = Path(raw).expanduser()
    return path if path.is_absolute() else ROOT_DIR / path


def get_zetaris_settings() -> ZetarisSettings:
    """Settings for EVIDENCE_STORE=zetaris. Raises ValueError when incomplete or invalid."""
    load_env()

    missing = [n for n in ("ZETARIS_USER", "ZETARIS_PASSWORD") if not os.getenv(n, "").strip()]
    transport = os.getenv("ZETARIS_TRANSPORT", "").strip().lower() or "jdbc"
    if transport not in SUPPORTED_TRANSPORTS:
        raise ValueError(
            f"Unsupported ZETARIS_TRANSPORT {transport!r}; expected one of: "
            + ", ".join(SUPPORTED_TRANSPORTS)
        )
    jdbc_jar = _optional_path("ZETARIS_JDBC_JAR")
    if transport == "jdbc" and jdbc_jar is None:
        missing.append("ZETARIS_JDBC_JAR")
    if missing:
        raise ValueError("EVIDENCE_STORE=zetaris needs " + ", ".join(missing))
    if jdbc_jar is not None and not jdbc_jar.is_file():
        raise ValueError(f"ZETARIS_JDBC_JAR file not found: {jdbc_jar}")

    staging = os.getenv("ZETARIS_STAGING", "").strip().lower() or "docker"
    if staging not in SUPPORTED_STAGING:
        raise ValueError(
            f"Unsupported ZETARIS_STAGING {staging!r}; expected one of: "
            + ", ".join(SUPPORTED_STAGING)
        )

    database = os.getenv("ZETARIS_DATABASE", "").strip() or DEFAULT_DATABASE
    if not _IDENTIFIER.match(database):
        raise ValueError("ZETARIS_DATABASE must use letters, digits, and underscore only")

    timeout_raw = os.getenv("ZETARIS_QUERY_TIMEOUT_SECONDS", "").strip()
    try:
        timeout = int(timeout_raw) if timeout_raw else DEFAULT_QUERY_TIMEOUT_SECONDS
    except ValueError as exc:
        raise ValueError("ZETARIS_QUERY_TIMEOUT_SECONDS must be an integer") from exc
    if timeout <= 0:
        raise ValueError("ZETARIS_QUERY_TIMEOUT_SECONDS must be > 0")

    return ZetarisSettings(
        user=os.getenv("ZETARIS_USER", "").strip(),
        password=os.getenv("ZETARIS_PASSWORD", ""),
        transport=transport,
        jdbc_url=os.getenv("ZETARIS_JDBC_URL", "").strip() or DEFAULT_JDBC_URL,
        jdbc_jar=jdbc_jar,
        java_home=_optional_path("ZETARIS_JAVA_HOME"),
        database=database,
        staging=staging,
        docker_container=os.getenv("ZETARIS_DOCKER_CONTAINER", "").strip()
        or DEFAULT_DOCKER_CONTAINER,
        staging_dir=(os.getenv("ZETARIS_STAGING_DIR", "").strip() or DEFAULT_STAGING_DIR).rstrip(
            "/"
        ),
        query_timeout_seconds=timeout,
    )
