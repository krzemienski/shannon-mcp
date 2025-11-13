"""
Agent Skills management and marketplace integration.

This module provides:
- Skill definition and registry
- Skill marketplace integration
- Skill installation and activation
- Skill versioning and updates
- Skill sharing between agents
"""

import asyncio
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
import structlog
import aiosqlite

from ..utils.logging import get_logger


logger = get_logger("shannon-mcp.skills")


class SkillCategory(Enum):
    """Categories of agent skills."""
    ANALYSIS = "analysis"
    CODE_GENERATION = "code_generation"
    DEBUGGING = "debugging"
    TESTING = "testing"
    DOCUMENTATION = "documentation"
    OPTIMIZATION = "optimization"
    SECURITY = "security"
    DATA_PROCESSING = "data_processing"
    API_INTEGRATION = "api_integration"
    CUSTOM = "custom"


@dataclass
class SkillVersion:
    """Version information for a skill."""
    version: str
    release_date: datetime
    changelog: str
    dependencies: List[str] = field(default_factory=list)
    breaking_changes: bool = False


@dataclass
class Skill:
    """Definition of an agent skill."""
    id: str
    name: str
    description: str
    category: SkillCategory
    version: SkillVersion
    author: str
    code: str  # Python code implementing the skill
    parameters: Dict[str, Any]
    returns: Dict[str, Any]
    examples: List[Dict[str, Any]] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    required_capabilities: List[str] = field(default_factory=list)
    installed: bool = False
    enabled: bool = True
    install_path: Optional[Path] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def checksum(self) -> str:
        """Calculate checksum of skill code."""
        return hashlib.sha256(self.code.encode()).hexdigest()[:16]


class SkillMarketplace:
    """
    Skill marketplace integration.

    Provides access to public skill repository and marketplace features.
    """

    def __init__(self, marketplace_url: str = "https://skills.shannon-mcp.io"):
        """
        Initialize skill marketplace.

        Args:
            marketplace_url: URL of the skill marketplace
        """
        self.marketplace_url = marketplace_url
        self.cache: Dict[str, Skill] = {}

    async def search_skills(
        self,
        query: Optional[str] = None,
        category: Optional[SkillCategory] = None,
        tags: Optional[List[str]] = None,
        limit: int = 20
    ) -> List[Skill]:
        """
        Search for skills in the marketplace.

        Args:
            query: Search query
            category: Filter by category
            tags: Filter by tags
            limit: Maximum results

        Returns:
            List of matching skills
        """
        logger.info(
            "Searching marketplace",
            query=query,
            category=category.value if category else None
        )

        # For now, return mock skills as marketplace is not yet live
        mock_skills = self._get_mock_marketplace_skills()

        results = mock_skills

        # Apply filters
        if query:
            results = [
                s for s in results
                if query.lower() in s.name.lower() or query.lower() in s.description.lower()
            ]

        if category:
            results = [s for s in results if s.category == category]

        if tags:
            results = [
                s for s in results
                if any(tag in s.tags for tag in tags)
            ]

        return results[:limit]

    async def get_skill(self, skill_id: str) -> Optional[Skill]:
        """
        Get a specific skill from marketplace.

        Args:
            skill_id: Skill ID

        Returns:
            Skill or None
        """
        # Check cache first
        if skill_id in self.cache:
            return self.cache[skill_id]

        # Search in mock skills
        mock_skills = self._get_mock_marketplace_skills()
        skill = next((s for s in mock_skills if s.id == skill_id), None)

        if skill:
            self.cache[skill_id] = skill

        return skill

    async def get_popular_skills(self, limit: int = 10) -> List[Skill]:
        """
        Get most popular skills.

        Args:
            limit: Maximum results

        Returns:
            List of popular skills
        """
        mock_skills = self._get_mock_marketplace_skills()
        return mock_skills[:limit]

    async def get_skill_updates(
        self,
        installed_skills: List[Skill]
    ) -> List[tuple[Skill, Skill]]:
        """
        Check for updates to installed skills.

        Args:
            installed_skills: List of installed skills

        Returns:
            List of (current_skill, updated_skill) tuples
        """
        updates = []

        for installed in installed_skills:
            marketplace_skill = await self.get_skill(installed.id)

            if marketplace_skill and marketplace_skill.version.version != installed.version.version:
                # Compare versions
                if self._is_newer_version(
                    marketplace_skill.version.version,
                    installed.version.version
                ):
                    updates.append((installed, marketplace_skill))

        return updates

    def _is_newer_version(self, v1: str, v2: str) -> bool:
        """Check if v1 is newer than v2."""
        # Simple version comparison (semantic versioning)
        try:
            v1_parts = [int(x) for x in v1.split('.')]
            v2_parts = [int(x) for x in v2.split('.')]
            return v1_parts > v2_parts
        except:
            return False

    def _get_mock_marketplace_skills(self) -> List[Skill]:
        """Get mock marketplace skills for testing."""
        return [
            Skill(
                id="skill_code_analyzer",
                name="Code Analyzer",
                description="Analyzes code quality, complexity, and suggests improvements",
                category=SkillCategory.ANALYSIS,
                version=SkillVersion(
                    version="1.2.0",
                    release_date=datetime(2025, 1, 10),
                    changelog="Added support for async code analysis"
                ),
                author="Shannon Team",
                code="""
async def analyze_code(code: str) -> dict:
    # Analyze code complexity, quality metrics, etc.
    return {
        "complexity": 5,
        "quality_score": 85,
        "suggestions": ["Add type hints", "Reduce complexity"]
    }
""",
                parameters={"code": {"type": "string"}},
                returns={"type": "object"},
                tags=["analysis", "code-quality", "metrics"],
                required_capabilities=["code_analysis"]
            ),
            Skill(
                id="skill_test_generator",
                name="Test Generator",
                description="Automatically generates unit tests for Python code",
                category=SkillCategory.TESTING,
                version=SkillVersion(
                    version="1.0.5",
                    release_date=datetime(2025, 1, 8),
                    changelog="Improved edge case coverage"
                ),
                author="Shannon Team",
                code="""
async def generate_tests(code: str, framework: str = "pytest") -> str:
    # Generate unit tests for the provided code
    return f"# Generated tests using {framework}"
""",
                parameters={
                    "code": {"type": "string"},
                    "framework": {"type": "string", "default": "pytest"}
                },
                returns={"type": "string"},
                tags=["testing", "automation", "pytest"],
                required_capabilities=["testing", "code_generation"]
            ),
            Skill(
                id="skill_api_client_generator",
                name="API Client Generator",
                description="Generates type-safe API clients from OpenAPI specs",
                category=SkillCategory.CODE_GENERATION,
                version=SkillVersion(
                    version="2.0.0",
                    release_date=datetime(2025, 1, 12),
                    changelog="Major rewrite with improved type safety",
                    breaking_changes=True
                ),
                author="Shannon Team",
                code="""
async def generate_api_client(openapi_spec: dict) -> str:
    # Generate Python API client from OpenAPI spec
    return "# Generated API client code"
""",
                parameters={"openapi_spec": {"type": "object"}},
                returns={"type": "string"},
                tags=["api", "code-generation", "openapi"],
                required_capabilities=["code_generation", "api_integration"]
            ),
            Skill(
                id="skill_security_scanner",
                name="Security Scanner",
                description="Scans code for security vulnerabilities and OWASP issues",
                category=SkillCategory.SECURITY,
                version=SkillVersion(
                    version="1.5.2",
                    release_date=datetime(2025, 1, 5),
                    changelog="Added OWASP Top 10 2023 checks"
                ),
                author="Shannon Team",
                code="""
async def scan_security(code: str) -> dict:
    # Scan for security vulnerabilities
    return {
        "vulnerabilities": [],
        "warnings": [],
        "score": 95
    }
""",
                parameters={"code": {"type": "string"}},
                returns={"type": "object"},
                tags=["security", "vulnerabilities", "owasp"],
                required_capabilities=["security_analysis"]
            ),
            Skill(
                id="skill_doc_generator",
                name="Documentation Generator",
                description="Generates comprehensive documentation from code",
                category=SkillCategory.DOCUMENTATION,
                version=SkillVersion(
                    version="1.1.0",
                    release_date=datetime(2025, 1, 7),
                    changelog="Added Markdown and RST support"
                ),
                author="Shannon Team",
                code="""
async def generate_docs(code: str, format: str = "markdown") -> str:
    # Generate documentation from code
    return f"# Generated documentation in {format}"
""",
                parameters={
                    "code": {"type": "string"},
                    "format": {"type": "string", "default": "markdown"}
                },
                returns={"type": "string"},
                tags=["documentation", "markdown", "docstrings"],
                required_capabilities=["documentation", "code_analysis"]
            ),
        ]


class SkillInstaller:
    """
    Skill installation and management.

    Handles installing, enabling, disabling, and uninstalling skills.
    """

    def __init__(self, skills_dir: Path, db_path: Path):
        """
        Initialize skill installer.

        Args:
            skills_dir: Directory for installed skills
            db_path: Path to database
        """
        self.skills_dir = skills_dir
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path

    async def install_skill(self, skill: Skill) -> bool:
        """
        Install a skill.

        Args:
            skill: Skill to install

        Returns:
            True if successful
        """
        logger.info(
            "Installing skill",
            skill_id=skill.id,
            version=skill.version.version
        )

        try:
            # Create skill directory
            skill_dir = self.skills_dir / skill.id
            skill_dir.mkdir(parents=True, exist_ok=True)

            # Write skill code
            code_path = skill_dir / "skill.py"
            code_path.write_text(skill.code)

            # Write skill metadata
            metadata_path = skill_dir / "metadata.json"
            metadata_path.write_text(json.dumps({
                "id": skill.id,
                "name": skill.name,
                "description": skill.description,
                "category": skill.category.value,
                "version": skill.version.version,
                "author": skill.author,
                "install_date": datetime.utcnow().isoformat(),
                "checksum": skill.checksum()
            }, indent=2))

            # Save to database
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    """
                    INSERT OR REPLACE INTO agent_skills
                    (id, name, description, category, version, code, installed, enabled, install_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        skill.id,
                        skill.name,
                        skill.description,
                        skill.category.value,
                        skill.version.version,
                        skill.code,
                        True,
                        True,
                        datetime.utcnow().isoformat()
                    )
                )
                await db.commit()

            skill.installed = True
            skill.install_path = skill_dir

            logger.info(
                "Skill installed successfully",
                skill_id=skill.id
            )

            return True

        except Exception as e:
            logger.error(
                "Skill installation failed",
                skill_id=skill.id,
                error=str(e)
            )
            return False

    async def uninstall_skill(self, skill_id: str) -> bool:
        """
        Uninstall a skill.

        Args:
            skill_id: Skill ID to uninstall

        Returns:
            True if successful
        """
        logger.info("Uninstalling skill", skill_id=skill_id)

        try:
            # Remove from filesystem
            skill_dir = self.skills_dir / skill_id
            if skill_dir.exists():
                import shutil
                shutil.rmtree(skill_dir)

            # Remove from database
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "DELETE FROM agent_skills WHERE id = ?",
                    (skill_id,)
                )
                await db.commit()

            logger.info("Skill uninstalled", skill_id=skill_id)
            return True

        except Exception as e:
            logger.error(
                "Skill uninstallation failed",
                skill_id=skill_id,
                error=str(e)
            )
            return False

    async def enable_skill(self, skill_id: str) -> bool:
        """Enable a skill."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE agent_skills SET enabled = ? WHERE id = ?",
                (True, skill_id)
            )
            await db.commit()

        logger.info("Skill enabled", skill_id=skill_id)
        return True

    async def disable_skill(self, skill_id: str) -> bool:
        """Disable a skill."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE agent_skills SET enabled = ? WHERE id = ?",
                (False, skill_id)
            )
            await db.commit()

        logger.info("Skill disabled", skill_id=skill_id)
        return True

    async def list_installed_skills(self) -> List[Skill]:
        """
        List all installed skills.

        Returns:
            List of installed skills
        """
        skills = []

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            async with db.execute(
                "SELECT * FROM agent_skills WHERE installed = ?"
                , (True,)
            ) as cursor:
                rows = await cursor.fetchall()

                for row in rows:
                    skill = Skill(
                        id=row["id"],
                        name=row["name"],
                        description=row["description"],
                        category=SkillCategory(row["category"]),
                        version=SkillVersion(
                            version=row["version"],
                            release_date=datetime.fromisoformat(row["install_date"]),
                            changelog=""
                        ),
                        author="",
                        code=row["code"],
                        parameters={},
                        returns={},
                        installed=True,
                        enabled=bool(row["enabled"]),
                        install_path=self.skills_dir / row["id"]
                    )
                    skills.append(skill)

        return skills


class SkillsManager:
    """
    Main skills management system.

    Combines marketplace, installer, and skill registry to provide
    complete skill management functionality.
    """

    def __init__(
        self,
        skills_dir: Path,
        db_path: Path,
        marketplace_url: str = "https://skills.shannon-mcp.io"
    ):
        """
        Initialize skills manager.

        Args:
            skills_dir: Directory for installed skills
            db_path: Path to database
            marketplace_url: Marketplace URL
        """
        self.marketplace = SkillMarketplace(marketplace_url)
        self.installer = SkillInstaller(skills_dir, db_path)
        self.installed_skills: Dict[str, Skill] = {}

    async def initialize(self) -> None:
        """Initialize the skills manager."""
        logger.info("Initializing skills manager")

        # Load installed skills
        skills = await self.installer.list_installed_skills()
        self.installed_skills = {skill.id: skill for skill in skills}

        logger.info(
            "Skills manager initialized",
            installed_count=len(self.installed_skills)
        )

    async def search_marketplace(
        self,
        query: Optional[str] = None,
        category: Optional[SkillCategory] = None,
        tags: Optional[List[str]] = None
    ) -> List[Skill]:
        """Search marketplace for skills."""
        return await self.marketplace.search_skills(query, category, tags)

    async def install_from_marketplace(self, skill_id: str) -> bool:
        """
        Install a skill from marketplace.

        Args:
            skill_id: Skill ID to install

        Returns:
            True if successful
        """
        # Get skill from marketplace
        skill = await self.marketplace.get_skill(skill_id)

        if not skill:
            logger.error("Skill not found in marketplace", skill_id=skill_id)
            return False

        # Install skill
        success = await self.installer.install_skill(skill)

        if success:
            self.installed_skills[skill.id] = skill

        return success

    async def check_for_updates(self) -> List[tuple[Skill, Skill]]:
        """Check for updates to installed skills."""
        return await self.marketplace.get_skill_updates(
            list(self.installed_skills.values())
        )

    async def update_skill(self, skill_id: str) -> bool:
        """
        Update a skill to latest version.

        Args:
            skill_id: Skill ID to update

        Returns:
            True if successful
        """
        # Get updated version from marketplace
        updated_skill = await self.marketplace.get_skill(skill_id)

        if not updated_skill:
            return False

        # Uninstall old version
        await self.installer.uninstall_skill(skill_id)

        # Install new version
        success = await self.installer.install_skill(updated_skill)

        if success:
            self.installed_skills[skill_id] = updated_skill

        return success

    async def get_skill(self, skill_id: str) -> Optional[Skill]:
        """Get an installed skill."""
        return self.installed_skills.get(skill_id)

    async def list_skills(
        self,
        enabled_only: bool = False
    ) -> List[Skill]:
        """List installed skills."""
        skills = list(self.installed_skills.values())

        if enabled_only:
            skills = [s for s in skills if s.enabled]

        return skills

    async def enable_skill(self, skill_id: str) -> bool:
        """Enable a skill."""
        success = await self.installer.enable_skill(skill_id)

        if success and skill_id in self.installed_skills:
            self.installed_skills[skill_id].enabled = True

        return success

    async def disable_skill(self, skill_id: str) -> bool:
        """Disable a skill."""
        success = await self.installer.disable_skill(skill_id)

        if success and skill_id in self.installed_skills:
            self.installed_skills[skill_id].enabled = False

        return success


__all__ = [
    'SkillsManager',
    'Skill',
    'SkillVersion',
    'SkillCategory',
    'SkillMarketplace',
    'SkillInstaller',
]
