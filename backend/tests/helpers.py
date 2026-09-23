"""Small helpers shared by the test modules."""
from orchestrator import BackgroundRunner, InMemoryRunStore, PipelineCoordinator, build_default_registry
from orchestrator.agents import StubAgent


def stages_by_name(coordinator, run_id):
    return {s.stage_name: s for s in coordinator.store.list_stages(run_id)}


def failing(name="broken"):
    return StubAgent(name, fail_times=-1)


def build_client(registry=None):
    """Flask test client wired to a coordinator that doesn't actually wait between retries."""
    from app import create_app

    coordinator = PipelineCoordinator(
        registry or build_default_registry(), InMemoryRunStore(), sleep=lambda seconds: None,
    )
    runner = BackgroundRunner(coordinator)
    app = create_app(runner=runner)
    app.testing = True
    return app.test_client(), runner
