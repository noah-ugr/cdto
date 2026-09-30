import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Third-party components that a release can leave out. A test marked with a group runs only when
# every file of the group is present, and is skipped with the reason otherwise.
THIRD_PARTY_GROUPS = {
    "engine": (
        "PetriNetModules/PetriNet_module.py",
        "Modules/monteCarloSimulator4.py",
        "core/pipeline.py",
        "config/models.py",
        "utils/mapping_utils.py",
        "utils/generator_utils.py",
    ),
    "optimizer": (
        "core/main.py",
        "optimizers/algorithms/iwo-new-single.py",
    ),
}


def group_available(group: str) -> bool:
    return all((REPO_ROOT / path).exists() for path in THIRD_PARTY_GROUPS[group])


def pytest_collection_modifyitems(config, items):
    missing = [group for group in THIRD_PARTY_GROUPS if not group_available(group)]
    for item in items:
        for group in missing:
            if group in item.keywords:
                item.add_marker(pytest.mark.skip(reason=f"{group} not included in this release"))
