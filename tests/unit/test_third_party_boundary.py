"""The benchmark, the rescoring, the validator and the DSL do not load third-party code.

A release without the engine and the optimizer keeps these parts working, so importing them must
not import any module of those components. Each entry point is imported in a new process and its
sys.modules is checked.
"""

import json
import subprocess
import sys

import pytest

from tests.unit.case_study import REPO_ROOT

# Modules of the engine and the optimizer (see THIRD_PARTY_GROUPS in tests/conftest.py).
THIRD_PARTY_MODULES = (
    "Modules",
    "PetriNetModules",
    "PetriNet_module",
    "RL_module",
    "read_PN",
    "generateGaussian",
    "optimizers",
    "core.pipeline",
    "core.main",
    "config.models",
    "utils.datetime_utils",
    "utils.durations_utils",
    "utils.excel_utils",
    "utils.general_outputs_utils",
    "utils.generator_utils",
    "utils.logger",
    "utils.mapping_utils",
    "utils.pnipnt_utils",
    "utils.utils",
)

ENTRY_POINTS = (
    "input_agent.src.PetriNetConfig",
    "input_agent.src.tools",
    "input_agent.sub_agents.feedback",
    "input_agent.sub_agents.optimizer",
    "input_agent.nodes",
    "benchmarks.metrics.rescore_results",
    "benchmarks.metrics.validator_pass",
    "benchmarks.comparisons.benchmark_compare_complexity",
    "benchmarks.comparisons.benchmark_compare_completeness",
)


def loaded_third_party(module: str) -> list[str]:
    code = (
        "import importlib, json, sys\n"
        "sys.argv = ['x']\n"
        f"importlib.import_module({module!r})\n"
        f"prefixes = {THIRD_PARTY_MODULES!r}\n"
        "print(json.dumps(sorted(m for m in sys.modules if m in prefixes or m.startswith(tuple(p + '.' for p in prefixes)))))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    )
    return json.loads(result.stdout.strip().splitlines()[-1])


@pytest.mark.parametrize("module", ENTRY_POINTS)
def test_entry_point_loads_no_third_party_module(module):
    assert loaded_third_party(module) == []
