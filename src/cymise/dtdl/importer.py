from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Iterable

from cymise.dtdl.dotnet_validator import validate_with_dotnet
from cymise.dtdl.preflight import preflight_validate
from cymise.dtdl.validation_types import ValidationIssue, ValidationResult
from cymise.graph.service import GraphService


@dataclass(slots=True)
class ImportCounts:
    files_scanned: int = 0
    json_docs_parsed: int = 0
    models_loaded: int = 0
    models_with_dtmi: int = 0
    model_documents_upserted: int = 0
    interface_nodes_upserted: int = 0
    relationship_edges_created: int = 0
    edges_skipped_missing_target: int = 0
    invalid_models: int = 0


@dataclass(slots=True)
class ImportResult:
    counts: ImportCounts = field(default_factory=ImportCounts)
    validation: ValidationResult = field(default_factory=ValidationResult)


def import_dtdl(input_path: str | Path, graph_service: GraphService) -> ImportResult:
    """
    Load DTDL JSON models from a file or folder, validate, persist, and materialize graph.
    """

    result = ImportResult()
    root = Path(input_path)
    files: list[Path] = []

    if root.is_dir():
        files = list(root.rglob("*.json"))
    elif root.is_file():
        files = [root]
    else:
        result.validation.add_issue(
            severity="error",
            message=f"Input path does not exist: {input_path}",
            code="input_not_found",
        )
        result.counts.invalid_models += 1
        return result

    result.counts.files_scanned = len(files)

    models: list[dict[str, Any]] = []
    model_sources: list[tuple[str, dict[str, Any]]] = []

    for file_path in files:
        try:
            raw_text = file_path.read_text(encoding="utf-8")
            payload = json.loads(raw_text)
        except FileNotFoundError:
            result.validation.add_issue(
                severity="error",
                message=f"Model file not found: {file_path}",
                code="file_not_found",
                path=str(file_path),
            )
            result.counts.invalid_models += 1
            continue
        except json.JSONDecodeError as exc:
            result.validation.add_issue(
                severity="error",
                message=f"Invalid JSON in {file_path}: {exc.msg}",
                code="invalid_json",
                path=str(file_path),
            )
            result.counts.invalid_models += 1
            continue

        result.counts.json_docs_parsed += 1

        entries: Iterable[Any]
        if isinstance(payload, list):
            entries = payload
        elif isinstance(payload, dict):
            entries = [payload]
        else:
            result.validation.add_issue(
                severity="error",
                message=f"Root JSON in {file_path} must be an object or array.",
                code="invalid_root",
                path=str(file_path),
            )
            result.counts.invalid_models += 1
            continue

        for item in entries:
            if isinstance(item, dict):
                models.append(item)
                model_sources.append((raw_text, item))
                result.counts.models_loaded += 1
            else:
                result.validation.add_issue(
                    severity="error",
                    message=f"Encountered non-object model in {file_path}.",
                    code="invalid_model_shape",
                    path=str(file_path),
                )
                result.counts.invalid_models += 1

    # Gather DTMI map
    dtmi_to_model: dict[str, dict[str, Any]] = {}
    for item in models:
        dtmi = item.get("@id")
        if isinstance(dtmi, str):
            dtmi_to_model[dtmi] = item
            result.counts.models_with_dtmi += 1
        else:
            result.validation.add_issue(
                severity="error",
                message="Model missing @id DTMI; skipping graph materialization.",
                code="missing_dtmi",
            )
            result.counts.invalid_models += 1

    if not models:
        return result

    # Pre-flight validation
    preflight_result = preflight_validate(models)
    result.validation.issues.extend(preflight_result.issues)

    # .NET validation (batch via temp file)
    with NamedTemporaryFile(mode="w+", suffix=".json", delete=True, encoding="utf-8") as tmp:
        json.dump(models, tmp)
        tmp.flush()
        dotnet_result = validate_with_dotnet(Path(tmp.name))
    result.validation.issues.extend(dotnet_result.issues)

    # Track invalid models based on validation results
    error_dtmis = {
        issue.model_id
        for issue in result.validation.issues
        if issue.severity == "error" and issue.model_id
    }
    result.counts.invalid_models += len(error_dtmis)

    # Upsert ModelDocuments for DTMI-bearing models
    for raw_text, model in model_sources:
        dtmi = model.get("@id")
        if not isinstance(dtmi, str):
            continue
        graph_service.repo.upsert_model_document(
            name=str(model.get("displayName") or dtmi),
            content=raw_text,
            dtmi=dtmi,
        )
        result.counts.model_documents_upserted += 1

    interface_dtmis = {
        dtmi for dtmi, model in dtmi_to_model.items() if _has_type(model, "Interface")
    }

    # Create/update interface nodes
    for dtmi in interface_dtmis:
        model = dtmi_to_model[dtmi]
        display_name = _first_string(model.get("displayName"))
        if graph_service.get_node(dtmi):
            graph_service.update_twin(dtmi, display_name=display_name)
        else:
            graph_service.create_twin(dtmi, display_name=display_name)
        result.counts.interface_nodes_upserted += 1

        node_issues = [issue for issue in result.validation.issues if issue.model_id == dtmi]
        graph_service.set_node_validation(dtmi, _issues_payload(node_issues))

    # Create relationship edges (only between imported dtmis)
    for dtmi in interface_dtmis:
        model = dtmi_to_model[dtmi]
        contents = model.get("contents") or []
        if not isinstance(contents, list):
            continue
        for item in contents:
            if not isinstance(item, dict):
                continue
            if not _has_type(item, "Relationship"):
                continue
            target = item.get("target")
            if not isinstance(target, str):
                continue
            if target not in interface_dtmis:
                result.counts.edges_skipped_missing_target += 1
                continue
            name = _first_string(item.get("name"))
            graph_service.create_relationship(dtmi, target, name=name)
            result.counts.relationship_edges_created += 1

    return result


def _has_type(model: dict[str, Any], expected: str) -> bool:
    raw_type = model.get("@type")
    if isinstance(raw_type, str):
        return raw_type == expected or raw_type.endswith("." + expected)
    if isinstance(raw_type, list):
        return any(
            isinstance(t, str) and (t == expected or t.endswith("." + expected))
            for t in raw_type
        )
    return False


def _first_string(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        for item in value:
            if isinstance(item, str):
                return item
    return None


def _issues_payload(issues: list[ValidationIssue]) -> dict[str, Any]:
    return {
        "issues": [
            {
                "severity": issue.severity,
                "message": issue.message,
                "model_id": issue.model_id,
                "path": issue.path,
                "code": issue.code,
            }
            for issue in issues
        ],
        "is_ok": not any(issue.severity == "error" for issue in issues),
    }
