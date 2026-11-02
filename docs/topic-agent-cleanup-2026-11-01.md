# Topic-agent cleanup and review - November 1, 2026

Removed only untracked, ignored generated caches and frontend build output. Dependencies, environment files, source code, tests, migrations, model assets and evaluation evidence were retained. Experimental files remain useful for reproducing documented comparisons; lack of production imports alone does not make them unnecessary.

## Removed directories

- `.pytest_cache` (13,006 bytes)
- `backend/.pytest_cache` (22,122 bytes)
- `backend/__pycache__` (7,908 bytes)
- `backend/tests/__pycache__` (494,574 bytes)
- `backend/agents/__pycache__` (30,978 bytes)
- `backend/agents/classification/__pycache__` (13,648 bytes)
- `backend/agents/aggregation/__pycache__` (4,310 bytes)
- `backend/agents/collection/__pycache__` (42,940 bytes)
- `backend/agents/security/__pycache__` (19,991 bytes)
- `backend/agents/security/tests/__pycache__` (593 bytes)
- `backend/agents/topic/__pycache__` (283,525 bytes)
- `backend/agents/sentiment/__pycache__` (15,219 bytes)
- `backend/e2e/__pycache__` (94,253 bytes)
- `backend/orchestrator/__pycache__` (93,143 bytes)
- `frontend/dist` (519,703 bytes)

Total removed: 1,655,913 bytes. Generated directories may reappear when tests or builds run.

## Verification

20 focused tests and 5 subtests passed for saved-model inference, discovery/training exports, LDA benchmark contracts, coordinator/persistence integration and topic counts. Tests used controlled offline inputs; no live database or model-quality evaluation was performed.

## Design review

See `topic-agent-design.md` for the agreed five-category design, student-only T001 scope, current contracts and outstanding implementation work. No production model, catalog, threshold or database records were changed.

## BERTopic-only cleanup

Archived the optional portable language-model classifier, adapter and tests under ignored review/archived-portable-language-model-2026-11-01/. Removed their production selection paths and optional example settings. Historical Mac experiments remain local as requested. Removed three unactivated cluster-count candidate pickle binaries (1,325,545,303 bytes), retaining shared embeddings, scripts, corpus provenance, assignments, metrics, samples and reports. Active model and database were not changed. Deployment files, migrations, current documentation and the model required for BERTopic were retained.

## Local-only scope cleanup

Removed `.dockerignore`, `backend/requirements-topic-cloud.txt`, and the three files in `deploy/topic/` because cloud packaging is outside the required scope. Updated current guide links. Preserved the primary backend requirements, active model, tests, migrations, release documentation and all local experiment archives.
