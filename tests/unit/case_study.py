"""Configurations of the Subsection 4.2 case study, shared by the tests that simulate them."""

import ast
import copy
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# What the IWO left in Modules/petrinet_shared_dicts.json in category F of the case study: algorithm
# format, tasks as bare durations, no precedences, its own horizon. Values recorded from an
# intermediate run before the optimizer fixes; the data are inline, so the test does not read any
# run folder.
IWO_OUTPUT = {
    "Teams": {"Teams": 1, "Simulation_period": 8760.0},
    "PNIpnt": {
        "ActID1": {
            "tasks": {"T1": 10, "T2": 30, "T3": 40},
            "T_period": 480,
            "T_wait": 3.8469394008671562,
            "Start_disp": 20.162826192031524,
            "Team": "TeamA",
            "Team members": 20,
            "Shift_duration": 8.0,
        },
        "ActID2": {
            "tasks": {"T1": 80, "T2": 85, "T3": 60, "T4": 10},
            "T_period": 720,
            "T_wait": 0.9992018988748135,
            "Start_disp": 21.124578111594403,
            "Team": "TeamA",
            "Team members": 20,
            "Shift_duration": 8.0,
        },
    },
}


def case_configs():
    """S_0 of the Subsection 4.2 case study (core/api.py), S_{k+1} and the category-C candidate."""
    tree = ast.parse((REPO_ROOT / "core" / "api.py").read_text(encoding="utf-8"))
    s0 = next(
        ast.literal_eval(node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and isinstance(node.value, ast.Dict)
        and any(getattr(t, "attr", None) == "initial_input" for t in node.targets)
    )
    s1 = copy.deepcopy(s0)
    s1["A002"]["tasks"]["T002"]["Duration"] = 85
    s1["A002"]["T_wait"] = 6
    candidate = copy.deepcopy(s1)
    del candidate["A002"]["tasks"]["T001"]
    return s0, s1, candidate
