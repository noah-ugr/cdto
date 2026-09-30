# Benchmark: datasets, protocol and environments

This document covers how the benchmark datasets were generated, how many generated samples are
inadmissible, the bootstrap protocol, the manifests every stage writes, and the deployment
environments. The commands that rebuild each result are in [reproduce.md](reproduce.md).

## Datasets

The two datasets are the files below. Every run manifest records their SHA-256.

| Axis | File | Lines | SHA-256 |
|---|---|---|---|
| Complexity | `benchmarks/datasets/benchmark_dataset_1_150.jsonl` | 2900 | `9ac10df3a0458fa29c79ba2a9e5a6b9caa2069c9038275152403a96fab03f7be` |
| Completeness | `benchmarks/datasets/benchmark_dataset_completeness_1_16_50samples.jsonl` | 750 | `891ce23092b256c04d9ebbfcf1d4fdab15d124fbb0d958d1ae6dd7089cd0754a` |

The generators draw with Python's `random` module without a fixed seed and humanise each request
with an LLM at temperature 0.7. Running them again therefore produces a different dataset: the
versioned files are the datasets.

### Base configurations

Both generators build the base configuration with the same `generate_base_json(activities,
tasks_per_activity)`. Every value is drawn uniformly from the ranges below.

| Level | Field | Values |
|---|---|---|
| Global | `runId` | 1–1000 |
| | `Teams` | 1–20 |
| | `Simulation_period` | 480–10080 |
| Activity `A00i` | `T_period` | 240–4320 |
| | `T_wait` | 1–48 |
| | `Start_disp` | 1–120 |
| | `Team` | `Team` + the i-th letter (`TeamA`, `TeamB`, …) |
| | `Team members` | 1–12 |
| | `Shift_duration` | 6–14 |
| | `Activity_Order_Enforced` | true or false (p = 0.5) |
| | `Activity_Order_Before` | the next activity with p = 0.5, else empty |
| Task `T00j` | `Duration` | 1–48 |
| | `Requires_Shutdown` | true or false (p = 0.5) |
| | `Cost_per_hour` | 25–500 |
| | `Order_Enforced` | true or false (p = 0.5) |
| | `Order_Before` | the next task; also the one after it with p = 0.3 |

### Complexity axis

Generator: [input_agent/src/dataset_generator_complexity.py](../input_agent/src/dataset_generator_complexity.py).

- **Levels.** The level is N = activities × tasks per activity. The file covers N = 1…50 in steps
  of 1, plus 60, 70, 80, 90, 100, 115, 130 and 150: 58 levels of 50 samples each. At each level
  the 50 samples are split evenly, in shuffled order, among the factorisations of N.
- **Instruction.** Each sample has one atomic instruction:
  - The operation is drawn uniformly among SET, DELETE, APPEND and REMOVE_ITEM.
  - A SET picks a level (global, activity or task) and a field of that level, with the new value
    drawn from ranges that include the base ranges. `Team` takes one of `TeamA`…`TeamF`.
  - A DELETE removes a field of an activity or a task.
  - An APPEND adds a precedence to `Activity_Order_Before` or `Order_Before`, choosing among
    entries not already in the list.
  - A REMOVE_ITEM removes one existing precedence entry.
  - APPEND and REMOVE_ITEM fall back to another operation when no candidate exists.
- **Ground truth.** `json_gt = PetriConfigEngine(json_base).apply_batch([instruction])`.
- **Request.** `humanize_instruction` turns the instruction into a Spanish request with the
  prompt in the generator.
- **Evaluated.** The benchmark evaluates 16 levels (1, 5, 10, 12, 14, 16, 18, 20, 24, 28, 32, 40,
  50, 80, 100, 150). Each has exactly 50 samples, so every sample of those levels is used, 800 in
  all. The runner would subsample a larger level with
  `random.Random(derive_group_seed(42, "sampling", N))`.

### Completeness axis

Generator: [input_agent/src/dataset_generator_completeness.py](../input_agent/src/dataset_generator_completeness.py).

- **Levels.** The complexity is fixed at N = 16 (1×16, 2×8, 4×4, 8×2 and 16×1). The level C is
  the number of instructions in the request, from 1 to 15, with 50 samples per level: 750 in all.
  Every sample is evaluated.
- **Batch.** The batch mixes independent and dependent instructions, with no duplicates:
  - Independent instructions are SET or DELETE, as in the complexity axis.
  - Dependent instructions alternate APPEND and REMOVE_ITEM.
  - The share of independent instructions is 1.0 for C ≤ 3, 0.7 for C ≤ 5, 0.5 for C ≤ 10 and
    0.4 above; the independent instructions come first.
- **Ground truth.** The GT applies the instructions in order.
- **Request.** The request humanises the whole batch.

### Inadmissibility of the generated samples

The generators do not check admissibility. The offline pass of the validator (rules of commit
`c818998`, [validator.md](validator.md)) checked every base with an empty batch and every GT with
its instruction(s) as the batch. The counts come from `dataset_pass.csv` and
`dataset_rules_by_axis.csv` in
`benchmarks/results/validator_pass/20260928T224634Z_c818998_9ed0ce/`.

| Samples | n | Base inadmissible | GT inadmissible | GT inadmissible, base admissible |
|---|---|---|---|---|
| Complexity, evaluated levels | 800 | 252 (31.5 %) | 335 (41.9 %) | 83 (10.4 %) |
| Complexity, all 2900 lines | 2900 | 1079 (37.2 %) | 1344 (46.3 %) | 274 (9.4 %) |
| Completeness (all evaluated) | 750 | 189 (25.2 %) | 567 (75.6 %) | 384 (51.2 %) |

- **Inadmissible bases.** Every inadmissible base fails `equipos`. The base generator gives each
  activity its own `Team` label and draws `Teams` independently, so any base with more activities
  than `Teams` has more labels than teams.
- **Rules added by the instruction.** These are the rules that fail on the GT but not on its base.

  | Rule | Complexity, evaluated | Completeness |
  |---|---|---|
  | `campos_leidos` (DELETE of a field the net reads) | 71 | 402 |
  | `campos_esquema` (DELETE of `Team` or `Requires_Shutdown`) | 35 | 195 |
  | `prec_aciclica` (APPEND that closes a precedence cycle) | 14 | 90 |
  | `equipos` (SET of `Team` to a new label) | 0 | 14 |

- **GTs by group.** Among the inadmissible GTs:
  - complexity, evaluated: 279 violate some DOMINIO rule and 85 some RED DE PETRI rule;
  - completeness: 336 and 430.

The ground truth of an inadmissible sample is kept: exact match is scored against it whatever its
admissibility. The validator's categories c1 (rejected, GT inadmissible) and d2 (admitted, GT
inadmissible) exist for these samples.

## Protocol

### Runs

The per-axis runners are
[benchmarks/comparisons/benchmark_compare_complexity.py](../benchmarks/comparisons/benchmark_compare_complexity.py)
and
[benchmark_compare_completeness.py](../benchmarks/comparisons/benchmark_compare_completeness.py).
[benchmarks/runner/run_model_benchmark_suite.py](../benchmarks/runner/run_model_benchmark_suite.py)
runs both axes and the UQ for one model. Each sample runs under two approaches.

- **P-E.** The planner emits a batch and the deterministic executor applies it. The benchmark
  switches the sub-agents off: there is no context retrieval and no deterministic validation or
  recovery loop, only the planner and the executor in benchmark mode.
- **Vanilla.** The model returns the full modified configuration.

Both approaches share one fairness configuration, which the summary block of every results JSON
records:

| Setting | Value |
|---|---|
| Temperature | 0.0 |
| Seed | none: no provider received one |
| Request timeout | 600 s |
| Sample (firewall) timeout | 600 s |
| Throttle between calls | 0.35 s |
| Retries | 2, backoff 0.8 s, jitter 0.2 s |
| Workers per approach | 4 |
| Output budget | 4096 tokens (`LLMService` default when `max_tokens` is None) |
| Master seed | 42 |

- **Calls without a configuration.** Firewall timeouts and hard kills log no prediction. They
  count as failures and are scored as `json_base`.
- **Rescoring.** The logged results were re-scored without new inference, with the corrected
  excision metric ([benchmarks/metrics/rescore_results.py](../benchmarks/metrics/rescore_results.py)).
  The `*_rescored.json` files carry a `rescoring` block with the source SHA-256 and consistency
  checks: exact match recomputed from the configurations agrees with the log, no exact-match or
  token value changes, and the legacy metric reproduces every logged value.

### What the requests carried

- **Seed.** No provider received a seed. Every record and every summary block logs `seed: null`
  and `seed_effective: false`.
  - Without `--llm-seed`, the runner removes `LLM_SEED` and `BENCHMARK_LLM_SEED` from the
    environment after loading `.env`, so neither the planner nor the vanilla client gets one.
  - [LLMService](../input_agent/src/llm.py) sends `seed` only when it is set, and only to the
    OpenAI and OpenAI-compatible APIs. The Anthropic request never carries it.
- **Reasoning.** GPT-5.4 received no reasoning parameter, so the API default applied.
  - `LLMService` has never sent `reasoning_effort`. The only other way to pass one is
    `extra_body` from `LLM_EXTRA_BODY_JSON`, and it is not recorded.
  - The token counts show no reasoning. On the 676 vanilla calls of the complexity axis with
    exact match, the median completion is 5 tokens above the cl100k length of the ground truth
    ([c_star_by_backend.py](../benchmarks/metrics/c_star_by_backend.py)).
- **Usage.** The logs do not separate reasoning tokens.
  - `token_usage` holds `prompt`, `completion` and `total` only. `LLMService._normalize_usage`
    drops the rest of the usage object, including OpenAI's
    `completion_tokens_details.reasoning_tokens`. The raw responses were not logged.
  - On Ollama's OpenAI-compatible endpoint, `completion` is `eval_count`, which counts the
    reasoning and content tokens of gpt-oss:20b together.
  - Reasoning, where there is any, is therefore inside `completion` and inside the 4096-token
    budget.

### Bootstrap

Every bootstrap in the repository fixes its seeds and records them.

- **Per-cell intervals** ([benchmarks/metrics/petri_net_uq.py](../benchmarks/metrics/petri_net_uq.py)).
  A cell is one (approach, level) pair with n = 50. The confidence level is 95 % (α = 0.05).
  - **Exact match:** double bootstrap (Hall), with B1 = 1000 outer and B2 = 200 inner resamples.
    The nominal level α̃ is calibrated on a grid of 100 values between 0.005 and 0.45 so that
    the inner intervals reach 95 % coverage over the outer resamples. The interval is read from
    the outer distribution at α̃.
  - **F1 micro, latency, total tokens, collateral rate and omission rate:** BCa (Efron and
    Tibshirani) with 10 000 resamples.
  - **Seeds:** master seed 42.
    - The cells are sorted by (approach, level), and `np.random.default_rng(42).integers(0, 2**32)`
      gives one seed per cell, in that order.
    - With `default_rng`, each cell seed gives six child seeds, one per metric: exact match, F1,
      latency, tokens, collateral and omission.
    - The header of each `uq_<axis>_results.csv` lists the cell seeds, so any cell can be
      reproduced alone.
    - `derive_group_seed` (`sha256("42:<approach>:<level>")`) is the seed of the runners' level
      sampling, not of these intervals.
- **Paired deltas** ([benchmarks/aggregator/plot_delta_uq.py](../benchmarks/aggregator/plot_delta_uq.py)):
  BCa on the paired P-E − vanilla differences per sample, with 10 000 resamples.
  - Seeds: `np.random.default_rng(42)` draws one seed per series, in the order of `--models`:
    per model in Fig. 1 and per compared model in Figs. 2 and 3. Each series seed then gives one
    seed per level and metric.
  - No manifest records the library versions of these figures.
- **`tab:cdto_improvement_summary`** ([benchmarks/metrics/cdto_vs_vanilla_summary.py](../benchmarks/metrics/cdto_vs_vanilla_summary.py)):
  - Paired mean improvements of P-E over vanilla per model, axis and regime, taken from the UQ
    CSVs.
  - The complexity axis is split at C = 32, the budget-safe regime, which lies below every
    backend's C*_low.
  - Signs: positive is better for exact match and F1; negative is better for latency, tokens,
    collateral and omission.
  - `--budget-safe-max-level 49` reproduces the earlier cl100k split (`*_cut49.csv`).
- **Validator pass:** percentile bootstrap of each proportion, B = 10 000, drawing
  Binomial(n, p̂), which is equivalent to resampling the Bernoulli units. The seed is
  `sha256("42:<salt>")` per proportion.
- **Humanisation check:** see [humanisation_check.md](humanisation_check.md). It uses paired
  resampling of samples, stratified by level, with 10 000 resamples and seed 42, and the exact
  McNemar test.

### Direction of taskCode and activityCode

In `taskCode` and `activityCode` a list names what its owner precedes: the engine runs the owner
before each ID it lists. On $S_0$ of the case study, A001.T003 precedes T001 and T002, and A002
precedes A001.

- **Texts that state it.**
  - [utils/automatic_documentation.py](../utils/automatic_documentation.py), the documentation
    the API generates from the configuration: for example "A001.T003 precedes T001 and T002". Its
    arcs are the ones the net is built with: task arcs `p7{owner}{i} -> t0007{listed}{i}`, and for
    activities the inhibitor arc `p02{owner} -> t{listed}1` and the buffer arc
    `pbuff{owner} -> t{listed}1`.
  - The context labels of `extract_validation_context` and `build_topology_map`
    ([input_agent/src/tools.py](../input_agent/src/tools.py)): `precedes`. No code calls these two
    functions.
  - [test_inputs/catalog.md](../test_inputs/catalog.md) and the example of `prec_aciclica` in
    [validator.md](validator.md).
  - [tests/unit/test_precedence_direction.py](../tests/unit/test_precedence_direction.py) pins the
    direction on $S_0$. It checks the generated arcs against the precedence dictionaries the net is
    built from, and the wording of the documentation and of the labels.
- **Who reads these texts.** Only the temporal xAI reads the generated documentation
  (`node_temporal_xai` in [input_agent/nodes.py](../input_agent/nodes.py), category E of the case
  study), and it looks cards up by node ID. The Markdown version and the two functions of
  `tools.py` have no reader.
- **What does not depend on it.**
  - The benchmark: P-E and vanilla use neither the generated documentation nor those labels, and the
    datasets edit only `Order_Before` and `Activity_Order_Before`, which the translation does not
    pass to the net.
  - The validator: it reads the four lists as edges from the owner to each entry, the engine's
    direction, and its cycle and reference checks do not change if every edge is reversed.
  - The simulations: the engine and $S_0$ are unchanged.

## Manifests

Each stage writes its provenance next to its output.

| Stage | File | Records |
|---|---|---|
| Benchmark run | `summary` block of `benchmark_compare_<axis>.json` | run id, UTC time, dataset path and SHA-256, approaches, levels, samples per level, model block (provider, model, temperature, seed, timeout), master seed, SHA-256 fingerprint of the configuration, fairness settings, planner LLM runtime |
| Rescoring | `rescoring` block of `*_rescored.json` | source file and SHA-256, legacy flag, consistency checks |
| UQ | `uq_<axis>_results.csv` (manifest as `#` lines) and `benchmark_compare_<axis>_manifest.json` | run id, input file and SHA-256, records, cells, α, n_iter, B1, B2, seed, group seeds, numpy/scipy/joblib/Python versions, platform, git commit |
| Validator pass | `validator_pass/<run>/manifest.json` | rules commit, HEAD, commits of validator/reindexing/executor/script, the rule→group map, script and dataset SHA-256, SHA-256 of each input, reconstruction checks, bootstrap settings |
| Humanisation check | `humanisation_check/<run>/manifest.json` | see [humanisation_check.md](humanisation_check.md#manifest) |
| Case study | `case_study_rerun/<run>/manifest.json` | command, HEAD, commit of each agent fix the run depends on, model and digest, Ollama version, LLM runtimes, environment (keys redacted), SHA-256 of every file |
| Zenodo | `benchmarks/results/zenodo_files.sha256` | `<sha256> *<path>` for every result file kept out of git and deposited in Zenodo (the result PNGs, the per-call log `calls.jsonl` of the humanisation check, `pe_batches.csv` and `vanilla_pass.csv`), sorted by path |

The runners' own `benchmark_compare_<axis>_manifest.json` files were later overwritten by the UQ
manifests of the same name. The run configuration of the original runs is therefore read from the
`summary` block of the results JSON. For the gpt-oss:20b runs,
[benchmarks/humanisation_check/provenance.py](../benchmarks/humanisation_check/provenance.py)
recovers the one setting that is not there, the sample timeout, by recomputing the configuration
fingerprint.

## Deployment environments

### Original benchmark runs (April 2026)

| Backend | API | Model | Complexity run (UTC) | Completeness run (UTC) |
|---|---|---|---|---|
| Claude Sonnet 4.6 | Anthropic API | `claude-sonnet-4-6` | 2026-04-28 10:56 | 2026-04-28 12:13 |
| GPT-5.4 | OpenAI API | `gpt-5.4` | 2026-04-29 09:13 | 2026-04-29 10:23 |
| gpt-oss:20b | Ollama, OpenAI-compatible endpoint | `gpt-oss:20b` | 2026-04-28 14:32 | 2026-04-28 17:52 |
| Llama 3.1 8B | Ollama, OpenAI-compatible endpoint | `llama3.1:latest` | 2026-04-29 13:10 | 2026-04-29 20:02 |

- **Not logged.** For the two Ollama backends the original runs recorded neither the Ollama
  version, the model digest, the server context length, `OLLAMA_NUM_PARALLEL` nor the GPU.
- **Stated by the authors, not recorded.** The GPU of these runs (an NVIDIA RTX 5090 with 32 GB
  on an Ubuntu server, as the supplementary material states) and the quantisation of the local
  weights (`gpt-oss:20b` MXFP4, `llama3.1:latest` Q4_K_M) are what the authors report. No
  manifest, log or result file of the April runs records them: the weights are identified only
  by their tag, and the tag's quantisation is the default of the Ollama library, not a logged
  value. The same holds for the March runs that humanised the datasets.
- **Context lower bound.** For gpt-oss:20b the context was at least 17 485 tokens: the longest
  untruncated prompt plus completion of those runs (`provenance.py`).
- **Request format.** The gpt-oss:20b runs used the request format of commit `a224cae`, which the
  request profile `2026-04-28-benchmark` reproduces.

### Runs of September 2026 (humanisation check and case study)

- **Humanisation check.** Its manifest records the server: host alias (also part of the run
  id), GPU and Ollama settings. It redacts `OLLAMA_HOST`, `OLLAMA_ORIGINS` and filesystem
  paths. The recorded files are kept as they were written, so the alias and the paths they hold
  stay as a record of provenance.
- **Case study.** Its manifests record the Ollama version and the model digest, but neither the
  host nor the GPU. It used the same endpoint as the humanisation check.

**Server**

| Item | Value |
|---|---|
| Ollama | 0.24.0 |
| GPU | NVIDIA GeForce RTX 5080, 16 GB, driver 595.84, CUDA 13.2 |
| Server settings | `OLLAMA_NUM_PARALLEL=2`, `OLLAMA_MAX_LOADED_MODELS=2`, `OLLAMA_KV_CACHE_TYPE=q8_0`, `OLLAMA_FLASH_ATTENTION=1`; `OLLAMA_CONTEXT_LENGTH` unset |
| Access | OpenAI-compatible endpoint reached through an SSH tunnel |

**Models**

| Model | Digest | Details |
|---|---|---|
| `gpt-oss-20b-ctx32k` | `65086a4a68ab43873b6e9d95ea7efc31cc1517c4a5a27f0c001f4abf129b731f` | `FROM gpt-oss:20b` + `PARAMETER num_ctx 32768` ([Modelfile](../benchmarks/humanisation_check/Modelfile.gpt-oss-20b-ctx32k)). Weights blob `e7b273f9…`, chat template `fa6710a9…`, system prompt and details verified identical to `gpt-oss:20b`; only `num_ctx` differs. 20.9B, MXFP4. Loaded fully on GPU with a 32 768-token context |
| `gpt-oss:20b` | `17052f91a42e97930aa6e28a6c6c06a983e6a58dbb00434885a0cf5313e376f7` | The base of the derived model (weights blob `e7b273f9…`) |
| `qwen2.5:32b` | `9f13ba1299afea09d9a956fc6a85becc99115a6d596fae201a5487a03bdc4368` | Humaniser of the check. 32.8B, Q4_K_M |

**Client:** Python 3.13.14 on Windows 11, openai 2.24.0, httpx 0.28.1, langchain-core 1.2.11,
langgraph 1.0.8, pydantic 2.12.5, numpy 2.2.6, scipy 1.17.0.

### Request profiles

[input_agent/src/llm.py](../input_agent/src/llm.py) (`REQUEST_PROFILES`) reproduces earlier
request formats of the OpenAI-compatible client on demand, through `request_profile` or
`LLM_REQUEST_PROFILE`. Without a profile the current format is used.

| Profile | Reproduces | JSON suffix in the system prompt | `response_format` JSON | Default `max_tokens` | `extra_body` | Response parsing |
|---|---|---|---|---|---|---|
| `2026-03-humaniser` | Commits `12e3297`/`6e07a45` (March 2026), which humanised both datasets | no | yes | none | no | `json.loads` only |
| `2026-04-28-benchmark` | Commit `a224cae` (28 April 2026), which ran the gpt-oss:20b benchmark | no | no | 4096 | from the environment | lenient JSON extraction |
