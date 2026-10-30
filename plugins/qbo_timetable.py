"""Register the QBO monitoring timetable for DAG serialization."""

from airflow.plugins_manager import AirflowPlugin

from qbo_connectivity.timetable import FifteenDayTimetable


class QboTimetablePlugin(AirflowPlugin):
    name = "qbo_fifteen_day_timetable"
    timetables = [FifteenDayTimetable]
