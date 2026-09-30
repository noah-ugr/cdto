"""RELEASE.json: the agent fixes the case study depends on, and the commit each one came in.

The re-run of the case study (rerun_case_study.py) needs every fix in FIX_SUBJECTS. Their commits
exist only in the history of the repository where they were made, so this module resolves them once,
by exact commit subject, and writes them to RELEASE.json at the repository root together with the
commit the release was made from. The re-run reads that file and does not start if a fix is missing;
it does not need the git history.

    python benchmarks/case_study/release_info.py            # writes RELEASE.json from git log HEAD

Exits with status 1, and writes nothing, if a fix is not in the history.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]
RELEASE_FILE = REPO_ROOT / "RELEASE.json"

# Agent fixes the case study depends on, by commit subject.
FIX_SUBJECTS = {
    "fresh_simulations": "fix(agent): run every CDTO simulation in a fresh process",
    "diagnostic_routine_inputs": "fix(agent): give the diagnostic routine the rejected candidate's delta and violations",
    "chat_current_query": "fix(agent): make the final chat answer summarise the current query",
    "candidate_kpis_against_s_k": "fix(agent): compare the rejected candidate's KPIs with the current configuration",
    "violation_messages": "fix(validator): English violation messages that say which field points to what",
    "xai_delta_log": "fix(agent): log the delta the xAI receives in the diagnostic routine",
    "s_star_decision_variables": "fix(optimizer): build S* from the current configuration, changing only the IWO decision variables",
    "s_star_checked": "fix(agent): apply S* through the admissibility check, like a batch",
    "s_star_simulated_and_explained": "fix(agent): simulate and explain S* before the chat, against the configuration it replaced",
    "precedence_direction": "fix(agent): describe taskCode and activityCode as what their owner precedes",
}


class ReleaseError(Exception):
    """RELEASE.json is missing, unreadable or lacks a required fix."""


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()


def fixes_from_history(repo: Path = REPO_ROOT) -> dict[str, dict[str, str | None]]:
    """Commit in HEAD of each fix in FIX_SUBJECTS, matched by exact subject (None if missing)."""
    by_subject: dict[str, str] = {}
    for line in _git(repo, "log", "--format=%H%x09%s", "HEAD").splitlines():
        sha, _, subject = line.partition("\t")
        by_subject.setdefault(subject, sha)
    return {name: {"subject": subject, "commit": by_subject.get(subject)} for name, subject in FIX_SUBJECTS.items()}


def build_release(repo: Path = REPO_ROOT) -> dict:
    fixes = fixes_from_history(repo)
    missing = [name for name, fix in fixes.items() if not fix["commit"]]
    if missing:
        raise ReleaseError(f"these fixes are not in the history of HEAD: {missing}")
    return {
        "source_commit": _git(repo, "rev-parse", "HEAD"),
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "fixes": fixes,
    }


def read_fixes(path: Path = RELEASE_FILE) -> dict[str, dict[str, str]]:
    """Fixes of RELEASE.json, checked against FIX_SUBJECTS: every one present, with its subject and a commit."""
    try:
        release = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ReleaseError(f"{path} does not exist; write it with python benchmarks/case_study/release_info.py") from None
    except (OSError, ValueError) as exc:
        raise ReleaseError(f"{path} cannot be read: {exc}") from None
    fixes = release.get("fixes") if isinstance(release, dict) else None
    if not isinstance(fixes, dict):
        raise ReleaseError(f"{path} has no fixes")
    missing = [
        name for name, subject in FIX_SUBJECTS.items()
        if not isinstance(fixes.get(name), dict) or fixes[name].get("subject") != subject or not fixes[name].get("commit")
    ]
    if missing:
        raise ReleaseError(f"{path} lacks these fixes: {missing}")
    return {name: fixes[name] for name in FIX_SUBJECTS}


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", default=str(RELEASE_FILE), help="Where to write RELEASE.json")
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        release = build_release()
    except ReleaseError as exc:
        print(f"ERROR: {exc}")
        return 1
    Path(args.output).write_text(json.dumps(release, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Saved: {args.output} (source commit {release['source_commit'][:7]}, {len(release['fixes'])} fixes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
