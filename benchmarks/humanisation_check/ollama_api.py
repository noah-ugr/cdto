"""
Minimal client for the Ollama native API: version, full model digests,
model details, loaded models, loading and unloading.

``base_url`` may be the OpenAI-compatible URL (``http://host:port/v1``); the
``/v1`` suffix is dropped for the native endpoints.

    python -m benchmarks.humanisation_check.ollama_api --base-url http://localhost:<PORT> \
        --models gpt-oss:20b qwen2.5:32b phi4:14b
prints the server version, the full digest of each model and whether it
matches the expected ``ollama list`` ID, and the loaded models.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import urllib.request
from typing import Any, Dict, Iterable, List, Optional

from benchmarks.humanisation_check.common import EXPECTED_SHORT_IDS


def native_base(base_url: str) -> str:
    base = base_url.rstrip("/")
    return base[: -len("/v1")] if base.endswith("/v1") else base


def _request(base_url: str, path: str, payload: Optional[dict] = None, timeout: float = 30.0) -> Any:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        native_base(base_url) + path,
        data=data,
        headers={"Content-Type": "application/json"},
        method="GET" if data is None else "POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def version(base_url: str) -> str:
    return _request(base_url, "/api/version")["version"]


def tags(base_url: str) -> List[dict]:
    return _request(base_url, "/api/tags").get("models", [])


def _same_model(entry: dict, name: str) -> bool:
    names = {entry.get("name"), entry.get("model")}
    return name in names or (":" not in name and f"{name}:latest" in names)


def find(models: Iterable[dict], name: str) -> Optional[dict]:
    return next((m for m in models if _same_model(m, name)), None)


def show(base_url: str, name: str) -> dict:
    return _request(base_url, "/api/show", {"model": name})


def loaded(base_url: str) -> List[dict]:
    return _request(base_url, "/api/ps").get("models", [])


def preload(base_url: str, name: str, timeout: float = 900.0) -> dict:
    """Load a model without generating (a generate request without prompt)."""
    return _request(base_url, "/api/generate", {"model": name}, timeout=timeout)


def unload(base_url: str, name: str, wait_s: float = 120.0) -> bool:
    """Unload a model (keep_alive 0) and wait until /api/ps no longer lists it."""
    _request(base_url, "/api/generate", {"model": name, "keep_alive": 0}, timeout=wait_s)
    deadline = time.time() + wait_s
    while time.time() < deadline:
        if find(loaded(base_url), name) is None:
            return True
        time.sleep(1.0)
    return False


def gpu_status(entry: dict) -> dict:
    size = int(entry.get("size") or 0)
    size_vram = int(entry.get("size_vram") or 0)
    return {
        "name": entry.get("name"),
        "digest": entry.get("digest"),
        "size": size,
        "size_vram": size_vram,
        "fraction_on_gpu": round(size_vram / size, 4) if size else None,
        "fully_on_gpu": size > 0 and size_vram >= size,
        "context_length": entry.get("context_length"),
        "expires_at": entry.get("expires_at"),
    }


def model_summary(base_url: str, name: str, models: Optional[List[dict]] = None) -> dict:
    """Digest, `ollama list` ID, default parameters and chat template of a model."""
    entry = find(models if models is not None else tags(base_url), name)
    if entry is None:
        return {"name": name, "present": False}
    digest = entry.get("digest") or ""
    summary = {
        "name": name,
        "present": True,
        "digest": digest,
        "short_id": digest[:12],
        "expected_short_id": EXPECTED_SHORT_IDS.get(name),
        "short_id_matches": EXPECTED_SHORT_IDS.get(name) in (None, digest[:12]),
        "size": entry.get("size"),
        "modified_at": entry.get("modified_at"),
        "details": entry.get("details"),
    }
    try:
        info = show(base_url, name)
        template = info.get("template") or ""
        summary.update({
            "parameters": info.get("parameters"),
            "template_sha256": hashlib.sha256(template.encode("utf-8")).hexdigest(),
            # gpt-oss templates stamp the current date into the system turn.
            "template_has_current_date": "currentDate" in template,
            "capabilities": info.get("capabilities"),
            "context_length_trained": {
                k: v for k, v in (info.get("model_info") or {}).items() if k.endswith(".context_length")
            },
            "weights_blobs": weights_blobs(info.get("modelfile")),
            "modelfile_sha256": hashlib.sha256((info.get("modelfile") or "").encode("utf-8")).hexdigest(),
        })
    except Exception as exc:
        summary["show_error"] = str(exc)
    return summary


def weights_blobs(modelfile: str) -> List[str]:
    """sha256 digests of the blobs named by the FROM lines of a modelfile (the weights layer)."""
    blobs = []
    for line in (modelfile or "").splitlines():
        if line.strip().upper().startswith("FROM "):
            blobs += re.findall(r"sha256[-:]([0-9a-f]{64})", line)
    return blobs


def parse_parameters(parameters: Optional[str]) -> List[tuple]:
    """``/api/show`` parameters as sorted (name, value) pairs."""
    pairs = []
    for line in (parameters or "").splitlines():
        parts = line.split(None, 1)
        if parts:
            pairs.append((parts[0], parts[1].strip().strip('"') if len(parts) > 1 else ""))
    return sorted(pairs)


def derivation_check(base_url: str, base: str, derived: str) -> Dict[str, Any]:
    """
    Check that ``derived`` is ``base`` with only num_ctx changed: same weights
    blob, chat template, system prompt, details and architecture metadata,
    and default parameters that differ only in num_ctx.
    """
    shown = {name: show(base_url, name) for name in (base, derived)}
    b, d = shown[base], shown[derived]
    base_params, derived_params = parse_parameters(b.get("parameters")), parse_parameters(d.get("parameters"))
    only_base = [p for p in base_params if p not in derived_params]
    only_derived = [p for p in derived_params if p not in base_params]
    num_ctx = [v for k, v in derived_params if k == "num_ctx"]

    def sha(text):
        return hashlib.sha256((text or "").encode("utf-8")).hexdigest()

    def details(info):  # parent_model names the base of a derived model
        return {k: v for k, v in (info.get("details") or {}).items() if k != "parent_model"}

    checks = {
        "weights_blobs_equal": bool(weights_blobs(b.get("modelfile"))) and weights_blobs(b.get("modelfile")) == weights_blobs(d.get("modelfile")),
        "template_equal": sha(b.get("template")) == sha(d.get("template")),
        "system_equal": (b.get("system") or "") == (d.get("system") or ""),
        "details_equal": details(b) == details(d),
        "model_info_equal": b.get("model_info") == d.get("model_info"),
        "only_num_ctx_differs": all(k == "num_ctx" for k, _ in only_base + only_derived) and len(num_ctx) == 1,
    }
    return {
        "base": base,
        "derived": derived,
        "weights_blobs": {base: weights_blobs(b.get("modelfile")), derived: weights_blobs(d.get("modelfile"))},
        "template_sha256": {base: sha(b.get("template")), derived: sha(d.get("template"))},
        "derived_parent_model": (d.get("details") or {}).get("parent_model"),
        "parameters_only_in_base": only_base,
        "parameters_only_in_derived": only_derived,
        "num_ctx": int(num_ctx[0]) if len(num_ctx) == 1 and num_ctx[0].isdigit() else None,
        "checks": checks,
        "ok": all(checks.values()),
    }


def server_summary(base_url: str, names: Iterable[str]) -> dict:
    out: Dict[str, Any] = {"base_url": base_url}
    try:
        out["version"] = version(base_url)
        models = tags(base_url)
        out["models"] = {name: model_summary(base_url, name, models) for name in names}
        out["loaded"] = [gpu_status(m) for m in loaded(base_url)]
    except Exception as exc:
        out["error"] = str(exc)
    return out


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ollama version, full model digests and loaded models")
    parser.add_argument("--base-url", required=True, help="http://localhost:<PORT> (a /v1 suffix is accepted)")
    parser.add_argument("--models", nargs="+", default=list(EXPECTED_SHORT_IDS))
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    summary = server_summary(args.base_url, args.models)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 1 if "error" in summary else 0


if __name__ == "__main__":
    raise SystemExit(main())
