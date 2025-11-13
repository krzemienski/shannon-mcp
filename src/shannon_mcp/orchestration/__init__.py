"""
Orchestration components for Shannon MCP Server.

This package provides task orchestration and intelligent routing
for SDK agents, plus multi-agent collaboration patterns.
"""

from .task_orchestrator import TaskOrchestrator, OrchestrationStrategy
from .collaboration_patterns import (
    CollaborationPattern,
    CollaborationStage,
    CollaborationResult,
    PipelineCollaboration,
    ParallelCollaboration,
    HierarchicalCollaboration,
    MapReduceCollaboration,
    CollaborationManager,
)

__all__ = [
    'TaskOrchestrator',
    'OrchestrationStrategy',
    'CollaborationPattern',
    'CollaborationStage',
    'CollaborationResult',
    'PipelineCollaboration',
    'ParallelCollaboration',
    'HierarchicalCollaboration',
    'MapReduceCollaboration',
    'CollaborationManager',
]
