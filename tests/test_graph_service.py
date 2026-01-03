from __future__ import annotations

import pytest

from cymise.graph.service import GraphService
from cymise.store.db import create_db, get_engine, get_session
from cymise.store.repo import StoreRepository


@pytest.fixture
def service(tmp_path):
    engine = get_engine(tmp_path / "graph.db")
    create_db(engine)
    session = get_session(engine)
    repo = StoreRepository(session)
    svc = GraphService(repo)
    try:
        yield svc
    finally:
        session.close()


def test_create_update_delete_twin(service: GraphService):
    node = service.create_twin("dtmi:com:example:thing;1", display_name="Thing")
    assert node.dtmi == "dtmi:com:example:thing;1"

    updated = service.update_twin(
        "dtmi:com:example:thing;1", display_name="Thing2", model_version="1.0.0"
    )
    assert updated.display_name == "Thing2"
    assert updated.model_version == "1.0.0"

    assert service.delete_twin("dtmi:com:example:thing;1") is True
    assert service.get_node("dtmi:com:example:thing;1") is None


def test_create_relationship_and_neighbors(service: GraphService):
    service.create_twin("dtmi:com:example:a;1", display_name="A")
    service.create_twin("dtmi:com:example:b;1", display_name="B")
    edge = service.create_relationship(
        "dtmi:com:example:a;1", "dtmi:com:example:b;1", name="relatesTo"
    )

    assert edge.source_dtmi == "dtmi:com:example:a;1"
    assert edge.target_dtmi == "dtmi:com:example:b;1"

    outgoing = service.get_outgoing_neighbors("dtmi:com:example:a;1")
    incoming = service.get_incoming_neighbors("dtmi:com:example:b;1")

    assert {n.dtmi for n in outgoing} == {"dtmi:com:example:b;1"}
    assert {n.dtmi for n in incoming} == {"dtmi:com:example:a;1"}


def test_get_subgraph(service: GraphService):
    service.create_twin("dtmi:com:example:a;1")
    service.create_twin("dtmi:com:example:b;1")
    service.create_twin("dtmi:com:example:c;1")
    service.create_twin("dtmi:com:example:d;1")

    service.create_relationship("dtmi:com:example:a;1", "dtmi:com:example:b;1")
    service.create_relationship("dtmi:com:example:b;1", "dtmi:com:example:c;1")
    service.create_relationship("dtmi:com:example:b;1", "dtmi:com:example:d;1")

    nodes_1, edges_1 = service.get_subgraph("dtmi:com:example:a;1", max_hops=1)
    assert {n.dtmi for n in nodes_1} == {"dtmi:com:example:a;1", "dtmi:com:example:b;1"}
    assert len(edges_1) == 1

    nodes_2, edges_2 = service.get_subgraph("dtmi:com:example:a;1", max_hops=2)
    assert {n.dtmi for n in nodes_2} == {
        "dtmi:com:example:a;1",
        "dtmi:com:example:b;1",
        "dtmi:com:example:c;1",
        "dtmi:com:example:d;1",
    }
    assert len(edges_2) == 3


def test_validation_payloads(service: GraphService):
    service.create_twin("dtmi:com:example:valnode;1")
    service.create_twin("dtmi:com:example:valnode2;1")
    edge = service.create_relationship(
        "dtmi:com:example:valnode;1", "dtmi:com:example:valnode2;1"
    )

    node_result = service.set_node_validation(
        "dtmi:com:example:valnode;1", {"severity": "warning"}
    )
    assert node_result.validation == {"severity": "warning"}
    assert service.get_node_validation("dtmi:com:example:valnode;1") == {
        "severity": "warning"
    }

    edge_result = service.set_edge_validation(edge.id, {"severity": "error"})
    assert edge_result.validation == {"severity": "error"}
    assert service.get_edge_validation(edge.id) == {"severity": "error"}


def test_create_relationship_missing_node_raises(service: GraphService):
    service.create_twin("dtmi:com:example:exists;1")
    with pytest.raises(ValueError):
        service.create_relationship(
            "dtmi:com:example:exists;1", "dtmi:com:example:missing;1"
        )


def test_get_subgraph_directionality(service: GraphService):
    service.create_twin("dtmi:com:example:a2;1")
    service.create_twin("dtmi:com:example:b2;1")
    service.create_twin("dtmi:com:example:c2;1")

    service.create_relationship("dtmi:com:example:a2;1", "dtmi:com:example:b2;1")
    service.create_relationship("dtmi:com:example:b2;1", "dtmi:com:example:c2;1")

    # Directed traversal from C should NOT walk back to B/A
    nodes_d, edges_d = service.get_subgraph("dtmi:com:example:c2;1", max_hops=2)
    assert {n.dtmi for n in nodes_d} == {"dtmi:com:example:c2;1"}
    assert edges_d == []

    # Undirected traversal from C should include neighborhood
    nodes_u, edges_u = service.get_subgraph(
        "dtmi:com:example:c2;1", max_hops=2, directed=False
    )
    assert {n.dtmi for n in nodes_u} == {
        "dtmi:com:example:a2;1",
        "dtmi:com:example:b2;1",
        "dtmi:com:example:c2;1",
    }
    assert len(edges_u) == 2
