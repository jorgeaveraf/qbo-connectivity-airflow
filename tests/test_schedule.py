"""The calendar stays anchored when a deployment or scheduler restart occurs."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from qbo_connectivity.schedule import next_anchored_run


@pytest.mark.parametrize(
    ("current", "expected"),
    [
        (datetime(2026, 10, 30, 12, tzinfo=UTC), datetime(2026, 11, 11, 14)),
        (datetime(2026, 11, 11, 14, tzinfo=UTC), datetime(2026, 11, 11, 14)),
        (datetime(2026, 11, 11, 14, 0, 1, tzinfo=UTC), datetime(2026, 11, 26, 14)),
        (datetime(2026, 11, 27, 12, tzinfo=UTC), datetime(2026, 12, 11, 14)),
    ],
)
def test_next_anchored_run(current: datetime, expected: datetime) -> None:
    assert next_anchored_run(current) == expected.replace(tzinfo=UTC)
    assert next_anchored_run(current).astimezone(ZoneInfo("America/Mexico_City")).hour == 8


def test_next_anchored_run_requires_timezone() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        next_anchored_run(datetime(2026, 10, 30, 12))
