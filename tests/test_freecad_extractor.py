from __future__ import annotations

import json
from types import SimpleNamespace

from cymise.extract.freecad_extractor import ExtractResult, extract_freecad
from cymise.graph.service import GraphService
from cymise.store.db import create_db, get_engine, get_session
from cymise.store.repo import StoreRepository


def _setup_service(tmp_path):
    engine = get_engine(tmp_path / "freecad.db")
    create_db(engine)
    session = get_session(engine)
    repo = StoreRepository(session)
    return GraphService(repo)


def test_extract_fallback_when_no_freecad(monkeypatch, tmp_path):
    service = _setup_service(tmp_path)
    file_path = tmp_path / "part.fcstd"
    file_path.write_text("content")
    fobj = service.add_file_object(str(file_path), media_type="application/freecad")

    monkeypatch.setattr("shutil.which", lambda _: None)
    result = extract_freecad(service, fobj["id"])

    assert result.ok is True
    assert result.extracted_object_id is not None
    extracted = next(iter(service.repo.list_extracted_objects()))
    assert extracted.data["tree"]["name"] == "part.fcstd"
    assert extracted.data["tool"]["mode"] == "fallback"


def test_extract_with_mocked_freecad(monkeypatch, tmp_path):
    service = _setup_service(tmp_path)
    file_path = tmp_path / "assembly.fcstd"
    file_path.write_text("content")
    fobj = service.add_file_object(str(file_path), media_type="application/freecad")

    monkeypatch.setattr("shutil.which", lambda _: "FreeCADCmd")

    payload = {"name": "root", "meta": {"dt_key": "value"}, "children": []}

    def fake_run(cmd, capture_output, text, timeout, check):
        return SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr="")

    monkeypatch.setattr("subprocess.run", fake_run)

    result = extract_freecad(service, fobj["id"])

    assert result.ok is True
    assert "dt_key" in result.dt_keys
    extracted = next(iter(service.repo.list_extracted_objects()))
    assert extracted.data["tool"]["mode"] == "headless"


def test_extract_missing_file(monkeypatch, tmp_path):
    service = _setup_service(tmp_path)
    missing_path = tmp_path / "missing.fcstd"
    fobj = service.add_file_object(str(missing_path), media_type="application/freecad")

    result = extract_freecad(service, fobj["id"])

    assert result.ok is False
    assert result.extracted_object_id is None
