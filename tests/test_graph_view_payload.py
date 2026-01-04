from __future__ import annotations

import pytest

pytest.importorskip("PySide6.QtWidgets")

from cymise.graph.service import GraphService
from cymise.store.db import create_db, get_engine, get_session
from cymise.store.repo import StoreRepository
from cymise.ui.views.graph_view import build_graph_payload


@pytest.fixture
def service(tmp_path):
    engine = get_engine(tmp_path / "graphview.db")
    create_db(engine)
    session = get_session(engine)
    repo = StoreRepository(session)
    svc = GraphService(repo)
    try:
        yield svc
    finally:
        session.close()


def test_build_graph_payload(service: GraphService):
    service.create_twin("dtmi:com:example:a;1", display_name="A")
    service.create_twin("dtmi:com:example:b;1", display_name="B")
    edge = service.create_relationship(
        "dtmi:com:example:a;1", "dtmi:com:example:b;1", name="rel"
    )
    service.set_node_validation("dtmi:com:example:a;1", {"severity": "warning"})

    payload = build_graph_payload(service)

    node_ids = {n["id"] for n in payload["nodes"]}
    assert node_ids == {"dtmi:com:example:a;1", "dtmi:com:example:b;1"}
    a_node = next(n for n in payload["nodes"] if n["id"] == "dtmi:com:example:a;1")
    assert a_node["label"] == "A"
    assert a_node["validation"] == {"severity": "warning"}

    assert payload["edges"][0]["id"] == str(edge.id)
    assert payload["edges"][0]["source"] == "dtmi:com:example:a;1"
    assert payload["edges"][0]["target"] == "dtmi:com:example:b;1"
