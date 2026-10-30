"""Check Airflow's next-run calculation, including the off-grid rollout run."""

import pytest

airflow = pytest.importorskip("airflow")
import pendulum  # noqa: E402
from airflow.timetables.base import DataInterval, TimeRestriction  # noqa: E402

from qbo_connectivity import timetable  # noqa: E402


def test_next_run_after_rollout_stays_on_original_grid(monkeypatch: pytest.MonkeyPatch) -> None:
    now = pendulum.datetime(2026, 10, 30, 19, tz="UTC")
    monkeypatch.setattr(timetable.pendulum, "now", lambda _tz: now)
    restriction = TimeRestriction(
        earliest=pendulum.datetime(2026, 10, 27, 14, tz="UTC"),
        latest=None,
        catchup=False,
    )
    off_grid_run = DataInterval.exact(pendulum.datetime(2026, 10, 30, 18, 49, tz="UTC"))
    schedule = timetable.FifteenDayTimetable()

    next_run = schedule.next_dagrun_info(
        last_automated_data_interval=off_grid_run,
        restriction=restriction,
    )

    assert next_run is not None
    assert next_run.run_after == pendulum.datetime(2026, 11, 11, 14, tz="UTC")
    assert schedule.serialize() == {}
    assert isinstance(schedule.deserialize({}), timetable.FifteenDayTimetable)
