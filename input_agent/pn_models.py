# models_petrinets.py
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, model_validator, ConfigDict
import re

ACTIVITY_KEY_RE = re.compile(r"^A\d{3}$")  # A001, A002...
TASK_KEY_RE = re.compile(r"^T\d{3}$")  # T001, T010, T100...

class PetriInfo(BaseModel):
    plant_name: str
    maintenance_type: str
    use_case: str
    petri_net_id: str
    version: str


class Task(BaseModel):
    model_config = ConfigDict(extra="allow")  # por si mañana metes más campos

    Duration: float
    Requires_Shutdown: bool

    # ✅ campos que ahora mismo se te estaban perdiendo
    taskDependency: Optional[bool] = None
    taskCode: Optional[List[str]] = None


class Activity(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    tasks: Dict[str, Task]
    T_period: float
    T_wait: float
    Start_disp: float
    Team: str
    team_members: int = Field(alias="Team members")
    Shift_duration: float

    activityDependency: Optional[bool] = None
    activityCode: Optional[List[str]] = None

    @model_validator(mode="after")
    def validate_task_keys(self):
        # límite anti-abuso
        if len(self.tasks) > 100:
            raise ValueError("Demasiadas tareas en una actividad.")

        invalid = [k for k in self.tasks.keys() if not TASK_KEY_RE.match(k)]
        if invalid:
            raise ValueError(
                f"Keys de tasks inválidas: {invalid}. Deben ser T001, T010, T100..."
            )
        return self


class PetriInput(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    runId: int
    Teams: int
    Simulation_period: float
    activities: Dict[str, "Activity"] = Field(default_factory=dict)

    @model_validator(mode="before")
    def collect_activities(cls, values: Any):
        if not isinstance(values, dict):
            raise ValueError("El body debe ser un objeto JSON.")

        globals_keys = {"runId", "Teams", "Simulation_period", "activities"}

        # Si ya viene activities, úsalo como base
        activities = dict(values.get("activities") or {})

        # Mueve keys sueltas que parezcan actividades
        for key in list(values.keys()):
            if key in globals_keys:
                continue
            if ACTIVITY_KEY_RE.match(key):
                activities[key] = values.pop(key)

        if not activities:
            raise ValueError("Debe definirse al menos una actividad (A001, A002, ...).")

        # Límite anti-abuso 
        if len(activities) > 100:
            raise ValueError("Demasiadas actividades.")

        values["activities"] = activities
        return values
