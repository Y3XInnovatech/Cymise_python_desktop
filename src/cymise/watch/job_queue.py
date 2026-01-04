from __future__ import annotations

import queue
import time
from dataclasses import dataclass
from typing import Any, Optional


@dataclass(slots=True)
class ParseJob:
    file_id: int
    path: str
    reason: str
    queued_at: float
    payload: Optional[dict[str, Any]] = None


class JobQueue:
    """Simple in-memory FIFO for parse jobs."""

    def __init__(self):
        self._queue: queue.Queue[ParseJob] = queue.Queue()

    def enqueue(self, job: ParseJob) -> None:
        self._queue.put(job)

    def get(self, timeout: Optional[float] = None) -> ParseJob:
        return self._queue.get(timeout=timeout)

    def empty(self) -> bool:
        return self._queue.empty()
