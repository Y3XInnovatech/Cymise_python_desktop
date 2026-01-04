from __future__ import annotations

from PySide6 import QtCore


class GraphCanvasBridge(QtCore.QObject):
    """Qt bridge exposed to JS via QWebChannel."""

    pong = QtCore.Signal(str)
    graph_data = QtCore.Signal(dict)
    graph_requested = QtCore.Signal()
    selection_changed = QtCore.Signal(str, str)  # id, kind ("node"|"edge")
    selection_changed_qt = selection_changed  # alias for Qt Designer friendliness

    @QtCore.Slot(str, result=str)
    def ping(self, payload: str) -> str:
        """Receive ping from JS and emit pong response."""
        message = f"pong:{payload}"
        self.pong.emit(message)
        return message

    @QtCore.Slot()
    def request_graph(self) -> None:
        """JS requests the latest graph data."""
        self.graph_requested.emit()

    @QtCore.Slot(str, str)
    def select_element(self, element_id: str, kind: str) -> None:
        """JS notifies Python about a selected node/edge."""
        self.selection_changed.emit(element_id, kind)
