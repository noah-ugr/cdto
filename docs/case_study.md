# Case study (Subsection 4.2)

This document backs the case study with detail the paper leaves out:

- which run each category comes from;
- the full text of every query and answer (the paper condenses them);
- the edits each query made and the effect of each edit on its own;
- the execution plans of A001 and A002;
- the known limitations.

## Runs

The case runs through the same code path as the web demo: `AppState.initialize()` and the
`/chat` endpoint function of [core/api.py](../core/api.py), with one thread and the queries in
order. The driver is
[benchmarks/case_study/rerun_case_study.py](../benchmarks/case_study/rerun_case_study.py).

| Categories | Queries | Run | HEAD |
|---|---|---|---|
| A, B, C, D, E | 1–7 | [20260930T001541Z_gpt-oss-20b-ctx32k](../benchmarks/results/case_study_rerun/20260930T001541Z_gpt-oss-20b-ctx32k/) | `52d74aa` |
| F | 8 | [20260930T001926Z_gpt-oss-20b-ctx32k_with_opt](../benchmarks/results/case_study_rerun/20260930T001926Z_gpt-oss-20b-ctx32k_with_opt/) | `52d74aa` |

Both runs used the same setup:

- **Model:** `gpt-oss-20b-ctx32k` on Ollama 0.24.0, digest `65086a4a68ab…`, temperature 0, no
  seed, timeout 600 s. It is `gpt-oss:20b` with a 32 768-token context; see
  [benchmark.md](benchmark.md#runs-of-september-2026-humanisation-check-and-case-study).
- **Environment:** `.env` disabled, every LLM setting taken from the process environment and
  recorded in `manifest.json` with keys redacted.

Each run folder holds, per query:

- the response, the update of every node and the final state;
- the configuration before and after the query;
- the engine outputs of its simulations; the PNGs are in Zenodo.

For query 5 it also holds the violations, the rejected candidate, its simulation, the explanation
and the feedback.

In query 8 of `001926Z` the IWO, the check, the simulation of $S^*$, the xAI and the chat
completed. Queries 1–7 of that run left the same configurations as in `001541Z`.

Queries 1–7 are run in both, with the same results and different texts:

- **Identical:** node sequences, executor outcomes, every configuration and the simulation
  results (`general_outputs_all.json`, `calculated_task_durations.json`) have the same SHA-256.
  The documentation the temporal xAI reads in query 7 (`dynamic_documentation.md` and `.txt`) is
  identical too.
- **Different:** the texts of the LLM, because the model has no seed and its chat template inserts
  the current date. The temporal answer of query 7 describes the handoff from A002 to A001 in
  `001541Z` and from A001 to A002 in `001926Z`; this is the second run that Subsection 4.2
  mentions.

The comparison test of category F, one report on $S_0$, $S_{k+1}$ and $S^*$, was not run (see
[Known limitations](#known-limitations)).

## Configuration $S_0$

This is Table `tab:simulation_configuration`, the configuration hard-coded in `core/api.py`
(`S0.json` in each run):

```json
{
  "runId": 25, "Teams": 1, "Simulation_period": 2000,
  "A001": {
    "tasks": {
      "T001": {"Duration": 10, "Requires_Shutdown": false},
      "T002": {"Duration": 30, "Requires_Shutdown": true},
      "T003": {"Duration": 40, "Requires_Shutdown": false, "taskDependency": true, "taskCode": ["T001", "T002"]}
    },
    "T_period": 480, "T_wait": 2, "Start_disp": 3, "Team": "TeamA", "Team members": 2, "Shift_duration": 8
  },
  "A002": {
    "tasks": {
      "T001": {"Duration": 80, "Requires_Shutdown": false},
      "T002": {"Duration": 100, "Requires_Shutdown": false, "taskDependency": true, "taskCode": ["T001"]},
      "T003": {"Duration": 60, "Requires_Shutdown": true, "taskDependency": true, "taskCode": ["T001"]},
      "T004": {"Duration": 10, "Requires_Shutdown": false, "taskDependency": true, "taskCode": ["T002", "T003"]}
    },
    "T_period": 720, "T_wait": 4, "Start_disp": 1, "Team": "TeamA", "Team members": 2, "Shift_duration": 8,
    "activityDependency": true, "activityCode": ["A001"]
  }
}
```

## Queries

The orchestrator and the dispatcher start every query; the table lists the nodes each query ran
after them (`node_updates.json`).

| # | Category | Query | Nodes | Outcome |
|---|---|---|---|---|
| 1 | A | What are the duration and shutdown requirement of each task in A002? | context, chat | `GET A002.tasks` returned the four tasks; $S_0$ unchanged |
| 2 | A | How many technicians are assigned to A001 and what is its dispatch start time? | context, chat | `GET A001.Team members` = 2, `GET A001.Start_disp` = 3; unchanged |
| 3 | B | Task T002 in A002 is causing delays. Reduce its duration by 15 %. | context, planner, executor, chat | `GET A002.tasks.T002.Duration` = 100; batch `SET A002.tasks.T002.Duration = 85`; committed |
| 4 | B | Increase the dispatching wait time of A002 by 50 %. | context, planner, executor, chat | `GET A002.T_wait` = 4; batch with `SET A002.T_wait = 6` (see below); committed, giving $S_{k+1}$ |
| 5 | C | Remove task T001 from A002; it looks like a redundant initial check. | planner, executor, simulator, xai, feedback, chat | Batch rejected by `referencias` (DOMINIO); candidate simulated against $S_k$; feedback |
| 6 | D | Simulate the updated configuration and explain the performance difference versus the original baseline. | simulator, xai, chat | $S_{k+1}$ simulated; KPIs against $S_0$ |
| 7 | E | What happens between t=400 and t=410 h? Show the A001–A002 handoff sequence. | temporal_xai, chat | Transitions in [400, 410] h identified |
| 8 | F | Net plan availability of 87.5 % is insufficient. Optimize the system to reach at least 90 %. | optimizer, simulator, xai, chat | $S^*$ checked, committed, simulated and explained against $S_{k+1}$ |

Batches of the edit queries (`q3`–`q5/edit_report.json`):

- **Query 3:** `SET A002.tasks.T002.Duration = 85`.
- **Query 4:** the planner emitted `SET A001.Team members = 2`, `SET A001.Start_disp = 3`,
  `SET A002.tasks.T002.Duration = 85` and `SET A002.T_wait = 6`. The first three write values the
  configuration already had, so the only change is `A002.T_wait` 4 → 6.
- **Query 5:** `DELETE A002.tasks.T001`. The check returned:

  ```
  [referencias | DOMINIO] A002.tasks.T002.taskCode: A002.T002 lists T001 in taskCode, but T001 no longer exists in A002
  [referencias | DOMINIO] A002.tasks.T003.taskCode: A002.T003 lists T001 in taskCode, but T001 no longer exists in A002
  ```

### Full answers

Queries 1–7 come from `20260930T001541Z_gpt-oss-20b-ctx32k` and query 8 from
`20260930T001926Z_gpt-oss-20b-ctx32k_with_opt`. The texts are copied from `response.json`
(`response`, `xai_report`, `episodic_xai_report`) without edits.

<details>
<summary>Query 1 (A)</summary>

The first answer of a session starts with the baseline xAI report ($S_0$ against itself, so all
deltas are zero). `/chat` prepends it when the session has no baseline report yet
(`core/api.py`, cold start).

```text
1. JSON Changes
- No structural changes detected.

2. KPI Changes

| KPI | Baseline | Current | Delta abs | Delta % |
|---|---:|---:|---:|---:|
| Activities Overlap (%) | 0.0000 | 0.0000 | 0.0000 | N/A |
| Intervention Time (h) | 1130.0000 | 1130.0000 | 0.0000 | 0.00% |
| Net Plan Availability (h) | 1750.0000 | 1750.0000 | 0.0000 | 0.00% |
| Net Plan Availability (%) | 87.5000 | 87.5000 | 0.0000 | 0.00% |
| Net Plan Unavailability (h) | 250.0000 | 250.0000 | 0.0000 | 0.00% |
| Net Plan Unavailability (%) | 12.5000 | 12.5000 | 0.0000 | 0.00% |
| P4 Busy Time (h) | 1002.0000 | 1002.0000 | 0.0000 | 0.00% |
| P4 Busy Time (%) | 50.1000 | 50.1000 | 0.0000 | 0.00% |
| Simulation Period (h) | 2000.0000 | 2000.0000 | 0.0000 | 0.00% |

3. Causality Between JSON Delta and KPI Delta (Detailed Explanation)
- With no JSON delta, all KPI values remain unchanged, reflecting the baseline operational state.
- The intervention time, net plan availability, and P4 busy time are stable, indicating consistent resource allocation and scheduling.
- The 12.5% unavailability aligns with the 250 h downtime within a 2000 h period, confirming expected maintenance or outage rates.
- Overall, the system operates at its designed capacity (87.5% availability, 50.1% P4 utilization) with no deviations to attribute to configuration changes.

T001 takes 80 minutes and does not require a shutdown; T002 takes 100 minutes and also does not require a shutdown. These tasks are part of the A002 process and can run concurrently if dependencies allow. Would you like to see the full task list or simulate scheduling for A002?
```

</details>

<details>
<summary>Query 2 (A)</summary>

```text
There are 2 technicians assigned to A001, and its dispatch start time is 3 (hours from the reference point). This means the team is ready to begin operations at that time. If you’d like to review the full schedule or modify the start time, just let me know.
```

</details>

<details>
<summary>Query 3 (B)</summary>

```text
The duration of Task T002 in A002 has been reduced from 100 to 85 units, cutting its time by 15%. This should help eliminate the current bottleneck and bring the overall project timeline closer to target. Next, you might want to run a simulation to see how this change propagates through the schedule, or check the updated KPI impact to confirm the improvement. Let me know if you’d like to proceed with a simulation or review the KPI changes.
```

</details>

<details>
<summary>Query 4 (B)</summary>

```text
The wait time for A002 has been increased from 4 to 6 units, a 50% boost as requested. This means the system will hold the dispatch for a longer period before proceeding, potentially reducing overlap with other tasks and giving more buffer for resource allocation. You might want to run a quick simulation to see how this change affects overall throughput or check the KPI dashboard for any shift in intervention time. Let me know if you'd like to simulate the impact or explore further adjustments.
```

</details>

<details>
<summary>Query 5 (C): answer and episodic xAI report</summary>

Answer:

```text
I see that removing T001 would create dangling references in tasks T002 and T003, which the validation engine flags as a referential integrity violation. This means the configuration cannot be applied safely until those references are resolved. To proceed, you could either keep T001, update T002 and T003 to drop the reference, or set T001’s duration to zero to preserve the link. Which option would you like to explore next?
```

Episodic xAI report (rejected candidate against $S_k$):

```text
# 1. JSON Changes
- **Deleted Task**: `T001` removed from activity `A002`.
- **Reference Violations**: Tasks `T002` and `T003` in `A002` still list `T001` in their `taskCode` field, creating dangling references.
- **No other structural changes**: No new activities, tasks, or global parameters were added or modified.

# 2. KPI Changes
| KPI | Baseline | Current | Delta abs | Delta % |
|---|---:|---:|---:|---:|
| Activities Overlap (%) | 0.0000 | 0.0000 | 0.0000 | N/A |
| Intervention Time (h) | 1088.0000 | 1040.0000 | -48.0000 | -4.41% |
| Net Plan Availability (h) | 1718.0000 | 1718.0000 | 0.0000 | 0.00% |
| Net Plan Availability (%) | 85.9000 | 85.9000 | 0.0000 | 0.00% |
| Net Plan Unavailability (h) | 282.0000 | 282.0000 | 0.0000 | 0.00% |
| Net Plan Unavailability (%) | 14.1000 | 14.1000 | 0.0000 | 0.00% |
| P4 Busy Time (h) | 956.0000 | 782.0000 | -174.0000 | -18.20% |
| P4 Busy Time (%) | 47.8000 | 39.1000 | -8.7000 | -18.20% |
| Simulation Period (h) | 2000.0000 | 2000.0000 | 0.0000 | 0.00% |

**Top Positive Shift**: None (all deltas are zero or negative).
**Top Negative Shift**: P4 Busy Time (h) –174 h (–18.20 %).

# 3. Causality Between JSON Delta and KPI Delta (Detailed Explanation)
- **Direct Effect**: Removing task `T001` from activity `A002` immediately reduces the workload assigned to that activity. This manifests as a 48‑hour decrease in overall intervention time (–4.41 %) and a 174‑hour drop in P4 busy time (–18.20 %). The proportional reductions in both metrics confirm that `T001` was a significant contributor to resource utilization.
- **Secondary/Cascade Effect**: The lower intervention and P4 busy times reduce the pressure on shared resources, which in turn keeps net plan availability and unavailability unchanged. The unchanged availability percentages (85.9 % and 14.1 %) indicate that the system’s capacity constraints were not affected by the deletion.
- **Reference Violations**: Tasks `T002` and `T003` still reference the deleted `T001`. While these dangling references do not directly alter the KPI values shown, they could lead to scheduling inconsistencies in future iterations if not resolved.

**Verdict**: The configuration change improves resource efficiency (lower intervention and busy times) without compromising overall plan availability. The impact is mixed: operational metrics improved, but no change in availability or simulation period. Overall, the system operates more efficiently post‑deletion.
```

</details>

<details>
<summary>Query 6 (D): answer and xAI report</summary>

Answer:

```text
I see the detailed xAI report has already been shared. A key takeaway is that the 15% reduction in task duration lowered intervention time and P4 busy time, but the 50% increase in wait time pushed net plan unavailability up by 12.8%. Next, you might want to run a sensitivity test on the wait time to see if a smaller increase could balance the unavailability without hurting intervention time.
```

xAI report ($S_{k+1}$ against $S_0$):

```text
1. JSON Changes

- **Wait Time**: A002 T_wait increased from 4 to 6 (+50%).
- **Task Duration**: A002 T002 Duration decreased from 100 to 85 (-15%).

2. KPI Changes

| KPI | Baseline | Current | Delta abs | Delta % |
|---|---:|---:|---:|---:|
| Activities Overlap (%) | 0.0000 | 0.0000 | 0.0000 | N/A |
| Intervention Time (h) | 1130.0000 | 1088.0000 | -42.0000 | -3.72% |
| Net Plan Availability (h) | 1750.0000 | 1718.0000 | -32.0000 | -1.83% |
| Net Plan Availability (%) | 87.5000 | 85.9000 | -1.6000 | -1.83% |
| Net Plan Unavailability (h) | 250.0000 | 282.0000 | 32.0000 | 12.80% |
| Net Plan Unavailability (%) | 12.5000 | 14.1000 | 1.6000 | 12.80% |
| P4 Busy Time (h) | 1002.0000 | 956.0000 | -46.0000 | -4.59% |
| P4 Busy Time (%) | 50.1000 | 47.8000 | -2.3000 | -4.59% |
| Simulation Period (h) | 2000.0000 | 2000.0000 | 0.0000 | 0.00% |

**Top positive shift**: Net Plan Unavailability (+12.8%).
**Top negative shift**: P4 Busy Time (%) (-4.59%).

3. Causality Between JSON Delta and KPI Delta (Detailed Explanation)

- The 50 % increase in A002 T_wait (+2 units) contributes to a modest rise in overall unavailability, but the 15 % reduction in T002 Duration (-15 units) dominates, leading to a net decrease in Intervention Time by 42 h.
- Shorter task duration directly reduces P4 busy time (–46 h, –4.59 %) and consequently lowers Net Plan Availability by 32 h (–1.83 %) while increasing Net Plan Unavailability by the same amount.
- The increased wait time adds to the unavailability pool, amplifying the Net Plan Unavailability rise.
- Secondary effect: Lower P4 busy time reduces resource utilization, which further limits plan availability, creating a cascade that worsens Net Plan Availability and increases Unavailability.

**Verdict**: Mixed impact – intervention and resource utilization improved, but plan availability and unavailability worsened.
```

</details>

<details>
<summary>Query 7 (E): answer and temporal report</summary>

Answer:

```text
The handoff from A002 to A001 occurs smoothly: at t=409 h A002’s break ends, freeing capacity for A001, and at t=410 h a worker is assigned to both, locking maintenance and starting downstream work. This sequence shows no bottlenecks and confirms the baseline behavior. Next, you could simulate a slight delay in the break clearance to see how it affects downstream throughput.
```

Temporal report:

```text
## Executive Summary
Between **t=400** and **t=410 h** the simulation executed a handoff from activity **A002** to **A001**. At **t=409 h** the break‑state of A002 was cleared, allowing A001 to enter its loop state and allocate capacity. One hour later, at **t=410 h**, a worker was assigned to both activities, locking the maintenance resource and enabling downstream work. The sequence demonstrates a smooth transition with no bottlenecks, consistent with the baseline behavior.

## Chronological Causal Narrative
- **t=409 h – Transition t4 fires**
  - *Cause*: Break token in **p5** and available capacity in **p3**.
  - *Effect*: Break token consumed, work‑state token produced, A002 marker moved from **p20** to **p021** (A001 loop), 25 capacity tokens allocated to **p3**, maintenance token to **p4**.
  - *Result*: A001 is now ready to start work; A002 is in a transition state.
- **t=410 h – Transition t3 fires**
  - *Cause*: Availability of a worker in **p3** and initial states of **p20** (A002) and **p021** (A001).
  - *Effect*: 1 token removed from **p3** (28→27), tokens added to **p20**, **p021**, **p4**, **p5**.
  - *Result*: Worker allocated to both A001 and A002, maintenance lock held, work commenced.

The chain **t4 → t3** illustrates the handoff: A002’s break ends, A001 begins work, and a shared worker is assigned.

## Pattern Analysis
- **No bottleneck detected**: The capacity pool **p3** remained partially available (27 tokens after t3) and did not constrain subsequent transitions.
- **Resource allocation pattern**: A001 received a bulk allocation of 25 capacity tokens at t=409, followed by a single worker token at t=410, indicating a staged handoff.
- **Maintenance lock**: The token in **p4** was consistently held during the handoff, preventing other maintenance‑dependent activities from proceeding.

## Impact on System State
| Place | Before (t=408.9) | After (t=410.1) | Change |
|-------|------------------|-----------------|--------|
| p20 (A002) | 1 | 1 | 0 |
| p021 (A001) | 0 | 1 | +1 |
| p3 (capacity) | 28 | 27 | –1 |
| p4 (maintenance) | 0 | 1 | +1 |
| p5 (break/work) | 1 | 1 | 0 |

The state changes confirm that A001 entered its loop state and a worker was allocated, while A002 remained in a transitional state.

## Configuration Impact
- **A002 T_wait increased from 4 h to 6 h**: The longer wait time likely delayed the readiness of the break token, but the handoff still occurred at the scheduled time.
- **A002 T002 duration decreased by 15 % (100 h → 85 h)**: This reduction would have advanced the overall timeline, potentially allowing the handoff to happen earlier; however, the events at 409–410 h remain consistent with the new duration.

No structural changes were introduced, so the handoff sequence follows the original design.

## Baseline Comparison
Compared to the baseline xAI report, the handoff sequence shows **identical behavior**: the same transitions fire at the same times, and the token counts match the baseline expectations. The KPI metrics (intervention time, net plan availability, P4 busy time) remain unchanged, confirming that the configuration delta did not alter the overall system performance during this window.
```

</details>

<details>
<summary>Query 8 (F): answer and xAI report</summary>

Answer:

```text
Great news—the optimization bumped Net Plan Availability up to 98.7%, comfortably above the 90% target. This was achieved mainly by adding more team members and adjusting start dispersion, which cut intervention time and freed up the plan. Next, you could run a short‑term simulation to confirm stability or review the impact on P4 Busy Time to ensure no downstream bottlenecks.
```

xAI report ($S^*$ against $S_{k+1}$):

```text
1. JSON Changes
- **Activity Values**
  - *A002*:
    - Start_disp: 1 → 21.1246 (+2012.46%)
    - Team members: 2 → 20 (+900%)
    - T_wait: 6 → 0.9992 (‑83.35%)
  - *A001*:
    - Start_disp: 3 → 20.1628 (+572.09%)
    - Team members: 2 → 20 (+900%)
    - T_wait: 2 → 3.8469 (+92.35%)
- No other structural changes.

2. KPI Changes
| KPI | Baseline | Current | Delta abs | Delta % |
|---|---:|---:|---:|---:|
| Activities Overlap (%) | 0.0000 | 0.0000 | 0.0000 | N/A |
| Intervention Time (h) | 1088.0000 | 591.0000 | -497.0000 | -45.68% |
| Net Plan Availability (h) | 1718.0000 | 1973.6931 | 255.6931 | 14.88% |
| Net Plan Availability (%) | 85.9000 | 98.6847 | 12.7847 | 14.88% |
| Net Plan Unavailability (h) | 282.0000 | 26.3069 | -255.6931 | -90.67% |
| Net Plan Unavailability (%) | 14.1000 | 1.3153 | -12.7847 | -90.67% |
| P4 Busy Time (h) | 956.0000 | 131.0406 | -824.9594 | -86.29% |
| P4 Busy Time (%) | 47.8000 | 6.5520 | -41.2480 | -86.29% |
| Simulation Period (h) | 2000.0000 | 2000.0000 | 0.0000 | 0.00% |

**Top positive shift:** Net Plan Availability (h) (+14.88%) and Net Plan Availability (%) (+14.88%).
**Top negative shift:** Net Plan Unavailability (h) (-90.67%) and Net Plan Unavailability (%) (-90.67%).

3. Causality Between JSON Delta and KPI Delta (Detailed Explanation)
The primary configuration changes involve a substantial increase in team members for both activities (from 2 to 20) and a significant expansion of start dispersion values. These adjustments directly reduce the duration of interventions, as evidenced by the 45.68% drop in Intervention Time (h). Shorter interventions free up plan availability, leading to a 14.88% increase in Net Plan Availability (h) and a corresponding rise in Net Plan Availability (%). The reduction in intervention time also cascades to a dramatic 86.29% decrease in P4 Busy Time (h) and P4 Busy Time (%), as the resource P4 is engaged for fewer hours. Consequently, Net Plan Unavailability (h) and Net Plan Unavailability (%) plummet by 90.67%, reflecting the system’s improved resilience. The increased start dispersion further mitigates potential overlaps, maintaining Activities Overlap at 0%. Overall, the configuration delta yields a net improvement in operational efficiency and availability, with the most pronounced gains in plan availability and reductions in busy time and unavailability.
```

</details>

## KPIs of each configuration

All KPIs are over 2000 h and come from the CDTO simulations: $S_0$, $S_{k+1}$ and the rejected
candidate from `001541Z`, and $S^*$ with its reference from `001926Z`.

| Configuration | Intervention (h) | P4 busy (h) | Net availability | Net unavailability (h) |
|---|---|---|---|---|
| $S_0$ | 1130 | 1002 | 87.5 % | 250 |
| $S_{k+1}$ (queries 3 and 4) | 1088 | 956 | 85.9 % | 282 |
| Rejected candidate of query 5 ($S_{k+1}$ without A002.T001) | 1040 | 782 | 85.9 % | 282 |
| $S^*$ (query 8) | 591 | 131.04 | 98.68 % | 26.31 |

## Attribution of each edit

$S_{k+1}$ differs from $S_0$ in two edits. To tell which edit causes each KPI change,
[benchmarks/case_study/single_edit_attribution.py](../benchmarks/case_study/single_edit_attribution.py)
simulates each edit alone on $S_0$. Each configuration runs in a new process; the results are in
[benchmarks/results/case_study_attribution/20260929T095804Z_single_edits/](../benchmarks/results/case_study_attribution/20260929T095804Z_single_edits/).

"Calendar" is the time from the start to the end of each execution of the task, shifts included,
equal in both executions.

| Configuration | Intervention (h) | P4 busy (h) | Availability | Unavailability (h) | A002.T001 calendar (h) | A002.T002 calendar (h) | A002.T003 calendar (h) | A002.T004 calendar (h) |
|---|---|---|---|---|---|---|---|---|
| $S_0$ | 1130 | 1002 | 87.5 % | 250 | 120 | 162 | 78 | 21 |
| $S_0$ + `A002.T_wait = 6` only | 1134 | 1002 | 85.9 % | 282 | 120 | 146 | 94 | 21 |
| $S_0$ + `A002.tasks.T002.Duration = 85` only | 1084 | 956 | 87.5 % | 250 | 120 | 139 | 78 | 21 |
| $S_{k+1}$ (both) | 1088 | 956 | 85.9 % | 282 | 120 | 123 | 94 | 21 |

- **`T_wait` 4 → 6** stretches the shutdown task A002.T003 from 78 to 94 h in each execution
  (+16 h). Over the two executions that is the +32 h of unavailability; intervention time rises
  by 4 h.
- **`T002` 100 → 85** lowers intervention time and P4 busy time by 46 h each, with no change in
  availability.
- **Both edits** give −42 h of intervention and −46 h of P4 busy time, from the shorter T002, and
  +32 h of unavailability, from the longer wait.

## Execution plans of A001 and A002

[benchmarks/case_study/plot_gantt_comparison.py](../benchmarks/case_study/plot_gantt_comparison.py)
draws the plans in the format of the paper's figure:

- one row per task execution;
- $S_0$ in blue and $S_{k+1}$ in orange;
- idle gaps scaled by 0.05;
- a table of times.

It does not simulate. It reads the fresh simulations saved by
[regenerate_gantt.py](../benchmarks/case_study/regenerate_gantt.py) and checks their hashes.

- **Output:**
  [benchmarks/results/case_study_gantt/20260929T093403Z_gantt_paper_format/](../benchmarks/results/case_study_gantt/20260929T093403Z_gantt_paper_format/),
  with `gantt_A001.pdf` (Figure `fig:gantt_chart_modified`), `gantt_A002.pdf` and
  `gantt_tables.json`; the PNGs are in Zenodo.
- **Source simulations:**
  [benchmarks/results/case_study_gantt/20260929T084426Z_gantt/](../benchmarks/results/case_study_gantt/20260929T084426Z_gantt/).
- **Transition names:** transition `t0007{j}{i}` is task `T00j` of activity `A00i`.

### A001 (first two executions)

| Row | Task | Execution | $S_0$ start–end (h) | $S_{k+1}$ start–end (h) | Shift (h) |
|---|---|---|---|---|---|
| a | A001.T003 | 1 | 388–438 | 367–417 | −21 |
| b | A001.T001 | 1 | 438–459 | 417–438 | −21 |
| c | A001.T002 | 1 | 459–506 | 438–485 | −21 |
| d | A001.T003 | 2 | 1493–1543 | 1451–1501 | −42 |
| e | A001.T001 | 2 | 1543–1564 | 1501–1522 | −42 |
| f | A001.T002 | 2 | 1564–1611 | 1522–1569 | −42 |

### A002 (first two executions)

| Row | Task | Execution | $S_0$ start–end (h) | $S_{k+1}$ start–end (h) | Shift of start / end (h) |
|---|---|---|---|---|---|
| a | A002.T004 | 1 | 5–26 | 7–28 | +2 / +2 |
| b | A002.T003 | 1 | 26–104 | 28–122 | +2 / +18 |
| c | A002.T002 | 1 | 104–266 | 122–245 | +18 / −21 |
| d | A002.T001 | 1 | 266–386 | 245–365 | −21 / −21 |
| e | A002.T004 | 2 | 1110–1131 | 1091–1112 | −19 / −19 |
| f | A002.T003 | 2 | 1131–1209 | 1112–1206 | −19 / −3 |
| g | A002.T002 | 2 | 1209–1371 | 1206–1329 | −3 / −42 |
| h | A002.T001 | 2 | 1371–1491 | 1329–1449 | −42 / −42 |

- **A002 cycle.** Each cycle of A002 ends 21 h sooner in $S_{k+1}$: the shorter T002 (−39 h of
  calendar time) outweighs the longer shutdown task T003 (+16 h) and the later start (+2 h).
- **Effect on A001.** In the plan, each execution of A001 starts when the cycle of A002 before it
  ends, so A001 starts 21 h earlier in the first cycle and 42 h earlier in the second.
- **Handoff.** The first execution of A001 starts at 367 h in $S_{k+1}$.

## Category F

Run `001926Z`, query 8.

1. **IWO.** The IWO ran on $S_{k+1}$ for 66.9 min and
   returned the decision vector $x^*$:

   | Variable | A001 | A002 |
   |---|---|---|
   | Crew size (`Team members`) | 20 | 20 |
   | Shift length (`Shift_duration`) | 8 | 8 |
   | `Start_disp` | 20.1628 | 21.1246 |
   | `T_wait` | 3.8469 | 0.9992 |

2. **$S^*$.** $S^*$ is $S_{k+1}$ with only these decision variables changed. It is applied as a
   batch of six SET instructions: `Team members`, `Start_disp` and `T_wait` of A001 and A002.
   `Shift_duration` was already 8.
3. **Check.** $S^*$ passed with no violations and was committed through the same path as the
   planner's batches.
4. **Simulation.** $S^*$ was then simulated and compared with the configuration it replaced,
   $S_{k+1}$, which was simulated too:

   | KPI | $S_{k+1}$ | $S^*$ | Change |
   |---|---|---|---|
   | Net availability | 85.9 % | 98.68 % | +12.78 pp |
   | Net unavailability | 282 h | 26.31 h | −255.69 h |
   | Intervention time | 1088 h | 591 h | −497 h |
   | P4 busy time | 956 h | 131.04 h | −824.96 h |

   $S^*$ reaches the 90 % target.
5. **Explanation.** The xAI explained $S^*$ against $S_{k+1}$ and the chat summarised it; both
   texts are under [Full answers](#full-answers).

The IWO convergence plot is `q8/iwo_convergence.png` (Zenodo).

## Known limitations

- **Internal evaluation of the optimizer.** The IWO scores each candidate with its own internal
  evaluation of the model, not with the CDTO simulation of the full configuration. Its objective
  values are therefore not the KPIs of the case study. The CDTO builds $S^*$ from the decision
  variables alone, checks it, and simulates it against $S_{k+1}$; the KPIs reported for $S^*$ are
  those of that simulation.
- **Episodic memory is not consulted in the API.**
  - When the check rejects a batch, the feedback node writes the query, the violations and the
    diagnosis to the episodic store.
  - No node of the graph reads that store. Only the command-line client
    ([input_agent/agent.py](../input_agent/agent.py)) consults it before a turn. The API used by
    the web demo and by this case study does not.
  - Simulation and xAI reports are not stored there either. A comparison of $S_0$, $S_{k+1}$ and
    $S^*$ drawn from episodic memory is therefore not possible, and the comparison test of
    category F was not run.
  - The driver runs with the working directory at `<CDTO_IO_DIR>/work`, so the episodic store of
    each run starts empty.

## Reproduce

See [reproduce.md](reproduce.md#case-study-subsection-42).
