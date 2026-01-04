from __future__ import annotations

import logging
import os
import platform
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ToolLaunchResult:
    ok: bool
    message: str
    command: Optional[list[str]] = None


def open_with_default_app(path: str | Path) -> ToolLaunchResult:
    file_path = Path(path)
    if not file_path.exists():
        msg = f"File does not exist: {file_path}"
        logger.error(msg)
        return ToolLaunchResult(ok=False, message=msg)

    system = platform.system()
    try:
        if system == "Windows":
            os.startfile(str(file_path))  # type: ignore[attr-defined]
            cmd = ["start", str(file_path)]
        elif system == "Darwin":
            subprocess.run(["open", str(file_path)], check=False)
            cmd = ["open", str(file_path)]
        else:
            subprocess.run(["xdg-open", str(file_path)], check=False)
            cmd = ["xdg-open", str(file_path)]
        return ToolLaunchResult(ok=True, message="Launched with default app.", command=cmd)
    except Exception as exc:  # pragma: no cover - defensive
        msg = f"Failed to launch default app: {exc}"
        logger.error(msg)
        return ToolLaunchResult(ok=False, message=msg)


def launch_tool(
    tool: str,
    file_path: str | Path,
    *,
    configured_path: Optional[str] = None,
) -> ToolLaunchResult:
    file_path = Path(file_path)
    if not file_path.exists():
        msg = f"File does not exist: {file_path}"
        logger.error(msg)
        return ToolLaunchResult(ok=False, message=msg)

    if tool == "default":
        return open_with_default_app(file_path)

    env_cmd = _env_command(tool)
    if env_cmd:
        return _spawn(env_cmd + [str(file_path)], f"{tool} via env")

    if configured_path:
        return _spawn([configured_path, str(file_path)], f"{tool} via configured path")

    candidates = _candidate_executables(tool)
    for candidate in candidates:
        found = shutil.which(candidate)
        if found:
            return _spawn([found, str(file_path)], f"{tool} via {candidate}")

    # Fallback to default app
    return open_with_default_app(file_path)


def _env_command(tool: str) -> Optional[list[str]]:
    var_map = {
        "freecad": "CYMISE_FREECAD_CMD",
        "kicad": "CYMISE_KICAD_CMD",
    }
    env_var = var_map.get(tool.lower())
    if not env_var:
        return None
    value = os.getenv(env_var)
    if not value:
        return None
    return shlex.split(value)


def _candidate_executables(tool: str) -> list[str]:
    if tool.lower() == "freecad":
        return ["FreeCAD", "freecad"]
    if tool.lower() == "kicad":
        return ["kicad", "kicad.exe", "pcbnew", "eeschema"]
    return []


def _spawn(cmd: list[str], context: str) -> ToolLaunchResult:
    try:
        subprocess.Popen(cmd)  # noqa: S603,S607
        return ToolLaunchResult(ok=True, message=f"Launched {context}.", command=cmd)
    except Exception as exc:  # pragma: no cover - defensive
        msg = f"Failed to launch {context}: {exc}"
        logger.error(msg)
        return ToolLaunchResult(ok=False, message=msg, command=cmd)
