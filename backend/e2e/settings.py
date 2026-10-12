"""
Settings and safety checks for the end-to-end suite.

Kept apart from conftest.py so the offline suite can test them: they are
what stands between a typo and writing to the wrong database.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

BACKEND = Path(__file__).resolve().parents[1]
RESULTS_ROOT = BACKEND / "e2e" / "results"
TOPIC_CATALOG = BACKEND / "agents" / "topic" / "topic_catalog.json"

RUN_TIMEOUT = 300          # seconds: one pipeline run over stored articles
COLLECTION_TIMEOUT = 600   # seconds: one real collection run (fetches and downloads pages)
SERVER_TIMEOUT = 60        # seconds: starting the servers and building the frontend
PAGE_TIMEOUT = 30_000      # milliseconds: a page load or a dashboard update


def load_e2e_env(env_file: Optional[str] = None, default: Path = BACKEND / ".env") -> Path:
    """
    Load the suite's credentials.

    E2E_ENV_FILE names the file (the future test database), and its values
    win over any already set. Without it, backend/.env, which, as with the
    app's own loaders, never replaces a value already set. A named file that
    does not exist, or an empty E2E_ENV_FILE, is an error: silently falling
    back to backend/.env would write to the shared database while you think
    you are testing somewhere else.
    """
    named = env_file if env_file is not None else os.environ.get("E2E_ENV_FILE")
    if named is None:
        load_dotenv(default)
        return default
    if not named:
        raise FileNotFoundError("E2E_ENV_FILE is set but empty: name the env file, "
                                "or unset it to use backend/.env.")
    path = Path(named)
    if not path.is_file():
        raise FileNotFoundError(f"E2E_ENV_FILE points at {path}, which does not exist.")
    load_dotenv(path, override=True)
    return path


def credential_problem(url: Optional[str], key: Optional[str]) -> Optional[str]:
    """Why these Supabase credentials cannot run the suite, or None if they can."""
    if not url or not key:
        return "SUPABASE_URL and SUPABASE_KEY are not set (backend/.env, or the file E2E_ENV_FILE names)."
    if key.startswith("sb_publishable_"):
        return ("SUPABASE_KEY is the publishable key, which cannot record pipeline runs. "
                "Use the secret key (sb_secret_...).")
    if "supabase.com/dashboard" in url:
        return "SUPABASE_URL is the dashboard page; use the API endpoint (https://<ref>.supabase.co)."
    return None
