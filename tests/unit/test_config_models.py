import pytest
from pydantic import ValidationError

pytest.importorskip("config.models", reason="engine not included")
pytestmark = pytest.mark.engine

from config.models import PetriInput  # noqa: E402


def valid_payload() -> dict:
    return {
        "runId": 1,
        "Teams": 1,
        "Simulation_period": 100.0,
        "A001": {
            "tasks": {
                "T001": {
                    "Duration": 4.0,
                    "Requires_Shutdown": False,
                }
            },
            "T_period": 24.0,
            "T_wait": 1.0,
            "Start_disp": 0.0,
            "Team": "TeamA",
            "Team members": 2,
            "Shift_duration": 8.0,
        },
    }


def test_petri_input_collects_top_level_activity() -> None:
    model = PetriInput(**valid_payload())

    assert "A001" in model.activities
    assert model.activities["A001"].tasks["T001"].Duration == 4.0


def test_petri_input_rejects_invalid_activity_key() -> None:
    payload = valid_payload()
    payload["A1"] = payload.pop("A001")

    with pytest.raises(ValidationError):
        PetriInput(**payload)


def test_petri_input_rejects_invalid_task_key() -> None:
    payload = valid_payload()
    payload["A001"]["tasks"]["T1"] = payload["A001"]["tasks"].pop("T001")

    with pytest.raises(ValidationError):
        PetriInput(**payload)
