"""
ClassroomScope pipeline orchestrator (SS-4).

Runs the agents in order — Collection -> Security -> Analysis -> Aggregation —
and records each run's progress. See docs/pipeline-coordinator.md.
"""
from .coordinator import ContractError, PipelineCoordinator
from .registry import AgentRegistry, build_default_registry
from .runner import BackgroundRunner, RunAlreadyActive
from .store import InMemoryRunStore, RunStore

__all__ = [
    "AgentRegistry",
    "BackgroundRunner",
    "ContractError",
    "InMemoryRunStore",
    "PipelineCoordinator",
    "RunAlreadyActive",
    "RunStore",
    "build_default_registry",
]
