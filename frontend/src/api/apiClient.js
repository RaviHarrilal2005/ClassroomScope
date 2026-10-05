/**
 * Data Access Layer — the ONLY file allowed to call the backend.
 *
 * Per the design doc (Section 3, "Why this structure"): every component
 * goes through this client rather than calling fetch() directly, so
 * auth headers, error handling, and response parsing live in one place.
 *
 * STATUS:
 *   - getResults() is wired to the /results endpoint. Its top_topics is
 *     real, counted from topic_results, and says when it is unavailable;
 *     sentiment and articles are still hardcoded until the aggregation
 *     agent exists. Treat those two as placeholder.
 *   - The run endpoints below are real: they read pipeline_runs and
 *     pipeline_stage_runs, and return genuine rows.
 *   - Auth token attachment, retries, and export calls are NOT built yet.
 */

const BASE_URL = "http://localhost:5000/api/v1";

/** Thrown for a non-2xx response, carrying the status and the parsed body. */
export class ApiError extends Error {
  constructor(message, status, body) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body ?? null;
  }
}

async function request(path, options = {}) {
  // TODO: attach session token from auth context once SS-5 login exists
  let res;
  try {
    res = await fetch(`${BASE_URL}${path}`, options);
  } catch (cause) {
    // fetch only rejects on a transport failure, which almost always means
    // the backend is not running. Saying so beats "Failed to fetch".
    throw new ApiError(
      `Cannot reach the backend at ${BASE_URL}. Is it running? (python app.py)`,
      0,
      null
    );
  }

  // Error responses carry a JSON body worth surfacing — 409 includes the
  // active run's id, 404 explains which run was missing.
  let body = null;
  if (res.status !== 204) {
    body = await res.json().catch(() => null);
  }

  if (!res.ok) {
    throw new ApiError(
      body?.error || `API error ${res.status} on ${path}`,
      res.status,
      body
    );
  }
  return body;
}

export async function checkHealth() {
  return request("/health");
}

export async function getResults(/* filters */) {
  // TODO: serialize filters (date range, source, topic) as query params
  return request("/results");
}

// --- pipeline runs ----------------------------------------------------

/** Recent runs, newest first: { active_run_id, runs: [...] }. */
export async function getRuns(limit = 20) {
  return request(`/runs?limit=${encodeURIComponent(limit)}`);
}

/** One run with its stage-by-stage status. This is what the poller calls. */
export async function getRun(runId) {
  return request(`/runs/${runId}`);
}

/**
 * Start a run. Returns immediately with the run at 'running' — the
 * pipeline continues on the server, so the caller polls getRun().
 *
 * Throws ApiError with status 409 when a run is already in progress;
 * err.body.active_run_id says which one.
 */
export async function startRun(triggerType = "manual") {
  // TODO(auth): admin-only once login (SS-5) exists — the backend has the
  // matching TODO on the endpoint.
  return request("/runs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ trigger_type: triggerType }),
  });
}

// TODO: exportResults(format) — CSV / PDF export
