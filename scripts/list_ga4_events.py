"""Fetch GA4 event inventory for review (not wired into the agent yet)."""

from __future__ import annotations

from ga4.events import fetch_event_inventory, format_event_inventory


def main() -> None:
    inventory = fetch_event_inventory()
    print(format_event_inventory(inventory))


if __name__ == "__main__":
    main()
