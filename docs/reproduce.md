# Reproducing the paper's tables and figures

Each entry gives the command that rebuilds a table or figure of the paper, the files it reads,
and where it writes. Commands run from the repository root, in PowerShell, with the environment
of the [README](../README.md) (on Windows, with `PYTHONIOENCODING=utf-8`).

There are two kinds of steps:

- **Offline:** rebuild a result from files already in the repository or in Zenodo, with no model
  calls.
- **Inference:** call a model. They need a provider key or an OpenAI-compatible server.
  `<BASE_URL>` stands for that server's `/v1` URL.

## Before starting

- **Zenodo files.** The files listed in `benchmarks/results/zenodo_files.sha256` are in the
  Zenodo deposit: the two datasets, the raw and re-scored per-call JSONs of the benchmark, the
  per-batch and per-record CSVs of the validator pass, the per-call log and the B/C results of
  the humanisation check, the logs of the runs of the illustrative case and every result PNG. Put
  them at their listed paths and check them:

  ```bash
  sha256sum -c benchmarks/results/zenodo_files.sha256
  ```

- **LLM variables.** The runners read the model settings from the command line or from
  `LLM_*` / `BENCHMARK_LLM_*`. The driver of the illustrative case refuses to start if any
  variable that would override the model, the URL or the request format is set; its preflight
  lists them.

## Figures and tables of the paper

Where each figure and table of the manuscript (`M`) and the Supplementary Material (`S`) comes
from. "Zenodo" marks files of the deposit, listed in `benchmarks/results/zenodo_files.sha256`.

### Figures

| Paper | File in the paper sources | File in the repository | Made by |
|---|---|---|---|
| M `fig:maintenance_evolution` | `Figures/maintenance_evolution.pdf` | none: drawing | — |
| M `fig:overview` | TikZ in the manuscript | `docs/figures/CDTO_graphical_abstract.png` (the same design, used as graphical abstract) | — |
| M `fig:petrinet_architecture` | `Figures/rect5.pdf` | none: drawing of the net | — |
| M `fig:pipeline` | TikZ in the manuscript | none | — |
| M `fig:dataset_pipeline` | TikZ in the manuscript | none | — |
| M `fig:agent_interactions`, boxes A–E | text in the manuscript | `q1`–`q7/response.json` of `benchmarks/results/case_study_rerun/20260930T001541Z_gpt-oss-20b-ctx32k/` (condensed) | `rerun_case_study.py` |
| M `fig:agent_interactions`, box F | text in the manuscript | `q8/response.json` of `benchmarks/results/case_study_rerun/20260930T001926Z_gpt-oss-20b-ctx32k_with_opt/` (condensed) | `rerun_case_study.py --with-optimization` |
| M `fig:gantt_chart_modified` | `Figures/gantt_chart_comparison_new.pdf` | `benchmarks/results/case_study_gantt/20260929T093403Z_gantt_paper_format/gantt_A001.pdf` | `plot_gantt_comparison.py` on the simulations of `20260929T084426Z_gantt` |
| M `fig:cost_axis` | `complexity_results/multi_model_uq_complexity_v2.pdf` | `benchmarks/results/models/aggregated/multi_model_uq_complexity_v2.pdf` | `plot_multi_model_uq.py --axis complexity` |
| M `fig:fidelity_axis` | `completeness_results/multi_model_uq_completeness_v2.pdf` | `benchmarks/results/models/aggregated/multi_model_uq_completeness_v2.pdf` | `plot_multi_model_uq.py --axis completeness` |
| S `supp:fig:iwo_convergence` | `Figures/iwo_convergence.png` | `q8/iwo_convergence.png` of `20260930T001926Z_gpt-oss-20b-ctx32k_with_opt` (Zenodo) | the IWO, in query 8 of the illustrative case |
| S `supp:fig:petristate`, `supp:fig:contracts` | text in the supplementary | none | — |
| S `fig:cdto_full_landscape` | `Figures/CDTO_interface.pdf`, `CDTO_json.pdf`, `forensic_analysis.pdf`, `causality.pdf`, `temporal_narrative.pdf`, `temporal_state.pdf` | none: screenshots of the web interface (`frontend/`) | — |

`gantt_chart_comparison.pdf` in `benchmarks/results/case_study_gantt/20260929T084426Z_gantt/` is
an earlier two-panel drawing of the same simulations, not the figure of the paper; the paper's
`gantt_chart_comparison_new.pdf` is `gantt_A001.pdf` byte for byte, except its creation date. The
figures of `benchmarks/results/models/aggregated/delta_<axis>/` (`plot_delta_uq.py`) are not used
in the paper.

### Tables

| Paper | Source in the repository |
|---|---|
| M `tab:petri_net_config`, `tab:dsl`, `tab:metrics` | Descriptive; `input_agent/src/models.py` (operations of the edit language) and `benchmarks/metrics/comparison_metrics.py` (metrics) |
| M `tab:rules` | `check_configuration` in `input_agent/src/tools.py`; [validator.md](validator.md) |
| M `tab:simulation_configuration` | $S_0$ in `core/api.py` (`initial_input`); `S0.json` of each run of the illustrative case |
| M `tab:agent_eval` | Queries in `benchmarks/case_study/rerun_case_study.py`; `q*/node_updates.json` of the two runs of the illustrative case |
| M `tab:cdto_improvement_summary` | `benchmarks/results/cdto_vs_vanilla_by_model_axis_regime.csv` |
| S `supp:tab:iwo_params` | Optimiser code (third-party, not in this release) |
| S `supp:tab:schema` | `input_agent/pn_models.py` (declared types) and `input_agent/src/dataset_generator_complexity.py` (value domains) |
| S `supp:tab:metrics` | Constants of `benchmarks/metrics/comparison_metrics.py` |
| S `supp:tab:cstar` | `benchmarks/results/c_star_by_backend.csv` |
| S `supp:tab:split` | No versioned file: medians of `token_usage` in the raw `benchmark_compare_complexity.json` files (Zenodo), without the calls that logged no usage |
| S `supp:tab:models` | `summary` blocks of the benchmark JSONs; `manifest.json` of the humanisation check and of the runs of the illustrative case; [benchmark.md](benchmark.md#deployment-environments) |

## Benchmark

### Raw runs (inference)

One run per model and axis. The recorded runs used these arguments; the other settings are
the runners' defaults, listed in [benchmark.md](benchmark.md#runs).

```powershell
# Complexity axis: the 16 evaluated levels, 50 samples each
python benchmarks/comparisons/benchmark_compare_complexity.py `
  --provider <anthropic|openai|openai_compatible> --llm-model <model> [--llm-base-url <BASE_URL>] `
  --complexity 1 5 10 12 14 16 18 20 24 28 32 40 50 80 100 150 --samples-per-complexity 50

# Completeness axis: levels 1-15, every sample
python benchmarks/comparisons/benchmark_compare_completeness.py `
  --provider <anthropic|openai|openai_compatible> --llm-model <model> [--llm-base-url <BASE_URL>]
```

| LLM | `--provider` | `--llm-model` |
|---|---|---|
| Claude Sonnet 4.6 | `anthropic` | `claude-sonnet-4-6` |
| GPT-5.4 | `openai` | `gpt-5.4` |
| gpt-oss:20b | `openai_compatible` | `gpt-oss:20b` (add `--request-profile 2026-04-28-benchmark` for the request format of the recorded run) |
| Llama 3.1 8B | `openai_compatible` | `llama3.1:latest` |

- **Output:** `benchmarks/results/models/<model_slug>/<axis>/benchmark_compare_<axis>.json`.
- **Not bit-reproducible.** Temperature 0 without a seed does not give identical outputs, and
  the recorded Ollama runs did not log the server version or model digest.

### Rescoring (offline)

```powershell
python benchmarks/metrics/rescore_results.py --validation-csv benchmarks/results/rescoring_validation.csv
```

- It writes `benchmark_compare_<axis>_rescored.json` next to each raw file, and
  `rescoring_validation.csv`.
- `--legacy-structural-keys` scores the same calls under the pre-correction metric
  (`*_rescored_legacy.json`), for comparison. Those scores are not used in the paper.

### Per-cell intervals (offline)

For each model and axis:

```powershell
$m = "gpt-oss_20b"; $axis = "complexity"   # also completeness, and each model
python benchmarks/metrics/petri_net_uq.py `
  benchmarks/results/models/$m/$axis/benchmark_compare_${axis}_rescored.json --axis $axis --seed 42 `
  --csv benchmarks/results/models/$m/$axis/uq_${axis}_results.csv `
  --manifest benchmarks/results/models/$m/$axis/benchmark_compare_${axis}_manifest.json `
  --plot benchmarks/results/models/$m/$axis/petri_uq_plot.png
```

With the same library versions (recorded in the manifest), the intervals are bit-identical.

### Tables built on the per-cell intervals (offline)

| Paper element | Command | Output |
|---|---|---|
| `tab:cdto_improvement_summary`, P-E vs vanilla (rows per model, axis and regime; per-model means; overall mean below the thresholds) | `python benchmarks/metrics/cdto_vs_vanilla_summary.py` | `benchmarks/results/cdto_vs_vanilla_{by_model_axis_regime,mean_per_model,overall}.csv` |
| `tab:cdto_improvement_summary` with the earlier split at the cl100k C*_low (49) | `python benchmarks/metrics/cdto_vs_vanilla_summary.py --budget-safe-max-level 49 --output-suffix _cut49` | `…_cut49.csv` |
| `\tokflat`, `\tokgrowth`, `\tokcross`: token cost along complexity (flatness of P-E, growth of vanilla, crossing level), per model and as macros | `python benchmarks/metrics/token_cost_summary.py`; `--exclude-zero-tokens` recomputes the means without the calls that logged no tokens | `benchmarks/results/token_cost_summary.csv` (`token_cost_summary_exclude_zero_tokens.csv`) |
| Truncation at the output limit per level | `python benchmarks/metrics/output_truncation.py --axis completeness` (gpt-oss:20b and Llama 3.1, the default) and `python benchmarks/metrics/output_truncation.py --axis complexity --models claude-sonnet-4-6 gpt-5.4 gpt-oss_20b llama3.1_latest` | `benchmarks/results/truncation_<axis>_by_level.csv` |
| Effect of zero-token vanilla calls on the means below the thresholds | `python benchmarks/metrics/zero_token_calls.py` | `benchmarks/results/zero_token_calls.csv` |
| Footnote of Subsection 6.3: Llama 3.1 without the samples that have a zero-token vanilla call (`drop_paired`). Token delta at complexity C ≤ 32 (+5.4 %) and at completeness (−16.5 %); largest change of the exact-match advantage over the two regimes (−0.7 pp, at complexity) | `python benchmarks/metrics/zero_token_calls.py` (prints the three figures per model) | `benchmarks/results/zero_token_calls_by_axis.csv` (`TotalTokens` and `ExactMatchChange`, row `drop_paired`) |
| Output-budget threshold C* (cl100k): length per level and C*_low 49, C*_mean 90, C*_high 115 | `python benchmarks/metrics/budget_complexity.py` | `benchmarks/results/budget_complexity_cl100k.csv` |
| `supp:tab:cstar`, output-budget thresholds per model (outputs, r_b, m_b, C*_low, C*_mean, C*_high in each model's tokens) | `python benchmarks/metrics/c_star_by_backend.py`; `--variants` adds the definitions that do not reproduce them. Exits with status 1 if a C*_low differs from `c_star.py` | `benchmarks/results/c_star_by_backend.csv` |
| Per-level means and 95 % intervals archived for the note of `tab:cdto_improvement_summary` (six metrics, per model, axis and approach; corrected metric; intervals as in Supplementary Material C) | `python benchmarks/metrics/per_level_tables.py` | `benchmarks/results/per_level/per_level_{complexity,completeness}.csv` and `per_level_tables.md` |

The per-model C* markers of the complexity figures are constants in
[benchmarks/aggregator/c_star.py](../benchmarks/aggregator/c_star.py): the C*_low column of
`c_star_by_backend.csv` (Claude 34, Llama 38, gpt-oss 45, GPT-5.4 48), which the script checks.

### Figures (offline)

```powershell
$models = "claude-sonnet-4-6", "gpt-oss_20b", "gpt-5.4", "llama3.1_latest"
$labels = "Claude Sonnet 4.6", "gpt-oss-20b", "GPT 5.4", "Llama 3.1"
foreach ($axis in "complexity", "completeness") {
  # Per-cell intervals of every model
  python benchmarks/aggregator/plot_multi_model_uq.py --axis $axis --models $models --labels $labels
  # Paired P-E - vanilla deltas (architecture effect) and model effects against GPT-5.4
  python benchmarks/aggregator/plot_delta_uq.py --axis $axis --models $models --labels $labels `
    --reference-model gpt-5.4 --seed 42 --n-iter 10000 --run-tag rescored `
    --output-dir benchmarks/results/models/aggregated/delta_$axis
}
```

- `plot_multi_model_uq.py` writes `benchmarks/results/models/aggregated/multi_model_uq_<axis>_v2.pdf`.
- `plot_delta_uq.py` writes `fig1_architecture_effect.pdf`, `fig2_model_effect_agentic.pdf` and
  `fig3_model_effect_vanilla.pdf` to `--output-dir`.
- **Arguments.** The model order sets the colours and the bootstrap seed of each series.
  `--run-tag rescored` makes `plot_delta_uq.py` read `benchmark_compare_<axis>_rescored.json`, the
  corrected metric; without it, it reads the raw logs. With these commands every versioned PDF is
  reproduced byte for byte except its creation date.

## Validator

| Paper element | Command | Output |
|---|---|---|
| Offline pass of the validator over the P-E batches: categories, rejection rates (`\rejrate`, `\rejreq`, `\rejcatch` from `pe_summary.csv`), per group, c2 per rule (offline) | `python benchmarks/metrics/validator_pass.py --rules-commit c818998` | `benchmarks/results/validator_pass/<run_id>/` |
| Per-rule table of [validator.md](validator.md#per-rule), and the rejections whose only violation is a cycle in a list the net does not read | `python benchmarks/metrics/validator_rule_table.py` (reads `pe_batches.csv`, from Zenodo) | `pe_rules_by_category.csv` and `pe_cycle_only_rejections.csv` in the run folder |

The recorded run is `20260928T224634Z_c818998_9ed0ce`.

## Humanisation check (inference)

```powershell
$run = "benchmarks/results/humanisation_check/<run_id>"
python -m benchmarks.humanisation_check.select_samples --run-dir $run      # 25 per level, seed 42
python -m benchmarks.humanisation_check.rehumanise --run-dir $run --model qwen2.5:32b --base-url <BASE_URL>
python -m benchmarks.humanisation_check.fidelity --run-dir $run
python -m benchmarks.humanisation_check.run_paired --run-dir $run --llm-base-url <BASE_URL> `
  --derived-model gpt-oss-20b-ctx32k --server-info <server_info.json>
python -m benchmarks.humanisation_check.compare --run-dir $run
```

- **Server info.** `--server-info` takes the JSON that
  `benchmarks/humanisation_check/collect_server_info.py` prints when run on the Ollama server.
  `--ssh-host` collects it directly.
- **Derived model.** It is created with
  [Modelfile.gpt-oss-20b-ctx32k](../benchmarks/humanisation_check/Modelfile.gpt-oss-20b-ctx32k).
- **Offline part.** `compare` is offline once `calls.jsonl` and the B/C results exist. It keeps
  the causes already filled in `discordant_pairs_planner_executor.md`.
- **Output:** `comparison_planner_executor.csv`, `controls_planner_executor.csv` and
  `comparison_summary_planner_executor.json`, which hold the tables of
  [humanisation_check.md](humanisation_check.md#results).

## Illustrative case (Subsections 5.1 and 6.1)

| Paper element | Source |
|---|---|
| Table `tab:simulation_configuration` (initial plan $S_0$) | $S_0$ in `core/api.py` (`initial_input`); copied to `S0.json` by every run |
| Table `tab:agent_eval` (sub-agents and expected behaviour per query) | `q*/node_updates.json` of the two runs below |
| Figure `fig:agent_interactions`, boxes A–E | `q1`–`q7/response.json` of `20260930T001541Z_gpt-oss-20b-ctx32k` |
| Figure `fig:agent_interactions`, box F | `q8` of `20260930T001926Z_gpt-oss-20b-ctx32k_with_opt` |
| Figure `fig:gantt_chart_modified` | `gantt_A001.pdf` of `benchmarks/results/case_study_gantt/20260929T093403Z_gantt_paper_format/` |
| Attributions in the text (per-edit KPI changes, Supplementary Material D) | `benchmarks/results/case_study_attribution/20260929T095804Z_single_edits/summary.csv` |

### Queries 1–7, categories A to E (inference)

```powershell
$Model = "gpt-oss-20b-ctx32k"; $BaseUrl = "<BASE_URL>"
$RunId = "$((Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ'))_$Model"
$env:LLM_PROVIDER = "openai_compatible"; $env:BENCHMARK_LLM_PROVIDER = "openai_compatible"
$env:LLM_MODEL = $Model;                 $env:BENCHMARK_LLM_MODEL = $Model
$env:LLM_BASE_URL = $BaseUrl;            $env:BENCHMARK_LLM_BASE_URL = $BaseUrl
$env:LLM_TEMPERATURE = "0";              $env:BENCHMARK_LLM_TEMPERATURE = "0"
$env:LLM_TIMEOUT = "600";                $env:BENCHMARK_LLM_TIMEOUT = "600"
$env:CDTO_IO_DIR = "C:\tmp\cdto_case_rerun_$RunId"   # an empty folder
$env:PYTHONIOENCODING = "utf-8"
python benchmarks/case_study/rerun_case_study.py --model $Model --base-url $BaseUrl --run-id $RunId --preflight-only
python benchmarks/case_study/rerun_case_study.py --model $Model --base-url $BaseUrl --run-id $RunId
```

The API key goes in `LLM_API_KEY` and `OPENAI_COMPATIBLE_API_KEY`.

### Queries 1–8, category F included (inference)

Use the same variables, and add `--with-optimization` to both commands:

- `$RunId` ends in `_with_opt`.
- `CDTO_IO_DIR` must be `C:\tmp\io`, and the folder must be empty or not exist; the optimizer
  reads and writes that folder. Rename an earlier one instead of deleting it.
- The IWO took 67 minutes in the recorded run.

```powershell
$env:CDTO_IO_DIR = "C:\tmp\io"
python benchmarks/case_study/rerun_case_study.py --model $Model --base-url $BaseUrl --run-id $RunId --with-optimization --preflight-only
python benchmarks/case_study/rerun_case_study.py --model $Model --base-url $BaseUrl --run-id $RunId --with-optimization
```

The preflight checks that `RELEASE.json`, at the repository root, lists every agent fix the run
depends on. In the development repository, write it first with
`python benchmarks/case_study/release_info.py`, which resolves each fix from the git history.

- **Recorded runs:** `20260930T001541Z_gpt-oss-20b-ctx32k` (queries 1–7) and
  `20260930T001926Z_gpt-oss-20b-ctx32k_with_opt` (queries 1–8), with commit `52d74aa`, which
  describes `taskCode` and `activityCode` as what their owner precedes.
- **The two runs** give the same configurations and simulation results for queries 1–7; only
  the LLM texts differ, since the chat template of the model inserts the current date.

### Execution plans and attributions (simulation only, no LLM)

```powershell
python benchmarks/case_study/regenerate_gantt.py                 # simulates S_0 and S_{k+1}
python benchmarks/case_study/plot_gantt_comparison.py `
  --source benchmarks/results/case_study_gantt/<regenerate_gantt run_id>
python benchmarks/case_study/single_edit_attribution.py          # S_0, each edit alone, S_{k+1}
```

- **Recorded runs:** `20260929T084426Z_gantt` (simulations), `20260929T093403Z_gantt_paper_format`
  (figures) and `20260929T095804Z_single_edits`.
- **Checks:** `plot_gantt_comparison.py` does not simulate; it checks the hashes of the source
  run.
- **Determinism:** each simulation runs in a new process. The recorded runs gave identical
  outputs for the same configuration: `general_outputs_all.json` of $S_{k+1}$ has the same
  SHA-256 in the attribution run and in the two runs of the illustrative case.

## Tests

```powershell
python -m pytest tests -q
```