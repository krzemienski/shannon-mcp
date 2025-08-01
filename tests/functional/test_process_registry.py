"""
Functional tests for process registry with real process monitoring.
"""

import pytest
import asyncio
import psutil
import os
import sys
import subprocess
import time
from pathlib import Path

from shannon_mcp.registry.manager import ProcessRegistryManager
from shannon_mcp.registry.storage import RegistryStorage
from shannon_mcp.registry.monitor import ResourceMonitor
from shannon_mcp.managers.session import SessionManager
from shannon_mcp.managers.binary import BinaryManager


class TestProcessRegistry:
    """Test process registry with real system processes."""
    
    @pytest.fixture
    async def registry_setup(self, tmp_path):
        """Set up process registry."""
        # Create registry database
        db_path = tmp_path / "registry.db"
        storage = RegistryStorage(db_path)
        await storage.initialize()
        
        # Create registry manager
        registry = ProcessRegistryManager(storage)
        monitor = ResourceMonitor()
        
        # Set up session manager
        binary_manager = BinaryManager()
        binaries = await binary_manager.discover_binaries()
        
        if not binaries:
            pytest.skip("No Claude Code binary found")
        
        session_manager = SessionManager(binary_manager=binary_manager)
        
        yield {
            "registry": registry,
            "storage": storage,
            "monitor": monitor,
            "session_manager": session_manager,
            "db_path": db_path
        }
        
        # Cleanup
        await storage.close()
    
    @pytest.mark.asyncio
    async def test_process_registration(self, registry_setup):
        """Test registering real processes."""
        setup = registry_setup
        registry = setup["registry"]
        
        # Register current Python process
        current_pid = os.getpid()
        
        entry_id = await registry.register_process({
            "pid": current_pid,
            "type": "test_runner",
            "command": " ".join(sys.argv),
            "metadata": {
                "test": "process_registration",
                "python_version": sys.version
            }
        })
        
        print(f"\nRegistered current process:")
        print(f"  PID: {current_pid}")
        print(f"  Entry ID: {entry_id}")
        
        # Verify registration
        process_info = await registry.get_process(entry_id)
        assert process_info is not None
        assert process_info["pid"] == current_pid
        assert process_info["type"] == "test_runner"
        
        # Check process is tracked as active
        active_processes = await registry.list_active_processes()
        assert any(p["pid"] == current_pid for p in active_processes)
    
    @pytest.mark.asyncio
    async def test_session_process_tracking(self, registry_setup):
        """Test tracking Claude Code session processes."""
        setup = registry_setup
        registry = setup["registry"]
        session_manager = setup["session_manager"]
        
        # Create sessions and track their processes
        session_entries = []
        
        for i in range(2):
            # Create session
            session = await session_manager.create_session(f"tracked-session-{i}")
            await session_manager.start_session(session.id)
            
            # Get session process info
            if hasattr(session, 'process') and session.process:
                pid = session.process.pid
                
                # Register in registry
                entry_id = await registry.register_process({
                    "pid": pid,
                    "type": "claude_session",
                    "session_id": session.id,
                    "command": f"claude --session {session.id}",
                    "metadata": {
                        "model": "claude-3-opus-20240229",
                        "start_time": time.time()
                    }
                })
                
                session_entries.append({
                    "session_id": session.id,
                    "entry_id": entry_id,
                    "pid": pid
                })
                
                print(f"\nTracked session {i}:")
                print(f"  Session ID: {session.id}")
                print(f"  PID: {pid}")
                print(f"  Entry ID: {entry_id}")
        
        # Verify all sessions are tracked
        claude_processes = await registry.list_processes_by_type("claude_session")
        assert len(claude_processes) >= len(session_entries)
        
        # Close sessions and verify cleanup
        for entry in session_entries:
            await session_manager.close_session(entry["session_id"])
            
            # Mark as terminated in registry
            await registry.mark_terminated(entry["entry_id"])
        
        # Verify terminated
        active_claude = await registry.list_processes_by_type("claude_session", active_only=True)
        for entry in session_entries:
            assert not any(p["entry_id"] == entry["entry_id"] for p in active_claude)
    
    @pytest.mark.asyncio
    async def test_resource_monitoring(self, registry_setup):
        """Test monitoring process resource usage."""
        setup = registry_setup
        registry = setup["registry"]
        monitor = setup["monitor"]
        session_manager = setup["session_manager"]
        
        # Create a session to monitor
        session = await session_manager.create_session("monitor-resources")
        await session_manager.start_session(session.id)
        
        if not hasattr(session, 'process') or not session.process:
            pytest.skip("Session process not available for monitoring")
        
        pid = session.process.pid
        
        # Register process
        entry_id = await registry.register_process({
            "pid": pid,
            "type": "monitored_session",
            "session_id": session.id
        })
        
        # Monitor resources over time
        samples = []
        
        for i in range(5):
            # Get resource usage
            usage = await monitor.get_process_resources(pid)
            
            if usage:
                samples.append(usage)
                
                # Store in registry
                await registry.update_resource_usage(entry_id, usage)
                
                print(f"\nResource sample {i+1}:")
                print(f"  CPU: {usage['cpu_percent']:.1f}%")
                print(f"  Memory: {usage['memory_mb']:.1f} MB")
                print(f"  Threads: {usage.get('num_threads', 0)}")
            
            # Execute work to generate resource usage
            await session_manager.execute_prompt(
                session.id,
                f"Count to {1000 * (i + 1)}"
            )
            
            await asyncio.sleep(1)
        
        # Get resource history
        history = await registry.get_resource_history(entry_id)
        
        print(f"\nResource history: {len(history)} samples")
        assert len(history) >= len(samples)
        
        # Cleanup
        await session_manager.close_session(session.id)
    
    @pytest.mark.asyncio
    async def test_process_health_checks(self, registry_setup):
        """Test process health monitoring."""
        setup = registry_setup
        registry = setup["registry"]
        
        # Create a subprocess to monitor
        process = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Register process
        entry_id = await registry.register_process({
            "pid": process.pid,
            "type": "test_subprocess",
            "health_check_enabled": True,
            "health_check_interval": 1  # 1 second
        })
        
        print(f"\nMonitoring subprocess PID: {process.pid}")
        
        # Perform health checks
        health_results = []
        
        for i in range(3):
            health = await registry.check_process_health(entry_id)
            health_results.append(health)
            
            print(f"\nHealth check {i+1}:")
            print(f"  Status: {health['status']}")
            print(f"  Running: {health['is_running']}")
            print(f"  Responsive: {health.get('responsive', 'N/A')}")
            
            await asyncio.sleep(1)
        
        # All checks should show healthy
        assert all(h["status"] == "healthy" for h in health_results)
        assert all(h["is_running"] for h in health_results)
        
        # Terminate process
        process.terminate()
        process.wait()
        
        # Final health check should show terminated
        final_health = await registry.check_process_health(entry_id)
        assert final_health["status"] == "terminated"
        assert not final_health["is_running"]
    
    @pytest.mark.asyncio
    async def test_zombie_cleanup(self, registry_setup):
        """Test cleaning up zombie processes."""
        setup = registry_setup
        registry = setup["registry"]
        
        # Create processes that will become zombies
        zombie_pids = []
        
        for i in range(3):
            # Create subprocess that exits immediately
            process = subprocess.Popen(
                [sys.executable, "-c", "exit(0)"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            pid = process.pid
            
            # Register before it exits
            entry_id = await registry.register_process({
                "pid": pid,
                "type": "potential_zombie",
                "expected_lifetime": "short"
            })
            
            zombie_pids.append((pid, entry_id))
            
            # Don't wait() - let it become zombie
            await asyncio.sleep(0.1)
        
        print(f"\nCreated {len(zombie_pids)} potential zombie processes")
        
        # Run zombie cleanup
        cleaned = await registry.cleanup_zombies()
        
        print(f"Cleaned up {cleaned} zombie processes")
        
        # Verify zombies are marked as terminated
        for pid, entry_id in zombie_pids:
            process_info = await registry.get_process(entry_id)
            assert process_info["status"] == "terminated"
    
    @pytest.mark.asyncio
    async def test_cross_session_messaging(self, registry_setup):
        """Test inter-process communication via registry."""
        setup = registry_setup
        registry = setup["registry"]
        
        # Register two processes that will communicate
        process1_id = await registry.register_process({
            "pid": os.getpid(),
            "type": "messenger",
            "name": "process1"
        })
        
        process2_id = await registry.register_process({
            "pid": os.getpid(),  # Same process for testing
            "type": "messenger",
            "name": "process2"
        })
        
        # Send message from process1 to process2
        message_id = await registry.send_message(
            from_process=process1_id,
            to_process=process2_id,
            message={
                "type": "greeting",
                "content": "Hello from process1",
                "timestamp": time.time()
            }
        )
        
        print(f"\nSent message: {message_id}")
        
        # Retrieve message for process2
        messages = await registry.get_messages(process2_id)
        
        assert len(messages) == 1
        assert messages[0]["content"] == "Hello from process1"
        assert messages[0]["from_process"] == process1_id
        
        # Mark message as read
        await registry.mark_message_read(message_id)
        
        # Verify no unread messages
        unread = await registry.get_messages(process2_id, unread_only=True)
        assert len(unread) == 0
    
    @pytest.mark.asyncio
    async def test_resource_alerts(self, registry_setup):
        """Test resource usage alerts."""
        setup = registry_setup
        registry = setup["registry"]
        monitor = setup["monitor"]
        
        # Set up alert thresholds
        alert_config = {
            "cpu_threshold": 80.0,  # 80% CPU
            "memory_threshold": 500,  # 500 MB
            "check_interval": 1
        }
        
        # Register current process with alerts
        entry_id = await registry.register_process({
            "pid": os.getpid(),
            "type": "alert_test",
            "alerts": alert_config
        })
        
        # Simulate high resource usage
        alerts_triggered = []
        
        # Create some CPU load
        start_time = time.time()
        while time.time() - start_time < 2:
            # Busy loop to generate CPU usage
            _ = sum(i * i for i in range(10000))
            
            # Check for alerts
            alerts = await registry.check_resource_alerts(entry_id)
            if alerts:
                alerts_triggered.extend(alerts)
        
        print(f"\nAlerts triggered: {len(alerts_triggered)}")
        for alert in alerts_triggered[:3]:  # Show first 3
            print(f"  {alert['type']}: {alert['message']}")
        
        # Should have triggered some alerts (at least for memory)
        assert len(alerts_triggered) > 0