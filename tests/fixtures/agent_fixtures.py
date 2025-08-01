"""
Agent Manager test fixtures.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
import uuid

from shannon_mcp.models.agent import Agent, AgentCategory


class AgentFixtures:
    """Fixtures for Agent Manager testing."""
    
    # Predefined agent templates
    AGENT_TEMPLATES = {
        "Architecture Agent": {
            "category": AgentCategory.CORE,
            "description": "Core system architecture and design patterns expert",
            "system_prompt": """You are the Architecture Agent for Shannon MCP.
            Your expertise includes system design, architectural patterns, and component integration.
            Focus on scalability, maintainability, and clean architecture principles.""",
            "capabilities": ["system_design", "api_design", "component_integration", "architecture_review"]
        },
        "Testing Agent": {
            "category": AgentCategory.QUALITY,
            "description": "Testing strategy and test implementation expert",
            "system_prompt": """You are the Testing Agent for Shannon MCP.
            You specialize in test design, coverage analysis, and quality assurance.
            Focus on comprehensive testing strategies including unit, integration, and e2e tests.""",
            "capabilities": ["test_design", "coverage_analysis", "test_automation", "quality_metrics"]
        },
        "Binary Manager Expert": {
            "category": AgentCategory.INFRASTRUCTURE,
            "description": "Claude Code binary discovery and management specialist",
            "system_prompt": """You are the Binary Manager Expert for Shannon MCP.
            You handle binary discovery, version management, and update mechanisms.
            Focus on cross-platform compatibility and efficient discovery strategies.""",
            "capabilities": ["binary_discovery", "version_management", "platform_compatibility", "update_handling"]
        },
        "Security Agent": {
            "category": AgentCategory.QUALITY,
            "description": "Security analysis and best practices enforcement",
            "system_prompt": """You are the Security Agent for Shannon MCP.
            You ensure secure coding practices, identify vulnerabilities, and implement security measures.
            Focus on input validation, authentication, and secure communication.""",
            "capabilities": ["security_audit", "vulnerability_assessment", "secure_coding", "threat_modeling"]
        }
    }
    
    @staticmethod
    def create_mock_agent(
        name: Optional[str] = None,
        category: Optional[AgentCategory] = None,
        agent_id: Optional[str] = None
    ) -> Agent:
        """Create a mock agent."""
        if not agent_id:
            agent_id = f"agent_{uuid.uuid4().hex[:8]}"
        
        if name and name in AgentFixtures.AGENT_TEMPLATES:
            template = AgentFixtures.AGENT_TEMPLATES[name]
            category = template["category"]
        else:
            if not name:
                name = f"Test Agent {uuid.uuid4().hex[:6]}"
            if not category:
                category = AgentCategory.SPECIALIZED
            
            template = {
                "description": f"Test agent for {category.value} tasks",
                "system_prompt": f"You are {name}. Assist with {category.value} tasks.",
                "capabilities": ["test", "debug", "analyze"]
            }
        
        return Agent(
            id=agent_id,
            name=name,
            description=template["description"],
            system_prompt=template["system_prompt"],
            category=category,
            capabilities=template["capabilities"],
            created_at=datetime.now(timezone.utc),
            metadata={
                "version": "1.0.0",
                "author": "Test Suite",
                "priority": 5
            }
        )
    
    @staticmethod
    def create_agent_collection() -> List[Agent]:
        """Create a collection of predefined agents."""
        agents = []
        
        for name, template in AgentFixtures.AGENT_TEMPLATES.items():
            agent = AgentFixtures.create_mock_agent(name=name)
            agents.append(agent)
        
        # Add some random specialized agents
        for i in range(3):
            agent = AgentFixtures.create_mock_agent(
                name=f"Specialized Agent {i+1}",
                category=AgentCategory.SPECIALIZED
            )
            agents.append(agent)
        
        return agents
    
    @staticmethod
    def create_agent_conversation(agent: Agent, messages: int = 5) -> List[Dict[str, Any]]:
        """Create a mock conversation with an agent."""
        conversation = []
        
        # Initial context
        conversation.append({
            "role": "system",
            "content": agent.system_prompt,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        # User query
        conversation.append({
            "role": "user",
            "content": f"Help me with a task related to {agent.capabilities[0]}",
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        # Agent responses
        for i in range(messages - 2):
            conversation.append({
                "role": "assistant",
                "content": f"[{agent.name}] Step {i+1}: Performing {agent.capabilities[i % len(agent.capabilities)]}...",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "metadata": {
                    "agent_id": agent.id,
                    "capability_used": agent.capabilities[i % len(agent.capabilities)]
                }
            })
        
        return conversation
    
    @staticmethod
    def create_agent_registry_file(path: Path, agents: List[Agent]) -> None:
        """Create an agent registry file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        
        registry = {
            "version": "1.0.0",
            "agents": [agent.dict() for agent in agents],
            "metadata": {
                "created_at": datetime.now(timezone.utc).isoformat(),
                "total_agents": len(agents),
                "categories": {
                    category.value: len([a for a in agents if a.category == category])
                    for category in AgentCategory
                }
            }
        }
        
        path.write_text(json.dumps(registry, indent=2, default=str))
    
    @staticmethod
    def create_agent_performance_metrics(agent: Agent) -> Dict[str, Any]:
        """Create mock performance metrics for an agent."""
        return {
            "agent_id": agent.id,
            "agent_name": agent.name,
            "metrics": {
                "total_invocations": 150,
                "successful_completions": 145,
                "average_duration_seconds": 12.5,
                "total_tokens_used": 25000,
                "error_rate": 0.033,
                "capabilities_usage": {
                    cap: 150 // len(agent.capabilities)
                    for cap in agent.capabilities
                }
            },
            "period": {
                "start": (datetime.now(timezone.utc) - timedelta(days=7)).isoformat(),
                "end": datetime.now(timezone.utc).isoformat()
            }
        }
    
    @staticmethod
    def create_agent_collaboration_graph(agents: List[Agent]) -> Dict[str, Any]:
        """Create a mock collaboration graph between agents."""
        graph = {
            "nodes": [
                {
                    "id": agent.id,
                    "name": agent.name,
                    "category": agent.category.value
                }
                for agent in agents
            ],
            "edges": []
        }
        
        # Create some mock collaborations
        for i in range(len(agents) - 1):
            if i % 2 == 0:  # Not all agents collaborate
                graph["edges"].append({
                    "source": agents[i].id,
                    "target": agents[i + 1].id,
                    "weight": 10 + i,
                    "collaboration_type": "sequential"
                })
        
        return graph