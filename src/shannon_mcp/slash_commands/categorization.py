"""
Advanced categorization system for slash commands.

This module provides enhanced command categorization capabilities including:
- Auto-categorization based on command patterns
- Dynamic category management
- Category hierarchies and relationships
- Smart category suggestions
- Category-based command filtering and organization
"""

import re
from typing import Dict, Any, List, Optional, Set, Tuple, Pattern
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, Counter
import structlog

from .registry import CommandCategory, Command, CommandRegistry
from .parser import CommandBlock
from ..utils.logging import get_logger
from ..utils.errors import ValidationError

logger = get_logger(__name__)


class AutoCategorizationStrategy(Enum):
    """Strategies for automatic categorization."""
    KEYWORD_BASED = "keyword_based"
    PATTERN_BASED = "pattern_based"
    DESCRIPTION_BASED = "description_based"
    USAGE_BASED = "usage_based"
    HYBRID = "hybrid"


@dataclass
class CategoryRule:
    """Rule for automatic command categorization."""
    category: CommandCategory
    patterns: List[Pattern] = field(default_factory=list)
    keywords: Set[str] = field(default_factory=set)
    description_patterns: List[Pattern] = field(default_factory=list)
    priority: int = 0
    
    def matches(self, command: Command) -> Tuple[bool, float]:
        """
        Check if command matches this rule.
        
        Returns:
            Tuple of (matches, confidence_score)
        """
        confidence = 0.0
        total_checks = 0
        
        # Check command name patterns
        if self.patterns:
            total_checks += 1
            for pattern in self.patterns:
                if pattern.search(command.metadata.name):
                    confidence += 1.0
                    break
        
        # Check keywords in command name
        if self.keywords:
            total_checks += 1
            name_words = set(command.metadata.name.lower().split('_'))
            if self.keywords.intersection(name_words):
                confidence += 1.0
        
        # Check description patterns
        if self.description_patterns:
            total_checks += 1
            for pattern in self.description_patterns:
                if pattern.search(command.metadata.description.lower()):
                    confidence += 1.0
                    break
        
        if total_checks == 0:
            return False, 0.0
        
        final_confidence = confidence / total_checks
        return final_confidence > 0.5, final_confidence


@dataclass
class CategoryMetrics:
    """Metrics for a command category."""
    category: CommandCategory
    command_count: int = 0
    usage_count: int = 0
    average_execution_time: float = 0.0
    success_rate: float = 0.0
    most_used_commands: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "category": self.category.value,
            "command_count": self.command_count,
            "usage_count": self.usage_count,
            "average_execution_time": self.average_execution_time,
            "success_rate": self.success_rate,
            "most_used_commands": self.most_used_commands
        }


@dataclass
class CategoryHierarchy:
    """Hierarchical category relationships."""
    parent: Optional[CommandCategory] = None
    children: Set[CommandCategory] = field(default_factory=set)
    level: int = 0
    
    def add_child(self, child: CommandCategory) -> None:
        """Add child category."""
        self.children.add(child)
    
    def remove_child(self, child: CommandCategory) -> None:
        """Remove child category."""
        self.children.discard(child)
    
    def get_descendants(self) -> Set[CommandCategory]:
        """Get all descendant categories."""
        descendants = set(self.children)
        for child in self.children:
            # This would require access to the full hierarchy
            # Implementation depends on CategoryManager context
            pass
        return descendants


class CategoryManager:
    """Advanced category management system."""
    
    def __init__(self, registry: Optional[CommandRegistry] = None):
        """Initialize category manager."""
        self.registry = registry
        self._rules: List[CategoryRule] = []
        self._hierarchy: Dict[CommandCategory, CategoryHierarchy] = {}
        self._metrics: Dict[CommandCategory, CategoryMetrics] = {}
        
        # Auto-categorization settings
        self.auto_categorization_enabled = True
        self.default_strategy = AutoCategorizationStrategy.HYBRID
        self.confidence_threshold = 0.7
        
        # Initialize default rules
        self._initialize_default_rules()
        self._initialize_hierarchy()
        
        logger.info("category_manager_initialized")
    
    def _initialize_default_rules(self) -> None:
        """Initialize default categorization rules."""
        default_rules = [
            # System commands
            CategoryRule(
                category=CommandCategory.SYSTEM,
                patterns=[
                    re.compile(r'^(config|settings|status|health|info|version|help)'),
                    re.compile(r'^(start|stop|restart|shutdown|reload)')
                ],
                keywords={'system', 'config', 'status', 'health', 'admin'},
                description_patterns=[
                    re.compile(r'system|configuration|admin|manage'),
                    re.compile(r'server|service|daemon')
                ],
                priority=10
            ),
            
            # Session management
            CategoryRule(
                category=CommandCategory.SESSION,
                patterns=[
                    re.compile(r'^(session|connect|disconnect|login|logout)'),
                    re.compile(r'^(save|load|restore|checkpoint)')
                ],
                keywords={'session', 'connect', 'save', 'load', 'restore'},
                description_patterns=[
                    re.compile(r'session|connection|save|load|checkpoint'),
                    re.compile(r'restore|backup|state')
                ],
                priority=9
            ),
            
            # Development commands
            CategoryRule(
                category=CommandCategory.DEVELOPMENT,
                patterns=[
                    re.compile(r'^(build|compile|test|debug|deploy)'),
                    re.compile(r'^(git|npm|pip|docker|k8s)')
                ],
                keywords={'build', 'test', 'debug', 'deploy', 'dev', 'code'},
                description_patterns=[
                    re.compile(r'build|compile|test|debug|development'),
                    re.compile(r'code|programming|software|deploy')
                ],
                priority=8
            ),
            
            # Analysis commands
            CategoryRule(
                category=CommandCategory.ANALYSIS,
                patterns=[
                    re.compile(r'^(analyze|parse|extract|process)'),
                    re.compile(r'^(report|stats|metrics|summary)')
                ],
                keywords={'analyze', 'parse', 'extract', 'report', 'stats'},
                description_patterns=[
                    re.compile(r'analyze|analysis|parse|extract|process'),
                    re.compile(r'report|statistics|metrics|data|summary')
                ],
                priority=7
            ),
            
            # Automation commands
            CategoryRule(
                category=CommandCategory.AUTOMATION,
                patterns=[
                    re.compile(r'^(auto|schedule|cron|batch|bulk)'),
                    re.compile(r'^(workflow|pipeline|task)')
                ],
                keywords={'auto', 'schedule', 'batch', 'workflow', 'automation'},
                description_patterns=[
                    re.compile(r'automat|schedule|batch|workflow|pipeline'),
                    re.compile(r'task|job|cron|recurring')
                ],
                priority=6
            ),
            
            # Integration commands
            CategoryRule(
                category=CommandCategory.INTEGRATION,
                patterns=[
                    re.compile(r'^(api|webhook|sync|import|export)'),
                    re.compile(r'^(github|slack|discord|email)')
                ],
                keywords={'api', 'webhook', 'sync', 'import', 'export', 'integration'},
                description_patterns=[
                    re.compile(r'api|webhook|integrat|sync|import|export'),
                    re.compile(r'github|slack|discord|email|external')
                ],
                priority=5
            )
        ]
        
        self._rules = sorted(default_rules, key=lambda r: r.priority, reverse=True)
        logger.debug("default_categorization_rules_initialized", rule_count=len(self._rules))
    
    def _initialize_hierarchy(self) -> None:
        """Initialize category hierarchy."""
        # System is top-level
        self._hierarchy[CommandCategory.SYSTEM] = CategoryHierarchy(level=0)
        
        # Development and Analysis are major categories
        self._hierarchy[CommandCategory.DEVELOPMENT] = CategoryHierarchy(level=1)
        self._hierarchy[CommandCategory.ANALYSIS] = CategoryHierarchy(level=1)
        
        # Session management under System
        self._hierarchy[CommandCategory.SESSION] = CategoryHierarchy(
            parent=CommandCategory.SYSTEM,
            level=2
        )
        self._hierarchy[CommandCategory.SYSTEM].add_child(CommandCategory.SESSION)
        
        # Automation and Integration as specialized categories
        self._hierarchy[CommandCategory.AUTOMATION] = CategoryHierarchy(level=1)
        self._hierarchy[CommandCategory.INTEGRATION] = CategoryHierarchy(level=1)
        
        # Utility as catch-all
        self._hierarchy[CommandCategory.UTILITY] = CategoryHierarchy(level=2)
        
        # Custom as user-defined
        self._hierarchy[CommandCategory.CUSTOM] = CategoryHierarchy(level=0)
        
        logger.debug("category_hierarchy_initialized")
    
    def add_categorization_rule(self, rule: CategoryRule) -> None:
        """Add a new categorization rule."""
        self._rules.append(rule)
        self._rules.sort(key=lambda r: r.priority, reverse=True)
        logger.debug(
            "categorization_rule_added",
            category=rule.category.value,
            priority=rule.priority
        )
    
    def remove_categorization_rule(self, category: CommandCategory, index: int = 0) -> bool:
        """Remove a categorization rule."""
        rules_for_category = [r for r in self._rules if r.category == category]
        if index < len(rules_for_category):
            rule_to_remove = rules_for_category[index]
            self._rules.remove(rule_to_remove)
            logger.debug("categorization_rule_removed", category=category.value)
            return True
        return False
    
    def auto_categorize_command(
        self,
        command: Command,
        strategy: Optional[AutoCategorizationStrategy] = None
    ) -> Tuple[CommandCategory, float]:
        """
        Automatically categorize a command.
        
        Args:
            command: Command to categorize
            strategy: Categorization strategy to use
            
        Returns:
            Tuple of (suggested_category, confidence)
        """
        if not self.auto_categorization_enabled:
            return CommandCategory.UTILITY, 0.0
        
        strategy = strategy or self.default_strategy
        
        if strategy == AutoCategorizationStrategy.HYBRID:
            return self._hybrid_categorization(command)
        elif strategy == AutoCategorizationStrategy.KEYWORD_BASED:
            return self._keyword_categorization(command)
        elif strategy == AutoCategorizationStrategy.PATTERN_BASED:
            return self._pattern_categorization(command)
        elif strategy == AutoCategorizationStrategy.DESCRIPTION_BASED:
            return self._description_categorization(command)
        elif strategy == AutoCategorizationStrategy.USAGE_BASED:
            return self._usage_categorization(command)
        else:
            return CommandCategory.UTILITY, 0.0
    
    def _hybrid_categorization(self, command: Command) -> Tuple[CommandCategory, float]:
        """Hybrid categorization using multiple strategies."""
        best_category = CommandCategory.UTILITY
        best_confidence = 0.0
        
        # Check all rules
        for rule in self._rules:
            matches, confidence = rule.matches(command)
            if matches and confidence > best_confidence:
                best_category = rule.category
                best_confidence = confidence
        
        # Apply confidence threshold
        if best_confidence < self.confidence_threshold:
            return CommandCategory.UTILITY, best_confidence
        
        return best_category, best_confidence
    
    def _keyword_categorization(self, command: Command) -> Tuple[CommandCategory, float]:
        """Categorize based on keywords in command name."""
        name_words = set(command.metadata.name.lower().split('_'))
        
        best_category = CommandCategory.UTILITY
        best_score = 0.0
        
        for rule in self._rules:
            if rule.keywords:
                overlap = rule.keywords.intersection(name_words)
                score = len(overlap) / len(rule.keywords)
                if score > best_score:
                    best_category = rule.category
                    best_score = score
        
        return best_category, best_score
    
    def _pattern_categorization(self, command: Command) -> Tuple[CommandCategory, float]:
        """Categorize based on name patterns."""
        best_category = CommandCategory.UTILITY
        best_confidence = 0.0
        
        for rule in self._rules:
            for pattern in rule.patterns:
                if pattern.search(command.metadata.name):
                    confidence = 1.0  # Pattern match is binary
                    if confidence > best_confidence:
                        best_category = rule.category
                        best_confidence = confidence
                    break
        
        return best_category, best_confidence
    
    def _description_categorization(self, command: Command) -> Tuple[CommandCategory, float]:
        """Categorize based on command description."""
        description = command.metadata.description.lower()
        
        best_category = CommandCategory.UTILITY
        best_confidence = 0.0
        
        for rule in self._rules:
            for pattern in rule.description_patterns:
                if pattern.search(description):
                    confidence = 1.0
                    if confidence > best_confidence:
                        best_category = rule.category
                        best_confidence = confidence
                    break
        
        return best_category, best_confidence
    
    def _usage_categorization(self, command: Command) -> Tuple[CommandCategory, float]:
        """Categorize based on usage patterns (requires usage data)."""
        # This would require integration with execution history
        # For now, return default
        return CommandCategory.UTILITY, 0.0
    
    def suggest_category_for_command_block(self, command_block: CommandBlock) -> CommandCategory:
        """Suggest category for a command block."""
        # Create a temporary command for categorization
        from .registry import CommandMetadata
        
        temp_metadata = CommandMetadata(
            name=command_block.command_name,
            description=command_block.content or f"Command: {command_block.command_name}",
            category=CommandCategory.UTILITY
        )
        
        temp_command = Command(metadata=temp_metadata, handler=lambda: None)
        
        category, confidence = self.auto_categorize_command(temp_command)
        
        logger.debug(
            "category_suggested",
            command=command_block.command_name,
            suggested_category=category.value,
            confidence=confidence
        )
        
        return category
    
    def get_category_metrics(self, category: CommandCategory) -> CategoryMetrics:
        """Get metrics for a category."""
        if category not in self._metrics:
            self._metrics[category] = CategoryMetrics(category=category)
        
        # Update metrics if registry is available
        if self.registry:
            self._update_category_metrics(category)
        
        return self._metrics[category]
    
    def _update_category_metrics(self, category: CommandCategory) -> None:
        """Update metrics for a category."""
        commands = self.registry.list_commands(category=category)
        
        if not commands:
            return
        
        metrics = self._metrics.setdefault(category, CategoryMetrics(category=category))
        metrics.command_count = len(commands)
        
        total_usage = sum(cmd.usage_count for cmd in commands)
        metrics.usage_count = total_usage
        
        # Calculate success rate and execution time (simplified)
        if commands:
            metrics.success_rate = 1.0  # Would need execution history
            metrics.average_execution_time = 0.0  # Would need execution history
            
            # Most used commands
            sorted_commands = sorted(commands, key=lambda c: c.usage_count, reverse=True)
            metrics.most_used_commands = [cmd.metadata.name for cmd in sorted_commands[:5]]
    
    def get_all_category_metrics(self) -> Dict[CommandCategory, CategoryMetrics]:
        """Get metrics for all categories."""
        if self.registry:
            for category in CommandCategory:
                self._update_category_metrics(category)
        
        return self._metrics.copy()
    
    def get_category_hierarchy(self) -> Dict[CommandCategory, CategoryHierarchy]:
        """Get category hierarchy."""
        return self._hierarchy.copy()
    
    def get_related_categories(self, category: CommandCategory) -> Set[CommandCategory]:
        """Get categories related to the given one."""
        hierarchy = self._hierarchy.get(category)
        if not hierarchy:
            return set()
        
        related = set()
        
        # Add parent
        if hierarchy.parent:
            related.add(hierarchy.parent)
        
        # Add children
        related.update(hierarchy.children)
        
        # Add siblings (same parent)
        if hierarchy.parent:
            parent_hierarchy = self._hierarchy.get(hierarchy.parent)
            if parent_hierarchy:
                siblings = parent_hierarchy.children - {category}
                related.update(siblings)
        
        return related
    
    def reorganize_commands_by_category(self) -> Dict[CommandCategory, List[str]]:
        """Reorganize all commands by their optimal categories."""
        if not self.registry:
            return {}
        
        reorganization = defaultdict(list)
        
        for command in self.registry.list_commands():
            optimal_category, confidence = self.auto_categorize_command(command)
            
            # Only suggest reorganization if confidence is high
            if confidence >= self.confidence_threshold and optimal_category != command.metadata.category:
                reorganization[optimal_category].append(command.metadata.name)
                
                logger.debug(
                    "command_reorganization_suggested",
                    command=command.metadata.name,
                    current_category=command.metadata.category.value,
                    suggested_category=optimal_category.value,
                    confidence=confidence
                )
        
        return dict(reorganization)
    
    def validate_category_distribution(self) -> Dict[str, Any]:
        """Validate the distribution of commands across categories."""
        if not self.registry:
            return {"error": "No registry available"}
        
        distribution = Counter()
        total_commands = 0
        
        for category in CommandCategory:
            commands = self.registry.list_commands(category=category)
            count = len(commands)
            distribution[category.value] = count
            total_commands += count
        
        # Calculate statistics
        avg_per_category = total_commands / len(CommandCategory) if total_commands > 0 else 0
        
        # Identify categories that might be over/under-utilized
        overloaded = {cat: count for cat, count in distribution.items() if count > avg_per_category * 2}
        underutilized = {cat: count for cat, count in distribution.items() if count < avg_per_category * 0.5}
        
        return {
            "total_commands": total_commands,
            "distribution": dict(distribution),
            "average_per_category": avg_per_category,
            "overloaded_categories": overloaded,
            "underutilized_categories": underutilized,
            "most_used_category": distribution.most_common(1)[0] if distribution else None,
            "balance_score": self._calculate_balance_score(distribution)
        }
    
    def _calculate_balance_score(self, distribution: Counter) -> float:
        """Calculate balance score for category distribution (0-1, higher is better)."""
        if not distribution:
            return 0.0
        
        counts = list(distribution.values())
        if not counts:
            return 0.0
        
        # Use coefficient of variation (lower is more balanced)
        mean_count = sum(counts) / len(counts)
        if mean_count == 0:
            return 1.0
        
        variance = sum((count - mean_count) ** 2 for count in counts) / len(counts)
        std_dev = variance ** 0.5
        cv = std_dev / mean_count
        
        # Convert to balance score (0-1, where 1 is perfectly balanced)
        return max(0.0, 1.0 - min(cv, 1.0))
    
    def get_stats(self) -> Dict[str, Any]:
        """Get categorization system statistics."""
        stats = {
            "auto_categorization_enabled": self.auto_categorization_enabled,
            "default_strategy": self.default_strategy.value,
            "confidence_threshold": self.confidence_threshold,
            "total_rules": len(self._rules),
            "rules_by_category": {},
            "hierarchy_levels": {}
        }
        
        # Rules by category
        rule_counts = Counter(rule.category.value for rule in self._rules)
        stats["rules_by_category"] = dict(rule_counts)
        
        # Hierarchy levels
        level_counts = Counter(hierarchy.level for hierarchy in self._hierarchy.values())
        stats["hierarchy_levels"] = dict(level_counts)
        
        # Category metrics
        if self.registry:
            stats["category_metrics"] = {
                cat.value: metrics.to_dict()
                for cat, metrics in self.get_all_category_metrics().items()
            }
            
            stats["distribution_analysis"] = self.validate_category_distribution()
        
        return stats


# Export public API
__all__ = [
    'CategoryManager',
    'CategoryRule',
    'CategoryMetrics',
    'CategoryHierarchy',
    'AutoCategorizationStrategy'
]