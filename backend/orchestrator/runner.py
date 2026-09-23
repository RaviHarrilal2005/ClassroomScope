"""
Runs the pipeline on a background thread.

A full run takes minutes, far longer than an HTTP request should wait.
So the API creates the run, hands it to this runner, and responds right
away with the run ID. The dashboard then polls the run's status.

Only one run may be active at a time — two collection runs at once
would fetch and store the same articles twice.

Known limitations (fine for now, listed in docs/pipeline-coordinator.md):
  * Runs happen inside the Flask process. If the server stops mid-run,
    that run is left at 'running' in the database.
  * A stuck agent blocks its run; per-stage timeouts are a next step.
"""
from __future__ import annotations

import logging
import threading
from typing import Optional

from .coordinator import PipelineCoordinator
from .models import RunRecord

logger = logging.getLogger(__name__)


class RunAlreadyActive(Exception):
    def __init__(self, run_id: int) -> None:
        super().__init__(f"Run {run_id} is already in progress")
        self.run_id = run_id


class BackgroundRunner:
    def __init__(self, coordinator: PipelineCoordinator) -> None:
        self.coordinator = coordinator
        self._lock = threading.Lock()
        self._active_run_id: Optional[int] = None
        self._thread: Optional[threading.Thread] = None

    @property
    def store(self):
        return self.coordinator.store

    @property
    def active_run_id(self) -> Optional[int]:
        with self._lock:
            return self._active_run_id

    def start(self, trigger_type: str = "manual") -> RunRecord:
        """Create a run and execute it in the background. Returns immediately."""
        with self._lock:
            if self._active_run_id is not None:
                raise RunAlreadyActive(self._active_run_id)
            run = self.coordinator.start_run(trigger_type)
            self._active_run_id = run.id
            self._thread = threading.Thread(
                target=self._execute, args=(run.id,),
                name=f"pipeline-run-{run.id}", daemon=True,
            )
            self._thread.start()
            return run

    def wait(self, timeout: Optional[float] = None) -> bool:
        """Block until the current run finishes. Returns False on timeout."""
        thread = self._thread
        if thread is None:
            return True
        thread.join(timeout)
        return not thread.is_alive()

    def _execute(self, run_id: int) -> None:
        try:
            self.coordinator.execute(run_id)
        except Exception:
            logger.exception("Run %s: background execution failed", run_id)
        finally:
            with self._lock:
                self._active_run_id = None
