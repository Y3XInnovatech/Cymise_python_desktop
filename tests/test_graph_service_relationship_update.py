from __future__ import annotations

from cymise.graph.service import GraphService
from cymise.store.db import create_db, get_engine, get_session
from cymise.store.repo import StoreRepository


def test_update_relationship_name(tmp_path):
    engine = get_engine(tmp_path / "rel.db")
    create_db(engine)
    session = get_session(engine)
    repo = StoreRepository(session)
    service = GraphService(repo)

    service.create_twin("dtmi:com:example:a;1")
    service.create_twin("dtmi:com:example:b;1")
    edge = service.create_relationship(
        "dtmi:com:example:a;1", "dtmi:com:example:b;1", name="old"
    )

    updated = service.update_relationship_name(edge.id, "new")
    assert updated.name == "new"

    fetched = repo.get_relationship_by_id(edge.id)
    assert fetched.name == "new"
