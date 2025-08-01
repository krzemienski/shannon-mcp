#!/usr/bin/env python3
"""
Bidirectional Validator for MCP Integration Testing

Validates that changes made through MCP are reflected on the host system
and that host system changes are properly detected through MCP.
"""

import os
import sys
import json
import asyncio
import hashlib
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class BidirectionalValidator:
    """Validates bidirectional consistency between MCP and host system."""
    
    def __init__(self, mcp_client):
        self.mcp_client = mcp_client
        self.validation_results = []
        
    async def validate_file_operation(self, 
                                    operation: str,
                                    mcp_params: Dict[str, Any],
                                    expected_host_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate a file operation bidirectionally.
        
        Args:
            operation: MCP operation name
            mcp_params: Parameters for MCP operation
            expected_host_state: Expected state on host after operation
            
        Returns:
            Validation result
        """
        validation_id = f"file-{operation}-{datetime.now().timestamp()}"
        
        try:
            # Capture initial state
            initial_state = await self._capture_host_state(mcp_params.get("path"))
            
            # Execute MCP operation
            mcp_result = await self.mcp_client.execute_operation(operation, mcp_params)
            
            if not mcp_result["success"]:
                return {
                    "validation_id": validation_id,
                    "operation": operation,
                    "direction": "mcp_to_host",
                    "success": False,
                    "error": "MCP operation failed",
                    "mcp_result": mcp_result
                }
            
            # Wait for filesystem sync
            await asyncio.sleep(0.1)
            
            # Capture post-operation state
            post_state = await self._capture_host_state(mcp_params.get("path"))
            
            # Validate MCP → Host
            mcp_to_host_valid = await self._validate_state_change(
                initial_state, post_state, expected_host_state
            )
            
            # Now validate Host → MCP visibility
            mcp_view = await self._get_mcp_view(mcp_params.get("path"))
            
            host_to_mcp_valid = self._compare_states(post_state, mcp_view)
            
            result = {
                "validation_id": validation_id,
                "operation": operation,
                "direction": "bidirectional",
                "success": mcp_to_host_valid and host_to_mcp_valid,
                "mcp_to_host": {
                    "valid": mcp_to_host_valid,
                    "initial_state": initial_state,
                    "post_state": post_state,
                    "expected_state": expected_host_state
                },
                "host_to_mcp": {
                    "valid": host_to_mcp_valid,
                    "host_state": post_state,
                    "mcp_view": mcp_view
                }
            }
            
            self.validation_results.append(result)
            return result
            
        except Exception as e:
            logger.error(f"Validation {validation_id} failed: {e}")
            return {
                "validation_id": validation_id,
                "operation": operation,
                "success": False,
                "error": str(e)
            }
    
    async def validate_process_operation(self,
                                       session_id: str,
                                       command: str,
                                       expected_output: str) -> Dict[str, Any]:
        """
        Validate process operations bidirectionally.
        
        Args:
            session_id: MCP session ID
            command: Command to execute
            expected_output: Expected output pattern
            
        Returns:
            Validation result
        """
        validation_id = f"process-{session_id}-{datetime.now().timestamp()}"
        
        try:
            # Get initial process state
            initial_processes = await self._get_system_processes()
            
            # Execute command through MCP
            mcp_result = await self.mcp_client.execute_operation(
                "execute_prompt",
                {
                    "session_id": session_id,
                    "prompt": command
                }
            )
            
            if not mcp_result["success"]:
                return {
                    "validation_id": validation_id,
                    "success": False,
                    "error": "MCP execution failed"
                }
            
            # Validate output
            mcp_output = mcp_result.get("result", {}).get("response", "")
            output_valid = expected_output in mcp_output
            
            # Check if command affected host system
            if "touch" in command or "mkdir" in command:
                # Extract path from command
                parts = command.split()
                if len(parts) > 1:
                    target_path = parts[-1]
                    host_change_valid = Path(target_path).exists()
                else:
                    host_change_valid = False
            else:
                host_change_valid = True  # Command doesn't create files
            
            # Get final process state
            final_processes = await self._get_system_processes()
            
            # Check for process leaks
            process_diff = len(final_processes) - len(initial_processes)
            no_process_leak = process_diff <= 1  # Allow for the command process
            
            result = {
                "validation_id": validation_id,
                "session_id": session_id,
                "command": command,
                "success": output_valid and host_change_valid and no_process_leak,
                "output_valid": output_valid,
                "host_change_valid": host_change_valid,
                "no_process_leak": no_process_leak,
                "mcp_output": mcp_output[:200],  # First 200 chars
                "process_diff": process_diff
            }
            
            self.validation_results.append(result)
            return result
            
        except Exception as e:
            logger.error(f"Process validation failed: {e}")
            return {
                "validation_id": validation_id,
                "success": False,
                "error": str(e)
            }
    
    async def validate_hook_operation(self,
                                    hook_name: str,
                                    trigger_event: str,
                                    expected_marker: Path) -> Dict[str, Any]:
        """
        Validate hook operations bidirectionally.
        
        Args:
            hook_name: Name of the hook
            trigger_event: Event to trigger
            expected_marker: Expected marker file path
            
        Returns:
            Validation result
        """
        validation_id = f"hook-{hook_name}-{datetime.now().timestamp()}"
        
        try:
            # Ensure marker doesn't exist
            if expected_marker.exists():
                expected_marker.unlink()
            
            # Trigger hook through MCP
            trigger_result = await self.mcp_client.execute_operation(
                "trigger_event",
                {
                    "event": trigger_event,
                    "data": {"hook_name": hook_name}
                }
            )
            
            if not trigger_result["success"]:
                return {
                    "validation_id": validation_id,
                    "success": False,
                    "error": "Hook trigger failed"
                }
            
            # Wait for hook execution
            await asyncio.sleep(1)
            
            # Validate host system change
            hook_executed = expected_marker.exists()
            
            # Validate MCP can see the change
            mcp_sees_marker = False
            if hook_executed:
                file_info = await self.mcp_client.execute_operation(
                    "get_file_info",
                    {"path": str(expected_marker)}
                )
                mcp_sees_marker = file_info["success"]
            
            # Read marker content if exists
            marker_content = None
            if hook_executed:
                marker_content = expected_marker.read_text()
            
            result = {
                "validation_id": validation_id,
                "hook_name": hook_name,
                "trigger_event": trigger_event,
                "success": hook_executed and mcp_sees_marker,
                "hook_executed": hook_executed,
                "mcp_sees_marker": mcp_sees_marker,
                "marker_path": str(expected_marker),
                "marker_content": marker_content
            }
            
            self.validation_results.append(result)
            return result
            
        except Exception as e:
            logger.error(f"Hook validation failed: {e}")
            return {
                "validation_id": validation_id,
                "success": False,
                "error": str(e)
            }
    
    async def _capture_host_state(self, path: str) -> Dict[str, Any]:
        """Capture host system state for a path."""
        p = Path(path)
        
        if not p.exists():
            return {
                "exists": False,
                "type": None,
                "size": 0,
                "hash": None,
                "permissions": None
            }
        
        state = {
            "exists": True,
            "type": "file" if p.is_file() else "directory",
            "size": p.stat().st_size if p.is_file() else 0,
            "permissions": oct(p.stat().st_mode)[-3:],
            "mtime": p.stat().st_mtime
        }
        
        # Calculate hash for files
        if p.is_file() and p.stat().st_size < 1024 * 1024:  # Only for files < 1MB
            try:
                content = p.read_bytes()
                state["hash"] = hashlib.sha256(content).hexdigest()
            except:
                state["hash"] = None
        else:
            state["hash"] = None
        
        return state
    
    async def _get_mcp_view(self, path: str) -> Dict[str, Any]:
        """Get MCP's view of a path."""
        try:
            # Get file info through MCP
            info_result = await self.mcp_client.execute_operation(
                "get_file_info",
                {"path": path}
            )
            
            if not info_result["success"]:
                return {"exists": False}
            
            info = info_result.get("result", {})
            
            # Try to read content for hash
            content_hash = None
            if info.get("type") == "file" and info.get("size", 0) < 1024 * 1024:
                read_result = await self.mcp_client.execute_operation(
                    "read_file",
                    {"path": path}
                )
                
                if read_result["success"]:
                    content = read_result.get("result", {}).get("content", "")
                    content_hash = hashlib.sha256(content.encode()).hexdigest()
            
            return {
                "exists": True,
                "type": info.get("type"),
                "size": info.get("size", 0),
                "hash": content_hash,
                "permissions": info.get("permissions"),
                "mtime": info.get("mtime")
            }
            
        except Exception as e:
            logger.error(f"Failed to get MCP view: {e}")
            return {"exists": False, "error": str(e)}
    
    async def _validate_state_change(self,
                                   initial: Dict[str, Any],
                                   post: Dict[str, Any],
                                   expected: Dict[str, Any]) -> bool:
        """Validate state change matches expectations."""
        # Check existence change
        if "exists" in expected:
            if post["exists"] != expected["exists"]:
                return False
        
        # Check type
        if "type" in expected and post["exists"]:
            if post["type"] != expected["type"]:
                return False
        
        # Check content (via hash)
        if "content" in expected and post["exists"] and post["type"] == "file":
            expected_hash = hashlib.sha256(expected["content"].encode()).hexdigest()
            if post.get("hash") != expected_hash:
                return False
        
        # Check size change
        if "size_change" in expected:
            size_diff = post.get("size", 0) - initial.get("size", 0)
            if abs(size_diff - expected["size_change"]) > 10:  # Allow small variance
                return False
        
        return True
    
    def _compare_states(self, host_state: Dict[str, Any], mcp_state: Dict[str, Any]) -> bool:
        """Compare host and MCP states for consistency."""
        # Both should agree on existence
        if host_state["exists"] != mcp_state.get("exists", False):
            return False
        
        if not host_state["exists"]:
            return True  # Both agree it doesn't exist
        
        # Compare attributes
        if host_state["type"] != mcp_state.get("type"):
            return False
        
        # For files, compare size and hash
        if host_state["type"] == "file":
            if abs(host_state["size"] - mcp_state.get("size", 0)) > 0:
                return False
            
            # Compare hashes if available
            if host_state.get("hash") and mcp_state.get("hash"):
                if host_state["hash"] != mcp_state["hash"]:
                    return False
        
        return True
    
    async def _get_system_processes(self) -> List[Dict[str, Any]]:
        """Get current system processes."""
        try:
            import psutil
            processes = []
            
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    processes.append({
                        "pid": proc.info['pid'],
                        "name": proc.info['name'],
                        "cmdline": ' '.join(proc.info.get('cmdline', []))
                    })
                except:
                    continue
            
            return processes
            
        except ImportError:
            # Fallback to ps command
            result = subprocess.run(
                ["ps", "aux"],
                capture_output=True,
                text=True
            )
            
            processes = []
            for line in result.stdout.split('\n')[1:]:
                if line:
                    parts = line.split(None, 10)
                    if len(parts) >= 11:
                        processes.append({
                            "pid": int(parts[1]),
                            "name": parts[10].split()[0] if parts[10] else "unknown"
                        })
            
            return processes
    
    def get_validation_summary(self) -> Dict[str, Any]:
        """Get summary of all validations."""
        total = len(self.validation_results)
        successful = sum(1 for r in self.validation_results if r.get("success", False))
        
        by_type = {}
        for result in self.validation_results:
            op_type = result.get("operation", "unknown")
            if op_type not in by_type:
                by_type[op_type] = {"total": 0, "successful": 0}
            by_type[op_type]["total"] += 1
            if result.get("success", False):
                by_type[op_type]["successful"] += 1
        
        return {
            "total_validations": total,
            "successful": successful,
            "failed": total - successful,
            "success_rate": successful / total if total > 0 else 0,
            "by_type": by_type,
            "all_results": self.validation_results
        }


class HostSystemValidator:
    """Validates host system state independently."""
    
    @staticmethod
    async def validate_no_side_effects(baseline: Dict[str, Any],
                                     current: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate no unexpected side effects on host system.
        
        Args:
            baseline: System state before tests
            current: Current system state
            
        Returns:
            Validation result
        """
        issues = []
        
        # Check for new processes
        baseline_pids = set(p["pid"] for p in baseline.get("processes", []))
        current_pids = set(p["pid"] for p in current.get("processes", []))
        
        new_pids = current_pids - baseline_pids
        if len(new_pids) > 5:  # Allow some process churn
            issues.append(f"Excessive new processes: {len(new_pids)}")
        
        # Check disk usage
        if "disk_usage" in baseline and "disk_usage" in current:
            usage_increase = current["disk_usage"] - baseline["disk_usage"]
            if usage_increase > 100 * 1024 * 1024:  # 100MB
                issues.append(f"Excessive disk usage increase: {usage_increase / (1024*1024):.1f}MB")
        
        # Check for modifications to system directories
        system_dirs = ["/etc", "/usr", "/bin", "/sbin"]
        for dir_path in system_dirs:
            if dir_path in current.get("modified_paths", []):
                issues.append(f"System directory modified: {dir_path}")
        
        return {
            "no_side_effects": len(issues) == 0,
            "issues": issues,
            "baseline": baseline,
            "current": current
        }
    
    @staticmethod
    async def capture_system_baseline() -> Dict[str, Any]:
        """Capture baseline system state."""
        baseline = {
            "timestamp": datetime.now().isoformat(),
            "processes": [],
            "disk_usage": 0,
            "open_files": 0
        }
        
        try:
            import psutil
            
            # Capture processes
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    baseline["processes"].append({
                        "pid": proc.info['pid'],
                        "name": proc.info['name']
                    })
                except:
                    continue
            
            # Capture disk usage
            disk_usage = psutil.disk_usage('/')
            baseline["disk_usage"] = disk_usage.used
            
            # Count open files
            open_files = 0
            for proc in psutil.process_iter():
                try:
                    open_files += len(proc.open_files())
                except:
                    continue
            baseline["open_files"] = open_files
            
        except ImportError:
            # Fallback to shell commands
            import subprocess
            
            # Get process count
            result = subprocess.run(["ps", "aux"], capture_output=True, text=True)
            baseline["processes"] = [{"pid": 0, "name": "fallback"}]
            
            # Get disk usage
            result = subprocess.run(["df", "/"], capture_output=True, text=True)
            lines = result.stdout.strip().split('\n')
            if len(lines) > 1:
                parts = lines[1].split()
                if len(parts) >= 3:
                    baseline["disk_usage"] = int(parts[2]) * 1024
        
        return baseline


class MCPResponseValidator:
    """Validates MCP response correctness."""
    
    @staticmethod
    def validate_response_structure(response: Dict[str, Any],
                                  expected_schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate MCP response matches expected schema.
        
        Args:
            response: MCP response to validate
            expected_schema: Expected response schema
            
        Returns:
            Validation result
        """
        errors = []
        
        def validate_field(data: Any, schema: Dict[str, Any], path: str = ""):
            if "type" in schema:
                expected_type = schema["type"]
                actual_type = type(data).__name__
                
                type_map = {
                    "string": "str",
                    "number": "float",
                    "integer": "int",
                    "boolean": "bool",
                    "array": "list",
                    "object": "dict"
                }
                
                if type_map.get(expected_type, expected_type) != actual_type:
                    errors.append(f"{path}: Expected {expected_type}, got {actual_type}")
            
            if "required" in schema and isinstance(data, dict):
                for field in schema["required"]:
                    if field not in data:
                        errors.append(f"{path}: Missing required field '{field}'")
            
            if "properties" in schema and isinstance(data, dict):
                for field, field_schema in schema["properties"].items():
                    if field in data:
                        validate_field(data[field], field_schema, f"{path}.{field}")
        
        validate_field(response, expected_schema)
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "response": response,
            "schema": expected_schema
        }
    
    @staticmethod
    def validate_streaming_response(chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Validate streaming response characteristics.
        
        Args:
            chunks: List of streaming chunks
            
        Returns:
            Validation result
        """
        if not chunks:
            return {
                "valid": False,
                "error": "No chunks received"
            }
        
        issues = []
        
        # Check chunk structure
        for i, chunk in enumerate(chunks):
            if not isinstance(chunk, dict):
                issues.append(f"Chunk {i}: Not a dictionary")
                continue
            
            if "type" not in chunk:
                issues.append(f"Chunk {i}: Missing 'type' field")
            
            if "timestamp" not in chunk:
                issues.append(f"Chunk {i}: Missing 'timestamp' field")
        
        # Check chunk ordering
        timestamps = [c.get("timestamp", 0) for c in chunks if "timestamp" in c]
        if timestamps != sorted(timestamps):
            issues.append("Chunks not in timestamp order")
        
        # Check for end marker
        has_end = any(c.get("type") == "end" for c in chunks)
        if not has_end:
            issues.append("No end marker in stream")
        
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "chunk_count": len(chunks),
            "chunk_types": list(set(c.get("type", "unknown") for c in chunks))
        }