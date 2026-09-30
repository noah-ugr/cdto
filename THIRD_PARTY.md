# Third-party code

The MIT licence in [LICENSE](LICENSE) covers only the code written by Noah Masegosa Cáceres. The
components below were written by others and are **not** covered by it.

This release leaves them out: none of them carries a licence that permits redistribution. The
parts of the paper that need them are listed in the [README](README.md#what-this-release-cannot-reproduce).

| Component | Files | Authors (file headers and history) | Licence | Used for |
|---|---|---|---|---|
| Petri net engine core | `PetriNetModules/PetriNet_module.py`, `RL_module.py`, `read_PN.py`, `__init__.py` | iPMLab (headers, 2023) | None declared | Every simulation: the case study, the execution plans, the attributions and the optimizer's evaluations |
| Net generators and Monte Carlo simulator | `Modules/Paramtrial_petri_net_A.py`, `Places_petri_net_A.py`, `Transitions_petri_net_A.py`, `activity_registry.py`, `exportResults.py`, `generateGaussian.py`, `monteCarloSimulator4.py`, `__init__.py` | Masoud Haghbin (`mhagh` in the headers) and others named in the headers ("Mohammad", "Mohammad Hisham Ismail"); refactored by QUANTIA (commits by `pepe-va2025`) | None declared | Same as above |
| Simulation pipeline and utilities | `core/pipeline.py`, `config/models.py`, `utils/datetime_utils.py`, `durations_utils.py`, `excel_utils.py`, `general_outputs_utils.py`, `generator_utils.py`, `logger.py`, `mapping_utils.py`, `pnipnt_utils.py` | QUANTIA (commits by `pepe-va2025`) | None declared | Translation of a configuration into the net, the run of the simulation and its KPIs |
| Optimizer | `core/main.py`, `optimizers/algorithms/iwo-new-single.py`, `optimizers/formulations/CostMinimization_underAvailability _TaskConstraints.py` | Masoud Haghbin (`mhagh` in the headers of `core/main.py` and the formulations) | None declared | Category F of the case study and `POST /optimize` |

Masoud Haghbin is a co-author of the paper.

## Modifications by Noah Masegosa Cáceres

These files were adapted for the CDTO; the modifications are not separated from the original code
in this release.

| File | Lines changed | Change |
|---|---|---|
| `core/main.py` | 1 | 2026-09-30: the repository root is taken from the location of the file instead of a fixed path on one machine (marked in the file) |
| `utils/mapping_utils.py` | 150 of 310 | Translation of the configuration into the algorithm format |
| `utils/generator_utils.py` | 49 of 270 | Generation of the net inputs |
| `core/pipeline.py` | 36 of 158 | Input/output folder and the run of the simulation |
| `Modules/monteCarloSimulator4.py`, `Paramtrial_petri_net_A.py`, `Places_petri_net_A.py`, `Transitions_petri_net_A.py` | 5, 3, 2, 2 | Paths and imports |
| `config/models.py` | 2 of 88 | Schema |
| `optimizers/algorithms/iwo-new-single.py`, the formulation | — | Paths and imports, when they were brought into this repository (March 2026) |

`config/paths.py` and `utils/automatic_documentation.py` were written by Noah Masegosa Cáceres and
are covered by the licence. 