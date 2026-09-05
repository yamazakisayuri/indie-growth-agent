"""App lookup helpers."""

from __future__ import annotations

from dataclasses import dataclass

from .client import AscClient


@dataclass(frozen=True)
class AscApp:
    id: str
    name: str
    bundle_id: str


def list_apps(client: AscClient, *, limit: int = 50) -> list[AscApp]:
    payload = client.get("/apps", params={"limit": limit})
    apps: list[AscApp] = []
    for item in payload.get("data") or []:
        attrs = item.get("attributes") or {}
        app_id = str(item.get("id") or "").strip()
        if not app_id:
            continue
        apps.append(
            AscApp(
                id=app_id,
                name=str(attrs.get("name") or "").strip(),
                bundle_id=str(attrs.get("bundleId") or "").strip(),
            )
        )
    return apps


def resolve_app(
    client: AscClient,
    *,
    app_id: str | None = None,
    bundle_id: str | None = None,
) -> AscApp:
    apps = list_apps(client)
    if not apps:
        raise RuntimeError("No apps found in App Store Connect for this API key.")

    if app_id:
        for app in apps:
            if app.id == app_id:
                return app
        raise RuntimeError(f"App Store Connect app id not found: {app_id}")

    if bundle_id:
        for app in apps:
            if app.bundle_id == bundle_id:
                return app
        raise RuntimeError(f"App Store Connect bundle id not found: {bundle_id}")

    if len(apps) == 1:
        return apps[0]

    choices = ", ".join(f"{a.name} ({a.bundle_id}, id={a.id})" for a in apps)
    raise RuntimeError(
        "Multiple apps found. Set APP_STORE_CONNECT_APP_ID or "
        f"APP_STORE_CONNECT_BUNDLE_ID. Available: {choices}"
    )
