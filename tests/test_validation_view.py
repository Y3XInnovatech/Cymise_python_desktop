from __future__ import annotations

import pytest

pytest.importorskip("PySide6.QtWidgets")

from PySide6 import QtWidgets

from cymise.graph.service import GraphService
from cymise.store.db import create_db, get_engine, get_session
from cymise.store.repo import StoreRepository
from cymise.ui.views.validation_view import ValidationView, extract_validation_groups


@pytest.fixture
def service(tmp_path):
    engine = get_engine(tmp_path / "validation.db")
    create_db(engine)
    session = get_session(engine)
    repo = StoreRepository(session)
    svc = GraphService(repo)
    try:
        yield svc
    finally:
        session.close()


def test_extract_validation_groups(service: GraphService):
    service.create_twin("dtmi:com:example:node;1")
    service.create_twin("dtmi:com:example:node2;1")
    service.set_node_validation(
        "dtmi:com:example:node;1",
        {
            "issues": [
                {"severity": "error", "message": "bad", "code": "E1", "model_id": "dtmi:com:example:node;1"}
            ]
        },
    )
    service.set_node_validation(
        "dtmi:com:example:node2;1",
        {
            "issues": [
                {"severity": "warning", "message": "warn", "code": "dt_custom"},
            ],
            "category": "cymise",
        },
    )
    groups = extract_validation_groups(service)
    assert set(groups.keys()) == {"dtmi:com:example:node;1", "dtmi:com:example:node2;1"}
    node_rows = groups["dtmi:com:example:node;1"]
    assert node_rows[0].severity == "error"
    assert node_rows[0].category == "dtdl"
    node2_rows = groups["dtmi:com:example:node2;1"]
    assert node2_rows[0].category == "cymise"


def test_issue_activation_signal(service: GraphService):
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    service.create_twin("dtmi:com:example:node;1")
    service.set_node_validation(
        "dtmi:com:example:node;1",
        {"issues": [{"severity": "error", "message": "bad", "code": "E1", "model_id": "dtmi:com:example:node;1"}]},
    )
    view = ValidationView(service)
    view.refresh_from_store()

    # select first model to populate table
    model_item = view.models_list.item(0)
    view.models_list.setCurrentItem(model_item)
    # trigger double-click handler manually
    first_cell = view.issues_table.item(0, 0)
    captured = []

    def _capture(kind, element_id):
        captured.append((kind, element_id))

    view.issueActivated.connect(_capture)
    view._on_issue_activated(first_cell)

    assert captured == [("node", "dtmi:com:example:node;1")]
