"""Per-rule table of the offline validator pass, from its per-batch CSV.

Reads ``pe_batches.csv`` of a run of validator_pass.py (default: the recorded
run 20260928T224634Z_c818998_9ed0ce) and the rule -> group map of its
``manifest.json``. No validator code is imported: the violations are the ones
the pass recorded.

A batch is rejected when its category is c1-base, c1-request or c2. For every
rule the table counts the rejected batches with at least one violation of that
rule, in total and per category. A batch can violate several rules, so the
counts do not add up to the 3296 rejections.

Writes to the run folder:

- ``pe_rules_by_category.csv``: rule, group, rejected, c1_base, c1_request, c2,
  ordered by rejected (the per-rule table of docs/validator.md);
- ``pe_cycle_only_rejections.csv``: the rejections whose only violations are
  ``prec_aciclica``, and how many of them have every cycle edge in a list the
  net does not read (``Order_Before``, ``Activity_Order_Before``), with their
  share of all rejections.

Exits with status 1 if the c2 column differs from ``pe_c2_by_rule.csv``, the
per-rule c2 count the pass wrote itself.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUN = REPO_ROOT / "benchmarks" / "results" / "validator_pass" / "20260928T224634Z_c818998_9ed0ce"
REJECTED = ("c1-base", "c1-request", "c2")
UNREAD_LISTS = {"Order_Before", "Activity_Order_Before"}
# Fields named in a prec_aciclica detail: "(A001.tasks.T002.Order_Before)" per edge, or
# "<owner> lists itself (<x>) in <field>" for a self-precedence.
EDGE_FIELD = re.compile(r"\.(\w+)\)")
SELF_FIELD = re.compile(r"lists itself \([^)]*\) in (\w+)")


def read_batches(run_dir: Path) -> list[dict]:
    csv.field_size_limit(10**9)
    with open(run_dir / "pe_batches.csv", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def rules_of(row: dict) -> set[str]:
    return {v["rule"] for v in json.loads(row["violations"])}


def rule_table(rows: list[dict], groups: dict[str, str]) -> list[dict]:
    counts = {category: Counter() for category in REJECTED}
    for row in rows:
        if row["category_all"] in counts:
            counts[row["category_all"]].update(rules_of(row))
    table = [
        {
            "rule": rule,
            "group": group,
            "rejected": sum(counts[c][rule] for c in REJECTED),
            "c1_base": counts["c1-base"][rule],
            "c1_request": counts["c1-request"][rule],
            "c2": counts["c2"][rule],
        }
        for rule, group in groups.items()
    ]
    order = list(groups)
    return sorted(table, key=lambda r: (-r["rejected"], order.index(r["rule"])))


def cycle_fields(row: dict) -> set[str]:
    fields = set()
    for violation in json.loads(row["violations"]):
        fields |= set(EDGE_FIELD.findall(violation["detail"]))
        fields |= set(SELF_FIELD.findall(violation["detail"]))
    return fields


def cycle_only(rows: list[dict]) -> dict:
    rejected = [r for r in rows if r["category_all"] in REJECTED]
    only = [r for r in rejected if rules_of(r) == {"prec_aciclica"}]
    fields = [cycle_fields(r) for r in only]
    unread = [f for f in fields if f and f <= UNREAD_LISTS]
    return {
        "rejected": len(rejected),
        "cycle_only": len(only),
        "cycle_only_unread": len(unread),
        "cycle_only_unread_share": round(len(unread) / len(rejected), 6) if rejected else None,
        "order_before_only": sum(f == {"Order_Before"} for f in unread),
        "activity_order_before_only": sum(f == {"Activity_Order_Before"} for f in unread),
    }


def c2_mismatches(run_dir: Path, table: list[dict]) -> list[str]:
    with open(run_dir / "pe_c2_by_rule.csv", encoding="utf-8", newline="") as f:
        total = next(r for r in csv.DictReader(f) if r["group"] == "total")
    return [row["rule"] for row in table if int(total[f"rule_{row['rule']}"]) != row["c2"]]


def write_csv(path: Path, rows: list[dict]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def print_markdown(table: list[dict]) -> None:
    print("| Rule | Group | Rejected | c1-base | c1-request | c2 |")
    print("|---|---|---|---|---|---|")
    for row in table:
        print(f"| `{row['rule']}` | {row['group']} | {row['rejected']} | {row['c1_base']} | {row['c1_request']} | {row['c2']} |")


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run-dir", default=str(DEFAULT_RUN), help="Folder of a validator_pass.py run")
    args = parser.parse_args(list(argv) if argv is not None else None)

    run_dir = Path(args.run_dir)
    groups = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))["rules"]
    rows = read_batches(run_dir)

    table = rule_table(rows, groups)
    write_csv(run_dir / "pe_rules_by_category.csv", table)
    print_markdown(table)

    cycles = cycle_only(rows)
    write_csv(run_dir / "pe_cycle_only_rejections.csv", [cycles])
    print(f"\nOnly prec_aciclica, every edge in a list the net does not read: {cycles['cycle_only_unread']} "
          f"of {cycles['rejected']} rejections ({100 * cycles['cycle_only_unread_share']:.2f} %)")
    print(f"Saved: {run_dir / 'pe_rules_by_category.csv'} and pe_cycle_only_rejections.csv")

    mismatched = c2_mismatches(run_dir, table)
    if mismatched:
        print(f"c2 differs from pe_c2_by_rule.csv for: {', '.join(mismatched)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
