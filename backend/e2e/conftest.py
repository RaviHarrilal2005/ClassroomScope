"""
End-to-end checks of the integrated pipeline, the API and the dashboard.

Run from backend/ (plain `pytest` never collects this folder):

    python -m pytest e2e              the real pipeline over 5 stored articles
    python -m pytest e2e --collect    plus one real RSS + GNews collection run

This writes to the Supabase project in backend/.env, or in the file that
E2E_ENV_FILE names. Design: docs/superpowers/specs/2026-10-08-e2e-testing-design.md

MVP (README, "MVP features — come back to these"): it runs against the
team's shared database until there is a test database.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, Iterator, NoReturn, Optional, Tuple
from urllib.parse import urlparse

import pytest
import requests

from e2e import database
from e2e.results import Check, Footprint, render
from e2e.servers import ServerThread, build_frontend, serve_backend, serve_static
from e2e.settings import (BACKEND, RESULTS_ROOT, RUN_TIMEOUT, SERVER_TIMEOUT, TOPIC_CATALOG,
                          credential_problem, load_e2e_env)


def pytest_addoption(parser):
    parser.addoption("--collect", action="store_true",
                     help="also run one real collection from RSS and GNews (never NewsAPI)")


@dataclass
class SessionState:
    results_dir: Path
    header: Dict[str, str]
    started_at: str      # UTC ISO: classification rows re-written since then are this session's
    checks: Dict[str, Check] = field(default_factory=dict)
    client: Any = None
    before: Optional[Dict[str, Tuple[int, int]]] = None
    stopped: Optional[str] = None


STATE: Optional[SessionState] = None


def pytest_configure(config):
    global STATE
    # Before anything imports the app or an agent: their own load_dotenv
    # calls never override, so the values loaded here win.
    try:
        load_e2e_env()
    except FileNotFoundError as exc:
        raise pytest.UsageError(str(exc)) from None
    if config.option.collectonly:
        return
    now = datetime.now()
    results_dir = RESULTS_ROOT / now.strftime("%Y-%m-%d_%H%M%S")
    results_dir.mkdir(parents=True, exist_ok=True)
    mode = ("stored articles (5 per run) and one real RSS + GNews collection"
            if config.getoption("--collect") else "stored articles only (5 per run)")
    STATE = SessionState(
        results_dir=results_dir,
        header={"Date": now.strftime("%Y-%m-%d %H:%M"), "Branch": git_describe(), "Mode": mode},
        started_at=datetime.now(timezone.utc).isoformat(),
    )


def git_describe() -> str:
    """'branch @ commit', for the results header."""
    def git(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=BACKEND, capture_output=True, text=True,
                              timeout=10).stdout.strip()
    try:
        return f"{git('rev-parse', '--abbrev-ref', 'HEAD')} @ {git('rev-parse', '--short', 'HEAD')}"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def pytest_runtest_logreport(report):
    if STATE is None:
        return
    check = STATE.checks.setdefault(report.nodeid, Check(report.nodeid.split("::")[-1]))
    check.seconds += report.duration
    for name, value in report.user_properties:
        target = {"note": check.notes, "screenshot": check.screenshots}.get(name)
        if target is not None and value not in target:
            target.append(value)
    if report.failed:
        check.outcome = "failed" if report.when == "call" else "error"
        check.error = report.longreprtext[-3000:]
    elif report.skipped:
        check.outcome = "skipped"
        reason = report.longrepr[2] if isinstance(report.longrepr, tuple) else str(report.longrepr)
        check.notes.append(reason.removeprefix("Skipped: "))


def pytest_sessionfinish(session, exitstatus):
    if STATE is None:
        return
    footprint = None
    if STATE.client is not None and STATE.before is not None:
        try:
            footprint = measure_footprint(STATE.client, STATE.before, STATE.started_at)
        except Exception as exc:   # the results file must still be written
            STATE.header["Footprint"] = f"could not be measured: {exc}"
    text = render(STATE.header, list(STATE.checks.values()), footprint, STATE.stopped)
    (STATE.results_dir / "results.md").write_text(text, encoding="utf-8")


def pytest_terminal_summary(terminalreporter):
    if STATE is not None:
        terminalreporter.write_line(f"End-to-end results: {STATE.results_dir / 'results.md'}")


def measure_footprint(client: Any, before: Dict[str, Tuple[int, int]], since: str) -> Footprint:
    after = database.snapshot(client)
    return Footprint(
        before={table: count for table, (count, _) in before.items()},
        after={table: count for table, (count, _) in after.items()},
        rewritten_classifications=database.count_since(client, "classification_results", "classified_at", since),
        run_ids=database.ids_above(client, "pipeline_runs", before["pipeline_runs"][1]),
        article_ids=database.ids_above(client, "articles", before["articles"][1]),
    )


@dataclass
class Environment:
    client: Any        # supabase Client
    registry: Any      # the AgentRegistry the test server's runs use
    database: str      # host only, never the key
    classifier: str
    topic_model: str


def stop(reason: str) -> NoReturn:
    """A setup check failed: nothing after it can work, so end the session."""
    if STATE is not None:
        STATE.stopped = reason
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
    if STATE is not None:
        STATE.client = client
        STATE.header["Database"] = host
        STATE.before = database.snapshot(client)

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
    if STATE is not None:
        STATE.header.update({"Classifier": classifier, "Topic model": topic_model})
    return Environment(client, registry, host, classifier, topic_model)


@pytest.fixture(scope="session")
def results_dir() -> Path:
    assert STATE is not None, "results_dir is only available in a test session"
    return STATE.results_dir


@pytest.fixture(scope="session")
def backend(environment) -> Iterator[ServerThread]:
    """The real app on a free port. Its runs use the real agents over 5 stored articles."""
    from app import create_app
    from orchestrator import BackgroundRunner, PipelineCoordinator
    from orchestrator.supabase_store import SupabaseRunStore

    runner = BackgroundRunner(PipelineCoordinator(environment.registry, SupabaseRunStore.from_env()))
    with serve_backend(create_app(runner=runner)) as server:
        yield server
        # A run a test started must finish recording before the server goes.
        runner.wait(timeout=RUN_TIMEOUT)


@pytest.fixture(scope="session")
def frontend(backend, tmp_path_factory) -> Iterator[ServerThread]:
    """The production build, pointed at the test backend, on a free port."""
    out = tmp_path_factory.mktemp("frontend-build")
    build_frontend(out, f"{backend.url}/api/v1", timeout=SERVER_TIMEOUT)
    with serve_static(out) as server:
        yield server


FINISHED = ("completed", "completed_with_errors", "failed")


@pytest.fixture(scope="session")
def api_run(backend, environment) -> SimpleNamespace:
    """
    One run started through the API and watched to the end (P1-P5, D2, D3).

    A second start goes out straight after the first, while the first is
    still running, for P3. The database facts P5 checks are read the
    moment the run finishes: pytest runs the browser tests first, and
    D3's run re-classifies the same 5 articles, which moves their
    classified_at out of this run's window. The tests assert on what was
    recorded here.
    """
    api = f"{backend.url}/api/v1"
    first = requests.post(f"{api}/runs", json={"trigger_type": "manual"}, timeout=60)
    second = requests.post(f"{api}/runs", json={"trigger_type": "manual"}, timeout=60)
    final = None
    if first.status_code == 202:
        final = first.json()
        deadline = time.monotonic() + RUN_TIMEOUT
        while final["status"] not in FINISHED and time.monotonic() < deadline:
            time.sleep(2)
            final = requests.get(f"{api}/runs/{final['id']}", timeout=60).json()
    stored = None
    if final is not None and final["status"] in FINISHED:
        db = environment.client
        row = database.run_row(db, final["id"])
        classified = database.classified_between(db, row["started_at"], row["finished_at"])
        stored = SimpleNamespace(
            row=row, stages=database.stage_rows(db, final["id"]), classified=classified,
            analysable=database.analysable(db, classified),
            with_topic=database.articles_with_rows(db, "topic_results", classified))
    # The runner clears its active run a moment after the database says the
    # run finished, so give the list up to 10 seconds to catch up.
    listing = requests.get(f"{api}/runs", timeout=60).json()
    deadline = time.monotonic() + 10
    while listing["active_run_id"] is not None and time.monotonic() < deadline:
        time.sleep(0.5)
        listing = requests.get(f"{api}/runs", timeout=60).json()
    return SimpleNamespace(first=first, second=second, final=final, listing=listing, stored=stored)


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    """Reduced motion, so charts draw their final frame at once; tall enough for both charts."""
    return {**browser_context_args, "reduced_motion": "reduce",
            "viewport": {"width": 1280, "height": 1600}}


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    page = item.funcargs.get("page")
    if report.when == "call" and report.failed and page is not None and STATE is not None:
        name = f"{item.name}-failure.png"
        try:
            page.screenshot(path=str(STATE.results_dir / name), full_page=True)
            report.user_properties.append(("screenshot", name))
        except Exception:   # a failed screenshot must not hide the test's own failure
            pass
