"""
ClassroomScope API Gateway (SS-4) — entry point.

STATUS:
  * /api/v1/runs  — pipeline coordinator endpoints (sequencing built,
                    agents are stubs until each owner's agent is ready)
  * /api/v1/results — still a hardcoded stub for the dashboard
  * Auth, the real data access layer, and the Supabase run store are
    NOT connected yet — see TODOs below and docs/pipeline-coordinator.md.
"""
import logging

from flask import Flask, jsonify
from flask_cors import CORS

from orchestrator import (
    BackgroundRunner,
    InMemoryRunStore,
    PipelineCoordinator,
    build_default_registry,
)
from orchestrator.routes import create_runs_blueprint


def create_app(runner=None):
    """
    Build the Flask app. Tests pass in their own runner; normal startup
    builds the default one (stub agents + in-memory run store).
    """
    app = Flask(__name__)
    CORS(app)  # TODO: restrict origins before this leaves localhost

    if runner is None:
        # TODO: switch to SupabaseRunStore.from_env() once the
        # pipeline_runs / pipeline_stage_runs tables exist (Task 6.3).
        coordinator = PipelineCoordinator(build_default_registry(), InMemoryRunStore())
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
