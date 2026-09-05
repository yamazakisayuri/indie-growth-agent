"""Analytics Reports API (Discovery & Engagement / App Downloads)."""

from __future__ import annotations

import gzip
from dataclasses import dataclass

from .client import AscClient

DISCOVERY_NAMES = (
    "App Store Discovery and Engagement Standard",
    "App Store Discovery and Engagement Detailed",
)
DOWNLOADS_NAMES = (
    "App Downloads Standard",
    "App Downloads Detailed",
)


@dataclass(frozen=True)
class AnalyticsRequest:
    id: str
    access_type: str
    stopped_due_to_inactivity: bool


@dataclass(frozen=True)
class AnalyticsReport:
    id: str
    name: str
    category: str


@dataclass(frozen=True)
class AnalyticsInstance:
    id: str
    granularity: str
    processing_date: str


def list_report_requests(client: AscClient, app_id: str) -> list[AnalyticsRequest]:
    payload = client.get(f"/apps/{app_id}/analyticsReportRequests", params={"limit": 50})
    out: list[AnalyticsRequest] = []
    for item in payload.get("data") or []:
        attrs = item.get("attributes") or {}
        rid = str(item.get("id") or "").strip()
        if not rid:
            continue
        out.append(
            AnalyticsRequest(
                id=rid,
                access_type=str(attrs.get("accessType") or ""),
                stopped_due_to_inactivity=bool(attrs.get("stoppedDueToInactivity")),
            )
        )
    return out


def pick_report_request(
    requests: list[AnalyticsRequest],
    *,
    preferred_id: str | None = None,
) -> AnalyticsRequest:
    if preferred_id:
        for req in requests:
            if req.id == preferred_id:
                return req
        raise RuntimeError(f"Analytics report request not found: {preferred_id}")

    ongoing = [
        r
        for r in requests
        if r.access_type == "ONGOING" and not r.stopped_due_to_inactivity
    ]
    if ongoing:
        return ongoing[0]

    snapshots = [r for r in requests if r.access_type == "ONE_TIME_SNAPSHOT"]
    if snapshots:
        return snapshots[0]

    raise RuntimeError(
        "No usable analytics report request found. Create an ONGOING "
        "App Analytics report request in App Store Connect first."
    )


def list_reports(client: AscClient, request_id: str) -> list[AnalyticsReport]:
    payload = client.get(
        f"/analyticsReportRequests/{request_id}/reports",
        params={"limit": 200},
    )
    out: list[AnalyticsReport] = []
    for item in payload.get("data") or []:
        attrs = item.get("attributes") or {}
        rid = str(item.get("id") or "").strip()
        if not rid:
            continue
        out.append(
            AnalyticsReport(
                id=rid,
                name=str(attrs.get("name") or ""),
                category=str(attrs.get("category") or ""),
            )
        )
    return out


def _pick_by_names(reports: list[AnalyticsReport], names: tuple[str, ...], contains: str) -> AnalyticsReport:
    by_name = {r.name: r for r in reports}
    for name in names:
        if name in by_name:
            return by_name[name]
    for report in reports:
        if contains in report.name:
            return report
    raise RuntimeError(f"Analytics report not found (looking for '{contains}')")


def pick_discovery_report(reports: list[AnalyticsReport]) -> AnalyticsReport:
    return _pick_by_names(reports, DISCOVERY_NAMES, "App Store Discovery and Engagement")


def pick_downloads_report(reports: list[AnalyticsReport]) -> AnalyticsReport:
    return _pick_by_names(reports, DOWNLOADS_NAMES, "App Downloads")


def list_daily_instances(
    client: AscClient,
    report_id: str,
    *,
    limit: int = 40,
) -> list[AnalyticsInstance]:
    payload = client.get(
        f"/analyticsReports/{report_id}/instances",
        params={"limit": limit, "filter[granularity]": "DAILY"},
    )
    out: list[AnalyticsInstance] = []
    for item in payload.get("data") or []:
        attrs = item.get("attributes") or {}
        iid = str(item.get("id") or "").strip()
        if not iid:
            continue
        out.append(
            AnalyticsInstance(
                id=iid,
                granularity=str(attrs.get("granularity") or ""),
                processing_date=str(attrs.get("processingDate") or ""),
            )
        )
    out.sort(key=lambda x: x.processing_date, reverse=True)
    return out


def list_segment_ids(client: AscClient, instance_id: str) -> list[str]:
    payload = client.get(
        f"/analyticsReportInstances/{instance_id}/segments",
        params={"limit": 200},
    )
    return [
        str(item.get("id") or "").strip()
        for item in (payload.get("data") or [])
        if str(item.get("id") or "").strip()
    ]


def download_segment_text(client: AscClient, segment_id: str) -> str:
    payload = client.get(f"/analyticsReportSegments/{segment_id}")
    attrs = ((payload.get("data") or {}).get("attributes")) or {}
    url = str(attrs.get("url") or "").strip()
    if not url:
        raise RuntimeError(f"Segment {segment_id} has no download URL")
    raw = client.get_bytes(url)
    if len(raw) >= 2 and raw[0] == 0x1F and raw[1] == 0x8B:
        text = gzip.decompress(raw).decode("utf-8")
    else:
        text = raw.decode("utf-8")
    return text.lstrip("\ufeff").strip()


def load_instance_texts(client: AscClient, instance_id: str) -> list[str]:
    texts: list[str] = []
    for segment_id in list_segment_ids(client, instance_id):
        texts.append(download_segment_text(client, segment_id))
    return texts
