import pytest

pytest.importorskip("utils.mapping_utils", reason="engine not included")
pytestmark = pytest.mark.engine

from utils.mapping_utils import demap_algorithm_config, map_to_algorithm_format  # noqa: E402


def sample_input() -> dict:
    return {
        "runId": 7,
        "Teams": 1,
        "Simulation_period": 240,
        "A001": {
            "tasks": {
                "T001": {"Duration": 10, "Requires_Shutdown": False},
                "T002": {
                    "Duration": 15,
                    "Requires_Shutdown": True,
                    "taskDependency": True,
                    "taskCode": ["T001"],
                },
            },
            "T_period": 48,
            "T_wait": 2,
            "Start_disp": 0,
            "Team": "TeamA",
            "Team members": 2,
            "Shift_duration": 8,
        },
        "A002": {
            "tasks": {
                "T001": {"Duration": 5, "Requires_Shutdown": False},
            },
            "T_period": 72,
            "T_wait": 3,
            "Start_disp": 1,
            "Team": "TeamA",
            "Team members": 2,
            "Shift_duration": 8,
            "activityDependency": True,
            "activityCode": ["A001"],
        },
    }


def test_map_to_algorithm_format_preserves_dependencies() -> None:
    mapped, mapping = map_to_algorithm_format(sample_input())

    assert mapping["activities"]["ActID1"] == "A001"
    assert mapping["tasks"]["ActID1"]["T2"] == "T002"
    assert mapped["ActID1"]["tasks"]["T2"]["Order_Before"] == ["T1"]
    assert mapped["ActID2"]["Activity_Order_Before"] == ["ActID1"]


def test_demap_algorithm_config_restores_public_codes() -> None:
    source = sample_input()
    mapped, _ = map_to_algorithm_format(source)
    mapped["ActID1"]["tasks"]["T1"]["Duration"] = 12
    mapped["Teams"] = 3

    demapped = demap_algorithm_config(mapped, source)

    assert demapped["Teams"] == 3
    assert demapped["A001"]["tasks"]["T001"]["Duration"] == 12
    assert demapped["A001"]["tasks"]["T002"]["taskCode"] == ["T001"]
    assert demapped["A002"]["activityCode"] == ["A001"]
