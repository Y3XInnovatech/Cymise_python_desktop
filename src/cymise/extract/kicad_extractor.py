from __future__ import annotations

import json
import re
import shlex
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from cymise.extract.freecad_extractor import find_dt_keys
from cymise.graph.service import GraphService


@dataclass(slots=True)
class ExtractResult:
    ok: bool
    message: str
    extracted_object_id: Optional[int] = None
    dt_keys: list[str] = field(default_factory=list)


def extract_kicad(
    graph_service: GraphService,
    file_id: int,
    *,
    fail_silently: bool = True,
) -> ExtractResult:
    file_obj = graph_service.repo.get_file_object_by_id(file_id)
    if not file_obj:
        return ExtractResult(ok=False, message=f"FileObject not found for id={file_id}")

    file_path = Path(file_obj.path)
    if not file_path.exists():
        return ExtractResult(ok=False, message=f"File does not exist: {file_path}")

    file_type = _detect_type(file_path)
    tool_info = {"name": "kicad", "mode": "native"}
    errors: list[str] = []
    data = {
        "file_id": file_id,
        "path": str(file_path),
        "file_type": file_type,
        "components": [],
        "nets": {},
        "dt_keys": [],
        "tool": tool_info,
    }

    # Try external command first if configured
    ext_cmd = _env_command()
    if ext_cmd:
        try:
            completed = subprocess.run(
                ext_cmd + [str(file_path)],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            if completed.returncode == 0 and completed.stdout:
                payload = json.loads(completed.stdout)
                if isinstance(payload, dict):
                    data.update(payload)
                    tool_info["mode"] = "external"
            else:
                errors.append(completed.stderr or "External KiCad extractor failed.")
        except Exception as exc:
            errors.append(f"External KiCad extractor failed: {exc}")

    if tool_info["mode"] == "native":
        try:
            parsed = _parse_kicad_file(file_path)
            data["components"] = parsed["components"]
            data["nets"] = parsed["nets"]
            # Merge dt_keys
            data["dt_keys"] = sorted(set(parsed["dt_keys"]))
        except Exception as exc:
            msg = f"Native parse failed: {exc}"
            if fail_silently:
                errors.append(msg)
            else:
                raise

    # Aggregate dt_keys regardless of source
    dt_keys = set(data.get("dt_keys") or [])
    dt_keys.update(find_dt_keys(data))
    data["dt_keys"] = sorted(dt_keys)
    if errors:
        data["errors"] = errors

    try:
        extracted = graph_service.repo.add_extracted_object(
            file_object_id=file_id, kind="kicad_ecad", data=data
        )
    except Exception as exc:
        if fail_silently:
            return ExtractResult(ok=False, message=f"Failed to persist extraction: {exc}")
        raise

    ok_flag = not errors
    return ExtractResult(
        ok=ok_flag,
        message="Extraction complete" if ok_flag else "Extraction completed with errors",
        extracted_object_id=extracted.id,
        dt_keys=sorted(dt_keys),
    )


def _detect_type(path: Path) -> str:
    lower = path.name.lower()
    if lower.endswith(".kicad_pcb"):
        return "pcb"
    if lower.endswith(".kicad_sch") or lower.endswith(".sch"):
        return "schematic"
    return "unknown"


def _env_command() -> Optional[list[str]]:
    value = _get_env("CYMISE_KICAD_EXTRACT_CMD")
    if not value:
        return None
    return shlex.split(value)


def _get_env(name: str) -> Optional[str]:
    try:
        import os

        return os.getenv(name)
    except Exception:
        return None


def _parse_kicad_file(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="ignore")
    components = _parse_components(text)
    nets = _parse_nets(text)
    dt_keys = set()
    for comp in components:
        dt_keys.update(find_dt_keys(comp))
    dt_keys.update(find_dt_keys(nets))
    # Scan raw text for dt_ keys to catch schematic properties
    for match in re.finditer(r"dt_[A-Za-z0-9_\-]+", text):
        dt_keys.add(match.group(0))
    return {"components": components, "nets": nets, "dt_keys": sorted(dt_keys)}


def _parse_components(text: str) -> list[dict]:
    components: list[dict] = []
    # Best-effort: look for "(comp (ref R1) ... (value 10k) ... (footprint ...))"
    for block in re.findall(r"\(comp\s+(.*?)\)", text, re.DOTALL):
        ref_match = re.search(r"\(ref\s+([^)]+)\)", block)
        value_match = re.search(r"\(value\s+([^)]+)\)", block)
        footprint_match = re.search(r"\(footprint\s+([^)]+)\)", block)
        comp_dict = {
            "ref": ref_match.group(1) if ref_match else "",
            "value": value_match.group(1) if value_match else "",
            "footprint": footprint_match.group(1) if footprint_match else "",
        }
        comp_dict["dt_keys"] = sorted(find_dt_keys(block) | find_dt_keys(comp_dict))
        components.append(comp_dict)

    # Fallback simple: search for (module ... (fp_text reference R1 ...)
    if not components:
        for block in re.findall(r"\(module\s+([^\s)]+).*?\)", text, re.DOTALL):
            ref_match = re.search(r"reference\s+([A-Za-z0-9]+)", block)
            val_match = re.search(r"value\s+([A-Za-z0-9\-\+\.]+)", block)
            comp_dict = {
                "ref": ref_match.group(1) if ref_match else "",
                "value": val_match.group(1) if val_match else "",
                "footprint": "",
            }
            comp_dict["dt_keys"] = sorted(find_dt_keys(block) | find_dt_keys(comp_dict))
            components.append(comp_dict)
    return components


def _parse_nets(text: str) -> dict:
    nets: dict[str, dict] = {}
    # KiCad net definition: (net <id> "<name>")
    for match in re.finditer(r"\(net\s+\d+\s+\"([^\"]+)\"\)", text):
        name = match.group(1)
        nets.setdefault(name, {"connections": 0})
    # Simple connection counting: look for (net <id> ...) references
    for match in re.finditer(r"\(net\s+(\d+)\s+\"([^\"]+)\"\)", text):
        name = match.group(2)
        nets[name]["connections"] += 1
    return nets
