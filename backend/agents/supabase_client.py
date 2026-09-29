"""
One Supabase client, shared by every agent package.

Each agent module used to build its own client at import time:

    _supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_ANON_KEY"))

That has three problems once the modules are imported by the pipeline
rather than run as scripts. Importing the module reaches out for
credentials, so a missing key becomes an ImportError in an unrelated
place (and the test suite cannot import the module at all). Every
module builds a separate connection. And the key name disagreed with
the orchestrator's, which reads SUPABASE_KEY.

`get_client()` fixes all three: nothing happens until someone asks for
a client, the client is built once, and the name resolution is in one
place.

ENVIRONMENT
  SUPABASE_URL       the API endpoint (https://<ref>.supabase.co), NOT
                     the dashboard page - a dashboard URL returns HTML
                     and surfaces as a confusing parse error downstream
  SUPABASE_KEY       preferred. Use the secret (sb_secret_...) key: the
                     publishable key has no privileges on the pipeline
                     tables and writes fail with 42501 permission denied
  SUPABASE_ANON_KEY  accepted as a fallback so the agent .env files that
                     predate this module keep working
"""
from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# backend/.env, whatever the working directory. Real environment
# variables win, so deployments can set them without a file.
ENV_PATH = Path(__file__).resolve().parents[1] / ".env"

KEY_VARS = ("SUPABASE_KEY", "SUPABASE_ANON_KEY")

_client: Optional[Any] = None
_lock = threading.Lock()


def _load_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:  # python-dotenv is optional; real env vars still work
        return
    load_dotenv(ENV_PATH)


def credentials() -> tuple[Optional[str], Optional[str], Optional[str]]:
    """(url, key, which_variable_the_key_came_from) — without building a client."""
    _load_env()
    url = os.environ.get("SUPABASE_URL")
    for name in KEY_VARS:
        key = os.environ.get(name)
        if key:
            return url, key, name
    return url, None, None


def is_configured() -> bool:
    url, key, _ = credentials()
    return bool(url and key)


def get_client() -> Any:
    """
    The shared client, built on first use.

    Raises RuntimeError with something actionable rather than letting a
    None url reach the Supabase library, which reports it as an opaque
    validation error.
    """
    global _client
    with _lock:
        if _client is not None:
            return _client

        url, key, source = credentials()
        if not url or not key:
            missing = "SUPABASE_URL" if not url else " or ".join(KEY_VARS)
            raise RuntimeError(
                f"{missing} is not set. Copy backend/.env.example to backend/.env "
                f"and fill it in (looked in {ENV_PATH})."
            )
        if url.startswith("https://supabase.com/"):
            raise RuntimeError(
                f"SUPABASE_URL is a dashboard page, not the API endpoint: {url}\n"
                "Use https://<project-ref>.supabase.co - the dashboard URL returns "
                "an HTML login page, which shows up later as a confusing parse error."
            )
        if source == "SUPABASE_ANON_KEY":
            logger.warning(
                "Using SUPABASE_ANON_KEY. The publishable key cannot write the "
                "pipeline tables (42501 permission denied); set SUPABASE_KEY to "
                "the secret key for pipeline runs."
            )

        try:
            from supabase import create_client
        except ImportError as exc:
            raise RuntimeError("The agents need the Supabase client: pip install supabase") from exc

        _client = create_client(url, key)
        return _client


def reset() -> None:
    """Drop the cached client. For tests that swap credentials."""
    global _client
    with _lock:
        _client = None
