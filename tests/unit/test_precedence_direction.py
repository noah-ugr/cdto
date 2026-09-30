"""Direction of taskCode and activityCode in the texts that describe them.

A list names what its owner precedes, which is what the engine runs: utils/mapping_utils.py copies
it into Order_Before/Activity_Order_Before and the net reads those as "the owner before each entry".
On S_0 of the case study, A001.T003 precedes T001 and T002, and A002 precedes A001. The arcs in the
generated documentation are checked against the precedence dictionaries the net is built from.
"""

import re

import pytest

from input_agent.src.tools import build_topology_map, extract_validation_context
from tests.unit.case_study import case_configs
from utils.automatic_documentation import (
    generate_petri_net_documentation,
    generate_petri_net_documentation_txt,
)

pytest.importorskip("utils.generator_utils", reason="engine not included")
pytestmark = pytest.mark.engine

from utils.generator_utils import _build_activity_precedence_from_pnipnt, _build_task_precedence_from_pnipnt  # noqa: E402
from utils.mapping_utils import map_to_algorithm_format  # noqa: E402


def s0():
    return case_configs()[0]


def engine_arcs(config):
    """Precedence arcs the net gets for config: (FROM, TO) of tasks, inhibitor and buffer arcs of activities."""
    algo, _ = map_to_algorithm_format(config)
    tasks = set()
    for after, meta in _build_task_precedence_from_pnipnt(algo).items():
        for before in meta["after"]:
            j, i = before[len("t0007"):-1], before[-1]  # t0007{j}{i}, single-digit indices in S_0
            tasks.add((f"p7{j}{i}", after))
    inhibitor, buffer = set(), set()
    for after, meta in _build_activity_precedence_from_pnipnt(algo).items():
        for before in meta["after"]:
            i_before, i_after = before.removeprefix("ActID"), after.removeprefix("ActID")
            inhibitor.add((f"p02{i_before}", f"t{i_after}1"))
            buffer.add((f"pbuff{i_before}", f"t{i_after}1"))
    return tasks, inhibitor, buffer


def txt_cards(txt):
    cards = [c for c in txt.split("\n---\n") if re.search(r"ID:\s*(PREC|BUFF)_", c)]
    parsed = []
    for card in cards:
        fields = dict(re.findall(r"^(ID|TYPE|FROM|TO|MEANING):\s*(.*)$", card, flags=re.M))
        parsed.append(fields)
    return parsed


def test_engine_runs_the_owner_first_on_s0():
    tasks, inhibitor, buffer = engine_arcs(s0())
    # A001.T003 precedes T001 and T002: both wait for the token T003 leaves in p731.
    assert {("p731", "t000711"), ("p731", "t000721")} <= tasks
    # A002 precedes A001.
    assert inhibitor == {("p022", "t11")}
    assert buffer == {("pbuff2", "t11")}


def test_markdown_says_what_each_owner_precedes():
    md = generate_petri_net_documentation(s0())
    assert "**A001.T003** precedes T001 and T002" in md
    assert "**A002.T004** precedes T002 and T003" in md
    assert "**A002** precedes A001" in md
    assert "| A001 | T003 | 40 | False | T001, T002 |" in md
    assert "| Activity | Task | Duration | Requires_Shutdown | Precedes |" in md
    for wording in ("requiere", "requires", "Dependencies"):
        assert wording not in md


def test_markdown_arcs_are_the_engine_arcs():
    md = generate_petri_net_documentation(s0())
    tasks, inhibitor, buffer = engine_arcs(s0())
    documented_tasks = set(re.findall(r"- Arc: \$(p7\d+) \\rightarrow (t0007\d+)\$", md))
    documented_inhibitor = set(re.findall(r"- Inhibitor arc: \$(p02\d+) \\rightarrow (t\d+1)\$", md))
    documented_buffer = set(re.findall(r"- Arc: \$(pbuff\d+) \\rightarrow (t\d+1)\$", md))
    assert documented_tasks == tasks
    assert documented_inhibitor == inhibitor
    assert documented_buffer == buffer


def test_txt_cards_are_the_engine_arcs_and_say_precedes():
    cards = txt_cards(generate_petri_net_documentation_txt(s0()))
    tasks, inhibitor, buffer = engine_arcs(s0())
    by_type = lambda t, prefix: {(c["FROM"], c["TO"]) for c in cards if c["TYPE"] == t and c["FROM"].startswith(prefix)}  # noqa: E731
    assert by_type("Precedence Arc", "p7") == tasks
    assert by_type("Inhibitor Arc", "p02") == inhibitor
    assert by_type("Precedence Arc", "pbuff") == buffer

    meanings = {c["ID"]: c["MEANING"] for c in cards}
    assert meanings["PREC_A001_T003_BEFORE_T001"].startswith("A001.T003 precedes T001")
    assert meanings["PREC_A001_T003_BEFORE_T002"].startswith("A001.T003 precedes T002")
    assert meanings["PREC_A002_BEFORE_A001"].startswith("A002 precedes A001")
    assert meanings["BUFF_A002_BEFORE_A001"].startswith("A002 precedes A001")
    assert not any("requires" in m for m in meanings.values())


def test_context_labels_say_what_each_owner_precedes():
    context = extract_validation_context(s0(), "A002.T_wait")
    entries = {(e["type"], e.get("parent_activity"), e["id"]): e for e in context["valid_ids"]}
    assert entries[("Task", "A001", "T003")]["precedes"] == ["T001", "T002"]
    assert entries[("Activity", None, "A002")]["precedes"] == ["A001"]
    assert entries[("Activity", None, "A001")]["precedes"] == []
    assert all("dependencies" not in e for e in context["valid_ids"])

    topology = build_topology_map(context["valid_ids"])
    assert topology["A002"]["precedes"] == ["A001"]
    assert topology["A001"]["tasks"]["T003"] == ["T001", "T002"]
