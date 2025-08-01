"""
Storage (Database and CAS) test fixtures.
"""

import hashlib
import zstandard
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timezone
import json
import uuid


class StorageFixtures:
    """Fixtures for Storage testing."""
    
    @staticmethod
    def create_test_content(size: int = 1000) -> bytes:
        """Create test content of specified size."""
        content = f"Test content {'x' * (size - 20)}\n".encode()
        return content[:size]
    
    @staticmethod
    def compute_hash(content: bytes) -> str:
        """Compute SHA-256 hash of content."""
        return hashlib.sha256(content).hexdigest()
    
    @staticmethod
    def compress_content(content: bytes) -> bytes:
        """Compress content using Zstandard."""
        cctx = zstandard.ZstdCompressor(level=3)
        return cctx.compress(content)
    
    @staticmethod
    def create_cas_entry(
        content: bytes,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """Create a CAS entry with content and metadata."""
        content_hash = StorageFixtures.compute_hash(content)
        compressed = StorageFixtures.compress_content(content)
        
        entry = {
            "hash": content_hash,
            "size": len(content),
            "compressed_size": len(compressed),
            "compression_ratio": len(compressed) / len(content),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {},
            "content": compressed
        }
        
        return content_hash, entry
    
    @staticmethod
    def create_cas_structure(base_path: Path, entries: int = 10) -> Dict[str, Path]:
        """Create a CAS directory structure with entries."""
        cas_dir = base_path / "cas"
        cas_dir.mkdir(parents=True, exist_ok=True)
        
        paths = {}
        for i in range(entries):
            content = StorageFixtures.create_test_content(size=100 * (i + 1))
            content_hash, entry = StorageFixtures.create_cas_entry(content)
            
            # CAS uses first 2 chars as directory
            subdir = cas_dir / content_hash[:2]
            subdir.mkdir(exist_ok=True)
            
            file_path = subdir / f"{content_hash}.zst"
            file_path.write_bytes(entry["content"])
            
            # Store metadata
            meta_path = subdir / f"{content_hash}.json"
            meta_path.write_text(json.dumps({
                k: v for k, v in entry.items() if k != "content"
            }, indent=2))
            
            paths[content_hash] = file_path
        
        return paths
    
    @staticmethod
    def create_database_schema() -> List[str]:
        """Get database schema creation SQL."""
        return [
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                project_path TEXT NOT NULL,
                prompt TEXT NOT NULL,
                model TEXT NOT NULL,
                temperature REAL,
                max_tokens INTEGER,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                metadata TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS agents (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                system_prompt TEXT NOT NULL,
                category TEXT NOT NULL,
                capabilities TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT,
                metadata TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS binaries (
                path TEXT PRIMARY KEY,
                version TEXT NOT NULL,
                discovered_at TEXT NOT NULL,
                discovery_method TEXT NOT NULL,
                last_used TEXT,
                metadata TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS cas_entries (
                hash TEXT PRIMARY KEY,
                size INTEGER NOT NULL,
                compressed_size INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                accessed_at TEXT,
                reference_count INTEGER DEFAULT 0,
                metadata TEXT
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);
            CREATE INDEX IF NOT EXISTS idx_sessions_created ON sessions(created_at);
            CREATE INDEX IF NOT EXISTS idx_agents_category ON agents(category);
            CREATE INDEX IF NOT EXISTS idx_binaries_version ON binaries(version);
            CREATE INDEX IF NOT EXISTS idx_cas_created ON cas_entries(created_at);
            """
        ]
    
    @staticmethod
    def create_test_database_entries() -> Dict[str, List[Dict[str, Any]]]:
        """Create test entries for all database tables."""
        now = datetime.now(timezone.utc)
        
        return {
            "sessions": [
                {
                    "id": f"session-{i}",
                    "project_path": f"/home/user/project-{i}",
                    "prompt": f"Test prompt {i}",
                    "model": ["claude-3-opus", "claude-3-sonnet"][i % 2],
                    "temperature": 0.7,
                    "max_tokens": 4096,
                    "status": ["created", "running", "completed", "failed"][i % 4],
                    "created_at": now.isoformat(),
                    "metadata": json.dumps({"test": True, "index": i})
                }
                for i in range(5)
            ],
            "agents": [
                {
                    "id": f"agent-{i}",
                    "name": f"Test Agent {i}",
                    "description": f"Test agent number {i}",
                    "system_prompt": f"You are test agent {i}",
                    "category": ["core", "infrastructure", "quality", "specialized"][i % 4],
                    "capabilities": json.dumps([f"capability-{j}" for j in range(3)]),
                    "created_at": now.isoformat(),
                    "metadata": json.dumps({"version": "1.0.0"})
                }
                for i in range(4)
            ],
            "binaries": [
                {
                    "path": f"/usr/local/bin/claude-{i}",
                    "version": f"1.{i}.0",
                    "discovered_at": now.isoformat(),
                    "discovery_method": ["which", "path", "nvm"][i % 3],
                    "metadata": json.dumps({"size": 25000000 + i * 1000000})
                }
                for i in range(3)
            ]
        }
    
    @staticmethod
    def create_migration_files(base_path: Path) -> List[Path]:
        """Create database migration files."""
        migrations_dir = base_path / "migrations"
        migrations_dir.mkdir(parents=True, exist_ok=True)
        
        migrations = [
            {
                "version": "001",
                "name": "initial_schema",
                "up": """
                CREATE TABLE sessions (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL
                );
                """,
                "down": "DROP TABLE sessions;"
            },
            {
                "version": "002",
                "name": "add_agents",
                "up": """
                CREATE TABLE agents (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL
                );
                """,
                "down": "DROP TABLE agents;"
            }
        ]
        
        paths = []
        for migration in migrations:
            filename = f"{migration['version']}_{migration['name']}.sql"
            path = migrations_dir / filename
            
            content = f"""-- Migration: {migration['name']}
-- Version: {migration['version']}

-- UP
{migration['up']}

-- DOWN
{migration['down']}
"""
            path.write_text(content)
            paths.append(path)
        
        return paths