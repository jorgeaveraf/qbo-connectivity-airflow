"""Stable 15-day boundaries for the production connectivity monitor."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

ANCHOR = datetime(2026, 10, 27, 8, tzinfo=ZoneInfo("America/Mexico_City"))
PERIOD = timedelta(days=15)


def next_anchored_run(at_or_after: datetime) -> datetime:
    """Return the first scheduled UTC instant at or after a timezone-aware instant."""
    if at_or_after.tzinfo is None:
        raise ValueError("A timezone-aware datetime is required")
    anchor_utc = ANCHOR.astimezone(UTC)
    moment_utc = at_or_after.astimezone(UTC)
    if moment_utc <= anchor_utc:
        return anchor_utc
    elapsed = moment_utc - anchor_utc
    intervals = elapsed // PERIOD
    candidate = anchor_utc + intervals * PERIOD
    return candidate if candidate >= moment_utc else candidate + PERIOD
