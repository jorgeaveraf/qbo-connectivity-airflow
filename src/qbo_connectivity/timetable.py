"""Airflow timetable for the anchored production connectivity schedule."""

from datetime import timedelta

import pendulum
from airflow.timetables.base import DagRunInfo, DataInterval, TimeRestriction, Timetable

from qbo_connectivity.schedule import ANCHOR, next_anchored_run


class FifteenDayTimetable(Timetable):
    """Run every 15 days at 08:00 Mexico City time, regardless of deployment time."""

    @property
    def summary(self) -> str:
        return "Every 15 days at 08:00 America/Mexico_City"

    @classmethod
    def deserialize(cls, data: dict) -> "FifteenDayTimetable":
        return cls()

    def serialize(self) -> dict:
        return {}

    def infer_manual_data_interval(self, *, run_after: pendulum.DateTime) -> DataInterval:
        return DataInterval.exact(run_after)

    def next_dagrun_info(
        self,
        *,
        last_automated_data_interval: DataInterval | None,
        restriction: TimeRestriction,
    ) -> DagRunInfo | None:
        earliest = restriction.earliest or ANCHOR
        if last_automated_data_interval is not None:
            earliest = max(earliest, last_automated_data_interval.end + timedelta(microseconds=1))
        if not restriction.catchup:
            earliest = max(earliest, pendulum.now("UTC"))
        next_run = pendulum.instance(next_anchored_run(earliest))
        if restriction.latest is not None and next_run > restriction.latest:
            return None
        return DagRunInfo.exact(next_run)
