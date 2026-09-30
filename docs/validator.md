# Deterministic validator

This document covers the admissibility check that every configuration change goes through
before it is committed: the 16 rules, the messages they produce, rejection examples from the
benchmark, and the per-rule results of the offline pass. It adds detail that the paper and the
supplementary material leave out.

- Code: `check_configuration` and `deterministic_validator` in
  [input_agent/src/tools.py](../input_agent/src/tools.py). The grouping of rules is the `RULES`
  dictionary in the same file.
- Rules frozen for the offline pass: commit `c818998`. Current messages: commit `554296f`, which
  changed only the text of the details (see [Messages](#messages)).
- Previous version (v1): commit `e0f1d0a`. See [Relation to v1](#relation-to-v1).
- Commit hashes here, as in the manifests, are those of the development history. `RELEASE.json`
  records the development commit a release comes from.

## Where the check runs

Every change to the current configuration $S_k$ goes through `_apply_batch` in
[input_agent/nodes.py](../input_agent/nodes.py):

1. Route check (`find_unresolved_routes`). A path that does not resolve aborts the batch before
   it is applied.
2. The batch is applied to a working copy, and temporary IDs are renumbered
   (`PetriConfigEngine.reindex_structure`).
3. `check_configuration(candidate, batch, previous_config=S_k)` returns every violation.
4. With no violations the candidate is committed as $S_{k+1}$. Otherwise $S_k$ is kept and:
   - if every violation is in the DOMINIO group, the rejected candidate is simulated and
     explained against $S_k$, and the feedback agent proposes a correction (queue
     `simulator, xai, feedback`);
   - if any violation is in the RED DE PETRI group, or the `limites` rule fails, the candidate
     is not simulated and only the feedback agent runs;
   - after three attempts the batch is dropped.

Three callers use this path:

- the executor, for the planner's batches;
- the optimizer, for $S^*$, written as SET instructions on the IWO decision variables;
- `POST /config/update`, for a configuration sent by a client.

The benchmark runs P-E with `skip_deterministic_validation`, which commits without the check.

## Groups

| Group | Meaning | What happens on rejection |
|---|---|---|
| DOMINIO | Types, domains and relations fixed by the semantics of the maintenance plan | Candidate simulated against $S_k$, explained, then feedback (except `limites`) |
| RED DE PETRI | What the Petri net instantiation and the simulator need to be well defined | Feedback only; the candidate is not simulated |

## Rule catalogue

The detail of each violation is in English. It says which field points to what, with short paths
(`A002.T002` for `A002.tasks.T002`). `<v>` is the value as it appears in the JSON.

Sources:

- **E**: schema (`config/models.py`, `input_agent/pn_models.py`);
- **S**: dataset generators (`input_agent/src/dataset_generator_*.py`);
- **P**: planner prompt;
- **C**: `test_inputs/catalog.md`;
- **M**: the Petri net variables manual;
- **T**: translation to the net and simulator;
- **D**: design decision not documented in the other sources.

### DOMINIO

| Rule (code name) | Requirement | Source | Message templates |
|---|---|---|---|
| `campos_esquema` | `Team` (activity) and `Requires_Shutdown` (task) present and not null | E, M | `<owner> has no <field> field` · `<owner> has <field> = null` |
| `tipos` | JSON type of every documented field that is present. Integers: `runId`, `Teams`, `Team members` (5 or 5.0). Numbers: `Simulation_period`, `T_period`, `T_wait`, `Start_disp`, `Shift_duration`, `Duration`, `Cost_per_hour`. Booleans: `Requires_Shutdown`, `Order_Enforced`, `Activity_Order_Enforced`, `taskDependency`, `activityDependency` (true or false only). Text: `Team`. Lists of IDs: `Order_Before`, `Activity_Order_Before`, `taskCode`, `activityCode`. Only the fields the schema declares Optional accept null | E, P, M | `<field> is <v>; it must be an integer` (or `a number`, `true or false`, `a text`, `a list of IDs (texts)`, `it cannot be null`) |
| `equipos` | Number of distinct `Team` labels ≤ `Teams` | C, M | `the activities use <n> distinct Team labels (<labels>) but Teams is <v>` |
| `ids` | Activity keys of the form `Axxx`; task keys of the form `Txxx` | E, P | `the activity key <id> does not have the form Axxx` · `<aid> has the task key <id>, which does not have the form Txxx` |
| `limites` | At most 1000 activities and 1000 tasks per activity, as a guard against oversized inputs | D | `the configuration has <n> activities; the maximum is 1000` · `<aid> has <n> tasks; the maximum is 1000` |
| `referencias` | Every entry of `Order_Before`, `Activity_Order_Before`, `taskCode` and `activityCode` names a task of the same activity or an existing activity, with or without its flag | M, P, S, C | `<aid>.<tid> lists <x> in <field>, but <x> no longer exists in <aid>` (the batch deleted it) · `… does not exist in <aid>` (it never existed) · `<aid>.<tid> lists <v> in <field>, which is not a task ID` · the same for activities |
| `rangos` | `T_period` > 0, `Shift_duration` ≤ 24, `Cost_per_hour` ≥ 0 | D | `<aid>.T_period is <v>; it must be > 0` · `<aid>.Shift_duration is <v>; it must be <= 24` · `<aid>.<tid>.Cost_per_hour is <v>; it must be >= 0` |
| `sanity_batch` | In the objects written by the batch's instructions: `T_period`, `T_wait`, `Start_disp`, `Shift_duration`, `Duration` numeric ≥ 0, and `Team members` an integer ≥ 0 (the v1 Sanity condition, decided on the batch) | v1 | `the instruction on <path> sets <field> to <v>; it must be a non-negative number` (or `… a non-negative integer` for `Team members`) |
| `campos_fuera_de_nivel` | No known field at a level that is not its own: activity or task fields at the root, task or global fields in an activity, activity or global fields in a task. Such an edit has no effect on the net, so the configuration would not do what it states. Unknown keys are still allowed | P | `<key> is an activity field, but it is at the root of the configuration` · `<aid> has <key>, which is a task field, not an activity field` · `<aid>.<tid> has <key>, which is an activity field, not a task field` |

### RED DE PETRI

| Rule (code name) | Requirement | Source | Message templates |
|---|---|---|---|
| `campos_leidos` | Fields the translation to the net reads, present and not null: `runId`, `Teams`, `Simulation_period`. Per activity: `tasks`, `T_period`, `T_wait`, `Start_disp`, `Team members`, `Shift_duration`. Per task: `Duration`. Activities and tasks are objects | T | `<owner> has no <field> field` · `<owner> has <field> = null` · `<aid> is <type>, not an object, so the translation to the Petri net drops it` · `<aid>.tasks is <type>, not an object of tasks` |
| `no_vacia` | At least one activity, and at least one task per activity | T | `the configuration has no activities` · `<aid> has no tasks` |
| `dom_real` | `T_period`, `T_wait`, `Start_disp`, `Shift_duration`: finite numbers ≥ 0. `Simulation_period`: a finite number > 0 | T | `<aid>.<field> is <v>; it must be a finite number >= 0` · `Simulation_period is <v>; it must be a finite number > 0` |
| `dom_int` | `Duration` and `Team members` are arc weights of the net: integers ≥ 1 (`int(v) == float(v) >= 1`) | T | `<field> is <v>; it must be an integer >= 1` |
| `turno_minimo` | `Shift_duration` ≥ 1 h: the net generates the crew once per hour of shift | T | `<aid>.Shift_duration is <v>; it must be >= 1 (hours)` |
| `prec_tipos` | With the flag active, `taskCode` and `activityCode` are lists, and `Activity_Order_Before` holds IDs, not lists or objects | T | `<aid>.<tid> has taskDependency = true, but its taskCode is <v>, not a list of task IDs` · the same for `activityCode` · `<aid> lists <v> in Activity_Order_Before; these entries are not activity IDs and the Petri net cannot be built` |
| `prec_aciclica` | No cycle among the active precedences, self-precedence included, within each activity (tasks) and across activities. A cycle leaves the transitions involved waiting for tokens that only they produce | T, C | `<owner> lists itself (<x>) in <field>` · `precedence cycle among <ids>: <owner> lists <x> in <field>; …` |

"Active" precedences are read with the same flags as the net: `Order_Enforced` with
`Order_Before`, `taskDependency` with `taskCode`, `Activity_Order_Enforced` with
`Activity_Order_Before`, and `activityDependency` with `activityCode`.

### One example per rule

The configuration is $S_0$ of the case study ([case_study.md](case_study.md)) with one change,
checked with the current code:

| Rule | Change to $S_0$ | Violation |
|---|---|---|
| `campos_esquema` | delete `A001.tasks.T001.Requires_Shutdown` | `[campos_esquema \| DOMINIO] A001.tasks.T001.Requires_Shutdown: A001.T001 has no Requires_Shutdown field` |
| `tipos` | `A001.T_period = "480"` | `[tipos \| DOMINIO] A001.T_period: A001.T_period is "480"; it must be a number` |
| `equipos` | `A002.Team = "TeamB"` (Teams = 1) | `[equipos \| DOMINIO] Teams: the activities use 2 distinct Team labels (TeamA, TeamB) but Teams is 1` |
| `ids` | add task key `X1` to A001 | `[ids \| DOMINIO] A001.tasks.X1: A001 has the task key X1, which does not have the form Txxx` |
| `limites` | give A001 1001 tasks | `[limites \| DOMINIO] A001.tasks: A001 has 1001 tasks; the maximum is 1000` (`ids` fails too: `Txxx` allows only 1000 keys) |
| `referencias` | delete `A002.tasks.T001` (category C of the case study) | `[referencias \| DOMINIO] A002.tasks.T002.taskCode: A002.T002 lists T001 in taskCode, but T001 no longer exists in A002`, and the same for T003 |
| `rangos` | `A001.Shift_duration = 30` | `[rangos \| DOMINIO] A001.Shift_duration: A001.Shift_duration is 30; it must be <= 24` |
| `sanity_batch` | batch `SET A001 = {…, "T_wait": -1}` | `[sanity_batch \| DOMINIO] A001: the instruction on A001 sets T_wait to -1; it must be a non-negative number` (the resulting candidate also fails `dom_real`) |
| `campos_fuera_de_nivel` | `A001.tasks.T001.Start_disp = 5` | `[campos_fuera_de_nivel \| DOMINIO] A001.tasks.T001.Start_disp: A001.T001 has Start_disp, which is an activity field, not a task field` |
| `campos_leidos` | delete `A002.T_wait` | `[campos_leidos \| RED DE PETRI] A002.T_wait: A002 has no T_wait field` |
| `no_vacia` | `A001.tasks = {}` | `[no_vacia \| RED DE PETRI] A001.tasks: A001 has no tasks` |
| `dom_real` | `A002.Start_disp = -2` | `[dom_real \| RED DE PETRI] A002.Start_disp: A002.Start_disp is -2; it must be a finite number >= 0` |
| `dom_int` | `A002.tasks.T001.Duration = 0.75` | `[dom_int \| RED DE PETRI] A002.tasks.T001.Duration: A002.T001.Duration is 0.75; it must be an integer >= 1` |
| `turno_minimo` | `A001.Shift_duration = 0.5` | `[turno_minimo \| RED DE PETRI] A001.Shift_duration: A001.Shift_duration is 0.5; it must be >= 1 (hours)` |
| `prec_tipos` | `A002.tasks.T002.taskCode = "T001"` | `[prec_tipos \| RED DE PETRI] A002.tasks.T002.taskCode: A002.T002 has taskDependency = true, but its taskCode is "T001", not a list of task IDs` (and `tipos` on the same field) |
| `prec_aciclica` | `A002.tasks.T001.taskCode = ["T004"]` (with `taskDependency = true`): T001 precedes T004, which already runs before T002 and T003, which precede T001 | `[prec_aciclica \| RED DE PETRI] A002.tasks: precedence cycle among T001, T002, T003, T004: A002.T001 lists T004 in taskCode; A002.T002 lists T001 in taskCode; A002.T003 lists T001 in taskCode; A002.T004 lists T002 in taskCode; A002.T004 lists T003 in taskCode` |

## Messages

A violation is `{"rule", "group", "path", "detail"}`. As text it reads
`[rule | group] path: detail` (`format_violation`). `path` is the offending substructure in full
form; `detail` uses short forms.

With the previous configuration $S_k$ at hand, which the executor, the optimizer and
`/config/update` always pass, `referencias` tells a reference to something the batch deleted
("no longer exists") from one to something that never existed ("does not exist").

The offline pass ran with the rules of `c818998`, whose details were in Spanish (for example
`falta el campo`). Commit `554296f` rewrote the details only. Every c2 example below was checked
again with the current code: each one produces the same rule on the same path as recorded.

## Relations considered and discarded

- **a.** A non-empty precedence list with its flag set to false. No source makes it invalid; the
  flag only disables the list. The generators produce it.
- **b.** Duplicate entries in precedence lists. They have no effect on the net.
- **d.** `Start_disp` < `Simulation_period`. Not documented.
- **e.** `T_wait` < `T_period`. Not documented, and `T_wait` has different meanings across
  sources.
- **g.** Same `Team` label implies the same `Team members` and `Shift_duration`. Not documented.
- **h.** `Team` as an index ≤ `Teams`. It contradicts `Team` being a text label (E, S, C).
- **i.** Root keys limited to the globals and activity IDs. The schema allows extra keys, so
  unknown keys are allowed; known fields at the wrong level are rejected by
  `campos_fuera_de_nivel`.
- **k.** The critical path fits in the period capacity. This is a planning heuristic, not an
  admissibility condition.
- **l.** Mixing the two precedence formats (`Order_*` and `taskCode`/`activityCode`). Not
  documented.

## Relation to v1

v1 (commit `e0f1d0a`) had three rules (Resource, Sanity, Topology) and the `PetriInput` schema.

- `equipos` is v1 Resource.
- `sanity_batch` is v1 Sanity.
- `referencias` extends v1 Topology, which only checked `taskCode`/`activityCode` with their
  flag set to true.
- The task-key condition of `ids` comes from v1; the activity-key condition is new.
- `limites` raises the v1 schema limit of 100, which the generators exceed.

v1 is kept in [tests/unit/v1_validator_reference.py](../tests/unit/v1_validator_reference.py):
its three rules and the body of its `ValidatorEngine.validate`. The tests check that the current
validator still rejects everything v1 rejected, except for the raised size limit.

## Offline pass over the benchmark

[benchmarks/metrics/validator_pass.py](../benchmarks/metrics/validator_pass.py) replays the
validating path of the executor on every recorded P-E batch, without new inference.

- **Input:** 4 backends × (800 complexity + 750 completeness) = 6200 batches.
- **Reconstruction:** each candidate is rebuilt from `json_base` with the executor in benchmark
  mode. The manifest's `checks` block confirms the rebuild:
  - all 4700 exact-match candidates equal the GT;
  - all 1459 other candidates with a logged prediction equal that prediction;
  - `reindex_structure` changed no candidate.
- **How GT and base are checked:** the GT is checked with the dataset instruction(s) as its batch,
  and the base with an empty batch.
- **Results folder:**
  [benchmarks/results/validator_pass/20260928T224634Z_c818998_9ed0ce/](../benchmarks/results/validator_pass/20260928T224634Z_c818998_9ed0ce/).
  `pe_batches.csv` and `vanilla_pass.csv` are in Zenodo (checksums in
  `benchmarks/results/zenodo_files.sha256`).

The categories are mutually exclusive and assigned in this order:

| Category | Meaning |
|---|---|
| a | No usable batch: empty, or not a valid `ModificationBatch` |
| b | Some route does not resolve; the executor aborts before applying |
| c1-base | Rejected; GT and base are inadmissible |
| c1-request | Rejected; GT inadmissible, base admissible |
| c2 | Rejected; GT admissible |
| d0 | Admitted; exact match, GT admissible |
| d1 | Admitted; not an exact match, GT admissible |
| d2 | Admitted; GT inadmissible |

### Totals

These counts come from `pe_summary.csv`, with 95 % percentile bootstrap intervals (B = 10 000).
The DOMINIO and RED DE PETRI rows repeat the classification with the validator restricted to that
group's rules.

| Rules | a | b | c1-base | c1-request | c2 | d0 | d1 | d2 | Rejected | c2 / (c2 + d1) |
|---|---|---|---|---|---|---|---|---|---|---|
| all 16 | 41 | 438 | 1632 | 1587 | 77 | 2180 | 229 | 16 | 3296 (53.2 % [51.9, 54.4]) | 25.2 % [20.3, 30.1] |
| DOMINIO only | 41 | 438 | 1597 | 588 | 106 | 2900 | 457 | 73 | 2291 (37.0 % [35.8, 38.2]) | 18.8 % [15.6, 22.0] |
| RED DE PETRI only | 41 | 438 | 0 | 1754 | 55 | 3420 | 470 | 22 | 1809 (29.2 % [28.1, 30.3]) | 10.5 % [8.0, 13.1] |

- Of the rejections with all rules, 97.7 % [97.1, 98.1] are c1: the GT itself is inadmissible.
- c2, the rejections of a batch whose GT is admissible, are 1.24 % [0.97, 1.53] of all batches.
- By backend, c2 counts: Claude Sonnet 4.6 5, GPT-5.4 2, gpt-oss:20b 10, Llama 3.1 60.

### Per rule

The table counts rejected batches (categories c1-base, c1-request and c2; 3296 in all) with at
least one violation of each rule. A batch can violate several rules, so the counts do not add up.

| Rule | Group | Rejected | c1-base | c1-request | c2 |
|---|---|---|---|---|---|
| `campos_leidos` | RED DE PETRI | 1635 | 468 | 1164 | 3 |
| `equipos` | DOMINIO | 1627 | 1579 | 48 | 0 |
| `campos_esquema` | DOMINIO | 740 | 173 | 560 | 7 |
| `prec_aciclica` | RED DE PETRI | 331 | 65 | 264 | 2 |
| `tipos` | DOMINIO | 88 | 33 | 22 | 33 |
| `referencias` | DOMINIO | 33 | 3 | 14 | 16 |
| `campos_fuera_de_nivel` | DOMINIO | 21 | 3 | 10 | 8 |
| `dom_int` | RED DE PETRI | 20 | 1 | 3 | 16 |
| `rangos` | DOMINIO | 7 | 1 | 0 | 6 |
| `no_vacia` | RED DE PETRI | 4 | 3 | 1 | 0 |
| `dom_real` | RED DE PETRI | 2 | 0 | 1 | 1 |
| `turno_minimo` | RED DE PETRI | 1 | 0 | 0 | 1 |
| `ids`, `limites`, `sanity_batch`, `prec_tipos` | | 0 | 0 | 0 | 0 |

- **Source:** `pe_rules_by_category.csv` in the run folder, written by
  [benchmarks/metrics/validator_rule_table.py](../benchmarks/metrics/validator_rule_table.py)
  from `pe_batches.csv` and the rule map of `manifest.json`. The script checks its c2 column
  against `pe_c2_by_rule.csv`, which the pass wrote itself.
- **Cycles in lists the net does not read:** 81 of the 3296 rejections (2.5 %) violate only
  `prec_aciclica`, and every edge of their cycles is in `Order_Before` (60) or
  `Activity_Order_Before` (21), which the net does not read. The same script writes these counts
  to `pe_cycle_only_rejections.csv`.

- **c1-base:** nearly all of it is `equipos`, which comes from the dataset bases (see
  [benchmark.md](benchmark.md#inadmissibility-of-the-generated-samples)).
- **Where GTs fail:** the rules that make a GT inadmissible when the base is admissible are
  `campos_leidos`, `campos_esquema` and `prec_aciclica`. They follow from requests that delete a
  required field or add a precedence that closes a cycle.

### c2 examples

`pe_c2_examples.json` keeps up to three c2 batches per rule, with their instructions. The
messages below are those of the current code on the same candidates. A batch listed as "(+n)"
has n more instructions that do not cause the violation.

| Rule | Backend | Axis, level, sample | Offending instruction | Violation |
|---|---|---|---|---|
| `campos_esquema` | Llama 3.1 | complexity 14, #657 | `DELETE A001.tasks.T006.Requires_Shutdown` | A001.T006 has no Requires_Shutdown field |
| `campos_esquema` | Llama 3.1 | completeness 1, #15 | `DELETE A002.tasks.T001.Requires_Shutdown` | A002.T001 has no Requires_Shutdown field |
| `campos_esquema` | Llama 3.1 | completeness 2, #76 | `DELETE A002.tasks.T008.Requires_Shutdown` (+1) | A002.T008 has no Requires_Shutdown field |
| `campos_fuera_de_nivel` | Claude Sonnet 4.6 | completeness 11, #517 | `SET A001.tasks.T001.Start_disp = 115` (+10) | A001.T001 has Start_disp, which is an activity field, not a task field |
| `campos_fuera_de_nivel` | Claude Sonnet 4.6 | completeness 15, #748 | `SET A001.Teams = 16` (+14) | A001 has Teams, which is a global field, not an activity field |
| `campos_fuera_de_nivel` | Llama 3.1 | complexity 12, #550 | `SET A003.tasks.T001.Start_disp = "A002.Duration"` | A003.T001 has Start_disp, which is an activity field, not a task field (also `tipos`) |
| `campos_leidos` | Llama 3.1 | complexity 10, #472 | `DELETE A003.Start_disp` | A003 has no Start_disp field |
| `campos_leidos` | Llama 3.1 | completeness 1, #4 | `DELETE A002.T_wait` | A002 has no T_wait field |
| `campos_leidos` | Llama 3.1 | completeness 4, #181 | `DELETE A002.T_wait` (+4) | A002 has no T_wait field |
| `dom_int` | Claude Sonnet 4.6 | completeness 7, #310 | `SET A001.tasks.T003.Duration = 0.75` (+6) | A001.T003.Duration is 0.75; it must be an integer >= 1 |
| `dom_int` | GPT-5.4 | completeness 7, #310 | `SET A001.tasks.T003.Duration = 0.75` (+6) | A001.T003.Duration is 0.75; it must be an integer >= 1 |
| `dom_int` | gpt-oss:20b | complexity 10, #454 | `SET A001.Team members = ["Operario1", …, "Operario8"]` | A001.Team members is ["Operario1", …]; it must be an integer >= 1 (also `tipos`) |
| `dom_real` | Llama 3.1 | complexity 5, #220 | `SET A002.Start_disp = "A001"` | A002.Start_disp is "A001"; it must be a finite number >= 0 (also `tipos`) |
| `prec_aciclica` | Llama 3.1 | complexity 80, #2606 | `APPEND A004.tasks.T005.Order_Before = "T002"` | precedence cycle among T002, T003, T005: A004.T002 lists T003 in Order_Before; A004.T003 lists T005 in Order_Before; A004.T005 lists T002 in Order_Before |
| `prec_aciclica` | Llama 3.1 | completeness 13, #615 | `APPEND A002.tasks.T004.Order_Before = "T002"` (+8) | precedence cycle among T002, T003, T004: A002.T002 lists T003 in Order_Before; A002.T003 lists T004 in Order_Before; A002.T004 lists T002 in Order_Before |
| `rangos` | Llama 3.1 | complexity 1, #12 | `SET A001.Shift_duration = 5256` | A001.Shift_duration is 5256; it must be <= 24 |
| `rangos` | Llama 3.1 | complexity 1, #23 | `SET A001.Shift_duration = 4341` | A001.Shift_duration is 4341; it must be <= 24 |
| `rangos` | Llama 3.1 | complexity 1, #49 | `SET A001.Shift_duration = 3276` | A001.Shift_duration is 3276; it must be <= 24 |
| `referencias` | Claude Sonnet 4.6 | complexity 28, #1391 | `DELETE A002.tasks.T004` | A002.T003 lists T004 in Order_Before, but T004 does not exist in A002 |
| `referencias` | Claude Sonnet 4.6 | completeness 12, #597 | `DELETE A003.tasks.T002` (+11) | A003.T001 lists T002 in Order_Before, but T002 does not exist in A003 |
| `referencias` | GPT-5.4 | completeness 12, #597 | `DELETE A003.tasks.T002` (+11) | A003.T001 lists T002 in Order_Before, but T002 does not exist in A003 |
| `tipos` | gpt-oss:20b | complexity 10, #454 | `SET A001.Team members = ["Operario1", …, "Operario8"]` | A001.Team members is ["Operario1", …]; it must be an integer (also `dom_int`) |
| `tipos` | gpt-oss:20b | complexity 50, #2479 | `SET A001.Team members = ["Operario1", "Operario2"]` | A001.Team members is ["Operario1", "Operario2"]; it must be an integer (also `dom_int`) |
| `tipos` | gpt-oss:20b | complexity 100, #2732 | `SET A001.Team members = ["Operario1", "Operario2"]` | A001.Team members is ["Operario1", "Operario2"]; it must be an integer (also `dom_int`) |
| `turno_minimo` | Llama 3.1 | complexity 12, #595 | `SET A001.Shift_duration = 0` (+1) | A001.Shift_duration is 0; it must be >= 1 (hours) |

The offline pass passes no previous configuration to the validator, so `referencias` reports
"does not exist" even when the batch itself deleted the task. In the agent, `_apply_batch` passes
$S_k$, and the same candidates would read "no longer exists".

### Configurations returned by vanilla

`vanilla_pass.csv` checks the configuration each vanilla call returned, with an empty batch. For
exact matches that configuration is the GT.

| Source | Admissible | Inadmissible |
|---|---|---|
| Exact match (the GT) | 1558 | 1465 |
| Other calls (`failed_cases.json_pred`) | 1016 | 2153 |
| No configuration logged | 8 | |

### Reproduce

```
python benchmarks/metrics/validator_pass.py --rules-commit c818998
```

The script writes a new folder under `benchmarks/results/validator_pass/`. It records the
validator, executor and reindexing commits in force, and whether `input_agent/` was clean. Run at
the current HEAD, it applies the same rules with the current English messages.
