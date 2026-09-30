# Humanisation check

The benchmark requests were written in natural language by an LLM (the humaniser) from each
technical instruction. This check measures how much the wording of the requests affects P-E. It
runs the same samples with the original requests and with requests re-humanised by another model,
and adjudicates by hand every sample whose outcome changes.

- Code: [benchmarks/humanisation_check/](../benchmarks/humanisation_check/)
- Results: [benchmarks/results/humanisation_check/veritas_qwen25_32b/](../benchmarks/results/humanisation_check/veritas_qwen25_32b/).
  The folder is named after the server alias the run recorded; the recorded files keep it, and
  the paths they hold, as a record of provenance.
  The per-call log `calls.jsonl` is in Zenodo.
- Trial runs (`trial_*`) are not results.

## Design

| Condition | Server | Requests | Source |
|---|---|---|---|
| A | Original (April 2026) | Original | Logged gpt-oss:20b results of the benchmark, re-scored |
| B | New (September 2026) | Original | Run in this check |
| C | New (September 2026) | Re-humanised by `qwen2.5:32b` | Run in this check |

- **Effects measured.** C − B is the effect of the humanisation, and the only basis of the
  conclusion. B − A checks that the new server reproduces the original one.
- **Scope.** P-E only; gpt-oss:20b as the evaluated model; latency is not compared.

## Protocol

1. **Sample selection** (`select_samples.py`). There are four levels per axis: complexity 1, 16,
   50 and 150, and completeness 1, 5, 10 and 15. For each level the pool is the set of samples
   gpt-oss:20b ran under P-E in the original benchmark, which equals the dataset's samples at that
   level. Twenty-five IDs are drawn from each pool with
   `random.Random(derive_group_seed(42, "humanisation_check:<axis>", level))`, so each level's
   draw does not depend on the others. That gives 200 samples (`sample_ids.json`).
2. **Re-humanisation** (`rehumanise.py`). The generators' humanisers run unchanged
   (`humanize_instruction` for complexity, `humanize_instruction_batch` for completeness). Their
   prompts have not changed since the datasets were built.
   - Settings are those of the generators: temperature 0.7, no seed, 4 requests in parallel.
   - The request format is that of March 2026 (profile `2026-03-humaniser`).
   - Only the model and the server URL change.
   - A format check confirmed, for every request, that there was no reasoning in the output, that
     the output was a bare JSON object with a non-empty `natural_query`, and that the finish
     reason was `stop`. All 200 passed.
3. **Fidelity check** (`fidelity.py`), which changes no prompt. For every instruction, the new
   request must name:
   - the activity and task of the path;
   - the parameter, by one of the synonyms the humaniser prompt prescribes or the literal key;
   - the value.

   A request missing any of them is flagged, and nothing is dropped. The check also warns of a
   possible inverted precedence and of a unit attached to a unitless number. The original
   requests get the same check as a reference. **23 of the 200 new requests were flagged.**
4. **Paired run** (`run_paired.py`). B and C of each sample are submitted back to back, in an
   order that alternates with the sample's position, to one pool of workers sharing one
   throttle. Both conditions therefore get the same concurrency and server state.
   - **Same as the original run:** provider `openai_compatible`, temperature 0, no seed,
     `max_tokens` None (4096), no `extra_body`, request and sample timeouts of 600 s, throttle
     0.35 s, 2 retries, backoff 0.8 s, jitter 0.2 s, sub-agents off, corrected metric. Requests
     use the format of the original run (profile `2026-04-28-benchmark`). A mismatch aborts the
     run.
   - **Declared deviations:**
     - the model is `gpt-oss-20b-ctx32k`, `gpt-oss:20b` with `num_ctx` 32 768 and nothing else
       changed (weights, template, system prompt and details verified identical);
     - there are 2 workers instead of 4, equal to the server's `OLLAMA_NUM_PARALLEL`, so no call
       waits in the server queue.
   - **GPU checks:** the model must be entirely on GPU with a context of at least 8192 tokens.
     This was checked before the run and after every level.
5. **Comparison** (`compare.py`).
   - **Metrics:** exact match, F1 micro, omission rate and collateral rate, for A, B and C, per
     level, per axis and in total.
   - **Differences:** paired differences C − B and B − A with a 95 % percentile bootstrap
     interval (10 000 resamples of samples, stratified by level for axis and overall totals,
     seed 42), and the exact McNemar test for exact match.
   - **Subsets:** C − B is repeated without the 23 flagged requests (`fidelity_ok`) and, after
     adjudication, without the pairs attributed to the humanisation (`excl_humanisation`).
6. **Adjudication.** `discordant_pairs_planner_executor.md` lists every sample where B and C
   differ in exact match. For each it shows the technical instruction, both requests, the batch
   gpt-oss:20b emitted in B and in C, and the edits that differ from the GT. Each pair was
   classified by hand:
   - **humanisation:** the new request drops, adds or changes something the instruction asks,
     for example an inverted precedence;
   - **model:** the new request is faithful and the difference comes from how gpt-oss:20b reads
     it;
   - **unclear.**

## Results

### Exact match (%)

| Subset | n | A | B | C | C − B [95 % CI] | McNemar p (C only / B only) | B − A [95 % CI] |
|---|---|---|---|---|---|---|---|
| All | 200 | 79.0 | 79.5 | 63.0 | −16.5 [−22.0, −11.5] | < 10⁻⁶ (5 / 38) | +0.5 [−3.5, +4.5] |
| Complexity | 100 | 95.0 | 96.0 | 98.0 | +2.0 [0.0, +5.0] | 0.50 (2 / 0) | +1.0 [−2.0, +4.0] |
| Complexity, level 1 | 25 | 92.0 | 96.0 | 100.0 | +4.0 [0.0, +12.0] | 1.0 | +4.0 [0.0, +12.0] |
| Complexity, level 16 | 25 | 92.0 | 96.0 | 100.0 | +4.0 [0.0, +12.0] | 1.0 | +4.0 [0.0, +12.0] |
| Complexity, level 50 | 25 | 96.0 | 96.0 | 96.0 | 0.0 | 1.0 | 0.0 |
| Complexity, level 150 | 25 | 100.0 | 96.0 | 96.0 | 0.0 | 1.0 | −4.0 [−12.0, 0.0] |
| Completeness | 100 | 63.0 | 63.0 | 28.0 | −35.0 [−45.0, −25.0] | < 10⁻⁶ (3 / 38) | 0.0 [−7.0, +7.0] |
| Completeness, level 1 | 25 | 100.0 | 100.0 | 80.0 | −20.0 [−36.0, −4.0] | 0.063 | 0.0 |
| Completeness, level 5 | 25 | 48.0 | 52.0 | 28.0 | −24.0 [−48.0, 0.0] | 0.11 | +4.0 [−8.0, +16.0] |
| Completeness, level 10 | 25 | 60.0 | 60.0 | 4.0 | −56.0 [−76.0, −32.0] | 0.00052 | 0.0 [−20.0, +20.0] |
| Completeness, level 15 | 25 | 44.0 | 40.0 | 0.0 | −40.0 [−60.0, −20.0] | 0.0020 | −4.0 [−20.0, +12.0] |
| Fidelity not flagged | 177 | 84.7 | 84.2 | 70.6 | −13.6 [−18.6, −8.5] | 1.9 × 10⁻⁵ (4 / 28) | −0.6 [−4.5, +3.4] |
| Without pairs attributed to humanisation | 164 | 79.3 | 76.2 | 75.6 | −0.6 [−3.7, +2.4] | 1.0 (3 / 4) | −3.0 [−6.7, +0.6] |

### Other metrics, all 200 samples

| Metric | A | B | C | C − B [95 % CI] | B − A [95 % CI] |
|---|---|---|---|---|---|
| F1 micro | 0.938 | 0.936 | 0.874 | −0.062 [−0.098, −0.027] | −0.002 [−0.026, +0.022] |
| Omission rate | 0.064 | 0.066 | 0.111 | +0.046 [+0.011, +0.081] | +0.001 [−0.023, +0.025] |
| Collateral rate | 0.030 | 0.031 | 0.042 | +0.011 [−0.007, +0.026] | +0.002 [−0.012, +0.016] |

The full table, per axis and level and for every subset, is `comparison_planner_executor.csv`.

### Controls

These are reported apart and are not part of the conclusion.

- **Prompt tokens.** For all 200 samples, B's prompt tokens equal A's, so the prompt, chat
  template and context are the same and B − A is a valid comparison.
- **Tokens and truncation.** Mean tokens per call; truncated means completion ≥ 4090 tokens.

  | | A | B | C |
  |---|---|---|---|
  | Total | 3732 | 3632 | 3803 |
  | Prompt | 2798 | 2798 | 2801 |
  | Completion | 935 | 834 | 1002 |
  | Truncated | 2.0 % | 2.0 % | 5.0 % |

  In C all truncations are on the completeness axis: 4 % at level 1, 8 % at 5, 12 % at 10 and
  16 % at 15.
- **Finish reason.** B: 196 `stop` and 4 `length`. C: 190 `stop` and 10 `length`. It agrees with
  the completion-count rule in all 400 calls.
- **Timeouts and errors.** None in A, B or C. The 400 calls logged no errors.
- **Possible sources of a B − A difference** listed by the comparison: Ollama 0.24.0,
  `OLLAMA_KV_CACHE_TYPE=q8_0`, `OLLAMA_FLASH_ATTENTION=1`, `OLLAMA_MAX_LOADED_MODELS=2`,
  `OLLAMA_NUM_PARALLEL=2`, `num_ctx` 32 768, 2 workers instead of 4, and a chat template that
  stamps the current date.

## Adjudicated pairs

There are 43 discordant pairs: 38 where B is an exact match and C is not, and 5 the other way
round. **Causes: 36 humanisation, 5 model, 2 unclear.**
`discordant_pairs_planner_executor.md` has the instruction, both requests, both batches and the
differing edits of every pair.

| # | Axis | Level | Sample | EM B | EM C | Cause |
|---|---|---|---|---|---|---|
| 1 | complexity | 1 | 17 | 0 | 1 | model |
| 2 | complexity | 16 | 791 | 0 | 1 | humanisation |
| 3 | completeness | 1 | 2 | 1 | 0 | humanisation |
| 4 | completeness | 1 | 23 | 1 | 0 | humanisation |
| 5 | completeness | 1 | 33 | 1 | 0 | model |
| 6 | completeness | 1 | 41 | 1 | 0 | humanisation |
| 7 | completeness | 1 | 48 | 1 | 0 | humanisation |
| 8 | completeness | 5 | 201 | 0 | 1 | unclear |
| 9 | completeness | 5 | 205 | 1 | 0 | humanisation |
| 10 | completeness | 5 | 206 | 0 | 1 | humanisation |
| 11 | completeness | 5 | 211 | 1 | 0 | humanisation |
| 12 | completeness | 5 | 226 | 1 | 0 | humanisation |
| 13 | completeness | 5 | 233 | 1 | 0 | model |
| 14 | completeness | 5 | 236 | 1 | 0 | humanisation |
| 15 | completeness | 5 | 237 | 1 | 0 | humanisation |
| 16 | completeness | 5 | 243 | 1 | 0 | humanisation |
| 17 | completeness | 5 | 248 | 1 | 0 | model |
| 18 | completeness | 10 | 450 | 1 | 0 | humanisation |
| 19 | completeness | 10 | 459 | 1 | 0 | humanisation |
| 20 | completeness | 10 | 465 | 1 | 0 | humanisation |
| 21 | completeness | 10 | 466 | 1 | 0 | humanisation |
| 22 | completeness | 10 | 467 | 0 | 1 | model |
| 23 | completeness | 10 | 469 | 1 | 0 | humanisation |
| 24 | completeness | 10 | 474 | 1 | 0 | humanisation |
| 25 | completeness | 10 | 475 | 1 | 0 | humanisation |
| 26 | completeness | 10 | 478 | 1 | 0 | humanisation |
| 27 | completeness | 10 | 479 | 1 | 0 | humanisation |
| 28 | completeness | 10 | 480 | 1 | 0 | humanisation |
| 29 | completeness | 10 | 482 | 1 | 0 | humanisation |
| 30 | completeness | 10 | 486 | 1 | 0 | unclear |
| 31 | completeness | 10 | 488 | 1 | 0 | humanisation |
| 32 | completeness | 10 | 491 | 1 | 0 | humanisation |
| 33 | completeness | 10 | 497 | 1 | 0 | humanisation |
| 34 | completeness | 15 | 701 | 1 | 0 | humanisation |
| 35 | completeness | 15 | 708 | 1 | 0 | humanisation |
| 36 | completeness | 15 | 711 | 1 | 0 | humanisation |
| 37 | completeness | 15 | 714 | 1 | 0 | humanisation |
| 38 | completeness | 15 | 719 | 1 | 0 | humanisation |
| 39 | completeness | 15 | 724 | 1 | 0 | humanisation |
| 40 | completeness | 15 | 725 | 1 | 0 | humanisation |
| 41 | completeness | 15 | 727 | 1 | 0 | humanisation |
| 42 | completeness | 15 | 735 | 1 | 0 | humanisation |
| 43 | completeness | 15 | 743 | 1 | 0 | humanisation |

Two examples from that file:

- **Complexity 1, sample 17 (model).**
  - Instruction: `SET A001.Team members = 3`.
  - B request: "Cambia la dotación de la actividad A-001 a 3." gpt-oss:20b emitted
    `SET A001.Team = "3"`.
  - C request: "Cambia la dotación de la actividad A001 para que tenga 3 operarios asignados."
    gpt-oss:20b emitted the exact instruction.
- **Complexity 16, sample 791 (humanisation).**
  - Instruction: `APPEND A001.tasks.T008.Order_Before = "T006"`, meaning T008 ends before T006
    starts.
  - B request: "Añade la regla de que la tarea 6 de la actividad 1 debe terminar antes de que
    comience la tarea 8." This inverts the precedence, and the model followed it.
  - C request: "Añade una restricción para que la tarea T008 de la actividad A001 tenga que
    terminar antes de empezar la tarea T006." This is correct, and the model emitted the exact
    instruction.

Without the 36 pairs attributed to the humanisation, C − B in exact match is −0.6 points
[−3.7, +2.4], with McNemar p = 1.0. Every row has a cause (`adjudication.complete` in
`comparison_summary_planner_executor.json`).

## Manifest

`manifest.json` records:

- **Design and code:** the design (A, B, C); the git commit and the uncommitted files at run time.
- **Client:** Python, platform, package versions and OpenAI client retries.
- **Server:**
  - the Ollama version and, per model, the digest, size, details, parameters, template SHA-256,
    Modelfile SHA-256 and weights blobs;
  - the loaded models at start and at every level (GPU fraction, context length);
  - the GPU and driver;
  - the Ollama variables that affect inference.
- **Derived model:** the check that `gpt-oss-20b-ctx32k` differs from `gpt-oss:20b` only in
  `num_ctx`.
- **Configuration:** the new and the original configuration side by side, with the declared
  deviations and the location in the code of every setting.
- **Inputs and outputs:**
  - the selected samples and their seed;
  - the humaniser's settings, the parameters sent and the format check;
  - the fidelity CSV;
  - the call log with its SHA-256, and the output files with their SHA-256;
  - the elapsed time (2291.5 s for the 400 calls) and the throughput.
- **Redaction:** OLLAMA_HOST, OLLAMA_ORIGINS and filesystem paths are redacted, and none of them
  affects inference. The unredacted copy is kept locally and is not deposited.
