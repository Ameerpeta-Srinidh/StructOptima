# Contributing to StructOptima

Thank you for your interest in contributing to StructOptima! This document provides guidelines and instructions for contributing.

## How to Contribute

### Reporting Bugs

1. Check existing [Issues](https://github.com/SrinidhAmeerpta/StructOptima/issues) to avoid duplicates
2. Create a new issue with:
   - Clear title describing the bug
   - Steps to reproduce
   - Expected vs actual behavior
   - Python version and OS

### Suggesting Features

Open an issue with the `enhancement` label. Include:
- Use case description
- Relevant IS code references (if applicable)
- Example inputs/outputs

### Code Contributions

1. **Fork** the repository
2. **Create a branch**: `git checkout -b feature/your-feature-name`
3. **Make changes** following the coding standards below
4. **Add tests** for new functionality
5. **Run tests**: `python -m pytest tests/ -v`
6. **Commit**: `git commit -m "Add: description of change"`
7. **Push**: `git push origin feature/your-feature-name`
8. **Open a Pull Request**

## Coding Standards

### Python Style

- Follow PEP 8
- Use type hints for function parameters and return values
- Use Pydantic models for data structures
- Add docstrings to all public functions and classes

### IS Code References

When implementing structural calculations, always include:
- The IS code clause reference in comments (e.g., `# IS 456 Cl. 39.3`)
- The formula being implemented
- Units in variable names or comments

Example:
```python
def calculate_axial_capacity(fck: float, fy: float, ag_mm2: float, ast_mm2: float) -> float:
    """
    Axial capacity per IS 456:2000 Cl. 39.3
    Pu = 0.4 fck Ac + 0.67 fy Asc
    """
    ac = ag_mm2 - ast_mm2  # Net concrete area (mm²)
    pu = 0.4 * fck * ac + 0.67 * fy * ast_mm2  # Newtons
    return pu / 1000  # kN
```

### Testing

- Place tests in the `tests/` directory
- Name test files `test_<module>.py`
- Name test functions `test_<description>`
- Use pytest fixtures from `conftest.py`
- Test edge cases and boundary conditions

### Commit Messages

Use conventional commit prefixes:
- `Add:` — New feature
- `Fix:` — Bug fix
- `Refactor:` — Code restructuring
- `Docs:` — Documentation changes
- `Test:` — Test additions or fixes

## Development Setup

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/StructOptima.git
cd StructOptima

# Install dependencies
pip install -r requirements.txt

# Run tests to verify setup
python -m pytest tests/ -v
```

## Questions?

Open an issue or contact the maintainer.

---

Thank you for helping improve StructOptima! 🏗️
