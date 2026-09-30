"""
Author: Noah Masegosa Caceres
Center: @ugr

Objective: Fair benchmark by complexity for Planner-Executor vs Vanilla LLM.

Protocol:
1. Load identical dataset rows from JSONL.
2. Run both approaches with strict parity (same retry/backoff/throttle policy).
3. Primary metric: exact JSON match against ground truth.
4. Keep excision metrics (micro/key/value F1 + safety tax) as diagnostics.
5. Aggregate metrics by complexity (activities * tasks_per_activity).
"""

import argparse
import contextlib
import io
import json
import os
import random
import sys
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Tuple

from pathlib import Path
from tqdm import tqdm

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    def load_dotenv() -> None:
        return

try:
    from langchain_core.messages import HumanMessage
except ModuleNotFoundError:
    class HumanMessage:
        def __init__(self, content: str):
            self.content = content

# benchmarks/comparisons/benchmark_compare_complexity.py -> repo root is 3 levels up
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
    
from input_agent.nodes import node_executor, node_planner
from input_agent.src.llm import REQUEST_PROFILES, LLMService, capture_raw_responses
from input_agent.src.PetriNetConfig import PetriConfigEngine
from input_agent.src.models import Colors
from benchmarks.metrics import (
    compare_json_exact,
    calculate_excision_micro_f1,
    _zero_token_usage,
    _merge_token_usage
)
from benchmarks.comparisons.sample_overrides import (
    apply_instruction_overrides,
    load_instruction_overrides,
    load_sample_ids,
    restrict_to_sample_ids,
)
from benchmarks.comparisons.traceability import (
    BenchmarkRunManifest,
    build_default_output_paths,
    build_environment_metadata,
    derive_group_seed,
    fingerprint_dict,
    infer_seed_effective,
    manifest_to_json,
    new_run_id,
    sha256_file,
    utc_now_iso,
)

def resolve_path(path_value: str, kind: str) -> Path:
    """Resolve dataset/output paths from cwd or repository-standard locations."""
    candidate = Path(path_value)
    if candidate.is_absolute():
        return candidate

    candidates = [
        Path.cwd() / candidate,
        REPO_ROOT / candidate,
        REPO_ROOT / "benchmarks" / candidate,
    ]

    if kind == "dataset":
        candidates.append(REPO_ROOT / "benchmarks" / "datasets" / candidate)
    elif kind == "output":
        candidates.append(REPO_ROOT / "benchmarks" / "results" / candidate)

    for cand in candidates:
        if cand.exists():
            return cand.resolve()

    if kind == "output":
        # For outputs, return a sensible writable location even if file does not yet exist.
        return (Path.cwd() / candidate).resolve()

    raise FileNotFoundError(
        "Dataset not found. Tried:\n- "
        + "\n- ".join(str(c.resolve()) for c in candidates)
        + "\nAvailable datasets:\n- "
        + "\n- ".join(
            str(p.resolve())
            for p in sorted((REPO_ROOT / "benchmarks" / "datasets").glob("*.jsonl"))
        )
    )


def _infer_model_name(provider: str, model_name: Optional[str]) -> str:
    if model_name:
        return model_name
    if provider == "anthropic":
        return os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")
    if provider == "openai":
        return os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    return os.getenv("LLM_MODEL", "gpt-oss:20b")


def _resolve_provider(provider: Optional[str]) -> str:
    if provider and provider != "auto":
        return provider
    return (
        os.getenv("BENCHMARK_LLM_PROVIDER")
        or os.getenv("LLM_PROVIDER")
        or "openai_compatible"
    )


def _resolve_api_key(provider: str) -> Optional[str]:
    if provider == "anthropic":
        return os.getenv("ANTHROPIC_API_KEY") or os.getenv("LLM_API_KEY")
    if provider == "openai":
        return os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY")
    return (
        os.getenv("OPENAI_COMPATIBLE_API_KEY")
        or os.getenv("DEEPSEEK_API_KEY")
        or os.getenv("OLLAMA_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or os.getenv("LLM_API_KEY")
    )


def _configure_planner_executor_env(
    provider: str,
    model_name: str,
    llm_temperature: float,
    llm_seed: Optional[int],
    llm_timeout_s: float,
    llm_base_url: Optional[str],
) -> None:
    os.environ["BENCHMARK_LLM_PROVIDER"] = provider
    os.environ["LLM_PROVIDER"] = provider
    os.environ["BENCHMARK_LLM_MODEL"] = model_name
    os.environ["LLM_MODEL"] = model_name
    os.environ["BENCHMARK_LLM_TEMPERATURE"] = str(llm_temperature)
    os.environ["LLM_TEMPERATURE"] = str(llm_temperature)
    os.environ["BENCHMARK_LLM_TIMEOUT"] = str(llm_timeout_s)
    os.environ["LLM_TIMEOUT"] = str(llm_timeout_s)

    if llm_seed is None:
        os.environ.pop("BENCHMARK_LLM_SEED", None)
        os.environ.pop("LLM_SEED", None)
    else:
        os.environ["BENCHMARK_LLM_SEED"] = str(llm_seed)
        os.environ["LLM_SEED"] = str(llm_seed)

    if llm_base_url:
        os.environ["BENCHMARK_LLM_BASE_URL"] = llm_base_url
        os.environ["LLM_BASE_URL"] = llm_base_url
    else:
        os.environ.pop("BENCHMARK_LLM_BASE_URL", None)
        os.environ.pop("LLM_BASE_URL", None)


def _is_transient_error_text(text: str) -> bool:
    if not text:
        return False
    txt = text.lower()
    transient_markers = [
        "429",
        "rate limit",
        "timeout",
        "timed out",
        "connection",
        "refused",
        "unavailable",
        "temporarily",
        "reset by peer",
        "service unavailable",
    ]
    return any(marker in txt for marker in transient_markers)


def _build_vanilla_prompt(json_base: Dict[str, Any], instruction_natural: str) -> Tuple[str, str]:
    system_prompt = (
        "Eres un Agente Experto en Configuración de Simulación de Redes de Petri. "
        "Tu objetivo es aplicar las peticiones del usuario en lenguaje natural directamente en una configuración JSON, "
        "devolviendo el objeto JSON completo y actualizado.\n\n"
        "### CONTEXTO Y ESTRUCTURA DE DATOS\n"
        "El JSON representa una simulación de procesos de Redes de Petri.\n"
        "**A. AJUSTES GLOBALES (Nivel Raíz)**\n"
        "- `runId`, `Teams`, `Simulation_period`.\n"
        "**B. NIVEL DE ACTIVIDAD (Claves que empiezan por 'A', ej. 'A001')**\n"
        "- `Team`, `Team members`, `Shift_duration`, `T_period`, `T_wait`, `Start_disp`.\n"
        "- `Activity_Order_Enforced` (bool), `Activity_Order_Before` (lista de IDs de actividades).\n"
        "**C. NIVEL DE TAREA (Claves que empiezan por 'T', ej. 'T001' dentro de 'tasks')**\n"
        "- `Duration`, `Requires_Shutdown` (bool), `Cost_per_hour`, `Order_Enforced` (bool), `Order_Before` (lista de IDs de tareas).\n\n"
        "### REGLAS CRÍTICAS (LEER CON ATENCIÓN)\n"
        "1. **MINIMALISMO ESTRICTO (NO ALUCINAR)**: Al crear una nueva entidad, define ÚNICAMENTE los parámetros mencionados explícitamente por el usuario. NO inventes valores por defecto. Déjalos ausentes.\n"
        "2. **Conciencia de Unidades**: Todos los tiempos están en HORAS.\n"
        "3. **NORMALIZACIÓN DE IDs (OBLIGATORIO)**:\n"
        "   - Normaliza siempre las referencias a actividades/tareas a los IDs canónicos del esquema.\n"
        "   - Actividades: A001, A002, ... (ej. 'Actividad 3', 'A3', 'A-003' -> 'A003').\n"
        "   - Tareas: T001, T002, ... (ej. 'Tarea 1', 'T1', 'T-001' -> 'T001').\n"
        "4. **Nombres de Clave Exactos**: Usa las claves exactas (ej. 'Team members').\n"
        "5. **T_wait vs Start_disp (NO CONFUNDIR)**:\n"
        "   - 'wait/espera' mapea a `T_wait`.\n"
        "   - 'start delay/offset/desfase/inicio' mapea a `Start_disp`.\n"
        "   - Nunca intercambies T_wait y Start_disp.\n"
        "6. **Las Listas de Dependencias Siempre están Anidadas (CRÍTICO)**:\n"
        "   - Las dependencias de Actividad se guardan SOLO en: `Axxx.Activity_Order_Before`.\n"
        "   - Las dependencias de Tarea se guardan SOLO en: `Axxx.tasks.Txxx.Order_Before`.\n"
        "   - NUNCA crees ni modifiques `Activity_Order_Before` o `Order_Before` en el nivel raíz.\n"
        "7. **LA DIRECCIÓN DEL ORDEN ES SAGRADA (NO INVERTIR)**:\n"
        "   - Para frases como 'X antes que Y' / 'X vaya antes de Y' / 'X precede a Y':\n"
        "     - La lista de dependencias dentro de X debe contener a Y.\n"
        "   - Nunca los intercambies, aunque el grafo actual ya contenga dependencias relacionadas. Eres un traductor literal.\n"
        "8. **Comportamiento de Actualización de Dependencias**:\n"
        "   - Si se añade una dependencia, ANÉXALA (APPEND) a la lista existente (no sobrescribas los elementos actuales).\n"
        "   - Evita duplicados en las listas de dependencias.\n"
        "9. **Semántica de Eliminación**:\n"
        "   - Si el usuario pide borrar/eliminar un parámetro, elimina esa clave del objeto.\n"
        "   - Nunca establezcas campos eliminados como null/None/[] como sustituto de la eliminación.\n"
        "10. **Convención de Nombres para Nuevas Entidades (El Truco del Alfabeto)**:\n"
        "   - Si insertas una nueva Actividad o Tarea ENTRE existentes, genera un ID temporal derivado del ID de la entidad ANTERIOR + '_new' (ej. 'A002_new' entre A002 y A003).\n"
        "11. **Conexión de Dependencias**: Si insertas un elemento nuevo, asegúrate de actualizar las dependencias para que el nuevo elemento esté en el flujo (ej. si añades entre A y B, ahora B depende de A_new, y A_new depende de A).\n\n"
        "### REQUISITOS DE SALIDA\n"
        "1) Devuelve exactamente UN objeto JSON con la clave 'json_pred'.\n"
        "2) 'json_pred' debe contener la configuración completa (FULL) actualizada.\n"
        "3) Preserva todos los campos no modificados exactamente como estaban.\n"
        "4) Si la petición es imposible o ambigua, realiza el cambio más seguro y mínimo.\n"
        "5) No incluyas explicaciones, bloques de markdown (como ```json) ni claves extra fuera de 'json_pred'.\n"
    )

    user_prompt = (
        "Input JSON configuration:\n"
        f"{json.dumps(json_base, ensure_ascii=False)}\n\n"
        "User request:\n"
        f"{instruction_natural}\n\n"
        "Remember: Output strictly a valid JSON object starting with {\"json_pred\": ...}"
    )
    return system_prompt, user_prompt


def _extract_json_pred(response_obj: Dict[str, Any], json_base: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(response_obj, dict):
        return json_base

    # Expected wrapper shape.
    wrapped = response_obj.get("json_pred")
    if isinstance(wrapped, dict):
        return wrapped

    # Fallback: sometimes the model returns the full object directly.
    if "runId" in response_obj and "Teams" in response_obj:
        return response_obj

    return json_base


class ApproachThrottle:
    """Thread-safe throttle to keep a minimum interval between approach calls."""

    def __init__(self, min_interval_s: float):
        self.min_interval_s = min_interval_s
        self.last_call_ts = 0.0
        self._lock = threading.Lock()

    def wait_for_turn(self) -> None:
        with self._lock:
            now = time.time()
            wait_s = self.min_interval_s - (now - self.last_call_ts)
            if wait_s > 0:
                time.sleep(wait_s)
            self.last_call_ts = time.time()


def run_planner_executor_once(example: Dict[str, Any]) -> Dict[str, Any]:
    json_base = example["json_base"]
    instruction_natural = example["instruction_natural"]

    state = {
        "messages": [HumanMessage(content=instruction_natural)],
        "context_data": "",
        "correction_history": [],
        "current_config": json_base,
        "original_config": json_base,
        "retry_count": 0,
        "validation_errors": [],
        "execution_log": [],
        "proposed_plan": None,
        "skip_deterministic_validation": True,
        "token_usage": _zero_token_usage(),
    }

    with contextlib.redirect_stdout(io.StringIO()):
        planner_out = node_planner(state)
    state.update(planner_out)

    planner_plan = state.get("proposed_plan")

    with contextlib.redirect_stdout(io.StringIO()):
        executor_out = node_executor(state)
    state.update(executor_out)

    planner_error = ""
    if isinstance(state.get("proposed_plan"), dict):
        planner_error = str(state["proposed_plan"].get("error", ""))

    validation_errors = state.get("validation_errors", []) or []
    error_blob = " | ".join([planner_error] + [str(v) for v in validation_errors]).strip(" |")

    planner_instructions: List[Dict[str, Any]] = []
    if isinstance(planner_plan, dict):
        planner_instructions = planner_plan.get("instructions", []) or []

    return {
        "json_pred": state.get("current_config", json_base),
        "planner_instructions": planner_instructions,
        "validation_errors": validation_errors,
        "error_blob": error_blob,
        "token_usage": state.get("token_usage", _zero_token_usage()),
    }


def run_vanilla_once(example: Dict[str, Any], llm: LLMService) -> Dict[str, Any]:
    json_base = example["json_base"]
    instruction_natural = example["instruction_natural"]

    system_prompt, user_prompt = _build_vanilla_prompt(json_base, instruction_natural)
    response_obj, token_usage = llm.llm_with_usage(system_prompt, user_prompt)

    error_blob = ""
    if isinstance(response_obj, dict) and response_obj.get("error"):
        error_blob = str(response_obj.get("error"))

    json_pred = _extract_json_pred(response_obj, json_base)
    validation_errors: List[str] = []

    return {
        "json_pred": json_pred,
        "planner_instructions": [],
        "validation_errors": validation_errors,
        "error_blob": error_blob,
        "token_usage": token_usage,
    }


def run_with_retry(
    approach: str,
    example: Dict[str, Any],
    max_retries: int,
    backoff_base_s: float,
    jitter_s: float,
    throttle: Optional[ApproachThrottle],
    llm: Optional[LLMService] = None,
    log_raw_responses: bool = False,
) -> Dict[str, Any]:
    attempt = 0
    started_at = time.perf_counter()
    aggregated_usage = _zero_token_usage()
    raw_calls: List[Dict[str, Any]] = []
    while True:
        attempt += 1

        if throttle is not None:
            throttle.wait_for_turn()

        with capture_raw_responses() if log_raw_responses else contextlib.nullcontext() as records:
            if approach == "planner_executor":
                out = run_planner_executor_once(example)
            else:
                if llm is None:
                    raise ValueError("LLMService must be provided for vanilla approach")
                out = run_vanilla_once(example, llm)
        if log_raw_responses:
            raw_calls.extend({"attempt": attempt, **rec} for rec in records)

        aggregated_usage = _merge_token_usage(aggregated_usage, out.get("token_usage"))

        transient = _is_transient_error_text(out.get("error_blob", ""))
        if transient and attempt <= max_retries:
            sleep_backoff = backoff_base_s * (2 ** (attempt - 1)) + random.uniform(0, jitter_s)
            time.sleep(sleep_backoff)
            continue

        out["attempts"] = attempt
        out["latency_s"] = time.perf_counter() - started_at
        out["token_usage"] = aggregated_usage
        if log_raw_responses:
            out["raw_calls"] = raw_calls
        return out


def _score_json_base(example: Dict[str, Any], legacy_structural_keys: bool = False) -> Dict[str, Any]:
    """Excision metrics for a call without a usable configuration, scored as json_base."""
    if legacy_structural_keys:
        # Pre-correction runs logged hard-coded zeros for these calls.
        return {
            "f1_micro": 0.0, "f1_keys": 0.0, "f1_values": 0.0,
            "collateral_damage": 0, "omissions": 0,
            "collateral_rate": 0.0, "omission_rate": 0.0,
        }
    json_base = example["json_base"]
    delta_gt = PetriConfigEngine(json_base).compute_delta(example["json_gt"])
    delta_pred = PetriConfigEngine(json_base).compute_delta(json_base)
    excision = calculate_excision_micro_f1(delta_gt, delta_pred)
    gt_key_count = int(excision["gt_key_count"])
    pred_key_count = int(excision["pred_key_count"])
    omissions = int(excision["omissions"])
    collateral_damage = int(excision["collateral_damage"])
    return {
        "f1_micro": round(float(excision["f1_micro"]), 6),
        "f1_keys": round(float(excision["f1_keys"]), 6),
        "f1_values": round(float(excision["f1_values"]), 6),
        "collateral_damage": collateral_damage,
        "omissions": omissions,
        "collateral_rate": round(collateral_damage / pred_key_count if pred_key_count else 0.0, 6),
        "omission_rate": round(omissions / gt_key_count if gt_key_count else 0.0, 6),
    }


def process_sample(
    sample_idx: int,
    example: Dict[str, Any],
    complexity: int,
    current_approach: str,
    max_retries: int,
    backoff_base_s: float,
    jitter_s: float,
    throttle: Optional[ApproachThrottle],
    llm_vanilla: Optional[LLMService],
    run_llm_metadata: Dict[str, Any],
    sample_timeout_s: float = 120.0,
    legacy_structural_keys: bool = False,
    log_raw_responses: bool = False,
) -> Dict[str, Any]:
    json_base = example["json_base"]
    json_gt = example["json_gt"]
    instruction_technical = example["instruction_technical"]

    start_time = time.perf_counter()
    raw_calls = None
    try:
        out = run_with_retry(
            approach=current_approach,
            example=example,
            max_retries=max_retries,
            backoff_base_s=backoff_base_s,
            jitter_s=jitter_s,
            throttle=throttle,
            llm=llm_vanilla,
            log_raw_responses=log_raw_responses,
        )
        raw_calls = out.get("raw_calls")
        # Firewall: check if sample processing exceeded timeout
        elapsed = time.perf_counter() - start_time
        if elapsed > sample_timeout_s:
            raise TimeoutError(
                f"Sample {sample_idx} exceeded timeout ({elapsed:.1f}s > {sample_timeout_s:.1f}s). "
                f"Approach: {current_approach}, Complexity: {complexity}"
            )

        json_pred = out["json_pred"]

        engine_gt = PetriConfigEngine(json_base)
        delta_gt = engine_gt.compute_delta(json_gt)

        engine_pred = PetriConfigEngine(json_base)
        delta_pred = engine_pred.compute_delta(json_pred)

        excision = calculate_excision_micro_f1(
            delta_gt, delta_pred, legacy_structural_keys=legacy_structural_keys
        )
        json_exact_ok = compare_json_exact(json_gt, json_pred)
        gt_key_count = int(excision.get("gt_key_count", 0))
        pred_key_count = int(excision.get("pred_key_count", 0))
        omissions = int(excision["omissions"])
        collateral_damage = int(excision["collateral_damage"])
        omission_rate = (omissions / gt_key_count) if gt_key_count > 0 else 0.0
        collateral_rate = (collateral_damage / pred_key_count) if pred_key_count > 0 else 0.0

        sample_accuracy = float(json_exact_ok)

        detailed_result = {
            "sample_idx": sample_idx,
            "approach": current_approach,
            "complexity": complexity,
            "provider": run_llm_metadata.get("provider"),
            "llm_mode": run_llm_metadata.get("llm_mode"),
            "model_name": run_llm_metadata.get("model_name"),
            "model_version": run_llm_metadata.get("model_version"),
            "seed": run_llm_metadata.get("seed"),
            "seed_effective": run_llm_metadata.get("seed_effective"),
            "temperature": run_llm_metadata.get("temperature"),
            "activities": example["activities_count"],
            "tasks_per_activity": example["tasks_per_act_count"],
            "instruction_natural": example["instruction_natural"],
            "instruction_technical": instruction_technical,
            "planner_instructions": out["planner_instructions"],
            "exact_match": float(json_exact_ok),
            "f1_micro": round(float(excision["f1_micro"]), 6),
            "f1_keys": round(float(excision["f1_keys"]), 6),
            "f1_values": round(float(excision["f1_values"]), 6),
            "collateral_damage": collateral_damage,
            "omissions": omissions,
            "collateral_rate": round(collateral_rate, 6),
            "omission_rate": round(omission_rate, 6),
            "exact_match_score": sample_accuracy,
            "attempts": out["attempts"],
            "latency_s": round(float(out.get("latency_s", 0.0)), 6),
            "token_usage": out.get("token_usage", _zero_token_usage()),
            "error_blob": out.get("error_blob", ""),
        }
        if log_raw_responses:
            detailed_result["raw_calls"] = raw_calls

        failed_case = None
        if not json_exact_ok:
            failed_case = {
                "sample_idx": sample_idx,
                "approach": current_approach,
                "complexity": complexity,
                "provider": run_llm_metadata.get("provider"),
                "llm_mode": run_llm_metadata.get("llm_mode"),
                "model_name": run_llm_metadata.get("model_name"),
                "model_version": run_llm_metadata.get("model_version"),
                "seed": run_llm_metadata.get("seed"),
                "seed_effective": run_llm_metadata.get("seed_effective"),
                "temperature": run_llm_metadata.get("temperature"),
                "instruction_natural": example["instruction_natural"],
                "instruction_technical": instruction_technical,
                "planner_instructions": out["planner_instructions"],
                "exact_match": float(json_exact_ok),
                "f1_micro": round(float(excision["f1_micro"]), 6),
                "f1_keys": round(float(excision["f1_keys"]), 6),
                "f1_values": round(float(excision["f1_values"]), 6),
                "collateral_damage": collateral_damage,
                "omissions": omissions,
                "collateral_rate": round(collateral_rate, 6),
                "omission_rate": round(omission_rate, 6),
                "exact_match_score": sample_accuracy,
                "json_base": json_base,
                "json_gt": json_gt,
                "json_pred": json_pred,
                "delta_gt": delta_gt,
                "delta_pred": delta_pred,
                "latency_s": round(float(out.get("latency_s", 0.0)), 6),
                "token_usage": out.get("token_usage", _zero_token_usage()),
                "attempts": out["attempts"],
                "error_blob": out.get("error_blob", ""),
            }

        return {
            "approach": current_approach,
            "json_exact_success": 1 if json_exact_ok else 0,
            "f1_micro": float(excision["f1_micro"]),
            "f1_keys": float(excision["f1_keys"]),
            "f1_values": float(excision["f1_values"]),
            "collateral_damage": collateral_damage,
            "omissions": omissions,
            "collateral_rate": collateral_rate,
            "omission_rate": omission_rate,
            "latency_s": float(out.get("latency_s", 0.0)),
            "total_tokens": int((out.get("token_usage") or {}).get("total", 0)),
            "attempts": out["attempts"],
            "failures": 0 if json_exact_ok else 1,
            "detailed_result": detailed_result,
            "failed_case": failed_case,
        }

    except Exception as e:
        is_timeout = isinstance(e, TimeoutError)
        error_msg = str(e)
        if is_timeout:
            error_msg = f"[FIREWALL TIMEOUT] {error_msg}"
        # No usable configuration: scored as json_base, as rescore_results.py does
        # for logged runs.
        no_config = _score_json_base(example, legacy_structural_keys)
        
        failed_result = {
            "sample_idx": sample_idx,
            "approach": current_approach,
            "complexity": complexity,
            "provider": run_llm_metadata.get("provider"),
            "llm_mode": run_llm_metadata.get("llm_mode"),
            "model_name": run_llm_metadata.get("model_name"),
            "model_version": run_llm_metadata.get("model_version"),
            "seed": run_llm_metadata.get("seed"),
            "seed_effective": run_llm_metadata.get("seed_effective"),
            "temperature": run_llm_metadata.get("temperature"),
            "activities": example.get("activities_count", 0),
            "tasks_per_activity": example.get("tasks_per_act_count", 0),
            "instruction_natural": example.get("instruction_natural", ""),
            "instruction_technical": example.get("instruction_technical"),
            "planner_instructions": [],
            "exact_match": 0.0,
            **no_config,
            "exact_match_score": 0.0,
            "attempts": 1,
            "latency_s": 0.0,
            "token_usage": _zero_token_usage(),
            "error_msg": error_msg,
            "is_timeout": is_timeout,
        }
        if log_raw_responses:
            failed_result["raw_calls"] = raw_calls
        failed_case = {
            "sample_idx": sample_idx,
            "approach": current_approach,
            "complexity": complexity,
            "provider": run_llm_metadata.get("provider"),
            "llm_mode": run_llm_metadata.get("llm_mode"),
            "model_name": run_llm_metadata.get("model_name"),
            "model_version": run_llm_metadata.get("model_version"),
            "seed": run_llm_metadata.get("seed"),
            "seed_effective": run_llm_metadata.get("seed_effective"),
            "temperature": run_llm_metadata.get("temperature"),
            "instruction_natural": example.get("instruction_natural", ""),
            "instruction_technical": example.get("instruction_technical"),
            "planner_instructions": [],
            "exact_match": 0.0,
            **no_config,
            "exact_match_score": 0.0,
            "attempts": 1,
            "latency_s": 0.0,
            "token_usage": _zero_token_usage(),
            "error_msg": error_msg,
            "is_timeout": is_timeout,
        }

        return {
            "approach": current_approach,
            "json_exact_success": 0,
            **no_config,
            "latency_s": 0.0,
            "total_tokens": 0,
            "attempts": 1,
            "failures": 1,
            "detailed_result": failed_result,
            "failed_case": failed_case,
            "is_timeout": is_timeout,
        }


def run_benchmark(
    dataset_path: str,
    output_path: Optional[str],
    max_samples: Optional[int],
    samples_per_complexity: Optional[int],
    complexity_filter: Optional[List[int]],
    min_interval_s: float,
    max_retries: int,
    backoff_base_s: float,
    jitter_s: float,
    approach: str,
    max_workers: int,
    llm_mode: Optional[str],
    llm_temperature: float,
    llm_seed: Optional[int],
    llm_timeout_s: float,
    llm_model_name: Optional[str],
    llm_model_version: Optional[str],
    llm_base_url: Optional[str],
    run_tag: Optional[str],
    master_seed: int,
    sample_timeout_s: float = 120.0,
    legacy_structural_keys: bool = False,
    sample_ids_path: Optional[str] = None,
    instruction_override_path: Optional[str] = None,
    log_raw_responses: bool = False,
    request_profile: Optional[str] = None,
) -> None:
    load_dotenv()
    random.seed(master_seed)

    llm_mode = _resolve_provider(llm_mode)

    dataset_file = resolve_path(dataset_path, kind="dataset")
    model_name = _infer_model_name(llm_mode, llm_model_name)
    provider_name = llm_mode

    if output_path:
        output_file = resolve_path(output_path, kind="output")
        output_file.parent.mkdir(parents=True, exist_ok=True)
        failures_file = output_file.with_name(f"{output_file.stem}_failures.jsonl")
        manifest_file = output_file.with_name(f"{output_file.stem}_manifest.json")
        model_slug = model_name.lower().replace("/", "_").replace(":", "_")
    else:
        output_file, failures_file, manifest_file, model_slug = build_default_output_paths(
            repo_root=REPO_ROOT,
            benchmark_axis="complexity",
            model_name=model_name,
            run_tag=run_tag,
        )

    _configure_planner_executor_env(
        provider=llm_mode,
        model_name=model_name,
        llm_temperature=llm_temperature,
        llm_seed=llm_seed,
        llm_timeout_s=llm_timeout_s,
        llm_base_url=llm_base_url,
    )
    # Opt-in earlier request format; unset, the current format is used whatever the environment says.
    if request_profile:
        os.environ["LLM_REQUEST_PROFILE"] = request_profile
    else:
        os.environ.pop("LLM_REQUEST_PROFILE", None)

    run_id = new_run_id()
    started_at_utc = utc_now_iso()
    started_at_perf = time.perf_counter()
    dataset_sha256 = sha256_file(dataset_file)

    selected_approaches = ["planner_executor", "vanilla"] if approach == "both" else [approach]

    run_llm_metadata = {
        "provider": provider_name,
        "llm_mode": llm_mode,
        "model_name": model_name,
        "model_version": llm_model_version,
        "base_url": llm_base_url,
        "temperature": llm_temperature,
        "seed": llm_seed,
        "seed_effective": infer_seed_effective(llm_mode, llm_seed),
        "timeout_s": llm_timeout_s,
    }

    print(f"\n{Colors.HEADER}=== FAIR BENCHMARK ({', '.join(selected_approaches)}) ==={Colors.RESET}")
    print(f"Run ID: {run_id}")
    print(f"Dataset: {dataset_file}")
    print(f"Dataset SHA-256: {dataset_sha256}")
    print(f"Output: {output_file}")
    print(f"Primary metric: json_exact_match")
    print(f"Model: {model_name} | version: {llm_model_version} | provider: {provider_name}")
    print(f"Throttle min interval: {min_interval_s:.2f}s")
    print(f"Retries: {max_retries} (base backoff {backoff_base_s:.2f}s)\n")
    print(f"Max workers per approach: {max_workers}")
    print(f"Sample timeout (FIREWALL): {sample_timeout_s:.1f}s - will skip hung samples and continue")
    if "vanilla" in selected_approaches:
        print(f"Vanilla LLM provider: {llm_mode} | temperature: {llm_temperature:.3f} | seed: {llm_seed}")
    if llm_mode != "openai" and llm_seed is not None:
        print(f"{Colors.YELLOW}Seed support is provider-dependent and may be ignored by backend.{Colors.RESET}")

    examples: List[Dict[str, Any]] = []
    with open(dataset_file, "r", encoding="utf-8") as f:
        for line in f:
            examples.append(json.loads(line))

    if max_samples is not None:
        examples = examples[:max_samples]

    grouped: Dict[int, List[Tuple[int, Dict[str, Any]]]] = defaultdict(list)
    for idx, ex in enumerate(examples):
        raw_level = ex.get("complexity_nodes", ex.get("complexity"))
        if raw_level is None:
            raise ValueError(f"Sample index {idx} missing 'complexity_nodes'/'complexity' field")
        grouped[int(raw_level)].append((idx, ex))

    # Opt-in options; each leaves the run untouched when unset.
    run_options: Dict[str, Any] = {}
    fingerprint_extras: Dict[str, Any] = {}
    if sample_ids_path:
        sample_ids_file = resolve_path(sample_ids_path, kind="dataset")
        grouped = restrict_to_sample_ids(grouped, load_sample_ids(sample_ids_file, axis="complexity"))
        run_options["sample_ids_file"] = {"path": str(sample_ids_file), "sha256": sha256_file(sample_ids_file)}
        fingerprint_extras["sample_ids_sha256"] = run_options["sample_ids_file"]["sha256"]
    if instruction_override_path:
        override_file = resolve_path(instruction_override_path, kind="dataset")
        grouped = apply_instruction_overrides(
            grouped,
            load_instruction_overrides(override_file, axis="complexity"),
            text_key="instruction_natural",
            technical_key="instruction_technical",
        )
        run_options["instruction_override_file"] = {"path": str(override_file), "sha256": sha256_file(override_file)}
        fingerprint_extras["instruction_override_sha256"] = run_options["instruction_override_file"]["sha256"]
    if request_profile:
        run_options["request_profile"] = request_profile
        fingerprint_extras["request_profile"] = request_profile

    if complexity_filter:
        requested_complexities = sorted(set(complexity_filter))
        selected_complexities = [n for n in requested_complexities if n in grouped]
        missing_complexities = [n for n in requested_complexities if n not in grouped]

        if missing_complexities:
            print(
                f"{Colors.YELLOW}Warning: requested complexity values not present in dataset: "
                f"{missing_complexities}{Colors.RESET}"
            )

        if not selected_complexities:
            raise ValueError(
                "None of the requested complexity values exist in the dataset. "
                f"Available values: {sorted(grouped.keys())}"
            )
    else:
        selected_complexities = sorted(grouped.keys())

    if samples_per_complexity is not None:
        if samples_per_complexity <= 0:
            raise ValueError("--samples-per-complexity must be greater than 0")

        for n in selected_complexities:
            current_group = grouped[n]
            if len(current_group) > samples_per_complexity:
                seeded_rng = random.Random(derive_group_seed(master_seed, "sampling", n))
                grouped[n] = seeded_rng.sample(current_group, samples_per_complexity)

    total_samples = sum(len(grouped[n]) for n in selected_complexities)
    group_seeds = {
        f"{appr}::{level}": derive_group_seed(master_seed, appr, level)
        for appr in selected_approaches
        for level in selected_complexities
    }
    config_fingerprint = fingerprint_dict(
        {
            "axis": "complexity",
            "dataset_sha256": dataset_sha256,
            "selected_approaches": selected_approaches,
            "selected_complexities": selected_complexities,
            "samples_per_complexity": samples_per_complexity,
            "llm": run_llm_metadata,
            "legacy_structural_keys": legacy_structural_keys,
            "fairness": {
                "min_interval_s": min_interval_s,
                "max_retries": max_retries,
                "backoff_base_s": backoff_base_s,
                "jitter_s": jitter_s,
                "max_workers": max_workers,
                "sample_timeout_s": sample_timeout_s,
                "master_seed": master_seed,
            },
            **fingerprint_extras,
        }
    )
    print(f"{Colors.GREEN}Selected complexity values: {selected_complexities}{Colors.RESET}")
    print(f"{Colors.GREEN}Loaded samples (selected): {total_samples}{Colors.RESET}\n")
    if samples_per_complexity is not None:
        print(
            f"{Colors.YELLOW}Random sampling enabled: up to {samples_per_complexity} samples per complexity.{Colors.RESET}\n"
        )

    max_workers = max(1, max_workers)
    llm_vanilla = None
    if "vanilla" in selected_approaches:
        api_key = _resolve_api_key(llm_mode)
        llm_vanilla = LLMService(
            mode=llm_mode,
            api_key=api_key,
            temperature=llm_temperature,
            seed=llm_seed,
            model=model_name,
            base_url=llm_base_url,
            timeout=llm_timeout_s,
        )

    approach_throttles = {name: ApproachThrottle(min_interval_s=min_interval_s) for name in selected_approaches}
    metrics_lock = threading.Lock()
    llm_runtime_metadata = llm_vanilla.get_runtime_metadata() if llm_vanilla is not None else {}

    per_approach_global = {
        name: {
            "json_exact_success": 0,
            "f1_micro_sum": 0.0,
            "f1_keys_sum": 0.0,
            "f1_values_sum": 0.0,
            "collateral_damage_sum": 0,
            "omissions_sum": 0,
            "collateral_rate_sum": 0.0,
            "omission_rate_sum": 0.0,
            "latency_sum": 0.0,
            "total_tokens_sum": 0,
            "attempts": 0,
            "failures": 0,
        }
        for name in selected_approaches
    }

    env_meta = build_environment_metadata()
    manifest = BenchmarkRunManifest(
        run_id=run_id,
        timestamp_utc=started_at_utc,
        benchmark_axis="complexity",
        run_tag=run_tag,
        dataset_path=str(dataset_file),
        dataset_sha256=dataset_sha256,
        output_path=str(output_file),
        provider=provider_name,
        llm_mode=llm_mode,
        model_name=model_name,
        model_version=llm_model_version,
        base_url=llm_base_url,
        temperature=llm_temperature,
        seed=llm_seed,
        seed_effective=infer_seed_effective(llm_mode, llm_seed),
        timeout_s=llm_timeout_s,
        approach=approach,
        selected_approaches=selected_approaches,
        max_samples=max_samples,
        samples_per_level=samples_per_complexity,
        selected_levels=selected_complexities,
        min_interval_s=min_interval_s,
        max_retries=max_retries,
        backoff_base_s=backoff_base_s,
        jitter_s=jitter_s,
        max_workers=max_workers,
        sample_timeout_s=sample_timeout_s,
        group_seeds=group_seeds,
        config_fingerprint_sha256=config_fingerprint,
        python_version=env_meta["python_version"],
        numpy_version=env_meta["numpy_version"],
        scipy_version=env_meta["scipy_version"],
        joblib_version=env_meta["joblib_version"],
        platform=env_meta["platform"],
        git_commit=env_meta["git_commit"],
    )

    summary_by_approach: Dict[str, Any] = {}

    results_by_complexity: Dict[int, Dict[str, Any]] = {}
    detailed_results: List[Dict[str, Any]] = []
    failed_cases: List[Dict[str, Any]] = []

    for complexity in selected_complexities:
        samples = grouped[complexity]
        print(f"{Colors.BOLD}Evaluating complexity N={complexity} ({len(samples)} samples){Colors.RESET}")

        complexity_stats = {
            name: {
                "json_exact_success": 0,
                "f1_micro_sum": 0.0,
                "f1_keys_sum": 0.0,
                "f1_values_sum": 0.0,
                "collateral_damage_sum": 0,
                "omissions_sum": 0,
                "collateral_rate_sum": 0.0,
                "omission_rate_sum": 0.0,
                "latency_sum": 0.0,
                "total_tokens_sum": 0,
                "attempts": 0,
                "failures": 0,
            }
            for name in selected_approaches
        }

        for current_approach in selected_approaches:
            future_to_sample = {}
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                for sample_idx, example in samples:
                    future = executor.submit(
                        process_sample,
                        sample_idx,
                        example,
                        complexity,
                        current_approach,
                        max_retries,
                        backoff_base_s,
                        jitter_s,
                        approach_throttles[current_approach],
                        llm_vanilla,
                        run_llm_metadata,
                        sample_timeout_s,
                        legacy_structural_keys,
                        log_raw_responses,
                    )
                    future_to_sample[future] = sample_idx

                progress_desc = f"N={complexity}:{current_approach}"
                for future in tqdm(as_completed(future_to_sample), total=len(future_to_sample), desc=progress_desc, leave=True, unit="sample"):
                    try:
                        result = future.result(timeout=sample_timeout_s + 10)
                    except TimeoutError:
                        sample_idx = future_to_sample[future]
                        print(f"\n{Colors.RED}[FIREWALL] Sample {sample_idx} exceeded outer timeout. Skipping and continuing...{Colors.RESET}")
                        with metrics_lock:
                            complexity_stats[current_approach]["failures"] += 1
                            per_approach_global[current_approach]["failures"] += 1
                        failed_cases.append({
                            "sample_idx": sample_idx,
                            "approach": current_approach,
                            "complexity": complexity,
                            "provider": run_llm_metadata.get("provider"),
                            "llm_mode": run_llm_metadata.get("llm_mode"),
                            "model_name": run_llm_metadata.get("model_name"),
                            "model_version": run_llm_metadata.get("model_version"),
                            "error_msg": f"[FIREWALL] Killed after {sample_timeout_s:.1f}s timeout",
                            "is_timeout": True,
                        })
                        continue
                    except Exception as e:
                        sample_idx = future_to_sample[future]
                        print(f"\n{Colors.RED}[ERROR] Sample {sample_idx} failed: {str(e)}{Colors.RESET}")
                        with metrics_lock:
                            complexity_stats[current_approach]["failures"] += 1
                            per_approach_global[current_approach]["failures"] += 1
                        failed_cases.append({
                            "sample_idx": sample_idx,
                            "approach": current_approach,
                            "complexity": complexity,
                            "provider": run_llm_metadata.get("provider"),
                            "llm_mode": run_llm_metadata.get("llm_mode"),
                            "model_name": run_llm_metadata.get("model_name"),
                            "model_version": run_llm_metadata.get("model_version"),
                            "error_msg": str(e),
                            "is_timeout": False,
                        })
                        continue
                    appr = result["approach"]

                    with metrics_lock:
                        complexity_stats[appr]["json_exact_success"] += result["json_exact_success"]
                        complexity_stats[appr]["f1_micro_sum"] += result.get("f1_micro", 0.0)
                        complexity_stats[appr]["f1_keys_sum"] += result.get("f1_keys", 0.0)
                        complexity_stats[appr]["f1_values_sum"] += result.get("f1_values", 0.0)
                        complexity_stats[appr]["collateral_damage_sum"] += result.get("collateral_damage", 0)
                        complexity_stats[appr]["omissions_sum"] += result.get("omissions", 0)
                        complexity_stats[appr]["collateral_rate_sum"] += result.get("collateral_rate", 0.0)
                        complexity_stats[appr]["omission_rate_sum"] += result.get("omission_rate", 0.0)
                        complexity_stats[appr]["latency_sum"] += result.get("latency_s", 0.0)
                        complexity_stats[appr]["total_tokens_sum"] += result.get("total_tokens", 0)
                        complexity_stats[appr]["attempts"] += result["attempts"]
                        complexity_stats[appr]["failures"] += result["failures"]

                        per_approach_global[appr]["json_exact_success"] += result["json_exact_success"]
                        per_approach_global[appr]["f1_micro_sum"] += result.get("f1_micro", 0.0)
                        per_approach_global[appr]["f1_keys_sum"] += result.get("f1_keys", 0.0)
                        per_approach_global[appr]["f1_values_sum"] += result.get("f1_values", 0.0)
                        per_approach_global[appr]["collateral_damage_sum"] += result.get("collateral_damage", 0)
                        per_approach_global[appr]["omissions_sum"] += result.get("omissions", 0)
                        per_approach_global[appr]["collateral_rate_sum"] += result.get("collateral_rate", 0.0)
                        per_approach_global[appr]["omission_rate_sum"] += result.get("omission_rate", 0.0)
                        per_approach_global[appr]["latency_sum"] += result.get("latency_s", 0.0)
                        per_approach_global[appr]["total_tokens_sum"] += result.get("total_tokens", 0)
                        per_approach_global[appr]["attempts"] += result["attempts"]
                        per_approach_global[appr]["failures"] += result["failures"]

                        detailed_results.append(result["detailed_result"])
                        if result["failed_case"] is not None:
                            failed_cases.append(result["failed_case"])

        results_by_complexity[complexity] = {}
        for current_approach in selected_approaches:
            samples_count = len(samples)
            stats = complexity_stats[current_approach]
            json_exact_acc = (stats["json_exact_success"] / samples_count) * 100 if samples_count else 0.0
            avg_f1_micro = (stats["f1_micro_sum"] / samples_count) if samples_count else 0.0
            avg_f1_keys = (stats["f1_keys_sum"] / samples_count) if samples_count else 0.0
            avg_f1_values = (stats["f1_values_sum"] / samples_count) if samples_count else 0.0
            avg_collateral_damage = (stats["collateral_damage_sum"] / samples_count) if samples_count else 0.0
            avg_omissions = (stats["omissions_sum"] / samples_count) if samples_count else 0.0
            avg_collateral_rate = (stats["collateral_rate_sum"] / samples_count) if samples_count else 0.0
            avg_omission_rate = (stats["omission_rate_sum"] / samples_count) if samples_count else 0.0
            avg_latency_s = (stats["latency_sum"] / samples_count) if samples_count else 0.0
            avg_total_tokens = (stats["total_tokens_sum"] / samples_count) if samples_count else 0.0
            avg_attempts = (stats["attempts"] / samples_count) if samples_count else 0.0

            results_by_complexity[complexity][current_approach] = {
                "total_samples": samples_count,
                "json_exact_successes": stats["json_exact_success"],
                "failures": stats["failures"],
                "exact_match_pct": round(json_exact_acc, 2),
                "excision_micro_f1_avg": round(avg_f1_micro, 4),
                "excision_key_f1_avg": round(avg_f1_keys, 4),
                "excision_value_f1_avg": round(avg_f1_values, 4),
                "collateral_damage_avg": round(avg_collateral_damage, 4),
                "omissions_avg": round(avg_omissions, 4),
                "collateral_rate_avg": round(avg_collateral_rate, 4),
                "omission_rate_avg": round(avg_omission_rate, 4),
                "avg_latency_s": round(avg_latency_s, 4),
                "avg_total_tokens": round(avg_total_tokens, 2),
                "avg_attempts": round(avg_attempts, 3),
            }

        complexity_line = []
        for current_approach in selected_approaches:
            acc = results_by_complexity[complexity][current_approach]["exact_match_pct"]
            complexity_line.append(f"{current_approach}={acc:.2f}%")
        print(f"{Colors.GREEN}N={complexity}: {' | '.join(complexity_line)}{Colors.RESET}\n")

        summary_by_approach = {}
        for current_approach in selected_approaches:
            stats = per_approach_global[current_approach]
            json_exact_acc = (stats["json_exact_success"] / total_samples) * 100 if total_samples else 0.0
            avg_f1_micro = (stats["f1_micro_sum"] / total_samples) if total_samples else 0.0
            avg_f1_keys = (stats["f1_keys_sum"] / total_samples) if total_samples else 0.0
            avg_f1_values = (stats["f1_values_sum"] / total_samples) if total_samples else 0.0
            avg_collateral_damage = (stats["collateral_damage_sum"] / total_samples) if total_samples else 0.0
            avg_omissions = (stats["omissions_sum"] / total_samples) if total_samples else 0.0
            avg_collateral_rate = (stats["collateral_rate_sum"] / total_samples) if total_samples else 0.0
            avg_omission_rate = (stats["omission_rate_sum"] / total_samples) if total_samples else 0.0
            avg_latency_s = (stats["latency_sum"] / total_samples) if total_samples else 0.0
            avg_total_tokens = (stats["total_tokens_sum"] / total_samples) if total_samples else 0.0
            avg_attempts = (stats["attempts"] / total_samples) if total_samples else 0.0

            summary_by_approach[current_approach] = {
                "total_samples": total_samples,
                "primary_metric": "json_exact_match",
                "exact_match_pct": round(json_exact_acc, 2),
                "json_exact_successes": stats["json_exact_success"],
                "excision_micro_f1_avg": round(avg_f1_micro, 4),
                "excision_key_f1_avg": round(avg_f1_keys, 4),
                "excision_value_f1_avg": round(avg_f1_values, 4),
                "collateral_damage_avg": round(avg_collateral_damage, 4),
                "omissions_avg": round(avg_omissions, 4),
                "collateral_rate_avg": round(avg_collateral_rate, 4),
                "omission_rate_avg": round(avg_omission_rate, 4),
                "avg_latency_s": round(avg_latency_s, 4),
                "avg_total_tokens": round(avg_total_tokens, 2),
                "total_failures": stats["failures"],
                "avg_attempts": round(avg_attempts, 3),
            }

        # Save partial results after each complexity level
        partial_output = {
            "summary": {
                "run_id": run_id,
                "timestamp_utc": started_at_utc,
                "dataset_path": dataset_path,
                "dataset_sha256": dataset_sha256,
                "mode": "fair_compare",
                "approach": approach,
                "axis": "complexity",
                "selected_approaches": selected_approaches,
                "selected_complexities": selected_complexities,
                "samples_per_complexity": samples_per_complexity,
                "total_samples": total_samples,
                "primary_metric": "json_exact_match",
                "model": run_llm_metadata,
                "master_seed": master_seed,
                "legacy_structural_keys": legacy_structural_keys,
                "config_fingerprint_sha256": config_fingerprint,
                **run_options,
                "fairness": {
                    "shared_throttle": min_interval_s,
                    "shared_max_retries": max_retries,
                    "shared_backoff_base_s": backoff_base_s,
                    "shared_jitter_s": jitter_s,
                    "max_workers_per_approach": max_workers,
                },
                "approaches": summary_by_approach,
                "status": f"Processing - Completed complexity N={complexity}",
            },
            "by_complexity": results_by_complexity,
            "detailed_results": detailed_results,
            "failed_cases": failed_cases,
            "manifest_path": str(manifest_file),
        }
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(partial_output, f, indent=2, ensure_ascii=False)

        manifest.status = f"processing_complexity_{complexity}"
        manifest.elapsed_s = round(time.perf_counter() - started_at_perf, 3)
        with open(manifest_file, "w", encoding="utf-8") as mf:
            json.dump(manifest_to_json(manifest), mf, indent=2, ensure_ascii=False)
        print(f"{Colors.YELLOW}[Checkpoint] Partial results saved to: {output_file}{Colors.RESET}")

    summary_by_approach = {}
    for current_approach in selected_approaches:
        stats = per_approach_global[current_approach]
        json_exact_acc = (stats["json_exact_success"] / total_samples) * 100 if total_samples else 0.0
        avg_f1_micro = (stats["f1_micro_sum"] / total_samples) if total_samples else 0.0
        avg_f1_keys = (stats["f1_keys_sum"] / total_samples) if total_samples else 0.0
        avg_f1_values = (stats["f1_values_sum"] / total_samples) if total_samples else 0.0
        avg_collateral_damage = (stats["collateral_damage_sum"] / total_samples) if total_samples else 0.0
        avg_omissions = (stats["omissions_sum"] / total_samples) if total_samples else 0.0
        avg_collateral_rate = (stats["collateral_rate_sum"] / total_samples) if total_samples else 0.0
        avg_omission_rate = (stats["omission_rate_sum"] / total_samples) if total_samples else 0.0
        avg_latency_s = (stats["latency_sum"] / total_samples) if total_samples else 0.0
        avg_total_tokens = (stats["total_tokens_sum"] / total_samples) if total_samples else 0.0
        avg_attempts = (stats["attempts"] / total_samples) if total_samples else 0.0

        summary_by_approach[current_approach] = {
            "total_samples": total_samples,
            "primary_metric": "json_exact_match",
            "exact_match_pct": round(json_exact_acc, 2),
            "json_exact_successes": stats["json_exact_success"],
            "excision_micro_f1_avg": round(avg_f1_micro, 4),
            "excision_key_f1_avg": round(avg_f1_keys, 4),
            "excision_value_f1_avg": round(avg_f1_values, 4),
            "collateral_damage_avg": round(avg_collateral_damage, 4),
            "omissions_avg": round(avg_omissions, 4),
            "collateral_rate_avg": round(avg_collateral_rate, 4),
            "omission_rate_avg": round(avg_omission_rate, 4),
            "avg_latency_s": round(avg_latency_s, 4),
            "avg_total_tokens": round(avg_total_tokens, 2),
            "total_failures": stats["failures"],
            "avg_attempts": round(avg_attempts, 3),
        }

    llm_runtime_metadata = llm_vanilla.get_runtime_metadata() if llm_vanilla is not None else {}

    output_data = {
        "summary": {
            "run_id": run_id,
            "timestamp_utc": started_at_utc,
            "dataset_path": dataset_path,
            "dataset_sha256": dataset_sha256,
            "mode": "fair_compare",
            "approach": approach,
            "axis": "complexity",
            "selected_approaches": selected_approaches,
            "selected_complexities": selected_complexities,
            "samples_per_complexity": samples_per_complexity,
            "total_samples": total_samples,
            "primary_metric": "json_exact_match",
            "model": run_llm_metadata,
            "master_seed": master_seed,
            "config_fingerprint_sha256": config_fingerprint,
            **run_options,
            "fairness": {
                "shared_throttle": min_interval_s,
                "shared_max_retries": max_retries,
                "shared_backoff_base_s": backoff_base_s,
                "shared_jitter_s": jitter_s,
                "max_workers_per_approach": max_workers,
            },
            "approaches": summary_by_approach,
            "llm": {
                "provider": provider_name,
                "model_name": model_name,
                "model_version": llm_model_version,
                "base_url": llm_base_url,
                "temperature": llm_temperature,
                "seed": llm_seed,
                "seed_effective": infer_seed_effective(llm_mode, llm_seed),
                "runtime": llm_runtime_metadata,
            },
            "manifest_path": str(manifest_file),
            "status": "completed",
        },
        "by_complexity": results_by_complexity,
        "detailed_results": detailed_results,
        "failed_cases": failed_cases,
        "manifest_path": str(manifest_file),
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    if failed_cases:
        with open(failures_file, "w", encoding="utf-8") as f:
            for failure in failed_cases:
                f.write(json.dumps(failure, ensure_ascii=False) + "\n")
        print(f"\n{Colors.YELLOW}Saved {len(failed_cases)} failed cases to: {failures_file}{Colors.RESET}")

    manifest.status = "completed"
    manifest.elapsed_s = round(time.perf_counter() - started_at_perf, 3)
    with open(manifest_file, "w", encoding="utf-8") as mf:
        json.dump(manifest_to_json(manifest), mf, indent=2, ensure_ascii=False)

    print(f"\n{Colors.HEADER}=== FINAL RESULTS ==={Colors.RESET}")
    for current_approach in selected_approaches:
        entry = summary_by_approach[current_approach]
        print(
            f"{current_approach}: exact_match_pct={entry['exact_match_pct']:.2f}%"
            f" | excision_micro_f1_avg={entry['excision_micro_f1_avg']:.4f}"
            f" | latency_s={entry['avg_latency_s']:.4f}"
            f" | avg_total_tokens={entry['avg_total_tokens']:.2f}"
            f" | failures={entry['total_failures']}"
            f" | avg_attempts={entry['avg_attempts']:.3f}"
        )
    print(f"Saved results: {output_file}")
    print(f"Saved manifest: {manifest_file}")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fair complexity benchmark: planner-executor vs vanilla LLM")
    parser.add_argument("--dataset", default="benchmarks/datasets/benchmark_dataset_1_150.jsonl", help="Path to dataset JSONL")
    parser.add_argument("--output", default=None, help="Path to output results JSON. If omitted, uses model-scoped default path.")
    parser.add_argument("--max-samples", type=int, default=None, help="Limit number of samples")
    parser.add_argument(
        "--samples-per-complexity",
        type=int,
        default=None,
        help="Randomly select up to N samples per complexity. If omitted, use all samples.",
    )
    parser.add_argument("--complexity", type=int, nargs="+", default=None, help="Only run specific complexity N values (e.g. --complexity 7 or --complexity 7 10). If omitted, run all.")
    parser.add_argument("--min-interval", type=float, default=0.35, help="Minimum seconds between LLM calls")
    parser.add_argument("--max-retries", type=int, default=2, help="Retries on transient server/LLM errors")
    parser.add_argument("--backoff-base", type=float, default=0.8, help="Exponential backoff base seconds")
    parser.add_argument("--jitter", type=float, default=0.2, help="Random jitter seconds for retry backoff")
    parser.add_argument("--max-workers", type=int, default=4, help="Parallel workers per approach")
    parser.add_argument("--provider", "--llm-mode", dest="llm_mode", choices=["auto", "openai", "openai_compatible", "anthropic"], default="auto", help="LLM provider API (auto uses BENCHMARK_LLM_PROVIDER/LLM_PROVIDER)")
    parser.add_argument("--llm-model", default=None, help="Exact model name for both planner/executor and vanilla runs")
    parser.add_argument("--llm-model-version", default=None, help="Optional model version label for traceability")
    parser.add_argument("--llm-base-url", default=None, help="Optional base URL override for server mode")
    parser.add_argument("--llm-temperature", type=float, default=0.0, help="Vanilla LLM temperature")
    parser.add_argument("--llm-seed", type=int, default=None, help="Vanilla LLM seed for reproducibility")
    parser.add_argument("--llm-timeout", type=float, default=600.0, help="Per-request timeout (seconds) for vanilla LLM calls")
    parser.add_argument("--run-tag", default=None, help="Optional label appended to model-scoped output filenames")
    parser.add_argument("--master-seed", type=int, default=42, help="Master seed for deterministic sampling and group seeds")
    parser.add_argument(
        "--approach",
        choices=["planner_executor", "vanilla", "both"],
        default="both",
        help="Which approach to benchmark",
    )
    parser.add_argument(
        "--sample-timeout",
        type=float,
        default=600.0,
        help="Timeout in seconds per sample. Exceeded samples are skipped (FIREWALL mechanism)",
    )
    parser.add_argument(
        "--legacy-structural-keys",
        action="store_true",
        help="Score with the pre-correction metric, where empty delta lists count as matched keys",
    )
    parser.add_argument(
        "--sample-ids",
        default=None,
        help="Only run the samples (dataset line indices) listed in this JSON file; see benchmarks/comparisons/sample_overrides.py",
    )
    parser.add_argument(
        "--instruction-override",
        default=None,
        help="Replace each sample's natural-language request with the text in this JSON/JSONL file; nothing else changes",
    )
    parser.add_argument(
        "--log-raw-responses",
        action="store_true",
        help="Log per call the finish reason and raw response text, plus the reasoning when the server returns it (logging only)",
    )
    parser.add_argument(
        "--request-profile",
        choices=sorted(REQUEST_PROFILES),
        default=None,
        help="Send openai_compatible requests in an earlier format (see REQUEST_PROFILES in input_agent/src/llm.py)",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> None:
    args = build_arg_parser().parse_args(argv)

    run_benchmark(
        dataset_path=args.dataset,
        output_path=args.output,
        max_samples=args.max_samples,
        samples_per_complexity=args.samples_per_complexity,
        complexity_filter=args.complexity,
        min_interval_s=args.min_interval,
        max_retries=args.max_retries,
        backoff_base_s=args.backoff_base,
        jitter_s=args.jitter,
        approach=args.approach,
        max_workers=args.max_workers,
        llm_mode=args.llm_mode,
        llm_temperature=args.llm_temperature,
        llm_seed=args.llm_seed,
        llm_timeout_s=args.llm_timeout,
        llm_model_name=args.llm_model,
        llm_model_version=args.llm_model_version,
        llm_base_url=args.llm_base_url,
        run_tag=args.run_tag,
        master_seed=args.master_seed,
        sample_timeout_s=args.sample_timeout,
        legacy_structural_keys=args.legacy_structural_keys,
        sample_ids_path=args.sample_ids,
        instruction_override_path=args.instruction_override,
        log_raw_responses=args.log_raw_responses,
        request_profile=args.request_profile,
    )


if __name__ == "__main__":
    main()