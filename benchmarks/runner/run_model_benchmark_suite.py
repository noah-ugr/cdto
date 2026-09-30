"""
Run benchmark compare (complexity + completeness) and UQ per model.

This script orchestrates model-by-model execution so each model stores isolated
artifacts under benchmarks/results/models/<model_slug>/.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# runner/.. -> benchmarks -> repo root
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from benchmarks.comparisons.traceability import build_default_output_paths, normalize_model_slug


@dataclass
class SuiteJob:
    model_name: str
    model_version: Optional[str]
    llm_mode: str
    llm_base_url: Optional[str]
    llm_temperature: float
    llm_seed: Optional[int]
    llm_timeout: float
    run_tag: Optional[str]
    master_seed: int


@dataclass
class SuiteResult:
    model_name: str
    model_slug: str
    complexity_ok: bool
    completeness_ok: bool
    uq_complexity_ok: bool
    uq_completeness_ok: bool
    errors: list[str]


def _run(cmd: list[str]) -> tuple[bool, str]:
    proc = subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode == 0:
        return True, proc.stdout
    return False, proc.stdout


def _build_compare_cmd(axis: str, job: SuiteJob, dataset: str, approach: str, max_workers: int) -> list[str]:
    script = (
        REPO_ROOT / "benchmarks" / "comparisons" / "benchmark_compare_complexity.py"
        if axis == "complexity"
        else REPO_ROOT / "benchmarks" / "comparisons" / "benchmark_compare_completeness.py"
    )

    cmd = [
        sys.executable,
        str(script),
        "--dataset",
        dataset,
        "--approach",
        approach,
        "--max-workers",
        str(max_workers),
        "--provider",
        job.llm_mode,
        "--llm-model",
        job.model_name,
        "--llm-temperature",
        str(job.llm_temperature),
        "--llm-timeout",
        str(job.llm_timeout),
        "--master-seed",
        str(job.master_seed),
    ]

    if job.model_version:
        cmd.extend(["--llm-model-version", job.model_version])
    if job.llm_base_url:
        cmd.extend(["--llm-base-url", job.llm_base_url])
    if job.llm_seed is not None:
        cmd.extend(["--llm-seed", str(job.llm_seed)])
    if job.run_tag:
        cmd.extend(["--run-tag", job.run_tag])

    return cmd


def _build_uq_cmd(axis: str, input_json: Path, output_dir: Path, run_tag: Optional[str], seed: int) -> list[str]:
    uq_script = REPO_ROOT / "benchmarks" / "metrics" / "petri_net_uq.py"
    tag = f"_{normalize_model_slug(run_tag)}" if run_tag else ""

    csv_path = output_dir / f"uq_{axis}{tag}_results.csv"
    manifest_path = output_dir / f"uq_{axis}{tag}_manifest.json"
    plot_path = output_dir / f"uq_{axis}{tag}_plot.png"

    return [
        sys.executable,
        str(uq_script),
        str(input_json),
        "--axis",
        axis,
        "--seed",
        str(seed),
        "--csv",
        str(csv_path),
        "--manifest",
        str(manifest_path),
        "--plot",
        str(plot_path),
    ]


def run_for_model(
    job: SuiteJob,
    complexity_dataset: str,
    completeness_dataset: str,
    approach: str,
    max_workers: int,
) -> SuiteResult:
    model_slug = normalize_model_slug(job.model_name)
    errors: list[str] = []

    complexity_json, _, _, _ = build_default_output_paths(
        repo_root=REPO_ROOT,
        benchmark_axis="complexity",
        model_name=job.model_name,
        run_tag=job.run_tag,
    )
    completeness_json, _, _, _ = build_default_output_paths(
        repo_root=REPO_ROOT,
        benchmark_axis="completeness",
        model_name=job.model_name,
        run_tag=job.run_tag,
    )

    complexity_dir = complexity_json.parent
    completeness_dir = completeness_json.parent

    complexity_cmd = _build_compare_cmd("complexity", job, complexity_dataset, approach, max_workers)
    complexity_ok, complexity_out = _run(complexity_cmd)
    if not complexity_ok:
        errors.append(f"complexity compare failed for {job.model_name}")

    completeness_cmd = _build_compare_cmd("completeness", job, completeness_dataset, approach, max_workers)
    completeness_ok, completeness_out = _run(completeness_cmd)
    if not completeness_ok:
        errors.append(f"completeness compare failed for {job.model_name}")

    uq_complexity_ok = False
    uq_completeness_ok = False

    if complexity_ok and complexity_json.exists():
        uq_complexity_cmd = _build_uq_cmd(
            axis="complexity",
            input_json=complexity_json,
            output_dir=complexity_dir,
            run_tag=job.run_tag,
            seed=job.master_seed,
        )
        uq_complexity_ok, uq_complexity_out = _run(uq_complexity_cmd)
        if not uq_complexity_ok:
            errors.append(f"complexity uq failed for {job.model_name}")
    else:
        uq_complexity_out = "skipped"

    if completeness_ok and completeness_json.exists():
        uq_completeness_cmd = _build_uq_cmd(
            axis="completeness",
            input_json=completeness_json,
            output_dir=completeness_dir,
            run_tag=job.run_tag,
            seed=job.master_seed,
        )
        uq_completeness_ok, uq_completeness_out = _run(uq_completeness_cmd)
        if not uq_completeness_ok:
            errors.append(f"completeness uq failed for {job.model_name}")
    else:
        uq_completeness_out = "skipped"

    suite_log = {
        "model_name": job.model_name,
        "model_slug": model_slug,
        "complexity_compare": {"ok": complexity_ok, "log": complexity_out},
        "completeness_compare": {"ok": completeness_ok, "log": completeness_out},
        "complexity_uq": {"ok": uq_complexity_ok, "log": uq_complexity_out},
        "completeness_uq": {"ok": uq_completeness_ok, "log": uq_completeness_out},
    }

    log_path = REPO_ROOT / "benchmarks" / "results" / "models" / model_slug / f"suite_log_{normalize_model_slug(job.run_tag or 'default')}.json"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as fh:
        json.dump(suite_log, fh, indent=2, ensure_ascii=False)

    return SuiteResult(
        model_name=job.model_name,
        model_slug=model_slug,
        complexity_ok=complexity_ok,
        completeness_ok=completeness_ok,
        uq_complexity_ok=uq_complexity_ok,
        uq_completeness_ok=uq_completeness_ok,
        errors=errors,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run complexity/completeness benchmark suite per model")
    parser.add_argument(
        "--models",
        nargs="+",
        required=True,
        help="List of model names to run (e.g. 'gpt-oss:20b' 'qwen/qwen3-32b')",
    )
    parser.add_argument("--model-version", default=None, help="Optional shared model version label")
    parser.add_argument("--provider", "--llm-mode", dest="llm_mode", choices=["openai", "openai_compatible", "anthropic"], default="openai_compatible")
    parser.add_argument("--llm-base-url", default=None)
    parser.add_argument("--llm-temperature", type=float, default=0.0)
    parser.add_argument("--llm-seed", type=int, default=None)
    parser.add_argument("--llm-timeout", type=float, default=600.0)
    parser.add_argument("--master-seed", type=int, default=42)
    parser.add_argument("--run-tag", default=None)

    parser.add_argument(
        "--complexity-dataset",
        default="benchmarks/datasets/benchmark_dataset_1_150.jsonl",
    )
    parser.add_argument(
        "--completeness-dataset",
        default="benchmarks/datasets/benchmark_dataset_completeness_1_16_50samples.jsonl",
    )
    parser.add_argument("--approach", choices=["planner_executor", "vanilla", "both"], default="both")
    parser.add_argument("--max-workers", type=int, default=4)

    args = parser.parse_args()

    started = datetime.now(timezone.utc).isoformat()

    results: list[SuiteResult] = []
    for model_name in args.models:
        job = SuiteJob(
            model_name=model_name,
            model_version=args.model_version,
            llm_mode=args.llm_mode,
            llm_base_url=args.llm_base_url,
            llm_temperature=args.llm_temperature,
            llm_seed=args.llm_seed,
            llm_timeout=args.llm_timeout,
            run_tag=args.run_tag,
            master_seed=args.master_seed,
        )
        print(f"[suite] Running model: {model_name}")
        result = run_for_model(
            job=job,
            complexity_dataset=args.complexity_dataset,
            completeness_dataset=args.completeness_dataset,
            approach=args.approach,
            max_workers=args.max_workers,
        )
        results.append(result)

    summary = {
        "started_at": started,
        "ended_at": datetime.now(timezone.utc).isoformat(),
        "args": vars(args),
        "results": [asdict(r) for r in results],
    }

    out = REPO_ROOT / "benchmarks" / "results" / "models" / f"suite_summary_{normalize_model_slug(args.run_tag or 'default')}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, ensure_ascii=False)

    print(f"[suite] Summary saved to: {out}")


if __name__ == "__main__":
    main()
