from __future__ import annotations

import time

from cymise.graph.service import GraphService
from cymise.store.db import create_db, get_engine, get_session
from cymise.store.repo import StoreRepository
from cymise.watch.file_watcher import FileWatcher, WatcherConfig


def _setup_service(tmp_path):
    engine = get_engine(tmp_path / "watch.db")
    create_db(engine)
    session = get_session(engine)
    repo = StoreRepository(session)
    return GraphService(repo)


def test_watcher_detects_modifications(tmp_path):
    service = _setup_service(tmp_path)
    file_path = tmp_path / "artifact.txt"
    file_path.write_text("one")
    f = service.add_file_object(str(file_path))

    config = WatcherConfig(debounce_ms=100, scan_interval_ms=50)
    watcher = FileWatcher(service, config=config)
    watcher.start()
    try:
        time.sleep(0.2)
        file_path.write_text("two")
        time.sleep(0.3)
    finally:
        watcher.stop()

    events = []
    while not watcher.events.empty():
        events.append(watcher.events.get_nowait())

    assert any(ev.change in ("created", "modified") for ev in events)
    jobs = []
    while not watcher.jobs.empty():
        jobs.append(watcher.jobs.get())
    assert any(job.reason in ("created", "modified") for job in jobs)


def test_watcher_detects_deletion(tmp_path):
    service = _setup_service(tmp_path)
    file_path = tmp_path / "gone.txt"
    file_path.write_text("content")
    service.add_file_object(str(file_path))

    config = WatcherConfig(debounce_ms=50, scan_interval_ms=30)
    watcher = FileWatcher(service, config=config)
    watcher.start()
    try:
        time.sleep(0.1)
        file_path.unlink()
        time.sleep(0.2)
    finally:
        watcher.stop()

    events = []
    while not watcher.events.empty():
        events.append(watcher.events.get_nowait())

    assert any(ev.change == "deleted" for ev in events)
