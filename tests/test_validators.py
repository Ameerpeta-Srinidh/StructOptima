"""
Edge case and stress tests for input validation.
"""
import pytest
import math
from src.validators import (
    ValidationError,
    validate_positive,
    validate_dimension,
    validate_load,
    validate_integer,
    validate_material_grade,
    validate_file_extension,
    sanitize_project_name,
    validate_coordinates
)


class TestValidatePositive:
    """Test positive number validation."""

    def test_valid_positive(self):
        """Test valid positive numbers."""
        assert validate_positive(5.0, "Test") == 5.0
        assert validate_positive(0.1, "Test") == 0.1
        assert validate_positive(1000, "Test") == 1000.0

    def test_string_number(self):
        """Test string that represents a number."""
        assert validate_positive("5.5", "Test") == 5.5
        assert validate_positive("  10  ", "Test") == 10.0

    def test_empty_value(self):
        """Test empty/None values."""
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_positive(None, "Test")
        
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_positive("", "Test")
        
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_positive("   ", "Test")

    def test_negative_value(self):
        """Test negative values are rejected."""
        with pytest.raises(ValidationError, match="cannot be negative"):
            validate_positive(-5.0, "Test")
        
        with pytest.raises(ValidationError, match="cannot be negative"):
            validate_positive("-10", "Test")

    def test_zero_value(self):
        """Test zero handling."""
        with pytest.raises(ValidationError, match="cannot be zero"):
            validate_positive(0, "Test", allow_zero=False)
        
        # Should pass when allow_zero=True
        assert validate_positive(0, "Test", allow_zero=True) == 0.0

    def test_garbage_text(self):
        """Test garbage text is rejected."""
        with pytest.raises(ValidationError, match="not a valid number"):
            validate_positive("abc", "Test")
        
        with pytest.raises(ValidationError, match="not a valid number"):
            validate_positive("12abc", "Test")
        
        with pytest.raises(ValidationError, match="not a valid number"):
            validate_positive("!@#$%", "Test")

    def test_nan_infinity(self):
        """Test NaN and infinity are rejected."""
        with pytest.raises(ValidationError, match="finite number"):
            validate_positive(float('nan'), "Test")
        
        with pytest.raises(ValidationError, match="finite number"):
            validate_positive(float('inf'), "Test")

    def test_bounds(self):
        """Test min/max bounds."""
        with pytest.raises(ValidationError, match="below minimum"):
            validate_positive(0.5, "Test", min_val=1.0)
        
        with pytest.raises(ValidationError, match="exceeds maximum"):
            validate_positive(100, "Test", max_val=50)

    def test_extremely_large_value(self):
        """Test extremely large values."""
        assert validate_positive(1e10, "Test", max_val=1e15) == 1e10
        
        with pytest.raises(ValidationError, match="exceeds maximum"):
            validate_positive(1e20, "Test", max_val=1e15)


class TestValidateDimension:
    """Test dimension validation."""

    def test_valid_dimensions(self):
        """Test valid building dimensions."""
        assert validate_dimension(10.0, "Width") == 10.0
        assert validate_dimension(0.5, "Height") == 0.5

    def test_too_small(self):
        """Test dimensions too small."""
        with pytest.raises(ValidationError, match="below minimum"):
            validate_dimension(0.01, "Width", min_val=0.1)

    def test_too_large(self):
        """Test unrealistic dimensions."""
        with pytest.raises(ValidationError, match="exceeds maximum"):
            validate_dimension(5000, "Width", max_val=1000)


class TestValidateLoad:
    """Test load validation."""

    def test_valid_loads(self):
        """Test valid load values."""
        assert validate_load(50.0, "Floor Load") == 50.0
        assert validate_load(0, "Wall Load", allow_zero=True) == 0.0

    def test_negative_load(self):
        """Test negative loads (uplift not supported in simple mode)."""
        with pytest.raises(ValidationError, match="cannot be negative"):
            validate_load(-10, "Floor Load")

    def test_excessive_load(self):
        """Test unrealistically high loads."""
        with pytest.raises(ValidationError, match="exceeds maximum"):
            validate_load(50000, "Floor Load", max_val=10000)


class TestValidateInteger:
    """Test integer validation."""

    def test_valid_integers(self):
        """Test valid integer values."""
        assert validate_integer(5, "Stories") == 5
        assert validate_integer(1, "Stories") == 1

    def test_decimal_rejected(self):
        """Test decimal numbers are rejected."""
        with pytest.raises(ValidationError, match="whole number"):
            validate_integer(2.5, "Stories")

    def test_zero_stories(self):
        """Test zero is rejected for story count."""
        with pytest.raises(ValidationError, match="cannot be zero"):
            validate_integer(0, "Stories", min_val=1)


class TestValidateMaterialGrade:
    """Test material grade validation."""

    def test_valid_concrete_grades(self):
        """Test valid concrete grades."""
        assert validate_material_grade("M25", "concrete") == "M25"
        assert validate_material_grade("m30", "concrete") == "M30"
        assert validate_material_grade("  M20  ", "concrete") == "M20"

    def test_valid_steel_grades(self):
        """Test valid steel grades."""
        assert validate_material_grade("Fe415", "steel") == "FE415"
        assert validate_material_grade("fe500", "steel") == "FE500"

    def test_invalid_grade(self):
        """Test invalid grades."""
        with pytest.raises(ValidationError, match="Invalid concrete grade"):
            validate_material_grade("M99", "concrete")
        
        with pytest.raises(ValidationError, match="Invalid steel grade"):
            validate_material_grade("Fe999", "steel")

    def test_empty_grade(self):
        """Test empty grade."""
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_material_grade("", "concrete")


class TestValidateFileExtension:
    """Test file extension validation."""

    def test_valid_extensions(self):
        """Test valid file extensions."""
        assert validate_file_extension("plan.dxf", [".dxf"]) is True
        assert validate_file_extension("model.IFC", [".ifc"]) is True

    def test_invalid_extension(self):
        """Test invalid extensions."""
        with pytest.raises(ValidationError, match="Invalid file type"):
            validate_file_extension("plan.pdf", [".dxf"])

    def test_empty_filename(self):
        """Test empty filename."""
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_file_extension("", [".dxf"])


class TestSanitizeProjectName:
    """Test project name sanitization."""

    def test_clean_name(self):
        """Test clean names pass through."""
        assert sanitize_project_name("My Project") == "My Project"

    def test_dangerous_characters(self):
        """Test dangerous characters are removed."""
        assert sanitize_project_name("Project<script>") == "Projectscript"
        assert sanitize_project_name("C:\\path\\file") == "Cpathfile"

    def test_empty_name(self):
        """Test empty name gets default."""
        assert sanitize_project_name("") == "Untitled Project"
        assert sanitize_project_name("   ") == "Untitled Project"

    def test_length_limit(self):
        """Test length is limited."""
        long_name = "A" * 200
        result = sanitize_project_name(long_name, max_length=100)
        assert len(result) == 100


class TestValidateCoordinates:
    """Test coordinate validation."""

    def test_valid_coordinates(self):
        """Test valid coordinates."""
        assert validate_coordinates(5.0, 10.0) == (5.0, 10.0)
        assert validate_coordinates("5", "10") == (5.0, 10.0)

    def test_nan_coordinates(self):
        """Test NaN coordinates."""
        with pytest.raises(ValidationError, match="cannot be NaN"):
            validate_coordinates(float('nan'), 5.0)

    def test_invalid_coordinates(self):
        """Test invalid coordinate values."""
        with pytest.raises(ValidationError, match="Invalid coordinate"):
            validate_coordinates("abc", 5.0)
