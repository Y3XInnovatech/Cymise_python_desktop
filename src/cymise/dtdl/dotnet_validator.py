from __future__ import annotations

import json
import os
import shlex
import subprocess
from pathlib import Path
from typing import Any

from .validation_types import Severity, ValidationIssue, ValidationResult

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_VALIDATOR_EXE_PATH = (
    _PROJECT_ROOT
    / "cymise_dtdl_validator"
    / "Cymise.DtdlValidator"
    / "bin"
    / "Debug"
    / "net8.0"
    / "Cymise.DtdlValidator.exe"
)

_DEFAULT_TIMEOUT = 60


def _build_command() -> list[str]:
    env_value = os.getenv("CYMISE_DTDL_VALIDATOR_CMD")
    if env_value:
        return shlex.split(env_value, posix=False)

    # Default: call the built executable directly
    try:
        exe_arg = str(_VALIDATOR_EXE_PATH.relative_to(_PROJECT_ROOT))
    except ValueError:
        exe_arg = str(_VALIDATOR_EXE_PATH)

    return [exe_arg]


def _map_severity(raw: Any) -> Severity:
    if isinstance(raw, str):
        lowered = raw.lower()
        if lowered in ("error", "warning"):
            return lowered  # type: ignore[return-value]
    return "error"


def _parse_issues(payload: Any) -> list[ValidationIssue]:
    if not isinstance(payload, dict):
        raise ValueError("Validator output must be a JSON object.")

    issues_data = payload.get("issues", [])
    if not isinstance(issues_data, list):
        raise ValueError("Validator output is missing an 'issues' list.")

    parsed: list[ValidationIssue] = []
    for issue in issues_data:
        if not isinstance(issue, dict):
            continue

        parsed.append(
            ValidationIssue(
                severity=_map_severity(issue.get("severity")),
                message=issue.get("message") or "Validator did not provide a message.",
                model_id=issue.get("modelId") or issue.get("model_id"),
                path=issue.get("path"),
                code=issue.get("code"),
            )
        )
    return parsed


def validate_with_dotnet(input_path: str | Path) -> ValidationResult:
    """
    Execute the .NET DTDL validator and return its findings as ValidationResult.

    The function is resilient: it never raises for validation failures and will
    return a ValidationResult with an error issue if the tool cannot be executed.
    """

    result = ValidationResult()
    command = _build_command()
    command.extend(["--input", str(Path(input_path))])

    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            cwd=_PROJECT_ROOT,
            timeout=_DEFAULT_TIMEOUT,
        )
    except FileNotFoundError:
        result.add_issue(
            severity="error",
            message="DTDL validator executable not found.",
            code="validator_not_found",
        )
        return result
    except subprocess.TimeoutExpired:
        result.add_issue(
            severity="error",
            message="DTDL validator timed out.",
            code="validator_timeout",
        )
        return result
    except Exception as exc:  # pragma: no cover - safety net
        result.add_issue(
            severity="error",
            message=f"Failed to start DTDL validator: {exc}",
            code="validator_start_failed",
        )
        return result

    if completed.returncode not in (0, 2):
        stderr = completed.stderr.strip()
        detail = f": {stderr}" if stderr else ""
        result.add_issue(
            severity="error",
            message=f".NET validator failed with exit code {completed.returncode}{detail}",
            code="validator_process_failed",
        )
        return result

    try:
        payload = json.loads(completed.stdout or "{}")
        result.issues.extend(_parse_issues(payload))
    except json.JSONDecodeError as exc:
        result.add_issue(
            severity="error",
            message=f"Failed to parse validator output: {exc.msg}",
            code="invalid_validator_output",
        )
    except ValueError as exc:
        result.add_issue(
            severity="error",
            message=f"Unexpected validator output: {exc}",
            code="invalid_validator_output",
        )

    return result
