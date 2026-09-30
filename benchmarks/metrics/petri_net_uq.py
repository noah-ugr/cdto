"""
petri_net_uq.py
================
Uncertainty Quantification (UQ) for LLM-agent benchmarks operating on Petri Nets.

Implements a two-tier bootstrap hierarchy:

    1. BCa Bootstrap       — Efron & Tibshirani (1993) — primary method for all metrics
    2. Double Bootstrap    — Hall (2013)               — exact_match (binary proportion)

Metrics per (approach, complexity/completeness) cell
-----------------------------------------------------
    - exact_match      : binary success rate             [Double Bootstrap]
    - f1_micro         : excision micro-F1               [BCa]
    - latency_s        : mean wall-clock latency (s)     [BCa]
    - total_tokens     : mean total tokens consumed      [BCa]
    - collateral_rate  : collateral damage / pred_keys   [BCa]
    - omission_rate    : omissions / gt_keys             [BCa]

Reproducibility & Traceability
-------------------------------
Every run produces a ``RunManifest`` saved as ``<stem>_manifest.json`` alongside
the results CSV.  The manifest records:

    run_id          — UUID4 that uniquely identifies this execution
    input_sha256    — SHA-256 of the raw input JSON; any byte-level change
                      in the dataset is detected immediately
    seed            — master RNG seed; re-run with the same seed + same
                      library versions → bit-identical CI values
    group_seeds     — per-(approach, level) seeds; any single cell can be
                      reproduced in isolation without re-running everything
    BootstrapResult.seed
                    — seed of each individual bootstrap call; any single CI
                      can be reproduced standalone
    Library versions (numpy, scipy, joblib), Python version, platform, git commit

The CSV output also embeds the manifest as ``#``-prefixed comment lines so
the file is self-describing — open it in any text editor and the full
provenance is visible at the top.

References
----------
Efron, B., & Tibshirani, R. J. (1993). An introduction to the bootstrap. Chapman & Hall.
Hall, P. (2013). The Bootstrap and Edgeworth Expansion. Springer.
"""

from __future__ import annotations

import hashlib
import json
import platform as _platform
import subprocess
import sys
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from scipy import stats


# ──────────────────────────────────────────────────────────────────────────────
# Environment helpers
# ──────────────────────────────────────────────────────────────────────────────

def _pkg_version(name: str) -> str:
    """Return installed package version string, or 'unknown'."""
    try:
        from importlib.metadata import version
        return version(name)
    except Exception:
        return "unknown"


def _git_commit() -> str:
    """Return short HEAD commit hash, or 'not-a-git-repo'."""
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
            timeout=3,
        )
        return out.decode().strip()
    except Exception:
        return "not-a-git-repo"


def _sha256_file(path: Path) -> str:
    """
    Compute SHA-256 hex digest of a file using streaming reads (memory-safe).

    The digest changes if a single byte of the input JSON is modified,
    making it a reliable fingerprint for dataset identity verification.
    """
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65_536), b""):
            h.update(chunk)
    return h.hexdigest()


# ──────────────────────────────────────────────────────────────────────────────
# Data structures
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class BootstrapResult:
    """
    Container for a single bootstrap confidence interval.

    The ``seed`` field records the exact RNG seed used for this call.
    To reproduce this specific CI in isolation::

        rng = np.random.default_rng(result.seed)
        reproduced = _bca_bootstrap(data, rng=rng, ...)   # or _double_bootstrap
    """
    mean: float
    ci_lower: float
    ci_upper: float
    method: str         # "BCa" or "double_bootstrap"
    n_iterations: int
    seed: int           # RNG seed used — enables standalone reproduction


@dataclass
class GroupResult:
    """
    All metric estimates for one (approach, level) cell.

    ``n_samples`` records the actual number of observations used, which
    must equal the designed n=50 per cell for the analysis to be valid.
    """
    approach: str
    level: int          # complexity N  or  completeness C
    n_samples: int      # number of observations in this cell (should be n=50)
    exact_match: BootstrapResult
    f1_micro: BootstrapResult
    latency_s: BootstrapResult
    total_tokens: BootstrapResult
    collateral_rate: BootstrapResult
    omission_rate: BootstrapResult


@dataclass
class RunManifest:
    """
    Complete provenance record for a single UQ run.

    Saved as ``<stem>_manifest.json`` alongside the results CSV.

    Reproduction guarantee
    ----------------------
    Given:
        1. The input file with matching ``input_sha256``
        2. The same ``seed``
        3. The same library versions listed in this manifest

    Re-running ``petri_net_uq.py`` with identical CLI parameters produces
    bit-identical CI values on the same OS / CPU architecture.

    For per-cell reproduction, use ``group_seeds["approach::level"]`` as the
    seed for ``_process_group``; for per-metric reproduction, use the ``seed``
    stored inside each ``BootstrapResult`` in the CSV's companion JSON.
    """
    # ── Identity ────────────────────────────────────────────────────────────
    run_id: str             # UUID4 — unique identifier for this execution
    timestamp_utc: str      # ISO-8601 wall-clock time (UTC)

    # ── Input provenance ────────────────────────────────────────────────────
    input_file: str         # path as provided to the script
    input_sha256: str       # SHA-256 of the raw input JSON file
    n_records: int          # total records in detailed_results
    n_groups: int           # number of (approach, level) cells processed

    # ── UQ hyper-parameters ─────────────────────────────────────────────────
    axis: str               # "complexity" or "completeness"
    alpha: float            # significance level (0.05 → 95 % CI)
    n_iter: int             # BCa resamples
    B1: int                 # double bootstrap outer iterations
    B2: int                 # double bootstrap inner iterations
    seed: int               # master RNG seed
    n_jobs: int             # joblib workers used

    # ── Per-group seeds ──────────────────────────────────────────────────────
    # Maps "approach::level" → seed integer used for that cell.
    # Allows any single cell to be reproduced independently.
    group_seeds: dict       # e.g. {"vanilla::5": 2847361923, ...}

    # ── Environment ─────────────────────────────────────────────────────────
    python_version: str     # e.g. "3.11.5"
    numpy_version: str
    scipy_version: str
    joblib_version: str
    platform: str           # OS + architecture string
    git_commit: str         # short HEAD hash or "not-a-git-repo"

    # ── Runtime ─────────────────────────────────────────────────────────────
    elapsed_s: float = 0.0  # wall-clock seconds; filled after run() completes


# ──────────────────────────────────────────────────────────────────────────────
# Core bootstrap routines  (pure functions — parallelism-safe)
# ──────────────────────────────────────────────────────────────────────────────

def _bca_bootstrap(
    data: np.ndarray,
    statistic: Callable[[np.ndarray], float] = np.mean,
    n_iter: int = 10_000,
    alpha: float = 0.05,
    rng: np.random.Generator | None = None,
    seed: int = 0,
) -> BootstrapResult:
    """

    Bias-Corrected and Accelerated (BCa) Bootstrap — Efron & Tibshirani (1993) & Chapman & Hall. (Capítulo 14).

    Fórmula original (Bias Corrected and Accelerated):
    ─────────────────────────────────────────────────────
    α_BCa = Φ [ ẑ₀ + (ẑ₀ + z_α) / (1 - â (ẑ₀ + z_α)) ]

    Donde:
        Φ          = función de distribución acumulada de la normal estándar
        ẑ₀         = corrección por sesgo (bias correction)
        â          = constante de aceleración (acceleration)
        z_α        = cuantil de la normal estándar para el nivel alpha

    El intervalo final se obtiene evaluando los percentiles ajustados
    sobre la distribución de los replicados bootstrap.

    Corrects for:
      - Bias   (z₀): proportion of bootstrap replicates below the observed
        statistic, mapped to the normal scale.
      - Acceleration (a): estimated via Jackknife leave-one-out replicates
        (Efron & Tibshirani, 1993, §14.3, eq. 14.15).

    The bootstrap replicates always use ``statistic``, not a hardcoded mean,
    so the method is correct for any estimator (mean, median, etc.).

    Parameters
    ----------
    data      : 1-D array of observed values.
    statistic : Callable array → scalar.  Must support a 1-D input.
    n_iter    : Number of bootstrap resamples.
    alpha     : Two-sided significance level.
    rng       : NumPy Generator for reproducibility.
    seed      : Seed that was used to initialise ``rng``; stored in the result
                for traceability — does not affect computation.
    """
    rng = rng or np.random.default_rng(seed)
    n = len(data)

    # Paso 1: Estimación puntual observada (θ̂)
    theta_hat = float(statistic(data))

    # Paso 2: Generar replicados bootstrap (θ̂*)
    # Se crea una matriz de índices para remuestrear con reemplazo
    idx = rng.integers(0, n, size=(n_iter, n))

    # Optimización: si la estadística es la media, usamos vectorización (mucho más rápido)
    if statistic is np.mean:
        boot_stats = data[idx].mean(axis=1)          # shape: (n_iter,)
    else:
        # Versión general (más lenta)
        boot_stats = np.array([statistic(data[idx[i]]) for i in range(n_iter)])

    # ── Corrección por sesgo (Bias Correction) ───────────────────────────────
    # ẑ₀ = Φ⁻¹( proporción de replicados bootstrap < θ̂ )
    # Según la fórmula original: mide cuánto está sesgada la distribución bootstrap
    prop_below = np.mean(boot_stats < theta_hat)
    # Evitamos valores extremos que causarían problemas numéricos
    prop_below = np.clip(prop_below, 1e-6, 1 - 1e-6)
    z0 = stats.norm.ppf(prop_below)                    # ẑ₀

    # ── Constante de aceleración (Acceleration) vía Jackknife ────────────────
    # â estima la asimetría (skewness) de la distribución de la estadística
    if statistic is np.mean:
        # Fórmula cerrada ultra-rápida para la media
        jack_stats = (data.sum() - data) / (n - 1)
    else:
        # Jackknife leave-one-out general
        jack_stats = np.array([statistic(np.delete(data, i)) for i in range(n)])

    jack_mean = jack_stats.mean()
    diffs = jack_mean - jack_stats

    # Fórmula del acceleration constant (Efron & Tibshirani, eq. 14.15)
    num = np.sum(diffs ** 3)
    den = 6.0 * (np.sum(diffs ** 2) ** 1.5)
    a = num / den if den != 0 else 0.0                 # â

    # ── Cálculo de los percentiles ajustados según la fórmula BCa ────────────
    z_lo = stats.norm.ppf(alpha / 2)      # z_{α/2}
    z_hi = stats.norm.ppf(1 - alpha / 2)  # z_{1-α/2}

    def _adj(z_k: float) -> float:
        """
        Función auxiliar que implementa el ajuste BCa:
        α_adj = Φ [ ẑ₀ + (ẑ₀ + z_k) / (1 - â(ẑ₀ + z_k)) ]
        """
        numer = z0 + z_k
        denom = 1.0 - a * (z0 + z_k)

        if denom == 0:
            # Caso degenerado raro
            return alpha / 2 if z_k < 0 else 1 - alpha / 2

        # Fórmula central del BCa
        return float(stats.norm.cdf(z0 + numer / denom))

    # Percentiles ajustados
    pct_lo = np.clip(_adj(z_lo), 0.0, 1.0)
    pct_hi = np.clip(_adj(z_hi), 0.0, 1.0)

    # Intervalo final BCa
    ci_lower = float(np.percentile(boot_stats, 100 * pct_lo))
    ci_upper = float(np.percentile(boot_stats, 100 * pct_hi))

    return BootstrapResult(
        mean=theta_hat,
        ci_lower=ci_lower,
        ci_upper=ci_upper,
        method="BCa",
        n_iterations=n_iter,
        seed=seed,
    )


def _double_bootstrap(
    data: np.ndarray,
    B1: int = 1_000,
    B2: int = 200,
    alpha: float = 0.05,
    rng: np.random.Generator | None = None,
    seed: int = 0,
) -> BootstrapResult:
    """

    Double Bootstrap (Bootstrap Iterado) — Hall (2013) / Davison & Hinkley.

    Fórmula / Idea principal del Double Bootstrap:
    ─────────────────────────────────────────────────────
    Se calibra el nivel α* tal que la cobertura real del intervalo
    interno sea lo más cercana posible a 1−α.

    Procedimiento:
        1. Bootstrap externo (B1 veces): generar muestras x* y calcular θ*
        2. Para cada x*, hacer bootstrap interno (B2 veces) y construir CI con nivel α̃
        3. Calibrar α̃* buscando el valor que hace que θ̂ original caiga dentro
           del CI interno aproximadamente (1−α) de las veces.
        4. Usar ese α̃* calibrado sobre la distribución del bootstrap externo.

    Esto reduce el error de cobertura de orden O(1/n) a O(1/n²).

    Referencia:
        Hall, P. (2013). The Bootstrap and Edgeworth Expansion. Springer.
        También descrito en Davison & Hinkley (1997) como "iterated bootstrap".

    Achieves O(n⁻²) coverage error for binary proportions by calibrating
    the nominal level α̃ so the actual coverage of the inner CI equals 1−α.

    Algorithm
    ---------
    Outer (B₁ resamples of data):
        x*   ~ Bootstrap(data)
        θ*   = mean(x*)           [proportion of successes]
        C*_α̃ = percentile CI of B₂ inner resamples of x*

    Calibration:
        α̃* = argmin |coverage(C*_α̃) − (1−α)|   over α̃ grid

    Final CI:
        Outer θ* distribution evaluated at the calibrated percentiles.

    Parameters
    ----------
    data : 1-D binary array (0/1) — exact_match values.
    B1   : Outer bootstrap iterations.
    B2   : Inner bootstrap iterations per outer resample (50–200 is sufficient
           for calibration; higher B2 increases precision of α̃ at extra cost).
    alpha: Desired two-sided significance level.
    rng  : NumPy Generator.
    seed : Seed used to initialise ``rng``; stored in result for traceability.
    """
    rng = rng or np.random.default_rng(seed)
    n = len(data)
    theta_hat = float(data.mean())          # θ̂ (proporción de éxitos)

    # ── Bootstrap Externo (Nivel 1) ──────────────────────────────────────────
    # Generamos B1 muestras bootstrap del dataset original
    outer_idx = rng.integers(0, n, size=(B1, n))
    outer_samples = data[outer_idx]                    # shape: (B1, n)
    outer_stats = outer_samples.mean(axis=1)           # θ*  → shape: (B1,)

    # ── Calibración del nivel α (Double Bootstrap) ───────────────────────────
    # Buscamos el mejor α̃ tal que el intervalo interno cubra θ̂ cerca de (1-α)
    alpha_grid = np.linspace(0.005, 0.45, 100)         # grid de posibles niveles
    coverage_counts = np.zeros(len(alpha_grid), dtype=np.float64)

    CHUNK = 100  # procesamos en bloques para ahorrar memoria

    for start in range(0, B1, CHUNK):
        end = min(start + CHUNK, B1)
        chunk_samples = outer_samples[start:end]       # (chunk_size, n)
        chunk_size = end - start

        # Bootstrap interno (B2 replicados por cada muestra externa)
        inner_idx = rng.integers(0, n, size=(chunk_size, B2, n))

        # Calculamos la media (proporción) para cada bootstrap interno
        inner_stats = chunk_samples[
            np.arange(chunk_size)[:, None, None], inner_idx
        ].mean(axis=2)                                 # shape: (chunk_size, B2)

        # Para cada candidato α̃, medimos cuántas veces el CI interno cubre θ̂
        for k, a_tilde in enumerate(alpha_grid):
            lo = np.percentile(inner_stats, 100 * a_tilde / 2,       axis=1)
            hi = np.percentile(inner_stats, 100 * (1 - a_tilde / 2), axis=1)

            # ¿Cubre el intervalo interno el valor observado θ̂?
            coverage_counts[k] += np.sum((lo <= theta_hat) & (theta_hat <= hi))

    # Elegimos el α̃ que mejor aproxima la cobertura deseada (1 - alpha)
    coverage = coverage_counts / B1
    idx_best = int(np.argmin(np.abs(coverage - (1.0 - alpha))))
    alpha_star = alpha_grid[idx_best]

    # ── Construcción del intervalo final usando el nivel calibrado ───────────
    ci_lower = float(np.percentile(outer_stats, 100 * alpha_star / 2))
    ci_upper = float(np.percentile(outer_stats, 100 * (1 - alpha_star / 2)))

    return BootstrapResult(
        mean=theta_hat,
        ci_lower=ci_lower,
        ci_upper=ci_upper,
        method="double_bootstrap",
        n_iterations=B1 * B2,
        seed=seed,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Per-group worker  (called by joblib — must be a top-level function)
# ──────────────────────────────────────────────────────────────────────────────

def _process_group(
    approach: str,
    level: int,
    axis: str,
    records: list[dict],
    alpha: float,
    n_iter: int,
    B1: int,
    B2: int,
    seed: int,
) -> GroupResult:
    """
    Compute all UQ metrics for a single (approach, level) cell.

    Seed chain
    ----------
    The ``seed`` argument is the group-level seed stored in ``RunManifest.group_seeds``.
    Six child seeds are derived from it deterministically (fixed order below):

        child_seeds[0] → exact_match   (double bootstrap)
        child_seeds[1] → f1_micro      (BCa)
        child_seeds[2] → latency_s     (BCa)
        child_seeds[3] → total_tokens  (BCa)
        child_seeds[4] → collateral_rate (BCa)
        child_seeds[5] → omission_rate   (BCa)

    Each child seed is stored in the corresponding ``BootstrapResult.seed``,
    enabling any individual CI to be reproduced in isolation.

    Parameters
    ----------
    axis : "complexity" or "completeness" — determines which JSON field to use
           as the grouping level.
    """
    # Derive six child seeds deterministically from the group seed
    rng = np.random.default_rng(seed)
    child_seeds = rng.integers(0, 2**32, size=6).tolist()
    (em_seed, f1_seed, lat_seed, tok_seed, coll_seed, omit_seed) = child_seeds

    # ── Extract arrays ────────────────────────────────────────────────────────
    exact           = np.array([r["exact_match"]          for r in records], dtype=float)
    f1              = np.array([r["f1_micro"]              for r in records], dtype=float)
    latency         = np.array([r["latency_s"]             for r in records], dtype=float)
    tokens          = np.array([r["token_usage"]["total"]  for r in records], dtype=float)
    collateral_rate = np.array([r["collateral_rate"]       for r in records], dtype=float)
    omission_rate   = np.array([r["omission_rate"]         for r in records], dtype=float)

    # ── Bootstrap ─────────────────────────────────────────────────────────────
    em_result   = _double_bootstrap(
        exact,
        B1=B1, B2=B2, alpha=alpha,
        rng=np.random.default_rng(em_seed),
        seed=em_seed,
    )
    f1_result   = _bca_bootstrap(
        f1,              statistic=np.mean, n_iter=n_iter, alpha=alpha,
        rng=np.random.default_rng(f1_seed),   seed=f1_seed,
    )
    lat_result  = _bca_bootstrap(
        latency,         statistic=np.mean, n_iter=n_iter, alpha=alpha,
        rng=np.random.default_rng(lat_seed),  seed=lat_seed,
    )
    tok_result  = _bca_bootstrap(
        tokens,          statistic=np.mean, n_iter=n_iter, alpha=alpha,
        rng=np.random.default_rng(tok_seed),  seed=tok_seed,
    )
    coll_result = _bca_bootstrap(
        collateral_rate, statistic=np.mean, n_iter=n_iter, alpha=alpha,
        rng=np.random.default_rng(coll_seed), seed=coll_seed,
    )
    omit_result = _bca_bootstrap(
        omission_rate,   statistic=np.mean, n_iter=n_iter, alpha=alpha,
        rng=np.random.default_rng(omit_seed), seed=omit_seed,
    )

    return GroupResult(
        approach=approach,
        level=level,
        n_samples=len(records),
        exact_match=em_result,
        f1_micro=f1_result,
        latency_s=lat_result,
        total_tokens=tok_result,
        collateral_rate=coll_result,
        omission_rate=omit_result,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Main class
# ──────────────────────────────────────────────────────────────────────────────

class PetriNetUQ:
    """
    Uncertainty Quantification engine for LLM-agent Petri Net benchmarks.

    Supports both experiment axes:
      - Complexity   (Exp A): groups by ``complexity_nodes``
      - Completeness (Exp B): groups by ``completeness``

    Reproducibility
    ---------------
    Pass ``seed`` to guarantee bit-identical results across runs.  The manifest
    saved by :meth:`save_manifest` records everything needed to re-run or audit.

    Parameters
    ----------
    json_path  : Path to the benchmark JSON containing ``detailed_results``.
    axis       : ``"complexity"`` (default) or ``"completeness"``.
    alpha      : Two-sided significance level (default 0.05 → 95 % CI).
    n_iter     : BCa bootstrap iterations.
    B1, B2     : Outer / inner iterations for the Double Bootstrap on exact_match.
    n_jobs     : Joblib parallel workers (-1 = all CPUs).
    seed       : Master random seed; the complete seed chain is deterministic
                 from this value — see ``RunManifest.group_seeds``.

    Examples
    --------
    >>> # Experiment A — complexity axis
    >>> df = PetriNetUQ.from_json("benchmark_compare_complexity_results.json")

    >>> # Experiment B — completeness axis
    >>> df = PetriNetUQ.from_json(
    ...     "benchmark_compare_completeness_results.json",
    ...     axis="completeness",
    ... )
    """

    _AXIS_FIELD = {
        "complexity":   "complexity",
        "completeness": "completeness",
    }

    def __init__(
        self,
        json_path: str | Path,
        axis: str = "complexity",
        alpha: float = 0.05,
        n_iter: int = 10_000,
        B1: int = 1_000,
        B2: int = 200,
        n_jobs: int = -1,
        seed: int = 42,
    ) -> None:
        if axis not in self._AXIS_FIELD:
            raise ValueError(f"axis must be one of {list(self._AXIS_FIELD)}; got {axis!r}")

        self.json_path = Path(json_path)
        self.axis      = axis
        self.alpha     = alpha
        self.n_iter    = n_iter
        self.B1        = B1
        self.B2        = B2
        self.n_jobs    = n_jobs
        self.seed      = seed
        self._rng      = np.random.default_rng(seed)

        self._records:     list[dict]                         = []
        self._groups:      dict[tuple[str, int], list[dict]]  = {}
        self._results:     list[GroupResult]                  = []
        self._group_seeds: dict[str, int]                     = {}  # manifest payload
        self._input_sha256: str                               = ""
        self.manifest:     RunManifest | None                 = None

    # ── I/O ──────────────────────────────────────────────────────────────────

    def load(self) -> "PetriNetUQ":
        """
        Parse the JSON benchmark output and build (approach, level) groups.

        Also computes the SHA-256 fingerprint of the raw input file so any
        downstream modification of the dataset is detectable.
        """
        level_field = self._AXIS_FIELD[self.axis]

        # ── SHA-256 fingerprint of the input ──────────────────────────────────
        self._input_sha256 = _sha256_file(self.json_path)
        print(
            f"[PetriNetUQ] Input: '{self.json_path.name}' "
            f"(SHA-256: {self._input_sha256[:16]}…)"
        )

        with self.json_path.open("r", encoding="utf-8") as fh:
            raw = json.load(fh)

        self._records = raw["detailed_results"]
        print(f"[PetriNetUQ] Loaded {len(self._records):,} records")
        print(f"[PetriNetUQ] Axis: {self.axis!r}  (field: '{level_field}')")

        for rec in self._records:
            level = int(rec[level_field])
            key   = (rec["approach"], level)
            self._groups.setdefault(key, []).append(rec)

        approaches = sorted({k[0] for k in self._groups})
        levels     = sorted({k[1] for k in self._groups})
        sizes      = [
            len(self._groups[(a, lv)])
            for a in approaches
            for lv in levels
            if (a, lv) in self._groups
        ]
        print(
            f"[PetriNetUQ] Groups: {len(self._groups)} | "
            f"Approaches: {approaches} | "
            f"Levels: {len(levels)} | "
            f"Samples/group: min={min(sizes)} max={max(sizes)} mean={np.mean(sizes):.1f}"
        )
        return self

    # ── Computation ───────────────────────────────────────────────────────────

    def run(self, verbose: int = 5) -> pd.DataFrame:
        """
        Execute the bootstrap pipeline for every (approach, level) group in parallel.

        Builds a :class:`RunManifest` recording full provenance.  Access it via
        ``self.manifest`` after the call, or call :meth:`save_manifest` to persist it.

        Returns
        -------
        pd.DataFrame with columns:
            Approach, Level, NSamples,
            ExactMatch_Mean,      ExactMatch_CI_Lower,      ExactMatch_CI_Upper,
            F1Micro_Mean,         F1Micro_CI_Lower,         F1Micro_CI_Upper,
            Latency_Mean,         Latency_CI_Lower,         Latency_CI_Upper,
            TotalTokens_Mean,     TotalTokens_CI_Lower,     TotalTokens_CI_Upper,
            CollateralRate_Mean,  CollateralRate_CI_Lower,  CollateralRate_CI_Upper,
            OmissionRate_Mean,    OmissionRate_CI_Lower,    OmissionRate_CI_Upper,
        """
        import time

        if not self._groups:
            self.load()

        keys  = sorted(self._groups.keys())
        seeds = self._rng.integers(0, 2**32, size=len(keys)).tolist()

        # Store group→seed mapping for the manifest
        self._group_seeds = {
            f"{ap}::{lv}": int(sd)
            for (ap, lv), sd in zip(keys, seeds)
        }

        run_id    = str(uuid.uuid4())
        ts_start  = datetime.now(timezone.utc)

        print(
            f"[PetriNetUQ] run_id={run_id}\n"
            f"[PetriNetUQ] Starting parallel UQ for {len(keys)} groups | "
            f"n_jobs={self.n_jobs} | "
            f"Double-Bootstrap B1={self.B1}×B2={self.B2} | "
            f"BCa n_iter={self.n_iter:,} | "
            f"seed={self.seed}"
        )

        t0 = time.perf_counter()
        self._results = Parallel(n_jobs=self.n_jobs, verbose=verbose)(
            delayed(_process_group)(
                approach=ap,
                level=lv,
                axis=self.axis,
                records=self._groups[(ap, lv)],
                alpha=self.alpha,
                n_iter=self.n_iter,
                B1=self.B1,
                B2=self.B2,
                seed=int(sd),
            )
            for (ap, lv), sd in zip(keys, seeds)
        )
        elapsed = time.perf_counter() - t0

        # ── Build RunManifest ─────────────────────────────────────────────────
        self.manifest = RunManifest(
            run_id=run_id,
            timestamp_utc=ts_start.isoformat(),
            input_file=str(self.json_path),
            input_sha256=self._input_sha256,
            n_records=len(self._records),
            n_groups=len(self._groups),
            axis=self.axis,
            alpha=self.alpha,
            n_iter=self.n_iter,
            B1=self.B1,
            B2=self.B2,
            seed=self.seed,
            n_jobs=self.n_jobs,
            group_seeds=self._group_seeds,
            python_version=sys.version.split()[0],
            numpy_version=_pkg_version("numpy"),
            scipy_version=_pkg_version("scipy"),
            joblib_version=_pkg_version("joblib"),
            platform=f"{_platform.system()} {_platform.machine()} {_platform.release()}",
            git_commit=_git_commit(),
            elapsed_s=round(elapsed, 3),
        )

        print(
            f"[PetriNetUQ] Completed in {elapsed:.1f}s | "
            f"run_id={run_id[:8]}… | "
            f"input_sha256={self._input_sha256[:16]}…"
        )

        return self._to_dataframe()

    # ── Output formatting ─────────────────────────────────────────────────────

    def _to_dataframe(self) -> pd.DataFrame:
        """Flatten GroupResult objects into a tidy DataFrame."""
        rows = []
        for gr in self._results:
            rows.append({
                "Approach":               gr.approach,
                "Level":                  gr.level,
                "NSamples":               gr.n_samples,  # audit: verify n=50 everywhere
                # Exact Match
                "ExactMatch_Mean":        gr.exact_match.mean,
                "ExactMatch_CI_Lower":    gr.exact_match.ci_lower,
                "ExactMatch_CI_Upper":    gr.exact_match.ci_upper,
                # F1 Micro
                "F1Micro_Mean":           gr.f1_micro.mean,
                "F1Micro_CI_Lower":       gr.f1_micro.ci_lower,
                "F1Micro_CI_Upper":       gr.f1_micro.ci_upper,
                # Latency (seconds)
                "Latency_Mean":           gr.latency_s.mean,
                "Latency_CI_Lower":       gr.latency_s.ci_lower,
                "Latency_CI_Upper":       gr.latency_s.ci_upper,
                # Token consumption
                "TotalTokens_Mean":       gr.total_tokens.mean,
                "TotalTokens_CI_Lower":   gr.total_tokens.ci_lower,
                "TotalTokens_CI_Upper":   gr.total_tokens.ci_upper,
                # Collateral damage rate
                "CollateralRate_Mean":    gr.collateral_rate.mean,
                "CollateralRate_CI_Lower": gr.collateral_rate.ci_lower,
                "CollateralRate_CI_Upper": gr.collateral_rate.ci_upper,
                # Omission rate
                "OmissionRate_Mean":      gr.omission_rate.mean,
                "OmissionRate_CI_Lower":  gr.omission_rate.ci_lower,
                "OmissionRate_CI_Upper":  gr.omission_rate.ci_upper,
            })
        return (
            pd.DataFrame(rows)
            .sort_values(["Approach", "Level"])
            .reset_index(drop=True)
        )

    def save_csv(
        self,
        df: pd.DataFrame,
        path: str | Path = "petri_uq_results.csv",
    ) -> Path:
        """
        Persist the results DataFrame to a self-describing CSV.

        The file begins with ``#``-prefixed comment lines containing the full
        ``RunManifest`` so provenance is embedded directly in the data file.
        Opening the CSV in any text editor immediately shows the run parameters,
        input hash, seed, and library versions used.

        Format::

            # PetriNetUQ Run Manifest
            # run_id: <uuid>
            # timestamp_utc: <ISO-8601>
            # input_file: ...
            # input_sha256: <sha256>
            # ...
            # --- data below ---
            Approach,Level,NSamples,...
            vanilla,1,50,...
        """
        out = Path(path)

        # ── Build manifest comment header ──────────────────────────────────────
        lines = ["# PetriNetUQ Run Manifest"]
        if self.manifest:
            d = asdict(self.manifest)
            # Flatten group_seeds separately (it's a dict)
            group_seeds = d.pop("group_seeds")
            for k, v in d.items():
                lines.append(f"# {k}: {v}")
            lines.append("# group_seeds:")
            for gk, gv in sorted(group_seeds.items()):
                lines.append(f"#   {gk}: {gv}")
        else:
            lines.append("# (manifest not available — call run() first)")
        lines.append("# --- data below ---")

        header_block = "\n".join(lines) + "\n"

        with out.open("w", encoding="utf-8") as fh:
            fh.write(header_block)
            df.to_csv(fh, index=False)

        print(f"[PetriNetUQ] Results saved → {out}")
        return out

    def save_manifest(
        self,
        path: str | Path | None = None,
    ) -> Path:
        """
        Write the ``RunManifest`` to a JSON file.

        Parameters
        ----------
        path : Output path.  Defaults to ``<json_stem>_manifest.json`` in the
               same directory as the input file.

        Returns
        -------
        Path to the saved manifest file.
        """
        if self.manifest is None:
            raise RuntimeError("No manifest available — call run() first.")

        if path is None:
            path = self.json_path.with_name(
                self.json_path.stem + "_manifest.json"
            )
        out = Path(path)
        with out.open("w", encoding="utf-8") as fh:
            json.dump(asdict(self.manifest), fh, indent=2)
        print(f"[PetriNetUQ] Manifest saved → {out}")
        return out

    # ── Visualisation ─────────────────────────────────────────────────────────

    def plot(
        self,
        df: pd.DataFrame,
        metrics: list[str] | None = None,
        figsize: tuple[int, int] = (20, 18),
        save_path: str | Path | None = None,
    ) -> None:
        """
        Render performance curves with 95 % CI shaded bands.

        Each sub-plot shows one metric for both approaches plotted against
        the experiment axis (complexity N or completeness C).

        The figure title includes the ``run_id`` short-code and master ``seed``
        so every saved plot is traceable back to its exact run.

        Parameters
        ----------
        df        : DataFrame returned by :meth:`run`.
        metrics   : Metric base-names to plot. Defaults to all six.
        figsize   : Matplotlib figure size.
        save_path : If provided, save the figure here instead of showing it.
        """
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
        except ImportError:
            raise ImportError("matplotlib is required: pip install matplotlib")

        metrics = metrics or [
            "ExactMatch", "F1Micro",
            "Latency",    "TotalTokens",
            "CollateralRate", "OmissionRate",
        ]

        x_label = (
            "Complexity level (N)"
            if self.axis == "complexity"
            else "Completeness (# instructions)"
        )

        titles = {
            "ExactMatch":      "Exact Match  [Double Bootstrap CI₉₅]",
            "F1Micro":         "Excision Micro-F1  [BCa CI₉₅]",
            "Latency":         "Latency (s)  [BCa CI₉₅]",
            "TotalTokens":     "Total Tokens consumed  [BCa CI₉₅]",
            "CollateralRate":  "Collateral Damage Rate  [BCa CI₉₅]",
            "OmissionRate":    "Omission Rate  [BCa CI₉₅]",
        }
        ylabels = {
            "ExactMatch":      "Proportion",
            "F1Micro":         "F1 Score",
            "Latency":         "Seconds",
            "TotalTokens":     "Tokens",
            "CollateralRate":  "collateral / pred_keys",
            "OmissionRate":    "omissions / gt_keys",
        }

        palette = {
            "planner_executor": ("#2563EB", "#BFDBFE"),
            "vanilla":          ("#DC2626", "#FECACA"),
        }

        approaches = sorted(df["Approach"].unique())
        n_metrics  = len(metrics)
        ncols      = 2
        nrows      = (n_metrics + ncols - 1) // ncols

        fig, axes = plt.subplots(nrows, ncols, figsize=figsize)
        axes = np.array(axes).flatten()

        for ax, metric in zip(axes, metrics):
            col_mean = f"{metric}_Mean"
            col_lo   = f"{metric}_CI_Lower"
            col_hi   = f"{metric}_CI_Upper"

            for approach in approaches:
                sub  = df[df["Approach"] == approach].sort_values("Level")
                x    = sub["Level"].values
                mean = sub[col_mean].values
                lo   = sub[col_lo].values
                hi   = sub[col_hi].values

                line_color, fill_color = palette.get(approach, ("#555", "#ccc"))
                label = approach.replace("_", " ").title()

                ax.plot(x, mean, color=line_color, linewidth=2.0, label=label)
                ax.fill_between(x, lo, hi, color=fill_color, alpha=0.35)

            ax.set_title(titles.get(metric, metric), fontsize=11, fontweight="bold", pad=8)
            ax.set_xlabel(x_label, fontsize=9)
            ax.set_ylabel(ylabels.get(metric, ""), fontsize=9)
            ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.6)
            ax.legend(fontsize=8)
            ax.tick_params(labelsize=8)
            ax.spines[["top", "right"]].set_visible(False)

        for ax in axes[n_metrics:]:
            ax.set_visible(False)

        # ── Traceable figure title ─────────────────────────────────────────────
        axis_label = self.axis.capitalize()
        run_tag = (
            f"run_id={self.manifest.run_id[:8]}… | seed={self.seed} | "
            f"sha256={self.manifest.input_sha256[:12]}…"
            if self.manifest
            else f"seed={self.seed}"
        )
        fig.suptitle(
            f"PetriNet LLM Benchmark — Uncertainty Quantification\n"
            f"Axis: {axis_label} | n=50 per group | Bootstrap CI₉₅\n"
            f"{run_tag}",
            fontsize=12,
            fontweight="bold",
            y=1.02,
        )
        plt.tight_layout()

        if save_path:
            out = Path(save_path)
            fig.savefig(out, dpi=150, bbox_inches="tight")
            print(f"[PetriNetUQ] Plot saved → {out}")
        else:
            plt.show()

        plt.close(fig)

    # ── Convenience factory ───────────────────────────────────────────────────

    @classmethod
    def from_json(
        cls,
        json_path: str | Path,
        *,
        axis: str = "complexity",
        alpha: float = 0.05,
        n_iter: int = 10_000,
        B1: int = 1_000,
        B2: int = 200,
        n_jobs: int = -1,
        seed: int = 42,
        csv_path: str | Path | None = "petri_uq_results.csv",
        manifest_path: str | Path | None = None,   # None → auto-named
        plot_path: str | Path | None = "petri_uq_plot.png",
        verbose: int = 5,
    ) -> pd.DataFrame:
        """
        Factory shortcut: load → run → save → plot in one call.

        Saves three artefacts by default:
          1. ``petri_uq_results.csv``   — results with embedded manifest header
          2. ``<input>_manifest.json``  — full :class:`RunManifest` as JSON
          3. ``petri_uq_plot.png``      — figures with run fingerprint in title

        Parameters
        ----------
        axis          : ``"complexity"`` (Exp A) or ``"completeness"`` (Exp B).
        csv_path      : Output CSV path; pass ``None`` to skip.
        manifest_path : Output manifest path; ``None`` → ``<input>_manifest.json``.
        plot_path     : Output plot path; pass ``None`` to skip.

        Returns
        -------
        pd.DataFrame with all UQ results.
        """
        uq = cls(
            json_path=json_path,
            axis=axis,
            alpha=alpha,
            n_iter=n_iter,
            B1=B1,
            B2=B2,
            n_jobs=n_jobs,
            seed=seed,
        )
        df = uq.run(verbose=verbose)

        if csv_path:
            uq.save_csv(df, csv_path)

        # Always save manifest (unless the user explicitly passed csv_path=None
        # and manifest_path=None, which means they want no output at all)
        if csv_path is not None or manifest_path is not None:
            uq.save_manifest(manifest_path)  # None → auto-named

        if plot_path:
            uq.plot(df, save_path=plot_path)

        return df


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    import time

    parser = argparse.ArgumentParser(
        description=(
            "Bootstrap UQ for Petri Net LLM benchmarks.\n\n"
            "Reproducibility: re-run with the same --seed and input file "
            "(verify via SHA-256 in the manifest) to get bit-identical CIs."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "json_file",
        nargs="?",
        default="benchmarks\\results\\models\\llama3.1_latest\\completeness\\benchmark_compare_completeness.json",
        help="Path to benchmark JSON (default: benchmark_compare_complexity.json)",
    )
    parser.add_argument(
        "--axis",
        choices=["complexity", "completeness"],
        default="completeness",
        help="Grouping axis: 'complexity' (Exp A) or 'completeness' (Exp B) [default: complexity]",
    )
    parser.add_argument("--B1",      type=int,   default=1_000,  help="Outer bootstrap iterations [default: 1000]")
    parser.add_argument("--B2",      type=int,   default=200,    help="Inner bootstrap iterations [default: 200]")
    parser.add_argument("--n-iter",  type=int,   default=10_000, help="BCa bootstrap iterations [default: 10000]")
    parser.add_argument("--n-jobs",  type=int,   default=-1,     help="Joblib workers [default: -1 = all CPUs]")
    parser.add_argument("--seed",    type=int,   default=42,     help="Master random seed [default: 42]")
    parser.add_argument("--csv",     default="petri_uq_results.csv",   help="Output CSV path")
    parser.add_argument("--manifest",default=None,                     help="Output manifest JSON path (default: <input>_manifest.json)")
    parser.add_argument("--plot",    default="petri_uq_plot.png",      help="Output plot path")
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Quick smoke-test: reduce B1/B2/n_iter significantly",
    )
    args = parser.parse_args()

    if args.smoke:
        args.B1, args.B2, args.n_iter = 200, 50, 2_000
        print("[PetriNetUQ] Smoke-test mode: B1=200, B2=50, n_iter=2000")

    t0 = time.perf_counter()
    df = PetriNetUQ.from_json(
        json_path=args.json_file,
        axis=args.axis,
        B1=args.B1,
        B2=args.B2,
        n_iter=args.n_iter,
        n_jobs=args.n_jobs,
        seed=args.seed,
        csv_path=args.csv,
        manifest_path=args.manifest,
        plot_path=args.plot,
        verbose=5,
    )
    elapsed = time.perf_counter() - t0

    print(f"\n[PetriNetUQ] Total wall-clock: {elapsed:.1f}s")
    print(df.to_string(max_rows=30))