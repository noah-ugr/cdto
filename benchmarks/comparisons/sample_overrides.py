"""
Sample restriction and request substitution for the benchmark runners.

Both are opt-in (``--sample-ids`` and ``--instruction-override``); without
them the runners select and present samples exactly as before.

A sample ID is the dataset line index the runners log as ``sample_idx``.

``--sample-ids`` file (JSON), as written by
``benchmarks/humanisation_check/select_samples.py``::

    {"samples": [{"axis": "complexity", "level": 16, "sample_idx": 812}, ...]}

A bare list of such records, or of integers, is also accepted. Records whose
``axis`` differs from the runner's axis are ignored; when ``level`` is given
it must match the dataset line.

``--instruction-override`` file (JSON list or JSONL), as written by
``benchmarks/humanisation_check/rehumanise.py``: one record per sample with
``sample_idx``, ``instruction_natural`` (the text that replaces the request)
and optionally ``axis`` and ``instruction_technical``. When the technical
instruction is given it must equal the dataset's, so a request cannot be
attached to the wrong sample. Only the request text changes; base
configuration, ground truth and technical instructions stay as in the
dataset.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

Grouped = Dict[int, List[Tuple[int, Dict[str, Any]]]]


def _read_records(path: str | Path, container_key: str) -> List[Any]:
    """Records of a JSON list, a JSON object holding them under ``container_key``, or JSONL."""
    text = Path(path).read_text(encoding="utf-8-sig")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    if isinstance(data, dict):
        return data[container_key] if container_key in data else [data]
    return data


def load_sample_ids(path: str | Path, axis: str) -> Dict[int, Optional[int]]:
    """Map each selected sample_idx of ``axis`` to its expected level (or None)."""
    records = _read_records(path, "samples")
    selected: Dict[int, Optional[int]] = {}
    for rec in records:
        if isinstance(rec, int):
            selected[rec] = None
            continue
        if rec.get("axis", axis) != axis:
            continue
        level = rec.get("level")
        selected[int(rec["sample_idx"])] = None if level is None else int(level)
    if not selected:
        raise ValueError(f"{path} lists no samples for axis '{axis}'")
    return selected


def restrict_to_sample_ids(grouped: Grouped, sample_ids: Dict[int, Optional[int]]) -> Grouped:
    """Keep only the listed samples, in dataset order; fail on unknown IDs or level mismatches."""
    restricted: Grouped = defaultdict(list)
    found: Dict[int, int] = {}
    for level, samples in grouped.items():
        for idx, ex in samples:
            if idx in sample_ids:
                restricted[level].append((idx, ex))
                found[idx] = level

    missing = sorted(set(sample_ids) - set(found))
    if missing:
        raise ValueError(f"sample IDs not in the dataset: {missing}")
    wrong_level = sorted(
        idx for idx, level in sample_ids.items() if level is not None and found[idx] != level
    )
    if wrong_level:
        raise ValueError(
            "sample IDs whose dataset level differs from the IDs file: "
            + ", ".join(f"{idx} (file {sample_ids[idx]}, dataset {found[idx]})" for idx in wrong_level)
        )
    return restricted


def load_instruction_overrides(path: str | Path, axis: str) -> Dict[int, Dict[str, Any]]:
    """Map sample_idx to its override record (``instruction_natural`` holds the new text)."""
    records = _read_records(path, "requests")
    overrides: Dict[int, Dict[str, Any]] = {}
    for rec in records:
        if rec.get("axis", axis) != axis:
            continue
        idx = int(rec["sample_idx"])
        if not isinstance(rec.get("instruction_natural"), str):
            raise ValueError(f"override for sample {idx} has no instruction_natural string")
        if idx in overrides:
            raise ValueError(f"duplicate override for sample {idx}")
        overrides[idx] = rec
    if not overrides:
        raise ValueError(f"{path} has no overrides for axis '{axis}'")
    return overrides


def override_example(
    example: Dict[str, Any],
    record: Dict[str, Any],
    text_key: str,
    technical_key: str,
) -> Dict[str, Any]:
    """Copy of ``example`` whose request text is the override's; nothing else changes."""
    expected = record.get("instruction_technical")
    if expected is not None and expected != example.get(technical_key):
        raise ValueError(
            f"override for sample {record['sample_idx']} does not match the dataset's technical instruction"
        )
    replaced = dict(example)
    replaced[text_key] = record["instruction_natural"]
    return replaced


def apply_instruction_overrides(
    grouped: Grouped,
    overrides: Dict[int, Dict[str, Any]],
    text_key: str,
    technical_key: str,
) -> Grouped:
    """Replace the request of every grouped sample; every sample needs an override."""
    missing = sorted(idx for samples in grouped.values() for idx, _ in samples if idx not in overrides)
    if missing:
        raise ValueError(
            f"no override for samples {missing}; restrict the run with --sample-ids"
        )
    return defaultdict(list, {
        level: [
            (idx, override_example(ex, overrides[idx], text_key, technical_key))
            for idx, ex in samples
        ]
        for level, samples in grouped.items()
    })
