from __future__ import annotations

import pytest

from cymise.graph.service import GraphService
from cymise.stitch.service import StitchService
from cymise.store.db import create_db, get_engine, get_session
from cymise.store.repo import StoreRepository


@pytest.fixture
def stitch_env(tmp_path):
    engine = get_engine(tmp_path / "stitch.db")
    create_db(engine)
    session = get_session(engine)
    repo = StoreRepository(session)
    graph_service = GraphService(repo)
    stitch_service = StitchService(graph_service)
    try:
        yield stitch_service, graph_service, repo
    finally:
        session.close()


def test_generate_candidates_dtmi_rule(stitch_env):
    stitch_service, _graph_service, repo = stitch_env
    file_obj = repo.add_file_object(path="doc.json", media_type="application/json", version="1.0")
    extracted = repo.add_extracted_object(
        file_object_id=file_obj.id,
        kind="metadata",
        data={"dt_keys": ["dtmi:com:acme:Foo;1"]},
    )

    candidates = stitch_service.generate_candidates_for_file(file_obj.id)
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.target_dtmi == "dtmi:com:acme:Foo;1"
    assert candidate.confidence == 0.9
    assert candidate.rationale == "dt_key looks like DTMI"
    assert candidate.extracted_object_id == extracted.id
    assert candidate.status == "candidate"


def test_generate_candidates_unresolved_rule(stitch_env):
    stitch_service, _graph_service, repo = stitch_env
    file_obj = repo.add_file_object(path="doc.json", media_type="application/json", version="1.0")
    extracted = repo.add_extracted_object(
        file_object_id=file_obj.id,
        kind="metadata",
        data={"dt_keys": ["dt_part_id"]},
    )

    candidates = stitch_service.generate_candidates_for_file(file_obj.id)
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.target_dtmi is None
    assert candidate.confidence == 0.3
    assert candidate.rationale == "unresolved dt_key"
    assert candidate.extracted_object_id == extracted.id


def test_persistence_and_list_filters(stitch_env):
    _stitch_service, graph_service, repo = stitch_env
    file_obj = repo.add_file_object(path="doc.json", media_type="application/json", version="1.0")
    extracted = repo.add_extracted_object(
        file_object_id=file_obj.id,
        kind="metadata",
        data={"dt_keys": ["dtmi:com:acme:Foo;1", "dt_part_id"]},
    )

    stitched = graph_service.stitch_file(file_obj.id)
    assert len(stitched) == 2
    ids = {c["id"] for c in stitched}

    listed_all = repo.list_stitch_candidates()
    assert {c.id for c in listed_all} == ids

    listed_for_file = repo.list_stitch_candidates(file_object_id=file_obj.id)
    assert len(listed_for_file) == 2

    listed_for_extracted = repo.list_stitch_candidates(extracted_object_id=extracted.id)
    assert len(listed_for_extracted) == 2

    listed_by_status = repo.list_stitch_candidates(status="candidate")
    assert len(listed_by_status) == 2


def test_update_stitch_candidate(stitch_env):
    stitch_service, _graph_service, repo = stitch_env
    file_obj = repo.add_file_object(path="doc.json", media_type="application/json", version="1.0")
    repo.add_extracted_object(
        file_object_id=file_obj.id,
        kind="metadata",
        data={"dt_keys": ["dtmi:com:acme:Foo;1"]},
    )

    stitched = stitch_service.stitch_file(file_obj.id)
    candidate_id = stitched[0]["id"]

    updated = repo.update_stitch_candidate(
        candidate_id,
        status="accepted",
        target_dtmi="dtmi:com:acme:Bar;2",
        confidence=0.95,
        rationale="manual review",
    )
    assert updated is not None
    assert updated.status == "accepted"
    assert updated.target_dtmi == "dtmi:com:acme:Bar;2"
    assert updated.confidence == 0.95
    assert updated.rationale == "manual review"
