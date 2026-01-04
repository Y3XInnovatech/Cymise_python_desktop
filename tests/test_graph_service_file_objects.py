from __future__ import annotations

import pytest

from cymise.graph.service import GraphService
from cymise.store.db import create_db, get_engine, get_session
from cymise.store.repo import StoreRepository


def test_file_object_attach_detach(tmp_path):
    engine = get_engine(tmp_path / "files.db")
    create_db(engine)
    session = get_session(engine)
    repo = StoreRepository(session)
    service = GraphService(repo)

    service.create_twin("dtmi:com:example:node;1")

    file_dto = service.add_file_object(
        path="artifact.step",
        media_type="application/step",
        version="1.0",
    )
    assert isinstance(file_dto["id"], int)
    assert file_dto["twin_dtmi"] is None

    attached = service.attach_file(file_dto["id"], "dtmi:com:example:node;1")
    assert attached["twin_dtmi"] == "dtmi:com:example:node;1"

    listed = service.list_file_objects()
    assert len(listed) == 1
    assert listed[0]["twin_dtmi"] == "dtmi:com:example:node;1"
    assert listed[0]["version"] == "1.0"
    assert listed[0]["media_type"] == "application/step"

    detached = service.detach_file(file_dto["id"])
    assert detached["twin_dtmi"] is None

    with pytest.raises(ValueError):
        service.attach_file(file_dto["id"], "dtmi:com:example:missing;1")

    updated = repo.update_file_object(
        file_dto["id"],
        version="2.0",
        media_type="application/x-step",
    )
    assert updated is not None
    assert updated.version == "2.0"
    assert updated.media_type == "application/x-step"

    listed2 = service.list_file_objects()
    assert listed2[0]["version"] == "2.0"
    assert listed2[0]["media_type"] == "application/x-step"

    session.close()
