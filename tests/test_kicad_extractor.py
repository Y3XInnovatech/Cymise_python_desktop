from __future__ import annotations

import json
from types import SimpleNamespace

from cymise.extract.kicad_extractor import extract_kicad
from cymise.graph.service import GraphService
from cymise.store.db import create_db, get_engine, get_session
from cymise.store.repo import StoreRepository


def _setup_service(tmp_path):
    engine = get_engine(tmp_path / "kicad.db")
    create_db(engine)
    session = get_session(engine)
    repo = StoreRepository(session)
    return GraphService(repo)


def test_extract_kicad_schematic_native(tmp_path):
    service = _setup_service(tmp_path)
    # Minimal schematic-like content with component and dt_ key
    content = '(comp (ref R1) (value 10k) (property "dt_key" "abc")) (net 1 "N$1")'
    file_path = tmp_path / "design.kicad_sch"
    file_path.write_text(content)
    fobj = service.add_file_object(str(file_path), media_type="application/kicad")

    result = extract_kicad(service, fobj["id"])

    assert result.ok
    extracted = next(iter(service.repo.list_extracted_objects()))
    assert extracted.data["file_type"] == "schematic"
    assert extracted.data["components"]
    assert "dt_key" in extracted.data["dt_keys"]
    assert extracted.data["nets"]


def test_extract_kicad_external(monkeypatch, tmp_path):
    service = _setup_service(tmp_path)
    file_path = tmp_path / "board.kicad_pcb"
    file_path.write_text("dummy")
    fobj = service.add_file_object(str(file_path), media_type="application/kicad")

    payload = {
        "components": [{"ref": "U1", "value": "MCU"}],
        "nets": {"GND": {"connections": 5}},
        "dt_keys": ["dt_board"],
    }

    monkeypatch.setenv("CYMISE_KICAD_EXTRACT_CMD", "kicad-extract")

    def fake_run(cmd, capture_output, text, timeout, check):
        return SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr="")

    monkeypatch.setattr("subprocess.run", fake_run)

    result = extract_kicad(service, fobj["id"])
    assert result.ok
    extracted = next(iter(service.repo.list_extracted_objects()))
    assert extracted.data["tool"]["mode"] == "external"
    assert "dt_board" in extracted.data["dt_keys"]


def test_extract_kicad_missing_file(tmp_path):
    service = _setup_service(tmp_path)
    file_path = tmp_path / "missing.kicad_pcb"
    fobj = service.add_file_object(str(file_path), media_type="application/kicad")

    result = extract_kicad(service, fobj["id"])

    assert not result.ok
    assert result.extracted_object_id is None
