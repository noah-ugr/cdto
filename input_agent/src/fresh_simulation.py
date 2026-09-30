"""
Author: Noah Masegosa Caceres
Center: @ugr

Objective: Ejecuta core.pipeline.run_petrinets_simulation en un proceso nuevo.

Cada simulación se ejecuta en un proceso nuevo para que el estado del engine se reconstruya a partir
de la configuración que se simula: estructura de la red, pesos de arco y retardos. Así el resultado
de una simulación depende solo de su configuración y no de lo que se haya simulado antes en el mismo
proceso del agente, que es también como el optimizador evalúa cada candidato.
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
TIMEOUT_ENV = "CDTO_SIMULATION_TIMEOUT_S"


def _as_dict(config: Any) -> Dict[str, Any]:
    if hasattr(config, "model_dump"):
        return config.model_dump(by_alias=True)
    return config


def _json_default(value: Any) -> Any:
    if hasattr(value, "item"):
        return value.item()
    if isinstance(value, (set, tuple)):
        return list(value)
    return str(value)


def run_petrinets_simulation_fresh(
    input: Any,
    info: Any = None,
    silence: bool = True,
    io_dir: Optional[str] = None,
    timeout: Optional[float] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Mismo contrato que core.pipeline.run_petrinets_simulation, en un proceso nuevo: devuelve
    (general_results, durations_results) y deja las salidas en CDTO_IO_DIR (o en io_dir, si se da).
    timeout (s) por defecto sale de CDTO_SIMULATION_TIMEOUT_S; sin ella no hay límite, como antes.
    """
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(p for p in (str(REPO_ROOT), env.get("PYTHONPATH")) if p)
    env.setdefault("PYTHONIOENCODING", "utf-8")
    if io_dir is not None:
        env["CDTO_IO_DIR"] = str(io_dir)
    if timeout is None and os.environ.get(TIMEOUT_ENV):
        timeout = float(os.environ[TIMEOUT_ENV])

    with tempfile.TemporaryDirectory(prefix="cdto_sim_") as tmp:
        config_path = Path(tmp) / "config.json"
        result_path = Path(tmp) / "result.json"
        config_path.write_text(json.dumps(_as_dict(input), ensure_ascii=False), encoding="utf-8")
        command = [sys.executable, "-m", "input_agent.src.fresh_simulation", str(config_path), str(result_path)]
        if not silence:
            command.append("--verbose")
        proc = subprocess.run(
            command,
            cwd=os.getcwd(),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        if proc.returncode != 0 or not result_path.exists():
            tail = (proc.stderr or proc.stdout or "").strip()[-2000:]
            raise RuntimeError(f"La simulación en un proceso nuevo falló (código {proc.returncode}): {tail}")
        result = json.loads(result_path.read_text(encoding="utf-8"))
    return result["general"], result["durations"]


def _main(argv) -> int:
    config_path, result_path = argv[0], argv[1]
    silence = "--verbose" not in argv[2:]

    from core.pipeline import run_petrinets_simulation

    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    general, durations = run_petrinets_simulation(input=config, info=None, silence=silence)
    Path(result_path).write_text(
        json.dumps({"general": general, "durations": durations}, default=_json_default), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
