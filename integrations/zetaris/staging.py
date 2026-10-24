"""Put a table's CSV where the Zetaris engine can read it.

The engine cannot read files on the laptop, only its own storage (the platform's
customer-data volume locally, object storage such as S3 when hosted).
"""

from __future__ import annotations

import subprocess
from typing import Protocol

from evidence.store import EvidenceStoreError

DATA_FILE = "data.csv"


class FileStager(Protocol):
    def put(self, table: str, data: bytes) -> str:
        """Store data as the only file of this table's directory. Returns the engine-side URI."""
        ...


class DockerVolumeStager:
    """Write into the customer-data volume through the running driver container."""

    def __init__(self, container: str, root_dir: str, *, user: str = "zetaris") -> None:
        self._container = container
        self._root = root_dir.rstrip("/")
        self._user = user

    def put(self, table: str, data: bytes) -> str:
        directory = f"{self._root}/{table}"
        # The engine reads every non-dot file in the directory as table data: write to a
        # dot-file, swap it in, then drop any other data file left in the directory.
        script = (
            'umask 002; mkdir -p "$1" && cat > "$1/.$2.tmp" && mv -f "$1/.$2.tmp" "$1/$2"'
            ' && find "$1" -mindepth 1 -maxdepth 1 ! -name "$2" ! -name ".*" -exec rm -rf {} +'
        )
        try:
            proc = subprocess.run(
                [
                    "docker", "exec", "-i", "-u", self._user, self._container,
                    "sh", "-c", script, "sh", directory, DATA_FILE,
                ],
                input=data,
                capture_output=True,
                timeout=120,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise EvidenceStoreError(f"Could not stage {table} for Zetaris: {exc}") from exc
        if proc.returncode != 0:
            detail = proc.stderr.decode(errors="replace").strip()[:300]
            raise EvidenceStoreError(f"Could not stage {table} for Zetaris: {detail}")
        return f"file://{directory}"
