"""Guard the 15-day production schedule without importing Airflow locally."""

import ast
from pathlib import Path


def test_fifteen_day_schedule_and_activation_limits() -> None:
    source = Path(__file__).resolve().parents[1] / "dags" / "qbo_connection_monitor.py"
    module = ast.parse(source.read_text(encoding="utf-8"))
    function = next(
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name == "qbo_connection_monitor"
    )
    decorator = next(
        node
        for node in function.decorator_list
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "dag"
    )
    options = {keyword.arg: keyword.value for keyword in decorator.keywords}

    schedule = options["schedule"]
    assert isinstance(schedule, ast.Call)
    assert isinstance(schedule.func, ast.Name)
    assert schedule.func.id == "timedelta"
    assert schedule.args == []
    assert {keyword.arg: ast.literal_eval(keyword.value) for keyword in schedule.keywords} == {
        "days": 15
    }
    assert ast.literal_eval(options["catchup"]) is False
    assert ast.literal_eval(options["max_active_runs"]) == 1
    assert ast.literal_eval(options["max_active_tasks"]) == 2

    start_date = options["start_date"]
    assert isinstance(start_date, ast.Call)
    assert isinstance(start_date.func, ast.Attribute)
    assert isinstance(start_date.func.value, ast.Name)
    assert (start_date.func.value.id, start_date.func.attr) == ("pendulum", "datetime")
    assert [ast.literal_eval(arg) for arg in start_date.args] == [2026, 10, 27, 8]
    assert {keyword.arg: ast.literal_eval(keyword.value) for keyword in start_date.keywords} == {
        "tz": "America/Mexico_City"
    }
