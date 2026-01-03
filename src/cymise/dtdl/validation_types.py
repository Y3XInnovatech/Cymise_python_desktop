from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional

Severity = Literal["error", "warning"]


@dataclass(slots=True)
class ValidationIssue:
    """Single validation finding produced by pre-flight checks."""

    severity: Severity
    message: str
    model_id: Optional[str] = None
    path: Optional[str] = None
    code: Optional[str] = None


@dataclass(slots=True)
class ValidationResult:
    """Aggregate of validation findings."""

    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "warning"]

    @property
    def is_ok(self) -> bool:
        return not self.errors

    def add_issue(
        self,
        severity: Severity,
        message: str,
        model_id: Optional[str] = None,
        path: Optional[str] = None,
        code: Optional[str] = None,
    ) -> None:
        self.issues.append(
            ValidationIssue(
                severity=severity,
                message=message,
                model_id=model_id,
                path=path,
                code=code,
            )
        )
