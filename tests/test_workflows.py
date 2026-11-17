"""Vérifie la structure des workflows GitHub Actions (et leur syntaxe via actionlint s'il est installé)."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

WF = Path(__file__).resolve().parent.parent / ".github" / "workflows"


def load(name: str) -> dict:
    data = yaml.safe_load((WF / name).read_text(encoding="utf-8"))
    # PyYAML lit la clé « on » comme le booléen True
    data["on"] = data.pop(True, data.get("on"))
    return data


def test_newsletter_workflow():
    wf = load("newsletter.yml")
    assert wf["on"]["schedule"][0]["cron"] == "0 6 * * 1"
    inputs = wf["on"]["workflow_dispatch"]["inputs"]
    assert inputs["dry_run"]["type"] == "boolean"
    assert wf["permissions"]["contents"] == "write"
    assert wf["concurrency"]["cancel-in-progress"] is False
    steps = wf["jobs"]["newsletter"]["steps"]
    text = (WF / "newsletter.yml").read_text(encoding="utf-8")
    for secret in ("GEMINI_API_KEY", "BREVO_API_KEY", "BREVO_LIST_ID", "BREVO_SENDER_EMAIL", "FALLBACK_API_KEY"):
        assert f"secrets.{secret}" in text
    assert any(s.get("with", {}).get("cache") == "pip" for s in steps)
    assert any("git add data docs" in s.get("run", "") for s in steps)


def test_keepalive_and_tests_workflows():
    keep = load("keepalive.yml")
    assert "schedule" in keep["on"]
    tests = load("tests.yml")
    assert "push" in tests["on"]


@pytest.mark.skipif(shutil.which("actionlint") is None, reason="actionlint non installé")
def test_actionlint():
    files = [str(p) for p in sorted(WF.glob("*.yml"))]
    res = subprocess.run(["actionlint", "-no-color", *files], capture_output=True, text=True)
    assert res.returncode == 0, res.stdout + res.stderr
