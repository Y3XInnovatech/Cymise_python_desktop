# Dev Setup (Windows, PowerShell)

1. Create a virtual environment (replace `3.11` if needed):  
   `py -3.11 -m venv .venv`
2. Activate it:  
   `.venv\Scripts\Activate.ps1`
3. Editable install with dev tools:  
   `pip install -e .[dev]`

## Dev commands (run with venv active)
- Lint: `./scripts/lint.ps1`
- Format (auto-fix): `./scripts/format.ps1`
- Tests: `./scripts/test.ps1`

Notes:
- Tools are configured via `pyproject.toml` (ruff, black, pytest).
- If PowerShell execution policy blocks scripts, you can run the module forms instead, e.g. `python -m ruff check src tests`.
