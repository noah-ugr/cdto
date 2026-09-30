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
