"""
Configuration loader for Shannon MCP Server.

This module provides comprehensive configuration management with:
- Multiple configuration sources (files, env vars, CLI)
- Schema validation
- Type coercion
- Configuration merging
- Hot reloading
- Defaults management
"""

import os
import json
import yaml
from pathlib import Path
from typing import Optional, Dict, Any, List, Union, Type, TypeVar, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime
import toml
from pydantic import BaseModel, Field, field_validator, ValidationError, ConfigDict
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent
import structlog
from functools import lru_cache
import asyncio

from .logging import get_logger
from .errors import ConfigurationError, ValidationError as ShannonValidationError
from .notifications import emit, EventCategory, EventPriority


logger = get_logger("shannon-mcp.config")
T = TypeVar('T', bound=BaseModel)


class ConfigSource(BaseModel):
    """Configuration source definition."""
    path: Optional[Path] = None
    data: Dict[str, Any] = Field(default_factory=dict)
    priority: int = 0
    source_type: str = "dict"
    
    model_config = ConfigDict(arbitrary_types_allowed=True)


class DatabaseConfig(BaseModel):
    """Database configuration."""
    path: Path = Field(default_factory=lambda: Path.home() / ".shannon-mcp" / "shannon.db")
    pool_size: int = 5
    timeout: float = 30.0
    journal_mode: str = "WAL"
    synchronous: str = "NORMAL"
    
    @field_validator('path')
    @classmethod
    def validate_path(cls, v):
        """Ensure path is absolute."""
        return v.absolute()


class LoggingConfig(BaseModel):
    """Logging configuration."""
    level: str = "INFO"
    format: str = "json"
    directory: Path = Field(default_factory=lambda: Path.home() / ".shannon-mcp" / "logs")
    max_size: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 10
    enable_sentry: bool = False
    sentry_dsn: Optional[str] = None
    
    @field_validator('level')
    @classmethod
    def validate_level(cls, v):
        """Validate log level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Invalid log level: {v}")
        return v.upper()


class BinaryManagerConfig(BaseModel):
    """Binary manager configuration."""
    search_paths: List[Path] = Field(default_factory=list)
    nvm_check: bool = True
    update_check_interval: int = 86400  # 24 hours
    cache_timeout: int = 3600  # 1 hour
    allowed_versions: Optional[List[str]] = None
    
    @field_validator('search_paths', mode='before')
    @classmethod
    def parse_search_paths(cls, v):
        """Parse search paths from various formats."""
        if isinstance(v, str):
            return [Path(p.strip()) for p in v.split(":")]
        elif isinstance(v, list):
            return [Path(p) for p in v]
        return v


class SessionManagerConfig(BaseModel):
    """Session manager configuration."""
    max_concurrent_sessions: int = 10
    session_timeout: int = 3600  # 1 hour
    buffer_size: int = 1024 * 1024  # 1MB
    stream_chunk_size: int = 8192
    enable_metrics: bool = True
    enable_replay: bool = False


class AgentSystemConfig(BaseModel):
    """Agent system configuration."""
    agents_directory: Path = Field(default_factory=lambda: Path.home() / ".claude" / "agents")
    github_import_enabled: bool = True
    execution_timeout: int = 300  # 5 minutes
    max_retries: int = 3
    enable_sandboxing: bool = True
    allowed_categories: List[str] = Field(default_factory=lambda: ["general", "development", "analysis"])


class AgentManagerConfig(BaseModel):
    """Agent manager configuration."""
    enable_default_agents: bool = True
    github_org: Optional[str] = None
    github_token: Optional[str] = None
    max_concurrent_tasks: int = 20
    task_timeout: int = 300  # 5 minutes
    collaboration_enabled: bool = True
    performance_tracking: bool = True


class CheckpointConfig(BaseModel):
    """Checkpoint system configuration."""
    storage_path: Path = Field(default_factory=lambda: Path.home() / ".shannon-mcp" / "checkpoints")
    compression_enabled: bool = True
    compression_level: int = 6
    auto_checkpoint_interval: int = 300  # 5 minutes
    max_checkpoints: int = 100
    cleanup_age_days: int = 30


class HooksConfig(BaseModel):
    """Hooks framework configuration."""
    config_paths: List[Path] = Field(default_factory=list)
    timeout: int = 30
    max_parallel: int = 5
    enable_templates: bool = True
    fail_fast: bool = False


class MCPConfig(BaseModel):
    """MCP protocol configuration."""
    transport: str = "stdio"
    stdio_command: Optional[str] = None
    sse_endpoint: Optional[str] = None
    connection_timeout: int = 30
    request_timeout: int = 300
    max_message_size: int = 10 * 1024 * 1024  # 10MB
    enable_compression: bool = True
    auto_discovery: bool = True


class AnalyticsConfig(BaseModel):
    """Analytics configuration."""
    enabled: bool = True
    metrics_path: Path = Field(default_factory=lambda: Path.home() / ".shannon-mcp" / "metrics")
    retention_days: int = 90
    export_formats: List[str] = Field(default_factory=lambda: ["json", "csv"])
    aggregation_interval: int = 3600  # 1 hour


class ShannonConfig(BaseModel):
    """Main Shannon MCP configuration."""
    # Core settings
    app_name: str = "shannon-mcp"
    version: str = "0.1.0"
    debug: bool = False
    
    # Component configurations
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    binary_manager: BinaryManagerConfig = Field(default_factory=BinaryManagerConfig)
    session_manager: SessionManagerConfig = Field(default_factory=SessionManagerConfig)
    agent_system: AgentSystemConfig = Field(default_factory=AgentSystemConfig)
    agent_manager: AgentManagerConfig = Field(default_factory=AgentManagerConfig)
    checkpoint: CheckpointConfig = Field(default_factory=CheckpointConfig)
    hooks: HooksConfig = Field(default_factory=HooksConfig)
    mcp: MCPConfig = Field(default_factory=MCPConfig)
    analytics: AnalyticsConfig = Field(default_factory=AnalyticsConfig)
    
    # Runtime settings
    enable_hot_reload: bool = True
    config_paths: List[Path] = Field(default_factory=list)
    
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        validate_assignment=True
    )


class ConfigLoader:
    """Configuration loader with multiple source support."""
    
    def __init__(self):
        """Initialize configuration loader."""
        self._sources: List[ConfigSource] = []
        self._config: Optional[ShannonConfig] = None
        self._observers: List[Observer] = []
        self._callbacks: List[Callable[[ShannonConfig], None]] = []
        self._lock = asyncio.Lock()
    
    def add_source(
        self,
        source: Union[str, Path, Dict[str, Any]],
        priority: int = 0,
        source_type: Optional[str] = None
    ) -> None:
        """
        Add configuration source.
        
        Args:
            source: Configuration source (file path or dict)
            priority: Source priority (higher wins)
            source_type: Source type (auto-detected if None)
        """
        if isinstance(source, (str, Path)):
            path = Path(source)
            if not source_type:
                source_type = self._detect_source_type(path)
            
            self._sources.append(ConfigSource(
                path=path,
                priority=priority,
                source_type=source_type
            ))
        else:
            self._sources.append(ConfigSource(
                data=source,
                priority=priority,
                source_type="dict"
            ))
        
        # Sort by priority
        self._sources.sort(key=lambda s: s.priority, reverse=True)
    
    def _detect_source_type(self, path: Path) -> str:
        """Detect configuration file type."""
        suffix = path.suffix.lower()
        if suffix == ".json":
            return "json"
        elif suffix in (".yaml", ".yml"):
            return "yaml"
        elif suffix == ".toml":
            return "toml"
        elif suffix == ".env":
            return "env"
        else:
            raise ConfigurationError(f"Unknown config file type: {suffix}")
    
    async def load(self) -> ShannonConfig:
        """
        Load configuration from all sources.
        
        Returns:
            Merged configuration
        """
        async with self._lock:
            merged_data = {}
            
            # Load from sources in priority order
            for source in self._sources:
                try:
                    data = await self._load_source(source)
                    merged_data = self._deep_merge(merged_data, data)
                except Exception as e:
                    logger.error(
                        "failed_to_load_source",
                        source=str(source.path or "dict"),
                        error=str(e)
                    )
                    if source.priority > 100:  # Critical source
                        raise
            
            # Load environment variables
            env_data = self._load_env_vars()
            merged_data = self._deep_merge(merged_data, env_data)
            
            # Create and validate configuration
            try:
                self._config = ShannonConfig(**merged_data)
                logger.info("configuration_loaded", sources=len(self._sources))
                
                # Emit configuration loaded event
                await emit(
                    "config_loaded",
                    EventCategory.SYSTEM,
                    {"config": self._config.dict()},
                    priority=EventPriority.HIGH
                )
                
                # Set up hot reload if enabled
                if self._config.enable_hot_reload:
                    await self._setup_hot_reload()
                
                return self._config
                
            except ValidationError as e:
                errors = []
                for error in e.errors():
                    field = ".".join(str(x) for x in error["loc"])
                    msg = error["msg"]
                    errors.append(f"{field}: {msg}")
                
                raise ConfigurationError(
                    f"Configuration validation failed: {'; '.join(errors)}"
                ) from e
    
    async def _load_source(self, source: ConfigSource) -> Dict[str, Any]:
        """Load data from a configuration source."""
        if source.path is None:
            return source.data
        
        if not source.path.exists():
            logger.warning("config_file_not_found", path=str(source.path))
            return {}
        
        content = source.path.read_text()
        
        if source.source_type == "json":
            return json.loads(content)
        elif source.source_type == "yaml":
            return yaml.safe_load(content) or {}
        elif source.source_type == "toml":
            return toml.loads(content)
        elif source.source_type == "env":
            return self._parse_env_file(content)
        else:
            raise ConfigurationError(f"Unknown source type: {source.source_type}")
    
    def _parse_env_file(self, content: str) -> Dict[str, Any]:
        """Parse .env file format."""
        result = {}
        
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            
            if "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                
                # Convert to nested structure
                parts = key.lower().split("_")
                current = result
                
                for part in parts[:-1]:
                    if part not in current:
                        current[part] = {}
                    current = current[part]
                
                current[parts[-1]] = value
        
        return result
    
    def _load_env_vars(self) -> Dict[str, Any]:
        """Load configuration from environment variables."""
        result = {}
        prefix = "SHANNON_"
        
        for key, value in os.environ.items():
            if key.startswith(prefix):
                # Remove prefix and convert to lowercase
                key = key[len(prefix):].lower()
                
                # Convert to nested structure
                parts = key.split("_")
                current = result
                
                for part in parts[:-1]:
                    if part not in current:
                        current[part] = {}
                    current = current[part]
                
                # Type conversion
                current[parts[-1]] = self._convert_value(value)
        
        return result
    
    def _convert_value(self, value: str) -> Any:
        """Convert string value to appropriate type."""
        # Boolean
        if value.lower() in ("true", "yes", "1", "on"):
            return True
        elif value.lower() in ("false", "no", "0", "off"):
            return False
        
        # Number
        try:
            if "." in value:
                return float(value)
            else:
                return int(value)
        except ValueError:
            pass
        
        # List (comma-separated)
        if "," in value:
            return [v.strip() for v in value.split(",")]
        
        # Path
        if value.startswith("/") or value.startswith("~"):
            return Path(value).expanduser()
        
        return value
    
    def _deep_merge(self, base: Dict[str, Any], update: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge two dictionaries."""
        result = base.copy()
        
        for key, value in update.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result
    
    async def _setup_hot_reload(self) -> None:
        """Set up hot reload for configuration files."""
        for source in self._sources:
            if source.path and source.path.exists():
                observer = Observer()
                handler = ConfigFileHandler(self, source.path)
                observer.schedule(handler, str(source.path.parent), recursive=False)
                observer.start()
                self._observers.append(observer)
                
                logger.info("hot_reload_enabled", path=str(source.path))
    
    def register_callback(self, callback: Callable[[ShannonConfig], None]) -> None:
        """Register configuration change callback."""
        self._callbacks.append(callback)
    
    async def _reload(self) -> None:
        """Reload configuration."""
        logger.info("reloading_configuration")
        
        try:
            old_config = self._config
            new_config = await self.load()
            
            # Notify callbacks if configuration changed
            if old_config != new_config:
                for callback in self._callbacks:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(new_config)
                        else:
                            callback(new_config)
                    except Exception as e:
                        logger.error(
                            "callback_error",
                            callback=callback.__name__,
                            error=str(e)
                        )
                
                # Emit configuration changed event
                await emit(
                    "config_changed",
                    EventCategory.SYSTEM,
                    {
                        "old_config": old_config.dict() if old_config else None,
                        "new_config": new_config.dict()
                    },
                    priority=EventPriority.HIGH
                )
                
        except Exception as e:
            logger.error("reload_failed", error=str(e))
    
    def get_config(self) -> ShannonConfig:
        """Get current configuration."""
        if self._config is None:
            raise ConfigurationError("Configuration not loaded")
        return self._config
    
    def shutdown(self) -> None:
        """Shutdown configuration loader."""
        for observer in self._observers:
            observer.stop()
            observer.join()
        self._observers.clear()


class ConfigFileHandler(FileSystemEventHandler):
    """File system event handler for configuration files."""
    
    def __init__(self, loader: ConfigLoader, path: Path):
        self.loader = loader
        self.path = path
    
    def on_modified(self, event: FileModifiedEvent) -> None:
        """Handle file modification."""
        if not event.is_directory and Path(event.src_path) == self.path:
            logger.info("config_file_modified", path=event.src_path)
            asyncio.create_task(self.loader._reload())


# Global configuration instance
_config_loader: Optional[ConfigLoader] = None


def get_config_loader() -> ConfigLoader:
    """Get global configuration loader."""
    global _config_loader
    if _config_loader is None:
        _config_loader = ConfigLoader()
    return _config_loader


async def load_config(
    config_paths: Optional[List[Union[str, Path]]] = None,
    extra_config: Optional[Dict[str, Any]] = None
) -> ShannonConfig:
    """
    Load configuration from standard locations.
    
    Args:
        config_paths: Additional configuration paths
        extra_config: Extra configuration to merge
    
    Returns:
        Loaded configuration
    """
    loader = get_config_loader()
    
    # Add default configuration paths
    default_paths = [
        Path.home() / ".shannon-mcp" / "config.yaml",
        Path.home() / ".shannon-mcp" / "config.json",
        Path("/etc/shannon-mcp/config.yaml"),
        Path("./shannon-mcp.yaml"),
        Path("./shannon-mcp.json"),
    ]
    
    for path in default_paths:
        if path.exists():
            loader.add_source(path, priority=10)
    
    # Add user-specified paths
    if config_paths:
        for i, path in enumerate(config_paths):
            loader.add_source(path, priority=20 + i)
    
    # Add extra configuration
    if extra_config:
        loader.add_source(extra_config, priority=100)
    
    return await loader.load()


def get_config() -> ShannonConfig:
    """Get current configuration."""
    return get_config_loader().get_config()


# Export public API
__all__ = [
    'ShannonConfig',
    'DatabaseConfig',
    'LoggingConfig',
    'BinaryManagerConfig',
    'SessionManagerConfig',
    'AgentSystemConfig',
    'AgentManagerConfig',
    'CheckpointConfig',
    'HooksConfig',
    'MCPConfig',
    'AnalyticsConfig',
    'ConfigLoader',
    'get_config_loader',
    'load_config',
    'get_config',
]