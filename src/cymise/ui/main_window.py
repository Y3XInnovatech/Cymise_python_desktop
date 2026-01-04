from __future__ import annotations

from PySide6 import QtWidgets

from cymise.graph.service import GraphService

from .views.graph_view import GraphView
from .views.properties_panel import PropertiesPanel
from .views.validation_view import ValidationView


class MainWindow(QtWidgets.QMainWindow):
    """Minimal desktop shell with tabbed views."""

    def __init__(self, graph_service: GraphService):
        super().__init__()
        self.setWindowTitle("CyMiSE Desktop")

        self.tabs = QtWidgets.QTabWidget()
        self.tabs.addTab(self._build_graph_tab(graph_service), "Graph")
        self.validation_view = ValidationView(graph_service, parent=self)
        self.tabs.addTab(self._placeholder_tab("Artifacts"), "Artifacts")
        self.tabs.addTab(self.validation_view, "Validation")
        self.tabs.addTab(self._placeholder_tab("Impact"), "Impact")

        self.setCentralWidget(self.tabs)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.validation_view.issueActivated.connect(self._on_validation_issue_activated)
        self.validation_view.refresh_from_store(graph_service)

    def _build_graph_tab(self, graph_service: GraphService) -> QtWidgets.QWidget:
        container = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(container)

        button_row = QtWidgets.QHBoxLayout()
        add_node_btn = QtWidgets.QPushButton("Add Interface")
        add_edge_btn = QtWidgets.QPushButton("Add Relationship")
        button_row.addWidget(add_node_btn)
        button_row.addWidget(add_edge_btn)
        button_row.addStretch(1)
        layout.addLayout(button_row)

        splitter = QtWidgets.QSplitter()
        self.graph_view = GraphView(graph_service, parent=container)
        self.properties_panel = PropertiesPanel(graph_service, parent=container)
        splitter.addWidget(self.graph_view)
        splitter.addWidget(self.properties_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter)

        add_node_btn.clicked.connect(self._add_interface)
        add_edge_btn.clicked.connect(self._add_relationship)
        self.graph_view.selectionChanged.connect(self._on_selection_changed)

        return container

    def _placeholder_tab(self, label: str) -> QtWidgets.QWidget:
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.addWidget(QtWidgets.QLabel(f"{label} view coming soon"))
        layout.addStretch(1)
        return widget

    def _on_selection_changed(self, element_id: str, kind: str) -> None:
        if kind == "node":
            self.properties_panel.show_node(element_id)
        elif kind == "edge":
            self.properties_panel.show_edge(element_id)

    def _add_interface(self) -> None:
        dtmi, ok = QtWidgets.QInputDialog.getText(self, "Add Interface", "DTMI:")
        if not ok or not dtmi:
            return
        display_name, _ = QtWidgets.QInputDialog.getText(self, "Add Interface", "Display Name:")
        self.graph_view.graph_service.create_twin(dtmi, display_name=display_name or None)
        self.graph_view.update_nodes(
            [
                {
                    "id": dtmi,
                    "label": display_name or dtmi,
                    "validation": {},
                }
            ]
        )

    def _add_relationship(self) -> None:
        selected = (
            self.properties_panel.current_id
            if self.properties_panel.current_kind == "node"
            else None
        )
        source, target = None, None
        if selected:
            source = selected
            target, ok = QtWidgets.QInputDialog.getText(
                self, "Add Relationship", "Target DTMI:"
            )
            if not ok or not target:
                return
        else:
            source, ok = QtWidgets.QInputDialog.getText(
                self, "Add Relationship", "Source DTMI:"
            )
            if not ok or not source:
                return
            target, ok = QtWidgets.QInputDialog.getText(
                self, "Add Relationship", "Target DTMI:"
            )
            if not ok or not target:
                return

        name, _ = QtWidgets.QInputDialog.getText(self, "Add Relationship", "Name:")
        edge = self.graph_view.graph_service.create_relationship(
            source, target, name=name or None
        )
        self.graph_view.update_edges(
            [
                {
                    "id": str(edge.id),
                    "source": source,
                    "target": target,
                    "label": name or "",
                    "validation": {},
                }
            ]
        )

    def _on_tab_changed(self, index: int) -> None:
        if self.tabs.widget(index) is self.validation_view:
            self.validation_view.refresh_from_store(self.graph_view.graph_service)

    def _on_validation_issue_activated(self, kind: str, element_id: str) -> None:
        self.tabs.setCurrentIndex(0)
        if kind == "node":
            self.properties_panel.show_node(element_id)
            self.graph_view.select_element("node", element_id)
        elif kind == "edge":
            self.properties_panel.show_edge(element_id)
            self.graph_view.select_element("edge", element_id)
