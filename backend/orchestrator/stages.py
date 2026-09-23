"""
Stage names, pipeline order, and status values.

These strings are what get written to the run-tracking tables proposed
in Task 6.3 (`pipeline_runs.status`, `pipeline_stage_runs.stage_name`,
`pipeline_stage_runs.status`), so keep them in sync with the schema.
"""

# --- Stage names ---------------------------------------------------------
COLLECTION = "collection"
SECURITY = "security"
SENTIMENT = "sentiment"
TOPIC = "topic"
CLASSIFICATION = "classification"
STANCE = "stance"
AGGREGATION = "aggregation"

# The four analysis agents are independent of each other (none reads
# another's output), so the coordinator runs them in parallel.
ANALYSIS_STAGES = (SENTIMENT, TOPIC, CLASSIFICATION, STANCE)

# Full order: Collection -> Security -> Analysis (parallel) -> Aggregation
PIPELINE_ORDER = (COLLECTION, SECURITY, *ANALYSIS_STAGES, AGGREGATION)


class RunStatus:
    """Values for pipeline_runs.status."""

    RUNNING = "running"
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"  # finished, but a stage failed
    FAILED = "failed"                                # stopped early / no usable output

    FINISHED = (COMPLETED, COMPLETED_WITH_ERRORS, FAILED)


class StageStatus:
    """Values for pipeline_stage_runs.status."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"   # never ran because an earlier stage stopped the run


TRIGGER_TYPES = ("manual", "scheduled")
