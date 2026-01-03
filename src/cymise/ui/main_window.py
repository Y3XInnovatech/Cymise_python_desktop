from __future__ import annotations

from PySide6 import QtWidgets

from cymise.graph.service import GraphService

from .views.graph_view import GraphView


class MainWindow(QtWidgets.QMainWindow):
    """Minimal desktop shell with tabbed views."""

    def __init__(self, graph_service: GraphService):
        super().__init__()
        self.setWindowTitle("CyMiSE Desktop")

        tabs = QtWidgets.QTabWidget()
        tabs.addTab(GraphView(graph_service, parent=self), "Graph")
        tabs.addTab(self._placeholder_tab("Artifacts"), "Artifacts")
        tabs.addTab(self._placeholder_tab("Validation"), "Validation")
        tabs.addTab(self._placeholder_tab("Impact"), "Impact")

        self.setCentralWidget(tabs)

    def _placeholder_tab(self, label: str) -> QtWidgets.QWidget:
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.addWidget(QtWidgets.QLabel(f"{label} view coming soon"))
        layout.addStretch(1)
        return widget
