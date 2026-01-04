from __future__ import annotations

from PySide6 import QtWidgets

from cymise.graph.service import GraphService


class PropertiesPanel(QtWidgets.QWidget):
    """Side panel for viewing/editing node/edge properties."""

    def __init__(self, graph_service: GraphService, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.graph_service = graph_service
        self.current_kind: str | None = None
        self.current_id: str | None = None

        self._node_group = self._build_node_form()
        self._edge_group = self._build_edge_form()

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self._node_group)
        layout.addWidget(self._edge_group)
        layout.addStretch(1)

        self._show_none()

    def _build_node_form(self) -> QtWidgets.QGroupBox:
        group = QtWidgets.QGroupBox("Node")
        form = QtWidgets.QFormLayout(group)
        self.node_dtmi = QtWidgets.QLineEdit()
        self.node_dtmi.setReadOnly(True)
        self.node_display = QtWidgets.QLineEdit()
        save_btn = QtWidgets.QPushButton("Save Node")
        save_btn.clicked.connect(self._save_node)

        form.addRow("DTMI", self.node_dtmi)
        form.addRow("Display Name", self.node_display)
        form.addRow(save_btn)
        return group

    def _build_edge_form(self) -> QtWidgets.QGroupBox:
        group = QtWidgets.QGroupBox("Edge")
        form = QtWidgets.QFormLayout(group)
        self.edge_id = QtWidgets.QLineEdit()
        self.edge_id.setReadOnly(True)
        self.edge_name = QtWidgets.QLineEdit()
        self.edge_source = QtWidgets.QLineEdit()
        self.edge_target = QtWidgets.QLineEdit()
        self.edge_source.setReadOnly(True)
        self.edge_target.setReadOnly(True)
        save_btn = QtWidgets.QPushButton("Save Edge")
        save_btn.clicked.connect(self._save_edge)

        form.addRow("Edge ID", self.edge_id)
        form.addRow("Name", self.edge_name)
        form.addRow("Source", self.edge_source)
        form.addRow("Target", self.edge_target)
        form.addRow(save_btn)
        return group

    def show_node(self, dtmi: str) -> None:
        node = self.graph_service.get_node(dtmi)
        if not node:
            self._show_none()
            return
        self.current_kind = "node"
        self.current_id = dtmi
        self.node_dtmi.setText(dtmi)
        self.node_display.setText(node.display_name or "")
        self._node_group.show()
        self._edge_group.hide()

    def show_edge(self, edge_id: str) -> None:
        try:
            edge_int = int(edge_id)
        except ValueError:
            self._show_none()
            return

        edge = self.graph_service.repo.get_relationship_by_id(edge_int)
        if not edge:
            self._show_none()
            return
        source = self.graph_service.repo.get_twin_by_id(edge.source_id)
        target = self.graph_service.repo.get_twin_by_id(edge.target_id)

        self.current_kind = "edge"
        self.current_id = edge_id
        self.edge_id.setText(edge_id)
        self.edge_name.setText(edge.name or "")
        self.edge_source.setText(source.dtmi if source else "")
        self.edge_target.setText(target.dtmi if target else "")
        self._node_group.hide()
        self._edge_group.show()

    def _save_node(self) -> None:
        if self.current_kind != "node" or not self.current_id:
            return
        display_name = self.node_display.text() or None
        self.graph_service.update_twin(self.current_id, display_name=display_name)

    def _save_edge(self) -> None:
        if self.current_kind != "edge" or not self.current_id:
            return
        try:
            edge_int = int(self.current_id)
        except ValueError:
            return
        name = self.edge_name.text() or None
        self.graph_service.update_relationship_name(edge_int, name)

    def _show_none(self) -> None:
        self.current_kind = None
        self.current_id = None
        self._node_group.hide()
        self._edge_group.hide()
