/**
 * Data Access Layer — the ONLY file allowed to call the backend.
 *
 * Per the design doc (Section 3, "Why this structure"): every component
 * goes through this client rather than calling fetch() directly, so
 * auth headers, error handling, and response parsing live in one place.
 *
 * STATUS: skeleton only.
 *   - getResults() is wired to the real stub endpoint and works.
 *   - Auth token attachment, retries, and export calls are NOT built yet.
 */

const BASE_URL = "http://localhost:5000/api/v1";

async function request(path, options = {}) {
  // TODO: attach session token from auth context once SS-5 login exists
  const res = await fetch(`${BASE_URL}${path}`, options);

  if (!res.ok) {
    // TODO: standardize error shape once the backend returns real error bodies
    throw new Error(`API error ${res.status} on ${path}`);
  }
  return res.json();
}

export async function checkHealth() {
  return request("/health");
}

export async function getResults(/* filters */) {
  // TODO: serialize filters (date range, source, topic) as query params
  return request("/results");
}

// TODO: getRunStatus() — for the run-status poller (Section 4 of design doc)
// TODO: triggerCollection() — admin-only, needs auth token
// TODO: exportResults(format) — CSV / PDF export
