"""
Input validation utilities for Structural Design Platform.

This module provides validation functions for all user inputs to prevent
crashes from edge cases like empty inputs, negative values, extremely
large values, and garbage text.

Usage:
    from src.validators import validate_dimension, validate_load, validate_positive
    
    # These raise ValueError with descriptive messages if invalid
    width = validate_dimension(user_input, "Building Width", min_val=1.0, max_val=100.0)
    load = validate_load(user_input, "Floor Load")
"""

from typing import Union, Optional, Any
from .logging_config import get_logger

logger = get_logger(__name__)


class ValidationError(ValueError):
    """Custom validation error with user-friendly messages."""
    pass


def validate_positive(
    value: Any,
    field_name: str,
    min_val: float = 0.0,
    max_val: float = float('inf'),
    allow_zero: bool = False
) -> float:
    """
    Validate that a value is a positive number within bounds.
    
    Args:
        value: The value to validate.
        field_name: Name of the field (for error messages).
        min_val: Minimum allowed value.
        max_val: Maximum allowed value.
        allow_zero: Whether zero is allowed.
    
    Returns:
        The validated value as a float.
    
    Raises:
        ValidationError: If validation fails.
    """
    # Handle None
    if value is None:
        raise ValidationError(f"{field_name}: Value cannot be empty")
    
    # Handle empty strings
    if isinstance(value, str):
        value = value.strip()
        if not value:
            raise ValidationError(f"{field_name}: Value cannot be empty")
        
        # Try to convert to float
        try:
            value = float(value)
        except (ValueError, TypeError):
            raise ValidationError(f"{field_name}: '{value}' is not a valid number")
    
    # Ensure it's a number
    try:
        value = float(value)
    except (ValueError, TypeError):
        raise ValidationError(f"{field_name}: Value must be a number")
    
    # Check for NaN or infinity
    import math
    if math.isnan(value) or math.isinf(value):
        raise ValidationError(f"{field_name}: Value must be a finite number")
    
    # Check for negative
    if value < 0:
        raise ValidationError(f"{field_name}: Value cannot be negative (got {value})")
    
    # Check for zero
    if value == 0 and not allow_zero:
        raise ValidationError(f"{field_name}: Value cannot be zero")
    
    # Check bounds
    if value < min_val:
        raise ValidationError(f"{field_name}: Value {value} is below minimum {min_val}")
    
    if value > max_val:
        raise ValidationError(f"{field_name}: Value {value} exceeds maximum {max_val}")
    
    return value


def validate_dimension(
    value: Any,
    field_name: str,
    min_val: float = 0.1,
    max_val: float = 1000.0
) -> float:
    """
    Validate a dimension (length, width, height) in meters.
    
    Args:
        value: The value to validate.
        field_name: Name of the dimension.
        min_val: Minimum allowed value (default: 0.1m).
        max_val: Maximum allowed value (default: 1000m).
    
    Returns:
        Validated dimension as float.
    """
    return validate_positive(value, field_name, min_val, max_val)


def validate_load(
    value: Any,
    field_name: str,
    min_val: float = 0.0,
    max_val: float = 10000.0,
    allow_zero: bool = True
) -> float:
    """
    Validate a load value (kN, kN/m, kN/m²).
    
    Args:
        value: The value to validate.
        field_name: Name of the load type.
        min_val: Minimum allowed value.
        max_val: Maximum allowed value.
        allow_zero: Whether zero load is allowed.
    
    Returns:
        Validated load as float.
    """
    return validate_positive(value, field_name, min_val, max_val, allow_zero)


def validate_integer(
    value: Any,
    field_name: str,
    min_val: int = 1,
    max_val: int = 1000
) -> int:
    """
    Validate an integer value (e.g., number of stories).
    
    Args:
        value: The value to validate.
        field_name: Name of the field.
        min_val: Minimum allowed value.
        max_val: Maximum allowed value.
    
    Returns:
        Validated integer.
    """
    # First validate as positive number
    float_val = validate_positive(value, field_name, min_val, max_val)
    
    # Check if it's a whole number
    if float_val != int(float_val):
        raise ValidationError(f"{field_name}: Value must be a whole number (got {float_val})")
    
    return int(float_val)


def validate_material_grade(grade: str, material_type: str = "concrete") -> str:
    """
    Validate a material grade string.
    
    Args:
        grade: The grade string (e.g., "M25", "Fe415").
        material_type: Type of material ("concrete" or "steel").
    
    Returns:
        Validated grade string (uppercase).
    """
    if not grade or not isinstance(grade, str):
        raise ValidationError(f"Material grade cannot be empty")
    
    grade = grade.strip().upper()
    
    if material_type == "concrete":
        valid_grades = ["M15", "M20", "M25", "M30", "M35", "M40", "M45", "M50", "M55", "M60"]
        if grade not in valid_grades:
            raise ValidationError(f"Invalid concrete grade: {grade}. Valid: {', '.join(valid_grades)}")
    
    elif material_type == "steel":
        valid_grades = ["FE415", "FE500", "FE550"]
        if grade not in valid_grades:
            raise ValidationError(f"Invalid steel grade: {grade}. Valid: {', '.join(valid_grades)}")
    
    return grade


def validate_file_extension(filename: str, allowed_extensions: list) -> bool:
    """
    Validate that a file has an allowed extension.
    
    Args:
        filename: Name of the file.
        allowed_extensions: List of allowed extensions (e.g., ['.dxf', '.DXF']).
    
    Returns:
        True if valid.
    
    Raises:
        ValidationError: If extension is not allowed.
    """
    if not filename:
        raise ValidationError("Filename cannot be empty")
    
    import os
    _, ext = os.path.splitext(filename)
    
    if ext.lower() not in [e.lower() for e in allowed_extensions]:
        raise ValidationError(
            f"Invalid file type: {ext}. Allowed: {', '.join(allowed_extensions)}"
        )
    
    return True


def sanitize_project_name(name: str, max_length: int = 100) -> str:
    """
    Sanitize a project name to prevent injection attacks.
    
    Args:
        name: The project name.
        max_length: Maximum allowed length.
    
    Returns:
        Sanitized name.
    """
    if not name:
        return "Untitled Project"
    
    # Remove dangerous characters
    import re
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    
    # Truncate
    name = name[:max_length]
    
    # Strip whitespace
    name = name.strip()
    
    return name if name else "Untitled Project"


def validate_coordinates(x: Any, y: Any, field_name: str = "Coordinates") -> tuple:
    """
    Validate a pair of coordinates.
    
    Returns:
        Tuple of (x, y) as floats.
    """
    try:
        x_val = float(x)
        y_val = float(y)
    except (ValueError, TypeError):
        raise ValidationError(f"{field_name}: Invalid coordinate values")
    
    import math
    if math.isnan(x_val) or math.isnan(y_val):
        raise ValidationError(f"{field_name}: Coordinates cannot be NaN")
    
    if math.isinf(x_val) or math.isinf(y_val):
        raise ValidationError(f"{field_name}: Coordinates cannot be infinite")
    
    return (x_val, y_val)
