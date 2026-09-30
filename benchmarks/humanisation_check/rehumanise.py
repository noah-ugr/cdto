"""
Re-humanise the selected requests with another model.

Calls the original humanisers unchanged -- ``humanize_instruction``
(complexity) and ``humanize_instruction_batch`` (completeness) from the
dataset generators, whose prompts have not changed since the datasets were
built -- on an ``LLMService`` with the generators' settings
(temperature 0.7, seed None, 4 requests in parallel) and the request format
of March 2026, when both datasets were humanised (request profile
``2026-03-humaniser``: system prompt without the later JSON suffix, JSON
response format, no max_tokens, no extra_body, response parsed with
``json.loads`` alone). Only the model and the server URL change. The
returned text is the generators' own post-processing
(``response.get("natural_query", "")``), stored as is.

Per request it also keeps the exact prompts (hashes and user turn), the raw
response, the request parameters sent and a format check:
- no reasoning (no reasoning field from the server, no <think> or harmony
  channel markers in the content);
- the raw content is a bare JSON object with the single key
  ``natural_query``, non-empty, which the original ``json.loads``
  post-processing accepts as it is;
- finish reason ``stop``.

Writes ``<run-dir>/requests_<model>.jsonl`` (original and new request per
sample; usable as ``--instruction-override``) and ``requests_<model>.meta.json``.
The dataset is never written.

    python -m benchmarks.humanisation_check.rehumanise --run-dir <run-dir> \
        --model qwen2.5:32b --base-url http://localhost:<PORT>/v1
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    def load_dotenv() -> None:
        return

from benchmarks.comparisons.traceability import normalize_model_slug
from benchmarks.humanisation_check import ollama_api
from benchmarks.humanisation_check.common import (
    AXES,
    SAMPLE_IDS_FILE,
    file_ref,
    git_state,
    load_dataset,
    resolve_run_dir,
    selected_samples,
    write_json,
)
from input_agent.src.dataset_generator_complexity import humanize_instruction
from input_agent.src.dataset_generator_completeness import humanize_instruction_batch
from input_agent.src.llm import REQUEST_PROFILES, LLMService, capture_raw_responses
from input_agent.src.models import Instruction


HUMANISER_TEMPERATURE = 0.7   # LLMService(temperature=0.7) in both dataset generators
HUMANISER_PARALLEL = 4        # max_parallel_llm default in both dataset generators
HUMANISER_PROFILE = "2026-03-humaniser"
REASONING_MARKERS = ("<think>", "</think>", "<|channel|>", "<|start|>", "<|message|>", "<reasoning>")


class RecordingLLM:
    """Passes the humaniser's single call through unchanged, keeping prompts and raw response."""

    def __init__(self, llm: LLMService):
        self._llm = llm
        self.system_prompt: Optional[str] = None
        self.user_prompt: Optional[str] = None
        self.raw: Optional[dict] = None

    def llm(self, system_prompt: str, user_query: str) -> dict:
        self.system_prompt, self.user_prompt = system_prompt, user_query
        with capture_raw_responses() as records:
            response = self._llm.llm(system_prompt, user_query)
        self.raw = records[-1] if records else None
        return response


def humanise(axis: str, row: dict, llm: LLMService) -> tuple[str, RecordingLLM]:
    """Run the original humaniser of ``axis`` on a dataset row."""
    recorder = RecordingLLM(llm)
    if axis == "complexity":
        text = humanize_instruction(Instruction(**row["instruction_technical"]), row["json_base"], recorder)
    else:
        instructions = [Instruction(**d) for d in row["instructions_technical"]]
        text = humanize_instruction_batch(instructions, row["json_base"], recorder)
    return text, recorder


def _sha256(text: Optional[str]) -> Optional[str]:
    return None if text is None else hashlib.sha256(text.encode("utf-8")).hexdigest()


def format_check(raw: Optional[dict], returned: str) -> Dict[str, Any]:
    """Check that the output has no reasoning and passes the original post-processing untouched."""
    raw = raw or {}
    content = (raw.get("content") or "").strip()
    direct = None
    try:
        parsed = json.loads(content)
        direct = parsed if isinstance(parsed, dict) else None
    except Exception:
        pass
    if direct is not None:
        parse_path = "direct"
    else:
        try:
            LLMService._extract_json_object_from_text(content)
            parse_path = "fenced" if "```" in content else "embedded"
        except Exception:
            parse_path = "failed"

    natural_query = direct.get("natural_query") if direct else None
    check = {
        "finish_reason": raw.get("finish_reason"),
        "reasoning_field": raw.get("reasoning_field"),
        "reasoning_markers": [m for m in REASONING_MARKERS if m in content],
        "parse_path": parse_path,
        "keys": sorted(direct) if direct is not None else None,
        "natural_query_nonempty": isinstance(natural_query, str) and bool(natural_query.strip()),
        "postprocess_unchanged": isinstance(natural_query, str) and natural_query == returned,
        "error": raw.get("error"),
    }
    problems = []
    if check["finish_reason"] != "stop":
        problems.append(f"finish_reason={check['finish_reason']}")
    if check["reasoning_field"]:
        problems.append(f"reasoning returned in '{check['reasoning_field']}'")
    if check["reasoning_markers"]:
        problems.append("reasoning markers " + " ".join(check["reasoning_markers"]))
    if check["parse_path"] != "direct":
        problems.append(f"not a bare JSON object (parse path: {check['parse_path']})")
    elif check["keys"] != ["natural_query"]:
        problems.append(f"keys {check['keys']}")
    if not check["natural_query_nonempty"]:
        problems.append("empty natural_query")
    if not check["postprocess_unchanged"]:
        problems.append("post-processing does not return the raw natural_query")
    if check["error"]:
        problems.append(f"error: {check['error']}")
    check["problems"] = problems
    check["ok"] = not problems
    return check


def _process(axis: str, level: int, idx: int, row: dict, llm: LLMService, model: str) -> dict:
    started = time.perf_counter()
    text, recorder = humanise(axis, row, llm)
    return {
        "axis": axis,
        "level": level,
        "sample_idx": idx,
        "humanizer_model": model,
        "instruction_technical": row[AXES[axis].technical_key],
        "instruction_natural_original": row[AXES[axis].text_key],
        "instruction_natural": text,
        "latency_s": round(time.perf_counter() - started, 3),
        "prompts": {
            "system_sha256": _sha256(recorder.system_prompt),
            "user_sha256": _sha256(recorder.user_prompt),
            "user": recorder.user_prompt,
        },
        "raw": recorder.raw,
        "format_check": format_check(recorder.raw, text),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Re-humanise the selected requests with another model")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--model", required=True, help="Humaniser model, e.g. qwen2.5:32b (phi4:14b as fallback)")
    parser.add_argument("--base-url", required=True, help="OpenAI-compatible URL, e.g. http://localhost:<PORT>/v1")
    parser.add_argument("--max-parallel", type=int, default=HUMANISER_PARALLEL)
    parser.add_argument("--request-profile", choices=[*sorted(REQUEST_PROFILES), "current"], default=HUMANISER_PROFILE,
                        help="Request format; the default reproduces the one that humanised the datasets")
    parser.add_argument("--strict-format", action="store_true",
                        help="Exit with status 2 if any output fails the format check (use for the trial run)")
    parser.add_argument("--no-ollama-info", action="store_true", help="Skip the Ollama version/digest queries")
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_dir = resolve_run_dir(args.run_dir)
    slug = normalize_model_slug(args.model)
    out_path = run_dir / f"requests_{slug}.jsonl"
    meta_path = run_dir / f"requests_{slug}.meta.json"
    if out_path.exists() and not args.overwrite:
        raise SystemExit(f"{out_path} exists; pass --overwrite to replace it")

    load_dotenv()  # as the dataset generators do
    profile = None if args.request_profile == "current" else args.request_profile
    if profile is None:
        os.environ.pop("LLM_REQUEST_PROFILE", None)
    llm = LLMService(temperature=HUMANISER_TEMPERATURE, model=args.model, base_url=args.base_url,
                     request_profile=profile)

    samples = selected_samples(run_dir)
    datasets = {axis: load_dataset(axis) for axis in {s["axis"] for s in samples}}
    jobs = [(s["axis"], s["level"], s["sample_idx"], datasets[s["axis"]][s["sample_idx"]]) for s in samples]
    for axis, level, idx, row in jobs:
        if int(row[AXES[axis].level_field]) != level:
            raise SystemExit(f"{axis} sample {idx}: dataset level differs from {SAMPLE_IDS_FILE}")

    started_utc = datetime.now(timezone.utc).isoformat()
    started = time.perf_counter()
    print(f"Humanising {len(jobs)} requests with {args.model} ({args.max_parallel} in parallel)...")
    records: List[dict] = []
    partial = out_path.with_suffix(".partial.jsonl")
    with ThreadPoolExecutor(max_workers=max(1, args.max_parallel)) as pool, open(partial, "w", encoding="utf-8") as pf:
        futures = [pool.submit(_process, axis, level, idx, row, llm, args.model) for axis, level, idx, row in jobs]
        for n, future in enumerate(futures, 1):
            rec = future.result()
            records.append(rec)
            pf.write(json.dumps(rec, ensure_ascii=False) + "\n")
            pf.flush()
            fc = rec["format_check"]
            status = "format ok" if fc["ok"] else "FORMAT: " + "; ".join(fc["problems"])
            print(f"[{n}/{len(jobs)}] {rec['axis']} L{rec['level']} #{rec['sample_idx']} {rec['latency_s']:.1f}s {status}")

    with open(out_path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    partial.unlink(missing_ok=True)

    failed = [r for r in records if not r["format_check"]["ok"]]
    system_hashes = {}
    for r in records:
        system_hashes.setdefault(r["axis"], set()).add(r["prompts"]["system_sha256"])

    server = None
    if not args.no_ollama_info:
        server = ollama_api.server_summary(args.base_url, [args.model])

    write_json(meta_path, {
        "humanizer_model": args.model,
        "base_url": args.base_url,
        "ollama": server,
        "llm_settings": {
            "mode": llm.mode,
            "temperature": llm.temperature,
            "seed": llm.seed,
            "max_tokens": llm.max_tokens,
            "timeout": llm.timeout,
            "request_profile": llm.request_profile,
            "request_profile_spec": REQUEST_PROFILES.get(llm.request_profile),
            "extra_body_in_environment": llm.extra_body,
            "request_params_sent": sorted({
                json.dumps((r.get("raw") or {}).get("request", {}).get("params"), sort_keys=True) for r in records
            }),
            "max_parallel": args.max_parallel,
        },
        "original_humanizer": {
            "model": "gpt-oss:20b on Ollama (paper, Subsection 4.1; OLLAMA_MODEL default of LLMService at the time)",
            "code": {
                "complexity": "input_agent/src/dataset_generator_complexity.py::humanize_instruction "
                              "(dataset of 2026-03-23; prompt as committed in d523e8a, unchanged since)",
                "completeness": "input_agent/src/dataset_generator_completeness.py::humanize_instruction_batch "
                                "(dataset of 2026-03-24; prompt as committed in 865521e, unchanged since)",
            },
            "llm": "LLMService(api_key=os.getenv('GROQ_API'), temperature=0.7) with input_agent/src/llm.py at "
                   "12e3297/6e07a45: mode 'server' (Ollama), request profile 2026-03-humaniser",
            "max_parallel_llm": HUMANISER_PARALLEL,
        },
        "system_prompt_sha256": {axis: sorted(h) for axis, h in system_hashes.items()},
        "sample_ids_file": file_ref(run_dir / SAMPLE_IDS_FILE),
        "datasets": {axis: file_ref(AXES[axis].dataset_path) for axis in datasets},
        "requests_file": file_ref(out_path),
        "format_check": {
            "n": len(records),
            "ok": len(records) - len(failed),
            "failed": [{"axis": r["axis"], "sample_idx": r["sample_idx"], **r["format_check"]} for r in failed],
        },
        "empty_requests": [
            {"axis": r["axis"], "sample_idx": r["sample_idx"]} for r in records if not r["instruction_natural"].strip()
        ],
        "python_version": sys.version.split()[0],
        "platform": f"{platform.system()} {platform.release()}",
        "git": git_state(),
        "started_utc": started_utc,
        "finished_utc": datetime.now(timezone.utc).isoformat(),
        "elapsed_s": round(time.perf_counter() - started, 1),
    })

    print(f"\nFormat check: {len(records) - len(failed)}/{len(records)} ok")
    for r in failed:
        print(f"  FAILED {r['axis']} #{r['sample_idx']}: {'; '.join(r['format_check']['problems'])}")
    if server and server.get("loaded"):
        for m in server["loaded"]:
            print(f"Loaded: {m['name']}  on GPU: {m['fraction_on_gpu']}  context: {m.get('context_length')}")
    print(f"Requests -> {out_path}\nMeta     -> {meta_path}")
    return 2 if (failed and args.strict_format) else 0


if __name__ == "__main__":
    raise SystemExit(main())
