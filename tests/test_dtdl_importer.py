from __future__ import annotations

import json
from pathlib import Path

import pytest

from cymise.dtdl.importer import import_dtdl
from cymise.dtdl.validation_types import ValidationResult
from cymise.graph.service import GraphService
from cymise.store.db import create_db, get_engine, get_session
from cymise.store.repo import StoreRepository


@pytest.fixture
def service(tmp_path):
    engine = get_engine(tmp_path / "import.db")
    create_db(engine)
    session = get_session(engine)
    repo = StoreRepository(session)
    svc = GraphService(repo)
    try:
        yield svc
    finally:
        session.close()


@pytest.fixture(autouse=True)
def mock_dotnet(monkeypatch):
    def _fake_validate(models_path):
        return ValidationResult()

    monkeypatch.setattr("cymise.dtdl.importer.validate_with_dotnet", _fake_validate)


def _write_json(path: Path, payload) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_single_interface_import(service: GraphService, tmp_path):
    model = {
        "@id": "dtmi:com:example:device;1",
        "@type": "Interface",
        "displayName": "Device",
        "contents": [],
        "@context": "dtmi:dtdl:context;3",
    }
    file_path = _write_json(tmp_path / "model.json", model)

    result = import_dtdl(file_path, service)

    assert result.counts.interface_nodes_upserted == 1
    assert result.counts.model_documents_upserted == 1
    node = service.get_node("dtmi:com:example:device;1")
    assert node is not None
    docs = list(service.repo.list_model_documents())
    assert docs and docs[0].dtmi == "dtmi:com:example:device;1"


def test_relationship_created_when_target_present(service: GraphService, tmp_path):
    source = {
        "@id": "dtmi:com:example:source;1",
        "@type": "Interface",
        "@context": "dtmi:dtdl:context;3",
        "contents": [
            {
                "@type": "Relationship",
                "name": "relatesTo",
                "target": "dtmi:com:example:target;1",
            }
        ],
    }
    target = {
        "@id": "dtmi:com:example:target;1",
        "@type": "Interface",
        "@context": "dtmi:dtdl:context;3",
        "contents": [],
    }
    file_path = _write_json(tmp_path / "models.json", [source, target])

    result = import_dtdl(file_path, service)

    assert result.counts.relationship_edges_created == 1
    neighbors = service.get_outgoing_neighbors("dtmi:com:example:source;1")
    assert {n.dtmi for n in neighbors} == {"dtmi:com:example:target;1"}


def test_relationship_skipped_when_target_missing(service: GraphService, tmp_path):
    source = {
        "@id": "dtmi:com:example:orphan;1",
        "@type": "Interface",
        "@context": "dtmi:dtdl:context;3",
        "contents": [
            {
                "@type": "Relationship",
                "name": "relatesTo",
                "target": "dtmi:com:example:missing;1",
            }
        ],
    }
    file_path = _write_json(tmp_path / "orphan.json", source)

    result = import_dtdl(file_path, service)

    assert result.counts.relationship_edges_created == 0
    assert result.counts.edges_skipped_missing_target == 1


def test_invalid_model_recorded_and_document_stored(service: GraphService, tmp_path):
    # Missing @type triggers preflight error; still stored because DTMI exists.
    invalid_model = {
        "@id": "dtmi:com:example:invalid;1",
        "@context": "dtmi:dtdl:context;3",
        "contents": [],
    }
    file_path = _write_json(tmp_path / "invalid.json", invalid_model)

    result = import_dtdl(file_path, service)

    assert result.counts.model_documents_upserted == 1
    assert result.counts.interface_nodes_upserted == 0
    assert result.counts.invalid_models >= 1
    docs = list(service.repo.list_model_documents())
    assert docs and docs[0].dtmi == "dtmi:com:example:invalid;1"
