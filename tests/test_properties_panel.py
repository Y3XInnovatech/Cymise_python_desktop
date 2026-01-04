from __future__ import annotations

import pytest

pytest.importorskip("PySide6.QtWidgets")

from PySide6 import QtWidgets

from cymise.graph.service import GraphService
from cymise.store.db import create_db, get_engine, get_session
from cymise.store.repo import StoreRepository
from cymise.ui.views.properties_panel import PropertiesPanel


@pytest.fixture
def service(tmp_path):
    engine = get_engine(tmp_path / "props.db")
    create_db(engine)
    session = get_session(engine)
    repo = StoreRepository(session)
    svc = GraphService(repo)
    try:
        yield svc
    finally:
        session.close()


def test_properties_panel_load_and_save_node(service: GraphService):
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    service.create_twin("dtmi:com:example:node;1", display_name="Old")
    panel = PropertiesPanel(service)

    panel.show_node("dtmi:com:example:node;1")
    panel.node_display.setText("New Name")
    panel._save_node()

    updated = service.get_node("dtmi:com:example:node;1")
    assert updated.display_name == "New Name"


def test_properties_panel_load_and_save_edge(service: GraphService):
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    service.create_twin("dtmi:com:example:a;1")
    service.create_twin("dtmi:com:example:b;1")
    edge = service.create_relationship(
        "dtmi:com:example:a;1", "dtmi:com:example:b;1", name="old"
    )
    panel = PropertiesPanel(service)

    panel.show_edge(str(edge.id))
    panel.edge_name.setText("new")
    panel._save_edge()

    updated = service.update_relationship_name(edge.id, "new")
    assert updated.name == "new"
