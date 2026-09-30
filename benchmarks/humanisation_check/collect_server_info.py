"""
Collect the Ollama host facts the manifest needs; run ON the Ollama server.

Standard library only (Python 3.6+). Prints one JSON object: GPU (nvidia-smi),
Ollama version and model list, and the server's OLLAMA_* environment from
the systemd unit, the running ``ollama serve`` process (if readable) or a
Docker container named ollama.

    ssh <HOST> python3 - < benchmarks/humanisation_check/collect_server_info.py
or let run_paired do it with ``--ssh-host <HOST>``.
"""

import json
import os
import subprocess
import sys

ENV_PREFIXES = ("OLLAMA_", "CUDA_VISIBLE_DEVICES", "GGML_", "HIP_VISIBLE_DEVICES")


def run(cmd):
    try:
        out = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
        return {"cmd": " ".join(cmd), "rc": out.returncode,
                "stdout": out.stdout.decode("utf-8", "replace").strip(),
                "stderr": out.stderr.decode("utf-8", "replace").strip()}
    except Exception as exc:
        return {"cmd": " ".join(cmd), "error": str(exc)}


def wanted(name):
    return name.startswith(ENV_PREFIXES)


def systemd_env():
    res = run(["systemctl", "show", "ollama", "--property=Environment", "--no-pager"])
    env = {}
    text = res.get("stdout", "")
    if text.startswith("Environment="):
        for item in text[len("Environment="):].split():
            if "=" in item:
                k, v = item.split("=", 1)
                if wanted(k):
                    env[k] = v.strip('"')
    return env, res


def process_env():
    res = run(["pgrep", "-f", "ollama serve"])
    envs = {}
    for pid in res.get("stdout", "").split():
        try:
            with open("/proc/%s/environ" % pid, "rb") as f:
                items = f.read().split(b"\0")
            envs[pid] = {k: v for k, v in (i.decode("utf-8", "replace").split("=", 1) for i in items if b"=" in i) if wanted(k)}
        except Exception as exc:
            envs[pid] = {"error": str(exc)}
    return envs


def docker_env():
    res = run(["docker", "inspect", "--format", "{{json .Config.Env}}", "ollama"])
    if res.get("rc") != 0:
        return None
    try:
        return {k: v for k, v in (i.split("=", 1) for i in json.loads(res["stdout"])) if wanted(k)}
    except Exception:
        return None


def main():
    sd_env, sd_raw = systemd_env()
    info = {
        "hostname": run(["hostname"]).get("stdout"),
        "gpu": run(["nvidia-smi", "--query-gpu=index,name,memory.total,memory.used,driver_version",
                    "--format=csv,noheader"]),
        "gpu_processes": run(["nvidia-smi", "--query-compute-apps=pid,process_name,used_memory",
                              "--format=csv,noheader"]),
        "nvidia_smi": run(["nvidia-smi"]),
        "ollama_version": run(["ollama", "--version"]),
        "ollama_list": run(["ollama", "list"]),
        "ollama_ps": run(["ollama", "ps"]),
        "env_systemd": sd_env,
        "env_systemd_raw": sd_raw,
        "env_process": process_env(),
        "env_docker": docker_env(),
        "env_shell": {k: v for k, v in os.environ.items() if wanted(k)},
        "python": sys.version.split()[0],
    }
    effective = {}
    for source in (info["env_shell"], info["env_docker"] or {}, info["env_systemd"],
                   *[e for e in info["env_process"].values() if "error" not in e]):
        effective.update(source)
    info["env_effective"] = effective
    print(json.dumps(info, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
