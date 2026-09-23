"""
Run the pipeline once from the terminal and print what happened.

    python run_pipeline.py                      normal run (stub agents)
    python run_pipeline.py --fail topic         topic agent always fails
    python run_pipeline.py --fail sentiment     sentiment fails -> fallback takes over
    python run_pipeline.py --fail security      screening fails -> analysis skipped
    python run_pipeline.py --flaky collection   fails once, succeeds on retry
    python run_pipeline.py --verbose            also show the coordinator's log

Uses stub agents and in-memory storage, so it needs no database.
Backoff waits are shortened so the demo doesn't sit idle.
"""
import argparse
import logging
import sys
import textwrap
import time

from orchestrator import InMemoryRunStore, PipelineCoordinator, build_default_registry
from orchestrator.agents import Agent, StubAgent
from orchestrator.stages import PIPELINE_ORDER, RunStatus


class FlakyOnce(Agent):
    """Fails on its first call (like a network blip), then behaves normally."""

    def __init__(self, inner: Agent) -> None:
        self.inner = inner
        self.name = f"{inner.name}_flaky"
        self._failed_once = False

    def run(self, ctx):
        if not self._failed_once:
            self._failed_once = True
            raise ConnectionError("simulated network blip")
        return self.inner.run(ctx)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run the ClassroomScope pipeline once with stub agents.")
    parser.add_argument("--fail", choices=PIPELINE_ORDER, action="append", default=[],
                        help="make this stage's agent fail every time (can repeat)")
    parser.add_argument("--flaky", choices=PIPELINE_ORDER, action="append", default=[],
                        help="make this stage fail once, then succeed (can repeat)")
    parser.add_argument("--verbose", action="store_true", help="show the coordinator's log messages")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO if args.verbose else logging.CRITICAL,
                        format="    log: %(message)s")

    registry = build_default_registry()
    for stage in args.flaky:
        registry.register(stage, FlakyOnce(registry.get(stage)), fallback=registry.get_fallback(stage))
    for stage in args.fail:
        registry.register(stage, StubAgent(f"{stage}_broken", fail_times=-1),
                          fallback=registry.get_fallback(stage))

    coordinator = PipelineCoordinator(
        registry, InMemoryRunStore(), sleep=lambda seconds: time.sleep(min(seconds, 0.3)),
    )
    run = coordinator.run("manual")

    print(f"\nClassroomScope pipeline - run #{run.id} ({run.trigger_type})")
    print(f"  {'Stage':<16}{'Status':<12}{'Attempts':<10}")
    print(f"  {'-' * 15:<16}{'-' * 11:<12}{'-' * 8:<10}")
    for stage in coordinator.store.list_stages(run.id):
        attempts = str(stage.attempt) if stage.attempt else "-"
        print(f"  {stage.stage_name:<16}{stage.status:<12}{attempts:<10}")
        if stage.error_detail:
            for line in textwrap.wrap(stage.error_detail, width=70):
                print(f"      {line}")

    print(f"\nResult: {run.status}")
    if run.notes:
        for line in textwrap.wrap(run.notes, width=74):
            print(f"  {line}")
    print()
    return 1 if run.status == RunStatus.FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
