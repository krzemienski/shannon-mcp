"""
Input validation utilities for Shannon MCP Server.
"""

from typing import Any, Dict, List, Optional, Union, Callable, Type
from dataclasses import dataclass
import re
import json
from datetime import datetime
from pathlib import Path

from .errors import ValidationError


@dataclass
class ValidationRule:
    """Represents a validation rule."""
    name: str
    validator: Callable[[Any], bool]
    message: str
    code: str


class Validator:
    """Base validator class."""
    
    def __init__(self, field_name: str):
        self.field_name = field_name
        self.rules: List[ValidationRule] = []
    
    def add_rule(self, rule: ValidationRule) -> 'Validator':
        """Add a validation rule."""
        self.rules.append(rule)
        return self
    
    def required(self, message: Optional[str] = None) -> 'Validator':
        """Require field to be present and not None."""
        rule = ValidationRule(
            name="required",
            validator=lambda x: x is not None,
            message=message or f"{self.field_name} is required",
            code="REQUIRED"
        )
        return self.add_rule(rule)
    
    def not_empty(self, message: Optional[str] = None) -> 'Validator':
        """Require field to not be empty."""
        def is_not_empty(value: Any) -> bool:
            if value is None:
                return False
            if isinstance(value, (str, list, dict)):
                return len(value) > 0
            return True
        
        rule = ValidationRule(
            name="not_empty",
            validator=is_not_empty,
            message=message or f"{self.field_name} cannot be empty",
            code="NOT_EMPTY"
        )
        return self.add_rule(rule)
    
    def min_length(self, length: int, message: Optional[str] = None) -> 'Validator':
        """Require minimum length."""
        rule = ValidationRule(
            name="min_length",
            validator=lambda x: x is not None and len(str(x)) >= length,
            message=message or f"{self.field_name} must be at least {length} characters",
            code="MIN_LENGTH"
        )
        return self.add_rule(rule)
    
    def max_length(self, length: int, message: Optional[str] = None) -> 'Validator':
        """Require maximum length."""
        rule = ValidationRule(
            name="max_length",
            validator=lambda x: x is None or len(str(x)) <= length,
            message=message or f"{self.field_name} must be at most {length} characters",
            code="MAX_LENGTH"
        )
        return self.add_rule(rule)
    
    def pattern(self, regex: Union[str, re.Pattern], message: Optional[str] = None) -> 'Validator':
        """Require field to match regex pattern."""
        if isinstance(regex, str):
            regex = re.compile(regex)
        
        rule = ValidationRule(
            name="pattern",
            validator=lambda x: x is None or bool(regex.match(str(x))),
            message=message or f"{self.field_name} format is invalid",
            code="PATTERN"
        )
        return self.add_rule(rule)
    
    def in_choices(self, choices: List[Any], message: Optional[str] = None) -> 'Validator':
        """Require field to be one of the given choices."""
        rule = ValidationRule(
            name="in_choices",
            validator=lambda x: x is None or x in choices,
            message=message or f"{self.field_name} must be one of: {', '.join(map(str, choices))}",
            code="IN_CHOICES"
        )
        return self.add_rule(rule)
    
    def type_check(self, expected_type: Type, message: Optional[str] = None) -> 'Validator':
        """Require field to be of specific type."""
        rule = ValidationRule(
            name="type_check",
            validator=lambda x: x is None or isinstance(x, expected_type),
            message=message or f"{self.field_name} must be of type {expected_type.__name__}",
            code="TYPE_CHECK"
        )
        return self.add_rule(rule)
    
    def range_check(self, min_val: Optional[Union[int, float]] = None, 
                   max_val: Optional[Union[int, float]] = None,
                   message: Optional[str] = None) -> 'Validator':
        """Require field to be within numeric range."""
        def in_range(value: Any) -> bool:
            if value is None:
                return True
            try:
                num_val = float(value)
                if min_val is not None and num_val < min_val:
                    return False
                if max_val is not None and num_val > max_val:
                    return False
                return True
            except (ValueError, TypeError):
                return False
        
        range_desc = []
        if min_val is not None:
            range_desc.append(f"≥ {min_val}")
        if max_val is not None:
            range_desc.append(f"≤ {max_val}")
        range_str = " and ".join(range_desc)
        
        rule = ValidationRule(
            name="range_check",
            validator=in_range,
            message=message or f"{self.field_name} must be {range_str}",
            code="RANGE_CHECK"
        )
        return self.add_rule(rule)
    
    def custom(self, validator_fn: Callable[[Any], bool], 
              message: str, code: str = "CUSTOM") -> 'Validator':
        """Add custom validation rule."""
        rule = ValidationRule(
            name="custom",
            validator=validator_fn,
            message=message,
            code=code
        )
        return self.add_rule(rule)
    
    def validate(self, value: Any) -> None:
        """Validate value against all rules."""
        for rule in self.rules:
            if not rule.validator(value):
                raise ValidationError(
                    field=self.field_name,
                    value=value,
                    constraint=rule.message
                )


class SchemaValidator:
    """Validates complex data structures against schemas."""
    
    def __init__(self):
        self.validators: Dict[str, Validator] = {}
    
    def field(self, name: str) -> Validator:
        """Create validator for a field."""
        validator = Validator(name)
        self.validators[name] = validator
        return validator
    
    def validate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate data against schema."""
        errors = []
        
        for field_name, validator in self.validators.items():
            value = data.get(field_name)
            try:
                validator.validate(value)
            except ValidationError as e:
                errors.append(e)
        
        if errors:
            # Raise first error (could be enhanced to collect all errors)
            raise errors[0]
        
        return data


# Pre-built validators for common patterns

def email_validator(field_name: str = "email") -> Validator:
    """Email address validator."""
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return (Validator(field_name)
            .required()
            .pattern(email_pattern, f"{field_name} must be a valid email address"))


def url_validator(field_name: str = "url") -> Validator:
    """URL validator."""
    url_pattern = r'^https?://[^\s/$.?#].[^\s]*$'
    return (Validator(field_name)
            .required()
            .pattern(url_pattern, f"{field_name} must be a valid URL"))


def uuid_validator(field_name: str = "id") -> Validator:
    """UUID validator."""
    uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
    return (Validator(field_name)
            .required()
            .pattern(uuid_pattern, f"{field_name} must be a valid UUID"))


def session_id_validator(field_name: str = "session_id") -> Validator:
    """Session ID validator."""
    return (Validator(field_name)
            .required()
            .min_length(8)
            .max_length(64)
            .pattern(r'^[a-zA-Z0-9_-]+$', f"{field_name} contains invalid characters"))


def agent_id_validator(field_name: str = "agent_id") -> Validator:
    """Agent ID validator."""
    return (Validator(field_name)
            .required()
            .min_length(1)
            .max_length(64)
            .pattern(r'^[a-zA-Z0-9_-]+$', f"{field_name} contains invalid characters"))


def json_validator(field_name: str = "data") -> Validator:
    """JSON string validator."""
    def is_valid_json(value: Any) -> bool:
        if value is None:
            return True
        try:
            json.loads(str(value))
            return True
        except (json.JSONDecodeError, TypeError):
            return False
    
    return (Validator(field_name)
            .custom(is_valid_json, f"{field_name} must be valid JSON", "INVALID_JSON"))


def file_path_validator(field_name: str = "path", must_exist: bool = False) -> Validator:
    """File path validator."""
    def is_valid_path(value: Any) -> bool:
        if value is None:
            return True
        try:
            path = Path(str(value))
            if must_exist:
                return path.exists()
            return True
        except (OSError, ValueError):
            return False
    
    message = f"{field_name} must be a valid file path"
    if must_exist:
        message += " and must exist"
    
    return (Validator(field_name)
            .custom(is_valid_path, message, "INVALID_PATH"))


def datetime_validator(field_name: str = "timestamp") -> Validator:
    """ISO datetime string validator."""
    def is_valid_datetime(value: Any) -> bool:
        if value is None:
            return True
        try:
            datetime.fromisoformat(str(value).replace('Z', '+00:00'))
            return True
        except (ValueError, TypeError):
            return False
    
    return (Validator(field_name)
            .custom(is_valid_datetime, 
                   f"{field_name} must be a valid ISO datetime string", 
                   "INVALID_DATETIME"))


def port_validator(field_name: str = "port") -> Validator:
    """Network port validator."""
    return (Validator(field_name)
            .type_check(int)
            .range_check(1, 65535, f"{field_name} must be between 1 and 65535"))


def positive_integer_validator(field_name: str = "value") -> Validator:
    """Positive integer validator."""
    return (Validator(field_name)
            .type_check(int)
            .range_check(1, None, f"{field_name} must be a positive integer"))


def non_negative_integer_validator(field_name: str = "value") -> Validator:
    """Non-negative integer validator."""
    return (Validator(field_name)
            .type_check(int)
            .range_check(0, None, f"{field_name} must be a non-negative integer"))


def percentage_validator(field_name: str = "percentage") -> Validator:
    """Percentage validator (0-100)."""
    return (Validator(field_name)
            .type_check((int, float))
            .range_check(0, 100, f"{field_name} must be between 0 and 100"))


# Schema validators for common Shannon MCP objects

def create_session_schema() -> SchemaValidator:
    """Schema for session creation requests."""
    schema = SchemaValidator()
    schema.field("prompt").required().not_empty().max_length(10000)
    schema.field("model").not_empty().max_length(100)
    schema.field("checkpoint_id").pattern(r'^[a-zA-Z0-9_-]+$')
    schema.field("context").type_check(dict)
    return schema


def agent_task_schema() -> SchemaValidator:
    """Schema for agent task assignment."""
    schema = SchemaValidator()
    schema.field("agent_id").required().min_length(1).max_length(64)
    schema.field("task").required().not_empty().max_length(5000)
    schema.field("priority").type_check(int).range_check(1, 10)
    schema.field("context").type_check(dict)
    schema.field("timeout").type_check(int).range_check(1, 3600)
    return schema


def checkpoint_schema() -> SchemaValidator:
    """Schema for checkpoint creation."""
    schema = SchemaValidator()
    schema.field("session_id").required().min_length(8).max_length(64)
    schema.field("name").max_length(100)
    schema.field("description").max_length(500)
    schema.field("tags").type_check(list)
    return schema


def analytics_query_schema() -> SchemaValidator:
    """Schema for analytics queries."""
    schema = SchemaValidator()
    schema.field("query_type").required().in_choices([
        "usage", "performance", "errors", "sessions", "agents", "tools", "resources"
    ])
    schema.field("parameters").type_check(dict)
    schema.field("limit").type_check(int).range_check(1, 10000)
    schema.field("offset").type_check(int).range_check(0, None)
    return schema


def hook_registration_schema() -> SchemaValidator:
    """Schema for hook registration."""
    schema = SchemaValidator()
    schema.field("name").required().not_empty().max_length(100)
    schema.field("event").required().not_empty().max_length(100)
    schema.field("type").required().in_choices(["shell", "http", "webhook", "function"])
    schema.field("target").required().not_empty().max_length(500)
    schema.field("filter_pattern").max_length(200)
    schema.field("retry_count").type_check(int).range_check(0, 10)
    schema.field("timeout").type_check(int).range_check(1, 300)
    return schema


# Utility functions

def validate_and_sanitize_input(data: Dict[str, Any], schema: SchemaValidator) -> Dict[str, Any]:
    """Validate and sanitize input data."""
    # First validate
    validated_data = schema.validate(data)
    
    # Then sanitize strings
    sanitized_data = {}
    for key, value in validated_data.items():
        if isinstance(value, str):
            # Basic sanitization
            sanitized_data[key] = value.strip()
        else:
            sanitized_data[key] = value
    
    return sanitized_data


def create_validation_error_response(error: ValidationError) -> Dict[str, Any]:
    """Create standardized validation error response."""
    return {
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "Input validation failed",
            "details": {
                "field": getattr(error, 'field', 'unknown'),
                "constraint": getattr(error, 'constraint', str(error)),
                "value": str(getattr(error, 'value', 'unknown'))
            }
        }
    }