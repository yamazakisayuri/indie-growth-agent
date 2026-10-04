"""Parse AdMob networkReport:generate response bodies."""

from __future__ import annotations

import json
from typing import Any, Iterator


def each_admob_stream_message(text: str) -> Iterator[dict[str, Any]]:
    """Yield message objects from a JSON array, single object, or NDJSON body."""
    trimmed = text.strip()
    if not trimmed:
        return

    try:
        parsed: Any = json.loads(trimmed)
    except json.JSONDecodeError:
        parsed = None

    if isinstance(parsed, list):
        for item in parsed:
            if isinstance(item, dict):
                yield item
        return
    if isinstance(parsed, dict):
        yield parsed
        return

    for line in trimmed.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            yield item
