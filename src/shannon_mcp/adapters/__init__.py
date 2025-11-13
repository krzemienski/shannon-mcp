"""
Adapters for Shannon MCP Server.

This package provides adapter layers for integrating external systems
and frameworks with Shannon MCP.
"""

from .agent_sdk import AgentSDKAdapter, SDKAgent, ExecutionMode

__all__ = [
    'AgentSDKAdapter',
    'SDKAgent',
    'ExecutionMode',
]
