"""JDBC transport: the Zetaris Lightning driver jar, called in-process through JPype."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from evidence.store import QueryResult

from .settings import ZetarisSettings
from .transport import zetaris_error

DRIVER_CLASS = "com.zetaris.lightning.jdbc.LightningDriver"
_JVM_LOCK = threading.Lock()


def _jvm_path(java_home: Path | None) -> str | None:
    if java_home is None:
        return None
    for candidate in ("lib/server/libjvm.dylib", "lib/server/libjvm.so", "bin/server/jvm.dll"):
        path = java_home / candidate
        if path.is_file():
            return str(path)
    raise ValueError(f"No JVM library under ZETARIS_JAVA_HOME={java_home}")


def _start_jvm(jar: Path, java_home: Path | None) -> None:
    import jpype

    with _JVM_LOCK:
        if jpype.isJVMStarted():
            return
        jvm = _jvm_path(java_home) or jpype.getDefaultJVMPath()
        jpype.startJVM(jvm, classpath=[str(jar)], convertStrings=True)


def _to_python(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    name = str(value.getClass().getName())
    if name in ("java.lang.Long", "java.lang.Integer", "java.lang.Short", "java.lang.Byte"):
        return int(value.longValue())
    if name in ("java.lang.Double", "java.lang.Float", "java.math.BigDecimal"):
        return float(value.doubleValue())
    if name == "java.lang.Boolean":
        return bool(value.booleanValue())
    return str(value.toString())


class JdbcTransport:
    def __init__(self, settings: ZetarisSettings) -> None:
        if settings.jdbc_jar is None:
            raise ValueError("JdbcTransport needs ZETARIS_JDBC_JAR")
        _start_jvm(settings.jdbc_jar, settings.java_home)
        import jpype

        jpype.JClass(DRIVER_CLASS)
        self._timeout = settings.query_timeout_seconds
        self._lock = threading.Lock()
        try:
            self._conn = jpype.JClass("java.sql.DriverManager").getConnection(
                settings.jdbc_url, settings.user, settings.password
            )
        except Exception as exc:
            raise zetaris_error(exc) from None

    def execute(self, sql: str, *, max_rows: int) -> QueryResult:
        with self._lock:
            statement = self._conn.createStatement()
            try:
                try:
                    statement.setQueryTimeout(self._timeout)
                except Exception:
                    pass
                if not statement.execute(sql):
                    return QueryResult(columns=(), rows=(), sql=sql)
                result_set = statement.getResultSet()
                meta = result_set.getMetaData()
                count = meta.getColumnCount()
                columns = tuple(str(meta.getColumnLabel(i)) for i in range(1, count + 1))
                rows: list[tuple[Any, ...]] = []
                while len(rows) <= max_rows and result_set.next():
                    rows.append(
                        tuple(_to_python(result_set.getObject(i)) for i in range(1, count + 1))
                    )
            except Exception as exc:
                raise zetaris_error(exc) from None
            finally:
                statement.close()
        return QueryResult(
            columns=columns,
            rows=tuple(rows[:max_rows]),
            truncated=len(rows) > max_rows,
            sql=sql,
        )

    def close(self) -> None:
        with self._lock:
            self._conn.close()
