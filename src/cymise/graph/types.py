from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass(slots=True)
class GraphNode:
    dtmi: str
    display_name: Optional[str]
    model_version: Optional[str]
    validation: Optional[dict[str, Any]]


@dataclass(slots=True)
class GraphEdge:
    id: int
    name: Optional[str]
    source_dtmi: str
    target_dtmi: str
    validation: Optional[dict[str, Any]]
