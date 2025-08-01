"""
Functional tests for agent system with real task execution.
"""

import pytest
import asyncio
import json
import time
from typing import List, Dict, Any

from shannon_mcp.managers.agent import AgentManager
from shannon_mcp.managers.session import SessionManager
from shannon_mcp.managers.binary import BinaryManager


class TestAgentSystem:
    """Test agent system with real Claude Code integration."""
    
    @pytest.fixture
    async def agent_setup(self):
        """Set up agent manager with session support."""
        binary_manager = BinaryManager()
        binaries = await binary_manager.discover_binaries()
        
        if not binaries:
            pytest.skip("No Claude Code binary found")
        
        session_manager = SessionManager(binary_manager=binary_manager)
        agent_manager = AgentManager(session_manager=session_manager)
        
        # Initialize agent database
        await agent_manager.initialize()
        
        yield agent_manager, session_manager
        
        # Cleanup
        await agent_manager.cleanup()
    
    @pytest.mark.asyncio
    async def test_agent_registration(self, agent_setup):
        """Test registering and listing agents."""
        agent_manager, _ = agent_setup
        
        # Register test agents
        agents = [
            {
                "name": "Code Reviewer",
                "description": "Reviews code for quality and best practices",
                "capabilities": ["code_review", "security_check", "performance_analysis"],
                "category": "quality"
            },
            {
                "name": "Test Generator",
                "description": "Generates unit and integration tests",
                "capabilities": ["unit_tests", "integration_tests", "test_coverage"],
                "category": "testing"
            },
            {
                "name": "Documentation Writer",
                "description": "Creates and updates documentation",
                "capabilities": ["api_docs", "user_guides", "code_comments"],
                "category": "documentation"
            }
        ]
        
        registered_ids = []
        for agent in agents:
            agent_id = await agent_manager.register_agent(agent)
            registered_ids.append(agent_id)
            print(f"\nRegistered agent: {agent['name']} (ID: {agent_id})")
        
        # List all agents
        all_agents = await agent_manager.list_agents()
        print(f"\nTotal agents: {len(all_agents)}")
        
        # Verify registration
        assert len(registered_ids) == len(agents)
        
        # List by category
        quality_agents = await agent_manager.list_agents(category="quality")
        assert len(quality_agents) >= 1
        assert quality_agents[0]["name"] == "Code Reviewer"
    
    @pytest.mark.asyncio
    async def test_agent_task_assignment(self, agent_setup):
        """Test assigning tasks to appropriate agents."""
        agent_manager, _ = agent_setup
        
        # Register specialized agents
        await agent_manager.register_agent({
            "name": "Python Expert",
            "description": "Expert in Python development",
            "capabilities": ["python", "debugging", "optimization"],
            "expertise_score": 0.9
        })
        
        await agent_manager.register_agent({
            "name": "General Developer",
            "description": "General programming knowledge",
            "capabilities": ["programming", "debugging"],
            "expertise_score": 0.6
        })
        
        # Test task assignment
        task = {
            "description": "Debug Python async/await issue",
            "required_capabilities": ["python", "debugging"],
            "priority": "high"
        }
        
        # Get best agent for task
        assigned_agent = await agent_manager.assign_task(task)
        
        print(f"\nTask: {task['description']}")
        print(f"Assigned to: {assigned_agent['name']}")
        print(f"Score: {assigned_agent.get('assignment_score', 0)}")
        
        # Should assign to Python Expert
        assert assigned_agent["name"] == "Python Expert"
        assert assigned_agent["assignment_score"] > 0.8
    
    @pytest.mark.asyncio
    async def test_agent_execution(self, agent_setup):
        """Test executing tasks with agents."""
        agent_manager, session_manager = agent_setup
        
        # Register and configure agent
        agent_id = await agent_manager.register_agent({
            "name": "Code Analyzer",
            "description": "Analyzes code structure and quality",
            "capabilities": ["analysis", "metrics", "suggestions"],
            "session_config": {
                "model": "claude-3-opus-20240229",
                "temperature": 0.3
            }
        })
        
        # Create task
        task = {
            "agent_id": agent_id,
            "type": "analyze_code",
            "input": """
def calculate_fibonacci(n):
    if n <= 1:
        return n
    return calculate_fibonacci(n-1) + calculate_fibonacci(n-2)
            """,
            "instructions": "Analyze this Fibonacci implementation and suggest improvements."
        }
        
        # Execute task
        execution_id = await agent_manager.execute_task(task)
        
        print(f"\nExecuting task: {execution_id}")
        
        # Wait for completion
        max_wait = 30  # seconds
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            status = await agent_manager.get_execution_status(execution_id)
            print(f"Status: {status['status']}")
            
            if status["status"] in ["completed", "failed"]:
                break
            
            await asyncio.sleep(1)
        
        # Get results
        result = await agent_manager.get_execution_result(execution_id)
        
        print(f"\nExecution result:")
        print(f"  Status: {result['status']}")
        print(f"  Duration: {result.get('duration', 0):.2f}s")
        print(f"  Output preview: {str(result.get('output', ''))[:200]}...")
        
        assert result["status"] == "completed"
        assert result["output"] is not None
        assert "fibonacci" in str(result["output"]).lower()
    
    @pytest.mark.asyncio
    async def test_multi_agent_collaboration(self, agent_setup):
        """Test multiple agents working together."""
        agent_manager, session_manager = agent_setup
        
        # Register collaborating agents
        agents = {
            "architect": await agent_manager.register_agent({
                "name": "System Architect",
                "description": "Designs system architecture",
                "capabilities": ["design", "architecture", "planning"]
            }),
            "developer": await agent_manager.register_agent({
                "name": "Developer",
                "description": "Implements code based on designs",
                "capabilities": ["coding", "implementation", "testing"]
            }),
            "reviewer": await agent_manager.register_agent({
                "name": "Code Reviewer",
                "description": "Reviews implementation quality",
                "capabilities": ["review", "quality", "feedback"]
            })
        }
        
        # Multi-step collaborative task
        project = {
            "name": "Simple Calculator API",
            "steps": [
                {
                    "agent": "architect",
                    "task": "Design a REST API for a calculator with add, subtract, multiply, divide operations"
                },
                {
                    "agent": "developer",
                    "task": "Implement the calculator API based on the architecture design",
                    "depends_on": 0
                },
                {
                    "agent": "reviewer",
                    "task": "Review the implementation and provide feedback",
                    "depends_on": 1
                }
            ]
        }
        
        # Execute collaborative workflow
        results = []
        
        for i, step in enumerate(project["steps"]):
            agent_id = agents[step["agent"]]
            
            # Prepare context from previous steps
            context = ""
            if "depends_on" in step:
                prev_result = results[step["depends_on"]]
                context = f"Previous step output:\n{prev_result['output']}\n\n"
            
            # Execute step
            task = {
                "agent_id": agent_id,
                "type": "collaborative_task",
                "input": context + step["task"],
                "step": i + 1,
                "total_steps": len(project["steps"])
            }
            
            execution_id = await agent_manager.execute_task(task)
            
            # Wait for completion
            await asyncio.sleep(2)  # Give it time to process
            
            result = await agent_manager.get_execution_result(execution_id)
            results.append(result)
            
            print(f"\nStep {i+1} - {step['agent']}:")
            print(f"  Status: {result['status']}")
            print(f"  Output preview: {str(result.get('output', ''))[:150]}...")
        
        # Verify collaboration
        assert len(results) == len(project["steps"])
        assert all(r["status"] == "completed" for r in results)
        
        # Check inter-agent references
        assert any("design" in str(r.get("output", "")).lower() for r in results)
        assert any("implement" in str(r.get("output", "")).lower() for r in results)
        assert any("review" in str(r.get("output", "")).lower() for r in results)
    
    @pytest.mark.asyncio
    async def test_agent_learning(self, agent_setup):
        """Test agent learning from task outcomes."""
        agent_manager, _ = agent_setup
        
        # Register learning agent
        agent_id = await agent_manager.register_agent({
            "name": "Learning Agent",
            "description": "Agent that improves with experience",
            "capabilities": ["learning", "adaptation"],
            "enable_learning": True
        })
        
        # Execute similar tasks multiple times
        task_template = {
            "agent_id": agent_id,
            "type": "classification",
            "feedback_enabled": True
        }
        
        test_cases = [
            {"input": "Python code with async/await", "expected": "async", "actual": None},
            {"input": "JavaScript Promise handling", "expected": "promise", "actual": None},
            {"input": "Python asyncio usage", "expected": "async", "actual": None},
            {"input": "C# Task.Run example", "expected": "task", "actual": None}
        ]
        
        # First pass - establish baseline
        print("\nFirst pass (learning):")
        for i, test in enumerate(test_cases):
            task = {**task_template, "input": test["input"]}
            execution_id = await agent_manager.execute_task(task)
            
            await asyncio.sleep(1)
            result = await agent_manager.get_execution_result(execution_id)
            
            # Provide feedback
            feedback = {
                "execution_id": execution_id,
                "correct": test["expected"] in str(result.get("output", "")).lower(),
                "expected": test["expected"]
            }
            
            await agent_manager.provide_feedback(feedback)
            test_cases[i]["actual"] = result.get("output", "")
            
            print(f"  Case {i+1}: {'✓' if feedback['correct'] else '✗'}")
        
        # Get agent metrics after learning
        metrics = await agent_manager.get_agent_metrics(agent_id)
        
        print(f"\nAgent metrics after learning:")
        print(f"  Total executions: {metrics.get('total_executions', 0)}")
        print(f"  Success rate: {metrics.get('success_rate', 0):.2%}")
        print(f"  Average confidence: {metrics.get('avg_confidence', 0):.2f}")
        
        assert metrics["total_executions"] >= len(test_cases)
    
    @pytest.mark.asyncio
    async def test_agent_specialization(self, agent_setup):
        """Test agent specialization for specific domains."""
        agent_manager, _ = agent_setup
        
        # Register specialized agents
        specialists = [
            {
                "name": "Frontend Specialist",
                "description": "Expert in React, Vue, and modern frontend",
                "capabilities": ["react", "vue", "css", "typescript"],
                "domain": "frontend",
                "expertise_keywords": ["component", "hooks", "state", "props"]
            },
            {
                "name": "Backend Specialist",
                "description": "Expert in APIs, databases, and server architecture",
                "capabilities": ["api", "database", "microservices", "security"],
                "domain": "backend",
                "expertise_keywords": ["endpoint", "query", "authentication", "scaling"]
            },
            {
                "name": "DevOps Specialist",
                "description": "Expert in CI/CD, containers, and infrastructure",
                "capabilities": ["docker", "kubernetes", "ci/cd", "monitoring"],
                "domain": "devops",
                "expertise_keywords": ["deploy", "container", "pipeline", "orchestration"]
            }
        ]
        
        for spec in specialists:
            await agent_manager.register_agent(spec)
        
        # Test domain-specific task routing
        test_tasks = [
            {
                "description": "Create a React component with useState hook",
                "expected_domain": "frontend"
            },
            {
                "description": "Design RESTful API with JWT authentication",
                "expected_domain": "backend"
            },
            {
                "description": "Set up Docker container with Kubernetes deployment",
                "expected_domain": "devops"
            }
        ]
        
        print("\nDomain-specific task routing:")
        for task in test_tasks:
            assigned = await agent_manager.assign_task({
                "description": task["description"],
                "auto_detect_domain": True
            })
            
            print(f"\nTask: {task['description']}")
            print(f"  Assigned to: {assigned['name']}")
            print(f"  Domain: {assigned.get('domain', 'unknown')}")
            
            assert assigned["domain"] == task["expected_domain"]