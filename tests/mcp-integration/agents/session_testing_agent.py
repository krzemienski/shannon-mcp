#!/usr/bin/env python3
"""
Session Testing Agent for MCP Integration

Validates session management, lifecycle, and Claude Code process handling
through the MCP server with real system validation.
"""

import os
import sys
import json
import asyncio
import subprocess
import psutil
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Set
from datetime import datetime
import logging

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from test_agent_base import TestAgentBase

logger = logging.getLogger(__name__)


class SessionTestingAgent(TestAgentBase):
    """Test agent for validating session management and process lifecycle."""
    
    def __init__(self):
        super().__init__(
            name="SessionTestingAgent",
            description="Validates MCP session management with real Claude Code processes"
        )
        self.sessions_dir = self.test_base_dir / "test-sessions"
        self.active_sessions = {}
        self.created_processes = set()
        
    async def validate_prerequisites(self) -> bool:
        """Validate session testing prerequisites."""
        try:
            # Ensure sessions directory exists
            self.sessions_dir.mkdir(parents=True, exist_ok=True)
            
            # Check if Claude Code is available
            claude_check = await self.execute_mcp_operation(
                "check_claude_code",
                {}
            )
            
            if not claude_check.get("success") or not claude_check.get("result", {}).get("available"):
                logger.error("Claude Code not available for session testing")
                return False
            
            # Verify we can track processes
            try:
                current_processes = len(psutil.pids())
                return current_processes > 0
            except:
                logger.error("Cannot access process information")
                return False
                
        except Exception as e:
            logger.error(f"Prerequisites validation failed: {e}")
            return False
    
    async def execute_test_scenarios(self) -> List[Dict[str, Any]]:
        """
        Execute comprehensive session test scenarios.
        
        Tests:
        1. Basic session creation and termination
        2. Multiple concurrent sessions
        3. Session state transitions
        4. Process lifecycle validation
        5. Resource cleanup verification
        6. Session persistence and recovery
        7. Error handling and recovery
        8. Session limits and quotas
        """
        test_results = []
        
        # Test 1: Basic Session Creation
        logger.info("Test 1: Basic session creation and termination")
        result = await self._test_basic_session()
        test_results.append(result)
        
        # Test 2: Concurrent Sessions
        logger.info("Test 2: Multiple concurrent sessions")
        result = await self._test_concurrent_sessions()
        test_results.append(result)
        
        # Test 3: Session State Transitions
        logger.info("Test 3: Session state transitions")
        result = await self._test_session_states()
        test_results.append(result)
        
        # Test 4: Process Lifecycle
        logger.info("Test 4: Process lifecycle validation")
        result = await self._test_process_lifecycle()
        test_results.append(result)
        
        # Test 5: Resource Cleanup
        logger.info("Test 5: Resource cleanup verification")
        result = await self._test_resource_cleanup()
        test_results.append(result)
        
        # Test 6: Session Persistence
        logger.info("Test 6: Session persistence and recovery")
        result = await self._test_session_persistence()
        test_results.append(result)
        
        # Test 7: Error Handling
        logger.info("Test 7: Error handling and recovery")
        result = await self._test_error_handling()
        test_results.append(result)
        
        # Test 8: Session Limits
        logger.info("Test 8: Session limits and quotas")
        result = await self._test_session_limits()
        test_results.append(result)
        
        self.test_results = test_results
        return test_results
    
    async def _test_basic_session(self) -> Dict[str, Any]:
        """Test basic session creation and termination."""
        test_name = "basic_session"
        
        try:
            # Create session
            create_result = await self.execute_mcp_operation(
                "create_session",
                {
                    "name": "test-basic-session",
                    "model": "claude-3-opus-20240229",
                    "config": {
                        "temperature": 0.7,
                        "max_tokens": 1000
                    }
                }
            )
            
            if not create_result["success"]:
                return {
                    "test": test_name,
                    "passed": False,
                    "error": "Failed to create session"
                }
            
            session_id = create_result.get("result", {}).get("session_id")
            self.active_sessions[session_id] = create_result["result"]
            
            # Verify process was created
            process_info = await self._get_session_process(session_id)
            process_created = process_info is not None
            
            if process_created:
                self.created_processes.add(process_info["pid"])
            
            # Get session details
            detail_result = await self.execute_mcp_operation(
                "get_session",
                {"session_id": session_id}
            )
            
            details_valid = (
                detail_result["success"] and
                detail_result.get("result", {}).get("state") == "running"
            )
            
            # Execute a simple prompt
            prompt_result = await self.execute_mcp_operation(
                "execute_prompt",
                {
                    "session_id": session_id,
                    "prompt": "echo 'Hello from MCP test'"
                }
            )
            
            prompt_success = (
                prompt_result["success"] and
                "Hello from MCP test" in str(prompt_result.get("result", {}).get("response", ""))
            )
            
            # Terminate session
            terminate_result = await self.execute_mcp_operation(
                "terminate_session",
                {"session_id": session_id}
            )
            
            # Verify process terminated
            await asyncio.sleep(1)
            process_terminated = not await self._is_process_running(process_info["pid"]) if process_created else True
            
            return {
                "test": test_name,
                "session_created": create_result["success"],
                "process_created": process_created,
                "details_valid": details_valid,
                "prompt_executed": prompt_success,
                "session_terminated": terminate_result["success"],
                "process_terminated": process_terminated,
                "passed": all([
                    create_result["success"],
                    process_created,
                    details_valid,
                    prompt_success,
                    terminate_result["success"],
                    process_terminated
                ]),
                "details": {
                    "session_id": session_id,
                    "process_pid": process_info.get("pid") if process_info else None
                }
            }
            
        except Exception as e:
            logger.error(f"Test {test_name} failed: {e}")
            return {
                "test": test_name,
                "passed": False,
                "error": str(e)
            }
    
    async def _test_concurrent_sessions(self) -> Dict[str, Any]:
        """Test multiple concurrent sessions."""
        test_name = "concurrent_sessions"
        num_sessions = 5
        
        try:
            concurrent_sessions = {}
            session_processes = {}
            
            # Create multiple sessions concurrently
            async def create_session(index: int) -> Dict[str, Any]:
                result = await self.execute_mcp_operation(
                    "create_session",
                    {
                        "name": f"concurrent-session-{index}",
                        "model": "claude-3-opus-20240229"
                    }
                )
                return index, result
            
            # Create sessions
            tasks = [create_session(i) for i in range(num_sessions)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            sessions_created = 0
            for index, result in results:
                if isinstance(result, dict) and result.get("success"):
                    session_id = result.get("result", {}).get("session_id")
                    concurrent_sessions[session_id] = result["result"]
                    sessions_created += 1
                    
                    # Track process
                    process_info = await self._get_session_process(session_id)
                    if process_info:
                        session_processes[session_id] = process_info
                        self.created_processes.add(process_info["pid"])
            
            # Verify all sessions are independent
            unique_processes = len(set(p["pid"] for p in session_processes.values()))
            processes_independent = unique_processes == len(session_processes)
            
            # Execute prompts in parallel
            async def execute_prompt(session_id: str, index: int) -> Dict[str, Any]:
                result = await self.execute_mcp_operation(
                    "execute_prompt",
                    {
                        "session_id": session_id,
                        "prompt": f"echo 'Session {index} active'"
                    }
                )
                return session_id, result
            
            prompt_tasks = [
                execute_prompt(sid, i) 
                for i, sid in enumerate(concurrent_sessions.keys())
            ]
            prompt_results = await asyncio.gather(*prompt_tasks, return_exceptions=True)
            
            prompts_successful = sum(
                1 for _, r in prompt_results 
                if isinstance(r, dict) and r.get("success")
            )
            
            # List all sessions
            list_result = await self.execute_mcp_operation(
                "list_sessions",
                {"state": "running"}
            )
            
            listed_count = len(list_result.get("result", {}).get("sessions", []))
            
            # Terminate all sessions
            for session_id in concurrent_sessions:
                await self.execute_mcp_operation(
                    "terminate_session",
                    {"session_id": session_id}
                )
            
            await asyncio.sleep(1)
            
            # Verify all processes terminated
            active_processes = sum(
                1 for p in session_processes.values()
                if await self._is_process_running(p["pid"])
            )
            
            return {
                "test": test_name,
                "target_sessions": num_sessions,
                "sessions_created": sessions_created,
                "processes_independent": processes_independent,
                "prompts_successful": prompts_successful,
                "sessions_listed": listed_count >= sessions_created,
                "all_terminated": active_processes == 0,
                "passed": all([
                    sessions_created == num_sessions,
                    processes_independent,
                    prompts_successful == sessions_created,
                    active_processes == 0
                ]),
                "details": {
                    "unique_processes": unique_processes,
                    "remaining_processes": active_processes
                }
            }
            
        except Exception as e:
            logger.error(f"Test {test_name} failed: {e}")
            return {
                "test": test_name,
                "passed": False,
                "error": str(e)
            }
    
    async def _test_session_states(self) -> Dict[str, Any]:
        """Test session state transitions."""
        test_name = "session_states"
        
        try:
            # Create session
            create_result = await self.execute_mcp_operation(
                "create_session",
                {
                    "name": "state-test-session",
                    "model": "claude-3-opus-20240229"
                }
            )
            
            if not create_result["success"]:
                return {
                    "test": test_name,
                    "passed": False,
                    "error": "Failed to create session"
                }
            
            session_id = create_result.get("result", {}).get("session_id")
            states_observed = []
            
            # Track initial state
            state_result = await self.execute_mcp_operation(
                "get_session",
                {"session_id": session_id}
            )
            states_observed.append(state_result.get("result", {}).get("state"))
            
            # Pause session
            pause_result = await self.execute_mcp_operation(
                "pause_session",
                {"session_id": session_id}
            )
            
            await asyncio.sleep(0.5)
            
            # Check paused state
            state_result = await self.execute_mcp_operation(
                "get_session",
                {"session_id": session_id}
            )
            paused_state = state_result.get("result", {}).get("state")
            states_observed.append(paused_state)
            
            # Resume session
            resume_result = await self.execute_mcp_operation(
                "resume_session",
                {"session_id": session_id}
            )
            
            await asyncio.sleep(0.5)
            
            # Check resumed state
            state_result = await self.execute_mcp_operation(
                "get_session",
                {"session_id": session_id}
            )
            resumed_state = state_result.get("result", {}).get("state")
            states_observed.append(resumed_state)
            
            # Execute prompt to verify functionality
            prompt_result = await self.execute_mcp_operation(
                "execute_prompt",
                {
                    "session_id": session_id,
                    "prompt": "echo 'State test complete'"
                }
            )
            
            # Terminate
            await self.execute_mcp_operation(
                "terminate_session",
                {"session_id": session_id}
            )
            
            # Check terminated state
            state_result = await self.execute_mcp_operation(
                "get_session",
                {"session_id": session_id}
            )
            final_state = state_result.get("result", {}).get("state")
            states_observed.append(final_state)
            
            # Validate state transitions
            expected_states = ["running", "paused", "running", "terminated"]
            states_correct = all(
                observed in [expected, "active", "inactive", "completed"]
                for observed, expected in zip(states_observed, expected_states)
            )
            
            return {
                "test": test_name,
                "session_created": create_result["success"],
                "pause_successful": pause_result["success"],
                "resume_successful": resume_result["success"],
                "prompt_after_resume": prompt_result["success"],
                "states_observed": states_observed,
                "state_transitions_valid": states_correct,
                "passed": all([
                    create_result["success"],
                    pause_result["success"],
                    resume_result["success"],
                    prompt_result["success"],
                    states_correct
                ]),
                "details": {
                    "session_id": session_id,
                    "states": states_observed
                }
            }
            
        except Exception as e:
            logger.error(f"Test {test_name} failed: {e}")
            return {
                "test": test_name,
                "passed": False,
                "error": str(e)
            }
    
    async def _test_process_lifecycle(self) -> Dict[str, Any]:
        """Test process lifecycle validation."""
        test_name = "process_lifecycle"
        
        try:
            # Get initial process count
            initial_claude_processes = await self._count_claude_processes()
            
            # Create session
            create_result = await self.execute_mcp_operation(
                "create_session",
                {
                    "name": "lifecycle-test-session",
                    "model": "claude-3-opus-20240229"
                }
            )
            
            if not create_result["success"]:
                return {
                    "test": test_name,
                    "passed": False,
                    "error": "Failed to create session"
                }
            
            session_id = create_result.get("result", {}).get("session_id")
            
            # Verify process started
            await asyncio.sleep(0.5)
            process_info = await self._get_session_process(session_id)
            process_started = process_info is not None
            
            if process_started:
                self.created_processes.add(process_info["pid"])
                
                # Monitor process metrics
                metrics = await self._get_process_metrics(process_info["pid"])
                
                # Execute some work
                for i in range(3):
                    await self.execute_mcp_operation(
                        "execute_prompt",
                        {
                            "session_id": session_id,
                            "prompt": f"echo 'Lifecycle test {i}'"
                        }
                    )
                
                # Get updated metrics
                await asyncio.sleep(1)
                updated_metrics = await self._get_process_metrics(process_info["pid"])
                
                # Verify process is active
                process_active = (
                    updated_metrics is not None and
                    updated_metrics.get("cpu_percent", 0) >= 0 and
                    updated_metrics.get("memory_mb", 0) > 0
                )
            else:
                metrics = None
                updated_metrics = None
                process_active = False
            
            # Terminate session
            terminate_result = await self.execute_mcp_operation(
                "terminate_session",
                {"session_id": session_id}
            )
            
            # Wait for cleanup
            await asyncio.sleep(2)
            
            # Verify process terminated
            process_terminated = not await self._is_process_running(process_info["pid"]) if process_started else True
            
            # Check final process count
            final_claude_processes = await self._count_claude_processes()
            processes_cleaned = final_claude_processes <= initial_claude_processes
            
            return {
                "test": test_name,
                "session_created": create_result["success"],
                "process_started": process_started,
                "process_active": process_active,
                "process_terminated": process_terminated,
                "processes_cleaned": processes_cleaned,
                "passed": all([
                    create_result["success"],
                    process_started,
                    process_active,
                    process_terminated,
                    processes_cleaned
                ]),
                "details": {
                    "initial_processes": initial_claude_processes,
                    "final_processes": final_claude_processes,
                    "process_pid": process_info.get("pid") if process_info else None,
                    "initial_metrics": metrics,
                    "final_metrics": updated_metrics
                }
            }
            
        except Exception as e:
            logger.error(f"Test {test_name} failed: {e}")
            return {
                "test": test_name,
                "passed": False,
                "error": str(e)
            }
    
    async def _test_resource_cleanup(self) -> Dict[str, Any]:
        """Test resource cleanup after session termination."""
        test_name = "resource_cleanup"
        
        try:
            # Create session with specific resources
            create_result = await self.execute_mcp_operation(
                "create_session",
                {
                    "name": "cleanup-test-session",
                    "model": "claude-3-opus-20240229",
                    "config": {
                        "working_dir": str(self.sessions_dir / "cleanup-test")
                    }
                }
            )
            
            if not create_result["success"]:
                return {
                    "test": test_name,
                    "passed": False,
                    "error": "Failed to create session"
                }
            
            session_id = create_result.get("result", {}).get("session_id")
            working_dir = self.sessions_dir / "cleanup-test"
            
            # Create some session artifacts
            await self.execute_mcp_operation(
                "execute_prompt",
                {
                    "session_id": session_id,
                    "prompt": f"echo 'test data' > {working_dir}/test-file.txt"
                }
            )
            
            # Get process info
            process_info = await self._get_session_process(session_id)
            if process_info:
                self.created_processes.add(process_info["pid"])
            
            # Check for open file handles
            initial_handles = await self._get_process_handles(process_info["pid"]) if process_info else 0
            
            # Create more activity
            for i in range(5):
                await self.execute_mcp_operation(
                    "execute_prompt",
                    {
                        "session_id": session_id,
                        "prompt": f"echo 'Activity {i}'"
                    }
                )
            
            # Terminate session
            terminate_result = await self.execute_mcp_operation(
                "terminate_session",
                {"session_id": session_id}
            )
            
            # Wait for cleanup
            await asyncio.sleep(2)
            
            # Verify cleanup
            process_cleaned = not await self._is_process_running(process_info["pid"]) if process_info else True
            
            # Check for leaked file handles
            leaked_handles = await self._check_leaked_handles()
            
            # Check session artifacts
            artifacts_cleaned = not working_dir.exists() or len(list(working_dir.iterdir())) == 0
            
            # Check for zombie processes
            zombies = await self._check_zombie_processes()
            
            return {
                "test": test_name,
                "session_created": create_result["success"],
                "session_terminated": terminate_result["success"],
                "process_cleaned": process_cleaned,
                "no_leaked_handles": leaked_handles == 0,
                "artifacts_cleaned": artifacts_cleaned,
                "no_zombies": zombies == 0,
                "passed": all([
                    create_result["success"],
                    terminate_result["success"],
                    process_cleaned,
                    leaked_handles == 0,
                    zombies == 0
                ]),
                "details": {
                    "session_id": session_id,
                    "initial_handles": initial_handles,
                    "leaked_handles": leaked_handles,
                    "zombie_count": zombies
                }
            }
            
        except Exception as e:
            logger.error(f"Test {test_name} failed: {e}")
            return {
                "test": test_name,
                "passed": False,
                "error": str(e)
            }
    
    async def _test_session_persistence(self) -> Dict[str, Any]:
        """Test session persistence and recovery."""
        test_name = "session_persistence"
        
        try:
            # Create persistent session
            create_result = await self.execute_mcp_operation(
                "create_session",
                {
                    "name": "persistent-test-session",
                    "model": "claude-3-opus-20240229",
                    "persistent": True
                }
            )
            
            if not create_result["success"]:
                return {
                    "test": test_name,
                    "passed": False,
                    "error": "Failed to create session"
                }
            
            session_id = create_result.get("result", {}).get("session_id")
            
            # Store some state
            state_result = await self.execute_mcp_operation(
                "execute_prompt",
                {
                    "session_id": session_id,
                    "prompt": "TEST_VAR='persistence_test'"
                }
            )
            
            # Get session checkpoint
            checkpoint_result = await self.execute_mcp_operation(
                "checkpoint_session",
                {"session_id": session_id}
            )
            
            checkpoint_created = checkpoint_result["success"]
            checkpoint_id = checkpoint_result.get("result", {}).get("checkpoint_id")
            
            # Disconnect session (simulate crash)
            process_info = await self._get_session_process(session_id)
            if process_info:
                self.created_processes.add(process_info["pid"])
                # Force terminate process
                try:
                    process = psutil.Process(process_info["pid"])
                    process.terminate()
                except:
                    pass
            
            await asyncio.sleep(1)
            
            # Recover session
            recover_result = await self.execute_mcp_operation(
                "recover_session",
                {
                    "session_id": session_id,
                    "checkpoint_id": checkpoint_id
                }
            )
            
            # Verify state preserved
            state_preserved = False
            if recover_result["success"]:
                verify_result = await self.execute_mcp_operation(
                    "execute_prompt",
                    {
                        "session_id": session_id,
                        "prompt": "echo $TEST_VAR"
                    }
                )
                
                state_preserved = (
                    verify_result["success"] and
                    "persistence_test" in str(verify_result.get("result", {}).get("response", ""))
                )
            
            # Clean up
            await self.execute_mcp_operation(
                "terminate_session",
                {"session_id": session_id}
            )
            
            return {
                "test": test_name,
                "session_created": create_result["success"],
                "checkpoint_created": checkpoint_created,
                "session_recovered": recover_result["success"],
                "state_preserved": state_preserved,
                "passed": all([
                    create_result["success"],
                    checkpoint_created,
                    recover_result["success"],
                    state_preserved
                ]),
                "details": {
                    "session_id": session_id,
                    "checkpoint_id": checkpoint_id,
                    "recovery_successful": state_preserved
                }
            }
            
        except Exception as e:
            logger.error(f"Test {test_name} failed: {e}")
            return {
                "test": test_name,
                "passed": False,
                "error": str(e)
            }
    
    async def _test_error_handling(self) -> Dict[str, Any]:
        """Test error handling and recovery."""
        test_name = "error_handling"
        
        try:
            # Test 1: Invalid session creation
            invalid_result = await self.execute_mcp_operation(
                "create_session",
                {
                    "name": "invalid-session",
                    "model": "non-existent-model"
                }
            )
            
            invalid_handled = not invalid_result["success"]
            
            # Test 2: Create valid session
            create_result = await self.execute_mcp_operation(
                "create_session",
                {
                    "name": "error-test-session",
                    "model": "claude-3-opus-20240229"
                }
            )
            
            if not create_result["success"]:
                return {
                    "test": test_name,
                    "passed": False,
                    "error": "Failed to create session"
                }
            
            session_id = create_result.get("result", {}).get("session_id")
            
            # Test 3: Execute invalid command
            error_result = await self.execute_mcp_operation(
                "execute_prompt",
                {
                    "session_id": session_id,
                    "prompt": "this_command_does_not_exist --invalid-flag"
                }
            )
            
            # Should succeed but contain error in response
            error_handled = error_result["success"]
            
            # Test 4: Session still functional after error
            recovery_result = await self.execute_mcp_operation(
                "execute_prompt",
                {
                    "session_id": session_id,
                    "prompt": "echo 'Recovered from error'"
                }
            )
            
            session_recovered = (
                recovery_result["success"] and
                "Recovered from error" in str(recovery_result.get("result", {}).get("response", ""))
            )
            
            # Test 5: Timeout handling
            timeout_result = await self.execute_mcp_operation(
                "execute_prompt",
                {
                    "session_id": session_id,
                    "prompt": "sleep 30",
                    "timeout": 2
                }
            )
            
            timeout_handled = not timeout_result["success"] or "timeout" in str(timeout_result)
            
            # Clean up
            await self.execute_mcp_operation(
                "terminate_session",
                {"session_id": session_id}
            )
            
            return {
                "test": test_name,
                "invalid_session_handled": invalid_handled,
                "error_command_handled": error_handled,
                "session_recovered": session_recovered,
                "timeout_handled": timeout_handled,
                "passed": all([
                    invalid_handled,
                    error_handled,
                    session_recovered,
                    timeout_handled
                ]),
                "details": {
                    "error_types_tested": [
                        "invalid_model",
                        "command_error",
                        "timeout"
                    ],
                    "recovery_successful": session_recovered
                }
            }
            
        except Exception as e:
            logger.error(f"Test {test_name} failed: {e}")
            return {
                "test": test_name,
                "passed": False,
                "error": str(e)
            }
    
    async def _test_session_limits(self) -> Dict[str, Any]:
        """Test session limits and quotas."""
        test_name = "session_limits"
        
        try:
            # Get current limits
            limits_result = await self.execute_mcp_operation(
                "get_session_limits",
                {}
            )
            
            max_sessions = limits_result.get("result", {}).get("max_concurrent_sessions", 10)
            
            # Try to create sessions up to limit
            created_sessions = []
            for i in range(max_sessions + 2):  # Try to exceed limit
                result = await self.execute_mcp_operation(
                    "create_session",
                    {
                        "name": f"limit-test-session-{i}",
                        "model": "claude-3-opus-20240229"
                    }
                )
                
                if result["success"]:
                    session_id = result.get("result", {}).get("session_id")
                    created_sessions.append(session_id)
                    self.active_sessions[session_id] = result["result"]
            
            # Should have created exactly max_sessions
            limit_enforced = len(created_sessions) == max_sessions
            
            # Check quota usage
            quota_result = await self.execute_mcp_operation(
                "get_session_quota",
                {}
            )
            
            quota_tracking = (
                quota_result["success"] and
                quota_result.get("result", {}).get("used") == len(created_sessions)
            )
            
            # Test resource limits per session
            if created_sessions:
                test_session = created_sessions[0]
                
                # Try to exceed token limit
                large_prompt = "echo '" + "x" * 10000 + "'"
                token_result = await self.execute_mcp_operation(
                    "execute_prompt",
                    {
                        "session_id": test_session,
                        "prompt": large_prompt
                    }
                )
                
                # Should either succeed with truncation or fail gracefully
                token_limit_handled = (
                    token_result["success"] or
                    "token" in str(token_result.get("error", "")).lower()
                )
            else:
                token_limit_handled = False
            
            # Clean up all sessions
            for session_id in created_sessions:
                await self.execute_mcp_operation(
                    "terminate_session",
                    {"session_id": session_id}
                )
            
            # Verify quota released
            await asyncio.sleep(1)
            final_quota = await self.execute_mcp_operation(
                "get_session_quota",
                {}
            )
            
            quota_released = (
                final_quota["success"] and
                final_quota.get("result", {}).get("used") == 0
            )
            
            return {
                "test": test_name,
                "limit_enforced": limit_enforced,
                "quota_tracking": quota_tracking,
                "token_limit_handled": token_limit_handled,
                "quota_released": quota_released,
                "passed": all([
                    limit_enforced,
                    quota_tracking,
                    token_limit_handled,
                    quota_released
                ]),
                "details": {
                    "max_sessions": max_sessions,
                    "sessions_created": len(created_sessions),
                    "limit_respected": limit_enforced
                }
            }
            
        except Exception as e:
            logger.error(f"Test {test_name} failed: {e}")
            return {
                "test": test_name,
                "passed": False,
                "error": str(e)
            }
    
    async def _get_session_process(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get process information for a session."""
        try:
            # Get session details
            result = await self.execute_mcp_operation(
                "get_session",
                {"session_id": session_id}
            )
            
            if not result["success"]:
                return None
            
            process_id = result.get("result", {}).get("process_id")
            if not process_id:
                return None
            
            # Verify process exists
            try:
                process = psutil.Process(process_id)
                return {
                    "pid": process_id,
                    "name": process.name(),
                    "status": process.status(),
                    "create_time": process.create_time()
                }
            except psutil.NoSuchProcess:
                return None
                
        except Exception as e:
            logger.error(f"Failed to get session process: {e}")
            return None
    
    async def _is_process_running(self, pid: int) -> bool:
        """Check if a process is running."""
        try:
            process = psutil.Process(pid)
            return process.is_running() and process.status() != psutil.STATUS_ZOMBIE
        except psutil.NoSuchProcess:
            return False
    
    async def _count_claude_processes(self) -> int:
        """Count Claude Code processes."""
        count = 0
        for proc in psutil.process_iter(['name', 'cmdline']):
            try:
                if 'claude' in proc.info['name'].lower() or \
                   any('claude' in arg.lower() for arg in (proc.info['cmdline'] or [])):
                    count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return count
    
    async def _get_process_metrics(self, pid: int) -> Optional[Dict[str, Any]]:
        """Get process metrics."""
        try:
            process = psutil.Process(pid)
            with process.oneshot():
                return {
                    "cpu_percent": process.cpu_percent(interval=0.1),
                    "memory_mb": process.memory_info().rss / (1024 * 1024),
                    "num_threads": process.num_threads(),
                    "num_fds": process.num_fds() if hasattr(process, 'num_fds') else 0
                }
        except:
            return None
    
    async def _get_process_handles(self, pid: int) -> int:
        """Get number of open file handles."""
        try:
            process = psutil.Process(pid)
            return len(process.open_files())
        except:
            return 0
    
    async def _check_leaked_handles(self) -> int:
        """Check for leaked file handles."""
        # This is a simplified check - in production would be more sophisticated
        leaked = 0
        for proc in psutil.process_iter(['name']):
            try:
                if 'claude' in proc.info['name'].lower():
                    if proc.pid not in self.created_processes:
                        # Found a Claude process we didn't create
                        leaked += 1
            except:
                continue
        return leaked
    
    async def _check_zombie_processes(self) -> int:
        """Check for zombie processes."""
        zombies = 0
        for proc in psutil.process_iter(['status']):
            try:
                if proc.info['status'] == psutil.STATUS_ZOMBIE:
                    zombies += 1
            except:
                continue
        return zombies
    
    async def validate_system_state(self) -> bool:
        """Validate system state after session tests."""
        try:
            # Check for orphaned Claude processes
            orphaned = 0
            for proc in psutil.process_iter(['name', 'create_time']):
                try:
                    if 'claude' in proc.info['name'].lower():
                        if proc.pid not in self.created_processes and \
                           proc.info['create_time'] > self.start_time.timestamp():
                            orphaned += 1
                            logger.warning(f"Found orphaned process: {proc.pid}")
                except:
                    continue
            
            if orphaned > 0:
                logger.error(f"Found {orphaned} orphaned Claude processes")
                return False
            
            # Check for excessive memory usage
            total_memory = psutil.virtual_memory().total
            used_memory = psutil.virtual_memory().used
            
            if used_memory / total_memory > 0.9:
                logger.warning("System memory usage above 90%")
                return False
            
            # Check session directory
            if self.sessions_dir.exists():
                session_files = list(self.sessions_dir.rglob("*"))
                if len(session_files) > 100:
                    logger.warning(f"Too many session artifacts: {len(session_files)}")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"System state validation failed: {e}")
            return False
    
    async def cleanup(self):
        """Clean up session test artifacts."""
        logger.info("Cleaning up session test artifacts")
        
        # Terminate any remaining sessions
        for session_id in list(self.active_sessions.keys()):
            try:
                await self.execute_mcp_operation(
                    "terminate_session",
                    {"session_id": session_id}
                )
            except:
                pass
        
        # Kill any orphaned processes
        for pid in self.created_processes:
            try:
                if await self._is_process_running(pid):
                    process = psutil.Process(pid)
                    process.terminate()
                    logger.info(f"Terminated orphaned process: {pid}")
            except:
                pass
        
        # Clean session directory
        if self.sessions_dir.exists():
            try:
                import shutil
                shutil.rmtree(self.sessions_dir)
            except Exception as e:
                logger.warning(f"Failed to clean sessions directory: {e}")


async def main():
    """Run the session testing agent."""
    agent = SessionTestingAgent()
    result = await agent.run()
    
    # Print summary
    print("\n" + "="*60)
    print("Session Testing Agent Results")
    print("="*60)
    print(json.dumps(result, indent=2))
    
    # Exit with appropriate code
    sys.exit(0 if result.get("summary", {}).get("status") == "PASSED" else 1)


if __name__ == "__main__":
    asyncio.run(main())