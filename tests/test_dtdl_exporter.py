from __future__ import annotations

import json
from pathlib import Path

import pytest

from cymise.dtdl.exporter import export_dtdl
from cymise.dtdl.validation_types import ValidationResult
from cymise.graph.service import GraphService
from cymise.store.db import create_db, get_engine, get_session
from cymise.store.repo import StoreRepository


@pytest.fixture
def service(tmp_path):
    engine = get_engine(tmp_path / "export.db")
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

    monkeypatch.setattr("cymise.dtdl.exporter.validate_with_dotnet", _fake_validate)


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_graph_only_export_writes_relationships(service: GraphService, tmp_path):
    service.create_twin("dtmi:com:example:src;1", display_name="Source")
    service.create_twin("dtmi:com:example:dst;1", display_name="Target")
    service.create_relationship(
        "dtmi:com:example:src;1", "dtmi:com:example:dst;1", name="relatesTo"
    )

    out_path = tmp_path / "out.json"
    result = export_dtdl(service, out_path)

    assert result.counts.models_exported == 2
    assert result.counts.files_written == 1
    models = _read_json(out_path)
    src = next(m for m in models if m["@id"] == "dtmi:com:example:src;1")
    rels = [c for c in src.get("contents", []) if c.get("@type") == "Relationship"]
    assert rels and rels[0]["target"] == "dtmi:com:example:dst;1"
    target = next(m for m in models if m["@id"] == "dtmi:com:example:dst;1")
    assert target.get("contents") == []


def test_model_document_reused_and_unknown_keys_removed(service: GraphService, tmp_path):
    service.create_twin("dtmi:com:example:iface;1")
    service.create_twin("dtmi:com:example:other;1")
    service.create_relationship(
        "dtmi:com:example:iface;1", "dtmi:com:example:other;1", name="relatesTo"
    )

    doc_payload = {
        "@id": "dtmi:com:example:iface;1",
        "@type": "Interface",
        "@context": "dtmi:dtdl:context;3",
        "description": "Existing description",
        "customKey": "should-be-removed",
        "contents": [],
    }
    service.repo.upsert_model_document(
        name="iface.json",
        content=json.dumps(doc_payload),
        dtmi="dtmi:com:example:iface;1",
    )

    out_path = tmp_path / "reuse.json"
    result = export_dtdl(service, out_path)

    models = _read_json(out_path)
    iface = next(m for m in models if m["@id"] == "dtmi:com:example:iface;1")
    assert iface.get("description") == "Existing description"
    assert "customKey" not in iface
    rels = [c for c in iface.get("contents", []) if c.get("@type") == "Relationship"]
    assert rels and rels[0]["target"] == "dtmi:com:example:other;1"
    assert result.counts.model_documents_used == 1


def test_validation_aggregated_without_raising(monkeypatch, service: GraphService, tmp_path):
    service.create_twin("dtmi:com:example:invalid;1")

    def fake_preflight(models):
        vr = ValidationResult()
        vr.add_issue(
            severity="error",
            message="missing something",
            model_id="dtmi:com:example:invalid;1",
            code="missing_key",
        )
        return vr

    monkeypatch.setattr("cymise.dtdl.exporter.preflight_validate", fake_preflight)

    out_path = tmp_path / "validation.json"
    result = export_dtdl(service, out_path)

    assert result.validation.errors
    assert result.counts.invalid_models == 1
    assert out_path.exists()
