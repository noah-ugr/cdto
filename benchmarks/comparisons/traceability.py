"""
Shared traceability helpers for benchmark comparison runners.

These utilities provide reproducible run identity, environment provenance,
stable model folder naming, and manifest serialization.
"""

from __future__ import annotations

import hashlib
import json
import platform as _platform
import re
import subprocess
import sys
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from typing import Any, Dict, Optional


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_run_id() -> str:
    return str(uuid.uuid4())


def pkg_version(name: str) -> str:
    try:
        return version(name)
    except Exception:
        return "unknown"


def git_commit() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
            timeout=3,
        )
        return out.decode().strip()
    except Exception:
        return "not-a-git-repo"


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65_536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def normalize_model_slug(model_name: str) -> str:
    # Normalize path-unsafe chars to '_' and keep lowercase for predictable paths.
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "_", (model_name or "unknown_model").strip())
    slug = slug.strip("._-") or "unknown_model"
    return slug.lower()


def fingerprint_dict(payload: Dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def derive_group_seed(master_seed: int, approach: str, level: int) -> int:
    seed_src = f"{master_seed}:{approach}:{level}".encode("utf-8")
    return int(hashlib.sha256(seed_src).hexdigest()[:8], 16)


def infer_seed_effective(llm_mode: str, llm_seed: Optional[int]) -> bool:
    if llm_seed is None:
        return False
    # Seed support is provider-specific; OpenAI tends to support it directly.
    return llm_mode in {"openai"}


@dataclass
class BenchmarkRunManifest:
    run_id: str
    timestamp_utc: str
    benchmark_axis: str
    run_tag: Optional[str]

    dataset_path: str
    dataset_sha256: str
    output_path: str

    provider: str
    llm_mode: str
    model_name: str
    model_version: Optional[str]
    base_url: Optional[str]
    temperature: float
    seed: Optional[int]
    seed_effective: bool
    timeout_s: float

    approach: str
    selected_approaches: list[str]

    max_samples: Optional[int]
    samples_per_level: Optional[int]
    selected_levels: list[int]

    min_interval_s: float
    max_retries: int
    backoff_base_s: float
    jitter_s: float
    max_workers: int
    sample_timeout_s: float

    group_seeds: Dict[str, int]
    config_fingerprint_sha256: str

    python_version: str
    numpy_version: str
    scipy_version: str
    joblib_version: str
    platform: str
    git_commit: str

    elapsed_s: float = 0.0
    status: str = "started"


@dataclass
class BenchmarkRunContext:
    run_id: str
    started_at_utc: str
    started_at_perf: float
    dataset_sha256: str
    model_slug: str
    output_file: Path
    failures_file: Path
    manifest_file: Path



def build_default_output_paths(
    repo_root: Path,
    benchmark_axis: str,
    model_name: str,
    run_tag: Optional[str],
) -> tuple[Path, Path, Path, str]:
    model_slug = normalize_model_slug(model_name)
    axis_folder = "complexity" if benchmark_axis == "complexity" else "completeness"
    root = repo_root / "benchmarks" / "results" / "models" / model_slug / axis_folder
    root.mkdir(parents=True, exist_ok=True)

    stem = f"benchmark_compare_{axis_folder}"
    if run_tag:
        stem = f"{stem}_{normalize_model_slug(run_tag)}"

    output_file = root / f"{stem}.json"
    failures_file = root / f"{stem}_failures.jsonl"
    manifest_file = root / f"{stem}_manifest.json"

    return output_file, failures_file, manifest_file, model_slug


def manifest_to_json(manifest: BenchmarkRunManifest) -> Dict[str, Any]:
    return asdict(manifest)


def build_environment_metadata() -> Dict[str, str]:
    return {
        "python_version": sys.version.split()[0],
        "numpy_version": pkg_version("numpy"),
        "scipy_version": pkg_version("scipy"),
        "joblib_version": pkg_version("joblib"),
        "platform": f"{_platform.system()} {_platform.machine()} {_platform.release()}",
        "git_commit": git_commit(),
    }
