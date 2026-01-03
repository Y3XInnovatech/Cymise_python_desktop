from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from cymise.dtdl.dotnet_validator import validate_with_dotnet
from cymise.dtdl.preflight import KNOWN_KEYS, preflight_validate
from cymise.dtdl.validation_types import ValidationResult
from cymise.graph.service import GraphService

DEFAULT_CONTEXT = "dtmi:dtdl:context;3"


@dataclass(slots=True)
class ExportCounts:
    models_exported: int = 0
    files_written: int = 0
    model_documents_used: int = 0
    invalid_models: int = 0


@dataclass(slots=True)
class ExportResult:
    counts: ExportCounts = field(default_factory=ExportCounts)
    validation: ValidationResult = field(default_factory=ValidationResult)


def export_dtdl_to_models(
    graph_service: GraphService, *, context: str | None = None
) -> list[dict[str, Any]]:
    nodes = graph_service.list_nodes()
    edges = graph_service.repo.list_relationships()
    node_map = {node.dtmi: node for node in nodes}
    edges_by_source: dict[str, list[dict[str, str | None]]] = {}

    for edge in edges:
        source = graph_service.repo.get_twin_by_id(edge.source_id)
        target = graph_service.repo.get_twin_by_id(edge.target_id)
        if not source or not target:
            continue
        edges_by_source.setdefault(source.dtmi, []).append(
            {"name": edge.name, "target": target.dtmi}
        )

    models: list[dict[str, Any]] = []
    for dtmi, node in node_map.items():
        base_model = _load_model_document(graph_service, dtmi)
        doc_used = base_model is not None
        if base_model is None:
            base_model = {"@id": dtmi, "@type": "Interface"}

        base_model["@context"] = context or base_model.get("@context") or DEFAULT_CONTEXT
        base_model["@id"] = dtmi
        base_model["@type"] = base_model.get("@type") or "Interface"

        if node.display_name:
            base_model["displayName"] = node.display_name

        contents = []
        if isinstance(base_model.get("contents"), list):
            contents = [
                _sanitize_content_item(item)
                for item in base_model["contents"]
                if _keep_non_relationship(item)
            ]
        rels = []
        for rel in edges_by_source.get(dtmi, []):
            rels.append(
                {
                    "@type": "Relationship",
                    "name": rel["name"] or "rel",
                    "target": rel["target"],
                }
            )
        base_model["contents"] = contents + rels

        cleaned = _sanitize_model(base_model)
        if cleaned is not None:
            models.append(cleaned)
            if doc_used:
                # Stored on the model for caller to
                # aggregate via counts (handled in export_dtdl)
                cleaned["_doc_used"] = True

    return models


def export_dtdl(
    graph_service: GraphService, output_path: str | Path, *, context: str | None = None
) -> ExportResult:
    result = ExportResult()
    models = export_dtdl_to_models(graph_service, context=context)

    # Capture document usage markers then strip them from payload
    for model in models:
        if model.pop("_doc_used", None):
            result.counts.model_documents_used += 1

    result.counts.models_exported = len(models)

    if not models:
        return result

    output_path = Path(output_path)
    output_path.write_text(json.dumps(models, indent=2), encoding="utf-8")
    result.counts.files_written = 1

    # Validation aggregation (non-raising)
    preflight = preflight_validate(models)
    result.validation.issues.extend(preflight.issues)

    with NamedTemporaryFile(mode="w+", suffix=".json", delete=True, encoding="utf-8") as tmp:
        json.dump(models, tmp)
        tmp.flush()
        dotnet = validate_with_dotnet(Path(tmp.name))
    result.validation.issues.extend(dotnet.issues)

    error_dtmis = {
        issue.model_id
        for issue in result.validation.issues
        if issue.severity == "error" and issue.model_id
    }
    result.counts.invalid_models = (
        len(error_dtmis)
        if error_dtmis
        else len([i for i in result.validation.issues if i.severity == "error"])
    )

    return result


def _load_model_document(graph_service: GraphService, dtmi: str) -> dict[str, Any] | None:
    doc = graph_service.get_model_document(dtmi)
    if not doc:
        return None
    try:
        payload = json.loads(doc.content)
    except json.JSONDecodeError:
        return None

    if isinstance(payload, dict):
        if payload.get("@id") == dtmi:
            return dict(payload)
        return None

    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict) and item.get("@id") == dtmi:
                return dict(item)
    return None


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


def _sanitize_content_item(item: Any) -> dict[str, Any]:
    if not isinstance(item, dict):
        return {}

    allowed_keys = KNOWN_KEYS | {"target"}
    cleaned = {k: v for k, v in item.items() if k in allowed_keys}

    # Only keep if there is a type and it is not a relationship (relationships are rebuilt)
    if _has_type(cleaned, "Relationship"):
        return {}
    return cleaned


def _sanitize_model(model: dict[str, Any]) -> dict[str, Any] | None:
    allowed_keys = KNOWN_KEYS | {"target"}
    cleaned = {k: v for k, v in model.items() if k in allowed_keys or k in ("@context", "@id")}
    contents = cleaned.get("contents")
    if contents and isinstance(contents, list):
        new_contents: list[dict[str, Any]] = []
        for item in contents:
            if not isinstance(item, dict):
                continue
            rel_clean = {k: v for k, v in item.items() if k in allowed_keys}
            if _has_type(rel_clean, "Relationship"):
                if "target" not in rel_clean or "name" not in rel_clean:
                    continue
                new_contents.append(
                    {
                        "@type": "Relationship",
                        "name": rel_clean.get("name") or "rel",
                        "target": rel_clean.get("target"),
                    }
                )
            else:
                new_contents.append(rel_clean)
        cleaned["contents"] = new_contents
    return cleaned if cleaned else None


def _keep_non_relationship(item: Any) -> bool:
    return isinstance(item, dict) and not _has_type(item, "Relationship")
