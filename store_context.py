"""Best-effort App Store listing context for Draft Generator (read-only).

Current Analytics API key may lack metadata/screenshot scopes; failures become
missingInputs rather than invented listing content.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from config import get_app_store_connect_settings, get_ga4_settings
from asc.apps import resolve_app
from asc.auth import create_jwt
from asc.client import AscApiError, AscClient

logger = logging.getLogger(__name__)


@dataclass
class StoreListingContext:
    """Observed listing / capability facts only — never invented screenshots."""

    available: dict[str, Any] = field(default_factory=dict)
    missing_inputs: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_prompt_block(self) -> str:
        lines = ["APP STORE / PRODUCT CONTEXT (observed only — do not invent):"]
        if self.available:
            for key, value in self.available.items():
                lines.append(f"- {key}: {value}")
        else:
            lines.append("- (no listing fields available)")
        if self.missing_inputs:
            lines.append("KNOWN GAPS (must appear in missingInputs if needed for the draft):")
            for item in self.missing_inputs:
                lines.append(f"- {item}")
        if self.notes:
            lines.append("NOTES:")
            for note in self.notes:
                lines.append(f"- {note}")
        return "\n".join(lines)


def _declared_event_capabilities() -> list[str]:
    """Developer-declared GA4 event meanings — capabilities, not UI screens."""
    settings = get_ga4_settings()
    if settings is None:
        return []
    lines: list[str] = []
    for item in settings.event_definitions:
        lines.append(f"{item.name}: {item.definition}")
    return lines


def collect_store_listing_context(
    *,
    app_hint: dict[str, Any] | None = None,
) -> StoreListingContext:
    """Gather whatever listing info we can without inventing screenshots/screens."""
    ctx = StoreListingContext()
    hint = app_hint or {}

    if hint.get("name"):
        ctx.available["appName"] = hint.get("name")
    if hint.get("bundleId"):
        ctx.available["bundleId"] = hint.get("bundleId")
    if hint.get("appStoreConnectId"):
        ctx.available["appStoreConnectId"] = hint.get("appStoreConnectId")
    if hint.get("territory"):
        ctx.available["territory"] = hint.get("territory")

    capabilities = _declared_event_capabilities()
    if capabilities:
        ctx.available["declaredGa4EventCapabilities"] = capabilities
    else:
        ctx.missing_inputs.append(
            "Declared in-app feature/event definitions (beyond Analyzer facts)"
        )

    # Screen inventory is not in the Analyzer path. Current screenshot *images*
    # are expected as user-provided inputs to the Draft Generator (not ASC OCR).
    ctx.missing_inputs.append("Available app screens/features inventory")
    ctx.notes.append(
        "Screenshot Draft prefers user-provided current App Store screenshot "
        "images as input. ASC file metadata alone is not a substitute for image content."
    )

    try:
        settings = get_app_store_connect_settings()
        client = AscClient(create_jwt(settings.credentials))
        app = resolve_app(
            client,
            app_id=settings.app_id or hint.get("appStoreConnectId"),
            bundle_id=settings.bundle_id or hint.get("bundleId"),
        )
        ctx.available["appName"] = app.name
        ctx.available["bundleId"] = app.bundle_id
        ctx.available["appStoreConnectId"] = app.id

        versions = client.get(
            f"/apps/{app.id}/appStoreVersions",
            params={"limit": 5, "filter[platform]": "IOS"},
        )
        chosen = None
        for item in versions.get("data") or []:
            state = (item.get("attributes") or {}).get("appStoreState")
            if state in ("READY_FOR_SALE", "READY_FOR_DISTRIBUTION"):
                chosen = item
                break
        if chosen is None and (versions.get("data") or []):
            chosen = versions["data"][0]

        if chosen is None:
            ctx.missing_inputs.append("App Store version / localization metadata")
            ctx.notes.append("No App Store version found for listing metadata.")
            return ctx

        attrs = chosen.get("attributes") or {}
        ctx.available["appStoreVersion"] = attrs.get("versionString")
        ctx.available["appStoreState"] = attrs.get("appStoreState")

        try:
            locs = client.get(
                f"/appStoreVersions/{chosen['id']}/appStoreVersionLocalizations",
                params={"limit": 20},
            )
        except AscApiError as exc:
            ctx.missing_inputs.extend(
                [
                    "Current App Store title / subtitle / keywords / description",
                    "Current App Store promotional text",
                ]
            )
            ctx.notes.append(
                f"ASC localization read not permitted or failed "
                f"(HTTP {exc.status}): {exc.message[:200]}"
            )
            return ctx

        localizations: list[dict[str, Any]] = []
        for loc in locs.get("data") or []:
            a = loc.get("attributes") or {}
            localizations.append(
                {
                    "locale": a.get("locale"),
                    "name": a.get("name"),
                    "subtitle": a.get("subtitle"),
                    "keywords": a.get("keywords"),
                    "promotionalText": a.get("promotionalText"),
                    "descriptionPreview": (a.get("description") or "")[:400],
                }
            )
        if localizations:
            ctx.available["localizations"] = localizations
            # We got text metadata — remove generic metadata missing if present.
            for item in (
                "Current App Store title / subtitle / keywords / description",
                "Current App Store promotional text",
            ):
                if item in ctx.missing_inputs:
                    ctx.missing_inputs.remove(item)
        else:
            ctx.missing_inputs.append(
                "Current App Store title / subtitle / keywords / description"
            )

        # Screenshot assets: try; still do not describe image contents we cannot see.
        screenshot_meta: list[dict[str, Any]] = []
        for loc in locs.get("data") or []:
            loc_id = loc.get("id")
            if not loc_id:
                continue
            try:
                sets = client.get(
                    f"/appStoreVersionLocalizations/{loc_id}/appScreenshotSets",
                    params={"limit": 10},
                )
            except AscApiError as exc:
                ctx.notes.append(
                    f"ASC screenshot set read failed (HTTP {exc.status}): "
                    f"{exc.message[:160]}"
                )
                continue
            for ss in sets.get("data") or []:
                sa = ss.get("attributes") or {}
                set_id = ss.get("id")
                entry: dict[str, Any] = {
                    "locale": (loc.get("attributes") or {}).get("locale"),
                    "displayType": sa.get("screenshotDisplayType"),
                    "files": [],
                }
                if set_id:
                    try:
                        shots = client.get(
                            f"/appScreenshotSets/{set_id}/appScreenshots",
                            params={"limit": 20},
                        )
                        for sh in shots.get("data") or []:
                            sha = sh.get("attributes") or {}
                            entry["files"].append(
                                {
                                    "fileName": sha.get("fileName"),
                                    "fileSize": sha.get("fileSize"),
                                }
                            )
                    except AscApiError:
                        pass
                screenshot_meta.append(entry)

        if screenshot_meta and any(s.get("files") for s in screenshot_meta):
            ctx.available["screenshotFileNames"] = screenshot_meta
            ctx.notes.append(
                "Screenshot file names may be available, but image content / "
                "captions / depicted UI were not OCR'd or described — do not invent them."
            )
        else:
            ctx.notes.append(
                "Current screenshot image content is not available to the Draft Generator."
            )

    except Exception as exc:  # noqa: BLE001 — listing context is best-effort
        logger.info("Store listing context partial/unavailable: %s", type(exc).__name__)
        ctx.notes.append(
            f"ASC listing fetch skipped or failed: {type(exc).__name__}: {str(exc)[:200]}"
        )
        for item in (
            "Current App Store title / subtitle / keywords / description",
            "Current App Store promotional text",
        ):
            if item not in ctx.missing_inputs:
                ctx.missing_inputs.append(item)

    # Dedupe missing while preserving order
    seen: set[str] = set()
    deduped: list[str] = []
    for item in ctx.missing_inputs:
        if item not in seen:
            seen.add(item)
            deduped.append(item)
    ctx.missing_inputs = deduped
    return ctx
