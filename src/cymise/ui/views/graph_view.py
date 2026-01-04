from __future__ import annotations

import json
from pathlib import Path

from PySide6 import QtCore, QtWebChannel, QtWebEngineWidgets, QtWidgets

from cymise.graph.service import GraphService

from ..web.graph_canvas_bridge import GraphCanvasBridge


class GraphView(QtWidgets.QWidget):
    """Graph tab hosting the WebEngine canvas."""

    selectionChanged = QtCore.Signal(str, str)  # id, kind ("node"|"edge")

    def __init__(self, graph_service: GraphService, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.graph_service = graph_service

        layout = QtWidgets.QVBoxLayout(self)
        self._view = QtWebEngineWidgets.QWebEngineView(self)
        layout.addWidget(self._view)

        self._bridge = GraphCanvasBridge()
        self._channel = QtWebChannel.QWebChannel(self._view.page())
        self._channel.registerObject("bridge", self._bridge)
        self._view.page().setWebChannel(self._channel)

        self._bridge.graph_requested.connect(self._send_graph_data)
        self._bridge.selection_changed.connect(self._on_selection_changed)
        self._view.loadFinished.connect(self._on_load_finished)
        self._load_canvas()

    def _load_canvas(self) -> None:
        html_path = Path(__file__).resolve().parent.parent / "web" / "graph_canvas.html"
        url = QtCore.QUrl.fromLocalFile(str(html_path))
        self._view.setUrl(url)

    def _on_load_finished(self, ok: bool) -> None:
        if not ok:
            return
        # Demonstrate Python -> JS call (not asserted in tests to avoid WebEngine flakiness).
        self._view.page().runJavaScript("window.cymiseReceive && window.cymiseReceive('pong')")
        self._send_graph_data()

    def _send_graph_data(self) -> None:
        payload = build_graph_payload(self.graph_service)
        self._bridge.graph_data.emit(payload)

    def _on_selection_changed(self, element_id: str, kind: str) -> None:
        self.selectionChanged.emit(element_id, kind)

    def update_nodes(self, nodes: list[dict]) -> None:
        self._run_js("window.cyUpdateNodes && window.cyUpdateNodes", nodes)

    def update_edges(self, edges: list[dict]) -> None:
        self._run_js("window.cyUpdateEdges && window.cyUpdateEdges", edges)

    def remove_nodes(self, node_ids: list[str]) -> None:
        self._run_js("window.cyRemoveNodes && window.cyRemoveNodes", node_ids)

    def remove_edges(self, edge_ids: list[str]) -> None:
        self._run_js("window.cyRemoveEdges && window.cyRemoveEdges", edge_ids)

    def apply_validation_styles(self, mapping: dict[str, str]) -> None:
        self._run_js("window.cyApplyValidation && window.cyApplyValidation", mapping)

    def _run_js(self, func_prefix: str, payload: object) -> None:
        try:
            encoded = json.dumps(payload)
        except (TypeError, ValueError):
            return
        self._view.page().runJavaScript(f"{func_prefix}({encoded});")


def build_graph_payload(graph_service: GraphService) -> dict:
    nodes = graph_service.list_nodes()
    edges = graph_service.repo.list_relationships()

    node_payloads = [
        {
            "id": node.dtmi,
            "label": node.display_name or node.dtmi,
            "validation": node.validation or {},
        }
        for node in nodes
    ]

    edge_payloads = []
    for edge in edges:
        source = graph_service.repo.get_twin_by_id(edge.source_id)
        target = graph_service.repo.get_twin_by_id(edge.target_id)
        if not source or not target:
            continue
        edge_payloads.append(
            {
                "id": str(edge.id),
                "source": source.dtmi,
                "target": target.dtmi,
                "label": edge.name or "",
                "validation": edge.validation or {},
            }
        )

    return {"nodes": node_payloads, "edges": edge_payloads}
