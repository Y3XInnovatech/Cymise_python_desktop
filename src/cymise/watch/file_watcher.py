from __future__ import annotations

import hashlib
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional

from cymise.graph.service import GraphService

from .job_queue import JobQueue, ParseJob

ChangeKind = Literal["created", "modified", "deleted"]


@dataclass(slots=True)
class FileChangeEvent:
    file_id: int
    path: str
    change: ChangeKind
    at: float


@dataclass(slots=True)
class WatcherConfig:
    debounce_ms: int = 500
    scan_interval_ms: int = 1000
    hash_algo: str = "sha256"


class FileWatcher:
    def __init__(self, graph_service: GraphService, config: Optional[WatcherConfig] = None):
        self.graph_service = graph_service
        self.config = config or WatcherConfig()
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self.events: "queue.Queue[FileChangeEvent]"  # type: ignore[name-defined]
        self.events = __import__("queue").Queue()
        self.jobs = JobQueue()

        self._state: dict[int, dict] = {}
        self._lock = threading.Lock()

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.is_running:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    def _run(self) -> None:
        debounce = self.config.debounce_ms / 1000.0
        interval = max(self.config.scan_interval_ms / 1000.0, 0.05)
        while not self._stop_event.is_set():
            now = time.monotonic()
            files = self.graph_service.list_file_objects()
            seen_ids = set()
            for f in files:
                file_id = f["id"]
                seen_ids.add(file_id)
                path = Path(f["path"])
                exists = path.exists()
                last = self._state.get(file_id)
                if not exists:
                    self._mark_change(file_id, str(path), "deleted", now)
                    continue
                file_hash = self._hash_file(path)
                if last is None:
                    self._mark_change(file_id, str(path), "created", now, file_hash)
                elif last.get("hash") != file_hash:
                    self._mark_change(file_id, str(path), "modified", now, file_hash)
                else:
                    # no change
                    pass

            # detect deleted for previously seen files not in current list
            for file_id, state in list(self._state.items()):
                if file_id not in seen_ids and state.get("exists", False):
                    self._mark_change(file_id, state.get("path", ""), "deleted", now)

            self._flush_ready(now, debounce)

            self._stop_event.wait(interval)

    def _mark_change(
        self,
        file_id: int,
        path: str,
        change: ChangeKind,
        now: float,
        file_hash: Optional[str] = None,
    ) -> None:
        with self._lock:
            entry = self._state.get(file_id, {})
            pending_change = entry.get("pending_change")
            pending_at = entry.get("pending_at")
            if pending_change == change and pending_at is not None:
                # same change already pending; keep original timestamp for debounce
                ts = pending_at
            else:
                ts = now
            entry.update(
                {
                    "path": path,
                    "pending_change": change,
                    "pending_at": ts,
                    "hash": file_hash if file_hash is not None else entry.get("hash"),
                    "exists": change != "deleted",
                }
            )
            self._state[file_id] = entry

    def _flush_ready(self, now: float, debounce: float) -> None:
        ready: list[tuple[int, dict]] = []
        with self._lock:
            for file_id, entry in list(self._state.items()):
                pending_at = entry.get("pending_at")
                pending_change = entry.get("pending_change")
                if pending_at is None or pending_change is None:
                    continue
                if now - pending_at >= debounce:
                    ready.append((file_id, entry))
                    entry["pending_change"] = None
                    entry["pending_at"] = None
                    entry["last_change"] = pending_change

        for file_id, entry in ready:
            path = entry.get("path", "")
            change = entry.get("last_change") or "modified"
            event = FileChangeEvent(file_id=file_id, path=path, change=change, at=now)
            self.events.put(event)
            if change in ("created", "modified", "deleted"):
                job = ParseJob(
                    file_id=file_id, path=path, reason=change, queued_at=now, payload={"hash": entry.get("hash")}
                )
                self.jobs.enqueue(job)
            entry["last_change"] = change

    def _hash_file(self, path: Path) -> str:
        h = hashlib.new(self.config.hash_algo)
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()


def start_watcher(graph_service: GraphService, config: Optional[WatcherConfig] = None) -> FileWatcher:
    watcher = FileWatcher(graph_service, config=config)
    watcher.start()
    return watcher
