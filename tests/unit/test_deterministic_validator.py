import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from input_agent.src.models import ModificationBatch
from input_agent.src.tools import (
    DOMINIO,
    RED_DE_PETRI,
    RULES,
    check_configuration,
    deterministic_validator,
)
from input_agent.sub_agents.feedback import ValidatorEngine
from tests.unit.v1_validator_reference import legacy_validate

REPO_ROOT = Path(__file__).resolve().parents[2]
DATASETS = [
    REPO_ROOT / "benchmarks" / "datasets" / "benchmark_dataset_1_150.jsonl",
    REPO_ROOT / "benchmarks" / "datasets" / "benchmark_dataset_completeness_1_16_50samples.jsonl",
]
EMPTY_BATCH = ModificationBatch(thought_process="", instructions=[])


class Engine:
    def __init__(self, data):
        self.data = data


def make_config(n_activities=2, n_tasks=3):
    config = {"runId": 1, "Teams": 2, "Simulation_period": 1000}
    for i in range(1, n_activities + 1):
        config[f"A{i:03d}"] = {
            "tasks": {
                f"T{j:03d}": {
                    "Duration": 4,
                    "Requires_Shutdown": True,
                    "Cost_per_hour": 10,
                    "Order_Enforced": False,
                    "Order_Before": [],
                }
                for j in range(1, n_tasks + 1)
            },
            "T_period": 200,
            "T_wait": 5,
            "Start_disp": 1,
            "Team": "TeamA",
            "Team members": 2,
            "Shift_duration": 8,
            "Activity_Order_Enforced": False,
            "Activity_Order_Before": [],
        }
    return config


DELETE = object()


def mutated(changes, base=None):
    """Config válida con cambios {'A001.tasks.T001.Duration': valor}; DELETE borra la clave."""
    config = copy.deepcopy(base) if base is not None else make_config()
    for dotted, value in changes.items():
        *parents, key = dotted.split(".")
        node = config
        for part in parents:
            node = node[part]
        if value is DELETE:
            del node[key]
        else:
            node[key] = value
    return config


def violations(config, batch=None):
    return [v.to_dict() for v in check_configuration(config, batch)]


def paths_of(config, rule, batch=None):
    return {v["path"] for v in violations(config, batch) if v["rule"] == rule}


def test_valid_config_has_no_violations():
    assert violations(make_config()) == []


def test_ruleset_and_groups():
    assert {r for r, g in RULES.items() if g == DOMINIO} == {
        "campos_esquema",
        "tipos",
        "equipos",
        "ids",
        "limites",
        "referencias",
        "rangos",
        "sanity_batch",
        "campos_fuera_de_nivel",
    }
    assert {r for r, g in RULES.items() if g == RED_DE_PETRI} == {
        "campos_leidos",
        "no_vacia",
        "dom_real",
        "dom_int",
        "turno_minimo",
        "prec_tipos",
        "prec_aciclica",
    }


def test_violations_are_structured():
    [violation] = violations(mutated({"A001.T_wait": DELETE}))
    assert violation == {
        "rule": "campos_leidos",
        "group": RED_DE_PETRI,
        "path": "A001.T_wait",
        "detail": "A001 has no T_wait field",
    }


# --- positivos: casos límite que cada regla admite ---------------------------------------------


def many_tasks(n):
    return {f"T{j:03d}": {"Duration": 1, "Requires_Shutdown": False} for j in range(1, n + 1)}


POSITIVE = {
    "campos_fuera_de_nivel": mutated(
        {
            "notas": "libre",
            "A001.notas": "libre",
            "A001.tasks.T001.notas": "libre",
            "A001.tasks.T001.T_period_hint": 3,
        }
    ),
    "campos_esquema": mutated(
        {"A001.tasks.T001.Cost_per_hour": DELETE, "A001.Activity_Order_Before": DELETE}
    ),
    "tipos": mutated(
        {
            "runId": 1.0,
            "A001.Team members": 3.0,
            "A001.T_period": 200.5,
            "A001.tasks.T001.taskDependency": None,
        }
    ),
    "equipos": mutated({"Teams": 1}),
    "ids": make_config(),
    "limites": mutated({"A001.tasks": many_tasks(1000)}),
    "referencias": mutated(
        {"A001.tasks.T001.Order_Before": ["T002", "T003"], "A001.Activity_Order_Before": ["A002"]}
    ),
    "rangos": mutated(
        {"A001.T_period": 1, "A001.Shift_duration": 24, "A001.tasks.T001.Cost_per_hour": 0}
    ),
    "campos_leidos": mutated({"A001.extra": {"libre": True}}),
    "no_vacia": make_config(n_activities=1, n_tasks=1),
    "dom_real": mutated({"A001.T_wait": 0, "A001.Start_disp": 0}),
    "dom_int": mutated({"A001.tasks.T001.Duration": 7.0, "A001.Team members": 1}),
    "turno_minimo": mutated({"A001.Shift_duration": 1}),
    "prec_tipos": mutated(
        {"A001.tasks.T001.taskDependency": False, "A001.tasks.T001.taskCode": None}
    ),
    "prec_aciclica": mutated(
        {
            "A001.tasks.T001.Order_Enforced": True,
            "A001.tasks.T001.Order_Before": ["T002"],
            "A001.tasks.T002.Order_Enforced": True,
            "A001.tasks.T002.Order_Before": ["T003"],
            "A002.tasks.T001.Order_Before": ["T002"],
            "A002.tasks.T002.Order_Before": ["T001"],
        }
    ),
}


@pytest.mark.parametrize("rule", sorted(POSITIVE))
def test_rule_positive(rule):
    assert paths_of(POSITIVE[rule], rule) == set()


def test_sanity_batch_positive():
    batch = ModificationBatch(
        thought_process="",
        instructions=[
            {"operation": "SET", "path": "A001", "value": {"T_period": 5, "Team members": 2}}
        ],
    )
    assert paths_of(make_config(), "sanity_batch", batch) == set()


# --- negativos: una violación de cada regla, con su ruta ---------------------------------------


def over_limit_activities():
    config = make_config(n_activities=1, n_tasks=1)
    for i in range(1000):
        config[f"B{i}"] = copy.deepcopy(config["A001"])
    return config


NEGATIVE = [
    ("campos_esquema", mutated({"A001.Team": DELETE}), "A001.Team"),
    (
        "campos_esquema",
        mutated({"A002.tasks.T003.Requires_Shutdown": None}),
        "A002.tasks.T003.Requires_Shutdown",
    ),
    ("tipos", mutated({"A001.T_period": "720"}), "A001.T_period"),
    ("tipos", mutated({"A001.Team members": True}), "A001.Team members"),
    ("tipos", mutated({"A001.Team members": 2.5}), "A001.Team members"),
    (
        "tipos",
        mutated({"A001.tasks.T001.Requires_Shutdown": "false"}),
        "A001.tasks.T001.Requires_Shutdown",
    ),
    ("tipos", mutated({"A001.tasks.T001.Order_Before": "T002"}), "A001.tasks.T001.Order_Before"),
    ("tipos", mutated({"A001.tasks.T001.Cost_per_hour": None}), "A001.tasks.T001.Cost_per_hour"),
    ("tipos", mutated({"A001.Team": 5}), "A001.Team"),
    ("equipos", mutated({"Teams": 1, "A002.Team": "TeamB"}), "Teams"),
    (
        "ids",
        mutated({"A001.tasks.T1": {"Duration": 1, "Requires_Shutdown": False}}),
        "A001.tasks.T1",
    ),
    ("ids", {**make_config(n_activities=1), "A1": make_config(n_activities=1)["A001"]}, "A1"),
    ("limites", mutated({"A001.tasks": many_tasks(1001)}), "A001.tasks"),
    ("limites", over_limit_activities(), ""),
    (
        "referencias",
        mutated({"A001.tasks.T001.Order_Before": ["T009"]}),
        "A001.tasks.T001.Order_Before",
    ),
    (
        "referencias",
        mutated({"A001.tasks.T001.Order_Before": ["A002.T001"]}),
        "A001.tasks.T001.Order_Before",
    ),
    (
        "referencias",
        mutated({"A001.Activity_Order_Before": ["A009"]}),
        "A001.Activity_Order_Before",
    ),
    ("referencias", mutated({"A001.activityCode": ["A009"]}), "A001.activityCode"),
    ("rangos", mutated({"A001.T_period": 0}), "A001.T_period"),
    ("rangos", mutated({"A001.Shift_duration": 25}), "A001.Shift_duration"),
    ("rangos", mutated({"A001.tasks.T001.Cost_per_hour": -1}), "A001.tasks.T001.Cost_per_hour"),
    ("campos_fuera_de_nivel", mutated({"Shift_duration": 9}), "Shift_duration"),
    (
        "campos_fuera_de_nivel",
        mutated({"Activity_Order_Before": ["A001"]}),
        "Activity_Order_Before",
    ),
    ("campos_fuera_de_nivel", mutated({"Duration": 3}), "Duration"),
    ("campos_fuera_de_nivel", mutated({"A001.Order_Before": ["A002"]}), "A001.Order_Before"),
    ("campos_fuera_de_nivel", mutated({"A001.Simulation_period": 5}), "A001.Simulation_period"),
    ("campos_fuera_de_nivel", mutated({"A001.tasks.T001.T_wait": 2}), "A001.tasks.T001.T_wait"),
    ("campos_fuera_de_nivel", mutated({"A001.tasks.T001.Teams": 2}), "A001.tasks.T001.Teams"),
    ("campos_leidos", mutated({"A001.T_wait": DELETE}), "A001.T_wait"),
    ("campos_leidos", mutated({"Teams": DELETE}), "Teams"),
    ("campos_leidos", mutated({"A002.Shift_duration": None}), "A002.Shift_duration"),
    ("campos_leidos", mutated({"A001.tasks.T002.Duration": DELETE}), "A001.tasks.T002.Duration"),
    ("campos_leidos", mutated({"A001.tasks": DELETE}), "A001.tasks"),
    ("campos_leidos", mutated({"A002": 5}), "A002"),
    ("no_vacia", mutated({"A001.tasks": {}}), "A001.tasks"),
    ("no_vacia", {"runId": 1, "Teams": 1, "Simulation_period": 10}, ""),
    ("dom_real", mutated({"A001.T_wait": -1}), "A001.T_wait"),
    ("dom_real", mutated({"Simulation_period": 0}), "Simulation_period"),
    ("dom_real", mutated({"A001.Start_disp": float("inf")}), "A001.Start_disp"),
    ("dom_real", mutated({"A002.Shift_duration": "ocho"}), "A002.Shift_duration"),
    ("dom_int", mutated({"A001.tasks.T001.Duration": 2.5}), "A001.tasks.T001.Duration"),
    ("dom_int", mutated({"A001.tasks.T001.Duration": 0}), "A001.tasks.T001.Duration"),
    ("dom_int", mutated({"A002.Team members": 0}), "A002.Team members"),
    ("turno_minimo", mutated({"A001.Shift_duration": 0.5}), "A001.Shift_duration"),
    ("turno_minimo", mutated({"A001.Shift_duration": 0}), "A001.Shift_duration"),
    (
        "prec_tipos",
        mutated({"A001.tasks.T001.taskDependency": True, "A001.tasks.T001.taskCode": None}),
        "A001.tasks.T001.taskCode",
    ),
    (
        "prec_tipos",
        mutated({"A001.activityDependency": True, "A001.activityCode": "A002"}),
        "A001.activityCode",
    ),
    (
        "prec_tipos",
        mutated({"A001.Activity_Order_Enforced": True, "A001.Activity_Order_Before": [["A002"]]}),
        "A001.Activity_Order_Before",
    ),
    (
        "prec_aciclica",
        mutated({"A001.tasks.T001.Order_Enforced": True, "A001.tasks.T001.Order_Before": ["T001"]}),
        "A001.tasks.T001.Order_Before",
    ),
    (
        "prec_aciclica",
        mutated(
            {
                "A001.tasks.T001.Order_Enforced": True,
                "A001.tasks.T001.Order_Before": ["T002"],
                "A001.tasks.T002.Order_Enforced": True,
                "A001.tasks.T002.Order_Before": ["T001"],
            }
        ),
        "A001.tasks",
    ),
    (
        "prec_aciclica",
        mutated(
            {
                "A001.Activity_Order_Enforced": True,
                "A001.Activity_Order_Before": ["A002"],
                "A002.Activity_Order_Enforced": True,
                "A002.Activity_Order_Before": ["A001"],
            }
        ),
        "",
    ),
    (
        "prec_aciclica",
        mutated({"A002.tasks.T003.taskDependency": True, "A002.tasks.T003.taskCode": ["T003"]}),
        "A002.tasks.T003.taskCode",
    ),
]


@pytest.mark.parametrize("rule, config, path", NEGATIVE, ids=[f"{r}:{p}" for r, _, p in NEGATIVE])
def test_rule_negative(rule, config, path):
    assert path in paths_of(config, rule)


@pytest.mark.parametrize(
    "value, detail",
    [
        (
            {"T_period": -5},
            "the instruction on Foo sets T_period to -5; it must be a non-negative number",
        ),
        (
            {"Duration": "4"},
            'the instruction on Foo sets Duration to "4"; it must be a non-negative number',
        ),
        (
            {"Team members": 2.0},
            "the instruction on Foo sets Team members to 2.0; it must be a non-negative integer",
        ),
    ],
)
def test_sanity_batch_negative(value, detail):
    batch = ModificationBatch(
        thought_process="", instructions=[{"operation": "SET", "path": "Foo", "value": value}]
    )
    found = [v for v in violations(make_config(), batch) if v["rule"] == "sanity_batch"]
    assert found == [{"rule": "sanity_batch", "group": DOMINIO, "path": "Foo", "detail": detail}]


def test_cycle_reports_offending_substructure():
    config = mutated(
        {
            "A001.tasks.T001.Order_Enforced": True,
            "A001.tasks.T001.Order_Before": ["T002"],
            "A001.tasks.T002.Order_Enforced": True,
            "A001.tasks.T002.Order_Before": ["T003"],
            "A001.tasks.T003.Order_Enforced": True,
            "A001.tasks.T003.Order_Before": ["T001"],
        }
    )
    [violation] = violations(config)
    assert violation["rule"] == "prec_aciclica" and violation["group"] == RED_DE_PETRI
    assert violation["detail"] == (
        "precedence cycle among T001, T002, T003: A001.T001 lists T002 in Order_Before; "
        "A001.T002 lists T003 in Order_Before; A001.T003 lists T001 in Order_Before"
    )


# --- mensajes: en inglés y diciendo qué campo apunta a qué (sanity_batch, arriba) -------------

MESSAGES = [
    (
        "campos_esquema",
        mutated({"A002.tasks.T003.Requires_Shutdown": None}),
        "A002.tasks.T003.Requires_Shutdown",
        "A002.T003 has Requires_Shutdown = null",
    ),
    (
        "tipos",
        mutated({"A001.T_period": "720"}),
        "A001.T_period",
        'A001.T_period is "720"; it must be a number',
    ),
    (
        "equipos",
        mutated({"Teams": 1, "A002.Team": "TeamB"}),
        "Teams",
        "the activities use 2 distinct Team labels (TeamA, TeamB) but Teams is 1",
    ),
    (
        "ids",
        mutated({"A001.tasks.T1": {"Duration": 1, "Requires_Shutdown": False}}),
        "A001.tasks.T1",
        "A001 has the task key T1, which does not have the form Txxx",
    ),
    (
        "limites",
        mutated({"A001.tasks": many_tasks(1001)}),
        "A001.tasks",
        "A001 has 1001 tasks; the maximum is 1000",
    ),
    (
        "referencias",
        mutated({"A001.tasks.T001.Order_Before": ["T009"]}),
        "A001.tasks.T001.Order_Before",
        "A001.T001 lists T009 in Order_Before, but T009 does not exist in A001",
    ),
    (
        "referencias",
        mutated({"A001.activityCode": ["A009"]}),
        "A001.activityCode",
        "A001 lists A009 in activityCode, but A009 does not exist",
    ),
    (
        "rangos",
        mutated({"A001.tasks.T001.Cost_per_hour": -1}),
        "A001.tasks.T001.Cost_per_hour",
        "A001.T001.Cost_per_hour is -1; it must be >= 0",
    ),
    (
        "campos_fuera_de_nivel",
        mutated({"A001.tasks.T001.T_wait": 2}),
        "A001.tasks.T001.T_wait",
        "A001.T001 has T_wait, which is an activity field, not a task field",
    ),
    ("campos_leidos", mutated({"A001.T_wait": DELETE}), "A001.T_wait", "A001 has no T_wait field"),
    ("no_vacia", mutated({"A001.tasks": {}}), "A001.tasks", "A001 has no tasks"),
    (
        "dom_real",
        mutated({"A001.T_wait": -1}),
        "A001.T_wait",
        "A001.T_wait is -1; it must be a finite number >= 0",
    ),
    (
        "dom_int",
        mutated({"A001.tasks.T001.Duration": 2.5}),
        "A001.tasks.T001.Duration",
        "A001.T001.Duration is 2.5; it must be an integer >= 1",
    ),
    (
        "turno_minimo",
        mutated({"A001.Shift_duration": 0.5}),
        "A001.Shift_duration",
        "A001.Shift_duration is 0.5; it must be >= 1 (hours)",
    ),
    (
        "prec_tipos",
        mutated({"A001.tasks.T001.taskDependency": True, "A001.tasks.T001.taskCode": None}),
        "A001.tasks.T001.taskCode",
        "A001.T001 has taskDependency = true, but its taskCode is null, not a list of task IDs",
    ),
    (
        "prec_aciclica",
        mutated({"A002.tasks.T003.taskDependency": True, "A002.tasks.T003.taskCode": ["T003"]}),
        "A002.tasks.T003.taskCode",
        "A002.T003 lists itself (T003) in taskCode",
    ),
]


@pytest.mark.parametrize(
    "rule, config, path, detail", MESSAGES, ids=[f"{r}:{p}" for r, _, p, _ in MESSAGES]
)
def test_rule_message(rule, config, path, detail):
    found = {v["detail"] for v in violations(config) if v["rule"] == rule and v["path"] == path}
    assert found == {detail}


def test_every_rule_has_a_message_test():
    assert {rule for rule, *_ in MESSAGES} | {"sanity_batch"} == set(RULES)


def test_reference_to_a_deleted_task_says_it_no_longer_exists():
    previous = mutated(
        {"A001.tasks.T002.taskDependency": True, "A001.tasks.T002.taskCode": ["T001"]}
    )
    candidate = mutated({"A001.tasks.T001": DELETE}, base=previous)
    [with_previous] = check_configuration(candidate, previous_config=previous)
    assert with_previous.detail == (
        "A001.T002 lists T001 in taskCode, but T001 no longer exists in A001"
    )
    [without_previous] = check_configuration(candidate)
    assert (
        without_previous.detail
        == "A001.T002 lists T001 in taskCode, but T001 does not exist in A001"
    )


def test_non_object_config_does_not_raise():
    assert {v["rule"] for v in violations(["no", "es", "un", "dict"])} == {"campos_leidos"}


def test_validator_engine_keeps_signature():
    is_valid, found = ValidatorEngine.validate(EMPTY_BATCH, Engine(mutated({"A001.tasks": {}})))
    assert is_valid is False
    assert found == [
        {
            "rule": "no_vacia",
            "group": RED_DE_PETRI,
            "path": "A001.tasks",
            "detail": "A001 has no tasks",
        }
    ]
    assert ValidatorEngine.validate(EMPTY_BATCH, Engine(make_config())) == (True, [])


# --- todo lo que rechazaba v1 se sigue rechazando ----------------------------------------------


def approved_exception(config):
    """Única condición de v1 retirada con aprobación: más de 100 actividades o tareas (ahora 1000)."""
    activities = [v for k, v in config.items() if k not in ("runId", "Teams", "Simulation_period")]
    return len(activities) > 100 or any(
        isinstance(a, dict) and len(a.get("tasks", {})) > 100 for a in activities
    )


def assert_v1_rejections_kept(config, batch):
    try:
        v1_valid, _ = legacy_validate(batch, Engine(copy.deepcopy(config)))
    except Exception:
        return  # v1 fallaba con una excepción, no rechazaba
    new_valid, _ = deterministic_validator(batch, Engine(copy.deepcopy(config)))
    if not v1_valid and not approved_exception(config):
        assert not new_valid, config


V1_CASES = [
    (EMPTY_BATCH, mutated({"A001.T_period": DELETE})),
    (EMPTY_BATCH, mutated({"Teams": 1, "A002.Team": "TeamB"})),
    (EMPTY_BATCH, mutated({"A001.activityDependency": True, "A001.activityCode": ["A009"]})),
    (
        EMPTY_BATCH,
        mutated({"A001.tasks.T001.taskDependency": True, "A001.tasks.T001.taskCode": ["T009"]}),
    ),
    (EMPTY_BATCH, mutated({"A001.tasks.T1": {"Duration": 1, "Requires_Shutdown": False}})),
    (EMPTY_BATCH, mutated({"A001.Team": 5})),
    (EMPTY_BATCH, mutated({"A001.Team members": 2.5})),
    (EMPTY_BATCH, mutated({"A001.tasks.T001.Requires_Shutdown": "quizá"})),
    (EMPTY_BATCH, {"runId": 1, "Teams": 1, "Simulation_period": 10}),
    (
        ModificationBatch(
            thought_process="",
            instructions=[{"operation": "SET", "path": "A001", "value": {"T_period": -5}}],
        ),
        make_config(),
    ),
    (
        ModificationBatch(
            thought_process="",
            instructions=[{"operation": "SET", "path": "Foo", "value": {"Duration": -1}}],
        ),
        make_config(),
    ),
    (
        ModificationBatch(
            thought_process="",
            instructions=[{"operation": "SET", "path": "A001.x", "value": {"Team members": 2.0}}],
        ),
        make_config(),
    ),
]


@pytest.mark.parametrize("batch, config", V1_CASES)
def test_v1_rejections_are_kept_unit(batch, config):
    try:
        v1_valid, _ = legacy_validate(batch, Engine(copy.deepcopy(config)))
    except Exception:
        pytest.fail("el caso debe ser un rechazo de v1, no una excepción")
    assert not v1_valid
    assert_v1_rejections_kept(batch=batch, config=config)


@pytest.mark.parametrize("dataset", DATASETS, ids=lambda p: p.name)
def test_v1_rejections_are_kept_on_dataset(dataset):
    if not dataset.exists():
        pytest.skip(f"dataset no disponible: {dataset}")
    with dataset.open(encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            instructions = row.get("instructions_technical") or [row["instruction_technical"]]
            assert_v1_rejections_kept(row["json_base"], EMPTY_BATCH)
            assert_v1_rejections_kept(
                row["json_gt"], ModificationBatch(thought_process="", instructions=instructions)
            )


# --- el chequeo no llama al simulador ----------------------------------------------------------

SIMULATOR_MODULES = (
    "core.pipeline",
    "Modules.monteCarloSimulator4",
    "Modules.Paramtrial_petri_net_A",
    "Modules.Places_petri_net_A",
    "Modules.Transitions_petri_net_A",
    "PetriNet_module",
    "utils.generator_utils",
)


def test_check_does_not_import_the_simulator():
    code = (
        "import sys, json\n"
        "from input_agent.sub_agents.feedback import ValidatorEngine\n"
        "from input_agent.src.tools import check_configuration\n"
        "check_configuration({'runId': 1, 'Teams': 1, 'Simulation_period': 1})\n"
        f"print(json.dumps(sorted(m for m in sys.modules if m.startswith({SIMULATOR_MODULES!r}))))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    )
    assert json.loads(result.stdout.strip().splitlines()[-1]) == []


def test_check_runs_with_the_simulator_disabled(monkeypatch):
    from input_agent.src import fresh_simulation

    def boom(*args, **kwargs):
        raise AssertionError("el chequeo no debe simular")

    monkeypatch.setattr(fresh_simulation, "run_petrinets_simulation_fresh", boom)
    is_valid, found = ValidatorEngine.validate(EMPTY_BATCH, Engine(mutated({"A001.tasks": {}})))
    assert not is_valid and found
