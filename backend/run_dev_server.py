"""
A backend for front-end work. Stub agents, in-memory storage, no network.

    python run_dev_server.py               stages take ~1.5s each
    python run_dev_server.py --fast        stages take ~0.2s each
    python run_dev_server.py --fail topic  make a stage fail (repeatable)
    python run_dev_server.py --seed 3      pre-create 3 finished runs

Why this exists: `python app.py` runs the real agents, so starting a run
from the dashboard fetches from the news APIs, downloads article pages a
second apart, and writes to the shared Supabase project. That is minutes
per run and real side effects on the team's data — too slow and too
consequential to sit behind a UI you are iterating on.

This serves the same endpoints with stub agents against an in-memory
store, so runs finish in seconds and nothing leaves the process. The
stages are deliberately slowed a little so a run actually has a visible
'running' phase to build progress UI against; a stub with no delay goes
from pending to succeeded faster than anything can poll it.

Everything else is the real thing: the same coordinator, the same
sequencing and failure rules, the same routes and JSON shapes.
"""
import argparse
import logging
import sys

from orchestrator import BackgroundRunner, InMemoryRunStore, PipelineCoordinator
from orchestrator.agents import StubAgent, stub_analysis, stub_fallback
from orchestrator.registry import build_default_registry
from orchestrator.stages import ANALYSIS_STAGES, COLLECTION, PIPELINE_ORDER, SECURITY


def build_registry(delay, failing_stages):
    """The default stub registry, but slow enough to watch."""
    registry = build_default_registry(live=False)

    for stage in PIPELINE_ORDER:
        if stage in failing_stages:
            registry.register(stage, StubAgent(f"{stage}_broken", fail_times=-1),
                              fallback=registry.get_fallback(stage))
            continue
        agent = registry.get(stage)
        # Collection and security run one after another; the four analysis
        # stages run at once, so give them a longer delay to make the
        # parallelism visible rather than a blur.
        agent.delay = delay * (2 if stage in ANALYSIS_STAGES else 1)
        fallback = registry.get_fallback(stage)
        if fallback is not None:
            fallback.delay = delay
    return registry


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--fast", action="store_true", help="0.2s per stage instead of 1.5s")
    parser.add_argument("--fail", choices=PIPELINE_ORDER, action="append", default=[],
                        help="make this stage fail every time (can repeat)")
    parser.add_argument("--seed", type=int, default=0, metavar="N",
                        help="pre-create N finished runs so lists aren't empty")
    parser.add_argument("--port", type=int, default=5000)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    delay = 0.2 if args.fast else 1.5
    store = InMemoryRunStore()
    coordinator = PipelineCoordinator(
        build_registry(delay, set(args.fail)), store,
        # Don't sit through real backoff waits in a dev server.
        sleep=lambda seconds: None,
    )

    for _ in range(args.seed):
        seed = PipelineCoordinator(
            build_registry(0, set(args.fail)), store, sleep=lambda seconds: None,
        )
        seed.run("scheduled")

    from app import create_app
    from orchestrator.topic_counts import unavailable

    app = create_app(
        runner=BackgroundRunner(coordinator),
        read_topics=lambda: unavailable("The dev server doesn't read the database, so there are no topic counts."),
    )
    print(f"\n  Dev backend (stub agents, in-memory) on http://localhost:{args.port}")
    print(f"  {delay}s per stage{' — failing: ' + ', '.join(args.fail) if args.fail else ''}")
    print(f"  {args.seed} seeded run(s). Nothing here touches Supabase or the network.\n")
    app.run(debug=False, port=args.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
