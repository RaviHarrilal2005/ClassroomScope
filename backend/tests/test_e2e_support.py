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
