from __future__ import annotations

import json
import shlex
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from cymise.graph.service import GraphService


@dataclass(slots=True)
class ExtractResult:
    ok: bool
    message: str
    extracted_object_id: Optional[int] = None
    dt_keys: list[str] = field(default_factory=list)


def find_dt_keys(data: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(data, dict):
        for k, v in data.items():
            if isinstance(k, str) and k.startswith("dt_"):
                keys.add(k)
            keys.update(find_dt_keys(v))
    elif isinstance(data, list):
        for item in data:
            keys.update(find_dt_keys(item))
    return keys


def extract_freecad(
    graph_service: GraphService, file_id: int, *, fail_silently: bool = True
) -> ExtractResult:
    file_obj = graph_service.repo.get_file_object_by_id(file_id)
    if not file_obj:
        msg = f"FileObject not found for id={file_id}"
        return ExtractResult(ok=False, message=msg)

    file_path = Path(file_obj.path)
    if not file_path.exists():
        msg = f"File does not exist: {file_path}"
        return ExtractResult(ok=False, message=msg)

    tool_info = {"name": "freecad", "mode": "fallback"}
    errors: list[str] = []
    tree: dict[str, Any] = {"name": file_path.name, "children": []}
    dt_keys: set[str] = set()

    cmd = _build_command()
    if cmd:
        try:
            completed = subprocess.run(
                cmd + [str(file_path)],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            tool_info["mode"] = "headless"
            if completed.returncode == 0 and completed.stdout:
                tree = json.loads(completed.stdout)
                dt_keys.update(find_dt_keys(tree))
            else:
                errors.append(completed.stderr or "FreeCAD command failed.")
        except Exception as exc:
            errors.append(f"FreeCAD invocation failed: {exc}")

    dt_keys.update(find_dt_keys(tree))
    dto = {
        "file_id": file_id,
        "path": str(file_path),
        "tree": tree,
        "dt_keys": sorted(dt_keys),
        "tool": tool_info,
    }
    if errors:
        dto["errors"] = errors

    try:
        extracted = graph_service.repo.add_extracted_object(
            file_object_id=file_id, kind="freecad_tree", data=dto
        )
    except Exception as exc:
        if fail_silently:
            return ExtractResult(ok=False, message=f"Failed to persist extraction: {exc}")
        raise

    return ExtractResult(
        ok=not errors,
        message="Extraction complete" if not errors else "Extraction completed with errors",
        extracted_object_id=extracted.id,
        dt_keys=sorted(dt_keys),
    )


def _build_command() -> Optional[list[str]]:
    env_cmd = _env_cmd()
    if env_cmd:
        return env_cmd
    for candidate in ("FreeCADCmd", "freecadcmd", "FreeCAD", "freecad"):
        found = shutil.which(candidate)
        if found:
            return [found]
    return None


def _env_cmd() -> Optional[list[str]]:
    value = _get_env("CYMISE_FREECAD_EXTRACT_CMD")
    if value:
        return shlex.split(value)
    return None


def _get_env(name: str) -> Optional[str]:
    try:
        import os

        return os.getenv(name)
    except Exception:
        return None
