from __future__ import annotations

import json
import re
from typing import Any, Iterable

from .validation_types import ValidationResult

# Simple DTMI shape: dtmi:<path>;<version>
DTMI_PATTERN = re.compile(r"^dtmi:[A-Za-z0-9_:]+;[1-9][0-9]*$")

# Known top-level Interface keys for a light-weight check.
KNOWN_KEYS = {
    "@id",
    "@type",
    "@context",
    "displayName",
    "description",
    "comment",
    "contents",
    "extends",
    "schemas",
    "name",
    "schema",
    "unit",
    "writable",
    "enumValues",
}

REQUIRED_KEYS = {"@id", "@type", "@context"}


def preflight_validate(models: Iterable[Any]) -> ValidationResult:
    """
    Perform quick structural validation of DTDL-like JSON models.

    The function is intentionally forgiving and never raises on validation problems.
    """

    result = ValidationResult()
    parsed_models: list[dict[str, Any]] = []

    if models is None:
        result.add_issue(
            severity="error",
            message="No models provided for validation.",
            code="no_models",
        )
        return result

    if isinstance(models, (str, bytes)):
        models = [models]

    try:
        iterator = enumerate(models)
    except TypeError:
        result.add_issue(
            severity="error",
            message="Models input must be an iterable of dicts or JSON strings.",
            code="invalid_models_input",
        )
        return result

    for idx, model in iterator:
        if isinstance(model, str):
            try:
                model = json.loads(model)
            except json.JSONDecodeError as exc:
                result.add_issue(
                    severity="error",
                    message=f"Model at index {idx} is not valid JSON: {exc.msg}",
                    path=f"[{idx}]",
                )
                continue
        if not isinstance(model, dict):
            result.add_issue(
                severity="error",
                message=f"Model at index {idx} must be a dict.",
                path=f"[{idx}]",
            )
            continue
        parsed_models.append(model)

    id_to_index: dict[str, int] = {}

    for idx, model in enumerate(parsed_models):
        model_id = model.get("@id")
        path = f"[{idx}]"

        # Required keys
        for key in REQUIRED_KEYS:
            if key not in model:
                result.add_issue(
                    severity="error",
                    message=f"Missing required key '{key}'.",
                    model_id=model_id,
                    path=path,
                    code="missing_key",
                )

        # DTMI sanity
        if isinstance(model_id, str):
            if not DTMI_PATTERN.match(model_id):
                result.add_issue(
                    severity="error",
                    message="Invalid DTMI format (expected dtmi:<path>;<version>).",
                    model_id=model_id,
                    path=path,
                    code="invalid_dtmi",
                )
            # Duplicate detection
            if model_id in id_to_index:
                first_idx = id_to_index[model_id]
                result.add_issue(
                    severity="error",
                    message=f"Duplicate @id also seen at index {first_idx}.",
                    model_id=model_id,
                    path=path,
                    code="duplicate_id",
                )
            else:
                id_to_index[model_id] = idx
        elif model_id is not None:
            result.add_issue(
                severity="error",
                message="@id must be a string.",
                model_id=None,
                path=path,
                code="invalid_id_type",
            )

        # @type validation
        raw_type = model.get("@type")
        if raw_type is not None:
            type_values: list[str] = []
            if isinstance(raw_type, str):
                type_values = [raw_type]
            elif isinstance(raw_type, list):
                type_values = [t for t in raw_type if isinstance(t, str)]
                if len(type_values) != len(raw_type):
                    result.add_issue(
                        severity="error",
                        message="@type list entries must be strings.",
                        model_id=model_id,
                        path=path,
                        code="invalid_type_entry",
                    )
            else:
                result.add_issue(
                    severity="error",
                    message="@type must be a string or list of strings.",
                    model_id=model_id,
                    path=path,
                    code="invalid_type",
                )

            if type_values and "Interface" not in type_values:
                result.add_issue(
                    severity="warning",
                    message='Expected "@type" to include "Interface".',
                    model_id=model_id,
                    path=path,
                    code="missing_interface_type",
                )

        # contents must be a list when present
        if "contents" in model and not isinstance(model["contents"], list):
            result.add_issue(
                severity="error",
                message="'contents' must be a list when provided.",
                model_id=model_id,
                path=path,
                code="invalid_contents_type",
            )

        # Unknown/custom keys -> warnings
        for key in model.keys():
            if key not in KNOWN_KEYS:
                result.add_issue(
                    severity="warning",
                    message=f"Unknown key '{key}' detected.",
                    model_id=model_id,
                    path=path,
                    code="unknown_key",
                )

    return result
