"""
API endpoints for pipeline runs.

  POST /api/v1/runs            start a run          -> 202 + run (409 if one is active)
  GET  /api/v1/runs            recent runs, newest first (?limit=N, max 100)
  GET  /api/v1/runs/<run_id>   one run with its stage-by-stage status

The dashboard's run-status poller calls GET /api/v1/runs/<run_id> every
few seconds while a run is active.
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from .models import to_dict
from .runner import BackgroundRunner, RunAlreadyActive
from .stages import TRIGGER_TYPES


def create_runs_blueprint(runner: BackgroundRunner) -> Blueprint:
    bp = Blueprint("runs", __name__, url_prefix="/api/v1/runs")
    store = runner.store

    def run_payload(run):
        data = to_dict(run)
        data["stages"] = [to_dict(s) for s in store.list_stages(run.id)]
        return data

    @bp.post("")
    def start_run():
        # TODO(auth): restrict to the Administrator role once login (SS-5) exists.
        body = request.get_json(silent=True) or {}
        trigger_type = body.get("trigger_type", "manual")
        if trigger_type not in TRIGGER_TYPES:
            return jsonify({"error": f"trigger_type must be one of {list(TRIGGER_TYPES)}"}), 400
        try:
            run = runner.start(trigger_type)
        except RunAlreadyActive as exc:
            return jsonify({
                "error": "A pipeline run is already in progress.",
                "active_run_id": exc.run_id,
            }), 409
        return jsonify(run_payload(run)), 202

    @bp.get("")
    def list_runs():
        limit = request.args.get("limit", default=20, type=int)
        limit = max(1, min(limit, 100))
        return jsonify({
            "active_run_id": runner.active_run_id,
            "runs": [to_dict(r) for r in store.list_runs(limit)],
        })

    @bp.get("/<int:run_id>")
    def get_run(run_id: int):
        run = store.get_run(run_id)
        if run is None:
            return jsonify({"error": f"Run {run_id} not found."}), 404
        return jsonify(run_payload(run))

    return bp
