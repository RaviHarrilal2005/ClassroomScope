"""
The end-to-end suite's own safety rails, tested offline.

They decide which database the suite writes to and whether it runs at
all, so a mistake here costs real data. None of these touch the network.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

from e2e.results import Check, Footprint, render
from e2e.servers import FrontendBuildError, build_frontend
from e2e.settings import credential_problem, load_e2e_env

BACKEND = Path(__file__).resolve().parents[1]


def test_plain_pytest_never_collects_the_end_to_end_suite():
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"],
        cwd=BACKEND, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300,
    )
    collected = result.stdout.replace("\\", "/")
    assert result.returncode == 0, collected + result.stderr
    assert "tests/test_routes.py" in collected
    assert "e2e/" not in collected


def test_a_missing_e2e_env_file_stops_instead_of_using_the_shared_database(tmp_path):
    with pytest.raises(FileNotFoundError, match="E2E_ENV_FILE"):
        load_e2e_env(str(tmp_path / "test.env"))


def test_the_named_env_file_wins_over_values_already_set(tmp_path, monkeypatch):
    env_file = tmp_path / "test.env"
    env_file.write_text("SUPABASE_URL=https://test-project.supabase.co\n")
    monkeypatch.setenv("SUPABASE_URL", "https://shared-project.supabase.co")
    assert load_e2e_env(str(env_file)) == env_file
    assert os.environ["SUPABASE_URL"] == "https://test-project.supabase.co"


@pytest.mark.parametrize("url, key, problem", [
    (None, "sb_secret_x", "not set"),
    ("https://abc.supabase.co", "sb_publishable_x", "publishable key"),
    ("https://supabase.com/dashboard/project/abc", "sb_secret_x", "dashboard page"),
])
def test_credentials_that_cannot_run_the_suite_say_why(url, key, problem):
    assert problem in (credential_problem(url, key) or "")


def test_a_secret_key_and_an_api_url_are_fine():
    assert credential_problem("https://abc.supabase.co", "sb_secret_x") is None


def test_results_list_every_check_and_the_footprint():
    checks = [
        Check("test_p1", "passed", 1.5, notes=["run #31"]),
        Check("test_d3", "failed", 75.0, screenshots=["D3-failure.png"], error="AssertionError: stuck at running"),
        Check("test_c1", "skipped", 0.0, notes=["real collection runs only with --collect"]),
    ]
    footprint = Footprint(before={"pipeline_runs": 12, "articles": 100}, after={"pipeline_runs": 14, "articles": 100},
                          rewritten_classifications=10, run_ids=[31, 32], article_ids=[])
    text = render({"Date": "2026-10-08 14:05", "Database": "abc.supabase.co"}, checks, footprint)

    assert text.startswith("# End-to-end results, 2026-10-08 14:05\n")
    assert "| Database | abc.supabase.co |" in text
    assert "**1 passed, 1 failed, 1 skipped** in 1m 16s" in text
    assert "| test_p1 | passed | 1.5s | run #31 |" in text
    assert "| pipeline_runs | 12 | 14 | +2 |" in text
    assert "| articles | 100 | 100 | 0 |" in text
    assert "- Classification rows re-written: 10" in text
    assert "- Runs created: #31, #32" in text
    assert "- New articles: none" in text
    assert "### test_d3" in text
    assert "AssertionError: stuck at running" in text
    assert "Screenshot: D3-failure.png" in text


def test_a_note_with_a_pipe_cannot_break_the_table():
    text = render({"Date": "now"}, [Check("test_x", notes=["a | b"])], None)
    assert "| test_x | passed | 0.0s | a \\| b |" in text


def test_a_session_stopped_by_a_setup_check_says_why():
    text = render({"Date": "now"}, [], None, stopped="S1: SUPABASE_URL and SUPABASE_KEY are not set.")
    assert "## Stopped early\n\nS1: SUPABASE_URL and SUPABASE_KEY are not set." in text
    assert "**0 passed, 0 failed, 0 skipped** in 0.0s" in text


def test_a_frontend_without_npm_install_fails_with_the_fix(tmp_path):
    with pytest.raises(FrontendBuildError, match="npm install"):
        build_frontend(tmp_path / "out", "http://127.0.0.1:1/api/v1", frontend_dir=tmp_path)
