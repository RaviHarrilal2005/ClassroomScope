"""
ClassroomScope API Gateway (SS-4) — entry point.

STATUS:
  * /api/v1/runs  — pipeline coordinator endpoints (sequencing built,
                    agents are stubs until each owner's agent is ready)
  * /api/v1/results — still a hardcoded stub for the dashboard
  * The run store is Supabase when SUPABASE_URL / SUPABASE_KEY are set,
    in-memory otherwise — see build_run_store() below.
  * Auth and the real data access layer are NOT connected yet — see the
    TODOs below and docs/pipeline-coordinator.md.
"""
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify
from flask_cors import CORS

from orchestrator import (
    BackgroundRunner,
    InMemoryRunStore,
    PipelineCoordinator,
    build_default_registry,
)
from orchestrator.routes import create_runs_blueprint
from orchestrator.supabase_store import SupabaseRunStore

logger = logging.getLogger(__name__)

# Reads backend/.env whatever the working directory. Real environment
# variables win, so deployments can set them without a file.
load_dotenv(Path(__file__).with_name(".env"))


def build_run_store():
    """
    Supabase when SUPABASE_URL / SUPABASE_KEY are set, in-memory otherwise.

    The fallback keeps the app startable for front-end work without
    credentials; without it, a missing variable is a hard startup failure.
    In-memory runs are lost when the process stops.
    """
    if not (os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_KEY")):
        logger.warning(
            "SUPABASE_URL / SUPABASE_KEY not set - using InMemoryRunStore; runs will not persist"
        )
        return InMemoryRunStore()
    logger.info("Using SupabaseRunStore for pipeline runs")
    return SupabaseRunStore.from_env()


def create_app(runner=None):
    """
    Build the Flask app. Tests pass in their own runner; normal startup
    builds the default one (stub agents + in-memory run store).
    """
    app = Flask(__name__)
    CORS(app)  # TODO: restrict origins before this leaves localhost

    if runner is None:
        coordinator = PipelineCoordinator(build_default_registry(), build_run_store())
        runner = BackgroundRunner(coordinator)
    app.register_blueprint(create_runs_blueprint(runner))

    @app.get("/api/v1/health")
    def health():
        """Lets the front end confirm the backend is reachable."""
        return jsonify({"status": "ok"})

    @app.get("/api/v1/results")
    def get_results():
        """
        Stub results endpoint.

        Returns hardcoded data shaped like what the real Aggregation
        Service (see design doc, Section 6.5) will eventually produce,
        so the front end can be built against a stable contract before
        the real pipeline exists.

        TODO:
          - accept filter query params (date range, source, topic)
          - replace hardcoded payload with a real call to the
            Data Access Layer once the Core Database is connected
          - add auth check once Session/Auth Context (SS-5) is wired in
        """
        return jsonify({
            "sentiment_distribution": {
                "positive": 0.55,
                "neutral": 0.23,
                "negative": 0.22,
            },
            "top_topics": [
                {"label": "Academic integrity", "count": 42},
                {"label": "Classroom AI tools", "count": 35},
                {"label": "Policy & regulation", "count": 21},
            ],
            "articles": [
                {
                    "id": "stub-1",
                    "title": "Universities rewrite AI policy amid ChatGPT concerns",
                    "source": "National",
                    "stakeholder": "Administrator",
                    "sentiment": "neutral",
                },
                {
                    "id": "stub-2",
                    "title": "Teachers embrace AI tutors in the classroom",
                    "source": "Trade",
                    "stakeholder": "Educator",
                    "sentiment": "positive",
                },
            ],
        })

    return app


app = create_app()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    app.run(debug=True, port=5000)
