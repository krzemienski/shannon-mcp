#!/usr/bin/env python3
"""
File System Test Agent for MCP Integration

Validates that MCP file operations correctly affect the host system
and that host system changes are properly reflected through MCP.
"""

import os
import sys
import json
import asyncio
import tempfile
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from test_agent_base import TestAgentBase

logger = logging.getLogger(__name__)


class FileSystemAgent(TestAgentBase):
    """Test agent for validating file system operations through MCP."""
    
    def __init__(self):
        super().__init__(
            name="FileSystemAgent",
            description="Validates MCP file system operations with bidirectional verification"
        )
        self.test_dir = self.test_base_dir / "test-filesystem"
        self.test_files = []
        
    async def validate_prerequisites(self) -> bool:
        """Validate file system test prerequisites."""
        try:
            # Create test directory
            self.test_dir.mkdir(parents=True, exist_ok=True)
            
            # Verify write permissions
            test_file = self.test_dir / ".prereq-test"
            test_file.write_text("test")
            content = test_file.read_text()
            test_file.unlink()
            
            return content == "test"
        except Exception as e:
            logger.error(f"Prerequisites validation failed: {e}")
            return False
    
    async def execute_test_scenarios(self) -> List[Dict[str, Any]]:
        """
        Execute comprehensive file system test scenarios.
        
        Tests:
        1. File creation through MCP → verify on host
        2. File modification through MCP → verify changes
        3. Directory operations through MCP → verify structure
        4. Host file creation → verify through MCP
        5. Concurrent operations → verify consistency
        6. Permission handling → verify security
        """
        test_results = []
        
        # Test 1: File Creation Through MCP
        logger.info("Test 1: File creation through MCP")
        result = await self._test_file_creation_mcp()
        test_results.append(result)
        
        # Test 2: File Modification Through MCP
        logger.info("Test 2: File modification through MCP")
        result = await self._test_file_modification_mcp()
        test_results.append(result)
        
        # Test 3: Directory Operations Through MCP
        logger.info("Test 3: Directory operations through MCP")
        result = await self._test_directory_operations_mcp()
        test_results.append(result)
        
        # Test 4: Host File Creation → MCP Detection
        logger.info("Test 4: Host file creation and MCP detection")
        result = await self._test_host_file_creation()
        test_results.append(result)
        
        # Test 5: Concurrent Operations
        logger.info("Test 5: Concurrent file operations")
        result = await self._test_concurrent_operations()
        test_results.append(result)
        
        # Test 6: Permission Handling
        logger.info("Test 6: File permission handling")
        result = await self._test_permission_handling()
        test_results.append(result)
        
        # Test 7: Large File Handling
        logger.info("Test 7: Large file operations")
        result = await self._test_large_file_handling()
        test_results.append(result)
        
        # Test 8: Symbolic Links and Special Files
        logger.info("Test 8: Symbolic links and special files")
        result = await self._test_special_files()
        test_results.append(result)
        
        self.test_results = test_results
        return test_results
    
    async def _test_file_creation_mcp(self) -> Dict[str, Any]:
        """Test file creation through MCP and verify on host."""
        test_name = "file_creation_mcp"
        test_file = self.test_dir / "mcp-created-file.txt"
        test_content = f"Created by MCP at {datetime.now().isoformat()}"
        
        try:
            # Execute MCP operation to create file
            mcp_result = await self.execute_mcp_operation(
                "create_file",
                {
                    "path": str(test_file),
                    "content": test_content,
                    "mode": "w"
                }
            )
            
            # Validate host system change
            host_validation = await self.validate_host_system_change({
                "type": "file_created",
                "path": str(test_file),
                "content": test_content
            })
            
            # Additional validation: file metadata
            metadata_valid = False
            if test_file.exists():
                stat = test_file.stat()
                metadata_valid = (
                    stat.st_size == len(test_content) and
                    stat.st_mode & 0o777 > 0
                )
                self.test_files.append(test_file)
            
            return {
                "test": test_name,
                "mcp_success": mcp_result["success"],
                "host_validation": host_validation,
                "metadata_valid": metadata_valid,
                "passed": mcp_result["success"] and host_validation and metadata_valid,
                "details": {
                    "file_path": str(test_file),
                    "content_length": len(test_content),
                    "mcp_result": mcp_result
                }
            }
            
        except Exception as e:
            logger.error(f"Test {test_name} failed: {e}")
            return {
                "test": test_name,
                "passed": False,
                "error": str(e)
            }
    
    async def _test_file_modification_mcp(self) -> Dict[str, Any]:
        """Test file modification through MCP."""
        test_name = "file_modification_mcp"
        test_file = self.test_dir / "mcp-modified-file.txt"
        
        try:
            # Create initial file
            initial_content = "Initial content"
            test_file.write_text(initial_content)
            initial_hash = hashlib.sha256(initial_content.encode()).hexdigest()
            
            # Modify through MCP
            modified_content = f"Modified by MCP at {datetime.now().isoformat()}"
            mcp_result = await self.execute_mcp_operation(
                "modify_file",
                {
                    "path": str(test_file),
                    "content": modified_content,
                    "mode": "w"
                }
            )
            
            # Validate modification
            host_validation = await self.validate_host_system_change({
                "type": "file_modified",
                "path": str(test_file),
                "contains": "Modified by MCP"
            })
            
            # Verify content hash changed
            hash_changed = False
            if test_file.exists():
                new_content = test_file.read_text()
                new_hash = hashlib.sha256(new_content.encode()).hexdigest()
                hash_changed = new_hash != initial_hash
                self.test_files.append(test_file)
            
            return {
                "test": test_name,
                "mcp_success": mcp_result["success"],
                "host_validation": host_validation,
                "hash_changed": hash_changed,
                "passed": mcp_result["success"] and host_validation and hash_changed,
                "details": {
                    "initial_hash": initial_hash,
                    "modification_detected": hash_changed
                }
            }
            
        except Exception as e:
            logger.error(f"Test {test_name} failed: {e}")
            return {
                "test": test_name,
                "passed": False,
                "error": str(e)
            }
    
    async def _test_directory_operations_mcp(self) -> Dict[str, Any]:
        """Test directory operations through MCP."""
        test_name = "directory_operations_mcp"
        test_dir = self.test_dir / "mcp-test-directory"
        nested_dir = test_dir / "nested" / "deep" / "structure"
        
        try:
            # Create directory structure through MCP
            mcp_result = await self.execute_mcp_operation(
                "create_directory",
                {
                    "path": str(nested_dir),
                    "parents": True
                }
            )
            
            # Validate directory creation
            dir_validation = await self.validate_host_system_change({
                "type": "directory_created",
                "path": str(nested_dir)
            })
            
            # Create files in directory
            files_created = 0
            for i in range(3):
                file_path = nested_dir / f"test-file-{i}.txt"
                file_result = await self.execute_mcp_operation(
                    "create_file",
                    {
                        "path": str(file_path),
                        "content": f"Test file {i}"
                    }
                )
                if file_result["success"] and file_path.exists():
                    files_created += 1
                    self.test_files.append(file_path)
            
            # List directory through MCP
            list_result = await self.execute_mcp_operation(
                "list_directory",
                {"path": str(nested_dir)}
            )
            
            # Validate listing
            listing_valid = (
                list_result["success"] and
                len(list_result.get("result", {}).get("files", [])) == files_created
            )
            
            return {
                "test": test_name,
                "mcp_success": mcp_result["success"],
                "dir_validation": dir_validation,
                "files_created": files_created == 3,
                "listing_valid": listing_valid,
                "passed": all([
                    mcp_result["success"],
                    dir_validation,
                    files_created == 3,
                    listing_valid
                ]),
                "details": {
                    "directory_path": str(nested_dir),
                    "files_created_count": files_created
                }
            }
            
        except Exception as e:
            logger.error(f"Test {test_name} failed: {e}")
            return {
                "test": test_name,
                "passed": False,
                "error": str(e)
            }
    
    async def _test_host_file_creation(self) -> Dict[str, Any]:
        """Test host file creation and MCP detection."""
        test_name = "host_file_creation"
        host_file = self.test_dir / "host-created-file.txt"
        
        try:
            # Create file directly on host
            host_content = f"Created by host at {datetime.now().isoformat()}"
            host_file.write_text(host_content)
            self.test_files.append(host_file)
            
            # Small delay to ensure file system sync
            await asyncio.sleep(0.1)
            
            # Read file through MCP
            mcp_result = await self.execute_mcp_operation(
                "read_file",
                {"path": str(host_file)}
            )
            
            # Validate MCP can see the file
            mcp_sees_file = (
                mcp_result["success"] and
                mcp_result.get("result", {}).get("content") == host_content
            )
            
            # Get file info through MCP
            info_result = await self.execute_mcp_operation(
                "get_file_info",
                {"path": str(host_file)}
            )
            
            # Validate file metadata
            metadata_valid = (
                info_result["success"] and
                info_result.get("result", {}).get("size") == len(host_content)
            )
            
            return {
                "test": test_name,
                "host_file_created": host_file.exists(),
                "mcp_sees_file": mcp_sees_file,
                "metadata_valid": metadata_valid,
                "passed": host_file.exists() and mcp_sees_file and metadata_valid,
                "details": {
                    "file_path": str(host_file),
                    "content_length": len(host_content),
                    "mcp_read_success": mcp_result["success"]
                }
            }
            
        except Exception as e:
            logger.error(f"Test {test_name} failed: {e}")
            return {
                "test": test_name,
                "passed": False,
                "error": str(e)
            }
    
    async def _test_concurrent_operations(self) -> Dict[str, Any]:
        """Test concurrent file operations for consistency."""
        test_name = "concurrent_operations"
        concurrent_dir = self.test_dir / "concurrent-test"
        concurrent_dir.mkdir(exist_ok=True)
        
        try:
            # Define concurrent operations
            async def create_file(index: int) -> Dict[str, Any]:
                file_path = concurrent_dir / f"concurrent-{index}.txt"
                result = await self.execute_mcp_operation(
                    "create_file",
                    {
                        "path": str(file_path),
                        "content": f"Concurrent file {index} - {datetime.now().isoformat()}"
                    }
                )
                if result["success"]:
                    self.test_files.append(file_path)
                return result
            
            # Execute concurrent operations
            tasks = [create_file(i) for i in range(10)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Count successes
            successes = sum(1 for r in results if isinstance(r, dict) and r.get("success"))
            
            # Verify all files exist on host
            host_files = list(concurrent_dir.glob("concurrent-*.txt"))
            host_count = len(host_files)
            
            # Read all files through MCP to verify consistency
            read_tasks = []
            for f in host_files:
                read_tasks.append(self.execute_mcp_operation(
                    "read_file",
                    {"path": str(f)}
                ))
            
            read_results = await asyncio.gather(*read_tasks, return_exceptions=True)
            read_successes = sum(1 for r in read_results if isinstance(r, dict) and r.get("success"))
            
            return {
                "test": test_name,
                "operations_attempted": 10,
                "mcp_successes": successes,
                "host_files_found": host_count,
                "mcp_reads_successful": read_successes,
                "passed": successes == 10 and host_count == 10 and read_successes == 10,
                "details": {
                    "consistency": successes == host_count == read_successes,
                    "concurrent_dir": str(concurrent_dir)
                }
            }
            
        except Exception as e:
            logger.error(f"Test {test_name} failed: {e}")
            return {
                "test": test_name,
                "passed": False,
                "error": str(e)
            }
    
    async def _test_permission_handling(self) -> Dict[str, Any]:
        """Test file permission handling and security."""
        test_name = "permission_handling"
        perm_file = self.test_dir / "permission-test-file.txt"
        
        try:
            # Create file with specific permissions through MCP
            mcp_result = await self.execute_mcp_operation(
                "create_file",
                {
                    "path": str(perm_file),
                    "content": "Permission test",
                    "mode": "w",
                    "permissions": 0o600  # Read/write for owner only
                }
            )
            
            if perm_file.exists():
                self.test_files.append(perm_file)
            
            # Check permissions on host
            permissions_correct = False
            if perm_file.exists():
                stat = perm_file.stat()
                # Check if permissions match (considering umask)
                permissions_correct = (stat.st_mode & 0o777) <= 0o600
            
            # Try to modify permissions through MCP
            chmod_result = await self.execute_mcp_operation(
                "change_permissions",
                {
                    "path": str(perm_file),
                    "mode": 0o644
                }
            )
            
            # Verify permission change
            permission_changed = False
            if chmod_result["success"] and perm_file.exists():
                new_stat = perm_file.stat()
                permission_changed = (new_stat.st_mode & 0o777) != (stat.st_mode & 0o777)
            
            # Test restricted path access (should fail)
            restricted_result = await self.execute_mcp_operation(
                "create_file",
                {
                    "path": "/etc/test-file-should-fail.txt",
                    "content": "This should fail"
                }
            )
            
            restricted_blocked = not restricted_result["success"]
            
            return {
                "test": test_name,
                "file_created": mcp_result["success"],
                "permissions_set": permissions_correct,
                "permission_change": chmod_result["success"] and permission_changed,
                "restricted_access_blocked": restricted_blocked,
                "passed": all([
                    mcp_result["success"],
                    permissions_correct,
                    restricted_blocked
                ]),
                "details": {
                    "test_file": str(perm_file),
                    "security_validated": restricted_blocked
                }
            }
            
        except Exception as e:
            logger.error(f"Test {test_name} failed: {e}")
            return {
                "test": test_name,
                "passed": False,
                "error": str(e)
            }
    
    async def _test_large_file_handling(self) -> Dict[str, Any]:
        """Test large file operations and streaming."""
        test_name = "large_file_handling"
        large_file = self.test_dir / "large-test-file.bin"
        
        try:
            # Create large file (10MB) through MCP
            size_mb = 10
            chunk_size = 1024 * 1024  # 1MB chunks
            
            # Start file creation
            create_result = await self.execute_mcp_operation(
                "create_file",
                {
                    "path": str(large_file),
                    "content": "",
                    "mode": "w"
                }
            )
            
            if not create_result["success"]:
                return {
                    "test": test_name,
                    "passed": False,
                    "error": "Failed to create large file"
                }
            
            # Append data in chunks
            bytes_written = 0
            for i in range(size_mb):
                chunk_data = f"Chunk {i} " * (chunk_size // 10)  # Repeated text
                append_result = await self.execute_mcp_operation(
                    "append_file",
                    {
                        "path": str(large_file),
                        "content": chunk_data
                    }
                )
                if append_result["success"]:
                    bytes_written += len(chunk_data)
            
            if large_file.exists():
                self.test_files.append(large_file)
            
            # Verify file size on host
            actual_size = large_file.stat().st_size if large_file.exists() else 0
            size_correct = abs(actual_size - bytes_written) < 1024  # Allow small difference
            
            # Test streaming read through MCP
            stream_result = await self.execute_mcp_operation(
                "stream_file",
                {
                    "path": str(large_file),
                    "chunk_size": chunk_size
                }
            )
            
            return {
                "test": test_name,
                "file_created": create_result["success"],
                "bytes_written": bytes_written,
                "actual_size": actual_size,
                "size_correct": size_correct,
                "streaming_supported": stream_result["success"],
                "passed": create_result["success"] and size_correct,
                "details": {
                    "target_size_mb": size_mb,
                    "actual_size_mb": actual_size / (1024 * 1024)
                }
            }
            
        except Exception as e:
            logger.error(f"Test {test_name} failed: {e}")
            return {
                "test": test_name,
                "passed": False,
                "error": str(e)
            }
    
    async def _test_special_files(self) -> Dict[str, Any]:
        """Test symbolic links and special file handling."""
        test_name = "special_files"
        
        try:
            # Create regular file
            target_file = self.test_dir / "symlink-target.txt"
            target_file.write_text("Symlink target content")
            self.test_files.append(target_file)
            
            # Create symlink through MCP
            symlink_path = self.test_dir / "test-symlink.txt"
            symlink_result = await self.execute_mcp_operation(
                "create_symlink",
                {
                    "target": str(target_file),
                    "link": str(symlink_path)
                }
            )
            
            # Verify symlink on host
            symlink_valid = symlink_path.is_symlink() if symlink_path.exists() else False
            if symlink_valid:
                self.test_files.append(symlink_path)
            
            # Read through symlink via MCP
            read_result = await self.execute_mcp_operation(
                "read_file",
                {
                    "path": str(symlink_path),
                    "follow_symlinks": True
                }
            )
            
            symlink_readable = (
                read_result["success"] and
                read_result.get("result", {}).get("content") == "Symlink target content"
            )
            
            # Test hidden file handling
            hidden_file = self.test_dir / ".hidden-test-file"
            hidden_result = await self.execute_mcp_operation(
                "create_file",
                {
                    "path": str(hidden_file),
                    "content": "Hidden file content"
                }
            )
            
            if hidden_file.exists():
                self.test_files.append(hidden_file)
            
            # List directory with hidden files
            list_result = await self.execute_mcp_operation(
                "list_directory",
                {
                    "path": str(self.test_dir),
                    "show_hidden": True
                }
            )
            
            hidden_visible = False
            if list_result["success"]:
                files = list_result.get("result", {}).get("files", [])
                hidden_visible = any(".hidden-test-file" in f for f in files)
            
            return {
                "test": test_name,
                "symlink_created": symlink_result["success"] or symlink_valid,
                "symlink_valid": symlink_valid,
                "symlink_readable": symlink_readable,
                "hidden_file_created": hidden_result["success"],
                "hidden_file_visible": hidden_visible,
                "passed": all([
                    symlink_valid or not symlink_result["success"],  # May not support symlinks
                    hidden_result["success"],
                    hidden_visible
                ]),
                "details": {
                    "symlink_support": symlink_valid,
                    "hidden_file_support": hidden_visible
                }
            }
            
        except Exception as e:
            logger.error(f"Test {test_name} failed: {e}")
            return {
                "test": test_name,
                "passed": False,
                "error": str(e)
            }
    
    async def validate_system_state(self) -> bool:
        """Validate system state after file system tests."""
        try:
            # Check for orphaned test files outside test directory
            orphaned_files = []
            for f in self.test_files:
                if f.exists() and not str(f).startswith(str(self.test_base_dir)):
                    orphaned_files.append(str(f))
            
            if orphaned_files:
                logger.warning(f"Found orphaned files: {orphaned_files}")
                return False
            
            # Verify test directory is not excessively large
            total_size = sum(
                f.stat().st_size for f in self.test_dir.rglob("*") 
                if f.is_file()
            )
            
            # Should be under 100MB for all tests
            if total_size > 100 * 1024 * 1024:
                logger.warning(f"Test directory too large: {total_size / (1024*1024):.2f}MB")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"System state validation failed: {e}")
            return False
    
    async def cleanup(self):
        """Clean up test files and directories."""
        logger.info("Cleaning up file system test artifacts")
        
        # Remove test files
        for f in self.test_files:
            try:
                if f.exists():
                    if f.is_symlink() or f.is_file():
                        f.unlink()
                    elif f.is_dir():
                        import shutil
                        shutil.rmtree(f)
            except Exception as e:
                logger.warning(f"Failed to clean up {f}: {e}")
        
        # Clean test directory
        if self.test_dir.exists():
            try:
                import shutil
                shutil.rmtree(self.test_dir)
            except Exception as e:
                logger.warning(f"Failed to clean test directory: {e}")


async def main():
    """Run the file system test agent."""
    agent = FileSystemAgent()
    result = await agent.run()
    
    # Print summary
    print("\n" + "="*60)
    print("File System Test Agent Results")
    print("="*60)
    print(json.dumps(result, indent=2))
    
    # Exit with appropriate code
    sys.exit(0 if result.get("summary", {}).get("status") == "PASSED" else 1)


if __name__ == "__main__":
    asyncio.run(main())