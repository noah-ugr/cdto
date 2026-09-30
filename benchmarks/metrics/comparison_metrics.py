"""Core benchmark metrics used by completeness and complexity comparisons.

Metric catalog:
- compare_json_exact:
  Strict exact match of final JSON state after numeric normalization. (Document-Level EM)

- calculate_excision_micro_f1:
  Implementation of the LLMStructBench Micro-averaged F1 (Eq 4-9) applied to Deltas.
  Includes partial credit for coercible types, fuzzy string matching (Levenshtein),
  and explicit extraction of Collateral Damage (Safety Tax).

Empty lists in a delta carry no content and are not flattened into keys.
``legacy_structural_keys=True`` restores the original behaviour, in which every
delta contained ``new_activities[]`` and ``deleted_activities[]`` and a
prediction identical to the base scored F1 4/(4+n) instead of 0.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from benchmarks.metrics.normalization import (
    canonicalize_unordered_list,
    normalize_value,
)


def compare_json_exact(json_gt: Dict[str, Any], json_pred: Dict[str, Any]) -> bool:
    """
    Document-Level JSON Exact Match.
    Strict final-state equality after numeric normalization.
    Since it uses Python dict equality, it correctly ignores key ordering.
    """
    return normalize_value(json_gt) == normalize_value(json_pred)


def _levenshtein_distance(s1: str, s2: str) -> int:
    """Calculates minimum edit distance between two strings."""
    if len(s1) < len(s2):
        return _levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    
    prev_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        curr_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = prev_row[j + 1] + 1
            deletions = curr_row[j] + 1
            substitutions = prev_row[j] + (c1 != c2)
            curr_row.append(min(insertions, deletions, substitutions))
        prev_row = curr_row
    return prev_row[-1]


def _flatten_to_dict(
    value: Any,
    path: str = "",
    legacy_structural_keys: bool = False,
) -> Dict[str, Any]:
    """
    Flattens a JSON structure into a dictionary of path -> raw normalized value.
    Unlike the previous version, this preserves raw types (int, bool) for
    coercibility checks required by LLMStructBench.
    Empty lists produce no key unless ``legacy_structural_keys`` is set.
    """
    normalized = normalize_value(value)
    result = {}

    if isinstance(normalized, dict):
        for key in sorted(normalized.keys()):
            child_path = f"{path}.{key}" if path else key
            result.update(_flatten_to_dict(normalized[key], child_path, legacy_structural_keys))
        return result

    if isinstance(normalized, list):
        # An empty list (e.g. an unused new_activities slot) must not count as
        # a matched key, or a do-nothing prediction earns partial credit.
        if not normalized and not legacy_structural_keys:
            return result
        # Canonicalize lists for deterministic comparison
        list_path = f"{path}[]" if path else "[]"
        result[list_path] = canonicalize_unordered_list(normalized)
        return result

    scalar_path = path or "$"
    result[scalar_path] = normalized
    return result


def calculate_excision_micro_f1(
    delta_gt: Dict[str, Any],
    delta_pred: Dict[str, Any],
    legacy_structural_keys: bool = False,
) -> Dict[str, float]:
    """
    Compute SOTA Micro-F1 over the isolated delta regions (Excision Score).
    Implements LLMStructBench Eq 4-9 with fuzzy credit and active penalties.
    ``legacy_structural_keys`` keeps empty lists as keys (pre-correction scoring).
    """
    # LLMStructBench Constants
    ALPHA = 0.25      # Key to Value weight
    BETA = 0.2        # Similarity gain for coercible mismatches
    GAMMA = 0.5       # Weight for approximate string matches
    L_GOOD = 0.1      # Threshold for near-perfect strings
    L_BAD = 2.0       # Threshold for hopelessly wrong strings
    P_BAD = -1.0      # Penalty for extreme hallucinations

    gt_items = _flatten_to_dict(delta_gt, legacy_structural_keys=legacy_structural_keys)
    pred_items = _flatten_to_dict(delta_pred, legacy_structural_keys=legacy_structural_keys)

    gt_keys = set(gt_items.keys())
    pred_keys = set(pred_items.keys())

    # If both Deltas are empty, the model perfectly executed a "do nothing" command
    if not gt_keys and not pred_keys:
        return {
            "f1_micro": 1.0,
            "f1_keys": 1.0,
            "f1_values": 1.0,
            "collateral_damage": 0,
            "omissions": 0,
            "gt_key_count": 0,
            "pred_key_count": 0,
        }

    # -----------------------------------------------------
    # 1. KEY COMPONENT (Eq 5, 6, 7)
    # -----------------------------------------------------
    tp_k = len(gt_keys.intersection(pred_keys))
    fp_k = len(pred_keys - gt_keys)  # Collateral Damage
    fn_k = len(gt_keys - pred_keys)  # Omissions

    p_keys = tp_k / (tp_k + fp_k) if (tp_k + fp_k) > 0 else 0.0
    r_keys = tp_k / (tp_k + fn_k) if (tp_k + fn_k) > 0 else 0.0
    f1_keys = (2 * p_keys * r_keys / (p_keys + r_keys)) if (p_keys + r_keys) > 0 else 0.0

    # -----------------------------------------------------
    # 2. VALUE COMPONENT (Eq 8, 9)
    # -----------------------------------------------------
    tp_v_credit = 0.0

    for k in gt_keys.intersection(pred_keys):
        v_gt = gt_items[k]
        v_pred = pred_items[k]

        if type(v_gt) == type(v_pred) and v_gt == v_pred:
            # Exact match
            tp_v_credit += 1.0
            
        elif str(v_gt).lower() == str(v_pred).lower():
            # Coercible mismatch (e.g., int 42 vs string "42")
            tp_v_credit += BETA
            
        elif isinstance(v_gt, str) and isinstance(v_pred, str):
            # Value deviation for strings
            dist = _levenshtein_distance(v_gt, v_pred)
            l_norm = dist / len(v_gt) if len(v_gt) > 0 else float('inf')
            
            if l_norm <= L_GOOD:
                tp_v_credit += 1.0
            elif L_GOOD < l_norm < L_BAD:
                tp_v_credit += GAMMA * (1.0 - l_norm)
            else:
                tp_v_credit += P_BAD # Active penalty for nonsensical strings
        else:
            # Hard type error or complete deviation (0 credit)
            tp_v_credit += 0.0

    # Ensure True Positives don't drop below 0 due to penalties
    tp_v = max(0.0, tp_v_credit)
    
    total_pred_values = len(pred_keys)
    total_gt_values = len(gt_keys)

    p_values = tp_v / total_pred_values if total_pred_values > 0 else 0.0
    r_values = tp_v / total_gt_values if total_gt_values > 0 else 0.0
    f1_values = (2 * p_values * r_values / (p_values + r_values)) if (p_values + r_values) > 0 else 0.0

    # -----------------------------------------------------
    # 3. MICRO-AVERAGED F1 (Eq 4)
    # -----------------------------------------------------
    f1_micro = (ALPHA * f1_keys) + ((1.0 - ALPHA) * f1_values)
    f1_micro = max(0.0, min(1.0, f1_micro)) # Bounded to [0, 1]

    return {
        "f1_micro": round(f1_micro, 6),
        "f1_keys": round(f1_keys, 6),
        "f1_values": round(f1_values, 6),
        "collateral_damage": fp_k,  # Extraneous keys not in GT
        "omissions": fn_k,          # Missing keys expected in GT
        "gt_key_count": len(gt_keys),
        "pred_key_count": len(pred_keys),
    }


def _zero_token_usage() -> Dict[str, int]:
    return {"prompt": 0, "completion": 0, "total": 0}


def _merge_token_usage(left: Optional[Dict[str, Any]], right: Optional[Dict[str, Any]]) -> Dict[str, int]:
    left = left or {}
    right = right or {}
    return {
        "prompt": int(left.get("prompt", 0)) + int(right.get("prompt", 0)),
        "completion": int(left.get("completion", 0)) + int(right.get("completion", 0)),
        "total": int(left.get("total", 0)) + int(right.get("total", 0)),
    }