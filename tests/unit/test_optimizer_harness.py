"""The harness of the optimizer (core/main.py) finds the repository from its own location, so the
IWO reads and writes the Modules folder of the copy it runs from."""

import importlib
from pathlib import Path

import pytest

from tests.unit.case_study import REPO_ROOT

pytestmark = [pytest.mark.engine, pytest.mark.optimizer]


def test_base_dir_is_the_repository_root():
    main = importlib.import_module("core.main")
    assert Path(main.base_dir) == REPO_ROOT
    assert Path(main.modules_dir) == REPO_ROOT / "Modules"
