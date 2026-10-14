"""
ClassroomScope API Gateway (SS-4) — entry point.

STATUS:
  * /api/v1/runs  — pipeline coordinator endpoints (sequencing built,
                    agents are stubs until each owner's agent is ready)
  * /api/v1/results — the analysable articles and their topic counts,
                      filtered per request (orchestrator/corpus.py);
                      sentiment is still a hardcoded placeholder
  * /api/v1/search/comments — keyword search over article comments
  * The run store is Supabase when SUPABASE_URL / SUPABASE_KEY are set,
    in-memory otherwise — see build_run_store() below.
  * Auth and the real data access layer are NOT connected yet — see the
    TODOs below and docs/pipeline-coordinator.md.
"""
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS

from orchestrator import (
    BackgroundRunner,
    InMemoryRunStore,
    PipelineCoordinator,
    build_default_registry,
)
from orchestrator import corpus
from orchestrator.routes import create_runs_blueprint
from orchestrator.supabase_store import SupabaseRunStore

logger = logging.getLogger(__name__)

# Shaped like what the aggregation agent will produce, but invented: no
# stage aggregates sentiment_results into /results yet.
PLACEHOLDER_SENTIMENT = {"positive": 0.55, "neutral": 0.23, "negative": 0.22}

# Reads backend/.env whatever the working directory. Real environment
# variables win, so deployments can set them without a file.
load_dotenv(Path(__file__).with_name(".env"))


def build_run_store():
    """
    Supabase when SUPABASE_URL / SUPABASE_KEY are set, in-memory otherwise.

    The fallback keeps the app startable for front-end work without
    credentials; without it, a missing variable is a hard startup failure.
    In-memory runs are lost when the process stops.

    SUPABASE_ANON_KEY is deliberately NOT accepted here, though the
    agents take it: the publishable key cannot write pipeline_runs or
    pipeline_stage_runs (42501), so using it would trade a clear warning
    at startup for every run failing halfway through.
    """
    missing = [name for name in ("SUPABASE_URL", "SUPABASE_KEY") if not os.environ.get(name)]
    if missing:
        detail = " and ".join(missing)
        if "SUPABASE_KEY" in missing and os.environ.get("SUPABASE_ANON_KEY"):
            detail += (" (SUPABASE_ANON_KEY is set, but the publishable key cannot"
                       " write the run tables - use the sb_secret_... key)")
        logger.warning(
            "%s not set - using InMemoryRunStore; runs will not persist", detail
        )
        return InMemoryRunStore()
    logger.info("Using SupabaseRunStore for pipeline runs")
    return SupabaseRunStore.from_env()


def create_app(runner=None, read_corpus=None, search_comments=None):
    """
    Build the Flask app. Tests pass in their own runner, corpus reader and
    comment search; normal startup builds the defaults (agents and run
    store from the environment, the corpus from Supabase when it is set).
    """
    app = Flask(__name__)
    CORS(app)  # TODO: restrict origins before this leaves localhost

    if runner is None:
        coordinator = PipelineCoordinator(build_default_registry(), build_run_store())
        runner = BackgroundRunner(coordinator)
    if read_corpus is None or search_comments is None:
        default_read, default_search = corpus.from_env()
        read_corpus = read_corpus or default_read
        search_comments = search_comments or default_search
    app.register_blueprint(create_runs_blueprint(runner))

    def filters_or_400():
        """The request's filters, or a 400 response saying what is wrong with them."""
        try:
            return corpus.parse_filters(request.args), None
        except ValueError as exc:
            return None, (jsonify({"error": str(exc)}), 400)

    @app.get("/api/v1/health")
    def health():
        """Lets the front end confirm the backend is reachable."""
        return jsonify({"status": "ok"})

    @app.get("/api/v1/results")
    def get_results():
        """
        The dashboard's data, narrowed by the filter query params: from,
        to, source_type, stakeholder, topic, q (see orchestrator/corpus.py).

        Articles and top topics are real. sentiment_distribution is still
        a placeholder until the sentiment agent is wired in.

        TODO: add auth check once Session/Auth Context (SS-5) is wired in
        """
        filters, error = filters_or_400()
        if error:
            return error
        return jsonify({
            "sentiment_distribution": PLACEHOLDER_SENTIMENT,
            **corpus.results_payload(read_corpus(), filters),
        })

    @app.get("/api/v1/search/comments")
    def get_comment_search():
        """
        Comments containing `q` on the articles the other filters allow.

        `q` doesn't narrow the articles here: a comment can use a word its
        article never does.
        """
        filters, error = filters_or_400()
        if error:
            return error
        if not filters["q"]:
            return jsonify({"error": "'q' is required."}), 400
        current = read_corpus()
        if not current["available"]:
            return jsonify(corpus.comments_unavailable(current["reason"]))
        articles = corpus.filter_articles(current["articles"], {**filters, "q": ""})
        try:
            return jsonify(search_comments(articles, filters["q"]))
        except Exception:
            logger.exception("Comment search failed")
            return jsonify(corpus.comments_unavailable("Could not search comments; see the backend log."))

    return app


app = create_app()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    app.run(debug=True, port=5000)
