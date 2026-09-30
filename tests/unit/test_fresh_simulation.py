import logging
import sys
from types import SimpleNamespace

import pytest

from input_agent.src import fresh_simulation
from tests.unit.case_study import REPO_ROOT, case_configs

if not logging.getLogger().handlers:
    logging.getLogger().addHandler(logging.NullHandler())

from input_agent import nodes


def kpis(general):
    return (
        general["Intervention_time_hours"],
        general["P4_total_busy_hours"],
        round(general["Net_plan_availability_percent"], 1),
    )


@pytest.mark.engine
def test_each_simulation_rebuilds_the_net(tmp_path):
    # Same process, one simulation after another, as the agent does: S_0, then S_{k+1}, then C.
    s0, s1, candidate = case_configs()
    io_dir = tmp_path / "io"
    results = [
        kpis(fresh_simulation.run_petrinets_simulation_fresh(cfg, io_dir=io_dir)[0])
        for cfg in (s0, s1, candidate)
    ]
    assert results == [(1130.0, 1002.0, 87.5), (1088.0, 956.0, 85.9), (1040.0, 782.0, 85.9)]
    assert (io_dir / "outputs" / "results" / "general_outputs_all.json").exists()


@pytest.mark.engine
def test_failure_in_the_child_is_reported(tmp_path):
    with pytest.raises(RuntimeError, match="proceso nuevo"):
        fresh_simulation.run_petrinets_simulation_fresh({"runId": 1}, io_dir=tmp_path / "io")


@pytest.mark.parametrize("episodic", [False, True])
def test_node_simulator_uses_a_fresh_process(monkeypatch, episodic):
    def in_process(*args, **kwargs):
        raise AssertionError("no debe simular en el mismo proceso")

    calls = []
    # core.pipeline sustituido por uno que falla: el nodo no lo importa en este proceso.
    monkeypatch.setitem(sys.modules, "core.pipeline", SimpleNamespace(run_petrinets_simulation=in_process))
    monkeypatch.setattr(
        fresh_simulation, "run_petrinets_simulation_fresh", lambda **kw: calls.append(kw["input"])
    )
    state = {
        "episodic_loop": episodic,
        "episodic_config": {"which": "candidate"},
        "current_config": {"which": "current"},
        "episodic_paths": {"stats_json": ""},
        "simulation_paths": {"stats_json": ""},
        "baseline_kpis": {},
    }
    result = nodes.node_simulator(state)
    # In the diagnostic routine S_k is simulated too (the reference of the rejected candidate).
    expected = (
        [{"which": "current"}, {"which": "candidate"}] if episodic else [{"which": "current"}]
    )
    assert calls == expected
    assert result["simulation_ready"] is True


@pytest.mark.parametrize("path", ["input_agent/agent.py", "core/api.py", "input_agent/nodes.py"])
def test_agent_code_does_not_simulate_in_process(path):
    source = (REPO_ROOT / path).read_text(encoding="utf-8")
    assert "from core.pipeline import run_petrinets_simulation" not in source
    assert "run_petrinets_simulation_fresh" in source
