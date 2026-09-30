"""Shared definitions for the humanisation check."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from benchmarks.comparisons.traceability import sha256_file


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
RESULTS_ROOT = REPO_ROOT / "benchmarks" / "results" / "humanisation_check"

EVALUATED_MODEL = "gpt-oss:20b"
A_MODEL_DIR = "gpt-oss_20b"
PLANNER = "planner_executor"
VANILLA = "vanilla"

SAMPLE_IDS_FILE = "sample_ids.json"
MANIFEST_FILE = "manifest.json"
CALLS_FILE = "calls.jsonl"

# `ollama list` IDs given for the new server (first 12 hex digits of the digest).
EXPECTED_SHORT_IDS = {
    "gpt-oss:20b": "17052f91a42e",
    "qwen2.5:32b": "9f13ba1299af",
    "phi4:14b":    "ac896e5b8b34",
}


@dataclass(frozen=True)
class AxisSpec:
    dataset: str
    level_field: str      # dataset field holding the level
    text_key: str         # natural-language request
    technical_key: str    # technical instruction(s)
    levels: tuple
    runner: str           # runner module

    @property
    def dataset_path(self) -> Path:
        return REPO_ROOT / self.dataset


AXES: Dict[str, AxisSpec] = {
    "complexity": AxisSpec(
        dataset="benchmarks/datasets/benchmark_dataset_1_150.jsonl",
        level_field="complexity_nodes",
        text_key="instruction_natural",
        technical_key="instruction_technical",
        levels=(1, 16, 50, 150),
        runner="benchmarks.comparisons.benchmark_compare_complexity",
    ),
    "completeness": AxisSpec(
        dataset="benchmarks/datasets/benchmark_dataset_completeness_1_16_50samples.jsonl",
        level_field="completeness",
        text_key="instructions_natural",
        technical_key="instructions_technical",
        levels=(1, 5, 10, 15),
        runner="benchmarks.comparisons.benchmark_compare_completeness",
    ),
}


def a_results_path(axis: str) -> Path:
    """Condition A: the re-scored gpt-oss:20b results of the original run."""
    return (
        REPO_ROOT / "benchmarks" / "results" / "models" / A_MODEL_DIR / axis
        / f"benchmark_compare_{axis}_rescored.json"
    )


def resolve_run_dir(path: str | Path) -> Path:
    run_dir = Path(path)
    return run_dir if run_dir.is_absolute() else (REPO_ROOT / run_dir).resolve()


def load_json(path: str | Path) -> Any:
    with open(path, encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: str | Path, obj: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def read_jsonl(path: str | Path) -> List[Dict[str, Any]]:
    with open(path, encoding="utf-8-sig") as f:
        return [json.loads(line) for line in f if line.strip()]


def load_dataset(axis: str) -> List[Dict[str, Any]]:
    return read_jsonl(AXES[axis].dataset_path)


def technical_instructions(axis: str, row: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Technical instructions of a dataset row as a list (complexity rows hold one)."""
    value = row[AXES[axis].technical_key]
    return value if isinstance(value, list) else [value]


def file_ref(path: str | Path) -> Dict[str, str]:
    path = Path(path)
    try:
        shown = str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        shown = str(path)
    return {"path": shown.replace("\\", "/"), "sha256": sha256_file(path)}


def git_state() -> Dict[str, Any]:
    """Full commit hash and uncommitted changes, so a dirty tree is visible in the manifest."""
    def _git(*args: str) -> str:
        return subprocess.check_output(["git", *args], cwd=REPO_ROOT, stderr=subprocess.DEVNULL, timeout=10).decode().strip()

    try:
        status = _git("status", "--porcelain")
        return {
            "commit": _git("rev-parse", "HEAD"),
            "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
            "dirty": bool(status),
            "uncommitted": status.splitlines(),
        }
    except Exception as exc:
        return {"commit": None, "error": str(exc)}


def selected_samples(run_dir: Path) -> List[Dict[str, Any]]:
    return load_json(run_dir / SAMPLE_IDS_FILE)["samples"]


def find_requests_file(run_dir: Path, explicit: str | None = None) -> Path:
    if explicit:
        path = Path(explicit)
        return path if path.is_absolute() else (REPO_ROOT / path).resolve()
    candidates = sorted(run_dir.glob("requests_*.jsonl"))
    if len(candidates) != 1:
        raise SystemExit(
            f"expected exactly one requests_*.jsonl in {run_dir}, found {len(candidates)}; pass --requests"
        )
    return candidates[0]
