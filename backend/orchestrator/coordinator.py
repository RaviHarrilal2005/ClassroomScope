"""
Pipeline coordinator — runs the agents in order and handles failures.

    Collection -> Security -> Analysis (4 agents in parallel) -> Aggregation

Failure rules
  Collection   Critical. Retried with backoff; if it still fails the run
               stops, because there is nothing to analyze.
  Security     Critical and fails closed. If screening fails, analysis is
               skipped so unscreened content is never analyzed.
  Analysis     Independent. One agent failing doesn't stop the others.
               Each stage retries, then uses its fallback agent if one
               is registered.
  Aggregation  Runs if at least one analysis stage succeeded, combining
               whatever results exist.

Every run ends in a recorded final state (completed,
completed_with_errors, or failed) — never left stuck at 'running'.

The coordinator moves control, not data: agents read and write the
database themselves, and the coordinator records what happened.
"""
from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Dict, Mapping, Optional

from .agents import Output
from .models import RunContext, RunRecord, StageRecord, utcnow
from .registry import AgentRegistry
from .retry import RetryPolicy, default_policies
from .stages import (
    AGGREGATION,
    ANALYSIS_STAGES,
    COLLECTION,
    PIPELINE_ORDER,
    SECURITY,
    TRIGGER_TYPES,
    RunStatus,
    StageStatus,
)
from .store import RunStore

logger = logging.getLogger(__name__)

MAX_ERROR_LENGTH = 500  # keep error_detail readable on the dashboard


class ContractError(Exception):
    """An agent returned output that doesn't match the agent contract."""


def describe(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {exc}"


def truncate(text: Optional[str]) -> Optional[str]:
    if text is None or len(text) <= MAX_ERROR_LENGTH:
        return text
    return text[: MAX_ERROR_LENGTH - 3] + "..."


class PipelineCoordinator:
    def __init__(
        self,
        registry: AgentRegistry,
        store: RunStore,
        policies: Optional[Mapping[str, RetryPolicy]] = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        # Fail at startup, not halfway through a run.
        missing = registry.missing(PIPELINE_ORDER)
        if missing:
            raise ValueError("No agent registered for stage(s): " + ", ".join(missing))

        self.registry = registry
        self.store = store
        self.policies: Dict[str, RetryPolicy] = default_policies()
        if policies:
            self.policies.update(policies)
        self._sleep = sleep  # injectable so tests don't actually wait

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def start_run(self, trigger_type: str = "manual") -> RunRecord:
        """
        Create the run record plus one 'pending' row per stage.

        Pre-creating every stage row means the dashboard can show the
        full list of stages (and which are still pending) from the start.
        Does not execute anything — see execute().
        """
        if trigger_type not in TRIGGER_TYPES:
            raise ValueError(f"trigger_type must be one of {TRIGGER_TYPES}, got '{trigger_type}'")
        run = self.store.create_run(trigger_type)
        for stage in PIPELINE_ORDER:
            self.store.create_stage(run.id, stage)
        logger.info("Run %s created (%s)", run.id, trigger_type)
        return run

    def execute(self, run_id: int) -> RunRecord:
        """Run every stage for an existing run. Returns the final run record."""
        run = self.store.get_run(run_id)
        if run is None:
            raise ValueError(f"Run {run_id} does not exist")
        if run.status != RunStatus.RUNNING:
            raise ValueError(f"Run {run_id} already finished with status '{run.status}'")

        try:
            return self._execute(run_id)
        except Exception as exc:
            # A bug in the coordinator or a storage failure. Record it so
            # the run doesn't sit at 'running' forever.
            logger.exception("Run %s: coordinator error", run_id)
            self._abort(run_id, f"Coordinator error: {describe(exc)}")
            return self._reload(run_id)

    def run(self, trigger_type: str = "manual") -> RunRecord:
        """Create and execute a run synchronously (used by the CLI and tests)."""
        return self.execute(self.start_run(trigger_type).id)

    # ------------------------------------------------------------------
    # Sequencing
    # ------------------------------------------------------------------
    def _execute(self, run_id: int) -> RunRecord:
        stages = {s.stage_name: s for s in self.store.list_stages(run_id)}
        ctx = RunContext(run_id=run_id)
        logger.info("Run %s started", run_id)

        # 1. Collection ---------------------------------------------------
        output = self._run_stage(stages[COLLECTION], ctx)
        if output is None:
            return self._finish(
                run_id, RunStatus.FAILED,
                "Collection failed after all retries, so there was nothing to analyze.",
            )
        ctx.article_ids = list(dict.fromkeys(output["article_ids"]))  # de-duplicate, keep order
        collected = len(ctx.article_ids)
        self.store.update_run(run_id, articles_collected=collected)
        if collected == 0:
            return self._finish(run_id, RunStatus.COMPLETED, "No new articles were collected.")

        # 2. Security (fail closed) ----------------------------------------
        output = self._run_stage(stages[SECURITY], ctx)
        if output is None:
            return self._finish(
                run_id, RunStatus.FAILED,
                "Security screening failed, so analysis was skipped to avoid "
                "analyzing unscreened content.",
            )
        ctx.approved_ids = list(dict.fromkeys(output["approved_ids"]))
        approved = len(ctx.approved_ids)
        summary = f"Collected {collected} article(s); {approved} passed security screening."
        if approved == 0:
            return self._finish(
                run_id, RunStatus.COMPLETED,
                summary + " Nothing left to analyze.",
            )

        # 3. Analysis (parallel) --------------------------------------------
        outcomes = self._run_analysis(stages, ctx)
        ctx.completed_analysis = [s for s in ANALYSIS_STAGES if outcomes[s] is not None]
        failed = [s for s in ANALYSIS_STAGES if outcomes[s] is None]
        if not ctx.completed_analysis:
            return self._finish(
                run_id, RunStatus.FAILED,
                summary + " Every analysis stage failed, so there was nothing to aggregate.",
            )

        # 4. Aggregation ------------------------------------------------------
        if self._run_stage(stages[AGGREGATION], ctx) is None:
            failed.append(AGGREGATION)

        if failed:
            return self._finish(
                run_id, RunStatus.COMPLETED_WITH_ERRORS,
                summary + f" Failed stage(s): {', '.join(failed)}. "
                "Results from the other stages were kept.",
            )
        return self._finish(run_id, RunStatus.COMPLETED, summary)

    def _run_analysis(self, stages: Dict[str, StageRecord], ctx: RunContext) -> Dict[str, Optional[Output]]:
        """Run the four analysis stages at the same time and wait for all of them."""
        outcomes: Dict[str, Optional[Output]] = {}
        with ThreadPoolExecutor(
            max_workers=len(ANALYSIS_STAGES),
            thread_name_prefix=f"run{ctx.run_id}-analysis",
        ) as pool:
            futures = {s: pool.submit(self._run_stage, stages[s], ctx) for s in ANALYSIS_STAGES}
            for stage, future in futures.items():
                try:
                    outcomes[stage] = future.result()
                except Exception as exc:
                    # _run_stage already handles agent errors, so reaching
                    # here means recording the stage itself failed.
                    logger.exception("Run %s: %s crashed the coordinator thread", ctx.run_id, stage)
                    self._mark_stage(stages[stage].id, StageStatus.FAILED, f"Coordinator error: {describe(exc)}")
                    outcomes[stage] = None
        return outcomes

    # ------------------------------------------------------------------
    # One stage: retry, then fallback, then record the outcome
    # ------------------------------------------------------------------
    def _run_stage(self, record: StageRecord, ctx: RunContext) -> Optional[Output]:
        """Returns the agent's output, or None if the stage failed."""
        stage = record.stage_name
        policy = self.policies.get(stage, RetryPolicy())
        agent = self.registry.get(stage)
        self.store.update_stage(record.id, status=StageStatus.RUNNING, started_at=utcnow())

        last_error = ""
        for attempt in range(1, policy.max_attempts + 1):
            self.store.update_stage(record.id, attempt=attempt)
            try:
                output = agent.run(self._snapshot(ctx))
                self._check_output(stage, output, ctx)
            except Exception as exc:
                last_error = describe(exc)
                logger.warning(
                    "Run %s: %s attempt %d/%d failed: %s",
                    ctx.run_id, stage, attempt, policy.max_attempts, last_error,
                )
                if attempt < policy.max_attempts:
                    self._sleep(policy.delay_after(attempt))
                continue
            self._mark_stage(record.id, StageStatus.SUCCEEDED)
            logger.info("Run %s: %s succeeded (attempt %d)", ctx.run_id, stage, attempt)
            return output

        fallback = self.registry.get_fallback(stage)
        if fallback is not None:
            try:
                output = fallback.run(self._snapshot(ctx))
                self._check_output(stage, output, ctx)
            except Exception as exc:
                last_error += f"; fallback '{fallback.name}' also failed: {describe(exc)}"
            else:
                self._mark_stage(
                    record.id, StageStatus.SUCCEEDED,
                    f"Primary agent failed ({last_error}); fallback '{fallback.name}' was used.",
                )
                logger.info("Run %s: %s succeeded using fallback", ctx.run_id, stage)
                return output

        self._mark_stage(record.id, StageStatus.FAILED, last_error)
        logger.error("Run %s: %s failed: %s", ctx.run_id, stage, last_error)
        return None

    @staticmethod
    def _check_output(stage: str, output: object, ctx: RunContext) -> None:
        """Reject output that breaks the agent contract instead of passing it on."""
        if not isinstance(output, dict):
            raise ContractError(f"expected a dict, got {type(output).__name__}")
        if stage == COLLECTION and not isinstance(output.get("article_ids"), list):
            raise ContractError("collection output needs an 'article_ids' list")
        if stage == SECURITY:
            approved = output.get("approved_ids")
            if not isinstance(approved, list):
                raise ContractError("security output needs an 'approved_ids' list")
            unknown = set(approved) - set(ctx.article_ids)
            if unknown:
                shown = ", ".join(sorted(map(str, unknown))[:5])
                raise ContractError(f"security approved IDs that were never collected: {shown}")

    @staticmethod
    def _snapshot(ctx: RunContext) -> RunContext:
        """Give each agent its own copy so one agent can't change what another sees."""
        return RunContext(
            run_id=ctx.run_id,
            article_ids=list(ctx.article_ids),
            approved_ids=list(ctx.approved_ids),
            completed_analysis=list(ctx.completed_analysis),
        )

    # ------------------------------------------------------------------
    # Recording outcomes
    # ------------------------------------------------------------------
    def _reload(self, run_id: int) -> RunRecord:
        """
        Re-read a run the caller has already validated or just written to.

        get_run is Optional because a caller may ask for any ID; here the row
        has to be there, so a None means it vanished mid-run. Raising says
        that plainly instead of handing a None back as a RunRecord.
        """
        run = self.store.get_run(run_id)
        if run is None:
            raise RuntimeError(f"Run {run_id} disappeared from the store mid-run")
        return run

    def _mark_stage(self, stage_id: int, status: str, error_detail: Optional[str] = None) -> None:
        self.store.update_stage(
            stage_id, status=status, finished_at=utcnow(), error_detail=truncate(error_detail),
        )

    def _finish(self, run_id: int, status: str, notes: Optional[str]) -> RunRecord:
        """Mark stages that never ran as skipped, then close out the run."""
        for stage in self.store.list_stages(run_id):
            if stage.status == StageStatus.PENDING:
                self.store.update_stage(stage.id, status=StageStatus.SKIPPED, finished_at=utcnow())
        self.store.update_run(run_id, status=status, finished_at=utcnow(), notes=truncate(notes))
        logger.info("Run %s finished: %s", run_id, status)
        return self._reload(run_id)

    def _abort(self, run_id: int, notes: str) -> None:
        """Best-effort cleanup after a coordinator error."""
        try:
            for stage in self.store.list_stages(run_id):
                if stage.status == StageStatus.PENDING:
                    self.store.update_stage(stage.id, status=StageStatus.SKIPPED, finished_at=utcnow())
                elif stage.status == StageStatus.RUNNING:
                    self._mark_stage(stage.id, StageStatus.FAILED, "Interrupted by a coordinator error.")
            self.store.update_run(run_id, status=RunStatus.FAILED, finished_at=utcnow(), notes=truncate(notes))
        except Exception:
            logger.exception("Run %s: could not record the failure", run_id)
