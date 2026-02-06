## AGENTS.md

### Build/Run Commands
- `poetry install` - Install dependencies
- `poetry run python app.py` - Run app
- `pytest` - Run all tests
- `pytest -k <test_name>` - Run single test

### Linting
- `poetry run mypy --show-error-codes src/` - Type checking
- `poetry run black --check src/` - Format check
- `poetry run flake8 src/` - Style linting

### Code Guidelines
- Use **snake_case** for variables/functions
- Use **CamelCase** for classes
- Always import from `src/` directory
- Use type hints with `typing_extensions`
- Handle errors with specific exceptions
- Keep functions < 20 lines
- Format code with Black (pep8, line-length=88)

### Rules
Include Cursor/Copilot rules from .cursor/rules/ or .cursorrules
Include Copilot instructions from .github/copilot-instructions.md