"""
End-to-end checks of the integrated pipeline, the API and the dashboard.

Run from backend/ (plain `pytest` never collects this folder):

    python -m pytest e2e              the real pipeline over 5 stored articles
    python -m pytest e2e --collect    plus one real RSS + GNews collection run

This writes to the Supabase project in backend/.env, or in the file that
E2E_ENV_FILE names. Design: docs/superpowers/specs/2026-10-08-e2e-testing-design.md
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, NoReturn
from urllib.parse import urlparse

import pytest

from e2e.settings import TOPIC_CATALOG, credential_problem, load_e2e_env


def pytest_addoption(parser):
    parser.addoption("--collect", action="store_true",
                     help="also run one real collection from RSS and GNews (never NewsAPI)")


def pytest_configure(config):
    # Before anything imports the app or an agent: their own load_dotenv
    # calls never override, so the values loaded here win.
    try:
        load_e2e_env()
    except FileNotFoundError as exc:
        raise pytest.UsageError(str(exc)) from None


@dataclass
class Environment:
    client: Any        # supabase Client
    registry: Any      # the AgentRegistry the test server's runs use
    database: str      # host only, never the key
    classifier: str
    topic_model: str


def stop(reason: str) -> NoReturn:
    """A setup check failed: nothing after it can work, so end the session."""
    pytest.exit(reason, returncode=2)


@pytest.fixture(scope="session", autouse=True)
def environment() -> Environment:
    """S1-S3: stops the session, with the reason, if the pipeline cannot run here."""
    url, key = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY")
    problem = credential_problem(url, key)
    if problem or url is None or key is None:
        stop(f"S1: {problem}")
    from supabase import create_client

    host = urlparse(url).hostname or url
    client = create_client(url, key)
    try:
        client.table("pipeline_runs").select("id").limit(1).execute()
    except Exception as exc:
        stop(f"S1: cannot read pipeline_runs on {host}: {exc}")

    from agents.adapters import TopicAgent
    from orchestrator import build_default_registry
    from orchestrator.registry import TOPIC_MODELS
    from orchestrator.stages import CLASSIFICATION, TOPIC

    registry = build_default_registry(live=True, backlog=True, backlog_limit=5)
    if not isinstance(registry.get(TOPIC), TopicAgent):
        stop("S2: the topic stage would be a stub here: its model is missing or only a Git LFS "
             "pointer. Run `git lfs pull` and `pip install -r requirements.txt`.")
    classifier = ("LLM (Luna), keyword scorer as fallback"
                  if registry.get_fallback(CLASSIFICATION) is not None
                  else "keyword scorer (no LLM keys set)")
    models = json.loads(TOPIC_CATALOG.read_text())["models"]
    topic_model = ", ".join(f"{name} ({reg['version']})" for name, reg in models.items()
                            if (TOPIC_MODELS / name).is_file())
    return Environment(client, registry, host, classifier, topic_model)
