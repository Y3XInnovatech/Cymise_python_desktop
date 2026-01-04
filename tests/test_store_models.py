from __future__ import annotations

import json

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from cymise.store.db import create_db, get_engine, get_session
from cymise.store.repo import StoreRepository


@pytest.fixture
def engine(tmp_path):
    db_path = tmp_path / "store.db"
    engine = get_engine(db_path)
    create_db(engine)
    return engine


@pytest.fixture
def repo(engine):
    with get_session(engine) as session:
        yield StoreRepository(session)


def test_schema_created(engine):
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    expected = {
        "twin_nodes",
        "relationship_edges",
        "file_objects",
        "extracted_objects",
        "model_documents",
        "stitch_candidates",
    }
    assert expected.issubset(table_names)


def test_twin_crud(repo):
    twin = repo.add_twin("dtmi:com:example:device;1", display_name="Device")
    fetched = repo.get_twin_by_dtmi("dtmi:com:example:device;1")
    assert fetched is not None
    assert fetched.id == twin.id

    repo.delete_twin(twin.id)
    assert repo.get_twin_by_dtmi("dtmi:com:example:device;1") is None


def test_twin_dtmi_unique(repo):
    repo.add_twin("dtmi:com:example:dup;1")
    with pytest.raises(IntegrityError):
        repo.add_twin("dtmi:com:example:dup;1")


def test_relationship_crud(repo):
    source = repo.add_twin("dtmi:com:example:source;1", display_name="Source")
    target = repo.add_twin("dtmi:com:example:target;1", display_name="Target")
    edge = repo.add_relationship(source.id, target.id, name="relatesTo")

    edges = repo.list_relationships()
    assert len(edges) == 1
    assert edges[0].id == edge.id
    assert edges[0].source_id == source.id
    assert edges[0].target_id == target.id


def test_file_and_extracted_objects(repo):
    twin = repo.add_twin("dtmi:com:example:filetwin;1")
    file_obj = repo.add_file_object(
        path="artifact.step",
        media_type="application/step",
        version="1.0",
        twin_id=twin.id,
    )
    extracted = repo.add_extracted_object(
        file_object_id=file_obj.id, kind="metadata", data={"k": "v"}
    )

    files = repo.list_file_objects()
    extracted_objects = repo.list_extracted_objects()

    assert len(files) == 1
    assert files[0].id == file_obj.id
    assert files[0].twin_id == twin.id

    assert len(extracted_objects) == 1
    assert extracted_objects[0].id == extracted.id
    assert extracted_objects[0].file_object_id == file_obj.id
    assert json.loads(json.dumps(extracted_objects[0].data)) == {"k": "v"}


def test_model_documents(repo):
    doc = repo.add_model_document(
        name="interface.json",
        content='{"@id":"dtmi:com:example:interface;1"}',
        dtmi="dtmi:com:example:interface;1",
    )
    docs = repo.list_model_documents()
    assert len(docs) == 1
    assert docs[0].id == doc.id
    assert docs[0].dtmi == "dtmi:com:example:interface;1"
