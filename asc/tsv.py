"""Parse and aggregate Apple Analytics TSV reports."""

from __future__ import annotations

from dataclasses import dataclass, field


def parse_tsv(text: str) -> list[dict[str, str]]:
    lines = [line for line in text.splitlines() if line]
    if len(lines) < 2:
        return []
    headers = [h.strip() for h in lines[0].split("\t")]
    rows: list[dict[str, str]] = []
    for line in lines[1:]:
        cols = line.split("\t")
        row = {headers[i]: (cols[i].strip() if i < len(cols) else "") for i in range(len(headers))}
        rows.append(row)
    return rows


def tsv_field(row: dict[str, str], *names: str) -> str:
    for name in names:
        if name in row:
            return row[name].strip()
    lower = {k.strip().lower(): v.strip() for k, v in row.items()}
    for name in names:
        value = lower.get(name.strip().lower())
        if value is not None:
            return value
    return ""


def parse_count(value: str) -> int:
    try:
        n = int(value.replace(",", ""))
    except ValueError:
        return 0
    return n if n > 0 else 0


def is_first_time_download(value: str) -> bool:
    t = " ".join(value.strip().lower().split())
    if "download" not in t:
        return False
    return "first-time" in t or "first time" in t or "first-time download" in t


def map_source_bucket(source_type: str) -> str | None:
    s = source_type.strip()
    if s == "App Store search":
        return "search"
    if s == "App Store browse":
        return "browse"
    if s in {"App referrer", "Web referrer"}:
        return "referrer"
    return None


@dataclass
class DailyMetrics:
    date: str
    impressions: int = 0
    product_page_views: int = 0
    first_time_downloads: int = 0
    impressions_by_source: dict[str, int] = field(default_factory=dict)
    downloads_by_source: dict[str, int] = field(default_factory=dict)

    def add_impression(self, n: int, source_type: str) -> None:
        if n <= 0:
            return
        self.impressions += n
        bucket = map_source_bucket(source_type)
        if bucket:
            self.impressions_by_source[bucket] = self.impressions_by_source.get(bucket, 0) + n

    def add_page_view(self, n: int) -> None:
        if n > 0:
            self.product_page_views += n

    def add_download(self, n: int, source_type: str) -> None:
        if n <= 0:
            return
        self.first_time_downloads += n
        bucket = map_source_bucket(source_type)
        if bucket:
            self.downloads_by_source[bucket] = self.downloads_by_source.get(bucket, 0) + n


def _match_territory(territory: str, territory_filter: str) -> bool:
    tf = territory_filter.strip().upper()
    if not tf or tf == "ALL":
        return True
    return territory.strip().upper() == tf


def aggregate_discovery(text: str, territory_filter: str) -> dict[str, DailyMetrics]:
    by_date: dict[str, DailyMetrics] = {}
    for row in parse_tsv(text):
        territory = tsv_field(row, "Territory")
        if not _match_territory(territory, territory_filter):
            continue
        date = tsv_field(row, "Date")
        if len(date) != 10:
            continue
        event = tsv_field(row, "Event")
        page_type = tsv_field(row, "Page Type")
        source_type = tsv_field(row, "Source Type")
        n = parse_count(tsv_field(row, "Counts", "Count"))
        metrics = by_date.setdefault(date, DailyMetrics(date=date))
        if event == "Impression":
            metrics.add_impression(n, source_type)
        elif event == "Page view" and page_type == "Product page":
            metrics.add_page_view(n)
    return by_date


def aggregate_downloads(text: str, territory_filter: str) -> dict[str, DailyMetrics]:
    by_date: dict[str, DailyMetrics] = {}
    for row in parse_tsv(text):
        territory = tsv_field(row, "Territory")
        if not _match_territory(territory, territory_filter):
            continue
        date = tsv_field(row, "Date")
        if len(date) != 10:
            continue
        download_type = tsv_field(row, "Download Type")
        if not is_first_time_download(download_type):
            continue
        source_type = tsv_field(row, "Source Type")
        n = parse_count(tsv_field(row, "Counts", "Count"))
        metrics = by_date.setdefault(date, DailyMetrics(date=date))
        metrics.add_download(n, source_type)
    return by_date


def merge_daily(into: dict[str, DailyMetrics], chunk: dict[str, DailyMetrics]) -> None:
    for date, src in chunk.items():
        dst = into.setdefault(date, DailyMetrics(date=date))
        dst.impressions += src.impressions
        dst.product_page_views += src.product_page_views
        dst.first_time_downloads += src.first_time_downloads
        for k, v in src.impressions_by_source.items():
            dst.impressions_by_source[k] = dst.impressions_by_source.get(k, 0) + v
        for k, v in src.downloads_by_source.items():
            dst.downloads_by_source[k] = dst.downloads_by_source.get(k, 0) + v


def sum_metrics(days: list[DailyMetrics]) -> DailyMetrics:
    total = DailyMetrics(date="")
    for day in days:
        total.impressions += day.impressions
        total.product_page_views += day.product_page_views
        total.first_time_downloads += day.first_time_downloads
        for k, v in day.impressions_by_source.items():
            total.impressions_by_source[k] = total.impressions_by_source.get(k, 0) + v
        for k, v in day.downloads_by_source.items():
            total.downloads_by_source[k] = total.downloads_by_source.get(k, 0) + v
    return total


def pct_change(current: int, previous: int) -> float | None:
    if previous <= 0:
        return None
    return (current - previous) / previous * 100.0
