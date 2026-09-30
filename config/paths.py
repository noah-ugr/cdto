"""Paths of the CDTO: the repository and the input/output folder of the simulations.

The simulations read and write under IO_DIR, which is CDTO_IO_DIR or /tmp/io: the net's input
workbooks in inputs/ and every result in outputs/results/. The only exception is
petrinet_shared_dicts.json, which the net generators read next to their scripts in Modules/.

Every path is fixed when the module is imported, so a process that needs another IO_DIR sets
CDTO_IO_DIR before importing it (input_agent.src.fresh_simulation runs each simulation in its own
process for that reason, among others). get_paths() returns every constant by name.
"""

import os
from pathlib import Path

# Repository
BASE_DIR = Path(__file__).resolve().parent.parent
MODULES_DIR = BASE_DIR / "Modules"

# Input/output folder of the simulations
IO_DIR = Path(os.getenv("CDTO_IO_DIR", "/tmp/io")).expanduser().resolve()
INPUTS_DIR = IO_DIR / "inputs"
OUTPUTS_DIR = IO_DIR / "outputs"
RESULTS_DIR = OUTPUTS_DIR / "results"

# Net generators and the workbooks they write
PLACES_SCRIPT = MODULES_DIR / "Places_petri_net_A.py"
TRANSITIONS_SCRIPT = MODULES_DIR / "Transitions_petri_net_A.py"
ARCS_SCRIPT = MODULES_DIR / "Paramtrial_petri_net_A.py"
PLACES_XLSX = INPUTS_DIR / "Place_petrinet_A.xlsx"
TRANSITIONS_XLSX = INPUTS_DIR / "Transitions_petrinet_A.xlsx"
ARCS_XLSX = INPUTS_DIR / "Arcs_petrinet_A.xlsx"
OUTPUT_XLSX = INPUTS_DIR / "Petrinet_A.xlsx"
SHARED_DICTS_JSON = MODULES_DIR / "petrinet_shared_dicts.json"

# Simulation results
SIM_OUTPUT_XLSX = RESULTS_DIR / "Petrinet_A_simulator.xlsx"
GENERAL_OUTPUTS_JSON = RESULTS_DIR / "general_outputs_all.json"
VISUALIZATION_METADATA_JSON = RESULTS_DIR / "visualization_metadata.json"

# Documentation and memory that the explainers read
DYNAMIC_DOCUMENTATION_MD = RESULTS_DIR / "dynamic_documentation.md"
DYNAMIC_DOCUMENTATION_TXT = RESULTS_DIR / "dynamic_documentation.txt"
EPISODIC_FAILURES_CSV = RESULTS_DIR / "episodic_failures.csv"
PETRI_VARIABLES_PDF = RESULTS_DIR / "Explanation_of_PetriNet_variables_.pdf"


def create_directories() -> None:
    """Create the input and result folders under IO_DIR if they are missing."""
    for folder in (INPUTS_DIR, OUTPUTS_DIR, RESULTS_DIR):
        folder.mkdir(parents=True, exist_ok=True)


def get_paths() -> dict[str, Path]:
    """Every path constant of this module, by name."""
    return {name: value for name, value in globals().items() if name.isupper()}
