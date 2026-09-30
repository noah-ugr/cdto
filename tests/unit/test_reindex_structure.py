import copy

import pytest

from input_agent.src.PetriNetConfig import PetriConfigEngine

GLOBALS = {"runId": 1, "Teams": 1, "Simulation_period": 100}


def act(tasks, **extra):
    activity = {
        "tasks": tasks,
        "T_period": 100,
        "T_wait": 1,
        "Start_disp": 0,
        "Team": "TeamA",
        "Team members": 1,
        "Shift_duration": 8,
    }
    activity.update(extra)
    return activity


def task(duration, **extra):
    t = {"Duration": duration, "Requires_Shutdown": False}
    t.update(extra)
    return t


def config(**activities):
    return {**GLOBALS, **activities}


def leaf_values(node):
    """Multiconjunto de valores hoja que no son IDs de referencia (para detectar pérdidas o duplicados)."""
    values = []
    for key, value in node.items():
        if isinstance(value, dict):
            values += leaf_values(value)
        elif key not in ("Order_Before", "Activity_Order_Before", "taskCode", "activityCode"):
            values.append((key, repr(value)))
    return sorted(values)


def reindex(cfg):
    engine = PetriConfigEngine(cfg)
    result = engine.reindex_structure()
    assert result is engine.data
    return result


CASES = {
    "1 actividad nueva al final": (
        config(
            A001=act(
                {"T001": task(1)}, Activity_Order_Enforced=True, Activity_Order_Before=["A002"]
            ),
            A002=act(
                {"T001": task(2)}, Activity_Order_Enforced=True, Activity_Order_Before=["A002_new"]
            ),
            A002_new=act({"T001": task(3)}),
        ),
        config(
            A001=act(
                {"T001": task(1)}, Activity_Order_Enforced=True, Activity_Order_Before=["A002"]
            ),
            A002=act(
                {"T001": task(2)}, Activity_Order_Enforced=True, Activity_Order_Before=["A003"]
            ),
            A003=act({"T001": task(3)}),
        ),
    ),
    "2 actividad intermedia, formato del Planner": (
        config(
            A001=act({"T001": task(1)}),
            A002=act(
                {"T001": task(2)}, Activity_Order_Enforced=True, Activity_Order_Before=["A002_new"]
            ),
            A003=act({"T001": task(4)}),
            A002_new=act(
                {"T001": task(3)}, Activity_Order_Enforced=True, Activity_Order_Before=["A003"]
            ),
        ),
        config(
            A001=act({"T001": task(1)}),
            A002=act(
                {"T001": task(2)}, Activity_Order_Enforced=True, Activity_Order_Before=["A003"]
            ),
            A003=act(
                {"T001": task(3)}, Activity_Order_Enforced=True, Activity_Order_Before=["A004"]
            ),
            A004=act({"T001": task(4)}),
        ),
    ),
    "3 actividad intermedia, formato activityCode": (
        config(
            A001=act({"T001": task(1)}),
            A002=act({"T001": task(2)}),
            A003=act({"T001": task(4)}, activityDependency=True, activityCode=["A002_new"]),
            A002_new=act({"T001": task(3)}, activityDependency=True, activityCode=["A002"]),
        ),
        config(
            A001=act({"T001": task(1)}),
            A002=act({"T001": task(2)}),
            A003=act({"T001": task(3)}, activityDependency=True, activityCode=["A002"]),
            A004=act({"T001": task(4)}, activityDependency=True, activityCode=["A003"]),
        ),
    ),
    "4 tarea nueva al final": (
        config(
            A001=act(
                {
                    "T001": task(1, Order_Enforced=True, Order_Before=["T002"]),
                    "T002": task(2, Order_Enforced=True, Order_Before=["T002_new"]),
                    "T002_new": task(3),
                }
            )
        ),
        config(
            A001=act(
                {
                    "T001": task(1, Order_Enforced=True, Order_Before=["T002"]),
                    "T002": task(2, Order_Enforced=True, Order_Before=["T003"]),
                    "T003": task(3),
                }
            )
        ),
    ),
    "5 tarea intermedia, formato del Planner": (
        config(
            A001=act(
                {
                    "T001": task(1, Order_Enforced=True, Order_Before=["T001_new"]),
                    "T002": task(2, Order_Enforced=True, Order_Before=["T003"]),
                    "T003": task(4),
                    "T001_new": task(3, Order_Enforced=True, Order_Before=["T002"]),
                }
            )
        ),
        config(
            A001=act(
                {
                    "T001": task(1, Order_Enforced=True, Order_Before=["T002"]),
                    "T002": task(3, Order_Enforced=True, Order_Before=["T003"]),
                    "T003": task(2, Order_Enforced=True, Order_Before=["T004"]),
                    "T004": task(4),
                }
            )
        ),
    ),
    "6 tarea intermedia, formato taskCode": (
        config(
            A001=act(
                {
                    "T001": task(1),
                    "T002": task(2, taskDependency=True, taskCode=["T001_new"]),
                    "T001_new": task(3, taskDependency=True, taskCode=["T001"]),
                }
            )
        ),
        config(
            A001=act(
                {
                    "T001": task(1),
                    "T002": task(3, taskDependency=True, taskCode=["T001"]),
                    "T003": task(2, taskDependency=True, taskCode=["T002"]),
                }
            )
        ),
    ),
    "7 inserción en A001 con referencias propias en A002": (
        config(
            A001=act({"T001": task(1), "T002": task(2), "T001_new": task(3)}),
            A002=act(
                {
                    "T001": task(5),
                    "T002": task(6, taskDependency=True, taskCode=["T001"]),
                    "T003": task(7, taskDependency=True, taskCode=["T002"]),
                }
            ),
        ),
        config(
            A001=act({"T001": task(1), "T002": task(3), "T003": task(2)}),
            A002=act(
                {
                    "T001": task(5),
                    "T002": task(6, taskDependency=True, taskCode=["T001"]),
                    "T003": task(7, taskDependency=True, taskCode=["T002"]),
                }
            ),
        ),
    ),
    "9 varias inserciones en el mismo batch": (
        config(
            A001=act(
                {
                    "T001": task(1, Order_Enforced=True, Order_Before=["T001_new"]),
                    "T002": task(2, Order_Enforced=True, Order_Before=["T002_new"]),
                    "T001_new": task(3, Order_Enforced=True, Order_Before=["T002"]),
                    "T002_new": task(4),
                },
                Activity_Order_Enforced=True,
                Activity_Order_Before=["A001_new"],
            ),
            A002=act(
                {"T001": task(6)}, Activity_Order_Enforced=True, Activity_Order_Before=["A002_new"]
            ),
            A001_new=act(
                {"T001": task(5)}, Activity_Order_Enforced=True, Activity_Order_Before=["A002"]
            ),
            A002_new=act(
                {"T001": task(7), "T001_new": task(8)},
                activityDependency=True,
                activityCode=["A001_new"],
            ),
        ),
        config(
            A001=act(
                {
                    "T001": task(1, Order_Enforced=True, Order_Before=["T002"]),
                    "T002": task(3, Order_Enforced=True, Order_Before=["T003"]),
                    "T003": task(2, Order_Enforced=True, Order_Before=["T004"]),
                    "T004": task(4),
                },
                Activity_Order_Enforced=True,
                Activity_Order_Before=["A002"],
            ),
            A002=act(
                {"T001": task(5)}, Activity_Order_Enforced=True, Activity_Order_Before=["A003"]
            ),
            A003=act(
                {"T001": task(6)}, Activity_Order_Enforced=True, Activity_Order_Before=["A004"]
            ),
            A004=act(
                {"T001": task(7), "T002": task(8)}, activityDependency=True, activityCode=["A002"]
            ),
        ),
    ),
    "10 una referencia colgante no se reasigna": (
        config(
            A001=act(
                {"T001": task(1)}, Activity_Order_Enforced=True, Activity_Order_Before=["A002"]
            ),
            A003=act({"T001": task(3)}),
            A001_new=act({"T001": task(2)}),
        ),
        config(
            A001=act(
                {"T001": task(1)}, Activity_Order_Enforced=True, Activity_Order_Before=["A002"]
            ),
            A003=act({"T001": task(2)}),
            A004=act({"T001": task(3)}),
        ),
    ),
}


@pytest.mark.parametrize("name", list(CASES))
def test_reindex_cases(name):
    source, expected = CASES[name]
    before = leaf_values(copy.deepcopy(source))
    result = reindex(copy.deepcopy(source))

    assert result == expected
    assert list(result) == list(expected)
    for key, activity in expected.items():
        if isinstance(activity, dict):
            assert list(result[key]["tasks"]) == list(activity["tasks"])
    assert leaf_values(result) == before  # sin campos perdidos ni duplicados


def test_control_without_temporary_ids_is_unchanged():
    source = config(
        A001=act({"T001": task(1, Order_Enforced=True, Order_Before=["T002"]), "T002": task(2)}),
        A002=act({"T001": task(3)}),
    )
    result = reindex(copy.deepcopy(source))
    assert result == source
    assert list(result) == list(source)
    assert list(result["A001"]["tasks"]) == ["T001", "T002"]


def test_gaps_without_temporary_ids_are_not_filled():
    source = config(
        A001=act({"T001": task(1), "T003": task(3)}),
        A003=act({"T001": task(4)}),
    )
    assert reindex(copy.deepcopy(source)) == source


def test_unusual_values_do_not_break_it():
    source = {
        **GLOBALS,
        "A001": 5,
        "Foo": [1, 2],
        "A002": act({"T001": task(1)}),
        "A001_new": act([1, 2]),
    }
    result = reindex(copy.deepcopy(source))
    assert list(result) == ["runId", "Teams", "Simulation_period", "A001", "A002", "A003", "Foo"]
    assert result["A001"] == 5 and result["Foo"] == [1, 2]
    assert result["A002"]["tasks"] == [1, 2] and result["A003"]["tasks"] == {"T001": task(1)}
