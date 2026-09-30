"""RELEASE.json lists the agent fixes the case study depends on; the re-run reads it instead of the
git history, which a release does not carry."""

import json
import subprocess

import pytest

from benchmarks.case_study import release_info
from benchmarks.case_study.release_info import FIX_SUBJECTS, ReleaseError, build_release, read_fixes


def git(repo, *args):
    subprocess.run(
        ["git", "-c", "user.name=test", "-c", "user.email=test@example.org", *args],
        cwd=repo, check=True, capture_output=True,
    )


def repo_with_commits(tmp_path, subjects):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    for subject in ["initial", *subjects]:
        git(repo, "commit", "-q", "--allow-empty", "-m", subject)
    return repo


def release_file(tmp_path, fixes):
    path = tmp_path / "RELEASE.json"
    path.write_text(json.dumps({"source_commit": "abc", "fixes": fixes}), encoding="utf-8")
    return path


def complete_fixes():
    return {name: {"subject": subject, "commit": f"sha-{name}"} for name, subject in FIX_SUBJECTS.items()}


def test_build_release_resolves_every_fix_from_the_history(tmp_path):
    repo = repo_with_commits(tmp_path, FIX_SUBJECTS.values())
    release = build_release(repo)
    assert set(release["fixes"]) == set(FIX_SUBJECTS)
    assert all(fix["commit"] for fix in release["fixes"].values())
    assert len(release["source_commit"]) == 40


def test_build_release_refuses_a_history_without_a_fix(tmp_path):
    subjects = list(FIX_SUBJECTS.values())[1:]
    repo = repo_with_commits(tmp_path, subjects)
    with pytest.raises(ReleaseError, match=next(iter(FIX_SUBJECTS))):
        build_release(repo)


def test_read_fixes_accepts_a_complete_release(tmp_path):
    assert read_fixes(release_file(tmp_path, complete_fixes())) == complete_fixes()


def test_read_fixes_needs_the_file(tmp_path):
    with pytest.raises(ReleaseError, match="does not exist"):
        read_fixes(tmp_path / "RELEASE.json")


@pytest.mark.parametrize("change", ["missing", "no_commit", "other_subject"])
def test_read_fixes_refuses_an_incomplete_release(tmp_path, change):
    fixes = complete_fixes()
    name = "s_star_checked"
    if change == "missing":
        del fixes[name]
    elif change == "no_commit":
        fixes[name]["commit"] = None
    else:
        fixes[name]["subject"] = "fix(agent): something else"
    with pytest.raises(ReleaseError, match=name):
        read_fixes(release_file(tmp_path, fixes))


def test_main_writes_release_json(tmp_path, monkeypatch):
    repo = repo_with_commits(tmp_path, FIX_SUBJECTS.values())
    monkeypatch.setattr(release_info, "build_release", lambda: build_release(repo))
    output = tmp_path / "out" / "RELEASE.json"
    output.parent.mkdir()
    assert release_info.main(["--output", str(output)]) == 0
    assert read_fixes(output).keys() == FIX_SUBJECTS.keys()
